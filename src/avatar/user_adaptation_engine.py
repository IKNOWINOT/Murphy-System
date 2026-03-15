"""Tracks and adapts to user interaction patterns."""

import logging
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Dict, Optional

from .avatar_models import UserAdaptation

logger = logging.getLogger(__name__)


class UserAdaptationEngine:
    """Tracks and adapts to user interaction patterns."""

    def __init__(self) -> None:
        self._adaptations: Dict[str, UserAdaptation] = {}
        self._lock = Lock()

    @staticmethod
    def _key(user_id: str, avatar_id: str) -> str:
        return f"{user_id}:{avatar_id}"

    def get_adaptation(self, user_id: str, avatar_id: str) -> UserAdaptation:
        """Get or create an adaptation record for a user-avatar pair."""
        key = self._key(user_id, avatar_id)
        with self._lock:
            if key not in self._adaptations:
                self._adaptations[key] = UserAdaptation(
                    user_id=user_id, avatar_id=avatar_id
                )
            return self._adaptations[key]

    def record_interaction(
        self, user_id: str, avatar_id: str, feedback: Optional[Dict] = None
    ) -> UserAdaptation:
        """Record an interaction and optionally store feedback."""
        key = self._key(user_id, avatar_id)
        with self._lock:
            if key not in self._adaptations:
                self._adaptations[key] = UserAdaptation(
                    user_id=user_id, avatar_id=avatar_id
                )
            adapt = self._adaptations[key]
            data = adapt.model_dump()
            data["interaction_count"] += 1
            data["last_interaction"] = datetime.now(timezone.utc)
            if feedback:
                data["feedback_history"].append(feedback)
            updated = UserAdaptation(**data)
            self._adaptations[key] = updated
            return updated

    def update_preferences(
        self, user_id: str, avatar_id: str, preferences: Dict[str, Any]
    ) -> UserAdaptation:
        """Update user preferences for a given avatar."""
        key = self._key(user_id, avatar_id)
        with self._lock:
            if key not in self._adaptations:
                self._adaptations[key] = UserAdaptation(
                    user_id=user_id, avatar_id=avatar_id
                )
            adapt = self._adaptations[key]
            data = adapt.model_dump()
            for field in (
                "preferred_response_length",
                "preferred_formality",
                "topics_of_interest",
                "behavioral_score",
            ):
                if field in preferences:
                    data[field] = preferences[field]
            updated = UserAdaptation(**data)
            self._adaptations[key] = updated
            return updated

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            total = len(self._adaptations)
            total_interactions = sum(
                a.interaction_count for a in self._adaptations.values()
            )
        return {
            "total_adaptations": total,
            "total_interactions": total_interactions,
        }
