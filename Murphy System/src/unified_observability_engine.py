"""
Unified Observability Engine for the Murphy System.

Design Label: OBS-010 — Unified Observability Dashboard Engine
Owner: Platform Engineering / DevOps Team
Dependencies:
  - EventBackbone (subscribes to lifecycle events, publishes ALERT_FIRED /
    ALERT_RESOLVED / ANOMALY_DETECTED)
  - PersistenceManager (optional — for durable metric snapshots)

Aggregates metrics from ALL subsystems (SelfFixLoop, HeartbeatMonitor,
SupervisionTree, ChaosResilienceLoop, BotInventory, CircuitBreakers) into a
single queryable store.  Computes real-time system health scores, provides
trend analysis and anomaly detection, and generates human-readable health
reports.

Architecture:
  MetricPoint  ──┐
  MetricWindow   │  (per-metric circular buffer, O(1) append)
  SystemHealthScore
  UnifiedObservabilityEngine  ─── main façade
  AlertRule + AlertManager    ─── configurable thresholds

Safety invariants:
  - Bounded memory: circular buffers with configurable sizes
  - Non-blocking: metric recording is fast (lock-guarded list append)
  - Analysis runs on-demand, never in the background
  - Full audit trail via EventBackbone
  - Thread-safe: all shared state protected by a Lock

Follows OpenTelemetry naming conventions where applicable.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import math
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

try:
    from thread_safe_operations import capped_append, capped_append_paired
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)
    def capped_append_paired(*lists_and_items: Any, max_size: int = 10_000) -> None:
        """Fallback bounded paired append (CWE-770)."""
        pairs = list(zip(lists_and_items[::2], lists_and_items[1::2]))
        if not pairs:
            return
        ref_list = pairs[0][0]
        if len(ref_list) >= max_size:
            trim = max_size // 10
            for lst, _ in pairs:
                del lst[:trim]
        for lst, item in pairs:
            lst.append(item)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_WINDOW_SIZE = 1_000
_MAX_METRIC_HISTORY = 50_000      # global hard cap on total stored points


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class MetricType(str, Enum):
    """OpenTelemetry-compatible metric kinds."""

    COUNTER = "counter"
    """Monotonically increasing value (e.g. total gaps fixed)."""

    GAUGE = "gauge"
    """Instantaneous measurement (e.g. healthy_bots / total_bots)."""

    HISTOGRAM = "histogram"
    """Distribution of measured values (e.g. fix latency)."""


class TrendDirection(str, Enum):
    """Direction of a metric trend over a window."""

    RISING = "rising"
    FALLING = "falling"
    STABLE = "stable"


# ---------------------------------------------------------------------------
# MetricPoint
# ---------------------------------------------------------------------------

@dataclass
class MetricPoint:
    """A single observed measurement."""

    metric_name: str
    """Dot-separated name, e.g. 'self_fix_loop.gaps_fixed'."""

    value: float
    """Numeric observation."""

    timestamp: float = field(default_factory=time.time)
    """Unix epoch seconds (float)."""

    tags: Dict[str, str] = field(default_factory=dict)
    """Arbitrary key/value dimensions — component, severity, category."""

    metric_type: MetricType = MetricType.GAUGE

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric_name": self.metric_name,
            "value": self.value,
            "timestamp": self.timestamp,
            "tags": dict(self.tags),
            "metric_type": self.metric_type.value,
        }


# ---------------------------------------------------------------------------
# MetricWindow — sliding circular buffer for a single metric series
# ---------------------------------------------------------------------------

class MetricWindow:
    """Fixed-size circular buffer with statistical helpers.

    Design target: O(1) append, O(n) queries (n ≤ window_size).
    """

    def __init__(self, window_size: int = _DEFAULT_WINDOW_SIZE) -> None:
        if window_size < 1:
            raise ValueError("window_size must be >= 1")
        self._window_size = window_size
        self._values: deque = deque(maxlen=window_size)
        self._timestamps: deque = deque(maxlen=window_size)
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------

    def add(self, value: float, timestamp: Optional[float] = None) -> None:
        """Append a new observation to the window."""
        ts = timestamp if timestamp is not None else time.time()
        with self._lock:
            capped_append_paired(self._values, value, self._timestamps, ts)

    # ------------------------------------------------------------------
    # Accessors (return copies for thread safety)
    # ------------------------------------------------------------------

    def _snapshot(self) -> Tuple[List[float], List[float]]:
        """Return a consistent (values, timestamps) snapshot."""
        with self._lock:
            return list(self._values), list(self._timestamps)

    def __len__(self) -> int:
        with self._lock:
            return len(self._values)

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def mean(self) -> float:
        """Arithmetic mean; 0.0 if empty."""
        vals, _ = self._snapshot()
        if not vals:
            return 0.0
        return sum(vals) / (len(vals) or 1)

    def _percentile(self, p: float) -> float:
        """Return the p-th percentile (0–100) using linear interpolation."""
        vals, _ = self._snapshot()
        if not vals:
            return 0.0
        sorted_vals = sorted(vals)
        n = len(sorted_vals)
        if n == 1:
            return sorted_vals[0]
        rank = p / 100.0 * (n - 1)
        lower = int(rank)
        upper = min(lower + 1, n - 1)
        frac = rank - lower
        return sorted_vals[lower] * (1 - frac) + sorted_vals[upper] * frac

    def p50(self) -> float:
        """50th percentile (median)."""
        return self._percentile(50)

    def p95(self) -> float:
        """95th percentile."""
        return self._percentile(95)

    def p99(self) -> float:
        """99th percentile."""
        return self._percentile(99)

    def rate(self) -> float:
        """Change per second over the entire window.

        Computed as (last_value - first_value) / elapsed_seconds.
        Returns 0.0 when the window has fewer than 2 points or elapsed ≤ 0.
        """
        vals, timestamps = self._snapshot()
        if len(vals) < 2:
            return 0.0
        elapsed = timestamps[-1] - timestamps[0]
        if elapsed <= 0:
            return 0.0
        return (vals[-1] - vals[0]) / elapsed

    def trend(self) -> TrendDirection:
        """Classify the trend using an ordinary least-squares slope.

        Returns RISING if slope > +epsilon, FALLING if slope < -epsilon,
        STABLE otherwise.  Epsilon is 1% of the absolute mean to avoid
        noise in near-flat series.
        """
        vals, timestamps = self._snapshot()
        if len(vals) < 2:
            return TrendDirection.STABLE

        n = len(vals)
        # Normalise timestamps to seconds from first point
        t0 = timestamps[0]
        xs = [t - t0 for t in timestamps]
        ys = vals

        mean_x = sum(xs) / (n or 1)
        mean_y = sum(ys) / (n or 1)
        numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
        denominator = sum((x - mean_x) ** 2 for x in xs)
        if denominator == 0:
            return TrendDirection.STABLE
        slope = numerator / denominator

        epsilon = abs(mean_y) * 0.01 if mean_y != 0 else 1e-9
        if slope > epsilon:
            return TrendDirection.RISING
        if slope < -epsilon:
            return TrendDirection.FALLING
        return TrendDirection.STABLE

    def anomaly_score(self) -> float:
        """Z-score–based anomaly score for the most recent value.

        Returns a value in [0.0, 1.0] where 1.0 means the last observation
        is 3+ standard deviations from the window mean.
        """
        vals, _ = self._snapshot()
        if len(vals) < 3:
            return 0.0
        mean_v = sum(vals) / (len(vals) or 1)
        variance = sum((v - mean_v) ** 2 for v in vals) / (len(vals) or 1)
        std_dev = math.sqrt(variance)
        if std_dev == 0:
            return 0.0
        z = abs(vals[-1] - mean_v) / std_dev
        # Normalise to [0, 1]; z ≥ 3 → score = 1.0
        return min(z / 3.0, 1.0)


# ---------------------------------------------------------------------------
# SystemHealthScore
# ---------------------------------------------------------------------------

@dataclass
class SystemHealthScore:
    """Snapshot of aggregate system health."""

    overall: float
    """Weighted average health across all components; range [0.0, 1.0]."""

    components: Dict[str, float] = field(default_factory=dict)
    """Per-component health score; range [0.0, 1.0]."""

    alerts: List[str] = field(default_factory=list)
    """Human-readable active alerts at the time of computation."""

    computed_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall": round(self.overall, 4),
            "components": {k: round(v, 4) for k, v in self.components.items()},
            "alerts": list(self.alerts),
            "computed_at": self.computed_at,
        }


# ---------------------------------------------------------------------------
# AlertRule  &  AlertManager
# ---------------------------------------------------------------------------

class AlertSeverity(str, Enum):
    """Severity levels for alert rules."""

    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


@dataclass
class AlertRule:
    """Declarative rule: fire when *metric* has exceeded *threshold*
    for *window_seconds* (rolling).

    Example::

        AlertRule(
            rule_id="cb-trips-high",
            name="Circuit Breaker Trip Storm",
            metric_name="circuit_breaker.trips",
            threshold=3.0,
            window_seconds=300,
            severity=AlertSeverity.CRITICAL,
            description="More than 3 circuit-breaker trips in 5 min",
        )
    """

    rule_id: str
    name: str
    metric_name: str
    threshold: float
    window_seconds: float = 300.0
    severity: AlertSeverity = AlertSeverity.WARNING
    description: str = ""
    enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "metric_name": self.metric_name,
            "threshold": self.threshold,
            "window_seconds": self.window_seconds,
            "severity": self.severity.value,
            "description": self.description,
            "enabled": self.enabled,
        }


@dataclass
class FiredAlert:
    """Record of a triggered alert."""

    alert_id: str
    rule_id: str
    rule_name: str
    severity: AlertSeverity
    metric_name: str
    observed_value: float
    threshold: float
    message: str = ""
    fired_at: float = field(default_factory=time.time)
    resolved_at: Optional[float] = None

    @property
    def is_active(self) -> bool:
        return self.resolved_at is None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "severity": self.severity.value,
            "metric_name": self.metric_name,
            "observed_value": round(self.observed_value, 4),
            "threshold": self.threshold,
            "message": self.message,
            "fired_at": self.fired_at,
            "resolved_at": self.resolved_at,
            "is_active": self.is_active,
        }


class AlertManager:
    """Evaluates AlertRules against current MetricWindows.

    Publishes ``ALERT_FIRED`` and ``ALERT_RESOLVED`` events to the
    optional EventBackbone.

    Thread-safe — all mutable state protected by ``_lock``.
    """

    def __init__(
        self,
        rules: Optional[List[AlertRule]] = None,
        event_backbone=None,
    ) -> None:
        self._lock = threading.Lock()
        self._backbone = event_backbone
        self._rules: Dict[str, AlertRule] = {}
        # rule_id → FiredAlert (None if resolved / never fired)
        self._active: Dict[str, FiredAlert] = {}
        self._history: List[FiredAlert] = []

        for rule in (_default_alert_rules() if rules is None else rules):
            self._rules[rule.rule_id] = rule

    # ------------------------------------------------------------------
    # Rule management
    # ------------------------------------------------------------------

    def add_rule(self, rule: AlertRule) -> None:
        with self._lock:
            self._rules[rule.rule_id] = rule

    def remove_rule(self, rule_id: str) -> bool:
        with self._lock:
            removed = self._rules.pop(rule_id, None) is not None
            self._active.pop(rule_id, None)
            return removed

    def list_rules(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [r.to_dict() for r in self._rules.values()]

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    def evaluate_rules(
        self,
        windows: Dict[str, MetricWindow],
        now: Optional[float] = None,
    ) -> List[FiredAlert]:
        """Evaluate all enabled rules against the provided metric windows.

        Returns newly fired alerts.  Resolves previously active alerts
        when their conditions no longer hold.
        """
        if now is None:
            now = time.time()

        newly_fired: List[FiredAlert] = []

        with self._lock:
            for rule in self._rules.values():
                if not rule.enabled:
                    continue
                window = windows.get(rule.metric_name)
                if window is None:
                    # metric not yet recorded → condition not met → resolve
                    self._maybe_resolve(rule.rule_id, now)
                    continue

                vals, timestamps = window._snapshot()
                # Collect values inside the rolling window
                cutoff = now - rule.window_seconds
                recent = [v for v, t in zip(vals, timestamps) if t >= cutoff]
                if not recent:
                    self._maybe_resolve(rule.rule_id, now)
                    continue

                # Use the maximum observed value in the window to determine firing
                observed = max(recent)
                fires = observed > rule.threshold

                if fires:
                    existing = self._active.get(rule.rule_id)
                    if existing is None:
                        alert = FiredAlert(
                            alert_id=str(uuid.uuid4()),
                            rule_id=rule.rule_id,
                            rule_name=rule.name,
                            severity=rule.severity,
                            metric_name=rule.metric_name,
                            observed_value=observed,
                            threshold=rule.threshold,
                            message=(
                                rule.description
                                or f"{rule.metric_name} = {observed:.4g} > {rule.threshold}"
                            ),
                            fired_at=now,
                        )
                        self._active[rule.rule_id] = alert
                        capped_append(self._history, alert)
                        newly_fired.append(alert)
                        self._publish_event("ALERT_FIRED", alert)
                        logger.warning(
                            "Alert FIRED: %s (%s) — %s",
                            rule.name,
                            rule.severity.value,
                            alert.message,
                        )
                else:
                    self._maybe_resolve(rule.rule_id, now)

        return newly_fired

    def _maybe_resolve(self, rule_id: str, now: float) -> None:
        """Resolve an active alert (caller holds _lock)."""
        existing = self._active.pop(rule_id, None)
        if existing is not None:
            existing.resolved_at = now
            self._publish_event("ALERT_RESOLVED", existing)
            logger.info("Alert RESOLVED: %s", existing.rule_name)

    def _publish_event(self, kind: str, alert: FiredAlert) -> None:
        if self._backbone is None:
            return
        try:
            from event_backbone import EventType
            etype = (
                EventType.ALERT_FIRED
                if kind == "ALERT_FIRED"
                else EventType.ALERT_RESOLVED
            )
            self._backbone.publish(
                event_type=etype,
                payload=alert.to_dict(),
                source="unified_observability_engine",
            )
        except Exception as exc:
            logger.debug("AlertManager publish skipped: %s", exc)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_active_alerts(self) -> List[Dict[str, Any]]:
        """Return currently firing (unresolved) alerts."""
        with self._lock:
            return [a.to_dict() for a in self._active.values()]

    def get_alert_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self._lock:
            return [a.to_dict() for a in list(reversed(self._history[-limit:]))]

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total_rules": len(self._rules),
                "active_alerts": len(self._active),
                "total_fired_ever": len(self._history),
            }


def _default_alert_rules() -> List[AlertRule]:
    return [
        AlertRule(
            "obs-cb-trips",
            "Circuit Breaker Trip Storm",
            "circuit_breaker.trips",
            threshold=3.0,
            window_seconds=300.0,
            severity=AlertSeverity.CRITICAL,
            description="More than 3 circuit-breaker trips in 5 min",
        ),
        AlertRule(
            "obs-heartbeat-failed",
            "Heartbeat Failures",
            "heartbeat.bots_failed",
            threshold=0.0,
            window_seconds=60.0,
            severity=AlertSeverity.WARNING,
            description="One or more bots failing heartbeat",
        ),
        AlertRule(
            "obs-self-fix-gaps",
            "Unresolved Self-Fix Gaps",
            "self_fix_loop.gaps_remaining",
            threshold=10.0,
            window_seconds=600.0,
            severity=AlertSeverity.WARNING,
            description="More than 10 unresolved gaps in self-fix loop",
        ),
        AlertRule(
            "obs-supervision-failures",
            "Supervision Child Failures",
            "supervision_tree.child_failures",
            threshold=5.0,
            window_seconds=300.0,
            severity=AlertSeverity.CRITICAL,
            description="More than 5 child-process failures in 5 min",
        ),
    ]


# ---------------------------------------------------------------------------
# UnifiedObservabilityEngine
# ---------------------------------------------------------------------------

# Default weights for component health contributions to overall score
_DEFAULT_WEIGHTS: Dict[str, float] = {
    "self_fix_loop": 0.25,
    "heartbeat": 0.25,
    "supervision_tree": 0.25,
    "circuit_breaker": 0.25,
}


class UnifiedObservabilityEngine:
    """Aggregates metrics from all Murphy subsystems into a single store.

    Design Label: OBS-010
    Owner: Platform Engineering / DevOps Team

    Quick-start::

        engine = UnifiedObservabilityEngine(event_backbone=bb)
        engine.record_metric("heartbeat.bots_healthy", 12.0,
                             tags={"component": "heartbeat"})
        score = engine.compute_health_score()
        report = engine.generate_report()  # noqa: T201
    """

    def __init__(
        self,
        event_backbone=None,
        persistence_manager=None,
        window_size: int = _DEFAULT_WINDOW_SIZE,
        component_weights: Optional[Dict[str, float]] = None,
        alert_rules: Optional[List[AlertRule]] = None,
    ) -> None:
        self._backbone = event_backbone
        self._pm = persistence_manager
        self._window_size = window_size
        self._weights = dict(component_weights or _DEFAULT_WEIGHTS)
        self._lock = threading.Lock()

        # metric_name → MetricWindow
        self._windows: Dict[str, MetricWindow] = {}
        # Flat list of all MetricPoints for query support
        self._store: List[MetricPoint] = []

        self._alert_manager = AlertManager(
            rules=alert_rules,
            event_backbone=event_backbone,
        )

        if self._backbone is not None:
            self._subscribe_to_backbone()

    # ------------------------------------------------------------------
    # Metric ingestion
    # ------------------------------------------------------------------

    def record_metric(
        self,
        metric_name: str,
        value: float,
        tags: Optional[Dict[str, str]] = None,
        metric_type: MetricType = MetricType.GAUGE,
        timestamp: Optional[float] = None,
    ) -> MetricPoint:
        """Ingest a single metric observation.

        Thread-safe, O(1) amortised.
        """
        ts = timestamp if timestamp is not None else time.time()
        point = MetricPoint(
            metric_name=metric_name,
            value=value,
            timestamp=ts,
            tags=dict(tags or {}),
            metric_type=metric_type,
        )

        with self._lock:
            if metric_name not in self._windows:
                self._windows[metric_name] = MetricWindow(self._window_size)
            self._windows[metric_name].add(value, ts)
            capped_append(self._store, point, max_size=_MAX_METRIC_HISTORY)

        logger.debug("Metric recorded: %s = %s", metric_name, value)
        return point

    # ------------------------------------------------------------------
    # EventBackbone integration — auto-extract metrics from events
    # ------------------------------------------------------------------

    def record_event(self, event) -> None:
        """Process an event from the EventBackbone and extract metrics."""
        try:
            from event_backbone import EventType
            etype = event.event_type
            p = event.payload or {}

            if etype == EventType.SELF_FIX_COMPLETED:
                gaps_fixed = float(p.get("gaps_fixed", 1))
                gaps_remaining = float(p.get("gaps_remaining", 0))
                self.record_metric(
                    "self_fix_loop.gaps_fixed",
                    gaps_fixed,
                    tags={"component": "self_fix_loop"},
                    metric_type=MetricType.COUNTER,
                )
                self.record_metric(
                    "self_fix_loop.gaps_remaining",
                    gaps_remaining,
                    tags={"component": "self_fix_loop"},
                    metric_type=MetricType.GAUGE,
                )

            elif etype == EventType.SELF_FIX_STARTED:
                self.record_metric(
                    "self_fix_loop.runs_started",
                    1.0,
                    tags={"component": "self_fix_loop"},
                    metric_type=MetricType.COUNTER,
                )

            elif etype == EventType.SELF_FIX_ROLLED_BACK:
                self.record_metric(
                    "self_fix_loop.rollbacks",
                    1.0,
                    tags={"component": "self_fix_loop"},
                    metric_type=MetricType.COUNTER,
                )

            elif etype == EventType.BOT_HEARTBEAT_OK:
                healthy = float(p.get("healthy_bots", p.get("bots_healthy", 1)))
                total = float(p.get("total_bots", healthy))
                self.record_metric(
                    "heartbeat.bots_healthy",
                    healthy,
                    tags={"component": "heartbeat"},
                    metric_type=MetricType.GAUGE,
                )
                self.record_metric(
                    "heartbeat.bots_total",
                    total,
                    tags={"component": "heartbeat"},
                    metric_type=MetricType.GAUGE,
                )

            elif etype == EventType.BOT_HEARTBEAT_FAILED:
                self.record_metric(
                    "heartbeat.bots_failed",
                    float(p.get("failed_bots", 1)),
                    tags={"component": "heartbeat"},
                    metric_type=MetricType.COUNTER,
                )

            elif etype == EventType.SUPERVISOR_CHILD_RESTARTED:
                self.record_metric(
                    "supervision_tree.child_restarts",
                    1.0,
                    tags={"component": "supervision_tree"},
                    metric_type=MetricType.COUNTER,
                )
                running = float(p.get("running_components", 0))
                total = float(p.get("total_components", 0))
                if total > 0:
                    self.record_metric(
                        "supervision_tree.running_components",
                        running,
                        tags={"component": "supervision_tree"},
                        metric_type=MetricType.GAUGE,
                    )
                    self.record_metric(
                        "supervision_tree.total_components",
                        total,
                        tags={"component": "supervision_tree"},
                        metric_type=MetricType.GAUGE,
                    )

            elif etype == EventType.SUPERVISOR_CHILD_FAILED:
                self.record_metric(
                    "supervision_tree.child_failures",
                    1.0,
                    tags={"component": "supervision_tree"},
                    metric_type=MetricType.COUNTER,
                )

            elif etype == EventType.SYSTEM_HEALTH:
                cb_closed = float(p.get("closed_breakers", 0))
                cb_total = float(p.get("total_breakers", 0))
                cb_trips = float(p.get("circuit_breaker_trips", 0))
                if cb_total > 0:
                    self.record_metric(
                        "circuit_breaker.closed_breakers",
                        cb_closed,
                        tags={"component": "circuit_breaker"},
                        metric_type=MetricType.GAUGE,
                    )
                    self.record_metric(
                        "circuit_breaker.total_breakers",
                        cb_total,
                        tags={"component": "circuit_breaker"},
                        metric_type=MetricType.GAUGE,
                    )
                if cb_trips > 0:
                    self.record_metric(
                        "circuit_breaker.trips",
                        cb_trips,
                        tags={"component": "circuit_breaker"},
                        metric_type=MetricType.COUNTER,
                    )

        except Exception as exc:
            logger.debug("record_event extraction skipped: %s", exc)

    def _subscribe_to_backbone(self) -> None:
        try:
            from event_backbone import EventType
            relevant = [
                EventType.SELF_FIX_COMPLETED,
                EventType.SELF_FIX_STARTED,
                EventType.SELF_FIX_ROLLED_BACK,
                EventType.BOT_HEARTBEAT_OK,
                EventType.BOT_HEARTBEAT_FAILED,
                EventType.SUPERVISOR_CHILD_RESTARTED,
                EventType.SUPERVISOR_CHILD_FAILED,
                EventType.SYSTEM_HEALTH,
            ]
            for etype in relevant:
                self._backbone.subscribe(etype, self.record_event)
            logger.debug("UnifiedObservabilityEngine subscribed to %d event types", len(relevant))
        except Exception as exc:
            logger.warning("Could not subscribe to EventBackbone: %s", exc)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def query(
        self,
        metric_name: str,
        time_range: Optional[Tuple[float, float]] = None,
        tags: Optional[Dict[str, str]] = None,
    ) -> List[MetricPoint]:
        """Query metric history.

        Args:
            metric_name: Exact metric name to filter on.
            time_range: Optional ``(start_ts, end_ts)`` Unix epoch tuple.
            tags: Optional tag filters — all provided tags must match.

        Returns:
            List of MetricPoints matching the criteria, oldest first.
        """
        with self._lock:
            points = [p for p in self._store if p.metric_name == metric_name]

        if time_range is not None:
            start, end = time_range
            points = [p for p in points if start <= p.timestamp <= end]

        if tags:
            def _matches(pt: MetricPoint) -> bool:
                return all(pt.tags.get(k) == v for k, v in tags.items())
            points = [p for p in points if _matches(p)]

        return points

    def get_metric_names(self) -> List[str]:
        """Return sorted list of all recorded metric names."""
        with self._lock:
            return sorted(self._windows.keys())

    def _latest_value(self, metric_name: str) -> Optional[float]:
        """Return the most recent value for a metric, or None."""
        pts = self.query(metric_name)
        if not pts:
            return None
        return pts[-1].value

    # ------------------------------------------------------------------
    # Health score computation
    # ------------------------------------------------------------------

    def compute_health_score(self) -> SystemHealthScore:
        """Aggregate all metrics into a SystemHealthScore.

        Formula per component:

        * **self_fix_loop**: ``gaps_remaining == 0 → 1.0``, else
          ``max(0, 1 - gaps_remaining / max_gaps)`` where
          ``max_gaps = gaps_fixed + gaps_remaining``.
        * **heartbeat**: ``healthy_bots / total_bots`` (from most recent values).
        * **supervision_tree**: ``running_components / total_components``.
        * **circuit_breaker**: ``closed_breakers / total_breakers``.

        Overall score = weighted average of component scores.
        """
        components: Dict[str, float] = {}

        # --- self_fix_loop ---
        gaps_remaining = self._latest_value("self_fix_loop.gaps_remaining")
        gaps_fixed = self._latest_value("self_fix_loop.gaps_fixed")
        if gaps_remaining is not None:
            total_gaps = (gaps_fixed or 0) + gaps_remaining
            if total_gaps <= 0 or gaps_remaining <= 0:
                components["self_fix_loop"] = 1.0
            else:
                components["self_fix_loop"] = max(0.0, 1.0 - gaps_remaining / (total_gaps or 1))
        else:
            components["self_fix_loop"] = 1.0  # no data → assume healthy

        # --- heartbeat ---
        healthy_bots = self._latest_value("heartbeat.bots_healthy")
        total_bots = self._latest_value("heartbeat.bots_total")
        if healthy_bots is not None and total_bots is not None and total_bots > 0:
            components["heartbeat"] = max(0.0, min(1.0, healthy_bots / total_bots))
        else:
            components["heartbeat"] = 1.0

        # --- supervision_tree ---
        running = self._latest_value("supervision_tree.running_components")
        total_comp = self._latest_value("supervision_tree.total_components")
        if running is not None and total_comp is not None and total_comp > 0:
            components["supervision_tree"] = max(0.0, min(1.0, running / total_comp))
        else:
            components["supervision_tree"] = 1.0

        # --- circuit_breaker ---
        closed_cb = self._latest_value("circuit_breaker.closed_breakers")
        total_cb = self._latest_value("circuit_breaker.total_breakers")
        if closed_cb is not None and total_cb is not None and total_cb > 0:
            components["circuit_breaker"] = max(0.0, min(1.0, closed_cb / total_cb))
        else:
            components["circuit_breaker"] = 1.0

        # Weighted average
        with self._lock:
            windows_snapshot = dict(self._windows)

        active_alerts = self._alert_manager.evaluate_rules(windows_snapshot)
        alert_messages = self._alert_manager.get_active_alerts()
        alert_texts = [a["message"] for a in alert_messages]

        total_weight = sum(
            self._weights.get(k, 0.0) for k in components
        )
        if total_weight <= 0:
            overall = sum(components.values()) / (len(components) or 1)
        else:
            overall = sum(
                components[k] * self._weights.get(k, 0.0) for k in components
            ) / total_weight

        return SystemHealthScore(
            overall=max(0.0, min(1.0, overall)),
            components=components,
            alerts=alert_texts,
            computed_at=time.time(),
        )

    # ------------------------------------------------------------------
    # Anomaly detection
    # ------------------------------------------------------------------

    def detect_anomalies(self, threshold: float = 0.7) -> List[str]:
        """Scan all metrics for anomalies.

        Returns a list of human-readable alert strings for any metric
        whose anomaly_score() exceeds ``threshold`` (default 0.7).
        """
        alerts: List[str] = []
        with self._lock:
            items = list(self._windows.items())

        for name, window in items:
            score = window.anomaly_score()
            if score >= threshold:
                direction = window.trend().value
                alerts.append(
                    f"ANOMALY [{name}]: score={score:.2f}, "
                    f"trend={direction}, last_value={window._snapshot()[0][-1] if window._snapshot()[0] else 'N/A'}"
                )
        return alerts

    # ------------------------------------------------------------------
    # Report generation
    # ------------------------------------------------------------------

    def generate_report(self) -> str:
        """Produce a human-readable Markdown health report."""
        score = self.compute_health_score()
        anomalies = self.detect_anomalies()
        now_str = datetime.fromtimestamp(score.computed_at, tz=timezone.utc).isoformat()

        lines: List[str] = [
            "# Murphy System — Health Report",
            "",
            f"**Generated:** {now_str}",
            f"**Overall Health:** {score.overall:.1%}",
            "",
            "## Component Health Scores",
            "",
        ]

        for component, value in sorted(score.components.items()):
            bar = _make_bar(value)
            lines.append(f"- **{component}**: {value:.1%} {bar}")

        lines += ["", "## Active Alerts", ""]
        if score.alerts:
            for alert in score.alerts:
                lines.append(f"- ⚠ {alert}")
        else:
            lines.append("- ✅ No active alerts")

        lines += ["", "## Anomaly Detection", ""]
        if anomalies:
            for a in anomalies:
                lines.append(f"- 🔴 {a}")
        else:
            lines.append("- ✅ No anomalies detected")

        lines += ["", "## Metric Summary", ""]
        with self._lock:
            metric_names = sorted(self._windows.keys())

        for name in metric_names:
            with self._lock:
                w = self._windows.get(name)
            if w is None:
                continue
            trend = w.trend().value
            mean_v = w.mean()
            p95_v = w.p95()
            n = len(w)
            lines.append(
                f"| `{name}` | n={n} | mean={mean_v:.4g} | "
                f"p95={p95_v:.4g} | trend={trend} |"
            )

        lines += [""]
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Dashboard data
    # ------------------------------------------------------------------

    def get_dashboard_data(self) -> Dict[str, Any]:
        """Return a structured dict suitable for rendering a dashboard."""
        score = self.compute_health_score()
        anomalies = self.detect_anomalies()

        metric_summaries: Dict[str, Any] = {}
        with self._lock:
            items = list(self._windows.items())

        for name, window in items:
            metric_summaries[name] = {
                "count": len(window),
                "mean": round(window.mean(), 4),
                "p50": round(window.p50(), 4),
                "p95": round(window.p95(), 4),
                "p99": round(window.p99(), 4),
                "rate": round(window.rate(), 6),
                "trend": window.trend().value,
                "anomaly_score": round(window.anomaly_score(), 4),
            }

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "health_score": score.to_dict(),
            "metrics": metric_summaries,
            "active_alerts": self._alert_manager.get_active_alerts(),
            "anomalies": anomalies,
            "alert_manager_status": self._alert_manager.get_status(),
        }

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            n_metrics = len(self._windows)
            n_points = len(self._store)
        return {
            "status": "ok",
            "metrics_tracked": n_metrics,
            "total_points_stored": n_points,
            "window_size": self._window_size,
            "backbone_attached": self._backbone is not None,
            "persistence_attached": self._pm is not None,
            "alert_manager": self._alert_manager.get_status(),
        }


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _make_bar(value: float, width: int = 10) -> str:
    """Return a simple ASCII progress bar for a 0–1 value."""
    filled = round(value * width)
    return "[" + "█" * filled + "░" * (width - filled) + "]"
