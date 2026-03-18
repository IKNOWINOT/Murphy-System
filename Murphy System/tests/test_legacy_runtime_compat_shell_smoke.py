from fastapi.testclient import TestClient

from src.runtime.legacy_runtime_compat_shell import create_app


def test_compat_shell_delegates_chat_to_core():
    app = create_app(prefer_core=True)
    client = TestClient(app)
    response = client.post('/api/chat', json={'message': 'route through compat shell'})
    assert response.status_code == 200
    payload = response.json()
    assert payload['trace_id']
    assert payload['route']


def test_compat_shell_delegates_execute_to_core():
    app = create_app(prefer_core=True)
    client = TestClient(app)
    response = client.post('/api/execute', json={'task_description': 'execute through compat shell'})
    assert response.status_code == 200
    payload = response.json()
    assert payload['trace_id']
    assert payload['route']
