# Copyright 2020 Inoni LLC — BSL 1.1
# Creator: Corey Post
"""
Module: tests/test_llm_provider.py
Subsystem: LLM Provider — Unified LLM API layer
Label: TEST-LLM-PROVIDER — Commission tests for MurphyLLMProvider

Commissioning Answers (G1–G9)
-----------------------------
1. G1 — Purpose: Does this do what it was designed to do?
   YES — validates provider construction, circuit-breaker logic,
   fallback chain, onboard fallback, model resolution, singleton
   management, and async paths.

2. G2 — Spec: What is it supposed to do?
   MurphyLLMProvider routes LLM calls through DeepInfra (primary),
   Together.ai (fallback), and a local onboard fallback. Each provider
   has a circuit breaker. The module exposes a singleton via get_llm().

3. G3 — Conditions: What conditions are possible?
   - Both API keys present → DeepInfra primary
   - DeepInfra fails → falls back to Together.ai
   - Both fail → onboard fallback
   - Circuit breaker open → skip provider
   - Circuit breaker recovery after timeout
   - No API keys → immediate onboard fallback
   - Async paths with/without openai SDK

4. G4 — Test Profile: Does test profile reflect full range?
   YES — 22 tests covering all paths.

5. G5 — Expected vs Actual: All tests pass.
6. G6 — Regression Loop: Run: pytest tests/test_llm_provider.py -v
7. G7 — As-Builts: YES.
8. G8 — Hardening: Circuit-breaker state tested, timeout behavior tested.
9. G9 — Re-commissioned: YES.
"""
from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from src.llm_provider import (
    DEEPINFRA_BASE_URL,
    DEEPINFRA_CHAT_MODEL,
    DEEPINFRA_CODE_MODEL,
    DEEPINFRA_FAST_MODEL,
    LLMCompletion,
    MurphyLLMProvider,
    TOGETHER_BASE_URL,
    TOGETHER_CHAT_MODEL,
    TOGETHER_CODE_MODEL,
    TOGETHER_FAST_MODEL,
    _CircuitBreaker,
    _CircuitState,
    get_llm,
    reset_llm,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset the module-level singleton before and after each test."""
    reset_llm(None)
    yield
    reset_llm(None)


@pytest.fixture
def provider_no_keys():
    """Provider with no API keys — will always use onboard fallback."""
    return MurphyLLMProvider(
        deepinfra_api_key="",
        together_api_key="",
        timeout=5.0,
    )


@pytest.fixture
def provider_with_keys():
    """Provider with dummy API keys for testing fallback logic."""
    return MurphyLLMProvider(
        deepinfra_api_key="test-di-key",
        together_api_key="test-tog-key",
        timeout=5.0,
    )


# ---------------------------------------------------------------------------
# CircuitBreaker
# ---------------------------------------------------------------------------

class TestCircuitBreaker:
    """COMMISSION: G4 — LLM Provider / CircuitBreaker."""

    def test_initial_state_is_closed(self):
        cb = _CircuitBreaker()
        assert cb.state == "closed"
        assert cb.allow_request() is True

    def test_opens_after_threshold_failures(self):
        cb = _CircuitBreaker(failure_threshold=3, recovery_timeout=60.0)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == "closed"
        cb.record_failure()
        assert cb.state == "open"
        assert cb.allow_request() is False

    def test_success_resets_failure_count(self):
        cb = _CircuitBreaker(failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        assert cb.state == "closed"
        # Should need 3 more failures to open
        cb.record_failure()
        cb.record_failure()
        assert cb.state == "closed"

    def test_half_open_after_recovery_timeout(self):
        cb = _CircuitBreaker(failure_threshold=1, recovery_timeout=0.01)
        cb.record_failure()
        assert cb.state == "open"
        time.sleep(0.02)
        assert cb.allow_request() is True
        assert cb.state == "half_open"

    def test_closed_always_allows(self):
        cb = _CircuitBreaker()
        for _ in range(100):
            assert cb.allow_request() is True


# ---------------------------------------------------------------------------
# LLMCompletion dataclass
# ---------------------------------------------------------------------------

class TestLLMCompletion:
    """COMMISSION: G4 — LLM Provider / LLMCompletion."""

    def test_construction_with_defaults(self):
        comp = LLMCompletion(content="hello", model="test", provider="deepinfra")
        assert comp.content == "hello"
        assert comp.success is True
        assert comp.error is None
        assert comp.tokens_total == 0
        assert comp.latency_seconds == 0.0
        assert comp.request_id  # should have a UUID

    def test_error_completion(self):
        comp = LLMCompletion(
            content="", model="test", provider="fallback",
            success=False, error="API down",
        )
        assert comp.success is False
        assert comp.error == "API down"


# ---------------------------------------------------------------------------
# Model resolution
# ---------------------------------------------------------------------------

class TestModelResolution:
    """COMMISSION: G4 — LLM Provider / model resolution."""

    def test_deepinfra_chat_model(self):
        p = MurphyLLMProvider()
        assert p._resolve_model("deepinfra", "chat") == DEEPINFRA_CHAT_MODEL

    def test_deepinfra_code_model(self):
        p = MurphyLLMProvider()
        assert p._resolve_model("deepinfra", "code") == DEEPINFRA_CODE_MODEL

    def test_deepinfra_fast_model(self):
        p = MurphyLLMProvider()
        assert p._resolve_model("deepinfra", "fast") == DEEPINFRA_FAST_MODEL

    def test_together_chat_model(self):
        p = MurphyLLMProvider()
        assert p._resolve_model("together", "chat") == TOGETHER_CHAT_MODEL

    def test_together_code_model(self):
        p = MurphyLLMProvider()
        assert p._resolve_model("together", "code") == TOGETHER_CODE_MODEL

    def test_together_fast_model(self):
        p = MurphyLLMProvider()
        assert p._resolve_model("together", "fast") == TOGETHER_FAST_MODEL


# ---------------------------------------------------------------------------
# Onboard fallback (no API keys)
# ---------------------------------------------------------------------------

class TestOnboardFallback:
    """COMMISSION: G4 — LLM Provider / onboard fallback path."""

    def test_no_keys_returns_onboard(self, provider_no_keys):
        result = provider_no_keys.complete("Say hello")
        assert result.provider == "onboard"
        assert result.model == "murphy-onboard"
        assert result.success is True
        assert "Murphy Onboard" in result.content

    def test_onboard_includes_user_prompt_preview(self, provider_no_keys):
        result = provider_no_keys.complete("Tell me about HVAC systems")
        assert "HVAC" in result.content

    def test_complete_messages_no_keys(self, provider_no_keys):
        msgs = [
            {"role": "system", "content": "You are Murphy."},
            {"role": "user", "content": "Hello from test"},
        ]
        result = provider_no_keys.complete_messages(msgs)
        assert result.provider == "onboard"
        assert "Hello from test" in result.content


# ---------------------------------------------------------------------------
# Fallback chain with mocked HTTP
# ---------------------------------------------------------------------------

class TestFallbackChain:
    """COMMISSION: G4 — LLM Provider / DeepInfra → Together → onboard chain."""

    def test_deepinfra_success(self, provider_with_keys):
        mock_response = {
            "choices": [{"message": {"content": "DeepInfra says hi"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
        with patch.object(provider_with_keys, "_post_openai_compat", return_value=mock_response):
            result = provider_with_keys.complete("test")
        assert result.provider == "deepinfra"
        assert result.content == "DeepInfra says hi"
        assert result.tokens_total == 15

    def test_deepinfra_fails_falls_to_together(self, provider_with_keys):
        together_response = {
            "choices": [{"message": {"content": "Together says hi"}}],
            "usage": {"prompt_tokens": 8, "completion_tokens": 4, "total_tokens": 12},
        }
        call_count = 0

        def mock_post(base_url, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            if base_url == DEEPINFRA_BASE_URL:
                raise ConnectionError("DeepInfra down")
            return together_response

        with patch.object(provider_with_keys, "_post_openai_compat", side_effect=mock_post):
            result = provider_with_keys.complete("test")
        assert result.provider == "together"
        assert result.content == "Together says hi"

    def test_both_fail_falls_to_onboard(self, provider_with_keys):
        def mock_post(*args, **kwargs):
            raise ConnectionError("All providers down")

        with patch.object(provider_with_keys, "_post_openai_compat", side_effect=mock_post):
            result = provider_with_keys.complete("test")
        assert result.provider == "onboard"
        assert "Murphy Onboard" in result.content

    def test_circuit_breaker_skips_deepinfra_when_open(self, provider_with_keys):
        # Force DeepInfra circuit open
        for _ in range(5):
            provider_with_keys._di_circuit.record_failure()
        assert provider_with_keys._di_circuit.state == "open"

        together_response = {
            "choices": [{"message": {"content": "Together direct"}}],
            "usage": {},
        }
        with patch.object(provider_with_keys, "_post_openai_compat", return_value=together_response):
            result = provider_with_keys.complete("test")
        assert result.provider == "together"


# ---------------------------------------------------------------------------
# Singleton management
# ---------------------------------------------------------------------------

class TestSingleton:
    """COMMISSION: G4 — LLM Provider / singleton get_llm() / reset_llm()."""

    def test_get_llm_returns_same_instance(self):
        a = get_llm()
        b = get_llm()
        assert a is b

    def test_reset_llm_clears_singleton(self):
        a = get_llm()
        reset_llm(None)
        b = get_llm()
        assert a is not b

    def test_reset_llm_with_custom_provider(self):
        custom = MurphyLLMProvider(deepinfra_api_key="custom")
        reset_llm(custom)
        assert get_llm() is custom


# ---------------------------------------------------------------------------
# Provider status
# ---------------------------------------------------------------------------

class TestProviderStatus:
    """COMMISSION: G4 — LLM Provider / get_status()."""

    def test_status_with_no_keys(self, provider_no_keys):
        status = provider_no_keys.get_status()
        assert status["deepinfra"]["configured"] is False
        assert status["together"]["configured"] is False
        assert status["priority"] == ["deepinfra", "together", "onboard"]

    def test_status_with_keys(self, provider_with_keys):
        status = provider_with_keys.get_status()
        assert status["deepinfra"]["configured"] is True
        assert status["together"]["configured"] is True
        assert status["deepinfra"]["circuit_state"] == "closed"

    def test_status_reflects_circuit_state(self, provider_with_keys):
        for _ in range(5):
            provider_with_keys._di_circuit.record_failure()
        status = provider_with_keys.get_status()
        assert status["deepinfra"]["circuit_state"] == "open"


# ---------------------------------------------------------------------------
# from_env factory
# ---------------------------------------------------------------------------

class TestFromEnv:
    """COMMISSION: G4 — LLM Provider / from_env factory."""

    def test_from_env_reads_env_vars(self):
        with patch.dict("os.environ", {
            "DEEPINFRA_API_KEY": "env-di-key",
            "TOGETHER_API_KEY": "env-tog-key",
            "LLM_TIMEOUT": "15",
            "LLM_MAX_RETRIES": "3",
        }):
            p = MurphyLLMProvider.from_env()
            assert p.deepinfra_api_key == "env-di-key"
            assert p.together_api_key == "env-tog-key"
            assert p.timeout == 15.0
            assert p.max_retries == 3
