"""PCR-060i — drill driver regression suite."""
from unittest.mock import patch, MagicMock

import pytest

from src.pcr060_drill_driver import (
    DrillResult,
    IterationRecord,
    drive_boundary_loop,
    f_curve_from_magnify,
    read_iterations,
)


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "drill.db")


# Stub goal plot for deterministic tests
class _StubTrajectoryPoint:
    def __init__(self, t, op, mr, name):
        self.t = t
        self.operational_targets = op
        self.money_ratio_targets = mr
        self.state_name = name


class _StubGoalPlot:
    def __init__(self, points):
        self.r_curve = points


def _good_goal_plot():
    return _StubGoalPlot([
        _StubTrajectoryPoint(0.0, {"resolution_score": 95, "density_index": 80,
                                    "coherence_score": 90, "iqs": 88, "cqi": 92},
                              {}, "goal"),
        _StubTrajectoryPoint(0.5, {"resolution_score": 70, "density_index": 60,
                                    "coherence_score": 70, "iqs": 65, "cqi": 70},
                              {}, "midway"),
        _StubTrajectoryPoint(1.0, {"resolution_score": 50, "density_index": 40,
                                    "coherence_score": 50, "iqs": 45, "cqi": 50},
                              {}, "present"),
    ])


# Mock Magnify responses
def _good_magnify(extra_score: float = 50):
    return {
        "success": True,
        "result": {
            "output": {
                "concept_overview": "An accounting SaaS",
                "industry": "accounting",
                "target_audience": "CPAs",
                "cost_complexity_estimate": "moderate",
            },
            "input_quality": {
                "resolution_score": 50, "density_index": 40,
                "coherence_score": 50, "iqs": 45, "cqi": 50,
            },
            "output_quality": {
                "resolution_score": extra_score, "density_index": extra_score - 10,
                "coherence_score": extra_score, "iqs": extra_score - 5,
                "cqi": extra_score,
            },
        },
    }


# ─────────────────────────────────────────────────────────────────────
# F(t) extraction
# ─────────────────────────────────────────────────────────────────────


class TestFCurveExtraction:
    def test_returns_two_points(self):
        f = f_curve_from_magnify(_good_magnify())
        assert len(f) == 2
        assert f[0]["t"] == 0.0
        assert f[1]["t"] == 1.0

    def test_handles_missing_response(self):
        assert f_curve_from_magnify(None) == []
        assert f_curve_from_magnify({}) == []

    def test_handles_malformed_result(self):
        assert f_curve_from_magnify({"success": True}) == []
        assert f_curve_from_magnify({"result": "not a dict"}) == []

    def test_excludes_categorical_from_state(self):
        # Per design: state vector is QUALITY-ONLY (numeric) for Δ
        # comparison. Categorical deliverable fields go on DrillResult
        # not in the comparison vector.
        f = f_curve_from_magnify(_good_magnify())
        assert "cost_complexity_estimate" not in f[1]["state"]
        assert "industry" not in f[1]["state"]
        assert "target_audience" not in f[1]["state"]
        # But the numeric quality scores ARE in there
        assert "resolution_score" in f[1]["state"]


# ─────────────────────────────────────────────────────────────────────
# Drive loop — convergence path (Q5=success)
# ─────────────────────────────────────────────────────────────────────


