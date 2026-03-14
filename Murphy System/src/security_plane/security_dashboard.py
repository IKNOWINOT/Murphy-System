"""Unified Security Dashboard — aggregate events from all security modules."""
# Copyright © 2020 Inoni Limited Liability Company

from __future__ import annotations

import logging
import threading
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

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
# Enumerations
# ---------------------------------------------------------------------------

class SecurityEventType(str, Enum):
    """Security event type (str subclass)."""
    AUTHORIZATION_DENIED = "authorization_denied"
    AUTHORIZATION_GRANTED = "authorization_granted"
    QUOTA_VIOLATION = "quota_violation"
    QUOTA_WARNING = "quota_warning"
    COMMUNICATION_LOOP = "communication_loop"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    IDENTITY_VERIFICATION_FAILED = "identity_verification_failed"
    IDENTITY_REVOKED = "identity_revoked"
    ANOMALY_DETECTED = "anomaly_detected"
    PII_DETECTED = "pii_detected"
    BOT_SUSPENDED = "bot_suspended"


class EscalationLevel(str, Enum):
    """Escalation level (str subclass)."""
    INFO = "info"
    WARNING = "warning"
    ALERT = "alert"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


_ESCALATION_ORDER: Dict[EscalationLevel, int] = {
    EscalationLevel.INFO: 0,
    EscalationLevel.WARNING: 1,
    EscalationLevel.ALERT: 2,
    EscalationLevel.CRITICAL: 3,
    EscalationLevel.EMERGENCY: 4,
}

# Non-incident event types excluded from compliance incident counts
_NON_INCIDENT_TYPES = {
    SecurityEventType.AUTHORIZATION_GRANTED.value,
    SecurityEventType.QUOTA_WARNING.value,
}

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class SecurityEvent:
    """Security event."""
    event_id: str
    event_type: SecurityEventType
    escalation_level: EscalationLevel
    source_module: str
    bot_id: Optional[str]
    tenant_id: Optional[str]
    description: str
    metadata: Dict[str, Any]
    timestamp: datetime
    correlated_events: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "escalation_level": self.escalation_level.value,
            "source_module": self.source_module,
            "bot_id": self.bot_id,
            "tenant_id": self.tenant_id,
            "description": self.description,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
            "correlated_events": list(self.correlated_events),
        }


@dataclass
class CorrelatedEventGroup:
    """Correlated event group."""
    group_id: str
    events: List[SecurityEvent]
    primary_event_id: str
    correlation_reason: str
    timestamp: datetime

    def to_dict(self) -> Dict[str, Any]:
        return {
            "group_id": self.group_id,
            "events": [e.to_dict() for e in self.events],
            "primary_event_id": self.primary_event_id,
            "correlation_reason": self.correlation_reason,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class SecurityReport:
    """Security report."""
    report_id: str
    generated_at: datetime
    period_start: datetime
    period_end: datetime
    total_events: int
    events_by_type: Dict[str, int]
    events_by_severity: Dict[str, int]
    top_affected_bots: List[Dict[str, Any]]
    compliance_summary: Dict[str, Any]
    recommendations: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "generated_at": self.generated_at.isoformat(),
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "total_events": self.total_events,
            "events_by_type": dict(self.events_by_type),
            "events_by_severity": dict(self.events_by_severity),
            "top_affected_bots": list(self.top_affected_bots),
            "compliance_summary": dict(self.compliance_summary),
            "recommendations": list(self.recommendations),
        }

# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

