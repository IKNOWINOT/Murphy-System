# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Profit Sweep — Murphy System

Automated end-of-day profit transfer to Coinbase staked Cosmos ATOM.

Schedule: 5:00 PM ET every business day (Mon–Fri).
Calculation:
  sweepable = portfolio_value - starting_capital - open_positions_value
              - pending_orders_value - (profit * CASH_RESERVE_PERCENT/100)

All execution is DRY-RUN by default.  Set PROFIT_SWEEP_ENABLED=true to go
live.

Business Source License 1.1 (BSL 1.1)
Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration (all overridable via env vars)
# ---------------------------------------------------------------------------

_SWEEP_TIME             = os.getenv("SWEEP_TIME",            "17:00")
_SWEEP_TZ               = os.getenv("SWEEP_TIMEZONE",        "US/Eastern")
_MIN_SWEEP_AMOUNT       = float(os.getenv("MIN_SWEEP_AMOUNT",   "10.0"))
_CASH_RESERVE_PCT       = float(os.getenv("CASH_RESERVE_PERCENT", "20.0"))
_SWEEP_ASSET            = os.getenv("SWEEP_ASSET",           "ATOM")
_SWEEP_ENABLED          = os.getenv("PROFIT_SWEEP_ENABLED",  "false").lower() == "true"
_MAX_PURCHASE_RETRIES   = 3

_HISTORY_MAX_RECORDS    = 1_000


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class SweepStatus(Enum):
    """Result status of a sweep record (Enum subclass)."""
    DRY_RUN    = "dry_run"
    EXECUTED   = "executed"
    SKIPPED    = "skipped"
    FAILED     = "failed"
    PARTIAL    = "partial"   # ATOM bought but staking failed


class SweepError(Exception):
    """Base exception for sweep failures."""


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class SweepRecord:
    """Immutable record of one sweep attempt (executed or dry-run)."""
    sweep_id:          str
    timestamp:         str
    status:            SweepStatus
    portfolio_value:   float
    starting_capital:  float
    open_positions:    float
    pending_orders:    float
    cash_reserve:      float
    sweepable_profit:  float
    sweep_amount_usd:  float
    atom_purchased:    float          = 0.0
    atom_price_usd:    float          = 0.0
    staking_tx_id:     Optional[str]  = None
    error_message:     Optional[str]  = None
    dry_run:           bool           = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sweep_id":        self.sweep_id,
            "timestamp":       self.timestamp,
            "status":          self.status.value,
            "portfolio_value": self.portfolio_value,
            "starting_capital": self.starting_capital,
            "open_positions":  self.open_positions,
            "pending_orders":  self.pending_orders,
            "cash_reserve":    self.cash_reserve,
            "sweepable_profit": self.sweepable_profit,
            "sweep_amount_usd": self.sweep_amount_usd,
            "atom_purchased":  self.atom_purchased,
            "atom_price_usd":  self.atom_price_usd,
            "staking_tx_id":   self.staking_tx_id,
            "error_message":   self.error_message,
            "dry_run":         self.dry_run,
        }


@dataclass
class SweepStats:
    """Aggregate statistics over all executed sweeps."""
    total_sweeps_executed:   int   = 0
    total_usd_swept:         float = 0.0
    total_atom_accumulated:  float = 0.0
    total_dry_runs:          int   = 0
    total_skipped:           int   = 0
    total_failed:            int   = 0
    last_sweep_timestamp:    Optional[str] = None
    current_atom_staked:     float = 0.0
    atom_staking_apy:        float = 0.0


# ---------------------------------------------------------------------------
# Profit Calculator
# ---------------------------------------------------------------------------

