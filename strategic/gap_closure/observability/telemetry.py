# Copyright © 2020-2026 Inoni Limited Liability Company. All rights reserved.
# Created by: Corey Post

"""
telemetry.py — Murphy System Observability & Telemetry Module
Metrics registry, Prometheus exporter, distributed tracer, dashboard summary.
"""

from __future__ import annotations

import json
import time
import threading
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class MetricType(Enum):
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Metric:
    name: str
    metric_type: MetricType
    value: float
    labels: Dict[str, str] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    help_text: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["metric_type"] = self.metric_type.value
        return d


@dataclass
class HistogramBucket:
    le: float        # upper bound
    count: int = 0

    def to_dict(self) -> dict:
        return {"le": self.le, "count": self.count}


@dataclass
class SpanEvent:
    name: str
    timestamp: float = field(default_factory=time.time)
    attributes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Span:
    trace_id: str
    span_id: str
    name: str
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[SpanEvent] = field(default_factory=list)
    parent_span_id: Optional[str] = None
    status: str = "active"

    @property
    def duration_ms(self) -> Optional[float]:
        if self.end_time is None:
            return None
        return round((self.end_time - self.start_time) * 1000, 3)

    def to_dict(self) -> dict:
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "name": self.name,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": self.duration_ms,
            "attributes": self.attributes,
            "events": [asdict(e) for e in self.events],
            "parent_span_id": self.parent_span_id,
            "status": self.status,
        }


# ---------------------------------------------------------------------------
# MetricsRegistry
# ---------------------------------------------------------------------------

