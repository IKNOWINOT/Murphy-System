"""
Heartbeat Liveness Protocol for the Murphy System.

Design Label: OBS-005 — Continuous Bot Health Monitoring
Owner: Platform Engineering / DevOps Team

Implements a Kubernetes-inspired reconciliation loop (observe → compare →
reconcile) adapted for Murphy's bot ecosystem:

  - HeartbeatPolicy  — per-bot configuration (interval, thresholds, strategy)
  - BotHealthState   — state machine: HEALTHY → DEGRADED → UNRESPONSIVE →
                       RECOVERING → TERMINATED
  - BotHeartbeat     — per-bot liveness record
  - HeartbeatMonitor — orchestrates polling, state transitions, and recovery

Safety invariants:
  - Thread-safe: all shared state guarded by threading.Lock
  - Bounded recovery iterations (max_recovery_attempts per bot)
  - Circuit breaker prevents cascading recovery storms
  - Full audit trail via EventBackbone
  - Never modifies source files at runtime

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

try:
    from thread_safe_operations import CircuitBreaker, capped_append
except ImportError:
    class CircuitBreaker:
        """Minimal fallback CircuitBreaker (pass-through, no tripping)."""
        def __init__(self, *args, **kwargs):
            pass
        def call(self, fn, *args, **kwargs):
            return fn(*args, **kwargs)
        @property
        def state(self):
            return "closed"
        def reset(self) -> None:
            pass
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class BotHealthState(Enum):
    """Liveness states for a monitored bot."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNRESPONSIVE = "unresponsive"
    RECOVERING = "recovering"
    TERMINATED = "terminated"


@dataclass
class HeartbeatPolicy:
    """Per-bot heartbeat configuration.

    Attributes:
        interval_sec: Expected time between heartbeats (seconds).
        max_missed_beats: Beats missed before transitioning to UNRESPONSIVE.
        recovery_strategy: Identifier passed to SelfHealingCoordinator.
        max_concurrent_runs: Maximum simultaneous recovery attempts.
        max_recovery_attempts: Hard cap on lifetime recovery attempts per bot.
        circuit_breaker_threshold: Consecutive failures before opening breaker.
        circuit_breaker_timeout: Seconds before half-open probe after trip.
    """
    interval_sec: float = 30.0
    max_missed_beats: int = 3
    recovery_strategy: str = "bot_unresponsive"
    max_concurrent_runs: int = 1
    max_recovery_attempts: int = 5
    circuit_breaker_threshold: int = 3
    circuit_breaker_timeout: float = 60.0


@dataclass
class BotHeartbeat:
    """Liveness record for a single monitored bot."""
    bot_id: str
    policy: HeartbeatPolicy
    last_seen: float = field(default_factory=time.monotonic)
    state: BotHealthState = BotHealthState.HEALTHY
    consecutive_misses: int = 0
    recovery_attempts: int = 0
    registered_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bot_id": self.bot_id,
            "state": self.state.value,
            "consecutive_misses": self.consecutive_misses,
            "recovery_attempts": self.recovery_attempts,
            "last_seen_ago_sec": round(time.monotonic() - self.last_seen, 2),
            "registered_at": self.registered_at,
            "policy": {
                "interval_sec": self.policy.interval_sec,
                "max_missed_beats": self.policy.max_missed_beats,
                "recovery_strategy": self.policy.recovery_strategy,
                "max_recovery_attempts": self.policy.max_recovery_attempts,
            },
        }


# ---------------------------------------------------------------------------
# HeartbeatMonitor
# ---------------------------------------------------------------------------

