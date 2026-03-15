"""
Control Loop for the MFGC Control Plane (Gap CFP-3).

Defines:
- ``ControlVector`` — Pydantic model for the control signal u_t.
- ``ControlLaw`` — feedback law u_t = K(x_t, x_target).
- ``StabilityMonitor`` — detects confidence oscillation / instability.
- ``ControlAuthorityMatrix`` — (actor, action) → bool access control.
- ``StabilityViolation`` — exception raised on instability.
"""

from __future__ import annotations

import logging
from collections import deque
from typing import Deque, Dict, Optional, Tuple

from pydantic import BaseModel, Field

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

from .state_vector import StateVector

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
# Exceptions
# ------------------------------------------------------------------ #


class StabilityViolation(Exception):
    """Raised when the stability monitor detects unacceptable oscillation."""


# ------------------------------------------------------------------ #
# Control Vector
# ------------------------------------------------------------------ #


class ControlVector(BaseModel):
    """The set of actions the MFGC system can apply at each time step (u_t)."""

    ask_question: bool = False
    generate_candidates: bool = False
    evaluate_gate: bool = False
    advance_phase: bool = False
    request_human_intervention: bool = False
    execute_action: bool = False

    # Magnitudes for continuous dimensions (all ≥ 0)
    question_weight: float = Field(default=0.0, ge=0.0, le=1.0)
    action_intensity: float = Field(default=0.0, ge=0.0, le=1.0)

    model_config = {"extra": "forbid"}

    def is_null(self) -> bool:
        """Return True when no action is requested."""
        return not any(
            [
                self.ask_question,
                self.generate_candidates,
                self.evaluate_gate,
                self.advance_phase,
                self.request_human_intervention,
                self.execute_action,
            ]
        )


# ------------------------------------------------------------------ #
# Control Law  u_t = K(x_t, x_target)
# ------------------------------------------------------------------ #


class ControlLaw:
    """Proportional feedback law mapping state error to a control vector.

    ``u_t = K · (x_target − x_t)``

    The gain *K* is a scalar applied element-wise.  Actions are activated
    when the corresponding state error exceeds the configured threshold.
    """

    def __init__(self, gain: float = 1.0, threshold: float = 0.05) -> None:
        if gain <= 0:
            raise ValueError("gain must be > 0")
        self._gain = gain
        self._threshold = threshold

    def compute_control(
        self, state: StateVector, target: StateVector
    ) -> ControlVector:
        """Compute control vector u_t given current state and target.

        Args:
            state: Current system state x_t.
            target: Desired target state x_target.

        Returns:
            A :class:`ControlVector` whose boolean actions are activated
            wherever the state error exceeds the threshold.
        """
        error = target.diff(state)  # target - state (positive = need to increase)

        confidence_err = error.get("confidence", 0.0) * self._gain
        phase_err = error.get("phase", 0.0) * self._gain
        info_err = error.get("information_completeness", 0.0) * self._gain
        gate_err = error.get("verification_coverage", 0.0) * self._gain
        authority_err = error.get("authority", 0.0) * self._gain

        ask_q = abs(info_err) > self._threshold
        gen_candidates = abs(confidence_err) > self._threshold
        eval_gate = abs(gate_err) > self._threshold
        advance = phase_err > self._threshold
        request_hitl = abs(authority_err) > self._threshold * 2
        execute = (
            abs(confidence_err) <= self._threshold
            and abs(info_err) <= self._threshold
        )

        q_weight = min(1.0, abs(info_err))
        intensity = min(1.0, abs(confidence_err))

        return ControlVector(
            ask_question=ask_q,
            generate_candidates=gen_candidates,
            evaluate_gate=eval_gate,
            advance_phase=advance,
            request_human_intervention=request_hitl,
            execute_action=execute,
            question_weight=q_weight,
            action_intensity=intensity,
        )


# ------------------------------------------------------------------ #
# Stability Monitor
# ------------------------------------------------------------------ #


