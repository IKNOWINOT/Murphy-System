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


def test_summary_parity_across_preview_status_info():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()

    status = murphy.get_system_status()
    info = murphy.get_system_info()
    doc = runtime.LivingDocument("doc-surface", "Surface", "content", "request")
    doc.confidence = 0.9
    murphy._update_document_tree(doc)
    preview = murphy._build_activation_preview(
        doc,
        "Validate summary parity across surfaces",
        {"answers": {step["stage"]: "ok" for step in murphy.flow_steps}}
    )

    assert info["integration_capabilities_summary"] == status["integration_capabilities_summary"]
    assert info["competitive_feature_alignment_summary"] == status["competitive_feature_alignment_summary"]
    assert preview["integration_capabilities_summary"] == status["integration_capabilities_summary"]
    assert preview["competitive_feature_alignment_summary"] == status["competitive_feature_alignment_summary"]
    assert preview["module_registry_summary"] == status["module_registry_summary"] == info["module_registry_summary"]
