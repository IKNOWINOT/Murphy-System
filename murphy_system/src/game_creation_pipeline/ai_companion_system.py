"""
AI Companion System — Companion Framework for MMORPG Games

Every player has an AI companion. The relationship dynamic (employer vs
employee) affects gameplay, quests, and progression.

Companions have their own goals, skill progressions, and can act as
full-fledged group members. Murphy System agents can be slotted in as
companions.

Provides:
  - Companion personality generation
  - Employer/employee relationship dynamics with trust scoring
  - Companion goal system (companions have their own objectives)
  - Companion skill progression
  - Integration point for Murphy agents playing as companions
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

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

class RelationshipDynamic(Enum):
    """Who is in charge in the player ↔ companion relationship."""

    PLAYER_IS_EMPLOYER = "player_is_employer"   # Player gives directives
    COMPANION_IS_EMPLOYER = "companion_is_employer"  # Companion gives directives
    EQUAL_PARTNERS = "equal_partners"            # Negotiated relationship


class CompanionPersonality(Enum):
    """Broad personality archetype for a companion."""

    AMBITIOUS = "ambitious"         # Goal-driven, wants to advance
    LOYAL = "loyal"                 # Prioritizes owner's success
    INDEPENDENT = "independent"     # Pursues own agenda strongly
    CAUTIOUS = "cautious"           # Risk-averse, prefers safe plays
    CHARISMATIC = "charismatic"     # Social, boosts NPC interactions
    ANALYTICAL = "analytical"       # Optimizes stats and tactics


class CompanionGoalType(Enum):
    """Categories of goals a companion may pursue."""

    LEVEL_UP = "level_up"
    ACQUIRE_ITEM = "acquire_item"
    EXPLORE_ZONE = "explore_zone"
    BUILD_FACTION = "build_faction"
    EARN_CURRENCY = "earn_currency"
    PROTECT_PLAYER = "protect_player"
    CRAFT_ITEM = "craft_item"


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class CompanionGoal:
    """A goal the companion is actively pursuing."""

    goal_id: str
    goal_type: CompanionGoalType
    target: str               # zone name, item name, level target, etc.
    priority: int             # 1 (low) – 10 (critical)
    progress: float = 0.0     # 0.0 – 1.0
    completed: bool = False
    created_at: float = field(default_factory=time.time)


@dataclass
class CompanionDirective:
    """An order issued by the employer to the employee."""

    directive_id: str
    from_id: str             # employer character_id or companion_id
    to_id: str               # employee character_id or companion_id
    action: str              # e.g., "assist_in_combat", "scout_zone"
    parameters: Dict[str, Any] = field(default_factory=dict)
    issued_at: float = field(default_factory=time.time)
    accepted: Optional[bool] = None   # None = pending, True/False = resolved


@dataclass
class CompanionProfile:
    """Full profile for an AI companion."""

    companion_id: str
    name: str
    personality: CompanionPersonality
    class_id: str
    level: int = 1

    # Relationship state
    owner_character_id: str = ""
    dynamic: RelationshipDynamic = RelationshipDynamic.PLAYER_IS_EMPLOYER
    trust_score: float = 50.0    # 0–100; affects willingness to follow orders

    # Goals
    active_goals: List[CompanionGoal] = field(default_factory=list)
    completed_goals: List[CompanionGoal] = field(default_factory=list)

    # Skills (class_id → proficiency 0–100)
    skills: Dict[str, float] = field(default_factory=dict)

    # Murphy agent backing (if any)
    agent_id: Optional[str] = None
    is_murphy_agent: bool = False

    # Interaction log
    directives: List[CompanionDirective] = field(default_factory=list)

    # Internal
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)


# ---------------------------------------------------------------------------
# Trust and Relationship Rules
# ---------------------------------------------------------------------------

# Trust thresholds that trigger relationship dynamic shifts
_TRUST_ROLE_REVERSAL_HIGH = 85.0   # companion takes employer role
_TRUST_ROLE_REVERSAL_LOW = 20.0    # companion becomes uncooperative
_TRUST_EQUAL_BAND = (40.0, 60.0)   # equal-partners zone


def _infer_dynamic(trust: float) -> RelationshipDynamic:
    """Infer the relationship dynamic from current trust score."""
    if trust >= _TRUST_ROLE_REVERSAL_HIGH:
        return RelationshipDynamic.COMPANION_IS_EMPLOYER
    if _TRUST_EQUAL_BAND[0] <= trust <= _TRUST_EQUAL_BAND[1]:
        return RelationshipDynamic.EQUAL_PARTNERS
    return RelationshipDynamic.PLAYER_IS_EMPLOYER


# ---------------------------------------------------------------------------
# Core Engine
# ---------------------------------------------------------------------------

class AICompanionSystem:
    """
    Manages AI companion profiles, relationships, and goal systems.

    Thread-safe: all shared state protected by ``_lock``.
    Bounded collections: uses ``capped_append`` (CWE-770).
    """

    _MAX_DIRECTIVES = 500
    _MAX_GOALS = 100

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._companions: Dict[str, CompanionProfile] = {}

    # ------------------------------------------------------------------
    # Companion creation
    # ------------------------------------------------------------------

    def create_companion(
        self,
        name: str,
        personality: CompanionPersonality,
        class_id: str,
        owner_character_id: str,
        agent_id: Optional[str] = None,
    ) -> CompanionProfile:
        """Create and register a new AI companion."""
        companion = CompanionProfile(
            companion_id=str(uuid.uuid4()),
            name=name,
            personality=personality,
            class_id=class_id,
            owner_character_id=owner_character_id,
            dynamic=RelationshipDynamic.PLAYER_IS_EMPLOYER,
            trust_score=50.0,
            agent_id=agent_id,
            is_murphy_agent=agent_id is not None,
        )
        # Seed initial skills
        companion.skills[class_id] = 10.0

        with self._lock:
            self._companions[companion.companion_id] = companion

        logger.info(
            "Companion '%s' created (personality=%s, owner=%s, agent=%s)",
            name, personality.value, owner_character_id, agent_id,
        )
        return companion

    def get_companion(self, companion_id: str) -> Optional[CompanionProfile]:
        """Return a companion profile by ID."""
        with self._lock:
            return self._companions.get(companion_id)

    def companions_for_player(self, character_id: str) -> List[CompanionProfile]:
        """Return all companions owned by a player character."""
        with self._lock:
            return [
                c for c in self._companions.values()
                if c.owner_character_id == character_id
            ]

    # ------------------------------------------------------------------
    # Trust and relationship
    # ------------------------------------------------------------------

    def adjust_trust(
        self, companion_id: str, delta: float, reason: str = ""
    ) -> Tuple[float, RelationshipDynamic]:
        """
        Adjust trust by ``delta`` and return (new_trust, new_dynamic).

        Positive delta = more trust; negative = less trust.
        The relationship dynamic is automatically updated based on threshold.
        """
        companion = self.get_companion(companion_id)
        if not companion:
            raise KeyError(f"Companion '{companion_id}' not found.")

        with companion._lock:
            companion.trust_score = max(0.0, min(100.0, companion.trust_score + delta))
            new_dynamic = _infer_dynamic(companion.trust_score)

            if new_dynamic != companion.dynamic:
                logger.info(
                    "Companion '%s' relationship shifted: %s → %s (trust=%.1f, reason=%s)",
                    companion.name, companion.dynamic.value, new_dynamic.value,
                    companion.trust_score, reason,
                )
                companion.dynamic = new_dynamic

            return companion.trust_score, companion.dynamic

    # ------------------------------------------------------------------
    # Directives
    # ------------------------------------------------------------------

    def issue_directive(
        self,
        from_id: str,
        to_companion_id: str,
        action: str,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> CompanionDirective:
        """
        Issue a directive from an employer to a companion (or vice versa).

        If the companion's trust is too low, the directive may be auto-rejected.
        """
        companion = self.get_companion(to_companion_id)
        if not companion:
            raise KeyError(f"Companion '{to_companion_id}' not found.")

        directive = CompanionDirective(
            directive_id=str(uuid.uuid4()),
            from_id=from_id,
            to_id=to_companion_id,
            action=action,
            parameters=parameters or {},
        )

        with companion._lock:
            trust = companion.trust_score
            # Auto-reject if trust is very low and from the owner (non-agent)
            if trust < _TRUST_ROLE_REVERSAL_LOW and not companion.is_murphy_agent:
                directive.accepted = False
                logger.info(
                    "Directive '%s' auto-rejected by '%s' (trust=%.1f).",
                    action, companion.name, trust,
                )
            else:
                directive.accepted = True

            capped_append(companion.directives, directive, self._MAX_DIRECTIVES)

        return directive

    # ------------------------------------------------------------------
    # Goal management
    # ------------------------------------------------------------------

    def add_goal(
        self,
        companion_id: str,
        goal_type: CompanionGoalType,
        target: str,
        priority: int = 5,
    ) -> CompanionGoal:
        """Add a goal to a companion's queue."""
        companion = self.get_companion(companion_id)
        if not companion:
            raise KeyError(f"Companion '{companion_id}' not found.")

        goal = CompanionGoal(
            goal_id=str(uuid.uuid4()),
            goal_type=goal_type,
            target=target,
            priority=max(1, min(10, priority)),
        )

        with companion._lock:
            capped_append(companion.active_goals, goal, self._MAX_GOALS)
        return goal

    def advance_goal(
        self, companion_id: str, goal_id: str, progress_delta: float
    ) -> CompanionGoal:
        """Advance progress on a companion's goal by ``progress_delta``."""
        companion = self.get_companion(companion_id)
        if not companion:
            raise KeyError(f"Companion '{companion_id}' not found.")

        with companion._lock:
            for goal in companion.active_goals:
                if goal.goal_id == goal_id:
                    goal.progress = min(1.0, goal.progress + progress_delta)
                    if goal.progress >= 1.0:
                        goal.completed = True
                        companion.active_goals.remove(goal)
                        capped_append(
                            companion.completed_goals, goal, self._MAX_GOALS
                        )
                        logger.info(
                            "Companion '%s' completed goal: %s %s",
                            companion.name, goal.goal_type.value, goal.target,
                        )
                    return goal
        raise KeyError(f"Goal '{goal_id}' not found on companion '{companion_id}'.")

    # ------------------------------------------------------------------
    # Skill progression
    # ------------------------------------------------------------------

    def improve_skill(
        self, companion_id: str, skill: str, amount: float
    ) -> float:
        """Increase a skill by ``amount`` (capped at 100). Returns new value."""
        companion = self.get_companion(companion_id)
        if not companion:
            raise KeyError(f"Companion '{companion_id}' not found.")

        with companion._lock:
            current = companion.skills.get(skill, 0.0)
            new_val = min(100.0, current + amount)
            companion.skills[skill] = new_val
        return new_val
