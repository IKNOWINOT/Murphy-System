# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Market Data Feed — Murphy System

Provides real-time and historical OHLCV candles, order-book snapshots,
best-bid-ask tickers, and computed technical indicators for all
registered trading pairs.

Key capabilities:
  - Multi-exchange candle cache with configurable TTL
  - On-demand technical indicators: RSI, MACD, Bollinger Bands, ATR, VWAP, EMA
  - Order-book normalisation and spread calculation
  - WebSocket-push model for live price subscriptions
  - Thread-safe subscription manager

Business Source License 1.1 (BSL 1.1)
Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
"""

from __future__ import annotations

import logging
import math
import statistics
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_MAX_CANDLES_CACHE  = 10_000
_MAX_BOOK_DEPTH     = 500
_DEFAULT_CANDLE_TTL = 300   # seconds before cache is considered stale


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class CandleGranularity(Enum):
    """Supported OHLCV timeframe granularities (Enum subclass)."""
    ONE_MINUTE    = "ONE_MINUTE"
    FIVE_MINUTE   = "FIVE_MINUTE"
    FIFTEEN_MINUTE= "FIFTEEN_MINUTE"
    THIRTY_MINUTE = "THIRTY_MINUTE"
    ONE_HOUR      = "ONE_HOUR"
    TWO_HOUR      = "TWO_HOUR"
    SIX_HOUR      = "SIX_HOUR"
    ONE_DAY       = "ONE_DAY"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Candle:
    """Single OHLCV candle."""
    exchange:    str
    pair:        str
    granularity: CandleGranularity
    open_time:   int     # Unix epoch (seconds)
    open:        float
    high:        float
    low:         float
    close:       float
    volume:      float


@dataclass
class OrderBookLevel:
    """Single price level in an order book."""
    price:  float
    size:   float


@dataclass
class OrderBook:
    """L2 order book snapshot."""
    exchange:  str
    pair:      str
    bids:      List[OrderBookLevel]  # sorted descending
    asks:      List[OrderBookLevel]  # sorted ascending
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @property
    def best_bid(self) -> float:
        """Highest bid price."""
        return self.bids[0].price if self.bids else 0.0

    @property
    def best_ask(self) -> float:
        """Lowest ask price."""
        return self.asks[0].price if self.asks else 0.0

    @property
    def spread(self) -> float:
        """Absolute bid-ask spread."""
        return self.best_ask - self.best_bid

    @property
    def mid_price(self) -> float:
        """Mid-point between best bid and best ask."""
        return (self.best_bid + self.best_ask) / 2.0 if (self.bids and self.asks) else 0.0


@dataclass
class TechnicalIndicators:
    """Computed technical indicator values for a candle series."""
    pair:       str
    granularity: CandleGranularity
    rsi_14:     Optional[float] = None
    macd:       Optional[float] = None
    macd_signal: Optional[float] = None
    macd_hist:  Optional[float] = None
    bb_upper:   Optional[float] = None
    bb_mid:     Optional[float] = None
    bb_lower:   Optional[float] = None
    atr_14:     Optional[float] = None
    vwap:       Optional[float] = None
    ema_9:      Optional[float] = None
    ema_21:     Optional[float] = None
    ema_50:     Optional[float] = None
    ema_200:    Optional[float] = None
    timestamp:  str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


# ---------------------------------------------------------------------------
# Technical analysis helpers (pure functions, no external deps)
# ---------------------------------------------------------------------------

def _ema(values: List[float], period: int) -> Optional[float]:
    """Compute the last EMA value for *values* using *period*."""
    if len(values) < period:
        return None
    k   = 2.0 / (period + 1)
    ema = sum(values[:period]) / period
    for v in values[period:]:
        ema = v * k + ema * (1 - k)
    return ema


def _rsi(closes: List[float], period: int = 14) -> Optional[float]:
    """Compute the RSI for the last *period* bars."""
    if len(closes) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        delta = closes[i] - closes[i - 1]
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0.0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def _macd(
    closes: List[float],
    fast: int = 12, slow: int = 26, signal: int = 9,
) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """Return (macd_line, signal_line, histogram) or (None, None, None)."""
    if len(closes) < slow + signal:
        return None, None, None
    fast_ema  = _ema(closes, fast)
    slow_ema  = _ema(closes, slow)
    if fast_ema is None or slow_ema is None:
        return None, None, None
    macd_line = fast_ema - slow_ema
    # Approximate signal with last *signal* MACD values
    macd_series = []
    for i in range(signal + 1, len(closes) + 1):
        fe = _ema(closes[:i], fast)
        se = _ema(closes[:i], slow)
        if fe is not None and se is not None:
            macd_series.append(fe - se)
    sig_line = _ema(macd_series, signal) if macd_series else None
    histogram = (macd_line - sig_line) if sig_line is not None else None
    return macd_line, sig_line, histogram


def _bollinger_bands(
    closes: List[float], period: int = 20, num_std: float = 2.0
) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """Return (upper, middle, lower) Bollinger Band values."""
    if len(closes) < period:
        return None, None, None
    window = closes[-period:]
    mid    = sum(window) / period
    std    = statistics.pstdev(window)
    return mid + num_std * std, mid, mid - num_std * std


def _atr(candles: List[Candle], period: int = 14) -> Optional[float]:
    """Compute Average True Range for the last *period* candles."""
    if len(candles) < period + 1:
        return None
    trs = []
    for i in range(1, len(candles)):
        high  = candles[i].high
        low   = candles[i].low
        prev_close = candles[i - 1].close
        trs.append(max(high - low, abs(high - prev_close), abs(low - prev_close)))
    return sum(trs[-period:]) / period


def _vwap(candles: List[Candle]) -> Optional[float]:
    """Compute VWAP over the provided candle window."""
    total_vol = sum(c.volume for c in candles)
    if total_vol == 0.0:
        return None
    return sum(((c.high + c.low + c.close) / 3.0) * c.volume for c in candles) / total_vol


# ---------------------------------------------------------------------------
# Market data feed
# ---------------------------------------------------------------------------

class MarketDataFeed:
    """
    Aggregates real-time market data from one or more exchanges.

    The feed maintains an in-memory candle cache per (exchange, pair, granularity)
    key with configurable TTL.  Callers can subscribe to price updates via
    callbacks that are invoked whenever new candle data arrives.
    """

    def __init__(self, exchange_registry: Optional[Any] = None, candle_ttl: int = _DEFAULT_CANDLE_TTL) -> None:
        self._registry   = exchange_registry
        self._candle_ttl = candle_ttl
        self._lock       = threading.Lock()
        # (exchange, pair, granularity) → List[Candle]
        self._candle_cache:    Dict[Tuple[str, str, str], List[Candle]] = {}
        self._cache_timestamps: Dict[Tuple[str, str, str], float]       = {}
        # pair → List[callback]
        self._price_callbacks:  Dict[str, List[Callable[[str, float], None]]] = {}

    # ---- candle access ---------------------------------------------------

    def get_candles(
        self,
        exchange:    str,
        pair:        str,
        granularity: CandleGranularity = CandleGranularity.ONE_HOUR,
        limit:       int               = 200,
        force_refresh: bool            = False,
    ) -> List[Candle]:
        """
        Return up to *limit* candles for *pair* on *exchange*.

        Uses the in-memory cache if data is fresh; otherwise fetches from
        the registered exchange connector.
        """
        key   = (exchange, pair, granularity.value)
        stale = force_refresh or self._is_stale(key)

        if stale and self._registry is not None:
            self._refresh_candles(exchange, pair, granularity, limit, key)

        with self._lock:
            cached = self._candle_cache.get(key, [])
            return list(cached[-limit:])

    def push_candle(self, candle: Candle) -> None:
        """Inject a single candle (e.g. from a WebSocket feed)."""
        key = (candle.exchange, candle.pair, candle.granularity.value)
        with self._lock:
            bucket = self._candle_cache.setdefault(key, [])
            try:
                from thread_safe_operations import capped_append
            except ImportError:
                def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
                    """Fallback bounded append (CWE-770)."""
                    if len(target_list) >= max_size:
                        del target_list[: max_size // 10]
                    target_list.append(item)
            capped_append(bucket, candle, _MAX_CANDLES_CACHE)
            self._cache_timestamps[key] = time.monotonic()
        # Notify price subscribers
        for cb in self._price_callbacks.get(candle.pair, []):
            try:
                cb(candle.pair, candle.close)
            except Exception as exc:
                logger.debug("Price callback error: %s", exc)

    # ---- technical indicators -------------------------------------------

    def get_indicators(
        self,
        exchange:    str,
        pair:        str,
        granularity: CandleGranularity = CandleGranularity.ONE_HOUR,
    ) -> TechnicalIndicators:
        """Compute and return all technical indicators for *pair*."""
        candles = self.get_candles(exchange, pair, granularity, limit=250)
        closes  = [c.close for c in candles]
        ind     = TechnicalIndicators(pair=pair, granularity=granularity)
        if closes:
            ind.rsi_14  = _rsi(closes)
            ind.macd, ind.macd_signal, ind.macd_hist = _macd(closes)
            ind.bb_upper, ind.bb_mid, ind.bb_lower   = _bollinger_bands(closes)
            ind.atr_14  = _atr(candles)
            ind.vwap    = _vwap(candles)
            ind.ema_9   = _ema(closes, 9)
            ind.ema_21  = _ema(closes, 21)
            ind.ema_50  = _ema(closes, 50)
            ind.ema_200 = _ema(closes, 200)
        return ind

    # ---- subscriptions ---------------------------------------------------

    def subscribe_price(
        self, pair: str, callback: Callable[[str, float], None]
    ) -> None:
        """Register *callback* to receive (pair, price) updates."""
        with self._lock:
            self._price_callbacks.setdefault(pair, []).append(callback)

    def unsubscribe_price(
        self, pair: str, callback: Callable[[str, float], None]
    ) -> None:
        """Remove a previously registered price callback."""
        with self._lock:
            callbacks = self._price_callbacks.get(pair, [])
            try:
                callbacks.remove(callback)
            except ValueError:
                logger.debug("Callback not found in price_callbacks for %s", pair)

    # ---- internal -------------------------------------------------------

    def _is_stale(self, key: Tuple[str, str, str]) -> bool:
        with self._lock:
            last = self._cache_timestamps.get(key, 0.0)
        return (time.monotonic() - last) > self._candle_ttl

    def _refresh_candles(
        self,
        exchange:    str,
        pair:        str,
        granularity: CandleGranularity,
        limit:       int,
        key:         Tuple[str, str, str],
    ) -> None:
        """Fetch fresh candles from the exchange registry and update cache."""
        connector = self._registry.get(exchange) if self._registry else None
        if connector is None:
            return
        try:
            now   = int(time.time())
            span  = _granularity_seconds(granularity) * limit
            start = now - span
            raw_candles = connector._cb.get_candles(  # type: ignore[attr-defined]
                pair.replace("/", "-"), start, now, granularity.value
            ) if hasattr(connector, "_cb") else []

            candles = []
            for c in raw_candles:
                try:
                    candles.append(Candle(
                        exchange    = exchange,
                        pair        = pair,
                        granularity = granularity,
                        open_time   = int(c.get("start", 0)),
                        open        = float(c.get("open", 0)),
                        high        = float(c.get("high", 0)),
                        low         = float(c.get("low", 0)),
                        close       = float(c.get("close", 0)),
                        volume      = float(c.get("volume", 0)),
                    ))
                except (ValueError, TypeError) as exc:
                    logger.debug("Malformed candle: %s", exc)
            with self._lock:
                self._candle_cache[key]      = candles
                self._cache_timestamps[key]  = time.monotonic()
        except Exception as exc:
            logger.error("MarketDataFeed._refresh_candles error: %s", exc)


def _granularity_seconds(g: CandleGranularity) -> int:
    """Return the duration in seconds for a candle granularity."""
    mapping = {
        CandleGranularity.ONE_MINUTE:     60,
        CandleGranularity.FIVE_MINUTE:    300,
        CandleGranularity.FIFTEEN_MINUTE: 900,
        CandleGranularity.THIRTY_MINUTE:  1_800,
        CandleGranularity.ONE_HOUR:       3_600,
        CandleGranularity.TWO_HOUR:       7_200,
        CandleGranularity.SIX_HOUR:       21_600,
        CandleGranularity.ONE_DAY:        86_400,
    }
    return mapping.get(g, 3_600)
