"""PCR-060i.1 — trajectory adapter + default detector regression suite."""
from unittest.mock import patch, MagicMock

import pytest

from src.pcr060_drill_driver import (
    drive_boundary_loop,
    make_default_detector,
    trajectory_delta_from_analysis,
)
from src.pcr060_trajectory_plotter import TrajectoryAnalysis


# ─────────────────────────────────────────────────────────────────────
# Adapter
# ─────────────────────────────────────────────────────────────────────


class TestTrajectoryDeltaAdapter:
    def test_returns_v2_trajectory_delta(self):
        analysis = TrajectoryAnalysis(
            deltas=[0.5, 0.3, 0.1],
            sample_ts=[0.0, 0.5, 1.0],
            delta_at_present=0.1,
            d_delta_dt=-0.2,
            converged=False,
            converging=True,
            flatlining=False,
            recommendation="fire",
            reason="narrowing",
            iteration=2,
            tolerance=0.10,
        )
        td = trajectory_delta_from_analysis(analysis)
        assert td is not None
        assert td.iteration == 2
        assert td.tolerance == 0.10
        assert td.d_delta_dt == -0.2

    def test_history_threaded_through(self):
        analysis = TrajectoryAnalysis(
            deltas=[0.1], sample_ts=[0.0], delta_at_present=0.1,
            d_delta_dt=-0.05, converged=False, converging=True,
            flatlining=False, recommendation="fire", reason="",
            iteration=3,
        )
        td = trajectory_delta_from_analysis(
            analysis,
            f_history=[0.0, 0.1, 0.2, 0.3],
            r_history=[0.9, 0.7, 0.5, 0.3],
            delta_history=[0.9, 0.6, 0.3, 0.1],
        )
        assert td.f_t == [0.0, 0.1, 0.2, 0.3]
        assert td.r_t == [0.9, 0.7, 0.5, 0.3]
        assert td.delta_t == [0.9, 0.6, 0.3, 0.1]

    def test_no_history_defaults_to_current_delta(self):
        analysis = TrajectoryAnalysis(
            deltas=[], sample_ts=[], delta_at_present=0.5,
            d_delta_dt=None, converged=False, converging=False,
            flatlining=False, recommendation="fire", reason="",
            iteration=0,
        )
        td = trajectory_delta_from_analysis(analysis)
        # When no history is provided, default is just the current delta
        assert td.delta_t == [0.5]


# ─────────────────────────────────────────────────────────────────────
# make_default_detector
# ─────────────────────────────────────────────────────────────────────


class TestDefaultDetector:
    def test_returns_callable(self):
        d = make_default_detector({"name": "test"})
        # Either a callable (if v3 importable) or None (if not)
        assert callable(d) or d is None

    def test_skips_when_response_is_none(self):
        d = make_default_detector({"name": "test"})
        if d is None:
            pytest.skip("v3 detector not importable in this env")
        result = d("prompt", None)
        assert result is None

    def test_passes_trajectory_when_signature_supports(self):
        d = make_default_detector({"name": "test"})
        if d is None:
            pytest.skip("v3 detector not importable")
        # The detector signature exposes trajectory_analysis param
        import inspect
        sig = inspect.signature(d)
        assert "trajectory_analysis" in sig.parameters


# ─────────────────────────────────────────────────────────────────────
# drive_boundary_loop with trajectory-aware detector
# ─────────────────────────────────────────────────────────────────────


def _good_magnify(score=50):
    return {
        "success": True,
        "result": {
            "output": {"concept_overview": "x"},
            "input_quality":  {"resolution_score": 40, "density_index": 40,
                                "coherence_score": 40, "iqs": 40, "cqi": 40},
            "output_quality": {"resolution_score": score, "density_index": score,
                                "coherence_score": score, "iqs": score, "cqi": score},
        },
    }


class _StubTP:
    def __init__(self, t, op, name):
        self.t = t
        self.operational_targets = op
        self.money_ratio_targets = {}
        self.state_name = name


class _StubGP:
    def __init__(self, target=70):
        self.r_curve = [
            _StubTP(0.0, {"resolution_score": target, "density_index": target,
                          "coherence_score": target, "iqs": target, "cqi": target}, "goal"),
            _StubTP(1.0, {"resolution_score": 40, "density_index": 40,
                          "coherence_score": 40, "iqs": 40, "cqi": 40}, "present"),
        ]


class TestDriveWithTrajectoryDetector:
    def test_detector_receives_trajectory_kwarg(self, tmp_path):
        """The custom detector with trajectory_analysis kwarg gets the kwarg."""
        captured = {"calls": []}

        def custom_detector(prompt, magnify_response, *,
                            trajectory_analysis=None,
                            iteration=0, budget_remaining=1.0):
            captured["calls"].append({
                "iteration":          iteration,
                "has_trajectory":     trajectory_analysis is not None,
                "trajectory_iter":    getattr(trajectory_analysis, "iteration", None),
            })
            # Return non-satisfied so loop keeps going
            class Result:
                satisfied = False
                weakest_link = "test_link"
            return Result()

        with patch("src.pcr060_drill_driver.call_magnify") as mock:
            mock.return_value = _good_magnify(40)
            drive_boundary_loop(
                "test", goal_plot=_StubGP(),
                db_path=str(tmp_path / "drill.db"),
                max_iterations=2, budget_cap_usd=10.0,
                boundary_detector=custom_detector,
                api_key="test-key",
            )

        # All calls received the trajectory_analysis kwarg
        assert len(captured["calls"]) == 2
        for call in captured["calls"]:
            assert call["has_trajectory"] is True
            assert call["trajectory_iter"] == call["iteration"]

    def test_legacy_detector_signature_still_works(self, tmp_path):
        """Detectors without trajectory_analysis kwarg still get called the old way."""
        captured = {"calls": 0}

        def legacy_detector(prompt, magnify_response):
            captured["calls"] += 1
            class Result:
                satisfied = False
                weakest_link = None
            return Result()

        with patch("src.pcr060_drill_driver.call_magnify") as mock:
            mock.return_value = _good_magnify(40)
            drive_boundary_loop(
                "test", goal_plot=_StubGP(),
                db_path=str(tmp_path / "drill.db"),
                max_iterations=2, budget_cap_usd=10.0,
                boundary_detector=legacy_detector,
                api_key="test-key",
            )
        assert captured["calls"] == 2  # called twice without crashing
