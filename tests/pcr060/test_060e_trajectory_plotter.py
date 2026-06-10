"""PCR-060e — trajectory plotter regression suite."""
import pytest

from src.pcr060_trajectory_plotter import (
    TrajectoryAnalysis,
    plot_trajectories,
    r_curve_from_goal_plot,
    state_vector_distance,
)


# ─────────────────────────────────────────────────────────────────────
# State-vector distance
# ─────────────────────────────────────────────────────────────────────


class TestStateVectorDistance:
    def test_empty_dicts_are_zero_distance(self):
        assert state_vector_distance({}, {}) == 0.0

    def test_identical_numerics_are_zero(self):
        a = {"revenue": 1000, "headcount": 5}
        assert state_vector_distance(a, a) == 0.0

    def test_double_revenue_is_normalized(self):
        # 1000 vs 2000 → |1000-2000| / max(1000,2000,1) = 0.5
        a = {"revenue": 1000}
        b = {"revenue": 2000}
        assert state_vector_distance(a, b) == pytest.approx(0.5)

    def test_missing_key_is_full_distance_one(self):
        a = {"x": 5, "y": 10}
        b = {"x": 5}
        # y missing in b → +1.0; x match → +0.0; avg = 0.5
        assert state_vector_distance(a, b) == pytest.approx(0.5)

    def test_string_targets_compare_by_equality(self):
        a = {"phase": "scaling"}
        b = {"phase": "scaling"}
        assert state_vector_distance(a, b) == 0.0
        c = {"phase": "build"}
        assert state_vector_distance(a, c) == 1.0

    def test_currency_strings_parse_as_numbers(self):
        a = {"mrr": "$10,000"}
        b = {"mrr": "$20,000"}
        # parses as 10000 vs 20000 → 0.5
        assert state_vector_distance(a, b) == pytest.approx(0.5)


# ─────────────────────────────────────────────────────────────────────
# Plot trajectories — convergence detection
# ─────────────────────────────────────────────────────────────────────


class TestConvergence:
    def test_identical_curves_have_zero_delta(self):
        # F(t) and R(1-t) trivially match at all sampled t
        curve = [
            {"t": 0.0, "state": {"x": 10}},
            {"t": 0.5, "state": {"x": 10}},
            {"t": 1.0, "state": {"x": 10}},
        ]
        result = plot_trajectories(curve, curve, sample_count=3)
        # F(t) compared to R(1-t) — but since all state values are 10,
        # the distance should be 0 at all sample t.
        assert result.delta_at_present == 0.0
        assert result.converged is True
        assert result.recommendation == "terminate"

    def test_diverging_curves_recommend_fire(self):
        # F and R have very different state vectors → high Δ
        f = [
            {"t": 0.0, "state": {"rev": 0}},
            {"t": 1.0, "state": {"rev": 1000}},
        ]
        r = [
            {"t": 0.0, "state": {"rev": 1000000}},
            {"t": 1.0, "state": {"rev": 0}},
        ]
        result = plot_trajectories(f, r, sample_count=3)
        # F(1) is rev=1000, R(0) is rev=1000000 → Δ should be high
        # F(0) is rev=0, R(1) is rev=0 → Δ at t=0 is 0
        # At t=1 (the "present" gauge), F(1)=1000 vs R(0)=1000000 → big delta
        assert result.delta_at_present > 0.5
        assert result.converged is False
        assert result.recommendation == "fire"

    def test_narrowing_iterations_recommend_fire_with_converging_flag(self):
        # Choose curves where F(1) and R(0) are equal — Δ at t=1 is 0
        # Prior delta=0.8 → dΔ/dt = 0 - 0.8 = -0.8 → strongly converging
        f = [{"t": 0.0, "state": {"x": 0}},   {"t": 1.0, "state": {"x": 100}}]
        r = [{"t": 0.0, "state": {"x": 100}}, {"t": 1.0, "state": {"x": 0}}]
        result = plot_trajectories(
            f, r, sample_count=3,
            prior_delta_at_present=0.8, iteration=2,
        )
        assert result.d_delta_dt is not None
        assert result.d_delta_dt < 0  # narrowing (delta_at_present=0, prior=0.8)
        assert result.converging is True

    def test_flatlining_recommends_apnea(self):
        f = [{"t": 0.0, "state": {"x": 50}}, {"t": 1.0, "state": {"x": 50}}]
        r = [{"t": 0.0, "state": {"x": 25}}, {"t": 1.0, "state": {"x": 25}}]
        # Iter N had Δ=0.5; this iter also Δ around 0.5 → flatline
        result = plot_trajectories(
            f, r, sample_count=3,
            prior_delta_at_present=0.5,
            iteration=3, tolerance=0.1, flatline_threshold=0.02,
        )
        # Δ should be ~0.5 (50 vs 25, relative 0.5)
        # |dΔ/dt| should be < flatline_threshold
        assert result.flatlining is True
        assert result.recommendation == "apnea"

    def test_iteration_zero_has_no_d_delta_dt(self):
        f = [{"t": 0.0, "state": {"x": 0}}, {"t": 1.0, "state": {"x": 100}}]
        r = [{"t": 0.0, "state": {"x": 100}}, {"t": 1.0, "state": {"x": 0}}]
        result = plot_trajectories(f, r, sample_count=3, iteration=0)
        assert result.d_delta_dt is None
        # Can't be converging on iteration 0 — no prior comparison
        assert result.converging is False


# ─────────────────────────────────────────────────────────────────────
# Adapter from GoalPlot
# ─────────────────────────────────────────────────────────────────────


class TestGoalPlotAdapter:
    def test_serializes_trajectory_points(self):
        class FakeTP:
            t = 0.5
            state_name = "midpoint"
            operational_targets = {"headcount": 10}
            money_ratio_targets = {"margin": 0.4}

        class FakeGoalPlot:
            r_curve = [FakeTP()]

        result = r_curve_from_goal_plot(FakeGoalPlot())
        assert len(result) == 1
        assert result[0]["t"] == 0.5
        assert result[0]["state_name"] == "midpoint"
        # Combined operational + money_ratio
        assert result[0]["state"] == {"headcount": 10, "margin": 0.4}

    def test_handles_missing_r_curve(self):
        class Empty:
            pass
        assert r_curve_from_goal_plot(Empty()) == []


# ─────────────────────────────────────────────────────────────────────
# Edge cases
# ─────────────────────────────────────────────────────────────────────


class TestEdgeCases:
    def test_empty_curves_return_zero_delta(self):
        result = plot_trajectories([], [], sample_count=3)
        # Empty state dicts → empty key set → distance 0
        assert result.delta_at_present == 0.0
        assert result.converged is True
        assert result.recommendation == "terminate"

    def test_sample_count_below_two_is_clamped(self):
        result = plot_trajectories(
            [{"t": 0.0, "state": {}}, {"t": 1.0, "state": {}}],
            [{"t": 0.0, "state": {}}, {"t": 1.0, "state": {}}],
            sample_count=1,
        )
        assert len(result.sample_ts) == 2  # clamped to 2

    def test_as_dict_contains_all_fields(self):
        result = plot_trajectories(
            [{"t": 0.0, "state": {"x": 1}}],
            [{"t": 0.0, "state": {"x": 1}}],
            sample_count=3,
        )
        d = result.as_dict()
        for key in ("deltas", "sample_ts", "delta_at_present", "d_delta_dt",
                    "converged", "converging", "flatlining",
                    "recommendation", "reason", "iteration",
                    "tolerance", "flatline_threshold"):
            assert key in d
