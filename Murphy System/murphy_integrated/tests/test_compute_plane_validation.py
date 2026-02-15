import importlib.util
from pathlib import Path


def load_runtime_module():
    runtime_dir = Path(__file__).resolve().parent.parent
    module_path = runtime_dir / "murphy_system_1.0_runtime.py"
    if not module_path.exists():
        candidates = list(runtime_dir.glob("murphy_system_*_runtime.py"))
        if not candidates:
            raise RuntimeError("Unable to locate Murphy runtime module")
        raise RuntimeError(f"Expected runtime 1.0 module missing. Found: {candidates}")
    spec = importlib.util.spec_from_file_location("murphy_system_runtime", module_path)
    module = importlib.util.module_from_spec(spec)
    if spec.loader is None:
        raise RuntimeError("Unable to load Murphy runtime module")
    spec.loader.exec_module(module)
    return module


def test_compute_plane_validation_returns_validated():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    payload = {
        "compute_request": {
            "expression": "minimize: x subject to: x >= 0",
            "language": "lp"
        }
    }
    result = murphy._execute_compute_plane_validation(payload)
    assert result is not None
    assert result["status"] == "validated"
    assert result["language"] == "lp"
    assert result["validation"]["is_valid"] is True


def test_compute_plane_validation_requires_expression():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    payload = {"compute_request": {"expression": "", "language": "lp"}}
    result = murphy._execute_compute_plane_validation(payload)
    assert result is not None
    assert result["status"] == "error"
