"""
Tests for the Murphy System control-theory formalization modules.

Covers:
  - state_model.py: StateVector creation, dimension addition, covariance tracking
  - observation_model.py: KalmanObserver, information gain, question selection
  - infinity_metric.py: differential entropy, Murphy Index, UncertaintyBudget,
      EntropyTracker, QuestionSelector
  - control_structure.py: ControlVector, ControlLaw (PI), StabilityMonitor,
      AuthorityGate
  - scaling_mechanism.py: DimensionExpander, ConstraintInjector, AuthorityExpander,
      RefinementLoop
  - llm_synthesis_validator.py: Pydantic schemas, OutputValidator, ConflictResolver,
      RegenerationTrigger
  - Integration: full predict → observe → update → control loop
"""

import math
import os
import unittest

import numpy as np


from control_theory.state_model import StateDimension, StateVector, StateEvolution
from control_theory.observation_model import KalmanObserver
from control_theory.infinity_metric import (
    CandidateQuestion,
    EntropyTracker,
    QuestionSelector,
    UncertaintyBudget,
    compute_differential_entropy,
    compute_murphy_index_formal,
)
from control_theory.control_structure import (
    AuthorityGate,
    ControlDimension,
    ControlLaw,
    ControlVector,
    StabilityMonitor,
)
from control_theory.scaling_mechanism import (
    AuthorityExpander,
    ConstraintInjector,
    DimensionExpander,
    InjectedConstraint,
    RefinementLoop,
    RoleNode,
)
from control_theory.llm_synthesis_validator import (
    ConflictKind,
    ConflictResolver,
    GeneratedConstraint,
    GeneratedRole,
    GeneratedStateDimension,
    OutputValidator,
    RegenerationTrigger,
    validate_output,
)


# ===================================================================
# I. STATE MODEL — StateVector, covariance, dimension addition
# ===================================================================

