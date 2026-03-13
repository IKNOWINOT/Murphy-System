"""
NPC Card Effect Auto-Generation Engine

Generates 4-tier progressive card effects for every entity in the game based
on an identity template derived from the creature's stats, combat behavior,
zone, and lore.  See §9.21 and §9.23 of the Experimental EverQuest
Modification Plan.

Tier 1 — Combat Spell (24-hour cooldown): double damage matching the NPC's
         primary damage type, conditional on weapon type, duration scaled by level.
Tier 2 — Defensive Buff (7-day cooldown): damage mitigation matching the NPC's
         primary damage type, percentage scaled by level.
Tier 3 — Weapon/Class Specialization (7-day cooldown): weapon conversion and
         haste for melee; spell damage boost for casters; hybrid gets a lesser dual
         benefit.
Tier 4 — Soul-Bound Protector (permanent): the entity's soul is bound to the
         card holder as a permanent companion; named creatures retain full AI,
         generic mobs become simple pets.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class DamageType(Enum):
    """Damage type (Enum subclass)."""
    BLUNT = "blunt"
    SLASH = "slash"
    PIERCE = "pierce"
    FIRE = "fire"
    COLD = "cold"
    MAGIC = "magic"
    POISON = "poison"
    DISEASE = "disease"
    BREATH = "breath"


class CombatArchetype(Enum):
    """Combat archetype (Enum subclass)."""
    MELEE = "melee"
    CASTER = "caster"
    HYBRID = "hybrid"
    PET_CLASS = "pet_class"
    HEALER = "healer"


class ProtectorAIType(Enum):
    """Protector AI type (Enum subclass)."""
    FULL_AI = "full_ai"
    PET_AI = "pet_ai"


# ---------------------------------------------------------------------------
# Level-scaling helpers (§9.23)
# ---------------------------------------------------------------------------

def _spell_duration_seconds(level: int) -> int:
    """Return tier-1 combat spell duration in seconds, scaled by entity level."""
    if level <= 10:
        return 30
    if level <= 30:
        return 45
    return 60


def _mitigation_percent(level: int) -> float:
    """Return tier-2 defensive buff mitigation %, scaled by entity level."""
    if level <= 10:
        return 0.10
    if level <= 30:
        return 0.25
    if level <= 50:
        return 0.40
    return 0.50


def _haste_percent(level: int) -> int:
    """Return tier-3 melee haste bonus, scaled by entity level."""
    if level <= 10:
        return 1
    if level <= 30:
        return 3
    if level <= 50:
        return 5
    return 5  # 51+ still 5% but gets secondary bonus


def _has_secondary_bonus(level: int) -> bool:
    """Entities level 51+ receive a secondary stat bonus on tier 3."""
    return level >= 51


def _caster_spell_damage_boost(level: int) -> int:
    """Return tier-3 caster spell damage boost percentage."""
    if level <= 10:
        return 10
    if level <= 30:
        return 15
    if level <= 50:
        return 20
    return 25


# ---------------------------------------------------------------------------
# Weapon conversion map (melee tier-3)
# ---------------------------------------------------------------------------

_TWO_HAND_TO_ONE_HAND = {
    DamageType.BLUNT: ("2HB", "1HB"),
    DamageType.SLASH: ("2HS", "1HS"),
    DamageType.PIERCE: ("2HP", "1HP"),
}


# ---------------------------------------------------------------------------
# Identity Template (input to auto-generation)
# ---------------------------------------------------------------------------

@dataclass
class IdentityTemplate:
    """Structured properties derived from an NPC's database entry."""

    entity_id: str
    entity_name: str
    entity_level: int
    primary_damage_type: DamageType = DamageType.BLUNT
    combat_archetype: CombatArchetype = CombatArchetype.MELEE
    zone_origin: str = "unknown"
    faction_alignment: str = "neutral"
    is_named: bool = False
    special_abilities: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Generated Effect Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class Tier1CombatSpell:
    """Tier 1 combat spell."""
    name: str
    description: str
    condition: str
    effect: str
    duration_seconds: int
    cooldown_hours: int = 24
    stacks_with: str = "all"


@dataclass
class Tier2DefensiveBuff:
    """Tier 2 defensive buff."""
    name: str
    description: str
    mitigation_type: str
    mitigation_percent: float
    cooldown_days: int = 7


@dataclass
class Tier3Specialization:
    """Tier 3 specialization."""
    name: str
    description: str
    effect_type: str  # weapon_conversion | spell_enhancement | hybrid
    details: Dict[str, Any] = field(default_factory=dict)
    cooldown_days: int = 7


@dataclass
class Tier4SoulProtector:
    """Tier 4 soul protector."""
    name: str
    protector_entity_id: str
    protector_level: int
    protector_ai_type: ProtectorAIType
    follows_between_zones: bool = True
    npc_reputation_penalty: float = -0.5
    ai_player_kill_on_sight: bool = True


@dataclass
class NPCCardEffects:
    """Complete 4-tier card effect set for a single entity."""

    entity_id: str
    entity_name: str
    entity_level: int
    is_named: bool
    primary_weapon_type: str
    combat_style: str
    tier_1: Tier1CombatSpell
    tier_2: Tier2DefensiveBuff
    tier_3: Tier3Specialization
    tier_4: Tier4SoulProtector


