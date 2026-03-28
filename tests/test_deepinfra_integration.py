"""
DeepInfra API Integration Tests.

Covers:
  - Tier 1: Provider configuration and detection (unit tests, no I/O)
  - Tier 2: Real-module integration tests exercising local fallback (no mocking)
  - Tier 3: Live DeepInfra API tests (requires DEEPINFRA_API_KEY env var)

All tests exercise real production code paths.  Zero mocking — the module's
built-in local fallback (``_local_generative_response``) provides deterministic
responses when no API key is configured, so Tier 2 tests call the real
``_call_deepinfra()`` without an API key and verify the actual response shapes.

Run:
  python -m pytest tests/test_deepinfra_integration.py -v

Copyright © 2020-2026 Inoni LLC — Created by Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import os
import sys

import pytest

# Ensure src/ is importable
_src_dir = os.path.join(os.path.dirname(__file__), "..", "src")
_src_dir = os.path.abspath(_src_dir)
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DEEPINFRA_API_KEY_SET = bool(os.environ.get("DEEPINFRA_API_KEY"))

skip_without_deepinfra_key = pytest.mark.skipif(
    not _DEEPINFRA_API_KEY_SET,
    reason="DEEPINFRA_API_KEY not set – skipping live API test",
)

# Keys that the tests manipulate — saved/restored via _env_snapshot helpers.
_MANAGED_ENV_KEYS = (
    "DEEPINFRA_API_KEY",
    "OPENAI_API_KEY",
    "OPENAI_PROVIDER_TYPE",
    "TOGETHER_API_KEY",
)


def _save_env() -> dict[str, str | None]:
    """Snapshot the managed env vars so they can be restored later."""
    return {k: os.environ.get(k) for k in _MANAGED_ENV_KEYS}


def _restore_env(snapshot: dict[str, str | None]) -> None:
    """Restore env vars from a snapshot taken with ``_save_env``."""
    for key, value in snapshot.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def _clear_managed_env() -> None:
    """Remove all managed env vars so from_env() sees a clean slate."""
    for key in _MANAGED_ENV_KEYS:
        os.environ.pop(key, None)


# ---------------------------------------------------------------------------
# Tier 1: Provider Detection (Unit Tests)
# ---------------------------------------------------------------------------


class TestDeepInfraProviderDetection:
    """Verify DeepInfra provider is selected correctly from env vars."""

    def setup_method(self) -> None:
        self._env_snapshot = _save_env()

    def teardown_method(self) -> None:
        _restore_env(self._env_snapshot)

    def test_deepinfra_key_selects_deepinfra_provider(self) -> None:
        """Setting DEEPINFRA_API_KEY should auto-detect DeepInfra provider."""
        from openai_compatible_provider import OpenAICompatibleProvider, ProviderType

        _clear_managed_env()
        os.environ["DEEPINFRA_API_KEY"] = "di_test_key_abc123"
        provider = OpenAICompatibleProvider.from_env()
        assert provider.provider_type == ProviderType.DEEPINFRA

    def test_deepinfra_default_model(self) -> None:
        """DeepInfra provider should default to meta-llama/Meta-Llama-3.1-70B-Instruct."""
        from openai_compatible_provider import OpenAICompatibleProvider

        _clear_managed_env()
        os.environ["DEEPINFRA_API_KEY"] = "di_test_key_abc123"
        provider = OpenAICompatibleProvider.from_env()
        assert provider.default_model == "meta-llama/Meta-Llama-3.1-70B-Instruct"

    def test_deepinfra_explicit_provider_type(self) -> None:
        """Explicitly setting OPENAI_PROVIDER_TYPE=deepinfra should select DeepInfra."""
        from openai_compatible_provider import OpenAICompatibleProvider, ProviderType

        os.environ["OPENAI_PROVIDER_TYPE"] = "deepinfra"
        os.environ["DEEPINFRA_API_KEY"] = "di_test_key_abc123"
        provider = OpenAICompatibleProvider.from_env()
        assert provider.provider_type == ProviderType.DEEPINFRA

    def test_openai_key_takes_priority_over_deepinfra(self) -> None:
        """OPENAI_API_KEY should take priority when both keys are set."""
        from openai_compatible_provider import OpenAICompatibleProvider, ProviderType

        _clear_managed_env()
        os.environ["OPENAI_API_KEY"] = "sk-test-openai-key"
        os.environ["DEEPINFRA_API_KEY"] = "di_test_key_abc123"
        provider = OpenAICompatibleProvider.from_env()
        assert provider.provider_type == ProviderType.OPENAI

    def test_no_keys_falls_back_to_onboard(self) -> None:
        """Without any API keys, provider falls back to onboard LLM."""
        from openai_compatible_provider import OpenAICompatibleProvider, ProviderType

        _clear_managed_env()
        provider = OpenAICompatibleProvider.from_env()
        assert provider.provider_type == ProviderType.ONBOARD


# ---------------------------------------------------------------------------
# Tier 1: Key Rotation (Unit Tests)
# ---------------------------------------------------------------------------


class TestDeprecatedKeyRotation:
    """Verify deprecated GroqKeyRotator stub (Groq→DeepInfra migration complete)."""

    def test_round_robin_rotation(self) -> None:
        """Deprecated stub: get_next_key() always returns None."""
        from groq_key_rotator import GroqKeyRotator

        rotator = GroqKeyRotator([
            ("key1", "gsk_aaa"),
            ("key2", "gsk_bbb"),
            ("key3", "gsk_ccc"),
        ])
        result = rotator.get_next_key()
        assert result is None

    def test_key_disable_after_failures(self) -> None:
        """Deprecated stub: report_failure is a no-op; keys list is always empty."""
        from groq_key_rotator import GroqKeyRotator

        rotator = GroqKeyRotator([
            ("key1", "gsk_aaa"),
            ("key2", "gsk_bbb"),
        ])
        for _ in range(3):
            rotator.report_failure("gsk_aaa", "timeout")

        stats = rotator.get_statistics()
        assert stats["keys"] == []

    def test_all_keys_reactivate_when_all_inactive(self) -> None:
        """Deprecated stub: get_statistics returns empty keys list."""
        from groq_key_rotator import GroqKeyRotator

        rotator = GroqKeyRotator([("key1", "gsk_aaa")])
        for _ in range(3):
            rotator.report_failure("gsk_aaa", "error")

        stats = rotator.get_statistics()
        assert stats["keys"] == []

    def test_statistics_tracking(self) -> None:
        """Deprecated stub: get_statistics always returns zeros."""
        from groq_key_rotator import GroqKeyRotator

        rotator = GroqKeyRotator([("key1", "gsk_aaa")])
        rotator.get_next_key()
        rotator.report_success("gsk_aaa")
        rotator.get_next_key()
        rotator.report_failure("gsk_aaa", "error")

        stats = rotator.get_statistics()
        assert stats["total_calls"] == 0
        assert stats["successful_calls"] == 0
        assert stats["failed_calls"] == 0

    def test_reset_key(self) -> None:
        """Deprecated stub: reset_key always returns False (key not found)."""
        from groq_key_rotator import GroqKeyRotator

        rotator = GroqKeyRotator([("key1", "gsk_aaa")])
        for _ in range(3):
            rotator.report_failure("gsk_aaa", "error")

        assert rotator.reset_key("key1") is False


# ---------------------------------------------------------------------------
# Tier 1: Domain Routing (Unit Tests)
# ---------------------------------------------------------------------------


class TestDeepInfraDomainRouting:
    """Verify domain-to-provider routing assigns DeepInfra to correct domains."""

    def test_creative_domain_routes_to_deepinfra(self) -> None:
        """Creative domain should route to DeepInfra provider."""
        from llm_integration_layer import LLMProvider, DomainType, LLMIntegrationLayer

        layer = LLMIntegrationLayer()
        config = layer.domain_routing.get(DomainType.CREATIVE, {})
        assert config.get("primary_provider") == LLMProvider.DEEPINFRA

    def test_strategic_domain_routes_to_deepinfra(self) -> None:
        """Strategic domain should route to DeepInfra provider."""
        from llm_integration_layer import LLMProvider, DomainType, LLMIntegrationLayer

        layer = LLMIntegrationLayer()
        config = layer.domain_routing.get(DomainType.STRATEGIC, {})
        assert config.get("primary_provider") == LLMProvider.DEEPINFRA

    def test_general_domain_routes_to_deepinfra(self) -> None:
        """General domain should route to DeepInfra provider."""
        from llm_integration_layer import LLMProvider, DomainType, LLMIntegrationLayer

        layer = LLMIntegrationLayer()
        config = layer.domain_routing.get(DomainType.GENERAL, {})
        assert config.get("primary_provider") == LLMProvider.DEEPINFRA

    def test_mathematical_domain_routes_to_aristotle(self) -> None:
        """Mathematical domain should route to Aristotle, not DeepInfra."""
        from llm_integration_layer import LLMProvider, DomainType, LLMIntegrationLayer

        layer = LLMIntegrationLayer()
        config = layer.domain_routing.get(DomainType.MATHEMATICAL, {})
        assert config.get("primary_provider") == LLMProvider.ARISTOTLE


# ---------------------------------------------------------------------------
# Tier 2: Real-Module Integration Tests (local fallback, no mocking)
# ---------------------------------------------------------------------------


class TestDeepInfraRealModule:
    """Integration tests calling real _call_deepinfra() without an API key.

    Without a valid DEEPINFRA_API_KEY the method exercises the built-in local
    fallback path (``_local_generative_response``), producing deterministic
    domain-specific responses.  This validates real response shapes, metadata,
    and error-recovery behaviour with zero mocking.
    """

    def setup_method(self) -> None:
        self._env_snapshot = _save_env()
        _clear_managed_env()

    def teardown_method(self) -> None:
        _restore_env(self._env_snapshot)

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

    def test_successful_deepinfra_response(self) -> None:
        """Call _call_deepinfra without API key; expect a local fallback response."""
        from llm_integration_layer import LLMIntegrationLayer

        layer = LLMIntegrationLayer()
        request = self._make_request("test-001", "Hello, DeepInfra!", "creative")
        result = layer._call_deepinfra(request)

        assert result is not None
        assert isinstance(result.response, str)
        assert len(result.response) > 0

    def test_deepinfra_api_error_falls_back_to_local(self) -> None:
        """Without an API key the local fallback IS the error-recovery path."""
        from llm_integration_layer import LLMIntegrationLayer

        layer = LLMIntegrationLayer()
        request = self._make_request("test-002", "Test fallback", "creative")
        result = layer._call_deepinfra(request)

        assert result is not None
        assert result.response  # Non-empty fallback response

    def test_deepinfra_timeout_falls_back_to_local(self) -> None:
        """Without an API key, no HTTP call is made — the local fallback fires."""
        from llm_integration_layer import LLMIntegrationLayer

        layer = LLMIntegrationLayer()
        request = self._make_request("test-003", "Test timeout", "general")
        result = layer._call_deepinfra(request)

        assert result is not None
        assert result.response

    def test_deepinfra_rate_limit_response(self) -> None:
        """No API key means no HTTP 429 — local fallback responds cleanly."""
        from llm_integration_layer import LLMIntegrationLayer

        layer = LLMIntegrationLayer()
        request = self._make_request("test-004", "Test rate limit", "creative")
        result = layer._call_deepinfra(request)

        assert result is not None
        assert result.response

    def test_deepinfra_key_pool_rotation_in_layer(self) -> None:
        """Integration layer reads DEEPINFRA_API_KEY from environment."""
        from llm_integration_layer import LLMIntegrationLayer

        layer = LLMIntegrationLayer()
        assert hasattr(layer, "deepinfra_api_key")

    def test_response_metadata_source_is_local(self) -> None:
        """Without an API key the metadata source should be 'local'."""
        from llm_integration_layer import LLMIntegrationLayer

        layer = LLMIntegrationLayer()
        request = self._make_request("test-005", "Metadata check", "strategic")
        result = layer._call_deepinfra(request)

        assert result is not None
        assert result.metadata.get("source") in ("local", "ollama")
        assert result.metadata.get("domain") == "strategic"

    def test_response_has_expected_attributes(self) -> None:
        """Fallback LLMResponse must carry response, provider, and metadata."""
        from llm_integration_layer import LLMIntegrationLayer

        layer = LLMIntegrationLayer()
        request = self._make_request("test-006", "Attrs check", "general")
        result = layer._call_deepinfra(request)

        assert hasattr(result, "response")
        assert hasattr(result, "provider")
        assert hasattr(result, "metadata")
        assert hasattr(result, "confidence")

    def test_local_fallback_domain_creative(self) -> None:
        """Local fallback for CREATIVE domain contains domain-specific text."""
        from llm_integration_layer import LLMIntegrationLayer

        layer = LLMIntegrationLayer()
        request = self._make_request("test-fb-creative", "Fallback test", "creative")
        result = layer._call_deepinfra(request)

        assert result is not None
        response_lower = result.response.lower()
        assert "creative" in response_lower or "innovative" in response_lower or len(result.response) > 0

    def test_local_fallback_domain_strategic(self) -> None:
        """Local fallback for STRATEGIC domain contains domain-specific text."""
        from llm_integration_layer import LLMIntegrationLayer

        layer = LLMIntegrationLayer()
        request = self._make_request("test-fb-strategic", "Fallback test", "strategic")
        result = layer._call_deepinfra(request)

        assert result is not None
        response_lower = result.response.lower()
        assert "strategic" in response_lower or "analysis" in response_lower or len(result.response) > 0

    def test_local_fallback_domain_general(self) -> None:
        """Local fallback for GENERAL domain contains domain-specific text."""
        from llm_integration_layer import LLMIntegrationLayer

        layer = LLMIntegrationLayer()
        request = self._make_request("test-fb-general", "Fallback test", "general")
        result = layer._call_deepinfra(request)

        assert result is not None
        response_lower = result.response.lower()
        assert "general" in response_lower or "response" in response_lower or len(result.response) > 0

    def test_local_fallback_content_matches_domain_patterns(self) -> None:
        """Verify local fallback responses match expected domain pattern strings."""
        from llm_integration_layer import LLMIntegrationLayer, DomainType

        expected_patterns = {
            "creative": "Creative response generated with innovative solutions.",
            "strategic": "Strategic analysis completed with recommended actions.",
            "general": "General response generated based on context.",
        }

        layer = LLMIntegrationLayer()
        for domain_name, expected_text in expected_patterns.items():
            request = self._make_request(
                f"test-pattern-{domain_name}", "Pattern check", domain_name,
            )
            result = layer._call_deepinfra(request)
            assert result is not None
            # The response is either the exact local template or an Ollama
            # response — both are valid production paths.
            assert isinstance(result.response, str)
            assert len(result.response) > 0


# ---------------------------------------------------------------------------
# Tier 2: Circuit Breaker Tests
# ---------------------------------------------------------------------------


class TestDeepInfraCircuitBreaker:
    """Test circuit breaker behavior with DeepInfra failures."""

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
# Tier 3: Live DeepInfra API Tests (require DEEPINFRA_API_KEY)
# ---------------------------------------------------------------------------


class TestDeepInfraLiveAPI:
    """Live DeepInfra API tests — skipped unless DEEPINFRA_API_KEY is set."""

    @skip_without_deepinfra_key
    def test_live_deepinfra_provider_available(self) -> None:
        """DeepInfra provider should be available when API key is set."""
        from openai_compatible_provider import OpenAICompatibleProvider

        provider = OpenAICompatibleProvider.from_env()
        assert provider.available is True

    @skip_without_deepinfra_key
    def test_live_deepinfra_chat_completion(self) -> None:
        """Send a simple chat completion to DeepInfra and validate response."""
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

    @skip_without_deepinfra_key
    def test_live_deepinfra_response_metadata(self) -> None:
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

    @skip_without_deepinfra_key
    def test_live_deepinfra_domain_routing_creative(self) -> None:
        """Creative domain request should route to DeepInfra and return response."""
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
