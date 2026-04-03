# Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
# Design Label: EMS-005
"""Renewable integration — solar PV model, battery SOC tracker, grid dispatch."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class SolarPVSystem:
    system_id: str
    capacity_kw: float
    tilt_angle: float = 30.0
    azimuth: float = 180.0  # south-facing
    efficiency: float = 0.18
    degradation_annual_pct: float = 0.5


@dataclass
class BatterySystem:
    battery_id: str
    capacity_kwh: float
    max_charge_kw: float
    max_discharge_kw: float
    soc_pct: float = 50.0
    min_soc_pct: float = 10.0
    max_soc_pct: float = 90.0
    roundtrip_efficiency: float = 0.92


class SolarPVModel:
    """Irradiance → AC output model with temperature & degradation derates."""

    def __init__(self, system: SolarPVSystem) -> None:
        self._system = system

    def estimate_generation(
        self,
        irradiance_w_m2: float,
        ambient_temp_c: float = 25.0,
        system_age_years: float = 0,
    ) -> Dict:
        s = self._system
        # temperature coefficient: ~-0.4 %/°C above 25 °C
        temp_derate = 1.0 - max(0, (ambient_temp_c - 25.0)) * 0.004
        # age degradation
        age_derate = 1.0 - (s.degradation_annual_pct / 100.0) * system_age_years
        age_derate = max(age_derate, 0.5)  # floor at 50 %
        # DC output: irradiance fraction × capacity
        irradiance_fraction = min(irradiance_w_m2 / 1000.0, 1.2)  # STC = 1000 W/m²
        dc_kw = s.capacity_kw * irradiance_fraction
        # inverter efficiency ~96 %
        inverter_eff = 0.96
        ac_kw = dc_kw * temp_derate * age_derate * inverter_eff
        return {
            "ac_output_kw": round(max(0, ac_kw), 3),
            "dc_output_kw": round(max(0, dc_kw), 3),
            "temperature_derate": round(temp_derate, 4),
            "age_derate": round(age_derate, 4),
            "efficiency_adjusted": round(temp_derate * age_derate * inverter_eff, 4),
        }


class BatteryController:
    """SOC-aware charge / discharge with safety limits."""

    def __init__(self, battery: BatterySystem) -> None:
        self._lock = threading.RLock()
        self._bat = battery

    def charge(self, kw: float, duration_hours: float) -> Dict:
        with self._lock:
            b = self._bat
            clamped_kw = min(kw, b.max_charge_kw)
            energy = clamped_kw * duration_hours * (b.roundtrip_efficiency ** 0.5)
            room = (b.max_soc_pct - b.soc_pct) / 100.0 * b.capacity_kwh
            stored = min(energy, room)
            b.soc_pct += (stored / b.capacity_kwh) * 100.0
            return {
                "energy_stored_kwh": round(stored, 3),
                "new_soc_pct": round(b.soc_pct, 2),
            }

    def discharge(self, kw: float, duration_hours: float) -> Dict:
        with self._lock:
            b = self._bat
            clamped_kw = min(kw, b.max_discharge_kw)
            energy = clamped_kw * duration_hours
            available = (b.soc_pct - b.min_soc_pct) / 100.0 * b.capacity_kwh
            delivered = min(energy, available) * (b.roundtrip_efficiency ** 0.5)
            b.soc_pct -= (min(energy, available) / b.capacity_kwh) * 100.0
            return {
                "energy_delivered_kwh": round(delivered, 3),
                "new_soc_pct": round(b.soc_pct, 2),
            }

    def get_status(self) -> Dict:
        with self._lock:
            b = self._bat
            avail_charge = (b.max_soc_pct - b.soc_pct) / 100.0 * b.capacity_kwh
            avail_discharge = (b.soc_pct - b.min_soc_pct) / 100.0 * b.capacity_kwh
            return {
                "soc_pct": round(b.soc_pct, 2),
                "available_charge_kwh": round(max(0, avail_charge), 3),
                "available_discharge_kwh": round(max(0, avail_discharge), 3),
            }


class GridInteractiveDispatch:
    """Coordinate solar + battery + grid for cost-optimal power dispatch."""

    def __init__(
        self,
        solar: SolarPVModel,
        battery: BatteryController,
    ) -> None:
        self._solar = solar
        self._battery = battery

    def dispatch(
        self,
        load_kw: float,
        solar_kw: float,
        grid_price: float,
        battery_soc: float,
    ) -> Dict:
        surplus = solar_kw - load_kw
        bat_status = self._battery.get_status()

        if surplus > 0:
            # excess solar — charge battery or export
            if bat_status["available_charge_kwh"] > 0:
                return {
                    "grid_import_kw": 0.0,
                    "grid_export_kw": 0.0,
                    "battery_action": "charge",
                    "battery_kw": round(min(surplus, self._battery._bat.max_charge_kw), 2),
                    "cost_usd_per_hour": 0.0,
                }
            return {
                "grid_import_kw": 0.0,
                "grid_export_kw": round(surplus, 2),
                "battery_action": "idle",
                "battery_kw": 0.0,
                "cost_usd_per_hour": round(-surplus * grid_price * 0.5, 4),  # export credit
            }

        deficit = -surplus  # positive = we need more power
        # high price + battery available → discharge
        if grid_price > 0.15 and bat_status["available_discharge_kwh"] > 0.5:
            bat_kw = min(deficit, self._battery._bat.max_discharge_kw)
            grid_kw = max(0, deficit - bat_kw)
            return {
                "grid_import_kw": round(grid_kw, 2),
                "grid_export_kw": 0.0,
                "battery_action": "discharge",
                "battery_kw": round(bat_kw, 2),
                "cost_usd_per_hour": round(grid_kw * grid_price, 4),
            }

        return {
            "grid_import_kw": round(deficit, 2),
            "grid_export_kw": 0.0,
            "battery_action": "idle",
            "battery_kw": 0.0,
            "cost_usd_per_hour": round(deficit * grid_price, 4),
        }
