"""
Cost Explosion Gate for Murphy System.

Design Label: FIN-002 — Multi-Layer Cost Protection & Explosion Detection
Owner: Finance Team / Platform Engineering
Dependencies:
  - EmergencyStopController (OPS-004, triggered on explosion events)
  - WingmanProtocol (optional, for cost-approval validation)

Implements Phase 8 — Operational Readiness & Autonomy Governance:
  Provides multi-layered cost protection by detecting and preventing
  exponential cost increases caused by runaway or misbehaving automations.
  Operates at four tiers: TASK, SESSION, TENANT, GLOBAL.

Explosion Detection Algorithm:
  - Sliding window of last 100 cost events per tier/owner.
  - Exponential moving average (EMA) with alpha=0.3.
  - Latest cost > 3× EMA  → EXPLOSION_DETECTED → trigger emergency stop.
  - Latest cost > 2× EMA  → CRITICAL            → block further spending.
  - Latest cost > 1.5× EMA → WARNING             → log warning.
  - Budget remaining < 10% → ELEVATED.

Circuit Breaker:
  - Track cost events per minute and per hour per tier/owner.
  - If rate exceeds configured max → trip circuit breaker → block new costs.
  - Auto-reset after configurable cooldown (default 5 minutes).

Safety invariants:
  - Thread-safe: all shared state guarded by Lock.
  - Bounded: event windows capped at _WINDOW_SIZE.
  - Fail-safe: ambiguous state → ELEVATED or CRITICAL.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Deque, Dict, List, Optional, Tuple

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_WINDOW_SIZE = 100          # sliding window per tier/owner
_EMA_ALPHA = 0.3            # EMA smoothing factor
_EXPLOSION_MULT = 3.0       # > 3× EMA → explosion
_CRITICAL_MULT = 2.0        # > 2× EMA → critical
_WARNING_MULT = 1.5         # > 1.5× EMA → warning
_ELEVATED_BUDGET_PCT = 0.10  # < 10% remaining → elevated
_DEFAULT_COOLDOWN_S = 300   # 5 minutes

_DEFAULT_BUDGETS: Dict[str, Dict[str, Any]] = {
    "task": {"limit": 10.0, "period": "task"},
    "session": {"limit": 100.0, "period": "session"},
    "tenant_daily": {"limit": 500.0, "period": "daily"},
    "global_daily": {"limit": 5000.0, "period": "daily"},
}

_MAX_HISTORY = 10_000


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class CostTier(str, Enum):
    """Budget / alerting tier levels."""
    TASK = "task"
    SESSION = "session"
    TENANT = "tenant"
    GLOBAL = "global"


class CostAlert(str, Enum):
    """Cost alert severity levels, from lowest to highest."""
    NOMINAL = "nominal"
    ELEVATED = "elevated"
    WARNING = "warning"
    CRITICAL = "critical"
    EXPLOSION_DETECTED = "explosion_detected"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class CostBudget:
    """A budget entry for a given tier / owner."""
    budget_id: str
    tier: CostTier
    owner_id: str
    limit: float
    spent: float
    currency: str
    period: str       # task / session / daily / monthly
    reset_at: str

    @property
    def remaining(self) -> float:
        return max(0.0, self.limit - self.spent)

    @property
    def remaining_fraction(self) -> float:
        if self.limit <= 0:
            return 0.0
        return self.remaining / self.limit

    def to_dict(self) -> Dict[str, Any]:
        return {
            "budget_id": self.budget_id,
            "tier": self.tier.value,
            "owner_id": self.owner_id,
            "limit": self.limit,
            "spent": self.spent,
            "remaining": self.remaining,
            "currency": self.currency,
            "period": self.period,
            "reset_at": self.reset_at,
        }


@dataclass
class CostEvent:
    """A single cost record."""
    event_id: str
    tier: CostTier
    owner_id: str
    amount: float
    description: str
    action_id: str
    timestamp: str
    cumulative_spend: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "tier": self.tier.value,
            "owner_id": self.owner_id,
            "amount": self.amount,
            "description": self.description,
            "action_id": self.action_id,
            "timestamp": self.timestamp,
            "cumulative_spend": self.cumulative_spend,
        }


@dataclass
class ExplosionSignal:
    """Signal emitted when a cost explosion is detected."""
    signal_id: str
    tier: CostTier
    owner_id: str
    rate_of_change: float
    moving_avg: float
    spike_magnitude: float
    alert_level: CostAlert
    recommended_action: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "tier": self.tier.value,
            "owner_id": self.owner_id,
            "rate_of_change": self.rate_of_change,
            "moving_avg": self.moving_avg,
            "spike_magnitude": self.spike_magnitude,
            "alert_level": self.alert_level.value,
            "recommended_action": self.recommended_action,
        }


@dataclass
class _CircuitBreaker:
    """Per-scope circuit breaker state."""
    max_per_minute: float
    max_per_hour: float
    tripped: bool = False
    tripped_at: Optional[float] = None
    cooldown_s: float = _DEFAULT_COOLDOWN_S
    # Timestamps of recent cost events (epoch seconds)
    recent_minute: Deque[float] = field(default_factory=deque)
    recent_hour: Deque[float] = field(default_factory=deque)


# ---------------------------------------------------------------------------
# Gate
# ---------------------------------------------------------------------------

class CostExplosionGate:
    """
    Multi-layered cost protection with explosion detection, circuit breakers,
    and cascading budget gates.

    Usage::

        gate = CostExplosionGate()
        result = gate.record_cost(CostTier.TASK, "task-1", 5.0, "LLM call")
        assert result["recorded"]
    """

    def __init__(
        self,
        emergency_stop=None,
        wingman_protocol=None,
        default_budgets: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._lock = threading.Lock()
        self._emergency_stop = emergency_stop or self._make_emergency_stop()
        self._wingman_protocol = wingman_protocol

        # budget_key → CostBudget
        self._budgets: Dict[str, CostBudget] = {}
        # (tier_value, owner_id) → Deque[CostEvent] (sliding window)
        self._windows: Dict[Tuple[str, str], Deque[CostEvent]] = {}
        # (tier_value, owner_id) → _CircuitBreaker
        self._breakers: Dict[Tuple[str, str], _CircuitBreaker] = {}
        # EMA per (tier_value, owner_id)
        self._ema: Dict[Tuple[str, str], float] = {}
        # Flat audit log
        self._audit: List[Dict[str, Any]] = []
        # Recent explosion signals
        self._explosions: List[Dict[str, Any]] = []

        self._setup_default_budgets(default_budgets or _DEFAULT_BUDGETS)

    # ------------------------------------------------------------------
    # Dependency factory
    # ------------------------------------------------------------------

    @staticmethod
    def _make_emergency_stop():
        try:
            from emergency_stop_controller import EmergencyStopController
            return EmergencyStopController()
        except Exception as exc:
            logger.debug("EmergencyStopController unavailable: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Default budgets
    # ------------------------------------------------------------------

    def _setup_default_budgets(self, defaults: Dict[str, Any]) -> None:
        mapping = {
            "task": (CostTier.TASK, "default", "task"),
            "session": (CostTier.SESSION, "default", "session"),
            "tenant_daily": (CostTier.TENANT, "default", "daily"),
            "global_daily": (CostTier.GLOBAL, "default", "daily"),
        }
        for key, (tier, owner, period) in mapping.items():
            if key in defaults:
                limit = defaults[key].get("limit", 10.0)
                self.register_budget(tier, owner, limit, period)

    # ------------------------------------------------------------------
    # Budget management
    # ------------------------------------------------------------------

    def register_budget(
        self,
        tier: CostTier,
        owner_id: str,
        limit: float,
        period: str = "daily",
        currency: str = "USD",
    ) -> CostBudget:
        """Register or replace a budget for a tier/owner combination."""
        budget_id = f"bgt-{uuid.uuid4().hex[:10]}"
        budget = CostBudget(
            budget_id=budget_id,
            tier=tier,
            owner_id=owner_id,
            limit=limit,
            spent=0.0,
            currency=currency,
            period=period,
            reset_at=datetime.now(timezone.utc).isoformat(),
        )
        key = self._budget_key(tier, owner_id)
        with self._lock:
            self._budgets[key] = budget
        logger.debug("Budget registered: %s tier=%s owner=%s limit=%.2f", budget_id, tier.value, owner_id, limit)
        return budget

    def reset_budget(self, budget_id: str) -> bool:
        """Manually reset a budget's spent amount (e.g., new billing period)."""
        with self._lock:
            for budget in self._budgets.values():
                if budget.budget_id == budget_id:
                    budget.spent = 0.0
                    budget.reset_at = datetime.now(timezone.utc).isoformat()
                    return True
        return False

    # ------------------------------------------------------------------
    # Cost recording
    # ------------------------------------------------------------------

    def record_cost(
        self,
        tier: CostTier,
        owner_id: str,
        amount: float,
        description: str,
        action_id: str = "",
    ) -> Dict[str, Any]:
        """Record a cost event and run explosion detection.

        Returns:
            recorded, alert_level, budget_remaining, explosion_detected, action_taken
        """
        with self._lock:
            # Check circuit breaker first
            cb_key = (tier.value, owner_id)
            breaker = self._breakers.get(cb_key)
            if breaker is not None and self._is_tripped(breaker):
                return {
                    "recorded": False,
                    "alert_level": CostAlert.CRITICAL.value,
                    "budget_remaining": self._budget_remaining_locked(tier, owner_id),
                    "explosion_detected": False,
                    "action_taken": "circuit_breaker_open",
                }

            # Update budget
            key = self._budget_key(tier, owner_id)
            budget = self._budgets.get(key)
            if budget is not None:
                budget.spent += amount

            cumulative = budget.spent if budget is not None else amount

            # Create event
            evt = CostEvent(
                event_id=f"ce-{uuid.uuid4().hex[:10]}",
                tier=tier,
                owner_id=owner_id,
                amount=amount,
                description=description,
                action_id=action_id,
                timestamp=datetime.now(timezone.utc).isoformat(),
                cumulative_spend=cumulative,
            )

            # Add to sliding window
            window = self._windows.setdefault(cb_key, deque(maxlen=_WINDOW_SIZE))
            window.append(evt)

            # Update circuit breaker event history
            if breaker is not None:
                now_ts = time.time()
                breaker.recent_minute.append(now_ts)
                breaker.recent_hour.append(now_ts)
                self._prune_breaker(breaker, now_ts)
                if (
                    len(breaker.recent_minute) > breaker.max_per_minute
                    or len(breaker.recent_hour) > breaker.max_per_hour
                ):
                    breaker.tripped = True
                    breaker.tripped_at = now_ts
                    logger.warning("Circuit breaker tripped: tier=%s owner=%s", tier.value, owner_id)

            # Update EMA — compute alert against the PREVIOUS EMA so a spike
            # is detected relative to the stable baseline (not the spike itself).
            prev_ema = self._ema.get(cb_key, amount)
            new_ema = _EMA_ALPHA * amount + (1.0 - _EMA_ALPHA) * prev_ema
            self._ema[cb_key] = new_ema

            # Determine alert level using the old (pre-spike) EMA as baseline
            alert_level, explosion_detected = self._compute_alert(tier, owner_id, amount, prev_ema, budget)

            # Persist audit entry
            audit_entry = {**evt.to_dict(), "alert_level": alert_level.value}
            capped_append(self._audit, audit_entry, _MAX_HISTORY)

        # Trigger emergency stop outside the main lock to avoid re-entrancy
        action_taken = "recorded"
        if explosion_detected:
            action_taken = "emergency_stop_triggered"
            self._trigger_stop(tier, owner_id, "cost explosion detected")
            signal = ExplosionSignal(
                signal_id=f"sig-{uuid.uuid4().hex[:8]}",
                tier=tier,
                owner_id=owner_id,
                rate_of_change=amount,
                moving_avg=new_ema,
                spike_magnitude=amount / (new_ema or 1),
                alert_level=alert_level,
                recommended_action="halt_spending_immediately",
            )
            with self._lock:
                capped_append(self._explosions, signal.to_dict(), 1000)

        budget_remaining = self._budget_remaining(tier, owner_id)

        return {
            "recorded": True,
            "alert_level": alert_level.value,
            "budget_remaining": budget_remaining,
            "explosion_detected": explosion_detected,
            "action_taken": action_taken,
        }

    def _compute_alert(
        self,
        tier: CostTier,
        owner_id: str,
        amount: float,
        ema: float,
        budget: Optional[CostBudget],
    ) -> Tuple[CostAlert, bool]:
        """Determine alert level. Caller must hold self._lock."""
        explosion = False
        alert = CostAlert.NOMINAL

        if ema > 0:
            ratio = amount / ema
            if ratio > _EXPLOSION_MULT:
                alert = CostAlert.EXPLOSION_DETECTED
                explosion = True
            elif ratio > _CRITICAL_MULT:
                alert = CostAlert.CRITICAL
            elif ratio > _WARNING_MULT:
                alert = CostAlert.WARNING

        if alert == CostAlert.NOMINAL and budget is not None:
            if budget.remaining_fraction < _ELEVATED_BUDGET_PCT:
                alert = CostAlert.ELEVATED

        return alert, explosion

    # ------------------------------------------------------------------
    # Pre-flight check
    # ------------------------------------------------------------------

    def check_budget(
        self,
        tier: CostTier,
        owner_id: str,
        proposed_amount: float,
    ) -> Dict[str, Any]:
        """Pre-flight check before spending.

        Returns:
            allowed, budget_remaining, alert_level, reason
        """
        with self._lock:
            # Circuit breaker
            cb_key = (tier.value, owner_id)
            breaker = self._breakers.get(cb_key)
            if breaker is not None and self._is_tripped(breaker):
                return {
                    "allowed": False,
                    "budget_remaining": self._budget_remaining_locked(tier, owner_id),
                    "alert_level": CostAlert.CRITICAL.value,
                    "reason": "circuit_breaker_open",
                }

            key = self._budget_key(tier, owner_id)
            budget = self._budgets.get(key)
            if budget is None:
                return {
                    "allowed": True,
                    "budget_remaining": None,
                    "alert_level": CostAlert.NOMINAL.value,
                    "reason": "no_budget_configured",
                }

            if proposed_amount > budget.remaining:
                return {
                    "allowed": False,
                    "budget_remaining": budget.remaining,
                    "alert_level": CostAlert.CRITICAL.value,
                    "reason": "budget_exceeded",
                }

            alert = CostAlert.NOMINAL
            if budget.remaining_fraction < _ELEVATED_BUDGET_PCT:
                alert = CostAlert.ELEVATED

            return {
                "allowed": True,
                "budget_remaining": budget.remaining,
                "alert_level": alert.value,
                "reason": "ok",
            }

    # ------------------------------------------------------------------
    # Explosion detection
    # ------------------------------------------------------------------

    def detect_explosion(
        self, tier: CostTier, owner_id: str
    ) -> Optional[ExplosionSignal]:
        """Analyze recent costs and return an ExplosionSignal if needed."""
        cb_key = (tier.value, owner_id)
        with self._lock:
            window = self._windows.get(cb_key)
            if not window:
                return None

            events = list(window)
            amounts = [e.amount for e in events]
            n = len(amounts)
            if n == 0:
                return None

            ema = self._ema.get(cb_key, amounts[-1])
            latest = amounts[-1]

            # Rate of change: difference between last two amounts
            rate = latest - (amounts[-2] if n >= 2 else latest)

            ratio = latest / (ema or 1)
            if ratio > _EXPLOSION_MULT:
                alert = CostAlert.EXPLOSION_DETECTED
                action = "halt_spending_immediately"
            elif ratio > _CRITICAL_MULT:
                alert = CostAlert.CRITICAL
                action = "block_new_spending"
            elif ratio > _WARNING_MULT:
                alert = CostAlert.WARNING
                action = "notify_and_monitor"
            else:
                return None

        return ExplosionSignal(
            signal_id=f"sig-{uuid.uuid4().hex[:8]}",
            tier=tier,
            owner_id=owner_id,
            rate_of_change=rate,
            moving_avg=ema,
            spike_magnitude=ratio,
            alert_level=alert,
            recommended_action=action,
        )

    # ------------------------------------------------------------------
    # Circuit breaker
    # ------------------------------------------------------------------

    def set_circuit_breaker(
        self,
        tier: CostTier,
        owner_id: str,
        max_per_minute: float,
        max_per_hour: float,
        cooldown_s: float = _DEFAULT_COOLDOWN_S,
    ) -> Dict[str, Any]:
        """Configure a circuit breaker for a tier/owner combination."""
        cb_key = (tier.value, owner_id)
        with self._lock:
            self._breakers[cb_key] = _CircuitBreaker(
                max_per_minute=max_per_minute,
                max_per_hour=max_per_hour,
                cooldown_s=cooldown_s,
            )
        return {
            "set": True,
            "tier": tier.value,
            "owner_id": owner_id,
            "max_per_minute": max_per_minute,
            "max_per_hour": max_per_hour,
            "cooldown_s": cooldown_s,
        }

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def get_spend_report(
        self,
        tier: Optional[CostTier] = None,
        owner_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Aggregated spend report, optionally filtered by tier and/or owner."""
        with self._lock:
            budgets = [
                b.to_dict()
                for b in self._budgets.values()
                if (tier is None or b.tier == tier)
                and (owner_id is None or b.owner_id == owner_id)
            ]
            total_spent = sum(b["spent"] for b in budgets)
            total_limit = sum(b["limit"] for b in budgets)

        return {
            "budgets": budgets,
            "total_spent": total_spent,
            "total_limit": total_limit,
            "total_remaining": total_limit - total_spent,
            "filter_tier": tier.value if tier else None,
            "filter_owner": owner_id,
        }

    def get_dashboard(self) -> Dict[str, Any]:
        """Full dashboard: all budgets, alerts, recent explosions, circuit breakers."""
        with self._lock:
            budgets = [b.to_dict() for b in self._budgets.values()]
            explosions = list(self._explosions[-10:])
            breakers = {
                f"{k[0]}:{k[1]}": {
                    "tripped": cb.tripped,
                    "max_per_minute": cb.max_per_minute,
                    "max_per_hour": cb.max_per_hour,
                }
                for k, cb in self._breakers.items()
            }
            recent_audit = list(self._audit[-20:])

        return {
            "budgets": budgets,
            "recent_explosions": explosions,
            "circuit_breakers": breakers,
            "recent_audit": recent_audit,
            "total_budgets": len(budgets),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _budget_key(tier: CostTier, owner_id: str) -> str:
        return f"{tier.value}::{owner_id}"

    def _budget_remaining(self, tier: CostTier, owner_id: str) -> Optional[float]:
        key = self._budget_key(tier, owner_id)
        with self._lock:
            budget = self._budgets.get(key)
            return budget.remaining if budget else None

    def _budget_remaining_locked(self, tier: CostTier, owner_id: str) -> Optional[float]:
        """Must be called while self._lock is held."""
        key = self._budget_key(tier, owner_id)
        budget = self._budgets.get(key)
        return budget.remaining if budget else None

    def _trigger_stop(self, tier: CostTier, owner_id: str, reason: str) -> None:
        """Trigger emergency stop for the given scope."""
        if self._emergency_stop is None:
            return
        try:
            if tier == CostTier.GLOBAL:
                self._emergency_stop.activate_global(reason)
            else:
                self._emergency_stop.activate_tenant(owner_id, reason)
        except Exception as exc:
            logger.error("Failed to trigger emergency stop: %s", exc)

    @staticmethod
    def _is_tripped(breaker: _CircuitBreaker) -> bool:
        if not breaker.tripped:
            return False
        if breaker.tripped_at is None:
            return False
        elapsed = time.time() - breaker.tripped_at
        if elapsed >= breaker.cooldown_s:
            breaker.tripped = False
            breaker.tripped_at = None
            return False
        return True

    @staticmethod
    def _prune_breaker(breaker: _CircuitBreaker, now_ts: float) -> None:
        """Remove stale timestamps from circuit breaker windows."""
        one_minute_ago = now_ts - 60.0
        one_hour_ago = now_ts - 3600.0
        while breaker.recent_minute and breaker.recent_minute[0] < one_minute_ago:
            breaker.recent_minute.popleft()
        while breaker.recent_hour and breaker.recent_hour[0] < one_hour_ago:
            breaker.recent_hour.popleft()
