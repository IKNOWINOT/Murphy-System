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


def test_gate_synthesis_includes_control_metrics():
    runtime = load_runtime_module()
    system = runtime.MurphySystem()
    doc = system._create_document(
        title="Marketing Automation",
        content="Automate marketing approvals with QA review",
        doc_type="automation"
    )
    result = system._attempt_gate_synthesis(doc.content, doc, None)
    assert result["status"] == "ok"
    gate = result["gates"][0]
    assert gate["control_metric"]["name"]
    assert gate["sensor_feedback"]["sensor"]
    assert gate["sensor_feedback"]["value"] is not None
