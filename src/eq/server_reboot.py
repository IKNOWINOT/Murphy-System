"""
Server Reboot — Decay Vote and Reboot Mechanics

Implements the server reboot / decay vote system described in §9.14–§9.16
of the Experimental EverQuest Modification Plan.

Key rules:
  - A world-decay vote triggers when the decay percentage exceeds a
    configurable threshold (default 50%).
  - AI agents and human players each cast one vote: RESTART or CONTINUE.
  - Collecting 4 Cards of Unmaking triggers an immediate reboot.
  - On reboot only 3rd-card enchanted items survive.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Set

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
# Enums
# ---------------------------------------------------------------------------

class VoteChoice(Enum):
    """Options available in a decay vote."""

    RESTART = "restart"
    CONTINUE = "continue"


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class Vote:
    """A single ballot in a decay vote."""

    voter_id: str
    choice: VoteChoice
    is_ai_agent: bool = False
    faction_id: str = ""


@dataclass
class VoteResult:
    """Tally of a completed decay vote."""

    total_votes: int
    restart_votes: int
    continue_votes: int
    restart_won: bool


# ---------------------------------------------------------------------------
# Decay Vote Manager
# ---------------------------------------------------------------------------

class DecayVoteManager:
    """Manages a world-decay vote session.

    §9.14: When world decay passes the threshold a vote is triggered.
    """

    def __init__(self, decay_threshold: float = 50.0) -> None:
        self._decay_threshold = decay_threshold
        self._votes: List[Vote] = []
        self._is_active: bool = False

    # --- Trigger ---

    def should_trigger_vote(self, decay_percentage: float) -> bool:
        """Return True if the decay percentage exceeds the threshold."""
        return decay_percentage >= self._decay_threshold

    # --- Voting ---

    def cast_vote(self, vote: Vote) -> None:
        """Record a vote.  Activates the session on first ballot."""
        self._is_active = True
        capped_append(self._votes, vote)

    def tally_votes(self) -> VoteResult:
        """Count ballots and determine the outcome."""
        restart = sum(1 for v in self._votes if v.choice is VoteChoice.RESTART)
        cont = sum(1 for v in self._votes if v.choice is VoteChoice.CONTINUE)
        total = len(self._votes)
        return VoteResult(
            total_votes=total,
            restart_votes=restart,
            continue_votes=cont,
            restart_won=restart > cont,
        )

    def reset_votes(self) -> None:
        """Clear all ballots and deactivate the session."""
        self._votes.clear()
        self._is_active = False

    # --- Properties ---

    @property
    def vote_count(self) -> int:
        return len(self._votes)

    @property
    def is_active(self) -> bool:
        return self._is_active


# ---------------------------------------------------------------------------
# Server Reboot Controller
# ---------------------------------------------------------------------------

class ServerRebootController:
    """Handles server-reboot conditions and item survival logic.

    §9.15–§9.16: 4 Cards of Unmaking = immediate reboot.
    Only 3rd-card enchanted items survive a reboot.
    """

    def __init__(self, vote_manager: DecayVoteManager) -> None:
        self._vote_manager = vote_manager

    # --- Reboot condition ---

    def check_reboot_condition(self, cards_of_unmaking_count: int) -> bool:
        """Return True if an immediate reboot is required.

        §9.15: Collecting 4 Cards of Unmaking triggers an immediate reboot.
        """
        return cards_of_unmaking_count >= 4

    # --- Initiate reboot ---

    def initiate_reboot(self, reason: str) -> Dict[str, object]:
        """Return a reboot summary dict.

        §9.16: Enchanted items (3rd-card) are preserved across reboots.
        """
        return {
            "reason": reason,
            "enchanted_items_preserved": True,
            "non_enchanted_items_wiped": True,
            "vote_result": (
                self._vote_manager.tally_votes()
                if self._vote_manager.is_active
                else None
            ),
        }

    # --- Item survival ---

    def get_surviving_items(self, enchanted_item_ids: Set[str]) -> Set[str]:
        """Return the item IDs that survive a server reboot.

        §9.16: Only 3rd-card enchanted items persist.
        """
        return set(enchanted_item_ids)
