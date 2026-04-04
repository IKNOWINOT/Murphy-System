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


def test_competitive_feature_alignment_summary_in_system_info():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()

    info = murphy.get_system_info()
    expected_integration_summary = murphy._build_integration_capabilities().get("summary", {})
    expected_alignment_summary = murphy._build_competitive_feature_alignment(
        murphy._build_integration_capabilities()
    ).get("summary", {})

    assert "integration_capabilities_summary" in info
    assert "competitive_feature_alignment_summary" in info
    assert "module_registry_summary" in info
    assert info["integration_capabilities_summary"] == expected_integration_summary
    assert info["competitive_feature_alignment_summary"] == expected_alignment_summary
    status = murphy.get_system_status()
    assert info["integration_capabilities_summary"] == status["integration_capabilities_summary"]
    assert info["competitive_feature_alignment_summary"] == status["competitive_feature_alignment_summary"]
    alignment_summary = info["competitive_feature_alignment_summary"]
    assert alignment_summary["total"] >= 1
    assert alignment_summary["available"] + alignment_summary["partial"] + alignment_summary["missing"] == alignment_summary["total"]
    assert info["module_registry_summary"]["total_available"] >= info["module_registry_summary"]["core_expected"]
    assert info["module_registry_summary"] == murphy._build_module_registry_summary()
    assert info["module_registry_summary"] == status["module_registry_summary"]
    assert info["module_registry_summary"]["core_registered"] == info["module_registry_summary"]["core_expected"]
    assert info["module_registry_summary"]["core_missing"] == []
