from fastapi.testclient import TestClient

from src.murphy_core.app_v3_canonical_execution_surface_v5 import create_app


client = TestClient(create_app())


def test_canonical_execution_surface_v5_health_identity():
    response = client.get('/api/health')
    assert response.status_code == 200
    payload = response.json()
    assert payload['service'] == 'murphy_core_v3_canonical_execution_surface_v5'


def test_canonical_execution_surface_v5_execute_includes_family_selection():
    response = client.post('/api/execute', json={'task_description': 'run a swarm task'})
    assert response.status_code == 200
    payload = response.json()
    assert payload['success'] is True
    assert 'subsystem_family_selection' in payload
    assert 'selected_families' in payload['subsystem_family_selection']


def test_canonical_execution_surface_v5_readiness_flags_founder_overlay():
    response = client.get('/api/readiness')
    assert response.status_code == 200
    payload = response.json()
    assert payload['status'] == 'ready'
    assert payload['founder_visibility_overlay']['enabled'] is True
