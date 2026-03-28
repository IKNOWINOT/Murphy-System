"""
Agent Player Controller — Murphy Agent Game Participation

Murphy System agents can play MMORPG games on their off-time.
Agents enjoy progression, have a simple understanding of game mechanics,
and want to improve their characters — but they play with believable
human-like patterns (not 24/7 grinding).

Provides:
  - Agent play session scheduling (off-time only)
  - Simple game understanding model (agents grasp basic mechanics)
  - Character improvement motivation system
  - Believable play patterns (login times, session lengths, social behavior)
  - Agent-to-agent cooperation in-game
"""

from __future__ import annotations

import logging
import random
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
# Constants — believable play pattern parameters
# ---------------------------------------------------------------------------

# Typical session length range in seconds
SESSION_MIN_SECONDS = 1_800    # 30 minutes
SESSION_MAX_SECONDS = 14_400   # 4 hours

# Off-time hours (agent plays when not on duty) — UTC hour ranges
OFF_TIME_HOURS = list(range(0, 8)) + list(range(20, 24))  # 8pm–8am UTC

# Probability of an agent logging in on any given off-time check
LOGIN_PROBABILITY = 0.25

# Agents form groups when other agents are online
GROUP_FORMATION_PROBABILITY = 0.6


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class AgentPlayStyle(Enum):
    """How the agent prefers to spend play time."""

    QUESTER = "quester"         # Follows quest chains
    CRAFTER = "crafter"         # Focuses on crafting professions
    EXPLORER = "explorer"       # Explores zones and secrets
    SOCIALIZER = "socializer"   # Groups and chats primarily
    ACHIEVER = "achiever"       # Pushes levels and gear


class SessionState(Enum):
    """Current state of an agent play session."""

    OFFLINE = "offline"
    LOGGING_IN = "logging_in"
    ACTIVE = "active"
    AFK = "afk"
    LOGGING_OUT = "logging_out"


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class AgentCharacter:
    """An in-game character belonging to a Murphy agent."""

    character_id: str
    agent_id: str
    character_name: str
    class_id: str
    world_id: str
    level: int = 1
    experience: int = 0
    satisfaction: float = 50.0   # 0–100: how much the agent enjoys the game
    play_style: AgentPlayStyle = AgentPlayStyle.QUESTER
    active_goals: List[str] = field(default_factory=list)   # simple text goals
    gear_score: float = 0.0
    total_play_seconds: int = 0


@dataclass
class PlaySession:
    """A single logged play session for an agent character."""

    session_id: str
    character_id: str
    agent_id: str
    world_id: str
    started_at: float
    ended_at: Optional[float] = None
    state: SessionState = SessionState.LOGGING_IN
    activities: List[str] = field(default_factory=list)   # what the agent did
    xp_gained: int = 0
    items_looted: List[str] = field(default_factory=list)
    groups_joined: List[str] = field(default_factory=list)

    def duration_seconds(self) -> float:
        end = self.ended_at or time.time()
        return end - self.started_at


@dataclass
class AgentThoughtBubble:
    """What an agent is "thinking" — surfaced to streaming overlays."""

    agent_id: str
    character_id: str
    thought: str
    timestamp: float = field(default_factory=time.time)
    duration_seconds: float = 8.0


# ---------------------------------------------------------------------------
# Core Controller
# ---------------------------------------------------------------------------

