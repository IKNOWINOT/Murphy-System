# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Trajectory Projection Engine — Murphy System

Detects "skyrocketing" assets exhibiting parabolic price movements and
calculates entry / exit points using curve-fitting and statistical projection.

Detection signals:
  - Rate-of-Change (ROC) acceleration
  - Volume surge (> 2× 20-period average)
  - Price above N standard deviations from mean
  - Consecutive green candles with increasing body size

Projection:
  - Polynomial / exponential curve fit to recent price action
  - Projected target price + confidence interval
  - Optimal entry (pullback within trend)
  - Optimal exit (projected peak with safety margin)

Trailing stop:
  - Trails at configurable % below running high
  - Tightens as price approaches target
  - Emergency exit if trajectory breaks

Risk guardrails:
  - Never chase > X% above detection price
  - Mandatory position-size reduction for trajectory trades
  - Hard stop always set

Business Source License 1.1 (BSL 1.1)
Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
"""

from __future__ import annotations

import logging
import math
import statistics
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

try:
    import numpy as np
    import numpy.polynomial.polynomial as poly
    _HAS_NUMPY = True
except ImportError:  # pragma: no cover
    _HAS_NUMPY = False

try:
    from scipy.optimize import curve_fit as _scipy_curve_fit
    _HAS_SCIPY = True
except ImportError:  # pragma: no cover
    _HAS_SCIPY = False

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_VOLUME_SURGE_MULTIPLIER  = 2.0   # volume > 2× avg → surge
_DEFAULT_STD_DEV_BREAK            = 2.0   # price > mean + N×std → parabolic
_DEFAULT_MIN_GREEN_CANDLES        = 3     # consecutive green candles required
_DEFAULT_TRAIL_PCT                = 0.05  # 5 % trailing stop below high
_DEFAULT_TRAIL_TIGHTEN_FACTOR     = 0.5   # halve trail % in last 20 % of move
_DEFAULT_MAX_CHASE_PCT            = 0.10  # max 10 % above detection price
_DEFAULT_TRAJECTORY_SIZE_FACTOR   = 0.50  # halve normal size for trajectory trades
_DEFAULT_PROJECTION_BARS          = 5     # bars forward to project
_DEFAULT_CONFIDENCE_PCT           = 0.80  # confidence interval coverage


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class TrajectorySignal(str, Enum):
    """Parabolic detection signal strength (Enum subclass)."""
    NONE     = "none"
    WEAK     = "weak"
    MODERATE = "moderate"
    STRONG   = "strong"
    PARABOLIC = "parabolic"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class Candle:
    """OHLCV candle (minimal)."""
    open:   float
    high:   float
    low:    float
    close:  float
    volume: float = 0.0

    @property
    def body(self) -> float:
        return abs(self.close - self.open)

    @property
    def is_green(self) -> bool:
        return self.close >= self.open


@dataclass
class TrajectoryAnalysis:
    """Full trajectory analysis for a single asset."""
    product_id:        str
    signal:            TrajectorySignal
    detection_price:   float
    current_price:     float
    projected_target:  Optional[float]
    confidence_low:    Optional[float]
    confidence_high:   Optional[float]
    optimal_entry:     Optional[float]
    optimal_exit:      Optional[float]
    hard_stop_loss:    Optional[float]
    trailing_stop:     Optional[float]
    max_chase_price:   Optional[float]  # never enter above this
    position_size_factor: float         # multiply normal size by this
    reasoning:         List[str]
    roc_acceleration:  Optional[float]
    volume_surge:      bool
    std_dev_breaks:    float
    green_candle_run:  int
    timestamp:         str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "product_id":           self.product_id,
            "signal":               self.signal.value,
            "detection_price":      self.detection_price,
            "current_price":        self.current_price,
            "projected_target":     self.projected_target,
            "confidence_low":       self.confidence_low,
            "confidence_high":      self.confidence_high,
            "optimal_entry":        self.optimal_entry,
            "optimal_exit":         self.optimal_exit,
            "hard_stop_loss":       self.hard_stop_loss,
            "trailing_stop":        self.trailing_stop,
            "max_chase_price":      self.max_chase_price,
            "position_size_factor": self.position_size_factor,
            "reasoning":            self.reasoning,
            "roc_acceleration":     self.roc_acceleration,
            "volume_surge":         self.volume_surge,
            "std_dev_breaks":       round(self.std_dev_breaks, 2),
            "green_candle_run":     self.green_candle_run,
            "timestamp":            self.timestamp,
        }


@dataclass
class TrailingStopState:
    """Mutable trailing-stop state for an open trajectory position."""
    product_id:      str
    entry_price:     float
    running_high:    float
    trail_pct:       float
    target_price:    Optional[float]
    stop_price:      float
    is_active:       bool = True

    def update(self, current_price: float) -> Tuple[float, bool]:
        """
        Update trailing stop given the latest price.
        Returns (new_stop_price, should_exit).
        """
        if not self.is_active:
            return self.stop_price, False

        if current_price > self.running_high:
            self.running_high = current_price
            # Tighten trail as price approaches target
            trail = self.trail_pct
            if self.target_price and self.entry_price:
                move_pct = (current_price - self.entry_price) / (
                    self.target_price - self.entry_price + 1e-12
                )
                if move_pct >= 0.80:
                    trail *= _DEFAULT_TRAIL_TIGHTEN_FACTOR
            self.stop_price = round(self.running_high * (1 - trail), 8)

        should_exit = current_price <= self.stop_price
        return self.stop_price, should_exit


# ---------------------------------------------------------------------------
# Trajectory Engine
# ---------------------------------------------------------------------------


class TrajectoryEngine:
    """
    Detects parabolic assets and calculates projection-based trade parameters.

    Thread-safe.
    """

    def __init__(
        self,
        volume_surge_mult:     float = _DEFAULT_VOLUME_SURGE_MULTIPLIER,
        std_dev_break:         float = _DEFAULT_STD_DEV_BREAK,
        min_green_candles:     int   = _DEFAULT_MIN_GREEN_CANDLES,
        trail_pct:             float = _DEFAULT_TRAIL_PCT,
        max_chase_pct:         float = _DEFAULT_MAX_CHASE_PCT,
        trajectory_size_factor: float = _DEFAULT_TRAJECTORY_SIZE_FACTOR,
        projection_bars:       int   = _DEFAULT_PROJECTION_BARS,
    ) -> None:
        self.volume_surge_mult      = volume_surge_mult
        self.std_dev_break          = std_dev_break
        self.min_green_candles      = min_green_candles
        self.trail_pct              = trail_pct
        self.max_chase_pct          = max_chase_pct
        self.trajectory_size_factor = trajectory_size_factor
        self.projection_bars        = projection_bars
        self._trailing_stops: Dict[str, TrailingStopState] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(self, product_id: str, candles: List[Candle]) -> TrajectoryAnalysis:
        """
        Analyze candle history for a single asset.

        Parameters
        ----------
        product_id : exchange product identifier (e.g. "BTC-USD")
        candles    : OHLCV history, oldest first, minimum 20 candles
        """
        reasoning: List[str] = []
        closes  = [c.close  for c in candles]
        volumes = [c.volume for c in candles]
        current = closes[-1] if closes else 0.0

        # ── Parabolic detection ─────────────────────────────────────────
        roc_accel    = self._calc_roc_acceleration(closes, reasoning)
        vol_surge    = self._detect_volume_surge(volumes, reasoning)
        std_breaks   = self._calc_std_dev_breaks(closes, reasoning)
        green_run    = self._count_green_run(candles, reasoning)

        signal       = self._classify_signal(roc_accel, vol_surge, std_breaks, green_run)
        if signal != TrajectorySignal.NONE:
            reasoning.insert(0, f"Trajectory signal: {signal.value.upper()}.")

        # ── Projection ──────────────────────────────────────────────────
        target, ci_low, ci_high = self._project_target(closes)

        # ── Entry / exit / stop ─────────────────────────────────────────
        entry  = self._optimal_entry(closes, current, signal)
        exit_p = self._optimal_exit(current, target)
        stop   = self._hard_stop(current, signal)
        trail  = current * (1 - self.trail_pct) if signal != TrajectorySignal.NONE else None
        max_ch = current * (1 + self.max_chase_pct)

        # Size factor based on signal strength
        size_f = self._size_factor(signal)

        return TrajectoryAnalysis(
            product_id           = product_id,
            signal               = signal,
            detection_price      = current,
            current_price        = current,
            projected_target     = target,
            confidence_low       = ci_low,
            confidence_high      = ci_high,
            optimal_entry        = entry,
            optimal_exit         = exit_p,
            hard_stop_loss       = stop,
            trailing_stop        = trail,
            max_chase_price      = max_ch,
            position_size_factor = size_f,
            reasoning            = reasoning,
            roc_acceleration     = roc_accel,
            volume_surge         = vol_surge,
            std_dev_breaks       = std_breaks,
            green_candle_run     = green_run,
        )

    def activate_trailing_stop(
        self,
        product_id:  str,
        entry_price: float,
        target:      Optional[float] = None,
        trail_pct:   Optional[float] = None,
    ) -> TrailingStopState:
        """Start tracking a trailing stop for an open position."""
        t = trail_pct or self.trail_pct
        state = TrailingStopState(
            product_id   = product_id,
            entry_price  = entry_price,
            running_high = entry_price,
            trail_pct    = t,
            target_price = target,
            stop_price   = round(entry_price * (1 - t), 8),
        )
        with self._lock:
            self._trailing_stops[product_id] = state
        return state

    def update_trailing_stop(
        self, product_id: str, current_price: float
    ) -> Tuple[Optional[float], bool]:
        """
        Tick the trailing stop for an open position.
        Returns (stop_price, should_exit).
        """
        with self._lock:
            state = self._trailing_stops.get(product_id)
            if not state:
                return None, False
            stop, exit_now = state.update(current_price)
            if exit_now:
                state.is_active = False
            return stop, exit_now

    def deactivate_trailing_stop(self, product_id: str) -> None:
        with self._lock:
            self._trailing_stops.pop(product_id, None)

    def get_trailing_stop(self, product_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            s = self._trailing_stops.get(product_id)
            if not s:
                return None
            return {
                "product_id":   s.product_id,
                "entry_price":  s.entry_price,
                "running_high": s.running_high,
                "stop_price":   s.stop_price,
                "trail_pct":    s.trail_pct,
                "target_price": s.target_price,
                "is_active":    s.is_active,
            }

    # ------------------------------------------------------------------
    # Detection helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _calc_roc_acceleration(closes: List[float], reasoning: List[str]) -> Optional[float]:
        """Return rate-of-change acceleration (2nd derivative of ROC)."""
        if len(closes) < 6:
            return None
        window = closes[-6:]
        rocs = []
        for i in range(1, len(window)):
            if window[i - 1] > 0:
                rocs.append((window[i] / window[i - 1]) - 1)
        if len(rocs) < 4:
            return None
        accel = []
        for i in range(1, len(rocs)):
            accel.append(rocs[i] - rocs[i - 1])
        avg_accel = statistics.mean(accel)
        if avg_accel > 0.02:
            reasoning.append(
                f"ROC acceleration {avg_accel:.3f} — price momentum accelerating."
            )
        return avg_accel

    def _detect_volume_surge(self, volumes: List[float], reasoning: List[str]) -> bool:
        """Return True if latest volume > surge_mult × 20-bar average."""
        if len(volumes) < 5:
            return False
        avg = statistics.mean(volumes[-20:]) if len(volumes) >= 20 else statistics.mean(volumes[:-1])
        last = volumes[-1]
        surge = last > avg * self.volume_surge_mult
        if surge:
            ratio = last / (avg or 1)
            reasoning.append(f"Volume surge: {ratio:.1f}× the 20-period average.")
        return surge

    def _calc_std_dev_breaks(self, closes: List[float], reasoning: List[str]) -> float:
        """Return how many σ above the 20-bar mean the latest close sits."""
        if len(closes) < 5:
            return 0.0
        window = closes[-20:] if len(closes) >= 20 else closes
        mean_p = statistics.mean(window)
        try:
            std_p = statistics.stdev(window)
        except statistics.StatisticsError:
            return 0.0
        if std_p <= 0:
            return 0.0
        breaks = (closes[-1] - mean_p) / std_p
        if breaks >= self.std_dev_break:
            reasoning.append(
                f"Price {breaks:.1f}σ above 20-bar mean — statistically extreme."
            )
        return breaks

    def _count_green_run(self, candles: List[Candle], reasoning: List[str]) -> int:
        """Count consecutive green (close ≥ open) candles from the end."""
        count = 0
        prev_body = None
        for c in reversed(candles):
            if not c.is_green:
                break
            if prev_body is not None and c.body < prev_body * 0.5:
                break  # body shrinking — not accelerating
            prev_body = c.body
            count += 1
        if count >= self.min_green_candles:
            reasoning.append(
                f"{count} consecutive green candles with growing bodies."
            )
        return count

    @staticmethod
    def _classify_signal(
        roc_accel:  Optional[float],
        vol_surge:  bool,
        std_breaks: float,
        green_run:  int,
    ) -> TrajectorySignal:
        """Aggregate detection scores into a single signal level."""
        score = 0
        if roc_accel and roc_accel > 0.005:
            score += 1
        if roc_accel and roc_accel > 0.02:
            score += 1
        if vol_surge:
            score += 1
        if std_breaks >= 2.0:
            score += 1
        if std_breaks >= 3.0:
            score += 1
        if green_run >= 3:
            score += 1
        if green_run >= 5:
            score += 1

        if score >= 6:
            return TrajectorySignal.PARABOLIC
        elif score >= 4:
            return TrajectorySignal.STRONG
        elif score >= 2:
            return TrajectorySignal.MODERATE
        elif score >= 1:
            return TrajectorySignal.WEAK
        return TrajectorySignal.NONE

    # ------------------------------------------------------------------
    # Projection helpers
    # ------------------------------------------------------------------

    def _project_target(
        self, closes: List[float]
    ) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        """
        Fit a polynomial to recent prices and project forward.
        Returns (target, ci_low, ci_high).
        """
        if len(closes) < 6:
            return None, None, None

        window = closes[-min(20, len(closes)):]

        if _HAS_NUMPY:
            x = np.arange(len(window), dtype=float)
            try:
                coeffs = np.polyfit(x, window, deg=2)
                p = np.poly1d(coeffs)
                x_target = len(window) - 1 + self.projection_bars
                target = float(p(x_target))
                # Confidence interval via residual std
                residuals = [window[i] - float(p(i)) for i in range(len(window))]
                std_res = float(np.std(residuals)) if len(residuals) > 1 else 0.0
                z = 1.645  # 90 % one-sided
                return (
                    round(target, 8),
                    round(target - z * std_res, 8),
                    round(target + z * std_res, 8),
                )
            except Exception:
                pass

        # Fallback: linear projection using last two points
        if len(window) >= 2:
            slope = window[-1] - window[-2]
            target = window[-1] + slope * self.projection_bars
            return round(target, 8), None, None

        return None, None, None

    def _optimal_entry(
        self, closes: List[float], current: float, signal: TrajectorySignal
    ) -> Optional[float]:
        """Return a suggested entry (slight pullback within uptrend)."""
        if signal == TrajectorySignal.NONE or not closes or current <= 0:
            return None
        # Entry: current price minus 0.5–1.5% pullback based on volatility
        if len(closes) >= 5:
            try:
                std = statistics.stdev(closes[-5:])
            except statistics.StatisticsError:
                std = current * 0.01
        else:
            std = current * 0.01
        pullback_pct = min(0.015, std / current)
        return round(current * (1 - pullback_pct), 8)

    def _optimal_exit(
        self, current: float, target: Optional[float]
    ) -> Optional[float]:
        """Return optimal exit with safety margin below projected target."""
        if not target or target <= current:
            return None
        safety = 0.95  # exit at 95 % of projected target
        return round(current + (target - current) * safety, 8)

    def _hard_stop(self, current: float, signal: TrajectorySignal) -> Optional[float]:
        """Return a hard stop loss for a trajectory trade."""
        if signal == TrajectorySignal.NONE or current <= 0:
            return None
        # Tighter stop for trajectory trades: 3-5 % based on signal
        stop_pct = {
            TrajectorySignal.WEAK:      0.05,
            TrajectorySignal.MODERATE:  0.04,
            TrajectorySignal.STRONG:    0.03,
            TrajectorySignal.PARABOLIC: 0.025,
        }.get(signal, 0.05)
        return round(current * (1 - stop_pct), 8)

    def _size_factor(self, signal: TrajectorySignal) -> float:
        """Scaling factor to apply to normal position size for trajectory trades."""
        if signal == TrajectorySignal.NONE:
            return 1.0
        # Trajectory trades use reduced sizing (higher risk)
        return self.trajectory_size_factor * {
            TrajectorySignal.WEAK:      1.0,
            TrajectorySignal.MODERATE:  0.9,
            TrajectorySignal.STRONG:    0.7,
            TrajectorySignal.PARABOLIC: 0.5,
        }.get(signal, 1.0)
