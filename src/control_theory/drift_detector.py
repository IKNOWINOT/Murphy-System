"""
Automated Drift Detector for the Murphy System.

Monitors entropy trajectory and state covariance for divergence from
acceptable operating bounds, firing DriftAlert events when anomalies
are detected.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional

from .infinity_metric import EntropyTracker, UncertaintyBudget
from .state_model import StateVector

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
# Alert types
# ------------------------------------------------------------------ #

@dataclass
class DriftAlert:
    """Fired when the system drifts outside acceptable operating bounds."""

    alert_type: str          # "entropy_drift" | "covariance_drift"
    dimension: Optional[str]  # None for entropy alerts
    severity: str            # "low" | "medium" | "high"
    timestamp: datetime
    recommended_action: str

    def __post_init__(self) -> None:
        if self.alert_type not in ("entropy_drift", "covariance_drift"):
            raise ValueError(
                f"Unknown alert_type '{self.alert_type}'. "
                "Expected 'entropy_drift' or 'covariance_drift'."
            )
        if self.severity not in ("low", "medium", "high"):
            raise ValueError(
                f"Unknown severity '{self.severity}'. "
                "Expected 'low', 'medium', or 'high'."
            )


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
