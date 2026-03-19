from src.murphy_core.config import CoreConfig
from src.murphy_core.gate_service import AdapterBackedGateService
from src.murphy_core.operator_runtime_surface_v4 import OperatorRuntimeSurfaceV4
from src.murphy_core.operator_status_runtime import ConfigurableOperatorStatusService
from src.murphy_core.provider_service import AdapterBackedProviderService
from src.murphy_core.registry import ModuleRegistry
from src.murphy_core.routing import CoreRouter
from src.murphy_core.runtime_deployment_modes_v3 import RuntimeDeploymentModesV3
from src.murphy_core.runtime_lineage_v3 import RuntimeLineageV3
from src.murphy_core.system_map import SystemMapService


def test_runtime_lineage_v3_prefers_canonical_execution_surface():
    lineage = RuntimeLineageV3()
    preferred = lineage.preferred()
    assert preferred.name == 'murphy_core_v3_canonical_execution_surface'
    assert preferred.status == 'preferred'
    assert preferred.role == 'canonical'


def test_runtime_deployment_modes_v3_prefers_canonical_execution_surface():
    modes = RuntimeDeploymentModesV3()
    preferred = modes.preferred_direct()
    overlay = modes.founder_overlay()
    assert preferred.name == 'canonical_execution_surface'
    assert preferred.category == 'canonical'
    assert overlay.name == 'founder_visibility_overlay'
    assert overlay.category == 'overlay'


def test_operator_runtime_surface_v4_reports_canonical_execution_and_founder_overlay():
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
    surface = OperatorRuntimeSurfaceV4(operator_status)
    summary = surface.ui_summary()
    assert summary['preferred_runtime_name'] == 'murphy_core_v3_canonical_execution_surface'
    assert summary['preferred_deployment_mode'] == 'canonical_execution_surface'
    assert summary['founder_overlay_mode'] == 'founder_visibility_overlay'
