# Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
# Design Label: EMS-007
"""Tariff engine — TOU rate modeling, demand charge optimization, bill simulation."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class RatePeriod(Enum):
    ON_PEAK = "on_peak"
    MID_PEAK = "mid_peak"
    OFF_PEAK = "off_peak"
    SUPER_OFF_PEAK = "super_off_peak"


@dataclass
class TariffSchedule:
    tariff_id: str
    utility: str
    rate_name: str
    periods: Dict[str, Dict] = field(default_factory=dict)
    # periods example: {"on_peak": {"rate_usd_per_kwh": 0.25, "hours": [(12,18)], "months": [6,7,8,9]}}

    @classmethod
    def default_commercial(cls) -> "TariffSchedule":
        return cls(
            tariff_id="default-comm-tou",
            utility="Generic Utility",
            rate_name="Commercial TOU",
            periods={
                RatePeriod.ON_PEAK.value: {
                    "rate_usd_per_kwh": 0.25,
                    "hours": [(12, 18)],
                    "months": [6, 7, 8, 9],
                },
                RatePeriod.MID_PEAK.value: {
                    "rate_usd_per_kwh": 0.15,
                    "hours": [(8, 12), (18, 21)],
                    "months": list(range(1, 13)),
                },
                RatePeriod.OFF_PEAK.value: {
                    "rate_usd_per_kwh": 0.08,
                    "hours": [(0, 8), (21, 24)],
                    "months": list(range(1, 13)),
                },
            },
        )


@dataclass
class DemandCharge:
    charge_type: str  # e.g. "facility_demand", "on_peak_demand"
    rate_usd_per_kw: float
    min_kw: float = 0.0


class TariffEngine:
    """TOU rate evaluation, bill simulation, and demand charge optimization."""

    def __init__(
        self,
        tariff: Optional[TariffSchedule] = None,
        demand_charges: Optional[List[DemandCharge]] = None,
    ) -> None:
        self._tariff = tariff or TariffSchedule.default_commercial()
        self._demand_charges = demand_charges or []

    # ── rate lookup ──────────────────────────────────────────────

    def get_current_period(self, timestamp: Optional[float] = None) -> RatePeriod:
        ts = timestamp or time.time()
        hour = (ts % 86400) / 3600
        import datetime as _dt
        dt = _dt.datetime.fromtimestamp(ts, tz=_dt.timezone.utc)
        month = dt.month

        for period_name, info in self._tariff.periods.items():
            months = info.get("months", list(range(1, 13)))
            if month not in months:
                continue
            for start_h, end_h in info.get("hours", []):
                if start_h <= hour < end_h:
                    try:
                        return RatePeriod(period_name)
                    except ValueError:
                        pass
        return RatePeriod.OFF_PEAK

    def get_rate(self, timestamp: Optional[float] = None) -> float:
        period = self.get_current_period(timestamp)
        info = self._tariff.periods.get(period.value, {})
        return info.get("rate_usd_per_kwh", 0.08)

    # ── bill simulation ──────────────────────────────────────────

    def simulate_bill(
        self,
        readings: List[Dict],
        demand_peak_kw: float = 0.0,
    ) -> Dict:
        """Simulate a monthly bill from interval readings.

        Each reading: {"timestamp": float, "kwh": float}
        """
        breakdown: Dict[str, float] = {}
        total_energy_cost = 0.0
        total_kwh = 0.0

        for r in readings:
            ts = r.get("timestamp", 0)
            kwh = r.get("kwh", 0)
            period = self.get_current_period(ts)
            rate = self.get_rate(ts)
            cost = kwh * rate
            breakdown[period.value] = breakdown.get(period.value, 0) + cost
            total_energy_cost += cost
            total_kwh += kwh

        demand_cost = 0.0
        for dc in self._demand_charges:
            if demand_peak_kw >= dc.min_kw:
                demand_cost += demand_peak_kw * dc.rate_usd_per_kw

        return {
            "energy_charges_usd": round(total_energy_cost, 2),
            "demand_charges_usd": round(demand_cost, 2),
            "total_usd": round(total_energy_cost + demand_cost, 2),
            "total_kwh": round(total_kwh, 2),
            "breakdown_by_period": {k: round(v, 2) for k, v in breakdown.items()},
        }

    # ── demand charge optimization ───────────────────────────────

    def optimize_demand(
        self,
        hourly_loads: List[float],
        battery: Optional[Dict] = None,
    ) -> Dict:
        """Flatten peak demand using optional battery storage.

        battery: {"capacity_kwh": float, "max_kw": float, "soc_pct": float}
        """
        if not hourly_loads:
            return {"original_peak": 0, "optimized_peak": 0, "savings_usd": 0}

        original_peak = max(hourly_loads)
        if battery is None:
            return {
                "original_peak": round(original_peak, 2),
                "optimized_peak": round(original_peak, 2),
                "savings_usd": 0.0,
                "schedule": [],
            }

        cap = battery.get("capacity_kwh", 0)
        max_kw = battery.get("max_kw", 0)
        soc_kwh = cap * battery.get("soc_pct", 50) / 100.0

        target = sum(hourly_loads) / len(hourly_loads)  # aim for flat profile
        schedule: List[Dict] = []
        optimized = list(hourly_loads)

        for i, load in enumerate(hourly_loads):
            if load > target and soc_kwh > 0:
                discharge = min(load - target, max_kw, soc_kwh)
                optimized[i] = load - discharge
                soc_kwh -= discharge
                schedule.append({"hour": i, "action": "discharge", "kw": round(discharge, 2)})
            elif load < target and soc_kwh < cap:
                charge = min(target - load, max_kw, cap - soc_kwh)
                optimized[i] = load + charge
                soc_kwh += charge
                schedule.append({"hour": i, "action": "charge", "kw": round(charge, 2)})

        opt_peak = max(optimized)
        reduction = original_peak - opt_peak
        savings = sum(dc.rate_usd_per_kw for dc in self._demand_charges) * reduction

        return {
            "original_peak": round(original_peak, 2),
            "optimized_peak": round(opt_peak, 2),
            "savings_usd": round(max(0, savings), 2),
            "schedule": schedule,
        }
