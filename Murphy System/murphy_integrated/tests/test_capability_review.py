import importlib.util
from pathlib import Path


def load_runtime_module():
    runtime_dir = Path(__file__).resolve().parent.parent
    candidates = list(runtime_dir.glob("murphy_system_*_runtime.py"))
    if not candidates:
        raise RuntimeError("Unable to locate Murphy runtime module")
    module_path = candidates[0]
    spec = importlib.util.spec_from_file_location("murphy_system_runtime", module_path)
    module = importlib.util.module_from_spec(spec)
    if spec.loader is None:
        raise RuntimeError("Unable to load Murphy runtime module")
    spec.loader.exec_module(module)
    return module


def test_capability_review_highlights_gaps():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    murphy.execution_metrics = {"total": 2, "success": 1, "total_time": 1.4}
    murphy.flow_steps = [{"stage": "signup"}]

    capability_tests = [
        {"id": "gate_synthesis", "status": "ok"},
        {"id": "true_swarm_system", "status": "error", "error": "missing execute_full_cycle"}
    ]
    capability_alignment = [
        {
            "id": "gate_synthesis",
            "available": True,
            "wired": True,
            "initialized": True,
            "activated": True,
            "capability_reflects": True,
            "gap_reason": "ready",
            "gap_action": "No gap detected."
        },
        {
            "id": "true_swarm_system",
            "available": True,
            "wired": False,
            "initialized": True,
            "activated": False,
            "capability_reflects": False,
            "gap_reason": "not_wired",
            "gap_action": "Wire this subsystem into execute_task or form processing."
        }
    ]
    org_chart_plan = {"coverage_summary": {"status": "partial"}}
    sensor_plan = {"region": "global", "regulatory_sources": []}

    review = murphy._build_capability_review(
        capability_tests,
        capability_alignment,
        org_chart_plan,
        sensor_plan
    )

    assert review["summary"]["ok"] == 1
    assert review["summary"]["error"] == 1
    assert review["execution_metrics"]["total_executions"] == 2
    assert any(gap["id"] == "true_swarm_system" for gap in review["gaps"])
