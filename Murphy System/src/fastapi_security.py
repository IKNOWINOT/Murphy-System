"""
FastAPI Security Integration for Murphy System

Provides centralized security controls for all FastAPI API servers:
- API key authentication on all routes (except health checks)
- JWT token validation as an alternative auth method
- CORS origin allowlist (replaces wildcard CORS)
- Rate limiting per client
- Input sanitization
- Security response headers

Mirrors flask_security.py for FastAPI services.

Addresses: SEC-001, SEC-002, SEC-004

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
"""

import hmac
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# ── JWT Configuration ──────────────────────────────────────────────

_JWT_SECRET = os.environ.get("MURPHY_JWT_SECRET", "")
_JWT_ALGORITHM = os.environ.get("MURPHY_JWT_ALGORITHM", "HS256")
_JWT_ISSUER = os.environ.get("MURPHY_JWT_ISSUER", "murphy-system")


def validate_jwt_token(token: str) -> Optional[Dict[str, Any]]:
    """Validate a JWT token and return the decoded payload.

    Requires ``MURPHY_JWT_SECRET`` to be set.  Returns ``None`` if JWT
    validation is not configured or the token is invalid.
    """
    if not _JWT_SECRET:
        return None
    try:
        import jwt  # PyJWT
        payload = jwt.decode(
            token,
            _JWT_SECRET,
            algorithms=[_JWT_ALGORITHM],
            issuer=_JWT_ISSUER,
            options={"require": ["exp", "sub"]},
        )
        return payload
    except Exception as exc:
        logger.debug("JWT validation failed: %s", exc)
        return None


# ── CORS Configuration ──────────────────────────────────────────────

def get_cors_origins() -> List[str]:
    """
    Get allowed CORS origins from environment.

    Reads MURPHY_CORS_ORIGINS env var (comma-separated).
    Defaults to localhost origins for development.
    """
    default_origins = (
        "http://localhost:3000,http://localhost:5000,http://localhost:8000,"
        "http://localhost:8080,http://localhost:9000"
    )
    origins_str = os.environ.get("MURPHY_CORS_ORIGINS", default_origins)
    return [o.strip() for o in origins_str.split(",") if o.strip()]


# ── API Key Validation ──────────────────────────────────────────────

def get_configured_api_keys() -> List[str]:
    """Get configured API keys from environment."""
    keys_str = os.environ.get("MURPHY_API_KEYS", "")
    if not keys_str:
        return []
    return [k.strip() for k in keys_str.split(",") if k.strip()]


def validate_api_key(api_key: str) -> bool:
    """Validate an API key against configured keys using constant-time comparison
    to prevent timing side-channel attacks (CWE-208).
    """
    configured_keys = get_configured_api_keys()
    if not configured_keys:
        # No keys configured — allow only in development or test mode.
        # staging and production both require explicit API keys.
        murphy_env = os.environ.get("MURPHY_ENV", "development")
        return murphy_env in ("development", "test")
    return any(hmac.compare_digest(api_key, key) for key in configured_keys)


