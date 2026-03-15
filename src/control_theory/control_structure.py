"""
Formal Control Structure with Stability Guarantees for the Murphy System.

Provides:
  - ControlVector: typed control actions with saturation limits
  - ControlLaw: u_t = K(x_t, x_ref) proportional-integral feedback
  - StabilityMonitor: tracks Lyapunov-like V(x) to ensure convergence
  - AuthorityGate: maps confidence → max allowed control magnitude

Control-theoretic motivation:
  The existing AuthorityController maps confidence → authority band but
  lacks a formal feedback law with stability guarantees.  This module
  adds:
    1. A proper PI control law with per-dimension gains.
    2. A Lyapunov stability monitor verifying V(x_{t+1}) < V(x_t).
    3. An authority gate that saturates control effort to the permitted
       envelope, preventing unsafe state changes.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
# Control vector
# ------------------------------------------------------------------ #

@dataclass
class ControlDimension:
    """Metadata for a single control dimension."""

    name: str
    lower_limit: float = -1.0
    upper_limit: float = 1.0
    unit: str = ""

    def saturate(self, value: float) -> float:
        """Clamp *value* to [lower_limit, upper_limit]."""
        return max(self.lower_limit, min(self.upper_limit, value))


class ControlVector:
    """
    Typed control output u_t ∈ U.

    Each dimension has declared saturation limits.  The vector supports
    element-wise saturation and scaling by an authority factor.
    """

    def __init__(
        self,
        dimensions: List[ControlDimension],
        values: Optional[List[float]] = None,
    ) -> None:
        self._dims = list(dimensions)
        n = len(self._dims)
        if values is not None:
            if len(values) != n:
                raise ValueError(
                    f"Expected {n} values, got {len(values)}"
                )
            self._u = np.array(
                [d.saturate(v) for d, v in zip(self._dims, values)],
                dtype=float,
            )
        else:
            self._u = np.zeros(n, dtype=float)

    @property
    def values(self) -> np.ndarray:
        return self._u.copy()

    @property
    def n(self) -> int:
        return len(self._dims)

    @property
    def dimension_names(self) -> List[str]:
        return [d.name for d in self._dims]

    def scale(self, factor: float) -> "ControlVector":
        """Return a new ControlVector scaled by *factor* and re-saturated."""
        new_vals = [d.saturate(float(self._u[i]) * factor) for i, d in enumerate(self._dims)]
        return ControlVector(dimensions=list(self._dims), values=new_vals)

    def to_array(self) -> np.ndarray:
        return self._u.copy()

    def __repr__(self) -> str:
        return f"ControlVector({dict(zip(self.dimension_names, self._u.tolist()))})"


# ------------------------------------------------------------------ #
# Control law — proportional-integral (PI) feedback
# ------------------------------------------------------------------ #

class ControlLaw:
    """
    Proportional-Integral feedback control law:

        e_t      = x_ref - x_t            (tracking error)
        Δu_t     = Kp × e_t + Ki × Σe    (PI update)
        u_t      = saturate(Δu_t)

    The integral term Σe accumulates tracking error to eliminate
    steady-state offset — a property not achievable with proportional
    control alone.
    """

    def __init__(
        self,
        Kp: float = 1.0,
        Ki: float = 0.1,
        dimensions: Optional[List[ControlDimension]] = None,
        per_dim_Kp: Optional[Dict[str, float]] = None,
    ) -> None:
        """
        Args:
            Kp: proportional gain (scalar or per-dimension via per_dim_Kp).
            Ki: integral gain.
            dimensions: control dimensions (defaults to generic unbounded dims).
            per_dim_Kp: optional {dim_name: gain} override.
        """
        self.Kp = Kp
        self.Ki = Ki
        self._dims = dimensions or []
        self._per_dim_Kp = per_dim_Kp or {}
        self._integral: Optional[np.ndarray] = None  # Σe

    def _dim_gain(self, name: str) -> float:
        return self._per_dim_Kp.get(name, self.Kp)

    def compute_control(
        self,
        state: np.ndarray,
        reference: np.ndarray,
        dt: float = 1.0,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Compute PI control output.

        Args:
            state: current state x_t ∈ ℝ^n.
            reference: target state x_ref ∈ ℝ^n.
            dt: time step for integral accumulation.

        Returns:
            (u_t, error_t) — control output and tracking error.
        """
        if len(state) != len(reference):
            raise ValueError("state and reference must have the same length.")

        n = len(state)
        if self._integral is None:
            self._integral = np.zeros(n, dtype=float)

        error = reference - state
        self._integral += error * dt

        # Per-dimension proportional gains
        if self._dims and len(self._dims) == n:
            Kp_vec = np.array([self._dim_gain(d.name) for d in self._dims])
        else:
            Kp_vec = np.full(n, self.Kp)

        u = Kp_vec * error + self.Ki * self._integral

        # Saturate per dimension if dims are defined
        if self._dims and len(self._dims) == n:
            u = np.array([d.saturate(float(ui)) for d, ui in zip(self._dims, u)])

        return u, error

    def reset_integral(self) -> None:
        """Reset the integral accumulator (e.g., after setpoint change)."""
        self._integral = None


