"""
Flask Security Integration for Murphy System

Provides centralized security controls for all Flask API servers:
- API key authentication on all routes (except health checks)
- CORS origin allowlist (replaces wildcard CORS)
- Rate limiting per client
- Input sanitization
- Security response headers
- Audit logging
- RBAC permission enforcement via ``require_permission`` decorator

Addresses: SEC-001, SEC-002, SEC-004, SEC-005, ARCH-001, ARCH-006

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
"""

import os
import logging
import functools
from typing import List, Optional, Dict, Any, Callable
from datetime import datetime

try:
    from flask import Flask, request, jsonify, Response, g
    from flask_cors import CORS
    _HAS_FLASK = True
except ImportError:
    Flask = None  # type: ignore[misc,assignment]
    _HAS_FLASK = False

try:
    from rbac_governance import RBACGovernance, Permission, Role  # type: ignore[import-untyped]
except ImportError:
    try:
        from .rbac_governance import RBACGovernance, Permission, Role
    except ImportError:
        from src.rbac_governance import RBACGovernance, Permission, Role

logger = logging.getLogger(__name__)

# Global RBAC instance shared across all secured Flask apps.
_rbac: Optional[RBACGovernance] = None


def get_rbac() -> RBACGovernance:
    """Return the global RBAC governance instance, creating one if needed."""
    global _rbac
    if _rbac is None:
        _rbac = RBACGovernance()
    return _rbac


def set_rbac(rbac: RBACGovernance) -> None:
    """Set the global RBAC governance instance (useful for testing)."""
    global _rbac
    _rbac = rbac


# ── Environment Utilities ────────────────────────────────────────────

def is_debug_mode() -> bool:
    """
    Check if debug mode is enabled based on MURPHY_ENV.

    Returns True only when MURPHY_ENV is 'development' (the default).
    Production, staging, and other environments disable debug mode.
    """
    return os.environ.get('MURPHY_ENV', 'development') == 'development'


# ── CORS Configuration ──────────────────────────────────────────────

def get_cors_origins() -> List[str]:
    """
    Get allowed CORS origins from environment.
    
    Reads MURPHY_CORS_ORIGINS env var (comma-separated).
    Defaults to localhost origins for development.
    
    Returns:
        List of allowed origin strings
    """
    default_origins = "http://localhost:3000,http://localhost:8080,http://localhost:8000"
    origins_str = os.environ.get("MURPHY_CORS_ORIGINS", default_origins)
    origins = [o.strip() for o in origins_str.split(",") if o.strip()]
    return origins


# ── API Key Validation ──────────────────────────────────────────────

def get_configured_api_keys() -> List[str]:
    """
    Get configured API keys from environment.
    
    Reads MURPHY_API_KEYS env var (comma-separated).
    Returns empty list if not configured (auth disabled in dev mode).
    """
    keys_str = os.environ.get("MURPHY_API_KEYS", "")
    if not keys_str:
        return []
    return [k.strip() for k in keys_str.split(",") if k.strip()]


def validate_api_key(api_key: str) -> bool:
    """
    Validate an API key against configured keys.
    
    Args:
        api_key: The API key to validate
        
    Returns:
        True if valid, False otherwise
    """
    configured_keys = get_configured_api_keys()
    if not configured_keys:
        # No keys configured — allow in development mode only
        murphy_env = os.environ.get("MURPHY_ENV", "development")
        if murphy_env == "development":
            return True
        return False
    return api_key in configured_keys


def _extract_api_key() -> Optional[str]:
    """Extract API key from request headers."""
    # Check Authorization: Bearer <token>
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:].strip()
    
    # Check X-API-Key header
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

class _FlaskRateLimiter:
    """Simple token-bucket rate limiter for Flask requests."""
    
    import time as _time
    
    def __init__(self, requests_per_minute: int = 60, burst_size: int = 10):
        self.rpm = requests_per_minute
        self.burst = burst_size
        self._buckets: Dict[str, Dict[str, Any]] = {}
    
    def check(self, client_id: str) -> Dict[str, Any]:
        import time
        now = time.monotonic()
        if client_id not in self._buckets:
            self._buckets[client_id] = {
                "tokens": self.burst,
                "last_refill": now,
            }
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


# Global rate limiter instance
_rate_limiter = _FlaskRateLimiter(requests_per_minute=60, burst_size=20)


# ── Security Headers ────────────────────────────────────────────────

_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
        "font-src 'self'; connect-src 'self'; "
        "frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    ),
}


# ── Input Sanitization ──────────────────────────────────────────────

import re

_INJECTION_PATTERNS = [
    re.compile(r"<script[^>]*>", re.IGNORECASE),
    re.compile(r"javascript:", re.IGNORECASE),
    re.compile(r";\s*(DROP|DELETE|UPDATE|INSERT|ALTER)\s", re.IGNORECASE),
    re.compile(r"\.\./", re.IGNORECASE),
]


