from fastapi.testclient import TestClient

from src.murphy_core.app_v3_runtime_surface import create_app


client = TestClient(create_app())


def test_operator_runtime_endpoint_exists():
    response = client.get('/api/operator/runtime')
    assert response.status_code == 200
    payload = response.json()
    assert payload['success'] is True
    assert 'preferred_runtime' in payload
    assert 'deployment_modes' in payload


def test_operator_runtime_summary_endpoint_exists():
    response = client.get('/api/operator/runtime-summary')
    assert response.status_code == 200
    payload = response.json()
    assert payload['success'] is True
    assert payload['preferred_deployment_mode'] == 'direct_core_runtime_correct'
    assert payload['transitional_deployment_mode'] == 'legacy_compat_shell'


def test_readiness_includes_runtime_summary():
    response = client.get('/api/readiness')
    assert response.status_code == 200
    payload = response.json()
    assert payload['status'] == 'ready'
    assert 'runtime_summary' in payload
