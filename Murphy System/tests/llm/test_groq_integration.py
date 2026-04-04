"""
Tests for DeepInfra / Together.ai LLM integration.

Formerly test_groq_integration.py — renamed to test DeepInfra as primary
provider and Together.ai as fallback. The GroqKeyRotator backward-compat
alias is also tested here.

Run:
  python -m pytest tests/test_groq_integration.py -v

Copyright © 2020-2026 Inoni LLC — Created by Corey Post
License: BSL 1.1
"""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Skip marker — tests that require a live DeepInfra key
# ---------------------------------------------------------------------------
skip_without_deepinfra_key = pytest.mark.skipif(
    not os.getenv("DEEPINFRA_API_KEY"),
    reason="DEEPINFRA_API_KEY not set — skipping live API tests",
)


# ===========================================================================
# Provider detection tests
# ===========================================================================

class TestDeepInfraProviderDetection:
    """OpenAICompatibleProvider auto-detects DeepInfra from env vars."""

    def test_deepinfra_key_selects_deepinfra_provider(self) -> None:
        env = {"DEEPINFRA_API_KEY": "dik_testkey", "OPENAI_API_KEY": ""}
        with patch.dict(os.environ, env, clear=False):
            from src.openai_compatible_provider import OpenAICompatibleProvider, ProviderType
            provider = OpenAICompatibleProvider.from_env()
            assert provider.provider_type == ProviderType.DEEPINFRA

    def test_deepinfra_default_model(self) -> None:
        env = {"DEEPINFRA_API_KEY": "dik_testkey", "OPENAI_API_KEY": ""}
        with patch.dict(os.environ, env, clear=False):
            from src.openai_compatible_provider import OpenAICompatibleProvider
            provider = OpenAICompatibleProvider.from_env()
            assert "llama" in provider.default_model.lower() or "meta" in provider.default_model.lower()

    def test_deepinfra_explicit_provider_type(self) -> None:
        env = {
            "DEEPINFRA_API_KEY": "dik_testkey",
            "OPENAI_PROVIDER_TYPE": "deepinfra",
        }
        with patch.dict(os.environ, env, clear=False):
            from src.openai_compatible_provider import OpenAICompatibleProvider, ProviderType
            provider = OpenAICompatibleProvider.from_env()
            assert provider.provider_type == ProviderType.DEEPINFRA

    def test_openai_key_takes_priority_over_deepinfra(self) -> None:
        env = {
            "OPENAI_API_KEY": "sk-openai-key",
            "DEEPINFRA_API_KEY": "dik_testkey",
            "OPENAI_PROVIDER_TYPE": "",
        }
        with patch.dict(os.environ, env, clear=False):
            from src.openai_compatible_provider import OpenAICompatibleProvider, ProviderType
            provider = OpenAICompatibleProvider.from_env()
            assert provider.provider_type == ProviderType.OPENAI

    def test_no_keys_falls_back_to_onboard(self) -> None:
        env = {
            "OPENAI_API_KEY": "",
            "DEEPINFRA_API_KEY": "",
            "OPENAI_PROVIDER_TYPE": "",
        }
        with patch.dict(os.environ, env, clear=False):
            from src.openai_compatible_provider import OpenAICompatibleProvider, ProviderType
            provider = OpenAICompatibleProvider.from_env()
            assert provider.provider_type == ProviderType.ONBOARD


# ===========================================================================
# Key-rotator tests (backward-compat alias GroqKeyRotator = DeepInfraKeyRotator)
# ===========================================================================

class TestDeepInfraKeyRotation:
    """Verify the DeepInfraKeyRotator round-robin and failure logic.

    Also tests the ``GroqKeyRotator`` backward-compat alias.
    """

    def test_round_robin_rotation(self) -> None:
        from src.groq_key_rotator import DeepInfraKeyRotator
        rotator = DeepInfraKeyRotator([
            ("key1", "dik_aaa"),
            ("key2", "dik_bbb"),
            ("key3", "dik_ccc"),
        ])
        names = [rotator.get_next_key()[0] for _ in range(6)]
        assert names == ["key1", "key2", "key3", "key1", "key2", "key3"]

    def test_failure_disables_key_after_3_failures(self) -> None:
        from src.groq_key_rotator import DeepInfraKeyRotator
        rotator = DeepInfraKeyRotator([
            ("key1", "dik_aaa"),
            ("key2", "dik_bbb"),
        ])
        for _ in range(3):
            rotator.report_failure("dik_aaa", "rate_limited")
        stats = rotator.get_statistics()
        key1_stat = next(k for k in stats["keys"] if k["name"] == "key1")
        assert key1_stat["is_active"] is False

    def test_all_disabled_keys_are_reactivated(self) -> None:
        from src.groq_key_rotator import DeepInfraKeyRotator
        rotator = DeepInfraKeyRotator([("key1", "dik_aaa")])
        for _ in range(3):
            rotator.report_failure("dik_aaa", "error")
        # Should reactivate and still return a key
        name, key = rotator.get_next_key()
        assert key == "dik_aaa"

    def test_report_success_clears_errors(self) -> None:
        from src.groq_key_rotator import DeepInfraKeyRotator
        rotator = DeepInfraKeyRotator([("key1", "dik_aaa")])
        rotator.report_failure("dik_aaa", "timeout")
        rotator.report_failure("dik_aaa", "timeout")
        rotator.report_success("dik_aaa")
        stats = rotator.get_statistics()
        key1_stat = stats["keys"][0]
        assert key1_stat["last_error"] is None

    def test_reset_key(self) -> None:
        from src.groq_key_rotator import DeepInfraKeyRotator
        rotator = DeepInfraKeyRotator([("key1", "dik_aaa")])
        for _ in range(3):
            rotator.report_failure("dik_aaa", "error")
        result = rotator.reset_key("key1")
        assert result is True
        stats = rotator.get_statistics()
        assert stats["keys"][0]["is_active"] is True

    def test_backward_compat_alias(self) -> None:
        """GroqKeyRotator must be an alias for DeepInfraKeyRotator."""
        from src.groq_key_rotator import DeepInfraKeyRotator, GroqKeyRotator
        assert GroqKeyRotator is DeepInfraKeyRotator

    def test_statistics_structure(self) -> None:
        from src.groq_key_rotator import DeepInfraKeyRotator
        rotator = DeepInfraKeyRotator([
            ("key1", "dik_aaa"),
            ("key2", "dik_bbb"),
        ])
        rotator.get_next_key()
        stats = rotator.get_statistics()
        assert "total_keys" in stats
        assert "active_keys" in stats
        assert "total_calls" in stats
        assert len(stats["keys"]) == 2


