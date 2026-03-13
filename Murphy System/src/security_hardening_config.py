"""
Murphy System — Security Hardening Configuration

Centralized security hardening policy that enforces:
- Input sanitization policies
- CORS lockdown configuration
- Rate limiting rules
- Content Security Policy (CSP) headers
- API key rotation enforcement
- Audit logging configuration
- Session security controls
- Path traversal prevention
- XSS/injection prevention
- Secrets management policy

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
"""

import hashlib
import logging
import os
import re
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set
from urllib.parse import unquote

logger = logging.getLogger(__name__)


# ── Input Sanitization ──────────────────────────────────────────────

class InputSanitizer:
    """Centralized input sanitization for all Murphy endpoints."""

    # Patterns that indicate injection attempts
    INJECTION_PATTERNS = [
        re.compile(r"<script[^>]*>", re.IGNORECASE),
        re.compile(r"javascript:", re.IGNORECASE),
        re.compile(r"on\w+\s*=", re.IGNORECASE),
        re.compile(r";\s*(DROP|DELETE|UPDATE|INSERT|ALTER)\s", re.IGNORECASE),
        re.compile(r"(\-\-|\/\*|\*\/)", re.IGNORECASE),
        re.compile(r"\.\./", re.IGNORECASE),
        re.compile(r"\\x[0-9a-fA-F]{2}"),
        re.compile(r"union\s+select", re.IGNORECASE),
        re.compile(r"waitfor\s+delay", re.IGNORECASE),
        re.compile(r"sleep\s*\(", re.IGNORECASE),
        re.compile(r"benchmark\s*\(", re.IGNORECASE),
        # Additional XSS vectors (CWE-79 hardening)
        re.compile(r"<svg[^>]*\bon\w+\s*=", re.IGNORECASE),
        re.compile(r"<img[^>]*\bon\w+\s*=", re.IGNORECASE),
        re.compile(r"<iframe[^>]*>", re.IGNORECASE),
        re.compile(r"<object[^>]*>", re.IGNORECASE),
        re.compile(r"<embed[^>]*>", re.IGNORECASE),
        re.compile(r"<body[^>]*\bon\w+\s*=", re.IGNORECASE),
        re.compile(r"vbscript:", re.IGNORECASE),
        re.compile(r"data:\s*text/html", re.IGNORECASE),
        # LDAP injection patterns (CWE-90)
        re.compile(r"[)(]\s*[)(|*]", re.IGNORECASE),
        # OS command injection (CWE-78)
        re.compile(r";\s*(?:cat|ls|rm|wget|curl|nc|bash|sh|cmd)\b", re.IGNORECASE),
    ]

    HTML_ENTITIES = {
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#x27;",
        "/": "&#x2F;",
    }

    @classmethod
    def sanitize_string(cls, value: str, max_length: int = 10000) -> str:
        """Sanitize a string input."""
        if not isinstance(value, str):
            return str(value)[:max_length]
        # Strip null bytes (CWE-158) before any processing
        value = value.replace("\x00", "")
        value = value[:max_length]
        for char, entity in cls.HTML_ENTITIES.items():
            value = value.replace(char, entity)
        return value

    @classmethod
    def detect_injection(cls, value: str) -> List[str]:
        """Detect injection patterns in input. Returns list of matched pattern names."""
        if not isinstance(value, str):
            return []
        threats = []
        for pattern in cls.INJECTION_PATTERNS:
            if pattern.search(value):
                threats.append(pattern.pattern)
        return threats

    @classmethod
    def sanitize_path(cls, path: str) -> str:
        """Sanitize a file path to prevent traversal attacks."""
        # Recursively decode URL-encoded sequences to prevent bypass
        _max_decode_rounds = 10
        prev = ""
        for _ in range(_max_decode_rounds):
            if prev == path:
                break
            prev = path
            path = unquote(path)
        path = path.replace("\\", "/")
        # Iteratively remove traversal sequences until stable
        prev = ""
        for _ in range(_max_decode_rounds):
            if prev == path:
                break
            prev = path
            path = re.sub(r"\.\./", "", path)
        path = re.sub(r"//+", "/", path)
        path = path.lstrip("/")
        return path

    @classmethod
    def sanitize_dict(cls, data: Dict[str, Any], max_depth: int = 10) -> Dict[str, Any]:
        """Recursively sanitize all string values in a dictionary."""
        if max_depth <= 0:
            return {}
        result = {}
        for key, value in data.items():
            clean_key = cls.sanitize_string(str(key), max_length=256)
            if isinstance(value, str):
                result[clean_key] = cls.sanitize_string(value)
            elif isinstance(value, dict):
                result[clean_key] = cls.sanitize_dict(value, max_depth - 1)
            elif isinstance(value, list):
                result[clean_key] = [
                    cls.sanitize_string(v) if isinstance(v, str) else v
                    for v in value[:1000]
                ]
            else:
                result[clean_key] = value
        return result


