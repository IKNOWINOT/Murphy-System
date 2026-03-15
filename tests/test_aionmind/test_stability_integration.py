"""
Tests for Layer 3 — StabilityIntegration.
"""

import pytest

from aionmind.stability_integration import (
    StabilityAction,
    StabilityCheckResult,
    StabilityIntegration,
)


class TestStabilityIntegration:

    def test_no_rsc_client_defaults_to_stable(self):
        """Without an RSC client, integration returns score=1.0 (stable)."""
        si = StabilityIntegration()
        result = si.check_stability(context_id="ctx-1", node_id="n-1")
        assert result.stable is True
        assert result.score == 1.0
        assert result.action == StabilityAction.PROCEED

    def test_instability_forces_human_review(self):
        """When score < threshold, the SAFE default is pause + human review."""

        class MockRSC:
            def get_status(self):
                return {"stability_score": 0.3}

        si = StabilityIntegration(stability_threshold=0.5, rsc_client=MockRSC())
        result = si.check_stability(context_id="ctx-1", node_id="n-1")
        assert result.stable is False
        assert result.score == pytest.approx(0.3)
        assert result.action == StabilityAction.REQUIRE_HUMAN_REVIEW

    def test_score_at_threshold_is_stable(self):
        class MockRSC:
            def get_status(self):
                return {"stability_score": 0.5}

        si = StabilityIntegration(stability_threshold=0.5, rsc_client=MockRSC())
        result = si.check_stability()
        assert result.stable is True
        assert result.action == StabilityAction.PROCEED

    def test_score_just_below_threshold(self):
        class MockRSC:
            def get_status(self):
                return {"stability_score": 0.499}

        si = StabilityIntegration(stability_threshold=0.5, rsc_client=MockRSC())
        result = si.check_stability()
        assert result.stable is False
        assert result.action == StabilityAction.REQUIRE_HUMAN_REVIEW

    def test_rsc_exception_defaults_to_stable(self):
        """If RSC query fails, fallback to score=1.0 to avoid false lockout."""

        class BrokenRSC:
            def get_status(self):
                raise RuntimeError("RSC unavailable")

        si = StabilityIntegration(rsc_client=BrokenRSC())
        result = si.check_stability()
        assert result.stable is True
        assert result.score == 1.0

    def test_last_result_is_recorded(self):
        si = StabilityIntegration()
        assert si.last_result is None
        si.check_stability()
        assert si.last_result is not None
        assert isinstance(si.last_result, StabilityCheckResult)
