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


def _build_onboarding_answers(murphy):
    return {step["stage"]: "ok" for step in murphy.flow_steps}


def test_orchestrator_readiness_snapshot_structure():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    snapshot = murphy._build_orchestrator_readiness_snapshot()
    assert snapshot["summary"]["total"] == 3
    assert snapshot["summary"]["ready"] + snapshot["summary"]["needs_wiring"] == 3
    assert snapshot["preferred_path"] in {"async_orchestrator", "two_phase_orchestrator", "simulation"}
    assert snapshot["execution_ready"] in {True, False}
    components = snapshot["components"]
    assert set(components.keys()) == {
        "async_orchestrator",
        "two_phase_orchestrator",
        "swarm_system"
    }
    for entry in components.values():
        assert entry["status"] in {"ready", "needs_wiring"}
        assert entry["available"] in {True, False}


def test_orchestrator_readiness_snapshot_in_preview():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    doc = runtime.LivingDocument("doc-orch", "Orchestrator", "content", "request")
    doc.confidence = 0.9
    murphy._update_document_tree(doc)
    preview = murphy._build_activation_preview(
        doc,
        "Check orchestrator readiness",
        {"answers": _build_onboarding_answers(murphy)}
    )
    assert "orchestrator_readiness" in preview
    assert preview["orchestrator_readiness"]["summary"]["total"] == 3


def test_orchestrator_readiness_snapshot_in_status():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    status = murphy.get_system_status()
    assert "orchestrator_readiness" in status
