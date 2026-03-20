from fastapi.testclient import TestClient

from src.murphy_core.config import CoreConfig
from src.murphy_core.gate_service import AdapterBackedGateService
from src.murphy_core.operator_runtime_surface_v8 import OperatorRuntimeSurfaceV8
from src.murphy_core.operator_status_runtime import ConfigurableOperatorStatusService
from src.murphy_core.provider_service import AdapterBackedProviderService
from src.murphy_core.registry import ModuleRegistry
from src.murphy_core.routing import CoreRouter
from src.murphy_core.runtime_deployment_modes_v7 import RuntimeDeploymentModesV7
from src.murphy_core.runtime_lineage_v7 import RuntimeLineageV7
from src.murphy_core.system_map import SystemMapService
from src.runtime.murphy_core_bridge_v3_canonical_execution_surface_v5 import create_bridge_app


def test_runtime_lineage_v7_prefers_canonical_execution_surface_v5():
    lineage = RuntimeLineageV7()
    preferred = lineage.preferred()
    assert preferred.name == 'murphy_core_v3_canonical_execution_surface_v5'
    assert preferred.status == 'preferred'
    assert preferred.role == 'canonical'
    assert preferred.startup == 'src/runtime/main_core_v3_canonical_execution_surface_v5.py'


def test_runtime_deployment_modes_v7_prefers_canonical_execution_surface_v5():
    modes = RuntimeDeploymentModesV7()
    preferred = modes.preferred_direct()
    overlay = modes.founder_overlay()
    assert preferred.name == 'canonical_execution_surface_v5'
    assert preferred.category == 'canonical'
    assert preferred.startup == 'src/runtime/main_core_v3_canonical_execution_surface_v5.py'
    assert overlay.name == 'founder_visibility_overlay'
    assert overlay.startup == 'src/runtime/main_core_v3_canonical_execution_surface_v5.py'


def test_operator_runtime_surface_v8_reports_canonical_execution_v5_and_founder_overlay():
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
    surface = OperatorRuntimeSurfaceV8(operator_status)
    summary = surface.ui_summary()
    assert summary['preferred_runtime_name'] == 'murphy_core_v3_canonical_execution_surface_v5'
    assert summary['preferred_runtime_startup'] == 'src/runtime/main_core_v3_canonical_execution_surface_v5.py'
    assert summary['preferred_deployment_mode'] == 'canonical_execution_surface_v5'
    assert summary['preferred_deployment_startup'] == 'src/runtime/main_core_v3_canonical_execution_surface_v5.py'
    assert summary['founder_overlay_mode'] == 'founder_visibility_overlay'
    assert summary['founder_overlay_startup'] == 'src/runtime/main_core_v3_canonical_execution_surface_v5.py'


def test_bridge_v5_runtime_summary_matches_boot_path_truth():
    client = TestClient(create_bridge_app(prefer_canonical_execution_surface_v5=True))
    response = client.get('/api/operator/runtime-summary')
    assert response.status_code == 200
    payload = response.json()
    assert payload['success'] is True
    assert payload['preferred_runtime_name'] == 'murphy_core_v3_canonical_execution_surface_v5'
    assert payload['preferred_runtime_startup'] == 'src/runtime/main_core_v3_canonical_execution_surface_v5.py'
    assert payload['preferred_deployment_mode'] == 'canonical_execution_surface_v5'
    assert payload['preferred_deployment_startup'] == 'src/runtime/main_core_v3_canonical_execution_surface_v5.py'
    assert payload['founder_overlay_startup'] == 'src/runtime/main_core_v3_canonical_execution_surface_v5.py'
