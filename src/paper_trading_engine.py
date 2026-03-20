"""
Paper Trading Engine — Murphy System

Comprehensive paper-trading simulator with:
  - Realistic execution: slippage model + tiered fee schedule
  - Full portfolio state: positions, cash, total equity
  - Trade journal: every entry/exit with timestamps, strategy, P&L
  - Performance metrics: Sharpe, Sortino, max-drawdown, profit factor,
    win rate, avg win/loss, total fees, net profit
  - Multi-strategy support (run N strategies simultaneously)
  - reset() to restart from scratch

Default starting capital: $10,000.
All trading is PAPER/SIMULATED — no real money is moved.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import math
import statistics
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Capped-append helper (guards against unbounded list growth)
# ---------------------------------------------------------------------------
try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(lst: list, item: Any, max_size: int = 10_000) -> None:  # type: ignore[misc]
        if len(lst) >= max_size:
            del lst[: max_size // 10]
        lst.append(item)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEFAULT_CAPITAL:       float = 10_000.0
DEFAULT_TAKER_FEE:     float = 0.001    # 0.10 %
DEFAULT_MAKER_FEE:     float = 0.0006   # 0.06 %
DEFAULT_SLIPPAGE_BPS:  float = 5.0      # 0.05 % per side
RISK_FREE_RATE:        float = 0.045    # 4.5 % annualised (approx US T-bills 2025)
ANNUALISATION_FACTOR:  int   = 252      # trading days per year


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class OrderSide(Enum):
    BUY  = "buy"
    SELL = "sell"


class OrderStatus(Enum):
    PENDING  = "pending"
    FILLED   = "filled"
    REJECTED = "rejected"


class PositionSide(Enum):
    LONG  = "long"
    SHORT = "short"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class TradeEntry:
    """A single open position leg (one BUY fill)."""
    trade_id:  str
    symbol:    str
    strategy:  str
    quantity:  float
    entry_price: float
    entry_time:  float          # Unix epoch
    stop_loss:   Optional[float] = None
    take_profit: Optional[float] = None
    entry_fee:   float = 0.0


@dataclass
class TradeRecord:
    """A completed round-trip (BUY → SELL) in the trade journal."""
    journal_id:    str
    symbol:        str
    strategy:      str
    side:          str          # "long"
    quantity:      float
    entry_price:   float
    exit_price:    float
    entry_time:    float
    exit_time:     float
    gross_pnl:     float
    fees_paid:     float
    net_pnl:       float
    return_pct:    float
    slippage_paid: float
    stop_loss:     Optional[float] = None
    take_profit:   Optional[float] = None
    exit_reason:   str = "manual"   # "manual" | "stop_loss" | "take_profit"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "journal_id":    self.journal_id,
            "symbol":        self.symbol,
            "strategy":      self.strategy,
            "side":          self.side,
            "quantity":      self.quantity,
            "entry_price":   round(self.entry_price,   6),
            "exit_price":    round(self.exit_price,    6),
            "entry_time":    self.entry_time,
            "exit_time":     self.exit_time,
            "entry_dt":      datetime.fromtimestamp(self.entry_time, tz=timezone.utc).isoformat(),
            "exit_dt":       datetime.fromtimestamp(self.exit_time,  tz=timezone.utc).isoformat(),
            "gross_pnl":     round(self.gross_pnl,     4),
            "fees_paid":     round(self.fees_paid,     6),
            "net_pnl":       round(self.net_pnl,       4),
            "return_pct":    round(self.return_pct,    6),
            "slippage_paid": round(self.slippage_paid, 6),
            "stop_loss":     self.stop_loss,
            "take_profit":   self.take_profit,
            "exit_reason":   self.exit_reason,
        }


@dataclass
class Position:
    """Current open position for a symbol."""
    symbol:       str
    strategy:     str
    quantity:     float
    avg_entry:    float
    current_price: float = 0.0
    stop_loss:    Optional[float] = None
    take_profit:  Optional[float] = None
    open_time:    float = field(default_factory=time.time)
    fees_paid:    float = 0.0

    @property
    def unrealized_pnl(self) -> float:
        return (self.current_price - self.avg_entry) * self.quantity

    @property
    def unrealized_pnl_pct(self) -> float:
        if self.avg_entry == 0:
            return 0.0
        return (self.current_price - self.avg_entry) / self.avg_entry

    @property
    def market_value(self) -> float:
        return self.quantity * self.current_price

    @property
    def cost_basis(self) -> float:
        return self.quantity * self.avg_entry

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol":           self.symbol,
            "strategy":         self.strategy,
            "quantity":         round(self.quantity,         8),
            "avg_entry":        round(self.avg_entry,        6),
            "current_price":    round(self.current_price,    6),
            "cost_basis":       round(self.cost_basis,       4),
            "market_value":     round(self.market_value,     4),
            "unrealized_pnl":   round(self.unrealized_pnl,   4),
            "unrealized_pnl_pct": round(self.unrealized_pnl_pct, 6),
            "stop_loss":        self.stop_loss,
            "take_profit":      self.take_profit,
            "open_since":       datetime.fromtimestamp(self.open_time, tz=timezone.utc).isoformat(),
            "fees_paid":        round(self.fees_paid, 6),
        }


# ---------------------------------------------------------------------------
# Fee model
# ---------------------------------------------------------------------------

class FeeModel:
    """
    Tiered maker/taker fee model.

    Pass maker=True if the order is a passive limit order (adds liquidity).
    Pass maker=False for market orders (takes liquidity).
    """

    def __init__(
        self,
        taker_fee_rate: float = DEFAULT_TAKER_FEE,
        maker_fee_rate: float = DEFAULT_MAKER_FEE,
    ) -> None:
        self.taker_fee_rate = taker_fee_rate
        self.maker_fee_rate = maker_fee_rate

    def calculate(self, notional: float, maker: bool = False) -> float:
        rate = self.maker_fee_rate if maker else self.taker_fee_rate
        return notional * rate


# ---------------------------------------------------------------------------
# Slippage model
# ---------------------------------------------------------------------------

class SlippageModel:
    """
    Simple fixed-BPS slippage model.

    Buys are filled slightly *above* the requested price.
    Sells are filled slightly *below*.
    """

    def __init__(self, bps: float = DEFAULT_SLIPPAGE_BPS) -> None:
        self.bps = bps  # basis points

    def apply(self, price: float, side: OrderSide) -> Tuple[float, float]:
        """Return (fill_price, slippage_cost_per_unit)."""
        slip_frac = self.bps / 10_000.0
        if side == OrderSide.BUY:
            fill_price = price * (1 + slip_frac)
        else:
            fill_price = price * (1 - slip_frac)
        return fill_price, abs(fill_price - price)


# ---------------------------------------------------------------------------
# PaperTradingEngine
# ---------------------------------------------------------------------------

class PaperTradingEngine:
    """
    Full paper-trading simulator.

    Tracks cash, open positions, and a closed-trade journal.
    All public methods are thread-safe.
    """

    def __init__(
        self,
        initial_capital: float = DEFAULT_CAPITAL,
        taker_fee_rate:  float = DEFAULT_TAKER_FEE,
        maker_fee_rate:  float = DEFAULT_MAKER_FEE,
        slippage_bps:    float = DEFAULT_SLIPPAGE_BPS,
        max_position_pct: float = 0.25,   # max 25 % of equity per position
    ) -> None:
        self._lock = threading.RLock()
        self.initial_capital   = initial_capital
        self.cash              = initial_capital
        self._fee_model        = FeeModel(taker_fee_rate, maker_fee_rate)
        self._slippage         = SlippageModel(slippage_bps)
        self.max_position_pct  = max_position_pct

        # State
        self._positions:   Dict[str, Position]    = {}   # symbol → Position
        self._open_trades: Dict[str, TradeEntry]  = {}   # trade_id → TradeEntry (FIFO per symbol)
        self._journal:     List[TradeRecord]      = []   # closed trades
        self._equity_curve: List[Tuple[float, float]] = [(time.time(), initial_capital)]
        self._active_strategies: List[str]         = []

        # Accumulated stats
        self._total_fees_paid:     float = 0.0
        self._total_slippage_paid: float = 0.0

        logger.info("PaperTradingEngine initialised — capital=%.2f", initial_capital)

    # ------------------------------------------------------------------
    # Core trading operations
    # ------------------------------------------------------------------

    def open_position(
        self,
        symbol:     str,
        quantity:   float,
        price:      float,
        strategy:   str,
        confidence: float = 0.5,
        stop_loss:  Optional[float] = None,
        take_profit: Optional[float] = None,
        maker:      bool = False,
    ) -> Dict[str, Any]:
        """
        Simulate buying `quantity` units of `symbol` at `price`.
        Returns a result dict with status, fill details, and updated portfolio.
        """
        with self._lock:
            if quantity <= 0 or price <= 0:
                return {"status": "rejected", "reason": "invalid quantity or price"}

            fill_price, slip_per_unit = self._slippage.apply(price, OrderSide.BUY)
            notional = fill_price * quantity
            fee      = self._fee_model.calculate(notional, maker)
            total_cost = notional + fee

            # Equity guard
            equity = self._total_equity()
            if total_cost > self.cash:
                return {"status": "rejected", "reason": "insufficient_cash",
                        "required": round(total_cost, 4), "available": round(self.cash, 4)}
            if notional > equity * self.max_position_pct:
                return {"status": "rejected", "reason": "position_size_exceeds_limit",
                        "limit": round(equity * self.max_position_pct, 4)}

            # Deduct cost
            self.cash -= total_cost
            self._total_fees_paid     += fee
            self._total_slippage_paid += slip_per_unit * quantity

            trade_id = str(uuid.uuid4())
            entry = TradeEntry(
                trade_id=trade_id, symbol=symbol, strategy=strategy,
                quantity=quantity, entry_price=fill_price,
                entry_time=time.time(),
                stop_loss=stop_loss, take_profit=take_profit,
                entry_fee=fee,
            )
            self._open_trades[trade_id] = entry

            # Update or create position record
            if symbol in self._positions:
                pos = self._positions[symbol]
                total_qty = pos.quantity + quantity
                pos.avg_entry = (pos.avg_entry * pos.quantity + fill_price * quantity) / total_qty
                pos.quantity  = total_qty
                pos.fees_paid += fee
            else:
                self._positions[symbol] = Position(
                    symbol=symbol, strategy=strategy,
                    quantity=quantity, avg_entry=fill_price,
                    current_price=fill_price,
                    stop_loss=stop_loss, take_profit=take_profit,
                    fees_paid=fee,
                )

            if strategy not in self._active_strategies:
                self._active_strategies.append(strategy)

            self._record_equity()
            logger.debug("OPEN %s qty=%.6f fill=%.6f fee=%.6f", symbol, quantity, fill_price, fee)

            return {
                "status":      "filled",
                "trade_id":    trade_id,
                "symbol":      symbol,
                "side":        "buy",
                "quantity":    quantity,
                "requested_price": price,
                "fill_price":  round(fill_price, 6),
                "fee":         round(fee, 6),
                "slippage":    round(slip_per_unit * quantity, 6),
                "total_cost":  round(total_cost, 4),
                "cash_after":  round(self.cash, 4),
                "strategy":    strategy,
                "confidence":  confidence,
            }

    def close_position(
        self,
        symbol:     str,
        price:      float,
        quantity:   Optional[float] = None,
        strategy:   Optional[str]   = None,
        exit_reason: str = "manual",
        maker:      bool = False,
    ) -> Dict[str, Any]:
        """
        Simulate selling `quantity` (or all) units of `symbol` at `price`.
        Closes the oldest open entry first (FIFO).
        """
        with self._lock:
            if symbol not in self._positions:
                return {"status": "rejected", "reason": "no_open_position", "symbol": symbol}

            pos = self._positions[symbol]
            close_qty = quantity if (quantity and quantity < pos.quantity) else pos.quantity

            fill_price, slip_per_unit = self._slippage.apply(price, OrderSide.SELL)
            notional  = fill_price * close_qty
            fee       = self._fee_model.calculate(notional, maker)
            proceeds  = notional - fee

            self.cash                 += proceeds
            self._total_fees_paid     += fee
            self._total_slippage_paid += slip_per_unit * close_qty

            # Match entries FIFO
            remaining_to_close = close_qty
            strat = strategy or pos.strategy
            closed_records: List[TradeRecord] = []

            entry_ids = [tid for tid, e in self._open_trades.items() if e.symbol == symbol]
            entry_ids.sort(key=lambda tid: self._open_trades[tid].entry_time)

            for tid in entry_ids:
                if remaining_to_close <= 0:
                    break
                entry = self._open_trades[tid]
                match_qty = min(entry.quantity, remaining_to_close)

                entry_notional = entry.entry_price * match_qty
                gross_pnl      = (fill_price - entry.entry_price) * match_qty
                trade_fee      = self._fee_model.calculate(fill_price * match_qty, maker) + \
                                 entry.entry_fee * (match_qty / entry.quantity)
                slip_cost      = slip_per_unit * match_qty
                net_pnl        = gross_pnl - trade_fee - slip_cost
                ret_pct        = gross_pnl / entry_notional if entry_notional > 0 else 0.0

                rec = TradeRecord(
                    journal_id=str(uuid.uuid4()),
                    symbol=symbol, strategy=strat, side="long",
                    quantity=match_qty,
                    entry_price=entry.entry_price, exit_price=fill_price,
                    entry_time=entry.entry_time, exit_time=time.time(),
                    gross_pnl=gross_pnl, fees_paid=trade_fee,
                    net_pnl=net_pnl, return_pct=ret_pct,
                    slippage_paid=slip_cost,
                    stop_loss=entry.stop_loss, take_profit=entry.take_profit,
                    exit_reason=exit_reason,
                )
                capped_append(self._journal, rec)
                closed_records.append(rec)

                remaining_to_close -= match_qty
                if match_qty >= entry.quantity:
                    del self._open_trades[tid]
                else:
                    entry.quantity -= match_qty

            # Update position
            pos.quantity -= close_qty
            if pos.quantity <= 1e-10:
                del self._positions[symbol]
            else:
                pos.current_price = fill_price

            self._record_equity()
            total_net_pnl = sum(r.net_pnl for r in closed_records)
            logger.debug("CLOSE %s qty=%.6f fill=%.6f fee=%.6f pnl=%.4f",
                         symbol, close_qty, fill_price, fee, total_net_pnl)

            return {
                "status":      "filled",
                "symbol":      symbol,
                "side":        "sell",
                "quantity":    close_qty,
                "requested_price": price,
                "fill_price":  round(fill_price, 6),
                "fee":         round(fee, 6),
                "slippage":    round(slip_per_unit * close_qty, 6),
                "proceeds":    round(proceeds, 4),
                "net_pnl":     round(total_net_pnl, 4),
                "cash_after":  round(self.cash, 4),
                "exit_reason": exit_reason,
                "records":     [r.to_dict() for r in closed_records],
            }

    def update_prices(self, prices: Dict[str, float]) -> Dict[str, Any]:
        """
        Update current prices for open positions and check stop/take triggers.
        Returns a dict of triggered exits.
        """
        with self._lock:
            triggered = {}
            for symbol, price in prices.items():
                if symbol in self._positions:
                    pos = self._positions[symbol]
                    pos.current_price = price
                    # Check stop-loss
                    if pos.stop_loss and price <= pos.stop_loss:
                        result = self.close_position(symbol, price, exit_reason="stop_loss")
                        triggered[symbol] = {"trigger": "stop_loss", "price": price, "result": result}
                    # Check take-profit
                    elif pos.take_profit and price >= pos.take_profit:
                        result = self.close_position(symbol, price, exit_reason="take_profit")
                        triggered[symbol] = {"trigger": "take_profit", "price": price, "result": result}
            self._record_equity()
            return triggered

    # ------------------------------------------------------------------
    # Portfolio state
    # ------------------------------------------------------------------

    def _total_equity(self) -> float:
        return self.cash + sum(p.market_value for p in self._positions.values())

    def get_portfolio(self) -> Dict[str, Any]:
        with self._lock:
            equity = self._total_equity()
            return {
                "cash":           round(self.cash, 4),
                "equity":         round(equity, 4),
                "initial_capital": self.initial_capital,
                "total_pnl":      round(equity - self.initial_capital, 4),
                "total_return_pct": round((equity - self.initial_capital) / self.initial_capital * 100, 4) if self.initial_capital > 0 else 0.0,
                "positions":      {s: p.to_dict() for s, p in self._positions.items()},
                "open_positions": len(self._positions),
                "active_strategies": list(self._active_strategies),
                "total_fees_paid":     round(self._total_fees_paid, 4),
                "total_slippage_paid": round(self._total_slippage_paid, 4),
            }

    def get_positions(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [p.to_dict() for p in self._positions.values()]

    # ------------------------------------------------------------------
    # Trade journal
    # ------------------------------------------------------------------

    def get_trades(self, limit: int = 500, strategy: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._lock:
            trades = list(self._journal)
            if strategy:
                trades = [t for t in trades if t.strategy == strategy]
            return [t.to_dict() for t in trades[-limit:]]

    # ------------------------------------------------------------------
    # Performance metrics
    # ------------------------------------------------------------------

    def get_performance(self) -> Dict[str, Any]:
        with self._lock:
            return _compute_metrics(
                journal=self._journal,
                equity_curve=self._equity_curve,
                initial_capital=self.initial_capital,
                current_equity=self._total_equity(),
                total_fees=self._total_fees_paid,
                total_slippage=self._total_slippage_paid,
            )

    def get_strategy_performance(self) -> Dict[str, Dict[str, Any]]:
        """Per-strategy breakdown of performance metrics."""
        with self._lock:
            strategies: Dict[str, List[TradeRecord]] = {}
            for rec in self._journal:
                strategies.setdefault(rec.strategy, []).append(rec)
            result = {}
            for strat, records in strategies.items():
                trades    = records
                wins      = [r for r in trades if r.net_pnl > 0]
                losses    = [r for r in trades if r.net_pnl <= 0]
                net_pnls  = [r.net_pnl for r in trades]
                result[strat] = {
                    "trades":        len(trades),
                    "wins":          len(wins),
                    "losses":        len(losses),
                    "win_rate":      round(len(wins) / len(trades), 4) if trades else 0.0,
                    "total_pnl":     round(sum(net_pnls), 4),
                    "avg_pnl":       round(statistics.mean(net_pnls), 4) if net_pnls else 0.0,
                    "avg_win":       round(statistics.mean([r.net_pnl for r in wins]), 4) if wins else 0.0,
                    "avg_loss":      round(statistics.mean([r.net_pnl for r in losses]), 4) if losses else 0.0,
                    "total_fees":    round(sum(r.fees_paid for r in trades), 4),
                    "total_slippage": round(sum(r.slippage_paid for r in trades), 4),
                }
            return result

    # ------------------------------------------------------------------
    # Equity curve
    # ------------------------------------------------------------------

    def get_equity_curve(self) -> List[Dict[str, float]]:
        with self._lock:
            return [{"time": t, "equity": round(e, 4)} for t, e in self._equity_curve]

    # ------------------------------------------------------------------
    # Reset
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Wipe all state and start fresh from initial_capital."""
        with self._lock:
            self.cash                  = self.initial_capital
            self._positions            = {}
            self._open_trades          = {}
            self._journal              = []
            self._equity_curve         = [(time.time(), self.initial_capital)]
            self._active_strategies    = []
            self._total_fees_paid      = 0.0
            self._total_slippage_paid  = 0.0
            logger.info("PaperTradingEngine reset — capital=%.2f", self.initial_capital)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _record_equity(self) -> None:
        capped_append(self._equity_curve, (time.time(), self._total_equity()))


