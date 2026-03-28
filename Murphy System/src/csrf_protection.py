"""
CSRF Token Protection for Murphy System

Provides stateless double-submit cookie CSRF protection for state-changing
HTTP endpoints (POST, PUT, PATCH, DELETE).

Token lifecycle:
  1. generate_token(session_id)  → opaque token bound to the session
  2. validate_token(session_id, token) → True if token matches and is fresh
  3. Tokens expire after CSRF_TOKEN_TTL_SECONDS (default: 3600 s)

Usage in FastAPI / Flask middleware — attach to any SecurityMiddleware or
register as a before_request hook.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import secrets
import threading
import time
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CSRF_TOKEN_TTL_SECONDS: int = int(os.environ.get("MURPHY_CSRF_TTL", "3600"))

# Signing secret — rotate via MURPHY_CSRF_SECRET env var in production.
_CSRF_SECRET: str = os.environ.get(
    "MURPHY_CSRF_SECRET", secrets.token_hex(32)
)


# ---------------------------------------------------------------------------
# Internal store
# ---------------------------------------------------------------------------

def _sign(session_id: str, token: str) -> str:
    """Return HMAC-SHA256 signature of ``session_id:token``."""
    payload = f"{session_id}:{token}".encode()
    return hmac.new(_CSRF_SECRET.encode(), payload, hashlib.sha256).hexdigest()


class CSRFTokenStore:
    """Thread-safe in-memory store of active CSRF tokens.

    Maps ``session_id → (token, issued_at)``.
    Tokens are evicted after :data:`CSRF_TOKEN_TTL_SECONDS`.
    """

    def __init__(self, ttl_seconds: int = CSRF_TOKEN_TTL_SECONDS) -> None:
        self._store: Dict[str, Tuple[str, float]] = {}
        self._lock = threading.Lock()
        self.ttl = ttl_seconds

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self, session_id: str) -> str:
        """Generate and store a new CSRF token for *session_id*.

        Returns the opaque token string that should be embedded in the page
        (e.g. as a hidden form field or response header).
        """
        if not session_id:
            raise ValueError("session_id must be a non-empty string")
        token = secrets.token_urlsafe(32)
        issued_at = time.monotonic()
        with self._lock:
            self._store[session_id] = (token, issued_at)
        logger.debug("CSRF: issued token for session %s", session_id[:8])
        return token

    def validate(self, session_id: str, token: str) -> Tuple[bool, str]:
        """Validate *token* for *session_id*.

        Returns ``(valid, reason)`` where *reason* is one of:
          ``"ok"``, ``"missing"``, ``"expired"``, ``"mismatch"``.
        """
        if not session_id or not token:
            return False, "missing"

        with self._lock:
            entry = self._store.get(session_id)

        if entry is None:
            return False, "missing"

        stored_token, issued_at = entry
        age = time.monotonic() - issued_at
        if age > self.ttl:
            with self._lock:
                self._store.pop(session_id, None)
            logger.warning("CSRF: expired token for session %s", session_id[:8])
            return False, "expired"

        # Constant-time comparison to prevent timing attacks
        if not hmac.compare_digest(stored_token, token):
            logger.warning("CSRF: token mismatch for session %s", session_id[:8])
            return False, "mismatch"

        return True, "ok"

    def revoke(self, session_id: str) -> None:
        """Revoke the CSRF token for *session_id* (e.g. on logout)."""
        with self._lock:
            self._store.pop(session_id, None)

    def purge_expired(self) -> int:
        """Remove all expired tokens from the store. Returns count removed."""
        now = time.monotonic()
        expired_keys = []
        with self._lock:
            for sid, (_, issued_at) in list(self._store.items()):
                if now - issued_at > self.ttl:
                    expired_keys.append(sid)
            for k in expired_keys:
                del self._store[k]
        return len(expired_keys)

    def __len__(self) -> int:
        with self._lock:
            return len(self._store)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_default_store = CSRFTokenStore()


def generate_token(session_id: str) -> str:
    """Generate a CSRF token for *session_id* using the default store."""
    return _default_store.generate(session_id)


def validate_token(session_id: str, token: str) -> Tuple[bool, str]:
    """Validate *token* for *session_id* using the default store."""
    return _default_store.validate(session_id, token)


def revoke_token(session_id: str) -> None:
    """Revoke the CSRF token for *session_id* using the default store."""
    _default_store.revoke(session_id)
