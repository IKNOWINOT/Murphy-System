"""
DCA (Dollar Cost Average) Strategy — Time-based or price-dip-based accumulation.

Generates BUY signals at regular intervals OR when price dips a configurable
percentage below a reference level, averaging into a position over time.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List

from strategy_templates.base_strategy import BaseStrategy, MarketBar, Signal, SignalAction

logger = logging.getLogger(__name__)


class DCAStrategy(BaseStrategy):
    """Dollar Cost Average — periodic buys or dip-triggered buys."""

    DEFAULT_PARAMS: Dict[str, Any] = {
        "mode":             "time",     # "time" | "dip" | "both"
        "interval_seconds": 3600,       # time mode: buy every N seconds
        "dip_threshold_pct": 0.03,      # dip mode: buy when price drops N% from reference
        "reference_period": 20,         # bars used to compute reference price
        "position_size":    0.05,       # fraction of capital per DCA buy
        "max_buys":         20,         # maximum number of DCA entries to track
    }

    def __init__(self, strategy_id: str, params: Dict[str, Any] | None = None) -> None:
        super().__init__(strategy_id, params)
        self._last_buy_time: float = 0.0
        self._buy_count: int = 0

    def analyze(self, bars: List[MarketBar]) -> Signal:
        p     = self.params
        price = bars[-1].close
        now   = time.time()

        closes    = self._closes(bars)
        reference = self._sma(closes, p["reference_period"]) or price

        if self._buy_count >= p["max_buys"]:
            return Signal(action=SignalAction.HOLD, confidence=0.5,
                          reasoning=f"DCA max buys ({p['max_buys']}) reached")

        should_buy = False
        reason     = ""

        if p["mode"] in ("time", "both"):
            elapsed = now - self._last_buy_time
            if elapsed >= p["interval_seconds"]:
                should_buy = True
                reason = f"DCA interval {p['interval_seconds']}s elapsed"

        if p["mode"] in ("dip", "both") and not should_buy:
            dip = (reference - price) / reference if reference > 0 else 0.0
            if dip >= p["dip_threshold_pct"]:
                should_buy = True
                reason = f"Price dipped {dip*100:.2f}% below reference {reference:.4f}"

        if should_buy:
            self._last_buy_time = now
            self._buy_count += 1
            self._trade_count += 1
            confidence = min(0.8, 0.4 + self._buy_count * 0.02)
            return Signal(
                action=SignalAction.BUY,
                confidence=round(confidence, 4),
                suggested_size=p["position_size"],
                reasoning=reason,
                metadata={"buy_count": self._buy_count, "reference": round(reference, 4)},
            )

        return Signal(
            action=SignalAction.HOLD,
            confidence=0.0,
            reasoning=f"DCA: waiting (mode={p['mode']}, buys={self._buy_count})",
        )
