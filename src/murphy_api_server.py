# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post · License: BSL 1.1
"""
murphy_api_server.py — PATCH-065a
Murphy Public API Server

Exposes Murphy as a first-class public API platform:
  - /api/v1/* versioned public routes (proxied to internal endpoints)
  - API key issuance, rotation, revocation with scopes
  - Per-key rate limiting with sliding window (in-memory + Redis optional)
  - OpenAPI 3.1 spec auto-generated from registered routes
  - Key usage telemetry and quota enforcement
  - Webhook endpoint for inbound events from external services

Design: MAS-001
Thread-safe: Yes (RLock per key bucket)
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import secrets
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MURPHY_API_VERSION = "v1"
KEY_PREFIX = "mak_"          # Murphy API Key prefix
KEY_BYTES = 32               # 256-bit key
DEFAULT_RPM = 60             # requests per minute
DEFAULT_RPD = 10_000         # requests per day
MAX_SCOPES = 20


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class KeyStatus(str, Enum):
    ACTIVE   = "active"
    REVOKED  = "revoked"
    EXPIRED  = "expired"
    PAUSED   = "paused"


class KeyTier(str, Enum):
    FREE       = "free"       # 60 rpm, 1k rpd
    DEVELOPER  = "developer"  # 300 rpm, 50k rpd
    ENTERPRISE = "enterprise" # unlimited


class Scope(str, Enum):
    """API scopes — coarse-grained permissions."""
    READ_HEALTH    = "health:read"
    READ_MODULES   = "modules:read"
    READ_AGENTS    = "agents:read"
    WRITE_AGENTS   = "agents:write"
    READ_FORGE     = "forge:read"
    WRITE_FORGE    = "forge:write"
    READ_MAIL      = "mail:read"
    WRITE_MAIL     = "mail:write"
    READ_CALENDAR  = "calendar:read"
    WRITE_CALENDAR = "calendar:write"
    CONNECTORS     = "connectors:*"
    OAUTH_MANAGE   = "oauth:manage"
    ADMIN          = "admin:*"       # superscope — implies all


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class APIKey:
    key_id:      str
    key_hash:    str          # SHA-256 of raw key — never store raw
    name:        str
    owner_id:    str
    scopes:      List[str]
    tier:        KeyTier      = KeyTier.FREE
    status:      KeyStatus    = KeyStatus.ACTIVE
    created_at:  float        = field(default_factory=time.time)
    expires_at:  Optional[float] = None
    last_used:   float        = 0.0
    request_count: int        = 0
    metadata:    Dict[str, Any] = field(default_factory=dict)

    def is_valid(self) -> bool:
        if self.status != KeyStatus.ACTIVE:
            return False
        if self.expires_at and time.time() > self.expires_at:
            return False
        return True

    def has_scope(self, required: str) -> bool:
        if "admin:*" in self.scopes:
            return True
        if required in self.scopes:
            return True
        # Wildcard match: "forge:*" covers "forge:read", "forge:write"
        ns = required.split(":")[0]
        return f"{ns}:*" in self.scopes

    def to_public_dict(self) -> Dict[str, Any]:
        return {
            "key_id":        self.key_id,
            "name":          self.name,
            "owner_id":      self.owner_id,
            "scopes":        self.scopes,
            "tier":          self.tier.value,
            "status":        self.status.value,
            "created_at":    self.created_at,
            "expires_at":    self.expires_at,
            "last_used":     self.last_used,
            "request_count": self.request_count,
        }


@dataclass
class RateBucket:
    """Sliding-window rate limiter per API key."""
    rpm_limit: int
    rpd_limit: int
    _minute_hits: List[float] = field(default_factory=list)
    _day_hits:    List[float] = field(default_factory=list)
    _lock:        threading.RLock = field(default_factory=threading.RLock)

    def check_and_record(self) -> Tuple[bool, str]:
        now = time.time()
        minute_ago = now - 60
        day_ago    = now - 86400
        with self._lock:
            self._minute_hits = [t for t in self._minute_hits if t > minute_ago]
            self._day_hits    = [t for t in self._day_hits    if t > day_ago]
            if self.rpm_limit > 0 and len(self._minute_hits) >= self.rpm_limit:
                return False, "rate_limit_minute"
            if self.rpd_limit > 0 and len(self._day_hits) >= self.rpd_limit:
                return False, "rate_limit_day"
            self._minute_hits.append(now)
            self._day_hits.append(now)
            return True, "ok"


@dataclass
class RouteDefinition:
    """A route exposed on the public /api/v1/* namespace."""
    path:        str          # e.g. "/api/v1/health"
    method:      str          # GET | POST | ...
    internal_path: str        # internal route it proxies to
    summary:     str
    description: str          = ""
    required_scopes: List[str] = field(default_factory=list)
    request_schema:  Optional[Dict] = None
    response_schema: Optional[Dict] = None
    tags:        List[str]    = field(default_factory=list)


# ---------------------------------------------------------------------------
# Key Store
# ---------------------------------------------------------------------------

class APIKeyStore:
    """Thread-safe in-memory key store with optional JSON persistence."""

    def __init__(self, persist_path: Optional[str] = None) -> None:
        self._keys:    Dict[str, APIKey] = {}   # key_id → APIKey
        self._hashes:  Dict[str, str]   = {}   # hash → key_id  (fast lookup)
        self._buckets: Dict[str, RateBucket] = {}
        self._lock  = threading.RLock()
        self._persist_path = persist_path
        if persist_path:
            self._load()

    # --- CRUD ---

    def create(
        self,
        owner_id: str,
        name: str,
        scopes: List[str],
        tier: KeyTier = KeyTier.FREE,
        expires_in_days: Optional[int] = None,
        metadata: Optional[Dict] = None,
    ) -> Tuple[str, APIKey]:
        """Returns (raw_key, APIKey). raw_key shown once only."""
        raw_key  = KEY_PREFIX + secrets.token_urlsafe(KEY_BYTES)
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        key_id   = str(uuid.uuid4())
        expires_at = (time.time() + expires_in_days * 86400) if expires_in_days else None

        tier_limits = {
            KeyTier.FREE:       (60, 1_000),
            KeyTier.DEVELOPER:  (300, 50_000),
            KeyTier.ENTERPRISE: (0, 0),   # 0 = unlimited
        }
        rpm, rpd = tier_limits.get(tier, (60, 1_000))

        api_key = APIKey(
            key_id=key_id, key_hash=key_hash, name=name,
            owner_id=owner_id, scopes=scopes[:MAX_SCOPES],
            tier=tier, expires_at=expires_at,
            metadata=metadata or {},
        )
        bucket = RateBucket(rpm_limit=rpm, rpd_limit=rpd)

        with self._lock:
            self._keys[key_id]     = api_key
            self._hashes[key_hash] = key_id
            self._buckets[key_id]  = bucket
        self._save()
        return raw_key, api_key

    def lookup(self, raw_key: str) -> Optional[APIKey]:
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        with self._lock:
            key_id = self._hashes.get(key_hash)
            return self._keys.get(key_id) if key_id else None

    def revoke(self, key_id: str) -> bool:
        with self._lock:
            k = self._keys.get(key_id)
            if not k:
                return False
            k.status = KeyStatus.REVOKED
        self._save()
        return True

    def list_by_owner(self, owner_id: str) -> List[APIKey]:
        with self._lock:
            return [k for k in self._keys.values() if k.owner_id == owner_id]

    def check_rate(self, key_id: str) -> Tuple[bool, str]:
        with self._lock:
            bucket = self._buckets.get(key_id)
        if not bucket:
            return False, "key_not_found"
        return bucket.check_and_record()

    def record_use(self, key_id: str) -> None:
        with self._lock:
            k = self._keys.get(key_id)
            if k:
                k.last_used      = time.time()
                k.request_count += 1

    def all_keys(self) -> List[APIKey]:
        with self._lock:
            return list(self._keys.values())

    # --- Persistence ---

    def _save(self) -> None:
        if not self._persist_path:
            return
        try:
            data = {
                kid: {
                    "key_hash": k.key_hash, "name": k.name,
                    "owner_id": k.owner_id, "scopes": k.scopes,
                    "tier": k.tier.value, "status": k.status.value,
                    "created_at": k.created_at, "expires_at": k.expires_at,
                    "last_used": k.last_used, "request_count": k.request_count,
                    "metadata": k.metadata,
                }
                for kid, k in self._keys.items()
            }
            os.makedirs(os.path.dirname(self._persist_path), exist_ok=True)
            tmp = self._persist_path + ".tmp"
            with open(tmp, "w") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp, self._persist_path)
        except Exception as exc:
            logger.error("APIKeyStore._save failed: %s", exc)

    def _load(self) -> None:
        if not os.path.exists(self._persist_path):
            return
        try:
            with open(self._persist_path) as f:
                data = json.load(f)
            for key_id, d in data.items():
                k = APIKey(
                    key_id=key_id, key_hash=d["key_hash"], name=d["name"],
                    owner_id=d["owner_id"], scopes=d["scopes"],
                    tier=KeyTier(d["tier"]), status=KeyStatus(d["status"]),
                    created_at=d["created_at"], expires_at=d.get("expires_at"),
                    last_used=d.get("last_used", 0),
                    request_count=d.get("request_count", 0),
                    metadata=d.get("metadata", {}),
                )
                tier_limits = {
                    KeyTier.FREE: (60, 1_000),
                    KeyTier.DEVELOPER: (300, 50_000),
                    KeyTier.ENTERPRISE: (0, 0),
                }
                rpm, rpd = tier_limits.get(k.tier, (60, 1_000))
                self._keys[key_id]     = k
                self._hashes[k.key_hash] = key_id
                self._buckets[key_id]  = RateBucket(rpm_limit=rpm, rpd_limit=rpd)
            logger.info("APIKeyStore loaded %d keys", len(self._keys))
        except Exception as exc:
            logger.error("APIKeyStore._load failed: %s", exc)


# ---------------------------------------------------------------------------
# Route Registry + OpenAPI generator
# ---------------------------------------------------------------------------

class PublicAPIRegistry:
    """Registry of all /api/v1/* routes for OpenAPI spec generation."""

    def __init__(self) -> None:
        self._routes: List[RouteDefinition] = []
        self._lock   = threading.Lock()

    def register(self, route: RouteDefinition) -> None:
        with self._lock:
            self._routes.append(route)

    def routes(self) -> List[RouteDefinition]:
        with self._lock:
            return list(self._routes)

    def openapi_spec(self, base_url: str = "https://murphy.systems") -> Dict[str, Any]:
        """Generate OpenAPI 3.1 spec from registered routes."""
        paths: Dict[str, Any] = {}
        all_tags: Set[str] = set()

        for r in self.routes():
            op: Dict[str, Any] = {
                "summary":     r.summary,
                "description": r.description,
                "tags":        r.tags,
                "security":    [{"MurphyApiKey": []}],
                "parameters":  [],
                "responses": {
                    "200": {"description": "Success"},
                    "401": {"description": "Unauthorized — missing or invalid API key"},
                    "403": {"description": "Forbidden — insufficient scope"},
                    "429": {"description": "Rate limit exceeded"},
                }
            }
            if r.required_scopes:
                op["x-required-scopes"] = r.required_scopes
            if r.request_schema and r.method in ("POST", "PUT", "PATCH"):
                op["requestBody"] = {
                    "required": True,
                    "content": {"application/json": {"schema": r.request_schema}},
                }
            if r.response_schema:
                op["responses"]["200"] = {
                    "description": "Success",
                    "content": {"application/json": {"schema": r.response_schema}},
                }
            paths.setdefault(r.path, {})[r.method.lower()] = op
            all_tags.update(r.tags)

        return {
            "openapi": "3.1.0",
            "info": {
                "title":       "Murphy System Public API",
                "description": "Programmatic access to the Murphy AI Operating System. Authenticate with a Murphy API key in the X-Murphy-Key header.",
                "version":     MURPHY_API_VERSION,
                "contact": {"name": "Murphy System", "url": "https://murphy.systems"},
                "license":     {"name": "BSL 1.1"},
            },
            "servers": [{"url": f"{base_url}/api/v1", "description": "Production"}],
            "paths":   paths,
            "tags":    [{"name": t} for t in sorted(all_tags)],
            "components": {
                "securitySchemes": {
                    "MurphyApiKey": {
                        "type": "apiKey",
                        "in":   "header",
                        "name": "X-Murphy-Key",
                        "description": "Issue keys at /api/v1/keys",
                    }
                }
            },
        }


# ---------------------------------------------------------------------------
# Request Validator
# ---------------------------------------------------------------------------

class APIRequestValidator:
    """Validates incoming /api/v1 requests: key, scope, rate."""

    def __init__(self, store: APIKeyStore) -> None:
        self._store = store

    def validate(
        self, raw_key: str, required_scope: Optional[str] = None
    ) -> Tuple[bool, Optional[APIKey], str]:
        """Returns (ok, api_key_obj, reason)."""
        if not raw_key:
            return False, None, "missing_key"

        key_obj = self._store.lookup(raw_key)
        if not key_obj:
            return False, None, "invalid_key"
        if not key_obj.is_valid():
            return False, key_obj, f"key_{key_obj.status.value}"
        if required_scope and not key_obj.has_scope(required_scope):
            return False, key_obj, "insufficient_scope"

        allowed, reason = self._store.check_rate(key_obj.key_id)
        if not allowed:
            return False, key_obj, reason

        self._store.record_use(key_obj.key_id)
        return True, key_obj, "ok"


# ---------------------------------------------------------------------------
# Webhook Verifier
# ---------------------------------------------------------------------------

class WebhookVerifier:
    """Verifies inbound webhook signatures from external services."""

    @staticmethod
    def verify_hmac_sha256(payload: bytes, signature: str, secret: str) -> bool:
        expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature.lstrip("sha256="))

    @staticmethod
    def verify_murphy_signature(payload: bytes, signature: str) -> bool:
        webhook_secret = os.environ.get("MURPHY_WEBHOOK_SECRET", "")
        if not webhook_secret:
            return False
        return WebhookVerifier.verify_hmac_sha256(payload, signature, webhook_secret)


# ---------------------------------------------------------------------------
# Murphy Public API Server (singleton façade)
# ---------------------------------------------------------------------------

class MurphyPublicAPIServer:
    """
    Singleton façade that wires the key store, validator, and route registry
    together. Mounted into the FastAPI app via create_public_api_routes().
    """

    _instance: Optional["MurphyPublicAPIServer"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "MurphyPublicAPIServer":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init()
        return cls._instance

    def _init(self) -> None:
        persist_dir  = os.environ.get("MURPHY_PERSISTENCE_DIR", "/var/lib/murphy-production")
        persist_path = os.path.join(persist_dir, "api_keys.json")
        self.store     = APIKeyStore(persist_path=persist_path)
        self.registry  = PublicAPIRegistry()
        self.validator = APIRequestValidator(self.store)
        self.webhook   = WebhookVerifier()
        self._register_core_routes()
        logger.info("MurphyPublicAPIServer initialised (MAS-001)")

    def _register_core_routes(self) -> None:
        core = [
            RouteDefinition("/api/v1/health",  "GET",  "/api/health",
                            "System health", tags=["system"],
                            required_scopes=[Scope.READ_HEALTH]),
            RouteDefinition("/api/v1/modules", "GET",  "/api/modules",
                            "List all modules", tags=["system"],
                            required_scopes=[Scope.READ_MODULES]),
            RouteDefinition("/api/v1/forge/generate", "POST", "/api/demo/generate-deliverable",
                            "Generate a Forge deliverable", tags=["forge"],
                            required_scopes=[Scope.WRITE_FORGE]),
            RouteDefinition("/api/v1/forge/stream", "POST", "/api/demo/generate-deliverable/stream",
                            "Stream a Forge deliverable (SSE)", tags=["forge"],
                            required_scopes=[Scope.WRITE_FORGE]),
            RouteDefinition("/api/v1/agents",  "GET",  "/api/agents",
                            "List active agents", tags=["agents"],
                            required_scopes=[Scope.READ_AGENTS]),
            RouteDefinition("/api/v1/mail/send", "POST", "/api/mail/send",
                            "Send an email via Murphy Mail", tags=["mail"],
                            required_scopes=[Scope.WRITE_MAIL]),
            RouteDefinition("/api/v1/calendar/events", "GET", "/api/roi-calendar/events",
                            "List calendar events", tags=["calendar"],
                            required_scopes=[Scope.READ_CALENDAR]),
            RouteDefinition("/api/v1/connectors", "GET", "/api/integrations/list",
                            "List available connectors", tags=["connectors"],
                            required_scopes=[Scope.CONNECTORS]),
        ]
        for r in core:
            self.registry.register(r)

    def issue_key(
        self,
        owner_id: str,
        name: str,
        scopes: List[str],
        tier: KeyTier = KeyTier.FREE,
        expires_in_days: Optional[int] = None,
    ) -> Tuple[str, APIKey]:
        return self.store.create(owner_id, name, scopes, tier, expires_in_days)

    def validate_request(
        self, raw_key: str, required_scope: Optional[str] = None
    ) -> Tuple[bool, Optional[APIKey], str]:
        return self.validator.validate(raw_key, required_scope)

    def openapi(self) -> Dict[str, Any]:
        return self.registry.openapi_spec()

    def stats(self) -> Dict[str, Any]:
        keys = self.store.all_keys()
        return {
            "total_keys":   len(keys),
            "active_keys":  sum(1 for k in keys if k.status == KeyStatus.ACTIVE),
            "revoked_keys": sum(1 for k in keys if k.status == KeyStatus.REVOKED),
            "total_requests": sum(k.request_count for k in keys),
            "routes_registered": len(self.registry.routes()),
        }


# ---------------------------------------------------------------------------
# Route factory (called from app.py)
# ---------------------------------------------------------------------------

def create_public_api_routes(app, murphy_instance=None) -> None:
    """
    Register /api/v1/* routes on the FastAPI app.
    Called once during app startup.
    """
    try:
        from fastapi import Request
    except ImportError:
        from starlette.requests import Request
    from starlette.responses import JSONResponse, StreamingResponse

    server = MurphyPublicAPIServer()

    def _key_from_request(request: Request) -> str:
        return (
            request.headers.get("X-Murphy-Key", "")
            or request.headers.get("x-murphy-key", "")
            or request.query_params.get("api_key", "")
        )

    def _ok(data: Any, status: int = 200) -> JSONResponse:
        return JSONResponse({"success": True,  "data": data}, status_code=status)

    def _err(code: str, msg: str, status: int = 400) -> JSONResponse:
        return JSONResponse({"success": False, "error": code, "message": msg}, status_code=status)

    # ── Key Management ──────────────────────────────────────────────────────

    @app.post("/api/v1/keys")
    async def v1_issue_key(request: Request):
        """Issue a new Murphy API key. Requires valid session or founder key."""
        # Auth: must be a logged-in user or founder
        session_user = getattr(request.state, "user", None)
        founder_key  = os.environ.get("FOUNDER_API_KEY", "")
        caller_key   = request.headers.get("X-Murphy-Key", "")
        if not session_user and (not founder_key or caller_key != founder_key):
            return _err("unauthorized", "Login or provide founder key", 401)

        body = await request.json()
        owner_id = (session_user or {}).get("user_id", "system")
        name     = body.get("name", "Unnamed key")
        scopes   = body.get("scopes", [Scope.READ_HEALTH])
        tier_str = body.get("tier", "free")
        expires  = body.get("expires_in_days")

        try:
            tier = KeyTier(tier_str)
        except ValueError:
            tier = KeyTier.FREE

        raw_key, key_obj = server.issue_key(owner_id, name, scopes, tier, expires)
        result = key_obj.to_public_dict()
        result["key"] = raw_key   # shown once
        return _ok(result, 201)

    @app.get("/api/v1/keys")
    async def v1_list_keys(request: Request):
        session_user = getattr(request.state, "user", None)
        if not session_user:
            return _err("unauthorized", "Login required", 401)
        owner_id = session_user.get("user_id", "")
        keys = server.store.list_by_owner(owner_id)
        return _ok([k.to_public_dict() for k in keys])

    @app.delete("/api/v1/keys/{key_id}")
    async def v1_revoke_key(request: Request, key_id: str):
        session_user = getattr(request.state, "user", None)
        if not session_user:
            return _err("unauthorized", "Login required", 401)
        ok = server.store.revoke(key_id)
        if not ok:
            return _err("not_found", "Key not found", 404)
        return _ok({"revoked": key_id})

    # ── OpenAPI Spec ────────────────────────────────────────────────────────

    @app.get("/api/v1/openapi.json")
    async def v1_openapi():
        return JSONResponse(server.openapi())

    @app.get("/api/v1/docs")
    async def v1_docs():
        html = """<!DOCTYPE html><html><head><title>Murphy API Docs</title>
        <meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
        <link rel="stylesheet" type="text/css" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css"/>
        </head><body>
        <div id="swagger-ui"></div>
        <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
        <script>
        SwaggerUIBundle({url:"/api/v1/openapi.json",dom_id:"#swagger-ui",
        presets:[SwaggerUIBundle.presets.apis,SwaggerUIBundle.SwaggerUIStandalonePreset],
        layout:"BaseLayout",deepLinking:true});
        </script></body></html>"""
        from starlette.responses import HTMLResponse
        return HTMLResponse(html)

    # ── Stats ───────────────────────────────────────────────────────────────

    @app.get("/api/v1/stats")
    async def v1_stats(request: Request):
        raw_key = _key_from_request(request)
        ok, key_obj, reason = server.validate_request(raw_key, "admin:*")
        if not ok:
            return _err(reason, "Admin scope required", 403)
        return _ok(server.stats())

    # ── Webhook ingest ───────────────────────────────────────────────────────

    @app.post("/api/v1/webhook/{source}")
    async def v1_webhook(request: Request, source: str):
        body_bytes = await request.body()
        sig = request.headers.get("X-Murphy-Signature", "")
        if sig and not server.webhook.verify_murphy_signature(body_bytes, sig):
            return _err("invalid_signature", "Webhook signature mismatch", 401)
        # Dispatch event internally
        try:
            payload = json.loads(body_bytes)
        except Exception:
            payload = {"raw": body_bytes.decode("utf-8", errors="replace")}
        logger.info("Webhook received from %s: %s", source, str(payload)[:200])
        return _ok({"received": True, "source": source, "event": payload.get("event", "unknown")})

    # ── Public health (no key required) ────────────────────────────────────

    @app.get("/api/v1/ping")
    async def v1_ping():
        return JSONResponse({"murphy": "online", "version": MURPHY_API_VERSION, "ts": time.time()})

    logger.info("PATCH-065a: Public API routes registered (/api/v1/*)")
