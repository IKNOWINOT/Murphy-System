"""
Billboard Ad System — In-Game Proximity Advertisement

In-game billboards display advertisements based on proximity to characters.
All advertisements are non-intrusive, cosmetic in nature, and revenue-
generating. Content is contextual and changes based on who is nearby.

Provides:
  - Proximity-based billboard content selection
  - Character profile-aware ad targeting
  - Non-intrusive placement rules
  - Revenue tracking per billboard impression
  - Ad content generation/rotation
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
# Constants
# ---------------------------------------------------------------------------

# Characters within this radius (game units) trigger an impression
DEFAULT_PROXIMITY_RADIUS: float = 50.0

# Maximum impressions per billboard per minute to avoid spam
MAX_IMPRESSIONS_PER_MINUTE: int = 10

# Rotation interval: billboard cycles content every N seconds
DEFAULT_ROTATION_SECONDS: float = 30.0


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class AdCategory(Enum):
    """What type of advertisement content a billboard shows."""

    GAME_EVENT = "game_event"         # In-game events and announcements
    COSMETIC_ITEM = "cosmetic_item"   # Cosmetic shop promotions
    GUILD_RECRUITMENT = "guild_recruitment"
    WORLD_NEWS = "world_news"         # Lore/news from the game world
    STREAM_PROMO = "stream_promo"     # Promote live streams of the game
    COMMUNITY = "community"           # Player community content


class BillboardPlacementZone(Enum):
    """Where in the world a billboard is placed."""

    CITY = "city"
    TOWN_SQUARE = "town_square"
    DUNGEON_ENTRANCE = "dungeon_entrance"
    WILDERNESS_ROAD = "wilderness_road"
    RAID_STAGING = "raid_staging"
    PLAYER_HOUSING = "player_housing"


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class AdContent:
    """A single advertisement that can be displayed on a billboard."""

    ad_id: str
    title: str
    body: str
    category: AdCategory
    target_class_ids: List[str] = field(default_factory=list)   # empty = all classes
    target_level_min: int = 1
    target_level_max: int = 100
    visual_url: str = ""
    cpc_value: float = 0.01   # cost-per-click / impression value (credits)
    active: bool = True


@dataclass
class Billboard:
    """An in-world billboard object."""

    billboard_id: str
    name: str
    zone_id: str
    placement_zone: BillboardPlacementZone
    position: Tuple[float, float, float]   # (x, y, z)
    proximity_radius: float = DEFAULT_PROXIMITY_RADIUS
    rotation_seconds: float = DEFAULT_ROTATION_SECONDS
    current_ad_id: Optional[str] = None
    last_rotated: float = field(default_factory=time.time)
    total_impressions: int = 0
    total_revenue: float = 0.0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)


@dataclass
class BillboardImpression:
    """Record of a character seeing a billboard ad."""

    impression_id: str
    billboard_id: str
    ad_id: str
    character_id: str
    character_class_id: str
    character_level: int
    timestamp: float = field(default_factory=time.time)
    revenue_credited: float = 0.0


# ---------------------------------------------------------------------------
# Core Engine
# ---------------------------------------------------------------------------

class BillboardAdSystem:
    """
    Manages in-game billboard advertisements with proximity awareness.

    Thread-safe: all shared state protected by ``_lock``.
    Bounded collections: uses ``capped_append`` (CWE-770).
    """

    _MAX_IMPRESSIONS = 100_000

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._billboards: Dict[str, Billboard] = {}
        self._ads: Dict[str, AdContent] = {}
        self._impressions: List[BillboardImpression] = []
        self._impression_counts: Dict[str, List[float]] = {}  # billboard_id → timestamps

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_billboard(self, billboard: Billboard) -> None:
        """Add a billboard to the system."""
        with self._lock:
            self._billboards[billboard.billboard_id] = billboard

    def register_ad(self, ad: AdContent) -> None:
        """Add an advertisement to the pool."""
        with self._lock:
            self._ads[ad.ad_id] = ad

    # ------------------------------------------------------------------
    # Proximity processing
    # ------------------------------------------------------------------

    def process_character_position(
        self,
        character_id: str,
        class_id: str,
        level: int,
        position: Tuple[float, float, float],
        zone_id: str,
    ) -> List[BillboardImpression]:
        """
        Check all billboards in the zone for proximity and record impressions.

        Returns list of impressions generated this tick.
        """
        impressions: List[BillboardImpression] = []
        now = time.time()

        with self._lock:
            zone_billboards = [
                b for b in self._billboards.values() if b.zone_id == zone_id
            ]

        for billboard in zone_billboards:
            dist = _distance(position, billboard.position)
            if dist > billboard.proximity_radius:
                continue

            # Rate-limit impressions per billboard
            if not self._can_impress(billboard.billboard_id, now):
                continue

            # Rotate ad if needed
            self._maybe_rotate(billboard, class_id, level, now)

            if not billboard.current_ad_id:
                continue

            with self._lock:
                ad = self._ads.get(billboard.current_ad_id)
            if not ad or not ad.active:
                continue

            impression = BillboardImpression(
                impression_id=str(uuid.uuid4()),
                billboard_id=billboard.billboard_id,
                ad_id=ad.ad_id,
                character_id=character_id,
                character_class_id=class_id,
                character_level=level,
                revenue_credited=ad.cpc_value,
            )

            with billboard._lock:
                billboard.total_impressions += 1
                billboard.total_revenue += ad.cpc_value

            with self._lock:
                capped_append(self._impressions, impression, self._MAX_IMPRESSIONS)
                times = self._impression_counts.setdefault(billboard.billboard_id, [])
                times.append(now)

            impressions.append(impression)

        return impressions

    # ------------------------------------------------------------------
    # Revenue reporting
    # ------------------------------------------------------------------

    def total_revenue(self) -> float:
        """Return total revenue across all billboards."""
        with self._lock:
            billboards = list(self._billboards.values())
        return sum(b.total_revenue for b in billboards)

    def billboard_revenue(self, billboard_id: str) -> float:
        """Return revenue for a specific billboard."""
        with self._lock:
            b = self._billboards.get(billboard_id)
        return b.total_revenue if b else 0.0

    def impressions_for_ad(self, ad_id: str) -> int:
        """Return total impressions for a specific ad."""
        with self._lock:
            return sum(1 for imp in self._impressions if imp.ad_id == ad_id)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _can_impress(self, billboard_id: str, now: float) -> bool:
        """Return True if billboard has not exceeded the per-minute rate limit."""
        with self._lock:
            times = self._impression_counts.get(billboard_id, [])
            # Purge timestamps older than 60s
            recent = [t for t in times if now - t < 60.0]
            self._impression_counts[billboard_id] = recent
            return len(recent) < MAX_IMPRESSIONS_PER_MINUTE

    def _maybe_rotate(
        self,
        billboard: Billboard,
        class_id: str,
        level: int,
        now: float,
    ) -> None:
        """Rotate the billboard's ad if the rotation interval has elapsed."""
        with billboard._lock:
            age = now - billboard.last_rotated
            if age < billboard.rotation_seconds and billboard.current_ad_id:
                return
            billboard.last_rotated = now

        best = self._select_ad(class_id, level)
        with billboard._lock:
            billboard.current_ad_id = best

    def _select_ad(self, class_id: str, level: int) -> Optional[str]:
        """Select the most relevant active ad for a character."""
        with self._lock:
            active_ads = [a for a in self._ads.values() if a.active]

        if not active_ads:
            return None

        # Score ads by relevance: class targeting match + level match
        def score(ad: AdContent) -> float:
            s = 1.0
            if ad.target_class_ids and class_id in ad.target_class_ids:
                s += 2.0
            if ad.target_level_min <= level <= ad.target_level_max:
                s += 1.0
            return s

        best = max(active_ads, key=score)
        return best.ad_id


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _distance(
    a: Tuple[float, float, float], b: Tuple[float, float, float]
) -> float:
    """Euclidean distance between two 3D points."""
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2) ** 0.5
