from src.murphy_core.config import CoreConfig
from src.murphy_core.gate_service import AdapterBackedGateService
from src.murphy_core.operator_status_runtime import ConfigurableOperatorStatusService
from src.murphy_core.provider_service import AdapterBackedProviderService
from src.murphy_core.registry import ModuleRegistry
from src.murphy_core.routing import CoreRouter
from src.murphy_core.system_map import SystemMapService


def test_configurable_operator_status_v3_label():
    config = CoreConfig(default_provider="local_rules")
    registry = ModuleRegistry()
    providers = AdapterBackedProviderService(config=config)
    gates = AdapterBackedGateService()
    system_map = SystemMapService(registry, CoreRouter())
    status = ConfigurableOperatorStatusService(
        config,
        registry,
        providers,
        gates,
        system_map,
        preferred_factory="murphy_core_v3",
    )

    snapshot = status.snapshot()
    assert snapshot["runtime"]["preferred_factory"] == "murphy_core_v3"


def test_configurable_operator_status_ui_summary_v3_label():
    config = CoreConfig(default_provider="local_rules")
    registry = ModuleRegistry()
    providers = AdapterBackedProviderService(config=config)
    gates = AdapterBackedGateService()
    system_map = SystemMapService(registry, CoreRouter())
    status = ConfigurableOperatorStatusService(
        config,
        registry,
        providers,
        gates,
        system_map,
        preferred_factory="murphy_core_v3",
    )

    summary = status.ui_summary()
    assert summary["preferred_factory"] == "murphy_core_v3"
    assert summary["preferred_provider"] == "local_rules"
