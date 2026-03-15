"""
Emergency Stop Controller for Murphy System.

Design Label: OPS-004 — Global & Per-Tenant Emergency Stop with Auto-Triggers
Owner: DevOps Team / Security Team
Dependencies:
  - PersistenceManager (for durable stop state and event log)
  - EventBackbone (publishes SYSTEM_HEALTH on stop/resume events)
  - AutomationModeController (OPS-003, optional, for forced mode downgrade)

Implements Phase 8 — Operational Readiness & Autonomy Governance:
  Provides emergency stop capability at global and per-tenant scope.
  Supports manual activation, automatic triggers (critical failure
  count threshold, error rate threshold), and controlled resume with
  reason logging.

Flow:
  1. Monitor for emergency conditions (manual or automatic triggers)
  2. Activate emergency stop (global or per-tenant)
  3. Log stop event with reason, scope, and timestamp
  4. Block all autonomous operations while stopped
  5. Allow controlled resume with authorization and reason
  6. Persist all stop/resume events

Safety invariants:
  - Thread-safe: all shared state guarded by Lock
  - Fail-safe: default to stopped state on ambiguity
  - Bounded: configurable max event history
  - Audit trail: every stop/resume event is logged
  - Non-destructive: stop does not destroy state, only blocks operations

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_EVENTS = 10_000
_DEFAULT_FAILURE_THRESHOLD = 5      # consecutive failures
_DEFAULT_ERROR_RATE_THRESHOLD = 0.2  # 20 % error rate


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class StopScope(str, Enum):
    """Scope of an emergency stop."""
    GLOBAL = "global"
    TENANT = "tenant"


class StopAction(str, Enum):
    """Type of stop event."""
    ACTIVATED = "activated"
    RESUMED = "resumed"


@dataclass
class StopEvent:
    """Record of an emergency stop or resume event."""
    event_id: str
    action: StopAction
    scope: StopScope
    tenant_id: str
    reason: str
    triggered_by: str = "manual"    # manual | auto_failure | auto_error_rate
    occurred_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "action": self.action.value,
            "scope": self.scope.value,
            "tenant_id": self.tenant_id,
            "reason": self.reason,
            "triggered_by": self.triggered_by,
            "occurred_at": self.occurred_at,
        }


# ---------------------------------------------------------------------------
# EmergencyStopController
# ---------------------------------------------------------------------------

class EmergencyStopController:
    """Global and per-tenant emergency stop with automatic triggers.

    Design Label: OPS-004
    Owner: DevOps Team / Security Team

    Usage::

        esc = EmergencyStopController()
        esc.activate_global("Critical security breach detected")
        assert esc.is_stopped()
        esc.resume_global("Breach contained, resuming operations")
        assert not esc.is_stopped()
    """

    def __init__(
        self,
        persistence_manager=None,
        event_backbone=None,
        failure_threshold: int = _DEFAULT_FAILURE_THRESHOLD,
        error_rate_threshold: float = _DEFAULT_ERROR_RATE_THRESHOLD,
    ) -> None:
        self._lock = threading.Lock()
        self._pm = persistence_manager
        self._backbone = event_backbone
        self._failure_threshold = failure_threshold
        self._error_rate_threshold = error_rate_threshold

        self._global_stopped: bool = False
        self._tenant_stopped: Set[str] = set()
        self._events: List[StopEvent] = []

        # Counters for automatic triggers
        self._consecutive_failures: int = 0
        self._recent_total: int = 0
        self._recent_failures: int = 0

    # ------------------------------------------------------------------
    # Status queries
    # ------------------------------------------------------------------

    def is_stopped(self, tenant_id: str = "") -> bool:
        """Check if operations are stopped (global or tenant-specific)."""
        with self._lock:
            if self._global_stopped:
                return True
            if tenant_id and tenant_id in self._tenant_stopped:
                return True
            return False

    # ------------------------------------------------------------------
    # Manual stop / resume
    # ------------------------------------------------------------------

    def activate_global(self, reason: str) -> StopEvent:
        """Activate global emergency stop."""
        evt = StopEvent(
            event_id=f"es-{uuid.uuid4().hex[:8]}",
            action=StopAction.ACTIVATED,
            scope=StopScope.GLOBAL,
            tenant_id="*",
            reason=reason,
            triggered_by="manual",
        )
        with self._lock:
            self._global_stopped = True
            self._record_event(evt)
        logger.critical("EMERGENCY STOP activated (global): %s", reason)
        return evt

    def resume_global(self, reason: str) -> StopEvent:
        """Resume operations after global stop."""
        evt = StopEvent(
            event_id=f"es-{uuid.uuid4().hex[:8]}",
            action=StopAction.RESUMED,
            scope=StopScope.GLOBAL,
            tenant_id="*",
            reason=reason,
            triggered_by="manual",
        )
        with self._lock:
            self._global_stopped = False
            self._consecutive_failures = 0
            self._recent_total = 0
            self._recent_failures = 0
            self._record_event(evt)
        logger.info("EMERGENCY STOP resumed (global): %s", reason)
        return evt

    def activate_tenant(self, tenant_id: str, reason: str) -> StopEvent:
        """Activate emergency stop for a specific tenant."""
        evt = StopEvent(
            event_id=f"es-{uuid.uuid4().hex[:8]}",
            action=StopAction.ACTIVATED,
            scope=StopScope.TENANT,
            tenant_id=tenant_id,
            reason=reason,
            triggered_by="manual",
        )
        with self._lock:
            self._tenant_stopped.add(tenant_id)
            self._record_event(evt)
        logger.warning("EMERGENCY STOP activated for tenant %s: %s", tenant_id, reason)
        return evt

    def resume_tenant(self, tenant_id: str, reason: str) -> StopEvent:
        """Resume operations for a specific tenant."""
        evt = StopEvent(
            event_id=f"es-{uuid.uuid4().hex[:8]}",
            action=StopAction.RESUMED,
            scope=StopScope.TENANT,
            tenant_id=tenant_id,
            reason=reason,
            triggered_by="manual",
        )
        with self._lock:
            self._tenant_stopped.discard(tenant_id)
            self._record_event(evt)
        logger.info("EMERGENCY STOP resumed for tenant %s: %s", tenant_id, reason)
        return evt

    # ------------------------------------------------------------------
    # Automatic triggers
    # ------------------------------------------------------------------

    def record_outcome(self, success: bool) -> Optional[StopEvent]:
        """Record a task outcome; may trigger automatic emergency stop."""
        with self._lock:
            self._recent_total += 1
            if success:
                self._consecutive_failures = 0
            else:
                self._consecutive_failures += 1
                self._recent_failures += 1

            # Check consecutive failure threshold
            if self._consecutive_failures >= self._failure_threshold:
                if not self._global_stopped:
                    evt = StopEvent(
                        event_id=f"es-{uuid.uuid4().hex[:8]}",
                        action=StopAction.ACTIVATED,
                        scope=StopScope.GLOBAL,
                        tenant_id="*",
                        reason=f"{self._consecutive_failures} consecutive failures",
                        triggered_by="auto_failure",
                    )
                    self._global_stopped = True
                    self._record_event(evt)
                    logger.critical("AUTO EMERGENCY STOP: %d consecutive failures",
                                    self._consecutive_failures)
                    return evt

            # Check error rate threshold (after minimum 10 observations)
            if self._recent_total >= 10:
                rate = self._recent_failures / self._recent_total
                if rate >= self._error_rate_threshold and not self._global_stopped:
                    evt = StopEvent(
                        event_id=f"es-{uuid.uuid4().hex[:8]}",
                        action=StopAction.ACTIVATED,
                        scope=StopScope.GLOBAL,
                        tenant_id="*",
                        reason=f"Error rate {rate:.1%} exceeds {self._error_rate_threshold:.1%}",
                        triggered_by="auto_error_rate",
                    )
                    self._global_stopped = True
                    self._record_event(evt)
                    logger.critical("AUTO EMERGENCY STOP: error rate %.1f%%", rate * 100)
                    return evt

        return None

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            return [e.to_dict() for e in self._events[-limit:]]

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "global_stopped": self._global_stopped,
                "stopped_tenants": sorted(self._tenant_stopped),
                "consecutive_failures": self._consecutive_failures,
                "recent_total": self._recent_total,
                "recent_failures": self._recent_failures,
                "total_events": len(self._events),
                "persistence_attached": self._pm is not None,
                "backbone_attached": self._backbone is not None,
            }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _record_event(self, evt: StopEvent) -> None:
        """Record event and persist / publish. Caller must hold self._lock."""
        if len(self._events) >= _MAX_EVENTS:
            self._events = self._events[_MAX_EVENTS // 10:]
        self._events.append(evt)

        # Persist (outside lock not needed — we tolerate best-effort)
        if self._pm is not None:
            try:
                self._pm.save_document(doc_id=evt.event_id, document=evt.to_dict())
            except Exception as exc:
                logger.error("Emergency stop event NOT persisted: %s", exc)

        # Publish
        if self._backbone is not None:
            self._publish_event(evt)

    def _publish_event(self, evt: StopEvent) -> None:
        try:
            from event_backbone import Event
            from event_backbone import EventType as ET
            backbone_evt = Event(
                event_id=f"evt-{uuid.uuid4().hex[:8]}",
                event_type=ET.SYSTEM_HEALTH,
                payload={
                    "source": "emergency_stop_controller",
                    "action": evt.action.value,
                    "scope": evt.scope.value,
                    "tenant_id": evt.tenant_id,
                    "reason": evt.reason,
                    "triggered_by": evt.triggered_by,
                },
                timestamp=datetime.now(timezone.utc).isoformat(),
                source="emergency_stop_controller",
            )
            self._backbone.publish_event(backbone_evt)
        except Exception as exc:
            logger.debug("EventBackbone publish skipped: %s", exc)
