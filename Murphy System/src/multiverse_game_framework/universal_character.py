"""
Universal Character & Leveling System for the Multiverse Game Framework.

Design Label: GAME-001 — Universal Character & Leveling System
Owner: Backend Team
Dependencies:
  - EventBackbone
  - PersistenceManager
  - src/eq/soul_engine.py (optional, SoulDocument link)

The same leveling system exists across all worlds. A character can be brought
to any world and their universal level and experience persist across all of them.

Safety invariants:
  - Thread-safe: all shared state guarded by Lock
  - Bounded collections with capped_append pattern (CWE-770)
  - Graceful degradation when subsystem dependencies are unavailable
  - Full audit trail via EventBackbone and PersistenceManager

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import math
import random
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional dependency imports with graceful fallback
# ---------------------------------------------------------------------------

try:
    from thread_safe_operations import capped_append
except ImportError:  # pragma: no cover
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:  # type: ignore[misc]
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

try:
    from event_backbone import EventBackbone, EventType
    _BACKBONE_AVAILABLE = True
except Exception:  # pragma: no cover
    EventBackbone = None  # type: ignore[assignment,misc]
    EventType = None  # type: ignore[assignment]
    _BACKBONE_AVAILABLE = False

try:
    from persistence_manager import PersistenceManager
    _PERSISTENCE_AVAILABLE = True
except Exception:  # pragma: no cover
    PersistenceManager = None  # type: ignore[assignment,misc]
    _PERSISTENCE_AVAILABLE = False

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

UNIVERSAL_LEVEL_CAP = 100
_MAX_HISTORY = 500
_MAX_EVENTS = 10_000

# LUCK XP curve is harder — multiplier on required XP
_LUCK_XP_MULTIPLIER = 3.0

# Base XP required per level (universal curve)
def _base_xp_for_level(level: int) -> int:
    """Universal XP curve: quadratic with exponential tail."""
    if level <= 1:
        return 0
    return int(1_000 * (level - 1) ** 2 + 500 * (level - 1))


# Cooperation wall: solo play diminishing returns above this level
SOLO_WALL_LEVEL = 25

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class CharacterClass(str, Enum):
    """EverQuest-inspired character classes."""
    WARRIOR = "Warrior"
    CLERIC = "Cleric"
    WIZARD = "Wizard"
    ROGUE = "Rogue"
    RANGER = "Ranger"
    BARD = "Bard"
    ENCHANTER = "Enchanter"
    NECROMANCER = "Necromancer"
    DRUID = "Druid"
    MONK = "Monk"
    SHAMAN = "Shaman"
    PALADIN = "Paladin"
    SHADOW_KNIGHT = "Shadow Knight"
    MAGICIAN = "Magician"
    BERSERKER = "Berserker"


class ClassRole(str, Enum):
    """Group composition roles."""
    TANK = "tank"
    HEALER = "healer"
    DPS = "dps"
    SUPPORT = "support"
    CC = "cc"  # crowd control


class LuckCheckOutcome(str, Enum):
    """Outcome of a luck check."""
    CRITICAL_SUCCESS = "critical_success"
    SUCCESS = "success"
    FAILURE = "failure"
    CRITICAL_FAILURE = "critical_failure"


class ActionType(str, Enum):
    """Action types that luck affects."""
    COMBAT = "combat"
    LOOT = "loot"
    CRAFTING = "crafting"
    EXPLORATION = "exploration"
    SOCIAL = "social"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class LuckCheckResult:
    """Result of a luck-based check.

    Args:
        outcome: Whether the check succeeded, failed, or was critical.
        modifier: The calculated luck modifier applied.
        raw_roll: The raw random roll before modifiers (0.0–1.0).
        action_type: The action type being checked.
        description: Human-readable description of what happened.
    """
    outcome: LuckCheckOutcome
    modifier: float
    raw_roll: float
    action_type: ActionType
    description: str


@dataclass
class LevelUpResult:
    """Result of a level-up event.

    Args:
        character_id: The character that levelled up.
        old_level: Previous level.
        new_level: New level.
        stat_increases: Stats that increased on level-up.
        unlocked_skills: Skills newly available at this level.
        world_id: World where the level-up occurred.
    """
    character_id: str
    old_level: int
    new_level: int
    stat_increases: Dict[str, int]
    unlocked_skills: List[str]
    world_id: Optional[str]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ClassDefinition:
    """Definition for a character class.

    Args:
        character_class: The class enum value.
        role: Primary group role.
        group_synergy_tags: Tags used to compute party synergy.
        required_for_content: Whether end-game content requires this class.
        base_stats: Starting stat bonuses for this class.
        primary_stats: Which stats this class prioritises on level-up.
        description: Flavour text.
    """
    character_class: CharacterClass
    role: ClassRole
    group_synergy_tags: List[str]
    required_for_content: bool
    base_stats: Dict[str, int]
    primary_stats: List[str]
    description: str


@dataclass
class UniversalCharacter:
    """A cross-world player character.

    Args:
        character_id: Unique character UUID.
        owner_id: Player or agent_id that owns this character.
        name: Display name.
        character_class: The character's class.
        level: Universal level (1–100).
        stats: Primary stats dict (STR, DEX, INT, WIS, CHA, STA, AGI, LUCK).
        experience_points: Current total XP.
        experience_to_next_level: XP required for the next level.
        skills: Mapping of skill_name → skill_level (class-specific).
        active_world_id: Current world (None = lobby).
        world_visit_history: Ordered list of world_ids visited.
        ai_companion: AI companion configuration dict.
        streaming_profile: Streaming preferences and overlay settings.
        soul_document_id: Optional link to SoulDocument in soul_engine.
        created_at: When the character was created.
    """
    character_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    owner_id: str = ""
    name: str = "Unknown"
    character_class: CharacterClass = CharacterClass.WARRIOR
    level: int = 1
    stats: Dict[str, int] = field(default_factory=lambda: {
        "STR": 10, "DEX": 10, "INT": 10, "WIS": 10,
        "CHA": 10, "STA": 10, "AGI": 10, "LUCK": 10,
    })
    experience_points: int = 0
    experience_to_next_level: int = field(default_factory=lambda: _base_xp_for_level(2))
    skills: Dict[str, int] = field(default_factory=dict)
    active_world_id: Optional[str] = None
    world_visit_history: List[str] = field(default_factory=list)
    ai_companion: Dict[str, Any] = field(default_factory=dict)
    streaming_profile: Dict[str, Any] = field(default_factory=dict)
    soul_document_id: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# LuckSystem
# ---------------------------------------------------------------------------


class LuckSystem:
    """Handles LUCK-based probability modifiers for all action types.

    LUCK is a primary stat with high implications across all gameplay systems.
    It is intentionally difficult to increase (slower XP curve, rare items,
    specific quests) to preserve meaningful variance.
    """

    # Base luck modifier thresholds
    _BASE_MODIFIER: float = 1.0
    _MAX_MODIFIER: float = 3.0
    _MIN_MODIFIER: float = 0.5

    # Critical thresholds (probability)
    _CRITICAL_SUCCESS_THRESHOLD: float = 0.95
    _CRITICAL_FAILURE_THRESHOLD: float = 0.05

    def calculate_luck_modifier(self, luck_stat: int, action_type: ActionType) -> float:
        """Calculate the luck multiplier for a given stat and action type.

        Args:
            luck_stat: The LUCK stat value (typically 1–1000+).
            action_type: The type of action being attempted.

        Returns:
            A float multiplier. 1.0 = neutral, >1.0 = bonus, <1.0 = penalty.
        """
        # Logarithmic scaling to prevent excessive dominance at high LUCK
        base = math.log(max(luck_stat, 1) + 1, 100)

        # Action-type weighting
        weights: Dict[ActionType, float] = {
            ActionType.COMBAT: 1.0,
            ActionType.LOOT: 1.5,       # Loot is heavily LUCK-dependent
            ActionType.CRAFTING: 1.2,
            ActionType.EXPLORATION: 1.3,
            ActionType.SOCIAL: 0.8,     # Social is less LUCK-dependent
        }
        weight = weights.get(action_type, 1.0)
        modifier = self._BASE_MODIFIER + (base - 0.5) * weight
        return max(self._MIN_MODIFIER, min(self._MAX_MODIFIER, modifier))

    def roll_luck_check(
        self,
        character: UniversalCharacter,
        action_type: ActionType,
        difficulty: float,
    ) -> LuckCheckResult:
        """Perform a luck-influenced check for a character action.

        Args:
            character: The character making the attempt.
            action_type: The type of action (combat, loot, crafting, etc.).
            difficulty: Difficulty of the action (0.0 easy → 1.0 very hard).

        Returns:
            LuckCheckResult with outcome, modifier, and roll details.
        """
        luck_stat = character.stats.get("LUCK", 10)
        modifier = self.calculate_luck_modifier(luck_stat, action_type)

        raw_roll = random.random()
        effective_roll = min(1.0, raw_roll * modifier)
        adjusted_threshold = max(0.05, difficulty)

        if effective_roll >= self._CRITICAL_SUCCESS_THRESHOLD:
            outcome = LuckCheckOutcome.CRITICAL_SUCCESS
            description = f"Critical success! LUCK({luck_stat}) blessed this {action_type.value}."
        elif effective_roll >= adjusted_threshold:
            outcome = LuckCheckOutcome.SUCCESS
            description = f"Success on {action_type.value} check (roll={effective_roll:.3f} vs {adjusted_threshold:.3f})."
        elif effective_roll <= self._CRITICAL_FAILURE_THRESHOLD:
            outcome = LuckCheckOutcome.CRITICAL_FAILURE
            description = f"Critical failure! LUCK({luck_stat}) failed this {action_type.value}."
        else:
            outcome = LuckCheckOutcome.FAILURE
            description = f"Failure on {action_type.value} check (roll={effective_roll:.3f} vs {adjusted_threshold:.3f})."

        return LuckCheckResult(
            outcome=outcome,
            modifier=modifier,
            raw_roll=raw_roll,
            action_type=action_type,
            description=description,
        )


# ---------------------------------------------------------------------------
# ClassBalanceRegistry
# ---------------------------------------------------------------------------

_CLASS_DEFINITIONS: List[ClassDefinition] = [
    ClassDefinition(
        character_class=CharacterClass.WARRIOR,
        role=ClassRole.TANK,
        group_synergy_tags=["tank", "melee", "aggro_control"],
        required_for_content=True,
        base_stats={"STR": 15, "STA": 15, "DEX": 8, "INT": 5, "WIS": 5, "CHA": 5, "AGI": 8, "LUCK": 5},
        primary_stats=["STR", "STA"],
        description="Frontline melee combatant. Required anchor for all group content.",
    ),
    ClassDefinition(
        character_class=CharacterClass.CLERIC,
        role=ClassRole.HEALER,
        group_synergy_tags=["healer", "divine", "group_sustain"],
        required_for_content=True,
        base_stats={"STR": 7, "STA": 10, "DEX": 7, "INT": 10, "WIS": 15, "CHA": 10, "AGI": 6, "LUCK": 5},
        primary_stats=["WIS", "INT"],
        description="Primary healer. Group survival depends on a skilled Cleric.",
    ),
    ClassDefinition(
        character_class=CharacterClass.WIZARD,
        role=ClassRole.DPS,
        group_synergy_tags=["dps", "elemental", "burst_magic"],
        required_for_content=False,
        base_stats={"STR": 5, "STA": 7, "DEX": 8, "INT": 18, "WIS": 10, "CHA": 7, "AGI": 8, "LUCK": 7},
        primary_stats=["INT", "WIS"],
        description="Highest burst magical damage. Fragile without tank cover.",
    ),
    ClassDefinition(
        character_class=CharacterClass.ROGUE,
        role=ClassRole.DPS,
        group_synergy_tags=["dps", "melee", "positional", "stealth"],
        required_for_content=False,
        base_stats={"STR": 10, "STA": 9, "DEX": 18, "INT": 8, "WIS": 7, "CHA": 7, "AGI": 15, "LUCK": 6},
        primary_stats=["DEX", "AGI"],
        description="Melee DPS with positional bonuses. Requires tank setup.",
    ),
    ClassDefinition(
        character_class=CharacterClass.RANGER,
        role=ClassRole.DPS,
        group_synergy_tags=["dps", "ranged", "nature", "hybrid"],
        required_for_content=False,
        base_stats={"STR": 12, "STA": 11, "DEX": 15, "INT": 8, "WIS": 10, "CHA": 7, "AGI": 12, "LUCK": 5},
        primary_stats=["DEX", "STR"],
        description="Hybrid ranged/melee. Versatile but rarely best-in-slot for a role.",
    ),
    ClassDefinition(
        character_class=CharacterClass.BARD,
        role=ClassRole.SUPPORT,
        group_synergy_tags=["support", "song", "speed", "mana_regen", "hybrid"],
        required_for_content=True,
        base_stats={"STR": 10, "STA": 10, "DEX": 12, "INT": 10, "WIS": 10, "CHA": 15, "AGI": 10, "LUCK": 8},
        primary_stats=["CHA", "DEX"],
        description="Unparalleled group utility. Speed songs, mana regen, crowd control.",
    ),
    ClassDefinition(
        character_class=CharacterClass.ENCHANTER,
        role=ClassRole.CC,
        group_synergy_tags=["cc", "charm", "mez", "mana_regen", "arcane"],
        required_for_content=True,
        base_stats={"STR": 5, "STA": 7, "DEX": 8, "INT": 18, "WIS": 12, "CHA": 15, "AGI": 7, "LUCK": 8},
        primary_stats=["INT", "CHA"],
        description="Master of crowd control. Charmed pets and mez keep pulls manageable.",
    ),
    ClassDefinition(
        character_class=CharacterClass.NECROMANCER,
        role=ClassRole.DPS,
        group_synergy_tags=["dps", "dot", "undead", "pet"],
        required_for_content=False,
        base_stats={"STR": 5, "STA": 8, "DEX": 8, "INT": 18, "WIS": 10, "CHA": 8, "AGI": 7, "LUCK": 9},
        primary_stats=["INT", "WIS"],
        description="Sustained DoT damage and undead pet support.",
    ),
    ClassDefinition(
        character_class=CharacterClass.DRUID,
        role=ClassRole.HEALER,
        group_synergy_tags=["healer", "nature", "transport", "outdoor"],
        required_for_content=False,
        base_stats={"STR": 7, "STA": 9, "DEX": 8, "INT": 10, "WIS": 16, "CHA": 10, "AGI": 8, "LUCK": 7},
        primary_stats=["WIS", "INT"],
        description="Secondary healer with travel spells and outdoor DPS.",
    ),
    ClassDefinition(
        character_class=CharacterClass.MONK,
        role=ClassRole.DPS,
        group_synergy_tags=["dps", "melee", "unarmed", "feign_death"],
        required_for_content=False,
        base_stats={"STR": 13, "STA": 12, "DEX": 15, "INT": 8, "WIS": 10, "CHA": 6, "AGI": 16, "LUCK": 5},
        primary_stats=["DEX", "AGI"],
        description="Fast melee DPS. Feign death is a unique survival tool.",
    ),
    ClassDefinition(
        character_class=CharacterClass.SHAMAN,
        role=ClassRole.SUPPORT,
        group_synergy_tags=["support", "slow", "buff", "healer", "spirit"],
        required_for_content=True,
        base_stats={"STR": 10, "STA": 10, "DEX": 8, "INT": 10, "WIS": 16, "CHA": 10, "AGI": 7, "LUCK": 9},
        primary_stats=["WIS", "STA"],
        description="Slow debuff changes combat math dramatically. Also buffs and heals.",
    ),
    ClassDefinition(
        character_class=CharacterClass.PALADIN,
        role=ClassRole.TANK,
        group_synergy_tags=["tank", "divine", "lay_on_hands", "undead_control"],
        required_for_content=False,
        base_stats={"STR": 13, "STA": 14, "DEX": 7, "INT": 7, "WIS": 14, "CHA": 12, "AGI": 7, "LUCK": 7},
        primary_stats=["STR", "WIS"],
        description="Holy warrior. Lay on Hands is a powerful emergency save.",
    ),
    ClassDefinition(
        character_class=CharacterClass.SHADOW_KNIGHT,
        role=ClassRole.TANK,
        group_synergy_tags=["tank", "dark", "lifetap", "undead"],
        required_for_content=False,
        base_stats={"STR": 14, "STA": 13, "DEX": 7, "INT": 12, "WIS": 6, "CHA": 8, "AGI": 7, "LUCK": 8},
        primary_stats=["STR", "INT"],
        description="Dark paladin. Lifetap sustains health at mana cost.",
    ),
    ClassDefinition(
        character_class=CharacterClass.MAGICIAN,
        role=ClassRole.DPS,
        group_synergy_tags=["dps", "elemental_pet", "summoner"],
        required_for_content=False,
        base_stats={"STR": 5, "STA": 7, "DEX": 8, "INT": 18, "WIS": 10, "CHA": 7, "AGI": 7, "LUCK": 8},
        primary_stats=["INT", "WIS"],
        description="Elemental pet summoner. Pet does most of the work.",
    ),
    ClassDefinition(
        character_class=CharacterClass.BERSERKER,
        role=ClassRole.DPS,
        group_synergy_tags=["dps", "melee", "frenzy", "aoe"],
        required_for_content=False,
        base_stats={"STR": 16, "STA": 14, "DEX": 12, "INT": 5, "WIS": 5, "CHA": 5, "AGI": 10, "LUCK": 8},
        primary_stats=["STR", "DEX"],
        description="Frenzied melee DPS. AoE frenzy excels against packs.",
    ),
]


class ClassBalanceRegistry:
    """Registry of all character classes and group composition rules.

    Classes matter significantly for group composition (EverQuest-style).
    Cooperation is required to progress — solo play hits a soft wall around
    level 20–30 and a hard wall around level 40.
    """

    def __init__(self) -> None:
        self._classes: Dict[CharacterClass, ClassDefinition] = {
            defn.character_class: defn for defn in _CLASS_DEFINITIONS
        }

    def get_class_definition(self, character_class: CharacterClass) -> Optional[ClassDefinition]:
        """Return the definition for a specific class."""
        return self._classes.get(character_class)

    def get_required_classes(self) -> List[ClassDefinition]:
        """Return classes that are required for end-game content."""
        return [d for d in self._classes.values() if d.required_for_content]

    def get_party_synergy_score(self, party_classes: List[CharacterClass]) -> float:
        """Score how well a group composition works together.

        A balanced party with all required roles scores higher. Duplicate roles
        or missing critical roles lower the score.

        Args:
            party_classes: List of class enum values in the party.

        Returns:
            A score from 0.0 (terrible composition) to 1.0 (perfect composition).
        """
        if not party_classes:
            return 0.0

        roles_present: Dict[ClassRole, int] = {}
        for cls in party_classes:
            defn = self._classes.get(cls)
            if defn:
                roles_present[defn.role] = roles_present.get(defn.role, 0) + 1

        # Required roles for viable group content
        required_roles = {ClassRole.TANK, ClassRole.HEALER}
        has_required = all(r in roles_present for r in required_roles)
        if not has_required:
            return 0.1  # Near-unviable without a tank and healer

        score = 0.5  # Base score for having tank + healer

        # Bonus for DPS
        if ClassRole.DPS in roles_present:
            score += 0.15

        # Bonus for CC or support
        if ClassRole.CC in roles_present or ClassRole.SUPPORT in roles_present:
            score += 0.2

        # Bonus for having both CC and support
        if ClassRole.CC in roles_present and ClassRole.SUPPORT in roles_present:
            score += 0.1

        # Check required-for-content classes coverage
        tags_present: set = set()
        for cls in party_classes:
            defn = self._classes.get(cls)
            if defn:
                tags_present.update(defn.group_synergy_tags)

        # Penalise heavy role stacking (e.g., 3 healers)
        for count in roles_present.values():
            if count >= 3:
                score -= 0.1 * (count - 2)

        return max(0.0, min(1.0, score))

    def all_classes(self) -> List[ClassDefinition]:
        """Return all class definitions."""
        return list(self._classes.values())


# ---------------------------------------------------------------------------
# UniversalLevelingEngine
# ---------------------------------------------------------------------------


class UniversalLevelingEngine:
    """Manages universal XP and leveling across all worlds.

    XP gained in any world counts toward the single universal level.
    """

    def __init__(
        self,
        backbone: Optional[Any] = None,
        persistence: Optional[Any] = None,
    ) -> None:
        self._backbone = backbone
        self._persistence = persistence
        self._lock = threading.Lock()
        self._level_up_log: List[LevelUpResult] = []
        self._luck_system = LuckSystem()
        self._class_registry = ClassBalanceRegistry()

    # ------------------------------------------------------------------
    # XP curve helpers
    # ------------------------------------------------------------------

    @staticmethod
    def xp_required_for_level(target_level: int) -> int:
        """Total cumulative XP required to reach a given level from level 1."""
        return sum(_base_xp_for_level(lvl) for lvl in range(2, target_level + 1))

    @staticmethod
    def xp_for_next_level(current_level: int) -> int:
        """XP required to advance from current_level to current_level+1."""
        return _base_xp_for_level(current_level + 1)

    # ------------------------------------------------------------------
    # Group synergy bonus
    # ------------------------------------------------------------------

    def _calculate_group_xp_bonus(
        self,
        party_classes: Optional[List[CharacterClass]],
    ) -> float:
        """Calculate group XP multiplier based on party composition."""
        if not party_classes or len(party_classes) < 2:
            return 1.0
        score = self._class_registry.get_party_synergy_score(party_classes)
        # Scale bonus: 0.0 synergy = 1.0x, 1.0 synergy = 1.5x
        return 1.0 + 0.5 * score

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def award_experience(
        self,
        character: UniversalCharacter,
        amount: int,
        source_world_id: str,
        source_action: str,
        party_classes: Optional[List[CharacterClass]] = None,
    ) -> None:
        """Award XP to a character from any world action.

        Args:
            character: The character receiving XP.
            amount: Raw XP amount before modifiers.
            source_world_id: World where the XP was earned.
            source_action: Description of the action (e.g., "mob_kill", "quest_complete").
            party_classes: Optional list of party member classes for synergy bonuses.
        """
        if character.level >= UNIVERSAL_LEVEL_CAP:
            return

        group_bonus = self._calculate_group_xp_bonus(party_classes)
        effective_amount = int(amount * group_bonus)

        # Solo wall: diminishing returns above SOLO_WALL_LEVEL
        if character.level > SOLO_WALL_LEVEL and (not party_classes or len(party_classes) < 2):
            penalty = 1.0 - 0.03 * (character.level - SOLO_WALL_LEVEL)
            effective_amount = int(effective_amount * max(0.1, penalty))

        with self._lock:
            character.experience_points += effective_amount
            logger.debug(
                "Awarded %d XP (raw=%d, group_bonus=%.2f) to %s from %s/%s",
                effective_amount, amount, group_bonus,
                character.character_id, source_world_id, source_action,
            )

    def check_level_up(self, character: UniversalCharacter) -> Optional[LevelUpResult]:
        """Check if the character has enough XP to level up.

        Applies level-up and returns a LevelUpResult if a level-up occurred,
        otherwise returns None. Only advances one level at a time.

        Args:
            character: The character to check.

        Returns:
            LevelUpResult if a level-up occurred, else None.
        """
        if character.level >= UNIVERSAL_LEVEL_CAP:
            return None

        needed = self.xp_for_next_level(character.level)
        if character.experience_points < needed:
            return None

        old_level = character.level
        character.experience_points -= needed
        character.level += 1
        character.experience_to_next_level = self.xp_for_next_level(character.level)

        # Calculate stat increases on level-up
        cls_defn = ClassBalanceRegistry().get_class_definition(character.character_class)
        stat_increases: Dict[str, int] = {}
        if cls_defn:
            for stat in cls_defn.primary_stats:
                character.stats[stat] = character.stats.get(stat, 10) + 2
                stat_increases[stat] = 2
            # Minor increase to other stats
            for stat in character.stats:
                if stat not in cls_defn.primary_stats and stat != "LUCK":
                    character.stats[stat] = character.stats.get(stat, 10) + 1
                    stat_increases[stat] = stat_increases.get(stat, 0) + 1
            # LUCK increases very slowly
            if character.level % 10 == 0:
                character.stats["LUCK"] = character.stats.get("LUCK", 10) + 1
                stat_increases["LUCK"] = stat_increases.get("LUCK", 0) + 1

        result = LevelUpResult(
            character_id=character.character_id,
            old_level=old_level,
            new_level=character.level,
            stat_increases=stat_increases,
            unlocked_skills=[],
            world_id=character.active_world_id,
        )

        with self._lock:
            capped_append(self._level_up_log, result, _MAX_EVENTS)

        self._publish_event("character_level_up", {
            "character_id": character.character_id,
            "old_level": old_level,
            "new_level": character.level,
        })
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _publish_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        """Publish an event to the EventBackbone if available."""
        if _BACKBONE_AVAILABLE and self._backbone is not None:
            try:
                self._backbone.publish(event_type, payload)
            except Exception:  # pragma: no cover
                logger.debug("EventBackbone publish failed silently", exc_info=True)
