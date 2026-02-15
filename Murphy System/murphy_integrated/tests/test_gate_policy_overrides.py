import importlib.util
from pathlib import Path

import pytest


def load_runtime_module():
    module_path = Path(__file__).resolve().parents[1] / "murphy_system_1.0_runtime.py"
    spec = importlib.util.spec_from_file_location("murphy_system_runtime", module_path)
    module = importlib.util.module_from_spec(spec)
    if spec.loader is None:
        raise RuntimeError("Unable to load Murphy runtime module")
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("override,expected", [
    ("open", "open"),
    ("blocked", "blocked"),
    (None, None),
    ("pending", None),
])
def test_normalize_gate_override(override, expected):
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.__new__(runtime.MurphySystem)
    assert murphy._normalize_gate_override(override, "Test Gate") == expected


def test_gate_chain_open_reason():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    doc = runtime.LivingDocument("doc-1", "Test", "content", "general")
    doc.confidence = 0.85
    doc.gate_policy = murphy.default_gate_policy
    gates = murphy._build_gate_chain(doc)
    assert gates
    assert gates[0]["status"] == "open"
    assert gates[0]["reason"] == "Confidence meets threshold"


def test_gate_chain_blocked_reason():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    doc = runtime.LivingDocument("doc-2", "Test", "content", "general")
    doc.confidence = 0.4
    doc.gate_policy = murphy.default_gate_policy
    gates = murphy._build_gate_chain(doc)
    assert gates[0]["status"] == "blocked"
    assert gates[0]["reason"] == "Confidence below threshold"
    assert gates[1]["status"] == "blocked"
    assert gates[1]["reason"] == "Blocked by Magnify Gate"
