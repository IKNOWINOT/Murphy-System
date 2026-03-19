from src.murphy_core.config import CoreConfig
from src.murphy_core.gate_service import AdapterBackedGateService
from src.murphy_core.operator_runtime_surface_v3 import OperatorRuntimeSurfaceV3
from src.murphy_core.operator_status_runtime import ConfigurableOperatorStatusService
from src.murphy_core.provider_service import AdapterBackedProviderService
from src.murphy_core.registry import ModuleRegistry
from src.murphy_core.routing import CoreRouter
from src.murphy_core.runtime_deployment_modes_v2 import RuntimeDeploymentModesV2
from src.murphy_core.runtime_lineage_v2 import RuntimeLineageV2
from src.murphy_core.system_map import SystemMapService


def test_runtime_lineage_v2_prefers_founder_execution_surface():
    lineage = RuntimeLineageV2()
    preferred = lineage.preferred()
    assert preferred.name == 'murphy_core_v3_founder_execution_surface'
    assert preferred.status == 'preferred'
    assert preferred.role == 'canonical'


def test_runtime_deployment_modes_v2_prefers_founder_execution_surface():
    modes = RuntimeDeploymentModesV2()
    preferred = modes.preferred_direct()
    assert preferred.name == 'founder_execution_surface'
    assert preferred.category == 'canonical'


def test_operator_runtime_surface_v3_reports_founder_execution_surface():
    config = CoreConfig(default_provider='local_rules')
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
        preferred_factory='murphy_core_v3',
    )
    surface = OperatorRuntimeSurfaceV3(operator_status)
    summary = surface.ui_summary()
    assert summary['preferred_runtime_name'] == 'murphy_core_v3_founder_execution_surface'
    assert summary['preferred_deployment_mode'] == 'founder_execution_surface'
