# Copyright © 2020 Inoni Limited Liability Company
"""
Time Tracking – Invoicing Hooks
================================

Event-driven hook system that fires when time tracking billing events
occur.  Hooks are synchronous by default; the design allows for an
async wrapper to be layered on later.

Copyright 2024 Inoni LLC – BSL-1.1
"""

from __future__ import annotations

import logging
import threading
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# Maximum audit-log entries kept in memory
_MAX_AUDIT_LOG = 10_000


# ---------------------------------------------------------------------------
# Event types
# ---------------------------------------------------------------------------


class TimeTrackingEvent(str, Enum):
    """Pre-defined billing/time-tracking event types."""

    ENTRY_APPROVED = "entry_approved"
    ENTRY_INVOICED = "entry_invoiced"
    INVOICE_GENERATED = "invoice_generated"
    BILLABLE_THRESHOLD_REACHED = "billable_threshold_reached"
    WEEKLY_SUMMARY_READY = "weekly_summary_ready"
    RATE_CHANGED = "rate_changed"


# ---------------------------------------------------------------------------
# Hook manager
# ---------------------------------------------------------------------------


class InvoicingHookManager:
    """Register callbacks for :class:`TimeTrackingEvent` and emit them.

    Usage::

        manager = InvoicingHookManager()

        def my_hook(event_type, payload):
            print(event_type, payload)

        manager.register_hook(TimeTrackingEvent.ENTRY_APPROVED, my_hook)
        manager.emit(TimeTrackingEvent.ENTRY_APPROVED, {"entry_id": "abc"})
    """

    def __init__(
        self,
        auto_invoice_threshold_hours: float = 40.0,
        billing_service=None,
    ) -> None:
        self._lock = threading.Lock()
        # {event_type: [callback, ...]}
        self._hooks: Dict[str, List[Callable[[str, Dict[str, Any]], None]]] = {}
        self._audit_log: List[Dict[str, Any]] = []
        self._auto_invoice_threshold = auto_invoice_threshold_hours
        self._billing_service = billing_service

        # Register built-in hooks
        self._register_builtin_hooks()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register_hook(
        self,
        event_type: TimeTrackingEvent,
        callback: Callable[[str, Dict[str, Any]], None],
    ) -> None:
        """Register *callback* for *event_type*."""
        key = event_type.value if isinstance(event_type, TimeTrackingEvent) else str(event_type)
        with self._lock:
            self._hooks.setdefault(key, [])
            if callback not in self._hooks[key]:
                self._hooks[key].append(callback)

    def unregister_hook(
        self,
        event_type: TimeTrackingEvent,
        callback: Callable[[str, Dict[str, Any]], None],
    ) -> None:
        """Remove *callback* from *event_type*."""
        key = event_type.value if isinstance(event_type, TimeTrackingEvent) else str(event_type)
        with self._lock:
            hooks = self._hooks.get(key, [])
            if callback in hooks:
                hooks.remove(callback)

    def emit(
        self, event_type: TimeTrackingEvent, payload: Dict[str, Any]
    ) -> int:
        """Fire all callbacks registered for *event_type*.

        Returns the number of callbacks invoked.
        """
        key = event_type.value if isinstance(event_type, TimeTrackingEvent) else str(event_type)
        with self._lock:
            callbacks = list(self._hooks.get(key, []))

        count = 0
        for cb in callbacks:
            try:
                cb(key, payload)
                count += 1
            except Exception as exc:
                logger.exception(
                    "Hook callback %r raised an exception for event %r",
                    cb,
                    key,
                )
        return count

    def get_audit_log(
        self, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Return the most-recent audit log entries."""
        with self._lock:
            return list(self._audit_log[-limit:])

    def clear_audit_log(self) -> None:
        with self._lock:
            self._audit_log.clear()

    # ------------------------------------------------------------------
    # Built-in hooks
    # ------------------------------------------------------------------

    def _register_builtin_hooks(self) -> None:
        for event in TimeTrackingEvent:
            self.register_hook(event, self.audit_log_hook)

        self.register_hook(TimeTrackingEvent.ENTRY_APPROVED, self.notification_hook)
        self.register_hook(TimeTrackingEvent.ENTRY_INVOICED, self.notification_hook)
        self.register_hook(
            TimeTrackingEvent.BILLABLE_THRESHOLD_REACHED,
            self.auto_invoice_hook,
        )

    def auto_invoice_hook(
        self, event_type: str, payload: Dict[str, Any]
    ) -> None:
        """Auto-generate an invoice draft when unbilled hours exceed threshold."""
        client_id = payload.get("client_id", "")
        unbilled_hours = payload.get("unbilled_hours", 0.0)
        logger.info(
            "auto_invoice_hook: client=%r unbilled_hours=%.2f threshold=%.2f",
            client_id,
            unbilled_hours,
            self._auto_invoice_threshold,
        )
        if unbilled_hours >= self._auto_invoice_threshold and self._billing_service is not None:
            try:
                entry_ids: List[str] = payload.get("entry_ids", [])
                if entry_ids:
                    self._billing_service.generate_invoice_from_entries(
                        client_id=client_id,
                        entry_ids=entry_ids,
                    )
                    logger.info(
                        "auto_invoice_hook: generated draft invoice for client=%r",
                        client_id,
                    )
            except Exception as exc:
                logger.exception(
                    "auto_invoice_hook: failed to generate invoice for client=%r",
                    client_id,
                )

    def notification_hook(
        self, event_type: str, payload: Dict[str, Any]
    ) -> None:
        """Log a notification when entries are approved or invoiced."""
        logger.info("TimeTracking notification [%s]: %s", event_type, payload)

    def audit_log_hook(
        self, event_type: str, payload: Dict[str, Any]
    ) -> None:
        """Record all billing events to the in-memory audit log."""
        from datetime import datetime, timezone

        entry: Dict[str, Any] = {
            "event_type": event_type,
            "payload": dict(payload),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        with self._lock:
            if len(self._audit_log) >= _MAX_AUDIT_LOG:
                # Evict oldest 10 % to avoid unbounded growth
                del self._audit_log[: _MAX_AUDIT_LOG // 10]
            self._audit_log.append(entry)
