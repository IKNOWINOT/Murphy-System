"""
FastAPI Security Integration for Murphy System

Provides centralized security controls for all FastAPI API servers:
- API key authentication on all routes (except health checks)
- CORS origin allowlist (replaces wildcard CORS)
- Rate limiting per client
- Input sanitization
- Security response headers

Mirrors flask_security.py for FastAPI services.

Addresses: SEC-001, SEC-002, SEC-004

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
"""

import os
import re
import hmac
import time
import logging
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


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


def _is_health_endpoint(path: str) -> bool:
    """Check if the request path is a health/readiness/metrics endpoint."""
    normalized = path.rstrip("/")
    exempt_suffixes = ("/health", "/healthz", "/ready", "/metrics")
    return any(normalized.endswith(s) or normalized == s[1:] for s in exempt_suffixes)


# ── Rate Limiting ────────────────────────────────────────────────────

class _FastAPIRateLimiter:
    """Simple token-bucket rate limiter with TTL-based cleanup."""

    _BUCKET_TTL_SECONDS = 3600  # Evict buckets inactive for 1 hour
    _CLEANUP_INTERVAL = 300     # Run cleanup every 5 minutes

    def __init__(self, requests_per_minute: int = 60, burst_size: int = 20):
        self.rpm = requests_per_minute
        self.burst = burst_size
        self._buckets: Dict[str, Dict[str, Any]] = {}
        self._last_cleanup: float = time.monotonic()

    def check(self, client_id: str) -> Dict[str, Any]:
        """Check whether *client_id* has a rate-limit token available."""
        now = time.monotonic()

        # Periodic stale-bucket cleanup (CWE-400 mitigation)
        if now - self._last_cleanup > self._CLEANUP_INTERVAL:
            self._evict_stale_buckets(now)

        if client_id not in self._buckets:
            self._buckets[client_id] = {"tokens": self.burst, "last_refill": now}
        bucket = self._buckets[client_id]
        elapsed = now - bucket["last_refill"]
        refill = elapsed * (self.rpm / 60.0)
        bucket["tokens"] = min(self.burst, bucket["tokens"] + refill)
        bucket["last_refill"] = now

        if bucket["tokens"] >= 1:
            bucket["tokens"] -= 1
            return {"allowed": True, "remaining": int(bucket["tokens"])}
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
)


# ── Input Sanitization ──────────────────────────────────────────────

_INJECTION_PATTERNS = [
    re.compile(r"<script[^>]*>", re.IGNORECASE),
    re.compile(r"javascript:", re.IGNORECASE),
    re.compile(r";\s*(DROP|DELETE|UPDATE|INSERT|ALTER)\s", re.IGNORECASE),
    re.compile(r"\.\./", re.IGNORECASE),
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
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "img-src 'self' data: https://fastapi.tiangolo.com; "
        "font-src 'self' https://cdn.jsdelivr.net; "
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

        # Rate limiting by client IP
        client_ip = request.client.host if request.client else "unknown"
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

        # API key authentication
        api_key = _extract_api_key(request)
        if api_key is None:
            murphy_env = os.environ.get("MURPHY_ENV", "development")
            if murphy_env not in ("development", "test"):
                logger.warning("[%s] Missing API key from %s", self.service_name, client_ip)
                return JSONResponse(
                    status_code=401,
                    content={"error": "Authentication required"},
                )
        elif not validate_api_key(api_key):
            logger.warning("[%s] Invalid API key from %s", self.service_name, client_ip)
            return JSONResponse(
                status_code=401,
                content={"error": "Invalid API key"},
            )

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

    Wires in:
    - CORS with origin allowlist (SEC-002)
    - API key authentication on all routes (SEC-001, SEC-004)
    - Rate limiting per client IP
    - Security response headers

    Args:
        app: FastAPI application to secure
        service_name: Service name for logging

    Returns:
        The same FastAPI app, now secured
    """
    # 1. Replace wildcard CORS with origin allowlist
    origins = get_cors_origins()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-Tenant-ID", "X-API-Key"],
    )

    # 2. Security middleware (auth + rate limiting + headers)
    app.add_middleware(SecurityMiddleware, service_name=service_name)

    murphy_env = os.environ.get("MURPHY_ENV", "development")
    if murphy_env == "development":
        logger.warning(
            "⚠️ Authentication is DISABLED in development mode. "
            "Set MURPHY_ENV=production to enable."
        )

    logger.info(
        f"[{service_name}] Security hardening applied: auth, CORS, rate limiting, security headers"
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
