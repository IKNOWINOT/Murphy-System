"""Tests for the Semantics Boundary Controller."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from src.semantics_boundary_controller import (
    SemanticsBoundaryController,
    BeliefState,
    RiskAssessment,
    ClarifyingQuestion,
    InvarianceCheck,
    VerificationOutcome,
    VerificationOutcomeStatus,
)


@pytest.fixture
def controller():
    return SemanticsBoundaryController()


# ------------------------------------------------------------------
# Belief-state management
# ------------------------------------------------------------------

class TestBeliefStateManagement:
    def test_create_hypothesis_default_prior(self, controller):
        belief = controller.create_hypothesis("test hypothesis")
        assert belief.prior == 0.5
        assert belief.posterior == 0.5
        assert isinstance(belief, BeliefState)

    def test_create_hypothesis_custom_prior(self, controller):
        belief = controller.create_hypothesis("high prior", prior=0.9)
        assert belief.prior == 0.9
        assert belief.posterior == 0.9

    def test_update_belief_positive_evidence(self, controller):
        belief = controller.create_hypothesis("h1", prior=0.5)
        updated = controller.update_belief(belief.hypothesis_id, 2.0, "supporting")
        assert updated.posterior > 0.5
        assert updated.evidence_count == 1

    def test_update_belief_negative_evidence(self, controller):
        belief = controller.create_hypothesis("h1", prior=0.5)
        updated = controller.update_belief(belief.hypothesis_id, 2.0, "opposing")
        assert updated.posterior < 0.5

    def test_update_belief_unknown_hypothesis(self, controller):
        with pytest.raises(KeyError):
            controller.update_belief("nonexistent-id", 1.0, "supporting")

    def test_belief_summary_structure(self, controller):
        controller.create_hypothesis("h1")
        summary = controller.get_belief_summary()
        assert "total_hypotheses" in summary
        assert "hypotheses" in summary
        assert summary["total_hypotheses"] == 1
        hyp = summary["hypotheses"][0]
        for key in ("hypothesis_id", "description", "prior", "posterior", "evidence_count", "confidence"):
            assert key in hyp

    def test_multiple_hypotheses_tracked(self, controller):
        controller.create_hypothesis("h1")
        controller.create_hypothesis("h2")
        controller.create_hypothesis("h3")
        summary = controller.get_belief_summary()
        assert summary["total_hypotheses"] == 3


# ------------------------------------------------------------------
# Risk assessment
# ------------------------------------------------------------------

class TestRiskAssessment:
    def test_compute_expected_loss(self, controller):
        result = controller.compute_expected_loss(
            "s1", probabilities=[0.5, 0.5], losses=[10.0, 20.0],
        )
        assert isinstance(result, RiskAssessment)
        assert abs(result.expected_loss - 15.0) < 1e-9

    def test_compute_expected_loss_empty_inputs(self, controller):
        result = controller.compute_expected_loss("s-empty", [], [])
        assert result.expected_loss == 0.0
        assert result.samples == 0

    def test_compute_cvar_default_alpha(self, controller):
        result = controller.compute_cvar("s2", values=[1.0, 2.0, 3.0, 4.0, 5.0])
        assert isinstance(result, RiskAssessment)
        assert result.samples == 5

    def test_compute_cvar_custom_alpha(self, controller):
        result = controller.compute_cvar("s3", values=[1.0, 2.0, 3.0, 4.0, 5.0], alpha=0.1)
        assert result.cvar_95 > 0.0

    def test_cvar_single_value(self, controller):
        result = controller.compute_cvar("s4", values=[42.0])
        assert result.expected_loss == 42.0

    def test_risk_assessment_fields(self, controller):
        result = controller.compute_expected_loss(
            "s-fields", probabilities=[0.3, 0.7], losses=[5.0, 10.0],
        )
        assert hasattr(result, "scenario_id")
        assert hasattr(result, "expected_loss")
        assert hasattr(result, "cvar_95")
        assert hasattr(result, "cvar_99")
        assert hasattr(result, "samples")
        assert hasattr(result, "timestamp")


# ------------------------------------------------------------------
# Clarifying questions
# ------------------------------------------------------------------

class TestClarifyingQuestions:
    def test_generate_questions_default_count(self, controller):
        controller.create_hypothesis("hypothesis A")
        questions = controller.generate_questions("task description")
        assert len(questions) <= 5
        assert all(isinstance(q, ClarifyingQuestion) for q in questions)

    def test_generate_questions_custom_max(self, controller):
        controller.create_hypothesis("hypothesis B")
        questions = controller.generate_questions("task", max_questions=2)
        assert len(questions) <= 2

    def test_answer_question_updates_state(self, controller):
        controller.create_hypothesis("hypothesis C")
        questions = controller.generate_questions("task")
        assert len(questions) > 0
        answered = controller.answer_question(questions[0].question_id, "the answer")
        assert answered.answered is True
        assert answered.answer == "the answer"

    def test_answer_unknown_question(self, controller):
        with pytest.raises(KeyError):
            controller.answer_question("nonexistent-q", "answer")

    def test_rvoi_rankings_sorted_by_info_gain(self, controller):
        controller.create_hypothesis("h1", prior=0.5)
        controller.create_hypothesis("h2", prior=0.9)
        controller.generate_questions("task", max_questions=10)
        rankings = controller.get_rvoi_rankings()
        gains = [r["estimated_info_gain"] for r in rankings]
        assert gains == sorted(gains, reverse=True)

    def test_answered_questions_excluded_from_rankings(self, controller):
        controller.create_hypothesis("h1")
        questions = controller.generate_questions("task", max_questions=3)
        controller.answer_question(questions[0].question_id, "done")
        rankings = controller.get_rvoi_rankings()
        answered_ids = {questions[0].question_id}
        for r in rankings:
            assert r["question_id"] not in answered_ids


# ------------------------------------------------------------------
# Invariance checks
# ------------------------------------------------------------------

class TestInvarianceChecks:
    def test_register_invariance_check(self, controller):
        check = controller.register_invariance_check("op_a", "op_b")
        assert isinstance(check, InvarianceCheck)
        assert check.operation_a == "op_a"
        assert check.operation_b == "op_b"
        assert check.verified is False

    def test_verify_invariance_commutative(self, controller):
        check = controller.register_invariance_check("add", "add")
        result = controller.verify_invariance(check.check_id, 5.0, 5.0)
        assert result.commutative is True
        assert result.verified is True

    def test_verify_invariance_non_commutative(self, controller):
        check = controller.register_invariance_check("sub", "sub")
        result = controller.verify_invariance(check.check_id, 5.0, 10.0)
        assert result.commutative is False
        assert result.discrepancy == 5.0

    def test_verify_invariance_with_tolerance(self, controller):
        check = controller.register_invariance_check("approx_a", "approx_b")
        result = controller.verify_invariance(check.check_id, 1.0, 1.0000001, tolerance=1e-6)
        assert result.commutative is True

    def test_verify_unknown_check(self, controller):
        with pytest.raises(KeyError):
            controller.verify_invariance("nonexistent-check", 1.0, 2.0)

    def test_multiple_invariance_checks(self, controller):
        c1 = controller.register_invariance_check("a", "b")
        c2 = controller.register_invariance_check("c", "d")
        controller.verify_invariance(c1.check_id, 1.0, 1.0)
        controller.verify_invariance(c2.check_id, 1.0, 2.0)
        status = controller.get_status()
        assert status["total_invariance_checks"] == 2
        assert status["verified_invariance"] == 2
        assert status["commutative_count"] == 1


# ------------------------------------------------------------------
# Verification feedback
# ------------------------------------------------------------------

class TestVerificationFeedback:
    def test_record_verification_pass(self, controller):
        v = controller.record_verification("task-1", "pass", "all good")
        assert isinstance(v, VerificationOutcome)
        assert v.outcome == VerificationOutcomeStatus.PASS

    def test_record_verification_fail(self, controller):
        v = controller.record_verification("task-2", "fail", "something broke")
        assert v.outcome == VerificationOutcomeStatus.FAIL

    def test_record_verification_inconclusive(self, controller):
        v = controller.record_verification("task-3", "inconclusive")
        assert v.outcome == VerificationOutcomeStatus.INCONCLUSIVE

    def test_route_failures_to_planning(self, controller):
        controller.record_verification("task-f1", "fail", "error A")
        controller.record_verification("task-f2", "fail", "error B")
        controller.record_verification("task-p1", "pass")
        routed = controller.route_failures_to_planning()
        assert len(routed) == 2
        assert all("suggestion" in r for r in routed)

    def test_failures_marked_as_routed(self, controller):
        controller.record_verification("task-f", "fail", "err")
        controller.route_failures_to_planning()
        routed_again = controller.route_failures_to_planning()
        assert len(routed_again) == 0

    def test_verification_history_filter_by_task(self, controller):
        controller.record_verification("task-a", "pass")
        controller.record_verification("task-b", "fail")
        controller.record_verification("task-a", "fail")
        history = controller.get_verification_history(task_id="task-a")
        assert len(history) == 2
        assert all(v.task_id == "task-a" for v in history)

    def test_verification_history_all(self, controller):
        controller.record_verification("t1", "pass")
        controller.record_verification("t2", "fail")
        history = controller.get_verification_history()
        assert len(history) == 2


# ------------------------------------------------------------------
# Controller status
# ------------------------------------------------------------------

class TestControllerStatus:
    def test_status_has_all_fields(self, controller):
        status = controller.get_status()
        expected_keys = {
            "total_hypotheses", "total_risk_assessments", "total_questions",
            "answered_questions", "total_invariance_checks", "verified_invariance",
            "commutative_count", "total_verifications", "pass_count", "fail_count",
            "inconclusive_count", "unrouted_failures", "controller_operational",
        }
        assert expected_keys.issubset(status.keys())

    def test_status_counts_update(self, controller):
        controller.create_hypothesis("h")
        controller.record_verification("t", "pass")
        controller.record_verification("t", "fail")
        status = controller.get_status()
        assert status["total_hypotheses"] == 1
        assert status["total_verifications"] == 2
        assert status["pass_count"] == 1
        assert status["fail_count"] == 1

    def test_controller_operational(self, controller):
        status = controller.get_status()
        assert status["controller_operational"] is True
