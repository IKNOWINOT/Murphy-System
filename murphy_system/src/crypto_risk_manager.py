# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Crypto Risk Manager — Murphy System

Pre-trade and portfolio-level risk controls for all automated
trading activity.  Implements:

  - Position sizing:  FIXED | KELLY | VOLATILITY_ADJUSTED | PERCENT_RISK
  - Stop-loss types:  fixed, trailing (price-based), ATR-multiple
  - Circuit breakers: daily-loss, drawdown, consecutive-loss, position-limit
  - Pre-trade check gateway used by every bot before signal submission

All circuit-breaker trips are logged and must be manually reset via
``reset_circuit_breakers()`` — no bot can trade while any breaker is open.

Business Source License 1.1 (BSL 1.1)
Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class PositionSizingMethod(Enum):
    """Algorithm for computing trade size (Enum subclass)."""
    FIXED               = "fixed"
    KELLY               = "kelly"
    VOLATILITY_ADJUSTED = "volatility_adjusted"
    PERCENT_RISK        = "percent_risk"


class StopLossType(Enum):
    """Stop-loss calculation method (Enum subclass)."""
    FIXED      = "fixed"
    TRAILING   = "trailing"
    ATR_BASED  = "atr_based"


class CircuitBreakerReason(Enum):
    """Reason a circuit breaker tripped (Enum subclass)."""
    DAILY_LOSS         = "daily_loss"
    DRAWDOWN           = "drawdown"
    CONSECUTIVE_LOSSES = "consecutive_losses"
    POSITION_LIMIT     = "position_limit"
    MANUAL             = "manual"


# ---------------------------------------------------------------------------
# Configuration data classes
# ---------------------------------------------------------------------------

@dataclass
class RiskLimits:
    """Portfolio-wide and per-trade risk parameters."""
    max_position_size_usd:     float = 5_000.0
    max_portfolio_exposure_pct: float = 0.80    # max 80 % in open trades
    max_daily_loss_usd:        float = 500.0
    max_drawdown_pct:          float = 0.15     # 15 %
    max_consecutive_losses:    int   = 5
    max_open_trades:           int   = 10
    default_stop_loss_pct:     float = 0.03     # 3 %
    default_take_profit_pct:   float = 0.05     # 5 %
    sizing_method:             PositionSizingMethod = PositionSizingMethod.PERCENT_RISK
    risk_per_trade_pct:        float = 0.01     # 1 % of portfolio per trade
    kelly_fraction:            float = 0.25     # quarter-Kelly


@dataclass
class CircuitBreaker:
    """An active or resolved circuit-breaker event."""
    breaker_id:   str
    reason:       CircuitBreakerReason
    triggered_at: str
    resolved_at:  Optional[str] = None
    details:      str = ""

    @property
    def is_open(self) -> bool:
        """True while the breaker has not been resolved."""
        return self.resolved_at is None


# ---------------------------------------------------------------------------
# Risk manager
# ---------------------------------------------------------------------------

