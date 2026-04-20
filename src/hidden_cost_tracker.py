# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Hidden Cost Tracker — Murphy System

Tracks ALL costs on every trade and auto-detects discrepancies between
expected and actual execution costs.  When a discrepancy is found the cost
model is updated and strategy profitability is recalculated.

Tracked costs:
  - Exchange fees (maker / taker)
  - Spread cost (mid-price vs executed price)
  - Slippage (market impact)
  - Network / withdrawal fees
  - Opportunity cost (time value in position)

Business Source License 1.1 (BSL 1.1)
Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
"""

from __future__ import annotations

import csv
import io
import logging
import statistics
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from thread_safe_operations import capped_append
except ImportError:  # pragma: no cover
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)

_MAX_RECORDS = 10_000
_DISCREPANCY_THRESHOLD = 0.001  # 0.1 % relative threshold triggers alert
_SPREAD_SPLIT_FACTOR   = 0.5    # spread cost attributed as 50 % of price-difference × quantity


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class TradeCost:
    """Full cost breakdown for a single trade."""
    trade_id:          str
    timestamp:         str
    pair:              str
    side:              str       # "buy" | "sell"
    quantity:          float
    executed_price:    float
    expected_price:    float
    exchange_fee:      float     # USD
    spread_cost:       float     # USD (executed vs mid-price)
    slippage:          float     # USD (executed vs expected)
    network_fee:       float     # USD
    opportunity_cost:  float     # USD (time-in-position cost)
    total_cost:        float     # sum of all above
    expected_total:    float     # what we budgeted
    discrepancy:       float     # actual - expected
    discrepancy_pct:   float     # relative to trade value
    strategy_id:       str       = ""
    notes:             str       = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CostModel:
    """Running averages used to estimate future costs."""
    exchange:          str = "default"
    avg_maker_fee_pct: float = 0.0010   # 0.10 %
    avg_taker_fee_pct: float = 0.0025   # 0.25 %
    avg_slippage_pct:  float = 0.0005   # 0.05 %
    avg_spread_pct:    float = 0.0005   # 0.05 %
    avg_network_fee:   float = 0.50     # USD flat
    last_updated:      str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def estimate_total_pct(self, is_maker: bool = False) -> float:
        """Return estimated total cost as % of trade value."""
        fee = self.avg_maker_fee_pct if is_maker else self.avg_taker_fee_pct
        return fee + self.avg_slippage_pct + self.avg_spread_pct

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class StrategyProfitability:
    """Cost-adjusted profitability for a single strategy."""
    strategy_id:       str
    total_trades:      int
    gross_pnl:         float
    total_costs:       float
    net_pnl:           float
    cost_as_pct_pnl:   float   # costs / gross_pnl
    is_profitable:     bool
    last_updated:      str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Hidden Cost Tracker
# ---------------------------------------------------------------------------


class HiddenCostTracker:
    """
    Records, models and audits all trading costs.

    Thread-safe.  All mutable state is guarded by a Lock.
    """

    def __init__(
        self,
        exchange:              str   = "coinbase",
        initial_taker_fee_pct: float = 0.0025,
        initial_maker_fee_pct: float = 0.0010,
        alert_callback: Optional[Any] = None,
    ) -> None:
        self._model = CostModel(
            exchange          = exchange,
            avg_taker_fee_pct = initial_taker_fee_pct,
            avg_maker_fee_pct = initial_maker_fee_pct,
        )
        self._records: List[TradeCost] = []
        self._strategy_pnl: Dict[str, List[float]] = {}   # strategy_id → list of net P&Ls
        self._alert_callback = alert_callback
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record_trade(
        self,
        trade_id:         str,
        pair:             str,
        side:             str,
        quantity:         float,
        expected_price:   float,
        executed_price:   float,
        exchange_fee_usd: float,
        network_fee_usd:  float = 0.0,
        opportunity_cost: float = 0.0,
        strategy_id:      str   = "",
        notes:            str   = "",
        is_maker:         bool  = False,
    ) -> TradeCost:
        """
        Record the full cost breakdown for a completed trade.

        Parameters
        ----------
        expected_price : the price used when deciding to trade (e.g., signal price)
        executed_price : the actual fill price
        exchange_fee_usd : the fee charged by the exchange in USD
        """
        trade_value = quantity * executed_price
        spread_cost = max(0.0, abs(executed_price - expected_price) * quantity * _SPREAD_SPLIT_FACTOR)
        slippage    = abs(executed_price - expected_price) * quantity - spread_cost

        expected_fee_pct = (
            self._model.avg_maker_fee_pct if is_maker else self._model.avg_taker_fee_pct
        )
        expected_total = (
            trade_value * expected_fee_pct
            + trade_value * self._model.avg_slippage_pct
            + trade_value * self._model.avg_spread_pct
            + self._model.avg_network_fee
        )
        actual_total = exchange_fee_usd + spread_cost + slippage + network_fee_usd + opportunity_cost
        discrepancy  = actual_total - expected_total
        disc_pct     = discrepancy / (trade_value or 1)

        cost = TradeCost(
            trade_id         = trade_id,
            timestamp        = datetime.now(timezone.utc).isoformat(),
            pair             = pair,
            side             = side,
            quantity         = quantity,
            executed_price   = executed_price,
            expected_price   = expected_price,
            exchange_fee     = exchange_fee_usd,
            spread_cost      = spread_cost,
            slippage         = slippage,
            network_fee      = network_fee_usd,
            opportunity_cost = opportunity_cost,
            total_cost       = actual_total,
            expected_total   = expected_total,
            discrepancy      = discrepancy,
            discrepancy_pct  = disc_pct,
            strategy_id      = strategy_id,
            notes            = notes,
        )

        with self._lock:
            capped_append(self._records, cost, _MAX_RECORDS)
            self._update_model(exchange_fee_usd, trade_value, slippage, spread_cost, network_fee_usd, is_maker)
            if abs(disc_pct) > _DISCREPANCY_THRESHOLD:
                self._handle_discrepancy(cost)

        logger.debug("HiddenCostTracker: recorded %s %s — total cost $%.4f", side, pair, actual_total)
        return cost

    def record_pnl(self, strategy_id: str, gross_pnl: float, trade_cost: float) -> None:
        """Record the net P&L for a closed trade (for profitability tracking)."""
        net = gross_pnl - trade_cost
        with self._lock:
            self._strategy_pnl.setdefault(strategy_id, []).append(net)

    def estimate_cost(
        self, pair: str, quantity: float, price: float, is_maker: bool = False
    ) -> float:
        """Return the estimated total cost in USD using the current model."""
        with self._lock:
            return quantity * price * self._model.estimate_total_pct(is_maker) + self._model.avg_network_fee

    def get_strategy_profitability(self, strategy_id: str) -> Optional[StrategyProfitability]:
        """Return cost-adjusted profitability for a single strategy."""
        with self._lock:
            records = [r for r in self._records if r.strategy_id == strategy_id]
            if not records:
                return None
            total_cost  = sum(r.total_cost for r in records)
            gross_pnl_vals = self._strategy_pnl.get(strategy_id, [])
            gross_pnl   = sum(gross_pnl_vals)
            net_pnl     = gross_pnl - total_cost
            cost_ratio  = total_cost / (abs(gross_pnl) or 1)
            return StrategyProfitability(
                strategy_id    = strategy_id,
                total_trades   = len(records),
                gross_pnl      = round(gross_pnl, 4),
                total_costs    = round(total_cost, 4),
                net_pnl        = round(net_pnl, 4),
                cost_as_pct_pnl = round(cost_ratio * 100, 2),
                is_profitable  = net_pnl > 0,
            )

    def get_dashboard(self) -> Dict[str, Any]:
        """Return cost summary data for the risk dashboard."""
        with self._lock:
            if not self._records:
                return {"total_records": 0}
            total_fees   = sum(r.exchange_fee for r in self._records)
            total_slip   = sum(r.slippage     for r in self._records)
            total_spread = sum(r.spread_cost  for r in self._records)
            total_costs  = sum(r.total_cost   for r in self._records)
            avg_slip     = total_slip / len(self._records)
            # cost as % of trade value
            total_val    = sum(r.quantity * r.executed_price for r in self._records)
            cost_pct     = total_costs / (total_val or 1) * 100
            discrepancies = [r for r in self._records if abs(r.discrepancy_pct) > _DISCREPANCY_THRESHOLD]
            return {
                "total_records":       len(self._records),
                "total_fees_usd":      round(total_fees, 4),
                "total_slippage_usd":  round(total_slip, 4),
                "total_spread_usd":    round(total_spread, 4),
                "total_costs_usd":     round(total_costs, 4),
                "avg_slippage_usd":    round(avg_slip, 6),
                "cost_as_pct_of_trade": round(cost_pct, 4),
                "discrepancy_count":   len(discrepancies),
                "cost_model":          self._model.to_dict(),
            }

    def get_records(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Return recent cost records."""
        with self._lock:
            return [r.to_dict() for r in self._records[-limit:]]

    def export_csv(self) -> str:
        """Export all cost records to CSV string."""
        with self._lock:
            if not self._records:
                return ""
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=list(asdict(self._records[0]).keys()))
            writer.writeheader()
            for r in self._records:
                writer.writerow(asdict(r))
            return output.getvalue()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _update_model(
        self,
        fee_usd:   float,
        trade_val: float,
        slip:      float,
        spread:    float,
        net_fee:   float,
        is_maker:  bool,
    ) -> None:
        """Update running cost model averages (exponential moving average)."""
        alpha = 0.05  # EMA smoothing factor
        if trade_val > 0:
            fee_pct    = fee_usd  / trade_val
            slip_pct   = slip     / trade_val
            spread_pct = spread   / trade_val
            if is_maker:
                self._model.avg_maker_fee_pct = (
                    (1 - alpha) * self._model.avg_maker_fee_pct + alpha * fee_pct
                )
            else:
                self._model.avg_taker_fee_pct = (
                    (1 - alpha) * self._model.avg_taker_fee_pct + alpha * fee_pct
                )
            self._model.avg_slippage_pct = (
                (1 - alpha) * self._model.avg_slippage_pct + alpha * slip_pct
            )
            self._model.avg_spread_pct = (
                (1 - alpha) * self._model.avg_spread_pct + alpha * spread_pct
            )
        if net_fee > 0:
            self._model.avg_network_fee = (
                (1 - alpha) * self._model.avg_network_fee + alpha * net_fee
            )
        self._model.last_updated = datetime.now(timezone.utc).isoformat()

    def _handle_discrepancy(self, cost: TradeCost) -> None:
        """Log discrepancy and optionally alert."""
        logger.warning(
            "HiddenCostTracker: cost discrepancy %.4f%% on %s %s "
            "(expected $%.4f, actual $%.4f)",
            cost.discrepancy_pct * 100,
            cost.side, cost.pair,
            cost.expected_total, cost.total_cost,
        )
        if self._alert_callback:
            try:
                self._alert_callback(cost)
            except Exception:
                logger.debug("Alert callback failed for cost tracking")
