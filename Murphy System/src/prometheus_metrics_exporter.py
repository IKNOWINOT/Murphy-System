# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Prometheus / OpenTelemetry Metrics Exporter — PME-001

Export system health, request latency, error rates, and resource
utilisation in Prometheus text exposition format *and* structured JSON.
Designed so non-technical operators can point a Prometheus/Grafana stack
at Murphy and get dashboards with zero custom configuration.

Design Principles:
  - Four standard metric types: Counter, Gauge, Histogram, Summary.
  - Labels attach arbitrary key-value dimensions to every sample.
  - CollectorRegistry aggregates all metrics in one place.
  - Prometheus text endpoint (`/metrics`) follows the official exposition
    format (https://prometheus.io/docs/instrumenting/exposition_formats/).
  - JSON endpoint (`/api/metrics/json`) returns the same data for UIs.
  - WingmanProtocol pair validation gates every metric registration.
  - CausalitySandbox gating simulates metric-publish side-effects.
  - Thread-safe: all shared state protected by locks.
  - No external dependencies beyond the Python stdlib + Flask.

Key Classes:
  MetricType            — enum of Counter / Gauge / Histogram / Summary
  LabelSet              — frozen label key-value pairs
  Sample                — a single metric observation
  MetricFamily          — definition + collected samples for one metric
  CollectorRegistry     — central store of all MetricFamily objects
  PrometheusRenderer    — renders registry → Prometheus text format
  JsonRenderer          — renders registry → JSON dict
  MetricsExporterAPI    — Flask blueprint with /metrics + JSON endpoints

Copyright © 2020 Inoni Limited Liability Company
"""
from __future__ import annotations

import logging
import math
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, FrozenSet, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

# ── Wingman / Sandbox stubs (real wiring when available) ─────────────
_WINGMAN_ENABLED = True
_SANDBOX_ENABLED = True


def set_wingman_enabled(flag: bool) -> None:
    """Toggle Wingman validation gate."""
    global _WINGMAN_ENABLED
    _WINGMAN_ENABLED = flag


def set_sandbox_enabled(flag: bool) -> None:
    """Toggle Causality Sandbox gate."""
    global _SANDBOX_ENABLED
    _SANDBOX_ENABLED = flag


def _wingman_validate(action: str, payload: Dict[str, Any]) -> bool:
    """Return True when Wingman pair approves *action*."""
    if not _WINGMAN_ENABLED:
        return True
    if not (bool(action) and isinstance(payload, dict)):
        return False
    # Validate that required fields are non-empty
    name = payload.get("name", "")
    return bool(name)


def _sandbox_simulate(action: str, payload: Dict[str, Any]) -> bool:
    """Return True when Causality Sandbox allows *action*."""
    if not _SANDBOX_ENABLED:
        return True
    if not (bool(action) and isinstance(payload, dict)):
        return False
    name = payload.get("name", "")
    return bool(name)


# ── Enums ────────────────────────────────────────────────────────────

class MetricType(str, Enum):
    """Supported Prometheus metric types."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


# ── Data Models ──────────────────────────────────────────────────────

LabelSet = FrozenSet[Tuple[str, str]]


def _label_set(**kwargs: str) -> LabelSet:
    """Build an immutable label set from keyword arguments."""
    return frozenset(kwargs.items())


EMPTY_LABELS: LabelSet = frozenset()


@dataclass(frozen=True)
class Sample:
    """Single time-series observation."""
    name: str
    labels: LabelSet
    value: float
    timestamp_ms: Optional[int] = None


@dataclass
class MetricFamily:
    """Definition and collected samples for one metric."""
    name: str
    help_text: str
    metric_type: MetricType
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    # Counter / Gauge values keyed by LabelSet
    _values: Dict[LabelSet, float] = field(default_factory=dict, repr=False)
    # Histogram state
    _bucket_bounds: Tuple[float, ...] = field(default=(0.005, 0.01, 0.025,
        0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0), repr=False)
    _hist_buckets: Dict[LabelSet, List[int]] = field(
        default_factory=dict, repr=False)
    _hist_sum: Dict[LabelSet, float] = field(
        default_factory=dict, repr=False)
    _hist_count: Dict[LabelSet, int] = field(
        default_factory=dict, repr=False)
    # Summary state (stores raw observations for quantile calc)
    _summary_obs: Dict[LabelSet, List[float]] = field(
        default_factory=dict, repr=False)

    # ── public mutators ──────────────────────────────────────────

    def inc(self, amount: float = 1.0, labels: LabelSet = EMPTY_LABELS) -> None:
        """Increment a Counter or Gauge."""
        if self.metric_type == MetricType.COUNTER and amount < 0:
            raise ValueError("Counter increment must be non-negative")
        with self._lock:
            self._values[labels] = self._values.get(labels, 0.0) + amount

    def dec(self, amount: float = 1.0, labels: LabelSet = EMPTY_LABELS) -> None:
        """Decrement a Gauge."""
        if self.metric_type != MetricType.GAUGE:
            raise TypeError("Only gauges support dec()")
        with self._lock:
            self._values[labels] = self._values.get(labels, 0.0) - amount

    def set_value(self, value: float, labels: LabelSet = EMPTY_LABELS) -> None:
        """Set absolute value for a Gauge."""
        if self.metric_type != MetricType.GAUGE:
            raise TypeError("Only gauges support set_value()")
        with self._lock:
            self._values[labels] = value

    def observe(self, value: float, labels: LabelSet = EMPTY_LABELS) -> None:
        """Record an observation (Histogram or Summary)."""
        if self.metric_type not in (MetricType.HISTOGRAM, MetricType.SUMMARY):
            raise TypeError("observe() is for histograms/summaries")
        with self._lock:
            if self.metric_type == MetricType.HISTOGRAM:
                self._observe_histogram(value, labels)
            else:
                self._observe_summary(value, labels)

    # ── histogram helpers ────────────────────────────────────────

    def _observe_histogram(self, value: float, labels: LabelSet) -> None:
        if labels not in self._hist_buckets:
            self._hist_buckets[labels] = [0] * len(self._bucket_bounds)
            self._hist_sum[labels] = 0.0
            self._hist_count[labels] = 0
        for i, bound in enumerate(self._bucket_bounds):
            if value <= bound:
                self._hist_buckets[labels][i] += 1
        self._hist_sum[labels] += value
        self._hist_count[labels] += 1

    # ── summary helpers ──────────────────────────────────────────

    def _observe_summary(self, value: float, labels: LabelSet) -> None:
        self._summary_obs.setdefault(labels, []).append(value)

    # ── collection ───────────────────────────────────────────────

    def collect(self) -> List[Sample]:
        """Return all current samples for this metric family."""
        with self._lock:
            if self.metric_type in (MetricType.COUNTER, MetricType.GAUGE):
                return self._collect_simple()
            elif self.metric_type == MetricType.HISTOGRAM:
                return self._collect_histogram()
            else:
                return self._collect_summary()

    def _collect_simple(self) -> List[Sample]:
        samples: List[Sample] = []
        for ls, val in self._values.items():
            samples.append(Sample(name=self.name, labels=ls, value=val))
        return samples

    def _collect_histogram(self) -> List[Sample]:
        samples: List[Sample] = []
        for ls in self._hist_buckets:
            cumulative = 0
            for i, bound in enumerate(self._bucket_bounds):
                cumulative += self._hist_buckets[ls][i]
                le_labels = ls | frozenset({("le", str(bound))})
                samples.append(Sample(
                    name=f"{self.name}_bucket", labels=le_labels,
                    value=float(cumulative)))
            inf_labels = ls | frozenset({("le", "+Inf")})
            samples.append(Sample(
                name=f"{self.name}_bucket", labels=inf_labels,
                value=float(self._hist_count.get(ls, 0))))
            samples.append(Sample(
                name=f"{self.name}_sum", labels=ls,
                value=self._hist_sum.get(ls, 0.0)))
            samples.append(Sample(
                name=f"{self.name}_count", labels=ls,
                value=float(self._hist_count.get(ls, 0))))
        return samples

    def _collect_summary(self) -> List[Sample]:
        samples: List[Sample] = []
        quantiles = (0.5, 0.9, 0.99)
        for ls, obs in self._summary_obs.items():
            if not obs:
                continue
            sorted_obs = sorted(obs)
            n = len(sorted_obs)
            for q in quantiles:
                idx = min(int(math.floor(q * n)), n - 1)
                q_labels = ls | frozenset({("quantile", str(q))})
                samples.append(Sample(
                    name=self.name, labels=q_labels,
                    value=sorted_obs[idx]))
            samples.append(Sample(
                name=f"{self.name}_sum", labels=ls,
                value=sum(obs)))
            samples.append(Sample(
                name=f"{self.name}_count", labels=ls,
                value=float(n)))
        return samples


# ── Collector Registry ───────────────────────────────────────────────

class CollectorRegistry:
    """Central store of all MetricFamily objects."""

    def __init__(self) -> None:
        self._families: Dict[str, MetricFamily] = {}
        self._lock = threading.Lock()

    def register(self, name: str, help_text: str,
                 metric_type: MetricType,
                 bucket_bounds: Optional[Tuple[float, ...]] = None) -> MetricFamily:
        """Create and register a new MetricFamily."""
        if not _wingman_validate("register_metric", {
                "name": name, "type": metric_type.value}):
            raise PermissionError("Wingman rejected metric registration")
        if not _sandbox_simulate("register_metric", {
                "name": name, "type": metric_type.value}):
            raise RuntimeError("Sandbox rejected metric registration")
        with self._lock:
            if name in self._families:
                return self._families[name]
            mf = MetricFamily(name=name, help_text=help_text,
                              metric_type=metric_type)
            if bucket_bounds and metric_type == MetricType.HISTOGRAM:
                mf._bucket_bounds = bucket_bounds
            self._families[name] = mf
            return mf

    def unregister(self, name: str) -> bool:
        """Remove a metric family by name."""
        with self._lock:
            return self._families.pop(name, None) is not None

    def get(self, name: str) -> Optional[MetricFamily]:
        """Look up a metric family by name."""
        with self._lock:
            return self._families.get(name)

    def collect_all(self) -> Dict[str, List[Sample]]:
        """Collect samples from every registered family."""
        with self._lock:
            families = dict(self._families)
        result: Dict[str, List[Sample]] = {}
        for name, mf in families.items():
            result[name] = mf.collect()
        return result

    def family_count(self) -> int:
        """Number of registered metric families."""
        with self._lock:
            return len(self._families)

    def clear(self) -> None:
        """Remove all metric families (for testing)."""
        with self._lock:
            self._families.clear()


# ── Default global registry ──────────────────────────────────────────

DEFAULT_REGISTRY = CollectorRegistry()


# ── Renderers ────────────────────────────────────────────────────────

def _labels_to_prom(labels: LabelSet) -> str:
    """Convert a LabelSet to Prometheus label string."""
    if not labels:
        return ""
    parts = sorted(f'{k}="{v}"' for k, v in labels)
    return "{" + ",".join(parts) + "}"


class PrometheusRenderer:
    """Render collected metrics → Prometheus text exposition format."""

    @staticmethod
    def render(registry: CollectorRegistry) -> str:
        """Return the full Prometheus text exposition output."""
        lines: List[str] = []
        with registry._lock:
            families = dict(registry._families)
        for name, mf in sorted(families.items()):
            lines.append(f"# HELP {name} {mf.help_text}")
            lines.append(f"# TYPE {name} {mf.metric_type.value}")
            for sample in mf.collect():
                lbl = _labels_to_prom(sample.labels)
                ts = f" {sample.timestamp_ms}" if sample.timestamp_ms else ""
                lines.append(f"{sample.name}{lbl} {sample.value}{ts}")
        lines.append("")  # trailing newline
        return "\n".join(lines)


class JsonRenderer:
    """Render collected metrics → JSON-serialisable dict."""

    @staticmethod
    def render(registry: CollectorRegistry) -> Dict[str, Any]:
        """Return a JSON-ready dict of all metrics."""
        output: Dict[str, Any] = {}
        with registry._lock:
            families = dict(registry._families)
        for name, mf in sorted(families.items()):
            samples = []
            for s in mf.collect():
                samples.append({
                    "name": s.name,
                    "labels": dict(s.labels),
                    "value": s.value,
                })
            output[name] = {
                "help": mf.help_text,
                "type": mf.metric_type.value,
                "samples": samples,
            }
        return output


# ── Built-in system metrics helpers ──────────────────────────────────

def register_builtin_metrics(registry: CollectorRegistry) -> Dict[str, MetricFamily]:
    """Register standard Murphy System metrics and return them."""
    metrics: Dict[str, MetricFamily] = {}
    metrics["murphy_requests_total"] = registry.register(
        "murphy_requests_total",
        "Total HTTP requests processed",
        MetricType.COUNTER)
    metrics["murphy_request_duration_seconds"] = registry.register(
        "murphy_request_duration_seconds",
        "HTTP request latency in seconds",
        MetricType.HISTOGRAM,
        bucket_bounds=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5,
                       1.0, 2.5, 5.0, 10.0))
    metrics["murphy_errors_total"] = registry.register(
        "murphy_errors_total",
        "Total errors encountered",
        MetricType.COUNTER)
    metrics["murphy_active_connections"] = registry.register(
        "murphy_active_connections",
        "Currently active connections",
        MetricType.GAUGE)
    metrics["murphy_uptime_seconds"] = registry.register(
        "murphy_uptime_seconds",
        "Seconds since process start",
        MetricType.GAUGE)
    metrics["murphy_response_size_bytes"] = registry.register(
        "murphy_response_size_bytes",
        "HTTP response body size distribution",
        MetricType.SUMMARY)
    return metrics


