"""
AUAR Layer 7 — Observability & Governance Layer
=================================================

Distributed tracing, metrics collection, audit logging, compliance
enforcement, and cost attribution for the AUAR pipeline.

Designed for OpenTelemetry-compatible export; the in-memory
implementation provides the same contract for testing and offline use.

Copyright 2024 Inoni LLC – BSL-1.1
"""

import logging
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

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
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class SpanRecord:
    """A single span within a request trace."""
    span_id: str = field(default_factory=lambda: str(uuid4()))
    parent_span_id: str = ""
    operation: str = ""
    start_time: float = 0.0
    end_time: float = 0.0
    attributes: Dict[str, Any] = field(default_factory=dict)
    status: str = "ok"  # ok | error

    @property
    def duration_ms(self) -> float:
        return (self.end_time - self.start_time) * 1000 if self.end_time else 0.0


@dataclass
class RequestTrace:
    """Complete trace for one AUAR request."""
    trace_id: str = field(default_factory=lambda: str(uuid4()))
    request_id: str = ""
    tenant_id: str = ""
    capability: str = ""
    provider_id: str = ""
    spans: List[SpanRecord] = field(default_factory=list)
    total_latency_ms: float = 0.0
    success: bool = True
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class AuditEntry:
    """Immutable audit log entry."""
    entry_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    actor: str = ""
    action: str = ""
    resource: str = ""
    detail: Dict[str, Any] = field(default_factory=dict)
    tenant_id: str = ""
    outcome: str = "success"  # success | failure | denied


@dataclass
class CostAttribution:
    """Cost record attributed to a tenant + capability + provider."""
    attribution_id: str = field(default_factory=lambda: str(uuid4()))
    tenant_id: str = ""
    capability: str = ""
    provider_id: str = ""
    cost: float = 0.0
    currency: str = "USD"
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    request_id: str = ""


# ---------------------------------------------------------------------------
# Observability Layer
# ---------------------------------------------------------------------------

