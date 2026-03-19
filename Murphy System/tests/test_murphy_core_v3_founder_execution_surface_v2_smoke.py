from fastapi.testclient import TestClient

from src.murphy_core.app_v3_founder_execution_surface_v2 import create_app


client = TestClient(create_app())


def test_founder_execution_surface_v2_runtime_summary_matches_founder_path():
    response = client.get('/api/operator/runtime-summary')
    assert response.status_code == 200
    payload = response.json()
    assert payload['success'] is True
    assert payload['preferred_runtime_name'] == 'murphy_core_v3_founder_execution_surface'
    assert payload['preferred_deployment_mode'] == 'founder_execution_surface'


def test_founder_execution_surface_v2_founder_summary_and_layer_index():
    response_summary = client.get('/api/founder/visibility-summary')
    response_layers = client.get('/api/founder/layer-index')
    assert response_summary.status_code == 200
    assert response_layers.status_code == 200
    summary = response_summary.json()
    layers = response_layers.json()
    assert summary['success'] is True
    assert layers['success'] is True
    assert summary['preferred_deployment_mode'] == 'founder_execution_surface'
    assert 'by_layer' in layers


def test_founder_execution_surface_v2_execute_includes_capability_gate():
    response = client.post('/api/execute', json={'task_description': 'run a swarm task'})
    assert response.status_code == 200
    payload = response.json()
    assert payload['success'] is True
    assert payload['capability_gate']['gate_name'] == 'capability_selection'
