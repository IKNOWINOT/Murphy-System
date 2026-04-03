# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""BAS-005 · Probabilistic occupancy sensing from multi-sensor fusion.

Fuses CO₂, PIR, badge-swipe, and BLE-beacon readings into a single
occupancy estimate per zone.  Includes a simple pre-conditioning prediction.

Thread-safe: mutable state guarded by RLock.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
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
# Data transfer objects
# ---------------------------------------------------------------------------


@dataclass
class OccupancySensorInput:
    """Single reading from one occupancy-related sensor."""

    sensor_id: str = ""
    sensor_type: str = ""  # co2 | pir | badge | ble
    value: float = 0.0
    confidence: float = 1.0  # 0-1
    timestamp: float = field(default_factory=time.time)


@dataclass
class OccupancyEstimate:
    """Fused occupancy result for a zone."""

    zone_id: str = ""
    estimated_count: int = 0
    confidence: float = 0.0
    is_occupied: bool = False
    contributing_sensors: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "estimated_count": self.estimated_count,
            "confidence": self.confidence,
            "is_occupied": self.is_occupied,
            "contributing_sensors": list(self.contributing_sensors),
            "timestamp": self.timestamp,
        }


# ---------------------------------------------------------------------------
# Fusion weights (higher = more trusted for head-count accuracy)
# ---------------------------------------------------------------------------

_SENSOR_WEIGHTS: Dict[str, float] = {
    "co2": 0.30,
    "pir": 0.20,
    "badge": 0.30,
    "ble": 0.20,
}

# CO₂ model parameters
_CO2_BASELINE_PPM: float = 400.0
_CO2_PER_PERSON_PPM: float = 40.0  # steady-state delta per occupant

# ---------------------------------------------------------------------------
# Occupancy Model
# ---------------------------------------------------------------------------


class OccupancyModel:
    """Multi-sensor fusion occupancy estimator for a single zone."""

    def __init__(self, zone_id: str, max_capacity: int = 50) -> None:
        self.zone_id = zone_id
        self.max_capacity = max_capacity

        self._lock = threading.RLock()
        # Latest reading per sensor_id
        self._latest: Dict[str, OccupancySensorInput] = {}
        self._history: List[Dict[str, Any]] = []

    # -- Sensor ingestion ---------------------------------------------------

    def update_sensor(self, sensor_input: OccupancySensorInput) -> None:
        """Store the latest reading from a sensor."""
        with self._lock:
            self._latest[sensor_input.sensor_id] = sensor_input
            capped_append(self._history, {
                "ts": time.time(),
                "sensor_id": sensor_input.sensor_id,
                "type": sensor_input.sensor_type,
                "value": sensor_input.value,
            })

    # -- Fusion estimate ----------------------------------------------------

    def estimate(self) -> OccupancyEstimate:
        """Fuse latest readings from all sensor types into one estimate."""
        with self._lock:
            if not self._latest:
                return OccupancyEstimate(zone_id=self.zone_id)

            # Group latest readings by sensor_type
            by_type: Dict[str, List[OccupancySensorInput]] = {}
            for inp in self._latest.values():
                by_type.setdefault(inp.sensor_type, []).append(inp)

            weighted_counts: List[float] = []
            total_weight: float = 0.0
            contributing: List[str] = []

            # CO₂-based count
            if "co2" in by_type:
                readings = by_type["co2"]
                avg_co2 = sum(r.value for r in readings) / len(readings)
                co2_count = max(0.0, (avg_co2 - _CO2_BASELINE_PPM) / _CO2_PER_PERSON_PPM)
                avg_conf = sum(r.confidence for r in readings) / len(readings)
                w = _SENSOR_WEIGHTS["co2"] * avg_conf
                weighted_counts.append(co2_count * w)
                total_weight += w
                contributing.extend(r.sensor_id for r in readings)

            # PIR binary (occupied = 1, vacant = 0)
            if "pir" in by_type:
                readings = by_type["pir"]
                pir_occupied = any(r.value > 0.0 for r in readings)
                pir_count = 1.0 if pir_occupied else 0.0
                avg_conf = sum(r.confidence for r in readings) / len(readings)
                w = _SENSOR_WEIGHTS["pir"] * avg_conf
                weighted_counts.append(pir_count * w)
                total_weight += w
                contributing.extend(r.sensor_id for r in readings)

            # Badge swipe count
            if "badge" in by_type:
                readings = by_type["badge"]
                badge_count = sum(r.value for r in readings)
                avg_conf = sum(r.confidence for r in readings) / len(readings)
                w = _SENSOR_WEIGHTS["badge"] * avg_conf
                weighted_counts.append(badge_count * w)
                total_weight += w
                contributing.extend(r.sensor_id for r in readings)

            # BLE beacon proximity count
            if "ble" in by_type:
                readings = by_type["ble"]
                ble_count = sum(r.value for r in readings)
                avg_conf = sum(r.confidence for r in readings) / len(readings)
                w = _SENSOR_WEIGHTS["ble"] * avg_conf
                weighted_counts.append(ble_count * w)
                total_weight += w
                contributing.extend(r.sensor_id for r in readings)

            if total_weight > 0.0:
                raw_count = sum(weighted_counts) / total_weight
            else:
                raw_count = 0.0

            est_count = max(0, min(self.max_capacity, int(round(raw_count))))
            confidence = min(1.0, total_weight / sum(_SENSOR_WEIGHTS.values()))

            return OccupancyEstimate(
                zone_id=self.zone_id,
                estimated_count=est_count,
                confidence=round(confidence, 3),
                is_occupied=est_count > 0,
                contributing_sensors=contributing,
                timestamp=time.time(),
            )

    # -- Pre-conditioning prediction ----------------------------------------

    def predict_preconditioning(self, minutes_ahead: int = 30) -> Dict[str, Any]:
        """Predict whether HVAC pre-conditioning should begin.

        Uses a simple heuristic: if recent history shows occupancy rising,
        recommend pre-conditioning.
        """
        with self._lock:
            recent = [
                e for e in self._history[-50:]
                if e.get("type") == "pir" and e["value"] > 0.0
            ]
            if len(recent) >= 3:
                return {
                    "should_precondition": True,
                    "confidence": min(1.0, len(recent) / 10.0),
                    "minutes_ahead": minutes_ahead,
                }
            return {
                "should_precondition": False,
                "confidence": 0.0,
                "minutes_ahead": minutes_ahead,
            }
