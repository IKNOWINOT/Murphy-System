# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""BAS-003 · Native HVAC control logic.

Provides PID control, Air Handling Unit (AHU) supply-air reset with
economizer, and zone-level temperature demand calculation.

Thread-safe: each controller guards mutable state with an RLock.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, List

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
# PID Controller
# ---------------------------------------------------------------------------


class PIDController:
    """Discrete proportional-integral-derivative controller."""

    def __init__(
        self,
        kp: float = 1.0,
        ki: float = 0.0,
        kd: float = 0.0,
        output_min: float = 0.0,
        output_max: float = 100.0,
        setpoint: float = 72.0,
    ) -> None:
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.output_min = output_min
        self.output_max = output_max
        self.setpoint = setpoint

        self._lock = threading.RLock()
        self._integral: float = 0.0
        self._prev_error: float = 0.0
        self._history: List[Dict[str, Any]] = []

    def compute(self, current_value: float, dt: float) -> float:
        """Return clamped control output for the current process value."""
        if dt <= 0.0:
            return 0.0
        with self._lock:
            error = self.setpoint - current_value

            self._integral += error * dt
            # Anti-windup: clamp integral contribution
            integral_contribution = self.ki * self._integral
            if integral_contribution > self.output_max:
                self._integral = self.output_max / self.ki if self.ki else 0.0
            elif integral_contribution < self.output_min:
                self._integral = self.output_min / self.ki if self.ki else 0.0

            derivative = (error - self._prev_error) / dt
            self._prev_error = error

            output = self.kp * error + self.ki * self._integral + self.kd * derivative
            output = max(self.output_min, min(self.output_max, output))

            capped_append(self._history, {
                "ts": time.time(),
                "error": error,
                "output": output,
            })
            return output

    def reset(self) -> None:
        with self._lock:
            self._integral = 0.0
            self._prev_error = 0.0
            self._history.clear()


# ---------------------------------------------------------------------------
# AHU Controller
# ---------------------------------------------------------------------------


class AHUController:
    """Air Handling Unit supply-air reset and economizer control."""

    def __init__(
        self,
        ahu_id: str,
        design_supply_temp: float = 55.0,
        min_oa_fraction: float = 0.15,
    ) -> None:
        self.ahu_id = ahu_id
        self.design_supply_temp = design_supply_temp
        self.min_oa_fraction = min_oa_fraction

        self._lock = threading.RLock()
        self._current_supply_temp: float = design_supply_temp
        self._history: List[Dict[str, Any]] = []

    # -- Trim & Respond supply-air reset ---------------------------------

    def supply_air_reset(self, zone_demands: List[float]) -> float:
        """Trim / respond: raise SAT when all zones satisfied, lower on high demand."""
        with self._lock:
            if not zone_demands:
                return self._current_supply_temp

            max_demand = max(zone_demands)
            avg_demand = sum(zone_demands) / len(zone_demands)

            sat_max = 65.0
            sat_min = self.design_supply_temp

            if max_demand < 30.0:
                # All zones nearly satisfied — trim SAT upward (save energy)
                self._current_supply_temp = min(
                    self._current_supply_temp + 0.5, sat_max
                )
            elif max_demand > 70.0:
                # At least one zone needs more cooling — respond downward
                self._current_supply_temp = max(
                    self._current_supply_temp - 0.5, sat_min
                )

            capped_append(self._history, {
                "ts": time.time(),
                "sat": self._current_supply_temp,
                "max_demand": max_demand,
                "avg_demand": avg_demand,
            })
            return self._current_supply_temp

    # -- Economizer decision ---------------------------------------------

    def economizer_decision(
        self,
        outdoor_temp: float,
        outdoor_rh: float,
        return_temp: float,
    ) -> Dict[str, Any]:
        """Return economizer mode and damper position."""
        with self._lock:
            # Enthalpy-light: if OAT < RAT and RH acceptable, use free cooling
            if outdoor_temp < return_temp - 2.0 and outdoor_rh < 70.0:
                mode = "free_cooling"
                damper_position = 100.0
            elif outdoor_temp < return_temp:
                mode = "mixed"
                # Linear interpolation based on temp delta
                delta = return_temp - outdoor_temp
                damper_position = max(
                    self.min_oa_fraction * 100.0,
                    min(100.0, 50.0 + delta * 5.0),
                )
            else:
                mode = "mechanical"
                damper_position = self.min_oa_fraction * 100.0

            result: Dict[str, Any] = {
                "mode": mode,
                "damper_position": round(damper_position, 1),
            }
            capped_append(self._history, {"ts": time.time(), **result})
            return result

    # -- Demand-controlled ventilation ------------------------------------

    def demand_controlled_ventilation(
        self,
        co2_levels: Dict[str, float],
        co2_setpoint: float = 800.0,
    ) -> Dict[str, float]:
        """Per-zone outdoor-air fraction based on CO₂ readings."""
        with self._lock:
            results: Dict[str, float] = {}
            for zone_id, co2_ppm in co2_levels.items():
                if co2_ppm <= co2_setpoint:
                    results[zone_id] = self.min_oa_fraction
                else:
                    excess_ratio = (co2_ppm - co2_setpoint) / co2_setpoint
                    oa_fraction = min(1.0, self.min_oa_fraction + excess_ratio * 0.5)
                    results[zone_id] = round(oa_fraction, 3)
            return results


# ---------------------------------------------------------------------------
# Zone Temperature Controller
# ---------------------------------------------------------------------------


class ZoneTemperatureController:
    """Heating / cooling demand for a single zone with deadband."""

    def __init__(
        self,
        zone_id: str,
        heating_setpoint: float = 70.0,
        cooling_setpoint: float = 74.0,
        deadband: float = 2.0,
    ) -> None:
        self.zone_id = zone_id
        self._lock = threading.RLock()
        self._heating_setpoint = heating_setpoint
        self._cooling_setpoint = cooling_setpoint
        self._deadband = deadband
        self._history: List[Dict[str, Any]] = []

    def compute_demand(self, current_temp: float) -> Dict[str, Any]:
        """Return mode (heating/cooling/satisfied) and demand_pct (0-100)."""
        with self._lock:
            heat_start = self._heating_setpoint - self._deadband / 2.0
            cool_start = self._cooling_setpoint + self._deadband / 2.0

            if current_temp < heat_start:
                deviation = heat_start - current_temp
                demand_pct = min(100.0, deviation / 10.0 * 100.0)
                mode = "heating"
            elif current_temp > cool_start:
                deviation = current_temp - cool_start
                demand_pct = min(100.0, deviation / 10.0 * 100.0)
                mode = "cooling"
            else:
                mode = "satisfied"
                demand_pct = 0.0

            result: Dict[str, Any] = {
                "mode": mode,
                "demand_pct": round(demand_pct, 1),
            }
            capped_append(self._history, {"ts": time.time(), **result})
            return result

    def update_setpoints(
        self,
        heating: float,
        cooling: float,
    ) -> None:
        with self._lock:
            self._heating_setpoint = heating
            self._cooling_setpoint = cooling
            logger.info(
                "Zone %s setpoints updated: heat=%.1f cool=%.1f",
                self.zone_id,
                heating,
                cooling,
            )