class TestStateVector(unittest.TestCase):
    """state_model.py — formal state vector with covariance."""

    def _make_2d(self) -> StateVector:
        dims = [
            StateDimension("confidence", dtype="float", bounds=(0.0, 1.0)),
            StateDimension("authority", dtype="float", bounds=(0.0, 1.0)),
        ]
        return StateVector(dims, initial_values=[0.7, 0.4])

    def test_creation_and_values(self):
        sv = self._make_2d()
        self.assertEqual(sv.n, 2)
        self.assertAlmostEqual(sv.get_value("confidence"), 0.7)
        self.assertAlmostEqual(sv.get_value("authority"), 0.4)

    def test_default_covariance_is_identity(self):
        sv = self._make_2d()
        np.testing.assert_array_almost_equal(sv.P, np.eye(2))

    def test_get_uncertainty_returns_diagonal(self):
        sv = self._make_2d()
        np.testing.assert_array_equal(sv.get_uncertainty(), np.array([1.0, 1.0]))

    def test_get_variance_named(self):
        sv = self._make_2d()
        self.assertAlmostEqual(sv.get_variance("confidence"), 1.0)

    def test_get_entropy_positive(self):
        sv = self._make_2d()
        self.assertGreater(sv.get_entropy(), 0.0)

    def test_get_entropy_formula(self):
        """H = 0.5 * (n * (1 + ln(2π)) + ln(det(P)))  for P = I_2."""
        sv = self._make_2d()
        n = 2
        expected = 0.5 * (n * (1.0 + math.log(2.0 * math.pi)) + math.log(1.0))
        self.assertAlmostEqual(sv.get_entropy(), expected, places=10)

    def test_predict_increases_covariance(self):
        """predict() adds process noise → P grows."""
        sv = self._make_2d()
        sv_pred = sv.predict()
        # Each diagonal entry should be strictly larger
        for i in range(sv.n):
            self.assertGreater(sv_pred.P[i, i], sv.P[i, i])

    def test_predict_preserves_dimensionality(self):
        sv = self._make_2d()
        sv_pred = sv.predict()
        self.assertEqual(sv.n, sv_pred.n)

    def test_predict_with_control_input(self):
        sv = self._make_2d()
        u = np.array([0.1, -0.1])
        sv_pred = sv.predict(control_input=u)
        # Values should shift by ~u (clamped to bounds)
        self.assertAlmostEqual(sv_pred.get_value("confidence"), 0.8, places=5)
        self.assertAlmostEqual(sv_pred.get_value("authority"), 0.3, places=5)

    def test_predict_clamps_to_bounds(self):
        dims = [StateDimension("x", bounds=(0.0, 1.0))]
        sv = StateVector(dims, initial_values=[0.95])
        u = np.array([0.2])  # would push above 1.0
        sv_pred = sv.predict(control_input=u)
        self.assertLessEqual(sv_pred.get_value("x"), 1.0)

    def test_update_reduces_uncertainty(self):
        """Kalman update should reduce variance for observed dimension."""
        sv = self._make_2d()
        H = np.eye(2)
        R = np.eye(2) * 0.1
        z = np.array([0.75, 0.45])
        sv_upd, innovation = sv.update(z, H, R)
        # Posterior variance should be less than prior variance
        for i in range(sv.n):
            self.assertLess(sv_upd.P[i, i], sv.P[i, i])

    def test_update_returns_innovation(self):
        sv = self._make_2d()
        H = np.eye(2)
        R = np.eye(2) * 0.1
        z = np.array([0.8, 0.5])
        _, innovation = sv.update(z, H, R)
        # innovation = z - H*x = [0.8-0.7, 0.5-0.4] = [0.1, 0.1]
        np.testing.assert_array_almost_equal(innovation, np.array([0.1, 0.1]), decimal=5)

    def test_add_dimension(self):
        sv = self._make_2d()
        new_dim = StateDimension("complexity", bounds=(0.0, 1.0))
        sv3 = sv.add_dimension(new_dim, initial_value=0.5, initial_variance=0.2)
        self.assertEqual(sv3.n, 3)
        self.assertIn("complexity", sv3.dimension_names)
        self.assertAlmostEqual(sv3.get_value("complexity"), 0.5)
        self.assertAlmostEqual(sv3.get_variance("complexity"), 0.2)

    def test_add_dimension_preserves_existing_covariance(self):
        sv = self._make_2d()
        new_dim = StateDimension("extra")
        sv3 = sv.add_dimension(new_dim, initial_value=0.0, initial_variance=1.0)
        # Original 2x2 block should be identical
        np.testing.assert_array_almost_equal(sv3.P[:2, :2], sv.P)
        # Cross-covariances with new dim are zero
        np.testing.assert_array_almost_equal(sv3.P[:2, 2], np.zeros(2))

    def test_to_dict(self):
        sv = self._make_2d()
        d = sv.to_dict()
        self.assertEqual(set(d.keys()), {"confidence", "authority"})
        self.assertAlmostEqual(d["confidence"], 0.7)

    def test_unknown_dimension_raises(self):
        sv = self._make_2d()
        with self.assertRaises(KeyError):
            sv.get_value("nonexistent")

    def test_state_evolution_predict(self):
        se = StateEvolution()
        sv = self._make_2d()
        sv_next = se.predict(sv)
        self.assertEqual(sv_next.n, sv.n)
        # P should have grown: P_next = I P Iᵀ + Q = P + Q
        for i in range(sv.n):
            self.assertGreater(sv_next.P[i, i], sv.P[i, i])

    def test_state_evolution_with_F(self):
        F = np.array([[0.9, 0.0], [0.0, 0.9]])
        se = StateEvolution(F=F)
        dims = [StateDimension("a"), StateDimension("b")]
        sv = StateVector(dims, initial_values=[1.0, 1.0])
        sv_next = se.predict(sv)
        # x_next = F * x = [0.9, 0.9]
        np.testing.assert_array_almost_equal(sv_next.x, [0.9, 0.9])


# ===================================================================
# II. OBSERVATION MODEL — KalmanObserver
# ===================================================================

class TestKalmanObserver(unittest.TestCase):
    """observation_model.py — KalmanObserver with Kalman gain and info gain."""

    def setUp(self):
        self.ko = KalmanObserver()
        self.x = np.array([0.5, 0.3])
        self.P = np.eye(2)
        self.H = np.array([[1.0, 0.0]])
        self.R = np.array([[0.1]])
        self.z = np.array([0.6])

    def test_observe_returns_innovation_and_gain(self):
        innovation, K = self.ko.observe(self.x, self.z, self.H, self.P, self.R)
        # innovation = z - H*x = 0.6 - 0.5 = 0.1
        self.assertAlmostEqual(float(innovation[0]), 0.1, places=10)
        self.assertEqual(K.shape, (2, 1))

    def test_kalman_gain_shape(self):
        _, K = self.ko.observe(self.x, self.z, self.H, self.P, self.R)
        # K ∈ ℝ^{n×m} = ℝ^{2×1}
        self.assertEqual(K.shape, (2, 1))

    def test_information_gain_positive(self):
        ig = self.ko.compute_information_gain(self.P, self.H, self.R)
        self.assertGreater(ig, 0.0)

    def test_information_gain_decreases_with_noise(self):
        """Higher measurement noise → lower information gain."""
        ig_low_noise = self.ko.compute_information_gain(self.P, self.H, np.array([[0.01]]))
        ig_high_noise = self.ko.compute_information_gain(self.P, self.H, np.array([[10.0]]))
        self.assertGreater(ig_low_noise, ig_high_noise)

    def test_select_best_question(self):
        H1 = np.array([[1.0, 0.0]])
        H2 = np.array([[0.0, 1.0]])
        R_small = np.array([[0.01]])
        R_large = np.array([[10.0]])
        # Channel A: observes dim 1 with small noise → high IG
        # Channel B: observes dim 2 with large noise → low IG
        best = self.ko.select_best_question(
            self.P,
            [("channelA", H1, R_small), ("channelB", H2, R_large)],
        )
        self.assertEqual(best, "channelA")

    def test_select_best_question_empty(self):
        self.assertIsNone(self.ko.select_best_question(self.P, []))


