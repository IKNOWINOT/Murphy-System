# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Crypto Portfolio Tracker — Murphy System

Aggregates positions and trade history from all registered exchanges and
wallets into a single unified portfolio view.  Computes real-time P&L,
drawdown, and standard risk metrics (Sharpe ratio, win rate, profit factor).

Designed to feed the Murphy System trading dashboard and the HITL
graduation engine with objective performance data.

Business Source License 1.1 (BSL 1.1)
Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
"""

from __future__ import annotations

import logging
import statistics
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_MAX_TRADE_HISTORY = 100_000


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class PositionSide(Enum):
    """Long or short position direction (Enum subclass)."""
    LONG  = "long"
    SHORT = "short"


class ReportPeriod(Enum):
    """Reporting time window (Enum subclass)."""
    DAILY   = "daily"
    WEEKLY  = "weekly"
    MONTHLY = "monthly"
    ALL_TIME = "all_time"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Position:
    """An open position in a specific pair on a specific exchange."""
    position_id:   str
    exchange_id:   str
    pair:          str
    side:          PositionSide
    quantity:      float
    avg_cost:      float
    current_price: float   = 0.0
    bot_id:        Optional[str] = None
    opened_at:     str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @property
    def market_value(self) -> float:
        """Current market value of the full position."""
        return self.quantity * self.current_price

    @property
    def cost_basis(self) -> float:
        """Original cost of the full position."""
        return self.quantity * self.avg_cost

    @property
    def unrealized_pnl(self) -> float:
        """Unrealized P&L at the current price."""
        if self.side == PositionSide.LONG:
            return (self.current_price - self.avg_cost) * self.quantity
        return (self.avg_cost - self.current_price) * self.quantity

    @property
    def unrealized_pnl_pct(self) -> float:
        """Unrealized P&L as a percentage of cost basis."""
        return self.unrealized_pnl / (self.cost_basis or 1)


@dataclass
class ClosedTrade:
    """Historical record of a completed trade (entry → exit)."""
    trade_id:       str
    exchange_id:    str
    pair:           str
    side:           PositionSide
    quantity:       float
    entry_price:    float
    exit_price:     float
    fee:            float
    pnl:            float
    pnl_pct:        float
    bot_id:         Optional[str]
    opened_at:      str
    closed_at:      str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class RiskMetrics:
    """Computed risk and performance statistics."""
    total_trades:     int
    winning_trades:   int
    losing_trades:    int
    win_rate:         float
    total_pnl_usd:    float
    total_pnl_pct:    float
    avg_win_usd:      float
    avg_loss_usd:     float
    profit_factor:    float
    max_drawdown:     float
    sharpe_ratio:     Optional[float]
    sortino_ratio:    Optional[float]
    expectancy_usd:   float
    largest_win:      float
    largest_loss:     float
    avg_trade_duration_hours: float
    computed_at:      str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class PortfolioSnapshot:
    """Point-in-time view of the entire portfolio."""
    snapshot_id:     str
    total_value_usd: float
    cash_usd:        float
    invested_usd:    float
    unrealized_pnl:  float
    realized_pnl:    float
    open_positions:  List[Dict[str, Any]]
    risk_metrics:    Optional[RiskMetrics]
    timestamp:       str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


# ---------------------------------------------------------------------------
# Portfolio tracker
# ---------------------------------------------------------------------------

class CryptoPortfolioTracker:
    """
    Maintains a live multi-exchange, multi-bot portfolio view.

    Call ``open_position()`` when a trade is filled, ``close_position()``
    when a position is exited, and ``update_prices()`` on every tick.
    The tracker computes full risk metrics on demand.
    """

    def __init__(
        self,
        initial_cash_usd: float = 0.0,
        exchange_registry: Optional[Any] = None,
    ) -> None:
        self._cash          = initial_cash_usd
        self._exchange      = exchange_registry
        self._lock          = threading.Lock()
        self._positions:    Dict[str, Position]    = {}
        self._closed_trades: List[ClosedTrade]     = []
        self._equity_curve: List[float]            = []
        self._peak_equity   = initial_cash_usd

    # ---- position management --------------------------------------------

    def open_position(
        self,
        exchange_id: str,
        pair:        str,
        side:        PositionSide,
        quantity:    float,
        entry_price: float,
        fee:         float   = 0.0,
        bot_id:      Optional[str] = None,
    ) -> str:
        """Record a new open position.  Returns position_id."""
        cost = quantity * entry_price + fee
        with self._lock:
            self._cash -= cost
            pos_id = str(uuid.uuid4())
            self._positions[pos_id] = Position(
                position_id = pos_id,
                exchange_id = exchange_id,
                pair        = pair,
                side        = side,
                quantity    = quantity,
                avg_cost    = entry_price,
                bot_id      = bot_id,
            )
        logger.debug("Portfolio: opened %s %s qty=%.6f @ %.4f", side.value, pair, quantity, entry_price)
        return pos_id

    def close_position(
        self,
        position_id: str,
        exit_price:  float,
        fee:         float = 0.0,
    ) -> Optional[ClosedTrade]:
        """Record a position close and return the ClosedTrade."""
        with self._lock:
            pos = self._positions.pop(position_id, None)
            if pos is None:
                return None
            proceeds = pos.quantity * exit_price - fee
            self._cash += proceeds
            if pos.side == PositionSide.LONG:
                pnl = proceeds - pos.cost_basis
            else:
                pnl = pos.cost_basis - proceeds
            pnl_pct = pnl / (pos.cost_basis or 1)
            trade = ClosedTrade(
                trade_id    = str(uuid.uuid4()),
                exchange_id = pos.exchange_id,
                pair        = pos.pair,
                side        = pos.side,
                quantity    = pos.quantity,
                entry_price = pos.avg_cost,
                exit_price  = exit_price,
                fee         = fee,
                pnl         = pnl,
                pnl_pct     = pnl_pct,
                bot_id      = pos.bot_id,
                opened_at   = pos.opened_at,
            )
            try:
                from thread_safe_operations import capped_append
            except ImportError:
                def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
                    """Fallback bounded append (CWE-770)."""
                    if len(target_list) >= max_size:
                        del target_list[: max_size // 10]
                    target_list.append(item)
            capped_append(self._closed_trades, trade, _MAX_TRADE_HISTORY)
        self._record_equity()
        logger.debug("Portfolio: closed %s pnl=%.4f (%.2f%%)", position_id, pnl, pnl_pct * 100)
        return trade

    def update_prices(self, price_map: Dict[str, float]) -> None:
        """Update current prices for all positions.  ``price_map`` maps pair → price."""
        with self._lock:
            for pos in self._positions.values():
                if pos.pair in price_map:
                    pos.current_price = price_map[pos.pair]

    def add_cash(self, amount: float) -> None:
        """Deposit or withdraw cash (use negative for withdrawal)."""
        with self._lock:
            self._cash += amount

    # ---- portfolio snapshot & metrics -----------------------------------

    def get_snapshot(self) -> PortfolioSnapshot:
        """Return a full portfolio snapshot with risk metrics."""
        with self._lock:
            open_positions = [
                {
                    "position_id":    p.position_id,
                    "exchange":       p.exchange_id,
                    "pair":           p.pair,
                    "side":           p.side.value,
                    "quantity":       p.quantity,
                    "avg_cost":       p.avg_cost,
                    "current_price":  p.current_price,
                    "market_value":   p.market_value,
                    "unrealized_pnl": p.unrealized_pnl,
                    "unrealized_pnl_pct": p.unrealized_pnl_pct,
                    "bot_id":         p.bot_id,
                }
                for p in self._positions.values()
            ]
            unrealized = sum(p.unrealized_pnl for p in self._positions.values())
            invested   = sum(p.cost_basis     for p in self._positions.values())
            realized   = sum(t.pnl            for t in self._closed_trades)
            total      = self._cash + invested + unrealized
        metrics = self.compute_risk_metrics()
        return PortfolioSnapshot(
            snapshot_id     = str(uuid.uuid4()),
            total_value_usd = total,
            cash_usd        = self._cash,
            invested_usd    = invested,
            unrealized_pnl  = unrealized,
            realized_pnl    = realized,
            open_positions  = open_positions,
            risk_metrics    = metrics,
        )

    def compute_risk_metrics(self, period: ReportPeriod = ReportPeriod.ALL_TIME) -> Optional[RiskMetrics]:
        """Compute full risk and performance statistics from closed trades."""
        with self._lock:
            trades = list(self._closed_trades)
        if not trades:
            return None

        wins    = [t for t in trades if t.pnl > 0]
        losses  = [t for t in trades if t.pnl <= 0]
        pnls    = [t.pnl for t in trades]
        total   = len(trades)
        win_rate = len(wins) / total

        avg_win  = sum(t.pnl for t in wins)  / (len(wins)   or 1)
        avg_loss = sum(t.pnl for t in losses) / (len(losses) or 1)
        gross_profit = sum(t.pnl for t in wins)
        gross_loss   = abs(sum(t.pnl for t in losses))
        profit_factor = gross_profit / (gross_loss or 1)

        expectancy = win_rate * avg_win + (1 - win_rate) * avg_loss

        # Drawdown from equity curve
        max_dd  = 0.0
        peak    = self._equity_curve[0] if self._equity_curve else 0.0
        for eq in self._equity_curve:
            peak   = max(peak, eq)
            max_dd = max(max_dd, (peak - eq) / (peak or 1))

        # Sharpe & Sortino
        sharpe  = None
        sortino = None
        if len(pnls) > 2:
            mean_pnl = sum(pnls) / len(pnls)
            std_pnl  = statistics.pstdev(pnls)
            sharpe   = (mean_pnl / (std_pnl or 1)) * (252 ** 0.5)
            down_dev = statistics.pstdev([p for p in pnls if p < 0] or [0.0])
            sortino  = (mean_pnl / (down_dev or 1)) * (252 ** 0.5)

        # Average trade duration
        def _hours(t: ClosedTrade) -> float:
            try:
                from datetime import datetime as _dt
                o = _dt.fromisoformat(t.opened_at.replace("Z", "+00:00"))
                c = _dt.fromisoformat(t.closed_at.replace("Z", "+00:00"))
                return (c - o).total_seconds() / 3600.0
            except Exception as exc:
                logger.debug("Duration calc failed: %s", exc)
                return 0.0

        durations = [_hours(t) for t in trades]
        avg_dur   = sum(durations) / (len(durations) or 1)

        return RiskMetrics(
            total_trades     = total,
            winning_trades   = len(wins),
            losing_trades    = len(losses),
            win_rate         = win_rate,
            total_pnl_usd    = sum(pnls),
            total_pnl_pct    = sum(t.pnl_pct for t in trades),
            avg_win_usd      = avg_win,
            avg_loss_usd     = avg_loss,
            profit_factor    = profit_factor,
            max_drawdown     = max_dd,
            sharpe_ratio     = sharpe,
            sortino_ratio    = sortino,
            expectancy_usd   = expectancy,
            largest_win      = max((t.pnl for t in wins),  default=0.0),
            largest_loss     = min((t.pnl for t in losses), default=0.0),
            avg_trade_duration_hours = avg_dur,
        )

    def get_trade_history(self, limit: int = 100, pair: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return recent closed trades, optionally filtered by *pair*."""
        with self._lock:
            trades = list(self._closed_trades)
        if pair:
            trades = [t for t in trades if t.pair == pair]
        trades = trades[-limit:]
        return [t.__dict__ for t in trades]

    def get_open_positions(self) -> List[Dict[str, Any]]:
        """Return all open positions."""
        with self._lock:
            return [p.__dict__ for p in self._positions.values()]

    # ---- helpers --------------------------------------------------------

    def _record_equity(self) -> None:
        with self._lock:
            unrealized = sum(p.unrealized_pnl for p in self._positions.values())
            invested   = sum(p.cost_basis     for p in self._positions.values())
            equity     = self._cash + invested + unrealized
            try:
                from thread_safe_operations import capped_append
            except ImportError:
                def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
                    """Fallback bounded append (CWE-770)."""
                    if len(target_list) >= max_size:
                        del target_list[: max_size // 10]
                    target_list.append(item)
            capped_append(self._equity_curve, equity, 100_000)
            self._peak_equity = max(self._peak_equity, equity)
