"""
Arbitrage Strategy — Cross-pair price discrepancy detection.

Compares prices across multiple symbol/exchange feeds.  When a price
spread between two correlated assets exceeds a configurable threshold,
generates BUY on the cheaper leg and SELL on the pricier leg.

In paper trading mode this is used to identify mispricing opportunities;
execution of both legs is handled by the paper trading engine.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from strategy_templates.base_strategy import BaseStrategy, MarketBar, Signal, SignalAction

logger = logging.getLogger(__name__)


class ArbitrageStrategy(BaseStrategy):
    """
    Cross-pair arbitrage via spread detection.

    Usage
    -----
    Pass two lists of bars (for asset_a and asset_b) via ``analyze_pair()``.
    The standard ``analyze()`` method returns HOLD unless secondary bars
    are provided via ``set_secondary_bars()``.
    """

    DEFAULT_PARAMS: Dict[str, Any] = {
        "spread_threshold":    0.005,   # minimum spread (fraction) to trigger
        "z_score_threshold":   2.0,     # spread Z-score required
        "spread_period":       30,      # lookback for spread statistics
        "position_size":       0.06,
        "stop_loss_pct":       0.02,
    }

    def __init__(self, strategy_id: str, params: Dict[str, Any] | None = None) -> None:
        super().__init__(strategy_id, params)
        self._secondary_bars: Optional[List[MarketBar]] = None
        self._spread_history: List[float] = []

    def set_secondary_bars(self, bars: List[MarketBar]) -> None:
        """Provide the second asset's bar data for arbitrage comparison."""
        self._secondary_bars = bars

    def analyze(self, bars: List[MarketBar]) -> Signal:
        """Single-asset analysis — returns HOLD unless secondary bars are set."""
        if self._secondary_bars is None:
            return Signal(action=SignalAction.HOLD, confidence=0.0,
                          reasoning="No secondary bars set — call set_secondary_bars()")
        return self.analyze_pair(bars, self._secondary_bars)

    def analyze_pair(
        self,
        bars_a: List[MarketBar],
        bars_b: List[MarketBar],
    ) -> Signal:
        """
        Compare two assets and detect arbitrage opportunity.

        Returns BUY signal (buy the underpriced, sell the overpriced leg)
        when the spread Z-score exceeds the threshold.
        """
        p = self.params
        if not bars_a or not bars_b:
            return Signal(action=SignalAction.HOLD, confidence=0.0, reasoning="empty bar lists")

        price_a = bars_a[-1].close
        price_b = bars_b[-1].close

        if price_b == 0 or price_a == 0:
            return Signal(action=SignalAction.HOLD, confidence=0.0, reasoning="zero price in pair")

        spread = (price_a - price_b) / price_b
        self._spread_history.append(spread)
        if len(self._spread_history) > p["spread_period"] * 2:
            self._spread_history = self._spread_history[-p["spread_period"] * 2:]

        # Need enough history for Z-score
        period = p["spread_period"]
        if len(self._spread_history) < period:
            return Signal(action=SignalAction.HOLD, confidence=0.0,
                          reasoning=f"Building spread history ({len(self._spread_history)}/{period})")

        window  = self._spread_history[-period:]
        mean_s  = sum(window) / period
        var_s   = sum((x - mean_s) ** 2 for x in window) / period
        std_s   = var_s ** 0.5
        zscore  = (spread - mean_s) / std_s if std_s > 0 else 0.0

        abs_spread = abs(spread)
        if abs_spread < p["spread_threshold"]:
            return Signal(action=SignalAction.HOLD, confidence=0.0,
                          reasoning=f"Spread {abs_spread:.4f} below threshold")

        z_thresh = p["z_score_threshold"]
        if abs(zscore) < z_thresh:
            return Signal(action=SignalAction.HOLD, confidence=0.0,
                          reasoning=f"Spread Z-score {zscore:.2f} below threshold {z_thresh}")

        # Asset A is expensive relative to B → sell A / buy B
        if zscore > z_thresh:
            self._trade_count += 1
            confidence = min(0.9, zscore / (z_thresh * 2))
            return Signal(
                action=SignalAction.SELL,  # sell the overpriced leg (A)
                confidence=round(confidence, 4),
                suggested_size=p["position_size"],
                stop_loss=round(price_a * (1 + p["stop_loss_pct"]), 6),
                reasoning=f"Arb: {bars_a[-1].symbol} overpriced vs {bars_b[-1].symbol}; spread Z={zscore:.2f}",
                metadata={
                    "symbol_a": bars_a[-1].symbol,
                    "symbol_b": bars_b[-1].symbol,
                    "spread": round(spread, 6),
                    "zscore": round(zscore, 4),
                    "action_b": "buy",
                },
            )

        # Asset A is cheap relative to B → buy A / sell B
        if zscore < -z_thresh:
            self._trade_count += 1
            confidence = min(0.9, abs(zscore) / (z_thresh * 2))
            return Signal(
                action=SignalAction.BUY,   # buy the underpriced leg (A)
                confidence=round(confidence, 4),
                suggested_size=p["position_size"],
                stop_loss=round(price_a * (1 - p["stop_loss_pct"]), 6),
                reasoning=f"Arb: {bars_a[-1].symbol} underpriced vs {bars_b[-1].symbol}; spread Z={zscore:.2f}",
                metadata={
                    "symbol_a": bars_a[-1].symbol,
                    "symbol_b": bars_b[-1].symbol,
                    "spread": round(spread, 6),
                    "zscore": round(zscore, 4),
                    "action_b": "sell",
                },
            )

        return Signal(action=SignalAction.HOLD, confidence=0.0, reasoning="no arb opportunity")
