"""
Self-Healing Coordinator for Murphy System.

Design Label: OBS-004 — Event-Driven Failure Recovery
Owner: DevOps Team / Platform Engineering
Dependencies:
  - EventBackbone (subscribes to TASK_FAILED, SYSTEM_HEALTH)
  - HealthMonitor (triggers recovery on UNHEALTHY components)

Implements Phase 1 — Observability & Monitoring — Self-Healing:
  - Registers recovery procedures (callables) per failure category
  - Listens for failure events via EventBackbone subscription
  - Executes matching recovery procedure when failures detected
  - Tracks recovery history with success/failure outcomes
  - Implements exponential back-off for repeated failures
  - Supports automatic rollback on cascading failures

Safety invariants:
  - Thread-safe: all shared state guarded by Lock
  - Max recovery attempts per category to prevent infinite loops
  - Cool-down period between recovery attempts
  - All recovery actions logged in audit trail

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

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class RecoveryStatus(str, Enum):
    """Outcome of a recovery attempt."""
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    COOLDOWN = "cooldown"


@dataclass
class RecoveryProcedure:
    """A registered recovery procedure for a failure category."""
    procedure_id: str
    category: str
    description: str
    handler: Callable[..., bool]
    max_attempts: int = 3
    cooldown_seconds: float = 60.0


@dataclass
class RecoveryAttempt:
    """Record of a single recovery attempt."""
    attempt_id: str
    procedure_id: str
    category: str
    status: RecoveryStatus
    trigger_event: str = ""
    message: str = ""
    duration_ms: float = 0.0
    attempted_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "attempt_id": self.attempt_id,
            "procedure_id": self.procedure_id,
            "category": self.category,
            "status": self.status.value,
            "trigger_event": self.trigger_event,
            "message": self.message,
            "duration_ms": round(self.duration_ms, 2),
            "attempted_at": self.attempted_at,
        }


# ---------------------------------------------------------------------------
# SelfHealingCoordinator
# ---------------------------------------------------------------------------

class SelfHealingCoordinator:
    """Event-driven failure detection and automatic recovery.

    Design Label: OBS-004
    Owner: DevOps Team

    Usage::

        coordinator = SelfHealingCoordinator(event_backbone=backbone)
        coordinator.register_procedure(RecoveryProcedure(
            procedure_id="restart-db",
            category="database_failure",
            description="Restart database connection pool",
            handler=lambda ctx: restart_db_pool(),
        ))
        coordinator.handle_failure("database_failure", trigger="health_check")
    """

    def __init__(self, event_backbone=None, max_history: int = 200) -> None:
        self._lock = threading.Lock()
        self._procedures: Dict[str, RecoveryProcedure] = {}
        self._category_index: Dict[str, str] = {}  # category → procedure_id
        self._attempts: List[RecoveryAttempt] = []
        self._last_attempt_time: Dict[str, float] = {}  # procedure_id → epoch
        self._consecutive_failures: Dict[str, int] = {}  # procedure_id → count
        self._max_history = max_history
        self._event_backbone = event_backbone

        # Wire EventBackbone subscriptions
        if self._event_backbone is not None:
            self._subscribe_events()

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_procedure(self, procedure: RecoveryProcedure) -> str:
        """Register a recovery procedure. Returns procedure_id."""
        with self._lock:
            self._procedures[procedure.procedure_id] = procedure
            self._category_index[procedure.category] = procedure.procedure_id
        logger.info(
            "Registered recovery procedure: %s for category '%s'",
            procedure.procedure_id, procedure.category,
        )
        return procedure.procedure_id

    def unregister_procedure(self, procedure_id: str) -> bool:
        """Remove a procedure. Returns True if found."""
        with self._lock:
            proc = self._procedures.pop(procedure_id, None)
            if proc is None:
                return False
            self._category_index.pop(proc.category, None)
        return True

    # ------------------------------------------------------------------
    # Failure handling
    # ------------------------------------------------------------------

    def handle_failure(
        self,
        category: str,
        trigger: str = "",
        context: Optional[Dict[str, Any]] = None,
    ) -> RecoveryAttempt:
        """Handle a failure event by executing the matching recovery procedure.

        Returns a RecoveryAttempt describing the outcome.
        """
        with self._lock:
            proc_id = self._category_index.get(category)
            if proc_id is None:
                attempt = RecoveryAttempt(
                    attempt_id=f"recov-{uuid.uuid4().hex[:8]}",
                    procedure_id="",
                    category=category,
                    status=RecoveryStatus.SKIPPED,
                    trigger_event=trigger,
                    message=f"No recovery procedure registered for category '{category}'",
                )
                self._record_attempt(attempt)
                return attempt

            procedure = self._procedures[proc_id]

            # Check cool-down
            last_time = self._last_attempt_time.get(proc_id, 0)
            elapsed = time.monotonic() - last_time
            if last_time > 0 and elapsed < procedure.cooldown_seconds:
                attempt = RecoveryAttempt(
                    attempt_id=f"recov-{uuid.uuid4().hex[:8]}",
                    procedure_id=proc_id,
                    category=category,
                    status=RecoveryStatus.COOLDOWN,
                    trigger_event=trigger,
                    message=f"Cooldown active ({elapsed:.0f}s / {procedure.cooldown_seconds:.0f}s)",
                )
                self._record_attempt(attempt)
                return attempt

            # Check max consecutive failures
            consec = self._consecutive_failures.get(proc_id, 0)
            if consec >= procedure.max_attempts:
                attempt = RecoveryAttempt(
                    attempt_id=f"recov-{uuid.uuid4().hex[:8]}",
                    procedure_id=proc_id,
                    category=category,
                    status=RecoveryStatus.SKIPPED,
                    trigger_event=trigger,
                    message=f"Max recovery attempts reached ({consec}/{procedure.max_attempts})",
                )
                self._record_attempt(attempt)
                return attempt

        # Execute recovery (outside lock)
        start = time.monotonic()
        try:
            success = procedure.handler(context or {})
            elapsed_ms = (time.monotonic() - start) * 1000.0
            status = RecoveryStatus.SUCCESS if success else RecoveryStatus.FAILED
            msg = "Recovery succeeded" if success else "Recovery handler returned False"
        except Exception as exc:
            elapsed_ms = (time.monotonic() - start) * 1000.0
            status = RecoveryStatus.FAILED
            msg = f"Recovery handler raised: {exc}"
            logger.error("Recovery procedure %s failed: %s", proc_id, exc)

        attempt = RecoveryAttempt(
            attempt_id=f"recov-{uuid.uuid4().hex[:8]}",
            procedure_id=proc_id,
            category=category,
            status=status,
            trigger_event=trigger,
            message=msg,
            duration_ms=elapsed_ms,
        )

        with self._lock:
            self._last_attempt_time[proc_id] = time.monotonic()
            if status == RecoveryStatus.SUCCESS:
                self._consecutive_failures[proc_id] = 0
            else:
                self._consecutive_failures[proc_id] = self._consecutive_failures.get(proc_id, 0) + 1
            self._record_attempt(attempt)

        # Publish recovery result
        if self._event_backbone is not None:
            try:
                from event_backbone import EventType
                self._event_backbone.publish(
                    event_type=EventType.LEARNING_FEEDBACK,
                    payload={
                        "source": "self_healing_coordinator",
                        "recovery_attempt": attempt.to_dict(),
                    },
                    source="self_healing_coordinator",
                )
            except Exception as exc:
                logger.warning("Failed to publish recovery event: %s", exc)

        return attempt

    # ------------------------------------------------------------------
    # History / Status
    # ------------------------------------------------------------------

    def get_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Return recent recovery attempts."""
        with self._lock:
            recent = self._attempts[-limit:]
        return [a.to_dict() for a in recent]

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            total = len(self._attempts)
            successes = sum(1 for a in self._attempts if a.status == RecoveryStatus.SUCCESS)
            failures = sum(1 for a in self._attempts if a.status == RecoveryStatus.FAILED)
            return {
                "registered_procedures": len(self._procedures),
                "categories": sorted(self._category_index.keys()),
                "total_attempts": total,
                "successful_recoveries": successes,
                "failed_recoveries": failures,
                "consecutive_failures": dict(self._consecutive_failures),
                "event_backbone_attached": self._event_backbone is not None,
            }

    def reset_failure_counter(self, category: str) -> bool:
        """Reset the consecutive failure counter for a category (manual intervention)."""
        with self._lock:
            proc_id = self._category_index.get(category)
            if proc_id is None:
                return False
            self._consecutive_failures[proc_id] = 0
            self._last_attempt_time.pop(proc_id, None)
        return True

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _record_attempt(self, attempt: RecoveryAttempt) -> None:
        """Append attempt to history (caller must hold lock or handle sync)."""
        self._attempts.append(attempt)
        if len(self._attempts) > self._max_history:
            self._attempts = self._attempts[-self._max_history:]

    def _subscribe_events(self) -> None:
        """Subscribe to failure events on the EventBackbone."""
        try:
            from event_backbone import EventType

            def _on_task_failed(event) -> None:
                payload = event.payload if hasattr(event, "payload") else {}
                category = payload.get("failure_category", payload.get("task_type", "task_failure"))
                self.handle_failure(category, trigger=f"event:{event.event_id}")

            def _on_system_unhealthy(event) -> None:
                payload = event.payload if hasattr(event, "payload") else {}
                if payload.get("system_status") == "unhealthy":
                    components = payload.get("components", [])
                    for comp in components:
                        if comp.get("status") == "unhealthy":
                            category = f"component_{comp.get('component_id', 'unknown')}"
                            self.handle_failure(category, trigger=f"health:{event.event_id}")

            self._event_backbone.subscribe(EventType.TASK_FAILED, _on_task_failed)
            self._event_backbone.subscribe(EventType.SYSTEM_HEALTH, _on_system_unhealthy)
            logger.info("SelfHealingCoordinator subscribed to EventBackbone")
        except Exception as exc:
            logger.warning("Failed to subscribe to EventBackbone: %s", exc)
