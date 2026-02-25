"""Tests for the Rubix Evidence Adapter."""

import threading
from unittest.mock import MagicMock

import pytest

from src.rubix_evidence_adapter import (
    EvidenceArtifact,
    EvidenceCheckResult,
    EvidenceType,
    EvidenceVerdict,
    RubixEvidenceAdapter,
)


@pytest.fixture
def adapter():
    return RubixEvidenceAdapter()


# ------------------------------------------------------------------
# Confidence interval
# ------------------------------------------------------------------

class TestConfidenceInterval:
    def test_pass_when_threshold_inside_ci(self, adapter):
        values = [0.4, 0.5, 0.6, 0.5, 0.5]
        result = adapter.check_confidence_interval(values, threshold=0.5)
        assert result.verdict == EvidenceVerdict.PASS
        assert result.evidence_type == EvidenceType.CONFIDENCE_INTERVAL
        assert "ci_lower" in result.details
        assert "ci_upper" in result.details

    def test_fail_when_threshold_outside_ci(self, adapter):
        values = [10.0, 10.1, 10.2, 10.0, 10.1]
        result = adapter.check_confidence_interval(values, threshold=0.5)
        assert result.verdict == EvidenceVerdict.FAIL

    def test_inconclusive_with_insufficient_data(self, adapter):
        result = adapter.check_confidence_interval([1.0], threshold=0.5)
        assert result.verdict == EvidenceVerdict.INCONCLUSIVE


# ------------------------------------------------------------------
# Hypothesis test
# ------------------------------------------------------------------

class TestHypothesisTest:
    def test_pass_significant_difference(self, adapter):
        sample_a = [100.0, 101.0, 102.0, 100.5, 101.5]
        sample_b = [50.0, 51.0, 52.0, 50.5, 51.5]
        result = adapter.check_hypothesis(sample_a, sample_b)
        assert result.verdict == EvidenceVerdict.PASS
        assert result.details["z_stat"] != 0

    def test_fail_insignificant_difference(self, adapter):
        sample_a = [5.0, 5.1, 4.9, 5.0, 5.05]
        sample_b = [5.0, 5.0, 5.0, 5.0, 5.0]
        result = adapter.check_hypothesis(sample_a, sample_b)
        assert result.verdict == EvidenceVerdict.FAIL

    def test_inconclusive_insufficient_data(self, adapter):
        result = adapter.check_hypothesis([1.0], [2.0])
        assert result.verdict == EvidenceVerdict.INCONCLUSIVE


# ------------------------------------------------------------------
# Bayesian update
# ------------------------------------------------------------------

class TestBayesianUpdate:
    def test_pass_high_posterior(self, adapter):
        result = adapter.check_bayesian_update(prior=0.8, likelihood=0.9, evidence=0.7)
        assert result.verdict == EvidenceVerdict.PASS
        expected_posterior = (0.8 * 0.9) / 0.7
        assert abs(result.score - expected_posterior) < 1e-9

    def test_fail_low_posterior(self, adapter):
        result = adapter.check_bayesian_update(prior=0.1, likelihood=0.2, evidence=0.9)
        assert result.verdict == EvidenceVerdict.FAIL
        assert result.score < 0.5

    def test_inconclusive_zero_evidence(self, adapter):
        result = adapter.check_bayesian_update(prior=0.5, likelihood=0.5, evidence=0.0)
        assert result.verdict == EvidenceVerdict.INCONCLUSIVE


# ------------------------------------------------------------------
# Monte Carlo
# ------------------------------------------------------------------

class TestMonteCarlo:
    def test_pass_with_always_true(self, adapter):
        result = adapter.check_monte_carlo(trials=100, success_fn=lambda: True, threshold=0.5)
        assert result.verdict == EvidenceVerdict.PASS
        assert result.details["rate"] == 1.0

    def test_fail_with_always_false(self, adapter):
        result = adapter.check_monte_carlo(trials=100, success_fn=lambda: False, threshold=0.5)
        assert result.verdict == EvidenceVerdict.FAIL
        assert result.details["rate"] == 0.0

    def test_inconclusive_zero_trials(self, adapter):
        result = adapter.check_monte_carlo(trials=0)
        assert result.verdict == EvidenceVerdict.INCONCLUSIVE

    def test_default_fn_runs(self, adapter):
        result = adapter.check_monte_carlo(trials=1000, threshold=0.0)
        assert result.verdict == EvidenceVerdict.PASS


# ------------------------------------------------------------------
# Forecast
# ------------------------------------------------------------------

