# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Graduation Controller — Murphy System

Determines when paper trading has proven profitable enough to enable live
trading.  Graduation requires ALL criteria to be met simultaneously.

Graduation criteria
-------------------
  - 7 consecutive profitable trading days
  - ≥ 50 completed trades
  - Win rate > 55 %
  - Profit factor > 1.5
  - Max drawdown < 10 %
  - Sharpe ratio > 1.0
  - All individual strategies net-profitable (after fees)
  - No calibration errors logged in last 48 hours

Graduation statuses
-------------------
  NOT_READY   — criteria not met
  APPROACHING — 80 %+ of criteria met
  READY       — all criteria met, awaiting user confirmation
  GRADUATED   — user confirmed; live trading can be enabled
  SUSPENDED   — was graduated but live performance degraded; reverted to paper

Auto-suspension triggers live → paper rollback when live performance drops
below configurable thresholds.

Business Source License 1.1 (BSL 1.1)
Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
"""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MIN_PROFITABLE_DAYS    = 7
_MIN_TRADES             = 50
_MIN_WIN_RATE           = 0.55
_MIN_PROFIT_FACTOR      = 1.5
_MAX_DRAWDOWN           = 0.10
_MIN_SHARPE             = 1.0
_CALIBRATION_ERROR_WINDOW_H = 48   # hours
_APPROACHING_THRESHOLD  = 0.80     # 80 % of criteria met
_AUTO_SUSPEND_WIN_RATE  = 0.45     # auto-suspend if live win rate falls below
_AUTO_SUSPEND_DRAWDOWN  = 0.15     # auto-suspend if live drawdown exceeds

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class GraduationStatus(str, Enum):
    """Trading mode graduation state (Enum subclass)."""
    NOT_READY   = "not_ready"
    APPROACHING = "approaching"
    READY       = "ready"
    GRADUATED   = "graduated"
    SUSPENDED   = "suspended"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class GraduationCriteria:
    """Configurable graduation thresholds."""
    min_profitable_days:    int   = _MIN_PROFITABLE_DAYS
    min_trades:             int   = _MIN_TRADES
    min_win_rate:           float = _MIN_WIN_RATE
    min_profit_factor:      float = _MIN_PROFIT_FACTOR
    max_drawdown:           float = _MAX_DRAWDOWN
    min_sharpe:             float = _MIN_SHARPE
    calibration_error_window_hours: int = _CALIBRATION_ERROR_WINDOW_H

    def to_dict(self) -> Dict[str, Any]:
        return {
            "min_profitable_days":           self.min_profitable_days,
            "min_trades":                    self.min_trades,
            "min_win_rate_pct":              round(self.min_win_rate * 100, 1),
            "min_profit_factor":             self.min_profit_factor,
            "max_drawdown_pct":              round(self.max_drawdown * 100, 1),
            "min_sharpe_ratio":              self.min_sharpe,
            "calibration_error_window_hours": self.calibration_error_window_hours,
        }


@dataclass
class CriteriaEvaluation:
    """Result of evaluating a single graduation criterion."""
    name:        str
    required:    Any
    actual:      Any
    met:         bool
    description: str = ""


@dataclass
class GraduationEvent:
    """A status-change event in graduation history."""
    event_id:    str
    from_status: GraduationStatus
    to_status:   GraduationStatus
    reason:      str
    triggered_by: str   # "system" | "user"
    timestamp:   str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id":    self.event_id,
            "from_status": self.from_status.value,
            "to_status":   self.to_status.value,
            "reason":      self.reason,
            "triggered_by": self.triggered_by,
            "timestamp":   self.timestamp,
        }


# ---------------------------------------------------------------------------
# Daily performance snapshot
# ---------------------------------------------------------------------------


@dataclass
class DayStats:
    """Aggregated stats for a single trading day."""
    date:      str
    trades:    int    = 0
    wins:      int    = 0
    losses:    int    = 0
    gross_pnl: float  = 0.0
    gross_loss: float = 0.0

    @property
    def is_profitable(self) -> bool:
        return self.gross_pnl > 0 and self.gross_pnl > self.gross_loss


# ---------------------------------------------------------------------------
# Graduation Controller
# ---------------------------------------------------------------------------


class GraduationController:
    """
    Tracks paper-trading performance and gates live-trading activation.

    Thread-safe.  All mutable state guarded by Lock.
    """

    def __init__(
        self,
        criteria: Optional[GraduationCriteria] = None,
        auto_suspend_win_rate:  float = _AUTO_SUSPEND_WIN_RATE,
        auto_suspend_drawdown:  float = _AUTO_SUSPEND_DRAWDOWN,
    ) -> None:
        self.criteria               = criteria or GraduationCriteria()
        self.auto_suspend_win_rate  = auto_suspend_win_rate
        self.auto_suspend_drawdown  = auto_suspend_drawdown

        self._status: GraduationStatus = GraduationStatus.NOT_READY
        self._history: List[GraduationEvent] = []

        # Paper trading metrics
        self._day_stats: Dict[str, DayStats] = {}
        self._all_trades: List[Dict[str, Any]] = []   # {"pnl": float, "strategy": str, "timestamp": str}
        self._strategy_nets: Dict[str, float] = {}    # strategy_id → net P&L
        self._peak_equity: float = 0.0
        self._current_equity: float = 0.0
        self._calibration_errors: List[str] = []      # ISO timestamps

        # Live performance counters (post-graduation)
        self._live_wins: int  = 0
        self._live_losses: int = 0
        self._live_peak: float = 0.0
        self._live_equity: float = 0.0

        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Recording trade outcomes
    # ------------------------------------------------------------------

    def record_trade(
        self,
        pnl:         float,
        strategy_id: str = "default",
        fee_cost:    float = 0.0,
    ) -> None:
        """Record a completed paper trade outcome."""
        with self._lock:
            ts = datetime.now(timezone.utc)
            date_key = ts.date().isoformat()

            # Daily stats
            day = self._day_stats.setdefault(date_key, DayStats(date=date_key))
            day.trades += 1
            if pnl > 0:
                day.wins   += 1
                day.gross_pnl += pnl
            else:
                day.losses  += 1
                day.gross_loss += abs(pnl)

            # All-trades list
            self._all_trades.append({
                "pnl":       pnl,
                "strategy":  strategy_id,
                "timestamp": ts.isoformat(),
            })

            # Strategy net P&L
            net = pnl - fee_cost
            self._strategy_nets[strategy_id] = self._strategy_nets.get(strategy_id, 0.0) + net

            # Equity tracking
            self._current_equity += net
            self._peak_equity = max(self._peak_equity, self._current_equity)

            # Re-evaluate graduation status
            self._evaluate_and_update()

    def record_live_trade(self, pnl: float, equity: float) -> None:
        """Record a live trade for auto-suspension monitoring."""
        with self._lock:
            if pnl > 0:
                self._live_wins += 1
            else:
                self._live_losses += 1
            self._live_equity = equity
            self._live_peak   = max(self._live_peak, equity)
            self._check_auto_suspend()

    def record_calibration_error(self) -> None:
        """Log a calibration error (prevents graduation for 48 hours)."""
        with self._lock:
            self._calibration_errors.append(datetime.now(timezone.utc).isoformat())
            # Prune old errors
            cutoff = (datetime.now(timezone.utc) - timedelta(
                hours=self.criteria.calibration_error_window_hours
            )).isoformat()
            self._calibration_errors = [e for e in self._calibration_errors if e >= cutoff]

    # ------------------------------------------------------------------
    # Status transitions
    # ------------------------------------------------------------------

    def confirm_graduation(self, confirmed_by: str = "user") -> Tuple[bool, str]:
        """
        User confirms graduation from READY → GRADUATED.
        Returns (success, message).
        """
        with self._lock:
            if self._status != GraduationStatus.READY:
                return False, f"Cannot confirm: status is {self._status.value}, expected ready."
            self._transition(
                GraduationStatus.GRADUATED,
                f"User {confirmed_by!r} confirmed graduation.",
                triggered_by = confirmed_by,
            )
            return True, "Graduation confirmed — live trading may now be enabled."

    def override_status(
        self, new_status: GraduationStatus, reason: str, override_by: str = "admin"
    ) -> Tuple[bool, str]:
        """
        Manual status override with safety warning.
        Returns (success, message).
        """
        warning = ""
        if new_status == GraduationStatus.GRADUATED and self._status != GraduationStatus.READY:
            warning = " ⚠️  WARNING: forcing graduation without meeting all criteria is not recommended."
        with self._lock:
            prev = self._status
            self._transition(
                new_status,
                f"Manual override by {override_by!r}: {reason}",
                triggered_by = override_by,
            )
            return True, f"Status changed {prev.value} → {new_status.value}.{warning}"

    def reset_to_paper(self, reason: str = "manual reset") -> None:
        """Revert to paper trading and clear graduation state."""
        with self._lock:
            if self._status in (GraduationStatus.GRADUATED, GraduationStatus.SUSPENDED):
                self._transition(
                    GraduationStatus.NOT_READY,
                    reason,
                    triggered_by="system",
                )
            self._live_wins   = 0
            self._live_losses = 0
            self._live_peak   = 0.0
            self._live_equity = 0.0

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    def evaluate(self) -> List[CriteriaEvaluation]:
        """Evaluate all graduation criteria and return detailed results."""
        with self._lock:
            return self._build_evaluations()

    def get_status(self) -> Dict[str, Any]:
        """Return full graduation status payload."""
        with self._lock:
            evaluations = self._build_evaluations()
            met_count   = sum(1 for e in evaluations if e.met)
            total_count = len(evaluations)
            return {
                "status":             self._status.value,
                "criteria_met":       met_count,
                "criteria_total":     total_count,
                "completion_pct":     round(met_count / (total_count or 1) * 100, 1),
                "criteria":           [
                    {
                        "name":        e.name,
                        "required":    e.required,
                        "actual":      e.actual,
                        "met":         e.met,
                        "description": e.description,
                    }
                    for e in evaluations
                ],
                "thresholds":         self.criteria.to_dict(),
                "total_trades":       len(self._all_trades),
                "current_equity_usd": round(self._current_equity, 2),
                "peak_equity_usd":    round(self._peak_equity, 2),
                "history_count":      len(self._history),
            }

    def get_history(self) -> List[Dict[str, Any]]:
        """Return graduation event history."""
        with self._lock:
            return [e.to_dict() for e in self._history]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_evaluations(self) -> List[CriteriaEvaluation]:
        c = self.criteria
        trades = self._all_trades
        n = len(trades)

        # 1. Consecutive profitable days
        consec_days = self._consecutive_profitable_days()
        # 2. Total trades
        # 3. Win rate
        wins = sum(1 for t in trades if t["pnl"] > 0)
        win_rate = wins / n if n > 0 else 0.0
        # 4. Profit factor
        pf = self._profit_factor()
        # 5. Max drawdown
        dd = self._max_drawdown()
        # 6. Sharpe
        sharpe = self._sharpe_ratio()
        # 7. All strategies profitable
        all_strat = all(v > 0 for v in self._strategy_nets.values()) if self._strategy_nets else False
        # 8. No calibration errors in window
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=c.calibration_error_window_hours)).isoformat()
        recent_errors = [e for e in self._calibration_errors if e >= cutoff]
        no_cal_errors = len(recent_errors) == 0

        return [
            CriteriaEvaluation(
                name="consecutive_profitable_days",
                required=c.min_profitable_days,
                actual=consec_days,
                met=consec_days >= c.min_profitable_days,
                description=f"Need {c.min_profitable_days} consecutive profitable trading days.",
            ),
            CriteriaEvaluation(
                name="total_trades",
                required=c.min_trades,
                actual=n,
                met=n >= c.min_trades,
                description=f"Need at least {c.min_trades} completed trades.",
            ),
            CriteriaEvaluation(
                name="win_rate",
                required=f">{c.min_win_rate:.0%}",
                actual=f"{win_rate:.1%}",
                met=win_rate > c.min_win_rate,
                description=f"Win rate must exceed {c.min_win_rate:.0%}.",
            ),
            CriteriaEvaluation(
                name="profit_factor",
                required=f">{c.min_profit_factor}",
                actual=round(pf, 3),
                met=pf > c.min_profit_factor,
                description=f"Profit factor (gross profit / gross loss) must exceed {c.min_profit_factor}.",
            ),
            CriteriaEvaluation(
                name="max_drawdown",
                required=f"<{c.max_drawdown:.0%}",
                actual=f"{dd:.1%}",
                met=dd < c.max_drawdown,
                description=f"Maximum drawdown must stay below {c.max_drawdown:.0%}.",
            ),
            CriteriaEvaluation(
                name="sharpe_ratio",
                required=f">{c.min_sharpe}",
                actual=round(sharpe, 3),
                met=sharpe > c.min_sharpe,
                description=f"Sharpe ratio must exceed {c.min_sharpe}.",
            ),
            CriteriaEvaluation(
                name="all_strategies_profitable",
                required=True,
                actual=all_strat,
                met=all_strat,
                description="All individual strategies must be net-profitable after fees.",
            ),
            CriteriaEvaluation(
                name="no_calibration_errors",
                required=True,
                actual=no_cal_errors,
                met=no_cal_errors,
                description=f"No calibration errors in the last {c.calibration_error_window_hours} hours.",
            ),
        ]

    def _evaluate_and_update(self) -> None:
        """Update status based on current evaluations (must be called under lock)."""
        if self._status in (GraduationStatus.GRADUATED, GraduationStatus.SUSPENDED):
            return  # Don't auto-advance from these states
        evals = self._build_evaluations()
        met = sum(1 for e in evals if e.met)
        total = len(evals)

        if met == total:
            new_status = GraduationStatus.READY
        elif met / total >= _APPROACHING_THRESHOLD:
            new_status = GraduationStatus.APPROACHING
        else:
            new_status = GraduationStatus.NOT_READY

        if new_status != self._status:
            self._transition(
                new_status,
                f"Criteria evaluation: {met}/{total} criteria met.",
                triggered_by="system",
            )

    def _check_auto_suspend(self) -> None:
        """Auto-suspend live trading if performance degrades (must be called under lock)."""
        if self._status != GraduationStatus.GRADUATED:
            return
        total_live = self._live_wins + self._live_losses
        if total_live < 10:
            return  # Not enough data
        live_win_rate = self._live_wins / total_live
        live_dd = (
            (self._live_peak - self._live_equity) / self._live_peak
            if self._live_peak > 0 else 0.0
        )
        if live_win_rate < self.auto_suspend_win_rate or live_dd > self.auto_suspend_drawdown:
            self._transition(
                GraduationStatus.SUSPENDED,
                f"Auto-suspension: live win rate {live_win_rate:.1%}, "
                f"live drawdown {live_dd:.1%}.",
                triggered_by="system",
            )
            logger.warning(
                "GraduationController: AUTO-SUSPENDED — performance degraded "
                "(win_rate=%.1f%%, drawdown=%.1f%%).",
                live_win_rate * 100, live_dd * 100,
            )

    def _transition(
        self, new_status: GraduationStatus, reason: str, triggered_by: str = "system"
    ) -> None:
        """Record a status transition (must be called under lock)."""
        event = GraduationEvent(
            event_id     = str(uuid.uuid4()),
            from_status  = self._status,
            to_status    = new_status,
            reason       = reason,
            triggered_by = triggered_by,
        )
        self._history.append(event)
        self._status = new_status
        logger.info(
            "GraduationController: %s → %s (%s)",
            event.from_status.value, new_status.value, reason,
        )

    def _consecutive_profitable_days(self) -> int:
        """Return the number of trailing consecutive profitable days."""
        sorted_days = sorted(self._day_stats.values(), key=lambda d: d.date, reverse=True)
        count = 0
        for day in sorted_days:
            if day.is_profitable:
                count += 1
            else:
                break
        return count

    def _profit_factor(self) -> float:
        """Gross profit / gross loss."""
        gross_profit = sum(t["pnl"] for t in self._all_trades if t["pnl"] > 0)
        gross_loss   = sum(abs(t["pnl"]) for t in self._all_trades if t["pnl"] < 0)
        return gross_profit / (gross_loss or 1)

    def _max_drawdown(self) -> float:
        """Maximum peak-to-trough drawdown fraction from paper equity curve."""
        if self._peak_equity <= 0:
            return 0.0
        return (self._peak_equity - self._current_equity) / self._peak_equity

    def _sharpe_ratio(self) -> float:
        """Approximate annualized Sharpe from daily P&L."""
        import math
        import statistics as _stats
        daily_pnls = [d.gross_pnl - d.gross_loss for d in self._day_stats.values()]
        if len(daily_pnls) < 2:
            return 0.0
        try:
            mean_r = _stats.mean(daily_pnls)
            std_r  = _stats.stdev(daily_pnls)
            if std_r <= 0:
                return 0.0
            return (mean_r / std_r) * math.sqrt(252)
        except Exception:
            return 0.0
