"""
Scalping Strategy — Short timeframe, small profit targets, tight stops, high frequency.

Generates BUY/SELL signals on micro price movements using EMA crossovers
and ATR-based position sizing. Designed for very short holding periods.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from strategy_templates.base_strategy import BaseStrategy, MarketBar, Signal, SignalAction

logger = logging.getLogger(__name__)


class ScalpingStrategy(BaseStrategy):
    """EMA crossover scalping with ATR-based tight stops."""

    DEFAULT_PARAMS: Dict[str, Any] = {
        "fast_ema":          5,
        "slow_ema":          13,
        "atr_period":        14,
        "stop_atr_mult":     1.0,   # stop = entry ± N * ATR
        "target_atr_mult":   1.5,   # target = entry ± N * ATR
        "min_atr_pct":       0.0005, # minimum ATR as fraction of price to trade
        "position_size":     0.05,   # smaller size for scalping
    }

    def analyze(self, bars: List[MarketBar]) -> Signal:
        p      = self.params
        closes = self._closes(bars)
        price  = closes[-1]

        fast_ema = self._ema(closes, p["fast_ema"])
        slow_ema = self._ema(closes, p["slow_ema"])
        atr      = self._atr(bars, p["atr_period"])

        if fast_ema is None or slow_ema is None or atr is None:
            return Signal(action=SignalAction.HOLD, confidence=0.0, reasoning="insufficient data")

        atr_pct = atr / price
        if atr_pct < p["min_atr_pct"]:
            return Signal(action=SignalAction.HOLD, confidence=0.0, reasoning="volatility too low to scalp")

        # Previous EMA values for crossover detection
        if len(closes) >= p["slow_ema"] + 1:
            prev_fast = self._ema(closes[:-1], p["fast_ema"])
            prev_slow = self._ema(closes[:-1], p["slow_ema"])
        else:
            prev_fast = prev_slow = None

        stop_dist   = atr * p["stop_atr_mult"]
        target_dist = atr * p["target_atr_mult"]

        # Golden cross (fast crosses above slow)
        if (
            fast_ema > slow_ema
            and prev_fast is not None
            and prev_slow is not None
            and prev_fast <= prev_slow
        ):
            confidence = min(1.0, (fast_ema - slow_ema) / slow_ema * 100)
            self._trade_count += 1
            return Signal(
                action=SignalAction.BUY,
                confidence=round(confidence, 4),
                suggested_size=p["position_size"],
                stop_loss=round(price - stop_dist, 6),
                take_profit=round(price + target_dist, 6),
                reasoning=f"EMA{p['fast_ema']} crossed above EMA{p['slow_ema']} — scalp entry",
                metadata={"fast_ema": round(fast_ema, 6), "slow_ema": round(slow_ema, 6), "atr": round(atr, 6)},
            )

        # Death cross (fast crosses below slow)
        if (
            fast_ema < slow_ema
            and prev_fast is not None
            and prev_slow is not None
            and prev_fast >= prev_slow
        ):
            confidence = min(1.0, (slow_ema - fast_ema) / slow_ema * 100)
            self._trade_count += 1
            return Signal(
                action=SignalAction.SELL,
                confidence=round(confidence, 4),
                suggested_size=p["position_size"],
                reasoning=f"EMA{p['fast_ema']} crossed below EMA{p['slow_ema']} — scalp exit",
                metadata={"fast_ema": round(fast_ema, 6), "slow_ema": round(slow_ema, 6), "atr": round(atr, 6)},
            )

        return Signal(
            action=SignalAction.HOLD,
            confidence=0.0,
            reasoning=f"EMA fast={fast_ema:.4f}, slow={slow_ema:.4f} — no crossover",
        )
