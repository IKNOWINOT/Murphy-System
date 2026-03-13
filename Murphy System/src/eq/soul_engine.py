"""
Soul Engine — Agent Soul Document Management

Implements the agent soul document lifecycle described in §3 (Agent Soul
Architecture) and §12.1 (Soul Document Schema) of the Experimental
EverQuest Modification Plan.

Integrates with:
  - card_system.CardCollection for card state
  - npc_card_effects for active card effect tracking
  - spawner_registry for entity awareness

The soul engine manages:
  - Creating new soul documents for AI agents
  - Recording memories, combat outcomes, faction changes
  - Tracking card collection state
  - Processing death/respawn with enchanted-item preservation
  - Named creature AI player designation
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from .card_system import CardCollection, _strip_unmaking_state

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Soul Document (§12.1)
# ---------------------------------------------------------------------------

@dataclass
class SoulDocument:
    """Complete soul document for an AI agent or player character."""

    agent_id: str
    name: str
    agent_class: str = "warrior"
    level: int = 1
    faction_id: str = "neutral"
    personality_traits: List[str] = field(default_factory=list)

    # Named creature flag — §9.9: only named creatures can be AI players
    is_named: bool = False
    is_ai_player: bool = False  # True only for named creatures

    # Short-term memory
    short_term_memory: Dict[str, Any] = field(default_factory=lambda: {
        "recent_events": [],
        "current_zone": "",
        "nearby_entities": [],
        "active_buffs": [],
        "combat_state": "idle",
        "group_context": {},
    })

    # Long-term archive
    long_term_archive: Dict[str, Any] = field(default_factory=lambda: {
        "encountered_players": {},
        "known_items": {},
        "faction_history": [],
        "combat_outcomes": [],
        "zone_knowledge": {},
        "trade_history": [],
    })

    # Recall engine
    recall_engine: Dict[str, Any] = field(default_factory=lambda: {
        "trigger_map": {},
        "association_graph": {},
        "confidence_scores": {},
    })

    # Faction alignment
    faction_alignment: Dict[str, Any] = field(default_factory=lambda: {
        "faction_id": "",
        "faction_standings": {},
        "ally_factions": [],
        "enemy_factions": [],
    })

    # Card collection
    card_collection: Optional[CardCollection] = None

    # Death state
    death_state: Dict[str, Any] = field(default_factory=lambda: {
        "alive": True,
        "death_cause": None,
        "killer_id": None,
        "betrayal_flag": False,
        "resurrectable": False,
    })

    # Lifestyle (NPC daily routines)
    lifestyle: Dict[str, Any] = field(default_factory=lambda: {
        "caste": "commoner",
        "job_role": "adventurer",
        "workplace": {},
        "residence": {},
        "schedule": {"sleep_start": 22, "work_start": 8, "adventure_start": 14},
    })

    # Heroic persona
    heroic_persona: Dict[str, Any] = field(default_factory=lambda: {
        "archetype": "neutral",
        "deity_devotion": "",
        "noble_traits": [],
    })

    # Bind point (for respawn)
    bind_point: str = "start_zone"

    # Soul-bound protector tracking
    soul_bound_protectors: List[str] = field(default_factory=list)  # entity_ids

    # Known soul-enslavers (for AI player KOS behavior)
    known_soul_enslavers: Set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        # Only named creatures can be AI players
        if self.is_named and self.is_ai_player is False:
            self.is_ai_player = True
        if not self.is_named:
            self.is_ai_player = False

        # Initialize card collection if not provided
        if self.card_collection is None:
            self.card_collection = CardCollection(holder_id=self.agent_id)


# ---------------------------------------------------------------------------
# Soul Engine
# ---------------------------------------------------------------------------

class SoulEngine:
    """Manages the lifecycle of agent soul documents."""

    def __init__(self) -> None:
        self._souls: Dict[str, SoulDocument] = {}

    # --- CRUD ---

    def create_soul(self, soul: SoulDocument) -> None:
        self._souls[soul.agent_id] = soul

    def get_soul(self, agent_id: str) -> Optional[SoulDocument]:
        return self._souls.get(agent_id)

    def remove_soul(self, agent_id: str) -> Optional[SoulDocument]:
        return self._souls.pop(agent_id, None)

    @property
    def soul_count(self) -> int:
        return len(self._souls)

    # --- Named creature / AI player queries ---

    def get_ai_players(self) -> List[SoulDocument]:
        """Return all named creatures that are AI players."""
        return [s for s in self._souls.values() if s.is_ai_player]

    def get_named_creatures(self) -> List[SoulDocument]:
        return [s for s in self._souls.values() if s.is_named]

    # --- Death / Respawn ---

    def process_death(self, agent_id: str, killer_id: str, cause: str = "combat") -> None:
        """Record death in the soul document."""
        soul = self._souls.get(agent_id)
        if not soul:
            return
        soul.death_state["alive"] = False
        soul.death_state["death_cause"] = cause
        soul.death_state["killer_id"] = killer_id

    def process_respawn_at_bind(self, agent_id: str) -> None:
        """Respawn the agent at their bind point.

        §9.22: no cards of unmaking, no unmaking buffs, enchanted items preserved.
        """
        soul = self._souls.get(agent_id)
        if not soul:
            return

        soul.death_state["alive"] = True
        soul.death_state["death_cause"] = None
        soul.death_state["killer_id"] = None

        # Strip unmaking state but preserve enchanted items
        if soul.card_collection:
            _strip_unmaking_state(soul.card_collection)

        # Update zone to bind point
        soul.short_term_memory["current_zone"] = soul.bind_point

    # --- Soul-bound protector reactions ---

    def react_to_soul_protector(self, observer_id: str, holder_id: str) -> Optional[str]:
        """An AI player observes someone with a soul-bound protector.

        §9.21: AI players will kill soul-bound protector holders on sight.
        Returns the reaction type or None if observer is not an AI player.
        """
        observer = self._souls.get(observer_id)
        if not observer or not observer.is_ai_player:
            return None

        # Record the soul-enslaver
        observer.known_soul_enslavers.add(holder_id)

        # Faction hit
        standings = observer.faction_alignment.get("faction_standings", {})
        standings[holder_id] = -1.0  # Maximum hostility

        # Record memory
        observer.long_term_archive.setdefault("combat_outcomes", []).append({
            "opponent": holder_id,
            "result": "engaged_soul_enslaver",
            "timestamp": time.time(),
        })

        return "kill_on_sight"

    # --- Memory recording ---

    def record_event(self, agent_id: str, event_type: str, data: Dict[str, Any]) -> None:
        soul = self._souls.get(agent_id)
        if not soul:
            return
        soul.short_term_memory["recent_events"].append({
            "timestamp": time.time(),
            "event_type": event_type,
            "data": data,
        })

    def record_combat_outcome(
        self, agent_id: str, opponent: str, result: str
    ) -> None:
        soul = self._souls.get(agent_id)
        if not soul:
            return
        soul.long_term_archive["combat_outcomes"].append({
            "opponent": opponent,
            "result": result,
            "timestamp": time.time(),
        })
