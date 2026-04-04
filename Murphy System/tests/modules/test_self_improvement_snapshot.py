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


def test_self_improvement_snapshot_in_preview():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    doc = runtime.LivingDocument("doc-improve", "Improve", "content", "request")
    doc.confidence = 0.45
    murphy._update_document_tree(doc)
    preview = murphy._build_activation_preview(
        doc,
        "Need automation planning with compliance checks",
        {"answers": {step["stage"]: "ok" for step in murphy.flow_steps}}
    )
    snapshot = preview.get("self_improvement", {})
    assert snapshot.get("status") in {"needs_attention", "ready", "unavailable"}
    summary = snapshot.get("summary", {})
    assert summary.get("total_backlog") == len(snapshot.get("backlog", []))
