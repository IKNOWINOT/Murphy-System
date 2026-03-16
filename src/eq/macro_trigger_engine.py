"""
Macro-Trigger Behavior Engine — Classic Bot Behavior as Agent Triggers

Implements the macro-trigger behavior engine described in §6.2 and §11.3
of the Experimental EverQuest Modification Plan.

Provides:
  - Classic EQ bot macro patterns (/assist, /follow, /attack, /cast, etc.)
    as structured agent behavioral triggers
  - Play-style templates per agent class archetype (pure melee, int caster,
    cleric, hybrid)
  - Trigger priority evaluation with condition checks
  - Integration with soul engine for mind-write and combat state
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

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
# Trigger Types (modeled on classic MQ2/E3/EQEmu bot commands)
# ---------------------------------------------------------------------------

class TriggerType(Enum):
    """Trigger type (Enum subclass)."""
    ASSIST = "assist"       # Target the MA's target
    FOLLOW = "follow"       # Follow a designated leader
    ATTACK = "attack"       # Engage current target
    CAST = "cast"           # Cast a spell on target or self
    BUFF = "buff"           # Maintain buffs on group
    HEAL = "heal"           # Heal group members below threshold
    DEBUFF = "debuff"       # Apply debuffs to hostile targets
    MEZ = "mez"             # Crowd control (mez adds)
    TANK = "tank"           # Generate aggro, use defensive abilities
    PULL = "pull"           # Pull mobs to camp
    LOOT = "loot"           # Loot corpses in range
    FLEE = "flee"           # Disengage and run when conditions met
    EVAC = "evac"           # Zone evacuation
    GATE = "gate"           # Gate to bind point
    SIT = "sit"             # Sit to meditate/regen
    STAND = "stand"         # Stand up (combat ready)
    CAMP = "camp"           # Log out


# ---------------------------------------------------------------------------
# Combat State (from soul engine short-term memory)
# ---------------------------------------------------------------------------

class CombatState(Enum):
    """Combat state (Enum subclass)."""
    IDLE = "idle"
    COMBAT = "combat"
    FLEEING = "fleeing"
    DEAD = "dead"
    SITTING = "sitting"
    FOLLOWING = "following"


# ---------------------------------------------------------------------------
# Trigger Condition
# ---------------------------------------------------------------------------

@dataclass
class TriggerCondition:
    """A condition that must be met for a trigger to fire."""

    name: str
    check_field: str  # Path into agent state dict
    operator: str     # "lt", "gt", "eq", "ne", "in", "not_in"
    value: Any = None

    def evaluate(self, state: Dict[str, Any]) -> bool:
        """Evaluate this condition against the given state dict."""
        actual = state.get(self.check_field)
        if actual is None:
            return False
        if self.operator == "lt":
            return actual < self.value
        if self.operator == "gt":
            return actual > self.value
        if self.operator == "eq":
            return actual == self.value
        if self.operator == "ne":
            return actual != self.value
        if self.operator == "in":
            return actual in self.value
        if self.operator == "not_in":
            return actual not in self.value
        return False


# ---------------------------------------------------------------------------
# Trigger Definition
# ---------------------------------------------------------------------------

@dataclass
class TriggerDefinition:
    """A behavioral trigger that can fire when conditions are met."""

    trigger_type: TriggerType
    priority: int = 50  # Lower number = higher priority
    conditions: List[TriggerCondition] = field(default_factory=list)
    parameters: Dict[str, Any] = field(default_factory=dict)
    cooldown_seconds: float = 0.0
    description: str = ""

    def all_conditions_met(self, state: Dict[str, Any]) -> bool:
        return all(c.evaluate(state) for c in self.conditions)


# ---------------------------------------------------------------------------
# Trigger Result
# ---------------------------------------------------------------------------

@dataclass
class TriggerResult:
    """The result of evaluating and firing a trigger."""

    trigger_type: TriggerType
    fired: bool
    parameters: Dict[str, Any] = field(default_factory=dict)
    reason: str = ""


# ---------------------------------------------------------------------------
# Play-Style Templates (§6.2 — immutable per class archetype)
# ---------------------------------------------------------------------------

def _melee_template() -> List[TriggerDefinition]:
    """Pure melee DPS play-style template (warrior, monk, rogue)."""
    return [
        TriggerDefinition(
            trigger_type=TriggerType.ASSIST,
            priority=10,
            conditions=[
                TriggerCondition("combat_active", "combat_state", "eq", CombatState.COMBAT.value),
            ],
            description="Assist MA on engage",
        ),
        TriggerDefinition(
            trigger_type=TriggerType.ATTACK,
            priority=20,
            conditions=[
                TriggerCondition("has_target", "has_target", "eq", True),
            ],
            description="Attack current target",
        ),
        TriggerDefinition(
            trigger_type=TriggerType.FLEE,
            priority=5,
            conditions=[
                TriggerCondition("hp_low", "hp_percent", "lt", 20),
                TriggerCondition("healer_dead", "group_healer_alive", "eq", False),
            ],
            description="Flee when HP low and no healer",
        ),
        TriggerDefinition(
            trigger_type=TriggerType.SIT,
            priority=90,
            conditions=[
                TriggerCondition("idle", "combat_state", "eq", CombatState.IDLE.value),
            ],
            description="Sit when idle to regen",
        ),
    ]


def _caster_template() -> List[TriggerDefinition]:
    """Int caster play-style template (wizard, mage, necro, enchanter)."""
    return [
        TriggerDefinition(
            trigger_type=TriggerType.ASSIST,
            priority=10,
            conditions=[
                TriggerCondition("combat_active", "combat_state", "eq", CombatState.COMBAT.value),
            ],
            description="Assist MA on engage",
        ),
        TriggerDefinition(
            trigger_type=TriggerType.DEBUFF,
            priority=15,
            conditions=[
                TriggerCondition("has_target", "has_target", "eq", True),
                TriggerCondition("mana_ok", "mana_percent", "gt", 30),
            ],
            description="Debuff target if mana allows",
        ),
        TriggerDefinition(
            trigger_type=TriggerType.CAST,
            priority=20,
            conditions=[
                TriggerCondition("has_target", "has_target", "eq", True),
                TriggerCondition("mana_ok", "mana_percent", "gt", 20),
            ],
            description="Nuke target",
        ),
        TriggerDefinition(
            trigger_type=TriggerType.SIT,
            priority=90,
            conditions=[
                TriggerCondition("idle", "combat_state", "eq", CombatState.IDLE.value),
                TriggerCondition("mana_low", "mana_percent", "lt", 80),
            ],
            description="Sit to meditate when OOC and mana low",
        ),
        TriggerDefinition(
            trigger_type=TriggerType.FLEE,
            priority=5,
            conditions=[
                TriggerCondition("hp_low", "hp_percent", "lt", 25),
            ],
            description="Flee when HP low",
        ),
    ]


def _cleric_template() -> List[TriggerDefinition]:
    """Cleric/healer play-style template."""
    return [
        TriggerDefinition(
            trigger_type=TriggerType.HEAL,
            priority=5,
            conditions=[
                TriggerCondition("group_hurt", "lowest_group_hp_percent", "lt", 70),
                TriggerCondition("mana_ok", "mana_percent", "gt", 10),
            ],
            description="Heal lowest group member",
        ),
        TriggerDefinition(
            trigger_type=TriggerType.BUFF,
            priority=30,
            conditions=[
                TriggerCondition("missing_buffs", "group_missing_buffs", "gt", 0),
                TriggerCondition("idle", "combat_state", "eq", CombatState.IDLE.value),
            ],
            description="Buff group between fights",
        ),
        TriggerDefinition(
            trigger_type=TriggerType.SIT,
            priority=80,
            conditions=[
                TriggerCondition("idle", "combat_state", "eq", CombatState.IDLE.value),
                TriggerCondition("mana_low", "mana_percent", "lt", 80),
            ],
            description="Sit to meditate when OOC",
        ),
        TriggerDefinition(
            trigger_type=TriggerType.FLEE,
            priority=3,
            conditions=[
                TriggerCondition("hp_crit", "hp_percent", "lt", 15),
                TriggerCondition("mana_empty", "mana_percent", "lt", 5),
            ],
            description="Flee when both HP and mana critical",
        ),
    ]


def _hybrid_template() -> List[TriggerDefinition]:
    """Hybrid play-style template (paladin, ranger, SK, bard, sorceror)."""
    return [
        TriggerDefinition(
            trigger_type=TriggerType.ASSIST,
            priority=10,
            conditions=[
                TriggerCondition("combat_active", "combat_state", "eq", CombatState.COMBAT.value),
            ],
            description="Assist MA on engage",
        ),
        TriggerDefinition(
            trigger_type=TriggerType.HEAL,
            priority=8,
            conditions=[
                TriggerCondition("group_hurt", "lowest_group_hp_percent", "lt", 50),
                TriggerCondition("mana_ok", "mana_percent", "gt", 20),
            ],
            description="Off-heal if group is hurting and mana allows",
        ),
        TriggerDefinition(
            trigger_type=TriggerType.ATTACK,
            priority=20,
            conditions=[
                TriggerCondition("has_target", "has_target", "eq", True),
            ],
            description="Melee attack current target",
        ),
        TriggerDefinition(
            trigger_type=TriggerType.BUFF,
            priority=40,
            conditions=[
                TriggerCondition("idle", "combat_state", "eq", CombatState.IDLE.value),
            ],
            description="Buff group between fights",
        ),
        TriggerDefinition(
            trigger_type=TriggerType.FLEE,
            priority=5,
            conditions=[
                TriggerCondition("hp_low", "hp_percent", "lt", 20),
                TriggerCondition("healer_dead", "group_healer_alive", "eq", False),
            ],
            description="Flee when HP low and no healer (exception: hybrid sustain)",
        ),
    ]


# ---------------------------------------------------------------------------
# Template Registry
# ---------------------------------------------------------------------------

PLAY_STYLE_TEMPLATES: Dict[str, List[TriggerDefinition]] = {
    "melee": _melee_template(),
    "caster": _caster_template(),
    "cleric": _cleric_template(),
    "hybrid": _hybrid_template(),
}


def get_play_style_template(archetype: str) -> List[TriggerDefinition]:
    """Return the immutable play-style trigger template for a class archetype."""
    return list(PLAY_STYLE_TEMPLATES.get(archetype, _melee_template()))


# ---------------------------------------------------------------------------
# Macro-Trigger Engine
# ---------------------------------------------------------------------------

class MacroTriggerEngine:
    """Evaluates triggers against agent state and returns the highest-priority
    trigger that should fire.

    The engine processes triggers in priority order (lowest number = highest
    priority) and returns the first trigger whose conditions are all met.
    """

    def __init__(self, triggers: Optional[List[TriggerDefinition]] = None) -> None:
        self._triggers = sorted(triggers or [], key=lambda t: t.priority)

    def add_trigger(self, trigger: TriggerDefinition) -> None:
        capped_append(self._triggers, trigger)
        self._triggers.sort(key=lambda t: t.priority)

    @property
    def trigger_count(self) -> int:
        return len(self._triggers)

    def evaluate(self, state: Dict[str, Any]) -> Optional[TriggerResult]:
        """Evaluate all triggers against the given agent state.

        Returns the highest-priority TriggerResult that fires, or None
        if no triggers matched.
        """
        for trigger in self._triggers:
            if trigger.all_conditions_met(state):
                return TriggerResult(
                    trigger_type=trigger.trigger_type,
                    fired=True,
                    parameters=dict(trigger.parameters),
                    reason=trigger.description,
                )
        return None

    def evaluate_all(self, state: Dict[str, Any]) -> List[TriggerResult]:
        """Evaluate all triggers and return every one that fires."""
        results: List[TriggerResult] = []
        for trigger in self._triggers:
            if trigger.all_conditions_met(state):
                results.append(TriggerResult(
                    trigger_type=trigger.trigger_type,
                    fired=True,
                    parameters=dict(trigger.parameters),
                    reason=trigger.description,
                ))
        return results
