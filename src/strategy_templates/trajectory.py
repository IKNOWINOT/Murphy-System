"""
Trajectory / Projection Strategy — Detect parabolic/skyrocketing moves.

1. Detects parabolic acceleration: each successive gain is larger than the last.
2. Fits a simple trajectory to estimate the peak price.
3. Generates BUY at the detected acceleration point.
4. Sets take-profit at the projected peak with a trailing stop.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional

from strategy_templates.base_strategy import BaseStrategy, MarketBar, Signal, SignalAction

logger = logging.getLogger(__name__)


class TrajectoryStrategy(BaseStrategy):
    """Parabolic move detector with trajectory peak projection."""

    DEFAULT_PARAMS: Dict[str, Any] = {
        "accel_period":       5,     # bars used to measure acceleration
        "accel_threshold":    0.015, # each step must exceed this % gain
        "projection_method":  "log", # "log" | "linear"
        "trailing_stop_pct":  0.05,  # trailing stop below entry
        "min_confidence":     0.5,
        "position_size":      0.08,
    }

    # ------------------------------------------------------------------
    # Trajectory helpers
    # ------------------------------------------------------------------

    def _detect_acceleration(self, closes: List[float], period: int, threshold: float) -> bool:
        """Return True if the last `period` bars show accelerating gains."""
        if len(closes) < period + 1:
            return False
        returns = [
            (closes[i] - closes[i - 1]) / closes[i - 1]
            for i in range(len(closes) - period, len(closes))
            if closes[i - 1] > 0
        ]
        if len(returns) < period:
            return False
        # All returns positive and each larger than the previous
        return all(r > threshold for r in returns) and all(returns[i] >= returns[i - 1] for i in range(1, len(returns)))

    def _project_peak(self, closes: List[float], period: int, method: str) -> Optional[float]:
        """Project the approximate peak price from recent trajectory."""
        if len(closes) < period + 1:
            return None
        segment = closes[-period - 1:]
        if method == "log":
            # Fit log-linear: extrapolate one more step
            try:
                log_prices = [math.log(p) for p in segment if p > 0]
                if len(log_prices) < 2:
                    return None
                avg_log_gain = (log_prices[-1] - log_prices[0]) / len(log_prices)
                # Assume gain decelerates — project half-step ahead
                projected_log = log_prices[-1] + avg_log_gain * 0.5
                return math.exp(projected_log)
            except (ValueError, OverflowError):
                return None
        else:
            # Linear extrapolation
            avg_gain = (segment[-1] - segment[0]) / len(segment)
            return segment[-1] + avg_gain

    # ------------------------------------------------------------------
    # Main analysis
    # ------------------------------------------------------------------

    def analyze(self, bars: List[MarketBar]) -> Signal:
        p      = self.params
        closes = self._closes(bars)
        price  = closes[-1]

        accel = self._detect_acceleration(closes, p["accel_period"], p["accel_threshold"])

        if accel:
            peak = self._project_peak(closes, p["accel_period"], p["projection_method"])

            # Compute momentum-based confidence
            recent_return = (price - closes[-p["accel_period"] - 1]) / closes[-p["accel_period"] - 1]
            confidence = min(0.95, p["min_confidence"] + recent_return * 5)

            self._trade_count += 1
            return Signal(
                action=SignalAction.BUY,
                confidence=round(confidence, 4),
                suggested_size=p["position_size"],
                stop_loss=round(price * (1 - p["trailing_stop_pct"]), 6),
                take_profit=round(peak, 6) if peak else None,
                reasoning=f"Parabolic acceleration detected over {p['accel_period']} bars; projected peak {peak:.4f}" if peak else "Parabolic acceleration detected",
                metadata={
                    "recent_return_pct": round(recent_return * 100, 2),
                    "projected_peak": round(peak, 4) if peak else None,
                    "trailing_stop_pct": p["trailing_stop_pct"],
                },
            )

        # Check if price is falling after parabolic move (exit signal)
        if len(closes) >= 3:
            last_ret   = (closes[-1] - closes[-2]) / closes[-2] if closes[-2] > 0 else 0.0
            prev_ret   = (closes[-2] - closes[-3]) / closes[-3] if closes[-3] > 0 else 0.0
            if prev_ret > p["accel_threshold"] and last_ret < -p["accel_threshold"]:
                self._trade_count += 1
                return Signal(
                    action=SignalAction.SELL,
                    confidence=0.7,
                    reasoning="Trajectory reversal detected — potential parabolic peak",
                    metadata={"last_ret": round(last_ret, 4), "prev_ret": round(prev_ret, 4)},
                )

        return Signal(
            action=SignalAction.HOLD,
            confidence=0.0,
            reasoning="No parabolic acceleration detected",
        )