class TestForecast:
    def test_pass_positive_trend(self, adapter):
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = adapter.check_forecast(values)
        assert result.verdict == EvidenceVerdict.PASS
        assert result.details["slope"] > 0

    def test_fail_negative_trend(self, adapter):
        values = [5.0, 4.0, 3.0, 2.0, 1.0]
        result = adapter.check_forecast(values)
        assert result.verdict == EvidenceVerdict.FAIL
        assert result.details["slope"] < 0

    def test_inconclusive_insufficient_data(self, adapter):
        result = adapter.check_forecast([1.0])
        assert result.verdict == EvidenceVerdict.INCONCLUSIVE

    def test_forecast_value(self, adapter):
        values = [0.0, 1.0, 2.0, 3.0]
        result = adapter.check_forecast(values, periods_ahead=2)
        # slope=1, intercept=0 => forecast = 1*(4+2)+0 = 6
        assert abs(result.details["forecast"] - 6.0) < 1e-9


# ------------------------------------------------------------------
# Evidence battery
# ------------------------------------------------------------------

class TestEvidenceBattery:
    def test_all_pass(self, adapter):
        checks = [
            ("confidence_interval", {"values": [0.5, 0.5, 0.5, 0.5], "threshold": 0.5}),
            ("bayesian_update", {"prior": 0.8, "likelihood": 0.9, "evidence": 0.7}),
        ]
        result = adapter.run_evidence_battery(checks)
        assert result.overall_verdict == EvidenceVerdict.PASS
        assert result.pass_count == 2
        assert result.fail_count == 0

    def test_any_fail_means_overall_fail(self, adapter):
        checks = [
            ("confidence_interval", {"values": [0.5, 0.5, 0.5, 0.5], "threshold": 0.5}),
            ("bayesian_update", {"prior": 0.1, "likelihood": 0.2, "evidence": 0.9}),
        ]
        result = adapter.run_evidence_battery(checks)
        assert result.overall_verdict == EvidenceVerdict.FAIL
        assert result.fail_count >= 1

    def test_inconclusive_only(self, adapter):
        checks = [
            ("confidence_interval", {"values": [1.0], "threshold": 0.5}),
        ]
        result = adapter.run_evidence_battery(checks)
        assert result.overall_verdict == EvidenceVerdict.INCONCLUSIVE

    def test_unknown_check_skipped(self, adapter):
        checks = [("nonexistent_check", {})]
        result = adapter.run_evidence_battery(checks)
        assert len(result.artifacts) == 0

    def test_battery_has_check_id(self, adapter):
        result = adapter.run_evidence_battery([])
        assert result.check_id.startswith("battery-")


# ------------------------------------------------------------------
# History tracking
# ------------------------------------------------------------------

class TestHistory:
    def test_history_records_artifacts(self, adapter):
        adapter.check_bayesian_update(prior=0.8, likelihood=0.9, evidence=0.7)
        adapter.check_forecast([1.0, 2.0, 3.0])
        history = adapter.get_history()
        assert len(history) == 2

    def test_history_most_recent_first(self, adapter):
        adapter.check_bayesian_update(prior=0.8, likelihood=0.9, evidence=0.7)
        adapter.check_forecast([1.0, 2.0, 3.0])
        history = adapter.get_history()
        assert history[0].evidence_type == EvidenceType.FORECAST

    def test_history_limit(self, adapter):
        for _ in range(5):
            adapter.check_bayesian_update(prior=0.8, likelihood=0.9, evidence=0.7)
        history = adapter.get_history(limit=3)
        assert len(history) == 3


# ------------------------------------------------------------------
# Status reporting
# ------------------------------------------------------------------

class TestStatus:
    def test_initial_status(self, adapter):
        status = adapter.get_status()
        assert status["total_checks"] == 0
        assert status["total_artifacts"] == 0

    def test_status_after_checks(self, adapter):
        adapter.check_bayesian_update(prior=0.8, likelihood=0.9, evidence=0.7)
        adapter.check_bayesian_update(prior=0.1, likelihood=0.2, evidence=0.9)
        status = adapter.get_status()
        assert status["total_checks"] == 2
        assert status["total_artifacts"] == 2
        assert status["pass_count"] == 1
        assert status["fail_count"] == 1


# ------------------------------------------------------------------
# Thread safety
# ------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_checks(self, adapter):
        errors = []

        def run_checks():
            try:
                for _ in range(50):
                    adapter.check_bayesian_update(prior=0.8, likelihood=0.9, evidence=0.7)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=run_checks) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        status = adapter.get_status()
        assert status["total_checks"] == 200
        assert status["total_artifacts"] == 200


# ------------------------------------------------------------------
# Artifact structure
# ------------------------------------------------------------------

class TestArtifactStructure:
    def test_artifact_has_required_fields(self, adapter):
        artifact = adapter.check_bayesian_update(prior=0.8, likelihood=0.9, evidence=0.7)
        assert artifact.artifact_id.startswith("ea-")
        assert isinstance(artifact.evidence_type, EvidenceType)
        assert isinstance(artifact.verdict, EvidenceVerdict)
        assert isinstance(artifact.score, float)
        assert isinstance(artifact.details, dict)
        assert artifact.created_at is not None
