#!/usr/bin/env python3
"""Retail Automation Simulation"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

def run():
    from industry_automation_wizard import IndustryAutomationWizard, IndustryType
    from energy_efficiency_framework import EnergyEfficiencyFramework
    from pro_con_decision_engine import ProConDecisionEngine

    print("=" * 60)
    print("Retail Automation Simulation")
    print("=" * 60)

    wizard = IndustryAutomationWizard()
    session = wizard.create_session(industry=IndustryType.RETAIL)
    types = wizard.get_automation_types("retail")
    print(f"\n[1] Retail automation types: {len(types)}")
    for t in types[:3]:
        print(f"    - {t['name']}")

    eef = EnergyEfficiencyFramework()
    data = {"site_name":"Retail Store","electricity_kwh":500_000,"natural_gas_therms":1_000,
            "facility_sqft":15_000,"electricity_cost":60_000,"facility_type":"retail"}
    analysis = eef.analyze_utility_data(data)
    ecms = eef.recommend_ecms(analysis, "retail")
    print(f"\n[2] Retail EUI: {analysis.eui_kbtu_sqft_yr:.1f} kBtu/sqft/yr")
    print(f"    Top ECM: {ecms[0].name if ecms else 'N/A'}")

    engine = ProConDecisionEngine()
    decision = engine.evaluate_ecms([e.__dict__ for e in ecms[:3]], budget=50_000, climate_zone="3A")
    print(f"\n[3] Top ECM to prioritise: {decision.winner.name if decision.winner else 'None'}")
    print(f"    {decision.reasoning[:100]}")
    print("\n[SIMULATION COMPLETE] Retail\n")

if __name__ == "__main__":
    run()
