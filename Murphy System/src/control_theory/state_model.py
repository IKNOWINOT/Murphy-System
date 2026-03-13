"""
Formal State Vector with Uncertainty for the Murphy System.

Provides a control-theoretic state representation:
  - StateVector: typed, dimensioned array with covariance matrix P_t
  - StateDimension: name, type, bounds, unit metadata
  - StateEvolution: x_{t+1} = f(x_t, u_t) + w_t, w_t ~ N(0, Q)

The covariance matrix P_t tracks per-dimension uncertainty and supports
differential-entropy computation:

    H(x) = 0.5 * ln((2πe)^n * det(P_t))

Dynamic dimension addition preserves existing covariance structure.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
# Dimension metadata
# ------------------------------------------------------------------ #

@dataclass
class StateDimension:
    """Typed metadata for a single state dimension."""

    name: str
    dtype: str = "float"           # "float" | "int"
    bounds: Tuple[Optional[float], Optional[float]] = (None, None)
    unit: str = ""                 # e.g. "seconds", "percent", "dimensionless"

    def clamp(self, value: float) -> float:
        """Clamp *value* to the declared bounds."""
        lo, hi = self.bounds
        if lo is not None:
            value = max(lo, value)
        if hi is not None:
            value = min(hi, value)
        return value


# ------------------------------------------------------------------ #
# State vector
# ------------------------------------------------------------------ #

class StateVector:
    """
    Formal state vector x_t ∈ ℝ^n with covariance matrix P_t ∈ ℝ^{n×n}.

    Implements:
      predict(u_t) → x_{t+1} = x_t + u_t + w_t, P_{t+1} = P_t + Q
      update(z, H, R) → Kalman measurement update
      add_dimension(name, initial_value, initial_variance)
      get_entropy() = 0.5 * ln((2πe)^n * |P_t|)
    """

    def __init__(
        self,
        dimensions: List[StateDimension],
        initial_values: Optional[List[float]] = None,
        initial_covariance: Optional[np.ndarray] = None,
    ) -> None:
        """
        Args:
            dimensions: ordered list of StateDimension objects.
            initial_values: initial x_0 (defaults to zeros).
            initial_covariance: initial P_0 (defaults to identity).
        """
        self._dims: List[StateDimension] = list(dimensions)
        n = len(self._dims)

        if initial_values is not None:
            if len(initial_values) != n:
                raise ValueError(
                    f"Expected {n} initial values, got {len(initial_values)}"
                )
            self._x: np.ndarray = np.array(initial_values, dtype=float)
        else:
            self._x = np.zeros(n, dtype=float)

        if initial_covariance is not None:
            if initial_covariance.shape != (n, n):
                raise ValueError(
                    f"Covariance must be ({n},{n}), got {initial_covariance.shape}"
                )
            self._P: np.ndarray = initial_covariance.astype(float)
        else:
            self._P = np.eye(n, dtype=float)

    # ---- properties ----------------------------------------------- #

    @property
    def x(self) -> np.ndarray:
        """State vector x_t (read-only view)."""
        return self._x.copy()

    @property
    def P(self) -> np.ndarray:
        """Covariance matrix P_t (read-only view)."""
        return self._P.copy()

    @property
    def n(self) -> int:
        """State dimension n."""
        return len(self._dims)

    @property
    def dimension_names(self) -> List[str]:
        """Ordered list of dimension names."""
        return [d.name for d in self._dims]

    def get_value(self, name: str) -> float:
        """Return the scalar value for a named dimension."""
        idx = self._index(name)
        return float(self._x[idx])

    def set_value(self, name: str, value: float) -> None:
        """Set the scalar value for a named dimension (with clamping)."""
        idx = self._index(name)
        self._x[idx] = self._dims[idx].clamp(value)

    def get_variance(self, name: str) -> float:
        """Return P[i,i] — the marginal variance of a named dimension."""
        idx = self._index(name)
        return float(self._P[idx, idx])

    # ---- prediction step ------------------------------------------ #

    def predict(
        self,
        control_input: Optional[np.ndarray] = None,
        process_noise_cov: Optional[np.ndarray] = None,
    ) -> "StateVector":
        """
        Linear prediction step:

            x_{t+1} = x_t + u_t
            P_{t+1} = P_t + Q

        Args:
            control_input: u_t ∈ ℝ^n.  Defaults to zero vector.
            process_noise_cov: Q ∈ ℝ^{n×n}.  Defaults to 0.001 * I.

        Returns:
            New StateVector representing the predicted state.
        """
        n = self.n
        u = control_input if control_input is not None else np.zeros(n)
        Q = process_noise_cov if process_noise_cov is not None else np.eye(n) * 0.001

        x_pred = self._x + u
        # Clamp to dimension bounds
        for i, dim in enumerate(self._dims):
            x_pred[i] = dim.clamp(float(x_pred[i]))

        P_pred = self._P + Q

        return StateVector(
            dimensions=list(self._dims),
            initial_values=x_pred.tolist(),
            initial_covariance=P_pred,
        )

    # ---- Kalman measurement update --------------------------------- #

    def update(
        self,
        measurement: np.ndarray,
        H: np.ndarray,
        R: np.ndarray,
    ) -> Tuple["StateVector", np.ndarray]:
        """
        Kalman measurement update:

            y   = z - H x          (innovation)
            S   = H P Hᵀ + R       (innovation covariance)
            K   = P Hᵀ S⁻¹         (Kalman gain)
            x'  = x + K y
            P'  = (I - K H) P

        Args:
            measurement: z ∈ ℝ^m.
            H: measurement matrix ∈ ℝ^{m×n}.
            R: measurement noise covariance ∈ ℝ^{m×m}.

        Returns:
            (updated_state_vector, innovation_vector)
        """
        n = self.n
        y = measurement - H @ self._x
        S = H @ self._P @ H.T + R
        K = self._P @ H.T @ np.linalg.inv(S)

        x_upd = self._x + K @ y
        P_upd = (np.eye(n) - K @ H) @ self._P

        # Clamp values
        for i, dim in enumerate(self._dims):
            x_upd[i] = dim.clamp(float(x_upd[i]))

        updated = StateVector(
            dimensions=list(self._dims),
            initial_values=x_upd.tolist(),
            initial_covariance=P_upd,
        )
        return updated, y

    # ---- uncertainty ------------------------------------------------ #

    def get_uncertainty(self) -> np.ndarray:
        """Return the diagonal of P_t (per-dimension variances)."""
        return np.diag(self._P).copy()

    def get_entropy(self) -> float:
        """
        Compute differential entropy of N(x, P):

            H = 0.5 * ln((2πe)^n * det(P))

        Returns 0.0 if P is singular (degenerate distribution).
        """
        n = self.n
        sign, log_det = np.linalg.slogdet(self._P)
        if sign <= 0:
            return 0.0
        return 0.5 * (n * (1.0 + math.log(2.0 * math.pi)) + log_det)

    # ---- dynamic dimension addition -------------------------------- #

    def add_dimension(
        self,
        dimension: StateDimension,
        initial_value: float = 0.0,
        initial_variance: float = 1.0,
    ) -> "StateVector":
        """
        Return a new StateVector with one additional dimension appended.

        Existing covariance structure is preserved (new row/column are
        zero off-diagonal, *initial_variance* on the diagonal).

        Args:
            dimension: StateDimension metadata for the new dimension.
            initial_value: x value for the new dimension.
            initial_variance: P[n,n] for the new dimension.

        Returns:
            New StateVector with n+1 dimensions.
        """
        new_dims = list(self._dims) + [dimension]
        new_x = np.append(self._x, dimension.clamp(initial_value))

        n = self.n
        new_P = np.zeros((n + 1, n + 1))
        new_P[:n, :n] = self._P
        new_P[n, n] = initial_variance

        return StateVector(
            dimensions=new_dims,
            initial_values=new_x.tolist(),
            initial_covariance=new_P,
        )

    # ---- helpers ---------------------------------------------------- #

    def _index(self, name: str) -> int:
        for i, d in enumerate(self._dims):
            if d.name == name:
                return i
        raise KeyError(f"Dimension '{name}' not found in state vector.")

    def to_dict(self) -> dict:
        """Return state values as a {name: value} dict."""
        return {d.name: float(self._x[i]) for i, d in enumerate(self._dims)}

    def __repr__(self) -> str:
        return (
            f"StateVector(n={self.n}, "
            f"dims={self.dimension_names}, "
            f"entropy={self.get_entropy():.4f})"
        )


# ------------------------------------------------------------------ #
# State evolution model
# ------------------------------------------------------------------ #

class StateEvolution:
    """
    Formal state-evolution model:

        x_{t+1} = F x_t + B u_t + w_t,   w_t ~ N(0, Q)

    Supports an optional nonlinear transition function via *transition_fn*:

        x_{t+1} = transition_fn(x_t, u_t)

    When *transition_fn* is provided the linear F/B matrices are ignored.
    An optional *jacobian_fn* enables Extended Kalman Filter covariance
    propagation:

        P_{t+1} = F(x_t) · P_t · F(x_t)ᵀ + Q

    where F(x_t) = ∂f/∂x evaluated at the current state.
    """

    def __init__(
        self,
        F: Optional[np.ndarray] = None,
        B: Optional[np.ndarray] = None,
        Q: Optional[np.ndarray] = None,
        transition_fn: Optional[Callable[[np.ndarray, np.ndarray], np.ndarray]] = None,
        jacobian_fn: Optional[Callable[[np.ndarray, np.ndarray], np.ndarray]] = None,
    ) -> None:
        """
        Args:
            F: state transition matrix (defaults to identity — random-walk model).
            B: control input matrix (defaults to identity).
            Q: process noise covariance (defaults to 0.001 * I).
            transition_fn: optional nonlinear function
                ``f(x_t, u_t) -> x_{t+1}`` (overrides F/B when provided).
            jacobian_fn: optional function ``J(x_t, u_t) -> F_t`` that computes
                the Jacobian ∂f/∂x for EKF covariance propagation.  Only
                used when *transition_fn* is also provided.
        """
        self._F = F
        self._B = B
        self._Q = Q
        self.transition_fn = transition_fn
        self.jacobian_fn = jacobian_fn

    def predict(
        self,
        state: StateVector,
        control_input: Optional[np.ndarray] = None,
    ) -> StateVector:
        """
        Propagate state vector and covariance one step forward.

        Linear (default):
            x_{t+1} = F x_t + B u_t
            P_{t+1} = F P_t Fᵀ + Q

        Nonlinear (when transition_fn is provided):
            x_{t+1} = transition_fn(x_t, u_t)
            P_{t+1} = J P_t Jᵀ + Q   (J from jacobian_fn, else identity)

        Args:
            state: current StateVector.
            control_input: u_t (defaults to zero).

        Returns:
            New predicted StateVector.
        """
        n = state.n
        Q = self._Q if self._Q is not None else np.eye(n) * 0.001
        u = control_input if control_input is not None else np.zeros(n)

        if self.transition_fn is not None:
            # Nonlinear prediction
            x_pred = self.transition_fn(state._x.copy(), u)
            if not isinstance(x_pred, np.ndarray):
                x_pred = np.array(x_pred, dtype=float)
            for i, dim in enumerate(state._dims):
                x_pred[i] = dim.clamp(float(x_pred[i]))

            if self.jacobian_fn is not None:
                F_t = self.jacobian_fn(state._x.copy(), u)
            else:
                F_t = np.eye(n)
            P_pred = F_t @ state._P @ F_t.T + Q
        else:
            # Linear prediction
            F = self._F if self._F is not None else np.eye(n)
            B = self._B if self._B is not None else np.eye(n)
            x_pred = F @ state._x + B @ u
            for i, dim in enumerate(state._dims):
                x_pred[i] = dim.clamp(float(x_pred[i]))
            P_pred = F @ state._P @ F.T + Q

        return StateVector(
            dimensions=list(state._dims),
            initial_values=x_pred.tolist(),
            initial_covariance=P_pred,
        )
