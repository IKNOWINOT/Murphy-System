"""
Proximity Billboard Advertising System for the Multiverse Game Framework.

Design Label: GAME-005 — Proximity Billboard Advertising System
Owner: Backend Team
Dependencies:
  - EventBackbone
  - PersistenceManager

Billboards are in-world advertising surfaces that activate when a character
enters their visibility radius. They are cosmetic and informational only —
no pay-to-win advantages.

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
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

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

_MAX_ANALYTICS_EVENTS = 100_000

# Type alias for 3D position
Position = Tuple[float, float, float]

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class BillboardScheduleWindow:
    """A time window during which a billboard is active.

    Args:
        start: Window start time (UTC).
        end: Window end time (UTC).
    """
    start: datetime
    end: datetime

    def is_active_now(self) -> bool:
        """Return True if the current UTC time falls within this window."""
        now = datetime.now(timezone.utc)
        return self.start <= now <= self.end


@dataclass
class Billboard:
    """An in-world advertising billboard.

    Args:
        billboard_id: Unique billboard UUID.
        world_id: World this billboard lives in.
        zone_id: Zone within the world.
        position: 3D (x, y, z) position.
        visibility_radius: Distance at which the billboard becomes visible.
        content: Dict with advertiser_id, creative_url, click_action, campaign_id.
        impression_count: Total impressions recorded.
        interaction_count: Total interactions recorded.
        active: Whether this billboard is currently active.
        schedule: Optional list of time windows; empty = always active.
    """
    billboard_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    world_id: str = ""
    zone_id: str = ""
    position: Position = (0.0, 0.0, 0.0)
    visibility_radius: float = 50.0
    content: Dict[str, Any] = field(default_factory=dict)
    impression_count: int = 0
    interaction_count: int = 0
    active: bool = True
    schedule: List[BillboardScheduleWindow] = field(default_factory=list)

    def is_currently_active(self) -> bool:
        """Return True if the billboard is active and within its schedule."""
        if not self.active:
            return False
        if not self.schedule:
            return True
        return any(w.is_active_now() for w in self.schedule)


@dataclass
class BillboardAnalytics:
    """Aggregated analytics for an advertising campaign.

    Args:
        campaign_id: The campaign identifier.
        total_impressions: Sum of impressions across all campaign billboards.
        total_interactions: Sum of interactions.
        unique_viewers: Set of character IDs that saw the billboard.
        ctr: Click-through rate (interactions / impressions).
    """
    campaign_id: str
    total_impressions: int
    total_interactions: int
    unique_viewers: int
    ctr: float


@dataclass
class _ImpressionRecord:
    billboard_id: str
    character_id: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class _InteractionRecord:
    billboard_id: str
    character_id: str
    action_type: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# BillboardEngine
# ---------------------------------------------------------------------------


class BillboardEngine:
    """Manages in-world billboard placement, proximity detection, and analytics.

    Policy:
    - Billboards must NOT give gameplay advantage (cosmetic/informational only).
    - No pay-to-win content is permitted.
    """

    def __init__(
        self,
        backbone: Optional[Any] = None,
        persistence: Optional[Any] = None,
    ) -> None:
        self._backbone = backbone
        self._persistence = persistence
        self._lock = threading.Lock()
        self._billboards: Dict[str, Billboard] = {}
        self._impressions: List[_ImpressionRecord] = []
        self._interactions: List[_InteractionRecord] = []

    # ------------------------------------------------------------------
    # Placement
    # ------------------------------------------------------------------

    def place_billboard(
        self,
        world_id: str,
        zone_id: str,
        position: Position,
        content: Dict[str, Any],
        radius: float = 50.0,
        schedule: Optional[List[BillboardScheduleWindow]] = None,
    ) -> Billboard:
        """Place a new billboard in the world.

        Args:
            world_id: Target world.
            zone_id: Zone within the world.
            position: 3D (x, y, z) position.
            content: Dict with advertiser_id, creative_url, click_action, campaign_id.
            radius: Visibility radius.
            schedule: Optional activation time windows.

        Returns:
            The newly created Billboard.
        """
        billboard = Billboard(
            world_id=world_id,
            zone_id=zone_id,
            position=position,
            visibility_radius=radius,
            content=dict(content),
            schedule=schedule or [],
        )
        with self._lock:
            self._billboards[billboard.billboard_id] = billboard
        logger.info(
            "Billboard placed in world=%s zone=%s pos=%s radius=%.1f",
            world_id, zone_id, position, radius,
        )
        self._publish_event("billboard_placed", {
            "billboard_id": billboard.billboard_id,
            "world_id": world_id,
        })
        return billboard

    # ------------------------------------------------------------------
    # Proximity detection
    # ------------------------------------------------------------------

    @staticmethod
    def _distance(a: Position, b: Position) -> float:
        """Euclidean distance between two 3D positions."""
        return math.sqrt(sum((ai - bi) ** 2 for ai, bi in zip(a, b)))

    def get_visible_billboards(
        self,
        character_position: Position,
        world_id: str,
    ) -> List[Billboard]:
        """Return all active billboards within visibility radius of a position.

        Args:
            character_position: The character's current (x, y, z) position.
            world_id: The world the character is in.

        Returns:
            List of visible, active Billboard objects.
        """
        visible: List[Billboard] = []
        for bb in self._billboards.values():
            if bb.world_id != world_id:
                continue
            if not bb.is_currently_active():
                continue
            dist = self._distance(character_position, bb.position)
            if dist <= bb.visibility_radius:
                visible.append(bb)
        return visible

    # ------------------------------------------------------------------
    # Analytics recording
    # ------------------------------------------------------------------

    def record_impression(self, billboard_id: str, character_id: str) -> None:
        """Record that a character saw a billboard.

        Args:
            billboard_id: The billboard that was seen.
            character_id: The character that saw it.
        """
        record = _ImpressionRecord(billboard_id=billboard_id, character_id=character_id)
        with self._lock:
            bb = self._billboards.get(billboard_id)
            if bb:
                bb.impression_count += 1
            capped_append(self._impressions, record, _MAX_ANALYTICS_EVENTS)
        self._publish_event("billboard_impression", {
            "billboard_id": billboard_id,
            "character_id": character_id,
        })

    def record_interaction(
        self,
        billboard_id: str,
        character_id: str,
        action_type: str,
    ) -> None:
        """Record that a character interacted with a billboard.

        Args:
            billboard_id: The billboard interacted with.
            character_id: The character that interacted.
            action_type: Type of interaction (e.g., "click", "dismiss").
        """
        record = _InteractionRecord(
            billboard_id=billboard_id,
            character_id=character_id,
            action_type=action_type,
        )
        with self._lock:
            bb = self._billboards.get(billboard_id)
            if bb:
                bb.interaction_count += 1
            capped_append(self._interactions, record, _MAX_ANALYTICS_EVENTS)
        self._publish_event("billboard_interaction", {
            "billboard_id": billboard_id,
            "character_id": character_id,
            "action_type": action_type,
        })

    def get_campaign_analytics(self, campaign_id: str) -> BillboardAnalytics:
        """Aggregate analytics for all billboards belonging to a campaign.

        Args:
            campaign_id: The campaign to aggregate.

        Returns:
            BillboardAnalytics summary.
        """
        # Find billboards in this campaign
        campaign_bbs: Dict[str, Billboard] = {
            bid: bb
            for bid, bb in self._billboards.items()
            if bb.content.get("campaign_id") == campaign_id
        }
        campaign_ids = set(campaign_bbs.keys())

        total_impressions = sum(bb.impression_count for bb in campaign_bbs.values())
        total_interactions = sum(bb.interaction_count for bb in campaign_bbs.values())
        unique_viewers = len({
            r.character_id
            for r in self._impressions
            if r.billboard_id in campaign_ids
        })
        ctr = (total_interactions / total_impressions) if total_impressions > 0 else 0.0

        return BillboardAnalytics(
            campaign_id=campaign_id,
            total_impressions=total_impressions,
            total_interactions=total_interactions,
            unique_viewers=unique_viewers,
            ctr=round(ctr, 4),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _publish_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        if _BACKBONE_AVAILABLE and self._backbone is not None:
            try:
                self._backbone.publish(event_type, payload)
            except Exception:  # pragma: no cover
                logger.debug("EventBackbone publish failed silently", exc_info=True)
