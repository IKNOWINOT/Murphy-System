"""
Lyapunov Stability Analysis for the Murphy System.

Provides:
  - LyapunovFunction — a quadratic candidate  V(x) = (x - x*)ᵀ P (x - x*)
  - StabilityAnalyzer — checks  V(x_{t+1}) < V(x_t) and BIBO stability.
"""

import logging
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .canonical_state import _DIMENSION_NAMES, CanonicalStateVector

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
# Lyapunov candidate
# ------------------------------------------------------------------ #

class LyapunovFunction:
    """
    Quadratic Lyapunov candidate:

        V(x) = Σ_i  P_i × (x_i - x*_i)²

    where P is a diagonal positive-definite weight matrix and x* is the
    equilibrium (target) state.
    """

    def __init__(
        self,
        equilibrium: CanonicalStateVector,
        weights: Optional[List[float]] = None,
    ):
        """
        Args:
            equilibrium: target state x*.
            weights: diagonal of P (one per dimension). Defaults to all 1.0.
        """
        self.equilibrium = equilibrium
        n = equilibrium.dimensionality()
        self.weights = weights if weights is not None else [1.0] * n

        if len(self.weights) != n:
            raise ValueError(
                f"Weights length {len(self.weights)} != dimensionality {n}"
            )
        if any(w < 0.0 for w in self.weights):
            raise ValueError("All Lyapunov weights must be ≥ 0.")

    def evaluate(self, state: CanonicalStateVector) -> float:
        """
        V(x) = Σ_i  P_i × (x_i - x*_i)²

        Returns a non-negative scalar.  V(x*) = 0.
        """
        x = state.to_vector()
        x_star = self.equilibrium.to_vector()
        return sum(
            w * (xi - xs) ** 2
            for w, xi, xs in zip(self.weights, x, x_star)
        )

    def gradient(self, state: CanonicalStateVector) -> List[float]:
        """
        ∂V/∂x_i = 2 P_i (x_i - x*_i)
        """
        x = state.to_vector()
        x_star = self.equilibrium.to_vector()
        return [
            2.0 * w * (xi - xs)
            for w, xi, xs in zip(self.weights, x, x_star)
        ]

    def is_positive_definite(self) -> bool:
        """Check that the weight matrix P is positive definite (all weights > 0)."""
        return all(w > 0.0 for w in self.weights)


# ------------------------------------------------------------------ #
# Stability analysis
# ------------------------------------------------------------------ #

@dataclass
class StabilityResult:
    """Outcome of a single-step stability check."""

    v_current: float
    v_next: float
    delta_v: float            # V(x_{t+1}) - V(x_t)
    is_decreasing: bool       # delta_v < 0 ⟹ locally stable step
    state_bounded: bool       # all dims within known bounds


class StabilityAnalyzer:
    """
    Checks Lyapunov stability conditions over trajectories.

    A system is Lyapunov-stable around x* if V(x_{t+1}) < V(x_t) for
    all x ≠ x*.  We verify this empirically over observed or predicted
    trajectories.
    """

    def __init__(self, lyapunov: LyapunovFunction):
        self.lyapunov = lyapunov

    def check_step(
        self,
        current: CanonicalStateVector,
        next_state: CanonicalStateVector,
    ) -> StabilityResult:
        """Check single-step Lyapunov decrease."""
        v_curr = self.lyapunov.evaluate(current)
        v_next = self.lyapunov.evaluate(next_state)
        delta = v_next - v_curr
        bounded = self._check_bounds(next_state)
        return StabilityResult(
            v_current=v_curr,
            v_next=v_next,
            delta_v=delta,
            is_decreasing=delta < 0.0,
            state_bounded=bounded,
        )

    def check_trajectory(
        self,
        trajectory: List[CanonicalStateVector],
    ) -> Tuple[bool, List[StabilityResult]]:
        """
        Verify Lyapunov decrease along an entire trajectory.

        Returns (all_decreasing, list_of_results).
        """
        if len(trajectory) < 2:
            return True, []
        results: List[StabilityResult] = []
        all_ok = True
        for i in range(len(trajectory) - 1):
            res = self.check_step(trajectory[i], trajectory[i + 1])
            results.append(res)
            if not res.is_decreasing:
                all_ok = False
        return all_ok, results

    def is_bibo_stable(
        self,
        trajectory: List[CanonicalStateVector],
    ) -> bool:
        """
        Bounded-Input Bounded-Output (BIBO) stability.

        True if every state in the trajectory remains within its valid
        dimension bounds.
        """
        return all(self._check_bounds(s) for s in trajectory)

    # ---- internal -------------------------------------------------- #

    @staticmethod
    def _check_bounds(state: CanonicalStateVector) -> bool:
        """True if all dimensions are within their declared bounds."""
        return (
            0.0 <= state.confidence <= 1.0
            and 0.0 <= state.authority <= 1.0
            and 0.0 <= state.murphy_index <= 1.0
            and 0 <= state.phase_index <= 6
            and 0.0 <= state.complexity <= 1.0
            and state.domain_depth >= 0
            and state.gate_count >= 0
            and state.active_constraints >= 0
            and state.artifact_count >= 0
            and 0.0 <= state.uncertainty_data <= 1.0
            and 0.0 <= state.uncertainty_authority <= 1.0
            and 0.0 <= state.uncertainty_information <= 1.0
            and 0.0 <= state.uncertainty_resources <= 1.0
            and 0.0 <= state.uncertainty_disagreement <= 1.0
            and state.uptime_seconds >= 0.0
            and state.active_tasks >= 0
            and state.cpu_usage_percent >= 0.0
        )
