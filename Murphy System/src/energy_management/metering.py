# Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
# Design Label: EMS-002
"""Murphy-native metering model for interval data ingestion."""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)


class MeterType(Enum):
    ELECTRICITY = "electricity"
    NATURAL_GAS = "natural_gas"
    WATER = "water"
    STEAM = "steam"
    CHILLED_WATER = "chilled_water"
    HOT_WATER = "hot_water"
    SOLAR_PV = "solar_pv"


@dataclass
class MeterReading:
    reading_id: str
    meter_id: str
    timestamp: float
    value: float
    unit: str
    demand_kw: Optional[float] = None
    quality: str = "good"


@dataclass
class MurphyMeter:
    meter_id: str
    name: str
    meter_type: MeterType
    building_id: str
    parent_meter_id: Optional[str] = None
    unit: str = "kWh"
    multiplier: float = 1.0
    readings: list = field(default_factory=list)


class MeteringRegistry:
    """Thread-safe registry for meters and interval readings."""

    def __init__(self, max_readings_per_meter: int = 100_000) -> None:
        self._lock = threading.RLock()
        self._meters: Dict[str, MurphyMeter] = {}
        self._max_readings = max_readings_per_meter

    def register_meter(self, meter: MurphyMeter) -> None:
        with self._lock:
            self._meters[meter.meter_id] = meter

    def add_reading(self, meter_id: str, reading: MeterReading) -> None:
        with self._lock:
            meter = self._meters.get(meter_id)
            if meter is None:
                raise KeyError(f"Meter {meter_id} not registered")
            capped_append(meter.readings, reading, self._max_readings)

    def get_readings(
        self,
        meter_id: str,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
    ) -> List[MeterReading]:
        with self._lock:
            meter = self._meters.get(meter_id)
            if meter is None:
                raise KeyError(f"Meter {meter_id} not registered")
            readings = list(meter.readings)
        result = readings
        if start_time is not None:
            result = [r for r in result if r.timestamp >= start_time]
        if end_time is not None:
            result = [r for r in result if r.timestamp <= end_time]
        return result

    def get_interval_data(
        self,
        meter_id: str,
        interval_minutes: int = 15,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
    ) -> List[Dict]:
        readings = self.get_readings(meter_id, start_time, end_time)
        if not readings:
            return []
        readings.sort(key=lambda r: r.timestamp)
        interval_sec = interval_minutes * 60
        buckets: Dict[int, List[MeterReading]] = {}
        for r in readings:
            bucket_key = int(r.timestamp // interval_sec) * interval_sec
            buckets.setdefault(bucket_key, []).append(r)
        result: List[Dict] = []
        for ts in sorted(buckets):
            group = buckets[ts]
            avg_val = sum(r.value for r in group) / len(group)
            demand_vals = [r.demand_kw for r in group if r.demand_kw is not None]
            result.append({
                "interval_start": ts,
                "interval_end": ts + interval_sec,
                "avg_value": avg_val,
                "reading_count": len(group),
                "peak_demand_kw": max(demand_vals) if demand_vals else None,
            })
        return result

    def get_demand_peak(
        self, meter_id: str, start_time: float, end_time: float
    ) -> Dict:
        readings = self.get_readings(meter_id, start_time, end_time)
        demand_readings = [r for r in readings if r.demand_kw is not None]
        if not demand_readings:
            return {"peak_kw": 0.0, "timestamp": None}
        peak = max(demand_readings, key=lambda r: r.demand_kw)  # type: ignore[arg-type]
        return {"peak_kw": peak.demand_kw, "timestamp": peak.timestamp}

    def get_total_consumption(
        self, meter_id: str, start_time: float, end_time: float
    ) -> Dict:
        readings = self.get_readings(meter_id, start_time, end_time)
        meter = self._meters[meter_id]
        total = sum(r.value * meter.multiplier for r in readings)
        return {"total": total, "unit": meter.unit}

    def list_meters(self, building_id: Optional[str] = None) -> List[MurphyMeter]:
        with self._lock:
            meters = list(self._meters.values())
        if building_id is not None:
            meters = [m for m in meters if m.building_id == building_id]
        return meters

    def get_submeter_hierarchy(self, meter_id: str) -> Dict:
        with self._lock:
            meter = self._meters.get(meter_id)
            if meter is None:
                raise KeyError(f"Meter {meter_id} not registered")
            children = [
                m.meter_id
                for m in self._meters.values()
                if m.parent_meter_id == meter_id
            ]
        return {
            "meter_id": meter_id,
            "parent": meter.parent_meter_id,
            "children": children,
        }
