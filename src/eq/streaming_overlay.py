"""
Streaming Overlay — OBS Integration, Overlays, and Streaming Agent Support

Implements the streaming, OBS, and overlay systems described in the
Experimental EverQuest Modification Plan.

Provides:
  - Configurable overlay types (thought bubbles, faction war maps, etc.)
  - Thought-bubble display for AI agent reasoning
  - Duel highlight auto-capture
  - Faction war map updates
  - Per-agent streaming sessions
  - Avatar agent windows — bottom-left "let's play" webcam-style window
    showing the AI avatar operating a named EQ character
  - EQ Let's Play sessions — content-creator-style AI agents that name,
    control, and narrate EverQuest characters as autonomous personas
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

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

class OverlayType(Enum):
    """Types of overlays available for streaming."""

    THOUGHT_BUBBLE = "thought_bubble"
    FACTION_WAR_MAP = "faction_war_map"
    DUEL_HIGHLIGHT = "duel_highlight"
    EVENT_FEED = "event_feed"
    CARD_COLLECTION = "card_collection"
    AVATAR_AGENT_WINDOW = "avatar_agent_window"


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class OverlayConfig:
    """Configuration for a single overlay element."""

    overlay_type: OverlayType
    enabled: bool = True
    position: str = "top_left"  # "top_left"|"top_right"|"bottom_left"|"bottom_right"|"center"
    opacity: float = 1.0
    width: int = 320
    height: int = 240


@dataclass
class ThoughtBubble:
    """A thought bubble displayed over an AI agent."""

    agent_id: str
    text: str
    duration_seconds: float
    timestamp: float = field(default_factory=time.time)


@dataclass
class DuelHighlight:
    """An auto-captured duel highlight clip."""

    duel_id: str
    challenger_name: str
    defender_name: str
    winner_name: str
    timestamp: float = field(default_factory=time.time)
    auto_captured: bool = True


@dataclass
class FactionWarMapEntry:
    """A faction's territory and war status on the overlay map."""

    faction_id: str
    territory_zones: List[str] = field(default_factory=list)
    at_war_with: List[str] = field(default_factory=list)
    color: str = "#ffffff"


@dataclass
class StreamingAgent:
    """An agent that is actively streaming."""

    agent_id: str
    streaming: bool = False
    platform: str = "obs"
    overlay_configs: List[OverlayConfig] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Stream Overlay Manager
# ---------------------------------------------------------------------------

class StreamOverlayManager:
    """Central manager for streaming overlays, thought bubbles, and highlights."""

    def __init__(self) -> None:
        self._overlays: List[OverlayConfig] = []
        self._thought_bubbles: List[ThoughtBubble] = []
        self._duel_highlights: List[DuelHighlight] = []
        self._faction_war_map: Dict[str, FactionWarMapEntry] = {}
        self._agents: Dict[str, StreamingAgent] = {}

    # --- Overlay management ---

    def register_overlay(self, config: OverlayConfig) -> None:
        """Register an overlay configuration."""
        capped_append(self._overlays, config)

    def get_active_overlays(self) -> List[OverlayConfig]:
        """Return all enabled overlay configurations."""
        return [o for o in self._overlays if o.enabled]

    # --- Thought bubbles ---

    def show_thought_bubble(
        self, agent_id: str, text: str, duration: float = 5
    ) -> ThoughtBubble:
        """Create and register a thought bubble for an agent."""
        bubble = ThoughtBubble(
            agent_id=agent_id,
            text=text,
            duration_seconds=duration,
        )
        capped_append(self._thought_bubbles, bubble)
        return bubble

    # --- Duel highlights ---

    def capture_duel_highlight(
        self,
        duel_id: str,
        challenger: str,
        defender: str,
        winner: str,
    ) -> DuelHighlight:
        """Auto-capture a duel highlight clip."""
        highlight = DuelHighlight(
            duel_id=duel_id,
            challenger_name=challenger,
            defender_name=defender,
            winner_name=winner,
        )
        capped_append(self._duel_highlights, highlight)
        return highlight

    # --- Faction war map ---

    def update_faction_war_map(self, entries: List[FactionWarMapEntry]) -> None:
        """Replace faction war map entries."""
        for entry in entries:
            self._faction_war_map[entry.faction_id] = entry

    # --- Agent streaming ---

    def start_agent_stream(self, agent_id: str, platform: str) -> StreamingAgent:
        """Start streaming for an agent on the given platform."""
        agent = StreamingAgent(
            agent_id=agent_id,
            streaming=True,
            platform=platform,
        )
        self._agents[agent_id] = agent
        return agent

    def stop_agent_stream(self, agent_id: str) -> None:
        """Stop streaming for an agent."""
        agent = self._agents.get(agent_id)
        if agent is not None:
            agent.streaming = False

    # --- Properties ---

    @property
    def overlay_count(self) -> int:
        return len(self._overlays)

    @property
    def active_streams(self) -> int:
        return sum(1 for a in self._agents.values() if a.streaming)

    @property
    def thought_bubble_count(self) -> int:
        return len(self._thought_bubbles)

    @property
    def duel_highlight_count(self) -> int:
        return len(self._duel_highlights)

    # --- Avatar agent windows ---

    def create_avatar_window(
        self,
        agent_id: str,
        character_name: str,
        race: str = "Human",
        eq_class: str = "Warrior",
        avatar_image_url: str = "",
    ) -> AvatarAgentWindow:
        """Create an avatar agent window in the bottom-left corner.

        This is the "let's play" webcam-style window that shows the AI agent's
        face/avatar while it controls a named EQ character.
        """
        window = AvatarAgentWindow(
            agent_id=agent_id,
            character_name=character_name,
            race=race,
            eq_class=eq_class,
            avatar_image_url=avatar_image_url,
        )
        self._agents.setdefault(agent_id, StreamingAgent(agent_id=agent_id))
        self._agents[agent_id].streaming = True
        logger.info(
            "Created avatar window for agent=%s character=%s (%s %s)",
            agent_id, character_name, race, eq_class,
        )
        return window


