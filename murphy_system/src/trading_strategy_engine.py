# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Trading Strategy Engine — Murphy System

Provides a pluggable strategy library and a lightweight backtesting engine,
combining best elements of Freqtrade's strategy API, Jesse's signal model,
and Hummingbot's market-making patterns.

Included strategies:
  - GridStrategy         : price-band grid (buy low / sell high)
  - DCAStrategy          : dollar-cost averaging with configurable intervals
  - MomentumStrategy     : RSI + MACD trend-following
  - VWAPStrategy         : VWAP mean-reversion
  - BreakoutStrategy     : range breakout / breakdown
  - MarketMakingStrategy : continuous bid-ask spread capture
  - ArbitrageStrategy    : cross-exchange price-spread capture

All strategies expose a standard ``generate_signal()`` interface and
integrate with the MarketDataFeed for indicators.

Business Source License 1.1 (BSL 1.1)
Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
"""

from __future__ import annotations

import logging
import threading
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class SignalAction(Enum):
    """Trading signal direction (Enum subclass)."""
    BUY          = "buy"
    SELL         = "sell"
    HOLD         = "hold"
    CLOSE_LONG   = "close_long"
    CLOSE_SHORT  = "close_short"
    NO_SIGNAL    = "no_signal"


class StrategyStatus(Enum):
    """Strategy lifecycle state (Enum subclass)."""
    IDLE     = "idle"
    ACTIVE   = "active"
    PAUSED   = "paused"
    STOPPED  = "stopped"
    ERROR    = "error"


# ---------------------------------------------------------------------------
# Signal
# ---------------------------------------------------------------------------

@dataclass
class TradingSignal:
    """Output of a strategy's analysis for a single bar / tick."""
    strategy_id:  str
    pair:         str
    action:       SignalAction
    confidence:   float              = 0.0   # 0.0 → 1.0
    suggested_price: Optional[float] = None
    suggested_size:  Optional[float] = None
    stop_loss:       Optional[float] = None
    take_profit:     Optional[float] = None
    reasoning:       str             = ""
    timestamp:       str             = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    metadata:        Dict[str, Any]  = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Base strategy
# ---------------------------------------------------------------------------

