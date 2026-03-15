"""
Murphy Integration — Voice Chat, Sentiment, Moderation, and Persistence

Implements the Murphy System integration points for voice chat configuration,
sentiment analysis, raid leader moderation, and Rosetta persistence.

Provides:
  - Voice chat configuration for multiple platforms
  - Simple keyword-based sentiment classification with moderation
  - Raid leader moderation actions (mute, unmute, kick)
  - Rosetta persistence adapter for soul document storage
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
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


# ---------------------------------------------------------------------------
# Voice Chat
# ---------------------------------------------------------------------------

@dataclass
class VoiceChatConfig:
    """Configuration for in-game voice chat."""

    enabled: bool = True
    platform: str = "webrtc"  # "webrtc" | "mumble" | "discord"
    push_to_talk: bool = True
    group_toggle: bool = True
    raid_toggle: bool = True


# ---------------------------------------------------------------------------
# Sentiment Classification
# ---------------------------------------------------------------------------

_TOXIC_KEYWORDS = [
    "hate", "kill you", "trash", "stupid", "idiot", "toxic",
    "loser", "noob", "die", "kys",
]

_POSITIVE_KEYWORDS = [
    "love", "great", "awesome", "nice", "good job", "thanks",
    "amazing", "well done", "gg", "bravo",
]


@dataclass
class SentimentResult:
    """Result of a sentiment classification."""

    text: str
    sentiment: str  # "positive" | "neutral" | "negative" | "toxic"
    confidence: float = 1.0
    moderated: bool = False


class SentimentClassifier:
    """Simple keyword-based sentiment classifier."""

    def classify(self, text: str) -> SentimentResult:
        """Classify *text* into a sentiment category."""
        lower = text.lower()

        for keyword in _TOXIC_KEYWORDS:
            if keyword in lower:
                return SentimentResult(
                    text=text, sentiment="toxic", confidence=0.9, moderated=True,
                )

        for keyword in _POSITIVE_KEYWORDS:
            if keyword in lower:
                return SentimentResult(
                    text=text, sentiment="positive", confidence=0.8,
                )

        return SentimentResult(text=text, sentiment="neutral", confidence=0.6)

    def should_moderate(self, result: SentimentResult) -> bool:
        """Return True if the result should be moderated."""
        return result.sentiment == "toxic"


# ---------------------------------------------------------------------------
# Raid Leader Moderation
# ---------------------------------------------------------------------------

@dataclass
class AdminAction:
    """A moderation action performed by a raid leader or admin."""

    admin_id: str
    action_type: str
    target_entity: str
    reason: str
    timestamp: float = field(default_factory=time.time)


class RaidLeaderModerator:
    """Manages raid leader moderation actions."""

    def __init__(self) -> None:
        self._actions: List[AdminAction] = []

    def mute_player(self, admin_id: str, target_id: str, reason: str) -> AdminAction:
        """Mute a player in the raid."""
        action = AdminAction(
            admin_id=admin_id,
            action_type="mute",
            target_entity=target_id,
            reason=reason,
        )
        capped_append(self._actions, action)
        return action

    def unmute_player(self, admin_id: str, target_id: str) -> AdminAction:
        """Unmute a previously muted player."""
        action = AdminAction(
            admin_id=admin_id,
            action_type="unmute",
            target_entity=target_id,
            reason="unmute",
        )
        capped_append(self._actions, action)
        return action

    def kick_from_raid(self, admin_id: str, target_id: str, reason: str) -> AdminAction:
        """Kick a player from the raid."""
        action = AdminAction(
            admin_id=admin_id,
            action_type="kick",
            target_entity=target_id,
            reason=reason,
        )
        capped_append(self._actions, action)
        return action

    def get_actions(self) -> List[AdminAction]:
        """Return all recorded moderation actions."""
        return list(self._actions)

    @property
    def action_count(self) -> int:
        return len(self._actions)


# ---------------------------------------------------------------------------
# Rosetta Persistence Adapter
# ---------------------------------------------------------------------------

class RosettaPersistenceAdapter:
    """In-memory persistence adapter for soul documents.

    Provides save/load/delete operations for agent soul data,
    acting as the bridge between the soul engine and persistent storage.
    """

    def __init__(self) -> None:
        self._souls: Dict[str, dict] = {}

    def save_soul(self, agent_id: str, soul_data: dict) -> bool:
        """Persist a soul document for *agent_id*. Returns True on success."""
        self._souls[agent_id] = dict(soul_data)
        return True

    def load_soul(self, agent_id: str) -> Optional[dict]:
        """Load a soul document by *agent_id*, or None if not found."""
        data = self._souls.get(agent_id)
        if data is not None:
            return dict(data)
        return None

    def delete_soul(self, agent_id: str) -> bool:
        """Delete a soul document. Returns True if it existed."""
        if agent_id in self._souls:
            del self._souls[agent_id]
            return True
        return False

    def list_saved_souls(self) -> List[str]:
        """Return all agent IDs with saved soul documents."""
        return list(self._souls.keys())

    @property
    def saved_soul_count(self) -> int:
        return len(self._souls)
