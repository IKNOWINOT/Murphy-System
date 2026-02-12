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