# ===================================================================
# III. INFINITY METRIC — entropy, Murphy Index, budget, selector
# ===================================================================

class TestDifferentialEntropy(unittest.TestCase):
    """infinity_metric.py — compute_differential_entropy."""

    def test_identity_matrix(self):
        """For P = I_n, H = 0.5 * n * ln(2πe)."""
        n = 3
        P = np.eye(n)
        h = compute_differential_entropy(P)
        # H = 0.5 * ln((2πe)^n) = 0.5 * n * ln(2πe) = 0.5 * n * (1 + ln(2π))
        expected = 0.5 * n * (1.0 + math.log(2.0 * math.pi))
        self.assertAlmostEqual(h, expected, places=10)

    def test_singular_matrix_returns_zero(self):
        P = np.zeros((2, 2))
        self.assertEqual(compute_differential_entropy(P), 0.0)

    def test_larger_variance_higher_entropy(self):
        P_small = np.eye(2) * 0.1
        P_large = np.eye(2) * 10.0
        self.assertLess(
            compute_differential_entropy(P_small),
            compute_differential_entropy(P_large),
        )

    def test_raises_on_non_square(self):
        with self.assertRaises(ValueError):
            compute_differential_entropy(np.ones((2, 3)))


class TestMurphyIndexFormal(unittest.TestCase):
    """infinity_metric.py — compute_murphy_index_formal."""

    def test_basic_expected_loss(self):
        """M = Σ(L_k * p_k) with no covariance term."""
        lp = [(0.5, 0.4), (1.0, 0.6)]  # E[L] = 0.5*0.4 + 1.0*0.6 = 0.8
        m = compute_murphy_index_formal(lp)
        self.assertAlmostEqual(m, 0.8, places=10)

    def test_covariance_increases_index(self):
        """Adding a positive covariance term increases the Murphy Index."""
        lp = [(0.5, 0.5)]
        m_no_cov = compute_murphy_index_formal(lp)
        m_with_cov = compute_murphy_index_formal(lp, covariance_matrix=np.eye(2))
        self.assertGreater(m_with_cov, m_no_cov)

    def test_zero_entropy_weight_equals_expected_loss(self):
        lp = [(1.0, 1.0)]
        m = compute_murphy_index_formal(lp, covariance_matrix=np.eye(2), entropy_weight=0.0)
        self.assertAlmostEqual(m, 1.0, places=10)


class TestUncertaintyBudget(unittest.TestCase):
    """infinity_metric.py — UncertaintyBudget."""

    def test_set_and_get(self):
        ub = UncertaintyBudget(default_budget=0.1)
        ub.set_budget("confidence", 0.05)
        self.assertAlmostEqual(ub.get_budget("confidence"), 0.05)

    def test_default_budget_for_unknown_dim(self):
        ub = UncertaintyBudget(default_budget=0.2)
        self.assertAlmostEqual(ub.get_budget("unknown_dim"), 0.2)

    def test_over_budget(self):
        ub = UncertaintyBudget()
        ub.set_budget("x", 0.1)
        self.assertTrue(ub.over_budget("x", 0.2))
        self.assertFalse(ub.over_budget("x", 0.05))

    def test_over_budget_dimensions(self):
        ub = UncertaintyBudget(default_budget=0.1)
        ub.set_budget("a", 0.05)
        ub.set_budget("b", 0.2)
        variances = {"a": 0.1, "b": 0.1, "c": 0.5}
        over = ub.over_budget_dimensions(variances)
        self.assertIn("a", over)
        self.assertIn("c", over)
        self.assertNotIn("b", over)

    def test_get_uncertainty_budget_returns_dict(self):
        ub = UncertaintyBudget()
        ub.set_budget("x", 0.1)
        d = ub.get_uncertainty_budget()
        self.assertIn("x", d)


class TestEntropyTracker(unittest.TestCase):
    """infinity_metric.py — EntropyTracker."""

    def test_record_and_history(self):
        tracker = EntropyTracker()
        P = np.eye(2)
        h = tracker.record(P)
        self.assertEqual(len(tracker.history), 1)
        self.assertAlmostEqual(h, tracker.history[0])

    def test_is_non_increasing_monotone(self):
        tracker = EntropyTracker()
        for scale in [1.0, 0.8, 0.6, 0.4]:
            tracker.record(np.eye(2) * scale)
        self.assertTrue(tracker.is_non_increasing())

    def test_is_non_increasing_fails_on_increase(self):
        tracker = EntropyTracker()
        tracker.record(np.eye(2) * 0.1)
        tracker.record(np.eye(2) * 10.0)   # entropy increases
        self.assertFalse(tracker.is_non_increasing())


