"""Tests for the Self-Improvement Engine module."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from src.self_improvement_engine import (
    ExecutionOutcome,
    ImprovementProposal,
    OutcomeType,
    SelfImprovementEngine,
)


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def engine():
    return SelfImprovementEngine()


def _make_outcome(
    task_id="t1",
    session_id="s1",
    outcome=OutcomeType.SUCCESS,
    task_type="deploy",
    duration=1.0,
    confidence=0.9,
    route="deterministic",
    corrections=None,
):
    return ExecutionOutcome(
        task_id=task_id,
        session_id=session_id,
        outcome=outcome,
        metrics={
            "task_type": task_type,
            "duration": duration,
            "confidence": confidence,
            "route": route,
        },
        corrections=corrections,
    )


# ------------------------------------------------------------------
# Outcome recording
# ------------------------------------------------------------------

class TestOutcomeRecording:
    def test_record_single_outcome(self, engine):
        outcome = _make_outcome(task_id="task-1")
        result = engine.record_outcome(outcome)
        assert result == "task-1"
        assert engine.get_status()["total_outcomes"] == 1

    def test_record_multiple_outcomes(self, engine):
        for i in range(5):
            engine.record_outcome(_make_outcome(task_id=f"t-{i}"))
        assert engine.get_status()["total_outcomes"] == 5

    def test_outcome_default_timestamp(self):
        outcome = ExecutionOutcome(
            task_id="t1", session_id="s1", outcome=OutcomeType.SUCCESS
        )
        assert outcome.timestamp is not None

    def test_outcome_custom_timestamp(self):
        outcome = ExecutionOutcome(
            task_id="t1",
            session_id="s1",
            outcome=OutcomeType.SUCCESS,
            timestamp="2024-01-01T00:00:00",
        )
        assert outcome.timestamp == "2024-01-01T00:00:00"


# ------------------------------------------------------------------
# Pattern extraction
# ------------------------------------------------------------------

class TestPatternExtraction:
    def test_no_patterns_on_empty(self, engine):
        patterns = engine.extract_patterns()
        assert patterns == []

    def test_failure_pattern_extracted(self, engine):
        for i in range(3):
            engine.record_outcome(
                _make_outcome(task_id=f"f-{i}", outcome=OutcomeType.FAILURE, task_type="build")
            )
        patterns = engine.extract_patterns()
        failure_pats = [p for p in patterns if p["type"] == "recurring_failure"]
        assert len(failure_pats) == 1
        assert failure_pats[0]["category"] == "build"
        assert failure_pats[0]["occurrences"] == 3

    def test_success_pattern_extracted(self, engine):
        for i in range(3):
            engine.record_outcome(
                _make_outcome(task_id=f"s-{i}", outcome=OutcomeType.SUCCESS, task_type="test", duration=2.5)
            )
        patterns = engine.extract_patterns()
        success_pats = [p for p in patterns if p["type"] == "success_pattern"]
        assert len(success_pats) == 1
        assert success_pats[0]["category"] == "test"
        assert success_pats[0]["avg_duration"] == pytest.approx(2.5)

    def test_timeout_cluster_extracted(self, engine):
        for i in range(2):
            engine.record_outcome(
                _make_outcome(task_id=f"to-{i}", outcome=OutcomeType.TIMEOUT, task_type="fetch")
            )
        patterns = engine.extract_patterns()
        timeout_pats = [p for p in patterns if p["type"] == "timeout_cluster"]
        assert len(timeout_pats) == 1

    def test_single_failure_no_pattern(self, engine):
        engine.record_outcome(_make_outcome(outcome=OutcomeType.FAILURE))
        patterns = engine.extract_patterns()
        failure_pats = [p for p in patterns if p["type"] == "recurring_failure"]
        assert failure_pats == []


# ------------------------------------------------------------------
# Proposal generation
# ------------------------------------------------------------------

class TestProposalGeneration:
    def test_generates_proposal_for_failure_pattern(self, engine):
        for i in range(3):
            engine.record_outcome(
                _make_outcome(task_id=f"f-{i}", outcome=OutcomeType.FAILURE, task_type="deploy")
            )
        proposals = engine.generate_proposals()
        assert len(proposals) >= 1
        deploy_props = [p for p in proposals if p.category == "deploy"]
        assert len(deploy_props) == 1
        assert deploy_props[0].priority in ("critical", "high", "medium")

    def test_critical_priority_for_many_failures(self, engine):
        for i in range(6):
            engine.record_outcome(
                _make_outcome(task_id=f"f-{i}", outcome=OutcomeType.FAILURE, task_type="build")
            )
        proposals = engine.generate_proposals()
        build_props = [p for p in proposals if p.category == "build"]
        assert build_props[0].priority == "critical"

    def test_timeout_proposal_generated(self, engine):
        for i in range(3):
            engine.record_outcome(
                _make_outcome(task_id=f"to-{i}", outcome=OutcomeType.TIMEOUT, task_type="api")
            )
        proposals = engine.generate_proposals()
        timeout_props = [p for p in proposals if p.category == "timeout"]
        assert len(timeout_props) == 1

    def test_success_template_proposal(self, engine):
        for i in range(3):
            engine.record_outcome(
                _make_outcome(task_id=f"s-{i}", outcome=OutcomeType.SUCCESS, task_type="lint", duration=0.5)
            )
        proposals = engine.generate_proposals()
        lint_props = [p for p in proposals if p.category == "lint"]
        assert len(lint_props) == 1
        assert lint_props[0].priority == "low"


# ------------------------------------------------------------------
# Remediation backlog
# ------------------------------------------------------------------

class TestRemediationBacklog:
    def test_backlog_empty_initially(self, engine):
        assert engine.get_remediation_backlog() == []

    def test_backlog_sorted_by_priority(self, engine):
        # Generate a mix of priorities
        for i in range(6):
            engine.record_outcome(
                _make_outcome(task_id=f"f-{i}", outcome=OutcomeType.FAILURE, task_type="deploy")
            )
        for i in range(2):
            engine.record_outcome(
                _make_outcome(task_id=f"g-{i}", outcome=OutcomeType.FAILURE, task_type="test")
            )
        engine.generate_proposals()
        backlog = engine.get_remediation_backlog()
        assert len(backlog) >= 2
        # First item should have higher or equal priority
        priorities = [p.priority for p in backlog]
        from src.self_improvement_engine import PRIORITY_ORDER
        priority_values = [PRIORITY_ORDER.get(p, 99) for p in priorities]
        assert priority_values == sorted(priority_values)

    def test_applied_not_in_backlog(self, engine):
        for i in range(3):
            engine.record_outcome(
                _make_outcome(task_id=f"f-{i}", outcome=OutcomeType.FAILURE, task_type="deploy")
            )
        proposals = engine.generate_proposals()
        pid = proposals[0].proposal_id
        engine.apply_correction(pid, "fixed")
        backlog = engine.get_remediation_backlog()
        ids_in_backlog = [p.proposal_id for p in backlog]
        assert pid not in ids_in_backlog


# ------------------------------------------------------------------
# Correction application
# ------------------------------------------------------------------

class TestCorrectionApplication:
    def test_apply_valid_correction(self, engine):
        for i in range(3):
            engine.record_outcome(
                _make_outcome(task_id=f"f-{i}", outcome=OutcomeType.FAILURE, task_type="deploy")
            )
        proposals = engine.generate_proposals()
        pid = proposals[0].proposal_id
        assert engine.apply_correction(pid, "root cause fixed") is True
        status = engine.get_status()
        assert status["applied_corrections"] == 1

    def test_apply_unknown_proposal(self, engine):
        assert engine.apply_correction("nonexistent", "n/a") is False

    def test_correction_logged(self, engine):
        for i in range(3):
            engine.record_outcome(
                _make_outcome(task_id=f"f-{i}", outcome=OutcomeType.FAILURE, task_type="deploy")
            )
        proposals = engine.generate_proposals()
        engine.apply_correction(proposals[0].proposal_id, "patched")
        status = engine.get_status()
        assert status["corrections_log_size"] == 1


# ------------------------------------------------------------------
# Confidence calibration
# ------------------------------------------------------------------

class TestConfidenceCalibration:
    def test_insufficient_data(self, engine):
        cal = engine.get_confidence_calibration("nonexistent")
        assert cal["sample_size"] == 0
        assert cal["recommendation"] == "insufficient_data"
        assert cal["calibrated_confidence"] == 0.5

    def test_well_calibrated(self, engine):
        # Reported confidence ~0.8, actual success rate ~0.8
        for i in range(8):
            engine.record_outcome(
                _make_outcome(task_id=f"s-{i}", outcome=OutcomeType.SUCCESS, task_type="deploy", confidence=0.8)
            )
        for i in range(2):
            engine.record_outcome(
                _make_outcome(task_id=f"f-{i}", outcome=OutcomeType.FAILURE, task_type="deploy", confidence=0.8)
            )
        cal = engine.get_confidence_calibration("deploy")
        assert cal["sample_size"] == 10
        assert cal["recommendation"] == "maintain"

    def test_overconfident_recommendation(self, engine):
        # High reported confidence, low actual success
        for i in range(2):
            engine.record_outcome(
                _make_outcome(task_id=f"s-{i}", outcome=OutcomeType.SUCCESS, task_type="predict", confidence=0.95)
            )
        for i in range(8):
            engine.record_outcome(
                _make_outcome(task_id=f"f-{i}", outcome=OutcomeType.FAILURE, task_type="predict", confidence=0.95)
            )
        cal = engine.get_confidence_calibration("predict")
        assert cal["recommendation"] == "decrease_confidence"

    def test_underconfident_recommendation(self, engine):
        # Low reported confidence, high actual success
        for i in range(9):
            engine.record_outcome(
                _make_outcome(task_id=f"s-{i}", outcome=OutcomeType.SUCCESS, task_type="lint", confidence=0.3)
            )
        engine.record_outcome(
            _make_outcome(task_id="f-0", outcome=OutcomeType.FAILURE, task_type="lint", confidence=0.3)
        )
        cal = engine.get_confidence_calibration("lint")
        assert cal["recommendation"] == "increase_confidence"


# ------------------------------------------------------------------
# Route optimisation
# ------------------------------------------------------------------

class TestRouteOptimization:
    def test_insufficient_data(self, engine):
        opt = engine.get_route_optimization("nonexistent")
        assert opt["sample_size"] == 0
        assert opt["recommended_route"] == "llm"

    def test_deterministic_recommended(self, engine):
        # Deterministic route succeeds > 80%
        for i in range(9):
            engine.record_outcome(
                _make_outcome(
                    task_id=f"d-{i}", outcome=OutcomeType.SUCCESS,
                    task_type="validate", route="deterministic",
                )
            )
        engine.record_outcome(
            _make_outcome(
                task_id="d-f", outcome=OutcomeType.FAILURE,
                task_type="validate", route="deterministic",
            )
        )
        opt = engine.get_route_optimization("validate")
        assert opt["recommended_route"] == "deterministic"

    def test_llm_recommended_when_better(self, engine):
        # LLM route outperforms deterministic
        for i in range(5):
            engine.record_outcome(
                _make_outcome(
                    task_id=f"l-{i}", outcome=OutcomeType.SUCCESS,
                    task_type="generate", route="llm",
                )
            )
        for i in range(5):
            engine.record_outcome(
                _make_outcome(
                    task_id=f"d-{i}", outcome=OutcomeType.FAILURE,
                    task_type="generate", route="deterministic",
                )
            )
        opt = engine.get_route_optimization("generate")
        assert opt["recommended_route"] == "llm"


# ------------------------------------------------------------------
# Status & learning summary
# ------------------------------------------------------------------

class TestStatusAndSummary:
    def test_empty_status(self, engine):
        status = engine.get_status()
        assert status["total_outcomes"] == 0
        assert status["total_proposals"] == 0

    def test_status_after_activity(self, engine):
        for i in range(3):
            engine.record_outcome(
                _make_outcome(task_id=f"f-{i}", outcome=OutcomeType.FAILURE, task_type="build")
            )
        engine.generate_proposals()
        status = engine.get_status()
        assert status["total_outcomes"] == 3
        assert status["total_proposals"] >= 1
        assert status["pending_proposals"] >= 1

    def test_learning_summary_empty(self, engine):
        summary = engine.get_learning_summary()
        assert summary["total_outcomes"] == 0
        assert summary["feedback_loop_active"] is False

    def test_learning_summary_with_data(self, engine):
        engine.record_outcome(_make_outcome(outcome=OutcomeType.SUCCESS))
        engine.record_outcome(_make_outcome(outcome=OutcomeType.FAILURE, task_id="f-1"))
        summary = engine.get_learning_summary()
        assert summary["total_outcomes"] == 2
        assert summary["outcome_distribution"]["success"] == 1
        assert summary["outcome_distribution"]["failure"] == 1
        assert summary["feedback_loop_active"] is True

    def test_learning_summary_top_failures(self, engine):
        for i in range(4):
            engine.record_outcome(
                _make_outcome(task_id=f"f-{i}", outcome=OutcomeType.FAILURE, task_type="deploy")
            )
        engine.extract_patterns()
        summary = engine.get_learning_summary()
        assert summary["patterns_identified"] >= 1
        assert len(summary["top_failure_patterns"]) >= 1
