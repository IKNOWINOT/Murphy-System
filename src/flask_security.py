"""
Flask Security Integration for Murphy System

Provides centralized security controls for all Flask API servers:
- API key authentication on all routes (except health checks)
- JWT token validation as an alternative auth method
- CORS origin allowlist (replaces wildcard CORS)
- Rate limiting per client
- Input sanitization
- Security response headers
- Audit logging

Addresses: SEC-001, SEC-002, SEC-004, ARCH-001, ARCH-006

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
"""

import functools
import hmac
import logging
import os
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

try:
    from flask import Flask, Response, jsonify, request
    from flask_cors import CORS
    _HAS_FLASK = True
except ImportError:
    Flask = None  # type: ignore[misc,assignment]
    _HAS_FLASK = False

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
    Validate an API key against configured keys using constant-time comparison
    to prevent timing side-channel attacks (CWE-208).

    Args:
        api_key: The API key to validate

    Returns:
        True if valid, False otherwise
    """
    configured_keys = get_configured_api_keys()
    if not configured_keys:
        # No keys configured — allow in development or test mode only
        murphy_env = os.environ.get("MURPHY_ENV", "development")
        return murphy_env in ("development", "test")
    return any(hmac.compare_digest(api_key, key) for key in configured_keys)


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


def _authenticate_request() -> Optional[bool]:
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


# ── Rate Limiting ────────────────────────────────────────────────────

class _FlaskRateLimiter:
    """Token-bucket rate limiter with swarm detection for Flask requests.

    Two tiers of rate limiting:
    - **Single-call** (default): standard ``burst_size`` tokens refilled at
      ``requests_per_minute`` rate.
    - **Swarm/batch**: when many requests arrive within ``swarm_window_seconds``
      the limiter switches to a higher ``swarm_burst_size``, allowing
      dashboards and batch callers to complete without being throttled.
    """

    import time as _time

    def __init__(
        self,
        requests_per_minute: int = 60,
        burst_size: int = 10,
        swarm_burst_size: int = 0,
        swarm_window_seconds: float = 2.0,
    ):
        self.rpm = requests_per_minute
        self.burst = burst_size
        self.swarm_burst = swarm_burst_size
        self.swarm_window = swarm_window_seconds
        self._buckets: Dict[str, Dict[str, Any]] = {}

    def check(self, client_id: str) -> Dict[str, Any]:
        """Check whether *client_id* has a rate-limit token available."""
        import time
        now = time.monotonic()
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
        swarm_elapsed = now - bucket.get("swarm_window_start", now)
        if swarm_elapsed > self.swarm_window:
            bucket["swarm_tokens"] = self.swarm_burst
            bucket["swarm_window_start"] = now
            bucket["swarm_hits"] = 0

        bucket["swarm_hits"] = bucket.get("swarm_hits", 0) + 1
        is_swarm = bucket["swarm_hits"] > self.burst

        if bucket["tokens"] >= 1:
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


# Global rate limiter instance
_rate_limiter = _FlaskRateLimiter(
    requests_per_minute=60,
    burst_size=20,
    swarm_burst_size=60,
    swarm_window_seconds=2.0,
)


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
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "img-src 'self' data:; "
        "font-src 'self' https://fonts.gstatic.com; connect-src 'self'; "
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


# ── Main Integration Function ────────────────────────────────────────

def configure_secure_app(app: Flask, service_name: str = "murphy-api") -> Flask:
    """
    Apply security hardening to a Flask application.

    This wires in:
    - CORS with origin allowlist (SEC-002)
    - API key authentication on all routes (SEC-001, SEC-004)
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
        allow_headers=["Content-Type", "Authorization", "X-Tenant-ID", "X-API-Key"],
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
                retry_after = int(rate_result.get("retry_after_seconds", 60))
                resp = jsonify({
                    "error": "Rate limit exceeded",
                    "retry_after_seconds": retry_after
                })
                resp.headers['Retry-After'] = str(retry_after)
                return resp, 429

        # API key / JWT authentication
        auth_result = _authenticate_request()
        if auth_result is None:
            # Only development and test skip auth; staging and production require it
            murphy_env = os.environ.get("MURPHY_ENV", "development")
            if murphy_env not in ("development", "test"):
                client_ip = request.remote_addr or "unknown"
                logger.warning(f"[{service_name}] Missing credentials from {client_ip}")
                return jsonify({"error": "Authentication required"}), 401
            # In development / test mode, allow requests without credentials
            return None

        if not auth_result:
            client_ip = request.remote_addr or "unknown"
            logger.warning(f"[{service_name}] Invalid credentials from {client_ip}")
            return jsonify({"error": "Invalid credentials"}), 401

        # Input sanitization for JSON requests
        if request.is_json and request.data:
            try:
                data = request.get_json(silent=True)
                if data and _check_injection(data):
                    logger.warning(f"[{service_name}] Injection attempt from {client_ip}")
                    return jsonify({"error": "Malicious input detected"}), 400
            except Exception as exc:
                logger.debug("Suppressed exception: %s", exc)
                pass  # Non-JSON body, skip sanitization

        return None

    # 3. After-request hook: security headers
    @app.after_request
    def _security_after_request(response: Response) -> Response:
        for header, value in _SECURITY_HEADERS.items():
            response.headers.setdefault(header, value)
        return response

    murphy_env = os.environ.get("MURPHY_ENV", "development")
    if murphy_env == "development":
        logger.warning(
            "WARNING: Running in development mode — authentication is DISABLED. "
            "Set MURPHY_ENV=staging or MURPHY_ENV=production for deployment."
        )

    logger.info(f"[{service_name}] Security hardening applied: auth, CORS, rate limiting, input sanitization, security headers")
    return app
