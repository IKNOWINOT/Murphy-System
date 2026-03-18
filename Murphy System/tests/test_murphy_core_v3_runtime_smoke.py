from fastapi.testclient import TestClient

from src.murphy_core.app_v3_runtime import create_app


client = TestClient(create_app())


def test_operator_status_runtime_prefers_v3():
    response = client.get('/api/operator/status')
    assert response.status_code == 200
    payload = response.json()
    assert payload['success'] is True
    assert payload['runtime']['preferred_factory'] == 'murphy_core_v3'


def test_operator_summary_runtime_prefers_v3():
    response = client.get('/api/operator/summary')
    assert response.status_code == 200
    payload = response.json()
    assert payload['success'] is True
    assert payload['preferred_factory'] == 'murphy_core_v3'


def test_readiness_runtime_includes_v3_operator_summary():
    response = client.get('/api/readiness')
    assert response.status_code == 200
    payload = response.json()
    assert payload['status'] == 'ready'
    assert payload['operator_summary']['preferred_factory'] == 'murphy_core_v3'