# ── Flask Blueprint ──────────────────────────────────────────────────

def create_metrics_blueprint(registry: Optional[CollectorRegistry] = None):
    """Build and return a Flask Blueprint exposing metrics endpoints."""
    try:
        from .blueprint_auth import require_blueprint_auth
    except ImportError:
        from blueprint_auth import require_blueprint_auth
    try:
        from flask import Blueprint, Response, jsonify, request
    except ImportError:
        raise ImportError("Flask is required for the metrics API blueprint")

    reg = registry or DEFAULT_REGISTRY
    bp = Blueprint("metrics_exporter", __name__)

    @bp.route("/metrics", methods=["GET"])
    def prometheus_endpoint():
        """Prometheus scrape target."""
        body = PrometheusRenderer.render(reg)
        # Bridge: append metrics from the canonical src.metrics module so the
        # Flask Blueprint and the FastAPI app share a unified view.
        try:
            from src.metrics import render_metrics as _render_canonical
            canonical = _render_canonical()
            if canonical.strip():
                body = body.rstrip("\n") + "\n" + canonical
        except Exception:
            pass
        return Response(body, status=200,
                        content_type="text/plain; version=0.0.4; charset=utf-8")

    @bp.route("/api/metrics/json", methods=["GET"])
    def json_endpoint():
        """JSON metrics for dashboards / UIs."""
        data = JsonRenderer.render(reg)
        return jsonify(data)

    @bp.route("/api/metrics/families", methods=["GET"])
    def list_families():
        """List registered metric family names."""
        with reg._lock:
            names = sorted(reg._families.keys())
        return jsonify({"families": names, "count": len(names)})

    @bp.route("/api/metrics/register", methods=["POST"])
    def register_metric():
        """Register a new metric family via API."""
        body = request.get_json(silent=True) or {}
        name = body.get("name", "").strip()
        help_text = body.get("help", "").strip()
        mtype = body.get("type", "").strip().lower()
        if not name or not help_text or not mtype:
            return jsonify({"error": "name, help, and type are required",
                            "code": "MISSING_FIELDS"}), 400
        try:
            mt = MetricType(mtype)
        except ValueError:
            return jsonify({"error": f"Invalid metric type: {mtype}",
                            "code": "INVALID_TYPE"}), 400
        try:
            mf = reg.register(name, help_text, mt)
        except (PermissionError, RuntimeError) as exc:
            return jsonify({"error": str(exc),
                            "code": "GATE_REJECTED"}), 403
        return jsonify({"name": mf.name, "type": mf.metric_type.value,
                        "help": mf.help_text}), 201

    @bp.route("/api/metrics/health", methods=["GET"])
    def metrics_health():
        """Health check for the metrics subsystem."""
        return jsonify({
            "status": "healthy",
            "family_count": reg.family_count(),
            "subsystem": "prometheus_metrics_exporter",
        })

    require_blueprint_auth(bp)
    return bp
