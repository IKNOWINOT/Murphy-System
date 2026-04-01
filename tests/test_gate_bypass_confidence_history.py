"""
Tests for Gate Bypass Confidence History (GATE-002).

Covers: trust escalation ladder, per-tool confidence tracking,
auto-bypass decisions, de-escalation, and reset.
"""

from __future__ import annotations

import pytest

from src.gate_bypass_controller import (
    ConfidenceHistoryTracker,
    EscalationThresholds,
    GateBypassController,
    TaskRiskLevel,
    TrustLevel,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tracker():
    return ConfidenceHistoryTracker(
        thresholds=EscalationThresholds(
            low_risk_bypass_after=10,
            medium_risk_bypass_after=50,
            min_success_rate=0.95,
        ),
    )


@pytest.fixture
def controller():
    return GateBypassController()


# ---------------------------------------------------------------------------
# Trust escalation tests
# ---------------------------------------------------------------------------

class TestTrustEscalation:
    def test_new_tool_starts_critical(self, tracker):
        trust = tracker.record_outcome("tool_a", True)
        assert trust.current_bypass_level == TaskRiskLevel.CRITICAL

    def test_escalate_to_low_after_threshold(self, tracker):
        for _ in range(10):
            trust = tracker.record_outcome("tool_a", True)
        assert trust.current_bypass_level == TaskRiskLevel.LOW

    def test_escalate_to_medium_after_threshold(self, tracker):
        for _ in range(50):
            trust = tracker.record_outcome("tool_a", True)
        assert trust.current_bypass_level == TaskRiskLevel.MEDIUM

    def test_failure_resets_consecutive(self, tracker):
        for _ in range(9):
            tracker.record_outcome("tool_a", True)
        tracker.record_outcome("tool_a", False)  # reset
        trust = tracker.record_outcome("tool_a", True)
        assert trust.consecutive_successes == 1
        assert trust.current_bypass_level == TaskRiskLevel.CRITICAL

    def test_de_escalation_on_low_success_rate(self, tracker):
        # First escalate
        for _ in range(10):
            tracker.record_outcome("tool_a", True)
        trust = tracker.get_trust_level("tool_a")
        assert trust.current_bypass_level == TaskRiskLevel.LOW

        # Now fail enough to drop success rate below 0.95
        # 10 successes out of 10 = 100%, need to add failures
        # After 10 success + 1 fail = 10/11 = 90.9% < 95%
        tracker.record_outcome("tool_a", False)
        trust = tracker.get_trust_level("tool_a")
        assert trust.current_bypass_level == TaskRiskLevel.CRITICAL


# ---------------------------------------------------------------------------
# Bypass decision tests
# ---------------------------------------------------------------------------

class TestBypassDecisions:
    def test_should_bypass_unknown_tool(self, tracker):
        assert tracker.should_bypass("unknown", TaskRiskLevel.LOW) is False

    def test_should_bypass_critical_never(self, tracker):
        for _ in range(100):
            tracker.record_outcome("tool_a", True)
        assert tracker.should_bypass("tool_a", TaskRiskLevel.CRITICAL) is False

    def test_should_bypass_low_after_escalation(self, tracker):
        for _ in range(10):
            tracker.record_outcome("tool_a", True)
        assert tracker.should_bypass("tool_a", TaskRiskLevel.LOW) is True

    def test_should_bypass_medium_after_escalation(self, tracker):
        for _ in range(50):
            tracker.record_outcome("tool_a", True)
        assert tracker.should_bypass("tool_a", TaskRiskLevel.MEDIUM) is True

    def test_should_not_bypass_medium_before_threshold(self, tracker):
        for _ in range(10):
            tracker.record_outcome("tool_a", True)
        assert tracker.should_bypass("tool_a", TaskRiskLevel.MEDIUM) is False


# ---------------------------------------------------------------------------
# Introspection tests
# ---------------------------------------------------------------------------

class TestIntrospection:
    def test_get_trust_level(self, tracker):
        tracker.record_outcome("tool_a", True)
        trust = tracker.get_trust_level("tool_a")
        assert trust is not None
        assert trust.total_runs == 1

    def test_get_trust_level_unknown(self, tracker):
        assert tracker.get_trust_level("unknown") is None

    def test_get_bypass_level_unknown(self, tracker):
        assert tracker.get_bypass_level("unknown") == TaskRiskLevel.CRITICAL

    def test_get_all_trust_levels(self, tracker):
        tracker.record_outcome("a", True)
        tracker.record_outcome("b", False)
        levels = tracker.get_all_trust_levels()
        assert len(levels) == 2

    def test_get_escalation_status(self, tracker):
        tracker.record_outcome("a", True)
        status = tracker.get_escalation_status()
        assert status["total_tools_tracked"] == 1
        assert "thresholds" in status

    def test_trust_level_to_dict(self, tracker):
        trust = tracker.record_outcome("tool_a", True)
        d = trust.to_dict()
        assert d["tool_id"] == "tool_a"
        assert d["total_runs"] == 1
        assert "success_rate" in d


# ---------------------------------------------------------------------------
# Reset tests
# ---------------------------------------------------------------------------

class TestReset:
    def test_reset_tool(self, tracker):
        for _ in range(20):
            tracker.record_outcome("tool_a", True)
        tracker.reset_tool("tool_a")
        trust = tracker.get_trust_level("tool_a")
        assert trust.total_runs == 0
        assert trust.current_bypass_level == TaskRiskLevel.CRITICAL

    def test_reset_unknown_tool(self, tracker):
        # Should not raise
        tracker.reset_tool("nonexistent")


# ---------------------------------------------------------------------------
# Existing GateBypassController integration
# ---------------------------------------------------------------------------

class TestGateBypassControllerExisting:
    def test_controller_basic(self, controller):
        decision = controller.evaluate("text_generation")
        assert decision.risk_level == TaskRiskLevel.MINIMAL
        assert decision.bypass_granted is True

    def test_controller_status(self, controller):
        status = controller.get_status()
        assert "policies" in status
        assert "success_tracker" in status

    def test_controller_record_success(self, controller):
        controller.record_success("test_task")
        status = controller.get_status()
        assert status["success_tracker"]["test_task"] == 1

    def test_controller_record_failure(self, controller):
        controller.record_success("test_task")
        controller.record_failure("test_task")
        status = controller.get_status()
        assert status["success_tracker"]["test_task"] == 0
