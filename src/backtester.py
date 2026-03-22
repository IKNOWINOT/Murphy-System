"""
Backtester — Murphy System

Runs any strategy template against historical OHLCV data and produces a
full performance report (same metrics as the paper trading engine).

Features
--------
- Accept historical OHLCV data from CSV files or pre-loaded dicts
- Run any BaseStrategy subclass against historical data
- Support multiple timeframes: 1m, 5m, 15m, 1h, 4h, 1d
- Compare multiple strategies side-by-side
- Output results as JSON for dashboard consumption
- Optionally integrates with yfinance for live historical downloads

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import csv
import io
import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from paper_trading_engine import PaperTradingEngine, _compute_metrics, DEFAULT_CAPITAL
from strategy_templates.base_strategy import BaseStrategy, MarketBar

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Timeframe constants
# ---------------------------------------------------------------------------

class Timeframe(Enum):
    ONE_MINUTE    = "1m"
    FIVE_MINUTES  = "5m"
    FIFTEEN_MINUTES = "15m"
    ONE_HOUR      = "1h"
    FOUR_HOURS    = "4h"
    ONE_DAY       = "1d"

    @property
    def seconds(self) -> int:
        return {
            "1m":  60, "5m": 300, "15m": 900,
            "1h": 3600, "4h": 14400, "1d": 86400,
        }[self.value]


# ---------------------------------------------------------------------------
# OHLCV row
# ---------------------------------------------------------------------------

@dataclass
class OHLCVRow:
    timestamp: float   # Unix epoch
    open:      float
    high:      float
    low:       float
    close:     float
    volume:    float

    def to_bar(self, symbol: str) -> MarketBar:
        return MarketBar(
            symbol=symbol,
            timestamp=self.timestamp,
            open=self.open,
            high=self.high,
            low=self.low,
            close=self.close,
            volume=self.volume,
        )


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------

def load_csv(
    path: Union[str, Path],
    symbol: str,
    timestamp_col: str = "timestamp",
    open_col: str = "open",
    high_col: str = "high",
    low_col:  str = "low",
    close_col: str = "close",
    volume_col: str = "volume",
    timestamp_is_ms: bool = False,
) -> List[OHLCVRow]:
    """Load OHLCV data from a CSV file."""
    rows: List[OHLCVRow] = []
    with open(str(path), newline="") as fh:
        reader = csv.DictReader(fh)
        for line in reader:
            ts = float(line[timestamp_col])
            if timestamp_is_ms:
                ts /= 1000.0
            rows.append(OHLCVRow(
                timestamp=ts,
                open=float(line[open_col]),
                high=float(line[high_col]),
                low=float(line[low_col]),
                close=float(line[close_col]),
                volume=float(line[volume_col]),
            ))
    rows.sort(key=lambda r: r.timestamp)
    logger.info("Loaded %d rows from %s for %s", len(rows), path, symbol)
    return rows


def load_dicts(rows: List[Dict[str, Any]]) -> List[OHLCVRow]:
    """Load OHLCV data from a list of dicts (API response format)."""
    result = []
    for r in rows:
        ts = float(r.get("timestamp", r.get("time", r.get("t", 0))))
        if ts > 1e12:   # milliseconds
            ts /= 1000.0
        result.append(OHLCVRow(
            timestamp=ts,
            open=float(r.get("open",  r.get("o", 0))),
            high=float(r.get("high",  r.get("h", 0))),
            low=float(r.get("low",   r.get("l", 0))),
            close=float(r.get("close", r.get("c", 0))),
            volume=float(r.get("volume", r.get("v", 0))),
        ))
    result.sort(key=lambda r: r.timestamp)
    return result


def load_yfinance(
    symbol: str,
    period: str = "6mo",
    interval: str = "1d",
) -> List[OHLCVRow]:
    """
    Download historical data via yfinance (lazy import).
    Returns an empty list if yfinance is not installed.
    """
    try:
        import yfinance as yf  # type: ignore[import]
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period, interval=interval)
        rows = []
        for dt, row in df.iterrows():
            # pandas DatetimeTZDtype has .timestamp(); pandas Timestamp uses .value (nanoseconds)
            ts = dt.timestamp() if hasattr(dt, "timestamp") else float(dt.value) / 1e9
            rows.append(OHLCVRow(
                timestamp=ts,
                open=float(row["Open"]),
                high=float(row["High"]),
                low=float(row["Low"]),
                close=float(row["Close"]),
                volume=float(row["Volume"]),
            ))
        logger.info("yfinance: downloaded %d rows for %s (%s %s)", len(rows), symbol, period, interval)
        return rows
    except ImportError:
        logger.warning("yfinance not installed — run: pip install yfinance")
        return []
    except Exception as exc:
        logger.warning("yfinance download failed for %s: %s", symbol, exc)
        return []


# ---------------------------------------------------------------------------
# BacktestResult
# ---------------------------------------------------------------------------

@dataclass
class BacktestResult:
    strategy_name: str
    symbol:        str
    timeframe:     str
    start_time:    float
    end_time:      float
    total_bars:    int
    metrics:       Dict[str, Any]
    equity_curve:  List[Dict[str, float]]
    trades:        List[Dict[str, Any]]
    run_duration_s: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy":     self.strategy_name,
            "symbol":       self.symbol,
            "timeframe":    self.timeframe,
            "start_date":   datetime.fromtimestamp(self.start_time, tz=timezone.utc).isoformat(),
            "end_date":     datetime.fromtimestamp(self.end_time,   tz=timezone.utc).isoformat(),
            "total_bars":   self.total_bars,
            "metrics":      self.metrics,
            "equity_curve": self.equity_curve,
            "trades":       self.trades,
            "run_duration_s": round(self.run_duration_s, 3),
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str)


# ---------------------------------------------------------------------------
# Backtester
# ---------------------------------------------------------------------------

class Backtester:
    """
    Runs strategy templates against historical OHLCV data.

    Parameters
    ----------
    initial_capital:  Starting portfolio cash ($).
    taker_fee_rate:   Simulated exchange taker fee.
    slippage_bps:     Simulated slippage in basis points.
    warmup_bars:      Number of bars to feed before trading starts (indicator warm-up).
    position_size_pct: Fraction of equity to deploy per signal.
    """

    def __init__(
        self,
        initial_capital:   float = DEFAULT_CAPITAL,
        taker_fee_rate:    float = 0.001,
        slippage_bps:      float = 5.0,
        warmup_bars:       int   = 50,
        position_size_pct: float = 0.10,
    ) -> None:
        self.initial_capital   = initial_capital
        self.taker_fee_rate    = taker_fee_rate
        self.slippage_bps      = slippage_bps
        self.warmup_bars       = warmup_bars
        self.position_size_pct = position_size_pct

    # ------------------------------------------------------------------
    # Single-strategy run
    # ------------------------------------------------------------------

    def run(
        self,
        strategy:  BaseStrategy,
        ohlcv:     List[OHLCVRow],
        symbol:    str,
        timeframe: str = "1d",
    ) -> BacktestResult:
        """
        Replay historical OHLCV bars through a strategy and return results.
        Positions are automatically closed at the end of the data.
        """
        t0 = time.time()

        engine = PaperTradingEngine(
            initial_capital=self.initial_capital,
            taker_fee_rate=self.taker_fee_rate,
            slippage_bps=self.slippage_bps,
        )

        bars: List[MarketBar] = []
        total_bars = len(ohlcv)

        for i, row in enumerate(ohlcv):
            bar = row.to_bar(symbol)
            bars.append(bar)

            # Update open position prices (triggers S/L and T/P checks)
            engine.update_prices({symbol: bar.close})

            if i < self.warmup_bars:
                continue

            # Ask strategy for a signal
            signal = strategy.analyze(bars)

            position = engine._positions.get(symbol)  # noqa: SLF001

            if signal.action.value == "buy" and position is None:
                qty = self._calc_qty(engine, bar.close, signal)
                if qty > 0:
                    engine.open_position(
                        symbol=symbol, quantity=qty, price=bar.close,
                        strategy=strategy.strategy_id,
                        confidence=signal.confidence,
                        stop_loss=signal.stop_loss,
                        take_profit=signal.take_profit,
                    )

            elif signal.action.value == "sell" and position is not None:
                engine.close_position(symbol=symbol, price=bar.close, exit_reason="strategy_signal")

        # Close any remaining open position at last price
        if symbol in engine._positions and ohlcv:  # noqa: SLF001
            last_price = ohlcv[-1].close
            engine.close_position(symbol=symbol, price=last_price, exit_reason="backtest_end")

        metrics = engine.get_performance()
        result = BacktestResult(
            strategy_name=strategy.strategy_id,
            symbol=symbol,
            timeframe=timeframe,
            start_time=ohlcv[0].timestamp if ohlcv else 0,
            end_time=ohlcv[-1].timestamp  if ohlcv else 0,
            total_bars=total_bars,
            metrics=metrics,
            equity_curve=engine.get_equity_curve(),
            trades=engine.get_trades(),
            run_duration_s=time.time() - t0,
        )
        logger.info(
            "Backtest %s/%s: %d trades, return=%.2f%%, sharpe=%.2f",
            strategy.strategy_id, symbol,
            metrics["total_trades"], metrics["total_return_pct"], metrics["sharpe_ratio"],
        )
        return result

    # ------------------------------------------------------------------
    # Multi-strategy comparison
    # ------------------------------------------------------------------

    def compare(
        self,
        strategies: List[BaseStrategy],
        ohlcv:      List[OHLCVRow],
        symbol:     str,
        timeframe:  str = "1d",
    ) -> Dict[str, Any]:
        """
        Run multiple strategies on the same dataset and return a side-by-side comparison.
        """
        results = [self.run(s, ohlcv, symbol, timeframe) for s in strategies]

        comparison = {
            "symbol":    symbol,
            "timeframe": timeframe,
            "strategies": {},
            "ranking":   [],
        }

        for r in results:
            comparison["strategies"][r.strategy_name] = {
                "total_return_pct": r.metrics.get("total_return_pct", 0),
                "sharpe_ratio":     r.metrics.get("sharpe_ratio", 0),
                "sortino_ratio":    r.metrics.get("sortino_ratio", 0),
                "max_drawdown_pct": r.metrics.get("max_drawdown_pct", 0),
                "win_rate":         r.metrics.get("win_rate", 0),
                "total_trades":     r.metrics.get("total_trades", 0),
                "profit_factor":    r.metrics.get("profit_factor", 0),
                "total_fees":       r.metrics.get("total_fees", 0),
                "net_profit_after_costs": r.metrics.get("net_profit_after_costs", 0),
            }

        # Rank by Sharpe ratio
        ranked = sorted(
            comparison["strategies"].items(),
            key=lambda kv: kv[1]["sharpe_ratio"],
            reverse=True,
        )
        comparison["ranking"] = [name for name, _ in ranked]
        comparison["winner"]  = ranked[0][0] if ranked else None

        return comparison

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _calc_qty(self, engine: PaperTradingEngine, price: float, signal: Any) -> float:
        """Calculate position size from signal or default position_size_pct."""
        equity     = engine._total_equity()  # noqa: SLF001
        size_frac  = signal.suggested_size if signal.suggested_size else self.position_size_pct
        target_val = equity * size_frac
        if price <= 0:
            return 0.0
        return target_val / price
