from fastapi.testclient import TestClient

from src.murphy_core.app import create_app


client = TestClient(create_app())


def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "healthy"
    assert payload["service"] == "murphy_core"


def test_readiness():
    response = client.get("/api/readiness")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert "core" in payload


def test_registry_modules():
    response = client.get("/api/registry/modules")
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert "modules" in payload


def test_chat_requires_message():
    response = client.post("/api/chat", json={})
    assert response.status_code == 400


def test_chat_trace_shape():
    response = client.post("/api/chat", json={"message": "build a workflow for invoice processing"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["trace_id"]
    assert payload["request_id"]
    assert payload["route"]
    assert isinstance(payload["gate_results"], list)


def test_recent_traces():
    client.post("/api/chat", json={"message": "hello from test"})
    response = client.get("/api/traces/recent")
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert isinstance(payload["traces"], list)
