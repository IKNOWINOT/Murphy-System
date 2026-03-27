# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Dynamic Risk Manager — Murphy System

Advanced risk management system that analyzes market conditions and
automatically recommends risk levels rather than requiring manual selection.

Risk factors evaluated:
  - Current market volatility (ATR, standard deviation of returns)
  - Portfolio concentration (% in single asset)
  - Current drawdown from peak
  - Recent win/loss streak
  - Correlation between held positions
  - Market regime detection (trending / ranging / volatile)

Position sizing via Kelly Criterion (half-Kelly default).
  - Max single trade:  5% of portfolio (configurable)
  - Max portfolio risk: 15% total exposure (configurable)

Outputs a ``RiskAssessment`` object explaining every recommendation.

Business Source License 1.1 (BSL 1.1)
Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
"""

from __future__ import annotations

import logging
import math
import statistics
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:  # pragma: no cover
    _HAS_NUMPY = False

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_MAX_POSITION_PCT   = 0.05   # 5 % of portfolio per trade
_DEFAULT_MAX_PORTFOLIO_RISK = 0.15   # 15 % total risk exposure
_DEFAULT_KELLY_FRACTION     = 0.50   # half-Kelly
_DEFAULT_ATR_PERIODS        = 14
_DEFAULT_VOL_PERIODS        = 20
_MIN_PRICES_REQUIRED        = 5      # minimum price history for analysis

# Risk score composite weights (sum to 100 across scaled contributions)
_WEIGHT_VOLATILITY          = 35     # volatility sub-score weight
_WEIGHT_DRAWDOWN            = 25     # drawdown sub-score weight
_WEIGHT_STREAK              = 15     # win/loss streak sub-score weight
_WEIGHT_CORRELATION         = 15     # correlation sub-score weight
_WEIGHT_REGIME              = 0.10   # regime component multiplier (applied to raw regime score)

# Regime raw scores fed into the composite (before multiplied by _WEIGHT_REGIME)
_REGIME_SCORE_VOLATILE      = 50
_REGIME_SCORE_RANGING       = 20
_REGIME_SCORE_TRENDING      = 10

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class RiskLevel(str, Enum):
    """System-recommended risk level (Enum subclass)."""
    CONSERVATIVE = "conservative"
    MODERATE     = "moderate"
    AGGRESSIVE   = "aggressive"


class MarketRegime(str, Enum):
    """Detected market regime (Enum subclass)."""
    TRENDING  = "trending"
    RANGING   = "ranging"
    VOLATILE  = "volatile"
    UNKNOWN   = "unknown"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class RiskAssessment:
    """Full risk assessment output for a single trade opportunity."""
    recommended_risk_level: RiskLevel
    max_position_size:      float          # USD
    suggested_stop_loss:    Optional[float]  # price
    suggested_take_profit:  Optional[float]  # price
    risk_score:             float          # 0-100 (higher = riskier)
    reasoning:              List[str]      = field(default_factory=list)
    market_regime:          MarketRegime   = MarketRegime.UNKNOWN
    kelly_fraction_used:    float          = _DEFAULT_KELLY_FRACTION
    atr:                    Optional[float] = None
    volatility:             Optional[float] = None  # std-dev of returns
    drawdown_pct:           float          = 0.0
    concentration_pct:      float          = 0.0
    win_streak:             int            = 0
    loss_streak:            int            = 0
    timestamp:              str            = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for API / JSON response."""
        return {
            "recommended_risk_level": self.recommended_risk_level.value,
            "max_position_size":      round(self.max_position_size, 4),
            "suggested_stop_loss":    self.suggested_stop_loss,
            "suggested_take_profit":  self.suggested_take_profit,
            "risk_score":             round(self.risk_score, 2),
            "reasoning":              self.reasoning,
            "market_regime":          self.market_regime.value,
            "kelly_fraction_used":    self.kelly_fraction_used,
            "atr":                    self.atr,
            "volatility":             self.volatility,
            "drawdown_pct":           round(self.drawdown_pct * 100, 2),
            "concentration_pct":      round(self.concentration_pct * 100, 2),
            "win_streak":             self.win_streak,
            "loss_streak":            self.loss_streak,
            "timestamp":              self.timestamp,
        }


