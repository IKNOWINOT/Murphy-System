"""
Test Suite for Murphy Terminal UI

Tests the MurphyAPIClient, intent detection, and application composition
without requiring a running backend (uses mocking).
"""

import json
import os
import sys
import re
from unittest.mock import patch, MagicMock

import requests
import pytest

# Ensure the parent directory (containing murphy_terminal.py) is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from murphy_terminal import (
    MurphyAPIClient,
    MurphyTerminalApp,
    detect_intent,
    INTENT_PATTERNS,
    DEFAULT_API_URL,
    WELCOME_TEXT,
)


# ---------------------------------------------------------------------------
# Intent Detection
# ---------------------------------------------------------------------------


class TestIntentDetection:
    """Tests for the local keyword/regex intent detector."""

    def test_health_intent(self):
        assert detect_intent("show health") == "intent_health"
        assert detect_intent("is the system alive?") == "intent_health"
        assert detect_intent("ping") == "intent_health"

    def test_status_intent(self):
        assert detect_intent("show status") == "intent_status"
        assert detect_intent("what is the system state") == "intent_status"
        assert detect_intent("open dashboard") == "intent_status"

    def test_info_intent(self):
        assert detect_intent("show info") == "intent_info"
        assert detect_intent("tell me about the system") == "intent_info"
        assert detect_intent("what version is running") == "intent_info"

    def test_help_intent(self):
        assert detect_intent("help") == "intent_help"
        assert detect_intent("show commands") == "intent_help"
        assert detect_intent("what can you do") == "intent_help"

    def test_exit_intent(self):
        assert detect_intent("exit") == "intent_exit"
        assert detect_intent("quit") == "intent_exit"
        assert detect_intent("bye") == "intent_exit"

    def test_corrections_intent(self):
        assert detect_intent("show corrections") == "intent_corrections"
        assert detect_intent("correction stats") == "intent_corrections"

    def test_hitl_intent(self):
        assert detect_intent("show pending interventions") == "intent_hitl"
        assert detect_intent("show hitl") == "intent_hitl"

    def test_execute_intent(self):
        assert detect_intent("execute onboarding") == "intent_execute"
        assert detect_intent("run task for site") == "intent_execute"
        assert detect_intent("launch deploy") == "intent_execute"

    def test_no_intent_for_general_chat(self):
        assert detect_intent("hello there") is None
        assert detect_intent("tell me a joke") is None
        assert detect_intent("how are you") is None

    def test_intent_case_insensitive(self):
        assert detect_intent("HEALTH") == "intent_health"
        assert detect_intent("Status") == "intent_status"
        assert detect_intent("EXIT") == "intent_exit"


# ---------------------------------------------------------------------------
# API Client
# ---------------------------------------------------------------------------


