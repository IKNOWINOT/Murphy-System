"""
Sorceror Class — Monk/Mage Hybrid Elemental Pet Class

Implements the Sorceror class design described in the SORCEROR_CLASS_DESIGN.md
document and referenced by §2 (Core Ability Categories), §2.2 (Proc-Based DPS),
§2.3 (Pet System), §2.10 (Discipline of Rumblecrush), and §2.11 (Lord of the
Maelstrom) of the Experimental EverQuest Modification Plan.

Key rules:
  - Eligible races: Dark Elf, Erudite, Human, High Elf, Gnome (int caster races).
  - Armor: cloth, leather, Fungi Tunic only.
  - Weapons: 1H slashing, 1H piercing, staves — no 1H blunt.
  - Single-element pet rule: all active pets must share one element unless
    Lord of the Maelstrom is active.
  - Proc lines: fire (AC/DS), earth (root/rune), air (haste/stun),
    water (slow/heal).
  - Discipline of Rumblecrush: 180s tanking disc, procs cost mana.
  - Lord of the Maelstrom: level 60 raid drop, lifts single-element restriction.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants & Configuration
# ---------------------------------------------------------------------------

ELIGIBLE_RACES = ("Dark Elf", "Erudite", "Human", "High Elf", "Gnome")
ARMOR_RESTRICTIONS = ("cloth", "leather", "Fungi Tunic")
WEAPON_RESTRICTIONS = ("1H slashing", "1H piercing", "staves")


@dataclass
class SorcerorConfig:
    """Static class configuration for the Sorceror."""

    eligible_races: tuple[str, ...] = ELIGIBLE_RACES
    armor_restrictions: tuple[str, ...] = ARMOR_RESTRICTIONS
    weapon_restrictions: tuple[str, ...] = WEAPON_RESTRICTIONS


# ---------------------------------------------------------------------------
# Element Enum
# ---------------------------------------------------------------------------

class ElementType(Enum):
    """The four elemental attunements a Sorceror can channel."""

    EARTH = "earth"
    AIR = "air"
    FIRE = "fire"
    WATER = "water"


# ---------------------------------------------------------------------------
# Pet Definitions
# ---------------------------------------------------------------------------

@dataclass
class PetDefinition:
    """Template for a summoned elemental companion."""

    element: ElementType
    level: int
    hp: int
    damage: int
    name: str


# ---------------------------------------------------------------------------
# Abilities
# ---------------------------------------------------------------------------

@dataclass
class SorcerorAbility:
    """A Sorceror class ability or spell."""

    name: str
    level_requirement: int
    mana_cost: int
    cooldown_seconds: float
    description: str
    element: Optional[ElementType] = None


# ---------------------------------------------------------------------------
# Proc Effects
# ---------------------------------------------------------------------------

@dataclass
class ProcEffect:
    """An elemental proc that triggers on melee hits."""

    name: str
    element: ElementType
    level_requirement: int
    proc_chance: float
    min_damage: int
    max_damage: int
    duration_seconds: float
    description: str


# ---------------------------------------------------------------------------
# Disciplines
# ---------------------------------------------------------------------------

@dataclass
class Discipline:
    """A class discipline (toggle / timed ability)."""

    name: str
    level_requirement: int
    duration_seconds: float
    description: str
    is_raid_drop: bool = False


# ---------------------------------------------------------------------------
# Fire Procs — AC / Damage Shield line
# ---------------------------------------------------------------------------

FIRE_PROCS: List[ProcEffect] = [
    ProcEffect("Ember Strike", ElementType.FIRE, 6, 0.10, 20, 50, 12.0,
               "Fire damage AE + self DS (3/hit) for 12s"),
    ProcEffect("Flame Lash", ElementType.FIRE, 14, 0.12, 40, 100, 18.0,
               "Fire damage AE + self DS (8/hit) + AC +5 for 18s"),
    ProcEffect("Inferno Burst", ElementType.FIRE, 26, 0.10, 80, 200, 18.0,
               "Fire damage AE + self DS (15/hit) + AC +10 for 18s"),
    ProcEffect("Soulfire Cascade", ElementType.FIRE, 38, 0.08, 150, 350, 24.0,
               "Fire damage AE + self DS (25/hit) + AC +15 for 24s"),
    ProcEffect("Pyre Storm", ElementType.FIRE, 50, 0.08, 300, 600, 24.0,
               "Fire damage AE + group DS (20/hit) + AC +20 for 24s"),
    ProcEffect("Arcane Conflagration", ElementType.FIRE, 60, 0.06, 500, 900, 30.0,
               "Fire damage AE + group DS (35/hit) + AC +30 for 30s"),
]

# ---------------------------------------------------------------------------
# Earth Procs — Root / Rune line
# ---------------------------------------------------------------------------

EARTH_PROCS: List[ProcEffect] = [
    ProcEffect("Stone Grasp", ElementType.EARTH, 8, 0.08, 0, 0, 6.0,
               "Root target 6s + self rune absorbing 50 damage"),
    ProcEffect("Earthen Snare", ElementType.EARTH, 18, 0.10, 0, 0, 8.0,
               "Root target 8s + self rune absorbing 120 damage"),
    ProcEffect("Tremor Bind", ElementType.EARTH, 30, 0.08, 0, 0, 10.0,
               "Root target 10s + self rune absorbing 250 damage"),
    ProcEffect("Bedrock Shackle", ElementType.EARTH, 42, 0.07, 0, 0, 12.0,
               "Root target 12s + self rune 400 + group rune 100"),
    ProcEffect("Tectonic Cage", ElementType.EARTH, 54, 0.06, 0, 0, 14.0,
               "Root target 14s + self rune 600 + group rune 200"),
]

# ---------------------------------------------------------------------------
# Air Procs — Haste / Stun line
# ---------------------------------------------------------------------------

AIR_PROCS: List[ProcEffect] = [
    ProcEffect("Gust Snap", ElementType.AIR, 10, 0.08, 10, 30, 6.0,
               "Stun target 2s + group haste +5% for 6s"),
    ProcEffect("Cyclone Lash", ElementType.AIR, 22, 0.10, 30, 70, 10.0,
               "Stun target 3s + group haste +8% for 10s"),
    ProcEffect("Tempest Strike", ElementType.AIR, 34, 0.08, 60, 140, 12.0,
               "Stun target 3s + group haste +12% for 12s"),
    ProcEffect("Squall Burst", ElementType.AIR, 46, 0.07, 100, 220, 14.0,
               "Stun target 4s + group haste +15% for 14s"),
    ProcEffect("Maelstrom Crack", ElementType.AIR, 58, 0.06, 180, 350, 18.0,
               "Stun target 4s + group haste +18% for 18s"),
]

# ---------------------------------------------------------------------------
# Water Procs — Slow / Heal line
# ---------------------------------------------------------------------------

WATER_PROCS: List[ProcEffect] = [
    ProcEffect("Chill Touch", ElementType.WATER, 12, 0.08, 0, 0, 8.0,
               "Slow target 10% + self heal 30 HP"),
    ProcEffect("Frost Sap", ElementType.WATER, 24, 0.10, 0, 0, 10.0,
               "Slow target 15% + self heal 70 HP"),
    ProcEffect("Tidal Drain", ElementType.WATER, 36, 0.08, 0, 0, 12.0,
               "Slow target 20% + group heal 50 HP"),
    ProcEffect("Torrent Leech", ElementType.WATER, 48, 0.07, 0, 0, 14.0,
               "Slow target 25% + group heal 100 HP"),
    ProcEffect("Deluge Cascade", ElementType.WATER, 58, 0.06, 0, 0, 18.0,
               "Slow target 30% + group heal 180 HP"),
]

# ---------------------------------------------------------------------------
# Discipline Definitions
# ---------------------------------------------------------------------------

DISCIPLINE_RUMBLECRUSH = Discipline(
    name="Discipline of Rumblecrush",
    level_requirement=55,
    duration_seconds=180.0,
    description=(
        "Avoidance tanking disc. Pets gain Defensive-like mitigation; "
        "Sorceror cycles pets to absorb hits. Every proc costs mana."
    ),
    is_raid_drop=False,
)

LORD_OF_THE_MAELSTROM = Discipline(
    name="Lord of the Maelstrom",
    level_requirement=60,
    duration_seconds=0.0,  # passive once obtained
    description=(
        "Raid-drop discipline from the final Plane of Sky boss. "
        "Lifts the single-element pet restriction permanently."
    ),
    is_raid_drop=True,
)

# ---------------------------------------------------------------------------
# Core Abilities
# ---------------------------------------------------------------------------

SORCEROR_ABILITIES: List[SorcerorAbility] = [
    SorcerorAbility("Hand-to-Hand", 1, 0, 0.0, "Base melee skill, scales with level"),
    SorcerorAbility("Tiger Claw", 4, 10, 6.0, "Fast melee strike, chance to proc fire damage", ElementType.FIRE),
    SorcerorAbility("Round Kick", 8, 0, 8.0, "Moderate damage kick"),
    SorcerorAbility("Dual Wield", 13, 0, 0.0, "Can wield two one-handed weapons"),
    SorcerorAbility("Eagle Strike", 15, 15, 6.0, "Fast double-strike with proc chance"),
    SorcerorAbility("Double Attack", 16, 0, 0.0, "Chance to strike twice per round"),
    SorcerorAbility("Flame Blink I", 17, 40, 90.0, "Blink 30 units, release 1 elemental", ElementType.FIRE),
    SorcerorAbility("Flying Kick", 20, 0, 10.0, "High-damage gap closer"),
    SorcerorAbility("Daze of Embers", 20, 80, 30.0, "AE mez 3 targets 12s", ElementType.FIRE),
    SorcerorAbility("Dragon Punch", 25, 20, 10.0, "Heavy single-target strike"),
    SorcerorAbility("Riposte", 25, 0, 0.0, "Counter-attack on successful parry"),
    SorcerorAbility("Flame Stupor", 34, 120, 30.0, "AE mez 4 targets 18s", ElementType.FIRE),
    SorcerorAbility("Flame Blink II", 35, 60, 75.0, "Blink 40 units, release 2 elementals", ElementType.FIRE),
    SorcerorAbility("Triple Attack", 46, 0, 0.0, "Chance to strike three times per round"),
    SorcerorAbility("Inferno Trance", 48, 160, 30.0, "AE mez 5 targets 24s", ElementType.FIRE),
    SorcerorAbility("Flame Blink III", 50, 80, 60.0, "Blink 50 units, release 3 elementals", ElementType.FIRE),
]

# ---------------------------------------------------------------------------
# Runtime State
# ---------------------------------------------------------------------------

@dataclass
class SorcerorState:
    """Mutable runtime state of a Sorceror character."""

    active_element: Optional[ElementType] = None
    active_pets: List[PetDefinition] = field(default_factory=list)
    has_lord_of_maelstrom: bool = False
    has_rumblecrush: bool = False
    liquify_available: bool = True
    mana_percent: float = 100.0


# ---------------------------------------------------------------------------
# Pet Summoning Helpers
# ---------------------------------------------------------------------------

def can_summon_pet(state: SorcerorState, pet: PetDefinition) -> bool:
    """Check whether a pet can be summoned given the single-element rule.

    §2.3: All active pets must share one element unless the Sorceror
    has acquired Lord of the Maelstrom.
    """
    if state.has_lord_of_maelstrom:
        return True
    if not state.active_pets:
        return True
    return state.active_element == pet.element


def switch_element(state: SorcerorState, new_element: ElementType) -> SorcerorState:
    """Dismiss all pets and switch the active element.

    §2.3: Summoning a pet of a different element dismisses all existing pets.
    """
    state.active_pets = []
    state.active_element = new_element
    return state
