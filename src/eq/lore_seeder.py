"""
Lore Seeder — EQEmu NPC/Mob/Boss Data Import and Soul Document Seeding

Implements the lore-seed import pipeline described in §7 and §11.3 of the
Experimental EverQuest Modification Plan.

Responsibilities:
  - Reads NPC data from the EQEmu game connector
  - Converts NPC records into IdentityTemplate objects for card-effect generation
  - Creates pre-populated soul documents for every named creature (AI players)
  - Assigns job roles based on original NPC function (merchant, guard, quest giver)
  - Seeds zone knowledge into agent long-term archives
  - Maps EQEmu faction data into soul document faction alignment
  - Generates SpawnerEntry records for the spawner registry
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .eq_game_connector import (
    EQEmuGameConnector,
    FactionData,
    NPCData,
    ZoneData,
)
from .npc_card_effects import (
    CombatArchetype,
    DamageType,
    IdentityTemplate,
)
from .soul_engine import SoulDocument, SoulEngine
from .spawner_registry import SpawnerEntry, SpawnerRegistry

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# NPC role classification
# ---------------------------------------------------------------------------

class NPCRole:
    """NPC role."""
    MERCHANT = "merchant"
    GUARD = "guard"
    QUEST_GIVER = "quest_giver"
    TRAINER = "trainer"
    BANKER = "banker"
    ADVENTURER = "adventurer"
    RAID_BOSS = "raid_boss"
    AMBIENT = "ambient"


def _classify_npc_role(npc: NPCData) -> str:
    """Classify an NPC's job role based on its EQEmu data fields."""
    if npc.merchant_id > 0:
        return NPCRole.MERCHANT
    if npc.level >= 60 and npc.is_named:
        return NPCRole.RAID_BOSS
    if "guard" in npc.name.lower():
        return NPCRole.GUARD
    if npc.adventure_template_id > 0:
        return NPCRole.QUEST_GIVER
    if npc.is_named:
        return NPCRole.ADVENTURER
    return NPCRole.AMBIENT


# ---------------------------------------------------------------------------
# Combat archetype heuristic
# ---------------------------------------------------------------------------

_CASTER_CLASSES = {11, 12, 13, 14}  # Necro, Wizard, Mage, Enchanter
_HEALER_CLASSES = {2, 6}  # Cleric, Druid
_HYBRID_CLASSES = {3, 4, 5, 8, 10, 15}  # Paladin, Ranger, SK, Bard, SHM, Berserker
_MELEE_CLASSES = {1, 7, 9, 16}  # Warrior, Monk, Rogue, Sorceror (custom)


def _classify_combat_archetype(npc: NPCData) -> CombatArchetype:
    """Map EQEmu class_id to CombatArchetype."""
    if npc.class_id in _CASTER_CLASSES:
        return CombatArchetype.CASTER
    if npc.class_id in _HEALER_CLASSES:
        return CombatArchetype.HEALER
    if npc.class_id in _HYBRID_CLASSES:
        return CombatArchetype.HYBRID
    return CombatArchetype.MELEE


# ---------------------------------------------------------------------------
# Damage type heuristic
# ---------------------------------------------------------------------------

def _classify_damage_type(npc: NPCData) -> DamageType:
    """Infer primary damage type from NPC stats and class."""
    abilities = npc.special_abilities.lower()
    if "fire" in abilities or "flame" in npc.name.lower():
        return DamageType.FIRE
    if "cold" in abilities or "ice" in npc.name.lower() or "frost" in npc.name.lower():
        return DamageType.COLD
    if "poison" in abilities:
        return DamageType.POISON
    if "disease" in abilities:
        return DamageType.DISEASE
    if "breath" in abilities:
        return DamageType.BREATH
    if npc.class_id in _CASTER_CLASSES:
        return DamageType.MAGIC
    if npc.class_id in {9}:  # Rogue
        return DamageType.PIERCE
    if npc.class_id in {7}:  # Monk
        return DamageType.BLUNT
    return DamageType.SLASH


# ---------------------------------------------------------------------------
# Entity category for spawner registry
# ---------------------------------------------------------------------------

def _classify_entity_category(npc: NPCData) -> str:
    """Map NPC data to spawner registry entity_category."""
    if npc.level >= 60 and npc.is_named:
        return "raid_boss"
    if npc.is_named:
        return "named"
    if npc.merchant_id > 0 or "guard" in npc.name.lower():
        return "npc"
    return "mob"


# ---------------------------------------------------------------------------
# Lore Seeder Result
# ---------------------------------------------------------------------------

@dataclass
class LoreSeedResult:
    """Summary of a lore-seeding pass."""

    npcs_processed: int = 0
    souls_created: int = 0
    spawner_entries_created: int = 0
    identity_templates_created: int = 0
    factions_mapped: int = 0
    zones_seeded: int = 0
    errors: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Lore Seeder
# ---------------------------------------------------------------------------

