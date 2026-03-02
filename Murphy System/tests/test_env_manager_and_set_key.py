"""
Tests for the env_manager module and the set key terminal command.

Covers:
- .env file reading, writing, and reloading
- API key format validation
- Intent detection for 'set key' command
- First-run API key gate behaviour
"""

import os
import sys
import tempfile
import pytest

# Ensure parent directory is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

pytest.importorskip("textual", reason="textual not installed — skipping terminal UI tests")

from src.env_manager import (
    read_env,
    write_env_key,
    reload_env,
    validate_api_key,
    API_KEY_FORMATS,
)
from murphy_terminal import detect_intent, MurphyTerminalApp, StatusBar
from textual.widgets import Input


# ---------------------------------------------------------------------------
# env_manager — read_env
# ---------------------------------------------------------------------------


class TestReadEnv:

    def test_read_basic_env(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("FOO=bar\nBAZ=qux\n")
        result = read_env(str(env_file))
        assert result == {"FOO": "bar", "BAZ": "qux"}

    def test_read_quoted_values(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text('KEY="value with spaces"\nOTHER=\'single\'\n')
        result = read_env(str(env_file))
        assert result["KEY"] == "value with spaces"
        assert result["OTHER"] == "single"

    def test_read_comments_and_blanks(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("# comment\n\nKEY=value\n\n# another\n")
        result = read_env(str(env_file))
        assert result == {"KEY": "value"}

    def test_read_missing_file(self, tmp_path):
        result = read_env(str(tmp_path / "nonexistent"))
        assert result == {}


# ---------------------------------------------------------------------------
# env_manager — write_env_key
# ---------------------------------------------------------------------------


class TestWriteEnvKey:

    def test_create_new_env(self, tmp_path):
        env_file = tmp_path / ".env"
        write_env_key(str(env_file), "GROQ_API_KEY", "gsk_test123")
        result = read_env(str(env_file))
        assert result["GROQ_API_KEY"] == "gsk_test123"

    def test_update_existing_key(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("GROQ_API_KEY=old_value\nOTHER=keep\n")
        write_env_key(str(env_file), "GROQ_API_KEY", "gsk_new_value")
        result = read_env(str(env_file))
        assert result["GROQ_API_KEY"] == "gsk_new_value"
        assert result["OTHER"] == "keep"

    def test_add_key_without_clobbering(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("EXISTING=value\n")
        write_env_key(str(env_file), "NEW_KEY", "new_value")
        result = read_env(str(env_file))
        assert result["EXISTING"] == "value"
        assert result["NEW_KEY"] == "new_value"

    def test_preserves_comments(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("# My config\nKEY=val\n")
        write_env_key(str(env_file), "KEY", "updated")
        content = env_file.read_text()
        assert "# My config" in content
        assert "KEY=updated" in content


# ---------------------------------------------------------------------------
# env_manager — reload_env
# ---------------------------------------------------------------------------


class TestReloadEnv:

    def test_reload_updates_os_environ(self, tmp_path, monkeypatch):
        env_file = tmp_path / ".env"
        env_file.write_text("TEST_RELOAD_VAR=hello_world\n")
        monkeypatch.delenv("TEST_RELOAD_VAR", raising=False)
        reload_env(str(env_file))
        assert os.environ.get("TEST_RELOAD_VAR") == "hello_world"


# ---------------------------------------------------------------------------
# env_manager — validate_api_key
# ---------------------------------------------------------------------------


class TestValidateApiKey:

    def test_valid_groq_key(self):
        ok, msg = validate_api_key("groq", "gsk_abcdefghijklmnopqrstuvwx")
        assert ok is True

    def test_invalid_groq_key_prefix(self):
        ok, msg = validate_api_key("groq", "sk-invalid_prefix_key_value")
        assert ok is False
        assert "gsk_" in msg

    def test_valid_openai_key(self):
        ok, msg = validate_api_key("openai", "sk-abcdefghijklmnopqrstuvwx")
        assert ok is True

    def test_invalid_openai_key(self):
        ok, msg = validate_api_key("openai", "gsk_wrong_prefix")
        assert ok is False

    def test_valid_anthropic_key(self):
        ok, msg = validate_api_key("anthropic", "sk-ant-abcdefghijklmnopqrstuvwx")
        assert ok is True

    def test_unknown_provider(self):
        ok, msg = validate_api_key("unknown_provider", "some-key")
        assert ok is False
        assert "Unknown provider" in msg

    def test_provider_case_insensitive(self):
        ok, msg = validate_api_key("GROQ", "gsk_abcdefghijklmnopqrstuvwx")
        assert ok is True

    def test_short_key_rejected(self):
        ok, msg = validate_api_key("groq", "gsk_short")
        assert ok is False

    def test_angle_bracket_groq_key(self):
        ok, msg = validate_api_key("groq", "<gsk_abcdefghijklmnopqrstuvwx>")
        assert ok is True

    def test_quoted_groq_key(self):
        ok, msg = validate_api_key("groq", '"gsk_abcdefghijklmnopqrstuvwx"')
        assert ok is True

    def test_angle_bracket_openai_key(self):
        ok, msg = validate_api_key("openai", "<sk-abcdefghijklmnopqrstuvwx>")
        assert ok is True

    def test_backtick_wrapped_key(self):
        ok, msg = validate_api_key("groq", "`gsk_abcdefghijklmnopqrstuvwx`")
        assert ok is True

    def test_single_quote_wrapped_key(self):
        ok, msg = validate_api_key("anthropic", "'sk-ant-abcdefghijklmnopqrstuvwx'")
        assert ok is True


# ---------------------------------------------------------------------------
# Intent detection — set key
# ---------------------------------------------------------------------------


class TestSetKeyIntentDetection:

    def test_set_key_basic(self):
        assert detect_intent("set key groq gsk_abc123") == "intent_set_key"

    def test_set_key_underscore(self):
        assert detect_intent("set_key openai sk-abc123") == "intent_set_key"

    def test_set_key_no_args(self):
        assert detect_intent("set key") == "intent_set_key"

    def test_set_key_before_set_api(self):
        """'set key' should not be confused with 'set api'."""
        assert detect_intent("set key groq gsk_abc") == "intent_set_key"
        assert detect_intent("set api http://host") == "intent_set_api"

    def test_set_key_case_insensitive(self):
        assert detect_intent("SET KEY groq gsk_abc") == "intent_set_key"


# ---------------------------------------------------------------------------
# TUI — first-run gate & set key flow
# ---------------------------------------------------------------------------


class TestFirstRunGate:

    @pytest.mark.asyncio
    async def test_no_gate_when_key_exists(self, monkeypatch):
        """When GROQ_API_KEY is set, the startup gate should not activate."""
        monkeypatch.setenv("GROQ_API_KEY", "gsk_test_value_for_gate_skip")
        app = MurphyTerminalApp(api_url="http://localhost:19999")
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.pause()
            assert app._awaiting_api_key is False

    @pytest.mark.asyncio
    async def test_gate_activates_without_key(self, monkeypatch):
        """When no GROQ_API_KEY exists, the startup gate should show a prompt."""
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        app = MurphyTerminalApp(api_url="http://localhost:19999")
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.pause()
            assert app._awaiting_api_key is True

    @pytest.mark.asyncio
    async def test_skip_dismisses_gate(self, monkeypatch):
        """Typing 'skip' during the gate should enter offline mode."""
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        app = MurphyTerminalApp(api_url="http://localhost:19999")
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.pause()
            assert app._awaiting_api_key is True
            for ch in "skip":
                await pilot.press(ch)
            await pilot.press("enter")
            await pilot.pause()
            assert app._awaiting_api_key is False
            assert app._offline_mode is True

    @pytest.mark.asyncio
    async def test_gate_activates_with_placeholder_key(self, monkeypatch):
        """When GROQ_API_KEY is a placeholder like 'your_groq_key_here', gate should still activate."""
        monkeypatch.setenv("GROQ_API_KEY", "your_groq_key_here")
        app = MurphyTerminalApp(api_url="http://localhost:19999")
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.pause()
            assert app._awaiting_api_key is True

    @pytest.mark.asyncio
    async def test_regular_command_dismisses_gate(self, monkeypatch):
        """Typing a regular command like 'help' should dismiss the gate."""
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        app = MurphyTerminalApp(api_url="http://localhost:19999")
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.pause()
            assert app._awaiting_api_key is True
            for ch in "help":
                await pilot.press(ch)
            await pilot.press("enter")
            await pilot.pause()
            assert app._awaiting_api_key is False


# ---------------------------------------------------------------------------
# TUI — set key flow
# ---------------------------------------------------------------------------


class TestSetKeyTUI:

    @pytest.mark.asyncio
    async def test_set_key_groq_in_terminal(self, tmp_path, monkeypatch):
        """User types 'set key groq <key>' and key is persisted and active."""
        env_file = tmp_path / ".env"
        monkeypatch.setattr("murphy_terminal.get_env_path", lambda: str(env_file))
        monkeypatch.setenv("GROQ_API_KEY", "gsk_old_key_to_skip_gate_check")

        app = MurphyTerminalApp(api_url="http://localhost:19999")
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.pause()
            cmd = "set key groq gsk_abcdefghijklmnopqrstuvwx"
            for ch in cmd:
                await pilot.press(ch)
            await pilot.press("enter")
            await pilot.pause()
            # Key should now be in os.environ
            assert os.environ.get("GROQ_API_KEY") == "gsk_abcdefghijklmnopqrstuvwx"
            # Key should be persisted in .env
            content = env_file.read_text()
            assert "gsk_abcdefghijklmnopqrstuvwx" in content

    @pytest.mark.asyncio
    async def test_set_key_writes_murphy_llm_provider(self, tmp_path, monkeypatch):
        """Setting a groq key should also write MURPHY_LLM_PROVIDER=groq to .env."""
        env_file = tmp_path / ".env"
        monkeypatch.setattr("murphy_terminal.get_env_path", lambda: str(env_file))
        monkeypatch.setenv("GROQ_API_KEY", "gsk_old_key_to_skip_gate_check")

        app = MurphyTerminalApp(api_url="http://localhost:19999")
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.pause()
            cmd = "set key groq gsk_abcdefghijklmnopqrstuvwx"
            for ch in cmd:
                await pilot.press(ch)
            await pilot.press("enter")
            await pilot.pause()
            # MURPHY_LLM_PROVIDER should be set in os.environ
            assert os.environ.get("MURPHY_LLM_PROVIDER") == "groq"
            # MURPHY_LLM_PROVIDER should be persisted to .env
            content = env_file.read_text()
            assert "MURPHY_LLM_PROVIDER=groq" in content


# ---------------------------------------------------------------------------
# MurphyAPIClient — configure_llm
# ---------------------------------------------------------------------------


class TestConfigureLlmClient:

    def test_configure_llm_returns_failure_when_backend_down(self):
        """configure_llm should return a dict with success=False when backend is unreachable."""
        from murphy_terminal import MurphyAPIClient
        client = MurphyAPIClient(base_url="http://localhost:19999")
        result = client.configure_llm("groq", "gsk_abcdefghijklmnopqrstuvwx")
        assert result.get("success") is False


# ---------------------------------------------------------------------------
# Placeholder key detection
# ---------------------------------------------------------------------------


class TestIsRealKey:

    def test_none_is_not_real(self):
        assert MurphyTerminalApp._is_real_key(None) is False

    def test_empty_is_not_real(self):
        assert MurphyTerminalApp._is_real_key("") is False

    def test_placeholder_is_not_real(self):
        assert MurphyTerminalApp._is_real_key("your_groq_key_here") is False

    def test_another_placeholder_is_not_real(self):
        assert MurphyTerminalApp._is_real_key("your_openai_key_here") is False

    def test_changeme_is_not_real(self):
        assert MurphyTerminalApp._is_real_key("CHANGE_ME") is False

    def test_xxx_is_not_real(self):
        assert MurphyTerminalApp._is_real_key("xxx") is False

    def test_real_groq_key(self):
        assert MurphyTerminalApp._is_real_key("gsk_abcdefghijklmnopqrstuvwx") is True

    def test_real_openai_key(self):
        assert MurphyTerminalApp._is_real_key("sk-abcdefghijklmnopqrstuvwx") is True


# ---------------------------------------------------------------------------
# Updated WELCOME_TEXT
# ---------------------------------------------------------------------------


class TestWelcomeTextSetKey:

    def test_welcome_text_mentions_set_key(self):
        from murphy_terminal import WELCOME_TEXT
        assert "set key" in WELCOME_TEXT
