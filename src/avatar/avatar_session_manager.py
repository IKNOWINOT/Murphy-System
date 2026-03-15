"""Manages avatar interaction sessions."""

import logging
import uuid
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Dict, List, Optional

from .avatar_models import AvatarSession

logger = logging.getLogger(__name__)


class AvatarSessionManager:
    """Manages avatar interaction sessions."""

    def __init__(self) -> None:
        self._sessions: Dict[str, AvatarSession] = {}
        self._lock = Lock()

    def start_session(self, avatar_id: str, user_id: str) -> AvatarSession:
        """Start a new session."""
        session = AvatarSession(
            session_id=str(uuid.uuid4()),
            avatar_id=avatar_id,
            user_id=user_id,
            started_at=datetime.now(timezone.utc),
        )
        with self._lock:
            self._sessions[session.session_id] = session
        return session

    def end_session(self, session_id: str) -> Optional[AvatarSession]:
        """End a session. Returns None if not found."""
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            data = session.model_dump()
            data["ended_at"] = datetime.now(timezone.utc)
            data["active"] = False
            updated = AvatarSession(**data)
            self._sessions[session_id] = updated
            return updated

    def get_session(self, session_id: str) -> Optional[AvatarSession]:
        """Get a session by ID."""
        with self._lock:
            return self._sessions.get(session_id)

    def record_message(self, session_id: str) -> Optional[AvatarSession]:
        """Increment message count for a session."""
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            data = session.model_dump()
            data["message_count"] += 1
            updated = AvatarSession(**data)
            self._sessions[session_id] = updated
            return updated

    def add_cost(self, session_id: str, cost_usd: float) -> Optional[AvatarSession]:
        """Add cost to a session."""
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            data = session.model_dump()
            data["total_cost_usd"] += cost_usd
            updated = AvatarSession(**data)
            self._sessions[session_id] = updated
            return updated

    def list_active_sessions(
        self, avatar_id: Optional[str] = None
    ) -> List[AvatarSession]:
        """List active sessions, optionally filtered by avatar_id."""
        with self._lock:
            sessions = [s for s in self._sessions.values() if s.active]
        if avatar_id:
            sessions = [s for s in sessions if s.avatar_id == avatar_id]
        return sessions

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            total = len(self._sessions)
            active = sum(1 for s in self._sessions.values() if s.active)
        return {
            "total_sessions": total,
            "active_sessions": active,
        }