class StabilityMonitor:
    """Tracks the confidence trajectory and detects oscillation.

    An oscillation is counted each time the confidence direction reverses
    (increase → decrease or vice versa).  If the number of reversals
    exceeds *max_reversals* without a net improvement of at least
    *min_net_gain*, a :class:`StabilityViolation` is raised.
    """

    def __init__(
        self,
        max_reversals: int = 3,
        window: int = 10,
        min_net_gain: float = 0.01,
    ) -> None:
        self._max_reversals = max_reversals
        self._window = window
        self._min_net_gain = min_net_gain
        self._history: Deque[float] = deque(maxlen=window)
        self._reversal_count: int = 0
        self._last_direction: Optional[int] = None  # +1 or -1

    def record(self, confidence: float) -> None:
        """Record a new confidence reading.

        Raises:
            StabilityViolation: if oscillation exceeds the configured limit.
        """
        capped_append(self._history, confidence)
        if len(self._history) < 2:
            return

        history = list(self._history)
        delta = history[-1] - history[-2]
        direction = 1 if delta > 0 else (-1 if delta < 0 else 0)

        if direction != 0:
            if self._last_direction is not None and direction != self._last_direction:
                self._reversal_count += 1
            self._last_direction = direction

        if self._reversal_count >= self._max_reversals:
            net_gain = history[-1] - history[0]
            if net_gain < self._min_net_gain:
                raise StabilityViolation(
                    f"Confidence oscillated {self._reversal_count} times "
                    f"with net gain {net_gain:.4f} < {self._min_net_gain}"
                )

    def reset(self) -> None:
        """Reset internal state."""
        self._history.clear()
        self._reversal_count = 0
        self._last_direction = None

    @property
    def reversal_count(self) -> int:
        """Number of direction reversals observed so far."""
        return self._reversal_count


# ------------------------------------------------------------------ #
# Control Authority Matrix
# ------------------------------------------------------------------ #


class ControlAuthorityMatrix:
    """Maps ``(actor, action) -> bool`` based on current authority level.

    Authority levels:
        0 — observer only (read-only)
        1 — can ask questions, generate candidates
        2 — can evaluate gates, advance phases
        3 — can execute actions and request HITL
    """

    # Minimum authority level required per action
    _REQUIRED_AUTHORITY: Dict[str, int] = {
        "ask_question": 1,
        "generate_candidates": 1,
        "evaluate_gate": 2,
        "advance_phase": 2,
        "request_human_intervention": 3,
        "execute_action": 3,
    }

    def __init__(self) -> None:
        # actor_id -> authority_level
        self._actors: Dict[str, int] = {}
        # explicit overrides: (actor_id, action) -> bool
        self._overrides: Dict[Tuple[str, str], bool] = {}

    def register_actor(self, actor_id: str, authority_level: int) -> None:
        """Register an actor with the given authority level (0–3)."""
        self._actors[actor_id] = max(0, min(3, authority_level))

    def grant(self, actor_id: str, action: str) -> None:
        """Explicitly grant *action* to *actor_id* regardless of level."""
        self._overrides[(actor_id, action)] = True

    def revoke(self, actor_id: str, action: str) -> None:
        """Explicitly deny *action* for *actor_id* regardless of level."""
        self._overrides[(actor_id, action)] = False

    def is_permitted(self, actor_id: str, action: str) -> bool:
        """Return True if *actor_id* is allowed to perform *action*."""
        override = self._overrides.get((actor_id, action))
        if override is not None:
            return override
        level = self._actors.get(actor_id, 0)
        required = self._REQUIRED_AUTHORITY.get(action, 99)
        return level >= required

    def check_or_escalate(
        self,
        actor_id: str,
        action: str,
        registry=None,
        escalation_policy=None,
    ):
        """
        Return True when permitted, or attempt escalation when not.

        If *escalation_policy* and *registry* are both provided and
        ``is_permitted()`` returns False, escalation is triggered.

        Args:
            actor_id: the requesting actor.
            action: the action being requested.
            registry: ``ActorRegistry`` instance (required for escalation).
            escalation_policy: ``EscalationPolicy`` instance (optional).

        Returns:
            True if the actor is permitted directly, or ``EscalationResult``
            if escalation resolved, or False if neither succeeded.
        """
        if self.is_permitted(actor_id, action):
            return True
        if escalation_policy is not None and registry is not None:
            level = float(self._actors.get(actor_id, 0))
            depth = 0
            if escalation_policy.should_escalate(actor_id, action, level, depth):
                result = escalation_policy.escalate(actor_id, action, registry)
                if result is not None:
                    return result
        return False


__all__ = [
    "ControlVector",
    "ControlLaw",
    "StabilityMonitor",
    "StabilityViolation",
    "ControlAuthorityMatrix",
]
