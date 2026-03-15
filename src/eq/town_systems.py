"""
Town Systems — Town Conquest, Inspect Asymmetry, and NPC Governance

Implements town conquest mechanics, inspect asymmetry (possession-based
knowledge), and NPC governance logging described in the Experimental
EverQuest Modification Plan.

Provides:
  - Inspect capability tracking: entities can only inspect items they
    have previously possessed.
  - Town conquest: siege, resolution, and faction ownership.
  - NPC governance logging for administrative actions.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
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
# Inspect Asymmetry
# ---------------------------------------------------------------------------

@dataclass
class InspectCapability:
    """Tracks which items an entity is allowed to inspect."""

    entity_id: str
    known_items: Dict[str, bool] = field(default_factory=dict)


class InspectSystem:
    """Possession-based inspect gate.

    An entity may only inspect an item if they have previously possessed it.
    """

    def __init__(self) -> None:
        self._capabilities: Dict[str, InspectCapability] = {}

    def _get_or_create(self, entity_id: str) -> InspectCapability:
        if entity_id not in self._capabilities:
            self._capabilities[entity_id] = InspectCapability(entity_id=entity_id)
        return self._capabilities[entity_id]

    def can_inspect(self, entity_id: str, item_id: str) -> bool:
        """Return True only if *entity_id* has previously possessed *item_id*."""
        cap = self._capabilities.get(entity_id)
        if cap is None:
            return False
        return cap.known_items.get(item_id, False)

    def register_possession(self, entity_id: str, item_id: str) -> None:
        """Mark *item_id* as inspectable for *entity_id*."""
        cap = self._get_or_create(entity_id)
        cap.known_items[item_id] = True

    def get_known_items(self, entity_id: str) -> List[str]:
        """Return all item IDs that *entity_id* can inspect."""
        cap = self._capabilities.get(entity_id)
        if cap is None:
            return []
        return [iid for iid, known in cap.known_items.items() if known]


# ---------------------------------------------------------------------------
# Town Conquest
# ---------------------------------------------------------------------------

@dataclass
class TownDefender:
    """An NPC defending a town."""

    npc_id: str
    name: str
    level: int
    role: str  # "guard" | "leader"


class TownState(Enum):
    """Lifecycle states for a town."""

    PEACEFUL = "peaceful"
    UNDER_SIEGE = "under_siege"
    CONQUERED = "conquered"
    LIBERATED = "liberated"


@dataclass
class Town:
    """A conquerable town within the game world."""

    town_id: str
    name: str
    owning_faction: str
    state: TownState = TownState.PEACEFUL
    defenders: List[TownDefender] = field(default_factory=list)
    buildings: List[str] = field(default_factory=list)


class TownConquestSystem:
    """Manages town registration, sieges, and faction ownership."""

    def __init__(self) -> None:
        self._towns: Dict[str, Town] = {}
        self._active_sieges: Dict[str, str] = {}  # town_id → attacker_faction

    def register_town(self, town: Town) -> None:
        """Register a town in the conquest system."""
        self._towns[town.town_id] = town

    def start_siege(self, town_id: str, attacker_faction: str) -> bool:
        """Begin a siege on a town.

        Returns True if the siege started, False if the town does not
        exist or is already under siege.
        """
        town = self._towns.get(town_id)
        if town is None or town.state == TownState.UNDER_SIEGE:
            return False
        town.state = TownState.UNDER_SIEGE
        self._active_sieges[town_id] = attacker_faction
        return True

    def resolve_siege(self, town_id: str, attackers_won: bool) -> TownState:
        """Resolve an active siege.

        Returns the resulting TownState after resolution.
        """
        town = self._towns.get(town_id)
        if town is None:
            return TownState.PEACEFUL

        attacker = self._active_sieges.pop(town_id, None)
        if attackers_won and attacker is not None:
            town.owning_faction = attacker
            town.state = TownState.CONQUERED
        else:
            town.state = TownState.LIBERATED
        return town.state

    def get_town(self, town_id: str) -> Optional[Town]:
        """Return a town by ID, or None."""
        return self._towns.get(town_id)

    def get_towns_by_faction(self, faction_id: str) -> List[Town]:
        """Return all towns owned by *faction_id*."""
        return [t for t in self._towns.values() if t.owning_faction == faction_id]

    @property
    def town_count(self) -> int:
        return len(self._towns)

    @property
    def sieges_active(self) -> int:
        return len(self._active_sieges)


# ---------------------------------------------------------------------------
# NPC Governance
# ---------------------------------------------------------------------------

@dataclass
class GovernanceLog:
    """A single governance action record."""

    action: str
    actor: str
    target: str
    timestamp: float = field(default_factory=time.time)


class GovernanceLogger:
    """Records NPC governance actions for auditing."""

    def __init__(self) -> None:
        self._logs: List[GovernanceLog] = []

    def log_action(self, action: str, actor: str, target: str) -> GovernanceLog:
        """Record a governance action and return the log entry."""
        entry = GovernanceLog(action=action, actor=actor, target=target)
        capped_append(self._logs, entry)
        return entry

    def get_logs(self, actor: Optional[str] = None) -> List[GovernanceLog]:
        """Return governance logs, optionally filtered by *actor*."""
        if actor is None:
            return list(self._logs)
        return [log for log in self._logs if log.actor == actor]

    @property
    def log_count(self) -> int:
        return len(self._logs)