class TestDriveLoop:
    def test_converges_when_magnify_matches_goal(self, db_path):
        # If Magnify returns output_quality matching goal scores → Δ=0 → terminate
        with patch("src.pcr060_drill_driver.call_magnify") as mock:
            mock.return_value = _good_magnify(extra_score=95)
            result = drive_boundary_loop(
                "build accounting SaaS",
                goal_plot=_good_goal_plot(),
                db_path=db_path,
                max_iterations=5,
                api_key="test-key",
            )
        assert result.success is True
        assert result.deliverable_quality == "verified"
        assert result.iterations_run == 1
        assert result.deliverable is not None

    def test_runs_full_budget_when_never_converging(self, db_path):
        # Magnify always returns BAD output_quality → Δ stays high → iterate
        with patch("src.pcr060_drill_driver.call_magnify") as mock:
            mock.return_value = _good_magnify(extra_score=20)
            result = drive_boundary_loop(
                "build accounting SaaS",
                goal_plot=_good_goal_plot(),
                db_path=db_path,
                max_iterations=3,
                budget_cap_usd=10.0,  # high cap so iterations exhaust first
                api_key="test-key",
            )
        assert result.iterations_run == 3
        assert result.success is False
        assert result.deliverable_quality == "degraded"

    def test_budget_cap_halts_loop(self, db_path):
        with patch("src.pcr060_drill_driver.call_magnify") as mock:
            mock.return_value = _good_magnify(extra_score=20)
            result = drive_boundary_loop(
                "build accounting SaaS",
                goal_plot=_good_goal_plot(),
                db_path=db_path,
                max_iterations=20,
                budget_cap_usd=0.10,  # only allows 2 calls
                api_key="test-key",
            )
        assert result.deliverable_quality == "budget_exceeded"
        assert result.iterations_run <= 3

    def test_magnify_failure_marks_quality(self, db_path):
        with patch("src.pcr060_drill_driver.call_magnify") as mock:
            mock.return_value = None  # simulate Magnify failure
            result = drive_boundary_loop(
                "build accounting SaaS",
                goal_plot=_good_goal_plot(),
                db_path=db_path,
                max_iterations=2,
                api_key="test-key",
            )
        assert result.success is False
        assert result.deliverable_quality == "magnify_failed"
        assert result.deliverable is None


# ─────────────────────────────────────────────────────────────────────
# Persistence (Q4=β)
# ─────────────────────────────────────────────────────────────────────


class TestPersistence:
    def test_iterations_persist_to_sqlite(self, db_path):
        with patch("src.pcr060_drill_driver.call_magnify") as mock:
            mock.return_value = _good_magnify(extra_score=20)
            result = drive_boundary_loop(
                "test prompt",
                goal_plot=_good_goal_plot(),
                db_path=db_path,
                max_iterations=3,
                budget_cap_usd=10.0,
                api_key="test-key",
            )
        rows = read_iterations(result.dispatch_id, db_path=db_path)
        assert len(rows) == 3
        for i, r in enumerate(rows):
            assert r["iteration"] == i
            assert r["recommendation"] in ("fire", "apnea", "terminate")
            assert r["cumulative_cost_usd"] >= 0
            assert r["dispatch_id"] == result.dispatch_id

    def test_cumulative_cost_increases_monotonically(self, db_path):
        with patch("src.pcr060_drill_driver.call_magnify") as mock:
            mock.return_value = _good_magnify(extra_score=20)
            result = drive_boundary_loop(
                "test", goal_plot=_good_goal_plot(),
                db_path=db_path, max_iterations=3,
                budget_cap_usd=10.0, api_key="test-key",
            )
        costs = [r.cumulative_cost_usd for r in result.iteration_log]
        for i in range(1, len(costs)):
            assert costs[i] >= costs[i-1]


# ─────────────────────────────────────────────────────────────────────
# Detector integration (placeholder for 060i.1)
# ─────────────────────────────────────────────────────────────────────


class TestDetectorIntegration:
    def test_detector_satisfied_terminates_only_if_traj_terminate(self, db_path):
        # Detector says satisfied=True. Trajectory says Δ is high → don't
        # terminate (need both per "success" path).
        class FakeDetectorResult:
            satisfied = True
            weakest_link = None

        with patch("src.pcr060_drill_driver.call_magnify") as mock:
            mock.return_value = _good_magnify(extra_score=20)  # bad quality
            result = drive_boundary_loop(
                "test", goal_plot=_good_goal_plot(),
                db_path=db_path, max_iterations=3,
                boundary_detector=lambda p, r: FakeDetectorResult(),
                budget_cap_usd=10.0, api_key="test-key",
            )
        # Should NOT have succeeded early — Δ is too high
        assert result.iterations_run == 3

    def test_detector_weakest_link_passed_as_scope(self, db_path):
        class FakeDetectorResult:
            satisfied = False
            weakest_link = "unit_economics"

        with patch("src.pcr060_drill_driver.call_magnify") as mock:
            mock.return_value = _good_magnify(extra_score=20)
            drive_boundary_loop(
                "test", goal_plot=_good_goal_plot(),
                db_path=db_path, max_iterations=2,
                boundary_detector=lambda p, r: FakeDetectorResult(),
                budget_cap_usd=10.0, api_key="test-key",
            )
        # Second call should have received scope from weakest_link
        if mock.call_count >= 2:
            second = mock.call_args_list[1]
            # scope kwarg should be the weakest_link
            assert second.kwargs.get("scope") == "unit_economics"
