"""
Base Strategy — Murphy System Paper Trading Engine

Abstract base class for all strategy templates.
Every strategy produces a Signal with action (BUY/SELL/HOLD),
confidence score (0-1), and optional position-sizing / risk hints.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Signal types
# ---------------------------------------------------------------------------

class SignalAction(Enum):
    """Trading signal direction."""
    BUY  = "buy"
    SELL = "sell"
    HOLD = "hold"


@dataclass
class Signal:
    """
    Output produced by a strategy's ``analyze()`` call.

    Attributes
    ----------
    action:          BUY / SELL / HOLD
    confidence:      float in [0, 1] — how certain the strategy is
    suggested_size:  fraction of portfolio to deploy (0-1), or None
    stop_loss:       absolute price level for stop-loss, or None
    take_profit:     absolute price level for take-profit, or None
    reasoning:       human-readable explanation of the signal
    metadata:        arbitrary extra data from the strategy
    timestamp:       ISO-8601 UTC string
    """
    action:         SignalAction
    confidence:     float                    = 0.0
    suggested_size: Optional[float]          = None
    stop_loss:      Optional[float]          = None
    take_profit:    Optional[float]          = None
    reasoning:      str                      = ""
    metadata:       Dict[str, Any]           = field(default_factory=dict)
    timestamp:      str                      = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action":         self.action.value,
            "confidence":     round(self.confidence, 4),
            "suggested_size": self.suggested_size,
            "stop_loss":      self.stop_loss,
            "take_profit":    self.take_profit,
            "reasoning":      self.reasoning,
            "metadata":       self.metadata,
            "timestamp":      self.timestamp,
        }


# ---------------------------------------------------------------------------
# Market data container
# ---------------------------------------------------------------------------

@dataclass
class MarketBar:
    """Single OHLCV bar plus optional indicators."""
    symbol:    str
    timestamp: float          # Unix epoch seconds
    open:      float
    high:      float
    low:       float
    close:     float
    volume:    float
    extra:     Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Base strategy
# ---------------------------------------------------------------------------

class BaseStrategy(ABC):
    """
    Abstract base class for all Murphy strategy templates.

    Subclasses must implement ``analyze()``.
    Configuration is passed as a plain dict so strategies can be
    serialised / deserialised from JSON.
    """

    #: Default parameter set — override in subclasses
    DEFAULT_PARAMS: Dict[str, Any] = {}

    def __init__(
        self,
        strategy_id: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.strategy_id = strategy_id
        self.params: Dict[str, Any] = dict(self.DEFAULT_PARAMS)
        if params:
            self.params.update(params)
        self._trade_count: int = 0
        logger.debug("Strategy %s initialised with params=%s", strategy_id, self.params)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    @abstractmethod
    def analyze(self, bars: List[MarketBar]) -> Signal:
        """
        Analyse market data and return a Signal.

        Parameters
        ----------
        bars:
            A list of OHLCV bars ordered oldest-first.
            The last element is the most recent (current) bar.

        Returns
        -------
        Signal with action, confidence, and optional risk levels.
        """

    def configure(self, params: Dict[str, Any]) -> None:
        """Update strategy parameters at runtime."""
        self.params.update(params)
        logger.info("Strategy %s reconfigured: %s", self.strategy_id, params)

    def get_params(self) -> Dict[str, Any]:
        """Return current parameter dict."""
        return dict(self.params)

    def get_info(self) -> Dict[str, Any]:
        """Return strategy metadata."""
        return {
            "strategy_id":  self.strategy_id,
            "class":        self.__class__.__name__,
            "params":       self.get_params(),
            "trade_count":  self._trade_count,
        }

    # ------------------------------------------------------------------
    # Shared indicator helpers (pure Python, no external deps required)
    # ------------------------------------------------------------------

    @staticmethod
    def _closes(bars: List[MarketBar]) -> List[float]:
        return [b.close for b in bars]

    @staticmethod
    def _volumes(bars: List[MarketBar]) -> List[float]:
        return [b.volume for b in bars]

    @staticmethod
    def _sma(values: List[float], period: int) -> Optional[float]:
        if len(values) < period:
            return None
        return sum(values[-period:]) / period

    @staticmethod
    def _ema(values: List[float], period: int) -> Optional[float]:
        if len(values) < period:
            return None
        k = 2.0 / (period + 1)
        ema = sum(values[:period]) / period
        for v in values[period:]:
            ema = v * k + ema * (1 - k)
        return ema

    @staticmethod
    def _rsi(values: List[float], period: int = 14) -> Optional[float]:
        if len(values) < period + 1:
            return None
        changes = [values[i] - values[i - 1] for i in range(1, len(values))]
        gains = [max(c, 0.0) for c in changes[-period:]]
        losses = [abs(min(c, 0.0)) for c in changes[-period:]]
        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100.0 - (100.0 / (1 + rs))

    @staticmethod
    def _macd(
        values: List[float],
        fast: int = 12,
        slow: int = 26,
        signal: int = 9,
    ) -> Optional[Dict[str, float]]:
        if len(values) < slow + signal:
            return None
        k_fast = 2.0 / (fast + 1)
        k_slow = 2.0 / (slow + 1)
        ema_f = sum(values[:fast]) / fast
        ema_s = sum(values[:slow]) / slow
        macd_vals: List[float] = []
        for v in values[slow:]:
            ema_f = v * k_fast + ema_f * (1 - k_fast)
            ema_s = v * k_slow + ema_s * (1 - k_slow)
            macd_vals.append(ema_f - ema_s)
        if len(macd_vals) < signal:
            return None
        k_sig = 2.0 / (signal + 1)
        sig_ema = sum(macd_vals[:signal]) / signal
        for m in macd_vals[signal:]:
            sig_ema = m * k_sig + sig_ema * (1 - k_sig)
        macd_val = macd_vals[-1]
        histogram = macd_val - sig_ema
        return {"macd": macd_val, "signal": sig_ema, "histogram": histogram}

    @staticmethod
    def _bollinger(
        values: List[float],
        period: int = 20,
        std_dev: float = 2.0,
    ) -> Optional[Dict[str, float]]:
        if len(values) < period:
            return None
        window = values[-period:]
        mean = sum(window) / period
        variance = sum((x - mean) ** 2 for x in window) / period
        std = variance ** 0.5
        return {
            "upper": mean + std_dev * std,
            "middle": mean,
            "lower": mean - std_dev * std,
            "std": std,
        }

    @staticmethod
    def _zscore(values: List[float], period: int = 20) -> Optional[float]:
        if len(values) < period:
            return None
        window = values[-period:]
        mean = sum(window) / period
        variance = sum((x - mean) ** 2 for x in window) / period
        std = variance ** 0.5
        if std == 0:
            return 0.0
        return (values[-1] - mean) / std

    @staticmethod
    def _atr(bars: List[MarketBar], period: int = 14) -> Optional[float]:
        if len(bars) < period + 1:
            return None
        true_ranges: List[float] = []
        for i in range(1, len(bars)):
            high = bars[i].high
            low = bars[i].low
            prev_close = bars[i - 1].close
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            true_ranges.append(tr)
        return sum(true_ranges[-period:]) / period
