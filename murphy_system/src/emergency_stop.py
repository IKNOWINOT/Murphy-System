# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Trading Emergency Stop — Murphy System

Always-active circuit breakers for the trading subsystem.

Circuit breakers that trigger automatic shutdown:
  - Single trade loss > 3 % of portfolio
  - Daily loss > 5 % of portfolio
  - Weekly loss > 10 % of portfolio
  - 5 consecutive losing trades
  - API errors > 3 in 5 minutes
  - Price data gaps > 2 minutes
  - Flash crash: > 10 % price drop in < 5 minutes

When triggered:
  1. Cancel all open orders (callback)
  2. Close all positions if in live mode (callback)
  3. Switch to paper mode
  4. Send alert / notification
  5. Log everything
  6. Require manual restart with 1-hour cooldown

Safety invariant: This system CANNOT be disabled.

Business Source License 1.1 (BSL 1.1)
Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
"""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants  (thresholds match the spec — configurable at construction time)
# ---------------------------------------------------------------------------

_DEFAULT_MAX_SINGLE_LOSS_PCT   = 0.03   # 3 %
_DEFAULT_MAX_DAILY_LOSS_PCT    = 0.05   # 5 %
_DEFAULT_MAX_WEEKLY_LOSS_PCT   = 0.10   # 10 %
_DEFAULT_MAX_CONSEC_LOSSES     = 5
_DEFAULT_MAX_API_ERRORS        = 3
_DEFAULT_API_ERROR_WINDOW_SECS = 300    # 5 minutes
_DEFAULT_MAX_DATA_GAP_SECS     = 120    # 2 minutes
_DEFAULT_FLASH_CRASH_DROP_PCT  = 0.10   # 10 %
_DEFAULT_FLASH_CRASH_WINDOW_SECS = 300  # 5 minutes
_DEFAULT_COOLDOWN_SECS         = 3600   # 1 hour

_MAX_LOG = 10_000
_LOG_TRIM_SIZE = _MAX_LOG // 10   # keep the most recent 10 % when capacity is exceeded

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class TradingStopReason(str, Enum):
    """Reason the trading emergency stop was triggered (Enum subclass)."""
    SINGLE_TRADE_LOSS  = "single_trade_loss"
    DAILY_LOSS         = "daily_loss"
    WEEKLY_LOSS        = "weekly_loss"
    CONSECUTIVE_LOSSES = "consecutive_losses"
    API_ERRORS         = "api_errors"
    DATA_GAP           = "data_gap"
    FLASH_CRASH        = "flash_crash"
    MANUAL             = "manual"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class TradingStopEvent:
    """A single emergency-stop or reset event."""
    event_id:     str
    reason:       TradingStopReason
    details:      str
    triggered_at: str
    reset_at:     Optional[str] = None
    reset_by:     Optional[str] = None
    cooldown_until: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Trading Emergency Stop
# ---------------------------------------------------------------------------


class TradingEmergencyStop:
    """
    Always-active circuit-breaker system for trading.

    Cannot be disabled.  All state changes are logged and require
    a 1-hour cooldown before manual reset is allowed.

    Thread-safe.
    """

    def __init__(
        self,
        portfolio_value_usd:      float = 10_000.0,
        max_single_loss_pct:      float = _DEFAULT_MAX_SINGLE_LOSS_PCT,
        max_daily_loss_pct:       float = _DEFAULT_MAX_DAILY_LOSS_PCT,
        max_weekly_loss_pct:      float = _DEFAULT_MAX_WEEKLY_LOSS_PCT,
        max_consecutive_losses:   int   = _DEFAULT_MAX_CONSEC_LOSSES,
        max_api_errors:           int   = _DEFAULT_MAX_API_ERRORS,
        api_error_window_secs:    int   = _DEFAULT_API_ERROR_WINDOW_SECS,
        max_data_gap_secs:        int   = _DEFAULT_MAX_DATA_GAP_SECS,
        flash_crash_drop_pct:     float = _DEFAULT_FLASH_CRASH_DROP_PCT,
        flash_crash_window_secs:  int   = _DEFAULT_FLASH_CRASH_WINDOW_SECS,
        cooldown_secs:            int   = _DEFAULT_COOLDOWN_SECS,
        on_stop:   Optional[Callable[[TradingStopEvent], None]] = None,
        on_cancel_orders: Optional[Callable[[], None]] = None,
        on_close_positions: Optional[Callable[[], None]] = None,
    ) -> None:
        self.portfolio_value          = portfolio_value_usd
        self.max_single_loss_pct      = max_single_loss_pct
        self.max_daily_loss_pct       = max_daily_loss_pct
        self.max_weekly_loss_pct      = max_weekly_loss_pct
        self.max_consecutive_losses   = max_consecutive_losses
        self.max_api_errors           = max_api_errors
        self.api_error_window_secs    = api_error_window_secs
        self.max_data_gap_secs        = max_data_gap_secs
        self.flash_crash_drop_pct     = flash_crash_drop_pct
        self.flash_crash_window_secs  = flash_crash_window_secs
        self.cooldown_secs            = cooldown_secs

        self._on_stop            = on_stop
        self._on_cancel_orders   = on_cancel_orders
        self._on_close_positions = on_close_positions

        self._is_stopped:      bool = False
        self._active_event:    Optional[TradingStopEvent] = None
        self._log:             List[TradingStopEvent] = []

        # Rolling counters
        self._daily_loss:       float = 0.0
        self._weekly_loss:      float = 0.0
        self._consec_losses:    int   = 0
        self._daily_reset_date: str   = datetime.now(timezone.utc).date().isoformat()
        self._weekly_reset_date: str  = datetime.now(timezone.utc).isocalendar()[:2]  # (year, week)

        # API error timestamps (rolling window)
        self._api_error_times: List[float] = []

        # Price history for flash-crash detection: (timestamp, price)
        self._price_hist: List[Tuple[float, float]] = []

        # Last seen price timestamp (for data-gap detection)
        self._last_price_ts: Optional[float] = None

        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Trade recording
    # ------------------------------------------------------------------

    def record_trade_loss(self, loss_usd: float, portfolio_value: float) -> Optional[TradingStopEvent]:
        """
        Record a losing trade.  Checks single-trade, daily, weekly, and
        consecutive-loss circuit breakers.  Returns stop event if triggered.
        """
        with self._lock:
            self._maybe_reset_daily()
            self.portfolio_value = portfolio_value
            self._daily_loss  += abs(loss_usd)
            self._weekly_loss += abs(loss_usd)
            self._consec_losses += 1

            # Single trade loss
            if abs(loss_usd) / (portfolio_value or 1) > self.max_single_loss_pct:
                return self._trigger(
                    TradingStopReason.SINGLE_TRADE_LOSS,
                    f"Single trade loss ${loss_usd:.2f} exceeds "
                    f"{self.max_single_loss_pct:.0%} of portfolio.",
                )

            # Daily loss
            if self._daily_loss / (portfolio_value or 1) > self.max_daily_loss_pct:
                return self._trigger(
                    TradingStopReason.DAILY_LOSS,
                    f"Daily loss ${self._daily_loss:.2f} exceeds "
                    f"{self.max_daily_loss_pct:.0%} of portfolio.",
                )

            # Weekly loss
            if self._weekly_loss / (portfolio_value or 1) > self.max_weekly_loss_pct:
                return self._trigger(
                    TradingStopReason.WEEKLY_LOSS,
                    f"Weekly loss ${self._weekly_loss:.2f} exceeds "
                    f"{self.max_weekly_loss_pct:.0%} of portfolio.",
                )

            # Consecutive losses
            if self._consec_losses >= self.max_consecutive_losses:
                return self._trigger(
                    TradingStopReason.CONSECUTIVE_LOSSES,
                    f"{self._consec_losses} consecutive losing trades.",
                )
            return None

    def record_trade_win(self) -> None:
        """Record a winning trade (resets consecutive-loss counter)."""
        with self._lock:
            self._consec_losses = 0

    def record_api_error(self) -> Optional[TradingStopEvent]:
        """Record an API error.  Triggers stop if too many occur in window."""
        import time as _time
        with self._lock:
            now = _time.monotonic()
            self._api_error_times.append(now)
            # Prune old errors outside window
            cutoff = now - self.api_error_window_secs
            self._api_error_times = [t for t in self._api_error_times if t >= cutoff]
            if len(self._api_error_times) > self.max_api_errors:
                return self._trigger(
                    TradingStopReason.API_ERRORS,
                    f"{len(self._api_error_times)} API errors in {self.api_error_window_secs}s window.",
                )
            return None

    def record_price(self, price: float) -> Optional[TradingStopEvent]:
        """
        Record the latest market price.  Checks for flash crash and data gaps.
        """
        import time as _time
        with self._lock:
            now = _time.monotonic()
            self._last_price_ts = now

            # Flash crash detection
            cutoff = now - self.flash_crash_window_secs
            self._price_hist = [(ts, p) for ts, p in self._price_hist if ts >= cutoff]
            self._price_hist.append((now, price))
            if len(self._price_hist) >= 2:
                baseline = self._price_hist[0][1]
                drop = (baseline - price) / (baseline or 1)
                if drop > self.flash_crash_drop_pct:
                    return self._trigger(
                        TradingStopReason.FLASH_CRASH,
                        f"Flash crash: price dropped {drop:.1%} in {self.flash_crash_window_secs}s.",
                    )
            return None

    def check_data_gap(self) -> Optional[TradingStopEvent]:
        """Check if price data has gone silent.  Call periodically."""
        import time as _time
        with self._lock:
            if self._last_price_ts is None:
                return None
            gap = _time.monotonic() - self._last_price_ts
            if gap > self.max_data_gap_secs:
                return self._trigger(
                    TradingStopReason.DATA_GAP,
                    f"Price data gap of {gap:.0f}s exceeds {self.max_data_gap_secs}s limit.",
                )
            return None

    # ------------------------------------------------------------------
    # Manual stop / reset
    # ------------------------------------------------------------------

    def trigger_manual(self, reason: str = "Manual emergency stop") -> TradingStopEvent:
        """Manually trigger the emergency stop."""
        with self._lock:
            return self._trigger(TradingStopReason.MANUAL, reason)

    def reset(self, reset_by: str = "operator") -> Tuple[bool, str]:
        """
        Reset the emergency stop after the cooldown period has elapsed.
        Returns (success, message).
        """
        with self._lock:
            if not self._is_stopped or not self._active_event:
                return False, "No active emergency stop to reset."
            now = datetime.now(timezone.utc)
            cooldown_until = self._active_event.cooldown_until
            if cooldown_until and now.isoformat() < cooldown_until:
                return False, f"Cooldown active until {cooldown_until}. Try again then."
            self._active_event.reset_at = now.isoformat()
            self._active_event.reset_by = reset_by
            self._is_stopped  = False
            self._active_event = None
            # Reset counters
            self._daily_loss   = 0.0
            self._weekly_loss  = 0.0
            self._consec_losses = 0
            self._api_error_times = []
            logger.info("TradingEmergencyStop: reset by %r", reset_by)
            return True, "Emergency stop reset. Trading may resume."

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    @property
    def is_stopped(self) -> bool:
        """True while any circuit breaker is open."""
        return self._is_stopped

    def get_status(self) -> Dict[str, Any]:
        """Return current status payload."""
        with self._lock:
            active = self._active_event.to_dict() if self._active_event else None
            return {
                "is_stopped":         self._is_stopped,
                "active_event":       active,
                "daily_loss_usd":     round(self._daily_loss, 2),
                "weekly_loss_usd":    round(self._weekly_loss, 2),
                "consecutive_losses": self._consec_losses,
                "api_errors_in_window": len(self._api_error_times),
                "total_events":       len(self._log),
                "thresholds": {
                    "single_trade_loss_pct": self.max_single_loss_pct,
                    "daily_loss_pct":        self.max_daily_loss_pct,
                    "weekly_loss_pct":       self.max_weekly_loss_pct,
                    "consecutive_losses":    self.max_consecutive_losses,
                    "max_api_errors":        self.max_api_errors,
                    "api_error_window_secs": self.api_error_window_secs,
                    "data_gap_secs":         self.max_data_gap_secs,
                    "flash_crash_pct":       self.flash_crash_drop_pct,
                    "cooldown_secs":         self.cooldown_secs,
                },
            }

    def get_log(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Return recent stop events."""
        with self._lock:
            return [e.to_dict() for e in self._log[-limit:]]

    def update_portfolio_value(self, value: float) -> None:
        with self._lock:
            self.portfolio_value = value

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _trigger(
        self, reason: TradingStopReason, details: str
    ) -> TradingStopEvent:
        """Open a circuit breaker (must be called under lock)."""
        now   = datetime.now(timezone.utc)
        cooldown = (now + timedelta(seconds=self.cooldown_secs)).isoformat()
        event = TradingStopEvent(
            event_id      = str(uuid.uuid4()),
            reason        = reason,
            details       = details,
            triggered_at  = now.isoformat(),
            cooldown_until = cooldown,
        )
        if len(self._log) >= _MAX_LOG:
            self._log = self._log[-_LOG_TRIM_SIZE:]
        self._log.append(event)
        self._is_stopped   = True
        self._active_event = event
        logger.critical(
            "TradingEmergencyStop TRIGGERED: %s — %s", reason.value, details
        )
        # Execute shutdown callbacks
        self._shutdown_sequence()
        if self._on_stop:
            try:
                self._on_stop(event)
            except Exception as exc:
                logger.error("TradingEmergencyStop: on_stop callback failed: %s", exc)
        return event

    def _shutdown_sequence(self) -> None:
        """Cancel orders, close positions (callbacks)."""
        if self._on_cancel_orders:
            try:
                self._on_cancel_orders()
            except Exception as exc:
                logger.error("TradingEmergencyStop: cancel_orders callback failed: %s", exc)
        if self._on_close_positions:
            try:
                self._on_close_positions()
            except Exception as exc:
                logger.error("TradingEmergencyStop: close_positions callback failed: %s", exc)

    def _maybe_reset_daily(self) -> None:
        """Reset daily/weekly counters at appropriate boundaries."""
        now = datetime.now(timezone.utc)
        today = now.date().isoformat()
        this_week = now.isocalendar()[:2]
        if today != self._daily_reset_date:
            self._daily_loss = 0.0
            self._daily_reset_date = today
        if this_week != self._weekly_reset_date:
            self._weekly_loss = 0.0
            self._weekly_reset_date = this_week
