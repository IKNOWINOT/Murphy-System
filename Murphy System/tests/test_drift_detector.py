"""
Tests for DriftDetector (Gap B — automated drift detection).

Proves:
  - Monotonically decreasing entropy produces no alerts.
  - Increasing entropy triggers an alert.
  - Over-budget covariance dimensions trigger alerts.
  - check_all() aggregates both types.
"""

import sys
import os
import unittest
from datetime import datetime, timezone

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from control_theory.drift_detector import DriftAlert, DriftDetector
from control_theory.infinity_metric import EntropyTracker, UncertaintyBudget
from control_theory.state_model import StateDimension, StateVector


def _make_state(n: int = 3, variance: float = 0.05) -> StateVector:
    """Helper — create a simple n-dimensional state with diagonal covariance."""
    dims = [StateDimension(f"dim_{i}", bounds=(None, None)) for i in range(n)]
    cov = np.eye(n) * variance
    return StateVector(dims, initial_values=[0.5] * n, initial_covariance=cov)


def _tracker_with_history(values):
    """Build an EntropyTracker pre-loaded with given history values."""
    tracker = EntropyTracker()
    # Inject directly since record() computes from a covariance matrix.
    for v in values:
        tracker._history.append(v)
    return tracker


class TestDriftAlertDataclass(unittest.TestCase):
    def test_valid_alert_creation(self):
        alert = DriftAlert(
            alert_type="entropy_drift",
            dimension=None,
            severity="high",
            timestamp=datetime.now(timezone.utc),
            recommended_action="do something",
        )
        self.assertEqual(alert.alert_type, "entropy_drift")
        self.assertEqual(alert.severity, "high")

    def test_invalid_alert_type_raises(self):
        with self.assertRaises(ValueError):
            DriftAlert(
                alert_type="unknown",
                dimension=None,
                severity="low",
                timestamp=datetime.now(timezone.utc),
                recommended_action="",
            )

    def test_invalid_severity_raises(self):
        with self.assertRaises(ValueError):
            DriftAlert(
                alert_type="entropy_drift",
                dimension=None,
                severity="critical",
                timestamp=datetime.now(timezone.utc),
                recommended_action="",
            )


class TestEntropyDrift(unittest.TestCase):
    """Entropy-trajectory checks."""

    def test_decreasing_entropy_no_alert(self):
        """Monotonically decreasing entropy must produce no alert."""
        detector = DriftDetector()
        tracker = _tracker_with_history([2.0, 1.8, 1.5, 1.2, 0.9])
        alert = detector.check_entropy_drift(tracker)
        self.assertIsNone(alert)

    def test_constant_entropy_no_alert(self):
        """Constant entropy is not diverging."""
        detector = DriftDetector()
        tracker = _tracker_with_history([1.0, 1.0, 1.0, 1.0])
        alert = detector.check_entropy_drift(tracker)
        self.assertIsNone(alert)

    def test_increasing_entropy_triggers_alert(self):
        """Monotonically increasing entropy must trigger an alert."""
        detector = DriftDetector(entropy_threshold=0.01)
        tracker = _tracker_with_history([0.5, 0.7, 0.9, 1.1, 1.3])
        alert = detector.check_entropy_drift(tracker)
        self.assertIsNotNone(alert)
        self.assertEqual(alert.alert_type, "entropy_drift")
        self.assertIsNone(alert.dimension)

    def test_high_severity_on_large_increase(self):
        """Large net increase should produce a 'high' severity alert."""
        detector = DriftDetector(entropy_threshold=0.05, high_entropy_threshold=0.2)
        tracker = _tracker_with_history([0.0, 0.05, 0.15, 0.30, 0.50])
        alert = detector.check_entropy_drift(tracker)
        self.assertIsNotNone(alert)
        self.assertEqual(alert.severity, "high")

    def test_medium_severity_threshold(self):
        """Moderate increase should produce a 'medium' severity alert."""
        detector = DriftDetector(entropy_threshold=0.05, high_entropy_threshold=0.5)
        tracker = _tracker_with_history([0.0, 0.02, 0.06, 0.10, 0.12])
        alert = detector.check_entropy_drift(tracker)
        self.assertIsNotNone(alert)
        self.assertEqual(alert.severity, "medium")

    def test_insufficient_history_no_alert(self):
        """Need at least 2 history points to detect drift."""
        detector = DriftDetector()
        tracker = _tracker_with_history([1.0])
        alert = detector.check_entropy_drift(tracker)
        self.assertIsNone(alert)

    def test_empty_history_no_alert(self):
        """Empty history should not raise and should return None."""
        detector = DriftDetector()
        tracker = _tracker_with_history([])
        alert = detector.check_entropy_drift(tracker)
        self.assertIsNone(alert)

    def test_window_size_limits_window(self):
        """Only the last window_size entries are considered."""
        detector = DriftDetector(entropy_threshold=0.01)
        # Old values are increasing, last 3 are decreasing.
        tracker = _tracker_with_history([0.5, 0.7, 0.9, 1.0, 1.0, 0.9, 0.8])
        alert = detector.check_entropy_drift(tracker, window_size=3)
        self.assertIsNone(alert)


