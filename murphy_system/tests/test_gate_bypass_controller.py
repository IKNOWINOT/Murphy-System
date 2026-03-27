"""
Tests for GATE-001: GateBypassController.

Validates risk classification, bypass evaluation, outcome feedback,
and safety invariants (CRITICAL/HIGH tasks never bypassed).

Design Label: TEST-001 / GATE-001
Owner: QA Team
"""

import os
import pytest


from gate_bypass_controller import (
    GateBypassController,
    TaskRiskLevel,
    BypassPolicy,
    BypassDecision,
    MINIMAL_RISK_TASK_TYPES,
    LOW_RISK_TASK_TYPES,
)


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def ctrl():
    return GateBypassController()


# ------------------------------------------------------------------
# Risk classification
# ------------------------------------------------------------------

class TestRiskClassification:
    def test_minimal_risk_task_type(self, ctrl):
        assert ctrl.classify_risk("tagline_creation") == TaskRiskLevel.MINIMAL

    def test_low_risk_task_type(self, ctrl):
        assert ctrl.classify_risk("content_generation") == TaskRiskLevel.LOW

    def test_unknown_defaults_to_medium(self, ctrl):
        assert ctrl.classify_risk("unknown_task") == TaskRiskLevel.MEDIUM

    def test_explicit_hint_overrides(self, ctrl):
        assert ctrl.classify_risk("tagline_creation", TaskRiskLevel.CRITICAL) == TaskRiskLevel.CRITICAL


# ------------------------------------------------------------------
# Bypass evaluation
# ------------------------------------------------------------------

class TestBypassEvaluation:
    def test_minimal_risk_bypass_granted_immediately(self, ctrl):
        decision = ctrl.evaluate("tagline_creation")
        assert decision.bypass_granted is True
        assert decision.risk_level == TaskRiskLevel.MINIMAL
        assert decision.require_gates is False

    def test_low_risk_requires_consecutive_successes(self, ctrl):
        decision = ctrl.evaluate("content_generation")
        assert decision.bypass_granted is False
        assert "insufficient_successes" in decision.reason

    def test_low_risk_bypass_after_successes(self, ctrl):
        for _ in range(3):
            ctrl.record_success("content_generation")
        decision = ctrl.evaluate("content_generation")
        assert decision.bypass_granted is True

    def test_medium_risk_never_bypassed(self, ctrl):
        for _ in range(10):
            ctrl.record_success("unknown_task")
        decision = ctrl.evaluate("unknown_task")
        assert decision.bypass_granted is False

    def test_high_risk_never_bypassed(self, ctrl):
        decision = ctrl.evaluate("deploy_production", risk_level=TaskRiskLevel.HIGH)
        assert decision.bypass_granted is False

    def test_critical_risk_never_bypassed(self, ctrl):
        decision = ctrl.evaluate("delete_database", risk_level=TaskRiskLevel.CRITICAL)
        assert decision.bypass_granted is False


# ------------------------------------------------------------------
# Safety invariants
# ------------------------------------------------------------------

class TestSafetyInvariants:
    def test_critical_always_requires_gates(self, ctrl):
        decision = ctrl.evaluate("anything", risk_level=TaskRiskLevel.CRITICAL)
        assert decision.bypass_granted is False
        assert decision.require_gates is True

    def test_high_always_requires_gates(self, ctrl):
        decision = ctrl.evaluate("anything", risk_level=TaskRiskLevel.HIGH)
        assert decision.bypass_granted is False
        assert decision.require_gates is True


# ------------------------------------------------------------------
# Outcome feedback
# ------------------------------------------------------------------

class TestOutcomeFeedback:
    def test_failure_resets_consecutive_counter(self, ctrl):
        for _ in range(3):
            ctrl.record_success("content_generation")
        ctrl.record_failure("content_generation")
        decision = ctrl.evaluate("content_generation")
        assert decision.bypass_granted is False

    def test_success_increments_counter(self, ctrl):
        ctrl.record_success("content_generation")
        status = ctrl.get_status()
        assert status["success_tracker"]["content_generation"] == 1


# ------------------------------------------------------------------
# Max auto-approvals
# ------------------------------------------------------------------

class TestMaxAutoApprovals:
    def test_exhaustion_blocks_bypass(self):
        policy = {
            TaskRiskLevel.MINIMAL: BypassPolicy(
                risk_level=TaskRiskLevel.MINIMAL,
                bypass_allowed=True,
                min_consecutive_successes=0,
                max_auto_approvals=2,
            ),
        }
        ctrl = GateBypassController(policies=policy)
        ctrl.evaluate("tagline_creation")
        ctrl.evaluate("tagline_creation")
        decision = ctrl.evaluate("tagline_creation")
        assert decision.bypass_granted is False
        assert "exhausted" in decision.reason


# ------------------------------------------------------------------
# Decision log
# ------------------------------------------------------------------

class TestDecisionLog:
    def test_log_accumulates(self, ctrl):
        ctrl.evaluate("tagline_creation")
        ctrl.evaluate("content_generation")
        log = ctrl.get_decision_log()
        assert len(log) == 2

    def test_decision_to_dict(self, ctrl):
        decision = ctrl.evaluate("tagline_creation")
        d = decision.to_dict()
        assert d["task_type"] == "tagline_creation"
        assert d["risk_level"] == "minimal"


# ------------------------------------------------------------------
# Status
# ------------------------------------------------------------------

class TestStatus:
    def test_status_includes_policies(self, ctrl):
        status = ctrl.get_status()
        assert "minimal" in status["policies"]
        assert "critical" in status["policies"]