class TestQuestionSelector(unittest.TestCase):
    """infinity_metric.py — QuestionSelector."""

    def setUp(self):
        self.qs = QuestionSelector()
        self.P = np.eye(3)

    def test_select_from_candidates_list(self):
        q1 = CandidateQuestion("q1", "Q1", expected_H_prior=2.0, expected_H_posterior=1.5)
        q2 = CandidateQuestion("q2", "Q2", expected_H_prior=2.0, expected_H_posterior=0.5)
        best = self.qs.select_best_question([q1, q2])
        self.assertEqual(best.question_id, "q2")

    def test_select_returns_none_on_empty(self):
        self.assertIsNone(self.qs.select_best_question([]))

    def test_information_gain_kalman(self):
        H = np.array([[1.0, 0.0, 0.0]])
        R = np.array([[0.1]])
        ig = self.qs.compute_information_gain_kalman(self.P, H, R)
        self.assertGreater(ig, 0.0)

    def test_select_next_question_picks_highest_ig(self):
        H_good = np.array([[1.0, 0.0, 0.0]])
        H_bad = np.array([[0.0, 0.0, 0.0]])
        R = np.array([[0.1]])
        best = self.qs.select_next_question(
            self.P,
            [("q_good", H_good, R), ("q_bad", H_bad, R)],
        )
        self.assertEqual(best, "q_good")

    def test_select_next_question_empty(self):
        self.assertIsNone(self.qs.select_next_question(self.P, []))


# ===================================================================
# IV. CONTROL STRUCTURE — ControlVector, ControlLaw, Stability, Authority
# ===================================================================

class TestControlVector(unittest.TestCase):
    """control_structure.py — ControlVector with saturation."""

    def _dims(self):
        return [
            ControlDimension("a", lower_limit=-1.0, upper_limit=1.0),
            ControlDimension("b", lower_limit=0.0, upper_limit=0.5),
        ]

    def test_creation(self):
        cv = ControlVector(self._dims(), values=[0.5, 0.3])
        np.testing.assert_array_almost_equal(cv.values, [0.5, 0.3])

    def test_saturation_on_creation(self):
        cv = ControlVector(self._dims(), values=[2.0, -1.0])
        self.assertAlmostEqual(float(cv.values[0]), 1.0)  # clamped to upper
        self.assertAlmostEqual(float(cv.values[1]), 0.0)  # clamped to lower

    def test_scale(self):
        cv = ControlVector(self._dims(), values=[0.4, 0.2])
        cv2 = cv.scale(0.5)
        self.assertAlmostEqual(float(cv2.values[0]), 0.2)
        self.assertAlmostEqual(float(cv2.values[1]), 0.1)

    def test_dimension_names(self):
        cv = ControlVector(self._dims())
        self.assertEqual(cv.dimension_names, ["a", "b"])


class TestControlLaw(unittest.TestCase):
    """control_structure.py — PI ControlLaw."""

    def test_compute_control_proportional(self):
        """With Ki=0, output should be Kp * (ref - state)."""
        law = ControlLaw(Kp=2.0, Ki=0.0)
        state = np.array([0.3, 0.5])
        ref = np.array([0.8, 0.5])
        u, error = law.compute_control(state, ref)
        # error = [0.5, 0.0], u = Kp * error = [1.0, 0.0]
        np.testing.assert_array_almost_equal(u, [1.0, 0.0], decimal=10)
        np.testing.assert_array_almost_equal(error, [0.5, 0.0], decimal=10)

    def test_integral_eliminates_steady_state_error(self):
        """Integral term grows over multiple steps, driving error to zero."""
        law = ControlLaw(Kp=1.0, Ki=0.1)
        state = np.array([0.0])
        ref = np.array([1.0])
        prev_u = np.array([0.0])
        for _ in range(10):
            u, _ = law.compute_control(state, ref)
            self.assertGreaterEqual(float(u[0]), float(prev_u[0]))
            prev_u = u

    def test_reset_integral(self):
        law = ControlLaw(Kp=1.0, Ki=0.5)
        state = np.array([0.0])
        ref = np.array([1.0])
        law.compute_control(state, ref)
        law.reset_integral()
        u_after_reset, _ = law.compute_control(state, ref)
        # After reset: integral initialised to 0 then accumulates one step
        # u = Kp * e + Ki * (e * dt) = 1.0 * 1.0 + 0.5 * 1.0 = 1.5
        self.assertAlmostEqual(float(u_after_reset[0]), 1.5, places=5)

    def test_length_mismatch_raises(self):
        law = ControlLaw()
        with self.assertRaises(ValueError):
            law.compute_control(np.array([1.0]), np.array([1.0, 2.0]))


