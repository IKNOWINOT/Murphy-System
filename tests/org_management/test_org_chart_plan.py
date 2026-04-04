import importlib.util
from pathlib import Path

import pytest


def load_runtime_module():
    module_path = Path(__file__).resolve().parents[1] / "murphy_system_1.0_runtime.py"
    spec = importlib.util.spec_from_file_location("murphy_system_runtime", module_path)
    module = importlib.util.module_from_spec(spec)
    if spec.loader is None:
        raise RuntimeError("Unable to load Murphy runtime module")
    spec.loader.exec_module(module)
    return module


def test_org_chart_plan_builds_contract_positions():
    runtime = load_runtime_module()
    system = runtime.MurphySystem()
    plan = system._build_org_chart_plan(
        "Design UI assets and launch a marketing campaign",
        ["Design UI assets", "Launch marketing campaign"]
    )
    if plan.get("status") == "unavailable":
        pytest.skip("Organization chart system not available")
    assert plan["required_positions"]
    assert plan["deliverable_coverage"]
    assert plan["position_contracts"]
    assert plan["coverage_summary"]["total_deliverables"] == 2


def test_org_chart_plan_unavailable():
    runtime = load_runtime_module()
    system = runtime.MurphySystem()
    system.org_chart_system = None
    plan = system._build_org_chart_plan("Test org chart coverage", ["Deliverable"])
    assert plan["status"] == "unavailable"
    assert "reason" in plan
