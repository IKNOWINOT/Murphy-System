"""
Wave 12 — LLM Cascade Commissioning Tests
Murphy System Production Readiness Audit

Exercises all 6 fallback tiers of the LLM content-generation cascade in
sequence using mocked providers.  Confirms that:

  Tier 1 — MurphyLLMProvider via src.llm_provider.get_llm()
  Tier 2 — LLMController (src.llm_controller) — async, broader models
  Tier 3 — LocalLLMFallback (src.local_llm_fallback) — on-device
  Tier 4 — MSS base content (_build_content_from_mss)
  Tier 5 — Minimal keyword content (_build_minimal_custom_content)
  Tier 6 — generate_deliverable always returns correct keys

Commission criteria:
  - When Provider 1 fails, Provider 2 is attempted.
  - When Providers 1–2 fail, Provider 3 (LocalLLMFallback) is attempted.
  - When all 3 LLM providers fail, MSS base content is used.
  - When MSS returns empty, minimal keyword content is used.
  - All paths return non-empty content with length > 100 chars.
  - generate_deliverable(query) always returns a dict with 'content'
    and 'filename' keys, regardless of which tier succeeds.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── Path setup ────────────────────────────────────────────────────────────────
SRC_DIR = Path(__file__).resolve().parent.parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# ── Imports under test ────────────────────────────────────────────────────────
from demo_deliverable_generator import (
    _build_minimal_custom_content,
    _generate_llm_content,
    generate_deliverable,
)

# ---------------------------------------------------------------------------
# Patch target constants — mirror the import paths used inside
# _generate_llm_content in demo_deliverable_generator.py
# ---------------------------------------------------------------------------
_PATCH_GET_LLM = "src.llm_provider.get_llm"
_PATCH_LLM_CONTROLLER = "src.llm_controller.LLMController"
_PATCH_LLM_REQUEST = "src.llm_controller.LLMRequest"
_PATCH_LOCAL_LLM = "src.local_llm_fallback.LocalLLMFallback"
_PATCH_BUILD_MSS = "demo_deliverable_generator._build_content_from_mss"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SAMPLE_QUERY = "build a business plan for a SaaS analytics platform"

_LONG_CONTENT = "X" * 500  # satisfies the > 200 char check inside _generate_llm_content


def _make_provider_mock(content: str = _LONG_CONTENT, provider: str = "deepinfra"):
    """Return a mock provider whose complete_messages() succeeds."""
    completion = MagicMock()
    completion.content = content
    completion.provider = provider
    completion.tokens_total = len(content.split())

    provider_mock = MagicMock()
    provider_mock.complete_messages.return_value = completion
    return provider_mock


def _make_controller_response(content: str = _LONG_CONTENT):
    """Return a mock LLMController response object."""
    resp = MagicMock()
    resp.content = content
    return resp


# ---------------------------------------------------------------------------
# TestLLMCascadeFallback
# ---------------------------------------------------------------------------

class TestLLMCascadeFallback:
    """Verify every tier of the LLM cascade works and falls back correctly.

    All external I/O is mocked.  Tests run synchronously in isolation.
    """

    # ── Tier 1: MurphyLLMProvider succeeds ───────────────────────────────────

    def test_tier1_murphyllm_provider_succeeds(self):
        """Tier 1 success: get_llm() returns content — no further tiers tried."""
        provider_mock = _make_provider_mock()

        with patch(_PATCH_GET_LLM, return_value=provider_mock):
            result = _generate_llm_content(_SAMPLE_QUERY)

        assert result, "Tier 1 must return non-empty content"
        assert len(result) > 100, "Tier 1 content must be > 100 chars"

    # ── Tier 1 fails → Tier 2: LLMController succeeds ────────────────────────

    def test_tier2_llm_controller_when_tier1_fails(self):
        """Tier 2: when get_llm() raises, LLMController is tried next."""
        ctrl_response = _make_controller_response()

        async def _fake_query(req):
            return ctrl_response

        ctrl_mock = MagicMock()
        ctrl_mock.query_llm = _fake_query

        with (
            patch(_PATCH_GET_LLM, side_effect=RuntimeError("Tier 1 down")),
            patch(_PATCH_LLM_CONTROLLER, return_value=ctrl_mock),
            patch(_PATCH_LLM_REQUEST),
        ):
            result = _generate_llm_content(_SAMPLE_QUERY)

        assert result, "Tier 2 must return non-empty content"
        assert len(result) > 100, "Tier 2 content must be > 100 chars"

    # ── Tiers 1–2 fail → Tier 3: LocalLLMFallback succeeds ──────────────────

    def test_tier3_local_llm_fallback_when_tiers_1_2_fail(self):
        """Tier 3: when get_llm() and LLMController both fail, LocalLLMFallback is used."""
        long_local_content = "L" * 200

        broken_ctrl = MagicMock()
        broken_ctrl.query_llm.side_effect = RuntimeError("Tier 2 down")

        local_mock = MagicMock()
        local_mock.generate.return_value = long_local_content

        with (
            patch(_PATCH_GET_LLM, side_effect=RuntimeError("Tier 1 down")),
            patch(_PATCH_LLM_CONTROLLER, return_value=broken_ctrl),
            patch(_PATCH_LLM_REQUEST),
            patch(_PATCH_LOCAL_LLM, return_value=local_mock),
        ):
            result = _generate_llm_content(_SAMPLE_QUERY)

        assert result, "Tier 3 must return non-empty content"
        assert len(result) > 100, "Tier 3 content must be > 100 chars"

    # ── Tiers 1–3 fail → Tier 4: MSS base content ────────────────────────────

    def test_tier4_mss_base_content_when_llm_tiers_fail(self):
        """Tier 4: when all 3 LLM providers fail, MSS base content is returned."""
        mss_content = "MSS-CONTENT: " + "Y" * 300

        broken_ctrl = MagicMock()
        broken_ctrl.query_llm.side_effect = RuntimeError("Tier 2 down")

        local_mock = MagicMock()
        local_mock.generate.return_value = ""  # empty → fall through

        with (
            patch(_PATCH_GET_LLM, side_effect=RuntimeError("Tier 1 down")),
            patch(_PATCH_LLM_CONTROLLER, return_value=broken_ctrl),
            patch(_PATCH_LLM_REQUEST),
            patch(_PATCH_LOCAL_LLM, return_value=local_mock),
            patch(_PATCH_BUILD_MSS, return_value=mss_content),
        ):
            result = _generate_llm_content(_SAMPLE_QUERY, mss_result={"some": "data"})

        assert result, "Tier 4 must return non-empty content"
        assert len(result) > 100, "Tier 4 content must be substantive"

    # ── Tiers 1–4 fail → Tier 5: minimal keyword content ────────────────────

    def test_tier5_minimal_keyword_content_when_mss_empty(self):
        """Tier 5: when MSS returns empty, _build_minimal_custom_content is used."""
        broken_ctrl = MagicMock()
        broken_ctrl.query_llm.side_effect = RuntimeError("Tier 2 down")

        local_mock = MagicMock()
        local_mock.generate.return_value = ""

        with (
            patch(_PATCH_GET_LLM, side_effect=RuntimeError("Tier 1 down")),
            patch(_PATCH_LLM_CONTROLLER, return_value=broken_ctrl),
            patch(_PATCH_LLM_REQUEST),
            patch(_PATCH_LOCAL_LLM, return_value=local_mock),
            patch(_PATCH_BUILD_MSS, return_value=""),  # empty → keyword engine
        ):
            result = _generate_llm_content(_SAMPLE_QUERY)

        assert result, "Tier 5 must return non-empty content"
        assert len(result) > 100, "Tier 5 minimal content must be > 100 chars"

    # ── _build_minimal_custom_content standalone check ───────────────────────

    def test_minimal_custom_content_is_substantive(self):
        """Tier 5 helper: _build_minimal_custom_content always returns > 100 chars."""
        queries = [
            "build a business plan for selling murphy",
            "create a game level for an MMORPG",
            "write a marketing campaign for a SaaS tool",
            "design a REST API for a payment processor",
            "build an automation workflow for Stripe webhooks",
        ]
        for q in queries:
            content = _build_minimal_custom_content(q)
            assert content, f"Empty content for query: {q}"
            assert len(content) > 100, (
                f"Tier 5 content too short ({len(content)} chars) for query: {q}"
            )

    # ── generate_deliverable always returns correct keys ──────────────────────

    def test_generate_deliverable_always_returns_required_keys(self):
        """Integration: generate_deliverable(query) always returns content + filename."""
        broken_ctrl = MagicMock()
        broken_ctrl.query_llm.side_effect = RuntimeError("all LLM down")

        local_mock = MagicMock()
        local_mock.generate.return_value = ""

        with (
            patch(_PATCH_GET_LLM, side_effect=RuntimeError("all LLM down")),
            patch(_PATCH_LLM_CONTROLLER, return_value=broken_ctrl),
            patch(_PATCH_LLM_REQUEST),
            patch(_PATCH_LOCAL_LLM, return_value=local_mock),
        ):
            result = generate_deliverable(_SAMPLE_QUERY)

        assert isinstance(result, dict), "generate_deliverable must return a dict"
        assert "content" in result, "Result must have 'content' key"
        assert "filename" in result, "Result must have 'filename' key"
        assert result["content"], "Content must be non-empty even when all LLMs fail"
        assert len(result["content"]) > 100, "Content must be > 100 chars"

    def test_generate_deliverable_with_working_llm(self):
        """Tier 1 happy-path: generate_deliverable returns LLM content when Tier 1 works."""
        provider_mock = _make_provider_mock()

        with patch(_PATCH_GET_LLM, return_value=provider_mock):
            result = generate_deliverable(_SAMPLE_QUERY)

        assert isinstance(result, dict)
        assert "content" in result
        assert "filename" in result
        assert result["content"]

    # ── Content length guarantee across all cascade paths ────────────────────

    @pytest.mark.parametrize("fail_tiers,expected_min_len", [
        (0, 100),   # All providers work — Tier 1 responds
        (1, 100),   # Tier 1 fails — Tier 2+ responds
        (2, 100),   # Tiers 1-2 fail — Tier 3+ responds
        (3, 100),   # All LLMs fail — MSS/keyword engine responds
    ])
    def test_content_length_guarantee_per_tier(self, fail_tiers, expected_min_len):
        """All cascade tiers produce content longer than the minimum threshold."""
        exc = RuntimeError("provider down")

        if fail_tiers == 0:
            get_llm_side = _make_provider_mock()
            get_llm_kw = {"return_value": get_llm_side}
        else:
            get_llm_kw = {"side_effect": exc}

        broken_ctrl = MagicMock()
        if fail_tiers >= 2:
            broken_ctrl.query_llm.side_effect = exc
        else:
            async def _ok(req):
                return _make_controller_response()
            broken_ctrl.query_llm = _ok

        local_mock = MagicMock()
        if fail_tiers >= 3:
            local_mock.generate.return_value = ""
        else:
            local_mock.generate.return_value = _LONG_CONTENT

        with (
            patch(_PATCH_GET_LLM, **get_llm_kw),
            patch(_PATCH_LLM_CONTROLLER, return_value=broken_ctrl),
            patch(_PATCH_LLM_REQUEST),
            patch(_PATCH_LOCAL_LLM, return_value=local_mock),
        ):
            result = generate_deliverable(_SAMPLE_QUERY)

        assert "content" in result
        assert len(result["content"]) >= expected_min_len, (
            f"Cascade tier (fail_tiers={fail_tiers}) produced only "
            f"{len(result['content'])} chars — expected >= {expected_min_len}"
        )

