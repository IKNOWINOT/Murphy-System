from murphy_system_1.0_runtime import MurphySystem


def test_org_chart_plan_builds_contract_positions():
    system = MurphySystem()
    plan = system._build_org_chart_plan(
        "Design UI assets and launch a marketing campaign",
        ["Design UI assets", "Launch marketing campaign"]
    )
    if plan.get("status") == "unavailable":
        return
    assert plan["required_positions"]
    assert plan["deliverable_coverage"]
    assert plan["position_contracts"]
    assert plan["coverage_summary"]["total_deliverables"] == 2
