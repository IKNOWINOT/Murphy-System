# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""BAS-004 · Lighting control with daylight harvesting and occupancy.

Provides daylight-responsive dimming, schedule-based occupancy awareness,
and predefined scene presets for zones.

Thread-safe: mutable state guarded by RLock.
"""

from __future__ import annotations

import logging
import threading
import time
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
# Daylight Harvesting
# ---------------------------------------------------------------------------


class DaylightHarvestingModel:
    """Calculate dimming level from ambient light to maintain target lux."""

    def __init__(
        self,
        target_lux: float = 500.0,
        max_dimming_pct: float = 100.0,
        min_dimming_pct: float = 10.0,
    ) -> None:
        self.target_lux = target_lux
        self.max_dimming_pct = max_dimming_pct
        self.min_dimming_pct = min_dimming_pct

    def calculate_dimming(self, ambient_lux: float) -> float:
        """Return artificial-light dim level (0-100 %) to reach target lux."""
        if ambient_lux >= self.target_lux:
            return 0.0
        if ambient_lux <= 0.0:
            return self.max_dimming_pct

        deficit_ratio = (self.target_lux - ambient_lux) / self.target_lux
        dim_level = deficit_ratio * self.max_dimming_pct
        return max(self.min_dimming_pct, min(self.max_dimming_pct, round(dim_level, 1)))


# ---------------------------------------------------------------------------
# Occupancy Schedule
# ---------------------------------------------------------------------------


class OccupancySchedule:
    """Weekly schedule that indicates occupied time-windows per day."""

    def __init__(self, schedule: Dict[int, List[Tuple[float, float]]]) -> None:
        """
        Parameters
        ----------
        schedule:
            Mapping of ISO weekday (0=Mon … 6=Sun) to a list of
            ``(start_hour, end_hour)`` windows, e.g. ``{0: [(8, 18)]}``
            means Monday 08:00–18:00.
        """
        self.schedule = schedule

    def is_occupied(self, day_of_week: int, hour: float) -> bool:
        """Return *True* when *hour* falls inside any window for *day_of_week*."""
        windows = self.schedule.get(day_of_week, [])
        return any(start <= hour < end for start, end in windows)

    @classmethod
    def default_office_schedule(cls) -> "OccupancySchedule":
        """Mon–Fri 07:00–19:00."""
        weekday_window: List[Tuple[float, float]] = [(7.0, 19.0)]
        return cls({d: weekday_window for d in range(5)})


# ---------------------------------------------------------------------------
# Lighting Zone Controller
# ---------------------------------------------------------------------------

# Predefined scene presets (dim level 0-100 %)
_SCENES: Dict[str, Dict[str, Any]] = {
    "meeting": {"dim_level": 80.0, "reason": "scene:meeting"},
    "presentation": {"dim_level": 30.0, "reason": "scene:presentation"},
    "cleaning": {"dim_level": 100.0, "reason": "scene:cleaning"},
    "off": {"dim_level": 0.0, "reason": "scene:off"},
}


class LightingZoneController:
    """Per-zone lighting controller combining schedule, occupancy, and daylight."""

    def __init__(
        self,
        zone_id: str,
        target_lux: float = 500.0,
        schedule: Optional[OccupancySchedule] = None,
    ) -> None:
        self.zone_id = zone_id
        self._lock = threading.RLock()
        self._harvest = DaylightHarvestingModel(target_lux=target_lux)
        self._schedule = schedule or OccupancySchedule.default_office_schedule()
        self._current_scene: Optional[str] = None
        self._history: List[Dict[str, Any]] = []

    def compute_output(
        self,
        ambient_lux: float,
        is_occupied: bool,
        time_of_day: float,
    ) -> Dict[str, Any]:
        """Decide dim level based on occupancy, schedule, and daylight.

        Parameters
        ----------
        ambient_lux:
            Current ambient light in the zone (from photosensor).
        is_occupied:
            Real-time occupancy status.
        time_of_day:
            Current hour as a float (e.g. 14.5 = 2:30 PM).
        """
        with self._lock:
            # Active scene overrides automatic control
            if self._current_scene and self._current_scene in _SCENES:
                result = dict(_SCENES[self._current_scene])
                capped_append(self._history, {"ts": time.time(), **result})
                return result

            if not is_occupied:
                result = {"dim_level": 0.0, "reason": "occupancy"}
                capped_append(self._history, {"ts": time.time(), **result})
                return result

            dim = self._harvest.calculate_dimming(ambient_lux)
            result = {"dim_level": dim, "reason": "daylight"}
            capped_append(self._history, {"ts": time.time(), **result})
            return result

    def set_scene(self, scene_name: str) -> Dict[str, Any]:
        """Activate a named scene preset.  Pass ``"off"`` to deactivate."""
        with self._lock:
            if scene_name not in _SCENES:
                logger.warning(
                    "Zone %s: unknown scene '%s'; available: %s",
                    self.zone_id,
                    scene_name,
                    list(_SCENES),
                )
                return {"error": f"unknown scene: {scene_name}"}
            self._current_scene = scene_name if scene_name != "off" else None
            result = dict(_SCENES[scene_name])
            capped_append(self._history, {"ts": time.time(), "scene": scene_name, **result})
            return result
