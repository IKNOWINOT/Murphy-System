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


def test_governance_dashboard_snapshot_defaults():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()

    snapshot = murphy._build_governance_dashboard_snapshot(
        {"delivery_readiness": "needs_info"},
        [{"owner": "operations_director", "status": "pending", "description": "ops task"}],
        {"status": "needs_info", "compliance_status": "clear"},
        {"status": "pending_review"}
    )

    summary = snapshot["summary"]
    assert summary["total"] == 6
    assert summary["needs_wiring"] == 1
    assert snapshot["status"] == "needs_wiring"
    assert snapshot["components"]["operations"]["normalized_status"] == "pending"


def test_governance_dashboard_snapshot_ready():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()

    snapshot = murphy._build_governance_dashboard_snapshot(
        {"delivery_readiness": "ready"},
        [
            {"owner": "operations_director", "status": "ready", "description": "ops task"},
            {"owner": "quality_assurance", "status": "complete", "description": "qa task"}
        ],
        {"status": "ready", "compliance_status": "clear"},
        {"status": "clear"}
    )

    summary = snapshot["summary"]
    assert summary["ready"] == summary["total"]
    assert snapshot["status"] == "ready"


def test_governance_dashboard_snapshot_in_system_status():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()

    murphy.latest_activation_preview = {
        "executive_directive": {"delivery_readiness": "needs_info"},
        "operations_plan": [{"owner": "operations_director", "status": "pending"}],
        "delivery_readiness": {"status": "needs_info", "compliance_status": "clear"},
        "handoff_queue": {"status": "pending_review"}
    }

    status = murphy.get_system_status()

    governance = status["governance_dashboard"]
    assert governance["summary"]["total"] == 6
    assert governance["status"] == "needs_wiring"
    assert governance["components"]["hitl"]["normalized_status"] == "pending"
