#!/usr/bin/env python3
"""21-Question Synthetic Interview Simulation"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

def run():
    from synthetic_interview_engine import SyntheticInterviewEngine, ReadingLevel, QUESTION_IDS

    print("=" * 60)
    print("21-Question Synthetic Interview Simulation")
    print("=" * 60)

    engine = SyntheticInterviewEngine()
    session = engine.create_session("chiller_plant", reading_level=ReadingLevel.HIGH_SCHOOL)
    print(f"\n[1] Session: {session.session_id}, Domain: chiller_plant")
    print(f"    All 21 question IDs loaded: {len(QUESTION_IDS)}")

    answers = [
        "We have 2 centrifugal chillers providing chilled water for a 200,000 sqft office building.",
        "The chiller connects to cooling towers, chilled water pumps, and the BAS via BACnet.",
        "Common failures are low delta-T syndrome and condenser fouling.",
        "Chillers start based on occupancy schedule and outdoor air temperature above 55F.",
        "The facility manager, HVAC technician, and energy manager all depend on this system.",
    ]

    print(f"\n[2] Simulating answers at HIGH_SCHOOL reading level:")
    for i, ans_text in enumerate(answers):
        q = engine.next_question(session.session_id)
        if not q:
            break
        print(f"\n    Q{i+1} [{q['question_id']}]: {q['question']}")
        result = engine.answer(session.session_id, q["question_id"], ans_text)
        print(f"    A: {ans_text[:70]}...")
        print(f"    Implicit answers inferred: {result['implicit_answers_found']}, Coverage: {result['coverage_pct']}%")

    status = engine.get_all_21_status(session.session_id)
    print(f"\n[3] Coverage Status:")
    print(f"    Direct answers: {len(status['covered'])}")
    print(f"    Inferred answers: {len(status['inferred'])}")
    print(f"    Remaining: {len(status['remaining'])}")
    print(f"    Total coverage: {status['coverage_pct']}%")

    model = engine.generate_knowledge_model(session.session_id)
    print(f"\n[4] Knowledge Model:")
    for k, v in model.items():
        if v and k != "domain":
            print(f"    {k}: {str(v)[:60]}")

    # Test reading level adaptation
    print(f"\n[5] Reading Level Adaptation:")
    technical = "The chiller delta-T must be maintained at 12-14F; low delta-T syndrome increases pump kW."
    adapted_hs = engine.adapt_to_reading_level(technical, ReadingLevel.HIGH_SCHOOL)
    print(f"    Expert:      {technical[:60]}")
    print(f"    HS adapted:  {adapted_hs[:60]}")
    print("\n[SIMULATION COMPLETE] Synthetic Interview\n")

if __name__ == "__main__":
    run()