class TestStabilityMonitor(unittest.TestCase):
    """control_structure.py — StabilityMonitor with Lyapunov condition."""

    def test_stable_trajectory(self):
        eq = np.array([1.0, 1.0])
        monitor = StabilityMonitor(equilibrium=eq)
        traj = [
            np.array([0.5, 0.5]),
            np.array([0.6, 0.6]),
            np.array([0.75, 0.75]),
            np.array([0.9, 0.9]),
        ]
        result = monitor.check_stability(traj)
        self.assertTrue(result.is_stable)
        self.assertLess(result.convergence_rate, 0.0)
        self.assertEqual(result.violations, 0)

    def test_unstable_trajectory(self):
        eq = np.array([0.0, 0.0])
        monitor = StabilityMonitor(equilibrium=eq)
        traj = [
            np.array([0.1, 0.1]),
            np.array([0.3, 0.3]),   # V increases — unstable step
        ]
        result = monitor.check_stability(traj)
        self.assertFalse(result.is_stable)
        self.assertGreater(result.violations, 0)

    def test_lyapunov_at_equilibrium_is_zero(self):
        eq = np.array([0.5, 0.5])
        monitor = StabilityMonitor(equilibrium=eq)
        self.assertAlmostEqual(monitor.lyapunov(eq), 0.0)

    def test_single_point_is_trivially_stable(self):
        monitor = StabilityMonitor(equilibrium=np.array([0.0]))
        result = monitor.check_stability([np.array([0.5])])
        self.assertTrue(result.is_stable)


class TestAuthorityGate(unittest.TestCase):
    """control_structure.py — AuthorityGate maps confidence → envelope."""

    def test_zero_confidence_zero_envelope(self):
        gate = AuthorityGate()
        self.assertAlmostEqual(gate.get_authority_envelope(0.0), 0.0)

    def test_full_confidence_full_envelope(self):
        gate = AuthorityGate()
        self.assertAlmostEqual(gate.get_authority_envelope(1.0), 1.0)

    def test_mid_confidence_partial_envelope(self):
        gate = AuthorityGate()
        envelope = gate.get_authority_envelope(0.6)
        self.assertGreater(envelope, 0.0)
        self.assertLess(envelope, 1.0)

    def test_apply_clips_large_control(self):
        gate = AuthorityGate()
        u = np.array([10.0, 0.0])  # large magnitude
        clipped = gate.apply(u, confidence=0.3)
        self.assertLessEqual(np.linalg.norm(clipped), 0.15)

    def test_apply_does_not_clip_small_control(self):
        gate = AuthorityGate()
        u = np.array([0.05, 0.05])
        clipped = gate.apply(u, confidence=1.0)
        np.testing.assert_array_almost_equal(clipped, u)


# ===================================================================
# V. SCALING MECHANISM — Expander, Injector, Expander, Refinement
# ===================================================================

class TestDimensionExpander(unittest.TestCase):
    """scaling_mechanism.py — DimensionExpander."""

    def _base_state(self):
        dims = [StateDimension("a"), StateDimension("b")]
        return StateVector(dims, initial_values=[0.5, 0.3])

    def test_expand_adds_dimensions(self):
        expander = DimensionExpander()
        sv = self._base_state()
        new_dims = [(StateDimension("c"), 0.1, 0.5)]
        sv2 = expander.expand_state(sv, new_dims)
        self.assertEqual(sv2.n, 3)
        self.assertIn("c", sv2.dimension_names)

    def test_expand_preserves_existing_covariance(self):
        expander = DimensionExpander()
        sv = self._base_state()
        sv2 = expander.expand_state(sv, [(StateDimension("c"), 0.0, 1.0)])
        np.testing.assert_array_almost_equal(sv2.P[:2, :2], sv.P)

    def test_expand_duplicate_raises(self):
        expander = DimensionExpander()
        sv = self._base_state()
        with self.assertRaises(ValueError):
            expander.expand_state(sv, [(StateDimension("a"), 0.0, 1.0)])

    def test_check_expansion_valid(self):
        expander = DimensionExpander()
        sv = self._base_state()
        valid, conflicts = expander.check_expansion_valid(
            sv, [StateDimension("c"), StateDimension("d")]
        )
        self.assertTrue(valid)
        self.assertEqual(conflicts, [])

    def test_check_expansion_invalid(self):
        expander = DimensionExpander()
        sv = self._base_state()
        valid, conflicts = expander.check_expansion_valid(
            sv, [StateDimension("a")]
        )
        self.assertFalse(valid)
        self.assertIn("a", conflicts)