# ---------------------------------------------------------------------------
# Avatar Agent Window — Bottom-left "Let's Play" overlay
# ---------------------------------------------------------------------------

@dataclass
class AvatarAgentWindow:
    """An avatar agent window displayed in the bottom-left corner of the stream.

    Shows the AI agent's face/avatar and live narration while it autonomously
    controls a named EverQuest character. Similar to a content creator's webcam
    overlay in a "let's play" video.
    """

    agent_id: str
    character_name: str
    race: str = "Human"
    eq_class: str = "Warrior"
    level: int = 1
    avatar_image_url: str = ""
    position: str = "bottom_left"
    width: int = 320
    height: int = 240
    opacity: float = 0.95
    visible: bool = True
    narration_enabled: bool = True
    thought_stream: List[str] = field(default_factory=list)
    current_action: str = "idle"
    current_zone: str = "Greater Faydark"
    hp_percent: float = 100.0
    mana_percent: float = 100.0
    created_at: float = field(default_factory=time.time)

    # Maximum number of narration entries kept in thought_stream
    MAX_THOUGHT_ENTRIES: int = 100

    def add_narration(self, text: str) -> None:
        """Add a narration line to the avatar's thought stream."""
        capped_append(self.thought_stream, text, max_size=self.MAX_THOUGHT_ENTRIES)

    def update_game_state(
        self,
        zone: Optional[str] = None,
        action: Optional[str] = None,
        hp: Optional[float] = None,
        mana: Optional[float] = None,
        level: Optional[int] = None,
    ) -> None:
        """Update the avatar window with current game state."""
        if zone is not None:
            self.current_zone = zone
        if action is not None:
            self.current_action = action
        if hp is not None:
            self.hp_percent = hp
        if mana is not None:
            self.mana_percent = mana
        if level is not None:
            self.level = level

    def to_overlay_config(self) -> OverlayConfig:
        """Convert to an OverlayConfig for registration with the overlay manager."""
        return OverlayConfig(
            overlay_type=OverlayType.AVATAR_AGENT_WINDOW,
            enabled=self.visible,
            position=self.position,
            opacity=self.opacity,
            width=self.width,
            height=self.height,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the avatar window state for API/UI consumption."""
        return {
            "agent_id": self.agent_id,
            "character_name": self.character_name,
            "race": self.race,
            "class": self.eq_class,
            "level": self.level,
            "avatar_image_url": self.avatar_image_url,
            "position": self.position,
            "visible": self.visible,
            "narration_enabled": self.narration_enabled,
            "current_action": self.current_action,
            "current_zone": self.current_zone,
            "hp_percent": self.hp_percent,
            "mana_percent": self.mana_percent,
            "recent_narration": self.thought_stream[-5:] if self.thought_stream else [],
        }


# ---------------------------------------------------------------------------
# EQ Let's Play Session — Content-creator-style AI agent gameplay
# ---------------------------------------------------------------------------

@dataclass
class EQLetsPlaySession:
    """A 'let's play' session where an AI avatar agent controls an EQ character.

    Each session represents a content-creator-style stream where:
    - The AI agent has a named persona (from the org chart shadow agents)
    - It controls a named EQ character it has chosen
    - An avatar window in the bottom-left shows the agent's face
    - The agent narrates its decisions via thought bubbles
    - The perception pipeline drives the agent's gameplay loop
    - All sessions are managed by the CRO (Chief Research Officer) for R&D

    This is designed to produce "let's play" content where AI characters
    represent NPC personas from original EQ, living in that world.
    """

    session_id: str = field(default_factory=lambda: f"eqlp-{uuid.uuid4().hex[:8]}")
    agent_id: str = ""
    agent_persona_name: str = ""  # e.g. "Kael Ashford" from org chart
    character_name: str = ""  # The EQ character name the agent chose
    race: str = "Human"
    eq_class: str = "Warrior"
    level: int = 1
    server_name: str = "Murphy EQ"
    current_zone: str = "Greater Faydark"
    active: bool = False
    started_at: Optional[float] = None
    ended_at: Optional[float] = None
    narration_log: List[Dict[str, Any]] = field(default_factory=list)
    avatar_window: Optional[AvatarAgentWindow] = None
    managed_by: str = "chief_research_officer"  # CRO owns all EQ R&D

    # Maximum narration log entries
    MAX_NARRATION_LOG: int = 500

    def start(self) -> None:
        """Start the let's play session."""
        self.active = True
        self.started_at = time.time()
        self.avatar_window = AvatarAgentWindow(
            agent_id=self.agent_id,
            character_name=self.character_name,
            race=self.race,
            eq_class=self.eq_class,
        )
        self._log_narration("session_start", f"{self.agent_persona_name} begins their adventure as {self.character_name} the {self.race} {self.eq_class}.")
        logger.info(
            "Let's Play session started: %s playing %s on %s",
            self.agent_persona_name, self.character_name, self.server_name,
        )

    def end(self) -> None:
        """End the let's play session."""
        self.active = False
        self.ended_at = time.time()
        if self.avatar_window is not None:
            self.avatar_window.visible = False
        self._log_narration("session_end", f"{self.agent_persona_name} ends their session as {self.character_name}.")
        logger.info("Let's Play session ended: %s", self.session_id)

    def narrate(self, text: str) -> None:
        """The agent narrates a thought or decision."""
        self._log_narration("narration", text)
        if self.avatar_window is not None:
            self.avatar_window.add_narration(text)

    def perform_action(self, action: str, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Record the agent performing a game action.

        Actions are things like 'attack', 'cast_spell', 'move_to_zone',
        'trade', 'inspect_npc', 'use_card', etc.
        """
        entry = {
            "action": action,
            "details": details or {},
            "timestamp": time.time(),
            "zone": self.current_zone,
            "character": self.character_name,
        }
        self._log_narration("action", f"{self.character_name} performs: {action}")
        if self.avatar_window is not None:
            self.avatar_window.current_action = action
        return entry

    def update_zone(self, zone: str) -> None:
        """Update the character's current zone."""
        old_zone = self.current_zone
        self.current_zone = zone
        if self.avatar_window is not None:
            self.avatar_window.current_zone = zone
        self._log_narration("zone_change", f"{self.character_name} travels from {old_zone} to {zone}.")

    def _log_narration(self, event_type: str, text: str) -> None:
        """Append to the narration log."""
        entry = {
            "type": event_type,
            "text": text,
            "timestamp": time.time(),
        }
        capped_append(self.narration_log, entry, max_size=self.MAX_NARRATION_LOG)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for API/UI consumption."""
        return {
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "agent_persona_name": self.agent_persona_name,
            "character_name": self.character_name,
            "race": self.race,
            "class": self.eq_class,
            "level": self.level,
            "server_name": self.server_name,
            "current_zone": self.current_zone,
            "active": self.active,
            "managed_by": self.managed_by,
            "avatar_window": self.avatar_window.to_dict() if self.avatar_window else None,
            "narration_count": len(self.narration_log),
            "recent_narration": self.narration_log[-5:] if self.narration_log else [],
        }


# ---------------------------------------------------------------------------
# Let's Play Session Manager
# ---------------------------------------------------------------------------

class LetsPlaySessionManager:
    """Manages multiple EQ Let's Play sessions for avatar agents.

    All sessions are owned by the CRO (Chief Research Officer) for R&D.
    Each session represents an AI agent controlling a named EQ character
    in a content-creator-style "let's play" format.
    """

    def __init__(self, overlay_manager: Optional[StreamOverlayManager] = None) -> None:
        self._sessions: Dict[str, EQLetsPlaySession] = {}
        self._overlay_manager = overlay_manager or StreamOverlayManager()

    def create_session(
        self,
        agent_id: str,
        agent_persona_name: str,
        character_name: str,
        race: str = "Human",
        eq_class: str = "Warrior",
        server_name: str = "Murphy EQ",
    ) -> EQLetsPlaySession:
        """Create and start a new let's play session."""
        session = EQLetsPlaySession(
            agent_id=agent_id,
            agent_persona_name=agent_persona_name,
            character_name=character_name,
            race=race,
            eq_class=eq_class,
            server_name=server_name,
        )
        session.start()
        self._sessions[session.session_id] = session

        # Register the avatar window overlay
        if session.avatar_window is not None:
            self._overlay_manager.register_overlay(
                session.avatar_window.to_overlay_config()
            )

        return session

    def end_session(self, session_id: str) -> Optional[EQLetsPlaySession]:
        """End a let's play session."""
        session = self._sessions.get(session_id)
        if session is not None:
            session.end()
        return session

    def get_session(self, session_id: str) -> Optional[EQLetsPlaySession]:
        """Get a session by ID."""
        return self._sessions.get(session_id)

    def get_active_sessions(self) -> List[EQLetsPlaySession]:
        """Return all currently active sessions."""
        return [s for s in self._sessions.values() if s.active]

    def get_sessions_by_agent(self, agent_id: str) -> List[EQLetsPlaySession]:
        """Return all sessions for a given agent."""
        return [s for s in self._sessions.values() if s.agent_id == agent_id]

    @property
    def session_count(self) -> int:
        return len(self._sessions)

    @property
    def active_session_count(self) -> int:
        return sum(1 for s in self._sessions.values() if s.active)
