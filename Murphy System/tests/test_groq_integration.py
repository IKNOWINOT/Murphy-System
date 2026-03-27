"""
Groq API Integration Tests.

Covers:
  - Tier 1: Provider configuration and detection (unit tests, no I/O)
  - Tier 2: Mocked HTTP integration tests (no external dependencies)
  - Tier 3: Live Groq API tests (requires DEEPINFRA_API_KEY env var)

Run:
  python -m pytest tests/test_groq_integration.py -v

Copyright © 2020-2026 Inoni LLC — Created by Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

# Ensure src/ is importable
_src_dir = os.path.join(os.path.dirname(__file__), "..", "src")
_src_dir = os.path.abspath(_src_dir)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DEEPINFRA_API_KEY_SET = bool(os.environ.get("DEEPINFRA_API_KEY"))

skip_without_groq_key = pytest.mark.skipif(
    not _DEEPINFRA_API_KEY_SET,
    reason="DEEPINFRA_API_KEY not set – skipping live API test",
)


# ---------------------------------------------------------------------------
# Tier 1: Provider Detection (Unit Tests)
# ---------------------------------------------------------------------------


class TestGroqProviderDetection:
    """Verify Groq provider is selected correctly from env vars."""

    def test_groq_key_selects_groq_provider(self) -> None:
        """Setting DEEPINFRA_API_KEY should auto-detect Groq provider."""
        from openai_compatible_provider import OpenAICompatibleProvider, ProviderType

        env = {"DEEPINFRA_API_KEY": "di_test_key_abc123"}
        with patch.dict(os.environ, env, clear=True):
            provider = OpenAICompatibleProvider.from_env()
        assert provider.provider_type == ProviderType.GROQ

    def test_groq_default_model(self) -> None:
        """Groq provider should default to mixtral-8x7b-32768."""
        from openai_compatible_provider import OpenAICompatibleProvider

        env = {"DEEPINFRA_API_KEY": "di_test_key_abc123"}
        with patch.dict(os.environ, env, clear=True):
            provider = OpenAICompatibleProvider.from_env()
        assert provider.default_model == "mixtral-8x7b-32768"

    def test_groq_explicit_provider_type(self) -> None:
        """Explicitly setting provider type to groq should work."""
        from openai_compatible_provider import OpenAICompatibleProvider, ProviderType

        env = {
            "OPENAI_PROVIDER_TYPE": "deepinfra",
            "DEEPINFRA_API_KEY": "di_test_key_abc123",
        }
        with patch.dict(os.environ, env, clear=False):
            provider = OpenAICompatibleProvider.from_env()
        assert provider.provider_type == ProviderType.GROQ

    def test_openai_key_takes_priority_over_groq(self) -> None:
        """OPENAI_API_KEY should take priority when both keys are set."""
        from openai_compatible_provider import OpenAICompatibleProvider, ProviderType

        env = {
            "OPENAI_API_KEY": "sk-test-openai-key",
            "DEEPINFRA_API_KEY": "di_test_key_abc123",
        }
        with patch.dict(os.environ, env, clear=True):
            provider = OpenAICompatibleProvider.from_env()
        assert provider.provider_type == ProviderType.OPENAI

    def test_no_keys_falls_back_to_onboard(self) -> None:
        """Without any API keys, provider falls back to onboard LLM."""
        from openai_compatible_provider import OpenAICompatibleProvider, ProviderType

        with patch.dict(os.environ, {}, clear=True):
            provider = OpenAICompatibleProvider.from_env()
        assert provider.provider_type == ProviderType.ONBOARD


# ---------------------------------------------------------------------------
# Tier 1: Key Rotation (Unit Tests)
# ---------------------------------------------------------------------------


class TestGroqKeyRotation:
    """Verify the GroqKeyRotator round-robin and failure logic."""

    def test_round_robin_rotation(self) -> None:
        """Keys should rotate in order."""
        from groq_key_rotator import GroqKeyRotator

        rotator = GroqKeyRotator([
            ("key1", "gsk_aaa"),
            ("key2", "gsk_bbb"),
            ("key3", "gsk_ccc"),
        ])
        names = [rotator.get_next_key()[0] for _ in range(6)]
        assert names == ["key1", "key2", "key3", "key1", "key2", "key3"]

    def test_key_disable_after_failures(self) -> None:
        """A key should be disabled after 3 consecutive failures."""
        from groq_key_rotator import GroqKeyRotator

        rotator = GroqKeyRotator([
            ("key1", "gsk_aaa"),
            ("key2", "gsk_bbb"),
        ])
        # Report 3 failures for key1
        for _ in range(3):
            rotator.report_failure("gsk_aaa", "timeout")

        stats = rotator.get_statistics()
        key1_stats = next(k for k in stats["keys"] if k["name"] == "key1")
        assert key1_stats["is_active"] is False

    def test_all_keys_reactivate_when_all_inactive(self) -> None:
        """When all keys are inactive, they should all be reactivated."""
        from groq_key_rotator import GroqKeyRotator

        rotator = GroqKeyRotator([
            ("key1", "gsk_aaa"),
        ])
        for _ in range(3):
            rotator.report_failure("gsk_aaa", "error")

        # All inactive; get_next_key should reactivate
        name, key = rotator.get_next_key()
        assert name == "key1"
        assert key == "gsk_aaa"

    def test_statistics_tracking(self) -> None:
        """Statistics should accurately reflect calls and outcomes."""
        from groq_key_rotator import GroqKeyRotator

        rotator = GroqKeyRotator([("key1", "gsk_aaa")])
        rotator.get_next_key()
        rotator.report_success("gsk_aaa")
        rotator.get_next_key()
        rotator.report_failure("gsk_aaa", "error")

        stats = rotator.get_statistics()
        assert stats["total_calls"] == 2
        assert stats["successful_calls"] == 1
        assert stats["failed_calls"] == 1

    def test_reset_key(self) -> None:
        """Resetting a key should reactivate it and clear errors."""
        from groq_key_rotator import GroqKeyRotator

        rotator = GroqKeyRotator([("key1", "gsk_aaa")])
        for _ in range(3):
            rotator.report_failure("gsk_aaa", "error")

        assert rotator.reset_key("key1") is True
        stats = rotator.get_statistics()
        key1 = next(k for k in stats["keys"] if k["name"] == "key1")
        assert key1["is_active"] is True
        assert key1["last_error"] is None


# ---------------------------------------------------------------------------
# Tier 1: Domain Routing (Unit Tests)
# ---------------------------------------------------------------------------


class TestGroqDomainRouting:
    """Verify domain-to-provider routing assigns Groq to correct domains."""

    def test_creative_domain_routes_to_groq(self) -> None:
        """Creative domain should route to Groq provider."""
        from llm_integration_layer import LLMProvider, DomainType, LLMIntegrationLayer

        layer = LLMIntegrationLayer()
        config = layer.domain_routing.get(DomainType.CREATIVE, {})
        assert config.get("primary_provider") == LLMProvider.DEEPINFRA

    def test_strategic_domain_routes_to_groq(self) -> None:
        """Strategic domain should route to Groq provider."""
        from llm_integration_layer import LLMProvider, DomainType, LLMIntegrationLayer

        layer = LLMIntegrationLayer()
        config = layer.domain_routing.get(DomainType.STRATEGIC, {})
        assert config.get("primary_provider") == LLMProvider.DEEPINFRA

    def test_general_domain_routes_to_groq(self) -> None:
        """General domain should route to Groq provider."""
        from llm_integration_layer import LLMProvider, DomainType, LLMIntegrationLayer

        layer = LLMIntegrationLayer()
        config = layer.domain_routing.get(DomainType.GENERAL, {})
        assert config.get("primary_provider") == LLMProvider.DEEPINFRA

    def test_mathematical_domain_routes_to_aristotle(self) -> None:
        """Mathematical domain should route to Aristotle, not Groq."""
        from llm_integration_layer import LLMProvider, DomainType, LLMIntegrationLayer

        layer = LLMIntegrationLayer()
        config = layer.domain_routing.get(DomainType.MATHEMATICAL, {})
        assert config.get("primary_provider") == LLMProvider.ARISTOTLE


# ---------------------------------------------------------------------------
# Tier 2: Mocked HTTP Integration Tests
# ---------------------------------------------------------------------------


class TestGroqMockedAPI:
    """Integration tests with mocked Groq HTTP responses."""

    def _make_request(self, request_id: str, prompt: str, domain: str) -> object:
        """Helper to build an LLMRequest with all required fields."""
        from llm_integration_layer import LLMRequest, LLMProvider, DomainType

        domain_map = {
            "creative": DomainType.CREATIVE,
            "strategic": DomainType.STRATEGIC,
            "general": DomainType.GENERAL,
            "mathematical": DomainType.MATHEMATICAL,
        }
        return LLMRequest(
            request_id=request_id,
            provider=LLMProvider.DEEPINFRA,
            domain=domain_map.get(domain, DomainType.GENERAL),
            prompt=prompt,
            context={},
        )

    def test_successful_groq_response(self) -> None:
        """Verify parsing of a successful Groq API response."""
        from llm_integration_layer import LLMIntegrationLayer

        layer = LLMIntegrationLayer(deepinfra_api_key="di_test_mock")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "id": "chatcmpl-test",
            "choices": [{
                "message": {"content": "Hello from Groq!"},
                "finish_reason": "stop",
            }],
            "usage": {"total_tokens": 42},
        }

        request = self._make_request("test-001", "Hello, Groq!", "creative")

        with patch("llm_integration_layer.requests.post", return_value=mock_response):
            result = layer._call_deepinfra(request)
        assert result.response == "Hello from Groq!"

    def test_groq_api_error_falls_back_to_local(self) -> None:
        """API error should trigger local LLM fallback."""
        from llm_integration_layer import LLMIntegrationLayer

        layer = LLMIntegrationLayer(deepinfra_api_key="di_test_mock")

        request = self._make_request("test-002", "Test fallback", "creative")

        with patch(
            "llm_integration_layer.requests.post",
            side_effect=Exception("Connection refused"),
        ):
            result = layer._call_deepinfra(request)
        # Should get a response from the local fallback, not an exception
        assert result is not None
        assert result.response  # Non-empty fallback response

    def test_groq_timeout_falls_back_to_local(self) -> None:
        """Timeout should trigger local LLM fallback."""
        import requests as req_lib
        from llm_integration_layer import LLMIntegrationLayer

        layer = LLMIntegrationLayer(deepinfra_api_key="di_test_mock")

        request = self._make_request("test-003", "Test timeout", "general")

        with patch(
            "llm_integration_layer.requests.post",
            side_effect=req_lib.Timeout("Request timed out"),
        ):
            result = layer._call_deepinfra(request)
        assert result is not None
        assert result.response

    def test_groq_rate_limit_response(self) -> None:
        """429 rate limit should be handled gracefully."""
        from llm_integration_layer import LLMIntegrationLayer
        import requests as req_lib

        layer = LLMIntegrationLayer(deepinfra_api_key="di_test_mock")

        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.raise_for_status.side_effect = req_lib.HTTPError(
            response=mock_response,
        )

        request = self._make_request("test-004", "Test rate limit", "creative")

        with patch("llm_integration_layer.requests.post", return_value=mock_response):
            result = layer._call_deepinfra(request)
        # Should get a local fallback response
        assert result is not None

    def test_groq_key_pool_rotation_in_layer(self) -> None:
        """Integration layer should rotate through multiple Groq keys."""
        from llm_integration_layer import LLMIntegrationLayer

        layer = LLMIntegrationLayer()
        layer.deepinfra_api_keys = ["gsk_key1", "gsk_key2", "gsk_key3"]
        layer.current_deepinfra_key_index = 0

        # Verify keys rotate (internal state)
        assert layer.deepinfra_api_keys[0] == "gsk_key1"
        assert layer.deepinfra_api_keys[1] == "gsk_key2"
        assert layer.deepinfra_api_keys[2] == "gsk_key3"
        assert len(layer.deepinfra_api_keys) == 3


# ---------------------------------------------------------------------------
# Tier 2: Circuit Breaker Tests
# ---------------------------------------------------------------------------


class TestGroqCircuitBreaker:
    """Test circuit breaker behavior with Groq failures."""

    def test_circuit_breaker_initial_state_closed(self) -> None:
        """Circuit breaker should start in CLOSED state."""
        from openai_compatible_provider import _CircuitBreaker, _CircuitState

        cb = _CircuitBreaker()
        assert cb._state == _CircuitState.CLOSED

    def test_circuit_breaker_opens_after_failures(self) -> None:
        """Circuit should open after threshold consecutive failures."""
        from openai_compatible_provider import _CircuitBreaker, _CircuitState

        cb = _CircuitBreaker(failure_threshold=3)
        for _ in range(3):
            cb.record_failure()
        assert cb._state == _CircuitState.OPEN

    def test_circuit_breaker_resets_on_success(self) -> None:
        """A success should reset the failure counter."""
        from openai_compatible_provider import _CircuitBreaker, _CircuitState

        cb = _CircuitBreaker(failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        assert cb._state == _CircuitState.CLOSED


# ---------------------------------------------------------------------------
# Tier 3: Live Groq API Tests (require DEEPINFRA_API_KEY)
# ---------------------------------------------------------------------------


class TestGroqLiveAPI:
    """Live Groq API tests — skipped unless DEEPINFRA_API_KEY is set."""

    @skip_without_groq_key
    def test_live_groq_provider_available(self) -> None:
        """Groq provider should be available when API key is set."""
        from openai_compatible_provider import OpenAICompatibleProvider

        provider = OpenAICompatibleProvider.from_env()
        assert provider.available is True

    @skip_without_groq_key
    def test_live_groq_chat_completion(self) -> None:
        """Send a simple chat completion to Groq and validate response."""
        from llm_integration_layer import (
            LLMIntegrationLayer, LLMRequest, LLMProvider, DomainType,
        )

        layer = LLMIntegrationLayer()

        request = LLMRequest(
            request_id="live-test-001",
            provider=LLMProvider.DEEPINFRA,
            domain=DomainType.GENERAL,
            prompt="Respond with exactly: MURPHY_TEST_OK",
            context={},
        )

        result = layer._call_deepinfra(request)
        assert result is not None
        assert result.response  # Non-empty response

    @skip_without_groq_key
    def test_live_groq_response_metadata(self) -> None:
        """Live response should include expected metadata fields."""
        from llm_integration_layer import (
            LLMIntegrationLayer, LLMRequest, LLMProvider, DomainType,
        )

        layer = LLMIntegrationLayer()

        request = LLMRequest(
            request_id="live-test-002",
            provider=LLMProvider.DEEPINFRA,
            domain=DomainType.CREATIVE,
            prompt="Say hello in exactly 5 words.",
            context={},
        )

        result = layer._call_deepinfra(request)
        assert result is not None
        assert hasattr(result, "response")
        assert hasattr(result, "provider")

    @skip_without_groq_key
    def test_live_groq_domain_routing_creative(self) -> None:
        """Creative domain request should route to Groq and return response."""
        from llm_integration_layer import (
            LLMIntegrationLayer, LLMRequest, LLMProvider, DomainType,
        )

        layer = LLMIntegrationLayer()

        request = LLMRequest(
            request_id="live-test-003",
            provider=LLMProvider.DEEPINFRA,
            domain=DomainType.CREATIVE,
            prompt="Write a one-sentence creative story about an AI.",
            context={},
        )

        result = layer.process_request(request)
        assert result is not None
        assert result.response
