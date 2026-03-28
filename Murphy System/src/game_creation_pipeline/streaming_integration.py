"""
Streaming Integration — Built-in Streaming Infrastructure

Deep streaming integration for every MMORPG game produced by the pipeline.
Built on the existing ``streaming_overlay.py`` from the eq package.

Provides:
  - OBS overlay templates per game
  - Spectator mode with camera controls
  - Highlight detection and clip capture
  - Agent thought bubble overlays
  - Stream event triggers (boss kills, rare drops, PvP moments)
"""

from __future__ import annotations

import logging
import threading
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

# Import eq streaming layer if available
try:
    from src.eq.streaming_overlay import StreamingOverlayManager as _EQOverlayManager
    _HAS_EQ_OVERLAY = True
except ImportError:
    _HAS_EQ_OVERLAY = False

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class StreamEventType(Enum):
    """Categories of in-game events worth capturing for streams."""

    BOSS_KILL = "boss_kill"
    RARE_DROP = "rare_drop"
    LEVEL_UP = "level_up"
    PVP_KILL = "pvp_kill"
    SYNERGY_CAST = "synergy_cast"
    DIVINE_LUCK = "divine_luck"
    GUILD_ACHIEVEMENT = "guild_achievement"
    WORLD_FIRST = "world_first"
    AGENT_THOUGHT = "agent_thought"


class CameraMode(Enum):
    """Spectator camera perspective."""

    FOLLOW = "follow"               # Follow a specific character
    FREE_ROAM = "free_roam"         # Free camera movement
    CINEMATIC = "cinematic"         # Auto-cinematic during events
    RAID_OVERVIEW = "raid_overview" # Bird's eye view of raid


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class OverlayTemplate:
    """OBS overlay template for a specific game or scene."""

    template_id: str
    game_id: str
    name: str
    elements: List[str]   # overlay element names (health bars, minimap, etc.)
    obs_scene_name: str = ""
    active: bool = True


@dataclass
class StreamEvent:
    """A noteworthy in-game event surfaced to the streaming layer."""

    event_id: str
    event_type: StreamEventType
    description: str
    character_id: str
    world_id: str
    timestamp: float = field(default_factory=time.time)
    is_highlight: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ClipCapture:
    """Record of a highlight clip captured."""

    clip_id: str
    trigger_event_id: str
    character_id: str
    world_id: str
    duration_seconds: float
    start_timestamp: float
    end_timestamp: float
    label: str = ""


@dataclass
class SpectatorSession:
    """An active spectator watching the game."""

    session_id: str
    spectator_id: str
    target_character_id: str
    world_id: str
    camera_mode: CameraMode = CameraMode.FOLLOW
    started_at: float = field(default_factory=time.time)


@dataclass
class AgentThoughtOverlay:
    """Thought bubble content for a Murphy agent character."""

    overlay_id: str
    agent_id: str
    character_id: str
    thought_text: str
    timestamp: float = field(default_factory=time.time)
    duration_seconds: float = 8.0


# ---------------------------------------------------------------------------
# Core Integration
# ---------------------------------------------------------------------------

