"""
Energy Efficiency Framework — CEM-Level Analysis
=================================================
Implements Certified Energy Manager (CEM) standard practices:
  * ECM catalog (25 measures across all categories)
  * ASHRAE Level I / II / III audit structures
  * Utility analysis with EUI calculation
  * MSS rubric integration (Magnify / Simplify / Solidify)
  * ROI and NPV calculations per IPMVP

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


class ECMCategory(str, Enum):
    HVAC = "hvac"
    LIGHTING = "lighting"
    ENVELOPE = "envelope"
    CONTROLS = "controls"
    RENEWABLE = "renewable"
    PROCESS = "process"
    WATER = "water"
    COMPRESSED_AIR = "compressed_air"
    STEAM = "steam"
    BEHAVIORAL = "behavioral"


@dataclass
class EnergyConservationMeasure:
    ecm_id: str = ""
    name: str = ""
    category: ECMCategory = ECMCategory.HVAC
    description: str = ""
    typical_savings_pct: float = 0.0
    typical_payback_years: float = 3.0
    implementation_cost_tier: str = "medium"
    applicable_systems: List[str] = field(default_factory=list)
    prerequisites: List[str] = field(default_factory=list)
    cem_reference: str = ""
    ashrae_reference: str = ""
    measurement_verification: str = "IPMVP Option B"
    kpi_metrics: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ecm_id": self.ecm_id, "name": self.name,
            "category": self.category.value if hasattr(self.category, "value") else str(self.category),
            "description": self.description,
            "typical_savings_pct": self.typical_savings_pct,
            "typical_payback_years": self.typical_payback_years,
            "implementation_cost_tier": self.implementation_cost_tier,
            "applicable_systems": self.applicable_systems,
            "prerequisites": self.prerequisites,
            "cem_reference": self.cem_reference,
            "ashrae_reference": self.ashrae_reference,
            "measurement_verification": self.measurement_verification,
            "kpi_metrics": self.kpi_metrics,
        }


ECM_CATALOG: List[EnergyConservationMeasure] = [
    EnergyConservationMeasure("ecm_dcv","Demand-Controlled Ventilation",ECMCategory.HVAC,
        "CO2-based OA reset reduces ventilation energy 20-30%.",22.0,3.5,"medium",
        ["AHU","RTU","DOAS"],[],
        "CEM Module 4 - HVAC Systems","ASHRAE 62.1 s6.2.7 / 90.1 s6.4.3.8",
        "IPMVP Option B",["OA_cfm","CO2_ppm","ventilation_energy_kBtu"]),
    EnergyConservationMeasure("ecm_sat_reset","Supply Air Temperature Reset",ECMCategory.HVAC,
        "Reset SAT based on zone demand; reduces reheat and cooling energy 10-20%.",15.0,1.5,"low",
        ["AHU","DOAS"],[],
        "CEM Module 4","ASHRAE 90.1 s6.5.2.1 / Guideline 36 s5.16",
        "IPMVP Option A",["SAT_degF","reheat_kBtu","cooling_ton_hrs"]),
    EnergyConservationMeasure("ecm_vsd_fans","VSD on Supply/Return Fans",ECMCategory.HVAC,
        "Variable-speed drives on AHU fans - cube-law savings up to 50%.",35.0,3.0,"medium",
        ["AHU","RTU"],["vav_system"],
        "CEM Module 4","ASHRAE 90.1 s6.5.3.3",
        "IPMVP Option B",["fan_kW","fan_rpm","static_pressure_inwg"]),
    EnergyConservationMeasure("ecm_vsd_pumps","VSD on CHW/HW Pumps",ECMCategory.HVAC,
        "Variable-speed drives on chilled- and hot-water pumps; 30-40% savings.",30.0,3.5,"medium",
        ["chiller_plant","boiler_plant"],[],
        "CEM Module 4","ASHRAE 90.1 s6.5.4.2",
        "IPMVP Option B",["pump_kW","diff_pressure_psi","flow_gpm"]),
    EnergyConservationMeasure("ecm_economizer","Airside Economizer",ECMCategory.HVAC,
        "Free cooling when OA enthalpy/temperature conditions are favourable.",18.0,2.0,"low",
        ["AHU","RTU"],[],
        "CEM Module 4","ASHRAE 90.1 s6.5.1",
        "IPMVP Option A",["OA_fraction","economizer_hours","cooling_avoided_ton_hrs"]),
    EnergyConservationMeasure("ecm_chiller_staging","Chiller Plant Staging Optimisation",ECMCategory.HVAC,
        "Load-based chiller sequencing targeting 0.5-0.6 kW/ton at full load.",12.0,2.5,"low",
        ["chiller_plant"],[],
        "CEM Module 5 - Chiller Plants","ASHRAE Guideline 22",
        "IPMVP Option C",["chiller_kW_ton","PLR","CHW_supply_temp"]),
    EnergyConservationMeasure("ecm_delta_t","Chilled Water Delta-T Optimisation",ECMCategory.HVAC,
        "Maintain 12-14 deg-F delta-T; low delta-T syndrome wastes pump energy.",8.0,1.0,"low",
        ["chiller_plant"],[],
        "CEM Module 5","ASHRAE Guideline 22 s4.4",
        "IPMVP Option A",["CHW_delta_T_degF","pump_kW","chiller_kW_ton"]),
    EnergyConservationMeasure("ecm_boiler_o2","Boiler O2 Trim Control",ECMCategory.HVAC,
        "Optimise combustion air to 2-4% flue O2; saves 1-3% fuel.",2.5,2.0,"medium",
        ["boiler_plant"],[],
        "CEM Module 6 - Boilers","ASHRAE Guideline 1.3",
        "IPMVP Option B",["flue_O2_pct","flue_temp_degF","fuel_therm"]),
    EnergyConservationMeasure("ecm_erv","Energy Recovery Ventilation",ECMCategory.HVAC,
        "Recover 60-80% of exhaust energy; required by 90.1 in many climates.",20.0,5.0,"high",
        ["AHU","DOAS"],[],
        "CEM Module 4","ASHRAE 90.1 Table 6.5.6.1",
        "IPMVP Option B",["ERV_effectiveness_pct","OA_heating_kBtu","recovery_kBtu"]),
    EnergyConservationMeasure("ecm_retrocomm","Retro-Commissioning",ECMCategory.CONTROLS,
        "Systematic BAS sequence review; typically 5-15% whole-building savings.",10.0,1.5,"low",
        ["all"],[],
        "CEM Module 8 - Commissioning","ASHRAE Guideline 0 / 1.1",
        "IPMVP Option C",["whole_building_kWh","EUI_kBtu_sqft_yr"]),
    EnergyConservationMeasure("ecm_occ_setback","Occupancy-Based Temperature Setback",ECMCategory.CONTROLS,
        "Night/weekend setback 4-6 deg-F; holiday scheduling for unoccupied periods.",8.0,0.5,"low",
        ["all"],[],
        "CEM Module 3 - Controls","ASHRAE 90.1 s6.4.3",
        "IPMVP Option A",["occupied_hours","setback_degF","HVAC_runtime_hrs"]),
    EnergyConservationMeasure("ecm_fdd","Fault Detection and Diagnostics",ECMCategory.CONTROLS,
        "Automated BAS analytics to detect faults; 8-12% whole-building savings.",10.0,2.5,"medium",
        ["AHU","chiller","boiler"],[],
        "CEM Module 8","ASHRAE Guideline 36 Appendix A",
        "IPMVP Option C",["fault_count","fault_energy_kBtu","MTBF_hrs"]),
    EnergyConservationMeasure("ecm_submetering","Electrical Sub-Metering",ECMCategory.CONTROLS,
        "Install sub-meters per LEED EA Credit; enables load disaggregation.",5.0,2.0,"medium",
        ["all"],[],
        "CEM Module 1 - Energy Auditing","ASHRAE Guideline 14",
        "IPMVP Option D",["circuit_kWh","peak_kW","load_factor"]),
    EnergyConservationMeasure("ecm_led_retrofit","LED Lighting Retrofit",ECMCategory.LIGHTING,
        "Replace fluorescent/HID with LED; 40-60% lighting energy reduction.",50.0,4.0,"high",
        ["all"],[],
        "CEM Module 2 - Lighting","ASHRAE 90.1 Table 9.6.1",
        "IPMVP Option A",["lighting_kWh","LPD_watts_sqft","lux_fc"]),
    EnergyConservationMeasure("ecm_occ_sensors","Occupancy Sensors for Lighting",ECMCategory.LIGHTING,
        "Automatic shut-off in intermittently occupied spaces; 20-40% reduction.",30.0,2.5,"medium",
        ["offices","restrooms","storage"],[],
        "CEM Module 2","ASHRAE 90.1 s9.4.1",
        "IPMVP Option A",["lighting_kWh","occupancy_hours","auto_off_events"]),
    EnergyConservationMeasure("ecm_daylight","Daylighting Controls",ECMCategory.LIGHTING,
        "Photosensor dimming in perimeter zones; 20-35% reduction in daylit areas.",25.0,4.0,"medium",
        ["perimeter_zones"],[],
        "CEM Module 2","ASHRAE 90.1 s9.4.1.4",
        "IPMVP Option A",["daylit_zone_kWh","daylight_hours","dimming_pct"]),
    EnergyConservationMeasure("ecm_air_seal","Building Air Sealing",ECMCategory.ENVELOPE,
        "Reduce infiltration; target less than 0.4 CFM75/sqft commercial.",5.0,3.0,"medium",
        ["all"],[],
        "CEM Module 7 - Envelope","ASHRAE 90.1 s5.4.3",
        "IPMVP Option B",["infiltration_CFM75","blower_door_ACH50","heating_kBtu"]),
    EnergyConservationMeasure("ecm_cool_roof","Cool Roof / Roof Insulation Upgrade",ECMCategory.ENVELOPE,
        "Increase roof R-value or install cool-roof coating; 5-15% HVAC savings.",8.0,6.0,"high",
        ["all"],[],
        "CEM Module 7","ASHRAE 90.1 Table 5.5.3.1.1",
        "IPMVP Option B",["roof_R_value","cooling_kWh","peak_kW"]),
    EnergyConservationMeasure("ecm_window_film","Low-E Window Film",ECMCategory.ENVELOPE,
        "Reduce solar heat gain; SHGC 0.25 vs 0.40 saves 5-12% cooling.",7.0,4.0,"medium",
        ["south_west_facades"],[],
        "CEM Module 7","ASHRAE 90.1 Table 5.5.4.5",
        "IPMVP Option A",["solar_gain_kBtu","cooling_kWh","SHGC"]),
    EnergyConservationMeasure("ecm_solar_pv","Solar PV Installation",ECMCategory.RENEWABLE,
        "On-site generation; typical office ROI 6-8 years with ITC incentives.",15.0,7.0,"high",
        ["all"],[],
        "CEM Module 9 - Renewables","ASHRAE 189.1 s10.3",
        "IPMVP Option A",["PV_kWh","capacity_kW","capacity_factor_pct"]),
    EnergyConservationMeasure("ecm_ca_leaks","Compressed Air Leak Repair",ECMCategory.COMPRESSED_AIR,
        "Typical systems lose 20-30% to leaks; ultrasonic survey plus repair.",25.0,1.0,"low",
        ["compressed_air_system"],[],
        "CEM Module 10 - Process Systems","ISA-7.0.01",
        "IPMVP Option B",["compressor_kW","leak_CFM","system_pressure_psig"]),
    EnergyConservationMeasure("ecm_steam_traps","Steam Trap Survey and Repair",ECMCategory.STEAM,
        "Failed-open traps waste 10-20% of steam; survey annually.",15.0,1.5,"low",
        ["steam_system"],[],
        "CEM Module 11 - Steam Systems","ASME TDP-1",
        "IPMVP Option B",["steam_trap_failure_rate","steam_kBtu","condensate_return_pct"]),
    EnergyConservationMeasure("ecm_heat_recovery","Waste Heat Recovery from Process",ECMCategory.PROCESS,
        "Recover process waste heat for preheating or space conditioning.",20.0,4.0,"high",
        ["manufacturing","data_center","restaurant"],[],
        "CEM Module 12 - Heat Recovery","ASME PTC 12.5",
        "IPMVP Option B",["recovered_kBtu","source_temp_degF","effectiveness_pct"]),
    EnergyConservationMeasure("ecm_low_flow","Low-Flow Fixture Retrofit",ECMCategory.WATER,
        "30-50% water reduction; also saves water-heating energy.",40.0,3.0,"medium",
        ["all"],[],
        "CEM Module 14 - Water","LEED WE Credit",
        "IPMVP Option A",["water_gallons","hot_water_kBtu","fixture_flow_gpm"]),
    EnergyConservationMeasure("ecm_awareness","Occupant Energy Awareness Training",ECMCategory.BEHAVIORAL,
        "Training plus dashboards; 3-7% reduction at zero capital cost.",5.0,0.5,"low",
        ["all"],[],
        "CEM Module 13 - Behavioral","ENERGY STAR Portfolio Manager",
        "IPMVP Option D",["occupant_actions","whole_building_kWh","EUI_benchmark"]),
]


@dataclass
class UtilityAnalysis:
    utility_id: str = field(default_factory=lambda: str(uuid.uuid4())[:10])
    site_name: str = ""
    analysis_period: str = ""
    electricity_kwh: float = 0.0
    electricity_cost: float = 0.0
    natural_gas_therms: float = 0.0
    natural_gas_cost: float = 0.0
    water_gallons: float = 0.0
    water_cost: float = 0.0
    peak_demand_kw: float = 0.0
    demand_charges: float = 0.0
    eui_kbtu_sqft_yr: float = 0.0
    energy_star_score: Optional[int] = None
    baseline_year: str = ""
    facility_sqft: float = 0.0
    utility_rates: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items()}


ASHRAE_AUDIT_LEVELS: Dict[str, Any] = {
    "Level_I": {
        "name": "Walk-Through Analysis",
        "description": "Preliminary analysis identifying low-cost and no-cost ECMs.",
        "effort_hours": "8-24",
        "deliverables": [
            "Utility bill summary (12 months)",
            "Preliminary ECM list with rough costs",
            "Energy use benchmarking",
            "Walk-through observations report",
        ],
        "data_required": ["12 months utility bills","Facility square footage","Occupancy schedule","Basic equipment list"],
        "typical_findings": ["Missing setback schedules","Lights on 24/7","Equipment running unoccupied"],
    },
    "Level_II": {
        "name": "Energy Survey and Analysis",
        "description": "Standard audit with detailed ECM analysis and savings projections.",
        "effort_hours": "40-120",
        "deliverables": [
            "Detailed energy use breakdown by end-use",
            "ECM analysis with cost and savings per measure",
            "Simple payback and ROI per ECM",
            "Prioritised recommendation list",
            "Baseline M&V plan",
        ],
        "data_required": ["24 months utility bills","Equipment nameplates","BAS trend data","Space-by-space survey","Utility rate schedule"],
        "typical_findings": ["VSD opportunities","LED retrofit","Economizer faults","Retro-Cx items"],
    },
    "Level_III": {
        "name": "Detailed Analysis of Capital-Intensive Modifications",
        "description": "Investment-grade audit with detailed engineering for major capital projects.",
        "effort_hours": "120-400",
        "deliverables": [
            "Investment-grade capital cost estimate (plus or minus 10-15%)",
            "Detailed engineering calculations",
            "M&V plan per IPMVP",
            "Financial analysis (NPV, IRR, lifecycle cost)",
            "Implementation plan with phasing",
            "Utility incentive identification",
            "Carbon reduction quantification",
        ],
        "data_required": ["15-minute interval meter data","BAS trend data 12+ months","Equipment performance curves","Utility rate schedule with demand charges","Building energy model","HVAC as-built drawings"],
        "typical_findings": ["Chiller replacement","DOAS retrofit","Solar PV feasibility","CHP opportunity"],
    },
}

_CBECS: Dict[str, float] = {
    "office":94.0,"school":76.0,"retail":73.0,"warehouse":35.0,
    "hospital":320.0,"hotel":155.0,"restaurant":450.0,
    "data_center":480.0,"manufacturing":150.0,"multifamily":75.0,
    "laboratory":380.0,"grocery":230.0,"other":90.0,
}


class MSSEnergyRubric:
    """Magnify / Simplify / Solidify rubric applied to energy data."""

    def magnify(self, utility_data: Dict[str, Any]) -> Dict[str, Any]:
        kwh = float(utility_data.get("electricity_kwh", 0))
        sqft = float(utility_data.get("facility_sqft", 1))
        therms = float(utility_data.get("natural_gas_therms", 0))
        eui = (kwh * 3.412 + therms * 100.0) / max(sqft, 1)
        median = _CBECS.get(utility_data.get("facility_type", "other"), 90.0)
        return {
            "detailed_breakdown": {
                "electricity_kbtu": round(kwh * 3.412, 1),
                "gas_kbtu": round(therms * 100.0, 1),
                "eui_kbtu_sqft_yr": round(eui, 1),
            },
            "load_disaggregation": {"hvac_pct":40,"lighting_pct":25,"plug_loads_pct":20,"dhw_pct":8,"other_pct":7},
            "ecm_opportunities": [e.name for e in ECM_CATALOG[:8]],
            "benchmark_comparison": {
                "your_eui": round(eui, 1),
                "median_eui": median,
                "vs_median_pct": round((eui - median) / max(median, 1) * 100, 1),
            },
            "recommended_audit_level": "Level_III" if eui > 200 else "Level_II",
            "estimated_savings_range": f"{round(eui*0.15,1)}-{round(eui*0.30,1)} kBtu/sqft/yr",
            "carbon_kgCO2e_yr": round(kwh * 0.386 + therms * 5.3, 1),
            "demand_charge_pct": round(
                float(utility_data.get("demand_charges",0)) /
                max(float(utility_data.get("electricity_cost",1)),1)*100, 1),
        }

    def simplify(self, utility_data: Dict[str, Any]) -> Dict[str, Any]:
        quick = [e for e in ECM_CATALOG if e.implementation_cost_tier == "low"][:3]
        total_cost = float(utility_data.get("electricity_cost",0)) + float(utility_data.get("natural_gas_cost",0))
        return {
            "top_3_quick_wins": [
                {"name":e.name,"savings_pct":e.typical_savings_pct,"payback_years":e.typical_payback_years}
                for e in quick
            ],
            "no_cost_measures": ["Occupancy setback scheduling","Turn off unoccupied lights","Fix obvious compressed-air leaks"],
            "simple_payback_summary": {
                "avg_payback_yrs": round(sum(e.typical_payback_years for e in quick)/max(len(quick),1),1),
                "best_payback_yrs": min((e.typical_payback_years for e in quick),default=0),
            },
            "estimated_annual_savings": round(total_cost * 0.10, 2),
        }

    def solidify(self, utility_data: Dict[str, Any], selected_ecms: Optional[List[str]] = None) -> Dict[str, Any]:
        ecms = selected_ecms or [ECM_CATALOG[0].ecm_id, ECM_CATALOG[10].ecm_id]
        return {
            "committed_ecm_plan": [{"ecm_id":e,"status":"approved","target_start":"Q1"} for e in ecms],
            "measurement_verification_plan": {
                "protocol": "IPMVP Option B",
                "baseline_period": "12 months pre-implementation",
                "reporting_period": "24 months post-implementation",
                "metering_points": ["whole-building kWh","sub-metered circuits"],
            },
            "baseline_values": {
                "eui_kbtu_sqft_yr": utility_data.get("eui_kbtu_sqft_yr",0),
                "electricity_kwh": utility_data.get("electricity_kwh",0),
            },
            "targets": {"eui_reduction_pct":15,"electricity_reduction_pct":12},
            "timeline_months": 18,
            "responsible_parties": ["Facilities Manager","Certified Energy Manager","Controls Contractor"],
        }


class EnergyEfficiencyFramework:
    """CEM-level energy-efficiency analysis engine."""

    def __init__(self) -> None:
        self._rubric = MSSEnergyRubric()

    def analyze_utility_data(self, utility_data: Dict[str, Any]) -> UtilityAnalysis:
        kwh = float(utility_data.get("electricity_kwh", 0))
        therms = float(utility_data.get("natural_gas_therms", 0))
        sqft = float(utility_data.get("facility_sqft", 1))
        el_cost = float(utility_data.get("electricity_cost", kwh * 0.12))
        gas_cost = float(utility_data.get("natural_gas_cost", therms * 1.20))
        eui = (kwh * 3.412 + therms * 100.0) / max(sqft, 1)
        return UtilityAnalysis(
            site_name=utility_data.get("site_name","Unknown Site"),
            analysis_period=utility_data.get("analysis_period","12 months"),
            electricity_kwh=kwh, electricity_cost=el_cost,
            natural_gas_therms=therms, natural_gas_cost=gas_cost,
            water_gallons=float(utility_data.get("water_gallons",0)),
            water_cost=float(utility_data.get("water_cost",0)),
            peak_demand_kw=float(utility_data.get("peak_demand_kw",0)),
            demand_charges=float(utility_data.get("demand_charges",0)),
            eui_kbtu_sqft_yr=round(eui,2),
            energy_star_score=utility_data.get("energy_star_score"),
            baseline_year=utility_data.get("baseline_year",str(datetime.now(timezone.utc).year-1)),
            facility_sqft=sqft,
            utility_rates=utility_data.get("utility_rates",{"electricity_per_kwh":0.12,"gas_per_therm":1.20}),
        )

    def recommend_ecms(self, analysis: UtilityAnalysis, facility_type: str = "office",
                       climate_zone: str = "") -> List[EnergyConservationMeasure]:
        ecms = list(ECM_CATALOG)
        if analysis.eui_kbtu_sqft_yr > 200:
            ecms.sort(key=lambda e: e.typical_savings_pct, reverse=True)
        else:
            ecms.sort(key=lambda e: e.typical_payback_years)
        return ecms[:10]

    def calculate_roi(self, ecm: EnergyConservationMeasure, analysis: UtilityAnalysis) -> Dict[str, Any]:
        frac = ecm.typical_savings_pct / 100.0
        el_rate = analysis.utility_rates.get("electricity_per_kwh", 0.12)
        gas_rate = analysis.utility_rates.get("gas_per_therm", 1.20)
        kwh_saved = analysis.electricity_kwh * frac * 0.6
        therm_saved = analysis.natural_gas_therms * frac * 0.4
        ann_usd = kwh_saved * el_rate + therm_saved * gas_rate
        costs = {"low":15000,"medium":75000,"high":300000}
        impl = costs.get(ecm.implementation_cost_tier, 50000)
        payback = impl / max(ann_usd, 1)
        npv = sum(ann_usd / (1.06**yr) for yr in range(1,11)) - impl
        return {
            "ecm_id": ecm.ecm_id,
            "annual_savings_kwh": round(kwh_saved),
            "annual_savings_usd": round(ann_usd, 2),
            "estimated_impl_cost": impl,
            "payback_years": round(payback, 1),
            "npv_10yr": round(npv),
            "irr_pct": round(100 / max(payback, 0.1), 1),
        }

    def generate_audit_report(self, level: str, analysis: UtilityAnalysis,
                              ecms: List[EnergyConservationMeasure]) -> Dict[str, Any]:
        audit_def = ASHRAE_AUDIT_LEVELS.get(level, ASHRAE_AUDIT_LEVELS["Level_II"])
        return {
            "audit_level": level,
            "audit_name": audit_def["name"],
            "site_name": analysis.site_name,
            "eui_kbtu_sqft_yr": analysis.eui_kbtu_sqft_yr,
            "deliverables": audit_def["deliverables"],
            "ecm_count": len(ecms),
            "top_ecms": [e.name for e in ecms[:5]],
            "estimated_savings_pct": round(sum(e.typical_savings_pct*0.4 for e in ecms[:5]),1),
            "next_steps": [
                (f"Implement {ecms[0].name} (payback {ecms[0].typical_payback_years} yrs)" if ecms else "No ECMs identified"),
                "Establish baseline per IPMVP",
                "Apply for utility incentives",
            ],
        }

    def get_cem_benchmark(self, facility_type: str, climate_zone: str = "") -> Dict[str, Any]:
        median = _CBECS.get(facility_type.lower(), _CBECS["other"])
        adj = {"1A":10,"2A":8,"7":12,"8":18}.get(climate_zone,0)
        return {
            "facility_type": facility_type,
            "climate_zone": climate_zone,
            "median_eui_kbtu_sqft_yr": median + adj,
            "energy_star_75pct_eui": round((median+adj)*0.6,1),
            "top_quartile_eui": round((median+adj)*0.5,1),
            "source": "CBECS 2018 / ENERGY STAR Portfolio Manager",
        }

    def apply_mss_rubric(self, rubric_mode: str, utility_data: Dict[str, Any]) -> Dict[str, Any]:
        if rubric_mode == "magnify":
            return self._rubric.magnify(utility_data)
        if rubric_mode == "simplify":
            return self._rubric.simplify(utility_data)
        if rubric_mode == "solidify":
            return self._rubric.solidify(utility_data)
        return {"error": f"Unknown rubric mode: {rubric_mode!r}. Use magnify/simplify/solidify."}
