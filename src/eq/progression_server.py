"""
Progression Server — Era System, XP Configuration, and Level Caps

Implements the progression server era system described in §4 of the
Experimental EverQuest Modification Plan.

Key rules:
  - The server advances through eras: Classic → Kunark → Velious →
    Luclin → Planes of Power.
  - Each era defines a level cap, unlocked zones, and content description.
  - Hell levels (44, 51, 54, 59) impose a 0.5× XP modifier.
  - Death XP penalty and corpse runs are era-configurable.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Era(Enum):
    """Progression server eras (§4), matching ServerEra from eq_game_connector."""

    CLASSIC = "classic"
    KUNARK = "kunark"
    VELIOUS = "velious"
    LUCLIN = "luclin"
    PLANES_OF_POWER = "planes_of_power"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class EraConfig:
    """Configuration for a single progression era."""

    era: Era
    max_level: int
    zones_unlocked: List[str] = field(default_factory=list)
    content_description: str = ""


@dataclass
class XPConfig:
    """Experience point configuration."""

    base_rate: float = 1.0
    hell_levels: List[int] = field(default_factory=lambda: [44, 51, 54, 59])
    death_xp_penalty_percent: float = 10.0
    corpse_runs_enabled: bool = True


@dataclass
class ProgressionSchedule:
    """Ordered list of eras that the server progresses through."""

    eras: List[EraConfig] = field(default_factory=list)
    current_era_index: int = 0


# ---------------------------------------------------------------------------
# Default Schedule
# ---------------------------------------------------------------------------

_CLASSIC_ZONES = [
    "qeynos", "freeport", "halas", "rivervale", "erudin",
    "paineel", "kaladim", "felwithe", "kelethin", "neriak",
    "grobb", "oggok", "blackburrow", "befallen", "cazic_thule",
    "lower_guk", "upper_guk", "soluseks_eye", "nagafens_lair",
    "plane_of_fear", "plane_of_hate", "plane_of_sky",
]

_KUNARK_ZONES = [
    "firiona_vie", "overthere", "lake_of_ill_omen", "dreadlands",
    "burning_woods", "frontier_mountains", "trakanons_teeth",
    "sebilis", "howling_stones", "karnors_castle", "veeshan_peak",
]

_VELIOUS_ZONES = [
    "iceclad_ocean", "eastern_wastes", "great_divide", "cobalt_scar",
    "crystal_caverns", "thurgadin", "kael_drakkel", "skyshrine",
    "temple_of_veeshan", "sleepers_tomb", "western_wastes",
]

_LUCLIN_ZONES = [
    "nexus", "bazaar", "shadow_haven", "paludal_caverns",
    "grimling_forest", "acrylia_caverns", "shar_vahl",
    "sanctus_seru", "ssraeshza_temple", "vex_thal",
]

_PLANES_ZONES = [
    "plane_of_knowledge", "plane_of_justice", "plane_of_nightmare",
    "plane_of_disease", "plane_of_innovation", "plane_of_valor",
    "plane_of_storms", "plane_of_torment", "plane_of_fire",
    "plane_of_water", "plane_of_air", "plane_of_earth",
    "plane_of_time",
]


def build_default_schedule() -> ProgressionSchedule:
    """Build the default Classic → Planes of Power progression schedule."""
    classic_zones = list(_CLASSIC_ZONES)
    kunark_zones = classic_zones + _KUNARK_ZONES
    velious_zones = kunark_zones + _VELIOUS_ZONES
    luclin_zones = velious_zones + _LUCLIN_ZONES
    planes_zones = luclin_zones + _PLANES_ZONES

    return ProgressionSchedule(
        eras=[
            EraConfig(
                era=Era.CLASSIC,
                max_level=50,
                zones_unlocked=classic_zones,
                content_description="Original EverQuest content — starting zones, dungeons, and original planes.",
            ),
            EraConfig(
                era=Era.KUNARK,
                max_level=60,
                zones_unlocked=kunark_zones,
                content_description="Ruins of Kunark — Iksar homeland, Sebilis, Veeshan's Peak.",
            ),
            EraConfig(
                era=Era.VELIOUS,
                max_level=60,
                zones_unlocked=velious_zones,
                content_description="Scars of Velious — Velious continent, Temple of Veeshan, Sleeper's Tomb.",
            ),
            EraConfig(
                era=Era.LUCLIN,
                max_level=60,
                zones_unlocked=luclin_zones,
                content_description="Shadows of Luclin — Moon of Luclin, Vex Thal, Bazaar.",
            ),
            EraConfig(
                era=Era.PLANES_OF_POWER,
                max_level=65,
                zones_unlocked=planes_zones,
                content_description="Planes of Power — elemental planes, Plane of Time.",
            ),
        ],
        current_era_index=0,
    )


# ---------------------------------------------------------------------------
# Progression Server
# ---------------------------------------------------------------------------

class ProgressionServer:
    """Manages server progression through expansion eras.

    §4: The server begins in Classic and advances through each era,
    unlocking zones and raising level caps as it goes.
    """

    def __init__(self, schedule: Optional[ProgressionSchedule] = None) -> None:
        self._schedule = schedule or build_default_schedule()
        self._xp_config = XPConfig()

    # --- Era management ---

    @property
    def current_era(self) -> EraConfig:
        """Return the current era configuration."""
        return self._schedule.eras[self._schedule.current_era_index]

    def advance_era(self) -> Optional[EraConfig]:
        """Advance to the next era. Returns the new era, or None if at end."""
        next_index = self._schedule.current_era_index + 1
        if next_index >= len(self._schedule.eras):
            return None
        self._schedule.current_era_index = next_index
        return self._schedule.eras[next_index]

    # --- Zone queries ---

    def is_zone_unlocked(self, zone_name: str, era: Optional[Era] = None) -> bool:
        """Check if a zone is unlocked in the given era (defaults to current)."""
        if era is not None:
            for era_cfg in self._schedule.eras:
                if era_cfg.era == era:
                    return zone_name in era_cfg.zones_unlocked
            return False
        return zone_name in self.current_era.zones_unlocked

    # --- Level cap ---

    def get_level_cap(self) -> int:
        """Return the current era's level cap."""
        return self.current_era.max_level

    # --- XP system ---

    def is_hell_level(self, level: int) -> bool:
        """Return True if the given level is a hell level."""
        return level in self._xp_config.hell_levels

    def calculate_xp_modifier(self, level: int) -> float:
        """Return the XP modifier for the given level.

        Hell levels receive 0.5× XP; all other levels receive 1.0×.
        """
        if self.is_hell_level(level):
            return 0.5
        return self._xp_config.base_rate
