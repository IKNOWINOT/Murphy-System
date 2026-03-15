"""Thread-safe avatar CRUD and lookup."""

import logging
from threading import Lock
from typing import Any, Dict, List, Optional

from .avatar_models import AvatarProfile

logger = logging.getLogger(__name__)


class AvatarRegistry:
    """Thread-safe avatar CRUD and lookup."""

    def __init__(self) -> None:
        self._avatars: Dict[str, AvatarProfile] = {}
        self._lock = Lock()

    def register(self, profile: AvatarProfile) -> bool:
        """Register a new avatar. Returns False if avatar_id already exists."""
        with self._lock:
            if profile.avatar_id in self._avatars:
                return False
            self._avatars[profile.avatar_id] = profile
            return True

    def unregister(self, avatar_id: str) -> bool:
        """Remove an avatar. Returns False if not found."""
        with self._lock:
            if avatar_id not in self._avatars:
                return False
            del self._avatars[avatar_id]
            return True

    def get(self, avatar_id: str) -> Optional[AvatarProfile]:
        """Get an avatar by ID."""
        with self._lock:
            return self._avatars.get(avatar_id)

    def list_avatars(self, enabled_only: bool = False) -> List[AvatarProfile]:
        """List all avatars, optionally filtering to enabled only."""
        with self._lock:
            avatars = list(self._avatars.values())
        if enabled_only:
            avatars = [a for a in avatars if a.enabled]
        return avatars

    def update(self, avatar_id: str, updates: Dict[str, Any]) -> Optional[AvatarProfile]:
        """Update avatar fields. Returns updated profile or None if not found."""
        with self._lock:
            profile = self._avatars.get(avatar_id)
            if profile is None:
                return None
            data = profile.model_dump()
            data.update(updates)
            updated = AvatarProfile(**data)
            self._avatars[avatar_id] = updated
            return updated

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            total = len(self._avatars)
            enabled = sum(1 for a in self._avatars.values() if a.enabled)
        return {
            "total_avatars": total,
            "enabled_avatars": enabled,
            "disabled_avatars": total - enabled,
        }
