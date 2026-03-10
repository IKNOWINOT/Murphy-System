"""
Murphy System - Murphy Engineering Toolbox
Copyright 2024-2026 Corey Post, Inoni LLC
License: BSL 1.1
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Unit Converter
# ---------------------------------------------------------------------------

class UnitConverter:
    """Comprehensive unit conversion across engineering domains."""

    # Conversion factors to SI base unit
    _LENGTH = {
        "m": 1.0, "km": 1000.0, "cm": 0.01, "mm": 0.001,
        "in": 0.0254, "ft": 0.3048, "yd": 0.9144, "mi": 1609.344,
    }
    _AREA = {
        "m2": 1.0, "cm2": 1e-4, "mm2": 1e-6,
        "in2": 6.4516e-4, "ft2": 0.09290304, "yd2": 0.83612736,
    }
    _VOLUME = {
        "m3": 1.0, "L": 1e-3, "mL": 1e-6, "gal": 3.785411784e-3,
        "ft3": 0.028316847, "in3": 1.6387064e-5,
    }
    _MASS = {
        "kg": 1.0, "g": 1e-3, "mg": 1e-6, "lb": 0.45359237,
        "oz": 0.028349523, "ton": 907.18474, "tonne": 1000.0,
    }
    _FORCE = {
        "N": 1.0, "kN": 1000.0, "lbf": 4.44822162, "kip": 4448.22162,
    }
    _PRESSURE = {
        "Pa": 1.0, "kPa": 1000.0, "MPa": 1e6, "GPa": 1e9,
        "psi": 6894.757, "ksi": 6894757.0, "atm": 101325.0, "bar": 1e5,
    }
    _ENERGY = {
        "J": 1.0, "kJ": 1000.0, "MJ": 1e6, "Wh": 3600.0, "kWh": 3.6e6,
        "BTU": 1055.056, "therm": 1.055056e8, "cal": 4.184,
    }
    _POWER = {
        "W": 1.0, "kW": 1000.0, "MW": 1e6, "hp": 745.69987, "BTU/hr": 0.29307107,
    }
    _FLOW = {
        "m3/s": 1.0, "L/s": 1e-3, "gpm": 6.30902e-5, "cfm": 4.71947e-4,
    }
    _VELOCITY = {
        "m/s": 1.0, "km/h": 1/3.6, "mph": 0.44704, "ft/s": 0.3048,
        "knot": 0.514444,
    }

    _TABLES: Dict[str, Dict[str, float]] = {
        "length": _LENGTH,
        "area": _AREA,
        "volume": _VOLUME,
        "mass": _MASS,
        "force": _FORCE,
        "pressure": _PRESSURE,
        "energy": _ENERGY,
        "power": _POWER,
        "flow": _FLOW,
        "velocity": _VELOCITY,
    }

    def convert(self, value: float, from_unit: str, to_unit: str) -> float:
        """Convert a value between compatible units."""
        for table in self._TABLES.values():
            if from_unit in table and to_unit in table:
                si_value = value * table[from_unit]
                return si_value / table[to_unit]
        # Temperature (special case)
        if from_unit in ("C", "F", "K") and to_unit in ("C", "F", "K"):
            return self._convert_temperature(value, from_unit, to_unit)
        raise ValueError(f"Cannot convert {from_unit!r} to {to_unit!r}: incompatible or unknown units")

    def _convert_temperature(self, value: float, from_unit: str, to_unit: str) -> float:
        # To Kelvin first
        if from_unit == "C":
            kelvin = value + 273.15
        elif from_unit == "F":
            kelvin = (value - 32) * 5 / 9 + 273.15
        else:
            kelvin = value
        # From Kelvin to target
        if to_unit == "C":
            return kelvin - 273.15
        elif to_unit == "F":
            return (kelvin - 273.15) * 9 / 5 + 32
        return kelvin

    def available_units(self, category: str) -> List[str]:
        return list(self._TABLES.get(category, {}).keys())


# ---------------------------------------------------------------------------
# Structural Calculations
# ---------------------------------------------------------------------------

@dataclass
class BeamResult:
    """Result container for beam computation."""
    max_deflection_m: float
    max_moment_Nm: float
    max_shear_N: float
    factor_of_safety: float
    description: str


class StructuralCalcs:
    """Beam deflection, moment of inertia, section modulus, stress/strain."""

    def simple_beam_deflection(
        self,
        load_N: float,
        span_m: float,
        E_Pa: float,
        I_m4: float,
        load_type: str = "center",
    ) -> BeamResult:
        """
        Compute maximum deflection for a simply-supported beam.
        load_type: 'center' (point load at center) or 'uniform' (UDL)
        """
        if load_type == "center":
            delta = (load_N * span_m ** 3) / (48 * E_Pa * I_m4)
            M_max = load_N * span_m / 4
            V_max = load_N / 2
        else:  # uniform distributed load
            w = load_N / span_m  # N/m
            delta = (5 * w * span_m ** 4) / (384 * E_Pa * I_m4)
            M_max = w * span_m ** 2 / 8
            V_max = w * span_m / 2

        return BeamResult(
            max_deflection_m=delta,
            max_moment_Nm=M_max,
            max_shear_N=V_max,
            factor_of_safety=1.0,  # FOS calculated separately with allowable stress
            description=f"Simple beam, {load_type} load",
        )

    def cantilever_deflection(
        self,
        load_N: float,
        span_m: float,
        E_Pa: float,
        I_m4: float,
    ) -> BeamResult:
        """Cantilever beam with point load at free end."""
        delta = (load_N * span_m ** 3) / (3 * E_Pa * I_m4)
        M_max = load_N * span_m
        V_max = load_N
        return BeamResult(
            max_deflection_m=delta,
            max_moment_Nm=M_max,
            max_shear_N=V_max,
            factor_of_safety=1.0,
            description="Cantilever beam, tip load",
        )

    def rectangular_moment_of_inertia(self, width_m: float, height_m: float) -> float:
        """Moment of inertia for a rectangular cross-section about the neutral axis."""
        return (width_m * height_m ** 3) / 12

    def section_modulus(self, I_m4: float, c_m: float) -> float:
        """Section modulus S = I / c."""
        return I_m4 / c_m if c_m != 0 else 0.0

    def bending_stress(self, moment_Nm: float, I_m4: float, c_m: float) -> float:
        """Maximum bending stress σ = M·c / I  (Pa)."""
        return (moment_Nm * c_m) / I_m4 if I_m4 != 0 else 0.0

    def factor_of_safety(self, allowable_stress_Pa: float, actual_stress_Pa: float) -> float:
        """Factor of safety = allowable / actual."""
        return allowable_stress_Pa / actual_stress_Pa if actual_stress_Pa != 0 else float("inf")


# ---------------------------------------------------------------------------
# HVAC Calculations
# ---------------------------------------------------------------------------

@dataclass
class HeatLoadResult:
    """Result container for heatload computation."""
    sensible_load_W: float
    latent_load_W: float
    total_load_W: float
    total_load_BTU_hr: float
    recommended_tonnage: float


class HVACCalcs:
    """Heat load, CFM sizing, duct sizing, psychrometric calculations."""

    def simple_heat_load(
        self,
        area_m2: float,
        delta_T_K: float,
        u_value_W_m2K: float = 0.5,
        occupants: int = 0,
        lighting_W_m2: float = 10.0,
        equipment_W: float = 0.0,
    ) -> HeatLoadResult:
        """Simplified ASHRAE heat load calculation."""
        envelope_load = area_m2 * u_value_W_m2K * delta_T_K
        occupant_sensible = occupants * 75  # W per person (ASHRAE)
        occupant_latent = occupants * 55   # W per person
        lighting_load = area_m2 * lighting_W_m2
        sensible = envelope_load + occupant_sensible + lighting_load + equipment_W
        latent = float(occupant_latent)
        total = sensible + latent
        btu_hr = total * 3.41214
        tonnage = total / 3517.0  # 1 ton = 3517 W
        return HeatLoadResult(
            sensible_load_W=round(sensible, 1),
            latent_load_W=round(latent, 1),
            total_load_W=round(total, 1),
            total_load_BTU_hr=round(btu_hr, 1),
            recommended_tonnage=round(tonnage, 2),
        )

    def cfm_from_load(self, load_W: float, delta_T_K: float = 8.0) -> float:
        """Required CFM from sensible heat load. Q = 1.1 × CFM × ΔT (BTU/hr, ΔT in °F)."""
        btu_hr = load_W * 3.41214
        delta_T_F = delta_T_K * 9 / 5
        cfm = btu_hr / (1.1 * delta_T_F) if delta_T_F != 0 else 0.0
        return round(cfm, 1)

    def dew_point(self, dry_bulb_C: float, relative_humidity_pct: float) -> float:
        """Magnus formula approximation for dew point (°C)."""
        rh = relative_humidity_pct / 100
        a, b = 17.27, 237.7
        alpha = (a * dry_bulb_C / (b + dry_bulb_C)) + math.log(max(rh, 1e-6))
        return (b * alpha) / (a - alpha)

    def enthalpy(self, dry_bulb_C: float, humidity_ratio: float) -> float:
        """Specific enthalpy of moist air (kJ/kg dry air)."""
        return 1.006 * dry_bulb_C + humidity_ratio * (2501 + 1.86 * dry_bulb_C)


# ---------------------------------------------------------------------------
# Electrical Calculations
# ---------------------------------------------------------------------------

@dataclass
class ElectricalResult:
    """Result container for electrical computation."""
    value: float
    unit: str
    description: str


class ElectricalCalcs:
    """Ohm's law, power factor, voltage drop, wire sizing."""

    def ohms_law(
        self,
        voltage_V: Optional[float] = None,
        current_A: Optional[float] = None,
        resistance_ohm: Optional[float] = None,
    ) -> Dict[str, float]:
        """Solve Ohm's law for the missing variable. Provide any two of V, I, R."""
        if voltage_V is None and current_A is not None and resistance_ohm is not None:
            return {"voltage_V": current_A * resistance_ohm}
        elif current_A is None and voltage_V is not None and resistance_ohm is not None:
            return {"current_A": voltage_V / resistance_ohm if resistance_ohm != 0 else 0.0}
        elif resistance_ohm is None and voltage_V is not None and current_A is not None:
            return {"resistance_ohm": voltage_V / current_A if current_A != 0 else float("inf")}
        raise ValueError("Provide exactly two of: voltage_V, current_A, resistance_ohm")

    def power(self, voltage_V: float, current_A: float, power_factor: float = 1.0) -> Dict[str, float]:
        """Compute apparent, real, and reactive power."""
        apparent_VA = voltage_V * current_A
        real_W = apparent_VA * power_factor
        reactive_VAR = math.sqrt(max(0.0, apparent_VA ** 2 - real_W ** 2))
        return {
            "apparent_VA": round(apparent_VA, 3),
            "real_W": round(real_W, 3),
            "reactive_VAR": round(reactive_VAR, 3),
        }

    def voltage_drop(
        self,
        current_A: float,
        resistance_per_m_ohm: float,
        length_m: float,
        phases: int = 1,
    ) -> float:
        """Voltage drop V = I × R × L × phase_factor."""
        phase_factor = 2.0 if phases == 1 else math.sqrt(3)
        return current_A * resistance_per_m_ohm * length_m * phase_factor

    def motor_fla(self, hp: float, voltage_V: float, efficiency: float = 0.9, pf: float = 0.85) -> float:
        """Estimate full-load amperage of a motor."""
        watts = hp * 745.7
        return watts / (voltage_V * efficiency * pf) if (voltage_V * efficiency * pf) != 0 else 0.0