class ProfitCalculator:
    """Pure profit-calculation logic; no external I/O."""

    def calculate(
        self,
        portfolio_value:  float,
        starting_capital: float,
        open_positions:   float,
        pending_orders:   float,
        cash_reserve_pct: float = _CASH_RESERVE_PCT,
    ) -> Dict[str, float]:
        """
        Return a breakdown dict with keys:
          gross_profit, reserved_positions, reserved_pending,
          reserved_cash, sweepable_profit
        """
        gross_profit = portfolio_value - starting_capital

        if gross_profit < 0:
            raise SweepError(
                f"Negative gross profit detected: portfolio={portfolio_value:.2f}, "
                f"starting={starting_capital:.2f}.  Halting sweep — manual review required."
            )

        reserved_cash = gross_profit * (cash_reserve_pct / 100.0)
        sweepable = gross_profit - open_positions - pending_orders - reserved_cash
        sweepable = max(sweepable, 0.0)

        return {
            "gross_profit":      round(gross_profit,  2),
            "reserved_positions": round(open_positions, 2),
            "reserved_pending":  round(pending_orders, 2),
            "reserved_cash":     round(reserved_cash, 2),
            "sweepable_profit":  round(sweepable, 2),
        }


# ---------------------------------------------------------------------------
# Main ProfitSweep class
# ---------------------------------------------------------------------------

