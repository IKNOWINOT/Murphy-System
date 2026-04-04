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


def test_gate_chain_blocks_following_gates():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    doc = runtime.LivingDocument("doc-1", "Test", "content", "request")
    doc.confidence = 0.4
    doc.gate_policy = [
        {"name": "Gate A", "threshold": 0.8},
        {"name": "Gate B", "threshold": 0.2}
    ]

    gates = murphy._build_gate_chain(doc)

    assert gates[0]["status"] == "blocked"
    assert gates[0]["blocked_by"] == "Gate A"
    assert gates[0]["reason"] == "Confidence below threshold"
    assert gates[1]["status"] == "blocked"
    assert gates[1]["blocked_by"] == "Gate A"
    assert gates[1]["reason"] == "Blocked by Gate A"
