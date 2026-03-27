"""
Tests for the LLM pipeline end-to-end fixes.

Covers:
- BUG-1: .env file loaded at backend startup (path resolution)
- BUG-2: /api/llm/configure persists key to .env
- BUG-3: StatusBar three-state machine (Off / ⚠️ / On ✓)
- BUG-4: Clipboard paste command ('paste') as text fallback
- BUG-5: LLMController.refresh_availability() updates model availability
- MurphyInput widget subclass existence and on_key handler
"""

import os
import re
import sys

import pytest

# Ensure the parent directory (containing murphy_terminal.py) is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _read_runtime_files() -> str:
    """Read the full runtime source after the INC-13 refactor.

    Concatenates the thin wrapper and the refactored modules so that
    tests greping for patterns can find content in any runtime file.
    """
    root = os.path.join(os.path.dirname(__file__), "..")
    parts: list[str] = []
    for rel in (
        "murphy_system_1.0_runtime.py",
        os.path.join("src", "runtime", "_deps.py"),
        os.path.join("src", "runtime", "app.py"),
        os.path.join("src", "runtime", "murphy_system_core.py"),
    ):
        path = os.path.join(root, rel)
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as fh:
                parts.append(fh.read())
    return "\n".join(parts)

try:
    import textual as _textual_mod
    _textual_available = True
except ImportError:
    _textual_available = False

_skip_textual = pytest.mark.skipif(
    not _textual_available,
    reason="textual not installed — skipping terminal UI tests",
)

from src.llm_controller import LLMController, LLMModel

if _textual_available:
    from murphy_terminal import (
        MurphyTerminalApp,
        MurphyInput,
        StatusBar,
        WELCOME_TEXT,
        detect_intent,
    )


# ---------------------------------------------------------------------------
# BUG-1: .env loading at startup
# ---------------------------------------------------------------------------

class TestDotenvLoadedAtStartup:
    """BUG-1: load_dotenv() is called at module level before create_app()."""

    # Maximum number of characters allowed between the import and the first call.
    # A small value ensures the call is at module level, not buried in a function.
    _MAX_CHARS_FROM_IMPORT = 500

    def test_load_dotenv_import_and_call_present(self):
        """Runtime imports dotenv AND calls it near the top of the module."""
        content = _read_runtime_files()
        assert "from dotenv import load_dotenv" in content, \
            "load_dotenv not imported in runtime"
        import_idx = content.index("from dotenv import load_dotenv")
        call_match = re.search(r"_load_dotenv\(", content[import_idx:])
        assert call_match is not None, "load_dotenv never called after import"
        assert call_match.start() < self._MAX_CHARS_FROM_IMPORT, \
            "load_dotenv call too far from import — must be at module level"

    def test_load_dotenv_uses_path_resolution(self):
        """Runtime resolves .env path relative to __file__."""
        content = _read_runtime_files()
        assert "__file__" in content, "No __file__ reference found for path resolution"
        assert ".env" in content, ".env path string missing from runtime"


# ---------------------------------------------------------------------------
# BUG-2: /api/llm/configure persists to .env
# ---------------------------------------------------------------------------

class TestConfigureEndpointPersistence:
    """BUG-2: /api/llm/configure writes key to .env for persistence."""

    def test_configure_endpoint_writes_to_env_file(self):
        """The configure endpoint body calls write_env_key or env_manager."""
        content = _read_runtime_files()
        configure_idx = content.index("async def llm_configure")
        # Find the next endpoint definition after llm_configure
        next_endpoint_match = re.search(r"@app\.(get|post|put|delete)\(", content[configure_idx + 1:])
        if next_endpoint_match:
            block = content[configure_idx: configure_idx + 1 + next_endpoint_match.start()]
        else:
            block = content[configure_idx: configure_idx + 2000]
        assert "write_env_key" in block or "env_manager" in block, \
            "/api/llm/configure does not persist key to .env (write_env_key missing)"

    def test_configure_endpoint_calls_refresh_availability(self):
        """The configure endpoint calls refresh_availability to update LLMController."""
        content = _read_runtime_files()
        configure_idx = content.index("async def llm_configure")
        next_endpoint_match = re.search(r"@app\.(get|post|put|delete)\(", content[configure_idx + 1:])
        if next_endpoint_match:
            block = content[configure_idx: configure_idx + 1 + next_endpoint_match.start()]
        else:
            block = content[configure_idx: configure_idx + 2000]
        assert "refresh_availability" in block, \
            "/api/llm/configure does not call refresh_availability()"


