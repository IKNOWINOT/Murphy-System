"""
Tests for the nonlinear state evolution hook (Gap D).

Proves:
  - Default linear behavior is unchanged.
  - Custom nonlinear transition_fn is called.
  - Jacobian-based EKF covariance propagation works.
"""

import os
import unittest
import math

import numpy as np


from control_theory.state_model import StateDimension, StateEvolution, StateVector


def _make_state(n: int = 2, values=None, variance: float = 1.0) -> StateVector:
    dims = [StateDimension(f"x{i}", bounds=(None, None)) for i in range(n)]
    vals = values if values is not None else [1.0] * n
    cov = np.eye(n) * variance
    return StateVector(dims, initial_values=vals, initial_covariance=cov)


class TestLinearDefaultBehavior(unittest.TestCase):
    """Default (no transition_fn) must behave exactly as before."""

    def test_identity_transition_no_control(self):
        """x_{t+1} = x_t when F=I and u=0."""
        evo = StateEvolution()
        state = _make_state(n=2, values=[0.5, 0.3])
        predicted = evo.predict(state)
        np.testing.assert_allclose(predicted.x, [0.5, 0.3], atol=1e-12)

    def test_linear_with_control(self):
        """x_{t+1} = x_t + u_t (identity F, identity B)."""
        evo = StateEvolution()
        state = _make_state(n=2, values=[0.5, 0.3])
        u = np.array([0.1, -0.1])
        predicted = evo.predict(state, control_input=u)
        np.testing.assert_allclose(predicted.x, [0.6, 0.2], atol=1e-12)

    def test_covariance_grows_by_Q(self):
        """P_{t+1} = P_t + Q (identity F)."""
        Q = np.eye(2) * 0.01
        evo = StateEvolution(Q=Q)
        state = _make_state(n=2, variance=0.5)
        predicted = evo.predict(state)
        expected_P = state.P + Q
        np.testing.assert_allclose(predicted.P, expected_P, atol=1e-12)

    def test_custom_F_matrix(self):
        """x_{t+1} = F x_t when custom F provided."""
        F = np.array([[0.9, 0.0], [0.0, 0.8]])
        evo = StateEvolution(F=F)
        state = _make_state(n=2, values=[1.0, 1.0])
        predicted = evo.predict(state)
        np.testing.assert_allclose(predicted.x, [0.9, 0.8], atol=1e-12)

    def test_returns_new_state_vector_not_in_place(self):
        """predict() must return a new StateVector."""
        evo = StateEvolution()
        state = _make_state(n=2, values=[0.5, 0.5])
        predicted = evo.predict(state)
        self.assertIsNot(predicted, state)


class TestNonlinearTransitionFn(unittest.TestCase):
    """transition_fn overrides the linear F/B model."""

    def test_transition_fn_is_called(self):
        """Verify the custom function is invoked."""
        call_log = []

        def my_fn(x, u):
            call_log.append(True)
            return x + u

        evo = StateEvolution(transition_fn=my_fn)
        state = _make_state(n=2, values=[1.0, 2.0])
        evo.predict(state, control_input=np.array([0.1, 0.2]))
        self.assertTrue(call_log, "transition_fn was never called")

    def test_nonlinear_squaring_function(self):
        """x_{t+1} = x_t² (element-wise) as a toy nonlinear model."""
        def square_fn(x, u):
            return x ** 2

        evo = StateEvolution(transition_fn=square_fn)
        state = _make_state(n=2, values=[2.0, 3.0])
        predicted = evo.predict(state)
        np.testing.assert_allclose(predicted.x, [4.0, 9.0], atol=1e-12)

    def test_nonlinear_ignores_F_B(self):
        """When transition_fn is set, F and B matrices are ignored."""
        F = np.array([[100.0, 0.0], [0.0, 100.0]])  # would massively amplify x
        B = np.array([[100.0, 0.0], [0.0, 100.0]])

        def identity_fn(x, u):
            return x.copy()

        evo = StateEvolution(F=F, B=B, transition_fn=identity_fn)
        state = _make_state(n=2, values=[0.5, 0.5])
        predicted = evo.predict(state, control_input=np.ones(2))
        np.testing.assert_allclose(predicted.x, [0.5, 0.5], atol=1e-12)

    def test_nonlinear_covariance_uses_identity_jacobian_by_default(self):
        """Without jacobian_fn, covariance propagates with identity Jacobian."""
        Q = np.eye(2) * 0.001

        def double_fn(x, u):
            return 2 * x

        evo = StateEvolution(Q=Q, transition_fn=double_fn)
        state = _make_state(n=2, values=[1.0, 1.0], variance=1.0)
        predicted = evo.predict(state)
        # With identity Jacobian: P_{t+1} = I P I^T + Q = P + Q
        expected_P = state.P + Q
        np.testing.assert_allclose(predicted.P, expected_P, atol=1e-12)

    def test_transition_fn_with_control(self):
        """transition_fn receives the control vector."""
        received_u = []

        def fn_with_control(x, u):
            received_u.append(u.copy())
            return x + u

        evo = StateEvolution(transition_fn=fn_with_control)
        state = _make_state(n=2, values=[0.0, 0.0])
        u = np.array([3.0, 4.0])
        predicted = evo.predict(state, control_input=u)
        np.testing.assert_allclose(predicted.x, [3.0, 4.0], atol=1e-12)
        np.testing.assert_allclose(received_u[0], [3.0, 4.0], atol=1e-12)


