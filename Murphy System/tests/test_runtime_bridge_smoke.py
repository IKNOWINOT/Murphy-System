from fastapi.testclient import TestClient

from src.runtime.murphy_core_bridge import create_bridge_app


def test_bridge_prefers_core():
    app = create_bridge_app(prefer_core=True)
    client = TestClient(app)
    response = client.get('/api/health')
    assert response.status_code == 200
    payload = response.json()
    assert payload['service'] == 'murphy_core'


def test_bridge_core_registry_available():
    app = create_bridge_app(prefer_core=True)
    client = TestClient(app)
    response = client.get('/api/registry/modules')
    assert response.status_code == 200
    payload = response.json()
    assert payload['success'] is True
    assert 'modules' in payload
