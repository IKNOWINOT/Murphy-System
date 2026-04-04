"""
Formal Control Vector and Action Space for the Murphy System.

Defines:
  - ControlAction enum — every discrete action the system can take.
  - ControlVector — typed control output u_t ∈ U.
  - ControlLaw — feedback control  u_t = K_t × e_t  with gain scheduling.
"""

import logging
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from .canonical_state import _DIMENSION_NAMES, CanonicalStateVector

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
# Action space  U
# ------------------------------------------------------------------ #

class ControlAction(Enum):
    """Enumeration of all discrete actions the system can emit."""

    GENERATE = "generate"        # produce LLM / swarm candidates
    FILTER = "filter"            # prune candidates by constraint
    SELECT = "select"            # choose best candidate
    COMMIT = "commit"            # lock selection into state
    DEPLOY = "deploy"            # execute in production
    ASK_QUESTION = "ask_question"   # request more info (observation)
    ADD_CONSTRAINT = "add_constraint"  # tighten constraint set
    ESCALATE = "escalate"            # invoke human-in-the-loop
    REGENERATE = "regenerate"        # re-trigger LLM synthesis
    RECALIBRATE = "recalibrate"      # trigger learning / recalibration


# Authority required for each action (mirrors AuthorityController).
_ACTION_AUTHORITY: Dict[ControlAction, float] = {
    ControlAction.GENERATE: 0.0,
    ControlAction.FILTER: 0.3,
    ControlAction.SELECT: 0.5,
    ControlAction.COMMIT: 0.7,
    ControlAction.DEPLOY: 0.9,
    ControlAction.ASK_QUESTION: 0.0,
    ControlAction.ADD_CONSTRAINT: 0.3,
    ControlAction.ESCALATE: 0.0,
    ControlAction.REGENERATE: 0.3,
    ControlAction.RECALIBRATE: 0.5,
}


# ------------------------------------------------------------------ #
# Control vector  u_t
# ------------------------------------------------------------------ #

@dataclass
class ControlVector:
    """
    Typed control output u_t ∈ U.

    Attributes:
        action: the discrete control action to take.
        intensity: [0, 1] — how aggressively to apply the action.
        target_dimensions: which state dimensions this action intends to affect.
        parameters: action-specific payload.
    """

    action: ControlAction
    intensity: float = 1.0
    target_dimensions: List[str] = field(default_factory=list)
    parameters: Dict = field(default_factory=dict)

    @property
    def required_authority(self) -> float:
        """Minimum authority level to execute this control output."""
        return _ACTION_AUTHORITY.get(self.action, 1.0)

    def is_authorized(self, current_authority: float) -> bool:
        """True if *current_authority* is sufficient for this action."""
        return current_authority >= self.required_authority


# ------------------------------------------------------------------ #
# Control law   u_t = K_t × e_t
# ------------------------------------------------------------------ #

# Per-phase gain schedule  (mirrors mfgc_core Phase weights).
# Keys are phase indices 0-6, values are gain multipliers for the
# generative vs deterministic dimension groups.
_GAIN_SCHEDULE: Dict[int, Dict[str, float]] = {
    0: {"generative": 0.9, "deterministic": 0.1},  # EXPAND
    1: {"generative": 0.8, "deterministic": 0.2},  # TYPE
    2: {"generative": 0.6, "deterministic": 0.4},  # ENUMERATE
    3: {"generative": 0.4, "deterministic": 0.6},  # CONSTRAIN
    4: {"generative": 0.3, "deterministic": 0.7},  # COLLAPSE
    5: {"generative": 0.2, "deterministic": 0.8},  # BIND
    6: {"generative": 0.1, "deterministic": 0.9},  # EXECUTE
}

# Dimensions classified as "generative" or "deterministic"
_GENERATIVE_DIMS = {
    "confidence", "domain_depth", "artifact_count",
    "uncertainty_data", "uncertainty_information",
}
_DETERMINISTIC_DIMS = {
    "authority", "murphy_index", "gate_count",
    "active_constraints", "phase_index",
}


class ControlLaw:
    """
    Feedback control law:  u_t = K(phase) × (x_target - x_t)

    The gain matrix K is diagonal with per-dimension gains that are
    scheduled by the current MFGC phase.
    """

    def __init__(
        self,
        gain_schedule: Optional[Dict[int, Dict[str, float]]] = None,
        base_gain: float = 1.0,
    ):
        self.gain_schedule = gain_schedule or dict(_GAIN_SCHEDULE)
        self.base_gain = base_gain

    def compute_error(
        self,
        target: CanonicalStateVector,
        current: CanonicalStateVector,
    ) -> List[float]:
        """e_t = x_target - x_t  (element-wise)."""
        t_vec = target.to_vector()
        c_vec = current.to_vector()
        return [t - c for t, c in zip(t_vec, c_vec)]

    def gain_for_dimension(self, dim_name: str, phase_index: int) -> float:
        """Return the scalar gain K_i for dimension *dim_name* at *phase_index*."""
        schedule = self.gain_schedule.get(phase_index, {"generative": 0.5, "deterministic": 0.5})
        if dim_name in _GENERATIVE_DIMS:
            return self.base_gain * schedule["generative"]
        if dim_name in _DETERMINISTIC_DIMS:
            return self.base_gain * schedule["deterministic"]
        return self.base_gain * 0.5  # default for unclassified dims

    def compute_control(
        self,
        target: CanonicalStateVector,
        current: CanonicalStateVector,
    ) -> List[float]:
        """
        u_t = K(phase) × e_t   (element-wise diagonal gain).

        Returns a list of control signals, one per state dimension.
        """
        error = self.compute_error(target, current)
        phase = current.phase_index
        return [
            self.gain_for_dimension(dim, phase) * e
            for dim, e in zip(_DIMENSION_NAMES, error)
        ]

    def suggest_action(
        self,
        target: CanonicalStateVector,
        current: CanonicalStateVector,
    ) -> ControlVector:
        """
        Suggest the best discrete action based on the error vector.

        Heuristic: largest absolute error dimension determines action type.
        """
        error = self.compute_error(target, current)
        abs_error = [abs(e) for e in error]
        max_idx = abs_error.index(max(abs_error))
        dim_name = _DIMENSION_NAMES[max_idx]

        # Map dominant error dimension to a control action
        if dim_name in {"confidence", "domain_depth", "artifact_count"}:
            action = ControlAction.GENERATE
        elif dim_name in {"uncertainty_data", "uncertainty_information"}:
            action = ControlAction.ASK_QUESTION
        elif dim_name in {"gate_count", "active_constraints"}:
            action = ControlAction.ADD_CONSTRAINT
        elif dim_name == "murphy_index":
            action = ControlAction.RECALIBRATE
        elif dim_name == "authority":
            action = ControlAction.ESCALATE
        else:
            action = ControlAction.GENERATE

        intensity = min(1.0, abs_error[max_idx])
        return ControlVector(
            action=action,
            intensity=intensity,
            target_dimensions=[dim_name],
        )
