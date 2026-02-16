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


def test_handoff_queue_snapshot_empty():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    snapshot = murphy._build_handoff_queue_snapshot([])
    summary = snapshot["summary"]
    assert summary["total_pending"] == 0
    assert snapshot["pending_interventions"] == []
    assert snapshot["pending_contracts"] == []
    expected_status = "clear" if murphy.hitl_monitor else "monitor_unavailable"
    assert snapshot["status"] == expected_status


def test_handoff_queue_snapshot_pending_items():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    murphy.handle_form_validation({"task_data": {"description": ""}})
    intervention = next(iter(murphy.hitl_interventions.values()))
    contracts = [{"gate": "HITL Contract", "status": "pending"}]
    snapshot = murphy._build_handoff_queue_snapshot(contracts)
    summary = snapshot["summary"]
    assert summary["pending_interventions"] == 1
    assert summary["pending_contracts"] == 1
    assert summary["total_pending"] == 2
    assert intervention in snapshot["pending_interventions"]
    if murphy.hitl_monitor:
        assert snapshot["status"] == "pending_review"
    else:
        assert snapshot["status"] == "needs_wiring"


def test_handoff_queue_snapshot_in_activation_preview():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    doc = runtime.LivingDocument("doc-handoff", "Handoff", "content", "request")
    doc.confidence = 0.88
    murphy._update_document_tree(doc)
    onboarding_answers = {step["stage"]: "ok" for step in murphy.flow_steps}
    preview = murphy._build_activation_preview(
        doc,
        "Need HITL approvals for release",
        {"answers": onboarding_answers}
    )
    assert "handoff_queue" in preview
    assert "summary" in preview["handoff_queue"]


def test_handoff_queue_snapshot_resolved_contracts():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    contracts = [
        {"gate": "HITL Contract", "status": status}
        for status in ["approved", "complete", "ready", "cleared"]
    ]
    snapshot = murphy._build_handoff_queue_snapshot(contracts)
    assert snapshot["summary"]["pending_contracts"] == 0
    assert snapshot["summary"]["total_pending"] == 0


def test_handoff_queue_snapshot_unresolved_contracts():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    contracts = [
        {"gate": "HITL Contract", "status": status}
        for status in ["pending", "blocked", "rejected"]
    ]
    snapshot = murphy._build_handoff_queue_snapshot(contracts)
    assert snapshot["summary"]["pending_contracts"] == len(contracts)