class ObservabilityLayer:
    """Central observability facade for the AUAR pipeline.

    Provides:
    - Distributed tracing (in-memory span collection)
    - Metrics counters & histograms
    - Audit logging
    - Cost attribution & billing aggregation
    """

    def __init__(self, max_traces: int = 10000, max_audit: int = 50000):
        self._traces: Dict[str, RequestTrace] = {}
        self._audit_log: List[AuditEntry] = []
        self._cost_records: List[CostAttribution] = []
        self._counters: Dict[str, int] = defaultdict(int)
        self._histograms: Dict[str, List[float]] = defaultdict(list)
        self._max_traces = max_traces
        self._max_audit = max_audit
        self._lock = threading.Lock()

    # -- Tracing ------------------------------------------------------------

    def start_trace(
        self,
        request_id: str,
        tenant_id: str = "",
        capability: str = "",
    ) -> RequestTrace:
        """Begin a new trace and return it."""
        trace = RequestTrace(
            request_id=request_id,
            tenant_id=tenant_id,
            capability=capability,
        )
        with self._lock:
            if len(self._traces) >= self._max_traces:
                # Evict oldest (FIFO)
                oldest_key = next(iter(self._traces))
                del self._traces[oldest_key]
            self._traces[trace.trace_id] = trace
        return trace

    def add_span(
        self,
        trace_id: str,
        operation: str,
        attributes: Optional[Dict[str, Any]] = None,
        parent_span_id: str = "",
    ) -> SpanRecord:
        """Add a span to an existing trace and return it."""
        span = SpanRecord(
            operation=operation,
            parent_span_id=parent_span_id,
            start_time=time.monotonic(),
            attributes=attributes or {},
        )
        with self._lock:
            trace = self._traces.get(trace_id)
            if trace:
                trace.spans.append(span)
        return span

    def end_span(self, span: SpanRecord, status: str = "ok") -> None:
        """Mark a span as complete."""
        span.end_time = time.monotonic()
        span.status = status

    def finish_trace(self, trace_id: str, success: bool = True) -> Optional[RequestTrace]:
        """Finalise a trace with total latency."""
        with self._lock:
            trace = self._traces.get(trace_id)
            if not trace:
                return None
            trace.success = success
            if trace.spans:
                start = min(s.start_time for s in trace.spans if s.start_time)
                end = max(s.end_time for s in trace.spans if s.end_time)
                trace.total_latency_ms = (end - start) * 1000
        return trace

    def get_trace(self, trace_id: str) -> Optional[RequestTrace]:
        with self._lock:
            return self._traces.get(trace_id)

    # -- Metrics ------------------------------------------------------------

    def increment(self, metric_name: str, value: int = 1) -> None:
        with self._lock:
            self._counters[metric_name] += value

    def observe(self, metric_name: str, value: float) -> None:
        """Record a histogram observation."""
        with self._lock:
            self._histograms[metric_name].append(value)

    def get_counter(self, metric_name: str) -> int:
        with self._lock:
            return self._counters.get(metric_name, 0)

    def get_histogram_summary(self, metric_name: str) -> Dict[str, float]:
        with self._lock:
            values = list(self._histograms.get(metric_name, []))
        if not values:
            return {"count": 0, "min": 0.0, "max": 0.0, "avg": 0.0, "p99": 0.0}
        values.sort()
        count = len(values)
        p99_idx = min(int(count * 0.99), count - 1)
        return {
            "count": float(count),
            "min": values[0],
            "max": values[-1],
            "avg": sum(values) / count,
            "p99": values[p99_idx],
        }

    # -- Audit logging ------------------------------------------------------

    def audit(
        self,
        actor: str,
        action: str,
        resource: str = "",
        detail: Optional[Dict[str, Any]] = None,
        tenant_id: str = "",
        outcome: str = "success",
    ) -> AuditEntry:
        """Record an audit entry."""
        entry = AuditEntry(
            actor=actor,
            action=action,
            resource=resource,
            detail=detail or {},
            tenant_id=tenant_id,
            outcome=outcome,
        )
        with self._lock:
            if len(self._audit_log) >= self._max_audit:
                self._audit_log = self._audit_log[-self._max_audit // 2 :]
            self._audit_log.append(entry)
        return entry

    def get_audit_log(
        self, tenant_id: Optional[str] = None, limit: int = 100
    ) -> List[AuditEntry]:
        with self._lock:
            entries = list(self._audit_log)
        if tenant_id:
            entries = [e for e in entries if e.tenant_id == tenant_id]
        return entries[-limit:]

    # -- Cost attribution ---------------------------------------------------

    def record_cost(
        self,
        tenant_id: str,
        capability: str,
        provider_id: str,
        cost: float,
        request_id: str = "",
        currency: str = "USD",
    ) -> CostAttribution:
        """Record a cost attribution entry."""
        attr = CostAttribution(
            tenant_id=tenant_id,
            capability=capability,
            provider_id=provider_id,
            cost=cost,
            currency=currency,
            request_id=request_id,
        )
        with self._lock:
            capped_append(self._cost_records, attr)
        return attr

    def get_cost_summary(
        self, tenant_id: Optional[str] = None
    ) -> Dict[str, float]:
        """Aggregate costs, optionally filtered by tenant."""
        with self._lock:
            records = list(self._cost_records)
        if tenant_id:
            records = [r for r in records if r.tenant_id == tenant_id]
        summary: Dict[str, float] = defaultdict(float)
        for r in records:
            summary[f"{r.capability}/{r.provider_id}"] += r.cost
        summary["total"] = sum(r.cost for r in records)
        return dict(summary)

    # -- Stats --------------------------------------------------------------

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "traces": len(self._traces),
                "audit_entries": len(self._audit_log),
                "cost_records": len(self._cost_records),
                "counters": dict(self._counters),
            }
