"""
Breakout Strategy — Support/Resistance levels + volume breakout confirmation.

Detects when price breaks above resistance or below support with
above-average volume, signalling a potential trend continuation.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from strategy_templates.base_strategy import BaseStrategy, MarketBar, Signal, SignalAction

logger = logging.getLogger(__name__)


class BreakoutStrategy(BaseStrategy):
    """Support/resistance breakout with volume confirmation."""

    DEFAULT_PARAMS: Dict[str, Any] = {
        "lookback":          20,   # bars used to establish S/R levels
        "volume_period":     20,
        "volume_multiplier": 1.5,  # volume must exceed N * average
        "buffer_pct":        0.001, # price must exceed level by this fraction
        "stop_loss_pct":     0.03,
        "take_profit_pct":   0.06,
        "position_size":     0.10,
    }

    def analyze(self, bars: List[MarketBar]) -> Signal:
        p = self.params
        if len(bars) < p["lookback"] + 1:
            return Signal(action=SignalAction.HOLD, confidence=0.0, reasoning="insufficient data")

        closes  = self._closes(bars)
        volumes = self._volumes(bars)
        price   = closes[-1]

        history   = bars[-(p["lookback"] + 1):-1]
        resistance = max(b.high for b in history)
        support    = min(b.low  for b in history)

        avg_vol = self._sma(volumes[:-1], p["volume_period"]) or 1.0
        vol_ok  = volumes[-1] > avg_vol * p["volume_multiplier"]

        # Bullish breakout
        if price > resistance * (1 + p["buffer_pct"]) and vol_ok:
            confidence = min(1.0, (price / resistance - 1) / 0.02)
            self._trade_count += 1
            return Signal(
                action=SignalAction.BUY,
                confidence=round(confidence, 4),
                suggested_size=p["position_size"],
                stop_loss=round(resistance * (1 - p["stop_loss_pct"]), 6),
                take_profit=round(price * (1 + p["take_profit_pct"]), 6),
                reasoning=f"Bullish breakout above resistance {resistance:.4f} with volume spike",
                metadata={"resistance": round(resistance, 4), "support": round(support, 4)},
            )

        # Bearish breakdown
        if price < support * (1 - p["buffer_pct"]) and vol_ok:
            confidence = min(1.0, (1 - price / support) / 0.02)
            self._trade_count += 1
            return Signal(
                action=SignalAction.SELL,
                confidence=round(confidence, 4),
                suggested_size=p["position_size"],
                reasoning=f"Bearish breakdown below support {support:.4f} with volume spike",
                metadata={"resistance": round(resistance, 4), "support": round(support, 4)},
            )

        return Signal(
            action=SignalAction.HOLD,
            confidence=0.0,
            reasoning=f"Price {price:.4f} within range [{support:.4f}, {resistance:.4f}]",
        )
