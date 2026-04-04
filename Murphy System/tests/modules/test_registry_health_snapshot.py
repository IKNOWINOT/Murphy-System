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


def test_registry_health_snapshot_structure():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    snapshot = murphy._build_registry_health_snapshot()
    assert snapshot["status"] in {"healthy", "needs_attention", "unavailable"}
    assert "summary" in snapshot
    assert "module_status" in snapshot
    assert isinstance(snapshot["reasons"], list)
    assert snapshot["summary"]["total_available"] >= 0


def test_schema_drift_snapshot_reports_missing_configs():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    snapshot = murphy._build_schema_drift_snapshot()
    assert snapshot["status"] in {"clear", "drift_detected"}
    assert snapshot["summary"]["total_issues"] == len(snapshot["issues"])
    if snapshot["status"] == "drift_detected":
        assert any(item["area"] == "persistence" for item in snapshot["issues"])


def test_registry_health_snapshot_in_activation_preview():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    doc = runtime.LivingDocument("doc-health", "Health", "content", "request")
    doc.confidence = 0.9
    murphy._update_document_tree(doc)
    preview = murphy._build_activation_preview(
        doc,
        "Validate registry health snapshot",
        {"answers": {step["stage"]: "ok" for step in murphy.flow_steps}}
    )
    assert "registry_health" in preview
    assert "schema_drift" in preview
