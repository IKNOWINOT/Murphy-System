"""
Remake System — Character Remake and Bonus Tracking

Implements the Remake System described in §4.4 of the Experimental
EverQuest Modification Plan.

Key rules:
  - A character at max level (65), with max AA and max skills, may remake
    into a new class.
  - Each remake grants a cumulative +1% bonus to all stats.
  - Full remake history is preserved per entity.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REMAKE_BONUS_PERCENT: float = 1.0  # 1% bonus per remake


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class RemakeRecord:
    """A single remake event for an entity."""

    entity_id: str
    remake_count: int
    total_bonus_percent: float
    previous_class: str
    new_class: str
    remade_at: float = field(default_factory=time.time)


@dataclass
class RemakeRequirements:
    """Prerequisites that must be met before a remake is allowed."""

    max_level: int = 65
    max_aa: bool = True
    max_skills: bool = True


# ---------------------------------------------------------------------------
# Remake System
# ---------------------------------------------------------------------------

class RemakeSystem:
    """Manages character remakes and cumulative bonuses.

    §4.4: Characters that meet all requirements may remake into a new
    class, gaining a +1% stat bonus per remake.
    """

    def __init__(self, requirements: RemakeRequirements | None = None) -> None:
        self._requirements = requirements or RemakeRequirements()
        self._history: Dict[str, List[RemakeRecord]] = {}

    # --- Eligibility ---

    def can_remake(
        self,
        entity_id: str,
        level: int,
        aa_maxed: bool,
        skills_maxed: bool,
    ) -> bool:
        """Check whether the entity meets all remake prerequisites."""
        return (
            level >= self._requirements.max_level
            and aa_maxed is self._requirements.max_aa
            and skills_maxed is self._requirements.max_skills
        )

    # --- Perform remake ---

    def perform_remake(
        self,
        entity_id: str,
        current_class: str,
        new_class: str,
    ) -> RemakeRecord:
        """Execute a remake: increment count, add +1% bonus, record history."""
        records = self._history.setdefault(entity_id, [])
        new_count = len(records) + 1
        new_bonus = new_count * REMAKE_BONUS_PERCENT

        record = RemakeRecord(
            entity_id=entity_id,
            remake_count=new_count,
            total_bonus_percent=new_bonus,
            previous_class=current_class,
            new_class=new_class,
        )
        records.append(record)
        return record

    # --- Queries ---

    def get_remake_count(self, entity_id: str) -> int:
        return len(self._history.get(entity_id, []))

    def get_total_bonus(self, entity_id: str) -> float:
        return self.get_remake_count(entity_id) * REMAKE_BONUS_PERCENT

    def get_remake_history(self, entity_id: str) -> List[RemakeRecord]:
        return list(self._history.get(entity_id, []))

    # --- Server-wide ---

    @property
    def total_remakes_server_wide(self) -> int:
        return sum(len(recs) for recs in self._history.values())