# ---------------------------------------------------------------------------
# Plumbing Calculations
# ---------------------------------------------------------------------------

class PlumbingCalcs:
    """Fixture unit counts, pipe sizing, water heater sizing."""

    # Simplified fixture unit table (WSFU)
    _FIXTURE_UNITS = {
        "toilet": 4,
        "lavatory": 1,
        "bathtub": 2,
        "shower": 2,
        "kitchen_sink": 2,
        "dishwasher": 2,
        "clothes_washer": 4,
        "urinal": 5,
        "service_sink": 3,
        "hose_bib": 5,
    }

    def fixture_units(self, fixture_counts: Dict[str, int]) -> int:
        """Compute total water supply fixture units."""
        total = 0
        for fixture, count in fixture_counts.items():
            total += self._FIXTURE_UNITS.get(fixture, 1) * count
        return total

    def demand_gpm(self, total_wsfu: int) -> float:
        """Estimate peak demand (gpm) from total WSFU using Hunter's curve approximation."""
        if total_wsfu <= 0:
            return 0.0
        # Simplified Hunter's curve approximation
        if total_wsfu <= 10:
            return 2.5 + 0.1 * total_wsfu
        elif total_wsfu <= 100:
            return 6.0 + 0.05 * total_wsfu
        else:
            return 10.0 + 0.02 * total_wsfu

    def water_heater_sizing_gal(self, occupants: int, usage_gal_per_person: float = 20.0) -> float:
        """Size a storage water heater based on occupancy."""
        return occupants * usage_gal_per_person * 0.7  # 70% first-hour factor