class BaseStrategy(ABC):
    """
    Abstract base class for all Murphy trading strategies.

    Subclasses must implement ``generate_signal()``.  Configuration is
    passed as a plain dict so strategies can be serialised to JSON.
    """

    def __init__(self, strategy_id: str, config: Optional[Dict[str, Any]] = None) -> None:
        self.strategy_id = strategy_id
        self.config      = config or {}
        self.status      = StrategyStatus.IDLE
        self._lock       = threading.Lock()
        self._signal_history: List[TradingSignal] = []

    @abstractmethod
    def generate_signal(
        self,
        pair:        str,
        market_data: Any,   # MarketDataFeed
        indicators:  Any,   # TechnicalIndicators
    ) -> TradingSignal:
        """Analyse current market state and return a trading signal."""

    def record_signal(self, signal: TradingSignal) -> None:
        """Append *signal* to the rolling history (max 10 000 entries)."""
        with self._lock:
            try:
                from thread_safe_operations import capped_append
            except ImportError:
                def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
                    """Fallback bounded append (CWE-770)."""
                    if len(target_list) >= max_size:
                        del target_list[: max_size // 10]
                    target_list.append(item)
            capped_append(self._signal_history, signal, 10_000)

    def get_signal_history(self, limit: int = 100) -> List[TradingSignal]:
        """Return the *limit* most recent signals."""
        with self._lock:
            return list(self._signal_history[-limit:])

    def to_dict(self) -> Dict[str, Any]:
        """Serialise strategy metadata for storage or UI display."""
        return {
            "strategy_id":  self.strategy_id,
            "strategy_type": type(self).__name__,
            "status":       self.status.value,
            "config":       self.config,
        }


# ---------------------------------------------------------------------------
# Concrete strategies
# ---------------------------------------------------------------------------

class GridStrategy(BaseStrategy):
    """
    Price-band grid trading.

    Maintains a ladder of limit orders between *lower* and *upper* price
    bounds, divided into *num_grids* equal bands.  Generates BUY signals
    when price is near a grid support level and SELL signals near resistance.

    Config keys:
      lower_price  (float) — grid lower bound
      upper_price  (float) — grid upper bound
      num_grids    (int)   — number of grid levels (default: 10)
      order_size   (float) — base order size in quote currency
    """

    def generate_signal(self, pair: str, market_data: Any, indicators: Any) -> TradingSignal:
        lower      = float(self.config.get("lower_price", 0))
        upper      = float(self.config.get("upper_price", 0))
        num_grids  = max(int(self.config.get("num_grids", 10)), 2)
        order_size = float(self.config.get("order_size", 100.0))
        current    = float(indicators.ema_9 or 0)

        if lower >= upper or current <= 0:
            return TradingSignal(
                strategy_id=self.strategy_id, pair=pair,
                action=SignalAction.NO_SIGNAL, reasoning="invalid_grid_config",
            )

        grid_step  = (upper - lower) / num_grids
        grid_levels = [lower + i * grid_step for i in range(num_grids + 1)]
        nearest    = min(grid_levels, key=lambda gl: abs(gl - current))
        proximity  = abs(current - nearest) / (grid_step or 1)
        confidence = max(0.0, 1.0 - proximity * 2)

        if current <= nearest and confidence > 0.3:
            action = SignalAction.BUY
        elif current >= nearest and confidence > 0.3:
            action = SignalAction.SELL
        else:
            action = SignalAction.HOLD

        signal = TradingSignal(
            strategy_id     = self.strategy_id,
            pair            = pair,
            action          = action,
            confidence      = confidence,
            suggested_price = nearest,
            suggested_size  = order_size / (nearest or 1),
            reasoning       = f"grid nearest={nearest:.4f} proximity={proximity:.3f}",
        )
        self.record_signal(signal)
        return signal


class DCAStrategy(BaseStrategy):
    """
    Dollar-cost averaging accumulation.

    Generates a BUY signal on every *interval_hours* interval regardless
    of price, with position size scaled by *invest_amount_usd*.

    Config keys:
      interval_hours    (int)   — hours between DCA buys (default: 24)
      invest_amount_usd (float) — USD to invest per DCA round
      rsi_max           (float) — skip buy if RSI > this threshold (default: 75)
    """

    def __init__(self, strategy_id: str, config: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(strategy_id, config)
        self._last_buy_ts: float = 0.0

    def generate_signal(self, pair: str, market_data: Any, indicators: Any) -> TradingSignal:
        import time
        interval_hours    = int(self.config.get("interval_hours", 24))
        invest_usd        = float(self.config.get("invest_amount_usd", 100.0))
        rsi_max           = float(self.config.get("rsi_max", 75.0))
        seconds_between   = interval_hours * 3600
        now               = time.time()
        rsi               = indicators.rsi_14

        if (now - self._last_buy_ts) < seconds_between:
            return TradingSignal(
                strategy_id=self.strategy_id, pair=pair,
                action=SignalAction.HOLD,
                reasoning=f"dca_interval_not_elapsed remaining={int(seconds_between - (now - self._last_buy_ts))}s",
            )
        if rsi is not None and rsi > rsi_max:
            return TradingSignal(
                strategy_id=self.strategy_id, pair=pair,
                action=SignalAction.HOLD,
                reasoning=f"dca_rsi_too_high rsi={rsi:.1f} max={rsi_max}",
            )

        current_price = indicators.ema_9 or 1.0
        self._last_buy_ts = now
        signal = TradingSignal(
            strategy_id     = self.strategy_id,
            pair            = pair,
            action          = SignalAction.BUY,
            confidence      = 0.7,
            suggested_size  = invest_usd / current_price,
            reasoning       = f"dca_interval_elapsed invest_usd={invest_usd}",
        )
        self.record_signal(signal)
        return signal


class MomentumStrategy(BaseStrategy):
    """
    RSI + MACD trend-following momentum strategy.

    BUY  when RSI < oversold threshold AND MACD histogram turns positive.
    SELL when RSI > overbought threshold AND MACD histogram turns negative.

    Config keys:
      rsi_oversold     (float) — default 30
      rsi_overbought   (float) — default 70
      order_size_usd   (float) — default 500
    """

    def generate_signal(self, pair: str, market_data: Any, indicators: Any) -> TradingSignal:
        rsi         = indicators.rsi_14
        macd_hist   = indicators.macd_hist
        oversold    = float(self.config.get("rsi_oversold", 30.0))
        overbought  = float(self.config.get("rsi_overbought", 70.0))
        order_size  = float(self.config.get("order_size_usd", 500.0))

        if rsi is None or macd_hist is None:
            return TradingSignal(
                strategy_id=self.strategy_id, pair=pair,
                action=SignalAction.NO_SIGNAL, reasoning="insufficient_indicator_data",
            )

        current_price = indicators.ema_9 or 1.0
        action     = SignalAction.HOLD
        confidence = 0.0

        if rsi < oversold and macd_hist > 0:
            action     = SignalAction.BUY
            confidence = min(1.0, (oversold - rsi) / oversold + macd_hist * 10)
        elif rsi > overbought and macd_hist < 0:
            action     = SignalAction.SELL
            confidence = min(1.0, (rsi - overbought) / (100 - overbought) + abs(macd_hist) * 10)

        signal = TradingSignal(
            strategy_id     = self.strategy_id,
            pair            = pair,
            action          = action,
            confidence      = round(confidence, 4),
            suggested_size  = order_size / (current_price or 1),
            reasoning       = f"momentum rsi={rsi:.1f} macd_hist={macd_hist:.6f}",
        )
        self.record_signal(signal)
        return signal


class VWAPStrategy(BaseStrategy):
    """
    VWAP mean-reversion strategy.

    BUY  when price drops >*deviation_pct*% below VWAP.
    SELL when price rises >*deviation_pct*% above VWAP.

    Config keys:
      deviation_pct  (float) — percentage deviation to trigger (default 1.5)
      order_size_usd (float) — default 500
    """

    def generate_signal(self, pair: str, market_data: Any, indicators: Any) -> TradingSignal:
        vwap       = indicators.vwap
        ema_9      = indicators.ema_9
        deviation  = float(self.config.get("deviation_pct", 1.5)) / 100.0
        order_size = float(self.config.get("order_size_usd", 500.0))

        if vwap is None or ema_9 is None or vwap == 0:
            return TradingSignal(
                strategy_id=self.strategy_id, pair=pair,
                action=SignalAction.NO_SIGNAL, reasoning="vwap_unavailable",
            )

        ratio      = (ema_9 - vwap) / vwap
        action     = SignalAction.HOLD
        confidence = 0.0

        if ratio < -deviation:
            action     = SignalAction.BUY
            confidence = min(1.0, abs(ratio) / deviation - 1.0)
        elif ratio > deviation:
            action     = SignalAction.SELL
            confidence = min(1.0, ratio / deviation - 1.0)

        signal = TradingSignal(
            strategy_id     = self.strategy_id,
            pair            = pair,
            action          = action,
            confidence      = round(confidence, 4),
            suggested_price = vwap,
            suggested_size  = order_size / (ema_9 or 1),
            reasoning       = f"vwap_reversion vwap={vwap:.4f} ema9={ema_9:.4f} ratio={ratio:.4f}",
        )
        self.record_signal(signal)
        return signal


class BreakoutStrategy(BaseStrategy):
    """
    Bollinger Band breakout / breakdown strategy.

    BUY  when close crosses above the upper Bollinger Band.
    SELL when close crosses below the lower Bollinger Band.

    Config keys:
      order_size_usd (float) — default 500
      bb_period      (int)   — default 20
    """

    def generate_signal(self, pair: str, market_data: Any, indicators: Any) -> TradingSignal:
        bb_upper   = indicators.bb_upper
        bb_lower   = indicators.bb_lower
        bb_mid     = indicators.bb_mid
        ema_9      = indicators.ema_9
        order_size = float(self.config.get("order_size_usd", 500.0))

        if None in (bb_upper, bb_lower, bb_mid, ema_9):
            return TradingSignal(
                strategy_id=self.strategy_id, pair=pair,
                action=SignalAction.NO_SIGNAL, reasoning="bb_unavailable",
            )

        band_width = (bb_upper - bb_lower) / (bb_mid or 1)
        action     = SignalAction.HOLD
        confidence = 0.0

        if ema_9 > bb_upper:
            action     = SignalAction.BUY
            confidence = min(1.0, (ema_9 - bb_upper) / (bb_upper or 1) * 10 + 0.5)
        elif ema_9 < bb_lower:
            action     = SignalAction.SELL
            confidence = min(1.0, (bb_lower - ema_9) / (bb_lower or 1) * 10 + 0.5)

        signal = TradingSignal(
            strategy_id     = self.strategy_id,
            pair            = pair,
            action          = action,
            confidence      = round(confidence, 4),
            suggested_size  = order_size / (ema_9 or 1),
            reasoning       = f"breakout bb_upper={bb_upper:.4f} bb_lower={bb_lower:.4f} price={ema_9:.4f}",
        )
        self.record_signal(signal)
        return signal


class MarketMakingStrategy(BaseStrategy):
    """
    Continuous bid-ask spread capture (market-making).

    Places a BUY limit at mid - *spread_pct*/2 and a SELL limit at
    mid + *spread_pct*/2 simultaneously.  Signal alternates BUY/SELL
    to drive the bot engine to refresh both sides.

    Config keys:
      spread_pct     (float) — half-spread percentage (default 0.2)
      order_size_usd (float) — default 200
    """

    def __init__(self, strategy_id: str, config: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(strategy_id, config)
        self._next_side: SignalAction = SignalAction.BUY

    def generate_signal(self, pair: str, market_data: Any, indicators: Any) -> TradingSignal:
        ema_9      = indicators.ema_9
        spread_pct = float(self.config.get("spread_pct", 0.2)) / 100.0
        order_size = float(self.config.get("order_size_usd", 200.0))

        if not ema_9:
            return TradingSignal(
                strategy_id=self.strategy_id, pair=pair,
                action=SignalAction.NO_SIGNAL, reasoning="price_unavailable",
            )

        if self._next_side == SignalAction.BUY:
            price            = ema_9 * (1 - spread_pct)
            self._next_side  = SignalAction.SELL
        else:
            price            = ema_9 * (1 + spread_pct)
            self._next_side  = SignalAction.BUY

        action = SignalAction.BUY if price < ema_9 else SignalAction.SELL
        signal = TradingSignal(
            strategy_id     = self.strategy_id,
            pair            = pair,
            action          = action,
            confidence      = 0.6,
            suggested_price = price,
            suggested_size  = order_size / (price or 1),
            reasoning       = f"market_making spread={spread_pct*100:.3f}% price={price:.4f}",
        )
        self.record_signal(signal)
        return signal


class ArbitrageStrategy(BaseStrategy):
    """
    Cross-exchange price-spread capture.

    Compares the last price on two exchanges; generates BUY on the cheaper
    and SELL on the more expensive when the spread exceeds *min_spread_pct*.

    Config keys:
      exchange_a     (str)   — first exchange ID
      exchange_b     (str)   — second exchange ID
      min_spread_pct (float) — minimum spread to trigger (default 0.5)
      order_size_usd (float) — default 500
    """

    def generate_signal(self, pair: str, market_data: Any, indicators: Any) -> TradingSignal:
        ex_a       = self.config.get("exchange_a", "")
        ex_b       = self.config.get("exchange_b", "")
        min_spread = float(self.config.get("min_spread_pct", 0.5)) / 100.0
        order_size = float(self.config.get("order_size_usd", 500.0))

        if not (ex_a and ex_b and market_data is not None):
            return TradingSignal(
                strategy_id=self.strategy_id, pair=pair,
                action=SignalAction.NO_SIGNAL, reasoning="arbitrage_config_missing",
            )

        try:
            ticker_a = market_data.get_ticker(ex_a, pair)
            ticker_b = market_data.get_ticker(ex_b, pair)
            if ticker_a is None or ticker_b is None:
                return TradingSignal(
                    strategy_id=self.strategy_id, pair=pair,
                    action=SignalAction.NO_SIGNAL, reasoning="ticker_unavailable",
                )
            price_a = ticker_a.last
            price_b = ticker_b.last
        except Exception as exc:
            logger.debug("ArbitrageStrategy ticker fetch: %s", exc)
            return TradingSignal(
                strategy_id=self.strategy_id, pair=pair,
                action=SignalAction.NO_SIGNAL, reasoning=f"ticker_error:{exc}",
            )

        spread = abs(price_a - price_b) / ((price_a + price_b) / 2.0 or 1)
        if spread < min_spread:
            return TradingSignal(
                strategy_id=self.strategy_id, pair=pair,
                action=SignalAction.HOLD,
                reasoning=f"arbitrage_spread_too_small spread={spread*100:.3f}%",
            )

        buy_exchange  = ex_a if price_a < price_b else ex_b
        sell_exchange = ex_b if price_a < price_b else ex_a
        buy_price     = min(price_a, price_b)
        signal = TradingSignal(
            strategy_id     = self.strategy_id,
            pair             = pair,
            action           = SignalAction.BUY,
            confidence       = min(1.0, spread / min_spread - 1.0),
            suggested_price  = buy_price,
            suggested_size   = order_size / (buy_price or 1),
            reasoning        = (
                f"arbitrage spread={spread*100:.3f}% "
                f"buy={buy_exchange}@{buy_price:.4f} "
                f"sell={sell_exchange}"
            ),
            metadata         = {"buy_exchange": buy_exchange, "sell_exchange": sell_exchange},
        )
        self.record_signal(signal)
        return signal


# ---------------------------------------------------------------------------
# Strategy registry
# ---------------------------------------------------------------------------

class StrategyRegistry:
    """
    Thread-safe catalogue of instantiated strategies.

    Strategies are keyed by their ``strategy_id``.  The registry also
    tracks per-strategy performance statistics populated by the bot engine.
    """

    def __init__(self) -> None:
        self._lock       = threading.Lock()
        self._strategies: Dict[str, BaseStrategy] = {}

    def register(self, strategy: BaseStrategy) -> str:
        """Add *strategy* to the registry.  Returns its ID."""
        with self._lock:
            self._strategies[strategy.strategy_id] = strategy
        logger.info("StrategyRegistry: registered %s", strategy.strategy_id)
        return strategy.strategy_id

    def get(self, strategy_id: str) -> Optional[BaseStrategy]:
        """Retrieve a strategy by ID."""
        with self._lock:
            return self._strategies.get(strategy_id)

    def list_strategies(self) -> List[Dict[str, Any]]:
        """Return serialised metadata for all registered strategies."""
        with self._lock:
            return [s.to_dict() for s in self._strategies.values()]

    def remove(self, strategy_id: str) -> bool:
        """Unregister a strategy."""
        with self._lock:
            removed = self._strategies.pop(strategy_id, None)
        return removed is not None


# ---------------------------------------------------------------------------
# Backtester
# ---------------------------------------------------------------------------

@dataclass
class BacktestTrade:
    """A simulated trade during a backtest run."""
    trade_id:    str
    pair:        str
    action:      SignalAction
    entry_price: float
    exit_price:  float
    quantity:    float
    pnl:         float
    pnl_pct:     float
    entry_time:  int
    exit_time:   int


@dataclass
class BacktestResult:
    """Aggregated result from a full backtest run."""
    strategy_id:     str
    pair:            str
    total_trades:    int
    winning_trades:  int
    losing_trades:   int
    win_rate:        float
    total_pnl:       float
    max_drawdown:    float
    sharpe_ratio:    Optional[float]
    profit_factor:   float
    trades:          List[BacktestTrade] = field(default_factory=list)


class Backtester:
    """
    Simple event-driven backtester that replays a candle series through
    any ``BaseStrategy`` implementation.
    """

    FEE_RATE = 0.001   # 0.10 %

    def run(
        self,
        strategy:       BaseStrategy,
        candles:        List[Any],   # List[Candle]
        initial_capital: float = 10_000.0,
    ) -> BacktestResult:
        """
        Walk *candles* forward, call ``generate_signal`` at each bar,
        and simulate fills.  Returns a ``BacktestResult`` summary.
        """
        from market_data_feed import (
            CandleGranularity,
            TechnicalIndicators,
            _atr,
            _bollinger_bands,
            _ema,
            _macd,
            _rsi,
            _vwap,
        )

        pair        = candles[0].pair if candles else "UNKNOWN"
        capital     = initial_capital
        position    = 0.0
        entry_price = 0.0
        trades: List[BacktestTrade] = []
        equity_curve: List[float]   = [capital]
        peak_equity   = capital

        for i in range(50, len(candles)):
            window  = candles[:i]
            closes  = [c.close for c in window]
            ind     = TechnicalIndicators(pair=pair, granularity=CandleGranularity.ONE_HOUR)
            ind.rsi_14  = _rsi(closes)
            ind.ema_9   = _ema(closes, 9)
            ind.ema_21  = _ema(closes, 21)
            ind.macd, ind.macd_signal, ind.macd_hist = _macd(closes)
            ind.bb_upper, ind.bb_mid, ind.bb_lower   = _bollinger_bands(closes)
            ind.atr_14  = _atr(window)
            ind.vwap    = _vwap(window)

            signal = strategy.generate_signal(pair, None, ind)
            price  = candles[i].close

            if signal.action == SignalAction.BUY and position == 0.0 and capital > 0:
                size      = signal.suggested_size or (capital * 0.1 / (price or 1))
                cost      = price * size * (1 + self.FEE_RATE)
                if cost <= capital:
                    capital    -= cost
                    position    = size
                    entry_price = price

            elif signal.action in (SignalAction.SELL, SignalAction.CLOSE_LONG) and position > 0:
                proceeds    = price * position * (1 - self.FEE_RATE)
                pnl         = proceeds - entry_price * position
                pnl_pct     = pnl / (entry_price * position or 1)
                trades.append(BacktestTrade(
                    trade_id    = str(uuid.uuid4()),
                    pair        = pair,
                    action      = signal.action,
                    entry_price = entry_price,
                    exit_price  = price,
                    quantity    = position,
                    pnl         = pnl,
                    pnl_pct     = pnl_pct,
                    entry_time  = candles[i - 1].open_time,
                    exit_time   = candles[i].open_time,
                ))
                capital  += proceeds
                position  = 0.0
                equity_curve.append(capital)
                peak_equity = max(peak_equity, capital)

        # Liquidate remaining position at last price
        if position > 0 and candles:
            last_price = candles[-1].close
            capital   += last_price * position * (1 - self.FEE_RATE)

        winning  = [t for t in trades if t.pnl > 0]
        losing   = [t for t in trades if t.pnl <= 0]
        total_pnl = capital - initial_capital
        win_rate  = len(winning) / (len(trades) or 1)
        gross_profit = sum(t.pnl for t in winning)
        gross_loss   = abs(sum(t.pnl for t in losing))
        profit_factor = gross_profit / (gross_loss or 1)

        # Max drawdown
        max_dd = 0.0
        peak   = initial_capital
        for eq in equity_curve:
            peak   = max(peak, eq)
            max_dd = max(max_dd, (peak - eq) / (peak or 1))

        # Sharpe (annualised, assuming daily returns)
        returns = []
        for j in range(1, len(equity_curve)):
            returns.append((equity_curve[j] - equity_curve[j - 1]) / (equity_curve[j - 1] or 1))
        import statistics as _stats
        sharpe = None
        if len(returns) > 2:
            mean_r = sum(returns) / len(returns)
            std_r  = _stats.pstdev(returns)
            sharpe = (mean_r / (std_r or 1)) * (252 ** 0.5)

        return BacktestResult(
            strategy_id    = strategy.strategy_id,
            pair           = pair,
            total_trades   = len(trades),
            winning_trades = len(winning),
            losing_trades  = len(losing),
            win_rate       = win_rate,
            total_pnl      = total_pnl,
            max_drawdown   = max_dd,
            sharpe_ratio   = sharpe,
            profit_factor  = profit_factor,
            trades         = trades,
        )
