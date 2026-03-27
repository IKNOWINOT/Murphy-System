"""
Momentum Strategy — RSI + MACD crossover + volume confirmation.

Buy  when: RSI crosses above oversold threshold AND MACD histogram turns positive
           AND volume is above average.
Sell when: RSI crosses above overbought threshold OR MACD histogram turns negative.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from strategy_templates.base_strategy import BaseStrategy, MarketBar, Signal, SignalAction

logger = logging.getLogger(__name__)


class MomentumStrategy(BaseStrategy):
    """RSI + MACD crossover with volume confirmation."""

    DEFAULT_PARAMS: Dict[str, Any] = {
        "rsi_period":       14,
        "rsi_oversold":     30.0,
        "rsi_overbought":   70.0,
        "macd_fast":        12,
        "macd_slow":        26,
        "macd_signal":      9,
        "volume_period":    20,
        "volume_threshold": 1.2,   # volume must be > N * average
        "stop_loss_pct":    0.03,
        "take_profit_pct":  0.06,
        "position_size":    0.10,
    }

    def analyze(self, bars: List[MarketBar]) -> Signal:
        closes  = self._closes(bars)
        volumes = self._volumes(bars)
        price   = closes[-1]

        p = self.params
        rsi  = self._rsi(closes, p["rsi_period"])
        macd = self._macd(closes, p["macd_fast"], p["macd_slow"], p["macd_signal"])
        avg_vol = self._sma(volumes, p["volume_period"])

        if rsi is None or macd is None or avg_vol is None:
            return Signal(action=SignalAction.HOLD, confidence=0.0, reasoning="insufficient data")

        volume_ok  = volumes[-1] > avg_vol * p["volume_threshold"]
        hist       = macd["histogram"]
        prev_hist  = None
        # try to compute previous histogram
        if len(closes) >= p["macd_slow"] + p["macd_signal"] + 1:
            prev_macd = self._macd(closes[:-1], p["macd_fast"], p["macd_slow"], p["macd_signal"])
            if prev_macd:
                prev_hist = prev_macd["histogram"]

        # BUY signal
        if (
            rsi < p["rsi_oversold"]
            and hist > 0
            and (prev_hist is None or prev_hist <= 0)
            and volume_ok
        ):
            confidence = min(1.0, (p["rsi_oversold"] - rsi) / p["rsi_oversold"] * 2)
            self._trade_count += 1
            return Signal(
                action=SignalAction.BUY,
                confidence=round(confidence, 4),
                suggested_size=p["position_size"],
                stop_loss=round(price * (1 - p["stop_loss_pct"]), 6),
                take_profit=round(price * (1 + p["take_profit_pct"]), 6),
                reasoning=f"RSI={rsi:.1f} oversold, MACD histogram turned positive, volume confirmed",
                metadata={"rsi": round(rsi, 2), "macd_hist": round(hist, 6)},
            )

        # SELL signal
        if rsi > p["rsi_overbought"] or (hist < 0 and prev_hist is not None and prev_hist >= 0):
            reason = (
                f"RSI={rsi:.1f} overbought" if rsi > p["rsi_overbought"]
                else "MACD histogram turned negative"
            )
            confidence = min(1.0, (rsi - p["rsi_overbought"]) / (100 - p["rsi_overbought"])) if rsi > p["rsi_overbought"] else 0.5
            self._trade_count += 1
            return Signal(
                action=SignalAction.SELL,
                confidence=max(0.3, round(confidence, 4)),
                suggested_size=p["position_size"],
                reasoning=reason,
                metadata={"rsi": round(rsi, 2), "macd_hist": round(hist, 6)},
            )

        return Signal(
            action=SignalAction.HOLD,
            confidence=0.0,
            reasoning=f"RSI={rsi:.1f}, MACD hist={hist:.6f} — no signal",
        )
