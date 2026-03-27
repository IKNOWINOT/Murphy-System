"""
Class Balance Engine — Class System and Balance Framework

Defines all playable classes, their role archetypes, synergy matrices,
and spell combination systems for MMORPG games produced by the pipeline.

Provides:
  - Class definitions with role archetypes (tank, healer, DPS, support, hybrid)
  - Synergy matrix — defines how classes combine
  - Spell combination system (simultaneous cast magnifiers)
  - Luck stat integration into all class abilities
  - Balance scoring and auto-adjustment recommendations
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
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
# Enums
# ---------------------------------------------------------------------------

class RoleArchetype(Enum):
    """Primary role a class fills in group content."""

    TANK = "tank"
    HEALER = "healer"
    DPS_MELEE = "dps_melee"
    DPS_RANGED = "dps_ranged"
    DPS_CASTER = "dps_caster"
    SUPPORT = "support"
    HYBRID = "hybrid"


class SpellElement(Enum):
    """Elemental tags used for combination spell detection."""

    FIRE = "fire"
    ICE = "ice"
    LIGHTNING = "lightning"
    SHADOW = "shadow"
    HOLY = "holy"
    EARTH = "earth"
    WIND = "wind"
    ARCANE = "arcane"
    NATURE = "nature"
    VOID = "void"


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class ClassAbility:
    """A single ability belonging to a class."""

    ability_id: str
    name: str
    element: Optional[SpellElement]
    base_power: float
    cast_time_seconds: float
    cooldown_seconds: float
    role: RoleArchetype
    luck_scaling: float = 0.0   # 0–1: how much luck amplifies this ability
    description: str = ""


@dataclass
class ClassDefinition:
    """Complete definition of a playable class."""

    class_id: str
    name: str
    primary_role: RoleArchetype
    secondary_role: Optional[RoleArchetype]
    description: str
    abilities: List[ClassAbility] = field(default_factory=list)
    base_stats: Dict[str, float] = field(default_factory=dict)
    luck_growth_rate: float = 0.5    # How fast luck stat grows for this class
    required_group_role: bool = False  # True = class NEEDS a group to be effective

    # Balance metadata
    intended_power_level: float = 1.0   # 1.0 = baseline
    current_power_level: float = 1.0


@dataclass
class CombinationSpell:
    """
    Emergent effect when two or more elemental spells combine simultaneously.

    e.g., FIRE + WIND → Firestorm with 2.5x magnifier.
    """

    combination_id: str
    name: str
    elements: Tuple[SpellElement, ...]   # elements that trigger this combo
    magnifier: float                      # power multiplier
    description: str
    min_casters: int = 2                  # minimum simultaneous casters


@dataclass
class SynergyBonus:
    """Bonus awarded when a set of roles cooperate."""

    bonus_id: str
    required_roles: Tuple[RoleArchetype, ...]
    multiplier: float
    description: str


@dataclass
class BalanceReport:
    """Auto-generated balance analysis."""

    report_id: str
    timestamp: float
    class_power_levels: Dict[str, float]   # class_id → power level
    outliers: List[str]                     # class_ids outside threshold
    recommendations: List[str]
    overall_balance_score: float            # 0–1, 1 = perfectly balanced


# ---------------------------------------------------------------------------
# Built-in Class Definitions
# ---------------------------------------------------------------------------

def _build_default_classes() -> Dict[str, ClassDefinition]:
    """Return the default set of 12 MMORPG classes."""

    def _ability(
        aid: str, name: str, elem: Optional[SpellElement],
        power: float, cast: float, cd: float, role: RoleArchetype,
        luck: float = 0.0, desc: str = "",
    ) -> ClassAbility:
        return ClassAbility(
            ability_id=aid, name=name, element=elem,
            base_power=power, cast_time_seconds=cast,
            cooldown_seconds=cd, role=role,
            luck_scaling=luck, description=desc,
        )

    classes = {}

    # --- TANK ---
    classes["warrior"] = ClassDefinition(
        class_id="warrior", name="Warrior",
        primary_role=RoleArchetype.TANK, secondary_role=None,
        description="Front-line tank. Must be present for group survival.",
        required_group_role=True,
        abilities=[
            _ability("war_taunt", "Warcry Taunt", None, 0, 0, 6, RoleArchetype.TANK),
            _ability("war_shield", "Iron Shield", None, 100, 1, 15, RoleArchetype.TANK),
        ],
        base_stats={"hp": 500, "defense": 80, "attack": 40, "luck": 10},
        luck_growth_rate=0.3,
    )

    classes["paladin"] = ClassDefinition(
        class_id="paladin", name="Paladin",
        primary_role=RoleArchetype.TANK, secondary_role=RoleArchetype.HEALER,
        description="Holy tank/healer hybrid. Synergizes with clerics.",
        required_group_role=True,
        abilities=[
            _ability("pal_holy_strike", "Holy Strike", SpellElement.HOLY, 120, 1.5, 8, RoleArchetype.DPS_MELEE, 0.3),
            _ability("pal_lay_hands", "Lay on Hands", SpellElement.HOLY, 500, 3.0, 600, RoleArchetype.HEALER, 0.5),
        ],
        base_stats={"hp": 450, "defense": 70, "attack": 50, "luck": 15},
        luck_growth_rate=0.4,
    )

    # --- HEALER ---
    classes["cleric"] = ClassDefinition(
        class_id="cleric", name="Cleric",
        primary_role=RoleArchetype.HEALER, secondary_role=None,
        description="Primary healer. Groups cannot survive long raids without one.",
        required_group_role=True,
        abilities=[
            _ability("clr_heal", "Divine Heal", SpellElement.HOLY, 300, 2.5, 0, RoleArchetype.HEALER, 0.6),
            _ability("clr_rez", "Resurrection", SpellElement.HOLY, 0, 5.0, 60, RoleArchetype.HEALER, 0.8),
        ],
        base_stats={"hp": 280, "defense": 30, "attack": 20, "luck": 20},
        luck_growth_rate=0.6,
    )

    classes["shaman"] = ClassDefinition(
        class_id="shaman", name="Shaman",
        primary_role=RoleArchetype.HEALER, secondary_role=RoleArchetype.SUPPORT,
        description="Nature healer with buffs and slows. High luck stat.",
        abilities=[
            _ability("sha_heal", "Ancestral Healing", SpellElement.NATURE, 220, 2.0, 0, RoleArchetype.HEALER, 0.7),
            _ability("sha_slow", "Spirit Slow", SpellElement.EARTH, 0, 1.5, 12, RoleArchetype.SUPPORT),
        ],
        base_stats={"hp": 300, "defense": 35, "attack": 30, "luck": 25},
        luck_growth_rate=0.7,
    )

    # --- DPS MELEE ---
    classes["rogue"] = ClassDefinition(
        class_id="rogue", name="Rogue",
        primary_role=RoleArchetype.DPS_MELEE, secondary_role=None,
        description="High single-target DPS. Requires a tank to function optimally.",
        required_group_role=True,
        abilities=[
            _ability("rog_backstab", "Backstab", SpellElement.SHADOW, 350, 0, 6, RoleArchetype.DPS_MELEE, 0.8),
            _ability("rog_evade", "Evasion", None, 0, 0, 30, RoleArchetype.DPS_MELEE),
        ],
        base_stats={"hp": 260, "defense": 25, "attack": 90, "luck": 30},
        luck_growth_rate=0.9,
    )

    classes["monk"] = ClassDefinition(
        class_id="monk", name="Monk",
        primary_role=RoleArchetype.DPS_MELEE, secondary_role=RoleArchetype.SUPPORT,
        description="Melee DPS with party utility. Harmony buffs reduce spell aggro.",
        abilities=[
            _ability("mnk_flying_kick", "Flying Kick", SpellElement.WIND, 200, 0, 4, RoleArchetype.DPS_MELEE, 0.4),
            _ability("mnk_harmony", "Tranquil Harmony", SpellElement.WIND, 0, 3, 60, RoleArchetype.SUPPORT),
        ],
        base_stats={"hp": 300, "defense": 40, "attack": 80, "luck": 20},
        luck_growth_rate=0.5,
    )

    # --- DPS CASTER ---
    classes["wizard"] = ClassDefinition(
        class_id="wizard", name="Wizard",
        primary_role=RoleArchetype.DPS_CASTER, secondary_role=None,
        description="Highest burst damage. Requires healer and tank support.",
        required_group_role=True,
        abilities=[
            _ability("wiz_fireball", "Fireball", SpellElement.FIRE, 600, 3.5, 10, RoleArchetype.DPS_CASTER, 0.5),
            _ability("wiz_ice_comet", "Ice Comet", SpellElement.ICE, 700, 4.0, 12, RoleArchetype.DPS_CASTER, 0.6),
        ],
        base_stats={"hp": 200, "defense": 15, "attack": 100, "luck": 15},
        luck_growth_rate=0.4,
    )

    classes["magician"] = ClassDefinition(
        class_id="magician", name="Magician",
        primary_role=RoleArchetype.DPS_CASTER, secondary_role=RoleArchetype.SUPPORT,
        description="Fire/earth pet caster. Pet provides off-tank capability.",
        abilities=[
            _ability("mag_fireball", "Blazing Bolt", SpellElement.FIRE, 450, 2.5, 8, RoleArchetype.DPS_CASTER, 0.4),
            _ability("mag_pet_fire", "Summon Fire Pet", SpellElement.FIRE, 0, 5, 300, RoleArchetype.SUPPORT),
        ],
        base_stats={"hp": 220, "defense": 20, "attack": 90, "luck": 18},
        luck_growth_rate=0.45,
    )

    # --- DPS RANGED ---
    classes["ranger"] = ClassDefinition(
        class_id="ranger", name="Ranger",
        primary_role=RoleArchetype.DPS_RANGED, secondary_role=RoleArchetype.SUPPORT,
        description="Ranged DPS with pull capability. Essential for crowd control.",
        abilities=[
            _ability("rng_arrow", "Arrow Shot", SpellElement.WIND, 280, 1.0, 3, RoleArchetype.DPS_RANGED, 0.5),
            _ability("rng_ensnare", "Ensnare", SpellElement.NATURE, 0, 1.5, 20, RoleArchetype.SUPPORT),
        ],
        base_stats={"hp": 280, "defense": 30, "attack": 85, "luck": 25},
        luck_growth_rate=0.6,
    )

    # --- SUPPORT ---
    classes["bard"] = ClassDefinition(
        class_id="bard", name="Bard",
        primary_role=RoleArchetype.SUPPORT, secondary_role=RoleArchetype.DPS_MELEE,
        description="Unique song-based support. Grants massive group buffs when cooperating.",
        abilities=[
            _ability("brd_haste", "Selo's Accelerando", SpellElement.ARCANE, 0, 0, 12, RoleArchetype.SUPPORT),
            _ability("brd_mana_song", "Cassindra's Chorus", SpellElement.ARCANE, 0, 0, 18, RoleArchetype.SUPPORT),
        ],
        base_stats={"hp": 290, "defense": 35, "attack": 60, "luck": 22},
        luck_growth_rate=0.55,
    )

    classes["enchanter"] = ClassDefinition(
        class_id="enchanter", name="Enchanter",
        primary_role=RoleArchetype.SUPPORT, secondary_role=RoleArchetype.DPS_CASTER,
        description="Crowd control master. Groups fail without an enchanter on hard content.",
        required_group_role=True,
        abilities=[
            _ability("enc_mez", "Mesmerize", SpellElement.ARCANE, 0, 1.5, 24, RoleArchetype.SUPPORT),
            _ability("enc_haste", "Clarity", SpellElement.ARCANE, 0, 4, 60, RoleArchetype.SUPPORT),
        ],
        base_stats={"hp": 220, "defense": 20, "attack": 70, "luck": 20},
        luck_growth_rate=0.5,
    )

    # --- HYBRID ---
    classes["shadowknight"] = ClassDefinition(
        class_id="shadowknight", name="Shadow Knight",
        primary_role=RoleArchetype.TANK, secondary_role=RoleArchetype.DPS_CASTER,
        description="Dark tank with lifetap and shadow magic. Unique dark synergies.",
        required_group_role=True,
        abilities=[
            _ability("sk_lifetap", "Lifetap", SpellElement.SHADOW, 300, 2, 8, RoleArchetype.DPS_CASTER, 0.6),
            _ability("sk_harm_touch", "Harm Touch", SpellElement.SHADOW, 800, 0, 900, RoleArchetype.DPS_MELEE, 0.7),
        ],
        base_stats={"hp": 460, "defense": 72, "attack": 55, "luck": 12},
        luck_growth_rate=0.35,
    )

    return classes


# Built-in combination spells (fire+wind, fire+fire, etc.)
DEFAULT_COMBINATIONS: List[CombinationSpell] = [
    CombinationSpell(
        combination_id="combo_firestorm",
        name="Firestorm",
        elements=(SpellElement.FIRE, SpellElement.WIND),
        magnifier=2.5,
        description="Fire + Wind creates a sweeping firestorm affecting all nearby enemies.",
    ),
    CombinationSpell(
        combination_id="combo_blizzard",
        name="Blizzard",
        elements=(SpellElement.ICE, SpellElement.WIND),
        magnifier=2.2,
        description="Ice + Wind creates a blizzard that slows and damages all enemies.",
    ),
    CombinationSpell(
        combination_id="combo_thunderstrike",
        name="Thunderstrike",
        elements=(SpellElement.LIGHTNING, SpellElement.WIND),
        magnifier=2.8,
        description="Lightning + Wind chain-lightning through all nearby foes.",
    ),
    CombinationSpell(
        combination_id="combo_void_shadow",
        name="Void Collapse",
        elements=(SpellElement.VOID, SpellElement.SHADOW),
        magnifier=3.0,
        description="Shadow + Void collapses the weave of space, stunning all enemies.",
    ),
    CombinationSpell(
        combination_id="combo_dual_fire",
        name="Inferno",
        elements=(SpellElement.FIRE, SpellElement.FIRE),
        magnifier=2.0,
        description="Two fire casters casting simultaneously create a raging inferno.",
        min_casters=2,
    ),
    CombinationSpell(
        combination_id="combo_holy_holy",
        name="Divine Radiance",
        elements=(SpellElement.HOLY, SpellElement.HOLY),
        magnifier=1.8,
        description="Two holy casters healing simultaneously create a radiant AoE heal.",
        min_casters=2,
    ),
]

# Built-in role synergy bonuses
DEFAULT_SYNERGIES: List[SynergyBonus] = [
    SynergyBonus(
        bonus_id="classic_trio",
        required_roles=(RoleArchetype.TANK, RoleArchetype.HEALER, RoleArchetype.DPS_CASTER),
        multiplier=1.15,
        description="Classic holy trinity — tank, healer, and caster working together.",
    ),
    SynergyBonus(
        bonus_id="full_support_stack",
        required_roles=(
            RoleArchetype.TANK, RoleArchetype.HEALER,
            RoleArchetype.SUPPORT, RoleArchetype.DPS_CASTER,
        ),
        multiplier=1.35,
        description="Full role coverage with dedicated support gives maximum efficiency.",
    ),
    SynergyBonus(
        bonus_id="dps_pair",
        required_roles=(RoleArchetype.DPS_MELEE, RoleArchetype.DPS_RANGED),
        multiplier=1.10,
        description="Melee and ranged DPS supporting each other increases burst window.",
    ),
]


# ---------------------------------------------------------------------------
# Core Engine
# ---------------------------------------------------------------------------

class ClassBalanceEngine:
    """
    Manages class definitions, synergy matrices, and balance scoring.

    Thread-safe: all shared state protected by ``_lock``.
    """

    _BALANCE_OUTLIER_THRESHOLD = 0.20   # >20% deviation from mean = outlier

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._classes: Dict[str, ClassDefinition] = _build_default_classes()
        self._combinations: List[CombinationSpell] = list(DEFAULT_COMBINATIONS)
        self._synergies: List[SynergyBonus] = list(DEFAULT_SYNERGIES)
        self._balance_reports: List[BalanceReport] = []

    # ------------------------------------------------------------------
    # Class access
    # ------------------------------------------------------------------

    def get_class(self, class_id: str) -> Optional[ClassDefinition]:
        """Return a class definition by ID."""
        with self._lock:
            return self._classes.get(class_id)

    def all_classes(self) -> List[ClassDefinition]:
        """Return all registered class definitions."""
        with self._lock:
            return list(self._classes.values())

    def register_class(self, class_def: ClassDefinition) -> None:
        """Add or replace a class definition."""
        with self._lock:
            self._classes[class_def.class_id] = class_def

    # ------------------------------------------------------------------
    # Synergy calculation
    # ------------------------------------------------------------------

    def role_synergy_multiplier(self, roles: List[RoleArchetype]) -> float:
        """
        Calculate the total synergy multiplier for a group composition.

        Returns the highest applicable synergy bonus (multiplicative).
        """
        role_set = set(roles)
        best = 1.0
        with self._lock:
            for syn in self._synergies:
                if all(r in role_set for r in syn.required_roles):
                    if syn.multiplier > best:
                        best = syn.multiplier
        return best

    def find_combination(
        self, elements: List[SpellElement]
    ) -> Optional[CombinationSpell]:
        """
        Find a combination spell matching the given set of elements.

        Checks for exact match (order-independent).
        """
        element_counts: Dict[SpellElement, int] = {}
        for e in elements:
            element_counts[e] = element_counts.get(e, 0) + 1

        with self._lock:
            for combo in self._combinations:
                combo_counts: Dict[SpellElement, int] = {}
                for e in combo.elements:
                    combo_counts[e] = combo_counts.get(e, 0) + 1
                if combo_counts == element_counts:
                    return combo
        return None

    # ------------------------------------------------------------------
    # Balance scoring
    # ------------------------------------------------------------------

    def generate_balance_report(self) -> BalanceReport:
        """
        Produce a balance report based on current class power levels.

        Identifies outliers and generates recommendations.
        """
        with self._lock:
            classes_snap = dict(self._classes)

        if not classes_snap:
            return BalanceReport(
                report_id=str(uuid.uuid4()),
                timestamp=time.time(),
                class_power_levels={},
                outliers=[],
                recommendations=["No classes registered."],
                overall_balance_score=1.0,
            )

        power_levels = {cid: c.current_power_level for cid, c in classes_snap.items()}
        mean_power = sum(power_levels.values()) / len(power_levels)

        outliers = [
            cid for cid, pwr in power_levels.items()
            if abs(pwr - mean_power) / max(mean_power, 0.01) > self._BALANCE_OUTLIER_THRESHOLD
        ]

        recommendations: List[str] = []
        for cid in outliers:
            pwr = power_levels[cid]
            if pwr > mean_power:
                recommendations.append(
                    f"Nerf '{classes_snap[cid].name}': power {pwr:.2f} is "
                    f"{((pwr - mean_power) / mean_power * 100):.1f}% above mean."
                )
            else:
                recommendations.append(
                    f"Buff '{classes_snap[cid].name}': power {pwr:.2f} is "
                    f"{((mean_power - pwr) / mean_power * 100):.1f}% below mean."
                )

        if not outliers:
            balance_score = 1.0
        else:
            deviations = [
                abs(power_levels[cid] - mean_power) / max(mean_power, 0.01)
                for cid in outliers
            ]
            avg_deviation = sum(deviations) / len(deviations)
            balance_score = max(0.0, 1.0 - avg_deviation)

        report = BalanceReport(
            report_id=str(uuid.uuid4()),
            timestamp=time.time(),
            class_power_levels=power_levels,
            outliers=outliers,
            recommendations=recommendations,
            overall_balance_score=round(balance_score, 4),
        )

        with self._lock:
            capped_append(self._balance_reports, report, 100)
        return report

    def update_class_power(self, class_id: str, new_power: float) -> None:
        """Update the observed power level for a class."""
        with self._lock:
            if class_id in self._classes:
                self._classes[class_id].current_power_level = max(0.1, new_power)