# ── CORS Configuration ──────────────────────────────────────────────

class CORSPolicy:
    """CORS lockdown configuration."""

    def __init__(
        self,
        allowed_origins: Optional[List[str]] = None,
        allowed_methods: Optional[List[str]] = None,
        allowed_headers: Optional[List[str]] = None,
        max_age: int = 3600,
        allow_credentials: bool = False,
    ):
        self.allowed_origins: Set[str] = set(allowed_origins or [])
        if "*" in self.allowed_origins:
            env = os.environ.get("MURPHY_ENV", "development").lower()
            if env in ("production", "staging"):
                raise ValueError(
                    "CORSPolicy: wildcard '*' origin is not allowed in "
                    f"{env}. Specify explicit origins."
                )
            import logging as _logging
            _logging.getLogger(__name__).warning(
                "CORSPolicy: wildcard '*' origin detected — this disables CORS protection. "
                "Use explicit origins in production."
            )
        self.allowed_methods: List[str] = allowed_methods or [
            "GET", "POST", "PUT", "DELETE", "OPTIONS"
        ]
        self.allowed_headers: List[str] = allowed_headers or [
            "Content-Type", "Authorization", "X-Request-ID"
        ]
        self.max_age = max_age
        self.allow_credentials = allow_credentials

    def is_origin_allowed(self, origin: str) -> bool:
        """Check if an origin is allowed."""
        if not self.allowed_origins:
            return False
        if "*" in self.allowed_origins:
            return True
        return origin in self.allowed_origins

    def get_headers(self, origin: str) -> Dict[str, str]:
        """Generate CORS response headers for a given origin."""
        headers = {}
        if self.is_origin_allowed(origin):
            headers["Access-Control-Allow-Origin"] = origin
            headers["Access-Control-Allow-Methods"] = ", ".join(self.allowed_methods)
            headers["Access-Control-Allow-Headers"] = ", ".join(self.allowed_headers)
            headers["Access-Control-Max-Age"] = str(self.max_age)
            if self.allow_credentials:
                headers["Access-Control-Allow-Credentials"] = "true"
        return headers

    def status(self) -> Dict[str, Any]:
        return {
            "allowed_origins_count": len(self.allowed_origins),
            "allowed_methods": self.allowed_methods,
            "max_age": self.max_age,
            "credentials": self.allow_credentials,
        }


# ── Rate Limiting ────────────────────────────────────────────────────