# ------------------------------------------------------------------ #
# Stability monitor
# ------------------------------------------------------------------ #

@dataclass
class StabilityResult:
    """Outcome of a Lyapunov stability check."""

    v_values: List[float]           # V(x) at each trajectory step
    is_stable: bool                 # V is globally non-increasing
    convergence_rate: float         # mean ΔV per step (< 0 = converging)
    violations: int                 # number of steps where V increased


class StabilityMonitor:
    """
    Tracks a Lyapunov-like function V(x) = ‖x - x*‖²_P over a trajectory.

    Stability condition: V(x_{t+1}) < V(x_t)  for all t.

    A trajectory is declared stable iff V is monotonically non-increasing.
    """

    def __init__(
        self,
        equilibrium: np.ndarray,
        weight_matrix: Optional[np.ndarray] = None,
    ) -> None:
        """
        Args:
            equilibrium: target state x* ∈ ℝ^n.
            weight_matrix: positive-definite P ∈ ℝ^{n×n}.  Defaults to I.
        """
        self.equilibrium = np.asarray(equilibrium, dtype=float)
        n = len(self.equilibrium)
        self._P = (
            np.asarray(weight_matrix, dtype=float)
            if weight_matrix is not None
            else np.eye(n, dtype=float)
        )

    def lyapunov(self, state: np.ndarray) -> float:
        """
        V(x) = (x - x*)ᵀ P (x - x*)
        """
        e = np.asarray(state, dtype=float) - self.equilibrium
        return float(e @ self._P @ e)

    def check_stability(self, trajectory: List[np.ndarray]) -> StabilityResult:
        """
        Check Lyapunov decrease along an entire trajectory.

        Args:
            trajectory: list of state vectors.

        Returns:
            StabilityResult with statistics.
        """
        if len(trajectory) < 2:
            v_vals = [self.lyapunov(trajectory[0])] if trajectory else []
            return StabilityResult(
                v_values=v_vals, is_stable=True, convergence_rate=0.0, violations=0
            )

        v_vals = [self.lyapunov(s) for s in trajectory]
        deltas = [v_vals[i + 1] - v_vals[i] for i in range(len(v_vals) - 1)]
        violations = sum(1 for d in deltas if d > 0)
        convergence_rate = sum(deltas) / len(deltas) if deltas else 0.0

        return StabilityResult(
            v_values=v_vals,
            is_stable=violations == 0,
            convergence_rate=convergence_rate,
            violations=violations,
        )


# ------------------------------------------------------------------ #
# Authority gate
# ------------------------------------------------------------------ #

# Authority bands and their maximum allowed control magnitude.
_AUTHORITY_BANDS: List[Tuple[float, float]] = [
    (0.0, 0.0),   # 0.00–0.24: observe only
    (0.25, 0.1),  # 0.25–0.49: small perturbations
    (0.50, 0.4),  # 0.50–0.69: moderate control
    (0.70, 0.7),  # 0.70–0.89: significant control
    (0.90, 1.0),  # 0.90–1.00: full authority
]


class AuthorityGate:
    """
    Maps confidence/authority level → maximum allowed control magnitude.

    Prevents the system from taking large actions when confidence is low,
    providing a soft safety boundary on the control effort.
    """

    def __init__(
        self,
        authority_bands: Optional[List[Tuple[float, float]]] = None,
    ) -> None:
        """
        Args:
            authority_bands: list of (min_confidence, max_magnitude) tuples
                sorted by min_confidence ascending.
        """
        self._bands = authority_bands or _AUTHORITY_BANDS

    def get_authority_envelope(self, confidence: float) -> float:
        """
        Return the maximum allowed control magnitude for *confidence*.

        Args:
            confidence: scalar in [0.0, 1.0].

        Returns:
            Maximum control magnitude in [0.0, 1.0].
        """
        confidence = max(0.0, min(1.0, confidence))
        max_magnitude = 0.0
        for threshold, magnitude in self._bands:
            if confidence >= threshold:
                max_magnitude = magnitude
        return max_magnitude

    def apply(self, control: np.ndarray, confidence: float) -> np.ndarray:
        """
        Clip the control vector to the authority envelope.

        Args:
            control: u_t ∈ ℝ^n.
            confidence: current confidence/authority level in [0, 1].

        Returns:
            Clipped control vector.
        """
        envelope = self.get_authority_envelope(confidence)
        norm = float(np.linalg.norm(control))
        if norm > envelope and norm > 0:
            return control * (envelope / norm)
        return control.copy()
