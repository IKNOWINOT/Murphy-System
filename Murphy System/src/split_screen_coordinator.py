"""
Split-Screen Coordinator — Murphy System

Wires SplitScreenManager with the task-routing subsystem so that
multi-cursor automation sessions can be assigned to discrete screen
zones and executed concurrently.

Public surface:
    SplitScreenSession    — one multi-cursor desktop session
    SplitScreenCoordinator — lifecycle manager for sessions

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from murphy_native_automation import (
    CursorContext,
    MultiCursorDesktop,
    ScreenZone,
    SplitScreenLayout,
    SplitScreenManager,
)

logger = logging.getLogger(__name__)

__all__ = [
    "SessionState",
    "SplitScreenSession",
    "SplitScreenCoordinator",
]


class SessionState(str, Enum):
    """Lifecycle state of a :class:`SplitScreenSession`.

    Attributes:
        PENDING:   Session created but not yet started.
        ACTIVE:    Session is running; cursors can be dispatched.
        PAUSED:    Session suspended; no new cursor actions dispatched.
        COMPLETED: Session finished successfully.
        FAILED:    Session terminated due to an unrecoverable error.
    """

    PENDING = "pending"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class SplitScreenSession:
    """Container for a single multi-cursor split-screen automation session.

    Attributes:
        session_id:   Unique identifier (auto-generated if not provided).
        layout:       The split-screen layout applied to this session.
        state:        Current lifecycle state.
        manager:      The :class:`SplitScreenManager` holding zones.
        desktop:      The :class:`MultiCursorDesktop` holding cursors.
        created_at:   UTC timestamp of creation.
        started_at:   UTC timestamp when the session was started.
        finished_at:  UTC timestamp when the session ended (or None).
        metadata:     Caller-supplied arbitrary key/value pairs.
        errors:       Accumulated error messages (non-fatal).
    """

    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    layout: SplitScreenLayout = SplitScreenLayout.QUAD
    state: SessionState = SessionState.PENDING
    manager: SplitScreenManager = field(init=False)
    desktop: MultiCursorDesktop = field(init=False)
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    _custom_zones: Optional[List[ScreenZone]] = field(
        default=None, repr=False, compare=False
    )

    def __post_init__(self) -> None:
        if self.layout == SplitScreenLayout.CUSTOM and self._custom_zones:
            self.manager = SplitScreenManager(
                SplitScreenLayout.CUSTOM, custom_zones=self._custom_zones
            )
        else:
            self.manager = SplitScreenManager(self.layout)
        self.desktop = MultiCursorDesktop()

    def start(self) -> None:
        """Transition session to ACTIVE."""
        if self.state != SessionState.PENDING:
            raise RuntimeError(
                f"Cannot start session in state {self.state!r}"
            )
        self.state = SessionState.ACTIVE
        self.started_at = datetime.now(timezone.utc)

    def pause(self) -> None:
        """Pause an ACTIVE session."""
        if self.state != SessionState.ACTIVE:
            raise RuntimeError(
                f"Cannot pause session in state {self.state!r}"
            )
        self.state = SessionState.PAUSED

    def resume(self) -> None:
        """Resume a PAUSED session."""
        if self.state != SessionState.PAUSED:
            raise RuntimeError(
                f"Cannot resume session in state {self.state!r}"
            )
        self.state = SessionState.ACTIVE

    def complete(self) -> None:
        """Mark session as COMPLETED."""
        if self.state not in (SessionState.ACTIVE, SessionState.PAUSED):
            raise RuntimeError(
                f"Cannot complete session in state {self.state!r}"
            )
        self.state = SessionState.COMPLETED
        self.finished_at = datetime.now(timezone.utc)

    def fail(self, reason: str = "") -> None:
        """Mark session as FAILED."""
        self.state = SessionState.FAILED
        self.finished_at = datetime.now(timezone.utc)
        if reason:
            self.errors.append(reason)

    def add_cursor(
        self,
        cursor_id: str,
        zone_id: str,
        *,
        metadata: Dict[str, Any] | None = None,
    ) -> CursorContext:
        """Add a cursor to *zone_id* in this session's desktop."""
        if self.state not in (SessionState.ACTIVE, SessionState.PENDING):
            raise RuntimeError(
                f"Cannot add cursor in state {self.state!r}"
            )
        # Validate that the zone exists.
        self.manager.get_zone(zone_id)
        return self.desktop.add_cursor(cursor_id, zone_id, metadata=metadata)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "layout": self.layout.value,
            "state": self.state.value,
            "zone_count": self.manager.zone_count(),
            "cursor_count": self.desktop.cursor_count(),
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "metadata": self.metadata,
            "errors": self.errors,
        }


class SplitScreenCoordinator:
    """Lifecycle manager for :class:`SplitScreenSession` objects.

    One coordinator can manage many concurrent sessions.  Thread-safe.

    Usage::

        coord = SplitScreenCoordinator()
        session = coord.create_session(SplitScreenLayout.QUAD)
        session.start()
        session.add_cursor("c0", "z0")
        session.complete()
        coord.remove_session(session.session_id)
    """

    def __init__(self) -> None:
        self._sessions: Dict[str, SplitScreenSession] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def create_session(
        self,
        layout: SplitScreenLayout = SplitScreenLayout.QUAD,
        *,
        custom_zones: Optional[List[ScreenZone]] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SplitScreenSession:
        """Create and register a new session."""
        sid = session_id or str(uuid.uuid4())
        with self._lock:
            if sid in self._sessions:
                raise ValueError(f"Session {sid!r} already exists")
            session = SplitScreenSession(
                session_id=sid,
                layout=layout,
                metadata=metadata or {},
                _custom_zones=custom_zones,
            )
            self._sessions[sid] = session
            logger.info("Created split-screen session %s layout=%s", sid, layout.value)
            return session

    def get_session(self, session_id: str) -> SplitScreenSession:
        with self._lock:
            if session_id not in self._sessions:
                raise KeyError(f"Session {session_id!r} not found")
            return self._sessions[session_id]

    def remove_session(self, session_id: str) -> None:
        with self._lock:
            if session_id not in self._sessions:
                raise KeyError(f"Session {session_id!r} not found")
            del self._sessions[session_id]
            logger.info("Removed split-screen session %s", session_id)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def session_count(self) -> int:
        with self._lock:
            return len(self._sessions)

    def active_sessions(self) -> List[SplitScreenSession]:
        with self._lock:
            return [
                s for s in self._sessions.values()
                if s.state == SessionState.ACTIVE
            ]

    def sessions_by_state(self, state: SessionState) -> List[SplitScreenSession]:
        with self._lock:
            return [s for s in self._sessions.values() if s.state == state]

    def snapshot(self) -> List[Dict[str, Any]]:
        """Return a serialisable snapshot of all sessions."""
        with self._lock:
            return [s.to_dict() for s in self._sessions.values()]
