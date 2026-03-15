"""
State Transition Model for the Murphy System.

Defines:
  x_{t+1} = f(x_t, u_t, w_t)

Where:
  x_t  — current canonical state vector
  u_t  — control vector (from control_vector.py)
  w_t  — process noise (stochastic disturbance)
"""

import logging
import math
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .canonical_state import _DIMENSION_NAMES, CanonicalStateVector

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
# Process noise model  w_t ~ N(0, Q)
# ------------------------------------------------------------------ #

@dataclass(frozen=True)
class ProcessNoise:
    """
    Diagonal process noise  w_t ~ N(0, diag(variances)).

    Each element of *variances* is the variance σ²_i for the i-th state
    dimension in canonical order.
    """

    variances: tuple  # length must equal len(_DIMENSION_NAMES)

    @staticmethod
    def default() -> "ProcessNoise":
        """Small default process noise for all 25 dimensions."""
        return ProcessNoise(variances=tuple(0.001 for _ in _DIMENSION_NAMES))

    @staticmethod
    def zero() -> "ProcessNoise":
        """No process noise (deterministic transition)."""
        return ProcessNoise(variances=tuple(0.0 for _ in _DIMENSION_NAMES))

    def sample(self) -> List[float]:
        """Draw one noise vector w_t from N(0, Q)."""
        return [
            random.gauss(0.0, math.sqrt(max(v, 0.0))) for v in self.variances
        ]


# ------------------------------------------------------------------ #
# State transition function
# ------------------------------------------------------------------ #

# Bounds per dimension for clamping (matches CanonicalStateVector validators).
_DIM_BOUNDS: Dict[str, tuple] = {
    "confidence": (0.0, 1.0),
    "authority": (0.0, 1.0),
    "murphy_index": (0.0, 1.0),
    "phase_index": (0, 6),
    "complexity": (0.0, 1.0),
    "domain_depth": (0, None),
    "gate_count": (0, None),
    "active_constraints": (0, None),
    "artifact_count": (0, None),
    "uncertainty_data": (0.0, 1.0),
    "uncertainty_authority": (0.0, 1.0),
    "uncertainty_information": (0.0, 1.0),
    "uncertainty_resources": (0.0, 1.0),
    "uncertainty_disagreement": (0.0, 1.0),
    "uptime_seconds": (0.0, None),
    "active_tasks": (0, None),
    "cpu_usage_percent": (0.0, 100.0),
    # Extended dimensions (v1.1.0)
    "response_latency": (0.0, None),
    "domain_coverage": (0.0, 1.0),
    "constraint_violation_count": (0, None),
    "delegation_depth": (0, None),
    "feedback_recency": (0.0, None),
    "observation_staleness": (0.0, None),
    "llm_confidence_aggregate": (0.0, 1.0),
    "escalation_pending_count": (0, None),
}


def _clamp(value: float, dim: str) -> float:
    """Clamp *value* to the valid range for *dim*."""
    lo, hi = _DIM_BOUNDS.get(dim, (None, None))
    if lo is not None and value < lo:
        value = lo
    if hi is not None and value > hi:
        value = hi
    return value


class StateTransitionFunction:
    """
    x_{t+1} = f(x_t, u_t, w_t)

    Default dynamics:  x_{t+1}  =  clamp( x_t  +  u_t  +  w_t )

    The additive model is the simplest linearised form.  Subclass and
    override ``transition()`` for non-linear dynamics.
    """

    def __init__(self, noise: Optional[ProcessNoise] = None):
        self.noise = noise or ProcessNoise.default()

    def transition(
        self,
        state: CanonicalStateVector,
        control: List[float],
        *,
        add_noise: bool = True,
    ) -> CanonicalStateVector:
        """
        Compute x_{t+1} = clamp( x_t + u_t + w_t ).

        Args:
            state: current state x_t.
            control: control signal u_t (list of floats, one per dimension).
            add_noise: whether to add process noise w_t.

        Returns:
            Next state x_{t+1} as a new CanonicalStateVector.
        """
        x_t = state.to_vector()
        w_t = self.noise.sample() if add_noise else [0.0] * len(x_t)

        if len(control) != len(x_t):
            raise ValueError(
                f"Control vector length {len(control)} != state dimension {len(x_t)}"
            )

        x_next = []
        for i, dim in enumerate(_DIMENSION_NAMES):
            raw = x_t[i] + control[i] + w_t[i]
            x_next.append(_clamp(raw, dim))

        return CanonicalStateVector.from_vector(x_next)

    def predict(
        self,
        state: CanonicalStateVector,
        control: List[float],
        horizon: int = 1,
    ) -> List[CanonicalStateVector]:
        """
        Roll out *horizon* deterministic predictions (no noise).

        Returns a list of predicted states [x_{t+1}, x_{t+2}, …].
        """
        trajectory: List[CanonicalStateVector] = []
        current = state
        for _ in range(horizon):
            current = self.transition(current, control, add_noise=False)
            trajectory.append(current)
        return trajectory
