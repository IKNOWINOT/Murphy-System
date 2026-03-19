from fastapi.testclient import TestClient

from src.runtime.murphy_core_bridge_v3_canonical_execution_surface import create_bridge_app


def test_bridge_canonical_execution_surface_prefers_canonical_app():
    app = create_bridge_app(prefer_canonical_execution_surface=True)
    client = TestClient(app)
    response = client.get('/api/health')
    assert response.status_code == 200
    payload = response.json()
    assert payload['service'] == 'murphy_core_v3_canonical_execution_surface'


def test_bridge_canonical_execution_surface_founder_overlay_available():
    app = create_bridge_app(prefer_canonical_execution_surface=True)
    client = TestClient(app)
    response = client.get('/api/founder/visibility-summary')
    assert response.status_code == 200
    payload = response.json()
    assert payload['success'] is True
    assert payload['ops_status'] == 'operational'
