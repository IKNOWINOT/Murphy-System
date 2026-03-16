#!/usr/bin/env python3
"""Manufacturing Industrial Automation Simulation"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

def run():
    from industry_automation_wizard import IndustryAutomationWizard, IndustryType
    from universal_ingestion_framework import AdapterRegistry, GRAINGER_BEST_SELLERS
    from system_configuration_engine import SystemConfigurationEngine, SystemType
    from pro_con_decision_engine import ProConDecisionEngine
    from synthetic_interview_engine import SyntheticInterviewEngine, ReadingLevel

    print("=" * 60)
    print("Manufacturing Industrial Automation Simulation")
    print("=" * 60)

    # 1. Industry wizard
    wizard = IndustryAutomationWizard()
    session = wizard.create_session(industry=IndustryType.MANUFACTURING)
    print(f"\n[1] Started Industry Wizard: {session.session_id}")
    auto_types = wizard.get_automation_types("manufacturing")
    print(f"    Available automation types: {len(auto_types)}")
    for t in auto_types[:3]:
        print(f"      - {t['name']}: {t['description'][:60]}")

    # 2. Universal ingestion
    registry = AdapterRegistry()
    csv_data = "point_name,point_type,description,units\nSPEED,AI,Motor Speed,RPM\nTORQUE,AI,Motor Torque,Nm\nRUN,DI,Motor Running,binary"
    result = registry.auto_detect_and_ingest(csv_data, "motor_points.csv")
    print(f"\n[2] Universal Ingestion: {result.records_ingested} records via {result.adapter_name}")

    # 3. Grainger best-sellers
    recs = registry.get_component_recommendations("VFD", "motor_control")
    print(f"\n[3] Grainger recommendations for VFD: {len(recs)} components")
    for r in recs[:2]:
        print(f"    - {r.manufacturer} {r.description[:50]} (#{r.part_number})")

    # 4. System config
    engine = SystemConfigurationEngine()
    st = engine.detect_system_type("PLC system with Modbus registers and HMI")
    strategy = engine.recommend_strategy(st, {"energy_priority": True})
    print(f"\n[4] System Type Detected: {st.value}")
    print(f"    Recommended Strategy: {strategy.name}")
    print(f"    Pros: {', '.join(strategy.pros[:2])}")

    # 5. 21-question interview
    interview = SyntheticInterviewEngine()
    isession = interview.create_session("manufacturing_line", reading_level=ReadingLevel.HIGH_SCHOOL)
    q = interview.next_question(isession.session_id)
    print(f"\n[5] Interview Q1: {q['question']}")
    result2 = interview.answer(isession.session_id, q["question_id"],
        "We have 3 PLCs controlling a conveyor system with VFDs and safety interlocks.")
    print(f"    Implicit answers inferred: {result2['implicit_answers_found']}")
    print(f"    Coverage: {result2['coverage_pct']}%")

    print("\n[SIMULATION COMPLETE] Manufacturing Automation\n")

if __name__ == "__main__":
    run()
