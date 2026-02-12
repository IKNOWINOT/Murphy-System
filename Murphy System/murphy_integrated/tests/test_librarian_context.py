import importlib.util
from pathlib import Path


def load_runtime_module():
    module_path = Path(__file__).resolve().parents[1] / "murphy_system_1.0_runtime.py"
    spec = importlib.util.spec_from_file_location("murphy_system_runtime", module_path)
    module = importlib.util.module_from_spec(spec)
    if spec.loader is None:
        raise RuntimeError("Unable to load Murphy runtime module")
    spec.loader.exec_module(module)
    return module


def test_librarian_context_builds_conditions():
    runtime = load_runtime_module()
    system = runtime.MurphySystem()
    doc = system._create_document(
        title="Automation Test",
        content="Run marketing automation with executive approvals",
        doc_type="automation"
    )
    preview = system._build_activation_preview(doc, doc.content, None)
    librarian_context = preview.get("librarian_context", {})
    assert librarian_context.get("status") in {"ready", "unavailable"}
    if librarian_context.get("status") == "ready":
        conditions = librarian_context.get("recommended_conditions", [])
        assert conditions
        assert all(condition.get("requires_approval") for condition in conditions)
