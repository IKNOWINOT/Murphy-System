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


def test_competitive_feature_alignment_in_system_status():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()

    status = murphy.get_system_status()

    assert "integration_capabilities" in status
    assert "integration_capabilities_summary" in status
    assert "competitive_feature_alignment" in status
    assert "competitive_feature_alignment_summary" in status
    assert "module_registry_summary" in status
    assert status["integration_capabilities_summary"] == status["integration_capabilities"]["summary"]
    assert status["module_registry_summary"] == murphy._build_module_registry_summary()
    assert status["module_registry_summary"]["total_available"] == status["module_registry"]["total_available"]
    assert status["module_registry_summary"]["total_available"] >= status["module_registry_summary"]["core_expected"]
    assert status["module_registry_summary"]["core_registered"] == status["module_registry_summary"]["core_expected"]
    assert status["module_registry_summary"]["core_missing"] == []
    alignment = status["competitive_feature_alignment"]
    assert alignment["summary"]["total"] == len(alignment["features"])
    assert status["competitive_feature_alignment_summary"] == alignment["summary"]
    feature_ids = {feature["id"] for feature in alignment["features"]}
    assert "ai_model_lifecycle" in feature_ids
    assert "low_code_automation" in feature_ids