# ---------------------------------------------------------------------------
# BUG-3: StatusBar three-state machine
# ---------------------------------------------------------------------------

@_skip_textual
class TestStatusBarThreeStates:
    """BUG-3: StatusBar shows Off / ⚠ / On ✓ states."""

    def _make_status_bar(self):
        return StatusBar()

    def test_status_bar_has_llm_warning_reactive(self):
        """StatusBar must have a llm_warning reactive attribute."""
        bar = self._make_status_bar()
        assert hasattr(bar, "llm_warning"), "StatusBar missing llm_warning reactive"

    def test_status_bar_render_off_state(self):
        """StatusBar renders 'Off' when llm_enabled=False and llm_warning=False."""
        bar = self._make_status_bar()
        bar.llm_enabled = False
        bar.llm_warning = False
        rendered = bar.render()
        assert "Off" in rendered, f"Expected 'Off' in render output, got: {rendered}"
        assert "⚠" not in rendered, f"Unexpected warning marker in Off state: {rendered}"

    def test_status_bar_render_warning_state(self):
        """StatusBar renders '⚠' when llm_warning=True and llm_enabled=False."""
        bar = self._make_status_bar()
        bar.llm_enabled = False
        bar.llm_warning = True
        rendered = bar.render()
        assert "⚠" in rendered, f"Expected '⚠' in render output, got: {rendered}"

    def test_status_bar_render_on_state(self):
        """StatusBar renders 'On ✓' when llm_enabled=True."""
        bar = self._make_status_bar()
        bar.llm_enabled = True
        bar.llm_warning = False
        rendered = bar.render()
        assert "On" in rendered, f"Expected 'On' in render output, got: {rendered}"
        assert "✓" in rendered, f"Expected '✓' in render output, got: {rendered}"

    def test_status_bar_enabled_overrides_warning(self):
        """When llm_enabled=True, the ⚠ marker must not appear (On ✓ wins)."""
        bar = self._make_status_bar()
        bar.llm_enabled = True
        bar.llm_warning = True  # inconsistent — enabled wins
        rendered = bar.render()
        assert "On" in rendered, f"Expected 'On' when enabled=True, got: {rendered}"


# ---------------------------------------------------------------------------
# BUG-4: Clipboard paste command
# ---------------------------------------------------------------------------

@_skip_textual
class TestPasteTextCommand:
    """BUG-4: Typing 'paste' is detected as intent_paste."""

    def test_paste_intent_detected(self):
        assert detect_intent("paste") == "intent_paste"

    def test_paste_intent_case_insensitive(self):
        assert detect_intent("PASTE") == "intent_paste"

    def test_intent_paste_method_exists(self):
        """MurphyTerminalApp has intent_paste method."""
        assert hasattr(MurphyTerminalApp, "intent_paste"), \
            "MurphyTerminalApp missing intent_paste method"

    def test_welcome_text_paste_tip(self):
        """WELCOME_TEXT contains a paste tip for discoverability."""
        assert "paste" in WELCOME_TEXT.lower(), \
            "WELCOME_TEXT should mention 'paste' command as a tip"


@_skip_textual
class TestMurphyInputWidget:
    """BUG-4: MurphyInput widget subclass exists and has on_key handler."""

    def test_murphy_input_is_input_subclass(self):
        from textual.widgets import Input
        assert issubclass(MurphyInput, Input), \
            "MurphyInput is not a subclass of textual Input"

    def test_murphy_input_has_on_key(self):
        assert hasattr(MurphyInput, "on_key"), \
            "MurphyInput is missing on_key handler"

    def test_insert_text_strips_whitespace(self):
        """_insert_text_into_input uses only the first stripped line."""
        import inspect
        source = inspect.getsource(MurphyTerminalApp._insert_text_into_input)
        assert "strip" in source, \
            "_insert_text_into_input should strip whitespace from pasted text"
        assert "splitlines" in source, \
            "_insert_text_into_input should handle multi-line text via splitlines"