# ---------------------------------------------------------------------------
# Auto-generation engine
# ---------------------------------------------------------------------------

def _pretty_name(raw: str) -> str:
    """Convert an entity_id like 'emperor_crush' to 'Emperor Crush'."""
    return raw.replace("_", " ").title()


def generate_card_effects(template: IdentityTemplate) -> NPCCardEffects:
    """Generate the full 4-tier NPC card effect set from an identity template.

    This is the main entry point of the auto-generation engine described in
    §9.23 of the Experimental EverQuest Modification Plan.
    """
    pretty = _pretty_name(template.entity_name)
    dt = template.primary_damage_type
    dt_label = dt.value  # e.g. "blunt"
    level = template.entity_level

    # --- Tier 1: Combat Spell (24-hour cooldown) ---
    tier1 = Tier1CombatSpell(
        name=f"{pretty}'s Fury",
        description=(
            f"Castable once per 24-hour period. Requires wielding a "
            f"{dt_label} weapon. Doubles all {dt_label} damage for "
            f"{_spell_duration_seconds(level)} seconds. Stacks with all "
            f"other damage modifiers."
        ),
        condition=f"requires_{dt_label}_weapon",
        effect=f"double_{dt_label}_damage",
        duration_seconds=_spell_duration_seconds(level),
    )

    # --- Tier 2: Defensive Buff (7-day cooldown) ---
    mit_pct = _mitigation_percent(level)
    tier2 = Tier2DefensiveBuff(
        name=f"{pretty}'s Resilience",
        description=(
            f"While active, the holder takes {int(mit_pct * 100)}% less "
            f"damage from {dt_label} weapons. 7-day cooldown after expiry."
        ),
        mitigation_type=f"{dt_label}_damage",
        mitigation_percent=mit_pct,
    )

    # --- Tier 3: Weapon/Class Specialization (7-day cooldown) ---
    archetype = template.combat_archetype

    if archetype in (CombatArchetype.MELEE, CombatArchetype.PET_CLASS):
        haste = _haste_percent(level)
        convert = _TWO_HAND_TO_ONE_HAND.get(dt)
        details: Dict[str, Any] = {"haste_percent": haste}
        desc_parts = [f"{haste}% haste on 1H weapons"]
        if convert:
            details[f"convert_{convert[0].lower()}_to_{convert[1].lower()}"] = True
            desc_parts.append(f"{convert[0]} → {convert[1]} conversion")
        if _has_secondary_bonus(level):
            details["secondary_stat_bonus"] = True
            desc_parts.append("secondary stat bonus")
        tier3 = Tier3Specialization(
            name=f"{pretty}'s Mastery",
            description="; ".join(desc_parts),
            effect_type="weapon_conversion",
            details=details,
        )
    elif archetype == CombatArchetype.CASTER:
        boost = _caster_spell_damage_boost(level)
        tier3 = Tier3Specialization(
            name=f"{pretty}'s Mastery",
            description=f"{boost}% {dt_label} spell damage boost",
            effect_type="spell_enhancement",
            details={"spell_school": dt_label, "damage_boost_percent": boost},
        )
    elif archetype == CombatArchetype.HEALER:
        boost = _caster_spell_damage_boost(level)
        tier3 = Tier3Specialization(
            name=f"{pretty}'s Mastery",
            description=f"{boost}% healing spell effectiveness boost",
            effect_type="spell_enhancement",
            details={"spell_school": "healing", "heal_boost_percent": boost},
        )
    else:  # HYBRID
        haste = max(1, _haste_percent(level) // 2)
        boost = max(5, _caster_spell_damage_boost(level) // 2)
        tier3 = Tier3Specialization(
            name=f"{pretty}'s Mastery",
            description=f"{haste}% haste + {boost}% spell damage (hybrid)",
            effect_type="hybrid",
            details={"haste_percent": haste, "spell_damage_boost": boost},
        )

    # --- Tier 4: Soul-Bound Protector (permanent) ---
    ai_type = ProtectorAIType.FULL_AI if template.is_named else ProtectorAIType.PET_AI
    tier4 = Tier4SoulProtector(
        name=f"Soul of {pretty}",
        protector_entity_id=template.entity_id,
        protector_level=template.entity_level,
        protector_ai_type=ai_type,
    )

    return NPCCardEffects(
        entity_id=template.entity_id,
        entity_name=template.entity_name,
        entity_level=template.entity_level,
        is_named=template.is_named,
        primary_weapon_type=dt_label,
        combat_style=archetype.value,
        tier_1=tier1,
        tier_2=tier2,
        tier_3=tier3,
        tier_4=tier4,
    )


# ---------------------------------------------------------------------------
# Batch generation (build card effect database from entity list)
# ---------------------------------------------------------------------------

def generate_all_card_effects(
    templates: List[IdentityTemplate],
) -> Dict[str, NPCCardEffects]:
    """Generate card effects for every entity in the provided list.

    Returns a dict keyed by entity_id.
    """
    return {t.entity_id: generate_card_effects(t) for t in templates}
