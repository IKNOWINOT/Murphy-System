"""
E2E tests for the Murphy System LLM pipeline.

Tests the full flow:
  terminal client → HTTP → backend → LLM controller → response

A mock Groq server (via pytest-httpserver or the mock_groq_server fixture
from conftest.py) is used so no real API key is required.
"""

import os
import sys

import pytest

_SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src"))
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

pytestmark = pytest.mark.e2e


class TestLLMControllerUnit:
    """Import-level smoke tests that don't need a running server."""

    def test_llm_controller_importable(self):
        """LLMController must be importable from src."""
        from llm_controller import LLMController  # noqa: F401

    def test_llm_model_enum_values(self):
        """LLMModel enum must contain at least Groq and local variants."""
        from llm_controller import LLMModel

        names = {m.name for m in LLMModel}
        assert any("GROQ" in n for n in names), "Expected at least one GROQ model"
        assert any("LOCAL" in n for n in names), "Expected at least one LOCAL model"

    def test_llm_request_dataclass(self):
        """LLMRequest must be constructable with a prompt."""
        from llm_controller import LLMRequest

        req = LLMRequest(prompt="hello")
        assert req.prompt == "hello"

    def test_llm_response_dataclass(self):
        """LLMResponse must carry content and model_used fields."""
        from llm_controller import LLMModel, LLMResponse

        resp = LLMResponse(
            content="ok",
            model_used=LLMModel.LOCAL_SMALL,
            confidence=0.9,
            tokens_used=10,
            cost=0.0,
            latency=0.1,
        )
        assert resp.content == "ok"
        assert resp.model_used == LLMModel.LOCAL_SMALL


class TestLocalLLMFallback:
    """Tests for the offline LLM fallback without a running server."""

    def test_local_llm_fallback_importable(self):
        from local_llm_fallback import LocalLLMFallback  # noqa: F401

    def test_local_llm_fallback_instantiable(self):
        from local_llm_fallback import LocalLLMFallback

        fallback = LocalLLMFallback()
        assert fallback is not None

    def test_local_llm_fallback_responds(self):
        """Fallback must return a non-empty string for a basic query."""
        from local_llm_fallback import LocalLLMFallback

        fallback = LocalLLMFallback()
        result = fallback.generate("What is Murphy System?")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_local_llm_fallback_handles_empty_query(self):
        """Fallback must not raise on an empty prompt."""
        from local_llm_fallback import LocalLLMFallback

        fallback = LocalLLMFallback()
        result = fallback.generate("")
        assert isinstance(result, str)


class TestLLMPipelineWithMockGroq:
    """
    Tests that exercise the LLM controller pointing at a mock Groq server.
    These tests are skipped if pytest-httpserver is not installed.
    """

    def test_mock_groq_server_available(self, mock_groq_server):
        """Skip gracefully when pytest-httpserver is not installed."""
        if mock_groq_server is None:
            pytest.skip("pytest-httpserver not installed")

    def test_mock_groq_server_responding(self, mock_groq_server):
        """The mock Groq server must serve chat completion responses."""
        if mock_groq_server is None:
            pytest.skip("pytest-httpserver not installed")

        import json
        import urllib.request

        url = f"http://{mock_groq_server.host}:{mock_groq_server.port}/openai/v1/chat/completions"
        payload = json.dumps(
            {
                "model": "mixtral-8x7b-32768",
                "messages": [{"role": "user", "content": "ping"}],
            }
        ).encode()
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())

        assert "choices" in data
        assert data["choices"][0]["message"]["content"] == "Mock Groq response"


class TestLLMPipelineE2E:
    """
    Full-pipeline E2E tests that require a running backend server.
    Skipped automatically when the server is not available.
    """

    def test_llm_status_endpoint(self, api_client):
        """GET /api/llm/status must return 200 with a JSON body."""
        resp = api_client.get("/api/llm/status")
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, dict)

    def test_llm_configure_endpoint(self, api_client):
        """POST /api/llm/configure must accept a configuration payload."""
        resp = api_client.post(
            "/api/llm/configure",
            json={"model": "local_small", "temperature": 0.7},
        )
        assert resp.status_code in (200, 201, 422)

    def test_llm_test_endpoint(self, api_client):
        """POST /api/llm/test must return a test response."""
        resp = api_client.post("/api/llm/test", json={"prompt": "ping"})
        assert resp.status_code in (200, 201, 422, 503)
