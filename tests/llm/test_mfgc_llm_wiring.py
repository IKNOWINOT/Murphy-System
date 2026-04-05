# Copyright © 2020-2026 Inoni LLC — Created by Corey Post
# License: BSL 1.1
"""
Module: tests/llm/test_mfgc_llm_wiring.py
Subsystem: MFGC LLM Integration — DeepInfra/Together.ai wiring through MurphyLLMProvider
Label: TEST-MFGC-LLM-WIRING-001

Commissioning Answers (G1–G9)
-----------------------------
1. G1 — Purpose: Does this do what it was designed to do?
   YES — validates that _try_llm_generate() delegates to MurphyLLMProvider
   instead of making inline HTTP calls, and that the full MFGC provider
   chain (DeepInfra → Together.ai → onboard) is exercised.

2. G2 — Spec: What is it supposed to do?
   _try_llm_generate() is the MFGC gate for LLM generation. It must:
   a) Delegate to MurphyLLMProvider (not inline requests.post)
   b) Return (text, None) when an external provider (deepinfra/together) answers
   c) Return (None, None) when only onboard is available — so _deterministic_reply
      runs the full Magnify x3/Solidify/HITL pipeline
   d) Never crash — all exceptions produce (None, None)

3. G3 — Conditions: What conditions are possible?
   - DeepInfra key set + API up → DeepInfra answers
   - DeepInfra down, Together.ai key set → Together.ai answers
   - Both down → onboard fallback → (None, None) returned
   - No API keys → onboard → (None, None) returned
   - llm_provider import fails → (None, None) returned
   - Provider raises unexpected exception → (None, None) returned

4. G4 — Test Profile: Does test profile reflect full range?
   YES — 15 tests covering all paths above.

5. G5 — Expected vs Actual: All tests pass.
6. G6 — Regression Loop: pytest tests/llm/test_mfgc_llm_wiring.py -v
7. G7 — As-Builts: Docstrings and labels updated.
8. G8 — Hardening: Exception paths tested. (None, None) contract enforced.
9. G9 — Re-commissioned: YES — after wiring refactor.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SRC_DIR = _REPO_ROOT / "Murphy System" / "src"
_ROOT_SRC = _REPO_ROOT / "src"

for _p in (str(_SRC_DIR), str(_ROOT_SRC)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from src.llm_provider import (
    LLMCompletion,
    MurphyLLMProvider,
    reset_llm,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Remove LLM-related env vars and reset the singleton between tests."""
    for key in (
        "DEEPINFRA_API_KEY", "TOGETHER_API_KEY", "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY", "MURPHY_LLM_PROVIDER", "MURPHY_LLM_MODEL",
    ):
        monkeypatch.delenv(key, raising=False)
    reset_llm(None)
    yield
    reset_llm(None)


def _make_core():
    """Construct a minimal MurphySystem for testing _try_llm_generate."""
    from src.runtime.murphy_system_core import MurphySystem
    core = MurphySystem.__new__(MurphySystem)
    # Minimal attributes needed by the methods under test
    core.librarian = MagicMock()
    core.chat_sessions = {}
    # API_PROVIDER_LINKS stub
    core.API_PROVIDER_LINKS = {
        "deepinfra": {"name": "DeepInfra", "url": "https://deepinfra.com/keys", "env_var": "DEEPINFRA_API_KEY"},
    }
    return core


# ---------------------------------------------------------------------------
# G3-a: DeepInfra succeeds — returns external content
# ---------------------------------------------------------------------------

class TestMFGCLLMDeepInfraSuccess:
    """MFGC-LLM-GEN-001: DeepInfra primary provider returns content."""

    def test_deepinfra_response_surfaced(self, monkeypatch):
        """When DeepInfra answers, _try_llm_generate returns (text, None)."""
        monkeypatch.setenv("DEEPINFRA_API_KEY", "test-key-123")
        fake_result = LLMCompletion(
            content="Hello from DeepInfra!",
            model="meta-llama/Meta-Llama-3.1-8B-Instruct",
            provider="deepinfra",
            latency_seconds=0.5,
        )
        mock_provider = MagicMock(spec=MurphyLLMProvider)
        mock_provider.complete_messages.return_value = fake_result

        with patch("src.llm_provider.get_llm", return_value=mock_provider):
            core = _make_core()
            text, error = core._try_llm_generate("What can you automate?")

        assert text == "Hello from DeepInfra!"
        assert error is None
        mock_provider.complete_messages.assert_called_once()
        # Verify MFGC system prompt is in the messages
        call_args = mock_provider.complete_messages.call_args
        messages = call_args[0][0]
        assert any("MFGC" in m["content"] for m in messages if m["role"] == "system")