class TestConstraintInjector(unittest.TestCase):
    """scaling_mechanism.py — ConstraintInjector."""

    def test_inject_feasible_constraint(self):
        injector = ConstraintInjector()
        c = InjectedConstraint(
            constraint_id="c1",
            description="x ≤ 1",
            g=lambda x: float(x[0]) - 1.0,
        )
        x_test = np.array([0.5])
        ok = injector.inject_constraint(c, test_point=x_test)
        self.assertTrue(ok)
        self.assertEqual(injector.count(), 1)

    def test_inject_infeasible_constraint_rejected(self):
        injector = ConstraintInjector()
        c = InjectedConstraint(
            constraint_id="c2",
            description="x ≤ 0  (violated at x=0.5)",
            g=lambda x: float(x[0]),
        )
        x_test = np.array([0.5])
        ok = injector.inject_constraint(c, test_point=x_test)
        self.assertFalse(ok)
        self.assertEqual(injector.count(), 0)

    def test_check_consistency(self):
        injector = ConstraintInjector()
        c = InjectedConstraint(
            constraint_id="c3",
            description="x ≤ 1",
            g=lambda x: float(x[0]) - 1.0,
        )
        injector.inject_constraint(c)
        ok, violated = injector.check_consistency(np.array([0.5]))
        self.assertTrue(ok)
        self.assertEqual(violated, [])

    def test_remove_constraint(self):
        injector = ConstraintInjector()
        c = InjectedConstraint("c4", "test", g=lambda x: -1.0)
        injector.inject_constraint(c)
        self.assertEqual(injector.count(), 1)
        injector.remove_constraint("c4")
        self.assertEqual(injector.count(), 0)


class TestAuthorityExpander(unittest.TestCase):
    """scaling_mechanism.py — AuthorityExpander."""

    def test_add_role(self):
        expander = AuthorityExpander()
        expander.add_role(RoleNode("r1", "Manager", authority_level=0.8))
        self.assertEqual(expander.role_count(), 1)

    def test_add_delegation_and_subordinates(self):
        expander = AuthorityExpander()
        expander.add_role(RoleNode("r1", "VP"))
        expander.add_role(RoleNode("r2", "Manager"))
        expander.add_role(RoleNode("r3", "Analyst"))
        expander.add_delegation("r1", "r2")
        expander.add_delegation("r2", "r3")
        subs = expander.subordinates("r1", transitive=True)
        self.assertIn("r2", subs)
        self.assertIn("r3", subs)

    def test_delegation_unknown_role_raises(self):
        expander = AuthorityExpander()
        expander.add_role(RoleNode("r1", "A"))
        with self.assertRaises(ValueError):
            expander.add_delegation("r1", "nonexistent")

    def test_get_authority(self):
        expander = AuthorityExpander()
        expander.add_role(RoleNode("r1", "Lead", authority_level=0.75))
        self.assertAlmostEqual(expander.get_authority("r1"), 0.75)


class TestRefinementLoop(unittest.TestCase):
    """scaling_mechanism.py — RefinementLoop."""

    def _state_and_obs(self):
        dims = [StateDimension("x"), StateDimension("y")]
        sv = StateVector(dims, initial_values=[0.5, 0.5],
                         initial_covariance=np.eye(2) * 5.0)
        H = np.eye(2)
        R = np.eye(2) * 0.1
        z = np.array([0.6, 0.7])
        return sv, [(z, H, R)]

    def test_refinement_reduces_entropy(self):
        loop = RefinementLoop()
        sv, obs = self._state_and_obs()
        result = loop.refine(sv, obs, iterations=5)
        self.assertLess(result.final_entropy, result.initial_entropy)

    def test_refinement_converges(self):
        loop = RefinementLoop(convergence_threshold=0.1)
        sv, obs = self._state_and_obs()
        result = loop.refine(sv, obs, iterations=20)
        self.assertTrue(result.converged)

    def test_refinement_result_has_final_state(self):
        loop = RefinementLoop()
        sv, obs = self._state_and_obs()
        result = loop.refine(sv, obs, iterations=3)
        self.assertIsNotNone(result.final_state)
        self.assertEqual(result.final_state.n, sv.n)


# ===================================================================
# VI. LLM SYNTHESIS VALIDATOR — schemas, validator, conflict, regen
# ===================================================================

class TestGeneratedSchemas(unittest.TestCase):
    """llm_synthesis_validator.py — Pydantic schemas."""

    def test_valid_state_dimension(self):
        gsd = GeneratedStateDimension(
            dimension_id="d1",
            name="risk_score",
            dtype="float",
            lower_bound=0.0,
            upper_bound=1.0,
        )
        self.assertEqual(gsd.dimension_id, "d1")

    def test_invalid_dtype_raises(self):
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            GeneratedStateDimension(dimension_id="d1", name="x", dtype="complex")

    def test_inconsistent_bounds_raise(self):
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            GeneratedStateDimension(
                dimension_id="d1", name="x", lower_bound=1.0, upper_bound=0.0
            )

    def test_valid_constraint(self):
        gc = GeneratedConstraint(
            constraint_id="c1",
            description="budget ≤ 1000",
            constraint_type="inequality",
        )
        self.assertEqual(gc.severity, "medium")

    def test_invalid_severity_raises(self):
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            GeneratedConstraint(
                constraint_id="c1", description="x", severity="extreme"
            )

    def test_valid_role(self):
        gr = GeneratedRole(
            role_id="role1",
            name="Architect",
            authority_level=0.8,
        )
        self.assertAlmostEqual(gr.authority_level, 0.8)

    def test_authority_level_out_of_range_raises(self):
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            GeneratedRole(role_id="r1", name="X", authority_level=1.5)