class StreamingIntegration:
    """
    Manages streaming infrastructure for MMORPG game instances.

    Thread-safe: all shared state protected by ``_lock``.
    Bounded collections: uses ``capped_append`` (CWE-770).
    """

    _MAX_EVENTS = 10_000
    _MAX_CLIPS = 1_000
    _MAX_THOUGHTS = 2_000
    _HIGHLIGHT_CLIP_DURATION = 30.0  # seconds before/after event

    # Events worth auto-clipping
    _HIGHLIGHT_EVENT_TYPES = {
        StreamEventType.BOSS_KILL,
        StreamEventType.RARE_DROP,
        StreamEventType.DIVINE_LUCK,
        StreamEventType.WORLD_FIRST,
        StreamEventType.SYNERGY_CAST,
    }

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._overlay_templates: Dict[str, OverlayTemplate] = {}
        self._events: List[StreamEvent] = []
        self._clips: List[ClipCapture] = []
        self._spectator_sessions: Dict[str, SpectatorSession] = {}
        self._agent_thoughts: List[AgentThoughtOverlay] = []

    # ------------------------------------------------------------------
    # Overlay management
    # ------------------------------------------------------------------

    def register_overlay_template(self, template: OverlayTemplate) -> None:
        """Register an OBS overlay template for a game."""
        with self._lock:
            self._overlay_templates[template.template_id] = template

    def get_overlay_template(self, game_id: str) -> Optional[OverlayTemplate]:
        """Return the active overlay template for a game."""
        with self._lock:
            for t in self._overlay_templates.values():
                if t.game_id == game_id and t.active:
                    return t
        return None

    def default_overlay_template(self, game_id: str) -> OverlayTemplate:
        """Create and register a sensible default overlay template."""
        template = OverlayTemplate(
            template_id=str(uuid.uuid4()),
            game_id=game_id,
            name=f"{game_id} Default Overlay",
            elements=[
                "health_bar", "mana_bar", "minimap", "group_frames",
                "experience_bar", "luck_meter", "synergy_indicator",
                "event_feed", "boss_health",
            ],
            obs_scene_name=f"{game_id}_gameplay",
        )
        self.register_overlay_template(template)
        return template

    # ------------------------------------------------------------------
    # Stream events
    # ------------------------------------------------------------------

    def emit_event(
        self,
        event_type: StreamEventType,
        description: str,
        character_id: str,
        world_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> StreamEvent:
        """Record a stream-worthy game event."""
        event = StreamEvent(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            description=description,
            character_id=character_id,
            world_id=world_id,
            is_highlight=event_type in self._HIGHLIGHT_EVENT_TYPES,
            metadata=metadata or {},
        )
        with self._lock:
            capped_append(self._events, event, self._MAX_EVENTS)

        if event.is_highlight:
            self._auto_clip(event)

        logger.info("Stream event: [%s] %s", event_type.value, description)
        return event

    def get_events(
        self,
        world_id: Optional[str] = None,
        highlights_only: bool = False,
        since: float = 0.0,
    ) -> List[StreamEvent]:
        """Return stream events, optionally filtered."""
        with self._lock:
            events = list(self._events)
        if world_id:
            events = [e for e in events if e.world_id == world_id]
        if highlights_only:
            events = [e for e in events if e.is_highlight]
        if since:
            events = [e for e in events if e.timestamp >= since]
        return events

    # ------------------------------------------------------------------
    # Spectator mode
    # ------------------------------------------------------------------

    def start_spectating(
        self,
        spectator_id: str,
        target_character_id: str,
        world_id: str,
        camera_mode: CameraMode = CameraMode.FOLLOW,
    ) -> SpectatorSession:
        """Start a spectator session."""
        session = SpectatorSession(
            session_id=str(uuid.uuid4()),
            spectator_id=spectator_id,
            target_character_id=target_character_id,
            world_id=world_id,
            camera_mode=camera_mode,
        )
        with self._lock:
            self._spectator_sessions[session.session_id] = session
        return session

    def stop_spectating(self, session_id: str) -> None:
        """End a spectator session."""
        with self._lock:
            self._spectator_sessions.pop(session_id, None)

    def switch_camera(self, session_id: str, mode: CameraMode) -> None:
        """Change the camera mode for a spectator session."""
        with self._lock:
            session = self._spectator_sessions.get(session_id)
            if session:
                session.camera_mode = mode

    # ------------------------------------------------------------------
    # Agent thought bubbles
    # ------------------------------------------------------------------

    def add_agent_thought(
        self,
        agent_id: str,
        character_id: str,
        thought_text: str,
        duration_seconds: float = 8.0,
    ) -> AgentThoughtOverlay:
        """Add an agent thought bubble for streaming overlay display."""
        overlay = AgentThoughtOverlay(
            overlay_id=str(uuid.uuid4()),
            agent_id=agent_id,
            character_id=character_id,
            thought_text=thought_text,
            duration_seconds=duration_seconds,
        )
        with self._lock:
            capped_append(self._agent_thoughts, overlay, self._MAX_THOUGHTS)
        return overlay

    def get_agent_thoughts(
        self, since_timestamp: float = 0.0
    ) -> List[AgentThoughtOverlay]:
        """Return recent agent thought bubbles for overlay rendering."""
        with self._lock:
            return [
                t for t in self._agent_thoughts
                if t.timestamp >= since_timestamp
            ]

    # ------------------------------------------------------------------
    # Clip capture
    # ------------------------------------------------------------------

    def get_clips(self, world_id: Optional[str] = None) -> List[ClipCapture]:
        """Return captured highlight clips."""
        with self._lock:
            clips = list(self._clips)
        if world_id:
            clips = [c for c in clips if c.world_id == world_id]
        return clips

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _auto_clip(self, event: StreamEvent) -> None:
        """Automatically record a clip for a highlight event."""
        now = event.timestamp
        clip = ClipCapture(
            clip_id=str(uuid.uuid4()),
            trigger_event_id=event.event_id,
            character_id=event.character_id,
            world_id=event.world_id,
            duration_seconds=self._HIGHLIGHT_CLIP_DURATION,
            start_timestamp=now - self._HIGHLIGHT_CLIP_DURATION / 2,
            end_timestamp=now + self._HIGHLIGHT_CLIP_DURATION / 2,
            label=f"{event.event_type.value}: {event.description[:60]}",
        )
        with self._lock:
            capped_append(self._clips, clip, self._MAX_CLIPS)
        logger.info("Auto-clip captured: %s", clip.label)
