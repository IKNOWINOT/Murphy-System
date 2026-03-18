from src.murphy_core.config import CoreConfig
from src.murphy_core.gate_service import AdapterBackedGateService
from src.murphy_core.operator_status import OperatorStatusService
from src.murphy_core.provider_service import AdapterBackedProviderService
from src.murphy_core.registry import ModuleRegistry
from src.murphy_core.routing import CoreRouter
from src.murphy_core.system_map import SystemMapService


def test_operator_status_snapshot():
    config = CoreConfig(default_provider="local_rules")
    registry = ModuleRegistry()
    providers = AdapterBackedProviderService(config=config)
    gates = AdapterBackedGateService()
    system_map = SystemMapService(registry, CoreRouter())
    status = OperatorStatusService(config, registry, providers, gates, system_map)

    snapshot = status.snapshot()
    assert snapshot["runtime"]["preferred_factory"] == "murphy_core_v2"
    assert "providers" in snapshot
    assert "gates" in snapshot
    assert "registry" in snapshot
    assert "system_map" in snapshot


def test_operator_status_ui_summary():
    config = CoreConfig(default_provider="local_rules")
    registry = ModuleRegistry()
    providers = AdapterBackedProviderService(config=config)
    gates = AdapterBackedGateService()
    system_map = SystemMapService(registry, CoreRouter())
    status = OperatorStatusService(config, registry, providers, gates, system_map)

    summary = status.ui_summary()
    assert summary["preferred_factory"] == "murphy_core_v2"
    assert summary["preferred_provider"] == "local_rules"
    assert summary["provider_count"] >= 1
    assert summary["gate_count"] >= 1