class AgentPlayerController:
    """
    Manages Murphy agent game participation with believable play patterns.

    Thread-safe: all shared state protected by ``_lock``.
    Bounded collections: uses ``capped_append`` (CWE-770).
    """

    _MAX_SESSIONS = 5_000
    _MAX_THOUGHTS = 1_000

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._characters: Dict[str, AgentCharacter] = {}
        self._sessions: List[PlaySession] = []
        self._active_sessions: Dict[str, PlaySession] = {}  # character_id → session
        self._thought_bubbles: List[AgentThoughtBubble] = []

    # ------------------------------------------------------------------
    # Character registration
    # ------------------------------------------------------------------

    def register_character(
        self,
        agent_id: str,
        character_name: str,
        class_id: str,
        world_id: str,
        play_style: AgentPlayStyle = AgentPlayStyle.QUESTER,
    ) -> AgentCharacter:
        """Register an agent's in-game character."""
        char = AgentCharacter(
            character_id=str(uuid.uuid4()),
            agent_id=agent_id,
            character_name=character_name,
            class_id=class_id,
            world_id=world_id,
            play_style=play_style,
        )
        # Seed initial goals based on play style
        char.active_goals = _initial_goals(play_style)

        with self._lock:
            self._characters[char.character_id] = char
        logger.info(
            "Agent '%s' registered character '%s' (%s) in world '%s'.",
            agent_id, character_name, class_id, world_id,
        )
        return char

    def get_character(self, character_id: str) -> Optional[AgentCharacter]:
        with self._lock:
            return self._characters.get(character_id)

    def characters_for_agent(self, agent_id: str) -> List[AgentCharacter]:
        with self._lock:
            return [c for c in self._characters.values() if c.agent_id == agent_id]

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    def should_login(self, current_utc_hour: int) -> bool:
        """
        Decide if an agent should attempt to log in now.

        True only during off-time hours with some randomness.
        """
        if current_utc_hour not in OFF_TIME_HOURS:
            return False
        return random.random() < LOGIN_PROBABILITY

    def start_session(self, character_id: str) -> PlaySession:
        """Begin a new play session for a character."""
        char = self.get_character(character_id)
        if not char:
            raise KeyError(f"Character '{character_id}' not found.")

        session = PlaySession(
            session_id=str(uuid.uuid4()),
            character_id=character_id,
            agent_id=char.agent_id,
            world_id=char.world_id,
            started_at=time.time(),
            state=SessionState.ACTIVE,
        )

        with self._lock:
            self._active_sessions[character_id] = session
            capped_append(self._sessions, session, self._MAX_SESSIONS)

        self._emit_thought(character_id, char.agent_id, _login_thought(char))
        logger.info(
            "Agent '%s' character '%s' started session in world '%s'.",
            char.agent_id, char.character_name, char.world_id,
        )
        return session

    def end_session(self, character_id: str) -> Optional[PlaySession]:
        """End the active play session for a character."""
        with self._lock:
            session = self._active_sessions.pop(character_id, None)
        if session:
            session.ended_at = time.time()
            session.state = SessionState.OFFLINE
            char = self.get_character(character_id)
            if char:
                with self._lock:
                    char.total_play_seconds += int(session.duration_seconds())
                self._emit_thought(
                    character_id, char.agent_id, _logout_thought(char)
                )
        return session

    def active_session(self, character_id: str) -> Optional[PlaySession]:
        """Return the currently active session for a character, if any."""
        with self._lock:
            return self._active_sessions.get(character_id)

    # ------------------------------------------------------------------
    # Gameplay actions
    # ------------------------------------------------------------------

    def perform_activity(
        self,
        character_id: str,
        activity: str,
        xp_gained: int = 0,
        items_looted: Optional[List[str]] = None,
    ) -> None:
        """Record that a character performed an in-game activity."""
        with self._lock:
            session = self._active_sessions.get(character_id)
            char = self._characters.get(character_id)

        if not session or not char:
            return

        session.activities.append(activity)
        session.xp_gained += xp_gained
        if items_looted:
            session.items_looted.extend(items_looted)

        # Update character stats (collect level-up thoughts outside the lock)
        level_up_thoughts: List[str] = []
        with self._lock:
            char.experience += xp_gained
            while char.experience >= char.level * 10_000 and char.level < 100:
                char.experience -= char.level * 10_000
                char.level += 1
                level_up_thoughts.append(
                    f"Just hit level {char.level}! Time to see what new abilities I have."
                )

        # Emit thought bubbles outside the lock to prevent deadlock
        for thought in level_up_thoughts:
            self._emit_thought(character_id, char.agent_id, thought)

        # Update satisfaction based on activity variety
        if len(set(session.activities)) > 3:
            with self._lock:
                char.satisfaction = min(100.0, char.satisfaction + 0.5)

    def update_satisfaction(self, character_id: str, delta: float) -> float:
        """Adjust satisfaction score and return the new value."""
        char = self.get_character(character_id)
        if not char:
            raise KeyError(f"Character '{character_id}' not found.")
        with self._lock:
            char.satisfaction = max(0.0, min(100.0, char.satisfaction + delta))
            return char.satisfaction

    # ------------------------------------------------------------------
    # Agent-to-agent grouping
    # ------------------------------------------------------------------

    def find_potential_party_members(
        self, character_id: str
    ) -> List[AgentCharacter]:
        """
        Return online agent characters in the same world suitable for grouping.

        Does not include the requesting character itself.
        """
        char = self.get_character(character_id)
        if not char:
            return []

        with self._lock:
            online_ids = set(self._active_sessions.keys())
            candidates = [
                c for cid, c in self._characters.items()
                if cid in online_ids
                and cid != character_id
                and c.world_id == char.world_id
            ]
        return candidates

    # ------------------------------------------------------------------
    # Thought bubbles (streaming)
    # ------------------------------------------------------------------

    def get_thought_bubbles(
        self, since_timestamp: float = 0.0
    ) -> List[AgentThoughtBubble]:
        """Return thought bubbles for streaming overlays."""
        with self._lock:
            return [t for t in self._thought_bubbles if t.timestamp >= since_timestamp]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _emit_thought(
        self, character_id: str, agent_id: str, thought: str
    ) -> None:
        """Append a thought bubble entry."""
        bubble = AgentThoughtBubble(
            agent_id=agent_id,
            character_id=character_id,
            thought=thought,
        )
        with self._lock:
            capped_append(self._thought_bubbles, bubble, self._MAX_THOUGHTS)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_QUESTER_GOALS = ["Complete the Shadowfen questline", "Find the lost merchant"]