class TestJacobianCovariancePropagation(unittest.TestCase):
    """EKF covariance propagation via jacobian_fn."""

    def test_jacobian_fn_is_used_for_covariance(self):
        """P_{t+1} = J P J^T + Q when jacobian_fn provided."""
        Q = np.eye(2) * 0.001

        def nonlinear_fn(x, u):
            return x * 2.0  # doubles the state

        def jacobian_fn(x, u):
            return np.eye(2) * 2.0  # ∂f/∂x = 2I

        evo = StateEvolution(Q=Q, transition_fn=nonlinear_fn, jacobian_fn=jacobian_fn)
        P0 = np.eye(2)
        state = _make_state(n=2, values=[1.0, 1.0], variance=1.0)
        state._P = P0
        predicted = evo.predict(state)

        J = np.eye(2) * 2.0
        expected_P = J @ P0 @ J.T + Q
        np.testing.assert_allclose(predicted.P, expected_P, atol=1e-10)

    def test_jacobian_fn_called_with_current_state(self):
        """jacobian_fn receives the pre-transition state x_t."""
        received_x = []

        def fn(x, u):
            return x.copy()

        def jac_fn(x, u):
            received_x.append(x.copy())
            return np.eye(len(x))

        evo = StateEvolution(transition_fn=fn, jacobian_fn=jac_fn)
        state = _make_state(n=2, values=[3.0, 7.0])
        evo.predict(state)
        np.testing.assert_allclose(received_x[0], [3.0, 7.0], atol=1e-12)

    def test_jacobian_based_covariance_grows_correctly(self):
        """Scaling Jacobian amplifies covariance proportionally."""
        scale = 3.0

        def fn(x, u):
            return x * scale

        def jac_fn(x, u):
            return np.eye(len(x)) * scale

        Q = np.zeros((2, 2))
        evo = StateEvolution(Q=Q, transition_fn=fn, jacobian_fn=jac_fn)
        P0 = np.eye(2)
        state = _make_state(n=2, values=[1.0, 1.0])
        state._P = P0
        predicted = evo.predict(state)

        expected_P = (scale ** 2) * P0
        np.testing.assert_allclose(predicted.P, expected_P, atol=1e-10)

    def test_linear_fn_jacobian_matches_F(self):
        """For a linear function, jacobian_fn should give same result as using F."""
        F = np.array([[0.9, 0.1], [0.0, 0.8]])
        Q = np.eye(2) * 0.001

        def linear_fn(x, u):
            return F @ x

        def jac_fn(x, u):
            return F  # constant Jacobian for linear function

        evo_nonlinear = StateEvolution(Q=Q, transition_fn=linear_fn, jacobian_fn=jac_fn)
        evo_linear = StateEvolution(F=F, Q=Q)

        state = _make_state(n=2, values=[0.5, 0.5], variance=1.0)
        pred_nl = evo_nonlinear.predict(state)
        pred_l = evo_linear.predict(state)

        np.testing.assert_allclose(pred_nl.x, pred_l.x, atol=1e-10)
        np.testing.assert_allclose(pred_nl.P, pred_l.P, atol=1e-10)


if __name__ == "__main__":
    unittest.main()
