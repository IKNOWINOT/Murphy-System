# Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
# Design Label: FDD-003
"""Statistical FDD — CUSUM charts and regression-based baseline deviation."""

from __future__ import annotations

import math
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)


class CUSUMDetector:
    """Cumulative Sum control chart for drift detection.

    Tracks cumulative deviation from target mean. Signals when
    CUSUM exceeds threshold (indicating sustained drift).
    """

    def __init__(
        self,
        target_mean: float,
        threshold: float = 5.0,
        allowance: float = 0.5,
    ) -> None:
        self._lock = threading.RLock()
        self._target = target_mean
        self._threshold = threshold
        self._allowance = allowance  # slack parameter (k)
        self._cusum_pos: float = 0.0
        self._cusum_neg: float = 0.0
        self._observations: list = []
        self._alarms: list = []

    def add_observation(self, value: float) -> Dict:
        """Add new observation and return drift status."""
        with self._lock:
            capped_append(self._observations, value, 50_000)
            deviation = value - self._target
            self._cusum_pos = max(0, self._cusum_pos + deviation - self._allowance)
            self._cusum_neg = max(0, self._cusum_neg - deviation - self._allowance)

            alarm = None
            if self._cusum_pos > self._threshold:
                alarm = "upward_drift"
                capped_append(self._alarms, {"type": "upward_drift", "value": value, "cusum": self._cusum_pos})
            elif self._cusum_neg > self._threshold:
                alarm = "downward_drift"
                capped_append(self._alarms, {"type": "downward_drift", "value": value, "cusum": self._cusum_neg})

            return {
                "cusum_pos": round(self._cusum_pos, 4),
                "cusum_neg": round(self._cusum_neg, 4),
                "alarm": alarm,
                "observation_count": len(self._observations),
            }

    def reset(self) -> None:
        with self._lock:
            self._cusum_pos = 0.0
            self._cusum_neg = 0.0

    def get_alarms(self) -> List[Dict]:
        with self._lock:
            return list(self._alarms)


class RegressionBaseline:
    """Simple linear regression baseline for energy consumption.

    Fits y = a + b*x using ordinary least squares.
    Detects deviations when actual exceeds predicted by threshold.
    """

    def __init__(self, deviation_threshold_pct: float = 15.0) -> None:
        self._lock = threading.RLock()
        self._threshold_pct = deviation_threshold_pct
        self._x_data: list = []
        self._y_data: list = []
        self._slope: Optional[float] = None
        self._intercept: Optional[float] = None

    def add_training_point(self, x: float, y: float) -> None:
        with self._lock:
            capped_append(self._x_data, x, 50_000)
            capped_append(self._y_data, y, 50_000)
            self._fit()

    def _fit(self) -> None:
        """Recompute OLS coefficients."""
        n = len(self._x_data)
        if n < 2:
            return
        sx = sum(self._x_data)
        sy = sum(self._y_data)
        sxx = sum(xi * xi for xi in self._x_data)
        sxy = sum(xi * yi for xi, yi in zip(self._x_data, self._y_data))
        denom = n * sxx - sx * sx
        if abs(denom) < 1e-12:
            return
        self._slope = (n * sxy - sx * sy) / denom
        self._intercept = (sy - self._slope * sx) / n

    def predict(self, x: float) -> Optional[float]:
        with self._lock:
            if self._slope is None or self._intercept is None:
                return None
            return self._intercept + self._slope * x

    def check_deviation(self, x: float, actual_y: float) -> Dict:
        predicted = self.predict(x)
        if predicted is None:
            return {"deviation_pct": None, "fault": False, "predicted": None}
        if abs(predicted) < 1e-9:
            return {"deviation_pct": 0, "fault": False, "predicted": predicted}
        deviation_pct = ((actual_y - predicted) / abs(predicted)) * 100
        return {
            "deviation_pct": round(deviation_pct, 2),
            "fault": abs(deviation_pct) > self._threshold_pct,
            "predicted": round(predicted, 3),
            "actual": actual_y,
        }

    def get_coefficients(self) -> Dict:
        with self._lock:
            return {
                "slope": self._slope,
                "intercept": self._intercept,
                "training_points": len(self._x_data),
            }