class TestOutputValidator(unittest.TestCase):
    """llm_synthesis_validator.py — OutputValidator."""

    def test_validate_valid_state_dimension(self):
        result = validate_output(
            "state_dimension",
            {"dimension_id": "d1", "name": "risk", "dtype": "float"},
        )
        self.assertTrue(result.is_valid)
        self.assertEqual(result.errors, [])

    def test_validate_invalid_returns_errors(self):
        result = validate_output("state_dimension", {"dimension_id": "", "name": ""})
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)

    def test_validate_unknown_schema_returns_error(self):
        result = validate_output("unknown_type", {})
        self.assertFalse(result.is_valid)
        self.assertTrue(any("Unknown schema" in e for e in result.errors))

    def test_batch_validate_all_valid(self):
        validator = OutputValidator()
        items = [
            ("state_dimension", {"dimension_id": "d1", "name": "x"}),
            ("constraint", {"constraint_id": "c1", "description": "x ≤ 1"}),
        ]
        self.assertTrue(validator.all_valid(items))


class TestConflictResolver(unittest.TestCase):
    """llm_synthesis_validator.py — ConflictResolver."""

    def test_no_conflict_on_unique_id(self):
        resolver = ConflictResolver()
        new = {"dimension_id": "d2", "name": "new_dim"}
        existing = [{"dimension_id": "d1", "name": "old_dim"}]
        report = resolver.detect_conflicts(new, existing, schema_name="state_dimension")
        self.assertFalse(report.has_conflicts)

    def test_duplicate_id_detected(self):
        resolver = ConflictResolver()
        new = {"dimension_id": "d1", "name": "dup"}
        existing = [{"dimension_id": "d1", "name": "original"}]
        report = resolver.detect_conflicts(new, existing, schema_name="state_dimension")
        self.assertTrue(report.has_conflicts)
        kinds = [k for k, _ in report.conflicts]
        self.assertIn(ConflictKind.DUPLICATE_ID, kinds)

    def test_overlapping_bounds_detected(self):
        resolver = ConflictResolver()
        new = {"name": "x", "lower_bound": 0.0, "upper_bound": 2.0}
        existing = [{"name": "x", "lower_bound": 0.0, "upper_bound": 1.0}]
        report = resolver.detect_conflicts(new, existing, schema_name="state_dimension")
        self.assertTrue(report.has_conflicts)
        kinds = [k for k, _ in report.conflicts]
        self.assertIn(ConflictKind.OVERLAPPING_BOUNDS, kinds)

    def test_authority_cycle_detected(self):
        resolver = ConflictResolver()
        new = {"role_id": "r1", "name": "A", "reports_to": "r2"}
        existing = [{"role_id": "r2", "name": "B", "reports_to": "r1"}]
        report = resolver.detect_conflicts(new, existing, schema_name="role")
        self.assertTrue(report.has_conflicts)
        kinds = [k for k, _ in report.conflicts]
        self.assertIn(ConflictKind.AUTHORITY_CYCLE, kinds)

    def test_no_authority_cycle_on_linear_chain(self):
        resolver = ConflictResolver()
        new = {"role_id": "r3", "name": "C", "reports_to": "r2"}
        existing = [{"role_id": "r2", "name": "B", "reports_to": "r1"}]
        report = resolver.detect_conflicts(new, existing, schema_name="role")
        cycle_conflicts = [k for k, _ in report.conflicts if k == ConflictKind.AUTHORITY_CYCLE]
        self.assertEqual(cycle_conflicts, [])


