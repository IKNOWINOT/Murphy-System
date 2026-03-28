"""
Error Calibrator — Murphy System

Compares expected returns vs actual returns for each strategy.
When divergence exceeds a threshold, triggers recalibration:
  - Adjusts strategy parameters
  - Logs the error and correction
  - Alerts if systematic errors are detected

Maintains per-strategy error profiles and calibration history.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import math
import statistics
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(lst: list, item: Any, max_size: int = 10_000) -> None:  # type: ignore[misc]
        if len(lst) >= max_size:
            del lst[: max_size // 10]
        lst.append(item)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ReturnObservation:
    """One strategy prediction compared against its actual outcome."""
    obs_id:          str
    strategy:        str
    symbol:          str
    timestamp:       float
    predicted_return: float   # what the strategy signalled it expected
    actual_return:    float   # what really happened
    divergence:       float   # actual - predicted
    divergence_pct:   float   # divergence / abs(predicted) if predicted != 0


@dataclass
class CalibrationEvent:
    """Recorded whenever a recalibration is triggered for a strategy."""
    event_id:    str
    strategy:    str
    timestamp:   float
    reason:      str
    trigger:     str          # "threshold_breach" | "systematic_bias" | "manual"
    old_params:  Dict[str, Any]
    new_params:  Dict[str, Any]
    bias_before: float
    bias_after:  float
    notes:       str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id":   self.event_id,
            "strategy":   self.strategy,
            "timestamp":  self.timestamp,
            "reason":     self.reason,
            "trigger":    self.trigger,
            "old_params": self.old_params,
            "new_params": self.new_params,
            "bias_before": round(self.bias_before, 6),
            "bias_after":  round(self.bias_after,  6),
            "notes":       self.notes,
        }


@dataclass
class StrategyErrorProfile:
    """Accumulated error statistics for a single strategy."""
    strategy:        str
    observations:    deque = field(default_factory=lambda: deque(maxlen=500))
    calibration_history: List[CalibrationEvent] = field(default_factory=list)
    bias:            float = 0.0     # rolling mean divergence
    mae:             float = 0.0     # mean absolute error
    rmse:            float = 0.0     # root mean squared error
    last_calibrated: float = 0.0
    recalibration_count: int = 0


# ---------------------------------------------------------------------------
# ErrorCalibrator
# ---------------------------------------------------------------------------

class ErrorCalibrator:
    """
    Tracks and corrects systematic prediction errors across trading strategies.

    For each strategy, it maintains a rolling window of (predicted, actual)
    return pairs.  When the rolling mean divergence exceeds `divergence_threshold`,
    it fires a recalibration callback and logs the event.
    """

    def __init__(
        self,
        window_size:           int   = 50,
        divergence_threshold:  float = 0.02,    # 2 % mean divergence triggers recal
        bias_alert_threshold:  float = 0.05,    # 5 % systematic bias fires alert
        min_observations:      int   = 10,      # min obs before calibration fires
        recal_cooldown_secs:   float = 300.0,   # 5-min cooldown between recals
    ) -> None:
        self._lock                  = threading.RLock()
        self.window_size            = window_size
        self.divergence_threshold   = divergence_threshold
        self.bias_alert_threshold   = bias_alert_threshold
        self.min_observations       = min_observations
        self.recal_cooldown_secs    = recal_cooldown_secs

        self._profiles: Dict[str, StrategyErrorProfile] = {}
        self._global_history: List[ReturnObservation]   = []
        self._alerts: List[Dict[str, Any]]               = []

        # Optional external recalibration hook:
        # set to a callable(strategy, old_params) → new_params
        self.recalibration_hook: Optional[Callable[[str, Dict], Dict]] = None

    # ------------------------------------------------------------------
    # Observation recording
    # ------------------------------------------------------------------

    def record_outcome(
        self,
        strategy:         str,
        symbol:           str,
        predicted_return: float,
        actual_return:    float,
    ) -> ReturnObservation:
        """
        Log an actual trade outcome against the strategy's prediction.
        Triggers recalibration automatically if thresholds are breached.
        """
        with self._lock:
            profile = self._get_or_create_profile(strategy)
            divergence     = actual_return - predicted_return
            denom          = abs(predicted_return) if abs(predicted_return) > 1e-9 else 1.0
            divergence_pct = divergence / denom

            obs = ReturnObservation(
                obs_id=str(uuid.uuid4()),
                strategy=strategy, symbol=symbol,
                timestamp=time.time(),
                predicted_return=predicted_return,
                actual_return=actual_return,
                divergence=divergence,
                divergence_pct=divergence_pct,
            )
            profile.observations.append(obs)
            capped_append(self._global_history, obs)
            self._update_profile_stats(profile)
            self._check_calibration_trigger(profile)

            logger.debug("ErrorCalibrator: strategy=%s divergence=%.4f bias=%.4f",
                         strategy, divergence, profile.bias)
            return obs

    # ------------------------------------------------------------------
    # Profile stats
    # ------------------------------------------------------------------

    def _get_or_create_profile(self, strategy: str) -> StrategyErrorProfile:
        if strategy not in self._profiles:
            self._profiles[strategy] = StrategyErrorProfile(strategy=strategy)
        return self._profiles[strategy]

    def _update_profile_stats(self, profile: StrategyErrorProfile) -> None:
        obs = list(profile.observations)
        if not obs:
            return
        divs = [o.divergence for o in obs]
        profile.bias = statistics.mean(divs)
        profile.mae  = statistics.mean([abs(d) for d in divs])
        profile.rmse = math.sqrt(statistics.mean([d ** 2 for d in divs]))

    # ------------------------------------------------------------------
    # Calibration trigger
    # ------------------------------------------------------------------

    def _check_calibration_trigger(self, profile: StrategyErrorProfile) -> None:
        obs = list(profile.observations)
        if len(obs) < self.min_observations:
            return

        now   = time.time()
        since = now - profile.last_calibrated
        if since < self.recal_cooldown_secs:
            return

        # Trigger conditions
        abs_bias = abs(profile.bias)
        if abs_bias > self.divergence_threshold:
            self._trigger_recalibration(profile, "threshold_breach",
                                        f"Bias {abs_bias:.4f} exceeds threshold {self.divergence_threshold:.4f}")
        elif abs_bias > self.bias_alert_threshold:
            self._fire_alert(profile.strategy, "systematic_bias",
                             f"Strategy {profile.strategy} has systematic bias {abs_bias:.4f}")

    def _trigger_recalibration(
        self, profile: StrategyErrorProfile, trigger: str, reason: str
    ) -> None:
        old_params  = {"bias": round(profile.bias, 6), "mae": round(profile.mae, 6)}
        new_params  = dict(old_params)

        if self.recalibration_hook:
            try:
                new_params = self.recalibration_hook(profile.strategy, old_params)
            except Exception as exc:
                logger.warning("Recalibration hook failed for %s: %s", profile.strategy, exc)

        # Adaptive bias correction: dampen confidence_threshold proportionally
        adjustment = -profile.bias * 0.5
        new_params["confidence_adjustment"] = round(adjustment, 6)
        new_params["recal_count"] = profile.recalibration_count + 1

        bias_before = profile.bias
        # Partially correct bias via reset of rolling window (keep last 20 %)
        keep = max(1, len(profile.observations) // 5)
        recent = list(profile.observations)[-keep:]
        profile.observations.clear()
        for o in recent:
            profile.observations.append(o)
        self._update_profile_stats(profile)

        event = CalibrationEvent(
            event_id=str(uuid.uuid4()),
            strategy=profile.strategy,
            timestamp=time.time(),
            reason=reason, trigger=trigger,
            old_params=old_params, new_params=new_params,
            bias_before=bias_before, bias_after=profile.bias,
            notes=f"Window trimmed to {keep} observations",
        )
        capped_append(profile.calibration_history, event)
        profile.last_calibrated    = time.time()
        profile.recalibration_count += 1

        logger.info("ErrorCalibrator RECAL strategy=%s trigger=%s bias_before=%.4f bias_after=%.4f",
                    profile.strategy, trigger, bias_before, profile.bias)

    def _fire_alert(self, strategy: str, alert_type: str, message: str) -> None:
        capped_append(self._alerts, {
            "alert_id": str(uuid.uuid4()),
            "strategy": strategy,
            "type":     alert_type,
            "message":  message,
            "timestamp": time.time(),
        })
        logger.warning("ErrorCalibrator alert: %s", message)

    # ------------------------------------------------------------------
    # Manual recalibration
    # ------------------------------------------------------------------

    def force_recalibrate(self, strategy: str, reason: str = "manual") -> Dict[str, Any]:
        with self._lock:
            profile = self._get_or_create_profile(strategy)
            self._trigger_recalibration(profile, "manual", reason)
            return self.get_profile(strategy)

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def get_profile(self, strategy: str) -> Dict[str, Any]:
        with self._lock:
            profile = self._get_or_create_profile(strategy)
            return {
                "strategy":           strategy,
                "observations":       len(profile.observations),
                "bias":               round(profile.bias, 6),
                "mae":                round(profile.mae,  6),
                "rmse":               round(profile.rmse, 6),
                "recalibration_count": profile.recalibration_count,
                "last_calibrated":    profile.last_calibrated,
                "calibration_history": [e.to_dict() for e in profile.calibration_history[-10:]],
            }

    def get_all_profiles(self) -> Dict[str, Dict[str, Any]]:
        with self._lock:
            return {s: self.get_profile(s) for s in self._profiles}

    def get_alerts(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._alerts[-limit:])

    def get_summary(self) -> Dict[str, Any]:
        with self._lock:
            profiles = list(self._profiles.values())
            return {
                "tracked_strategies": len(profiles),
                "total_observations": sum(len(p.observations) for p in profiles),
                "total_recalibrations": sum(p.recalibration_count for p in profiles),
                "pending_alerts":    len(self._alerts),
                "strategies_with_high_bias": [
                    p.strategy for p in profiles
                    if abs(p.bias) > self.bias_alert_threshold
                ],
            }