# ---------------------------------------------------------------------------
# Project Management Calculations
# ---------------------------------------------------------------------------

@dataclass
class CPMActivity:
    """CPM activity node for critical-path scheduling."""
    activity_id: str
    name: str
    duration: float
    predecessors: List[str] = field(default_factory=list)
    early_start: float = 0.0
    early_finish: float = 0.0
    late_start: float = 0.0
    late_finish: float = 0.0
    total_float: float = 0.0
    on_critical_path: bool = False


class ProjectManagement:
    """Critical path method and earned value calculations."""

    def critical_path(self, activities: List[CPMActivity]) -> Tuple[List[str], float]:
        """
        Compute critical path using forward/backward pass.
        Returns (critical_path_ids, total_duration).
        """
        activity_map = {a.activity_id: a for a in activities}

        # Forward pass
        for act in activities:
            if not act.predecessors:
                act.early_start = 0.0
            else:
                act.early_start = max(
                    activity_map[p].early_finish
                    for p in act.predecessors
                    if p in activity_map
                )
            act.early_finish = act.early_start + act.duration

        total_duration = max(a.early_finish for a in activities) if activities else 0.0

        # Backward pass
        for act in reversed(activities):
            successors = [a for a in activities if act.activity_id in a.predecessors]
            if not successors:
                act.late_finish = total_duration
            else:
                act.late_finish = min(s.late_start for s in successors)
            act.late_start = act.late_finish - act.duration
            act.total_float = act.late_start - act.early_start
            act.on_critical_path = abs(act.total_float) < 1e-6

        critical = [a.activity_id for a in activities if a.on_critical_path]
        return critical, total_duration

    def earned_value(
        self,
        budget_at_completion: float,
        planned_value: float,
        earned_value_pct: float,
        actual_cost: float,
    ) -> Dict[str, float]:
        """Compute EVM metrics: CPI, SPI, EAC, ETC, VAC."""
        ev = budget_at_completion * (earned_value_pct / 100)
        cpi = ev / actual_cost if actual_cost != 0 else float("inf")
        spi = ev / planned_value if planned_value != 0 else float("inf")
        eac = budget_at_completion / cpi if cpi not in (0.0, float("inf")) else float("inf")
        etc = eac - actual_cost if eac != float("inf") else float("inf")
        vac = budget_at_completion - eac if eac != float("inf") else float("-inf")
        cv = ev - actual_cost
        sv = ev - planned_value
        return {
            "EV": round(ev, 2),
            "PV": round(planned_value, 2),
            "AC": round(actual_cost, 2),
            "CPI": round(cpi, 4) if cpi != float("inf") else None,
            "SPI": round(spi, 4) if spi != float("inf") else None,
            "EAC": round(eac, 2) if eac != float("inf") else None,
            "ETC": round(etc, 2) if etc != float("inf") else None,
            "VAC": round(vac, 2) if vac != float("-inf") else None,
            "CV": round(cv, 2),
            "SV": round(sv, 2),
        }


