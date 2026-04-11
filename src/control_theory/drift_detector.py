"""
Automated Drift Detector for the Murphy System.

Monitors entropy trajectory and state covariance for divergence from
acceptable operating bounds, firing DriftAlert events when anomalies
are detected.

Extended with manifold-aware drift detection (Design Label: DRIFT-MANIFOLD-001)
that detects correlated multi-dimensional drift from a target manifold surface.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional

import numpy as np

from .infinity_metric import EntropyTracker, UncertaintyBudget
from .state_model import StateVector

logger = logging.getLogger(__name__)

# Feature flag for manifold drift detection
MANIFOLD_DRIFT_ENABLED: bool = os.environ.get("MURPHY_MANIFOLD_DRIFT", "0") == "1"

# Valid alert types (extended to include manifold_drift)
_VALID_ALERT_TYPES = ("entropy_drift", "covariance_drift", "manifold_drift")


# ------------------------------------------------------------------ #
# Alert types
# ------------------------------------------------------------------ #

@dataclass
class DriftAlert:
    """Fired when the system drifts outside acceptable operating bounds."""

    alert_type: str          # "entropy_drift" | "covariance_drift" | "manifold_drift"
    dimension: Optional[str]  # None for entropy/manifold alerts
    severity: str            # "low" | "medium" | "high"
    timestamp: datetime
    recommended_action: str

    def __post_init__(self) -> None:
        if self.alert_type not in _VALID_ALERT_TYPES:
            raise ValueError(
                f"Unknown alert_type '{self.alert_type}'. "
                f"Expected one of {_VALID_ALERT_TYPES}."
            )
        if self.severity not in ("low", "medium", "high"):
            raise ValueError(
                f"Unknown severity '{self.severity}'. "
                "Expected 'low', 'medium', or 'high'."
            )


@dataclass
class ManifoldDriftAlert(DriftAlert):
    """
    Extended alert for manifold drift.
    Design Label: DRIFT-MANIFOLD-002

    Includes the distance from the manifold surface and a recommended
    retraction vector to bring the state back on-manifold.
    """

    manifold_distance: float = 0.0
    retraction_vector: Optional[List[float]] = None

    def __post_init__(self) -> None:
        # Force alert_type for manifold drift alerts
        object.__setattr__(self, "alert_type", "manifold_drift")
        super().__post_init__()


# ------------------------------------------------------------------ #
# Drift detector
# ------------------------------------------------------------------ #

class DriftDetector:
    """
    Monitors entropy and covariance for divergence.

    Usage::

        detector = DriftDetector(entropy_threshold=0.05)
        alerts = detector.check_all(state, budget, entropy_tracker)
    """

    def __init__(
        self,
        entropy_threshold: float = 0.05,
        high_entropy_threshold: float = 0.2,
    ) -> None:
        """
        Args:
            entropy_threshold: minimum entropy increase across the window
                that counts as drift (used in ``check_entropy_drift``).
            high_entropy_threshold: larger increase that elevates severity
                to "high".
        """
        self.entropy_threshold = entropy_threshold
        self.high_entropy_threshold = high_entropy_threshold

    # ---- entropy drift --------------------------------------------- #

    def check_entropy_drift(
        self,
        entropy_tracker: EntropyTracker,
        tolerance: float = 0.0,
        window_size: int = 5,
    ) -> Optional[DriftAlert]:
        """
        Detect monotonically increasing entropy over the last *window_size* steps.

        Args:
            entropy_tracker: tracker whose ``history`` list is inspected.
            tolerance: per-step increase that is tolerated before counting
                as drift (default 0 — any increase triggers).
            window_size: how many recent history points to evaluate.

        Returns:
            A ``DriftAlert`` if entropy is increasing, else ``None``.
        """
        history = entropy_tracker.history
        if len(history) < 2:
            return None

        window = history[-window_size:] if len(history) >= window_size else history
        if len(window) < 2:
            return None

        # Check if entropy is trending upward (net increase over window).
        net_increase = window[-1] - window[0]
        if net_increase <= tolerance:
            return None

        severity = (
            "high" if net_increase >= self.high_entropy_threshold
            else "medium" if net_increase >= self.entropy_threshold
            else "low"
        )
        return DriftAlert(
            alert_type="entropy_drift",
            dimension=None,
            severity=severity,
            timestamp=datetime.now(timezone.utc),
            recommended_action=(
                "Increase observation frequency to reduce state uncertainty. "
                "Consider running the AdaptiveObserver entropy-reduction loop."
            ),
        )

    # ---- covariance drift ------------------------------------------ #

    def check_covariance_drift(
        self,
        state: StateVector,
        budget: UncertaintyBudget,
    ) -> List[DriftAlert]:
        """
        Check each state dimension against its uncertainty budget.

        Args:
            state: current StateVector whose covariance diagonal is checked.
            budget: per-dimension maximum acceptable variance.

        Returns:
            List of DriftAlerts, one per over-budget dimension.
        """
        alerts: List[DriftAlert] = []
        variances = state.get_uncertainty()  # np.ndarray — diag(P)

        for i, name in enumerate(state.dimension_names):
            variance = float(variances[i])
            if budget.over_budget(name, variance):
                budget_val = budget.get_budget(name)
                excess = variance - budget_val
                severity = (
                    "high" if excess > budget_val  # more than 2× budget
                    else "medium" if excess > budget_val * 0.5
                    else "low"
                )
                alerts.append(
                    DriftAlert(
                        alert_type="covariance_drift",
                        dimension=name,
                        severity=severity,
                        timestamp=datetime.now(timezone.utc),
                        recommended_action=(
                            f"Dimension '{name}' variance {variance:.4f} exceeds "
                            f"budget {budget_val:.4f}. "
                            "Direct an observation toward this dimension."
                        ),
                    )
                )
        return alerts

    # ---- combined check -------------------------------------------- #

    def check_all(
        self,
        state: StateVector,
        budget: UncertaintyBudget,
        entropy_tracker: EntropyTracker,
        entropy_tolerance: float = 0.0,
        window_size: int = 5,
    ) -> List[DriftAlert]:
        """
        Run all drift checks and return the combined list of alerts.

        Args:
            state: current StateVector.
            budget: per-dimension uncertainty budget.
            entropy_tracker: entropy history.
            entropy_tolerance: per-step increase tolerated before alerting.
            window_size: window for entropy drift check.

        Returns:
            Aggregated list of DriftAlerts (entropy + covariance).
        """
        alerts: List[DriftAlert] = []

        entropy_alert = self.check_entropy_drift(
            entropy_tracker,
            tolerance=entropy_tolerance,
            window_size=window_size,
        )
        if entropy_alert is not None:
            alerts.append(entropy_alert)

        alerts.extend(self.check_covariance_drift(state, budget))
        return alerts


# ------------------------------------------------------------------ #
# Manifold-aware drift detector
# ------------------------------------------------------------------ #

class ManifoldDriftDetector:
    """
    Detects drift from a target manifold surface.
    Design Label: DRIFT-MANIFOLD-003

    Extends traditional axis-aligned drift detection with manifold-aware
    checks that catch *correlated* multi-dimensional drift (e.g., two
    dimensions drifting in opposite directions that cancel on each axis
    but move off-manifold).

    Falls back to the base DriftDetector when manifold detection is
    disabled or the manifold is not configured.

    Usage::

        from control_theory.manifold_projection import SphereManifold
        detector = ManifoldDriftDetector(
            manifold=SphereManifold(radius=1.0),
            tolerance=0.05,
        )
        alerts = detector.check_manifold_drift(state_vector)
    """

    def __init__(
        self,
        manifold=None,
        tolerance: float = 0.05,
        high_tolerance: float = 0.2,
        enabled: Optional[bool] = None,
    ) -> None:
        """
        Args:
            manifold: Manifold instance (from manifold_projection.py).
            tolerance: distance threshold for "medium" severity alert.
            high_tolerance: distance threshold for "high" severity alert.
            enabled: override for feature flag.
        """
        self.manifold = manifold
        self.tolerance = tolerance
        self.high_tolerance = high_tolerance
        self.enabled = enabled if enabled is not None else MANIFOLD_DRIFT_ENABLED

    def check_manifold_drift(
        self,
        state_values: "np.ndarray",
    ) -> Optional[ManifoldDriftAlert]:
        """
        Check if the state has drifted off the target manifold.

        Args:
            state_values: numeric state vector as numpy array.

        Returns:
            ManifoldDriftAlert if drift exceeds tolerance, else None.
        """
        if not self.enabled or self.manifold is None:
            return None

        try:
            distance = self.manifold.distance_to_manifold(state_values)

            if distance <= self.tolerance:
                return None

            severity = "high" if distance >= self.high_tolerance else "medium"

            # Compute retraction vector (direction back to manifold)
            projected = self.manifold.project(state_values)
            retraction = (projected - state_values).tolist()

            return ManifoldDriftAlert(
                alert_type="manifold_drift",
                dimension=None,
                severity=severity,
                timestamp=datetime.now(timezone.utc),
                recommended_action=(
                    f"State has drifted {distance:.4f} from the target manifold "
                    f"(tolerance={self.tolerance:.4f}). "
                    "Apply manifold retraction to re-project state."
                ),
                manifold_distance=distance,
                retraction_vector=retraction,
            )
        except Exception as exc:  # DRIFT-MANIFOLD-ERR-001
            logger.warning(
                "DRIFT-MANIFOLD-ERR-001: Manifold drift check failed (%s)",
                exc,
            )
            return None

    def check_trajectory_drift(
        self,
        trajectory: List["np.ndarray"],
        window_size: int = 5,
    ) -> List[ManifoldDriftAlert]:
        """
        Check a trajectory of state vectors for manifold drift.

        Fires alerts for any state in the recent window that exceeds
        the tolerance.

        Args:
            trajectory: list of state vectors.
            window_size: how many recent states to check.

        Returns:
            List of ManifoldDriftAlerts (may be empty).
        """
        if not self.enabled or self.manifold is None or not trajectory:
            return []

        alerts: List[ManifoldDriftAlert] = []
        window = trajectory[-window_size:]
        for state_values in window:
            alert = self.check_manifold_drift(state_values)
            if alert is not None:
                alerts.append(alert)
        return alerts
