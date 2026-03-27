"""
Faction Manager — Faction Standings, War Declarations, and Diplomacy

Implements the faction management layer described in §5.6 and §11.3 of the
Experimental EverQuest Modification Plan.

Provides:
  - Per-entity faction standings (initialized from EQEmu faction table)
  - Faction reputation changes from interactions (kills, quests, trades)
  - War declarations between factions
  - Alliance and enemy tracking
  - Grudge and friendship mechanics within the soul engine
  - Card-holder army mobilization faction logic
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

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
# Constants
# ---------------------------------------------------------------------------

FACTION_MAX = 2000
FACTION_MIN = -2000
FACTION_ALLY_THRESHOLD = 750
FACTION_AMIABLE_THRESHOLD = 500
FACTION_INDIFFERENT_THRESHOLD = 0
FACTION_APPREHENSIVE_THRESHOLD = -100
FACTION_DUBIOUS_THRESHOLD = -500
FACTION_THREATENINGLY_THRESHOLD = -750
FACTION_KOS_THRESHOLD = -1000


class FactionCon(Enum):
    """Faction standing "consider" labels, matching classic EQ."""

    ALLY = "ally"
    WARMLY = "warmly"
    KINDLY = "kindly"
    AMIABLE = "amiable"
    INDIFFERENT = "indifferent"
    APPREHENSIVE = "apprehensive"
    DUBIOUS = "dubious"
    THREATENINGLY = "threateningly"
    READY_TO_ATTACK = "ready_to_attack"


def standing_to_con(standing: int) -> FactionCon:
    """Convert a numeric standing to a FactionCon label."""
    if standing >= FACTION_ALLY_THRESHOLD:
        return FactionCon.ALLY
    if standing >= FACTION_AMIABLE_THRESHOLD:
        return FactionCon.WARMLY
    if standing >= 250:
        return FactionCon.KINDLY
    if standing >= FACTION_INDIFFERENT_THRESHOLD:
        return FactionCon.AMIABLE
    if standing >= FACTION_APPREHENSIVE_THRESHOLD:
        return FactionCon.INDIFFERENT
    if standing >= FACTION_DUBIOUS_THRESHOLD:
        return FactionCon.APPREHENSIVE
    if standing >= FACTION_THREATENINGLY_THRESHOLD:
        return FactionCon.DUBIOUS
    if standing >= FACTION_KOS_THRESHOLD:
        return FactionCon.THREATENINGLY
    return FactionCon.READY_TO_ATTACK


# ---------------------------------------------------------------------------
# Faction Record
# ---------------------------------------------------------------------------

@dataclass
class FactionRecord:
    """A single faction within the world."""

    faction_id: str
    name: str
    base_standing: int = 0
    allies: List[str] = field(default_factory=list)
    enemies: List[str] = field(default_factory=list)
    at_war_with: Set[str] = field(default_factory=set)
    territory_zones: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Entity Standings
# ---------------------------------------------------------------------------

@dataclass
class EntityStandings:
    """Faction standings for a single entity (player or agent)."""

    entity_id: str
    standings: Dict[str, int] = field(default_factory=dict)
    grudges: Set[str] = field(default_factory=set)  # entity IDs
    friends: Set[str] = field(default_factory=set)  # entity IDs

    def get_standing(self, faction_id: str) -> int:
        return self.standings.get(faction_id, 0)

    def get_con(self, faction_id: str) -> FactionCon:
        return standing_to_con(self.get_standing(faction_id))

    def adjust_standing(self, faction_id: str, amount: int) -> int:
        """Adjust standing and return the new value, clamped to min/max."""
        current = self.standings.get(faction_id, 0)
        new_val = max(FACTION_MIN, min(FACTION_MAX, current + amount))
        self.standings[faction_id] = new_val
        return new_val


# ---------------------------------------------------------------------------
# War Declaration
# ---------------------------------------------------------------------------

@dataclass
class WarDeclaration:
    """Record of an active war between two factions."""

    aggressor_faction: str
    defender_faction: str
    reason: str = ""
    active: bool = True


# ---------------------------------------------------------------------------
# Faction Manager
# ---------------------------------------------------------------------------

class FactionManager:
    """Server-wide faction system.

    Tracks factions, entity standings, wars, and diplomacy.
    """

    def __init__(self) -> None:
        self._factions: Dict[str, FactionRecord] = {}
        self._entity_standings: Dict[str, EntityStandings] = {}
        self._wars: List[WarDeclaration] = []

    # --- Faction CRUD ---

    def register_faction(self, faction: FactionRecord) -> None:
        self._factions[faction.faction_id] = faction

    def get_faction(self, faction_id: str) -> Optional[FactionRecord]:
        return self._factions.get(faction_id)

    @property
    def faction_count(self) -> int:
        return len(self._factions)

    def get_all_factions(self) -> List[FactionRecord]:
        return list(self._factions.values())

    # --- Entity standings ---

    def get_or_create_standings(self, entity_id: str) -> EntityStandings:
        if entity_id not in self._entity_standings:
            self._entity_standings[entity_id] = EntityStandings(entity_id=entity_id)
        return self._entity_standings[entity_id]

    def get_entity_con(self, entity_id: str, faction_id: str) -> FactionCon:
        es = self._entity_standings.get(entity_id)
        if es is None:
            return FactionCon.INDIFFERENT
        return es.get_con(faction_id)

    def adjust_entity_standing(
        self, entity_id: str, faction_id: str, amount: int
    ) -> int:
        """Adjust an entity's standing with a faction.

        Also adjusts allied/enemy factions by a fraction of the hit.
        Returns the new primary faction standing.
        """
        es = self.get_or_create_standings(entity_id)
        new_val = es.adjust_standing(faction_id, amount)

        # Ripple to allies/enemies
        faction = self._factions.get(faction_id)
        if faction:
            ally_amount = amount // 4
            enemy_amount = -(amount // 4)
            for ally_id in faction.allies:
                es.adjust_standing(ally_id, ally_amount)
            for enemy_id in faction.enemies:
                es.adjust_standing(enemy_id, enemy_amount)

        return new_val

    # --- Kill-based faction hit ---

    def process_kill_faction_hit(
        self,
        killer_id: str,
        victim_faction_id: str,
        hit_amount: int = -50,
    ) -> Optional[int]:
        """Process faction consequences of killing an NPC.

        Returns the new standing with the victim's faction, or None
        if the faction doesn't exist.
        """
        if victim_faction_id not in self._factions:
            return None
        return self.adjust_entity_standing(killer_id, victim_faction_id, hit_amount)

    # --- Grudge / friendship ---

    def add_grudge(self, entity_id: str, target_id: str) -> None:
        es = self.get_or_create_standings(entity_id)
        es.grudges.add(target_id)
        es.friends.discard(target_id)

    def add_friend(self, entity_id: str, target_id: str) -> None:
        es = self.get_or_create_standings(entity_id)
        es.friends.add(target_id)
        es.grudges.discard(target_id)

    def has_grudge(self, entity_id: str, target_id: str) -> bool:
        es = self._entity_standings.get(entity_id)
        return target_id in es.grudges if es else False

    def has_friend(self, entity_id: str, target_id: str) -> bool:
        es = self._entity_standings.get(entity_id)
        return target_id in es.friends if es else False

    # --- War declarations ---

    def declare_war(
        self, aggressor_id: str, defender_id: str, reason: str = ""
    ) -> Optional[WarDeclaration]:
        """Declare war between two factions."""
        agg = self._factions.get(aggressor_id)
        dfn = self._factions.get(defender_id)
        if not agg or not dfn:
            return None

        war = WarDeclaration(
            aggressor_faction=aggressor_id,
            defender_faction=defender_id,
            reason=reason,
        )
        capped_append(self._wars, war)
        agg.at_war_with.add(defender_id)
        dfn.at_war_with.add(aggressor_id)
        return war

    def end_war(self, aggressor_id: str, defender_id: str) -> bool:
        """End a war between two factions. Returns True if a war was ended."""
        for war in self._wars:
            if (
                war.aggressor_faction == aggressor_id
                and war.defender_faction == defender_id
                and war.active
            ):
                war.active = False
                agg = self._factions.get(aggressor_id)
                dfn = self._factions.get(defender_id)
                if agg:
                    agg.at_war_with.discard(defender_id)
                if dfn:
                    dfn.at_war_with.discard(aggressor_id)
                return True
        return False

    def get_active_wars(self) -> List[WarDeclaration]:
        return [w for w in self._wars if w.active]

    def is_at_war(self, faction_a: str, faction_b: str) -> bool:
        """Check if two factions are currently at war."""
        for war in self._wars:
            if not war.active:
                continue
            if (
                (war.aggressor_faction == faction_a and war.defender_faction == faction_b)
                or (war.aggressor_faction == faction_b and war.defender_faction == faction_a)
            ):
                return True
        return False

    # --- Army mobilization (§9.10) ---

    def get_faction_territory_zones(self, faction_id: str) -> List[str]:
        """Return the zones controlled by a faction."""
        faction = self._factions.get(faction_id)
        return list(faction.territory_zones) if faction else []

    def get_hostile_factions(self, faction_id: str) -> List[str]:
        """Return all factions hostile (at war or enemy) to the given faction."""
        faction = self._factions.get(faction_id)
        if not faction:
            return []
        hostile: Set[str] = set(faction.enemies) | faction.at_war_with
        return list(hostile)
