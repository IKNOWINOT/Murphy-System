#!/usr/bin/env python3
"""Healthcare Facility Automation Simulation"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

def run():
    from industry_automation_wizard import IndustryAutomationWizard, IndustryType
    from synthetic_interview_engine import SyntheticInterviewEngine, ReadingLevel
    from pro_con_decision_engine import ProConDecisionEngine
    from climate_resilience_engine import ClimateResilienceEngine

    print("=" * 60)
    print("Healthcare Facility Automation Simulation")
    print("=" * 60)

    wizard = IndustryAutomationWizard()
    session = wizard.create_session(industry=IndustryType.HEALTHCARE)
    types = wizard.get_automation_types("healthcare")
    print(f"\n[1] Healthcare automation types available: {len(types)}")
    for t in types[:3]:
        print(f"    - {t['name']}")

    interview = SyntheticInterviewEngine()
    isession = interview.create_session("hospital_BAS", reading_level=ReadingLevel.PROFESSIONAL)
    q = interview.next_question(isession.session_id)
    print(f"\n[2] Professional-level question: {q['question']}")
    r = interview.answer(isession.session_id, q["question_id"],
        "HIPAA compliance required. ASHRAE 170 governs our OR and ICU ventilation. "
        "We have AHUs with HEPA filtration and 20 ACH in surgical suites.")
    print(f"    Implicit answers found: {r['implicit_answers_found']} (HIPAA, ASHRAE, AHU inferred)")

    climate = ClimateResilienceEngine()
    recs = climate.get_design_recommendations("Houston, TX", "AHU")
    print(f"\n[3] Climate recs for Houston (Zone 2A): {recs[0]}")

    engine = ProConDecisionEngine()
    decision = engine.evaluate_equipment([
        {"name": "Standard AHU", "description": "CAV with MERV-13",
         "scores": {"efficiency":6,"first_cost":9,"life_cycle_cost":6,"reliability":7,"lead_time":8,"local_support":8,"safety_listing":1,"code_compliance":1}},
        {"name": "Healthcare AHU", "description": "VAV with HEPA, ASHRAE 170 compliant",
         "scores": {"efficiency":9,"first_cost":4,"life_cycle_cost":8,"reliability":9,"lead_time":5,"local_support":7,"safety_listing":1,"code_compliance":1}},
    ], application="Hospital OR AHU", location="Houston TX")
    print(f"\n[4] Equipment Decision: {decision.winner.name if decision.winner else 'None'}")
    print(f"    {decision.reasoning[:100]}")
    print("\n[SIMULATION COMPLETE] Healthcare\n")

if __name__ == "__main__":
    run()
