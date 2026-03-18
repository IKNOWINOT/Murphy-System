from fastapi.testclient import TestClient

from src.murphy_core.app_v3 import create_app


client = TestClient(create_app())


def test_health_v3():
    response = client.get('/api/health')
    assert response.status_code == 200
    payload = response.json()
    assert payload['status'] == 'healthy'
    assert payload['service'] == 'murphy_core_v3'


def test_operator_status_v3():
    response = client.get('/api/operator/status')
    assert response.status_code == 200
    payload = response.json()
    assert payload['success'] is True
    assert 'runtime' in payload
    assert 'providers' in payload
    assert 'gates' in payload


def test_operator_summary_v3():
    response = client.get('/api/operator/summary')
    assert response.status_code == 200
    payload = response.json()
    assert payload['success'] is True
    assert payload['preferred_factory'] == 'murphy_core_v2'


def test_readiness_v3_includes_operator_summary():
    response = client.get('/api/readiness')
    assert response.status_code == 200
    payload = response.json()
    assert payload['status'] == 'ready'
    assert 'operator_summary' in payload
