#!/usr/bin/env python3
"""Full CEM Energy Audit Simulation"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

def run():
    from energy_efficiency_framework import EnergyEfficiencyFramework, MSSEnergyRubric, ASHRAE_AUDIT_LEVELS
    from climate_resilience_engine import ClimateResilienceEngine
    from pro_con_decision_engine import ProConDecisionEngine

    print("=" * 60)
    print("CEM Energy Audit Simulation — ASHRAE Level II")
    print("=" * 60)

    eef = EnergyEfficiencyFramework()
    utility_data = {
        "site_name": "Phoenix Office Campus",
        "electricity_kwh": 2_400_000,
        "natural_gas_therms": 2_000,
        "facility_sqft": 80_000,
        "electricity_cost": 288_000,
        "natural_gas_cost": 2_400,
        "demand_charges": 42_000,
        "peak_demand_kw": 580,
        "facility_type": "office",
    }
    analysis = eef.analyze_utility_data(utility_data)
    print(f"\n[1] EUI: {analysis.eui_kbtu_sqft_yr:.1f} kBtu/sqft/yr")
    benchmark = eef.get_cem_benchmark("office", "2B")
    print(f"    CBECS Median: {benchmark['median_eui_kbtu_sqft_yr']} kBtu/sqft/yr")
    print(f"    Energy Star 75th pct: {benchmark['energy_star_75pct_eui']} kBtu/sqft/yr")

    ecms = eef.recommend_ecms(analysis, "office", "2B")
    print(f"\n[2] Top 5 ECMs for Phoenix (Hot-Dry Zone 2B):")
    for e in ecms[:5]:
        roi = eef.calculate_roi(e, analysis)
        print(f"    - {e.name}: {e.typical_savings_pct}% savings, ${roi['annual_savings_usd']:,.0f}/yr, {roi['payback_years']} yr payback")

    report = eef.generate_audit_report("Level_II", analysis, ecms)
    print(f"\n[3] Audit Report: {report['audit_name']}")
    print(f"    Deliverables ({len(report['deliverables'])}):")
    for d in report["deliverables"][:3]:
        print(f"      - {d}")

    rubric = MSSEnergyRubric()
    mag = rubric.magnify(utility_data)
    print(f"\n[4] Magnify: EUI {mag['detailed_breakdown']['eui_kbtu_sqft_yr']} vs median {mag['benchmark_comparison']['median_eui']}")
    print(f"    Recommended audit level: {mag['recommended_audit_level']}")
    sol = rubric.solidify(utility_data, [ecms[0].ecm_id, ecms[1].ecm_id])
    print(f"\n[5] Solidify M&V Plan: {sol['measurement_verification_plan']['protocol']}")
    print(f"    Target EUI reduction: {sol['targets']['eui_reduction_pct']}%")

    climate = ClimateResilienceEngine()
    recs = climate.get_design_recommendations("Phoenix, AZ", "chiller")
    print(f"\n[6] Climate rec for Phoenix (Zone 2B): {recs[0]}")
    print("\n[SIMULATION COMPLETE] Energy Audit\n")

if __name__ == "__main__":
    run()
