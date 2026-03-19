from fastapi.testclient import TestClient

from src.murphy_core.app_v3_founder_execution_surface import create_app


client = TestClient(create_app())


def test_founder_visibility_endpoints_exist():
    response_visibility = client.get('/api/founder/visibility')
    response_summary = client.get('/api/founder/visibility-summary')
    response_layers = client.get('/api/founder/layer-index')
    assert response_visibility.status_code == 200
    assert response_summary.status_code == 200
    assert response_layers.status_code == 200
    assert response_visibility.json()['success'] is True
    assert response_summary.json()['success'] is True
    assert response_layers.json()['success'] is True


def test_execute_includes_capability_gate():
    response = client.post('/api/execute', json={'task_description': 'run a swarm task'})
    assert response.status_code == 200
    payload = response.json()
    assert payload['success'] is True
    assert 'capability_gate' in payload
    assert payload['capability_gate']['gate_name'] == 'capability_selection'


def test_readiness_includes_founder_summary():
    response = client.get('/api/readiness')
    assert response.status_code == 200
    payload = response.json()
    assert payload['status'] == 'ready'
    assert 'founder_summary' in payload
    assert payload['founder_summary']['family_count'] >= 1