class MetricsRegistry:
    """Thread-safe registry for Murphy System metrics."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: Dict[str, float] = {}
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, List[float]] = {}
        self._summaries: Dict[str, List[float]] = {}
        self._help: Dict[str, str] = {}
        self._labels: Dict[str, Dict[str, str]] = {}

    def _key(self, name: str, labels: Optional[Dict[str, str]] = None) -> str:
        if not labels:
            return name
        label_str = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"

    def counter(self, name: str, value: float = 1.0,
                labels: Optional[Dict[str, str]] = None, help_text: str = "") -> None:
        key = self._key(name, labels)
        with self._lock:
            self._counters[key] = self._counters.get(key, 0) + value
            if help_text:
                self._help[name] = help_text
            if labels:
                self._labels[key] = labels

    def gauge(self, name: str, value: float,
              labels: Optional[Dict[str, str]] = None, help_text: str = "") -> None:
        key = self._key(name, labels)
        with self._lock:
            self._gauges[key] = value
            if help_text:
                self._help[name] = help_text
            if labels:
                self._labels[key] = labels

    def histogram(self, name: str, value: float,
                  labels: Optional[Dict[str, str]] = None, help_text: str = "") -> None:
        key = self._key(name, labels)
        with self._lock:
            if key not in self._histograms:
                self._histograms[key] = []
            self._histograms[key].append(value)
            if help_text:
                self._help[name] = help_text

    def summary(self, name: str, value: float,
                labels: Optional[Dict[str, str]] = None, help_text: str = "") -> None:
        key = self._key(name, labels)
        with self._lock:
            if key not in self._summaries:
                self._summaries[key] = []
            self._summaries[key].append(value)
            if help_text:
                self._help[name] = help_text

    def record(self, metric: Metric) -> None:
        if metric.metric_type == MetricType.COUNTER:
            self.counter(metric.name, metric.value, metric.labels, metric.help_text)
        elif metric.metric_type == MetricType.GAUGE:
            self.gauge(metric.name, metric.value, metric.labels, metric.help_text)
        elif metric.metric_type == MetricType.HISTOGRAM:
            self.histogram(metric.name, metric.value, metric.labels, metric.help_text)
        elif metric.metric_type == MetricType.SUMMARY:
            self.summary(metric.name, metric.value, metric.labels, metric.help_text)

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "histograms": {k: list(v) for k, v in self._histograms.items()},
                "summaries": {k: list(v) for k, v in self._summaries.items()},
            }

    def export_prometheus_text(self) -> str:
        lines: List[str] = []
        snap = self.snapshot()

        for key, val in snap["counters"].items():
            base_name = key.split("{")[0]
            if base_name in self._help:
                lines.append(f"# HELP {base_name} {self._help[base_name]}")
            lines.append(f"# TYPE {base_name} counter")
            lines.append(f"{key} {val}")

        for key, val in snap["gauges"].items():
            base_name = key.split("{")[0]
            if base_name in self._help:
                lines.append(f"# HELP {base_name} {self._help[base_name]}")
            lines.append(f"# TYPE {base_name} gauge")
            lines.append(f"{key} {val}")

        for key, values in snap["histograms"].items():
            if not values:
                continue
            base_name = key.split("{")[0]
            if base_name in self._help:
                lines.append(f"# HELP {base_name} {self._help[base_name]}")
            lines.append(f"# TYPE {base_name} histogram")
            buckets = [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
            for le in buckets:
                cnt = sum(1 for v in values if v <= le)
                lines.append(f"{base_name}_bucket{{le=\"{le}\"}} {cnt}")
            lines.append(f"{base_name}_bucket{{le=\"+Inf\"}} {len(values)}")
            lines.append(f"{base_name}_sum {sum(values)}")
            lines.append(f"{base_name}_count {len(values)}")

        return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# TelemetryExporter
# ---------------------------------------------------------------------------

class TelemetryExporter:
    """Exports metrics in multiple formats."""

    def __init__(self, registry: MetricsRegistry) -> None:
        self._registry = registry

    def prometheus_text(self) -> str:
        return self._registry.export_prometheus_text()

    def json_snapshot(self, indent: int = 2) -> str:
        return json.dumps(self._registry.snapshot(), indent=indent)


# ---------------------------------------------------------------------------
# DistributedTracer
# ---------------------------------------------------------------------------

class DistributedTracer:
    """Lightweight distributed tracing (no external deps)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._spans: Dict[str, Span] = {}
        self._traces: Dict[str, List[str]] = {}   # trace_id → [span_ids]

    def start_span(self, name: str, trace_id: Optional[str] = None,
                   parent_span_id: Optional[str] = None,
                   attributes: Optional[Dict[str, Any]] = None) -> Span:
        span = Span(
            trace_id=trace_id or str(uuid.uuid4()),
            span_id=str(uuid.uuid4()),
            name=name,
            parent_span_id=parent_span_id,
            attributes=attributes or {},
        )
        with self._lock:
            self._spans[span.span_id] = span
            if span.trace_id not in self._traces:
                self._traces[span.trace_id] = []
            self._traces[span.trace_id].append(span.span_id)
        return span

    def end_span(self, span_id: str, status: str = "ok",
                 attributes: Optional[Dict[str, Any]] = None) -> Optional[Span]:
        with self._lock:
            span = self._spans.get(span_id)
            if span:
                span.end_time = time.time()
                span.status = status
                if attributes:
                    span.attributes.update(attributes)
        return span

    def add_event(self, span_id: str, name: str,
                  attributes: Optional[Dict[str, Any]] = None) -> None:
        with self._lock:
            span = self._spans.get(span_id)
            if span:
                span.events.append(SpanEvent(name=name, attributes=attributes or {}))

    def get_span(self, span_id: str) -> Optional[Span]:
        return self._spans.get(span_id)

    def get_trace(self, trace_id: str) -> List[Span]:
        with self._lock:
            span_ids = self._traces.get(trace_id, [])
            return [self._spans[sid] for sid in span_ids if sid in self._spans]

    def active_spans(self) -> List[Span]:
        with self._lock:
            return [s for s in self._spans.values() if s.end_time is None]

    def total_spans_recorded(self) -> int:
        """Return the total number of spans recorded across all traces."""
        with self._lock:
            return sum(len(v) for v in self._traces.values())


# ---------------------------------------------------------------------------
# ObservabilityDashboard
# ---------------------------------------------------------------------------

