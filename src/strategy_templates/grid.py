"""
Grid Trading Strategy — Buy low / sell high within a configured price range.

Divides a price range into N equal grid levels.  Generates BUY signals
when price crosses a grid level downward and SELL signals when price
crosses a grid level upward.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from strategy_templates.base_strategy import BaseStrategy, MarketBar, Signal, SignalAction

logger = logging.getLogger(__name__)


class GridStrategy(BaseStrategy):
    """Price-grid trading: buy at lower levels, sell at higher levels."""

    DEFAULT_PARAMS: Dict[str, Any] = {
        "lower_price":    None,   # set at runtime; defaults to SMA - 2*std
        "upper_price":    None,   # set at runtime; defaults to SMA + 2*std
        "grid_levels":    10,     # number of grid cells
        "init_period":    50,     # bars used to auto-set range if not configured
        "position_size":  0.05,   # per-grid position size (fraction of capital)
    }

    def __init__(self, strategy_id: str, params: Dict[str, Any] | None = None) -> None:
        super().__init__(strategy_id, params)
        self._prev_price: Optional[float] = None
        self._grids: List[float] = []

    # ------------------------------------------------------------------
    # Grid helpers
    # ------------------------------------------------------------------

    def _build_grids(self, lower: float, upper: float) -> List[float]:
        levels = self.params["grid_levels"]
        if lower >= upper or levels < 2:
            return []
        step = (upper - lower) / levels
        return [lower + i * step for i in range(levels + 1)]

    def _auto_range(self, closes: List[float]) -> Optional[tuple]:
        period = self.params["init_period"]
        bb = self._bollinger(closes, period, 2.0)
        if bb is None:
            return None
        return bb["lower"], bb["upper"]

    # ------------------------------------------------------------------
    # Main analysis
    # ------------------------------------------------------------------

    def analyze(self, bars: List[MarketBar]) -> Signal:
        p      = self.params
        closes = self._closes(bars)
        price  = closes[-1]

        # Auto-detect range if not set
        if not self._grids:
            lower = p["lower_price"]
            upper = p["upper_price"]
            if lower is None or upper is None:
                auto = self._auto_range(closes)
                if auto is None:
                    self._prev_price = price
                    return Signal(action=SignalAction.HOLD, confidence=0.0,
                                  reasoning="insufficient data for grid range")
                lower, upper = auto
                p["lower_price"] = round(lower, 6)
                p["upper_price"] = round(upper, 6)
            self._grids = self._build_grids(float(lower), float(upper))
            logger.info("Grid %s: %d levels from %.4f to %.4f",
                        self.strategy_id, len(self._grids), float(lower), float(upper))

        if self._prev_price is None:
            self._prev_price = price
            return Signal(action=SignalAction.HOLD, confidence=0.0, reasoning="initialising grid")

        prev  = self._prev_price
        lower = p["lower_price"]
        upper = p["upper_price"]
        self._prev_price = price

        # Out of range — HOLD
        if price < float(lower) or price > float(upper):
            return Signal(action=SignalAction.HOLD, confidence=0.3,
                          reasoning=f"Price {price:.4f} outside grid range [{lower:.4f}, {upper:.4f}]")

        # Detect which grid levels were crossed
        for level in self._grids:
            if prev > level >= price:   # price dropped through grid level → BUY
                self._trade_count += 1
                return Signal(
                    action=SignalAction.BUY,
                    confidence=0.6,
                    suggested_size=p["position_size"],
                    stop_loss=round(float(lower) * 0.99, 6),
                    take_profit=round(level + (self._grids[1] - self._grids[0]), 6) if len(self._grids) > 1 else None,
                    reasoning=f"Price crossed grid level {level:.4f} downward — grid buy",
                    metadata={"grid_level": round(level, 4)},
                )
            if prev < level <= price:   # price rose through grid level → SELL
                self._trade_count += 1
                return Signal(
                    action=SignalAction.SELL,
                    confidence=0.6,
                    suggested_size=p["position_size"],
                    reasoning=f"Price crossed grid level {level:.4f} upward — grid sell",
                    metadata={"grid_level": round(level, 4)},
                )

        return Signal(action=SignalAction.HOLD, confidence=0.0,
                      reasoning=f"Price {price:.4f} within grid — no level crossed")
