"""
Avatar Interaction Quality Scorer

Measures how well the Murphy avatar is performing for each user by analyzing
interaction quality signals. This is NOT a user profiling or surveillance tool —
it scores the AVATAR's effectiveness, not the user's behavior.

Inputs:
  - Interaction count: How much the user has engaged with their avatar
  - Feedback history: User-provided ratings of avatar responses

Outputs:
  - Quality score (0.0-1.0): Higher = avatar is serving this user well
  - Used to adapt avatar behavior to better serve the user

The score helps Murphy improve its own service quality. Users can view,
reset, or opt out of scoring at any time.
"""

import logging
from threading import Lock
from typing import Any, Dict

from .avatar_models import UserAdaptation

logger = logging.getLogger(__name__)


class BehavioralScoringEngine:
    """
    Avatar Interaction Quality Engine.

    Measures how well the Murphy avatar is serving each user — this scores
    AVATAR quality, not user worth or behavior. A higher score means the
    avatar is responding well to this user's needs; a lower score is a
    signal for the avatar to adapt and improve.
    """

    def __init__(self) -> None:
        self._scores: Dict[str, float] = {}
        self._lock = Lock()

    def calculate_score(self, adaptation: UserAdaptation) -> float:
        """Calculate avatar quality score based on user interaction and feedback history."""
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
        """Adjust avatar quality score for a user."""
        with self._lock:
            current = self._scores.get(user_id, 0.5)
            new_score = max(0.0, min(1.0, current + delta))
            self._scores[user_id] = new_score
            return new_score

    def get_score(self, user_id: str) -> float:
        """Get avatar quality score for a user."""
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
