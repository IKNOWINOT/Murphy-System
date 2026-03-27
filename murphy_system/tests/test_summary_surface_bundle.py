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


def test_summary_surface_bundle_matches_builders():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    bundle = murphy._build_summary_surface_bundle()

    integration = murphy._build_integration_capabilities()
    alignment = murphy._build_competitive_feature_alignment(integration)
    registry_summary = murphy._build_module_registry_summary()

    assert bundle["integration_capabilities"] == integration
    assert bundle["integration_capabilities_summary"] == integration.get("summary", {})
    assert bundle["competitive_feature_alignment"] == alignment
    assert bundle["competitive_feature_alignment_summary"] == alignment.get("summary", {})
    assert bundle["module_registry_summary"] == registry_summary
