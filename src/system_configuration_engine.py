"""
System Configuration Engine
============================
Detects automation system type from description, selects optimal
control strategy using pro/con weighting, and applies MSS configuration
modes (Magnify / Simplify / Solidify).

Copyright (c) 2020 Inoni Limited Liability Company  Creator: Corey Post
License: BSL 1.1
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SystemType(str, Enum):
    AHU = "ahu"
    RTU = "rtu"
    FCU = "fcu"
    VAV_BOX = "vav_box"
    CHILLER_PLANT = "chiller_plant"
    BOILER_PLANT = "boiler_plant"
    COOLING_TOWER = "cooling_tower"
    HEAT_PUMP = "heat_pump"
    VRF_SYSTEM = "vrf_system"
    RADIANT_SYSTEM = "radiant_system"
    DOAS = "doas"
    HEAT_EXCHANGER = "heat_exchanger"
    ELECTRICAL_PANEL = "electrical_panel"
    PLC_SYSTEM = "plc_system"
    SCADA_SYSTEM = "scada_system"
    GENERIC = "generic"


@dataclass
class ControlStrategy:
    strategy_id: str = ""
    name: str = ""
    system_type: SystemType = SystemType.GENERIC
    description: str = ""
    setpoints: Dict[str, Any] = field(default_factory=dict)
    sequence_of_operations: List[str] = field(default_factory=list)
    energy_efficiency_rating: str = "standard"
    applicable_standards: List[str] = field(default_factory=list)
    prerequisites: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    pros: List[str] = field(default_factory=list)
    cons: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_id": self.strategy_id, "name": self.name,
            "system_type": self.system_type.value if hasattr(self.system_type, "value") else str(self.system_type),
            "description": self.description, "setpoints": self.setpoints,
            "sequence_of_operations": self.sequence_of_operations,
            "energy_efficiency_rating": self.energy_efficiency_rating,
            "applicable_standards": self.applicable_standards,
            "recommendations": self.recommendations,
            "pros": self.pros, "cons": self.cons,
        }


@dataclass
class SystemConfiguration:
    config_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    system_type: SystemType = SystemType.GENERIC
    system_name: str = ""
    strategy: Optional[ControlStrategy] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    setpoints: Dict[str, Any] = field(default_factory=dict)
    schedules: Dict[str, Any] = field(default_factory=dict)
    alarms: Dict[str, Any] = field(default_factory=dict)
    verified: bool = False
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "config_id": self.config_id,
            "system_type": self.system_type.value if hasattr(self.system_type, "value") else str(self.system_type),
            "system_name": self.system_name,
            "strategy": self.strategy.to_dict() if self.strategy else None,
            "parameters": self.parameters, "setpoints": self.setpoints,
            "schedules": self.schedules, "alarms": self.alarms,
            "verified": self.verified, "created_at": self.created_at,
        }


STRATEGY_TEMPLATES: Dict[SystemType, List[ControlStrategy]] = {
    SystemType.AHU: [
        ControlStrategy(
            "ahu_cav", "Constant Air Volume (CAV)", SystemType.AHU,
            "Fixed supply airflow with variable temperature control.",
            {"supply_air_temp_sp": 55.0, "min_oa_fraction": 0.20, "filter_dp_alarm": 1.0},
            ["Enable on occupancy schedule","Modulate cooling valve to maintain SAT 55F","Stage heating on low-limit","Monitor filter DP alarm at 1.0 inwg","Disable on unoccupied schedule"],
            "standard", ["ASHRAE 90.1","ASHRAE 62.1"], [],
            ["Consider VAV retrofit for 20-30% fan energy savings"],
            pros=["Simple controls","Low first cost","Reliable"],
            cons=["Higher energy use than VAV","Overcooling risk","No part-load benefit"],
        ),
        ControlStrategy(
            "ahu_vav", "Variable Air Volume (VAV) with Supply Air Reset", SystemType.AHU,
            "Variable airflow with SAT reset per ASHRAE Guideline 36.",
            {"supply_air_temp_sp": 55.0, "sat_reset_max": 65.0, "min_oa_fraction": 0.15, "duct_static_sp": 1.0},
            ["Enable on schedule","Modulate VFD to maintain duct static setpoint","Reset SAT based on zone demand (Guideline 36)","DCV via CO2 if occupancy varies","Occupied/unoccupied setback"],
            "high-performance", ["ASHRAE 90.1 s6.5","ASHRAE Guideline 36","ASHRAE 62.1"], [],
            ["Target 30-40% fan energy savings vs CAV","Commission SAT reset sequence carefully"],
            pros=["30-40% fan energy savings","Reduced reheat","Zone comfort"],
            cons=["Higher complexity","Requires VFD","Commissioning intensive"],
        ),
    ],
    SystemType.RTU: [
        ControlStrategy(
            "rtu_standard", "Standard RTU Control", SystemType.RTU,
            "Single-zone thermostat control with economizer.",
            {"cooling_sp": 74.0, "heating_sp": 70.0, "deadband": 4.0},
            ["Enable on occupancy schedule","Stage compressors for cooling","Stage gas heat for heating","Airside economizer when OA suitable","Unoccupied setback"],
            "standard", ["ASHRAE 90.1 s6.4.3"], [],
            ["Add DCV sensor for occupancy-based ventilation savings"],
            pros=["Simple","Low maintenance","Self-contained"],
            cons=["Less efficient than chilled water","Single-zone only"],
        ),
        ControlStrategy(
            "rtu_econom", "RTU with Integrated Economizer and DCV", SystemType.RTU,
            "High-performance RTU with differential enthalpy economizer and DCV.",
            {"cooling_sp": 74.0, "heating_sp": 70.0, "co2_sp": 1100, "deadband": 4.0},
            ["Enable on schedule","Differential enthalpy economizer","DCV via CO2 sensor","Demand-based defrost for heat pump","Unoccupied setback"],
            "efficient", ["ASHRAE 90.1 s6.5.1","ASHRAE 62.1 s6.2.7"], [],
            ["15-20% energy savings vs standard RTU"],
            pros=["15-20% savings","Better IAQ","Code compliant"],
            cons=["Higher cost","Enthalpy sensor maintenance"],
        ),
    ],
    SystemType.CHILLER_PLANT: [
        ControlStrategy(
            "chiller_fixed_sp", "Fixed Chilled Water Supply Temperature", SystemType.CHILLER_PLANT,
            "Constant 44F CHWS with load-based chiller staging.",
            {"chws_temp_sp": 44.0, "delta_t_target": 12.0, "staging_threshold_pct": 85},
            ["Stage chillers at 85% load of lead unit","Maintain 44F CHWS","Monitor delta-T; alarm below 8F","Lead/lag rotation weekly","Night setback to 46F unoccupied"],
            "standard", ["ASHRAE Guideline 22"], [],
            ["Consider CHWS reset for 3-5% additional savings"],
            pros=["Simple","Reliable","Low risk"],
            cons=["Not optimal part-load efficiency"],
        ),
        ControlStrategy(
            "chiller_reset", "Chilled Water Supply Reset with Optimal Start", SystemType.CHILLER_PLANT,
            "CHWS reset based on building load with load-based staging per ASHRAE Guideline 22.",
            {"chws_temp_sp_min": 44.0, "chws_temp_sp_max": 56.0, "delta_t_target": 14.0},
            ["Reset CHWS temp based on highest zone demand","Stage chillers by efficiency curve","Optimize delta-T to 14F","VSD pumps track differential pressure","Cooling tower approach optimisation"],
            "high-performance", ["ASHRAE 90.1 s6.5.2","ASHRAE Guideline 22","ASHRAE Guideline 36"], [],
            ["8-12% chiller energy savings vs fixed setpoint"],
            pros=["8-12% chiller savings","Better part-load efficiency","Reduced pump energy"],
            cons=["More complex","Requires careful commissioning"],
        ),
    ],
    SystemType.BOILER_PLANT: [
        ControlStrategy(
            "boiler_outdoor_reset", "Hot Water Supply Temperature Outdoor Reset", SystemType.BOILER_PLANT,
            "HWS temperature reset based on outdoor air temperature.",
            {"hws_temp_design": 180.0, "hws_temp_min": 120.0, "oa_design": 0.0, "oa_high": 60.0},
            ["Reset HWS from 180F at 0F OA to 120F at 60F OA","Stage boilers by efficiency","O2 trim on lead boiler","Low-limit freeze protection at 35F OA","Boiler rotation monthly"],
            "efficient", ["ASHRAE 90.1","ASHRAE Guideline 1.3"], [],
            ["Outdoor reset saves 5-10% on gas consumption"],
            pros=["5-10% gas savings","Reduces boiler cycling","Condensing mode at low HWS"],
            cons=["Requires OA sensor","Reheat zones need recalibration"],
        ),
    ],
    SystemType.VAV_BOX: [
        ControlStrategy(
            "vav_pressure_independent", "Pressure-Independent VAV with Reheat", SystemType.VAV_BOX,
            "Pressure-independent VAV with hot-water or electric reheat per Guideline 36.",
            {"cooling_max_cfm": 500, "heating_min_cfm": 150, "heating_sp": 70.0, "cooling_sp": 74.0},
            ["Modulate airflow between min and max for cooling","Reheat at minimum airflow for heating","DCV min OA per CO2","Override to max on smoke alarm","Unoccupied setback"],
            "high-performance", ["ASHRAE Guideline 36 s5.7","ASHRAE 62.1"], [],
            ["Commission deadband carefully to avoid hunting"],
            pros=["Individual zone control","Energy efficient","ASHRAE 62.1 compliant"],
            cons=["Many control points","Commissioning intensive"],
        ),
    ],
    SystemType.PLC_SYSTEM: [
        ControlStrategy(
            "plc_standard", "Standard PLC Process Control", SystemType.PLC_SYSTEM,
            "Ladder logic PLC with HMI for process control.",
            {"scan_rate_ms": 100, "watchdog_timeout_ms": 500},
            ["Execute ladder logic at 100ms scan rate","Watchdog timer resets on comm loss","Hardwired safety interlocks independent of PLC","Alarm annunciation to HMI","Historian logging at 1-sec resolution"],
            "standard", ["ISA-88","IEC 61131-3","NFPA 70E"], [],
            ["Consider safety PLC (SIL-2) for critical interlock functions"],
            pros=["Deterministic control","Industry standard","Reliable"],
            cons=["Proprietary programming","Limited integration without OPC-UA"],
        ),
    ],
    SystemType.SCADA_SYSTEM: [
        ControlStrategy(
            "scada_supervisory", "Supervisory SCADA with Historian", SystemType.SCADA_SYSTEM,
            "SCADA with OPC-UA data collection, historian, and dashboard.",
            {"poll_rate_ms": 1000, "historian_compression_deadband": 0.5},
            ["Poll field devices via OPC-UA at 1-sec intervals","Store data in historian with compression","Display real-time dashboards","Alarm management per ISA-18.2","Generate periodic KPI reports"],
            "standard", ["ISA-18.2","IEC 62541 OPC-UA","NERC CIP (utility)"], [],
            ["Implement cybersecurity hardening per NERC CIP or IEC 62443"],
            pros=["Unified visibility","Historical trending","Alarm management"],
            cons=["Complex integration","Cybersecurity exposure","High maintenance"],
        ),
    ],
}

# Fill remaining system types with generic strategies
for _st in SystemType:
    if _st not in STRATEGY_TEMPLATES:
        STRATEGY_TEMPLATES[_st] = [
            ControlStrategy(
                f"{_st.value}_generic", f"Standard {_st.value.replace('_',' ').title()} Control",
                _st, f"Standard control sequence for {_st.value}.",
                {"enable_schedule": "occupied_hours"},
                ["Enable on occupancy schedule","Monitor primary sensors","Alarm on out-of-range condition","Disable unoccupied"],
                "standard", ["ASHRAE 90.1"], [], [],
                pros=["Simple","Reliable"], cons=["Not optimised for efficiency"],
            )
        ]

# keyword -> SystemType detection
_TYPE_KEYWORDS: Dict[str, SystemType] = {
    "air handling unit": SystemType.AHU, "ahu": SystemType.AHU,
    "rooftop unit": SystemType.RTU, "rtu": SystemType.RTU, "rooftop": SystemType.RTU,
    "fan coil unit": SystemType.FCU, "fcu": SystemType.FCU, "fan coil": SystemType.FCU,
    "vav box": SystemType.VAV_BOX, "vav": SystemType.VAV_BOX, "variable air volume": SystemType.VAV_BOX,
    "chiller": SystemType.CHILLER_PLANT, "chilled water": SystemType.CHILLER_PLANT,
    "boiler": SystemType.BOILER_PLANT, "hot water": SystemType.BOILER_PLANT,
    "cooling tower": SystemType.COOLING_TOWER,
    "heat pump": SystemType.HEAT_PUMP,
    "vrf": SystemType.VRF_SYSTEM, "variable refrigerant": SystemType.VRF_SYSTEM,
    "radiant": SystemType.RADIANT_SYSTEM,
    "doas": SystemType.DOAS, "dedicated outdoor air": SystemType.DOAS,
    "heat exchanger": SystemType.HEAT_EXCHANGER,
    "electrical panel": SystemType.ELECTRICAL_PANEL, "panelboard": SystemType.ELECTRICAL_PANEL,
    "plc": SystemType.PLC_SYSTEM, "programmable logic": SystemType.PLC_SYSTEM,
    "scada": SystemType.SCADA_SYSTEM,
}


class SystemConfigurationEngine:
    """Detect system type, select strategy, apply MSS modes."""

    def detect_system_type(self, description: str,
                            points: Optional[List[Dict[str, Any]]] = None) -> SystemType:
        desc_lower = description.lower()
        for keyword, sys_type in _TYPE_KEYWORDS.items():
            if keyword in desc_lower:
                return sys_type
        return SystemType.GENERIC

    def get_strategies(self, system_type: SystemType) -> List[ControlStrategy]:
        return list(STRATEGY_TEMPLATES.get(system_type, []))

    def recommend_strategy(self, system_type: SystemType,
                            context: Optional[Dict[str, Any]] = None) -> ControlStrategy:
        strategies = self.get_strategies(system_type)
        if not strategies:
            return ControlStrategy(f"{system_type.value}_fallback","Generic Control",system_type)
        ctx = context or {}
        # Pro/con scoring: prefer high-performance when energy matters
        energy_priority = ctx.get("energy_priority", False)
        def score(s: ControlStrategy) -> float:
            base = len(s.pros) - len(s.cons) * 0.5
            if energy_priority and s.energy_efficiency_rating == "high-performance":
                base += 3.0
            if "standard" in s.energy_efficiency_rating:
                base -= 0.5
            return base
        return sorted(strategies, key=score, reverse=True)[0]

    def configure(self, system_type: SystemType, strategy_id: str,
                  user_inputs: Optional[Dict[str, Any]] = None) -> SystemConfiguration:
        strategies = self.get_strategies(system_type)
        strategy = next((s for s in strategies if s.strategy_id == strategy_id), None)
        if strategy is None and strategies:
            strategy = strategies[0]
        inputs = user_inputs or {}
        setpoints = dict(strategy.setpoints) if strategy else {}
        setpoints.update(inputs.get("setpoints", {}))
        return SystemConfiguration(
            system_type=system_type,
            system_name=inputs.get("system_name", strategy_id),
            strategy=strategy,
            parameters=inputs.get("parameters", {}),
            setpoints=setpoints,
            schedules=inputs.get("schedules", {"occupied": "07:00-19:00", "weekend": "09:00-17:00"}),
            alarms=inputs.get("alarms", {"comm_failure": "critical", "sensor_fault": "high"}),
        )

    def magnify(self, config: SystemConfiguration) -> Dict[str, Any]:
        s = config.strategy
        return {
            "all_setpoints": config.setpoints,
            "full_sequence": s.sequence_of_operations if s else [],
            "all_alarms": config.alarms,
            "monitoring_points": list(config.setpoints.keys()),
            "standards": s.applicable_standards if s else [],
            "recommendations": s.recommendations if s else [],
            "pros": s.pros if s else [],
            "cons": s.cons if s else [],
        }

    def simplify(self, config: SystemConfiguration) -> Dict[str, Any]:
        s = config.strategy
        critical_sp = {k: v for k, v in config.setpoints.items() if any(
            kw in k.lower() for kw in ["sp","setpoint","alarm","limit"]
        )}
        return {
            "critical_setpoints": critical_sp or config.setpoints,
            "safety_alarms": {k: v for k, v in config.alarms.items() if v in ("critical","high")},
            "key_sequence_steps": (s.sequence_of_operations[:3] if s else []),
        }

    def solidify(self, config: SystemConfiguration) -> Dict[str, Any]:
        return {
            "config_id": config.config_id,
            "version": "1.0",
            "locked_setpoints": config.setpoints,
            "locked_schedules": config.schedules,
            "change_control": "require_approval",
            "created_at": config.created_at,
            "strategy_id": config.strategy.strategy_id if config.strategy else "unknown",
        }