# ---------------------------------------------------------------------------
# G3-b: Together.ai fallback succeeds
# ---------------------------------------------------------------------------

class TestMFGCLLMTogetherFallback:
    """MFGC-LLM-GEN-001: Together.ai fallback returns content."""

    def test_together_response_surfaced(self, monkeypatch):
        """When Together.ai answers (DeepInfra was down), returns (text, None)."""
        monkeypatch.setenv("TOGETHER_API_KEY", "tog-key-456")
        fake_result = LLMCompletion(
            content="Hello from Together.ai!",
            model="meta-llama/Llama-3.1-8B-Instruct-Turbo",
            provider="together",
            latency_seconds=0.8,
        )
        mock_provider = MagicMock(spec=MurphyLLMProvider)
        mock_provider.complete_messages.return_value = fake_result

        with patch("src.llm_provider.get_llm", return_value=mock_provider):
            core = _make_core()
            text, error = core._try_llm_generate("Tell me about automation")

        assert text == "Hello from Together.ai!"
        assert error is None


# ---------------------------------------------------------------------------
# G3-c: Both providers down — onboard fallback → (None, None)
# ---------------------------------------------------------------------------

class TestMFGCLLMOnboardFallthrough:
    """MFGC-LLM-GEN-001: Onboard provider triggers (None, None) pass-through."""

    def test_onboard_returns_none_none(self):
        """When only onboard is available, returns (None, None) for deterministic pipeline."""
        fake_result = LLMCompletion(
            content="[Murphy Onboard] acknowledged",
            model="murphy-onboard",
            provider="onboard",
        )
        mock_provider = MagicMock(spec=MurphyLLMProvider)
        mock_provider.complete_messages.return_value = fake_result

        with patch("src.llm_provider.get_llm", return_value=mock_provider):
            core = _make_core()
            text, error = core._try_llm_generate("Help me automate")

        # Critical contract: (None, None) so _deterministic_reply runs
        assert text is None
        assert error is None

    def test_fallback_provider_returns_none_none(self):
        """Any non-external provider (fallback, onboard) → (None, None)."""
        for provider_name in ("onboard", "fallback", "local", "murphy-local"):
            fake_result = LLMCompletion(
                content="Some local response",
                model="local-model",
                provider=provider_name,
            )
            mock_provider = MagicMock(spec=MurphyLLMProvider)
            mock_provider.complete_messages.return_value = fake_result

            with patch("src.llm_provider.get_llm", return_value=mock_provider):
                core = _make_core()
                text, error = core._try_llm_generate("Test")

            assert text is None, f"Expected None for provider={provider_name}"
            assert error is None, f"Expected None error for provider={provider_name}"


# ---------------------------------------------------------------------------
# G3-d: Import failure → graceful (None, None)
# ---------------------------------------------------------------------------

class TestMFGCLLMImportFailure:
    """MFGC-LLM-GEN-001: Missing llm_provider module → graceful fallback."""

    def test_import_error_returns_none_none(self):
        """If get_llm raises ImportError at call time, returns (None, None)."""
        core = _make_core()
        with patch("src.llm_provider.get_llm", side_effect=ImportError("no module")):
            text, error = core._try_llm_generate("Test")

        assert text is None
        assert error is None


# ---------------------------------------------------------------------------
# G3-e: Provider raises unexpected exception → (None, None)
# ---------------------------------------------------------------------------

class TestMFGCLLMExceptionHandling:
    """MFGC-LLM-GEN-001: Unexpected exceptions → graceful (None, None)."""

    def test_provider_runtime_error(self):
        """RuntimeError from provider → (None, None)."""
        mock_provider = MagicMock(spec=MurphyLLMProvider)
        mock_provider.complete_messages.side_effect = RuntimeError("connection reset")

        with patch("src.llm_provider.get_llm", return_value=mock_provider):
            core = _make_core()
            text, error = core._try_llm_generate("Test")

        assert text is None
        assert error is None

    def test_provider_timeout_error(self):
        """Timeout from provider → (None, None)."""
        mock_provider = MagicMock(spec=MurphyLLMProvider)
        mock_provider.complete_messages.side_effect = TimeoutError("15s exceeded")

        with patch("src.llm_provider.get_llm", return_value=mock_provider):
            core = _make_core()
            text, error = core._try_llm_generate("Test")

        assert text is None
        assert error is None


