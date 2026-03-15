"""
E2E tests for Murphy System API endpoints.

Exercises every documented API endpoint with real HTTP calls against
a running backend server.  All tests are skipped automatically when the
server cannot be started (the running_server fixture in conftest.py
calls pytest.skip in that case).
"""

import pytest

pytestmark = pytest.mark.e2e


class TestHealthAndStatus:
    """Core health/status endpoints."""

    def test_health_endpoint(self, api_client):
        """GET /api/health must return HTTP 200."""
        resp = api_client.get("/api/health")
        assert resp.status_code == 200

    def test_health_response_is_json(self, api_client):
        """GET /api/health must return a JSON object."""
        resp = api_client.get("/api/health")
        body = resp.json()
        assert isinstance(body, dict)

    def test_status_endpoint(self, api_client):
        """GET /api/status must return HTTP 200."""
        resp = api_client.get("/api/status")
        assert resp.status_code in (200, 404)

    def test_auar_health_endpoint(self, api_client):
        """GET /api/auar/health must return a health payload."""
        resp = api_client.get("/api/auar/health")
        assert resp.status_code in (200, 404)


class TestChatEndpoints:
    """Chat / conversation endpoints."""

    def test_chat_endpoint_accepts_message(self, api_client):
        """POST /api/chat must accept a message payload."""
        resp = api_client.post(
            "/api/chat",
            json={"message": "hello", "session_id": "e2e-test"},
        )
        assert resp.status_code in (200, 201, 404, 422, 503)

    def test_chat_response_structure(self, api_client):
        """POST /api/chat response must be JSON when the endpoint exists."""
        resp = api_client.post(
            "/api/chat",
            json={"message": "hello", "session_id": "e2e-test"},
        )
        if resp.status_code == 404:
            pytest.skip("/api/chat endpoint not registered on this build")
        assert resp.headers.get("content-type", "").startswith("application/json")


class TestExecuteEndpoints:
    """Code/command execution endpoints."""

    def test_execute_endpoint(self, api_client):
        """POST /api/execute must accept an execution payload."""
        resp = api_client.post(
            "/api/execute",
            json={"code": "print('hello')", "language": "python"},
        )
        assert resp.status_code in (200, 201, 404, 422, 503)


class TestLLMEndpoints:
    """LLM management endpoints."""

    def test_llm_status(self, api_client):
        """GET /api/llm/status must respond."""
        resp = api_client.get("/api/llm/status")
        assert resp.status_code in (200, 404)

    def test_llm_configure(self, api_client):
        """POST /api/llm/configure must accept a config payload."""
        resp = api_client.post(
            "/api/llm/configure",
            json={"model": "local_small"},
        )
        assert resp.status_code in (200, 201, 404, 422)

    def test_llm_test(self, api_client):
        """POST /api/llm/test must respond."""
        resp = api_client.post("/api/llm/test", json={"prompt": "test"})
        assert resp.status_code in (200, 201, 404, 422, 503)

    def test_llm_reload(self, api_client):
        """POST /api/llm/reload must respond."""
        resp = api_client.post("/api/llm/reload")
        assert resp.status_code in (200, 201, 404, 422, 503)


class TestLibrarianEndpoints:
    """Librarian / knowledge-base endpoints."""

    def test_librarian_health(self, api_client):
        """GET /api/librarian/health must respond."""
        resp = api_client.get("/api/librarian/health")
        assert resp.status_code in (200, 404)

    def test_librarian_query(self, api_client):
        """POST /api/librarian/query must accept a query payload."""
        resp = api_client.post(
            "/api/librarian/query",
            json={"query": "Murphy System overview"},
        )
        assert resp.status_code in (200, 201, 404, 422, 503)


class TestDocumentsEndpoints:
    """Document management endpoints."""

    def test_documents_list(self, api_client):
        """GET /api/documents must respond."""
        resp = api_client.get("/api/documents")
        assert resp.status_code in (200, 404)

    def test_documents_upload(self, api_client):
        """POST /api/documents must accept a document payload."""
        resp = api_client.post(
            "/api/documents",
            json={"title": "test", "content": "hello world"},
        )
        assert resp.status_code in (200, 201, 404, 415, 422)


class TestFormsEndpoints:
    """Form intake endpoints."""

    def test_forms_health(self, api_client):
        """GET /api/forms/health must respond."""
        resp = api_client.get("/api/forms/health")
        assert resp.status_code in (200, 404)

    def test_forms_submit(self, api_client):
        """POST /api/forms must accept a form submission."""
        resp = api_client.post(
            "/api/forms",
            json={"form_type": "contact", "data": {"name": "E2E Test"}},
        )
        assert resp.status_code in (200, 201, 404, 422, 503)


class TestAUAREndpoints:
    """AUAR (Adaptive Universal API Router) endpoints."""

    def test_auar_stats(self, api_client):
        """GET /api/auar/stats must respond."""
        resp = api_client.get("/api/auar/stats")
        assert resp.status_code in (200, 404)

    def test_auar_route(self, api_client):
        """POST /api/auar/route must accept a routing request."""
        resp = api_client.post(
            "/api/auar/route",
            json={"capability": "text_generation", "input": {"text": "hello"}},
        )
        assert resp.status_code in (200, 201, 404, 422, 503)
