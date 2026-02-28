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
    detect_feedback,
    DialogContext,
    INTENT_PATTERNS,
    DEFAULT_API_URL,
    WELCOME_TEXT,
    RECONNECT_INTERVAL,
    MAX_RECONNECT_ATTEMPTS,
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

    def test_contains_new_commands(self):
        assert "start interview" in WELCOME_TEXT
        assert "set api" in WELCOME_TEXT
        assert "reconnect" in WELCOME_TEXT


# ---------------------------------------------------------------------------
# API Client — new methods
# ---------------------------------------------------------------------------


class TestMurphyAPIClientNew:
    """Tests for newly added API client methods."""

    def test_set_base_url(self):
        client = MurphyAPIClient(base_url="http://localhost:8000")
        client.session_id = "old-session"
        client.set_base_url("http://newhost:9000/")
        assert client.base_url == "http://newhost:9000"
        assert client.session_id is None
        assert client.last_error is None

    @patch("murphy_terminal.requests.get")
    def test_test_connection_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"status": "healthy", "version": "2.0"}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        client = MurphyAPIClient(base_url="http://localhost:8000")
        ok, detail = client.test_connection()
        assert ok is True
        assert "Healthy" in detail
        assert client.last_error is None

    @patch("murphy_terminal.requests.get")
    def test_test_connection_refused(self, mock_get):
        mock_get.side_effect = requests.ConnectionError("refused")
        client = MurphyAPIClient(base_url="http://localhost:8000")
        ok, detail = client.test_connection()
        assert ok is False
        assert "refused" in detail.lower() or "connection" in detail.lower()
        assert client.last_error is not None

    @patch("murphy_terminal.requests.get")
    def test_test_connection_timeout(self, mock_get):
        mock_get.side_effect = requests.Timeout("timed out")
        client = MurphyAPIClient(base_url="http://localhost:8000", timeout=5)
        ok, detail = client.test_connection()
        assert ok is False
        assert "timeout" in detail.lower() or "Timeout" in detail


# ---------------------------------------------------------------------------
# Dialog Context — synthetic interview
# ---------------------------------------------------------------------------


class TestDialogContext:
    """Tests for the interview / dialog context tracker."""

    def test_initial_state(self):
        ctx = DialogContext()
        assert ctx.active is False
        assert ctx.step_index == 0
        assert ctx.collected == {}
        assert ctx.is_complete is False

    def test_start_interview(self):
        ctx = DialogContext()
        prompt = ctx.start()
        assert ctx.active is True
        assert "Step 1/" in prompt
        assert "name" in ctx.asked_questions

    def test_advance_records_answer(self):
        ctx = DialogContext()
        ctx.start()
        response = ctx.advance("Acme Corp")
        assert ctx.collected["name"] == "Acme Corp"
        assert ctx.step_index == 1
        assert "Step 2/" in response

    def test_advance_to_completion(self):
        ctx = DialogContext()
        ctx.start()
        for i in range(len(DialogContext.INTERVIEW_STEPS)):
            ctx.advance(f"answer-{i}")
        assert ctx.is_complete is True
        assert ctx.active is False

    def test_skip_step(self):
        ctx = DialogContext()
        ctx.start()
        response = ctx.advance("skip")
        assert ctx.collected["name"] == "(skipped)"
        assert ctx.step_index == 1
        assert "Step 2/" in response

    def test_go_back(self):
        ctx = DialogContext()
        ctx.start()
        ctx.advance("Acme Corp")
        assert ctx.step_index == 1
        response = ctx._go_back()
        assert ctx.step_index == 0
        assert "Step 1/" in response

    def test_go_back_at_start(self):
        ctx = DialogContext()
        ctx.start()
        response = ctx._go_back()
        assert ctx.step_index == 0
        assert "beginning" in response.lower() or "Step 1/" in response

    def test_review_shows_collected(self):
        ctx = DialogContext()
        ctx.start()
        ctx.advance("Acme Corp")
        summary = ctx.summary()
        assert "Acme Corp" in summary

    def test_summary_empty(self):
        ctx = DialogContext()
        assert "no information" in ctx.summary().lower()

    def test_progress_label(self):
        ctx = DialogContext()
        ctx.start()
        label = ctx.progress_label
        assert "Step 1/" in label

    def test_infer_all(self):
        assert DialogContext._infer_value("billing_tier", "all of them") == "all"
        assert DialogContext._infer_value("billing_tier", "all tiers") == "all"
        assert DialogContext._infer_value("billing_tier", "everything") == "all"

    def test_infer_unsure(self):
        assert DialogContext._infer_value("use_case", "not sure") == "(needs guidance)"
        assert DialogContext._infer_value("use_case", "idk") == "(needs guidance)"
        assert DialogContext._infer_value("use_case", "no idea") == "(needs guidance)"

    def test_infer_yes_no(self):
        assert DialogContext._infer_value("confirm", "yes") == "yes"
        assert DialogContext._infer_value("confirm", "yep") == "yes"
        assert DialogContext._infer_value("confirm", "no") == "no"
        assert DialogContext._infer_value("confirm", "nope") == "no"

    def test_infer_passthrough(self):
        assert DialogContext._infer_value("name", "my company", "My Company") == "My Company"

    def test_record_feedback(self):
        ctx = DialogContext()
        ctx.record_feedback("system is too complicated")
        assert len(ctx.feedback_log) == 1
        assert "complicated" in ctx.feedback_log[0]


