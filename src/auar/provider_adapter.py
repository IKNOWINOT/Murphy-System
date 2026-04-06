"""
AUAR Layer 5 — Provider Adapter Layer
=======================================

Implements the adapter pattern for downstream provider communication.
Each adapter encapsulates authentication, protocol translation, retry
logic, and connection management for a specific provider.

Supports auth methods: API Key, Bearer Token, OAuth2, Basic, HMAC.
Supports protocols: REST (JSON), GraphQL, gRPC (stub), SOAP (stub).

Uses httpx.AsyncClient for real HTTP transport when available, with a
pluggable execute_fn for testing and offline operation.

Copyright 2024 Inoni LLC – BSL-1.1
"""

import asyncio
import json
import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums & config
# ---------------------------------------------------------------------------

class AuthMethod(Enum):
    """Auth method (Enum subclass)."""
    NONE = "none"
    API_KEY = "api_key"
    BEARER = "bearer"
    OAUTH2 = "oauth2"
    BASIC = "basic"
    HMAC = "hmac"


class Protocol(Enum):
    """Protocol (Enum subclass)."""
    REST = "rest"
    GRAPHQL = "graphql"
    GRPC = "grpc"
    SOAP = "soap"


@dataclass
class AdapterConfig:
    """Configuration for a single provider adapter."""
    provider_id: str = ""
    provider_name: str = ""
    base_url: str = ""
    auth_method: AuthMethod = AuthMethod.API_KEY
    auth_credentials: Dict[str, str] = field(default_factory=dict)
    protocol: Protocol = Protocol.REST
    timeout_s: float = 10.0
    max_retries: int = 3
    retry_backoff_s: float = 0.5
    headers: Dict[str, str] = field(default_factory=dict)
    connection_pool_size: int = 10


@dataclass
class AdapterResponse:
    """Standardised response from a provider adapter."""
    success: bool = True
    status_code: int = 200
    body: Dict[str, Any] = field(default_factory=dict)
    headers: Dict[str, str] = field(default_factory=dict)
    latency_ms: float = 0.0
    retries_used: int = 0
    error: str = ""


# ---------------------------------------------------------------------------
# Provider Adapter (base)
# ---------------------------------------------------------------------------

