"""
Spawner Unlock Registry — Entity Tracking and World Decay

Implements the per-entity spawner tracking, unmade status logging,
world decay percentage calculation, and milestone announcements
described in §9.11, §9.16, and §12.8 of the Experimental EverQuest
Modification Plan.

Each entity type has a registry entry that tracks:
  - Whether it can still spawn in the world
  - How many cards of that entity are in circulation
  - Whether 4 cards were traded to The Unmaker (making the entity unmade)
  - Who unmade it and when
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

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
# Spawner Registry Entry (§12.8)
# ---------------------------------------------------------------------------

@dataclass
class SpawnerEntry:
    """Per-entity tracking record."""

    entity_id: str
    entity_name: str
    entity_category: str  # mob, npc, named, god, raid_boss, ambient
    entity_level: int = 1
    spawner_unlocked: bool = True
    cards_in_circulation: int = 0
    four_card_combo_unmade: bool = False
    unmade_by: Optional[str] = None
    unmade_at: Optional[float] = None
    total_kills_before_unmade: int = 0
    card_drop_rate: float = 0.01
    zones_spawned_in: List[str] = field(default_factory=list)
    last_spawn_time: Optional[float] = None
    endangered: bool = False  # True when 3 cards are in circulation


# ---------------------------------------------------------------------------
# World Decay State (§12.9)
# ---------------------------------------------------------------------------

@dataclass
class WorldDecayState:
    """Global server-level decay tracking."""

    server_id: str = "default"
    total_entity_types: int = 0
    entities_unmade: int = 0

    @property
    def decay_percentage(self) -> float:
        if self.total_entity_types == 0:
            return 0.0
        return (self.entities_unmade / self.total_entity_types) * 100.0

    @property
    def milestone(self) -> Optional[int]:
        """Return the current milestone percentage (10, 25, 50, 75, 90) or None."""
        pct = self.decay_percentage
        for threshold in (90, 75, 50, 25, 10):
            if pct >= threshold:
                return threshold
        return None


# ---------------------------------------------------------------------------
# Spawner Registry (§9.16)
# ---------------------------------------------------------------------------

class SpawnerRegistry:
    """Server-wide entity spawner registry.

    Tracks every entity type in the game, their spawner status,
    card circulation counts, and world decay progression.
    """

    def __init__(self, server_id: str = "default") -> None:
        self._entries: Dict[str, SpawnerEntry] = {}
        self.decay_state = WorldDecayState(server_id=server_id)
        self._announcements: List[str] = []

    # --- Registration ---

    def register_entity(self, entry: SpawnerEntry) -> None:
        """Register a new entity type in the spawner registry."""
        self._entries[entry.entity_id] = entry
        self.decay_state.total_entity_types = len(self._entries)

    def get_entry(self, entity_id: str) -> Optional[SpawnerEntry]:
        return self._entries.get(entity_id)

    @property
    def entity_count(self) -> int:
        return len(self._entries)

    @property
    def unmade_count(self) -> int:
        return sum(1 for e in self._entries.values() if e.four_card_combo_unmade)

    # --- Card circulation ---

    def increment_card_count(self, entity_id: str) -> None:
        """A new card of this entity was dropped — increment circulation."""
        entry = self._entries.get(entity_id)
        if entry and not entry.four_card_combo_unmade:
            entry.cards_in_circulation += 1
            entry.endangered = entry.cards_in_circulation >= 3

    def decrement_card_count(self, entity_id: str) -> None:
        entry = self._entries.get(entity_id)
        if entry:
            entry.cards_in_circulation = max(0, entry.cards_in_circulation - 1)
            entry.endangered = entry.cards_in_circulation >= 3

    # --- Unmaking ---

    def unmake_entity(self, entity_id: str, unmade_by: str) -> bool:
        """Permanently delete an entity type from the world.

        Returns True if the entity was successfully unmade.
        """
        entry = self._entries.get(entity_id)
        if not entry or entry.four_card_combo_unmade:
            return False

        entry.four_card_combo_unmade = True
        entry.spawner_unlocked = False
        entry.unmade_by = unmade_by
        entry.unmade_at = time.time()

        self.decay_state.entities_unmade = self.unmade_count
        self._check_decay_milestones()
        return True

    # --- Decay milestones ---

    def _check_decay_milestones(self) -> None:
        pct = self.decay_state.decay_percentage
        for threshold in (10, 25, 50, 75, 90):
            if pct >= threshold:
                msg = f"[WORLD DECAY] {threshold}% of entity types have been unmade!"
                if msg not in self._announcements:
                    capped_append(self._announcements, msg)

    @property
    def announcements(self) -> List[str]:
        return list(self._announcements)

    # --- Queries ---

    def get_endangered_entities(self) -> List[SpawnerEntry]:
        """Return entities with 3+ cards in circulation (one away from deletion)."""
        return [e for e in self._entries.values() if e.endangered and not e.four_card_combo_unmade]

    def get_unmade_entities(self) -> List[SpawnerEntry]:
        return [e for e in self._entries.values() if e.four_card_combo_unmade]

    def get_alive_entities(self) -> List[SpawnerEntry]:
        return [e for e in self._entries.values() if not e.four_card_combo_unmade]
