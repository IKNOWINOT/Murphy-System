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


def test_summary_bundle_used_by_status_and_info():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()

    custom_bundle = {
        "integration_capabilities": {"summary": {"total": 3, "ready": 2}},
        "integration_capabilities_summary": {"total": 3, "ready": 2},
        "competitive_feature_alignment": {"summary": {"total": 4, "available": 3, "partial": 1, "missing": 0}, "features": []},
        "competitive_feature_alignment_summary": {"total": 4, "available": 3, "partial": 1, "missing": 0},
        "module_registry_summary": {
            "total_available": 999,
            "total_active": 99,
            "core_expected": 28,
            "core_registered": 28,
            "core_missing": [],
            "auto_registered": 123,
            "category_counts": {"runtime": 1}
        }
    }
    murphy._build_summary_surface_bundle = lambda: custom_bundle

    status = murphy.get_system_status()
    info = murphy.get_system_info()

    assert status["integration_capabilities_summary"] == custom_bundle["integration_capabilities_summary"]
    assert status["competitive_feature_alignment_summary"] == custom_bundle["competitive_feature_alignment_summary"]
    assert status["module_registry_summary"] == custom_bundle["module_registry_summary"]
    assert info["integration_capabilities_summary"] == custom_bundle["integration_capabilities_summary"]
    assert info["competitive_feature_alignment_summary"] == custom_bundle["competitive_feature_alignment_summary"]
    assert info["module_registry_summary"] == custom_bundle["module_registry_summary"]