class ObservabilityDashboard:
    """High-level summary for dashboard rendering."""

    def __init__(self, registry: MetricsRegistry, tracer: DistributedTracer) -> None:
        self._registry = registry
        self._tracer = tracer

    def get_summary(self) -> Dict[str, Any]:
        snap = self._registry.snapshot()
        active = self._tracer.active_spans()

        confidence_values = snap["histograms"].get("confidence_score_histogram", [])
        avg_confidence = (
            round(sum(confidence_values) / len(confidence_values), 4)
            if confidence_values else None
        )

        return {
            "system_health": self._compute_health(snap),
            "metrics": {
                "gate_evaluations_total": snap["counters"].get("gate_evaluations_total", 0),
                "llm_requests_total": snap["counters"].get("llm_requests_total", 0),
                "deployment_count": snap["counters"].get("deployment_count", 0),
                "confidence_score_samples": len(confidence_values),
                "avg_confidence_score": avg_confidence,
            },
            "tracing": {
                "active_spans": len(active),
                "total_spans_recorded": self._tracer.total_spans_recorded(),
            },
            "gauges": dict(snap["gauges"]),
        }

    def _compute_health(self, snap: Dict[str, Any]) -> str:
        error_rate = snap["gauges"].get("error_rate", 0)
        if error_rate > 0.1:
            return "RED"
        if error_rate > 0.05:
            return "YELLOW"
        return "GREEN"


# ---------------------------------------------------------------------------
# Pre-registered Murphy System metrics
# ---------------------------------------------------------------------------

def build_default_registry() -> MetricsRegistry:
    """Create and seed the default Murphy System metrics registry."""
    reg = MetricsRegistry()
    reg.counter("gate_evaluations_total", 0,
                help_text="Total number of safety/governance gate evaluations")
    reg.counter("llm_requests_total", 0,
                help_text="Total LLM provider requests routed")
    reg.counter("deployment_count", 0,
                help_text="Total system deployments performed")
    reg.gauge("error_rate", 0.0,
              help_text="Current error rate (0.0 – 1.0)")
    reg.gauge("active_agents", 0.0,
              help_text="Number of currently active agents in the swarm")
    reg.gauge("connector_count", 0.0,
              help_text="Number of registered connectors")
    return reg


# Lazy-initialized module-level singletons — call get_default_*() to access
_default_registry: Optional[MetricsRegistry] = None
_default_tracer: Optional[DistributedTracer] = None
_default_dashboard: Optional[ObservabilityDashboard] = None


def get_default_registry() -> MetricsRegistry:
    """Return (and lazily create) the shared default MetricsRegistry."""
    global _default_registry
    if _default_registry is None:
        _default_registry = build_default_registry()
    return _default_registry


def get_default_tracer() -> DistributedTracer:
    """Return (and lazily create) the shared default DistributedTracer."""
    global _default_tracer
    if _default_tracer is None:
        _default_tracer = DistributedTracer()
    return _default_tracer


def get_default_dashboard() -> ObservabilityDashboard:
    """Return (and lazily create) the shared default ObservabilityDashboard."""
    global _default_dashboard
    if _default_dashboard is None:
        _default_dashboard = ObservabilityDashboard(
            get_default_registry(), get_default_tracer()
        )
    return _default_dashboard


if __name__ == "__main__":
    # Quick demo
    reg = build_default_registry()
    reg.counter("gate_evaluations_total", 42)
    reg.counter("llm_requests_total", 150)
    reg.counter("deployment_count", 7)
    reg.gauge("error_rate", 0.02)
    for v in [0.91, 0.87, 0.95, 0.78, 0.99, 0.85]:
        reg.histogram("confidence_score_histogram", v,
                      help_text="Distribution of Murphy confidence scores")

    tracer = DistributedTracer()
    span = tracer.start_span("api_request", attributes={"route": "/api/v1/run"})
    tracer.add_event(span.span_id, "gate_check", {"gate": "hipaa"})
    tracer.end_span(span.span_id, status="ok")

    dashboard = ObservabilityDashboard(reg, tracer)
    summary = dashboard.get_summary()

    print("Murphy System Observability Dashboard — Summary")
    print(json.dumps(summary, indent=2))
    print()
    print("Prometheus export (first 20 lines):")
    exporter = TelemetryExporter(reg)
    for line in exporter.prometheus_text().split("\n")[:20]:
        print(" ", line)
