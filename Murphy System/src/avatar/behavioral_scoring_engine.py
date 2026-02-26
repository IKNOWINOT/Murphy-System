"""Scores user behavior based on interaction patterns."""

from threading import Lock
from typing import Any, Dict

from .avatar_models import UserAdaptation


class BehavioralScoringEngine:
    """Scores user behavior based on interaction patterns."""

    def __init__(self) -> None:
        self._scores: Dict[str, float] = {}
        self._lock = Lock()

    def calculate_score(self, adaptation: UserAdaptation) -> float:
        """Calculate behavioral score (0.0-1.0) based on interaction history."""
        base = min(adaptation.interaction_count / 10.0, 1.0)
        positive_feedback = sum(
            1 for f in adaptation.feedback_history if f.get("rating", 0) > 3
        )
        negative_feedback = sum(
            1 for f in adaptation.feedback_history if f.get("rating", 0) <= 2
        )
        total_feedback = positive_feedback + negative_feedback
        if total_feedback > 0:
            feedback_ratio = positive_feedback / total_feedback
            score = (base * 0.5) + (feedback_ratio * 0.5)
        else:
            score = base
        score = max(0.0, min(1.0, score))
        with self._lock:
            self._scores[adaptation.user_id] = score
        return score

    def update_score(self, user_id: str, delta: float) -> float:
        """Adjust a user's behavioral score."""
        with self._lock:
            current = self._scores.get(user_id, 0.5)
            new_score = max(0.0, min(1.0, current + delta))
            self._scores[user_id] = new_score
            return new_score

    def get_score(self, user_id: str) -> float:
        """Get a user's behavioral score."""
        with self._lock:
            return self._scores.get(user_id, 0.5)

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            total = len(self._scores)
            avg = sum(self._scores.values()) / total if total else 0.0
        return {
            "total_users_scored": total,
            "average_score": round(avg, 3),
        }
