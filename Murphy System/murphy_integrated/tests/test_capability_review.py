import importlib.util
from pathlib import Path
from unittest.mock import patch


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


def test_success_rate_helper_handles_zero_and_percentages():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()

    assert murphy._calculate_success_rate(0, 0) == 0.0
    assert murphy._calculate_success_rate(1, 2) == 50.0


def test_llm_readiness_handles_missing_modules():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()

    def fake_find_spec(name):
        if name == runtime.MurphySystem.LLM_MODULE_CANDIDATES[0]:
            raise ModuleNotFoundError("missing")
        return None

    with patch.object(runtime.importlib.util, "find_spec", side_effect=fake_find_spec):
        readiness = murphy._check_llm_readiness()
        assert readiness["status"] == "not_configured"
        assert readiness["modules"] == []


def test_llm_readiness_detects_available_modules():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    target_module = runtime.MurphySystem.LLM_MODULE_CANDIDATES[1]

    def fake_find_spec(name):
        if name == target_module:
            return object()
        return None

    with patch.object(runtime.importlib.util, "find_spec", side_effect=fake_find_spec):
        readiness = murphy._check_llm_readiness()
        assert readiness["status"] == "available"
        assert readiness["modules"] == [target_module]


def test_autonomy_extension_status_reflects_readiness():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    murphy.integration_engine = object()
    murphy.governance_scheduler = object()
    murphy.inoni_automation = object()
    extensions = {item["id"]: item for item in murphy._build_autonomy_extension_status()}

    assert extensions["business_metrics_scaling"]["status"] == "available"
    assert extensions["auto_patching"]["status"] == "partial"

    murphy.flow_steps = []
    extensions = {item["id"]: item for item in murphy._build_autonomy_extension_status()}
    assert extensions["self_service_onboarding"]["status"] == "needs_configuration"
