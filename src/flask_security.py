"""
Flask Security Integration for Murphy System

Provides centralized security controls for all Flask API servers:
- API key authentication on all routes (except health checks)
- JWT token validation as an alternative auth method
- CORS origin allowlist (replaces wildcard CORS)
- Rate limiting per client with X-RateLimit-* response headers
- CSRF token validation for all state-changing Flask routes (POST/PUT/PATCH/DELETE)
- Input sanitization
- Security response headers (HSTS, CSP, X-Frame-Options, X-Content-Type-Options)
- Audit logging

Addresses: SEC-001, SEC-002, SEC-004, ARCH-001, ARCH-006, SEC-005 (CSRF), SEC-006 (Rate-limit headers)

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
"""

import functools
import hashlib
import hmac
import logging
import os
import re
import secrets
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

try:
    from flask import Flask, Response, g, jsonify, request
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

    Reads MURPHY_API_KEY env var (canonical; MURPHY_API_KEYS accepted as legacy alias).
    Returns empty list if not configured (auth disabled in dev mode).
    """
    keys_str = os.environ.get("MURPHY_API_KEY", "") or os.environ.get("MURPHY_API_KEYS", "")
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

        seconds_per_token = 60.0 / self.rpm if self.rpm > 0 else 60.0
        reset_after = max(0.0, seconds_per_token - (time.monotonic() - bucket["last_refill"]))
        reset_epoch = int(time.time() + reset_after)

        if bucket["tokens"] >= 1:
            bucket["tokens"] -= 1
            return {
                "allowed": True,
                "remaining": int(bucket["tokens"]),
                "limit": self.burst,
                "reset_after_seconds": reset_after,
                "reset_epoch": reset_epoch,
            }

        # Standard tokens exhausted — check swarm allowance
        if is_swarm and bucket.get("swarm_tokens", 0) >= 1:
            bucket["swarm_tokens"] -= 1
            return {
                "allowed": True,
                "remaining": int(bucket["swarm_tokens"]),
                "limit": self.swarm_burst,
                "reset_after_seconds": reset_after,
                "reset_epoch": reset_epoch,
                "swarm_mode": True,
            }

        retry_after = (1 - bucket["tokens"]) * seconds_per_token
        return {
            "allowed": False,
            "remaining": 0,
            "retry_after_seconds": retry_after,
            "limit": self.burst,
            "reset_epoch": int(time.time() + retry_after),
        }


# Global rate limiter instance
_rate_limiter = _FlaskRateLimiter(
    # Defaults are intentionally high to accommodate multi-cursor (70 parallel
    # actions), swarm agents, automation triggers, and sensor-style polling
    # throughout the Murphy System UI and backend.  Override via env vars to
    # tighten limits in resource-constrained environments.
    requests_per_minute=int(os.environ.get("MURPHY_RATE_LIMIT_RPM", "600")),
    burst_size=int(os.environ.get("MURPHY_RATE_LIMIT_BURST", "200")),
    swarm_burst_size=int(os.environ.get("MURPHY_RATE_LIMIT_SWARM_BURST", "500")),
    swarm_window_seconds=float(os.environ.get("MURPHY_RATE_LIMIT_SWARM_WINDOW", "1.0")),
)


# ── CSRF Protection ──────────────────────────────────────────────────

# Methods that mutate state and require a valid CSRF token
_CSRF_PROTECTED_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

# Paths exempt from CSRF validation (login/logout supply credentials directly)
_CSRF_EXEMPT_PATHS = frozenset({
    "/api/auth/login",
    "/api/auth/logout",
    "/api/auth/signup",
    "/api/auth/register",
    "/api/auth/callback",
})

# Secret used to sign CSRF tokens.  Override with MURPHY_CSRF_SECRET env var.
_CSRF_SECRET = os.environ.get("MURPHY_CSRF_SECRET", "")


class FlaskCSRFProtection:
    """Stateless CSRF protection for Flask using HMAC-signed double-submit tokens.

    A CSRF token is ``HMAC-SHA256(csrf_secret, session_id)`` rendered as a
    hex string.  The client receives the token in the ``X-CSRF-Token`` response
    header on GET requests, and must echo it back in the ``X-CSRF-Token``
    *request* header on every state-changing (POST/PUT/PATCH/DELETE) call.

    Stateless design means no server-side session store is required.

    When ``MURPHY_CSRF_SECRET`` is not configured (development / test) the
    check is skipped to avoid blocking local workflows.  In staging/production
    the env var must be set or every mutation request will be rejected with 403.
    """

    @staticmethod
    def generate_token(session_id: str) -> str:
        """Return an HMAC-SHA256 CSRF token for *session_id*."""
        if not _CSRF_SECRET:
            return hashlib.sha256(session_id.encode()).hexdigest()
        return hmac.new(
            _CSRF_SECRET.encode(),
            session_id.encode(),
            hashlib.sha256,
        ).hexdigest()

    @staticmethod
    def validate_token(session_id: str, submitted_token: str) -> bool:
        """Return True if *submitted_token* is valid for *session_id*."""
        if not submitted_token:
            return False
        expected = FlaskCSRFProtection.generate_token(session_id)
        return hmac.compare_digest(expected, submitted_token)

    @staticmethod
    def is_exempt(path: str, method: str) -> bool:
        """Return True if this request does NOT require CSRF validation."""
        if method.upper() not in _CSRF_PROTECTED_METHODS:
            return True
        normalized = path.rstrip("/")
        return normalized in _CSRF_EXEMPT_PATHS

    @classmethod
    def check_current_request(cls) -> Optional[str]:
        """Validate the CSRF token on the current Flask request.

        Returns ``None`` on success, or an error message string on failure.
        Skips validation when ``MURPHY_CSRF_SECRET`` is unset in dev/test.
        """
        murphy_env = os.environ.get("MURPHY_ENV", "development")
        if not _CSRF_SECRET and murphy_env in ("development", "test"):
            return None

        if cls.is_exempt(request.path, request.method):
            return None

        # Derive a session identifier from the session cookie or Authorization header
        session_id = (
            request.cookies.get("murphy_session", "")
            or request.headers.get("Authorization", "")
            or (request.remote_addr or "unknown")
        )

        submitted = request.headers.get("X-CSRF-Token", "").strip()
        if not submitted:
            return "Missing X-CSRF-Token header"

        if not cls.validate_token(session_id, submitted):
            logger.warning(
                "CSRF validation failed for %s %s (session prefix=%s…)",
                request.method,
                request.path,
                session_id[:8],
            )
            return "Invalid CSRF token"

        return None


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
    - API key / JWT authentication on all routes (SEC-001, SEC-004)
    - CSRF token validation for POST/PUT/PATCH/DELETE routes (SEC-005)
    - Rate limiting per client IP with X-RateLimit-* response headers (SEC-006)
    - Input sanitization (ARCH-001)
    - Security response headers: HSTS, CSP, X-Frame-Options, X-Content-Type-Options

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
        allow_headers=[
            "Content-Type", "Authorization", "X-Tenant-ID", "X-API-Key",
            "X-CSRF-Token",  # clients echo this for state-changing requests
        ],
        methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"]
    )
    logger.info("[%s] CORS configured with allowed origins: %s", service_name, origins)

    # 2. Before-request hook: rate limiting + auth + CSRF + input sanitization
    @app.before_request
    def _security_before_request():
        # Skip auth for health endpoints and OPTIONS (CORS preflight)
        if request.method == "OPTIONS":
            return None
        if _is_health_endpoint(request.path):
            return None

        client_ip = request.remote_addr or "unknown"

        # Rate limiting by client IP (skip in testing mode)
        rate_result = None
        if not app.config.get('TESTING'):
            rate_result = _rate_limiter.check(client_ip)
            if not rate_result["allowed"]:
                logger.warning("[%s] Rate limit exceeded for %s", service_name, client_ip)
                retry_after = int(rate_result.get("retry_after_seconds", 60))
                resp = jsonify({
                    "error": "Rate limit exceeded",
                    "retry_after_seconds": retry_after
                })
                resp.headers["Retry-After"] = str(retry_after)
                resp.headers["X-RateLimit-Limit"] = str(rate_result.get("limit", 0))
                resp.headers["X-RateLimit-Remaining"] = "0"
                resp.headers["X-RateLimit-Reset"] = str(rate_result.get("reset_epoch", 0))
                return resp, 429
            # Store for after_request to attach informational headers
            g.rate_result = rate_result

        # API key / JWT authentication
        auth_result = _authenticate_request()
        if auth_result is None:
            # Only development and test skip auth; staging and production require it
            murphy_env = os.environ.get("MURPHY_ENV", "development")
            if murphy_env not in ("development", "test"):
                logger.warning("[%s] Missing credentials from %s", service_name, client_ip)
                return jsonify({"error": "Authentication required"}), 401
            # In development / test mode, allow requests without credentials
            return None

        if not auth_result:
            logger.warning("[%s] Invalid credentials from %s", service_name, client_ip)
            return jsonify({"error": "Invalid credentials"}), 401

        # CSRF validation for state-changing endpoints (SEC-005)
        csrf_error = FlaskCSRFProtection.check_current_request()
        if csrf_error:
            logger.warning(
                "[%s] CSRF check failed for %s %s from %s: %s",
                service_name, request.method, request.path, client_ip, csrf_error,
            )
            return jsonify({"error": csrf_error}), 403

        # Input sanitization for JSON requests
        if request.is_json and request.data:
            try:
                data = request.get_json(silent=True)
                if data and _check_injection(data):
                    logger.warning("[%s] Injection attempt from %s", service_name, client_ip)
                    return jsonify({"error": "Malicious input detected"}), 400
            except Exception as exc:
                logger.debug("Suppressed exception during injection check: %s", exc)

        return None

    # 3. After-request hook: security headers + rate-limit headers
    @app.after_request
    def _security_after_request(response: Response) -> Response:
        for header, value in _SECURITY_HEADERS.items():
            response.headers.setdefault(header, value)
        # Attach X-RateLimit-* informational headers (SEC-006)
        rate_result = getattr(g, "rate_result", None)
        if rate_result:
            response.headers.setdefault("X-RateLimit-Limit", str(rate_result.get("limit", 0)))
            response.headers.setdefault("X-RateLimit-Remaining", str(rate_result.get("remaining", 0)))
            response.headers.setdefault("X-RateLimit-Reset", str(rate_result.get("reset_epoch", 0)))
        return response

    murphy_env = os.environ.get("MURPHY_ENV", "development")
    if murphy_env == "development":
        logger.warning(
            "WARNING: Running in development mode — authentication is DISABLED. "
            "Set MURPHY_ENV=staging or MURPHY_ENV=production for deployment."
        )

    logger.info(
        "[%s] Security hardening applied: auth, CSRF, CORS, rate limiting, "
        "input sanitization, security headers",
        service_name,
    )
    return app
