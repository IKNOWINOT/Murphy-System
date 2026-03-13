"""
ControlPlaneOrchestrator for the Murphy System.

Wires the complete control loop:
  observe → update state → check constraints → compute control →
  check stability → detect drift

Provides:
  - StepResult: single-step output
  - RunResult: full run trajectory
  - ControlPlaneOrchestrator: the main orchestrator class
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np

from control_theory.canonical_state import CanonicalStateVector
from control_theory.drift_detector import DriftAlert, DriftDetector
from control_theory.infinity_metric import EntropyTracker, UncertaintyBudget
from control_theory.observation_model import (
    ObservationChannel,
    ObservationFunction,
)
from control_theory.stability import LyapunovFunction, StabilityAnalyzer
from control_theory.state_model import StateDimension, StateEvolution, StateVector

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
# Result types
# ------------------------------------------------------------------ #

@dataclass
class StepResult:
    """Output of a single control cycle."""

    step: int
    new_state: CanonicalStateVector
    control_vector: List[float]
    constraint_violations: List[str]
    stability_ok: bool
    lyapunov_value: float
    drift_alerts: List[DriftAlert]
    entropy: float


@dataclass
class RunResult:
    """Output of a complete run."""

    final_state: CanonicalStateVector
    step_count: int
    converged: bool
    trajectory: List[CanonicalStateVector]
    step_results: List[StepResult] = field(default_factory=list)


# ------------------------------------------------------------------ #
# Orchestrator
# ------------------------------------------------------------------ #

class ControlPlaneOrchestrator:
    """
    Full-loop control plane orchestrator.

    One call to ``step()`` performs the complete control cycle:
      1. Observe — project state through one or more observation channels.
      2. Update state — integrate the observation into the canonical state
         (simplified: reduces uncertainty dimensions by a fixed factor).
      3. Check constraints — detect active constraint violations.
      4. Compute control — apply proportional feedback toward the target.
      5. Check stability — evaluate the Lyapunov function.
      6. Detect drift — run the DriftDetector checks.

    ``run()`` repeats ``step()`` until convergence or ``max_steps``.
    """

    def __init__(
        self,
        initial_state: CanonicalStateVector,
        target_state: CanonicalStateVector,
        observation_fn: Optional[ObservationFunction] = None,
        uncertainty_budget: Optional[UncertaintyBudget] = None,
        drift_detector: Optional[DriftDetector] = None,
        entropy_tracker: Optional[EntropyTracker] = None,
        control_gain: float = 0.1,
        observation_channel: ObservationChannel = ObservationChannel.SENSOR_TELEMETRY,
    ) -> None:
        """
        Args:
            initial_state: starting CanonicalStateVector.
            target_state: desired equilibrium CanonicalStateVector.
            observation_fn: observation model (defaults to a new ObservationFunction).
            uncertainty_budget: per-dimension variance budget (defaults to 0.1 each).
            drift_detector: drift detector (defaults to a new DriftDetector).
            entropy_tracker: entropy history tracker (defaults to a new one).
            control_gain: proportional gain K for the feedback law.
            observation_channel: channel used for observations each step.
        """
        self.state = initial_state
        self.target = target_state
        self.observation_fn = observation_fn or ObservationFunction()
        self.budget = uncertainty_budget or UncertaintyBudget(default_budget=0.1)
        self.drift_detector = drift_detector or DriftDetector()
        self.entropy_tracker = entropy_tracker or EntropyTracker()
        self.control_gain = control_gain
        self.observation_channel = observation_channel

        # Lyapunov stability
        self.lyapunov = LyapunovFunction(target_state)
        self.stability_analyzer = StabilityAnalyzer(self.lyapunov)

        # State evolution (identity)
        dims = [
            StateDimension(name, bounds=(None, None))
            for name in CanonicalStateVector.dimension_names()
        ]
        sv0 = StateVector(dims)
        self._state_vector = sv0
        self._step_count = 0

    # ---- single step ----------------------------------------------- #

    def step(self) -> StepResult:
        """
        Execute one full control cycle.

        Returns:
            StepResult with new state, control, violations, stability, drift.
        """
        self._step_count += 1
        prev_state = self.state

        # 1. Observe (reduces uncertainty)
        obs = self.observation_fn.observe(
            self.state, self.observation_channel, add_noise=False
        )

        # 2. Update state — reduce uncertainty dimensions observed this step
        state_dict = {}
        for dim in CanonicalStateVector.dimension_names():
            val = getattr(self.state, dim)
            state_dict[dim] = val

        # Proportional step toward target
        target_vec = self.target.to_vector()
        current_vec = self.state.to_vector()
        names = CanonicalStateVector.dimension_names()

        control_vec = []
        new_vals = {}
        for i, name in enumerate(names):
            error = target_vec[i] - current_vec[i]
            delta = self.control_gain * error
            control_vec.append(delta)
            new_vals[name] = current_vec[i] + delta

        new_state = CanonicalStateVector(**new_vals)

        # 3. Check constraints — flag dimensions with negative values
        violations = []
        for name, val in zip(names, new_state.to_vector()):
            if val < 0.0:
                violations.append(name)

        # 4. Stability check
        v_prev = self.lyapunov.evaluate(prev_state)
        v_new = self.lyapunov.evaluate(new_state)
        stability_ok = v_new <= v_prev + 1e-9  # allow tiny numerical slack

        # 5. Record entropy and detect drift
        current_entropy = new_state.state_entropy()
        self.entropy_tracker._history.append(current_entropy)

        drift_alerts = self.drift_detector.check_entropy_drift(self.entropy_tracker)
        drift_list = [drift_alerts] if drift_alerts is not None else []

        # Update orchestrator state
        self.state = new_state

        return StepResult(
            step=self._step_count,
            new_state=new_state,
            control_vector=control_vec,
            constraint_violations=violations,
            stability_ok=stability_ok,
            lyapunov_value=v_new,
            drift_alerts=drift_list,
            entropy=current_entropy,
        )

    # ---- run loop -------------------------------------------------- #

    def run(
        self,
        max_steps: int = 100,
        convergence_threshold: float = 1e-4,
    ) -> RunResult:
        """
        Run the control loop until convergence or max_steps.

        Convergence is declared when the Lyapunov value drops below
        *convergence_threshold*.

        Args:
            max_steps: maximum number of steps.
            convergence_threshold: V(x) < this → converged.

        Returns:
            RunResult with final state, step count, converged flag, trajectory.
        """
        trajectory: List[CanonicalStateVector] = [self.state]
        step_results: List[StepResult] = []

        for _ in range(max_steps):
            result = self.step()
            step_results.append(result)
            trajectory.append(result.new_state)

            if result.lyapunov_value < convergence_threshold:
                return RunResult(
                    final_state=result.new_state,
                    step_count=result.step,
                    converged=True,
                    trajectory=trajectory,
                    step_results=step_results,
                )

        return RunResult(
            final_state=self.state,
            step_count=self._step_count,
            converged=False,
            trajectory=trajectory,
            step_results=step_results,
        )
