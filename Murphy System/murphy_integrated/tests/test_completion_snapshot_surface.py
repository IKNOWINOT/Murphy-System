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


def test_completion_snapshot_surface_parity():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    expected = murphy._build_completion_snapshot()

    status = murphy.get_system_status()
    info = murphy.get_system_info()
    doc = runtime.LivingDocument("test_completion_doc", "Completion", "content", "request")
    doc.confidence = 0.9
    murphy._update_document_tree(doc)
    preview = murphy._build_activation_preview(
        doc,
        "Validate completion snapshot parity",
        {"answers": {step["stage"]: "ok" for step in murphy.flow_steps}}
    )

    assert status["completion_snapshot"] == expected
    assert info["completion_snapshot"] == expected
    assert preview["completion_snapshot"] == expected
    assert expected["summary"]["total_areas"] == len(expected["areas"])
