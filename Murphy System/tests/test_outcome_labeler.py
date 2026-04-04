# Copyright © 2020-2026 Inoni LLC — Created by Corey Post
# License: BSL 1.1
"""
Extended tests for outcome_labeler module.

Covers all label categories, efficiency with various baselines,
safety scoring edge cases, confidence calibration boundaries,
human agreement logic, overall quality bounds, batch labeling,
and label category determination.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from murphy_foundation_model.action_trace_serializer import ActionTrace
from murphy_foundation_model.outcome_labeler import OutcomeLabeler, OutcomeLabels


def _make_trace(**overrides):
    defaults = dict(
        trace_id="t-001",
        timestamp=datetime(2025, 6, 1, 12, 0, 0),
        world_state={"cpu": 42.0},
        intent="test intent",
        constraints=[],
        confidence_at_decision=0.9,
        murphy_index_at_decision=0.1,
        alternatives_considered=[],
        reasoning_chain=["step1"],
        actions_taken=[{"action": "test"}],
        action_types=["API_CALL"],
        outcome_success=True,
        outcome_utility=0.8,
        outcome_details={"detail": "ok"},
    )
    defaults.update(overrides)
    return ActionTrace(**defaults)


class TestLabelCategories:
    """Test all three label categories: positive, partial, negative."""

    def test_positive_requires_success_no_correction(self):
        labeler = OutcomeLabeler()
        trace = _make_trace(outcome_success=True, human_correction=None)
        labels = labeler.label_trace(trace)
        assert labels.label_category == "positive"
        assert labels.success is True

    def test_partial_requires_success_with_correction(self):
        labeler = OutcomeLabeler()
        trace = _make_trace(outcome_success=True, human_correction="adjusted param")
        labels = labeler.label_trace(trace)
        assert labels.label_category == "partial"
        assert labels.success is True

    def test_negative_on_failure_no_correction(self):
        labeler = OutcomeLabeler()
        trace = _make_trace(outcome_success=False, human_correction=None)
        labels = labeler.label_trace(trace)
        assert labels.label_category == "negative"

    def test_negative_on_failure_with_correction(self):
        labeler = OutcomeLabeler()
        trace = _make_trace(outcome_success=False, human_correction="total override")
        labels = labeler.label_trace(trace)
        assert labels.label_category == "negative"

    def test_label_category_is_string(self):
        labeler = OutcomeLabeler()
        for success, corr, expected in [
            (True, None, "positive"),
            (True, "x", "partial"),
            (False, None, "negative"),
        ]:
            labels = labeler.label_trace(
                _make_trace(outcome_success=success, human_correction=corr)
            )
            assert labels.label_category == expected


class TestEfficiencyScoring:
    """Test efficiency with and without baselines for different action types."""

    def test_no_baseline_returns_neutral(self):
        labeler = OutcomeLabeler()
        trace = _make_trace(execution_time_ms=100.0)
        assert labeler.label_trace(trace).efficiency == 0.75

    def test_zero_execution_time_returns_neutral(self):
        labeler = OutcomeLabeler(efficiency_baseline={"API_CALL": 100.0})
        trace = _make_trace(execution_time_ms=0.0)
        assert labeler.label_trace(trace).efficiency == 0.75

    def test_at_baseline_returns_1(self):
        labeler = OutcomeLabeler(efficiency_baseline={"API_CALL": 200.0})
        trace = _make_trace(execution_time_ms=200.0)
        assert labeler.label_trace(trace).efficiency == 1.0

    def test_below_baseline_returns_1(self):
        labeler = OutcomeLabeler(efficiency_baseline={"API_CALL": 200.0})
        trace = _make_trace(execution_time_ms=50.0)
        assert labeler.label_trace(trace).efficiency == 1.0

    def test_at_5x_baseline_returns_0(self):
        labeler = OutcomeLabeler(efficiency_baseline={"API_CALL": 100.0})
        trace = _make_trace(execution_time_ms=500.0)
        assert labeler.label_trace(trace).efficiency == 0.0

    def test_above_5x_baseline_returns_0(self):
        labeler = OutcomeLabeler(efficiency_baseline={"API_CALL": 100.0})
        trace = _make_trace(execution_time_ms=1000.0)
        assert labeler.label_trace(trace).efficiency == 0.0

    def test_midpoint_linear_decay(self):
        labeler = OutcomeLabeler(efficiency_baseline={"API_CALL": 100.0})
        trace = _make_trace(execution_time_ms=300.0)
        # ratio=3.0, efficiency = 1.0 - (3.0-1.0)/4.0 = 0.5
        assert labeler.label_trace(trace).efficiency == pytest.approx(0.5)

    def test_multiple_action_types_sum_baselines(self):
        labeler = OutcomeLabeler(
            efficiency_baseline={"API_CALL": 100.0, "COMMAND": 200.0}
        )
        trace = _make_trace(
            action_types=["API_CALL", "COMMAND"],
            execution_time_ms=300.0,  # at combined baseline
        )
        assert labeler.label_trace(trace).efficiency == 1.0

    def test_unknown_action_type_in_baseline(self):
        labeler = OutcomeLabeler(efficiency_baseline={"COMMAND": 100.0})
        trace = _make_trace(action_types=["API_CALL"], execution_time_ms=50.0)
        # No baseline match → neutral
        assert labeler.label_trace(trace).efficiency == 0.75


class TestSafetyScore:
    """Test safety score with 0, 1, 2+ constraint violations."""

    def test_no_violations(self):
        labeler = OutcomeLabeler()
        trace = _make_trace(outcome_details={"status": "all good"})
        assert labeler.label_trace(trace).safety_score == 1.0

    def test_one_safety_keyword(self):
        labeler = OutcomeLabeler()
        trace = _make_trace(outcome_details={"msg": "gate_blocked by policy"})
        assert labeler.label_trace(trace).safety_score == 0.5

    def test_two_safety_keywords(self):
        labeler = OutcomeLabeler()
        trace = _make_trace(outcome_details={
            "error": "escalation required",
            "action": "rollback performed",
        })
        assert labeler.label_trace(trace).safety_score == 0.0

    def test_three_safety_keywords(self):
        labeler = OutcomeLabeler()
        trace = _make_trace(outcome_details={
            "e1": "safety_violation",
            "e2": "gate_blocked",
            "e3": "override_required",
        })
        assert labeler.label_trace(trace).safety_score == 0.0

    def test_custom_safety_keywords(self):
        labeler = OutcomeLabeler(safety_keywords=frozenset({"critical_error"}))
        trace = _make_trace(outcome_details={"msg": "critical_error in system"})
        assert labeler.label_trace(trace).safety_score == 0.5

    def test_keyword_case_insensitive_in_details_str(self):
        labeler = OutcomeLabeler()
        trace = _make_trace(outcome_details={"msg": "Safety_Violation detected"})
        assert labeler.label_trace(trace).safety_score == 0.5


class TestConfidenceCalibration:
    """Test confidence calibration edge cases."""

    def test_perfect_calibration_success_high_conf(self):
        labeler = OutcomeLabeler()
        trace = _make_trace(outcome_success=True, confidence_at_decision=1.0)
        assert labeler.label_trace(trace).confidence_calibration == pytest.approx(1.0)

    def test_perfect_calibration_failure_zero_conf(self):
        labeler = OutcomeLabeler()
        trace = _make_trace(outcome_success=False, confidence_at_decision=0.0)
        assert labeler.label_trace(trace).confidence_calibration == pytest.approx(1.0)

    def test_worst_calibration_success_zero_conf(self):
        labeler = OutcomeLabeler()
        trace = _make_trace(outcome_success=True, confidence_at_decision=0.0)
        assert labeler.label_trace(trace).confidence_calibration == pytest.approx(0.0)

    def test_worst_calibration_failure_full_conf(self):
        labeler = OutcomeLabeler()
        trace = _make_trace(outcome_success=False, confidence_at_decision=1.0)
        assert labeler.label_trace(trace).confidence_calibration == pytest.approx(0.0)

    def test_midpoint_calibration(self):
        labeler = OutcomeLabeler()
        trace = _make_trace(outcome_success=True, confidence_at_decision=0.5)
        assert labeler.label_trace(trace).confidence_calibration == pytest.approx(0.5)


class TestHumanAgreement:
    """Test human agreement with and without corrections."""

    def test_no_correction_gives_1(self):
        labeler = OutcomeLabeler()
        trace = _make_trace(human_correction=None)
        assert labeler.label_trace(trace).human_agreement == 1.0

    def test_any_correction_gives_half(self):
        labeler = OutcomeLabeler()
        trace = _make_trace(human_correction="minor fix")
        assert labeler.label_trace(trace).human_agreement == 0.5

    def test_empty_string_correction_counts(self):
        labeler = OutcomeLabeler()
        trace = _make_trace(human_correction="")
        # Empty string is falsy → treated as no correction
        assert labeler.label_trace(trace).human_agreement == 1.0


class TestOverallQuality:
    """Test overall quality is within [0, 1] range."""

    def test_best_case_overall_quality(self):
        labeler = OutcomeLabeler()
        trace = _make_trace(
            outcome_success=True,
            confidence_at_decision=1.0,
            human_correction=None,
            outcome_details={},
        )
        labels = labeler.label_trace(trace)
        assert 0.0 <= labels.overall_quality <= 1.0
        # 0.30*1 + 0.20*0.75(neutral) + 0.20*1.0 + 0.15*1.0 + 0.15*1.0 = 0.9
        assert labels.overall_quality == pytest.approx(0.3 + 0.15 + 0.20 + 0.15 + 0.15, abs=0.01)

    def test_worst_case_overall_quality(self):
        labeler = OutcomeLabeler()
        trace = _make_trace(
            outcome_success=False,
            confidence_at_decision=1.0,
            human_correction="full override",
            outcome_details={"error": "safety_violation and rollback"},
        )
        labels = labeler.label_trace(trace)
        assert 0.0 <= labels.overall_quality <= 1.0

    def test_overall_is_weighted_sum(self):
        labeler = OutcomeLabeler()
        trace = _make_trace(
            outcome_success=True,
            confidence_at_decision=0.9,
            human_correction=None,
            outcome_details={},
        )
        labels = labeler.label_trace(trace)
        expected = (
            0.30 * 1.0
            + 0.20 * labels.efficiency
            + 0.20 * labels.safety_score
            + 0.15 * labels.confidence_calibration
            + 0.15 * labels.human_agreement
        )
        assert labels.overall_quality == pytest.approx(expected, abs=0.001)


class TestBatchLabeling:
    """Test batch labeling with mixed trace types."""

    def test_mixed_batch(self):
        labeler = OutcomeLabeler()
        traces = [
            _make_trace(outcome_success=True, human_correction=None),
            _make_trace(outcome_success=True, human_correction="fix"),
            _make_trace(outcome_success=False),
        ]
        all_labels = labeler.label_traces(traces)
        assert len(all_labels) == 3
        categories = [lb.label_category for lb in all_labels]
        assert "positive" in categories
        assert "partial" in categories
        assert "negative" in categories

    def test_empty_batch(self):
        labeler = OutcomeLabeler()
        assert labeler.label_traces([]) == []

    def test_batch_all_same_category(self):
        labeler = OutcomeLabeler()
        traces = [_make_trace(outcome_success=True) for _ in range(5)]
        all_labels = labeler.label_traces(traces)
        assert all(lb.label_category == "positive" for lb in all_labels)
