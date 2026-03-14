"""
Session Context Manager for the Murphy System.

Design Label: SCM-001 — Session Context Manager

Manages per-session context objects that track user input, conversation
history, active projects, known modules, system architecture, regulatory
environment, cost models, and resolution level.

Features:
  - Thread-safe per-session locking
  - Configurable session expiry (default 3600 s)
  - Bounded message history (max 100 per session)
  - Maximum 10,000 concurrent sessions

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)

_VALID_RESOLUTION_LEVELS = {f"RM{i}" for i in range(7)}
_MAX_MESSAGES = 100
_MAX_SESSIONS = 10_000


def _now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


@dataclass
class SessionContext:
    """Holds all contextual state for a single user session."""

    session_id: str
    user_input: str = ""
    previous_messages: List[str] = field(default_factory=list)
    active_project: str = ""
    known_modules: List[str] = field(default_factory=list)
    system_architecture: Dict = field(default_factory=dict)
    regulatory_environment: List[str] = field(default_factory=list)
    cost_models: Dict = field(default_factory=dict)
    resolution_level: str = "RM0"
    created_at: str = field(default_factory=_now_iso)
    last_accessed: str = field(default_factory=_now_iso)


class SessionManager:
    """Thread-safe manager for SessionContext instances."""

    def __init__(self, expiry_seconds: int = 3600) -> None:
        self._expiry_seconds = expiry_seconds
        self._sessions: Dict[str, SessionContext] = {}
        self._locks: Dict[str, threading.Lock] = {}
        self._global_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_lock(self, session_id: str) -> threading.Lock:
        """Return the per-session lock, creating one if needed."""
        with self._global_lock:
            if session_id not in self._locks:
                self._locks[session_id] = threading.Lock()
            return self._locks[session_id]

    def _is_expired(self, ctx: SessionContext) -> bool:
        last = datetime.fromisoformat(ctx.last_accessed)
        now = datetime.now(timezone.utc)
        return (now - last).total_seconds() > self._expiry_seconds

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_session(
        self,
        user_input: str = "",
        active_project: str = "",
    ) -> Optional[SessionContext]:
        """Create and store a new session. Returns None when at capacity."""
        with self._global_lock:
            if len(self._sessions) >= _MAX_SESSIONS:
                logger.warning("Session limit reached (%d)", _MAX_SESSIONS)
                return None
            session_id = str(uuid.uuid4())
            ctx = SessionContext(
                session_id=session_id,
                user_input=user_input,
                active_project=active_project,
            )
            self._sessions[session_id] = ctx
            self._locks[session_id] = threading.Lock()
        logger.info("Created session %s", session_id)
        return ctx

    def get_session(self, session_id: str) -> Optional[SessionContext]:
        """Retrieve a session, updating *last_accessed*. Returns None if
        the session does not exist or has expired."""
        lock = self._get_lock(session_id)
        with lock:
            ctx = self._sessions.get(session_id)
            if ctx is None:
                return None
            if self._is_expired(ctx):
                logger.info("Session %s expired", session_id)
                self._remove_session(session_id)
                return None
            ctx.last_accessed = _now_iso()
            return ctx

    def update_context(
        self, session_id: str, **kwargs
    ) -> Optional[SessionContext]:
        """Update arbitrary fields on a session. Returns the updated
        context, or None if the session is missing / expired."""
        lock = self._get_lock(session_id)
        with lock:
            ctx = self._sessions.get(session_id)
            if ctx is None or self._is_expired(ctx):
                return None
            for key, value in kwargs.items():
                if hasattr(ctx, key):
                    setattr(ctx, key, value)
                else:
                    logger.warning(
                        "Ignoring unknown field '%s' for session %s",
                        key,
                        session_id,
                    )
            ctx.last_accessed = _now_iso()
            return ctx

    def add_message(self, session_id: str, message: str) -> bool:
        """Append a message to the session's history (bounded at
        *_MAX_MESSAGES*). Returns False if the session is missing."""
        lock = self._get_lock(session_id)
        with lock:
            ctx = self._sessions.get(session_id)
            if ctx is None or self._is_expired(ctx):
                return False
            capped_append(ctx.previous_messages, message, max_size=_MAX_MESSAGES)
            ctx.last_accessed = _now_iso()
            return True

    def get_active_modules(self, session_id: str) -> List[str]:
        """Return *known_modules* for the given session."""
        lock = self._get_lock(session_id)
        with lock:
            ctx = self._sessions.get(session_id)
            if ctx is None or self._is_expired(ctx):
                return []
            ctx.last_accessed = _now_iso()
            return list(ctx.known_modules)

    def set_resolution_level(self, session_id: str, level: str) -> bool:
        """Set the resolution level (RM0–RM6). Returns False on invalid
        level or missing session."""
        if level not in _VALID_RESOLUTION_LEVELS:
            logger.warning("Invalid resolution level: %s", level)
            return False
        lock = self._get_lock(session_id)
        with lock:
            ctx = self._sessions.get(session_id)
            if ctx is None or self._is_expired(ctx):
                return False
            ctx.resolution_level = level
            ctx.last_accessed = _now_iso()
            return True

    def list_sessions(self) -> List[str]:
        """Return all active (non-expired) session IDs."""
        with self._global_lock:
            return [
                sid
                for sid, ctx in self._sessions.items()
                if not self._is_expired(ctx)
            ]

    def delete_session(self, session_id: str) -> bool:
        """Remove a session. Returns False if the session does not exist."""
        lock = self._get_lock(session_id)
        with lock:
            if session_id not in self._sessions:
                return False
            self._remove_session(session_id)
            return True

    def cleanup_expired(self) -> int:
        """Remove all expired sessions. Returns the number removed."""
        with self._global_lock:
            expired = [
                sid
                for sid, ctx in self._sessions.items()
                if self._is_expired(ctx)
            ]
        removed = 0
        for sid in expired:
            lock = self._get_lock(sid)
            with lock:
                ctx = self._sessions.get(sid)
                if ctx is not None and self._is_expired(ctx):
                    self._remove_session(sid)
                    removed += 1
        if removed:
            logger.info("Cleaned up %d expired sessions", removed)
        return removed

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _remove_session(self, session_id: str) -> None:
        """Delete session data (caller must already hold appropriate lock)."""
        self._sessions.pop(session_id, None)
        with self._global_lock:
            self._locks.pop(session_id, None)
