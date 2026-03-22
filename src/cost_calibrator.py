"""
Cost Calibrator — Murphy System

Tracks expected vs actual execution prices to detect and quantify hidden
trading costs: spread, slippage, exchange fees, and network fees.

Auto-adjusts future trade cost estimates based on observed patterns and
alerts when costs exceed configurable thresholds.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import statistics
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

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
class CostObservation:
    """Single data point: expected cost vs observed cost for one trade."""
    trade_id:      str
    symbol:        str
    strategy:      str
    timestamp:     float
    expected_price:   float
    actual_price:     float
    price_discrepancy: float       # actual - expected
    expected_fee:  float
    actual_fee:    float
    fee_discrepancy: float
    expected_slippage: float
    actual_slippage:   float
    slippage_discrepancy: float
    total_hidden_cost: float       # sum of all discrepancies

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trade_id":           self.trade_id,
            "symbol":             self.symbol,
            "strategy":           self.strategy,
            "timestamp":          self.timestamp,
            "expected_price":     round(self.expected_price,      6),
            "actual_price":       round(self.actual_price,        6),
            "price_discrepancy":  round(self.price_discrepancy,   6),
            "expected_fee":       round(self.expected_fee,        6),
            "actual_fee":         round(self.actual_fee,          6),
            "fee_discrepancy":    round(self.fee_discrepancy,     6),
            "expected_slippage":  round(self.expected_slippage,   6),
            "actual_slippage":    round(self.actual_slippage,     6),
            "slippage_discrepancy": round(self.slippage_discrepancy, 6),
            "total_hidden_cost":  round(self.total_hidden_cost,   6),
        }


@dataclass
class CostAlert:
    """Fired when a cost discrepancy exceeds a threshold."""
    alert_id:  str
    symbol:    str
    cost_type: str   # "slippage" | "fee" | "spread" | "total"
    observed:  float
    threshold: float
    timestamp: float
    message:   str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert_id":  self.alert_id,
            "symbol":    self.symbol,
            "cost_type": self.cost_type,
            "observed":  round(self.observed,  6),
            "threshold": round(self.threshold, 6),
            "timestamp": self.timestamp,
            "message":   self.message,
        }


# ---------------------------------------------------------------------------
# CostCalibrator
# ---------------------------------------------------------------------------

class CostCalibrator:
    """
    Detects, quantifies, and auto-adjusts for hidden trading costs.

    Usage
    -----
    1. Before a trade: call ``expected_costs()`` to get your estimates.
    2. After the trade fills: call ``record_observation()`` with actual values.
    3. Call ``get_adjusted_estimates()`` to get calibrated estimates for future trades.
    """

    def __init__(
        self,
        window_size: int   = 100,       # rolling observations used for calibration
        slippage_alert_bps: float = 15.0,  # alert if slippage > N bps
        fee_alert_pct:      float = 0.002,  # alert if fee > 0.2 % of notional
        total_cost_alert_bps: float = 30.0, # alert if total hidden cost > N bps
    ) -> None:
        self._lock       = threading.RLock()
        self.window_size = window_size
        self._thresholds = {
            "slippage": slippage_alert_bps / 10_000,
            "fee":      fee_alert_pct,
            "total":    total_cost_alert_bps / 10_000,
        }
        # Rolling history
        self._observations: deque[CostObservation] = deque(maxlen=window_size)
        self._alerts:       List[CostAlert]         = []

        # Calibrated adjustments (updated after each observation)
        self._slippage_adj: float = 0.0   # extra bps to add to slippage estimate
        self._fee_adj:      float = 0.0   # extra fraction to add to fee estimate
        self._spread_adj:   float = 0.0   # extra price adjustment

        import uuid as _uuid
        self._uuid = _uuid

    # ------------------------------------------------------------------
    # Pre-trade estimates
    # ------------------------------------------------------------------

    def expected_costs(
        self,
        symbol:      str,
        notional:    float,
        base_slippage_bps: float = 5.0,
        base_fee_rate:     float = 0.001,
    ) -> Dict[str, float]:
        """Return calibrated cost estimates for a prospective trade."""
        with self._lock:
            adj_slippage_rate = (base_slippage_bps / 10_000) + self._slippage_adj
            adj_fee_rate      = base_fee_rate + self._fee_adj
            spread_cost       = notional * self._spread_adj

            return {
                "notional":         round(notional, 4),
                "slippage_est":     round(notional * adj_slippage_rate, 6),
                "fee_est":          round(notional * adj_fee_rate, 6),
                "spread_est":       round(spread_cost, 6),
                "total_cost_est":   round(notional * (adj_slippage_rate + adj_fee_rate) + spread_cost, 6),
                "slippage_rate":    round(adj_slippage_rate, 8),
                "fee_rate":         round(adj_fee_rate, 8),
                "calibration_adj":  {
                    "slippage_bps_added": round(self._slippage_adj * 10_000, 4),
                    "fee_pct_added":      round(self._fee_adj * 100, 6),
                },
            }

    # ------------------------------------------------------------------
    # Post-trade recording
    # ------------------------------------------------------------------

    def record_observation(
        self,
        trade_id:          str,
        symbol:            str,
        strategy:          str,
        expected_price:    float,
        actual_price:      float,
        expected_fee:      float,
        actual_fee:        float,
        expected_slippage: float,
        actual_slippage:   float,
    ) -> CostObservation:
        """Record a completed trade's cost discrepancies and update calibration."""
        with self._lock:
            obs = CostObservation(
                trade_id=trade_id, symbol=symbol, strategy=strategy,
                timestamp=time.time(),
                expected_price=expected_price,   actual_price=actual_price,
                price_discrepancy=actual_price - expected_price,
                expected_fee=expected_fee,       actual_fee=actual_fee,
                fee_discrepancy=actual_fee - expected_fee,
                expected_slippage=expected_slippage, actual_slippage=actual_slippage,
                slippage_discrepancy=actual_slippage - expected_slippage,
                total_hidden_cost=(
                    abs(actual_price - expected_price) +
                    abs(actual_fee - expected_fee) +
                    abs(actual_slippage - expected_slippage)
                ),
            )
            self._observations.append(obs)
            self._recalibrate()
            self._check_alerts(obs, expected_price, actual_slippage, actual_fee)
            logger.debug("CostCalibrator obs: symbol=%s hidden_cost=%.6f", symbol, obs.total_hidden_cost)
            return obs

    # ------------------------------------------------------------------
    # Calibration
    # ------------------------------------------------------------------

    def _recalibrate(self) -> None:
        """Update adjustment factors from rolling observations."""
        obs = list(self._observations)
        if len(obs) < 5:
            return

        prices = [abs(o.price_discrepancy / o.expected_price) for o in obs if o.expected_price > 0]
        fees   = [(o.actual_fee - o.expected_fee) / max(o.expected_fee, 1e-9) for o in obs]
        slips  = [o.slippage_discrepancy / max(o.expected_slippage, 1e-9) for o in obs]

        # Use median to be robust to outliers
        self._spread_adj = statistics.median(prices)
        self._fee_adj    = max(0.0, statistics.median(fees))
        # slips is a ratio of discrepancy/expected; scale by 0.0001 so the
        # adjustment is expressed as a fractional rate (1 basis point = 0.0001)
        self._slippage_adj = max(0.0, statistics.median([abs(s) for s in slips]) * 0.0001)

    # ------------------------------------------------------------------
    # Alerts
    # ------------------------------------------------------------------

    def _check_alerts(
        self, obs: CostObservation, expected_price: float,
        actual_slippage: float, actual_fee: float,
    ) -> None:
        import uuid as _uuid

        def _fire(cost_type: str, observed: float, threshold: float, msg: str) -> None:
            alert = CostAlert(
                alert_id=str(_uuid.uuid4()),
                symbol=obs.symbol, cost_type=cost_type,
                observed=observed, threshold=threshold,
                timestamp=time.time(), message=msg,
            )
            capped_append(self._alerts, alert)
            logger.warning("CostAlert %s: %s", cost_type, msg)

        ref = expected_price if expected_price > 0 else 1.0
        if actual_slippage / ref > self._thresholds["slippage"]:
            _fire("slippage", actual_slippage, self._thresholds["slippage"] * ref,
                  f"{obs.symbol}: slippage {actual_slippage/ref*10000:.1f}bps exceeds threshold")

        if obs.total_hidden_cost / ref > self._thresholds["total"]:
            _fire("total", obs.total_hidden_cost, self._thresholds["total"] * ref,
                  f"{obs.symbol}: total hidden cost {obs.total_hidden_cost/ref*10000:.1f}bps exceeds threshold")

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def get_summary(self) -> Dict[str, Any]:
        with self._lock:
            obs = list(self._observations)
            if not obs:
                return {"observations": 0, "calibration": "insufficient_data"}
            hidden_costs = [o.total_hidden_cost for o in obs]
            return {
                "observations": len(obs),
                "avg_hidden_cost_per_trade": round(statistics.mean(hidden_costs), 6),
                "max_hidden_cost_per_trade": round(max(hidden_costs), 6),
                "total_hidden_cost":         round(sum(hidden_costs), 4),
                "calibration_adjustments": {
                    "slippage_bps_added": round(self._slippage_adj * 10_000, 4),
                    "fee_pct_added":      round(self._fee_adj * 100, 6),
                    "spread_pct_added":   round(self._spread_adj * 100, 6),
                },
                "pending_alerts": len(self._alerts),
            }

    def get_alerts(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            return [a.to_dict() for a in self._alerts[-limit:]]

    def get_history(self, limit: int = 200) -> List[Dict[str, Any]]:
        with self._lock:
            return [o.to_dict() for o in list(self._observations)[-limit:]]
