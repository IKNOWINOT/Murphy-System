from fastapi.testclient import TestClient

from src.runtime.murphy_core_bridge_v2 import create_bridge_app


def test_bridge_v2_prefers_core_v2():
    app = create_bridge_app(prefer_core_v2=True)
    client = TestClient(app)
    response = client.get('/api/health')
    assert response.status_code == 200
    payload = response.json()
    assert payload['service'] == 'murphy_core_v2'


def test_bridge_v2_system_map_available():
    app = create_bridge_app(prefer_core_v2=True)
    client = TestClient(app)
    response = client.get('/api/system/map')
    assert response.status_code == 200
    payload = response.json()
    assert payload['success'] is True
    assert 'compatibility_routes' in payload