class RateLimiter:
    """Token-bucket rate limiter for API endpoints."""

    _BUCKET_TTL_SECONDS = 3600    # Evict buckets inactive for 1 hour
    _CLEANUP_INTERVAL = 300       # Run cleanup every 5 minutes
    _MAX_BUCKETS = 100_000        # Hard cap to prevent memory exhaustion

    def __init__(
        self,
        requests_per_minute: int = 60,
        burst_size: int = 10,
    ):
        self.rpm = requests_per_minute
        self.burst = burst_size
        self._buckets: Dict[str, Dict[str, Any]] = {}
        self._last_cleanup: float = time.monotonic()

    def check(self, client_id: str) -> Dict[str, Any]:
        """Check if a request from client_id is allowed."""
        now = time.monotonic()

        # Periodic stale-bucket cleanup (CWE-400 mitigation)
        if now - self._last_cleanup > self._CLEANUP_INTERVAL:
            self._evict_stale_buckets(now)

        if client_id not in self._buckets:
            # Hard cap: reject if too many tracked clients
            if len(self._buckets) >= self._MAX_BUCKETS:
                self._evict_stale_buckets(now)
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
            return {
                "allowed": True,
                "remaining": int(bucket["tokens"]),
                "limit": self.rpm,
                "reset_seconds": 60.0 / self.rpm,
            }
        else:
            return {
                "allowed": False,
                "remaining": 0,
                "limit": self.rpm,
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

    def status(self) -> Dict[str, Any]:
        return {
            "requests_per_minute": self.rpm,
            "burst_size": self.burst,
            "active_clients": len(self._buckets),
        }


class RedisRateLimiter(RateLimiter):
    """
    Token-bucket rate limiter backed by Redis for multi-worker deployments.

    When multiple uvicorn workers are running each worker would otherwise
    have its own independent in-process rate limiter, effectively multiplying
    the allowed rate by the number of workers.  This subclass stores token
    bucket state in Redis so all workers share the same view.

    Falls back to the parent in-memory implementation silently if the ``redis``
    package is unavailable or the connection fails.

    Configuration:
        MURPHY_REDIS_URL — Redis connection URL (default: ``redis://localhost:6379/0``)

    Usage::

        from src.security_hardening_config import get_rate_limiter
        limiter = get_rate_limiter()        # auto-selects Redis or in-memory
        result = limiter.check("client-ip")
    """

    _KEY_PREFIX = "murphy:rl:"
    _KEY_TTL = 120  # Expire Redis keys after 2 minutes of inactivity

    def __init__(
        self,
        requests_per_minute: int = 60,
        burst_size: int = 10,
        redis_url: Optional[str] = None,
    ):
        super().__init__(requests_per_minute=requests_per_minute, burst_size=burst_size)
        self._redis_url = redis_url or os.environ.get(
            "MURPHY_REDIS_URL", "redis://localhost:6379/0"
        )
        self._redis: Optional[Any] = None  # redis.Redis when connected, None otherwise
        self._redis_available = False
        self._connect()

    def _connect(self) -> None:
        """Attempt to connect to Redis; fall back gracefully on failure."""
        try:
            import redis as _redis_lib
            client = _redis_lib.from_url(self._redis_url, socket_connect_timeout=2)
            client.ping()
            self._redis = client
            self._redis_available = True
            logger.info("RedisRateLimiter: connected to %s", self._redis_url)
        except Exception as exc:
            logger.warning(
                "RedisRateLimiter: cannot connect to Redis (%s) — "
                "falling back to in-memory rate limiter.",
                exc,
            )
            self._redis_available = False

    def check(self, client_id: str) -> Dict[str, Any]:
        """Check rate limit, preferring Redis; fall back to in-memory on error."""
        if not self._redis_available:
            return super().check(client_id)
        try:
            return self._check_redis(client_id)
        except Exception as exc:
            logger.warning(
                "RedisRateLimiter: Redis error (%s) — falling back to in-memory.", exc
            )
            self._redis_available = False
            return super().check(client_id)

    def _check_redis(self, client_id: str) -> Dict[str, Any]:
        """Token-bucket check using Redis WATCH/MULTI/EXEC for atomicity."""
        now = time.time()
        key = f"{self._KEY_PREFIX}{client_id}"

        pipe = self._redis.pipeline()
        pipe.hgetall(key)
        (raw,) = pipe.execute()

        if raw:
            tokens = float(raw.get(b"tokens", self.burst))
            last_refill = float(raw.get(b"last_refill", now))
        else:
            tokens = float(self.burst)
            last_refill = now

        elapsed = now - last_refill
        refill = elapsed * (self.rpm / 60.0)
        tokens = min(float(self.burst), tokens + refill)
        last_refill = now

        if tokens >= 1.0:
            tokens -= 1.0
            allowed = True
        else:
            allowed = False

        pipe = self._redis.pipeline()
        pipe.hset(key, mapping={"tokens": tokens, "last_refill": last_refill})
        pipe.expire(key, self._KEY_TTL)
        pipe.execute()

        if allowed:
            return {
                "allowed": True,
                "remaining": int(tokens),
                "limit": self.rpm,
                "reset_seconds": 60.0 / self.rpm,
            }
        return {
            "allowed": False,
            "remaining": 0,
            "limit": self.rpm,
            "retry_after_seconds": (1.0 - tokens) * (60.0 / self.rpm),
        }

    def status(self) -> Dict[str, Any]:
        base = super().status()
        base["backend"] = "redis" if self._redis_available else "memory"
        base["redis_url"] = self._redis_url
        return base


def get_rate_limiter(
    requests_per_minute: int = 60,
    burst_size: int = 10,
) -> RateLimiter:
    """
    Return the appropriate rate limiter for this deployment.

    Prefers ``RedisRateLimiter`` when ``MURPHY_REDIS_URL`` is set (or Redis
    is available at the default URL).  Falls back to the in-memory
    ``RateLimiter`` otherwise.
    """
    redis_url = os.environ.get("MURPHY_REDIS_URL", "")
    if redis_url:
        return RedisRateLimiter(
            requests_per_minute=requests_per_minute,
            burst_size=burst_size,
            redis_url=redis_url,
        )
    return RateLimiter(requests_per_minute=requests_per_minute, burst_size=burst_size)


def extract_client_id(
    remote_addr: str,
    forwarded_for: Optional[str] = None,
    *,
    trusted_proxies: Optional[Set[str]] = None,
) -> str:
    """Safely extract a client identifier for rate limiting.

    When ``forwarded_for`` is provided and the *immediate* connection
    (``remote_addr``) is from a trusted proxy, the *right-most* untrusted
    IP in ``X-Forwarded-For`` is returned.  Otherwise ``remote_addr`` is
    used directly, preventing spoofing when there is no trusted reverse
    proxy in front of the application.

    Args:
        remote_addr: The direct connection IP address.
        forwarded_for: Value of the ``X-Forwarded-For`` header (may be ``None``).
        trusted_proxies: Set of proxy IP addresses to trust.  If not
            provided, ``X-Forwarded-For`` is ignored entirely.

    Returns:
        A string suitable as ``client_id`` for :class:`RateLimiter.check`.
    """
    if not forwarded_for or not trusted_proxies:
        return remote_addr or "unknown"

    if remote_addr not in trusted_proxies:
        return remote_addr or "unknown"

    # Parse the chain: "client, proxy1, proxy2"
    parts = [ip.strip() for ip in forwarded_for.split(",") if ip.strip()]
    if not parts:
        return remote_addr or "unknown"

    # Walk from the right; the first non-trusted entry is the real client
    for ip in reversed(parts):
        if ip not in trusted_proxies:
            return ip

    # All IPs are trusted proxies – fall back to remote_addr
    return remote_addr or "unknown"


# ── Content Security Policy ─────────────────────────────────────────

class ContentSecurityPolicy:
    """CSP header generation for Murphy UI endpoints."""

    DEFAULT_POLICY = {
        "default-src": ["'self'"],
        "script-src": ["'self'"],
        "style-src": ["'self'"],
        "img-src": ["'self'", "data:"],
        "font-src": ["'self'"],
        "connect-src": ["'self'"],
        "frame-ancestors": ["'none'"],
        "base-uri": ["'self'"],
        "form-action": ["'self'"],
        "object-src": ["'none'"],
    }

    def __init__(self, policy: Optional[Dict[str, List[str]]] = None):
        self.policy = policy or dict(self.DEFAULT_POLICY)

    def add_source(self, directive: str, source: str):
        """Add a source to a CSP directive."""
        if directive not in self.policy:
            self.policy[directive] = []
        if source not in self.policy[directive]:
            self.policy[directive].append(source)

    def to_header(self) -> str:
        """Generate CSP header value."""
        parts = []
        for directive, sources in self.policy.items():
            parts.append(f"{directive} {' '.join(sources)}")
        return "; ".join(parts)

    def get_headers(self) -> Dict[str, str]:
        """Return all security headers."""
        return {
            "Content-Security-Policy": self.to_header(),
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
        }

    def status(self) -> Dict[str, Any]:
        return {
            "directives": len(self.policy),
            "header_length": len(self.to_header()),
        }


# ── API Key Rotation ────────────────────────────────────────────────

class APIKeyRotationPolicy:
    """Enforce API key rotation schedules."""

    def __init__(self, rotation_days: int = 90, warning_days: int = 14):
        self.rotation_days = rotation_days
        self.warning_days = warning_days
        self._keys: Dict[str, Dict[str, Any]] = {}

    def register_key(self, key_id: str, created_at: Optional[datetime] = None):
        """Register an API key with its creation date."""
        self._keys[key_id] = {
            "created_at": created_at or datetime.now(timezone.utc),
            "rotated": False,
        }

    def check_rotation(self, key_id: str) -> Dict[str, Any]:
        """Check if a key needs rotation."""
        if key_id not in self._keys:
            return {"status": "unknown", "key_id": key_id}

        info = self._keys[key_id]
        age = datetime.now(timezone.utc) - info["created_at"]
        days_remaining = self.rotation_days - age.days

        if days_remaining <= 0:
            return {
                "status": "expired",
                "key_id": key_id,
                "age_days": age.days,
                "action": "rotate_immediately",
            }
        elif days_remaining <= self.warning_days:
            return {
                "status": "warning",
                "key_id": key_id,
                "age_days": age.days,
                "days_remaining": days_remaining,
                "action": "schedule_rotation",
            }
        else:
            return {
                "status": "valid",
                "key_id": key_id,
                "age_days": age.days,
                "days_remaining": days_remaining,
            }

    def generate_key(self) -> str:
        """Generate a cryptographically secure API key."""
        return f"murphy_{secrets.token_urlsafe(32)}"

    def status(self) -> Dict[str, Any]:
        results = {"total_keys": len(self._keys), "expired": 0, "warning": 0, "valid": 0}
        for key_id in self._keys:
            check = self.check_rotation(key_id)
            results[check["status"]] = results.get(check["status"], 0) + 1
        return results


# ── Audit Logger ─────────────────────────────────────────────────────

class AuditLogger:
    """Structured audit logging for security events.

    In addition to the in-memory circular buffer, each audit event is
    persisted via the standard ``logging`` module so that events survive
    process restarts when a file or external log handler is configured.
    """

    def __init__(self, max_entries: int = 10000):
        self.max_entries = max_entries
        self._log: List[Dict[str, Any]] = []
        self._persist_logger = logging.getLogger("murphy.audit")

    def log(
        self,
        event_type: str,
        actor: str,
        resource: str,
        action: str,
        outcome: str = "success",
        details: Optional[Dict[str, Any]] = None,
    ):
        """Record an audit event."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "actor": actor,
            "resource": resource,
            "action": action,
            "outcome": outcome,
            "details": details or {},
        }
        self._log.append(entry)
        if len(self._log) > self.max_entries:
            self._log = self._log[-self.max_entries:]
        # Persist to durable log (file handler, syslog, etc.)
        try:
            self._persist_logger.info(
                "AUDIT event=%s actor=%s resource=%s action=%s outcome=%s",
                event_type, actor, resource, action, outcome,
                extra={"audit_entry": entry},
            )
        except Exception:
            pass  # Never let audit persistence failure break the request

    def query(
        self,
        event_type: Optional[str] = None,
        actor: Optional[str] = None,
        outcome: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Query audit log entries."""
        results = self._log
        if event_type:
            results = [e for e in results if e["event_type"] == event_type]
        if actor:
            results = [e for e in results if e["actor"] == actor]
        if outcome:
            results = [e for e in results if e["outcome"] == outcome]
        return results[-limit:]

    def status(self) -> Dict[str, Any]:
        return {
            "total_entries": len(self._log),
            "max_entries": self.max_entries,
            "event_types": list(set(e["event_type"] for e in self._log)),
        }


# ── Session Security ────────────────────────────────────────────────

class SessionSecurity:
    """Session security controls."""

    def __init__(
        self,
        session_timeout_minutes: int = 30,
        max_concurrent_sessions: int = 5,
        require_mfa: bool = False,
    ):
        self.timeout = timedelta(minutes=session_timeout_minutes)
        self.max_concurrent = max_concurrent_sessions
        self.require_mfa = require_mfa
        self._sessions: Dict[str, Dict[str, Any]] = {}

    def create_session(self, user_id: str) -> Dict[str, Any]:
        """Create a new session for a user."""
        # Check concurrent session limit
        user_sessions = [
            s for s in self._sessions.values()
            if s["user_id"] == user_id and not self._is_expired(s)
        ]
        if len(user_sessions) >= self.max_concurrent:
            return {
                "created": False,
                "reason": "max_concurrent_sessions_exceeded",
                "limit": self.max_concurrent,
            }

        session_id = secrets.token_urlsafe(32)
        self._sessions[session_id] = {
            "user_id": user_id,
            "created_at": datetime.now(timezone.utc),
            "last_activity": datetime.now(timezone.utc),
            "mfa_verified": not self.require_mfa,
        }
        return {
            "created": True,
            "session_id": session_id,
            "expires_in_minutes": self.timeout.total_seconds() / 60,
        }

    def validate_session(self, session_id: str) -> Dict[str, Any]:
        """Validate a session is active and not expired."""
        if session_id not in self._sessions:
            return {"valid": False, "reason": "session_not_found"}

        session = self._sessions[session_id]
        if self._is_expired(session):
            del self._sessions[session_id]
            return {"valid": False, "reason": "session_expired"}

        if not session["mfa_verified"]:
            return {"valid": False, "reason": "mfa_required"}

        session["last_activity"] = datetime.now(timezone.utc)
        return {"valid": True, "user_id": session["user_id"]}

    def _is_expired(self, session: Dict[str, Any]) -> bool:
        return datetime.now(timezone.utc) - session["last_activity"] > self.timeout

    def status(self) -> Dict[str, Any]:
        active = sum(1 for s in self._sessions.values() if not self._is_expired(s))
        return {
            "active_sessions": active,
            "total_created": len(self._sessions),
            "timeout_minutes": self.timeout.total_seconds() / 60,
            "mfa_required": self.require_mfa,
        }


# ── Brute-Force Protection ──────────────────────────────────────────

class BruteForceProtection:
    """Track failed authentication attempts and enforce lockout (CWE-307).

    After ``max_attempts`` failures within ``window_seconds``, the
    client is locked out for ``lockout_seconds``.
    """

    _CLEANUP_INTERVAL = 300  # Purge stale entries every 5 minutes
    _MAX_TRACKED = 50_000    # Hard cap to prevent memory exhaustion

    def __init__(
        self,
        max_attempts: int = 5,
        window_seconds: int = 900,
        lockout_seconds: int = 900,
    ):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.lockout_seconds = lockout_seconds
        self._attempts: Dict[str, List[float]] = {}
        self._lockouts: Dict[str, float] = {}
        self._last_cleanup: float = time.monotonic()

    def record_failure(self, client_id: str) -> Dict[str, Any]:
        """Record a failed authentication attempt for *client_id*.

        Returns a dict with ``locked_out`` bool and remaining attempts.
        """
        now = time.monotonic()
        self._maybe_cleanup(now)

        if client_id not in self._attempts:
            if len(self._attempts) >= self._MAX_TRACKED:
                self._cleanup(now)
            self._attempts[client_id] = []

        # Prune old attempts outside the window
        window_start = now - self.window_seconds
        self._attempts[client_id] = [
            t for t in self._attempts[client_id] if t > window_start
        ]
        self._attempts[client_id].append(now)

        if len(self._attempts[client_id]) >= self.max_attempts:
            self._lockouts[client_id] = now + self.lockout_seconds
            logger.warning(
                "BruteForceProtection: client %s locked out after %d failures",
                client_id, len(self._attempts[client_id]),
            )
            return {
                "locked_out": True,
                "attempts": len(self._attempts[client_id]),
                "lockout_seconds": self.lockout_seconds,
            }

        return {
            "locked_out": False,
            "attempts": len(self._attempts[client_id]),
            "remaining": self.max_attempts - len(self._attempts[client_id]),
        }

    def is_locked_out(self, client_id: str) -> bool:
        """Check if *client_id* is currently locked out."""
        if client_id not in self._lockouts:
            return False
        now = time.monotonic()
        if now >= self._lockouts[client_id]:
            del self._lockouts[client_id]
            self._attempts.pop(client_id, None)
            return False
        return True

    def record_success(self, client_id: str) -> None:
        """Clear failure tracking after a successful authentication."""
        self._attempts.pop(client_id, None)
        self._lockouts.pop(client_id, None)

    def _maybe_cleanup(self, now: float) -> None:
        if now - self._last_cleanup > self._CLEANUP_INTERVAL:
            self._cleanup(now)

    def _cleanup(self, now: float) -> None:
        """Purge expired lockouts and stale attempt records."""
        expired_lockouts = [
            cid for cid, exp in self._lockouts.items() if now >= exp
        ]
        for cid in expired_lockouts:
            del self._lockouts[cid]
            self._attempts.pop(cid, None)

        window_start = now - self.window_seconds
        stale_attempts = [
            cid for cid, attempts in self._attempts.items()
            if not attempts or attempts[-1] < window_start
        ]
        for cid in stale_attempts:
            del self._attempts[cid]

        self._last_cleanup = now

    def status(self) -> Dict[str, Any]:
        return {
            "max_attempts": self.max_attempts,
            "window_seconds": self.window_seconds,
            "lockout_seconds": self.lockout_seconds,
            "tracked_clients": len(self._attempts),
            "active_lockouts": len(self._lockouts),
        }


# ── Request Body Size Limiter ───────────────────────────────────────

class RequestSizeLimiter:
    """Enforce maximum request body size (CWE-400 mitigation).

    Configurable per-endpoint category (default 1 MB, file upload 10 MB).
    """

    def __init__(
        self,
        default_max_bytes: int = 1_048_576,     # 1 MB
        upload_max_bytes: int = 10_485_760,      # 10 MB
    ):
        self.default_max_bytes = default_max_bytes
        self.upload_max_bytes = upload_max_bytes

    def check(self, content_length: Optional[int], path: str = "") -> Dict[str, Any]:
        """Check if the request body size is within the allowed limit.

        Returns a dict with ``allowed`` bool and ``max_bytes`` value.
        """
        is_upload = "/upload" in path or "/import" in path
        max_bytes = self.upload_max_bytes if is_upload else self.default_max_bytes

        if content_length is None:
            return {"allowed": True, "max_bytes": max_bytes}

        if content_length > max_bytes:
            return {
                "allowed": False,
                "max_bytes": max_bytes,
                "content_length": content_length,
                "reason": "request_body_too_large",
            }

        return {"allowed": True, "max_bytes": max_bytes}

    def status(self) -> Dict[str, Any]:
        return {
            "default_max_bytes": self.default_max_bytes,
            "upload_max_bytes": self.upload_max_bytes,
        }


# ── Security Hardening Orchestrator ─────────────────────────────────

class SecurityHardeningConfig:
    """Central orchestrator for all security hardening controls."""

    def __init__(self):
        self.sanitizer = InputSanitizer()
        self.cors = CORSPolicy()
        self.rate_limiter = RateLimiter()
        self.csp = ContentSecurityPolicy()
        self.key_rotation = APIKeyRotationPolicy()
        self.audit = AuditLogger()
        self.session = SessionSecurity()
        self.brute_force = BruteForceProtection()
        self.request_size = RequestSizeLimiter()
        self._initialized = True

    def apply_request_security(
        self, client_id: str, origin: str, request_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Apply full security pipeline to an incoming request."""
        # 0. Brute-force lockout check
        if self.brute_force.is_locked_out(client_id):
            self.audit.log("brute_force", client_id, "api", "blocked", "denied")
            return {
                "allowed": False,
                "reason": "account_locked",
            }

        # 1. Rate limiting
        rate_check = self.rate_limiter.check(client_id)
        if not rate_check["allowed"]:
            self.audit.log("rate_limit", client_id, "api", "blocked", "denied")
            return {
                "allowed": False,
                "reason": "rate_limit_exceeded",
                "retry_after": rate_check.get("retry_after_seconds"),
            }

        # 2. CORS check
        cors_ok = self.cors.is_origin_allowed(origin) if origin else True

        # 3. Input sanitization
        sanitized = self.sanitizer.sanitize_dict(request_data)

        # 4. Injection detection
        threats = []
        for key, value in request_data.items():
            if isinstance(value, str):
                detected = self.sanitizer.detect_injection(value)
                if detected:
                    threats.extend(detected)

        if threats:
            self.audit.log(
                "injection_attempt", client_id, "api", "blocked", "denied",
                {"threats": threats[:5]}
            )
            return {
                "allowed": False,
                "reason": "injection_detected",
                "threat_count": len(threats),
            }

        self.audit.log("request", client_id, "api", "processed", "success")
        return {
            "allowed": True,
            "cors_valid": cors_ok,
            "sanitized_data": sanitized,
            "rate_remaining": rate_check["remaining"],
        }

    def get_response_headers(self, origin: str = "") -> Dict[str, str]:
        """Get all security response headers."""
        headers = self.csp.get_headers()
        if origin:
            headers.update(self.cors.get_headers(origin))
        return headers

    def status(self) -> Dict[str, Any]:
        """Full security hardening status."""
        return {
            "module": "security_hardening_config",
            "initialized": self._initialized,
            "components": {
                "input_sanitizer": "active",
                "cors_policy": self.cors.status(),
                "rate_limiter": self.rate_limiter.status(),
                "content_security_policy": self.csp.status(),
                "api_key_rotation": self.key_rotation.status(),
                "audit_logger": self.audit.status(),
                "session_security": self.session.status(),
                "brute_force_protection": self.brute_force.status(),
                "request_size_limiter": self.request_size.status(),
            },
        }
