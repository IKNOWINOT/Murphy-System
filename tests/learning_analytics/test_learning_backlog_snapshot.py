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


def test_learning_backlog_snapshot_needs_info():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    learning_loop = murphy._build_learning_loop_plan("Test", {}, {})
    training_patterns = {
        "wingman_protocol": {"training_sources": ["scripted_ui_screenshots"]},
        "high_confidence_paths": []
    }

    snapshot = murphy._build_learning_backlog_snapshot(learning_loop, training_patterns)

    assert snapshot["status"] == "needs_info"
    assert snapshot["requirements_status"] == "needs_info"
    assert snapshot["summary"]["total_iterations"] == len(learning_loop["iterations"])
    assert snapshot["routing"]["training_sources"] == ["scripted_ui_screenshots"]
    assert snapshot["gap_action"]


def test_learning_backlog_snapshot_ready():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    murphy.flow_steps = []
    murphy.swarm_system = object()
    learning_loop = murphy._build_learning_loop_plan("Automation", {"answers": {}}, {})
    training_patterns = {
        "wingman_protocol": {"training_sources": ["gate_chain_outputs"]},
        "high_confidence_paths": [{"from": "requirements_identification", "to": "execution_plan"}]
    }

    snapshot = murphy._build_learning_backlog_snapshot(learning_loop, training_patterns)

    assert snapshot["status"] == "ready"
    assert snapshot["summary"]["queued_iterations"] == snapshot["summary"]["total_iterations"]
    assert snapshot["routing"]["status"] == "ready"
    assert snapshot["routing"]["high_confidence_paths"] == 1
