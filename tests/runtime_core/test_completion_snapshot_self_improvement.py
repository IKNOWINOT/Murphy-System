import importlib.util
from pathlib import Path


def load_runtime_module():
    runtime_dir = Path(__file__).resolve().parent.parent.parent
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


def test_completion_snapshot_updates_self_improvement_backlog():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    murphy.latest_activation_preview = {
        "dynamic_implementation": {"next_actions": []},
        "capability_review": {"gaps": []}
    }
    def completion_snapshot_with_threshold():
        return {
            "areas": [
                {"area": "execution_wiring", "percent": 45},
                {"area": "deterministic_llm_routing", "percent": 35},
                {"area": "ui_user_testing", "percent": 72}
            ],
            "summary": {
                "total_areas": 3,
                "average_percent": 50.67,
                "remediation_threshold_percent": 40
            }
        }
    murphy._build_completion_snapshot = completion_snapshot_with_threshold

    status = murphy.get_system_status()
    self_improvement = status["self_improvement"]

    assert self_improvement["status"] == "needs_attention"
    assert self_improvement["summary"]["completion_gaps"] == 1
    assert self_improvement["summary"]["completion_total_areas"] == 3
    assert self_improvement["summary"]["completion_remediation_threshold_percent"] == 40
    assert self_improvement["summary"]["completion_average_percent"] == 50.67
    assert self_improvement["summary"]["completion_gap_areas"] == ["deterministic_llm_routing"]
    assert self_improvement["summary"]["completion_coverage_ratio"] == 0.67
    assert self_improvement["summary"]["completion_backlog_items"] == 1
    assert self_improvement["summary"]["completion_backlog_ratio"] == 1.0
    assert any(item.get("type") == "completion" for item in self_improvement.get("backlog", []))
    assert "Prioritize low completion areas and schedule remediation loops." in self_improvement.get("remediation_actions", [])


def test_completion_snapshot_default_threshold_fallback():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    murphy.latest_activation_preview = {
        "dynamic_implementation": {"next_actions": []},
        "capability_review": {"gaps": []}
    }

    def completion_snapshot_without_threshold():
        return {
            "areas": [
                {"area": "execution_wiring", "percent": 45},
                {"area": "deterministic_llm_routing", "percent": 35},
                {"area": "ui_user_testing", "percent": 72}
            ],
            "summary": {"total_areas": 3, "average_percent": 50.67}
        }
    murphy._build_completion_snapshot = completion_snapshot_without_threshold

    status = murphy.get_system_status()
    assert status["self_improvement"]["summary"]["completion_gaps"] == 2
    assert status["self_improvement"]["summary"]["completion_total_areas"] == 3
    assert status["self_improvement"]["summary"]["completion_remediation_threshold_percent"] == 50
    assert status["self_improvement"]["summary"]["completion_average_percent"] == 50.67
    assert status["self_improvement"]["summary"]["completion_gap_areas"] == [
        "execution_wiring",
        "deterministic_llm_routing"
    ]
    assert status["self_improvement"]["summary"]["completion_coverage_ratio"] == 0.33
    assert status["self_improvement"]["summary"]["completion_backlog_items"] == 2
    assert status["self_improvement"]["summary"]["completion_backlog_ratio"] == 1.0
