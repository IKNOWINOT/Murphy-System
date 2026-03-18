from src.murphy_core.config import CoreConfig
from src.murphy_core.gate_service import AdapterBackedGateService
from src.murphy_core.operator_runtime_surface_v2 import OperatorRuntimeSurfaceV2
from src.murphy_core.operator_status_runtime import ConfigurableOperatorStatusService
from src.murphy_core.operations_status import OperationsStatus
from src.murphy_core.provider_service import AdapterBackedProviderService
from src.murphy_core.registry import ModuleRegistry
from src.murphy_core.routing import CoreRouter
from src.murphy_core.system_map import SystemMapService
from src.murphy_core.ui_runtime_dashboard import UIRuntimeDashboard


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
    return OperatorRuntimeSurfaceV2(operator_status)


def test_ui_runtime_dashboard_builds():
    dashboard = UIRuntimeDashboard(_build_surface())
    payload = dashboard.build()
    assert "cards" in payload
    assert "actions" in payload
    assert len(payload["cards"]) >= 3
    assert len(payload["actions"]) >= 2


def test_operations_status_snapshot_and_runbook():
    ops = OperationsStatus(_build_surface())
    snapshot = ops.snapshot()
    assert snapshot["status"] == "operational"
    assert snapshot["preferred_runtime"] == "murphy_core_v3_runtime_correct"
    assert isinstance(snapshot["runbook"], list)
    assert len(snapshot["runbook"]) >= 2