def _check_injection(data: Any) -> bool:
    """Check for injection patterns in request data. Returns True if threat detected."""
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


# ── RBAC Permission Decorator ────────────────────────────────────────

def require_permission(*permissions: Permission) -> Callable:
    """Flask route decorator that enforces RBAC permissions (SEC-005).

    Usage::

        @app.route("/api/admin/config", methods=["POST"])
        @require_permission(Permission.CONFIGURE_SYSTEM)
        def admin_config():
            ...

    The decorator reads ``g.rbac_user_id`` (set by ``configure_secure_app``'s
    before-request hook) and checks that the user holds **all** listed
    permissions via the global :class:`RBACGovernance` instance.

    In development mode (``MURPHY_ENV=development``) the check is skipped so
    unauthenticated local testing continues to work.
    """

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Skip enforcement in development mode
            if is_debug_mode():
                return fn(*args, **kwargs)

            rbac = get_rbac()
            user_id = getattr(g, "rbac_user_id", None)
            if user_id is None:
                return jsonify({"error": "User identity not provided"}), 403

            for perm in permissions:
                allowed, reason = rbac.check_permission(user_id, perm)
                if not allowed:
                    logger.warning(
                        "RBAC denied %s for user %s: %s", perm.value, user_id, reason
                    )
                    return jsonify({
                        "error": "Forbidden",
                        "detail": f"Missing permission: {perm.value}",
                    }), 403

            return fn(*args, **kwargs)

        return wrapper

    return decorator


# ── Main Integration Function ────────────────────────────────────────

def configure_secure_app(app: Flask, service_name: str = "murphy-api") -> Flask:
    """
    Apply security hardening to a Flask application.
    
    This wires in:
    - CORS with origin allowlist (SEC-002)
    - API key authentication on all routes (SEC-001, SEC-004)
    - RBAC user/tenant context extraction (SEC-005)
    - Rate limiting per client IP (ARCH-006)
    - Input sanitization (ARCH-001)
    - Security response headers
    - Audit logging
    
    Args:
        app: Flask application to secure
        service_name: Service name for logging
        
    Returns:
        The same Flask app, now secured
    """
    # 1. Replace wildcard CORS with origin allowlist
    origins = get_cors_origins()
    CORS(
        app,
        origins=origins,
        supports_credentials=True,
        allow_headers=["Content-Type", "Authorization", "X-Tenant-ID", "X-User-ID", "X-API-Key"],
        methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"]
    )
    logger.info(f"[{service_name}] CORS configured with allowed origins: {origins}")
    
    # 2. Before-request hook: authentication + rate limiting + input sanitization
    @app.before_request
    def _security_before_request():
        # Skip auth for health endpoints and OPTIONS (CORS preflight)
        if request.method == "OPTIONS":
            return None
        if _is_health_endpoint(request.path):
            return None
        
        # Rate limiting by client IP (skip in testing mode)
        if not app.config.get('TESTING'):
            client_ip = request.remote_addr or "unknown"
            rate_result = _rate_limiter.check(client_ip)
            if not rate_result["allowed"]:
                logger.warning(f"[{service_name}] Rate limit exceeded for {client_ip}")
                return jsonify({
                    "error": "Rate limit exceeded",
                    "retry_after_seconds": rate_result.get("retry_after_seconds", 60)
                }), 429
        
        # API key authentication
        api_key = _extract_api_key()
        if api_key is None:
            # Check if auth is required (production mode)
            murphy_env = os.environ.get("MURPHY_ENV", "development")
            if murphy_env != "development":
                logger.warning(f"[{service_name}] Missing API key from {client_ip}")
                return jsonify({"error": "Authentication required"}), 401
            # In development mode, allow requests without API key
            return None
        
        if not validate_api_key(api_key):
            logger.warning(f"[{service_name}] Invalid API key from {client_ip}")
            return jsonify({"error": "Invalid API key"}), 401
        
        # Store RBAC context for downstream @require_permission checks (SEC-005).
        # Headers: X-User-ID identifies the caller, X-Tenant-ID scopes the tenant.
        g.rbac_user_id = request.headers.get("X-User-ID")
        g.rbac_tenant_id = request.headers.get("X-Tenant-ID")
        
        # Input sanitization for JSON requests
        if request.is_json and request.data:
            try:
                data = request.get_json(silent=True)
                if data and _check_injection(data):
                    logger.warning(f"[{service_name}] Injection attempt from {client_ip}")
                    return jsonify({"error": "Malicious input detected"}), 400
            except Exception:
                pass  # Non-JSON body, skip sanitization
        
        return None
    
    # 3. After-request hook: security headers
    @app.after_request
    def _security_after_request(response: Response) -> Response:
        for header, value in _SECURITY_HEADERS.items():
            response.headers.setdefault(header, value)
        return response
    
    logger.info(f"[{service_name}] Security hardening applied: auth, CORS, RBAC, rate limiting, input sanitization, security headers")
    return app
