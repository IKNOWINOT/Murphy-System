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


def test_summary_consistency_drift_updates_self_improvement_backlog():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    murphy.latest_activation_preview = {
        "dynamic_implementation": {"next_actions": []},
        "capability_review": {"gaps": []}
    }
    def drift_snapshot(*args, **kwargs):
        return {
        "status": "drift_detected",
        "checks": {
            "integration_summary_present": True,
            "alignment_summary_present": False,
            "registry_total_matches_status": False,
            "registry_core_complete": True
        }
    }
    murphy._build_summary_surface_consistency = drift_snapshot

    status = murphy.get_system_status()
    self_improvement = status["self_improvement"]

    assert self_improvement["status"] == "needs_attention"
    assert self_improvement["summary_surface_consistency"]["status"] == "drift_detected"
    assert any(item.get("type") == "consistency" for item in self_improvement.get("backlog", []))
    assert self_improvement["summary"]["consistency_gaps"] >= 1
    assert "Resolve summary surface consistency drift across preview/status/info outputs." in self_improvement.get("remediation_actions", [])
