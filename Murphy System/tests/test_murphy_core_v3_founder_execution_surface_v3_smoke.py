from fastapi.testclient import TestClient

from src.murphy_core.app_v3_founder_execution_surface_v3 import create_app


client = TestClient(create_app())


def test_founder_execution_surface_v3_runtime_summary_matches_founder_path():
    response = client.get('/api/operator/runtime-summary')
    assert response.status_code == 200
    payload = response.json()
    assert payload['success'] is True
    assert payload['preferred_runtime_name'] == 'murphy_core_v3_founder_execution_surface'
    assert payload['preferred_deployment_mode'] == 'founder_execution_surface'


def test_founder_execution_surface_v3_execute_includes_subsystem_family_selection():
    response = client.post('/api/execute', json={'task_description': 'run a swarm task'})
    assert response.status_code == 200
    payload = response.json()
    assert payload['success'] is True
    assert 'subsystem_family_selection' in payload
    assert 'selected_families' in payload['subsystem_family_selection']


def test_founder_execution_surface_v3_readiness_flags_family_selection():
    response = client.get('/api/readiness')
    assert response.status_code == 200
    payload = response.json()
    assert payload['status'] == 'ready'
    assert payload['subsystem_family_selection']['enabled'] is True
