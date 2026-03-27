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
        write_env_key(str(env_file), "DEEPINFRA_API_KEY", "gsk_test123")
        result = read_env(str(env_file))
        assert result["DEEPINFRA_API_KEY"] == "gsk_test123"

    def test_update_existing_key(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("DEEPINFRA_API_KEY=old_value\nOTHER=keep\n")
        write_env_key(str(env_file), "DEEPINFRA_API_KEY", "gsk_new_value")
        result = read_env(str(env_file))
        assert result["DEEPINFRA_API_KEY"] == "gsk_new_value"
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
        ok, msg = validate_api_key("deepinfra", "gsk_abcdefghijklmnopqrstuvwx")
        assert ok is True

    def test_invalid_groq_key_prefix(self):
        ok, msg = validate_api_key("deepinfra", "sk-invalid_prefix_key_value")
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
        ok, msg = validate_api_key("DEEPINFRA", "gsk_abcdefghijklmnopqrstuvwx")
        assert ok is True

    def test_short_key_rejected(self):
        ok, msg = validate_api_key("deepinfra", "gsk_short")
        assert ok is False

    def test_angle_bracket_groq_key(self):
        ok, msg = validate_api_key("deepinfra", "<gsk_abcdefghijklmnopqrstuvwx>")
        assert ok is True

    def test_quoted_groq_key(self):
        ok, msg = validate_api_key("deepinfra", '"gsk_abcdefghijklmnopqrstuvwx"')
        assert ok is True

    def test_angle_bracket_openai_key(self):
        ok, msg = validate_api_key("openai", "<sk-abcdefghijklmnopqrstuvwx>")
        assert ok is True

    def test_backtick_wrapped_key(self):
        ok, msg = validate_api_key("deepinfra", "`gsk_abcdefghijklmnopqrstuvwx`")
        assert ok is True

    def test_single_quote_wrapped_key(self):
        ok, msg = validate_api_key("anthropic", "'sk-ant-abcdefghijklmnopqrstuvwx'")
        assert ok is True


# ---------------------------------------------------------------------------
# Intent detection — set key
# ---------------------------------------------------------------------------


class TestSetKeyIntentDetection:

    def test_set_key_basic(self):
        assert detect_intent("set key deepinfra gsk_abc123") == "intent_set_key"

    def test_set_key_underscore(self):
        assert detect_intent("set_key openai sk-abc123") == "intent_set_key"

    def test_set_key_no_args(self):
        assert detect_intent("set key") == "intent_set_key"

    def test_set_key_before_set_api(self):
        """'set key' should not be confused with 'set api'."""
        assert detect_intent("set key deepinfra gsk_abc") == "intent_set_key"
        assert detect_intent("set api http://host") == "intent_set_api"

    def test_set_key_case_insensitive(self):
        assert detect_intent("SET KEY deepinfra gsk_abc") == "intent_set_key"


# ---------------------------------------------------------------------------
# TUI — first-run gate & set key flow
# ---------------------------------------------------------------------------


class TestFirstRunGate:

    @pytest.mark.asyncio
    async def test_no_gate_when_key_exists(self, monkeypatch):
        """When DEEPINFRA_API_KEY is set, the startup gate should not activate."""
        monkeypatch.setenv("DEEPINFRA_API_KEY", "gsk_test_value_for_gate_skip")
        app = MurphyTerminalApp(api_url="http://localhost:19999")
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.pause()
            assert app._awaiting_api_key is False

    @pytest.mark.asyncio
    async def test_gate_activates_without_key(self, monkeypatch):
        """When no DEEPINFRA_API_KEY exists, the startup gate should show a prompt."""
        monkeypatch.delenv("DEEPINFRA_API_KEY", raising=False)
        app = MurphyTerminalApp(api_url="http://localhost:19999")
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.pause()
            assert app._awaiting_api_key is True

    @pytest.mark.asyncio
    async def test_skip_dismisses_gate(self, monkeypatch):
        """Typing 'skip' during the gate should enter offline mode."""
        monkeypatch.delenv("DEEPINFRA_API_KEY", raising=False)
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
        """When DEEPINFRA_API_KEY is a placeholder like 'your_groq_key_here', gate should still activate."""
        monkeypatch.setenv("DEEPINFRA_API_KEY", "your_groq_key_here")
        app = MurphyTerminalApp(api_url="http://localhost:19999")
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.pause()
            assert app._awaiting_api_key is True

    @pytest.mark.asyncio
    async def test_regular_command_dismisses_gate(self, monkeypatch):
        """Typing a regular command like 'help' should dismiss the gate."""
        monkeypatch.delenv("DEEPINFRA_API_KEY", raising=False)
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
        """User types 'set key deepinfra <key>' and key is persisted and active."""
        env_file = tmp_path / ".env"
        monkeypatch.setattr("murphy_terminal.get_env_path", lambda: str(env_file))
        monkeypatch.setenv("DEEPINFRA_API_KEY", "gsk_old_key_to_skip_gate_check")

        app = MurphyTerminalApp(api_url="http://localhost:19999")
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.pause()
            cmd = "set key deepinfra gsk_abcdefghijklmnopqrstuvwx"
            for ch in cmd:
                await pilot.press(ch)
            await pilot.press("enter")
            await pilot.pause()
            await pilot.pause()  # extra pause for async event flush
            # Key should now be in os.environ
            assert os.environ.get("DEEPINFRA_API_KEY") == "gsk_abcdefghijklmnopqrstuvwx"
            # Key should be persisted in .env
            content = env_file.read_text()
            assert "gsk_abcdefghijklmnopqrstuvwx" in content

    @pytest.mark.asyncio
    async def test_set_key_writes_murphy_llm_provider(self, tmp_path, monkeypatch):
        """Setting a deepinfra key should also write MURPHY_LLM_PROVIDER=deepinfra to .env."""
        env_file = tmp_path / ".env"
        monkeypatch.setattr("murphy_terminal.get_env_path", lambda: str(env_file))
        monkeypatch.setenv("DEEPINFRA_API_KEY", "gsk_old_key_to_skip_gate_check")

        app = MurphyTerminalApp(api_url="http://localhost:19999")
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.pause()
            cmd = "set key deepinfra gsk_abcdefghijklmnopqrstuvwx"
            for ch in cmd:
                await pilot.press(ch)
            await pilot.press("enter")
            await pilot.pause()
            await pilot.pause()  # extra pause for async event flush
            # MURPHY_LLM_PROVIDER should be set in os.environ
            assert os.environ.get("MURPHY_LLM_PROVIDER") == "deepinfra"
            # MURPHY_LLM_PROVIDER should be persisted to .env
            content = env_file.read_text()
            assert "MURPHY_LLM_PROVIDER=deepinfra" in content


# ---------------------------------------------------------------------------
# MurphyAPIClient — configure_llm
# ---------------------------------------------------------------------------


class TestConfigureLlmClient:

    def test_configure_llm_returns_failure_when_backend_down(self):
        """configure_llm should return a dict with success=False when backend is unreachable."""
        from murphy_terminal import MurphyAPIClient
        client = MurphyAPIClient(base_url="http://localhost:19999")
        result = client.configure_llm("deepinfra", "gsk_abcdefghijklmnopqrstuvwx")
        assert result.get("success") is False

    def test_configure_llm_posts_to_correct_endpoint(self, monkeypatch):
        """configure_llm should POST to /api/llm/configure with provider and api_key."""
        from murphy_terminal import MurphyAPIClient
        captured = {}

        def mock_post(path, data):
            captured["path"] = path
            captured["data"] = data
            return {"success": True, "enabled": True, "provider": "deepinfra"}

        client = MurphyAPIClient(base_url="http://localhost:19999")
        monkeypatch.setattr(client, "_post", mock_post)
        result = client.configure_llm("deepinfra", "gsk_abcdefghijklmnopqrstuvwx")
        assert captured["path"] == "/api/llm/configure"
        assert captured["data"]["provider"] == "deepinfra"
        assert captured["data"]["api_key"] == "gsk_abcdefghijklmnopqrstuvwx"
        assert result.get("success") is True

    def test_configure_llm_returns_success_response(self, monkeypatch):
        """configure_llm should return the backend response on success."""
        from murphy_terminal import MurphyAPIClient

        def mock_post(path, data):
            return {"success": True, "enabled": True, "provider": "deepinfra", "model": "meta-llama/Meta-Llama-3.1-8B-Instruct"}

        client = MurphyAPIClient(base_url="http://localhost:19999")
        monkeypatch.setattr(client, "_post", mock_post)
        result = client.configure_llm("deepinfra", "gsk_abcdefghijklmnopqrstuvwx")
        assert result.get("success") is True
        assert result.get("provider") == "deepinfra"
        assert result.get("model") == "meta-llama/Meta-Llama-3.1-8B-Instruct"


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


# ---------------------------------------------------------------------------
# Paste (Ctrl+V) functionality
# ---------------------------------------------------------------------------


class TestReadClipboard:

    def test_read_clipboard_returns_string_or_none(self):
        """_read_clipboard should return a str or None — never raise."""
        result = MurphyTerminalApp._read_clipboard()
        assert result is None or isinstance(result, str)

    def test_read_clipboard_uses_pyperclip_when_available(self, monkeypatch):
        """_read_clipboard should use pyperclip when it is importable."""
        import murphy_terminal

        class FakePyperclip:
            @staticmethod
            def paste():
                return "clipboard_via_pyperclip"

        monkeypatch.setattr(murphy_terminal, "pyperclip", FakePyperclip)
        result = MurphyTerminalApp._read_clipboard()
        assert result == "clipboard_via_pyperclip"

    def test_read_clipboard_returns_none_when_all_methods_fail(self, monkeypatch):
        """_read_clipboard returns None when pyperclip is absent and subprocess fails."""
        import subprocess
        import murphy_terminal

        monkeypatch.setattr(murphy_terminal, "pyperclip", None)

        def failing_run(*args, **kwargs):
            raise FileNotFoundError("no clipboard tool")

        monkeypatch.setattr(subprocess, "run", failing_run)
        result = MurphyTerminalApp._read_clipboard()
        assert result is None


class TestPasteClipboardAction:

    @pytest.mark.asyncio
    async def test_paste_clipboard_inserts_text_into_input(self, monkeypatch):
        """Ctrl+V should paste clipboard text into the input widget."""
        monkeypatch.setenv("DEEPINFRA_API_KEY", "gsk_test_for_paste_skip_gate")
        app = MurphyTerminalApp(api_url="http://localhost:19999")
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.pause()
            monkeypatch.setattr(
                MurphyTerminalApp, "_read_clipboard",
                staticmethod(lambda: "gsk_pasted_key_value"),
            )
            await pilot.press("ctrl+v")
            await pilot.pause()
            input_widget = app.query_one("#user-input", Input)
            assert "gsk_pasted_key_value" in input_widget.value

    @pytest.mark.asyncio
    async def test_paste_clipboard_empty_does_not_crash(self, monkeypatch):
        """When clipboard is empty, action_paste_clipboard should not crash or modify input."""
        monkeypatch.setenv("DEEPINFRA_API_KEY", "gsk_test_for_paste_skip_gate")
        app = MurphyTerminalApp(api_url="http://localhost:19999")
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.pause()
            monkeypatch.setattr(
                MurphyTerminalApp, "_read_clipboard",
                staticmethod(lambda: None),
            )
            await pilot.press("ctrl+v")
            await pilot.pause()
            # The action should not crash; input should remain empty / unchanged
            input_widget = app.query_one("#user-input", Input)
            assert input_widget.value == ""


# ---------------------------------------------------------------------------
# strip_key_wrapping — Unicode invisible character stripping
# ---------------------------------------------------------------------------


class TestStripKeyWrapping:

    def test_strips_zero_width_space(self):
        from src.env_manager import strip_key_wrapping
        key = "\u200bgsk_abcdefghijklmnopqrstuvwx\u200b"
        assert strip_key_wrapping(key) == "gsk_abcdefghijklmnopqrstuvwx"

    def test_strips_bom(self):
        from src.env_manager import strip_key_wrapping
        key = "\ufeffgsk_abcdefghijklmnopqrstuvwx"
        assert strip_key_wrapping(key) == "gsk_abcdefghijklmnopqrstuvwx"

    def test_strips_non_breaking_space(self):
        from src.env_manager import strip_key_wrapping
        key = "\u00a0gsk_abcdefghijklmnopqrstuvwx\u00a0"
        assert strip_key_wrapping(key) == "gsk_abcdefghijklmnopqrstuvwx"

    def test_validate_key_with_zero_width_space_passes_after_strip(self):
        ok, _ = validate_api_key("deepinfra", "\u200bgsk_abcdefghijklmnopqrstuvwx\u200b")
        assert ok is True


# ---------------------------------------------------------------------------
# Placeholder key detection — .env.example placeholders
# ---------------------------------------------------------------------------


class TestEnvExamplePlaceholders:

    def test_groq_api_key_placeholder_not_real(self):
        """The placeholder in .env.example should trigger the startup gate."""
        assert MurphyTerminalApp._is_real_key("your_groq_api_key_here") is False

    def test_openai_placeholder_not_real(self):
        assert MurphyTerminalApp._is_real_key("sk-your_openai_key_here") is False

    def test_anthropic_placeholder_not_real(self):
        assert MurphyTerminalApp._is_real_key("sk-ant-your_anthropic_key_here") is False


# ---------------------------------------------------------------------------
# Bracketed paste — on_paste event handler
# ---------------------------------------------------------------------------


class TestOnPasteEvent:

    @pytest.mark.asyncio
    async def test_on_paste_inserts_text_into_input(self, monkeypatch):
        """Textual Paste event (bracketed paste) should insert text into input."""
        from textual import events
        monkeypatch.setenv("DEEPINFRA_API_KEY", "gsk_test_for_bracketed_paste")
        app = MurphyTerminalApp(api_url="http://localhost:19999")
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.pause()
            paste_event = events.Paste("gsk_bracketed_paste_value")
            app.post_message(paste_event)
            await pilot.pause()
            input_widget = app.query_one("#user-input", Input)
            assert "gsk_bracketed_paste_value" in input_widget.value

    @pytest.mark.asyncio
    async def test_on_paste_uses_first_line_only(self, monkeypatch):
        """Bracketed paste with multiple lines should only insert the first line."""
        from textual import events
        monkeypatch.setenv("DEEPINFRA_API_KEY", "gsk_test_for_multiline_paste")
        app = MurphyTerminalApp(api_url="http://localhost:19999")
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.pause()
            paste_event = events.Paste("gsk_firstline\nsecondline")
            app.post_message(paste_event)
            await pilot.pause()
            input_widget = app.query_one("#user-input", Input)
            assert "gsk_firstline" in input_widget.value
            assert "secondline" not in input_widget.value

    @pytest.mark.asyncio
    async def test_shift_insert_pastes_clipboard(self, monkeypatch):
        """Shift+Insert should also trigger paste_clipboard action."""
        monkeypatch.setenv("DEEPINFRA_API_KEY", "gsk_test_for_shift_insert")
        app = MurphyTerminalApp(api_url="http://localhost:19999")
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.pause()
            monkeypatch.setattr(
                MurphyTerminalApp, "_read_clipboard",
                staticmethod(lambda: "gsk_shift_insert_value"),
            )
            await pilot.press("shift+insert")
            await pilot.pause()
            input_widget = app.query_one("#user-input", Input)
            assert "gsk_shift_insert_value" in input_widget.value


# ---------------------------------------------------------------------------
# Gap test: Ctrl+V binding has priority=True (Bug 3 regression)
# ---------------------------------------------------------------------------


class TestCtrlVBindingConfiguration:
    """The ctrl+v Binding must carry priority=True so the app-level paste action
    overrides Textual's built-in Input widget binding of the same key.
    Without this, Ctrl+V silently does nothing (Input uses its internal clipboard).
    """

    def test_ctrl_v_binding_has_priority_true(self):
        """ctrl+v MUST have priority=True or it will be shadowed by Input's own binding."""
        ctrl_v = next(
            (b for b in MurphyTerminalApp.BINDINGS if b.key == "ctrl+v"),
            None,
        )
        assert ctrl_v is not None, "ctrl+v binding not found in MurphyTerminalApp.BINDINGS"
        assert ctrl_v.priority is True, (
            "ctrl+v binding must have priority=True; without it Textual's Input "
            "widget intercepts the keystroke before the app-level handler runs"
        )

    def test_ctrl_v_binding_action_is_paste_clipboard(self):
        """ctrl+v must trigger paste_clipboard, not some other action."""
        ctrl_v = next(
            (b for b in MurphyTerminalApp.BINDINGS if b.key == "ctrl+v"),
            None,
        )
        assert ctrl_v is not None
        assert ctrl_v.action == "paste_clipboard"

    def test_shift_insert_binding_exists(self):
        """Shift+Insert must be registered as a fallback paste shortcut."""
        shift_ins = next(
            (b for b in MurphyTerminalApp.BINDINGS if b.key == "shift+insert"),
            None,
        )
        assert shift_ins is not None, "shift+insert binding not found"
        assert shift_ins.action == "paste_clipboard"


# ---------------------------------------------------------------------------
# Gap test: read_env handles BOM-encoded files (Windows Notepad default)
# ---------------------------------------------------------------------------


class TestReadEnvBomHandling:
    """Windows Notepad (and many Windows editors) save UTF-8 files with a BOM
    (U+FEFF byte order mark) at the start.  Without utf-8-sig encoding the BOM
    becomes part of the first key name ('\ufeffDEEPINFRA_API_KEY') and the key is
    silently dropped from the parsed result.
    """

    def test_bom_prefixed_file_reads_correctly(self, tmp_path):
        env_file = tmp_path / ".env"
        # Write with BOM exactly as Windows Notepad does
        env_file.write_bytes(b"\xef\xbb\xbfDEEPINFRA_API_KEY=gsk_bomtest\nOTHER=value\n")
        result = read_env(str(env_file))
        assert "DEEPINFRA_API_KEY" in result, (
            "DEEPINFRA_API_KEY was not parsed from a BOM-prefixed .env file; "
            "the file was likely opened with utf-8 instead of utf-8-sig"
        )
        assert result["DEEPINFRA_API_KEY"] == "gsk_bomtest"

    def test_bom_does_not_contaminate_key_name(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_bytes(b"\xef\xbb\xbfFOO=bar\n")
        result = read_env(str(env_file))
        for k in result.keys():
            assert "\ufeff" not in k, f"BOM character found in key '{k}'"

    def test_non_bom_file_still_works(self, tmp_path):
        """Ensure the encoding change doesn't break plain UTF-8 files."""
        env_file = tmp_path / ".env"
        env_file.write_text("DEEPINFRA_API_KEY=gsk_plain\n", encoding="utf-8")
        result = read_env(str(env_file))
        assert result["DEEPINFRA_API_KEY"] == "gsk_plain"

    def test_startup_gate_triggers_when_bom_env_has_placeholder(self, tmp_path, monkeypatch):
        """If the .env file is BOM-encoded and contains only a placeholder, the
        startup gate should still fire — i.e. read_env must parse the key cleanly
        so _is_real_key can evaluate it correctly."""
        env_file = tmp_path / ".env"
        env_file.write_bytes(
            b"\xef\xbb\xbfDEEPINFRA_API_KEY=your_groq_api_key_here\n"
        )
        monkeypatch.setattr("murphy_terminal.get_env_path", lambda: str(env_file))
        monkeypatch.delenv("DEEPINFRA_API_KEY", raising=False)
        from src.env_manager import read_env as _re
        env_vars = _re(str(env_file))
        # After BOM fix, the key is parseable; a placeholder value must not be real
        assert MurphyTerminalApp._is_real_key(env_vars.get("DEEPINFRA_API_KEY")) is False


# ---------------------------------------------------------------------------
# Gap test: .env.example placeholder consistency check
# ---------------------------------------------------------------------------


class TestEnvExampleConsistency:
    """Regression: the startup gate checks _PLACEHOLDER_KEY_VALUES but .env.example
    uses slightly different placeholder strings.  If they drift apart, the gate
    silently lets through placeholder values and the user never gets prompted to
    set a real key.
    """

    @staticmethod
    def _get_placeholder_key_values():
        """Read the private frozenset from murphy_terminal."""
        import murphy_terminal
        return murphy_terminal._PLACEHOLDER_KEY_VALUES

    def test_env_example_groq_placeholder_is_blocked(self, tmp_path):
        """The exact string 'your_groq_api_key_here' (from .env.example) must be
        in _PLACEHOLDER_KEY_VALUES so the startup gate fires for unconfigured installs."""
        placeholders = self._get_placeholder_key_values()
        assert "your_groq_api_key_here" in placeholders, (
            "'your_groq_api_key_here' is the placeholder in .env.example for DEEPINFRA_API_KEY "
            "but it is not in _PLACEHOLDER_KEY_VALUES — users who don't replace the "
            "template value will bypass the startup gate"
        )

    def test_env_example_all_api_key_placeholders_are_blocked(self):
        """Parse the actual .env.example file and verify every API-key-shaped
        placeholder value is in _PLACEHOLDER_KEY_VALUES.
        Dynamically discovers all uncommented *_API_KEY lines so the test
        stays up-to-date as new providers are added to .env.example."""
        import murphy_terminal
        import re

        env_example_path = os.path.join(
            os.path.dirname(__file__), "..", ".env.example"
        )
        if not os.path.isfile(env_example_path):
            pytest.skip(".env.example file not found")

        with open(env_example_path, "r", encoding="utf-8") as fh:
            content = fh.read()

        # Dynamically match any uncommented line that looks like an API key variable
        # Pattern: KEY_NAME=value where KEY_NAME ends with _API_KEY or _TOKEN
        api_key_lines = re.findall(
            r"^([A-Z_]+(?:_API_KEY|_TOKEN))=(.+)$", content, re.MULTILINE
        )
        checked = 0
        for var, value in api_key_lines:
            value = value.strip()
            if not value or value.startswith("#"):
                continue
            checked += 1
            assert MurphyTerminalApp._is_real_key(value) is False, (
                f"The placeholder value '{value}' for {var} in .env.example "
                f"passes _is_real_key — it's not in _PLACEHOLDER_KEY_VALUES. "
                f"Users who don't replace this value will bypass the startup gate."
            )
        assert checked > 0, ".env.example appears to have no API key lines — pattern may be wrong"

    def test_is_real_key_rejects_all_placeholder_variants(self):
        """Every entry in _PLACEHOLDER_KEY_VALUES must be rejected by _is_real_key."""
        import murphy_terminal
        for placeholder in murphy_terminal._PLACEHOLDER_KEY_VALUES:
            assert MurphyTerminalApp._is_real_key(placeholder) is False, (
                f"'{placeholder}' is in _PLACEHOLDER_KEY_VALUES but _is_real_key "
                f"accepted it — the check is case-sensitive and the set entry may "
                f"not match"
            )


# ---------------------------------------------------------------------------
# Gap test: strip_key_wrapping edge cases
# ---------------------------------------------------------------------------


class TestStripKeyWrappingEdgeCases:
    """Additional edge-case tests for strip_key_wrapping that exercise
    combinations and idempotency."""

    def setup_method(self):
        from src.env_manager import strip_key_wrapping
        self.strip = strip_key_wrapping

    def test_empty_string_returns_empty(self):
        assert self.strip("") == ""

    def test_whitespace_only_returns_empty(self):
        assert self.strip("   \t  ") == ""

    def test_invisible_unicode_only_returns_empty(self):
        assert self.strip("\u200b\ufeff\u00a0") == ""

    def test_idempotent_plain_key(self):
        key = "gsk_abcdefghijklmnopqrstuvwx"
        assert self.strip(self.strip(key)) == self.strip(key)

    def test_idempotent_bom_wrapped(self):
        key = "\ufeffgsk_abc\ufeff"
        once = self.strip(key)
        twice = self.strip(once)
        assert once == twice

    def test_mixed_unicode_and_whitespace(self):
        key = "  \u200b  gsk_abcdefghijklmnopqrstuvwx\t\u00a0  "
        assert self.strip(key) == "gsk_abcdefghijklmnopqrstuvwx"

    def test_quote_wrapping_after_unicode_strip(self):
        """Quotes around the key should still be stripped even after unicode removal."""
        key = "\u200b\"gsk_abcdefghijklmnopqrstuvwx\"\u200b"
        assert self.strip(key) == "gsk_abcdefghijklmnopqrstuvwx"

    def test_angle_bracket_after_unicode_strip(self):
        key = "\ufeff<gsk_abcdefghijklmnopqrstuvwx>\ufeff"
        assert self.strip(key) == "gsk_abcdefghijklmnopqrstuvwx"
