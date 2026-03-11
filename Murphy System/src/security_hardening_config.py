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

import re
import time
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any, Set

import logging

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
        path = path.replace("\\", "/")
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

    def __init__(
        self,
        requests_per_minute: int = 60,
        burst_size: int = 10,
    ):
        self.rpm = requests_per_minute
        self.burst = burst_size
        self._buckets: Dict[str, Dict[str, Any]] = {}

    def check(self, client_id: str) -> Dict[str, Any]:
        """Check if a request from client_id is allowed."""
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

    def status(self) -> Dict[str, Any]:
        return {
            "requests_per_minute": self.rpm,
            "burst_size": self.burst,
            "active_clients": len(self._buckets),
        }


# ── Content Security Policy ─────────────────────────────────────────

class ContentSecurityPolicy:
    """CSP header generation for Murphy UI endpoints."""

    DEFAULT_POLICY = {
        "default-src": ["'self'"],
        "script-src": ["'self'"],
        "style-src": ["'self'", "'unsafe-inline'"],
        "img-src": ["'self'", "data:"],
        "font-src": ["'self'"],
        "connect-src": ["'self'"],
        "frame-ancestors": ["'none'"],
        "base-uri": ["'self'"],
        "form-action": ["'self'"],
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
    """Structured audit logging for security events."""

    def __init__(self, max_entries: int = 10000):
        self.max_entries = max_entries
        self._log: List[Dict[str, Any]] = []

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
        self._initialized = True

    def apply_request_security(
        self, client_id: str, origin: str, request_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Apply full security pipeline to an incoming request."""
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
            },
        }
