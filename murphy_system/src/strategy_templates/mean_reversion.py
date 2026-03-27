"""
Mean Reversion Strategy — Bollinger Bands + Z-score.

Buy  when price drops below the lower Bollinger Band AND Z-score < -threshold.
Sell when price rises above the upper Bollinger Band OR Z-score >  threshold.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from strategy_templates.base_strategy import BaseStrategy, MarketBar, Signal, SignalAction

logger = logging.getLogger(__name__)


class MeanReversionStrategy(BaseStrategy):
    """Bollinger Bands + Z-score mean reversion detection."""

    DEFAULT_PARAMS: Dict[str, Any] = {
        "bb_period":       20,
        "bb_std":          2.0,
        "zscore_period":   20,
        "zscore_buy":     -2.0,
        "zscore_sell":     2.0,
        "stop_loss_pct":   0.04,
        "take_profit_pct": 0.04,
        "position_size":   0.10,
    }

    def analyze(self, bars: List[MarketBar]) -> Signal:
        closes = self._closes(bars)
        price  = closes[-1]
        p      = self.params

        bb     = self._bollinger(closes, p["bb_period"], p["bb_std"])
        zscore = self._zscore(closes, p["zscore_period"])

        if bb is None or zscore is None:
            return Signal(action=SignalAction.HOLD, confidence=0.0, reasoning="insufficient data")

        # BUY: price below lower band AND strongly negative Z-score
        if price < bb["lower"] and zscore < p["zscore_buy"]:
            confidence = min(1.0, abs(zscore) / abs(p["zscore_buy"]) * 0.6)
            self._trade_count += 1
            return Signal(
                action=SignalAction.BUY,
                confidence=round(confidence, 4),
                suggested_size=p["position_size"],
                stop_loss=round(price * (1 - p["stop_loss_pct"]), 6),
                take_profit=round(bb["middle"], 6),
                reasoning=f"Price {price:.4f} below BB lower {bb['lower']:.4f}, Z={zscore:.2f}",
                metadata={"zscore": round(zscore, 4), "bb_lower": round(bb["lower"], 4)},
            )

        # SELL: price above upper band OR strongly positive Z-score
        if price > bb["upper"] or zscore > p["zscore_sell"]:
            confidence = min(1.0, zscore / p["zscore_sell"] * 0.6) if zscore > p["zscore_sell"] else 0.5
            self._trade_count += 1
            return Signal(
                action=SignalAction.SELL,
                confidence=max(0.3, round(confidence, 4)),
                suggested_size=p["position_size"],
                reasoning=f"Price {price:.4f} above BB upper {bb['upper']:.4f}, Z={zscore:.2f}",
                metadata={"zscore": round(zscore, 4), "bb_upper": round(bb["upper"], 4)},
            )

        return Signal(
            action=SignalAction.HOLD,
            confidence=0.0,
            reasoning=f"Z={zscore:.2f}, price within Bollinger Bands",
        )