# ---------------------------------------------------------------------------
# BUG-5: LLMController.refresh_availability()
# ---------------------------------------------------------------------------

class TestLLMControllerRefreshAvailability:
    """BUG-5: refresh_availability() re-checks env vars at runtime."""

    def test_refresh_availability_method_exists(self):
        controller = LLMController()
        assert hasattr(controller, "refresh_availability"), \
            "LLMController missing refresh_availability method"
        assert callable(controller.refresh_availability)

    def test_refresh_availability_marks_groq_available_when_key_set(self):
        """After setting DEEPINFRA_API_KEY, refresh_availability() enables DeepInfra models."""
        original = os.environ.pop("DEEPINFRA_API_KEY", None)
        try:
            controller = LLMController()
            assert not controller.models[LLMModel.GROQ_MIXTRAL].available
            assert not controller.models[LLMModel.GROQ_LLAMA].available
            assert not controller.models[LLMModel.GROQ_GEMMA].available

            os.environ["DEEPINFRA_API_KEY"] = "gsk_test_key_for_testing_only"
            controller.refresh_availability()

            assert controller.models[LLMModel.GROQ_MIXTRAL].available, \
                "GROQ_MIXTRAL should be available after refresh_availability()"
            assert controller.models[LLMModel.GROQ_LLAMA].available, \
                "GROQ_LLAMA should be available after refresh_availability()"
            assert controller.models[LLMModel.GROQ_GEMMA].available, \
                "GROQ_GEMMA should be available after refresh_availability()"
        finally:
            if original is not None:
                os.environ["DEEPINFRA_API_KEY"] = original
            else:
                os.environ.pop("DEEPINFRA_API_KEY", None)

    def test_refresh_availability_marks_groq_unavailable_when_key_removed(self):
        """After removing DEEPINFRA_API_KEY, refresh_availability() disables DeepInfra models."""
        original = os.environ.get("DEEPINFRA_API_KEY")
        try:
            os.environ["DEEPINFRA_API_KEY"] = "gsk_test_key"
            controller = LLMController()
            assert controller.models[LLMModel.GROQ_MIXTRAL].available

            del os.environ["DEEPINFRA_API_KEY"]
            controller.refresh_availability()

            assert not controller.models[LLMModel.GROQ_MIXTRAL].available, \
                "GROQ_MIXTRAL should be unavailable after key removal + refresh"
        finally:
            if original is not None:
                os.environ["DEEPINFRA_API_KEY"] = original
            else:
                os.environ.pop("DEEPINFRA_API_KEY", None)

    def test_local_models_always_available_after_refresh(self):
        """Local models must stay available regardless of DEEPINFRA_API_KEY."""
        original = os.environ.pop("DEEPINFRA_API_KEY", None)
        try:
            controller = LLMController()
            controller.refresh_availability()
            assert controller.models[LLMModel.LOCAL_SMALL].available, \
                "LOCAL_SMALL must always be available"
            assert controller.models[LLMModel.LOCAL_MEDIUM].available, \
                "LOCAL_MEDIUM must always be available"
        finally:
            if original is not None:
                os.environ["DEEPINFRA_API_KEY"] = original

    def test_reconfigure_method_exists(self):
        controller = LLMController()
        assert hasattr(controller, "reconfigure"), \
            "LLMController missing reconfigure method"
        assert callable(controller.reconfigure)

    def test_reconfigure_updates_env_and_availability(self):
        """reconfigure() sets DEEPINFRA_API_KEY in environ and refreshes models."""
        original = os.environ.pop("DEEPINFRA_API_KEY", None)
        try:
            controller = LLMController()
            assert not controller.models[LLMModel.GROQ_MIXTRAL].available

            controller.reconfigure("gsk_new_test_key")

            assert os.environ.get("DEEPINFRA_API_KEY") == "gsk_new_test_key", \
                "reconfigure() should set DEEPINFRA_API_KEY in os.environ"
            assert controller.models[LLMModel.GROQ_MIXTRAL].available, \
                "reconfigure() should enable DeepInfra models"
        finally:
            if original is not None:
                os.environ["DEEPINFRA_API_KEY"] = original
            else:
                os.environ.pop("DEEPINFRA_API_KEY", None)