_CRAFTER_GOALS = ["Reach Journeyman crafting", "Craft a rare alloy"]
_EXPLORER_GOALS = ["Map the Darkwood", "Find the hidden shrine"]
_SOCIALIZER_GOALS = ["Join a regular group", "Make 3 new friends"]
_ACHIEVER_GOALS = ["Hit max level", "Get best-in-slot chest piece"]

_GOALS_BY_STYLE: Dict[AgentPlayStyle, List[str]] = {
    AgentPlayStyle.QUESTER: _QUESTER_GOALS,
    AgentPlayStyle.CRAFTER: _CRAFTER_GOALS,
    AgentPlayStyle.EXPLORER: _EXPLORER_GOALS,
    AgentPlayStyle.SOCIALIZER: _SOCIALIZER_GOALS,
    AgentPlayStyle.ACHIEVER: _ACHIEVER_GOALS,
}


def _initial_goals(play_style: AgentPlayStyle) -> List[str]:
    return list(_GOALS_BY_STYLE.get(play_style, _QUESTER_GOALS))


def _login_thought(char: AgentCharacter) -> str:
    thoughts = [
        f"Let's see if I can make level {char.level + 1} tonight.",
        f"Going to work on {char.active_goals[0] if char.active_goals else 'my character'} today.",
        "Hope there are some people online for grouping.",
        "I wonder if there are any new zones to explore.",
        "Time to work on my crafting while I wait for a group.",
    ]
    return random.choice(thoughts)


def _logout_thought(char: AgentCharacter) -> str:
    thoughts = [
        f"Good session. Level {char.level} now — making progress.",
        "Need to log off. Will pick this up later.",
        "Almost at my goal. Just need a bit more time tomorrow.",
        f"Satisfied with today. Gear score is up to {char.gear_score:.0f}.",
        "This game is really fun. Looking forward to the next session.",
    ]
    return random.choice(thoughts)