class CryptoRiskManager:
    """
    Pre-trade risk controller and portfolio circuit-breaker system.

    Every bot should call ``pre_trade_check()`` before submitting a signal
    to the HITL gateway.  A False return means the trade must not proceed.

    Use ``compute_position_size()`` to get the recommended trade size
    given the current portfolio value and strategy win rate.
    """

    def __init__(self, limits: Optional[RiskLimits] = None) -> None:
        self.limits          = limits or RiskLimits()
        self._lock           = threading.Lock()
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._daily_loss:    float = 0.0
        self._daily_reset:   str   = datetime.now(timezone.utc).date().isoformat()
        self._open_trades:   int   = 0
        self._consecutive_losses: int = 0
        self._peak_portfolio: float = 0.0
        self._portfolio_value: float = 0.0

    # ---- pre-trade gate -------------------------------------------------

    def pre_trade_check(
        self,
        bot_id:     str,
        pair:       str,
        side:       str,
        size:       float,
    ) -> bool:
        """
        Return True if the proposed trade passes all risk checks.

        Checks performed (in order):
          1. No open circuit breakers
          2. Daily loss limit not exceeded
          3. Max open trades not reached
          4. Position size within limits
        """
        self._maybe_reset_daily()

        with self._lock:
            # 1. Circuit breakers
            open_breakers = [b for b in self._circuit_breakers.values() if b.is_open]
            if open_breakers:
                reasons = [b.reason.value for b in open_breakers]
                logger.warning(
                    "Risk: pre_trade_check BLOCKED for %s %s — open breakers: %s",
                    bot_id, pair, reasons,
                )
                return False

            # 2. Daily loss
            if self._daily_loss >= self.limits.max_daily_loss_usd:
                self._trip_breaker(CircuitBreakerReason.DAILY_LOSS,
                                   f"daily_loss={self._daily_loss:.2f}")
                return False

            # 3. Open trades
            if self._open_trades >= self.limits.max_open_trades:
                logger.warning("Risk: open_trades limit reached (%d)", self._open_trades)
                return False

            # 4. Position size
            if size > self.limits.max_position_size_usd:
                logger.warning(
                    "Risk: size %.2f exceeds max %.2f for %s",
                    size, self.limits.max_position_size_usd, pair,
                )
                return False

        return True

    # ---- position sizing ------------------------------------------------

    def compute_position_size(
        self,
        portfolio_value: float,
        entry_price:     float,
        stop_loss_price: float,
        win_rate:        float  = 0.5,
        avg_win:         float  = 1.0,
        avg_loss:        float  = 1.0,
        atr:             Optional[float] = None,
    ) -> float:
        """
        Return the recommended position size in base-currency units.

        Parameters
        ----------
        portfolio_value : current total portfolio value in USD
        entry_price     : planned entry price
        stop_loss_price : planned stop-loss price
        win_rate        : historical win rate [0-1] (Kelly only)
        avg_win         : average win amount (Kelly only)
        avg_loss        : average loss amount (Kelly only)
        atr             : Average True Range (volatility_adjusted only)
        """
        method  = self.limits.sizing_method
        sl_dist = abs(entry_price - stop_loss_price)

        if method == PositionSizingMethod.FIXED:
            usd_size = self.limits.max_position_size_usd * 0.1

        elif method == PositionSizingMethod.PERCENT_RISK:
            risk_usd = portfolio_value * self.limits.risk_per_trade_pct
            usd_size = risk_usd / (sl_dist or entry_price * 0.01) * entry_price

        elif method == PositionSizingMethod.KELLY:
            b         = avg_win / (avg_loss or 1)
            kelly_pct = win_rate - (1 - win_rate) / b
            kelly_pct = max(0.0, kelly_pct) * self.limits.kelly_fraction
            usd_size  = portfolio_value * kelly_pct

        elif method == PositionSizingMethod.VOLATILITY_ADJUSTED:
            vol_factor = (atr / entry_price) if (atr and entry_price) else 0.02
            risk_usd   = portfolio_value * self.limits.risk_per_trade_pct
            usd_size   = risk_usd / (vol_factor or 0.02)

        else:
            usd_size = portfolio_value * 0.01

        # Cap at limit
        usd_size  = min(usd_size, self.limits.max_position_size_usd)
        base_size = usd_size / (entry_price or 1)
        return round(base_size, 8)

    # ---- stop-loss calculation ------------------------------------------

    def compute_stop_loss(
        self,
        entry_price: float,
        side:        str,
        method:      StopLossType = StopLossType.FIXED,
        atr:         Optional[float] = None,
        atr_multiplier: float = 2.0,
    ) -> float:
        """Return the stop-loss price for the given entry."""
        if method == StopLossType.FIXED:
            pct  = self.limits.default_stop_loss_pct
            dist = entry_price * pct
        elif method == StopLossType.ATR_BASED:
            dist = (atr or entry_price * 0.02) * atr_multiplier
        else:
            dist = entry_price * self.limits.default_stop_loss_pct

        if side.lower() == "buy":
            return round(entry_price - dist, 8)
        return round(entry_price + dist, 8)

    def compute_take_profit(self, entry_price: float, side: str) -> float:
        """Return a default take-profit price for the given entry."""
        dist = entry_price * self.limits.default_take_profit_pct
        if side.lower() == "buy":
            return round(entry_price + dist, 8)
        return round(entry_price - dist, 8)

    # ---- post-trade updates --------------------------------------------

    def record_trade_open(self, trade_value_usd: float) -> None:
        """Call when a new trade is opened."""
        with self._lock:
            self._open_trades = max(0, self._open_trades + 1)

    def record_trade_close(self, pnl_usd: float) -> None:
        """Call when a trade closes.  Triggers circuit breakers if needed."""
        with self._lock:
            self._open_trades = max(0, self._open_trades - 1)
            if pnl_usd < 0:
                self._daily_loss         += abs(pnl_usd)
                self._consecutive_losses += 1
                if self._consecutive_losses >= self.limits.max_consecutive_losses:
                    self._trip_breaker(
                        CircuitBreakerReason.CONSECUTIVE_LOSSES,
                        f"count={self._consecutive_losses}",
                    )
            else:
                self._consecutive_losses = 0

    def update_portfolio_value(self, value: float) -> None:
        """Update the current portfolio value; checks drawdown breaker."""
        with self._lock:
            self._portfolio_value = value
            self._peak_portfolio  = max(self._peak_portfolio, value)
            if self._peak_portfolio > 0:
                dd = (self._peak_portfolio - value) / self._peak_portfolio
                if dd >= self.limits.max_drawdown_pct:
                    self._trip_breaker(CircuitBreakerReason.DRAWDOWN, f"drawdown={dd:.3f}")

    # ---- circuit breakers ----------------------------------------------

    def reset_circuit_breakers(self, reason: Optional[CircuitBreakerReason] = None) -> int:
        """
        Manually resolve all (or a specific) circuit breaker(s).
        Returns number of breakers resolved.
        """
        import uuid as _uuid
        resolved = 0
        with self._lock:
            for b in self._circuit_breakers.values():
                if b.is_open and (reason is None or b.reason == reason):
                    b.resolved_at = datetime.now(timezone.utc).isoformat()
                    resolved += 1
        logger.warning("CryptoRiskManager: resolved %d circuit breaker(s)", resolved)
        return resolved

    def get_circuit_breakers(self) -> List[Dict[str, Any]]:
        """Return all circuit-breaker records."""
        with self._lock:
            return [
                {
                    "breaker_id":   b.breaker_id,
                    "reason":       b.reason.value,
                    "is_open":      b.is_open,
                    "triggered_at": b.triggered_at,
                    "resolved_at":  b.resolved_at,
                    "details":      b.details,
                }
                for b in self._circuit_breakers.values()
            ]

    def get_risk_summary(self) -> Dict[str, Any]:
        """Return a dict summarising current risk state."""
        with self._lock:
            open_breakers = [b for b in self._circuit_breakers.values() if b.is_open]
            return {
                "open_circuit_breakers": len(open_breakers),
                "breaker_reasons":       [b.reason.value for b in open_breakers],
                "daily_loss_usd":        self._daily_loss,
                "daily_loss_limit_usd":  self.limits.max_daily_loss_usd,
                "open_trades":           self._open_trades,
                "max_open_trades":       self.limits.max_open_trades,
                "consecutive_losses":    self._consecutive_losses,
                "portfolio_value_usd":   self._portfolio_value,
                "peak_portfolio_usd":    self._peak_portfolio,
                "sizing_method":         self.limits.sizing_method.value,
            }

    # ---- helpers --------------------------------------------------------

    def _trip_breaker(self, reason: CircuitBreakerReason, details: str = "") -> None:
        """Internal: open a new circuit breaker (must be called under self._lock)."""
        import uuid as _uuid
        bid = str(_uuid.uuid4())
        self._circuit_breakers[bid] = CircuitBreaker(
            breaker_id   = bid,
            reason       = reason,
            triggered_at = datetime.now(timezone.utc).isoformat(),
            details      = details,
        )
        logger.warning(
            "CryptoRiskManager: circuit breaker TRIPPED — %s (%s)", reason.value, details
        )

    def _maybe_reset_daily(self) -> None:
        """Reset daily loss counter at UTC midnight."""
        today = datetime.now(timezone.utc).date().isoformat()
        with self._lock:
            if today != self._daily_reset:
                self._daily_loss  = 0.0
                self._daily_reset = today
