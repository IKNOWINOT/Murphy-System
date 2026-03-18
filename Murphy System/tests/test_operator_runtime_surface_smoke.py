from src.murphy_core.config import CoreConfig
from src.murphy_core.gate_service import AdapterBackedGateService
from src.murphy_core.operator_runtime_surface import OperatorRuntimeSurface
from src.murphy_core.operator_status_runtime import ConfigurableOperatorStatusService
from src.murphy_core.provider_service import AdapterBackedProviderService
from src.murphy_core.registry import ModuleRegistry
from src.murphy_core.routing import CoreRouter
from src.murphy_core.system_map import SystemMapService


def _build_surface():
    config = CoreConfig(default_provider="local_rules")
    registry = ModuleRegistry()
    providers = AdapterBackedProviderService(config=config)
    gates = AdapterBackedGateService()
    system_map = SystemMapService(registry, CoreRouter())
    operator_status = ConfigurableOperatorStatusService(
        config,
        registry,
        providers,
        gates,
        system_map,
        preferred_factory="murphy_core_v3",
    )
    return OperatorRuntimeSurface(operator_status)


def test_operator_runtime_surface_snapshot():
    surface = _build_surface()
    snapshot = surface.snapshot()
    assert "operator" in snapshot
    assert "lineage" in snapshot
    assert snapshot["preferred_runtime"]["name"] == "murphy_core_v3_runtime_correct"


def test_operator_runtime_surface_ui_summary():
    surface = _build_surface()
    summary = surface.ui_summary()
    assert summary["preferred_factory"] == "murphy_core_v3"
    assert summary["preferred_runtime_name"] == "murphy_core_v3_runtime_correct"
    assert summary["rollback_layer_count"] >= 1
    assert summary["compatibility_layer_count"] >= 1