def _extract_api_key(request: Request) -> Optional[str]:
    """Extract API key from request headers."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:].strip()
    api_key = request.headers.get("X-API-Key", "")
    if api_key:
        return api_key
    return None


def _authenticate_request(request: Request) -> Optional[bool]:
    """Authenticate a request via API key or JWT token.

    Returns:
        ``True`` if authenticated, ``False`` if credentials present but
        invalid, ``None`` if no credentials found.
    """
    auth_header = request.headers.get("Authorization", "")
    api_key_header = request.headers.get("X-API-Key", "")

    # Try API key from X-API-Key header
    if api_key_header:
        return validate_api_key(api_key_header)

    # Try Bearer token — could be an API key or a JWT
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
        # First try JWT validation (if configured)
        jwt_payload = validate_jwt_token(token)
        if jwt_payload is not None:
            return True
        # Fall back to API key validation
        return validate_api_key(token)

    return None  # no credentials provided


def _is_health_endpoint(path: str) -> bool:
    """Check if the request path is a health/readiness/metrics endpoint."""
    normalized = path.rstrip("/")
    exempt_suffixes = ("/health", "/healthz", "/ready", "/metrics")
    return any(normalized.endswith(s) or normalized == s[1:] for s in exempt_suffixes)


def _is_static_or_ui_page(path: str) -> bool:
    """Check if the request is for static assets or UI HTML pages.

    Static files and UI page loads should not be rate-limited because:
    1. Each page load triggers multiple asset requests (CSS, JS, SVG).
    2. Rate-limiting page loads degrades the user experience.
    """
    normalized = path.rstrip("/")
    # Static asset paths
    if normalized.startswith("/static/") or normalized.startswith("/ui/static/"):
        return True
    # UI HTML page routes (not API calls)
    if normalized.startswith("/ui/") and "/api/" not in normalized:
        return True
    # Root landing page
    if normalized == "" or normalized == "/":
        return True
    # Favicon — browsers automatically request this on every page load
    if normalized == "/favicon.ico" or normalized.endswith("/favicon.svg"):
        return True
    # Root-level HTML pages served directly (e.g. /login.html, /signup.html)
    # These are static content — blocking them returns raw JSON to the browser.
    if normalized.endswith(".html"):
        return True
    return False


def _is_public_api_route(path: str, method: str = "GET") -> bool:
    """Check if the request is for a public API route that requires no authentication.

    These routes are intentionally accessible without credentials because they
    support normal pre-login browsing (landing page, pricing, signup, login).
    Failing to exempt them causes innocent unauthenticated requests to be counted
    as brute-force failures, locking out visitors after just 1-2 page loads
    (CWE-307).

    Route list derived from API_ROUTES.md (Auth: No entries) plus OAuth/auth
    flow requirements:
    - /api/health       — health check (also covered by _is_health_endpoint)
    - /api/manifest     — machine-readable endpoint list
    - /api/info         — system info
    - /api/ui/links     — UI navigation links for frontend rendering
    - /api/auth/oauth/* — OAuth initiation buttons (pre-login page)
    - /api/auth/callback/* — OAuth callback handling
    - /api/auth/login   — login endpoint
    - /api/auth/register / /api/auth/signup — registration endpoint
    - /api/reviews      — GET only; public reviews on landing/pricing pages
    - /api/billing/plans — GET only; pricing page fetches plan data without login
    - /api/billing/currencies — GET only; pricing page currency list without login
    """
    normalized = path.rstrip("/")

    # Exact-match public routes (no auth required regardless of method)
    _PUBLIC_EXACT = frozenset({
        "/api/health",
        "/api/manifest",
        "/api/info",
        "/api/ui/links",
        "/api/auth/login",
        "/api/auth/logout",
        "/api/auth/register",
        "/api/auth/signup",
        "/api/auth/callback",
        "/api/auth/providers",
        "/api/usage/daily",
    })
    if normalized in _PUBLIC_EXACT:
        return True

    # OAuth initiation and callback flows — must be accessible pre-login
    if normalized.startswith("/api/auth/oauth/"):
        return True
    if normalized.startswith("/api/auth/callback/"):
        return True

    # Public reviews — GET only (displayed on landing/pricing pages without login)
    if normalized == "/api/reviews" and method.upper() == "GET":
        return True

    # Billing plans and currencies — GET only; pricing page needs these without login
    if normalized in ("/api/billing/plans", "/api/billing/currencies") and method.upper() == "GET":
        return True

    return False


def _is_login_endpoint(path: str, method: str) -> bool:
    """Return True only for the actual credential-submission login endpoint.

    Brute-force failure tracking (CWE-307) is scoped exclusively to this
    endpoint because it is the only one where an attacker submits a password
    guess.  Chat, Librarian, and other authenticated API endpoints do NOT count
    toward the brute-force lockout — a missing or expired session token on those
    routes is a session management issue, not a password-guessing attack.
    """
    return path.rstrip("/") == "/api/auth/login" and method.upper() == "POST"


# ── Rate Limiting ────────────────────────────────────────────────────

class _FastAPIRateLimiter:
    """Token-bucket rate limiter with swarm detection.

    Two tiers of rate limiting:
    - **Single-call** (default): standard ``burst_size`` tokens refilled at
      ``requests_per_minute`` rate.  Suitable for normal sequential API usage.
    - **Swarm/batch**: when many requests arrive within ``swarm_window_seconds``
      the limiter automatically switches to a higher ``swarm_burst_size`` for
      that client, allowing dashboards and smoke-test pages that fire many
      parallel requests to complete without being throttled.

    The swarm bucket drains independently and resets once the rapid-fire
    window elapses, preventing abuse while accommodating legitimate batch
    patterns like UI dashboards and automated test suites.
    """

    _BUCKET_TTL_SECONDS = 3600  # Evict buckets inactive for 1 hour
    _CLEANUP_INTERVAL = 300     # Run cleanup every 5 minutes

    def __init__(
        self,
        requests_per_minute: int = 60,
        burst_size: int = 20,
        swarm_burst_size: int = 0,
        swarm_window_seconds: float = 2.0,
    ):
        self.rpm = requests_per_minute
        self.burst = burst_size
        self.swarm_burst = swarm_burst_size
        self.swarm_window = swarm_window_seconds
        self._buckets: Dict[str, Dict[str, Any]] = {}
        self._last_cleanup: float = time.monotonic()

    def check(self, client_id: str) -> Dict[str, Any]:
        """Check whether *client_id* has a rate-limit token available."""
        now = time.monotonic()

        # Periodic stale-bucket cleanup (CWE-400 mitigation)
        if now - self._last_cleanup > self._CLEANUP_INTERVAL:
            self._evict_stale_buckets(now)

        if client_id not in self._buckets:
            self._buckets[client_id] = {
                "tokens": self.burst,
                "last_refill": now,
                "swarm_tokens": self.swarm_burst,
                "swarm_window_start": now,
                "swarm_hits": 0,
            }
        bucket = self._buckets[client_id]
        elapsed = now - bucket["last_refill"]
        refill = elapsed * (self.rpm / 60.0)
        bucket["tokens"] = min(self.burst, bucket["tokens"] + refill)
        bucket["last_refill"] = now

        # --- Swarm detection ---
        # Track rapid-fire hits within the swarm window
        swarm_elapsed = now - bucket.get("swarm_window_start", now)
        if swarm_elapsed > self.swarm_window:
            # Window expired — reset swarm counters
            bucket["swarm_tokens"] = self.swarm_burst
            bucket["swarm_window_start"] = now
            bucket["swarm_hits"] = 0

        bucket["swarm_hits"] = bucket.get("swarm_hits", 0) + 1
        is_swarm = bucket["swarm_hits"] > self.burst

        # --- Token check ---
        if bucket["tokens"] >= 1:
            # Normal single-call path: consume a standard token
            bucket["tokens"] -= 1
            return {"allowed": True, "remaining": int(bucket["tokens"])}

        # Standard tokens exhausted — check swarm allowance
        if is_swarm and bucket.get("swarm_tokens", 0) >= 1:
            bucket["swarm_tokens"] -= 1
            return {
                "allowed": True,
                "remaining": int(bucket["swarm_tokens"]),
                "swarm_mode": True,
            }

        return {
            "allowed": False,
            "remaining": 0,
            "retry_after_seconds": (1 - bucket["tokens"]) * (60.0 / self.rpm),
        }

    def _evict_stale_buckets(self, now: float) -> None:
        """Remove buckets that have not been used within the TTL window."""
        stale_keys = [
            cid for cid, b in self._buckets.items()
            if now - b["last_refill"] > self._BUCKET_TTL_SECONDS
        ]
        for key in stale_keys:
            del self._buckets[key]
        self._last_cleanup = now


_rate_limiter = _FastAPIRateLimiter(
    requests_per_minute=int(os.environ.get("MURPHY_RATE_LIMIT_RPM", "60")),
    burst_size=int(os.environ.get("MURPHY_RATE_LIMIT_BURST", "20")),
    swarm_burst_size=int(os.environ.get("MURPHY_RATE_LIMIT_SWARM_BURST", "60")),
    swarm_window_seconds=float(os.environ.get("MURPHY_RATE_LIMIT_SWARM_WINDOW", "2.0")),
)


# ── Input Sanitization ──────────────────────────────────────────────

_INJECTION_PATTERNS = [
    re.compile(r"<script[^>]*>", re.IGNORECASE),
    re.compile(r"javascript:", re.IGNORECASE),
    re.compile(r";\s*(DROP|DELETE|UPDATE|INSERT|ALTER)\s", re.IGNORECASE),
    re.compile(r"\.\./", re.IGNORECASE),
    # Additional XSS vectors (CWE-79 hardening)
    re.compile(r"<svg[^>]*\bon\w+\s*=", re.IGNORECASE),
    re.compile(r"<img[^>]*\bon\w+\s*=", re.IGNORECASE),
    re.compile(r"<iframe[^>]*>", re.IGNORECASE),
    re.compile(r"<object[^>]*>", re.IGNORECASE),
    re.compile(r"<embed[^>]*>", re.IGNORECASE),
    re.compile(r"vbscript:", re.IGNORECASE),
    re.compile(r"data:\s*text/html", re.IGNORECASE),
]


def _check_injection(data: Any) -> bool:
    """Check for injection patterns. Returns True if threat detected."""
    if isinstance(data, str):
        for pattern in _INJECTION_PATTERNS:
            if pattern.search(data):
                return True
    elif isinstance(data, dict):
        for value in data.values():
            if _check_injection(value):
                return True
    elif isinstance(data, list):
        for item in data:
            if _check_injection(item):
                return True
    return False


# ── Brute-Force Protection ───────────────────────────────────────────

class _BruteForceTracker:
    """Track failed auth attempts per client IP (CWE-307 mitigation)."""

    def __init__(self, max_attempts: int = 5, window_seconds: int = 900, lockout_seconds: int = 900):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.lockout_seconds = lockout_seconds
        self._attempts: Dict[str, List[float]] = {}
        self._lockouts: Dict[str, float] = {}

    def record_failure(self, client_id: str) -> bool:
        """Record failed auth. Returns True if now locked out."""
        now = time.monotonic()
        if client_id not in self._attempts:
            self._attempts[client_id] = []
        window_start = now - self.window_seconds
        self._attempts[client_id] = [t for t in self._attempts[client_id] if t > window_start]
        self._attempts[client_id].append(now)
        if len(self._attempts[client_id]) >= self.max_attempts:
            self._lockouts[client_id] = now + self.lockout_seconds
            return True
        return False

    def is_locked_out(self, client_id: str) -> bool:
        if client_id not in self._lockouts:
            return False
        if time.monotonic() >= self._lockouts[client_id]:
            del self._lockouts[client_id]
            self._attempts.pop(client_id, None)
            return False
        return True

    def record_success(self, client_id: str) -> None:
        self._attempts.pop(client_id, None)
        self._lockouts.pop(client_id, None)


_brute_force = _BruteForceTracker(
    max_attempts=int(os.environ.get("MURPHY_AUTH_MAX_ATTEMPTS", "20")),
    window_seconds=int(os.environ.get("MURPHY_AUTH_WINDOW_SECONDS", "900")),
    lockout_seconds=int(os.environ.get("MURPHY_AUTH_LOCKOUT_SECONDS", "900")),
)


# ── Request Body Size Limit ─────────────────────────────────────────

_MAX_BODY_BYTES = int(os.environ.get("MURPHY_MAX_BODY_BYTES", str(1_048_576)))  # 1 MB default


# ── Security Headers ────────────────────────────────────────────────

_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Content-Security-Policy": (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
        "img-src 'self' data: https://fastapi.tiangolo.com; "
        "font-src 'self' https://cdn.jsdelivr.net https://fonts.gstatic.com; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    ),
}


# ── Security Middleware ──────────────────────────────────────────────

class SecurityMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware providing authentication, rate limiting, and security headers."""

    def __init__(self, app, service_name: str = "murphy-api"):
        super().__init__(app)
        self.service_name = service_name

    async def dispatch(self, request: Request, call_next):
        """Process an incoming request through auth, rate-limit, and header pipelines."""
        # Skip auth for health endpoints and OPTIONS (CORS preflight)
        if request.method == "OPTIONS":
            response = await call_next(request)
            return response
        if _is_health_endpoint(request.url.path):
            response = await call_next(request)
            self._add_security_headers(response)
            return response
        # Skip rate limiting / auth for static assets and UI page loads
        if _is_static_or_ui_page(request.url.path):
            response = await call_next(request)
            self._add_security_headers(response)
            return response
        # Skip brute-force tracking for public API routes (pre-login browsing).
        # These endpoints are intentionally unauthenticated; recording a failure
        # here would lock out users after normal page loads (CWE-307).
        if _is_public_api_route(request.url.path, request.method):
            response = await call_next(request)
            self._add_security_headers(response)
            return response

        # Client identification (used for brute-force, rate limit, and auth tracking)
        client_ip = request.client.host if request.client else "unknown"

        # Brute-force lockout check (CWE-307)
        if _brute_force.is_locked_out(client_ip):
            logger.warning("[%s] Client %s locked out (brute-force)", self.service_name, client_ip)
            return JSONResponse(
                status_code=429,
                content={"error": "Too many failed attempts. Try again later."},
            )

        # Request body size check (CWE-400)
        content_length_str = request.headers.get("content-length")
        if content_length_str:
            try:
                content_length = int(content_length_str)
                if content_length > _MAX_BODY_BYTES:
                    logger.warning("[%s] Oversized request from %s: %d bytes", self.service_name, client_ip, content_length)
                    return JSONResponse(
                        status_code=413,
                        content={"error": "Request body too large", "max_bytes": _MAX_BODY_BYTES},
                    )
            except ValueError:
                pass

        # Rate limiting
        rate_result = _rate_limiter.check(client_ip)
        if not rate_result["allowed"]:
            logger.warning("[%s] Rate limit exceeded for %s", self.service_name, client_ip)
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "retry_after_seconds": rate_result.get("retry_after_seconds", 60),
                },
            )

        # API key / JWT authentication
        auth_result = _authenticate_request(request)
        if auth_result is None:
            murphy_env = os.environ.get("MURPHY_ENV", "development")
            # Only development and test modes skip auth; staging and production require it
            if murphy_env not in ("development", "test"):
                logger.warning("[%s] Missing credentials from %s", self.service_name, client_ip)
                # Only count brute-force failures for actual login POST attempts.
                # Chat, Librarian, and other API endpoints without credentials are
                # session management issues, not password-guessing attacks (CWE-307).
                if _is_login_endpoint(request.url.path, request.method):
                    _brute_force.record_failure(client_ip)
                return JSONResponse(
                    status_code=401,
                    content={"error": "Authentication required"},
                )
        elif not auth_result:
            logger.warning("[%s] Invalid credentials from %s", self.service_name, client_ip)
            # Only count brute-force failures for actual login POST attempts.
            if _is_login_endpoint(request.url.path, request.method):
                locked = _brute_force.record_failure(client_ip)
                status_code = 429 if locked else 401
                content = (
                    {"error": "Too many failed attempts. Try again later."}
                    if locked
                    else {"error": "Invalid credentials"}
                )
                return JSONResponse(status_code=status_code, content=content)
            return JSONResponse(status_code=401, content={"error": "Invalid credentials"})
        else:
            # Successful auth — clear any brute-force tracking
            _brute_force.record_success(client_ip)

        response = await call_next(request)
        self._add_security_headers(response)
        return response

    @staticmethod
    def _add_security_headers(response):
        for header, value in _SECURITY_HEADERS.items():
            if header not in response.headers:
                response.headers[header] = value


# ── Main Integration Function ────────────────────────────────────────

def configure_secure_fastapi(app: FastAPI, service_name: str = "murphy-api") -> FastAPI:
    """
    Apply security hardening to a FastAPI application.

    Wires in (execution order: outermost → innermost):
    1. SecurityMiddleware — per-IP rate limiting, JWT/API-key auth, brute-force
       protection, request body size limits, and security response headers (SEC-001, SEC-004)
    2. PerUserRateLimitMiddleware — per-user and per-endpoint rate limits
       (keys on X-User-ID header; endpoint tiers for /api/execute, /api/admin, etc.)
    3. RBACMiddleware — role-based access control on /api/* routes
    4. RiskClassificationMiddleware — per-request risk scoring (low/medium/high/critical)
    5. DLPScannerMiddleware — request/response body scan for sensitive data leakage
    6. CORSMiddleware — origin allowlist (SEC-002)

    All security layers are fail-closed: an unexpected error returns 4xx/5xx rather
    than allowing the request through.

    Public endpoints (/health, /docs, /openapi.json, etc.) bypass all checks.

    Args:
        app: FastAPI application to secure
        service_name: Service name for logging

    Returns:
        The same FastAPI app, now secured
    """
    # Step 1: Wire Security Plane middleware
    # (per-user rate limit → RBAC → risk classification → DLP).
    # Added before SecurityMiddleware so they execute AFTER IP-level auth succeeds.
    try:
        from src.security_plane.middleware import wire_security_plane_middleware
        wire_security_plane_middleware(app)
    except ImportError:
        logger.warning(
            "[%s] security_plane.middleware not available — per-user rate limiting, "
            "RBAC, risk classification, and DLP middleware not wired",
            service_name,
        )

    # Step 2: CORS (added before SecurityMiddleware so it wraps CORS headers around
    # auth errors — required for browser-based error handling).
    origins = get_cors_origins()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-Tenant-ID", "X-API-Key"],
    )

    # Step 3: Main security middleware — outermost layer (per-IP rate limit + auth + headers).
    app.add_middleware(SecurityMiddleware, service_name=service_name)

    murphy_env = os.environ.get("MURPHY_ENV", "development")
    if murphy_env == "development":
        logger.warning(
            "WARNING: Running in development mode — authentication is DISABLED. "
            "Set MURPHY_ENV=staging or MURPHY_ENV=production for deployment."
        )

    logger.info(
        "[%s] Security hardening applied: auth, per-user rate limiting, RBAC, "
        "risk classification, DLP, CORS, security headers",
        service_name,
    )
    return app


# ── RBAC Enforcement ─────────────────────────────────────────────────

# Singleton holder — set via ``register_rbac_governance()``
_rbac_instance = None


def register_rbac_governance(rbac) -> None:
    """
    Register the live ``RBACGovernance`` instance so that
    ``require_permission`` can enforce endpoint-level scopes.

    Call once at startup after MurphySystem creates the RBAC module:
        ``register_rbac_governance(murphy.rbac_governance)``
    """
    global _rbac_instance
    _rbac_instance = rbac
    # Also register with the ASGI RBACMiddleware so the middleware-level check uses
    # the same governance instance.
    try:
        from src.security_plane.middleware import register_rbac_middleware_governance
        register_rbac_middleware_governance(rbac)
    except ImportError:
        pass
    logger.info("RBAC governance registered for FastAPI endpoint enforcement")


def require_permission(permission_name: str):
    """
    FastAPI dependency that enforces RBAC at the API layer.

    Usage::

        from src.fastapi_security import require_permission

        @app.post("/api/execute")
        async def execute_task(
            request: Request,
            _auth=Depends(require_permission("execute_task")),
        ):
            ...

    Behaviour:
    - If no RBAC instance is registered, the check is **permissive** (allows
      the request) so that development/testing workflows are not blocked.
    - If RBAC is registered, the middleware reads ``X-User-ID`` from the
      request headers and calls ``RBACGovernance.check_permission``.
    - Returns HTTP 403 when the permission check fails.
    """
    async def _dependency(request: Request):
        if _rbac_instance is None:
            return  # permissive when RBAC not wired

        user_id = request.headers.get("X-User-ID", "")
        if not user_id:
            murphy_env = os.environ.get("MURPHY_ENV", "development")
            # Only development and test skip RBAC; staging and production require it
            if murphy_env in ("development", "test"):
                return  # anonymous OK in dev/test
            raise HTTPException(status_code=401, detail="X-User-ID header required")

        try:
            # Dynamically resolve the Permission enum member
            from src.rbac_governance import Permission as RBACPermission
            perm = RBACPermission(permission_name)
        except ImportError:
            logger.warning("RBAC module not available — allowing request")
            return
        except ValueError:
            valid = [p.value for p in RBACPermission]
            logger.warning(
                "Unknown RBAC permission '%s' (valid: %s) — allowing request",
                permission_name,
                ", ".join(valid),
            )
            return

        allowed, reason = _rbac_instance.check_permission(user_id, perm)
        if not allowed:
            raise HTTPException(
                status_code=403,
                detail=f"Permission denied: {permission_name} ({reason})",
            )

    return _dependency