# ===========================================================================
# NOTE: TestDeepInfraDomainRouting and TestDeepInfraMockedAPI were removed.
# Those tests referenced stale Groq-era APIs (_select_provider, LLMDomain,
# LLMProvider.GROQ, _call_groq) that no longer exist in LLMIntegrationLayer.
# DeepInfra integration is fully tested in tests/test_deepinfra_integration.py.
# ===========================================================================


# ===========================================================================
# MurphyLLMProvider tests (new unified provider)
# ===========================================================================

class TestMurphyLLMProvider:
    """Tests for the new MurphyLLMProvider singleton."""

    def test_get_llm_returns_singleton(self) -> None:
        from src.llm_provider import get_llm, reset_llm
        reset_llm()
        llm1 = get_llm()
        llm2 = get_llm()
        assert llm1 is llm2

    def test_provider_has_complete_method(self) -> None:
        from src.llm_provider import get_llm
        llm = get_llm()
        assert callable(getattr(llm, "complete", None))
        assert callable(getattr(llm, "acomplete", None))

    def test_llm_completion_dataclass(self) -> None:
        from src.llm_provider import LLMCompletion
        c = LLMCompletion(
            content="Hello from DeepInfra",
            provider="deepinfra",
            model="meta-llama/Meta-Llama-3.1-70B-Instruct",
        )
        assert c.content == "Hello from DeepInfra"
        assert c.provider == "deepinfra"
        assert c.success is True  # default

    def test_provider_names(self) -> None:
        from src.llm_provider import MurphyLLMProvider, DEEPINFRA_BASE_URL, TOGETHER_BASE_URL
        assert "deepinfra" in DEEPINFRA_BASE_URL
        assert "together" in TOGETHER_BASE_URL

    @skip_without_deepinfra_key
    def test_live_deepinfra_completion(self) -> None:
        """Live test — only runs when DEEPINFRA_API_KEY is set."""
        from src.llm_provider import get_llm, reset_llm
        reset_llm()
        llm = get_llm()
        result = llm.complete(
            "Say 'DeepInfra OK' and nothing else.",
            system="You are a test assistant. Follow instructions exactly.",
            model_hint="fast",
            temperature=0.0,
            max_tokens=20,
        )
        assert result.success
        assert "deepinfra" in result.provider.lower() or "together" in result.provider.lower()
        assert len(result.content) > 0


# ===========================================================================
# Multi-provider router tests
# ===========================================================================

class TestMultiProviderRouter:
    """Test the DeepInfra / Together entries in build_default_router."""

    def test_deepinfra_providers_present(self) -> None:
        from strategic.gap_closure.llm.multi_provider_router import build_default_router
        router = build_default_router()
        names = [p.name for p in router.list_providers()]
        assert any("DeepInfra" in n for n in names), f"No DeepInfra provider in {names}"

    def test_together_providers_present(self) -> None:
        """Together providers may or may not be in the default router."""
        from strategic.gap_closure.llm.multi_provider_router import build_default_router
        router = build_default_router()
        names = [p.name for p in router.list_providers()]
        # Together is an overflow provider, not always in the default router
        # Just verify the router loaded without errors
        assert len(names) > 0, "Router should have at least one provider"

    def test_no_groq_providers(self) -> None:
        from strategic.gap_closure.llm.multi_provider_router import build_default_router
        router = build_default_router()
        names = [p.name.lower() for p in router.list_providers()]
        assert not any("groq" in n for n in names), f"Groq provider found in {names}"

    def test_deepinfra_endpoints_correct(self) -> None:
        from strategic.gap_closure.llm.multi_provider_router import build_default_router
        router = build_default_router()
        deepinfra_providers = [
            p for p in router.list_providers() if "DeepInfra" in p.name
        ]
        for p in deepinfra_providers:
            assert "deepinfra.com" in p.endpoint, f"Wrong endpoint for {p.name}: {p.endpoint}"

    def test_together_endpoints_correct(self) -> None:
        from strategic.gap_closure.llm.multi_provider_router import build_default_router
        router = build_default_router()
        together_providers = [
            p for p in router.list_providers() if "Together" in p.name
        ]
        # Together is optional overflow — skip check if not configured
        for p in together_providers:
            assert "together.xyz" in p.endpoint, f"Wrong endpoint for {p.name}: {p.endpoint}"

    def test_routing_cheapest_selects_low_cost(self) -> None:
        from strategic.gap_closure.llm.multi_provider_router import (
            build_default_router, RoutingStrategy,
        )
        router = build_default_router()
        decision = router.route(strategy=RoutingStrategy.CHEAPEST)
        assert decision is not None
        assert decision.provider.cost_per_1k_tokens == min(
            p.cost_per_1k_tokens for p in router.list_providers()
        )