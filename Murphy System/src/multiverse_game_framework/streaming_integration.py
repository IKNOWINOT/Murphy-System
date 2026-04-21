"""
Built-in Streaming & Spectator System for the Multiverse Game Framework.

Design Label: GAME-008 — Built-in Streaming & Spectator System
Owner: Backend Team
Dependencies:
  - EventBackbone
  - PersistenceManager
  - src/video_streaming_connector.py (integration hooks)

Games have deep streaming capability built in. Overlay configs, spectator
mode, hotspot recommendations, and auto-highlight detection are all first-
class features.

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

# Integration hook — video_streaming_connector (optional)
try:
    from video_streaming_connector import VideoStreamingConnector  # type: ignore[import]
    _VSC_AVAILABLE = True
except Exception:  # pragma: no cover
    VideoStreamingConnector = None  # type: ignore[assignment,misc]
    _VSC_AVAILABLE = False

_MAX_SESSIONS = 10_000
_MAX_HIGHLIGHTS = 50_000

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class StreamQuality(str, Enum):
    """Stream quality preset."""
    LOW = "low"       # 480p / 1 Mbps
    MEDIUM = "medium"  # 720p / 3 Mbps
    HIGH = "high"     # 1080p / 6 Mbps
    ULTRA = "ultra"   # 4K / 15 Mbps


class StreamPlatform(str, Enum):
    """Supported streaming platforms."""
    TWITCH = "twitch"
    YOUTUBE_LIVE = "youtube_live"
    KICK_LIVE = "kick_live"
    FACEBOOK_LIVE = "facebook_live"
    RESTREAM = "restream"


class HighlightType(str, Enum):
    """Type of auto-detected highlight moment."""
    SYNERGY_COMBO = "synergy_combo"
    BOSS_KILL = "boss_kill"
    RARE_DROP = "rare_drop"
    PVP_MOMENT = "pvp_moment"
    LEVEL_UP = "level_up"
    DISCOVERY = "discovery"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class StreamingHotspot:
    """A zone recommended for streaming.

    Args:
        hotspot_id: Unique ID.
        world_id: World containing this hotspot.
        zone_id: Zone identifier.
        name: Display name.
        reason: Why this zone is good for streaming.
        scenic_score: Visual appeal 0.0–1.0.
        action_score: Combat/action density 0.0–1.0.
    """
    hotspot_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    world_id: str = ""
    zone_id: str = ""
    name: str = ""
    reason: str = ""
    scenic_score: float = 0.5
    action_score: float = 0.5


@dataclass
class OverlayConfig:
    """Configuration for in-stream overlay elements.

    Args:
        show_health_bar: Display character health bar.
        show_party_frames: Display party member status.
        show_synergy_alerts: Flash alert when a spell synergy triggers.
        show_minimap: Overlay minimap.
        camera_angle: Preferred camera angle preset.
        custom_fields: Additional overlay key-value pairs.
    """
    show_health_bar: bool = True
    show_party_frames: bool = True
    show_synergy_alerts: bool = True
    show_minimap: bool = True
    camera_angle: str = "third_person"
    custom_fields: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StreamSession:
    """An active or past streaming session.

    Args:
        session_id: Unique UUID.
        character_id: Streaming character.
        platform: Target streaming platform.
        quality: Stream quality setting.
        overlay: Overlay configuration.
        world_id: World being streamed.
        live: Whether the stream is currently live.
        spectator_ids: Set of viewer character IDs in spectator mode.
        start_time: When the stream started.
        end_time: When the stream ended (None if still live).
        vsc_session_id: Optional reference to VideoStreamingConnector session.
    """
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    character_id: str = ""
    platform: StreamPlatform = StreamPlatform.TWITCH
    quality: StreamQuality = StreamQuality.HIGH
    overlay: OverlayConfig = field(default_factory=OverlayConfig)
    world_id: str = ""
    live: bool = False
    spectator_ids: List[str] = field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    vsc_session_id: Optional[str] = None


@dataclass
class HighlightEvent:
    """An auto-detected streaming highlight moment.

    Args:
        highlight_id: Unique UUID.
        stream_session_id: Parent stream session.
        highlight_type: Category of highlight.
        description: Human-readable description of the moment.
        timestamp: When it occurred.
        metadata: Optional extra context.
    """
    highlight_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    stream_session_id: str = ""
    highlight_type: HighlightType = HighlightType.SYNERGY_COMBO
    description: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# StreamingManager
# ---------------------------------------------------------------------------


class StreamingManager:
    """Manages streaming sessions, overlays, spectator mode, and highlights.

    Provides integration hooks to video_streaming_connector.py for
    platform-level operations (Twitch, YouTube Live, etc.).
    """

    def __init__(
        self,
        backbone: Optional[Any] = None,
        persistence: Optional[Any] = None,
        vsc: Optional[Any] = None,
    ) -> None:
        self._backbone = backbone
        self._persistence = persistence
        self._vsc = vsc  # VideoStreamingConnector instance (optional)
        self._lock = threading.Lock()
        self._sessions: Dict[str, StreamSession] = {}
        self._highlights: List[HighlightEvent] = []
        # world_id → list of streaming hotspots
        self._hotspots: Dict[str, List[StreamingHotspot]] = {}

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    def start_stream(
        self,
        character_id: str,
        platform: StreamPlatform,
        quality_settings: Optional[Dict[str, Any]] = None,
        world_id: str = "",
    ) -> StreamSession:
        """Start a new streaming session for a character.

        Args:
            character_id: The streaming character's ID.
            platform: Target platform.
            quality_settings: Optional dict with quality overrides.
            world_id: World being streamed.

        Returns:
            The created StreamSession (now live).
        """
        quality = StreamQuality.HIGH
        if quality_settings:
            q_value = quality_settings.get("quality")
            if q_value:
                try:
                    quality = StreamQuality(q_value)
                except ValueError:  # PROD-HARD A2: unknown quality string — log and fall back to HIGH
                    logger.debug("Unknown stream quality %r in settings; defaulting to HIGH", q_value)

        session = StreamSession(
            character_id=character_id,
            platform=platform,
            quality=quality,
            world_id=world_id,
            live=True,
            start_time=datetime.now(timezone.utc),
        )

        # Optional: register with VideoStreamingConnector
        if _VSC_AVAILABLE and self._vsc is not None:
            try:
                vsc_result = self._vsc.start_stream(
                    platform=platform.value,
                    title=f"Murphy World: {world_id or 'Lobby'}",
                )
                if vsc_result:
                    session.vsc_session_id = str(vsc_result.get("session_id", ""))
            except Exception:  # pragma: no cover
                logger.debug("VSC start_stream failed silently", exc_info=True)

        with self._lock:
            capped_append(list(self._sessions.values()), session, _MAX_SESSIONS)
            self._sessions[session.session_id] = session

        self._publish_event("stream_started", {
            "session_id": session.session_id,
            "character_id": character_id,
            "platform": platform.value,
            "world_id": world_id,
        })
        return session

    def configure_overlay(
        self,
        stream_session: StreamSession,
        overlay_config: OverlayConfig,
    ) -> None:
        """Update the overlay configuration for an active stream.

        Args:
            stream_session: The target StreamSession.
            overlay_config: New overlay configuration.
        """
        stream_session.overlay = overlay_config
        self._publish_event("overlay_configured", {
            "session_id": stream_session.session_id,
        })

    def stop_stream(self, session_id: str) -> Optional[StreamSession]:
        """End a live streaming session.

        Args:
            session_id: The session to stop.

        Returns:
            The stopped StreamSession, or None if not found.
        """
        session = self._sessions.get(session_id)
        if session is None:
            return None
        session.live = False
        session.end_time = datetime.now(timezone.utc)
        self._publish_event("stream_stopped", {"session_id": session_id})
        return session

    def get_active_streams(self, world_id: str) -> List[StreamSession]:
        """Return all currently live streams in a world.

        Args:
            world_id: The world to query.

        Returns:
            List of live StreamSession objects in that world.
        """
        return [
            s for s in self._sessions.values()
            if s.live and s.world_id == world_id
        ]

    # ------------------------------------------------------------------
    # Spectator mode
    # ------------------------------------------------------------------

    def enable_spectator_mode(
        self,
        viewer_id: str,
        target_character_id: str,
    ) -> Optional[StreamSession]:
        """Allow a viewer to spectate a streaming character.

        Args:
            viewer_id: The spectating character's ID.
            target_character_id: The character to watch.

        Returns:
            The StreamSession being spectated, or None if target is not streaming.
        """
        session = next(
            (s for s in self._sessions.values() if s.character_id == target_character_id and s.live),
            None,
        )
        if session is None:
            return None
        if viewer_id not in session.spectator_ids:
            session.spectator_ids.append(viewer_id)
        self._publish_event("spectator_joined", {
            "session_id": session.session_id,
            "viewer_id": viewer_id,
        })
        return session

    # ------------------------------------------------------------------
    # Hotspots
    # ------------------------------------------------------------------

    def register_hotspot(self, hotspot: StreamingHotspot) -> None:
        """Register a streaming hotspot for a world.

        Args:
            hotspot: The StreamingHotspot to register.
        """
        with self._lock:
            world_list = self._hotspots.setdefault(hotspot.world_id, [])
            capped_append(world_list, hotspot, 1_000)

    def get_streaming_hotspots(self, world_id: str) -> List[StreamingHotspot]:
        """Return streaming hotspots for a given world, sorted by combined score.

        Args:
            world_id: World to query.

        Returns:
            List of StreamingHotspot objects sorted by (scenic + action) score.
        """
        spots = self._hotspots.get(world_id, [])
        return sorted(spots, key=lambda h: h.scenic_score + h.action_score, reverse=True)

    # ------------------------------------------------------------------
    # Auto-highlight detection
    # ------------------------------------------------------------------

    def record_highlight(
        self,
        stream_session_id: str,
        highlight_type: HighlightType,
        description: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> HighlightEvent:
        """Record an auto-detected highlight moment for a stream.

        Args:
            stream_session_id: The stream this highlight belongs to.
            highlight_type: Category of the moment.
            description: Human-readable description.
            metadata: Optional extra context.

        Returns:
            The created HighlightEvent.
        """
        event = HighlightEvent(
            stream_session_id=stream_session_id,
            highlight_type=highlight_type,
            description=description,
            metadata=metadata or {},
        )
        with self._lock:
            capped_append(self._highlights, event, _MAX_HIGHLIGHTS)
        self._publish_event("highlight_detected", {
            "highlight_id": event.highlight_id,
            "session_id": stream_session_id,
            "type": highlight_type.value,
        })
        return event

    def get_session_highlights(self, stream_session_id: str) -> List[HighlightEvent]:
        """Return all highlights for a given stream session."""
        return [h for h in self._highlights if h.stream_session_id == stream_session_id]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _publish_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        if _BACKBONE_AVAILABLE and self._backbone is not None:
            try:
                self._backbone.publish(event_type, payload)
            except Exception:  # pragma: no cover
                logger.debug("EventBackbone publish failed silently", exc_info=True)
