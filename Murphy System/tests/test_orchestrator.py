"""
Tests for ControlPlaneOrchestrator (Gap G — production wiring of the full loop).

Proves:
  - step() returns a StepResult with all required fields.
  - run() converges toward the target with decreasing Lyapunov function.
  - Entropy is tracked across the run.
  - Full integration: observe → update → constraints → control → stability → drift.
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from control_theory.canonical_state import CanonicalStateVector
from control_theory.drift_detector import DriftDetector
from control_theory.infinity_metric import EntropyTracker, UncertaintyBudget
from control_theory.observation_model import ObservationChannel, ObservationFunction
from control_plane.orchestrator import (
    ControlPlaneOrchestrator,
    RunResult,
    StepResult,
)


def _make_orchestrator(
    confidence_start: float = 0.1,
    confidence_target: float = 0.9,
    control_gain: float = 0.2,
) -> ControlPlaneOrchestrator:
    """Helper — build an orchestrator moving confidence toward the target."""
    initial = CanonicalStateVector(confidence=confidence_start)
    target = CanonicalStateVector(confidence=confidence_target)
    return ControlPlaneOrchestrator(
        initial_state=initial,
        target_state=target,
        control_gain=control_gain,
    )


class TestStepResult(unittest.TestCase):
    """StepResult has all required fields."""

    def test_step_result_fields_present(self):
        orch = _make_orchestrator()
        result = orch.step()
        self.assertIsInstance(result, StepResult)
        self.assertIsInstance(result.new_state, CanonicalStateVector)
        self.assertIsInstance(result.control_vector, list)
        self.assertIsInstance(result.constraint_violations, list)
        self.assertIsInstance(result.stability_ok, bool)
        self.assertIsInstance(result.lyapunov_value, float)
        self.assertIsInstance(result.drift_alerts, list)
        self.assertIsInstance(result.entropy, float)

    def test_control_vector_has_correct_length(self):
        orch = _make_orchestrator()
        result = orch.step()
        self.assertEqual(len(result.control_vector), 25)

    def test_step_counter_increments(self):
        orch = _make_orchestrator()
        r1 = orch.step()
        r2 = orch.step()
        self.assertEqual(r1.step, 1)
        self.assertEqual(r2.step, 2)

    def test_new_state_is_canonical_state_vector(self):
        orch = _make_orchestrator()
        result = orch.step()
        self.assertIsInstance(result.new_state, CanonicalStateVector)


class TestStabilityProperties(unittest.TestCase):
    """Stability check verifies Lyapunov decrease."""

    def test_moving_toward_target_is_stable(self):
        """With positive gain toward target, each step should be stable."""
        orch = _make_orchestrator(confidence_start=0.1, confidence_target=0.9, control_gain=0.1)
        for _ in range(5):
            result = orch.step()
            self.assertTrue(result.stability_ok, "Each step moving toward target must be stable")

    def test_lyapunov_decreases_toward_target(self):
        """Lyapunov value should decrease as state moves toward target."""
        orch = _make_orchestrator(confidence_start=0.0, confidence_target=1.0, control_gain=0.2)
        lyapunov_values = []
        for _ in range(10):
            result = orch.step()
            lyapunov_values.append(result.lyapunov_value)
        # Overall trend: decreasing
        self.assertLess(lyapunov_values[-1], lyapunov_values[0])


class TestRunResult(unittest.TestCase):
    """run() returns a RunResult with trajectory."""

    def test_run_result_fields_present(self):
        orch = _make_orchestrator()
        result = orch.run(max_steps=5)
        self.assertIsInstance(result, RunResult)
        self.assertIsInstance(result.final_state, CanonicalStateVector)
        self.assertIsInstance(result.step_count, int)
        self.assertIsInstance(result.converged, bool)
        self.assertIsInstance(result.trajectory, list)
        self.assertIsInstance(result.step_results, list)

    def test_trajectory_has_correct_length(self):
        """Trajectory length = steps taken + 1 (initial state)."""
        orch = _make_orchestrator()
        result = orch.run(max_steps=5, convergence_threshold=1e-10)
        self.assertEqual(len(result.trajectory), result.step_count + 1)
        self.assertEqual(len(result.step_results), result.step_count)

    def test_run_converges_near_target(self):
        """With enough steps, the system converges (Lyapunov near 0)."""
        orch = _make_orchestrator(
            confidence_start=0.0,
            confidence_target=1.0,
            control_gain=0.5,
        )
        result = orch.run(max_steps=200, convergence_threshold=1e-4)
        self.assertTrue(result.converged)

    def test_run_reports_non_convergence_when_steps_exhausted(self):
        """With only 1 step and a tight threshold, should NOT converge."""
        orch = _make_orchestrator(confidence_start=0.0, confidence_target=1.0, control_gain=0.01)
        result = orch.run(max_steps=1, convergence_threshold=1e-10)
        self.assertFalse(result.converged)
        self.assertEqual(result.step_count, 1)

    def test_final_state_closer_to_target(self):
        """Final state should be closer to target than initial state."""
        initial = CanonicalStateVector(confidence=0.0)
        target = CanonicalStateVector(confidence=1.0)
        orch = ControlPlaneOrchestrator(
            initial_state=initial,
            target_state=target,
            control_gain=0.1,
        )
        result = orch.run(max_steps=20)
        initial_error = abs(initial.confidence - target.confidence)
        final_error = abs(result.final_state.confidence - target.confidence)
        self.assertLess(final_error, initial_error)


class TestEntropyTracking(unittest.TestCase):
    """Entropy is tracked across the run."""

    def test_entropy_recorded_each_step(self):
        orch = _make_orchestrator()
        result = orch.run(max_steps=5, convergence_threshold=1e-10)
        history = orch.entropy_tracker.history
        self.assertGreaterEqual(len(history), result.step_count)

    def test_each_step_result_has_entropy(self):
        orch = _make_orchestrator()
        result = orch.run(max_steps=3, convergence_threshold=1e-10)
        for sr in result.step_results:
            self.assertIsInstance(sr.entropy, float)
            self.assertGreaterEqual(sr.entropy, 0.0)


class TestDriftDetection(unittest.TestCase):
    """Drift alerts are surfaced in step results."""

    def test_drift_alerts_field_is_list(self):
        orch = _make_orchestrator()
        result = orch.step()
        self.assertIsInstance(result.drift_alerts, list)

    def test_no_drift_alerts_on_first_step(self):
        """First step has insufficient history for entropy drift detection."""
        orch = _make_orchestrator()
        result = orch.step()
        # First step: history has only 1 entry → no entropy drift alert
        self.assertEqual(len(result.drift_alerts), 0)


class TestIntegrationFullLoop(unittest.TestCase):
    """Full integration test: all 6 stages run correctly."""

    def test_full_loop_end_to_end(self):
        """Run the complete loop and verify trajectory converges."""
        initial = CanonicalStateVector(
            confidence=0.1,
            authority=0.2,
            complexity=0.8,
        )
        target = CanonicalStateVector(
            confidence=0.9,
            authority=0.8,
            complexity=0.1,
        )
        budget = UncertaintyBudget(default_budget=0.5)
        drift_det = DriftDetector(entropy_threshold=0.1)
        tracker = EntropyTracker()

        orch = ControlPlaneOrchestrator(
            initial_state=initial,
            target_state=target,
            uncertainty_budget=budget,
            drift_detector=drift_det,
            entropy_tracker=tracker,
            control_gain=0.3,
        )
        result = orch.run(max_steps=50, convergence_threshold=1e-3)

        # Trajectory should be non-trivial
        self.assertGreater(len(result.trajectory), 1)
        # Final state should be closer to target on confidence
        self.assertGreater(result.final_state.confidence, initial.confidence)
        # Lyapunov function of final state should be less than initial
        final_lyap = orch.lyapunov.evaluate(result.final_state)
        initial_lyap = orch.lyapunov.evaluate(initial)
        self.assertLess(final_lyap, initial_lyap)


if __name__ == "__main__":
    unittest.main()