# ---------------------------------------------------------------------------
# Metrics computation (pure function — reusable by backtester)
# ---------------------------------------------------------------------------

def _compute_metrics(
    journal:        List[TradeRecord],
    equity_curve:   List[Tuple[float, float]],
    initial_capital: float,
    current_equity:  float,
    total_fees:      float,
    total_slippage:  float,
) -> Dict[str, Any]:
    """Compute the full performance metric suite from a trade journal."""

    if not journal:
        return {
            "total_trades": 0, "wins": 0, "losses": 0,
            "win_rate": 0.0, "loss_rate": 0.0,
            "avg_win": 0.0, "avg_loss": 0.0,
            "profit_factor": 0.0,
            "total_pnl": 0.0, "net_profit_after_costs": 0.0,
            "total_return_pct": 0.0,
            "sharpe_ratio": 0.0, "sortino_ratio": 0.0,
            "max_drawdown": 0.0, "max_drawdown_pct": 0.0,
            "total_fees": round(total_fees, 4),
            "total_slippage": round(total_slippage, 4),
            "equity": round(current_equity, 4),
        }

    wins   = [r for r in journal if r.net_pnl > 0]
    losses = [r for r in journal if r.net_pnl <= 0]
    total  = len(journal)
    win_rate  = len(wins)  / total
    loss_rate = len(losses) / total
    avg_win   = statistics.mean([r.net_pnl for r in wins])   if wins   else 0.0
    avg_loss  = statistics.mean([r.net_pnl for r in losses]) if losses else 0.0
    gross_wins  = sum(r.net_pnl for r in wins)
    gross_losses = abs(sum(r.net_pnl for r in losses))
    profit_factor = gross_wins / gross_losses if gross_losses > 0 else float("inf")

    total_pnl   = sum(r.net_pnl for r in journal)
    total_return = (current_equity - initial_capital) / initial_capital if initial_capital > 0 else 0.0

    # --- Sharpe / Sortino from trade returns ---
    returns = [r.return_pct for r in journal]
    daily_rf = RISK_FREE_RATE / ANNUALISATION_FACTOR

    sharpe  = 0.0
    sortino = 0.0
    if len(returns) > 1:
        avg_r = statistics.mean(returns)
        std_r = statistics.stdev(returns)
        if std_r > 0:
            sharpe = ((avg_r - daily_rf) / std_r) * math.sqrt(ANNUALISATION_FACTOR)
        # Sortino — downside deviation only
        down_returns = [r for r in returns if r < daily_rf]
        if down_returns:
            down_var = sum((r - daily_rf) ** 2 for r in down_returns) / len(returns)
            down_std = down_var ** 0.5
            if down_std > 0:
                sortino = ((avg_r - daily_rf) / down_std) * math.sqrt(ANNUALISATION_FACTOR)

    # --- Max drawdown from equity curve ---
    max_dd = 0.0
    peak   = equity_curve[0][1] if equity_curve else initial_capital
    for _, val in equity_curve:
        if val > peak:
            peak = val
        dd = (peak - val) / peak if peak > 0 else 0.0
        if dd > max_dd:
            max_dd = dd

    return {
        "total_trades":  total,
        "wins":          len(wins),
        "losses":        len(losses),
        "win_rate":      round(win_rate,  4),
        "loss_rate":     round(loss_rate, 4),
        "avg_win":       round(avg_win,   4),
        "avg_loss":      round(avg_loss,  4),
        "profit_factor": round(profit_factor, 4) if profit_factor != float("inf") else 999.0,
        "total_pnl":     round(total_pnl, 4),
        "net_profit_after_costs": round(total_pnl - total_fees - total_slippage, 4),
        "total_return_pct": round(total_return * 100, 4),
        "sharpe_ratio":  round(sharpe,  4),
        "sortino_ratio": round(sortino, 4),
        "max_drawdown":  round(max_dd,  4),
        "max_drawdown_pct": round(max_dd * 100, 4),
        "total_fees":    round(total_fees, 4),
        "total_slippage": round(total_slippage, 4),
        "equity":        round(current_equity, 4),
        "initial_capital": initial_capital,
    }