class SecurityDashboard:
    """Unified security monitoring dashboard."""

    def __init__(self, max_events: int = 50000,
                 correlation_window_seconds: int = 300) -> None:
        self._lock = threading.Lock()
        self._max_events = max_events
        self._correlation_window = timedelta(seconds=correlation_window_seconds)
        self._events: List[SecurityEvent] = []
        self._correlated_groups: List[CorrelatedEventGroup] = []
        self._escalation_callbacks: Dict[
            EscalationLevel, List[Callable[[SecurityEvent], None]]
        ] = defaultdict(list)
        self._event_count_by_type: Counter = Counter()
        self._event_count_by_level: Counter = Counter()
        logger.info("SecurityDashboard initialised (max_events=%d, window=%ds)",
                     max_events, correlation_window_seconds)

    # -- public API ---------------------------------------------------------

    def register_escalation_callback(
        self, level: EscalationLevel, callback: Callable[[SecurityEvent], None],
    ) -> None:
        with self._lock:
            self._escalation_callbacks[level].append(callback)
        logger.debug("Registered escalation callback for level=%s", level.value)

    def record_event(self, event: SecurityEvent) -> Optional[CorrelatedEventGroup]:
        """Record a security event and attempt correlation."""
        with self._lock:
            self._events.append(event)
            self._event_count_by_type[event.event_type.value] += 1
            self._event_count_by_level[event.escalation_level.value] += 1
            if len(self._events) > self._max_events:
                self._events = self._events[-self._max_events:]
            group = self._correlate_event(event)
            if group is not None:
                capped_append(self._correlated_groups, group)
        logger.info("Recorded event %s [%s/%s] from %s", event.event_id,
                     event.event_type.value, event.escalation_level.value,
                     event.source_module)
        self._check_escalation(event)
        return group

    def get_events(self, event_type: Optional[SecurityEventType] = None,
                   escalation_level: Optional[EscalationLevel] = None,
                   bot_id: Optional[str] = None,
                   tenant_id: Optional[str] = None,
                   limit: int = 100) -> List[SecurityEvent]:
        """Return filtered events, most recent first."""
        with self._lock:
            results = list(reversed(self._events))
        if event_type is not None:
            results = [e for e in results if e.event_type == event_type]
        if escalation_level is not None:
            results = [e for e in results if e.escalation_level == escalation_level]
        if bot_id is not None:
            results = [e for e in results if e.bot_id == bot_id]
        if tenant_id is not None:
            results = [e for e in results if e.tenant_id == tenant_id]
        return results[:limit]

    def get_correlated_groups(self, limit: int = 50) -> List[CorrelatedEventGroup]:
        with self._lock:
            return list(reversed(self._correlated_groups))[:limit]

    def generate_report(self, period_hours: int = 24) -> SecurityReport:
        """Generate a comprehensive security report for the given period."""
        now = datetime.now(timezone.utc)
        period_start = now - timedelta(hours=period_hours)
        with self._lock:
            period_events = [e for e in self._events if e.timestamp >= period_start]
        type_counts: Counter = Counter(e.event_type.value for e in period_events)
        severity_counts: Counter = Counter(
            e.escalation_level.value for e in period_events)
        bot_counter: Counter = Counter(
            e.bot_id for e in period_events if e.bot_id is not None)
        top_bots = [{"bot_id": bid, "event_count": cnt}
                    for bid, cnt in bot_counter.most_common(10)]
        report = SecurityReport(
            report_id=str(uuid.uuid4()), generated_at=now,
            period_start=period_start, period_end=now,
            total_events=len(period_events),
            events_by_type=dict(type_counts),
            events_by_severity=dict(severity_counts),
            top_affected_bots=top_bots,
            compliance_summary=self._build_compliance_summary(
                period_events, type_counts),
            recommendations=self._build_recommendations(
                type_counts, severity_counts),
        )
        logger.info("Generated report %s (%d events, %dh window)",
                     report.report_id, report.total_events, period_hours)
        return report

    def get_dashboard_summary(self) -> Dict[str, Any]:
        """Get a real-time dashboard summary."""
        now = datetime.now(timezone.utc)
        one_hour_ago = now - timedelta(hours=1)
        with self._lock:
            total = len(self._events)
            recent = [e for e in self._events if e.timestamp >= one_hour_ago]
            recent_groups = [g for g in self._correlated_groups
                            if g.timestamp >= one_hour_ago]
        return {
            "timestamp": now.isoformat(),
            "total_events_stored": total,
            "events_last_hour": len(recent),
            "correlated_groups_last_hour": len(recent_groups),
            "last_hour_by_type": dict(Counter(
                e.event_type.value for e in recent)),
            "last_hour_by_severity": dict(Counter(
                e.escalation_level.value for e in recent)),
            "highest_recent_severity": self._highest_severity(recent),
        }

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total_events": len(self._events),
                "total_correlated_groups": len(self._correlated_groups),
                "events_by_type": dict(self._event_count_by_type),
                "events_by_severity": dict(self._event_count_by_level),
                "max_events": self._max_events,
                "correlation_window_seconds": int(
                    self._correlation_window.total_seconds()),
            }

    # -- internal helpers ---------------------------------------------------

    def _correlate_event(self, event: SecurityEvent) -> Optional[CorrelatedEventGroup]:
        """Try to correlate *event* with recent events from the same bot."""
        if event.bot_id is None:
            return None
        cutoff = event.timestamp - self._correlation_window
        related = [e for e in self._events
                   if e.event_id != event.event_id
                   and e.bot_id == event.bot_id
                   and e.timestamp >= cutoff]
        if not related:
            return None
        # Link events bidirectionally
        related_ids = [e.event_id for e in related]
        event.correlated_events.extend(related_ids)
        for rel in related:
            if event.event_id not in rel.correlated_events:
                rel.correlated_events.append(event.event_id)
        window_s = int(self._correlation_window.total_seconds())
        group = CorrelatedEventGroup(
            group_id=str(uuid.uuid4()),
            events=related + [event],
            primary_event_id=event.event_id,
            correlation_reason=(
                f"Multiple events for bot {event.bot_id} within {window_s}s window"),
            timestamp=event.timestamp,
        )
        logger.debug("Correlated %d events into group %s for bot %s",
                      len(group.events), group.group_id, event.bot_id)
        return group

    def _check_escalation(self, event: SecurityEvent) -> None:
        """Fire registered callbacks when an event meets the escalation level."""
        with self._lock:
            callbacks = list(
                self._escalation_callbacks.get(event.escalation_level, []))
        for cb in callbacks:
            try:
                cb(event)
            except Exception as exc:
                logger.debug("Suppressed exception: %s", exc)
                logger.exception("Escalation callback failed for event %s",
                                 event.event_id)

    @staticmethod
    def _highest_severity(events: List[SecurityEvent]) -> Optional[str]:
        if not events:
            return None
        return max(events,
                   key=lambda e: _ESCALATION_ORDER.get(e.escalation_level, 0)
                   ).escalation_level.value

    @staticmethod
    def _build_compliance_summary(events: List[SecurityEvent],
                                  type_counts: Counter) -> Dict[str, Any]:
        return {
            "authorization_denials": type_counts.get(
                SecurityEventType.AUTHORIZATION_DENIED.value, 0),
            "pii_incidents": type_counts.get(
                SecurityEventType.PII_DETECTED.value, 0),
            "identity_failures": type_counts.get(
                SecurityEventType.IDENTITY_VERIFICATION_FAILED.value, 0),
            "total_security_incidents": sum(
                c for t, c in type_counts.items()
                if t not in _NON_INCIDENT_TYPES),
            "audit_completeness": "full" if events else "no_data",
        }

    @staticmethod
    def _build_recommendations(type_counts: Counter,
                               severity_counts: Counter) -> List[str]:
        recs: List[str] = []
        if type_counts.get(SecurityEventType.QUOTA_VIOLATION.value, 0) > 10:
            recs.append("High quota violation rate — review resource limits "
                        "and consider adjusting thresholds.")
        if type_counts.get(
                SecurityEventType.IDENTITY_VERIFICATION_FAILED.value, 0) > 5:
            recs.append("Frequent identity verification failures — audit bot "
                        "credential rotation policies.")
        if type_counts.get(SecurityEventType.COMMUNICATION_LOOP.value, 0) > 3:
            recs.append("Communication loops detected — inspect swarm topology "
                        "for circular message paths.")
        if type_counts.get(SecurityEventType.PII_DETECTED.value, 0) > 0:
            recs.append("PII leakage incidents recorded — strengthen data-leak "
                        "prevention filters.")
        if severity_counts.get(EscalationLevel.CRITICAL.value, 0) > 0:
            recs.append("Critical-severity events occurred — perform root-cause "
                        "analysis and verify incident response procedures.")
        if severity_counts.get(EscalationLevel.EMERGENCY.value, 0) > 0:
            recs.append("Emergency-level events detected — immediate executive "
                        "review recommended.")
        if not recs:
            recs.append("No actionable concerns identified in the reporting period.")
        return recs
