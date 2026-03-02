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
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List


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
        self._overlays.append(config)

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
        self._thought_bubbles.append(bubble)
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
        self._duel_highlights.append(highlight)
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
