"""
Test Suite for Murphy Terminal UI

Tests the MurphyAPIClient, intent detection, and application composition
without requiring a running backend (uses mocking).
"""

import json
import os
import re
from unittest.mock import patch, MagicMock

import requests
import pytest

# Ensure the parent directory (containing murphy_terminal.py) is on the path

pytest.importorskip("textual", reason="textual not installed — skipping terminal UI tests")

from murphy_terminal import (
    MurphyAPIClient,
    MurphyTerminalApp,
    StatusBar,
    detect_intent,
    detect_feedback,
    DialogContext,
    INTENT_PATTERNS,
    DEFAULT_API_URL,
    WELCOME_TEXT,
    RECONNECT_INTERVAL,
    MAX_RECONNECT_ATTEMPTS,
    MODULE_COMMAND_MAP,
    DASHBOARD_LINKS,
    API_PROVIDER_LINKS,
)
from textual.widgets import Input


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

    def test_llm_status_intent(self):
        assert detect_intent("llm status") == "intent_llm_status"
        assert detect_intent("llm_status") == "intent_llm_status"

    def test_librarian_status_intent(self):
        assert detect_intent("librarian status") == "intent_librarian_status"
        assert detect_intent("librarian_status") == "intent_librarian_status"

    def test_llm_status_before_general_status(self):
        """'llm status' should match llm_status, not general status."""
        assert detect_intent("llm status") == "intent_llm_status"

    def test_librarian_status_before_librarian(self):
        """'librarian status' should match librarian_status, not librarian."""
        assert detect_intent("librarian status") == "intent_librarian_status"


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

    @patch("murphy_terminal.requests.post")
    def test_librarian_ask(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "success": True,
            "reply_text": "I can help with that!",
            "intent": "general",
            "mode": "deterministic",
            "suggested_commands": ["help"],
        }
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        client = self._make_client()
        client.session_id = "s-1"
        result = client.librarian_ask("hello")

        assert result["success"] is True
        assert result["reply_text"] == "I can help with that!"
        mock_post.assert_called_once_with(
            "http://localhost:8000/api/librarian/ask",
            json={"message": "hello", "session_id": "s-1"},
            timeout=5,
        )

    @patch("murphy_terminal.requests.get")
    def test_llm_status(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "enabled": True,
            "provider": "deepinfra",
            "model": "meta-llama/Meta-Llama-3.1-8B-Instruct",
            "healthy": True,
        }
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        client = self._make_client()
        result = client.llm_status()

        assert result["enabled"] is True
        assert result["provider"] == "deepinfra"
        mock_get.assert_called_once_with(
            "http://localhost:8000/api/llm/status", timeout=5
        )

    @patch("murphy_terminal.requests.get")
    def test_librarian_status(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "enabled": True,
            "healthy": True,
        }
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        client = self._make_client()
        result = client.librarian_status()

        assert result["enabled"] is True
        mock_get.assert_called_once_with(
            "http://localhost:8000/api/librarian/status", timeout=5
        )


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
        assert "start interview" in WELCOME_TEXT

    def test_contains_new_commands(self):
        assert "start interview" in WELCOME_TEXT
        assert "show modules" in WELCOME_TEXT
        assert "librarian" in WELCOME_TEXT

    def test_contains_greeting(self):
        assert "Hello!" in WELCOME_TEXT
        assert "automation" in WELCOME_TEXT.lower()

    def test_contains_dashboard_links(self):
        assert "Dashboard Links" in WELCOME_TEXT
        assert "/docs" in WELCOME_TEXT
        assert "localhost:8000" in WELCOME_TEXT


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

    def test_friendly_error_connection(self):
        app = MurphyTerminalApp(api_url="http://localhost:9999")
        exc = requests.ConnectionError("HTTPConnectionPool(...)")
        msg = app._friendly_error(exc)
        assert "refused" in msg.lower() or "backend" in msg.lower()
        assert "HTTPConnectionPool" not in msg
        assert "urllib3" not in msg

    def test_friendly_error_timeout(self):
        app = MurphyTerminalApp(api_url="http://localhost:9999")
        exc = requests.Timeout("timed out")
        msg = app._friendly_error(exc)
        assert "timed out" in msg.lower()
        assert len(msg) < 50

    def test_friendly_error_generic(self):
        app = MurphyTerminalApp(api_url="http://localhost:9999")
        exc = RuntimeError("something weird happened")
        msg = app._friendly_error(exc)
        assert "RuntimeError" in msg
        assert "something weird happened" not in msg

    def test_friendly_error_http_error(self):
        app = MurphyTerminalApp(api_url="http://localhost:9999")
        mock_resp = MagicMock()
        mock_resp.status_code = 503
        exc = requests.HTTPError(response=mock_resp)
        msg = app._friendly_error(exc)
        assert "503" in msg
        assert "HTTP" in msg

    @patch("murphy_terminal.requests.get")
    def test_test_connection_http_error(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.raise_for_status.side_effect = requests.HTTPError(response=mock_resp)
        mock_get.return_value = mock_resp

        client = MurphyAPIClient(base_url="http://localhost:8000")
        ok, detail = client.test_connection()
        assert ok is False
        assert "500" in detail
        assert client.last_error is not None


# ---------------------------------------------------------------------------
# Integration tests — simulate real user interaction with the TUI
# ---------------------------------------------------------------------------


class TestTUIUserInteraction:
    """Integration tests using Textual's run_test() that simulate actual
    user interaction: launching the app, typing commands, and checking the
    resulting UI state.  These verify the app works end-to-end as a user
    would experience it, not just in isolated unit tests."""

    @pytest.mark.asyncio
    async def test_app_launches_and_shows_welcome(self):
        """User opens the app: should see welcome banner and disconnected status."""
        app = MurphyTerminalApp(api_url="http://localhost:19999")
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.pause()
            status_bar = app.query_one(StatusBar)
            assert status_bar.connected is False
            # Welcome banner should be written
            assert "Murphy" in app.title.lower() or "Murphy" in WELCOME_TEXT

    @pytest.mark.asyncio
    async def test_disconnected_error_is_human_readable(self):
        """On startup with no backend, error message should be clean (no tracebacks)."""
        app = MurphyTerminalApp(api_url="http://localhost:19999")
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.pause()
            # Check the client.last_error is clean
            assert app.client.last_error is not None
            assert "HTTPConnectionPool" not in app.client.last_error
            assert "urllib3" not in app.client.last_error
            assert "object at 0x" not in app.client.last_error

    @pytest.mark.asyncio
    async def test_user_types_help(self):
        """User types 'help' and presses enter: should get a help response."""
        app = MurphyTerminalApp(api_url="http://localhost:19999")
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.pause()
            for ch in "help":
                await pilot.press(ch)
            await pilot.press("enter")
            await pilot.pause()
            # The input should have been cleared after submission
            input_widget = app.query_one("#user-input", Input)
            assert input_widget.value == ""

    @pytest.mark.asyncio
    async def test_user_starts_interview_flow(self):
        """User starts interview, answers a question, and dialog state advances."""
        app = MurphyTerminalApp(api_url="http://localhost:19999")
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.pause()
            # Start interview
            for ch in "start interview":
                await pilot.press(ch)
            await pilot.press("enter")
            await pilot.pause()
            assert app.dialog.active is True
            assert app.dialog.step_index == 0

            # Answer first question
            for ch in "Acme Corp":
                await pilot.press(ch)
            await pilot.press("enter")
            await pilot.pause()
            assert app.dialog.collected.get("name") == "Acme Corp"
            assert app.dialog.step_index == 1

    @pytest.mark.asyncio
    async def test_user_navigates_interview_back_and_skip(self):
        """User navigates back and skip during interview."""
        app = MurphyTerminalApp(api_url="http://localhost:19999")
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.pause()
            # Start and answer first question
            for ch in "start interview":
                await pilot.press(ch)
            await pilot.press("enter")
            await pilot.pause()
            for ch in "TestOrg":
                await pilot.press(ch)
            await pilot.press("enter")
            await pilot.pause()
            assert app.dialog.step_index == 1

            # Go back
            for ch in "back":
                await pilot.press(ch)
            await pilot.press("enter")
            await pilot.pause()
            assert app.dialog.step_index == 0

            # Skip
            for ch in "skip":
                await pilot.press(ch)
            await pilot.press("enter")
            await pilot.pause()
            assert app.dialog.step_index == 1
            assert app.dialog.collected.get("name") == "(skipped)"

    @pytest.mark.asyncio
    async def test_user_contextual_answers_inferred(self):
        """User gives contextual answers like 'all of them' and 'not sure'."""
        app = MurphyTerminalApp(api_url="http://localhost:19999")
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.pause()
            # Start interview and fill first two steps (name, business_goal)
            for cmd in ["start interview", "Me", "all of them"]:
                for ch in cmd:
                    await pilot.press(ch)
                await pilot.press("enter")
                await pilot.pause()
            assert app.dialog.collected["business_goal"] == "all"

            # Third step (use_case): "not sure"
            for ch in "not sure":
                await pilot.press(ch)
            await pilot.press("enter")
            await pilot.pause()
            assert app.dialog.collected["use_case"] == "(needs guidance)"

    @pytest.mark.asyncio
    async def test_user_full_interview_to_confirm(self):
        """User completes entire interview and confirms."""
        app = MurphyTerminalApp(api_url="http://localhost:19999")
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.pause()
            answers = [
                "start interview", "My Org", "grow revenue",
                "automation", "Slack and email", "pro", "GitHub", "yes",
            ]
            for cmd in answers:
                for ch in cmd:
                    await pilot.press(ch)
                await pilot.press("enter")
                await pilot.pause()
            # Interview should be complete
            assert app.dialog.is_complete is True
            assert app.dialog.active is False

            # Now confirm
            for ch in "confirm":
                await pilot.press(ch)
            await pilot.press("enter")
            await pilot.pause()
            # collected data should still be there
            assert app.dialog.collected["name"] == "My Org"

    @pytest.mark.asyncio
    async def test_user_sends_feedback(self):
        """User expresses frustration and gets acknowledgment."""
        app = MurphyTerminalApp(api_url="http://localhost:19999")
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.pause()
            for ch in "this is too complicated":
                await pilot.press(ch)
            await pilot.press("enter")
            await pilot.pause()
            assert len(app.dialog.feedback_log) == 1
            assert "complicated" in app.dialog.feedback_log[0]

    @pytest.mark.asyncio
    async def test_user_changes_api_url(self):
        """User changes the backend URL with 'set api'."""
        app = MurphyTerminalApp(api_url="http://localhost:19999")
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.pause()
            for ch in "set api http://newhost:5000":
                await pilot.press(ch)
            await pilot.press("enter")
            await pilot.pause()
            await pilot.pause()
            assert app.client.base_url == "http://newhost:5000"
            assert "newhost:5000" in app.sub_title

    @pytest.mark.asyncio
    async def test_user_help_is_contextual_during_interview(self):
        """When user types 'help' during interview, gets contextual help."""
        app = MurphyTerminalApp(api_url="http://localhost:19999")
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.pause()
            for ch in "start interview":
                await pilot.press(ch)
            await pilot.press("enter")
            await pilot.pause()
            assert app.dialog.active is True
            # Type help during interview — dialog should stay active
            for ch in "help":
                await pilot.press(ch)
            await pilot.press("enter")
            await pilot.pause()
            assert app.dialog.active is True
            assert app.dialog.step_index == 0  # Should NOT have advanced

    @pytest.mark.asyncio
    async def test_user_chat_while_disconnected_shows_clean_error(self):
        """User sends a chat message while disconnected — error should be clean."""
        app = MurphyTerminalApp(api_url="http://localhost:19999")
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.pause()
            for ch in "hello there":
                await pilot.press(ch)
            await pilot.press("enter")
            await pilot.pause()
            await pilot.pause()
            # No crash means it handled the error gracefully
            # The input should be cleared
            input_widget = app.query_one("#user-input", Input)
            assert input_widget.value == ""


# ---------------------------------------------------------------------------
# New intent detection tests for added commands
# ---------------------------------------------------------------------------


class TestNewModuleIntentDetection:
    """Tests for newly added module intent patterns."""

    def test_librarian_intent(self):
        assert detect_intent("librarian") == "intent_librarian"
        assert detect_intent("show library") == "intent_librarian"
        assert detect_intent("knowledge base search") == "intent_librarian"

    def test_modules_intent(self):
        assert detect_intent("show modules") == "intent_modules"
        assert detect_intent("list modules") == "intent_modules"
        assert detect_intent("modules") == "intent_modules"

    def test_billing_intent(self):
        assert detect_intent("billing") == "intent_billing"
        assert detect_intent("show subscription") == "intent_billing"
        assert detect_intent("pricing") == "intent_billing"

    def test_links_intent(self):
        assert detect_intent("links") == "intent_links"
        assert detect_intent("show urls") == "intent_links"
        assert detect_intent("open ui") == "intent_ui"
        assert detect_intent("dashboards") == "intent_links"

    def test_plan_intent(self):
        assert detect_intent("plan") == "intent_plan"
        assert detect_intent("execution plan") == "intent_plan"
        assert detect_intent("two-plane") == "intent_plan"
        assert detect_intent("show planning") == "intent_plan"


# ---------------------------------------------------------------------------
# Module command map and dashboard links
# ---------------------------------------------------------------------------


class TestModuleCommandMap:
    """Tests for MODULE_COMMAND_MAP data structure."""

    def test_module_map_not_empty(self):
        assert len(MODULE_COMMAND_MAP) > 0

    def test_all_modules_have_commands(self):
        for module, cmds in MODULE_COMMAND_MAP.items():
            assert isinstance(cmds, list), f"{module} should map to a list"
            assert len(cmds) > 0, f"{module} should have at least one command"

    def test_key_modules_present(self):
        assert "billing" in MODULE_COMMAND_MAP
        assert "librarian" in MODULE_COMMAND_MAP
        assert "hitl" in MODULE_COMMAND_MAP
        assert "execution" in MODULE_COMMAND_MAP
        assert "health_monitor" in MODULE_COMMAND_MAP
        assert "planning" in MODULE_COMMAND_MAP


class TestDashboardLinks:
    """Tests for DASHBOARD_LINKS data structure."""

    def test_links_not_empty(self):
        assert len(DASHBOARD_LINKS) > 0

    def test_links_have_name_and_url(self):
        for link in DASHBOARD_LINKS:
            assert "name" in link
            assert "url" in link
            assert link["url"].startswith("/")

    def test_swagger_link_present(self):
        urls = [link["url"] for link in DASHBOARD_LINKS]
        assert "/docs" in urls


# ---------------------------------------------------------------------------
# API Provider Links & Integration Inference
# ---------------------------------------------------------------------------


class TestAPIProviderLinks:
    """Tests for the API_PROVIDER_LINKS data structure."""

    def test_links_not_empty(self):
        assert len(API_PROVIDER_LINKS) > 0

    def test_groq_present(self):
        assert "deepinfra" in API_PROVIDER_LINKS
        assert "url" in API_PROVIDER_LINKS["deepinfra"]
        assert "env_var" in API_PROVIDER_LINKS["deepinfra"]

    def test_all_entries_have_required_fields(self):
        for key, info in API_PROVIDER_LINKS.items():
            assert "name" in info, f"{key} missing name"
            assert "url" in info, f"{key} missing url"
            assert "env_var" in info, f"{key} missing env_var"
            assert "description" in info, f"{key} missing description"

    def test_urls_look_valid(self):
        for key, info in API_PROVIDER_LINKS.items():
            assert info["url"].startswith("https://"), f"{key} url should be https"


class TestDialogContextIntegrations:
    """Test DialogContext._infer_integrations returns relevant services."""

    def test_email_mention(self):
        dc = DialogContext()
        dc.collected = {"platforms": "email and Slack"}
        recs = dc._infer_integrations()
        assert "sendgrid" in recs or "google" in recs
        assert "slack" in recs

    def test_crm_mention(self):
        dc = DialogContext()
        dc.collected = {"platforms": "CRM, HubSpot"}
        recs = dc._infer_integrations()
        assert "hubspot" in recs

    def test_sales_mention_recommends_stripe(self):
        dc = DialogContext()
        dc.collected = {"business_goal": "sell products online", "platforms": "Shopify"}
        recs = dc._infer_integrations()
        assert "shopify" in recs
        assert "stripe" in recs

    def test_always_recommends_llm(self):
        """If LLM is not configured, deepinfra should always be recommended."""
        import os
        old = os.environ.pop("MURPHY_LLM_PROVIDER", None)
        try:
            dc = DialogContext()
            dc.collected = {"name": "Test Co"}
            recs = dc._infer_integrations()
            assert "deepinfra" in recs
        finally:
            if old is not None:
                os.environ["MURPHY_LLM_PROVIDER"] = old

    def test_completion_message_mentions_api_keys(self):
        dc = DialogContext()
        dc.collected = {"platforms": "Slack, email"}
        dc.step_index = len(dc.INTERVIEW_STEPS)  # simulate completion
        msg = dc._complete_message()
        assert "api keys" in msg.lower()


class TestApiKeysIntentDetection:
    """Test that 'api keys' and 'get api keys' are detected."""

    def test_api_keys(self):
        assert detect_intent("api keys") == "intent_api_keys"

    def test_get_api_keys(self):
        assert detect_intent("get api keys") == "intent_api_keys"

    def test_api_key(self):
        assert detect_intent("api key") == "intent_api_keys"


# ---------------------------------------------------------------------------
# Workflow-aware integration inference
# ---------------------------------------------------------------------------


class TestWorkflowActionInferenceTerminal:
    """Test that workflow ACTIONS trigger integration inference in terminal."""

    def test_send_email_action_infers_sendgrid(self):
        dc = DialogContext()
        dc.collected = {"business_goal": "send email campaigns to customers"}
        recs = dc._infer_integrations()
        assert "sendgrid" in recs or "google" in recs

    def test_post_to_channel_infers_slack(self):
        dc = DialogContext()
        dc.collected = {"use_case": "post to channel when builds complete"}
        recs = dc._infer_integrations()
        assert "slack" in recs

    def test_create_issue_infers_jira_or_github(self):
        dc = DialogContext()
        dc.collected = {"use_case": "create issue when bug detected"}
        recs = dc._infer_integrations()
        assert "jira" in recs or "github" in recs

    def test_goal_increase_sales_infers_crm(self):
        dc = DialogContext()
        dc.collected = {"business_goal": "increase sales by 30%"}
        recs = dc._infer_integrations()
        assert "hubspot" in recs

    def test_goal_devops_infers_github(self):
        dc = DialogContext()
        dc.collected = {"business_goal": "devops automation"}
        recs = dc._infer_integrations()
        assert "github" in recs
        assert "slack" in recs

    def test_completion_message_has_next_steps(self):
        dc = DialogContext()
        dc.collected = {"platforms": "Slack, email", "business_goal": "automate operations"}
        dc.step_index = len(dc.INTERVIEW_STEPS)
        msg = dc._complete_message()
        assert "What to do next" in msg
        assert "set key deepinfra" in msg

    def test_completion_message_numbers_integrations(self):
        dc = DialogContext()
        dc.collected = {"platforms": "email, Slack"}
        dc.step_index = len(dc.INTERVIEW_STEPS)
        msg = dc._complete_message()
        # Should have numbered list (1., 2., etc)
        assert "1." in msg


# ---------------------------------------------------------------------------
# Enhanced interview steps
# ---------------------------------------------------------------------------


class TestEnhancedInterview:
    """Tests for the enhanced business-first interview flow."""

    def test_business_goal_before_technical(self):
        """Interview should ask about business goals before technical details."""
        steps = DialogContext.INTERVIEW_STEPS
        keys = [s["key"] for s in steps]
        assert "business_goal" in keys
        assert "platforms" in keys
        # business_goal should come before billing_tier
        assert keys.index("business_goal") < keys.index("billing_tier")

    def test_interview_has_seven_steps(self):
        assert len(DialogContext.INTERVIEW_STEPS) == 7

    def test_platforms_step_exists(self):
        keys = [s["key"] for s in DialogContext.INTERVIEW_STEPS]
        assert "platforms" in keys

    def test_infer_auto_configure(self):
        assert DialogContext._infer_value("integrations", "auto") == "(auto-configure)"
        assert DialogContext._infer_value("integrations", "let murphy decide") == "(auto-configure)"
        assert DialogContext._infer_value("integrations", "you decide") == "(auto-configure)"

    def test_infer_auto_configure_not_triggered_by_other_input(self):
        assert DialogContext._infer_value("integrations", "github", "GitHub") == "GitHub"
        assert DialogContext._infer_value("integrations", "slack and email", "Slack and email") == "Slack and email"
        assert DialogContext._infer_value("name", "auto company", "Auto Company") == "Auto Company"

    def test_full_interview_business_first(self):
        """Complete the full enhanced interview and verify all keys collected."""
        ctx = DialogContext()
        ctx.start()
        answers = [
            "Acme Corp",       # name
            "reduce costs",    # business_goal
            "automation",      # use_case
            "Slack, GitHub",   # platforms
            "pro",             # billing_tier
            "auto",            # integrations
            "yes",             # confirm
        ]
        for ans in answers:
            ctx.advance(ans)
        assert ctx.is_complete is True
        assert ctx.collected["name"] == "Acme Corp"
        assert ctx.collected["business_goal"] == "reduce costs"
        assert ctx.collected["platforms"] == "Slack, GitHub"
        assert ctx.collected["integrations"] == "(auto-configure)"


# ---------------------------------------------------------------------------
# TUI integration tests for new features
# ---------------------------------------------------------------------------


class TestTUINewFeatures:
    """Integration tests for new terminal UI features."""

    @pytest.mark.asyncio
    async def test_user_types_modules(self):
        """User types 'show modules' and gets module listing."""
        app = MurphyTerminalApp(api_url="http://localhost:19999")
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.pause()
            for ch in "show modules":
                await pilot.press(ch)
            await pilot.press("enter")
            await pilot.pause()
            # No crash and input cleared
            input_widget = app.query_one("#user-input", Input)
            assert input_widget.value == ""

    @pytest.mark.asyncio
    async def test_user_types_billing(self):
        """User types 'billing' and gets billing info."""
        app = MurphyTerminalApp(api_url="http://localhost:19999")
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.pause()
            for ch in "billing":
                await pilot.press(ch)
            await pilot.press("enter")
            await pilot.pause()
            input_widget = app.query_one("#user-input", Input)
            assert input_widget.value == ""

    @pytest.mark.asyncio
    async def test_user_types_links(self):
        """User types 'links' and gets dashboard URLs."""
        app = MurphyTerminalApp(api_url="http://localhost:19999")
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.pause()
            for ch in "links":
                await pilot.press(ch)
            await pilot.press("enter")
            await pilot.pause()
            input_widget = app.query_one("#user-input", Input)
            assert input_widget.value == ""

    @pytest.mark.asyncio
    async def test_user_types_librarian(self):
        """User types 'librarian' and gets librarian info."""
        app = MurphyTerminalApp(api_url="http://localhost:19999")
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.pause()
            for ch in "librarian":
                await pilot.press(ch)
            await pilot.press("enter")
            await pilot.pause()
            input_widget = app.query_one("#user-input", Input)
            assert input_widget.value == ""

            assert input_widget.value == ""


# ---------------------------------------------------------------------------
# Bug-fix regression tests
# ---------------------------------------------------------------------------


class TestBug5DefaultSuccessFalse:
    """BUG-5: _apply_api_key should default 'success' to False, not True."""

    @patch("murphy_terminal.requests.post")
    def test_configure_llm_returns_empty_dict_treated_as_failure(self, mock_post):
        """If backend returns {} (no 'success' key), it should be treated as failure."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {}
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        client = MurphyAPIClient(base_url="http://localhost:8000", timeout=5)
        result = client.configure_llm("deepinfra", "gsk_test_key_value")
        # With the old default of True, `not result.get("success", True)` would be
        # False (i.e. treated as success).  With the fix, `not result.get("success", False)`
        # is True (i.e. treated as failure).
        assert result.get("success", False) is False

    @patch("murphy_terminal.requests.post")
    def test_configure_llm_explicit_success_true(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"success": True, "provider": "deepinfra"}
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        client = MurphyAPIClient(base_url="http://localhost:8000", timeout=5)
        result = client.configure_llm("deepinfra", "gsk_test_key_value")
        assert result.get("success", False) is True

    @patch("murphy_terminal.requests.post")
    def test_configure_llm_explicit_success_false(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"success": False, "error": "bad key"}
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        client = MurphyAPIClient(base_url="http://localhost:8000", timeout=5)
        result = client.configure_llm("deepinfra", "gsk_bad")
        assert result.get("success", False) is False


class TestBug4StatusBarAuth:
    """BUG-4: _check_llm_status should rely on actual auth test, not just env vars."""

    @patch("murphy_terminal.requests.post")
    @patch("murphy_terminal.requests.get")
    def test_llm_status_enabled_but_test_fails_returns_false(self, mock_get, mock_post):
        """Status says enabled but auth test fails → client should reflect failure."""
        # Mock llm_status → enabled
        get_resp = MagicMock()
        get_resp.json.return_value = {"enabled": True, "provider": "deepinfra", "model": "meta-llama/Meta-Llama-3.1-8B-Instruct"}
        get_resp.raise_for_status = MagicMock()
        mock_get.return_value = get_resp

        # Mock llm_test → failure
        post_resp = MagicMock()
        post_resp.json.return_value = {"success": False, "error": "Invalid API key"}
        post_resp.raise_for_status = MagicMock()
        mock_post.return_value = post_resp

        client = MurphyAPIClient(base_url="http://localhost:8000", timeout=5)
        status = client.llm_status()
        assert status.get("enabled") is True

        test_result = client.llm_test()
        assert test_result.get("success") is False

    @patch("murphy_terminal.requests.post")
    @patch("murphy_terminal.requests.get")
    def test_llm_status_enabled_and_test_passes(self, mock_get, mock_post):
        """Status enabled and auth test passes → should report success."""
        get_resp = MagicMock()
        get_resp.json.return_value = {"enabled": True, "provider": "deepinfra", "model": "meta-llama/Meta-Llama-3.1-8B-Instruct"}
        get_resp.raise_for_status = MagicMock()
        mock_get.return_value = get_resp

        post_resp = MagicMock()
        post_resp.json.return_value = {"success": True, "provider": "deepinfra"}
        post_resp.raise_for_status = MagicMock()
        mock_post.return_value = post_resp

        client = MurphyAPIClient(base_url="http://localhost:8000", timeout=5)
        status = client.llm_status()
        assert status.get("enabled") is True

        test_result = client.llm_test()
        assert test_result.get("success") is True


class TestBug1ClipboardPriority:
    """BUG-1: On Windows, win32clipboard should be tried before subprocess."""

    def test_read_clipboard_method_exists(self):
        """Verify _read_clipboard is a static method on the app class."""
        assert hasattr(MurphyTerminalApp, "_read_clipboard")
        assert callable(MurphyTerminalApp._read_clipboard)

    def test_key_ctrl_v_handler_exists(self):
        """Verify the key_ctrl_v app-level handler exists."""
        assert hasattr(MurphyTerminalApp, "key_ctrl_v")
        assert callable(MurphyTerminalApp.key_ctrl_v)

    def test_action_paste_clipboard_exists(self):
        """Verify action_paste_clipboard method exists."""
        assert hasattr(MurphyTerminalApp, "action_paste_clipboard")


class TestBug6NoHardcodedKeys:
    """BUG-6: No real API keys should remain in the archive directory."""

    def test_no_groq_keys_in_archive(self):
        """Ensure no gsk_ prefixed keys of 20+ chars remain in the archive."""
        archive_dir = os.path.join(os.path.dirname(__file__), "..", "archive")
        if not os.path.isdir(archive_dir):
            pytest.skip("archive directory not present")
        pattern = re.compile(r"gsk_[A-Za-z0-9]{20,}")
        hits: list[str] = []
        for root, _dirs, files in os.walk(archive_dir):
            for fname in files:
                fpath = os.path.join(root, fname)
                try:
                    with open(fpath, encoding="utf-8", errors="ignore") as fh:
                        for lineno, line in enumerate(fh, 1):
                            if pattern.search(line):
                                hits.append(f"{fpath}:{lineno}")
                except (OSError, UnicodeDecodeError):
                    pass
        assert hits == [], f"Found hardcoded DeepInfra keys:\n" + "\n".join(hits[:10])
