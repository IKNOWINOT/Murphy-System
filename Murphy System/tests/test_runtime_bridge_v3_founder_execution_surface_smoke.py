from fastapi.testclient import TestClient

from src.runtime.murphy_core_bridge_v3_founder_execution_surface import create_bridge_app


def test_bridge_founder_execution_surface_prefers_founder_app():
    app = create_bridge_app(prefer_founder_execution_surface=True)
    client = TestClient(app)
    response = client.get('/api/founder/visibility-summary')
    assert response.status_code == 200
    payload = response.json()
    assert payload['success'] is True
    assert payload['preferred_factory'] == 'murphy_core_v3'


def test_bridge_founder_execution_surface_health():
    app = create_bridge_app(prefer_founder_execution_surface=True)
    client = TestClient(app)
    response = client.get('/api/health')
    assert response.status_code == 200
    payload = response.json()
    assert payload['service'] == 'murphy_core_v3_founder_execution_surface'
