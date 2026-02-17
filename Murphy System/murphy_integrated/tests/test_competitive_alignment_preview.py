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


def test_competitive_feature_alignment_in_activation_preview():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    doc = runtime.LivingDocument("doc-competitive", "Competitive", "content", "request")
    doc.confidence = 0.9
    murphy._update_document_tree(doc)

    preview = murphy._build_activation_preview(
        doc,
        "Validate competitive feature alignment in activation preview",
        {"answers": {step["stage"]: "ok" for step in murphy.flow_steps}}
    )

    assert "competitive_feature_alignment" in preview
    alignment = preview["competitive_feature_alignment"]
    assert alignment["summary"]["total"] == len(alignment["features"])