class TestRegenerationTrigger(unittest.TestCase):
    """llm_synthesis_validator.py — RegenerationTrigger."""

    def test_regenerate_below_threshold(self):
        trigger = RegenerationTrigger(threshold=0.5, window_size=3)
        history = [0.3, 0.2, 0.1]
        self.assertTrue(trigger.should_regenerate(history))

    def test_no_regenerate_above_threshold(self):
        trigger = RegenerationTrigger(threshold=0.5, window_size=3)
        history = [0.8, 0.9, 0.7]
        self.assertFalse(trigger.should_regenerate(history))

    def test_max_retries_halts_regeneration(self):
        trigger = RegenerationTrigger(threshold=0.5, max_retries=2)
        history = [0.1, 0.1, 0.1]
        # Even with low confidence, should not regenerate after max_retries
        self.assertFalse(trigger.should_regenerate(history, current_retries=2))

    def test_empty_history_triggers_regeneration(self):
        trigger = RegenerationTrigger(threshold=0.5)
        self.assertTrue(trigger.should_regenerate([]))

    def test_window_uses_most_recent_values(self):
        """Only the last window_size values should matter."""
        trigger = RegenerationTrigger(threshold=0.5, window_size=2)
        # Old values are low, recent are high
        history = [0.1, 0.1, 0.1, 0.9, 0.8]
        self.assertFalse(trigger.should_regenerate(history))


# ===================================================================
# VII. INTEGRATION — full predict → observe → update → control loop
# ===================================================================

class TestIntegrationLoop(unittest.TestCase):
    """End-to-end: predict → observe (Kalman) → update → control → stability."""

    def setUp(self):
        # 2-D state: [confidence, authority]
        self.dims = [
            StateDimension("confidence", bounds=(0.0, 1.0)),
            StateDimension("authority", bounds=(0.0, 1.0)),
        ]
        self.sv = StateVector(
            self.dims,
            initial_values=[0.3, 0.2],
            initial_covariance=np.eye(2) * 0.5,
        )
        self.target = np.array([0.9, 0.8])

    def test_full_loop_reduces_error(self):
        """After one predict-observe-update-control cycle, state moves toward target."""
        se = StateEvolution()
        ko = KalmanObserver()
        law = ControlLaw(Kp=0.5, Ki=0.0)
        monitor = StabilityMonitor(equilibrium=self.target)
        gate = AuthorityGate()

        sv = self.sv
        H = np.eye(2)
        R = np.eye(2) * 0.1
        trajectory = [sv.x.copy()]

        for _ in range(5):
            # 1. Compute control
            u, _ = law.compute_control(sv.x, self.target)
            u = gate.apply(u, confidence=float(sv.get_value("confidence")))

            # 2. Predict
            sv = se.predict(sv, control_input=u)

            # 3. Observe (simulate measurement = true + tiny noise)
            z = sv.x + np.random.normal(0, 0.01, size=2)
            sv, _ = sv.update(z, H, R)

            trajectory.append(sv.x.copy())

        # State should be closer to target after 5 steps
        initial_error = np.linalg.norm(trajectory[0] - self.target)
        final_error = np.linalg.norm(trajectory[-1] - self.target)
        self.assertLess(final_error, initial_error)

    def test_entropy_decreases_with_observations(self):
        """Accumulating observations should reduce state entropy."""
        tracker = EntropyTracker()
        sv = self.sv
        H = np.eye(2)
        R = np.eye(2) * 0.05

        tracker.record(sv.P)

        for _ in range(5):
            z = np.array([0.9, 0.8])
            sv, _ = sv.update(z, H, R)
            tracker.record(sv.P)

        self.assertTrue(tracker.is_non_increasing())

    def test_dynamic_expansion_in_loop(self):
        """New dimensions can be added mid-loop without breaking existing state."""
        expander = DimensionExpander()
        sv = self.sv

        new_dim = StateDimension("complexity", bounds=(0.0, 1.0))
        sv3 = expander.expand_state(sv, [(new_dim, 0.5, 0.2)])

        # Original dimensions still intact
        self.assertAlmostEqual(sv3.get_value("confidence"), sv.get_value("confidence"))
        self.assertEqual(sv3.n, sv.n + 1)

    def test_murphy_index_decreases_with_reduced_uncertainty(self):
        """As covariance shrinks, formal Murphy Index should decrease."""
        sv_high_uncertainty = StateVector(
            self.dims,
            initial_values=[0.5, 0.5],
            initial_covariance=np.eye(2) * 10.0,
        )
        sv_low_uncertainty = StateVector(
            self.dims,
            initial_values=[0.5, 0.5],
            initial_covariance=np.eye(2) * 0.01,
        )
        lp = [(0.5, 0.5)]
        m_high = compute_murphy_index_formal(lp, sv_high_uncertainty.P)
        m_low = compute_murphy_index_formal(lp, sv_low_uncertainty.P)
        self.assertGreater(m_high, m_low)

    def test_constraint_injection_and_consistency(self):
        """Constraints injected at a feasible point should pass consistency."""
        injector = ConstraintInjector()
        # confidence ≤ 0.95
        c = InjectedConstraint(
            "budget_cap",
            "confidence ≤ 0.95",
            g=lambda x: float(x[0]) - 0.95,
        )
        injector.inject_constraint(c, test_point=self.sv.x)
        ok, violated = injector.check_consistency(self.sv.x)
        self.assertTrue(ok)
        self.assertEqual(violated, [])


if __name__ == "__main__":
    unittest.main()