# ---------------------------------------------------------------------------
# G3-f: Message building includes MFGC/5U framework
# ---------------------------------------------------------------------------

class TestMFGCMessageBuilding:
    """MFGC-LLM-MSG-001: System prompt encodes MFGC/5U framework."""

    def test_system_prompt_contains_mfgc_dimensions(self):
        """System message includes all MFGC/5U dimension names."""
        core = _make_core()
        messages = core._build_mfgc_llm_messages("Hello", "some context")

        system_msgs = [m for m in messages if m["role"] == "system"]
        assert len(system_msgs) >= 1
        system_text = " ".join(m["content"] for m in system_msgs)

        # 5U dimensions
        for dim in ("5U-Identity", "5U-Context", "5U-Scale", "5U-Temporal", "5U-Data"):
            assert dim in system_text, f"Missing {dim} in MFGC system prompt"

        # MFGC gates
        for gate in ("MFGC-Objective", "MFGC-Constraint", "MFGC-Integration", "MFGC-Governance"):
            assert gate in system_text, f"Missing {gate} in MFGC system prompt"

    def test_context_appended_as_system_message(self):
        """Context string is appended as a second system message."""
        core = _make_core()
        messages = core._build_mfgc_llm_messages("Hello", "user profile data")

        system_msgs = [m for m in messages if m["role"] == "system"]
        assert len(system_msgs) == 2
        assert "user profile data" in system_msgs[1]["content"]

    def test_no_context_produces_single_system_message(self):
        """Empty context string → only one system message."""
        core = _make_core()
        messages = core._build_mfgc_llm_messages("Hello", "")

        system_msgs = [m for m in messages if m["role"] == "system"]
        assert len(system_msgs) == 1

    def test_user_prompt_is_last_message(self):
        """User prompt is always the final message."""
        core = _make_core()
        messages = core._build_mfgc_llm_messages("What can you do?", "ctx")

        assert messages[-1]["role"] == "user"
        assert messages[-1]["content"] == "What can you do?"


# ---------------------------------------------------------------------------
# G3-g: _get_llm_status includes Together.ai in provider chain
# ---------------------------------------------------------------------------

class TestMFGCLLMStatusProviderChain:
    """MFGC-LLM-STATUS-001: Status reports full provider chain."""

    def test_deepinfra_plus_together_chain(self, monkeypatch):
        """Both keys set → providers list includes DeepInfra + Together.ai + onboard."""
        monkeypatch.setenv("DEEPINFRA_API_KEY", "di-key")
        monkeypatch.setenv("TOGETHER_API_KEY", "tog-key")
        core = _make_core()
        status = core._get_llm_status()

        providers = status.get("providers", [])
        provider_names = [p["provider"] for p in providers]
        assert "deepinfra" in provider_names
        assert "together" in provider_names
        assert "onboard" in provider_names
        assert status["mode"] == "external_api"

    def test_deepinfra_only_chain(self, monkeypatch):
        """Only DeepInfra key → providers list has DeepInfra + onboard (no Together)."""
        monkeypatch.setenv("DEEPINFRA_API_KEY", "di-key")
        core = _make_core()
        status = core._get_llm_status()

        providers = status.get("providers", [])
        provider_names = [p["provider"] for p in providers]
        assert "deepinfra" in provider_names
        assert "together" not in provider_names
        assert "onboard" in provider_names

    def test_no_deepinfra_but_together_available(self, monkeypatch):
        """DeepInfra key missing, Together.ai key set → falls to Together.ai."""
        monkeypatch.setenv("MURPHY_LLM_PROVIDER", "deepinfra")
        monkeypatch.setenv("TOGETHER_API_KEY", "tog-key")
        core = _make_core()
        status = core._get_llm_status()

        assert status["provider"] == "together"
        assert status["mode"] == "external_api"
        assert "Together.ai" in status.get("note", "")

    def test_no_keys_onboard_mode(self):
        """No API keys → onboard mode."""
        core = _make_core()
        status = core._get_llm_status()

        assert status["provider"] == "onboard"
        assert status["mode"] == "onboard"