# ---------------------------------------------------------------------------
# Cost Estimation
# ---------------------------------------------------------------------------

class CostEstimation:
    """RS Means-style unit cost database and quantity takeoff."""

    def __init__(self, unit_costs: Optional[Dict[str, float]] = None) -> None:
        # Default unit costs in USD per unit (user-configurable)
        self._unit_costs: Dict[str, float] = unit_costs or {
            "concrete_m3": 180.0,
            "rebar_kg": 1.20,
            "structural_steel_kg": 2.50,
            "drywall_m2": 15.0,
            "insulation_m2": 8.0,
            "copper_pipe_m": 25.0,
            "conduit_m": 5.0,
            "wire_m": 2.50,
            "hvac_ton": 1800.0,
        }
        self._markup_pct: float = 15.0
        self._overhead_pct: float = 10.0

    def set_unit_cost(self, item: str, cost_per_unit: float) -> None:
        self._unit_costs[item] = cost_per_unit

    def estimate(
        self, quantities: Dict[str, float], markup_pct: Optional[float] = None
    ) -> Dict[str, Any]:
        """Compute cost estimate from a quantity takeoff dict."""
        line_items: List[Dict[str, Any]] = []
        subtotal = 0.0
        for item, qty in quantities.items():
            unit_cost = self._unit_costs.get(item, 0.0)
            cost = qty * unit_cost
            line_items.append({"item": item, "quantity": qty, "unit_cost": unit_cost, "cost": round(cost, 2)})
            subtotal += cost

        markup = markup_pct if markup_pct is not None else self._markup_pct
        overhead = subtotal * self._overhead_pct / 100
        profit = subtotal * markup / 100
        total = subtotal + overhead + profit

        return {
            "line_items": line_items,
            "subtotal": round(subtotal, 2),
            "overhead": round(overhead, 2),
            "markup_pct": markup,
            "profit": round(profit, 2),
            "total": round(total, 2),
        }


