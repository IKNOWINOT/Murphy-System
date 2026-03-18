from fastapi.testclient import TestClient

from src.murphy_core.app_v2 import create_app


client = TestClient(create_app())


def test_health_v2():
    response = client.get('/api/health')
    assert response.status_code == 200
    payload = response.json()
    assert payload['status'] == 'healthy'
    assert payload['service'] == 'murphy_core_v2'


def test_readiness_v2_has_provider_and_gate_health():
    response = client.get('/api/readiness')
    assert response.status_code == 200
    payload = response.json()
    assert payload['status'] == 'ready'
    assert 'provider_health' in payload
    assert 'gate_health' in payload


def test_system_map_v2_includes_compatibility_routes():
    response = client.get('/api/system/map')
    assert response.status_code == 200
    payload = response.json()
    assert payload['success'] is True
    assert 'compatibility_routes' in payload


def test_chat_v2_returns_trace_and_route():
    response = client.post('/api/chat', json={'message': 'build a production workflow for invoice processing'})
    assert response.status_code == 200
    payload = response.json()
    assert payload['trace_id']
    assert payload['route']
    assert isinstance(payload['gate_results'], list)
