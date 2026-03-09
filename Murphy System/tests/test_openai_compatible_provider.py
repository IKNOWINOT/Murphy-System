"""
Tests for OpenAI-Compatible LLM Provider (INC-01 / C-01).

Covers:
  - Provider configuration from environment variables
  - Chat completion happy path (mocked OpenAI SDK)
  - Fallback behaviour when provider is unavailable
  - Circuit breaker transitions
  - Reconfiguration / hot-reload
  - Edge cases (empty messages, missing API key, ImportError)

Copyright © 2020-2026 Inoni LLC — Created by Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import asyncio
import os
import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure src/ is importable
_src_dir = os.path.join(os.path.dirname(__file__), "..", "src")
_src_dir = os.path.abspath(_src_dir)
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from openai_compatible_provider import (
    ChatMessage,
    CompletionResponse,
    OpenAICompatibleProvider,
    ProviderConfig,
    ProviderType,
    _CircuitBreaker,
    _CircuitState,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def provider_config() -> ProviderConfig:
    """A basic config for testing with a dummy key."""
    return ProviderConfig(
        provider_type=ProviderType.OPENAI,
        api_key="sk-test-key-12345",
        base_url=None,
        default_model="gpt-3.5-turbo",
    )


@pytest.fixture
def provider(provider_config: ProviderConfig) -> OpenAICompatibleProvider:
    """Provider instance with a dummy key (no real API calls)."""
    return OpenAICompatibleProvider(provider_config)


@pytest.fixture
def messages() -> list[ChatMessage]:
    """A minimal conversation."""
    return [
        ChatMessage(role="system", content="You are Murphy."),
        ChatMessage(role="user", content="Hello!"),
    ]


# ---------------------------------------------------------------------------
# Configuration tests
# ---------------------------------------------------------------------------


class TestProviderConfig:
    """Tests for provider configuration and factory methods."""

    def test_default_config_values(self) -> None:
        cfg = ProviderConfig()
        assert cfg.provider_type == ProviderType.OPENAI
        assert cfg.default_model == "gpt-3.5-turbo"
        assert cfg.max_retries == 2
        assert cfg.timeout_seconds == 30.0

    def test_from_env_openai(self) -> None:
        env = {
            "OPENAI_API_KEY": "sk-env-key",
            "OPENAI_PROVIDER_TYPE": "openai",
            "OPENAI_DEFAULT_MODEL": "gpt-4",
        }
        with patch.dict(os.environ, env, clear=False):
            p = OpenAICompatibleProvider.from_env()
            assert p.provider_type == ProviderType.OPENAI
            assert p.default_model == "gpt-4"
            assert p.available is True

    def test_from_env_groq(self) -> None:
        env = {
            "OPENAI_PROVIDER_TYPE": "groq",
            "GROQ_API_KEY": "gsk_test",
        }
        with patch.dict(os.environ, env, clear=False):
            p = OpenAICompatibleProvider.from_env()
            assert p.provider_type == ProviderType.GROQ
            assert p.default_model == "mixtral-8x7b-32768"

    def test_from_env_ollama_no_key_still_available(self) -> None:
        env = {"OPENAI_PROVIDER_TYPE": "ollama"}
        with patch.dict(os.environ, env, clear=False):
            p = OpenAICompatibleProvider.from_env()
            assert p.provider_type == ProviderType.OLLAMA
            assert p.available is True  # Local providers don't require keys

    def test_unavailable_when_no_key_for_cloud(self) -> None:
        cfg = ProviderConfig(provider_type=ProviderType.OPENAI, api_key="")
        p = OpenAICompatibleProvider(cfg)
        assert p.available is False


# ---------------------------------------------------------------------------
# Chat completion tests (mocked SDK)
# ---------------------------------------------------------------------------


def _mock_openai_module() -> types.ModuleType:
    """Build a fake ``openai`` module with AsyncOpenAI / OpenAI stubs."""
    mod = types.ModuleType("openai")

    # Build a realistic response object
    usage = MagicMock()
    usage.prompt_tokens = 10
    usage.completion_tokens = 20
    usage.total_tokens = 30

    choice_msg = MagicMock()
    choice_msg.content = "Hello from Murphy!"

    choice = MagicMock()
    choice.message = choice_msg

    response = MagicMock()
    response.choices = [choice]
    response.usage = usage

    # AsyncOpenAI mock
    async_client = MagicMock()
    create_coro = AsyncMock(return_value=response)
    async_client.chat.completions.create = create_coro

    async_cls = MagicMock(return_value=async_client)
    mod.AsyncOpenAI = async_cls

    # Sync OpenAI mock
    sync_client = MagicMock()
    sync_client.chat.completions.create = MagicMock(return_value=response)
    sync_cls = MagicMock(return_value=sync_client)
    mod.OpenAI = sync_cls

    return mod


class TestChatCompletion:
    """Tests for chat_completion (async)."""

    @pytest.mark.asyncio
    async def test_happy_path(self, provider, messages) -> None:
        fake_openai = _mock_openai_module()
        with patch.dict("sys.modules", {"openai": fake_openai}):
            # Reset cached clients
            provider._async_client = None
            resp = await provider.chat_completion(messages)

        assert isinstance(resp, CompletionResponse)
        assert resp.content == "Hello from Murphy!"
        assert resp.tokens_total == 30
        assert resp.provider == "openai"
        assert resp.latency_seconds >= 0

    @pytest.mark.asyncio
    async def test_model_override(self, provider, messages) -> None:
        fake_openai = _mock_openai_module()
        with patch.dict("sys.modules", {"openai": fake_openai}):
            provider._async_client = None
            resp = await provider.chat_completion(messages, model="gpt-4")

        assert resp.model == "gpt-4"

    @pytest.mark.asyncio
    async def test_fallback_when_unavailable(self, messages) -> None:
        cfg = ProviderConfig(provider_type=ProviderType.OPENAI, api_key="")
        p = OpenAICompatibleProvider(cfg)
        resp = await p.chat_completion(messages)

        assert resp.provider == "fallback"
        assert "unavailable" in resp.content.lower()

    @pytest.mark.asyncio
    async def test_fallback_on_exception(self, provider, messages) -> None:
        """If the SDK raises, the provider should return a fallback."""
        fake_openai = _mock_openai_module()
        # Make create() raise
        fake_openai.AsyncOpenAI.return_value.chat.completions.create = AsyncMock(
            side_effect=ConnectionError("network down"),
        )
        with patch.dict("sys.modules", {"openai": fake_openai}):
            provider._async_client = None
            resp = await provider.chat_completion(messages)

        assert resp.provider == "fallback"

    @pytest.mark.asyncio
    async def test_empty_messages(self, provider) -> None:
        """Calling with an empty message list should still return a response."""
        fake_openai = _mock_openai_module()
        with patch.dict("sys.modules", {"openai": fake_openai}):
            provider._async_client = None
            resp = await provider.chat_completion([])

        assert isinstance(resp, CompletionResponse)


# ---------------------------------------------------------------------------
# Circuit breaker tests
# ---------------------------------------------------------------------------


class TestCircuitBreaker:
    """Tests for the lightweight inline circuit breaker."""

    def test_starts_closed(self) -> None:
        cb = _CircuitBreaker()
        assert cb._state == _CircuitState.CLOSED
        assert cb.allow_request() is True

    def test_opens_after_threshold(self) -> None:
        cb = _CircuitBreaker(failure_threshold=3, recovery_timeout=60)
        for _ in range(3):
            cb.record_failure()
        assert cb._state == _CircuitState.OPEN
        assert cb.allow_request() is False

    def test_success_resets_count(self) -> None:
        cb = _CircuitBreaker(failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        assert cb._failure_count == 0
        assert cb._state == _CircuitState.CLOSED

    def test_half_open_after_timeout(self) -> None:
        cb = _CircuitBreaker(failure_threshold=1, recovery_timeout=0.0)
        cb.record_failure()
        assert cb._state == _CircuitState.OPEN
        # With recovery_timeout=0, it should immediately allow a probe
        assert cb.allow_request() is True
        assert cb._state == _CircuitState.HALF_OPEN


# ---------------------------------------------------------------------------
# Reconfiguration tests
# ---------------------------------------------------------------------------


class TestReconfigure:
    """Tests for hot-reload / reconfigure."""

    def test_reconfigure_updates_key(self, provider) -> None:
        provider.reconfigure(api_key="sk-new-key-999")
        assert provider._config.api_key == "sk-new-key-999"
        assert provider.available is True
        # Cached clients should be cleared
        assert provider._client is None
        assert provider._async_client is None

    def test_reconfigure_with_empty_key_disables(self, provider) -> None:
        provider.reconfigure(api_key="")
        assert provider.available is False

    def test_get_status(self, provider) -> None:
        status = provider.get_status()
        assert status["provider_type"] == "openai"
        assert status["available"] is True
        assert status["circuit_state"] == "closed"
        assert status["has_api_key"] is True


# ---------------------------------------------------------------------------
# Import guard test
# ---------------------------------------------------------------------------


class TestImportGuard:
    """Verify graceful degradation when ``openai`` is not installed."""

    @pytest.mark.asyncio
    async def test_missing_openai_package(self, provider, messages) -> None:
        """If openai is not importable, we should get a fallback response."""
        # Temporarily remove openai from sys.modules and make import fail
        saved = sys.modules.pop("openai", None)
        with patch.dict("sys.modules", {"openai": None}):
            provider._async_client = None
            resp = await provider.chat_completion(messages)

        if saved is not None:
            sys.modules["openai"] = saved

        # Should still return a response (fallback)
        assert isinstance(resp, CompletionResponse)


# ---------------------------------------------------------------------------
# Integration with llm_controller.py (import check)
# ---------------------------------------------------------------------------


class TestLLMControllerIntegration:
    """Verify that llm_controller.py correctly imports the provider."""

    def test_llm_controller_imports_provider(self) -> None:
        """INC-01 signal: llm_controller.py imports openai_compatible_provider."""
        import importlib

        # Force a fresh import
        for mod_name in list(sys.modules):
            if "llm_controller" in mod_name:
                del sys.modules[mod_name]

        spec = importlib.util.find_spec("llm_controller")
        assert spec is not None, "llm_controller module not found on sys.path"

        source_path = spec.origin
        assert source_path is not None
        with open(source_path, "r") as f:
            source = f.read()

        assert "openai_compatible_provider" in source, (
            "llm_controller.py must import openai_compatible_provider (INC-01)"
        )
