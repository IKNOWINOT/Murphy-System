import importlib.util
from pathlib import Path

# Sample a few modules to keep assertions lightweight while verifying tags.
SAMPLE_MODULE_LIMIT = 3


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


def test_module_registry_contains_gate_synthesis():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    status = murphy.module_manager.get_module_status()

    expected_modules = [
        "gate_synthesis",
        "module_manager",
        "modular_runtime",
        "universal_control_plane",
        "inoni_business_automation",
        "two_phase_orchestrator",
        "form_intake",
        "confidence_engine",
        "execution_engine",
        "learning_engine",
        "hitl_monitor",
        "governance_framework",
        "telemetry_ingestion",
        "mfgc_adapter",
        "system_integrator",
    ]
    for module_name in expected_modules:
        assert module_name in status["modules"]
        assert status["modules"][module_name]["status"] == "available"


def test_module_registry_summary_reports_core_modules():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    summary = murphy._build_module_registry_summary()

    assert summary["core_missing"] == []
    assert summary["core_registered"] == summary["core_expected"]
    assert summary["total_available"] >= summary["core_expected"]
    assert summary["auto_registered"] >= 1
    assert isinstance(summary["category_counts"], dict)
    assert summary["category_counts"]
    assert all(value >= 0 for value in summary["category_counts"].values())
    assert any(value > 0 for value in summary["category_counts"].values())
    category_total = sum(summary["category_counts"].values())
    assert category_total >= summary["auto_registered"]


def test_module_registry_summary_handles_empty_category_tag():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    summary_before = murphy._build_module_registry_summary()
    unknown_key = runtime.MurphySystem.MODULE_CATEGORY_UNKNOWN
    unknown_before = summary_before["category_counts"].get(unknown_key, 0)
    murphy.module_manager.register_module(
        name="empty_category_module",
        module_path="fake.empty",
        description="Empty category module",
        capabilities=[f"{runtime.MurphySystem.MODULE_CATEGORY_PREFIX} "]
    )
    assert "empty_category_module" in murphy.module_manager.get_module_status()["modules"]
    summary = murphy._build_module_registry_summary()
    assert summary["category_counts"].get(unknown_key, 0) == unknown_before + 1


def test_module_registry_includes_src_inventory():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    status = murphy.module_manager.get_module_status()

    module_name = "src.command_system"
    assert module_name in status["modules"]
    capabilities = status["modules"][module_name]["capabilities"]
    assert runtime.MurphySystem.MODULE_AUTO_SCAN_TAG in capabilities
    assert f"{runtime.MurphySystem.MODULE_PATH_PREFIX}{module_name}" in capabilities
    assert any(
        capability.startswith(runtime.MurphySystem.MODULE_CATEGORY_PREFIX)
        for capability in capabilities
    )


def test_module_registry_includes_local_packages():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    status = murphy.module_manager.get_module_status()
    modules = status["modules"]

    def assert_package_registered(prefix: str) -> None:
        package_modules = [
            name for name in modules
            if name.startswith(prefix)
        ]
        assert package_modules, f"Expected auto-registered modules under {prefix}"
        # Sample a few modules to keep assertions lightweight.
        for module_name in package_modules[:SAMPLE_MODULE_LIMIT]:
            capabilities = modules[module_name]["capabilities"]
            assert runtime.MurphySystem.MODULE_AUTO_SCAN_TAG in capabilities
            assert f"{runtime.MurphySystem.MODULE_PATH_PREFIX}{module_name}" in capabilities

    assert_package_registered("bots.")


def test_competitive_feature_alignment_summary():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    integration_capabilities = murphy._build_integration_capabilities()
    alignment = murphy._build_competitive_feature_alignment(integration_capabilities)

    assert "summary" in alignment
    assert "features" in alignment
    assert alignment["summary"]["total"] == len(alignment["features"])
    assert alignment["features"]
    assert all(
        feature["status"] in runtime.MurphySystem.COMPETITIVE_FEATURE_STATUS_VALUES
        for feature in alignment["features"]
    )
    integration_metrics_feature_id = next(
        (
            feature["id"] for feature in runtime.MurphySystem.COMPETITIVE_FEATURES
            if feature.get("includes_integration_metrics")
        ),
        None
    )
    assert integration_metrics_feature_id is not None
    connector_feature = next(
        (
            feature for feature in alignment["features"]
            if feature["id"] == integration_metrics_feature_id
        ),
        None
    )
    assert connector_feature is not None
    assert connector_feature["integration_summary"] == integration_capabilities["summary"]
    feature_ids = {feature["id"] for feature in alignment["features"]}
    assert "ai_model_lifecycle" in feature_ids
    assert "low_code_automation" in feature_ids