# ---------------------------------------------------------------------------
# Feedback detection
# ---------------------------------------------------------------------------


class TestFeedbackDetection:
    """Tests for the frustration / feedback detection patterns."""

    def test_detects_frustration(self):
        assert detect_feedback("this is too complicated") is True
        assert detect_feedback("I'm confused") is True
        assert detect_feedback("this is broken") is True
        assert detect_feedback("it's not working") is True

    def test_detects_feedback_keywords(self):
        assert detect_feedback("I have some feedback") is True
        assert detect_feedback("here's a suggestion") is True

    def test_detects_help_request(self):
        assert detect_feedback("please help me") is True
        assert detect_feedback("i need help") is True
        assert detect_feedback("I'm stuck") is True

    def test_no_feedback_for_normal_input(self):
        assert detect_feedback("show health status") is False
        assert detect_feedback("hello there") is False
        assert detect_feedback("run task deploy") is False


# ---------------------------------------------------------------------------
# New intent detection
# ---------------------------------------------------------------------------


class TestNewIntentDetection:
    """Tests for newly added intent patterns."""

    def test_set_api_intent(self):
        assert detect_intent("set api http://host:9000") == "intent_set_api"
        assert detect_intent("set_api http://host:9000") == "intent_set_api"

    def test_test_api_intent(self):
        assert detect_intent("test api") == "intent_test_api"
        assert detect_intent("test connection") == "intent_test_api"
        assert detect_intent("test_connection") == "intent_test_api"

    def test_reconnect_intent(self):
        assert detect_intent("reconnect") == "intent_reconnect"

    def test_start_interview_intent(self):
        assert detect_intent("start interview") == "intent_start_interview"
        assert detect_intent("onboard me") == "intent_start_interview"
        assert detect_intent("setup") == "intent_start_interview"
        assert detect_intent("begin") == "intent_start_interview"

    def test_skip_intent(self):
        assert detect_intent("skip") == "intent_skip"

    def test_back_intent(self):
        assert detect_intent("back") == "intent_back"
        assert detect_intent("previous") == "intent_back"

    def test_review_intent(self):
        assert detect_intent("review") == "intent_review"

    def test_restart_intent(self):
        assert detect_intent("restart") == "intent_restart_interview"

    def test_confirm_intent(self):
        assert detect_intent("confirm") == "intent_confirm"


# ---------------------------------------------------------------------------
# App — new attributes
# ---------------------------------------------------------------------------


class TestMurphyTerminalAppNew:
    """Tests for new application attributes and configuration."""

    def test_app_has_dialog_context(self):
        app = MurphyTerminalApp(api_url="http://localhost:9999")
        assert isinstance(app.dialog, DialogContext)

    def test_app_reconnect_defaults(self):
        app = MurphyTerminalApp(api_url="http://localhost:9999")
        assert app._reconnect_attempts == 0
        assert RECONNECT_INTERVAL > 0
        assert MAX_RECONNECT_ATTEMPTS > 0