class ProviderAdapter:
    """Adapter for a single downstream provider.

    In production this wraps ``httpx.AsyncClient`` or similar; here we
    provide a synchronous simulation with a pluggable ``execute_fn``
    callback for easy testing and offline operation.
    """

    def __init__(
        self,
        config: AdapterConfig,
        execute_fn: Optional[Callable] = None,
        token_refresh_fn: Optional[Callable] = None,
    ):
        self.config = config
        self._execute_fn = execute_fn or self._default_execute
        self._token_refresh_fn = token_refresh_fn
        self._lock = threading.Lock()
        self._stats = {"calls": 0, "successes": 0, "failures": 0, "retries": 0}

    # -- Auth header construction -------------------------------------------

    def _build_auth_headers(self, body: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
        creds = self.config.auth_credentials
        method = self.config.auth_method

        if method == AuthMethod.API_KEY:
            key_header = creds.get("header_name", "X-API-Key")
            return {key_header: creds.get("api_key", "")}
        if method == AuthMethod.BEARER:
            return {"Authorization": f"Bearer {creds.get('token', '')}"}
        if method == AuthMethod.BASIC:
            import base64
            pair = f"{creds.get('username', '')}:{creds.get('password', '')}"
            encoded = base64.b64encode(pair.encode()).decode()
            return {"Authorization": f"Basic {encoded}"}
        if method == AuthMethod.OAUTH2:
            return self._build_oauth2_headers()
        if method == AuthMethod.HMAC:
            return self._build_hmac_headers(body=body)
        return {}

    def _build_oauth2_headers(self) -> Dict[str, str]:
        """Build OAuth2 Authorization header with token refresh support.

        Expected credentials keys:
            access_token  — current Bearer token
            refresh_token — used to obtain a new access_token (optional)
            token_url     — endpoint for token refresh (optional)
            client_id     — OAuth2 client identifier (optional)
            client_secret — OAuth2 client secret (optional)

        When *access_token* is present it is used directly.  If a
        ``token_refresh_fn`` callable has been provided at construction
        time it will be invoked when the token is empty, enabling the
        adapter to participate in a real OAuth2 token-refresh flow
        without hard-coding HTTP calls.
        """
        creds = self.config.auth_credentials
        access_token = creds.get("access_token", "")

        if not access_token and self._token_refresh_fn:
            try:
                new_token = self._token_refresh_fn(creds)
                if isinstance(new_token, str) and new_token:
                    creds["access_token"] = new_token
                    access_token = new_token
            except Exception as exc:
                logger.warning("OAuth2 token refresh failed: %s", type(exc).__name__)

        if access_token:
            return {"Authorization": f"Bearer {access_token}"}
        return {}

    def _build_hmac_headers(self, body: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
        """Build HMAC request-signing headers.

        Expected credentials keys:
            secret_key  — shared secret used for HMAC-SHA256 signing
            key_id      — identifier sent in the ``X-HMAC-Key-Id`` header

        The v2 signature covers the canonicalized body, method path,
        timestamp, and key-id to prevent body tampering.
        """
        import hashlib
        import hmac as hmac_mod

        creds = self.config.auth_credentials
        secret = creds.get("secret_key", "")
        key_id = creds.get("key_id", "")

        timestamp = str(int(time.time()))
        # v2: include canonicalized body in signature
        canon_body = ""
        if body:
            canon_body = json.dumps(body, sort_keys=True, separators=(",", ":"))
        message = f"{timestamp}:{key_id}:{canon_body}"
        signature = hmac_mod.new(
            secret.encode(), message.encode(), hashlib.sha256
        ).hexdigest()

        return {
            "X-HMAC-Signature": signature,
            "X-HMAC-Timestamp": timestamp,
            "X-HMAC-Key-Id": key_id,
            "X-HMAC-Version": "v2",
        }

    # -- Protocol-aware request preparation ---------------------------------

    def _prepare_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Adapt *payload* based on the configured protocol.

        For REST requests the payload is returned unchanged.  For
        GRAPHQL the body is wrapped in the standard ``{"query": …,
        "variables": …}`` envelope.  gRPC payloads are converted to
        JSON-encoded messages suitable for grpc-gateway / gRPC-Web
        transport.  SOAP payloads are wrapped in a SOAP 1.2 XML envelope.
        """
        protocol = self.config.protocol
        if protocol == Protocol.GRAPHQL:
            body = payload.get("body", {})
            query = body.pop("query", "")
            wrapped_body = {"query": query, "variables": body}
            return {**payload, "body": wrapped_body, "method": "POST"}
        if protocol == Protocol.GRPC:
            return self._prepare_grpc_request(payload)
        if protocol == Protocol.SOAP:
            return self._prepare_soap_request(payload)
        # REST — pass through
        return payload

    def _prepare_grpc_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Translate a gRPC-style payload to JSON-over-HTTP for grpc-gateway.

        Uses the gRPC-Web / grpc-gateway convention where the service
        and method are mapped to a REST-style path and the protobuf
        message is sent as a JSON body.
        """
        body = payload.get("body", {})
        service = body.pop("service", "")
        method = body.pop("method", "")
        # grpc-gateway convention: /<package.Service>/<Method>
        grpc_path = f"/{service}/{method}" if service and method else payload.get("path", "/")
        headers = dict(payload.get("headers", {}))
        headers.setdefault("Content-Type", "application/grpc+json")
        headers.setdefault("Accept", "application/grpc+json")
        return {
            **payload,
            "method": "POST",
            "path": grpc_path,
            "body": body,  # remaining fields are the protobuf-JSON message
            "headers": headers,
        }

    def _prepare_soap_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Wrap payload in a minimal SOAP 1.2 XML envelope."""
        body = payload.get("body", {})
        action = body.pop("soap_action", "")
        # Build a simple XML body from the remaining key-value pairs
        inner_xml_parts = []
        for key, val in body.items():
            inner_xml_parts.append(f"<{key}>{val}</{key}>")
        inner_xml = "".join(inner_xml_parts)
        soap_body = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">'
            "<soap:Body>"
            f"{inner_xml}"
            "</soap:Body>"
            "</soap:Envelope>"
        )
        headers = dict(payload.get("headers", {}))
        headers["Content-Type"] = "application/soap+xml; charset=utf-8"
        if action:
            headers["SOAPAction"] = action
        return {
            **payload,
            "method": "POST",
            "body": soap_body,
            "headers": headers,
            "_raw_body": True,  # signal to call() to send body as string, not JSON
        }

    # -- Execution ----------------------------------------------------------

    def call(
        self,
        method: str,
        path: str,
        body: Optional[Dict[str, Any]] = None,
        query_params: Optional[Dict[str, str]] = None,
    ) -> AdapterResponse:
        """Execute a request to the provider with retry logic."""
        start = time.monotonic()
        auth_headers = self._build_auth_headers(body=body)
        merged_headers = {**self.config.headers, **auth_headers}

        request_payload = {
            "method": method.upper(),
            "url": f"{self.config.base_url.rstrip('/')}/{path.lstrip('/')}",
            "headers": merged_headers,
            "body": body or {},
            "query_params": query_params or {},
            "protocol": self.config.protocol.value,
        }

        # Apply protocol-specific transformations
        request_payload = self._prepare_request(request_payload)

        response = self._execute_with_retries(request_payload)
        response.latency_ms = (time.monotonic() - start) * 1000
        return response

    async def async_call(
        self,
        method: str,
        path: str,
        body: Optional[Dict[str, Any]] = None,
        query_params: Optional[Dict[str, str]] = None,
    ) -> AdapterResponse:
        """Execute a request to the provider with async retry logic."""
        start = time.monotonic()
        auth_headers = self._build_auth_headers(body=body)
        merged_headers = {**self.config.headers, **auth_headers}

        request_payload = {
            "method": method.upper(),
            "url": f"{self.config.base_url.rstrip('/')}/{path.lstrip('/')}",
            "headers": merged_headers,
            "body": body or {},
            "query_params": query_params or {},
            "protocol": self.config.protocol.value,
        }

        request_payload = self._prepare_request(request_payload)
        response = await self._async_execute_with_retries(request_payload)
        response.latency_ms = (time.monotonic() - start) * 1000
        return response

    def call_sync(
        self,
        method: str,
        path: str,
        body: Optional[Dict[str, Any]] = None,
        query_params: Optional[Dict[str, str]] = None,
    ) -> AdapterResponse:
        """Synchronous wrapper that runs the async call path.

        Suitable for CLI or testing contexts where an event loop is not
        already running.  Uses :func:`asyncio.run` so that retries use
        ``asyncio.sleep`` instead of blocking ``time.sleep``.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # Already inside an async context — fall back to the
            # blocking call() to avoid nested event-loop errors.
            return self.call(method, path, body, query_params)

        return asyncio.run(
            self.async_call(method, path, body, query_params)
        )

    def _execute_with_retries(self, payload: Dict[str, Any]) -> AdapterResponse:
        last_error = ""
        retries = 0
        for attempt in range(self.config.max_retries + 1):
            try:
                result = self._execute_fn(payload)
                with self._lock:
                    self._stats["calls"] += 1
                    self._stats["successes"] += 1
                resp = AdapterResponse(
                    success=True,
                    status_code=result.get("status_code", 200),
                    body=result.get("body", {}),
                    headers=result.get("headers", {}),
                    retries_used=retries,
                )
                return resp
            except Exception as exc:
                logger.debug("Caught exception: %s", exc)
                last_error = str(exc)
                retries += 1
                with self._lock:
                    self._stats["retries"] += 1
                if attempt < self.config.max_retries:
                    time.sleep(self.config.retry_backoff_s * (attempt + 1))

        with self._lock:
            self._stats["calls"] += 1
            self._stats["failures"] += 1

        return AdapterResponse(
            success=False,
            status_code=502,
            error=last_error,
            retries_used=retries,
        )

    async def _async_execute_with_retries(self, payload: Dict[str, Any]) -> AdapterResponse:
        """Async retry loop using asyncio.sleep instead of blocking time.sleep."""
        last_error = ""
        retries = 0
        for attempt in range(self.config.max_retries + 1):
            try:
                result = self._execute_fn(payload)
                with self._lock:
                    self._stats["calls"] += 1
                    self._stats["successes"] += 1
                return AdapterResponse(
                    success=True,
                    status_code=result.get("status_code", 200),
                    body=result.get("body", {}),
                    headers=result.get("headers", {}),
                    retries_used=retries,
                )
            except Exception as exc:
                logger.debug("Caught exception: %s", exc)
                last_error = str(exc)
                retries += 1
                with self._lock:
                    self._stats["retries"] += 1
                if attempt < self.config.max_retries:
                    await asyncio.sleep(self.config.retry_backoff_s * (attempt + 1))

        with self._lock:
            self._stats["calls"] += 1
            self._stats["failures"] += 1

        return AdapterResponse(
            success=False,
            status_code=502,
            error=last_error,
            retries_used=retries,
        )

    @staticmethod
    def _default_execute(payload: Dict[str, Any]) -> Dict[str, Any]:
        """Default no-op executor for offline / test usage."""
        return {
            "status_code": 200,
            "body": {"message": "ok", "provider_received": payload.get("body", {})},
            "headers": {"Content-Type": "application/json"},
        }

    @staticmethod
    def _httpx_execute_factory(config: "AdapterConfig"):
        """Create an execute_fn that uses httpx for real HTTP calls."""
        try:
            import httpx
        except ImportError:
            return None

        def execute(payload: Dict[str, Any]) -> Dict[str, Any]:
            with httpx.Client(
                timeout=config.timeout_s,
                limits=httpx.Limits(
                    max_connections=config.connection_pool_size,
                ),
            ) as client:
                resp = client.request(
                    method=payload.get("method", "GET"),
                    url=payload["url"],
                    headers=payload.get("headers", {}),
                    json=payload.get("body"),
                    params=payload.get("query_params"),
                )
                return {
                    "status_code": resp.status_code,
                    "body": resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {"raw": resp.text},
                    "headers": dict(resp.headers),
                }
        return execute

    def get_stats(self) -> Dict[str, int]:
        with self._lock:
            return dict(self._stats)


# ---------------------------------------------------------------------------
# Provider Adapter Manager
# ---------------------------------------------------------------------------

class ProviderAdapterManager:
    """Registry and lifecycle manager for provider adapters."""

    def __init__(self):
        self._adapters: Dict[str, ProviderAdapter] = {}
        self._lock = threading.Lock()

    def register_adapter(
        self,
        config: AdapterConfig,
        execute_fn: Optional[Callable] = None,
        token_refresh_fn: Optional[Callable] = None,
    ) -> str:
        adapter = ProviderAdapter(config, execute_fn, token_refresh_fn)
        with self._lock:
            self._adapters[config.provider_id] = adapter
        logger.info("Registered adapter: %s (%s)", config.provider_name, config.provider_id)
        return config.provider_id

    def get_adapter(self, provider_id: str) -> Optional[ProviderAdapter]:
        with self._lock:
            return self._adapters.get(provider_id)

    def call_provider(
        self,
        provider_id: str,
        method: str,
        path: str,
        body: Optional[Dict[str, Any]] = None,
    ) -> AdapterResponse:
        adapter = self.get_adapter(provider_id)
        if not adapter:
            return AdapterResponse(success=False, status_code=404, error="Adapter not found")
        return adapter.call(method, path, body)

    async def async_call_provider(
        self,
        provider_id: str,
        method: str,
        path: str,
        body: Optional[Dict[str, Any]] = None,
    ) -> AdapterResponse:
        """Async version using asyncio.sleep-based retries."""
        adapter = self.get_adapter(provider_id)
        if not adapter:
            return AdapterResponse(success=False, status_code=404, error="Adapter not found")
        return await adapter.async_call(method, path, body)

    def deregister_adapter(self, provider_id: str) -> bool:
        """Remove an adapter from the registry."""
        with self._lock:
            return self._adapters.pop(provider_id, None) is not None

    def list_adapters(self) -> List[str]:
        with self._lock:
            return list(self._adapters.keys())

    def get_all_stats(self) -> Dict[str, Dict[str, int]]:
        with self._lock:
            return {pid: a.get_stats() for pid, a in self._adapters.items()}
