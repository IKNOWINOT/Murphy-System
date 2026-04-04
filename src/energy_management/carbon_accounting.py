# Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
# Design Label: EMS-006
"""Carbon accounting — Scope 1/2 emissions tracking with grid intensity signals."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)


class EmissionScope(Enum):
    SCOPE_1 = "scope_1"
    SCOPE_2 = "scope_2"
    SCOPE_3 = "scope_3"


@dataclass
class EmissionFactor:
    source: str
    factor_kg_co2e_per_unit: float
    unit: str
    scope: EmissionScope
    region: str = "US_AVG"


# ── default emission factors ────────────────────────────────────
_DEFAULT_FACTORS: Dict[str, EmissionFactor] = {
    "electricity_US_AVG": EmissionFactor(
        source="electricity", factor_kg_co2e_per_unit=0.386,
        unit="kWh", scope=EmissionScope.SCOPE_2, region="US_AVG",
    ),
    "natural_gas": EmissionFactor(
        source="natural_gas", factor_kg_co2e_per_unit=53.07,
        unit="MMBtu", scope=EmissionScope.SCOPE_1,
    ),
    "diesel": EmissionFactor(
        source="diesel", factor_kg_co2e_per_unit=10.21,
        unit="gallon", scope=EmissionScope.SCOPE_1,
    ),
    "propane": EmissionFactor(
        source="propane", factor_kg_co2e_per_unit=5.72,
        unit="gallon", scope=EmissionScope.SCOPE_1,
    ),
}


class CarbonTracker:
    """Real-time carbon emissions tracker with Scope 1 & 2 accounting."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._factors: Dict[str, EmissionFactor] = dict(_DEFAULT_FACTORS)
        self._grid_intensity: Dict[str, Dict] = {}  # region → {kg_co2e_per_kwh, ts}
        self._emission_log: list = []

    # ── factor management ────────────────────────────────────────

    def add_emission_factor(self, factor: EmissionFactor) -> None:
        with self._lock:
            key = f"{factor.source}_{factor.region}"
            self._factors[key] = factor

    # ── Scope 1: direct combustion ───────────────────────────────

    def calculate_scope1(
        self, fuel_type: str, quantity: float, unit: str = ""
    ) -> Dict:
        with self._lock:
            factor = self._factors.get(fuel_type)
            if factor is None:
                return {"kg_co2e": 0.0, "source": fuel_type, "error": "unknown fuel type"}
            kg = quantity * factor.factor_kg_co2e_per_unit
            entry = {
                "scope": "scope_1", "source": fuel_type,
                "quantity": quantity, "kg_co2e": round(kg, 3), "ts": time.time(),
            }
            capped_append(self._emission_log, entry)
            return {"kg_co2e": round(kg, 3), "source": fuel_type}

    # ── Scope 2: purchased electricity ───────────────────────────

    def calculate_scope2(
        self, electricity_kwh: float, region: str = "US_AVG"
    ) -> Dict:
        with self._lock:
            # prefer live grid intensity if available
            live = self._grid_intensity.get(region)
            if live:
                factor = live["kg_co2e_per_kwh"]
            else:
                ef = self._factors.get(f"electricity_{region}")
                factor = ef.factor_kg_co2e_per_unit if ef else 0.386
            kg = electricity_kwh * factor
            entry = {
                "scope": "scope_2", "source": "electricity",
                "kwh": electricity_kwh, "kg_co2e": round(kg, 3),
                "region": region, "ts": time.time(),
            }
            capped_append(self._emission_log, entry)
            return {"kg_co2e": round(kg, 3), "grid_factor": factor}

    # ── live grid intensity ──────────────────────────────────────

    def set_grid_carbon_intensity(
        self, region: str, kg_co2e_per_kwh: float
    ) -> None:
        with self._lock:
            self._grid_intensity[region] = {
                "kg_co2e_per_kwh": kg_co2e_per_kwh,
                "timestamp": time.time(),
            }

    def get_live_intensity(self, region: str = "US_AVG") -> Dict:
        with self._lock:
            live = self._grid_intensity.get(region)
            if live:
                return {
                    "kg_co2e_per_kwh": live["kg_co2e_per_kwh"],
                    "timestamp": live["timestamp"],
                    "source": "live_signal",
                }
            ef = self._factors.get(f"electricity_{region}")
            return {
                "kg_co2e_per_kwh": ef.factor_kg_co2e_per_unit if ef else 0.386,
                "timestamp": time.time(),
                "source": "default_factor",
            }

    # ── totals ───────────────────────────────────────────────────

    def total_emissions(
        self,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
    ) -> Dict:
        with self._lock:
            entries = list(self._emission_log)
        if start_time is not None:
            entries = [e for e in entries if e.get("ts", 0) >= start_time]
        if end_time is not None:
            entries = [e for e in entries if e.get("ts", 0) <= end_time]
        s1 = sum(e.get("kg_co2e", 0) for e in entries if e.get("scope") == "scope_1")
        s2 = sum(e.get("kg_co2e", 0) for e in entries if e.get("scope") == "scope_2")
        return {
            "scope_1_kg_co2e": round(s1, 3),
            "scope_2_kg_co2e": round(s2, 3),
            "total_kg_co2e": round(s1 + s2, 3),
            "entries": len(entries),
        }
