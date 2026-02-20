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


def test_summary_surface_consistency_available_across_surfaces():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()

    direct = murphy._build_summary_surface_consistency()
    assert direct["status"] in {"consistent", "drift_detected"}
    assert direct["checks"]["registry_total_matches_status"] in {True, False}

    status = murphy.get_system_status()
    info = murphy.get_system_info()

    doc = runtime.LivingDocument("test_consistency_doc", "Consistency", "content", "request")
    doc.confidence = 0.9
    murphy._update_document_tree(doc)
    preview = murphy._build_activation_preview(
        doc,
        "Validate summary surface consistency",
        {"answers": {step["stage"]: "ok" for step in murphy.flow_steps}}
    )

    assert "summary_surface_consistency" in status
    assert "summary_surface_consistency" in info
    assert "summary_surface_consistency" in preview
    assert status["summary_surface_consistency"]["status"] == "consistent"
    assert info["summary_surface_consistency"]["status"] == "consistent"
    assert preview["summary_surface_consistency"]["status"] == "consistent"
    assert status["summary_surface_consistency"]["checks"]["completion_snapshot_present"] is True
    assert status["self_improvement"]["summary"]["consistency_gaps"] == 0
    assert preview["self_improvement"]["summary"]["consistency_gaps"] == 0


def test_summary_surface_consistency_detects_missing_completion_snapshot():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    consistency = murphy._build_summary_surface_consistency(
        completion_snapshot={"areas": [], "summary": {"total_areas": 0, "average_percent": 0.0}}
    )
    assert consistency["status"] == "drift_detected"
    assert consistency["checks"]["completion_snapshot_present"] is False