@dataclass
class PositionInfo:
    """Current position held in a single asset."""
    symbol:     str
    value_usd:  float
    entry_price: float = 0.0


# ---------------------------------------------------------------------------
# Dynamic Risk Manager
# ---------------------------------------------------------------------------


class DynamicRiskManager:
    """
    Analyzes market conditions and recommends appropriate risk parameters.

    Thread-safe.  All mutable state is guarded by an internal Lock.
    """

    def __init__(
        self,
        portfolio_value_usd:   float = 10_000.0,
        max_position_pct:      float = _DEFAULT_MAX_POSITION_PCT,
        max_portfolio_risk_pct: float = _DEFAULT_MAX_PORTFOLIO_RISK,
        kelly_fraction:        float = _DEFAULT_KELLY_FRACTION,
        atr_multiplier_stop:   float = 2.0,
        atr_multiplier_tp:     float = 3.0,
    ) -> None:
        self.portfolio_value       = portfolio_value_usd
        self.max_position_pct      = max_position_pct
        self.max_portfolio_risk_pct = max_portfolio_risk_pct
        self.kelly_fraction        = kelly_fraction
        self.atr_multiplier_stop   = atr_multiplier_stop
        self.atr_multiplier_tp     = atr_multiplier_tp

        self._peak_value:    float = portfolio_value_usd
        self._positions:     List[PositionInfo] = []
        self._trade_results: List[float] = []   # +/- P&L per closed trade
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def assess(
        self,
        prices:       List[float],
        entry_price:  float,
        side:         str = "buy",
        win_rate:     float = 0.50,
        avg_win:      float = 1.0,
        avg_loss:     float = 1.0,
        volumes:      Optional[List[float]] = None,
        corr_matrix:  Optional[List[List[float]]] = None,
    ) -> RiskAssessment:
        """
        Perform a full risk assessment and return a ``RiskAssessment``.

        Parameters
        ----------
        prices      : recent close prices (oldest first, min 5 required)
        entry_price : contemplated entry price
        side        : "buy" or "sell"
        win_rate    : historical win rate 0-1 for Kelly calc
        avg_win     : average winning trade size (Kelly)
        avg_loss    : average losing trade size (Kelly)
        volumes     : optional volume history parallel to prices
        corr_matrix : optional N×N correlation matrix for open positions
        """
        with self._lock:
            reasoning: List[str] = []

            # ── 1. Volatility analysis ───────────────────────────────────
            atr        = self._calc_atr(prices)
            vol        = self._calc_volatility(prices)
            vol_score  = self._score_volatility(vol, entry_price, reasoning)

            # ── 2. Portfolio concentration ───────────────────────────────
            conc_pct   = self._calc_concentration(reasoning)

            # ── 3. Drawdown ──────────────────────────────────────────────
            dd_score   = self._score_drawdown(reasoning)
            dd_pct     = self._current_drawdown()

            # ── 4. Win/loss streak ───────────────────────────────────────
            win_s, loss_s = self._calc_streaks()
            streak_score  = self._score_streak(win_s, loss_s, reasoning)

            # ── 5. Correlation penalty ───────────────────────────────────
            corr_score = self._score_correlation(corr_matrix, reasoning)

            # ── 6. Market regime detection ───────────────────────────────
            regime = self._detect_regime(prices, volumes, reasoning)

            # ── 7. Composite risk score (0-100) ──────────────────────────
            risk_score = min(100.0, (
                vol_score    * _WEIGHT_VOLATILITY +
                dd_score     * _WEIGHT_DRAWDOWN +
                streak_score * _WEIGHT_STREAK +
                corr_score   * _WEIGHT_CORRELATION +
                (
                    _REGIME_SCORE_VOLATILE if regime == MarketRegime.VOLATILE else
                    _REGIME_SCORE_RANGING  if regime == MarketRegime.RANGING  else
                    _REGIME_SCORE_TRENDING
                ) * _WEIGHT_REGIME
            ))

            # ── 8. Recommend risk level ──────────────────────────────────
            risk_level = self._recommend_level(risk_score, regime, reasoning)

            # ── 9. Kelly position size ───────────────────────────────────
            kelly_frac = self._dynamic_kelly(risk_level)
            pos_size   = self._calc_position_size(
                entry_price, win_rate, avg_win, avg_loss, kelly_frac, reasoning
            )

            # ── 10. ATR-based stop/take-profit ───────────────────────────
            stop_loss, take_profit = self._calc_sl_tp(entry_price, atr, side)

            return RiskAssessment(
                recommended_risk_level = risk_level,
                max_position_size      = pos_size,
                suggested_stop_loss    = stop_loss,
                suggested_take_profit  = take_profit,
                risk_score             = risk_score,
                reasoning              = reasoning,
                market_regime          = regime,
                kelly_fraction_used    = kelly_frac,
                atr                    = atr,
                volatility             = vol,
                drawdown_pct           = dd_pct,
                concentration_pct      = conc_pct,
                win_streak             = win_s,
                loss_streak            = loss_s,
            )

    def update_portfolio_value(self, value: float) -> None:
        """Call on each portfolio snapshot update."""
        with self._lock:
            self.portfolio_value = value
            if value > self._peak_value:
                self._peak_value = value

    def add_position(self, symbol: str, value_usd: float, entry_price: float = 0.0) -> None:
        """Register an open position."""
        with self._lock:
            self._positions = [p for p in self._positions if p.symbol != symbol]
            self._positions.append(PositionInfo(symbol, value_usd, entry_price))

    def remove_position(self, symbol: str) -> None:
        """Remove a closed position."""
        with self._lock:
            self._positions = [p for p in self._positions if p.symbol != symbol]

    def record_trade_result(self, pnl_usd: float) -> None:
        """Record a closed trade P&L for streak tracking."""
        with self._lock:
            self._trade_results.append(pnl_usd)
            if len(self._trade_results) > 500:
                self._trade_results = self._trade_results[-500:]

    def get_summary(self) -> Dict[str, Any]:
        """Return current risk state summary."""
        with self._lock:
            dd = self._current_drawdown()
            w, l = self._calc_streaks()
            return {
                "portfolio_value_usd": self.portfolio_value,
                "peak_value_usd":      self._peak_value,
                "current_drawdown_pct": round(dd * 100, 2),
                "open_positions":      len(self._positions),
                "win_streak":          w,
                "loss_streak":         l,
                "total_trade_records": len(self._trade_results),
            }

    # ------------------------------------------------------------------
    # Internal calculations
    # ------------------------------------------------------------------

    @staticmethod
    def _calc_atr(prices: List[float], periods: int = _DEFAULT_ATR_PERIODS) -> Optional[float]:
        """Calculate Average True Range from close prices (simplified)."""
        if len(prices) < 2:
            return None
        trs: List[float] = []
        for i in range(1, len(prices)):
            tr = abs(prices[i] - prices[i - 1])
            trs.append(tr)
        window = trs[-min(periods, len(trs)):]
        return statistics.mean(window) if window else None

    @staticmethod
    def _calc_volatility(prices: List[float], periods: int = _DEFAULT_VOL_PERIODS) -> Optional[float]:
        """Return standard deviation of log returns over last ``periods`` bars."""
        if len(prices) < _MIN_PRICES_REQUIRED:
            return None
        window = prices[-min(periods + 1, len(prices)):]
        returns: List[float] = []
        for i in range(1, len(window)):
            if window[i - 1] > 0:
                returns.append(math.log(window[i] / window[i - 1]))
        return statistics.stdev(returns) if len(returns) >= 2 else None

    def _score_volatility(
        self, vol: Optional[float], entry: float, reasoning: List[str]
    ) -> float:
        """Return 0-100 volatility sub-score."""
        if vol is None or entry <= 0:
            reasoning.append("Volatility data unavailable; using neutral score.")
            return 50.0
        vol_pct = vol * math.sqrt(365)  # annualized
        if vol_pct < 0.30:
            reasoning.append(f"Low annualized volatility ({vol_pct:.1%}) — favors moderate sizing.")
            return 25.0
        elif vol_pct < 0.60:
            reasoning.append(f"Moderate volatility ({vol_pct:.1%}) — standard sizing applies.")
            return 50.0
        elif vol_pct < 1.00:
            reasoning.append(f"High volatility ({vol_pct:.1%}) — reduce position size.")
            return 75.0
        else:
            reasoning.append(f"Extreme volatility ({vol_pct:.1%}) — minimal position recommended.")
            return 95.0

    def _calc_concentration(self, reasoning: List[str]) -> float:
        """Return fraction of portfolio in single largest position."""
        if not self._positions or self.portfolio_value <= 0:
            return 0.0
        max_pos = max(p.value_usd for p in self._positions)
        conc = max_pos / self.portfolio_value
        if conc > 0.30:
            reasoning.append(
                f"High concentration: largest position is {conc:.1%} of portfolio."
            )
        return conc

    def _current_drawdown(self) -> float:
        """Return current drawdown fraction from peak."""
        if self._peak_value <= 0:
            return 0.0
        return max(0.0, (self._peak_value - self.portfolio_value) / self._peak_value)

    def _score_drawdown(self, reasoning: List[str]) -> float:
        """Return 0-100 drawdown sub-score."""
        dd = self._current_drawdown()
        if dd < 0.03:
            return 10.0
        elif dd < 0.07:
            reasoning.append(f"Drawdown {dd:.1%} — moderate caution advised.")
            return 40.0
        elif dd < 0.12:
            reasoning.append(f"Drawdown {dd:.1%} — reduce risk exposure.")
            return 70.0
        else:
            reasoning.append(f"Severe drawdown {dd:.1%} — switch to conservative mode.")
            return 95.0

    def _calc_streaks(self) -> Tuple[int, int]:
        """Return (win_streak, loss_streak) from recent results."""
        win_s = loss_s = 0
        for r in reversed(self._trade_results):
            if r > 0:
                if loss_s > 0:
                    break
                win_s += 1
            else:
                if win_s > 0:
                    break
                loss_s += 1
        return win_s, loss_s

    def _score_streak(self, win_s: int, loss_s: int, reasoning: List[str]) -> float:
        """Return 0-100 streak sub-score."""
        if loss_s >= 5:
            reasoning.append(f"{loss_s} consecutive losses — circuit breaker territory.")
            return 90.0
        elif loss_s >= 3:
            reasoning.append(f"{loss_s} consecutive losses — reduce sizing.")
            return 65.0
        elif win_s >= 5:
            reasoning.append(f"{win_s} consecutive wins — guard against overconfidence.")
            return 35.0
        return 30.0

    @staticmethod
    def _score_correlation(
        corr_matrix: Optional[List[List[float]]], reasoning: List[str]
    ) -> float:
        """Return 0-100 correlation sub-score."""
        if not corr_matrix:
            return 20.0
        # average off-diagonal correlations
        flat = []
        n = len(corr_matrix)
        for i in range(n):
            for j in range(n):
                if i != j:
                    try:
                        flat.append(abs(float(corr_matrix[i][j])))
                    except (TypeError, IndexError):
                        pass
        if not flat:
            return 20.0
        avg_corr = statistics.mean(flat)
        if avg_corr > 0.75:
            reasoning.append(
                f"Portfolio highly correlated (avg {avg_corr:.2f}) — poor diversification."
            )
            return 75.0
        elif avg_corr > 0.50:
            reasoning.append(
                f"Moderate correlation ({avg_corr:.2f}) — some diversification benefit."
            )
            return 40.0
        return 15.0

    @staticmethod
    def _detect_regime(
        prices:   List[float],
        volumes:  Optional[List[float]],
        reasoning: List[str],
    ) -> MarketRegime:
        """Classify market regime from price and volume history."""
        if len(prices) < _MIN_PRICES_REQUIRED:
            return MarketRegime.UNKNOWN

        # Simple regime detection via recent returns spread
        recent = prices[-min(20, len(prices)):]
        lo, hi = min(recent), max(recent)
        spread = (hi - lo) / (lo or 1)
        mean_p = statistics.mean(recent)

        returns = [recent[i] / recent[i - 1] - 1 for i in range(1, len(recent))]
        if not returns:
            return MarketRegime.UNKNOWN

        try:
            vol = statistics.stdev(returns)
        except statistics.StatisticsError:
            vol = 0.0

        # High vol → volatile
        if vol > 0.04:
            reasoning.append("Market regime: VOLATILE (high intraday standard deviation).")
            return MarketRegime.VOLATILE

        # Check trend: last price vs mean
        last = prices[-1]
        trend_strength = abs(last - mean_p) / (mean_p or 1)
        if trend_strength > 0.05:
            direction = "uptrend" if last > mean_p else "downtrend"
            reasoning.append(f"Market regime: TRENDING ({direction}).")
            return MarketRegime.TRENDING

        reasoning.append("Market regime: RANGING (low trend strength, low volatility).")
        return MarketRegime.RANGING

    @staticmethod
    def _recommend_level(
        risk_score: float, regime: MarketRegime, reasoning: List[str]
    ) -> RiskLevel:
        """Derive the recommended risk level from composite score + regime."""
        if risk_score >= 70 or regime == MarketRegime.VOLATILE:
            reasoning.append(
                "System recommendation: CONSERVATIVE — elevated risk score or volatile regime."
            )
            return RiskLevel.CONSERVATIVE
        elif risk_score >= 40:
            reasoning.append(
                "System recommendation: MODERATE — balanced risk score."
            )
            return RiskLevel.MODERATE
        else:
            reasoning.append(
                "System recommendation: AGGRESSIVE — low risk score, stable conditions."
            )
            return RiskLevel.AGGRESSIVE

    def _dynamic_kelly(self, level: RiskLevel) -> float:
        """Scale Kelly fraction based on recommended risk level."""
        base = self.kelly_fraction  # half-Kelly by default (0.5)
        if level == RiskLevel.CONSERVATIVE:
            return base * 0.5          # quarter-Kelly
        elif level == RiskLevel.MODERATE:
            return base                # half-Kelly
        else:
            return min(base * 1.5, 1.0)  # three-quarter-Kelly, capped at full

    def _calc_position_size(
        self,
        entry_price: float,
        win_rate:    float,
        avg_win:     float,
        avg_loss:    float,
        kelly_frac:  float,
        reasoning:   List[str],
    ) -> float:
        """Return maximum position size in USD using Kelly Criterion."""
        if avg_loss <= 0:
            avg_loss = 1.0
        b = avg_win / avg_loss
        # Kelly % = win_rate - (1 - win_rate) / b
        raw_kelly = win_rate - (1 - win_rate) / b
        raw_kelly = max(0.0, raw_kelly)
        kelly_pct = raw_kelly * kelly_frac

        usd_size = self.portfolio_value * kelly_pct
        # Hard cap: max_position_pct of portfolio
        cap = self.portfolio_value * self.max_position_pct
        if usd_size > cap:
            reasoning.append(
                f"Kelly size capped at {self.max_position_pct:.0%} max-position limit."
            )
            usd_size = cap

        reasoning.append(
            f"Position size: ${usd_size:,.2f} "
            f"(Kelly {raw_kelly:.3f} × fraction {kelly_frac:.2f})."
        )
        return round(usd_size, 2)

    def _calc_sl_tp(
        self,
        entry_price: float,
        atr: Optional[float],
        side: str,
    ) -> Tuple[Optional[float], Optional[float]]:
        """Return (stop_loss_price, take_profit_price) using ATR."""
        if not atr or entry_price <= 0:
            return None, None
        dist_stop = atr * self.atr_multiplier_stop
        dist_tp   = atr * self.atr_multiplier_tp
        if side.lower() == "buy":
            return (
                round(entry_price - dist_stop, 8),
                round(entry_price + dist_tp,   8),
            )
        return (
            round(entry_price + dist_stop, 8),
            round(entry_price - dist_tp,   8),
        )