class TestMurphyAPIClient:
    """Tests for the REST API client (mocked HTTP)."""

    def _make_client(self, base_url: str = "http://localhost:8000") -> MurphyAPIClient:
        return MurphyAPIClient(base_url=base_url, timeout=5)

    @patch("murphy_terminal.requests.get")
    def test_health(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"status": "healthy", "version": "1.0"}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        client = self._make_client()
        result = client.health()

        assert result == {"status": "healthy", "version": "1.0"}
        mock_get.assert_called_once_with(
            "http://localhost:8000/api/health", timeout=5
        )

    @patch("murphy_terminal.requests.get")
    def test_status(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"state": "running"}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        client = self._make_client()
        result = client.status()

        assert result["state"] == "running"
        mock_get.assert_called_once_with(
            "http://localhost:8000/api/status", timeout=5
        )

    @patch("murphy_terminal.requests.get")
    def test_info(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"version": "1.0", "name": "Murphy"}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        client = self._make_client()
        result = client.info()

        assert result["name"] == "Murphy"

    @patch("murphy_terminal.requests.post")
    def test_create_session(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"session_id": "sess-123"}
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        client = self._make_client()
        result = client.create_session("test")

        assert result["session_id"] == "sess-123"
        assert client.session_id == "sess-123"

    @patch("murphy_terminal.requests.post")
    def test_chat(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"response": "Hello!"}
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        client = self._make_client()
        client.session_id = "sess-1"
        result = client.chat("hi")

        assert result["response"] == "Hello!"
        mock_post.assert_called_once_with(
            "http://localhost:8000/api/chat",
            json={"message": "hi", "session_id": "sess-1"},
            timeout=5,
        )

    @patch("murphy_terminal.requests.post")
    def test_chat_without_session(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"response": "Hello!"}
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        client = self._make_client()
        result = client.chat("hello")

        mock_post.assert_called_once_with(
            "http://localhost:8000/api/chat",
            json={"message": "hello"},
            timeout=5,
        )

    @patch("murphy_terminal.requests.post")
    def test_execute(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"success": True, "result": "done"}
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        client = self._make_client()
        result = client.execute("onboard site foo")

        assert result["success"] is True
        mock_post.assert_called_once_with(
            "http://localhost:8000/api/execute",
            json={
                "task_description": "onboard site foo",
                "task_type": "general",
            },
            timeout=5,
        )

    @patch("murphy_terminal.requests.post")
    def test_execute_with_session_and_params(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"success": True}
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        client = self._make_client()
        client.session_id = "s-1"
        result = client.execute("deploy", parameters={"env": "prod"})

        mock_post.assert_called_once_with(
            "http://localhost:8000/api/execute",
            json={
                "task_description": "deploy",
                "task_type": "general",
                "parameters": {"env": "prod"},
                "session_id": "s-1",
            },
            timeout=5,
        )

    @patch("murphy_terminal.requests.get")
    def test_corrections_stats(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"total": 42}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        client = self._make_client()
        result = client.corrections_stats()

        assert result["total"] == 42

    @patch("murphy_terminal.requests.get")
    def test_hitl_pending(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"pending": []}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        client = self._make_client()
        result = client.hitl_pending()

        assert result["pending"] == []

    @patch("murphy_terminal.requests.get")
    def test_hitl_stats(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"total_interventions": 5}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        client = self._make_client()
        result = client.hitl_stats()

        assert result["total_interventions"] == 5

    def test_url_trailing_slash_stripped(self):
        client = MurphyAPIClient(base_url="http://host:9000/")
        assert client.base_url == "http://host:9000"

    @patch("murphy_terminal.requests.get")
    def test_connection_error_propagates(self, mock_get):
        mock_get.side_effect = requests.ConnectionError("refused")
        client = self._make_client()
        with pytest.raises(requests.ConnectionError):
            client.health()


# ---------------------------------------------------------------------------
# App composition (smoke tests)
# ---------------------------------------------------------------------------


class TestMurphyTerminalApp:
    """Smoke tests for the Textual application."""

    def test_app_instantiation(self):
        app = MurphyTerminalApp(api_url="http://localhost:9999")
        assert app.client.base_url == "http://localhost:9999"
        assert app.TITLE == "Murphy System Terminal"

    def test_app_default_api_url(self):
        app = MurphyTerminalApp()
        assert app.client.base_url == DEFAULT_API_URL

    def test_detect_intent_patterns_are_compiled(self):
        for pattern, name in INTENT_PATTERNS:
            assert isinstance(pattern, re.Pattern)
            assert name.startswith("intent_")


# ---------------------------------------------------------------------------
# Welcome text
# ---------------------------------------------------------------------------


class TestWelcomeText:
    """Ensure the welcome banner contains expected content."""

    def test_contains_murphy(self):
        assert "Murphy" in WELCOME_TEXT

    def test_contains_examples(self):
        assert "health" in WELCOME_TEXT
        assert "help" in WELCOME_TEXT
        assert "exit" in WELCOME_TEXT
