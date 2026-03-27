"""
Sentiment Strategy — Fear/greed index + social signal framework.

This strategy provides a framework for incorporating external sentiment
data (fear/greed index, social media signals, news sentiment).
When live sentiment data is unavailable, it uses placeholder values
based on recent price momentum as a proxy.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from strategy_templates.base_strategy import BaseStrategy, MarketBar, Signal, SignalAction

logger = logging.getLogger(__name__)


class SentimentStrategy(BaseStrategy):
    """Fear/greed + social sentiment trading framework."""

    DEFAULT_PARAMS: Dict[str, Any] = {
        "fear_threshold":       30.0,   # fear/greed index: below = extreme fear → buy
        "greed_threshold":      70.0,   # above = extreme greed → sell
        "social_weight":        0.3,    # weight of social signal in combined score
        "price_proxy_period":   14,     # bars used for price-proxy sentiment
        "position_size":        0.08,
        "stop_loss_pct":        0.04,
        "take_profit_pct":      0.08,
    }

    def __init__(self, strategy_id: str, params: Dict[str, Any] | None = None) -> None:
        super().__init__(strategy_id, params)
        # External sentiment can be injected via update_sentiment()
        self._fear_greed_index: Optional[float] = None   # 0–100 (0=extreme fear, 100=extreme greed)
        self._social_score:     Optional[float] = None   # -1 to +1 (negative=bearish, positive=bullish)
        self._sentiment_ts:     float            = 0.0

    # ------------------------------------------------------------------
    # Sentiment injection (called by live data feeds / scrapers)
    # ------------------------------------------------------------------

    def update_sentiment(self, fear_greed: Optional[float], social_score: Optional[float]) -> None:
        """Inject live sentiment data from an external source."""
        self._fear_greed_index = fear_greed
        self._social_score     = social_score
        self._sentiment_ts     = time.time()
        logger.debug("Sentiment updated: fear_greed=%.1f, social=%.2f",
                     fear_greed or -1, social_score or 0)

    # ------------------------------------------------------------------
    # Price-proxy sentiment (fallback)
    # ------------------------------------------------------------------

    def _price_proxy_sentiment(self, closes: List[float], period: int) -> float:
        """Estimate sentiment [0-100] from price momentum as a proxy."""
        rsi = self._rsi(closes, period)
        if rsi is None:
            return 50.0  # neutral
        return rsi  # RSI ~= fear/greed proxy

    # ------------------------------------------------------------------
    # Main analysis
    # ------------------------------------------------------------------

    def analyze(self, bars: List[MarketBar]) -> Signal:
        p      = self.params
        closes = self._closes(bars)
        price  = closes[-1]

        # Use injected sentiment or fall back to price proxy
        stale  = (time.time() - self._sentiment_ts) > 3600  # stale after 1 hour
        if self._fear_greed_index is not None and not stale:
            fg_score = self._fear_greed_index
            source   = "live"
        else:
            fg_score = self._price_proxy_sentiment(closes, p["price_proxy_period"])
            source   = "price_proxy"

        # Incorporate social score if available
        combined = fg_score
        if self._social_score is not None and not stale:
            social_shifted = (self._social_score + 1) * 50  # map [-1,1] → [0,100]
            combined = fg_score * (1 - p["social_weight"]) + social_shifted * p["social_weight"]

        # Extreme Fear → contrarian BUY
        if combined < p["fear_threshold"]:
            confidence = min(0.85, (p["fear_threshold"] - combined) / p["fear_threshold"] * 1.2)
            self._trade_count += 1
            return Signal(
                action=SignalAction.BUY,
                confidence=round(confidence, 4),
                suggested_size=p["position_size"],
                stop_loss=round(price * (1 - p["stop_loss_pct"]), 6),
                take_profit=round(price * (1 + p["take_profit_pct"]), 6),
                reasoning=f"Extreme fear (score={combined:.1f}, source={source}) — contrarian buy",
                metadata={"fg_score": round(combined, 2), "source": source},
            )

        # Extreme Greed → contrarian SELL
        if combined > p["greed_threshold"]:
            confidence = min(0.85, (combined - p["greed_threshold"]) / (100 - p["greed_threshold"]) * 1.2)
            self._trade_count += 1
            return Signal(
                action=SignalAction.SELL,
                confidence=round(confidence, 4),
                suggested_size=p["position_size"],
                reasoning=f"Extreme greed (score={combined:.1f}, source={source}) — contrarian sell",
                metadata={"fg_score": round(combined, 2), "source": source},
            )

        return Signal(
            action=SignalAction.HOLD,
            confidence=0.0,
            reasoning=f"Sentiment neutral (score={combined:.1f}, source={source})",
        )
