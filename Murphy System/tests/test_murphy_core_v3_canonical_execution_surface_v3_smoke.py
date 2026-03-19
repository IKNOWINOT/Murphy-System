from fastapi.testclient import TestClient

from src.murphy_core.app_v3_canonical_execution_surface_v3 import create_app


client = TestClient(create_app())


def test_canonical_execution_surface_v3_health_identity():
    response = client.get('/api/health')
    assert response.status_code == 200
    payload = response.json()
    assert payload['service'] == 'murphy_core_v3_canonical_execution_surface_v3'


def test_canonical_execution_surface_v3_runtime_summary_matches_canonical_v2_defaults():
    response = client.get('/api/operator/runtime-summary')
    assert response.status_code == 200
    payload = response.json()
    assert payload['success'] is True
    assert payload['preferred_runtime_name'] == 'murphy_core_v3_canonical_execution_surface_v2'
    assert payload['preferred_deployment_mode'] == 'canonical_execution_surface_v2'
    assert payload['founder_overlay_mode'] == 'founder_visibility_overlay'


def test_canonical_execution_surface_v3_execute_includes_family_selection():
    response = client.post('/api/execute', json={'task_description': 'run a swarm task'})
    assert response.status_code == 200
    payload = response.json()
    assert payload['success'] is True
    assert 'subsystem_family_selection' in payload
