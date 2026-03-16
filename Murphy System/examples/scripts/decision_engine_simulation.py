#!/usr/bin/env python3
"""Pro/Con Decision Engine Simulation"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

def run():
    from pro_con_decision_engine import ProConDecisionEngine, STANDARD_CRITERIA
    from energy_efficiency_framework import ECM_CATALOG

    print("=" * 60)
    print("Pro/Con Decision Engine Simulation")
    print("=" * 60)

    engine = ProConDecisionEngine()
    print(f"\n[1] Available criteria sets: {list(STANDARD_CRITERIA.keys())}")

    # Energy system decision
    decision = engine.evaluate(
        "Should we upgrade to a high-performance chiller plant?",
        [
            {"name":"Keep Existing Chillers","description":"Maintain current equipment",
             "scores":{"roi":4,"energy_savings":2,"implementation_cost":9,"maintenance_burden":7,"occupant_comfort":6,"resilience":5,"safety_compliance":1,"ashrae_compliance":1}},
            {"name":"High-Efficiency Chillers","description":"Upgrade to mag-lev chillers 0.4 kW/ton",
             "scores":{"roi":8,"energy_savings":9,"implementation_cost":3,"maintenance_burden":3,"occupant_comfort":9,"resilience":8,"safety_compliance":1,"ashrae_compliance":1}},
            {"name":"Non-Compliant Option","description":"Option that fails safety code",
             "scores":{"roi":9,"energy_savings":9,"implementation_cost":9,"maintenance_burden":9,"occupant_comfort":9,"resilience":9,"safety_compliance":0,"ashrae_compliance":1}},
        ],
        criteria_set="energy_system_selection"
    )
    print(f"\n[2] Chiller Decision:")
    print(engine.explain_decision(decision))

    # ECM prioritization
    ecm_data = [e.__dict__ for e in ECM_CATALOG[:5]]
    ecm_decision = engine.evaluate_ecms(ecm_data, budget=200_000, climate_zone="5A")
    print(f"\n[3] ECM to implement first: '{ecm_decision.winner.name if ecm_decision.winner else 'None'}'")
    print(f"    Net score: {ecm_decision.winner.net_score:.2f}" if ecm_decision.winner else "")
    print("\n[SIMULATION COMPLETE] Pro/Con Decision Engine\n")

if __name__ == "__main__":
    run()
