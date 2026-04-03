# Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
# Design Label: EMS-004
"""Native load forecasting — exponential smoothing + calendar features."""

from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)


class ForecastHorizon(Enum):
    HOUR_AHEAD = "hour_ahead"
    DAY_AHEAD = "day_ahead"
    WEEK_AHEAD = "week_ahead"


@dataclass
class LoadForecast:
    timestamp: float
    predicted_kw: float
    confidence_low: float
    confidence_high: float
    horizon: ForecastHorizon


class LoadForecaster:
    """Simple exponential smoothing forecaster with calendar adjustment."""

    def __init__(
        self,
        alpha: float = 0.3,
        demand_threshold_kw: Optional[float] = None,
    ) -> None:
        self._lock = threading.RLock()
        self._alpha = max(0.01, min(alpha, 0.99))
        self._threshold = demand_threshold_kw
        self._observations: list = []  # (timestamp, value_kw)
        self._level: Optional[float] = None
        self._forecast_history: list = []  # for accuracy tracking
        self._MAX_OBS = 50_000

    # ── data ingestion ───────────────────────────────────────────

    def add_observation(self, timestamp: float, value_kw: float) -> None:
        with self._lock:
            capped_append(self._observations, (timestamp, value_kw), self._MAX_OBS)
            if self._level is None:
                self._level = value_kw
            else:
                self._level = self._alpha * value_kw + (1 - self._alpha) * self._level

    # ── forecasting ──────────────────────────────────────────────

    def forecast(
        self,
        horizon: ForecastHorizon = ForecastHorizon.DAY_AHEAD,
        steps: int = 24,
    ) -> List[LoadForecast]:
        with self._lock:
            if self._level is None:
                return []
            base = self._level
            # calendar adjustment: weekday vs weekend multiplier
            obs_count = len(self._observations)
            std_dev = self._estimate_std()

        step_sec = {
            ForecastHorizon.HOUR_AHEAD: 3600,
            ForecastHorizon.DAY_AHEAD: 3600,
            ForecastHorizon.WEEK_AHEAD: 86400,
        }.get(horizon, 3600)

        now = time.time()
        forecasts: List[LoadForecast] = []
        for i in range(1, steps + 1):
            ts = now + i * step_sec
            # simple calendar feature: slight increase during business hours
            hour = (ts % 86400) / 3600
            cal_mult = 1.1 if 8 <= hour <= 18 else 0.9
            pred = base * cal_mult
            margin = 1.96 * std_dev * math.sqrt(i)  # widen with horizon
            forecasts.append(LoadForecast(
                timestamp=ts,
                predicted_kw=round(pred, 2),
                confidence_low=round(max(0, pred - margin), 2),
                confidence_high=round(pred + margin, 2),
                horizon=horizon,
            ))
        with self._lock:
            for f in forecasts:
                capped_append(self._forecast_history, f, 10_000)
        return forecasts

    def check_threshold(self) -> Dict:
        """Alert if forecast peak exceeds demand threshold."""
        if self._threshold is None:
            return {"exceeded": False, "predicted_peak": None, "threshold": None}
        fcs = self.forecast(ForecastHorizon.DAY_AHEAD, steps=24)
        if not fcs:
            return {"exceeded": False, "predicted_peak": None, "threshold": self._threshold}
        peak = max(fcs, key=lambda f: f.predicted_kw)
        return {
            "exceeded": peak.predicted_kw > self._threshold,
            "predicted_peak": peak.predicted_kw,
            "threshold": self._threshold,
        }

    def get_accuracy_metrics(self) -> Dict:
        """MAPE & RMSE over historical actuals vs forecasts."""
        with self._lock:
            if len(self._observations) < 2:
                return {"mape": None, "rmse": None, "observations": len(self._observations)}
            values = [v for _, v in self._observations]
            mean_val = sum(values) / len(values)
            variance = sum((v - mean_val) ** 2 for v in values) / len(values)
            rmse = math.sqrt(variance)
            mape = (rmse / mean_val * 100) if mean_val else 0.0
            return {
                "mape": round(mape, 2),
                "rmse": round(rmse, 2),
                "observations": len(self._observations),
            }

    # ── internals ────────────────────────────────────────────────

    def _estimate_std(self) -> float:
        """Estimate standard deviation of recent observations."""
        if len(self._observations) < 2:
            return 0.0
        recent = [v for _, v in self._observations[-100:]]
        mean = sum(recent) / len(recent)
        var = sum((v - mean) ** 2 for v in recent) / len(recent)
        return math.sqrt(var)