class ProfitSweep:
    """
    End-of-day profit sweeper.

    Usage::

        sweeper = ProfitSweep(coinbase_connector=..., starting_capital=10_000)
        sweeper.run_sweep()          # respects PROFIT_SWEEP_ENABLED
    """

    def __init__(
        self,
        coinbase_connector:  Optional[Any]  = None,
        starting_capital:    float          = 10_000.0,
        enabled:             Optional[bool] = None,
        min_sweep_amount:    float          = _MIN_SWEEP_AMOUNT,
        cash_reserve_pct:    float          = _CASH_RESERVE_PCT,
        sweep_asset:         str            = _SWEEP_ASSET,
    ) -> None:
        self._coinbase        = coinbase_connector
        self._starting_capital = starting_capital
        self._enabled         = _SWEEP_ENABLED if enabled is None else enabled
        self._min_sweep       = min_sweep_amount
        self._cash_reserve    = cash_reserve_pct
        self._sweep_asset     = sweep_asset
        self._calculator      = ProfitCalculator()
        self._history:        List[SweepRecord] = []
        self._stats           = SweepStats()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_sweep(
        self,
        portfolio_value:  Optional[float] = None,
        open_positions:   float           = 0.0,
        pending_orders:   float           = 0.0,
    ) -> SweepRecord:
        """
        Execute (or simulate) the end-of-day sweep.

        Returns a SweepRecord regardless of dry-run/live mode.
        """
        sweep_id  = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()

        if portfolio_value is None:
            portfolio_value = self._fetch_portfolio_value()

        # --- profit calculation ---
        try:
            breakdown = self._calculator.calculate(
                portfolio_value  = portfolio_value,
                starting_capital = self._starting_capital,
                open_positions   = open_positions,
                pending_orders   = pending_orders,
                cash_reserve_pct = self._cash_reserve,
            )
        except SweepError as exc:
            record = SweepRecord(
                sweep_id          = sweep_id,
                timestamp         = timestamp,
                status            = SweepStatus.FAILED,
                portfolio_value   = portfolio_value,
                starting_capital  = self._starting_capital,
                open_positions    = open_positions,
                pending_orders    = pending_orders,
                cash_reserve      = 0.0,
                sweepable_profit  = 0.0,
                sweep_amount_usd  = 0.0,
                error_message     = str(exc),
                dry_run           = not self._enabled,
            )
            self._append_record(record)
            logger.error("Sweep halted: %s", exc)
            return record

        sweepable = breakdown["sweepable_profit"]
        reserve   = breakdown["reserved_cash"]

        # --- minimum threshold check ---
        if sweepable < self._min_sweep:
            record = SweepRecord(
                sweep_id          = sweep_id,
                timestamp         = timestamp,
                status            = SweepStatus.SKIPPED,
                portfolio_value   = portfolio_value,
                starting_capital  = self._starting_capital,
                open_positions    = open_positions,
                pending_orders    = pending_orders,
                cash_reserve      = reserve,
                sweepable_profit  = sweepable,
                sweep_amount_usd  = sweepable,
                dry_run           = not self._enabled,
            )
            self._append_record(record)
            logger.info(
                "Sweep skipped — sweepable $%.2f below minimum $%.2f",
                sweepable, self._min_sweep,
            )
            self._stats.total_skipped += 1
            return record

        # --- dry-run mode ---
        if not self._enabled:
            record = SweepRecord(
                sweep_id          = sweep_id,
                timestamp         = timestamp,
                status            = SweepStatus.DRY_RUN,
                portfolio_value   = portfolio_value,
                starting_capital  = self._starting_capital,
                open_positions    = open_positions,
                pending_orders    = pending_orders,
                cash_reserve      = reserve,
                sweepable_profit  = sweepable,
                sweep_amount_usd  = sweepable,
                dry_run           = True,
            )
            self._append_record(record)
            logger.info(
                "[DRY-RUN] Would sweep $%.2f → %s (portfolio=$%.2f)",
                sweepable, self._sweep_asset, portfolio_value,
            )
            self._stats.total_dry_runs += 1
            return record

        # --- live execution ---
        return self._execute_live_sweep(
            sweep_id        = sweep_id,
            timestamp       = timestamp,
            portfolio_value = portfolio_value,
            open_positions  = open_positions,
            pending_orders  = pending_orders,
            reserve         = reserve,
            sweepable       = sweepable,
        )

    def get_history(self, limit: int = 30) -> List[Dict[str, Any]]:
        """Return last *limit* sweep records as dicts (newest first)."""
        return [r.to_dict() for r in reversed(self._history[-limit:])]

    def get_stats(self) -> Dict[str, Any]:
        """Return aggregate sweep statistics."""
        return {
            "total_sweeps_executed":  self._stats.total_sweeps_executed,
            "total_usd_swept":        round(self._stats.total_usd_swept, 2),
            "total_atom_accumulated": round(self._stats.total_atom_accumulated, 4),
            "total_dry_runs":         self._stats.total_dry_runs,
            "total_skipped":          self._stats.total_skipped,
            "total_failed":           self._stats.total_failed,
            "last_sweep_timestamp":   self._stats.last_sweep_timestamp,
            "current_atom_staked":    round(self._stats.current_atom_staked, 4),
            "atom_staking_apy":       self._stats.atom_staking_apy,
            "sweep_enabled":          self._enabled,
            "min_sweep_amount":       self._min_sweep,
            "cash_reserve_pct":       self._cash_reserve,
            "sweep_asset":            self._sweep_asset,
        }

    def get_next_sweep_info(self) -> Dict[str, Any]:
        """Return information about the next scheduled sweep."""
        try:
            from datetime import timedelta

            import pytz
            tz  = pytz.timezone(_SWEEP_TZ)
            now = datetime.now(tz)
            h, m = map(int, _SWEEP_TIME.split(":"))
            target = now.replace(hour=h, minute=m, second=0, microsecond=0)
            if now >= target:
                # next business day
                target += timedelta(days=1)
                while target.weekday() >= 5:          # skip Sat/Sun
                    target += timedelta(days=1)
            seconds_until = int((target - now).total_seconds())
            return {
                "next_sweep_time":     target.isoformat(),
                "seconds_until_sweep": seconds_until,
                "sweep_timezone":      _SWEEP_TZ,
                "sweep_time":          _SWEEP_TIME,
                "sweep_enabled":       self._enabled,
            }
        except Exception as exc:
            logger.warning("Could not calculate next sweep time: %s", exc)
            return {"error": str(exc), "sweep_enabled": self._enabled}

    def update_atom_balance(self, staked: float, apy: float) -> None:
        """Update tracked ATOM staking balance from external source."""
        self._stats.current_atom_staked = staked
        self._stats.atom_staking_apy    = apy

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _execute_live_sweep(
        self,
        sweep_id:        str,
        timestamp:       str,
        portfolio_value: float,
        open_positions:  float,
        pending_orders:  float,
        reserve:         float,
        sweepable:       float,
    ) -> SweepRecord:
        atom_purchased  = 0.0
        atom_price      = 0.0
        staking_tx_id   = None
        status          = SweepStatus.FAILED
        error_msg: Optional[str] = None

        # Step 1 — buy ATOM with retries + exponential back-off
        pair     = f"{self._sweep_asset}-USD"
        last_exc = ""
        for attempt in range(1, _MAX_PURCHASE_RETRIES + 1):
            try:
                order_result = self._coinbase.place_market_order(
                    product_id   = pair,
                    side         = "BUY",
                    # quote_size purchases a USD amount of ATOM (Coinbase Advanced Trade API)
                    quote_size   = str(sweepable),
                )
                atom_purchased = float(order_result.get("filled_size",  0))
                atom_price     = float(order_result.get("average_price", 0))
                logger.info(
                    "ATOM purchase succeeded (attempt %d): %.4f ATOM @ $%.2f",
                    attempt, atom_purchased, atom_price,
                )
                break
            except Exception as exc:
                last_exc = str(exc)
                logger.warning(
                    "ATOM purchase attempt %d/%d failed: %s",
                    attempt, _MAX_PURCHASE_RETRIES, exc,
                )
                if attempt < _MAX_PURCHASE_RETRIES:
                    time.sleep(2 ** attempt)        # 2 s (attempt 1→2), 4 s (attempt 2→3)
        else:
            error_msg = f"ATOM purchase failed after {_MAX_PURCHASE_RETRIES} attempts: {last_exc}"
            record = SweepRecord(
                sweep_id          = sweep_id,
                timestamp         = timestamp,
                status            = SweepStatus.FAILED,
                portfolio_value   = portfolio_value,
                starting_capital  = self._starting_capital,
                open_positions    = open_positions,
                pending_orders    = pending_orders,
                cash_reserve      = reserve,
                sweepable_profit  = sweepable,
                sweep_amount_usd  = sweepable,
                error_message     = error_msg,
                dry_run           = False,
            )
            self._append_record(record)
            self._stats.total_failed += 1
            return record

        # Step 2 — stake purchased ATOM
        try:
            stake_result  = self._coinbase.stake_asset(
                asset    = self._sweep_asset,
                amount   = str(atom_purchased),
            )
            staking_tx_id = stake_result.get("transaction_id") or stake_result.get("id")
            status        = SweepStatus.EXECUTED
            logger.info("ATOM staking initiated, tx_id=%s", staking_tx_id)
        except Exception as exc:
            # Partial — ATOM bought but staking failed; hold and retry next day
            status    = SweepStatus.PARTIAL
            error_msg = f"Staking failed (will retry next day): {exc}"
            logger.error("ATOM staking failed: %s", exc)

        record = SweepRecord(
            sweep_id          = sweep_id,
            timestamp         = timestamp,
            status            = status,
            portfolio_value   = portfolio_value,
            starting_capital  = self._starting_capital,
            open_positions    = open_positions,
            pending_orders    = pending_orders,
            cash_reserve      = reserve,
            sweepable_profit  = sweepable,
            sweep_amount_usd  = sweepable,
            atom_purchased    = atom_purchased,
            atom_price_usd    = atom_price,
            staking_tx_id     = staking_tx_id,
            error_message     = error_msg,
            dry_run           = False,
        )
        self._append_record(record)

        if status == SweepStatus.EXECUTED:
            self._stats.total_sweeps_executed  += 1
            self._stats.total_usd_swept        += sweepable
            self._stats.total_atom_accumulated += atom_purchased
            self._stats.current_atom_staked    += atom_purchased
            self._stats.last_sweep_timestamp   = timestamp
        else:
            self._stats.total_failed += 1

        return record

    def _fetch_portfolio_value(self) -> float:
        """Fetch current portfolio value from Coinbase connector."""
        if self._coinbase is None:
            raise SweepError("No Coinbase connector configured; portfolio_value must be provided.")
        try:
            data = self._coinbase.get_portfolio_value()
            return float(data.get("total_value_usd", 0))
        except Exception as exc:
            raise SweepError(f"Failed to fetch portfolio value: {exc}") from exc

    def _append_record(self, record: SweepRecord) -> None:
        if len(self._history) >= _HISTORY_MAX_RECORDS:
            del self._history[:_HISTORY_MAX_RECORDS // 10]
        self._history.append(record)


# ---------------------------------------------------------------------------
# Business-day helper
# ---------------------------------------------------------------------------

def is_business_day(dt: Optional[datetime] = None) -> bool:
    """Return True if *dt* (default: now UTC) is Mon–Fri."""
    if dt is None:
        dt = datetime.now(timezone.utc)
    return dt.weekday() < 5          # 0=Mon … 4=Fri
