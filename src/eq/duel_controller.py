"""
Duel Controller — Duel Challenge and Loot Transfer System

Implements the duel challenge, acceptance, resolution, and loot-stake
mechanics described in §5.4 of the Experimental EverQuest Modification Plan.

Key rules:
  - A challenger stakes items and issues a challenge to a defender.
  - The defender may accept, decline, or let the challenge expire (60s default).
  - On resolution the loser's staked items transfer to the winner.
  - Forfeit counts as a loss — staked items still transfer.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import List

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

class DuelState(Enum):
    """Lifecycle states for a duel challenge."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    DECLINED = "declined"
    EXPIRED = "expired"


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class DuelChallenge:
    """A duel challenge between two entities with optional item stakes."""

    challenger_id: str
    defender_id: str
    stake_item_ids: List[str] = field(default_factory=list)
    state: DuelState = DuelState.PENDING
    created_at: float = field(default_factory=time.time)
    expires_in_seconds: int = 60


@dataclass
class DuelOutcome:
    """Result of a completed duel."""

    winner_id: str
    loser_id: str
    loot_transferred: List[str] = field(default_factory=list)
    was_forfeit: bool = False


# ---------------------------------------------------------------------------
# Controller
# ---------------------------------------------------------------------------

class DuelController:
    """Manages duel lifecycle, loot stakes, and history.

    §5.4: Duel challenges, acceptance windows, and item transfer on loss.
    """

    def __init__(self) -> None:
        self._challenges: List[DuelChallenge] = []
        self._outcomes: List[DuelOutcome] = []

    # --- Challenge lifecycle ---

    def issue_challenge(
        self,
        challenger_id: str,
        defender_id: str,
        stake_items: List[str],
    ) -> DuelChallenge:
        """Create a new duel challenge."""
        challenge = DuelChallenge(
            challenger_id=challenger_id,
            defender_id=defender_id,
            stake_item_ids=list(stake_items),
        )
        capped_append(self._challenges, challenge)
        return challenge

    def accept_challenge(self, challenge: DuelChallenge) -> DuelChallenge:
        """Accept a pending challenge and move it to IN_PROGRESS."""
        if challenge.state is DuelState.PENDING:
            challenge.state = DuelState.IN_PROGRESS
        return challenge

    def decline_challenge(self, challenge: DuelChallenge) -> DuelChallenge:
        """Decline a pending challenge."""
        if challenge.state is DuelState.PENDING:
            challenge.state = DuelState.DECLINED
        return challenge

    def resolve_duel(
        self, challenge: DuelChallenge, winner_id: str
    ) -> DuelOutcome:
        """Resolve a duel: transfer staked items from loser to winner.

        §5.4: Staked items from the loser are given to the winner.
        """
        loser_id = (
            challenge.defender_id
            if winner_id == challenge.challenger_id
            else challenge.challenger_id
        )
        was_forfeit = challenge.state is not DuelState.IN_PROGRESS

        challenge.state = DuelState.COMPLETED

        outcome = DuelOutcome(
            winner_id=winner_id,
            loser_id=loser_id,
            loot_transferred=list(challenge.stake_item_ids),
            was_forfeit=was_forfeit,
        )
        capped_append(self._outcomes, outcome)
        return outcome

    # --- Queries ---

    def get_active_duels(self) -> List[DuelChallenge]:
        """Return all challenges that are PENDING or IN_PROGRESS."""
        return [
            c for c in self._challenges
            if c.state in (DuelState.PENDING, DuelState.IN_PROGRESS)
        ]

    def get_duel_history(self, entity_id: str) -> List[DuelOutcome]:
        """Return all outcomes involving the given entity."""
        return [
            o for o in self._outcomes
            if o.winner_id == entity_id or o.loser_id == entity_id
        ]

    # --- Properties ---

    @property
    def active_duel_count(self) -> int:
        return len(self.get_active_duels())

    @property
    def total_duels_completed(self) -> int:
        return len(self._outcomes)
