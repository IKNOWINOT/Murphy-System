from fastapi.testclient import TestClient

from src.runtime.murphy_core_bridge_v3_runtime_correct import create_bridge_app


def test_bridge_v3_runtime_correct_prefers_runtime_correct_app():
    app = create_bridge_app(prefer_core_v3_runtime_correct=True)
    client = TestClient(app)
    response = client.get('/api/operator/status')
    assert response.status_code == 200
    payload = response.json()
    assert payload['success'] is True
    assert payload['runtime']['preferred_factory'] == 'murphy_core_v3'


def test_bridge_v3_runtime_correct_health():
    app = create_bridge_app(prefer_core_v3_runtime_correct=True)
    client = TestClient(app)
    response = client.get('/api/health')
    assert response.status_code == 200
    payload = response.json()
    assert payload['service'] == 'murphy_core_v3'
