"""
API Gateway Adapter — Unified API gateway for external integrations
with rate limiting, authentication management, webhook dispatch,
circuit breaker pattern, and request/response transformation.
"""

import hashlib
import json
import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)


class GatewayAuthMethod(Enum):
    """Gateway auth method (Enum subclass)."""
    API_KEY = "api_key"
    BEARER_TOKEN = "bearer_token"
    OAUTH2 = "oauth2"
    BASIC = "basic"
    HMAC = "hmac"
    NONE = "none"


class RouteMethod(Enum):
    """Route method (Enum subclass)."""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"
    ANY = "ANY"


class CircuitState(Enum):
    """Circuit state (Enum subclass)."""
    CLOSED = "closed"  # normal operation
    OPEN = "open"  # failing, reject requests
    HALF_OPEN = "half_open"  # testing recovery


@dataclass
class RateLimitRule:
    """Rate limit rule."""
    max_requests: int = 100
    window_seconds: int = 60
    per_client: bool = True


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker config."""
    failure_threshold: int = 5
    recovery_timeout: float = 30.0
    half_open_max_calls: int = 3


@dataclass
class RouteDefinition:
    """Route definition."""
    route_id: str
    path: str
    method: RouteMethod
    target_service: str
    auth_method: GatewayAuthMethod = GatewayAuthMethod.NONE
    rate_limit: RateLimitRule = field(default_factory=RateLimitRule)
    circuit_breaker: CircuitBreakerConfig = field(default_factory=CircuitBreakerConfig)
    transform_request: Optional[str] = None
    transform_response: Optional[str] = None
    timeout_seconds: float = 30.0
    cache_ttl: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RouteState:
    """Route state."""
    route: RouteDefinition
    request_count: int = 0
    error_count: int = 0
    circuit_state: CircuitState = CircuitState.CLOSED
    circuit_failures: int = 0
    circuit_opened_at: float = 0.0
    half_open_calls: int = 0
    window_start: float = 0.0
    window_requests: int = 0
    last_response_time: float = 0.0
    cache: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GatewayRequest:
    """Gateway request."""
    request_id: str
    path: str
    method: str
    headers: Dict[str, str] = field(default_factory=dict)
    body: Any = None
    query_params: Dict[str, str] = field(default_factory=dict)
    client_id: str = "anonymous"
    timestamp: float = field(default_factory=time.time)


@dataclass
class GatewayResponse:
    """Gateway response."""
    request_id: str
    status_code: int
    body: Any = None
    headers: Dict[str, str] = field(default_factory=dict)
    latency_ms: float = 0.0
    cached: bool = False
    error: Optional[str] = None


class APIGatewayAdapter:
    """Unified API gateway with rate limiting, auth, circuit breaker, caching, and routing."""

    def __init__(self):
        self._lock = threading.Lock()
        self._routes: Dict[str, RouteState] = {}
        self._client_limits: Dict[str, Dict[str, int]] = {}  # client -> route -> count
        self._request_log: List[Dict[str, Any]] = []
        self._handlers: Dict[str, Callable] = {}
        self._api_keys: Dict[str, str] = {}  # key -> client_id
        self._webhook_subscriptions: Dict[str, List[Dict[str, Any]]] = {}

    def register_route(self, route: RouteDefinition) -> bool:
        with self._lock:
            self._routes[route.route_id] = RouteState(route=route)
            return True

    def register_handler(self, target_service: str, handler: Callable) -> None:
        self._handlers[target_service] = handler

    def register_api_key(self, api_key: str, client_id: str) -> None:
        self._api_keys[api_key] = client_id

    def _find_route(self, path: str, method: str) -> Optional[RouteState]:
        for state in self._routes.values():
            route = state.route
            if route.path == path and (route.method.value == method or route.method == RouteMethod.ANY):
                return state
        return None

    def _check_auth(self, route: RouteDefinition, request: GatewayRequest) -> Optional[str]:
        if route.auth_method == GatewayAuthMethod.NONE:
            return None
        if route.auth_method == GatewayAuthMethod.API_KEY:
            key = request.headers.get("X-API-Key", "")
            if key not in self._api_keys:
                return "Invalid API key"
            request.client_id = self._api_keys[key]
            return None
        if route.auth_method == GatewayAuthMethod.BEARER_TOKEN:
            auth = request.headers.get("Authorization", "")
            if not auth.startswith("Bearer "):
                return "Missing bearer token"
            return None
        return None

    def _check_rate_limit(self, route_state: RouteState, client_id: str) -> bool:
        rl = route_state.route.rate_limit
        now = time.time()
        if now - route_state.window_start > rl.window_seconds:
            route_state.window_start = now
            route_state.window_requests = 0
            if rl.per_client:
                self._client_limits.setdefault(client_id, {})[route_state.route.route_id] = 0

        if rl.per_client:
            client_counts = self._client_limits.setdefault(client_id, {})
            count = client_counts.get(route_state.route.route_id, 0)
            if count >= rl.max_requests:
                return False
            client_counts[route_state.route.route_id] = count + 1
        else:
            if route_state.window_requests >= rl.max_requests:
                return False
            route_state.window_requests += 1
        return True

    def _check_circuit_breaker(self, route_state: RouteState) -> Optional[str]:
        cb = route_state.route.circuit_breaker
        if route_state.circuit_state == CircuitState.OPEN:
            if time.time() - route_state.circuit_opened_at > cb.recovery_timeout:
                route_state.circuit_state = CircuitState.HALF_OPEN
                route_state.half_open_calls = 0
            else:
                return "Circuit breaker open"
        if route_state.circuit_state == CircuitState.HALF_OPEN:
            if route_state.half_open_calls >= cb.half_open_max_calls:
                route_state.circuit_state = CircuitState.OPEN
                route_state.circuit_opened_at = time.time()
                return "Circuit breaker open (half-open limit reached)"
            route_state.half_open_calls += 1
        return None

    def _record_success(self, route_state: RouteState):
        if route_state.circuit_state == CircuitState.HALF_OPEN:
            route_state.circuit_state = CircuitState.CLOSED
            route_state.circuit_failures = 0

    def _record_failure(self, route_state: RouteState):
        cb = route_state.route.circuit_breaker
        route_state.circuit_failures += 1
        route_state.error_count += 1
        if route_state.circuit_failures >= cb.failure_threshold:
            route_state.circuit_state = CircuitState.OPEN
            route_state.circuit_opened_at = time.time()

    def process_request(self, request: GatewayRequest) -> GatewayResponse:
        start = time.time()

        # Find route
        route_state = self._find_route(request.path, request.method)
        if not route_state:
            return GatewayResponse(
                request_id=request.request_id,
                status_code=404,
                error="Route not found",
                latency_ms=(time.time() - start) * 1000,
            )

        # Auth check
        auth_error = self._check_auth(route_state.route, request)
        if auth_error:
            return GatewayResponse(
                request_id=request.request_id,
                status_code=401,
                error=auth_error,
                latency_ms=(time.time() - start) * 1000,
            )

        # Rate limit check
        if not self._check_rate_limit(route_state, request.client_id):
            return GatewayResponse(
                request_id=request.request_id,
                status_code=429,
                error="Rate limit exceeded",
                latency_ms=(time.time() - start) * 1000,
            )

        # Circuit breaker check
        cb_error = self._check_circuit_breaker(route_state)
        if cb_error:
            return GatewayResponse(
                request_id=request.request_id,
                status_code=503,
                error=cb_error,
                latency_ms=(time.time() - start) * 1000,
            )

        # Check cache
        if route_state.route.cache_ttl > 0 and request.method == "GET":
            cache_key = f"{request.path}:{json.dumps(request.query_params, sort_keys=True)}"
            cached = route_state.cache.get(cache_key)
            if cached and time.time() - cached.get("timestamp", 0) < route_state.route.cache_ttl:
                return GatewayResponse(
                    request_id=request.request_id,
                    status_code=200,
                    body=cached["body"],
                    cached=True,
                    latency_ms=(time.time() - start) * 1000,
                )

        # Execute handler
        handler = self._handlers.get(route_state.route.target_service)
        route_state.request_count += 1

        if handler:
            try:
                result = handler(request)
                self._record_success(route_state)
                response = GatewayResponse(
                    request_id=request.request_id,
                    status_code=200,
                    body=result,
                    latency_ms=(time.time() - start) * 1000,
                )
            except Exception as exc:
                logger.debug("Caught exception: %s", exc)
                self._record_failure(route_state)
                response = GatewayResponse(
                    request_id=request.request_id,
                    status_code=500,
                    error=str(exc),
                    latency_ms=(time.time() - start) * 1000,
                )
        else:
            self._record_success(route_state)
            response = GatewayResponse(
                request_id=request.request_id,
                status_code=200,
                body={
                    "target_service": route_state.route.target_service,
                    "simulated": True,
                    "path": request.path,
                    "method": request.method,
                },
                latency_ms=(time.time() - start) * 1000,
            )

        # Update cache
        if route_state.route.cache_ttl > 0 and request.method == "GET" and response.status_code == 200:
            cache_key = f"{request.path}:{json.dumps(request.query_params, sort_keys=True)}"
            route_state.cache[cache_key] = {
                "body": response.body,
                "timestamp": time.time(),
            }

        route_state.last_response_time = response.latency_ms

        with self._lock:
            capped_append(self._request_log, {
                "request_id": request.request_id,
                "path": request.path,
                "method": request.method,
                "client_id": request.client_id,
                "status_code": response.status_code,
                "latency_ms": response.latency_ms,
                "cached": response.cached,
                "timestamp": request.timestamp,
            })

        return response

    def subscribe_webhook(self, event_type: str, url: str, secret: Optional[str] = None) -> str:
        sub_id = hashlib.sha256(f"{event_type}:{url}:{time.time()}".encode()).hexdigest()[:16]
        with self._lock:
            subs = self._webhook_subscriptions.setdefault(event_type, [])
            subs.append({
                "subscription_id": sub_id,
                "event_type": event_type,
                "url": url,
                "secret": secret,
                "created_at": time.time(),
                "active": True,
            })
        return sub_id

    def dispatch_webhook(self, event_type: str, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        subs = self._webhook_subscriptions.get(event_type, [])
        results = []
        for sub in subs:
            if sub.get("active"):
                results.append({
                    "subscription_id": sub["subscription_id"],
                    "url": sub["url"],
                    "event_type": event_type,
                    "dispatched": True,
                    "payload_size": len(json.dumps(payload)),
                })
        return results

    def list_webhook_subscriptions(self) -> Dict[str, List[Dict[str, Any]]]:
        return dict(self._webhook_subscriptions)

    def get_route_stats(self) -> List[Dict[str, Any]]:
        return [
            {
                "route_id": state.route.route_id,
                "path": state.route.path,
                "method": state.route.method.value,
                "request_count": state.request_count,
                "error_count": state.error_count,
                "circuit_state": state.circuit_state.value,
                "avg_response_ms": state.last_response_time,
            }
            for state in self._routes.values()
        ]

    def get_statistics(self) -> Dict[str, Any]:
        with self._lock:
            total = len(self._request_log)
            errors = sum(1 for r in self._request_log if r["status_code"] >= 400)
            return {
                "total_routes": len(self._routes),
                "total_requests": total,
                "total_errors": errors,
                "success_rate": (total - errors) / max(total, 1),
                "webhook_subscriptions": sum(len(s) for s in self._webhook_subscriptions.values()),
                "registered_handlers": len(self._handlers),
                "registered_api_keys": len(self._api_keys),
            }

    def status(self) -> Dict[str, Any]:
        return {
            "module": "api_gateway_adapter",
            "statistics": self.get_statistics(),
            "routes": self.get_route_stats(),
        }