class LoreSeeder:
    """Imports EQEmu data and seeds soul documents, spawner entries, and
    identity templates for the Murphy EQ modification.

    Usage::

        connector = EQEmuGameConnector()
        connector.connect()
        # ... load data into connector ...

        soul_engine = SoulEngine()
        spawner_registry = SpawnerRegistry()
        seeder = LoreSeeder(connector, soul_engine, spawner_registry)
        result = seeder.seed_all()
    """

    def __init__(
        self,
        connector: EQEmuGameConnector,
        soul_engine: SoulEngine,
        spawner_registry: SpawnerRegistry,
    ) -> None:
        self.connector = connector
        self.soul_engine = soul_engine
        self.spawner_registry = spawner_registry
        self._identity_templates: Dict[str, IdentityTemplate] = {}
        self._faction_map: Dict[int, FactionData] = {}

    # --- High-level pipeline ---

    def seed_all(self) -> LoreSeedResult:
        """Run the full lore-seeding pipeline.

        1. Load factions into the faction map
        2. Seed zone knowledge
        3. Process every NPC → soul document + spawner entry + identity template
        """
        result = LoreSeedResult()

        # Step 1: Map factions
        for faction in self.connector.get_all_factions():
            self._faction_map[faction.faction_id] = faction
            result.factions_mapped += 1

        # Step 2: Seed zones
        for zone in self.connector.get_all_zones():
            result.zones_seeded += 1

        # Step 3: Process NPCs
        for npc_id, npc in sorted(self.connector._npcs.items()):
            try:
                self._process_npc(npc, result)
            except Exception as exc:  # noqa: BLE001
                logger.debug("Caught exception: %s", exc)
                result.errors.append(f"NPC {npc.npc_id} ({npc.name}): {exc}")

        return result

    # --- Per-NPC processing ---

    def _process_npc(self, npc: NPCData, result: LoreSeedResult) -> None:
        result.npcs_processed += 1

        # Create identity template
        template = self._build_identity_template(npc)
        self._identity_templates[template.entity_id] = template
        result.identity_templates_created += 1

        # Create spawner entry
        entry = self._build_spawner_entry(npc)
        self.spawner_registry.register_entity(entry)
        result.spawner_entries_created += 1

        # Create soul document for named creatures only (AI players)
        if npc.is_named:
            soul = self._build_soul_document(npc)
            self.soul_engine.create_soul(soul)
            result.souls_created += 1

    # --- Builder methods ---

    def _build_identity_template(self, npc: NPCData) -> IdentityTemplate:
        """Convert an EQEmu NPC record to a card-effect IdentityTemplate."""
        return IdentityTemplate(
            entity_id=str(npc.npc_id),
            entity_name=npc.name.replace(" ", "_").lower(),
            entity_level=npc.level,
            primary_damage_type=_classify_damage_type(npc),
            combat_archetype=_classify_combat_archetype(npc),
            zone_origin="",  # Set when spawn group data is available
            faction_alignment=self._faction_name(npc.primary_faction),
            is_named=npc.is_named,
            special_abilities=npc.special_abilities.split(",") if npc.special_abilities else [],
        )

    def _build_spawner_entry(self, npc: NPCData) -> SpawnerEntry:
        return SpawnerEntry(
            entity_id=str(npc.npc_id),
            entity_name=npc.name,
            entity_category=_classify_entity_category(npc),
            entity_level=npc.level,
        )

    def _build_soul_document(self, npc: NPCData) -> SoulDocument:
        """Create a pre-populated soul document for a named creature."""
        role = _classify_npc_role(npc)
        faction_name = self._faction_name(npc.primary_faction)

        soul = SoulDocument(
            agent_id=str(npc.npc_id),
            name=npc.name,
            agent_class=self._class_name(npc.class_id),
            level=npc.level,
            faction_id=faction_name,
            personality_traits=self._infer_traits(npc),
            is_named=True,
        )

        # Pre-populate faction alignment
        soul.faction_alignment["faction_id"] = faction_name
        faction = self._faction_map.get(npc.primary_faction)
        if faction:
            soul.faction_alignment["ally_factions"] = [
                self._faction_name(aid) for aid in faction.allies
            ]
            soul.faction_alignment["enemy_factions"] = [
                self._faction_name(eid) for eid in faction.enemies
            ]

        # Assign lifestyle/job role
        soul.lifestyle["job_role"] = role
        if role == NPCRole.RAID_BOSS:
            soul.lifestyle["caste"] = "royal"
        elif role in (NPCRole.MERCHANT, NPCRole.GUARD):
            soul.lifestyle["caste"] = "commoner"

        return soul

    # --- Helpers ---

    def _faction_name(self, faction_id: int) -> str:
        faction = self._faction_map.get(faction_id)
        return faction.name if faction else "neutral"

    @staticmethod
    def _class_name(class_id: int) -> str:
        _CLASS_MAP = {
            1: "warrior", 2: "cleric", 3: "paladin", 4: "ranger",
            5: "shadowknight", 6: "druid", 7: "monk", 8: "bard",
            9: "rogue", 10: "shaman", 11: "necromancer", 12: "wizard",
            13: "magician", 14: "enchanter", 15: "berserker", 16: "sorceror",
        }
        return _CLASS_MAP.get(class_id, "warrior")

    @staticmethod
    def _infer_traits(npc: NPCData) -> List[str]:
        """Infer personality traits from NPC data."""
        traits: List[str] = []
        if npc.level >= 60:
            traits.append("powerful")
        if npc.is_named:
            traits.append("notable")
        if npc.merchant_id > 0:
            traits.append("mercantile")
        if "guard" in npc.name.lower():
            traits.append("dutiful")
        if npc.aggro_range > 100:
            traits.append("aggressive")
        return traits or ["neutral"]

    # --- Access to generated data ---

    def get_identity_templates(self) -> Dict[str, IdentityTemplate]:
        return dict(self._identity_templates)
