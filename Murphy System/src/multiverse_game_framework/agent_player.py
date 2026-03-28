"""
Murphy Agent Game Player System for the Multiverse Game Framework.

Design Label: GAME-007 — Murphy Agent Game Player System
Owner: Backend Team
Dependencies:
  - EventBackbone
  - PersistenceManager
  - src/agent_persona_library/
  - universal_character.UniversalCharacter
  - world_registry.WorldRegistry

Murphy System agents play the games on their off time. They have simple
understanding of the game and want to improve their characters. Agents form
parties with other agents, seek out synergy combinations, and actively
recruit human players.

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

_MAX_GOALS = 20
_MAX_SESSION_LOG = 5_000

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class PlayStyle(str, Enum):
    """Agent play style preference."""
    CONSERVATIVE = "conservative"
    AGGRESSIVE = "aggressive"
    SOCIAL = "social"
    EXPLORER = "explorer"


class GoalType(str, Enum):
    """Type of in-game goal the agent is pursuing."""
    LEVEL_UP = "level_up"
    COMPLETE_QUEST = "complete_quest"
    ACQUIRE_ITEM = "acquire_item"
    EXPLORE_ZONE = "explore_zone"
    FORM_PARTY = "form_party"
    DISCOVER_SYNERGY = "discover_synergy"
    RECRUIT_PLAYER = "recruit_player"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class AgentGoal:
    """A discrete objective the agent is actively pursuing.

    Args:
        goal_id: Unique UUID.
        goal_type: Category of the goal.
        description: Human-readable objective.
        target_world_id: World the goal is set in (if world-specific).
        priority: 1 (highest) – 10 (lowest).
        completed: Whether this goal has been achieved.
    """
    goal_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    goal_type: GoalType = GoalType.LEVEL_UP
    description: str = ""
    target_world_id: Optional[str] = None
    priority: int = 5
    completed: bool = False


@dataclass
class PlaySession:
    """A scheduled agent play session.

    Args:
        session_id: Unique UUID.
        agent_id: The playing agent.
        character_id: Character being played.
        world_id: World where play occurs.
        duration_minutes: Intended session length.
        start_time: When the session is scheduled to start.
        active_goals: Goals pursued during this session.
        streaming: Whether the agent is streaming this session.
    """
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str = ""
    character_id: str = ""
    world_id: str = ""
    duration_minutes: int = 60
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    active_goals: List[AgentGoal] = field(default_factory=list)
    streaming: bool = False


@dataclass
class PlaySessionResult:
    """Outcome of a simulated play session.

    Args:
        session_id: The completed session.
        xp_earned: Total XP earned.
        goals_completed: Goals that were achieved.
        goals_failed: Goals not achieved.
        synergies_triggered: Synergy combos that fired.
        recruits_sent: Number of player recruitment messages sent.
        satisfaction_delta: Change to the agent's satisfaction score.
        highlight_events: Notable moments suitable for streaming highlights.
    """
    session_id: str
    xp_earned: int
    goals_completed: List[str] = field(default_factory=list)
    goals_failed: List[str] = field(default_factory=list)
    synergies_triggered: int = 0
    recruits_sent: int = 0
    satisfaction_delta: float = 0.0
    highlight_events: List[str] = field(default_factory=list)
    duration_minutes: int = 60
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class AgentPlayerProfile:
    """Persistent profile for an agent that plays the game.

    Args:
        agent_id: Links to src/agent_persona_library/.
        character_id: Links to UniversalCharacter.
        play_schedule: Cron-style or description of when the agent plays.
        play_style: Preferred play approach.
        goals: Current objectives.
        satisfaction_score: 0.0–1.0 enjoyment metric.
        preferred_world_ids: Worlds the agent gravitates towards.
        preferred_party_members: Other agent_ids the agent likes grouping with.
    """
    agent_id: str = ""
    character_id: str = ""
    play_schedule: str = "off_duty"
    play_style: PlayStyle = PlayStyle.SOCIAL
    goals: List[AgentGoal] = field(default_factory=list)
    satisfaction_score: float = 0.5
    preferred_world_ids: List[str] = field(default_factory=list)
    preferred_party_members: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# AgentPlayerEngine
# ---------------------------------------------------------------------------


class AgentPlayerEngine:
    """Manages agent play sessions, goal generation, and simulated gameplay.

    Agents form parties with other agents, seek out synergy combinations,
    and actively recruit human players. They also stream their sessions via
    integration hooks in streaming_integration.py.
    """

    def __init__(
        self,
        backbone: Optional[Any] = None,
        persistence: Optional[Any] = None,
    ) -> None:
        self._backbone = backbone
        self._persistence = persistence
        self._lock = threading.Lock()
        self._profiles: Dict[str, AgentPlayerProfile] = {}
        self._sessions: Dict[str, PlaySession] = {}
        self._session_log: List[PlaySessionResult] = []

    # ------------------------------------------------------------------
    # Profile management
    # ------------------------------------------------------------------

    def register_agent_profile(self, profile: AgentPlayerProfile) -> None:
        """Register an agent player profile.

        Args:
            profile: The AgentPlayerProfile to register.
        """
        with self._lock:
            self._profiles[profile.agent_id] = profile

    def get_agent_profile(self, agent_id: str) -> Optional[AgentPlayerProfile]:
        """Return the profile for the given agent_id, or None."""
        return self._profiles.get(agent_id)

    # ------------------------------------------------------------------
    # Session scheduling
    # ------------------------------------------------------------------

    def schedule_play_session(
        self,
        agent_id: str,
        duration_minutes: int,
        world_id: str = "",
        streaming: bool = False,
    ) -> PlaySession:
        """Schedule a play session for an agent.

        Args:
            agent_id: The agent to schedule.
            duration_minutes: Intended session duration.
            world_id: World to play in (empty = pick preferred or random).
            streaming: Whether to stream the session.

        Returns:
            The created PlaySession.
        """
        profile = self._profiles.get(agent_id)
        character_id = profile.character_id if profile else ""

        if not world_id and profile and profile.preferred_world_ids:
            world_id = profile.preferred_world_ids[0]

        session = PlaySession(
            agent_id=agent_id,
            character_id=character_id,
            world_id=world_id,
            duration_minutes=max(1, duration_minutes),
            streaming=streaming,
        )

        if profile:
            goals = self.generate_agent_goals(profile)
            session.active_goals = goals[:3]  # Focus on top 3 goals per session

        with self._lock:
            self._sessions[session.session_id] = session

        self._publish_event("agent_session_scheduled", {
            "session_id": session.session_id,
            "agent_id": agent_id,
            "world_id": world_id,
            "duration_minutes": duration_minutes,
        })
        return session

    # ------------------------------------------------------------------
    # Goal generation
    # ------------------------------------------------------------------

    def generate_agent_goals(
        self,
        agent_profile: AgentPlayerProfile,
    ) -> List[AgentGoal]:
        """Generate contextual goals based on the agent's profile and play style.

        Goals are sorted by priority. Style influences which goals are generated:
        - SOCIAL: prioritise party formation and player recruitment
        - EXPLORER: prioritise zone exploration
        - AGGRESSIVE: prioritise levelling and item acquisition
        - CONSERVATIVE: prioritise quest completion and synergy discovery

        Args:
            agent_profile: The profile to generate goals for.

        Returns:
            List of AgentGoal sorted by priority ascending (1 = highest).
        """
        goals: List[AgentGoal] = []
        style = agent_profile.play_style

        # Everyone wants to level up
        goals.append(AgentGoal(
            goal_type=GoalType.LEVEL_UP,
            description="Gain experience and level up the character.",
            priority=2 if style == PlayStyle.AGGRESSIVE else 3,
        ))

        if style in (PlayStyle.SOCIAL, PlayStyle.EXPLORER):
            goals.append(AgentGoal(
                goal_type=GoalType.FORM_PARTY,
                description="Find and join a party of complementary classes.",
                priority=1,
            ))

        if style == PlayStyle.EXPLORER:
            goals.append(AgentGoal(
                goal_type=GoalType.EXPLORE_ZONE,
                description="Discover a new zone or hidden area.",
                priority=2,
            ))

        if style in (PlayStyle.SOCIAL, PlayStyle.CONSERVATIVE):
            goals.append(AgentGoal(
                goal_type=GoalType.RECRUIT_PLAYER,
                description="Recruit a human player to join the world.",
                priority=3,
            ))

        if style in (PlayStyle.CONSERVATIVE, PlayStyle.AGGRESSIVE):
            goals.append(AgentGoal(
                goal_type=GoalType.COMPLETE_QUEST,
                description="Complete an available quest chain.",
                priority=2,
            ))

        goals.append(AgentGoal(
            goal_type=GoalType.DISCOVER_SYNERGY,
            description="Experiment with spell combinations to find a new synergy.",
            priority=4,
        ))

        # Carry over incomplete goals from the profile
        for existing in agent_profile.goals:
            if not existing.completed:
                goals.append(existing)

        # Deduplicate by goal_type and sort
        seen_types: set = set()
        unique_goals: List[AgentGoal] = []
        for g in sorted(goals, key=lambda g: g.priority):
            if g.goal_type not in seen_types:
                seen_types.add(g.goal_type)
                unique_goals.append(g)

        with self._lock:
            agent_profile.goals = unique_goals[:_MAX_GOALS]

        return unique_goals

    # ------------------------------------------------------------------
    # Session execution (simulated)
    # ------------------------------------------------------------------

    def execute_play_session(self, session: PlaySession) -> PlaySessionResult:
        """Simulate a play session and return the outcome.

        This is the logic layer; actual game rendering is handled by
        downstream game engines. Simulates XP gain, goal progression,
        synergy attempts, and recruitment activity.

        Args:
            session: The PlaySession to execute.

        Returns:
            PlaySessionResult with XP, goal outcomes, and highlights.
        """
        profile = self._profiles.get(session.agent_id)
        play_style = profile.play_style if profile else PlayStyle.CONSERVATIVE

        # Base XP scales with session duration and play style
        style_xp_multipliers = {
            PlayStyle.AGGRESSIVE: 1.4,
            PlayStyle.CONSERVATIVE: 1.0,
            PlayStyle.SOCIAL: 1.2,  # Group bonus
            PlayStyle.EXPLORER: 1.1,
        }
        base_xp = session.duration_minutes * 50
        xp_earned = int(base_xp * style_xp_multipliers.get(play_style, 1.0))

        goals_completed: List[str] = []
        goals_failed: List[str] = []
        highlights: List[str] = []

        for goal in session.active_goals:
            # Simple probabilistic completion
            success_chance = 0.7 if play_style == PlayStyle.CONSERVATIVE else 0.6
            if random.random() < success_chance:
                goal.completed = True
                goals_completed.append(goal.goal_id)
                if goal.goal_type == GoalType.DISCOVER_SYNERGY:
                    highlights.append("Discovered a new spell synergy!")
                elif goal.goal_type == GoalType.EXPLORE_ZONE:
                    highlights.append("Found a hidden area!")
            else:
                goals_failed.append(goal.goal_id)

        synergies = random.randint(0, 3) if play_style == PlayStyle.SOCIAL else random.randint(0, 1)
        recruits = random.randint(1, 3) if play_style == PlayStyle.SOCIAL else 0

        if session.streaming:
            highlights.append("Live stream session with viewer interactions.")

        result = PlaySessionResult(
            session_id=session.session_id,
            xp_earned=xp_earned,
            goals_completed=goals_completed,
            goals_failed=goals_failed,
            synergies_triggered=synergies,
            recruits_sent=recruits,
            highlight_events=highlights,
            duration_minutes=session.duration_minutes,
        )

        satisfaction = self.evaluate_satisfaction(profile, result) if profile else 0.5
        result.satisfaction_delta = satisfaction - (profile.satisfaction_score if profile else 0.5)

        if profile:
            with self._lock:
                profile.satisfaction_score = satisfaction
                # Clear completed goals
                profile.goals = [g for g in profile.goals if not g.completed]

        with self._lock:
            capped_append(self._session_log, result, _MAX_SESSION_LOG)

        self._publish_event("agent_session_completed", {
            "session_id": session.session_id,
            "agent_id": session.agent_id,
            "xp_earned": xp_earned,
            "goals_completed": len(goals_completed),
        })
        return result

    # ------------------------------------------------------------------
    # Satisfaction
    # ------------------------------------------------------------------

    def evaluate_satisfaction(
        self,
        agent_profile: Optional[AgentPlayerProfile],
        session_result: PlaySessionResult,
    ) -> float:
        """Calculate how satisfied the agent is with the session.

        Satisfaction is influenced by XP gain, goal completion rate, and
        synergies triggered.

        Args:
            agent_profile: The agent's profile (may be None).
            session_result: The result of the most recent session.

        Returns:
            New satisfaction score 0.0–1.0.
        """
        base = agent_profile.satisfaction_score if agent_profile else 0.5

        # Goal completion ratio
        total_goals = len(session_result.goals_completed) + len(session_result.goals_failed)
        completion_rate = (
            len(session_result.goals_completed) / total_goals if total_goals > 0 else 0.5
        )

        # XP contribution (normalised: 3000 XP/hr = fully satisfied)
        expected_xp_per_hour = 3_000
        duration_hours = max(1, session_result.duration_minutes) / 60.0
        actual_xph = session_result.xp_earned / duration_hours
        xp_satisfaction = min(1.0, actual_xph / expected_xp_per_hour)

        # Synergy bonus
        synergy_bonus = min(0.1, session_result.synergies_triggered * 0.02)

        new_score = (
            base * 0.3
            + completion_rate * 0.35
            + xp_satisfaction * 0.3
            + synergy_bonus
        )
        return round(max(0.0, min(1.0, new_score)), 4)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _publish_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        if _BACKBONE_AVAILABLE and self._backbone is not None:
            try:
                self._backbone.publish(event_type, payload)
            except Exception:  # pragma: no cover
                logger.debug("EventBackbone publish failed silently", exc_info=True)
