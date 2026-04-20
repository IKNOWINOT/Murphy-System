#!/usr/bin/env python3
"""Virtual Org Chart and Shadow Agent Simulation"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

def run():
    from org_chart_generator import OrgChartGenerator, OrgIndustry

    print("=" * 60)
    print("Virtual Org Chart + Shadow Agent Simulation")
    print("=" * 60)

    gen = OrgChartGenerator()
    session = gen.create_session()
    print(f"\n[1] Session created: {session.session_id}")

    q = gen.next_question(session.session_id)
    print(f"    Q: {q['question']}")
    gen.answer(session.session_id, q["question_id"], "Acme Controls, a building automation startup")
    q2 = gen.next_question(session.session_id)
    if q2:
        gen.answer(session.session_id, q2["question_id"], "Building Automation")
    q3 = gen.next_question(session.session_id)
    if q3:
        gen.answer(session.session_id, q3["question_id"], "small")
    q4 = gen.next_question(session.session_id)
    if q4:
        gen.answer(session.session_id, q4["question_id"], "engineering, sales, operations")

    # Answer remaining
    for _ in range(10):
        qn = gen.next_question(session.session_id)
        if qn:
            gen.answer(session.session_id, qn["question_id"], "Yes, standard approach")

    result = gen.generate_virtual_org(session.session_id)
    positions = result.get("positions", result.get("virtual_employees", []))
    print(f"\n[2] Generated {len(positions)} virtual positions/employees")
    for pos in positions[:4]:
        name = pos.get("role", pos.get("title", "position"))
        print(f"    - {name}")

    print(f"\n[3] Shadow agents created — these become baselines when real employees are hired")
    print(f"    IP Classification: business_ip (company-owned baseline)")

    # Hire first employee
    if positions:
        pos_id = positions[0].get("position_id", positions[0].get("id", "pos_001"))
        hire_result = gen.hire_employee(
            session.session_id,
            pos_id,
            "Alice Johnson",
            "alice@acme.com",
            {"tools": "github,slack", "background": "P.E. licensed engineer"},
        )
        print(f"\n[4] Hired employee: Alice Johnson")
        print(f"    IP Classification: {hire_result.get('ip_classification','employee_ip')}")
        print(f"    Shadow agent tailored to her background")
    print("\n[SIMULATION COMPLETE] Org Chart\n")

if __name__ == "__main__":
    run()