class TestCovarianceDrift(unittest.TestCase):
    """Covariance-against-budget checks."""

    def test_no_alert_when_within_budget(self):
        """All dimensions under budget → no alerts."""
        detector = DriftDetector()
        state = _make_state(n=2, variance=0.05)
        budget = UncertaintyBudget(default_budget=0.1)
        alerts = detector.check_covariance_drift(state, budget)
        self.assertEqual(alerts, [])

    def test_alert_when_over_budget(self):
        """Dimension exceeding budget triggers a covariance_drift alert."""
        detector = DriftDetector()
        state = _make_state(n=2, variance=0.5)
        budget = UncertaintyBudget(default_budget=0.1)
        alerts = detector.check_covariance_drift(state, budget)
        self.assertGreater(len(alerts), 0)
        for a in alerts:
            self.assertEqual(a.alert_type, "covariance_drift")
            self.assertIsNotNone(a.dimension)

    def test_only_over_budget_dims_alert(self):
        """Only the over-budget dimension fires an alert."""
        dims = [
            StateDimension("under_budget", bounds=(None, None)),
            StateDimension("over_budget", bounds=(None, None)),
        ]
        cov = np.diag([0.01, 0.5])
        state = StateVector(dims, initial_values=[0.0, 0.0], initial_covariance=cov)
        budget = UncertaintyBudget(default_budget=0.1)
        detector = DriftDetector()
        alerts = detector.check_covariance_drift(state, budget)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].dimension, "over_budget")

    def test_high_severity_on_2x_budget(self):
        """More than 2× budget should produce 'high' severity."""
        dims = [StateDimension("d", bounds=(None, None))]
        cov = np.array([[0.5]])  # budget = 0.1, excess = 0.4 > 0.1
        state = StateVector(dims, initial_values=[0.0], initial_covariance=cov)
        budget = UncertaintyBudget(default_budget=0.1)
        detector = DriftDetector()
        alerts = detector.check_covariance_drift(state, budget)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].severity, "high")


class TestCheckAll(unittest.TestCase):
    """check_all() aggregates entropy + covariance alerts."""

    def test_check_all_no_alerts(self):
        """No drift → empty list."""
        detector = DriftDetector()
        state = _make_state(n=2, variance=0.05)
        budget = UncertaintyBudget(default_budget=0.1)
        tracker = _tracker_with_history([1.0, 0.9, 0.8])
        alerts = detector.check_all(state, budget, tracker)
        self.assertEqual(alerts, [])

    def test_check_all_entropy_only(self):
        """Increasing entropy with in-budget covariance → entropy alert only."""
        detector = DriftDetector(entropy_threshold=0.01)
        state = _make_state(n=2, variance=0.05)
        budget = UncertaintyBudget(default_budget=0.1)
        tracker = _tracker_with_history([0.5, 0.7, 0.9])
        alerts = detector.check_all(state, budget, tracker)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].alert_type, "entropy_drift")

    def test_check_all_covariance_only(self):
        """Decreasing entropy with over-budget covariance → covariance alert."""
        detector = DriftDetector()
        state = _make_state(n=2, variance=0.5)
        budget = UncertaintyBudget(default_budget=0.1)
        tracker = _tracker_with_history([1.0, 0.9, 0.8])
        alerts = detector.check_all(state, budget, tracker)
        types = {a.alert_type for a in alerts}
        self.assertIn("covariance_drift", types)
        self.assertNotIn("entropy_drift", types)

    def test_check_all_both_alerts(self):
        """Both entropy drift and covariance drift fire together."""
        detector = DriftDetector(entropy_threshold=0.01)
        state = _make_state(n=2, variance=0.5)
        budget = UncertaintyBudget(default_budget=0.1)
        tracker = _tracker_with_history([0.5, 0.7, 0.9])
        alerts = detector.check_all(state, budget, tracker)
        types = {a.alert_type for a in alerts}
        self.assertIn("entropy_drift", types)
        self.assertIn("covariance_drift", types)

    def test_alerts_have_timestamps(self):
        """All alerts carry a UTC timestamp."""
        detector = DriftDetector(entropy_threshold=0.01)
        state = _make_state(n=1, variance=0.5)
        budget = UncertaintyBudget(default_budget=0.1)
        tracker = _tracker_with_history([0.5, 0.8])
        alerts = detector.check_all(state, budget, tracker)
        for a in alerts:
            self.assertIsInstance(a.timestamp, datetime)
            self.assertIsNotNone(a.timestamp.tzinfo)

    def test_alerts_have_recommended_actions(self):
        """All alerts carry a non-empty recommended_action string."""
        detector = DriftDetector(entropy_threshold=0.01)
        state = _make_state(n=1, variance=0.5)
        budget = UncertaintyBudget(default_budget=0.1)
        tracker = _tracker_with_history([0.5, 0.8])
        alerts = detector.check_all(state, budget, tracker)
        for a in alerts:
            self.assertIsInstance(a.recommended_action, str)
            self.assertGreater(len(a.recommended_action), 0)


if __name__ == "__main__":
    unittest.main()