# ---------------------------------------------------------------------------
# Reference Data
# ---------------------------------------------------------------------------

class ReferenceData:
    """Material properties, standard sizes, code references."""

    MATERIALS: Dict[str, Dict[str, Any]] = {
        "steel_A36": {"E_GPa": 200, "yield_MPa": 250, "ultimate_MPa": 400, "density_kg_m3": 7850},
        "aluminum_6061": {"E_GPa": 69, "yield_MPa": 276, "ultimate_MPa": 310, "density_kg_m3": 2700},
        "copper": {"E_GPa": 117, "yield_MPa": 70, "ultimate_MPa": 220, "density_kg_m3": 8960},
        "concrete_4000psi": {"E_GPa": 29.7, "compressive_MPa": 27.6, "density_kg_m3": 2400},
        "wood_douglas_fir": {"E_GPa": 12.4, "bending_MPa": 15.2, "density_kg_m3": 530},
    }

    STANDARD_PIPE_SIZES_IN: List[float] = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0, 4.0, 6.0, 8.0, 10.0, 12.0]

    CODE_REFERENCES: Dict[str, str] = {
        "structural_steel": "AISC 360-22 Specification for Structural Steel Buildings",
        "concrete": "ACI 318-19 Building Code for Structural Concrete",
        "electrical": "NFPA 70 NEC 2023 National Electrical Code",
        "plumbing": "IPC 2021 International Plumbing Code",
        "hvac": "ASHRAE 90.1-2022 Energy Standard for Buildings",
        "fire": "NFPA 13-2022 Standard for Sprinkler Systems",
    }

    @classmethod
    def get_material(cls, name: str) -> Optional[Dict[str, Any]]:
        return cls.MATERIALS.get(name)

    @classmethod
    def list_materials(cls) -> List[str]:
        return list(cls.MATERIALS.keys())