class HeartbeatMonitor:
    """Periodically reconciles bot liveness and triggers recovery.

    Design Label: OBS-005
    Owner: Platform Engineering

    Usage::

        monitor = HeartbeatMonitor(
            event_backbone=backbone,
            healing_coordinator=coordinator,
        )
        monitor.register_bot("bot-123", HeartbeatPolicy(interval_sec=10))
        monitor.record_heartbeat("bot-123")
        monitor.tick()  # call from a scheduler loop
        dashboard = monitor.get_health_dashboard()
    """

    def __init__(
        self,
        event_backbone=None,
        healing_coordinator=None,
        max_tick_history: int = 500,
    ) -> None:
        self._lock = threading.Lock()
        self._heartbeats: Dict[str, BotHeartbeat] = {}
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._active_recoveries: Dict[str, int] = {}  # bot_id → active count
        self._tick_history: List[Dict[str, Any]] = []
        self._max_tick_history = max_tick_history
        self._ticks_run = 0
        self._event_backbone = event_backbone
        self._healing_coordinator = healing_coordinator

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_bot(
        self,
        bot_id: str,
        policy: Optional[HeartbeatPolicy] = None,
    ) -> None:
        """Register a bot for heartbeat monitoring.

        Args:
            bot_id: Unique identifier for the bot.
            policy: Heartbeat configuration; uses defaults if omitted.
        """
        effective_policy = policy or HeartbeatPolicy()
        with self._lock:
            if bot_id in self._heartbeats:
                logger.debug("Bot %s already registered; skipping.", bot_id)
                return
            self._heartbeats[bot_id] = BotHeartbeat(
                bot_id=bot_id,
                policy=effective_policy,
            )
            self._circuit_breakers[bot_id] = CircuitBreaker(
                failure_threshold=effective_policy.circuit_breaker_threshold,
                recovery_timeout=effective_policy.circuit_breaker_timeout,
            )
        logger.info("HeartbeatMonitor: registered bot %s", bot_id)

    def deregister_bot(self, bot_id: str) -> bool:
        """Remove a bot from monitoring. Returns True if found."""
        with self._lock:
            if bot_id not in self._heartbeats:
                return False
            del self._heartbeats[bot_id]
            self._circuit_breakers.pop(bot_id, None)
        logger.info("HeartbeatMonitor: deregistered bot %s", bot_id)
        return True

    # ------------------------------------------------------------------
    # Heartbeat recording
    # ------------------------------------------------------------------

    def record_heartbeat(self, bot_id: str) -> bool:
        """Called by a bot to report liveness.

        Resets consecutive_misses and transitions back to HEALTHY if the
        bot was in DEGRADED or RECOVERING state.

        Returns:
            True if the bot is registered, False otherwise.
        """
        with self._lock:
            hb = self._heartbeats.get(bot_id)
            if hb is None:
                logger.warning(
                    "record_heartbeat: unknown bot %s — ignoring.", bot_id
                )
                return False
            hb.last_seen = time.monotonic()
            hb.consecutive_misses = 0
            previous_state = hb.state
            if hb.state not in (BotHealthState.TERMINATED,):
                hb.state = BotHealthState.HEALTHY
                cb = self._circuit_breakers.get(bot_id)
                if cb is not None:
                    cb.reset()

        if previous_state != BotHealthState.HEALTHY:
            self._publish(
                "BOT_HEARTBEAT_OK",
                {
                    "bot_id": bot_id,
                    "previous_state": previous_state.value,
                    "recovered_from": previous_state.value,
                },
            )
        return True

    # ------------------------------------------------------------------
    # Reconciliation tick
    # ------------------------------------------------------------------

    def tick(self) -> Dict[str, Any]:
        """One iteration of the observe → compare → reconcile loop.

        Checks all registered bots, transitions states based on missed
        heartbeats, and triggers recovery for unresponsive bots.

        Returns:
            A summary dict with counts of bots in each state.
        """
        with self._lock:
            snapshot = list(self._heartbeats.items())
            self._ticks_run += 1

        now = time.monotonic()
        summary: Dict[str, int] = {s.value: 0 for s in BotHealthState}
        transitions = []

        for bot_id, hb in snapshot:
            elapsed = now - hb.last_seen
            threshold = hb.policy.interval_sec

            with self._lock:
                current_state = hb.state

            if current_state == BotHealthState.TERMINATED:
                summary[BotHealthState.TERMINATED.value] += 1
                continue

            if elapsed <= threshold:
                # Beat arrived on time
                with self._lock:
                    hb.consecutive_misses = 0
                    if hb.state not in (
                        BotHealthState.RECOVERING,
                        BotHealthState.TERMINATED,
                    ):
                        hb.state = BotHealthState.HEALTHY
                summary[BotHealthState.HEALTHY.value] += 1
                self._publish(
                    "BOT_HEARTBEAT_OK",
                    {"bot_id": bot_id, "elapsed_sec": round(elapsed, 2)},
                )
                continue

            # Beat missed
            with self._lock:
                hb.consecutive_misses += 1
                misses = hb.consecutive_misses
                policy = hb.policy

            self._publish(
                "BOT_HEARTBEAT_MISSED",
                {
                    "bot_id": bot_id,
                    "consecutive_misses": misses,
                    "elapsed_sec": round(elapsed, 2),
                },
            )

            if misses < policy.max_missed_beats:
                # Transition to DEGRADED
                with self._lock:
                    if hb.state not in (
                        BotHealthState.RECOVERING,
                        BotHealthState.TERMINATED,
                    ):
                        hb.state = BotHealthState.DEGRADED
                summary[BotHealthState.DEGRADED.value] += 1
                transitions.append((bot_id, BotHealthState.DEGRADED))
            else:
                # Unresponsive — attempt recovery
                with self._lock:
                    if hb.state not in (
                        BotHealthState.RECOVERING,
                        BotHealthState.TERMINATED,
                    ):
                        hb.state = BotHealthState.UNRESPONSIVE
                summary[BotHealthState.UNRESPONSIVE.value] += 1
                transitions.append((bot_id, BotHealthState.UNRESPONSIVE))
                self._attempt_recovery(bot_id, hb)

        tick_record = {
            "tick_id": f"tick-{uuid.uuid4().hex[:8]}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "summary": summary,
            "transitions": [(b, s.value) for b, s in transitions],
        }
        with self._lock:
            capped_append(self._tick_history, tick_record, self._max_tick_history)

        return summary

    # ------------------------------------------------------------------
    # Recovery
    # ------------------------------------------------------------------

    def _attempt_recovery(self, bot_id: str, hb: BotHeartbeat) -> None:
        """Trigger recovery for an unresponsive bot via SelfHealingCoordinator.

        Guards:
          - Circuit breaker: if tripped, recovery is skipped.
          - max_recovery_attempts: hard cap per-bot.
        """
        with self._lock:
            policy = hb.policy
            attempts = hb.recovery_attempts
            cb = self._circuit_breakers.get(bot_id)

        if attempts >= policy.max_recovery_attempts:
            logger.warning(
                "Bot %s: max recovery attempts (%d) reached — marking TERMINATED.",
                bot_id,
                policy.max_recovery_attempts,
            )
            with self._lock:
                hb.state = BotHealthState.TERMINATED
            return

        if cb is not None and cb.get_state() == "OPEN":
            logger.warning(
                "Bot %s: circuit breaker OPEN — skipping recovery.", bot_id
            )
            return

        with self._lock:
            active = self._active_recoveries.get(bot_id, 0)
            if active >= policy.max_concurrent_runs:
                logger.debug(
                    "Bot %s: max_concurrent_runs (%d) reached — skipping recovery.",
                    bot_id,
                    policy.max_concurrent_runs,
                )
                return
            hb.state = BotHealthState.RECOVERING
            hb.recovery_attempts += 1
            self._active_recoveries[bot_id] = active + 1

        self._publish(
            "BOT_HEARTBEAT_RECOVERY_STARTED",
            {
                "bot_id": bot_id,
                "attempt_number": hb.recovery_attempts,
                "recovery_strategy": policy.recovery_strategy,
            },
        )
        logger.info(
            "HeartbeatMonitor: starting recovery for bot %s (attempt %d/%d)",
            bot_id,
            hb.recovery_attempts,
            policy.max_recovery_attempts,
        )

        if self._healing_coordinator is not None:
            self._run_coordinator_recovery(bot_id, hb, policy, cb)
        else:
            # No coordinator wired — mark healthy optimistically
            with self._lock:
                hb.state = BotHealthState.HEALTHY
                hb.consecutive_misses = 0
                self._active_recoveries[bot_id] = max(
                    0, self._active_recoveries.get(bot_id, 1) - 1
                )
            self._publish(
                "BOT_HEARTBEAT_RECOVERED",
                {"bot_id": bot_id, "via": "optimistic_no_coordinator"},
            )

    def _run_coordinator_recovery(
        self,
        bot_id: str,
        hb: BotHeartbeat,
        policy: HeartbeatPolicy,
        cb: Optional[CircuitBreaker],
    ) -> None:
        """Delegate recovery to SelfHealingCoordinator and handle outcome."""
        try:
            self._ensure_recovery_procedure(bot_id, policy)
            attempt = self._healing_coordinator.handle_failure(
                category=policy.recovery_strategy,
                trigger=f"heartbeat_monitor/{bot_id}",
                context={"bot_id": bot_id},
            )
            success = attempt.status.value == "success"
        except Exception as exc:
            logger.error(
                "HeartbeatMonitor: coordinator recovery raised for bot %s: %s",
                bot_id,
                exc,
            )
            success = False

        if success:
            with self._lock:
                hb.state = BotHealthState.HEALTHY
                hb.consecutive_misses = 0
                self._active_recoveries[bot_id] = max(
                    0, self._active_recoveries.get(bot_id, 1) - 1
                )
                if cb is not None:
                    cb.reset()
            self._publish(
                "BOT_HEARTBEAT_RECOVERED",
                {"bot_id": bot_id, "via": "healing_coordinator"},
            )
            logger.info("HeartbeatMonitor: bot %s recovered.", bot_id)
        else:
            with self._lock:
                hb.state = BotHealthState.UNRESPONSIVE
                self._active_recoveries[bot_id] = max(
                    0, self._active_recoveries.get(bot_id, 1) - 1
                )
            if cb is not None:
                cb._on_failure()
                logger.debug(
                    "Circuit breaker recorded failure for bot %s (state=%s).",
                    bot_id,
                    cb.get_state(),
                )
            logger.warning(
                "HeartbeatMonitor: recovery failed for bot %s.", bot_id
            )

    def _ensure_recovery_procedure(
        self, bot_id: str, policy: HeartbeatPolicy
    ) -> None:
        """Register a default recovery procedure if none exists for the strategy."""
        if self._healing_coordinator is None:
            return
        try:
            from self_healing_coordinator import RecoveryProcedure
            status = self._healing_coordinator.get_status()
            if policy.recovery_strategy not in status.get("categories", []):
                proc = RecoveryProcedure(
                    procedure_id=f"hb-recovery-{policy.recovery_strategy}",
                    category=policy.recovery_strategy,
                    description=(
                        f"Auto-registered heartbeat recovery for strategy "
                        f"'{policy.recovery_strategy}'"
                    ),
                    handler=lambda ctx: True,
                    cooldown_seconds=0.0,
                )
                self._healing_coordinator.register_procedure(proc)
        except Exception as exc:
            logger.warning(
                "Could not ensure recovery procedure for %s: %s",
                policy.recovery_strategy,
                exc,
            )

    # ------------------------------------------------------------------
    # Dashboard / Status
    # ------------------------------------------------------------------

    def get_health_dashboard(self) -> Dict[str, Any]:
        """Return current health status of all registered bots."""
        with self._lock:
            bots_snapshot = {
                bot_id: hb.to_dict()
                for bot_id, hb in self._heartbeats.items()
            }
            breakers_snapshot = {
                bot_id: {
                    "state": cb.get_state(),
                    "failure_count": cb.get_failure_count(),
                }
                for bot_id, cb in self._circuit_breakers.items()
            }
            active_recoveries_snapshot = dict(self._active_recoveries)
            ticks = self._ticks_run

        summary: Dict[str, int] = {s.value: 0 for s in BotHealthState}
        for entry in bots_snapshot.values():
            state_val = entry.get("state", BotHealthState.HEALTHY.value)
            if state_val in summary:
                summary[state_val] += 1

        return {
            "total_bots": len(bots_snapshot),
            "ticks_run": ticks,
            "summary": summary,
            "bots": bots_snapshot,
            "circuit_breakers": breakers_snapshot,
            "active_recoveries": active_recoveries_snapshot,
        }

    def get_tick_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Return recent tick records."""
        with self._lock:
            return list(self._tick_history[-limit:])

    # ------------------------------------------------------------------
    # EventBackbone helpers
    # ------------------------------------------------------------------

    def _publish(self, event_name: str, payload: Dict[str, Any]) -> None:
        """Publish a heartbeat lifecycle event to the EventBackbone."""
        if self._event_backbone is None:
            return
        try:
            from event_backbone import EventType
            event_type_map = {
                "BOT_HEARTBEAT_OK": EventType.BOT_HEARTBEAT_OK,
                "BOT_HEARTBEAT_MISSED": EventType.BOT_HEARTBEAT_MISSED,
                "BOT_HEARTBEAT_RECOVERY_STARTED": EventType.BOT_HEARTBEAT_RECOVERY_STARTED,
                "BOT_HEARTBEAT_RECOVERED": EventType.BOT_HEARTBEAT_RECOVERED,
            }
            et = event_type_map.get(event_name)
            if et is None:
                return
            self._event_backbone.publish(
                event_type=et,
                payload=payload,
                source="heartbeat_monitor",
            )
        except Exception as exc:
            logger.warning(
                "HeartbeatMonitor: failed to publish %s: %s", event_name, exc
            )
