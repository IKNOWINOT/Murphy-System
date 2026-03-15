"""Advanced analytics dashboard for Murphy System (RECOMMENDATIONS 6.2.5).

Provides execution analytics, compliance tracking, performance metrics,
business intelligence, real-time dashboard generation, and an alert rules engine.
All operations are thread-safe and return JSON-serializable dictionaries.
"""

import logging
import math
import statistics
import threading
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Supported metric types."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    RATE = "rate"


class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertState(Enum):
    """Alert rule states."""
    OK = "ok"
    FIRING = "firing"
    RESOLVED = "resolved"


class WidgetType(Enum):
    """Dashboard widget types."""
    LINE_CHART = "line_chart"
    BAR_CHART = "bar_chart"
    PIE_CHART = "pie_chart"
    TABLE = "table"
    GAUGE = "gauge"
    COUNTER = "counter"
    HEATMAP = "heatmap"


@dataclass
class TaskExecution:
    """Record of a single task execution."""
    task_id: str
    task_type: str
    start_time: float
    end_time: float
    success: bool
    error_message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def latency(self) -> float:
        return self.end_time - self.start_time

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "success": self.success,
            "latency": self.latency,
            "error_message": self.error_message,
            "metadata": self.metadata.copy(),
        }


@dataclass
class ComplianceRecord:
    """A single compliance assessment record."""
    record_id: str
    timestamp: float
    category: str
    score: float
    violations: List[str] = field(default_factory=list)
    remediated: bool = False
    remediation_time: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "timestamp": self.timestamp,
            "category": self.category,
            "score": self.score,
            "violations": list(self.violations),
            "remediated": self.remediated,
            "remediation_time": self.remediation_time,
        }


@dataclass
class PerformanceSample:
    """A single performance measurement."""
    timestamp: float
    cpu_percent: float
    memory_percent: float
    api_response_ms: float
    queue_depth: int
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "cpu_percent": self.cpu_percent,
            "memory_percent": self.memory_percent,
            "api_response_ms": self.api_response_ms,
            "queue_depth": self.queue_depth,
            "metadata": self.metadata.copy(),
        }


@dataclass
class AlertRule:
    """Definition of an alert threshold rule."""
    rule_id: str
    name: str
    metric_name: str
    condition: str  # "gt", "lt", "gte", "lte", "eq"
    threshold: float
    severity: AlertSeverity = AlertSeverity.WARNING
    cooldown_seconds: float = 60.0
    state: AlertState = AlertState.OK
    last_triggered: Optional[float] = None
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "metric_name": self.metric_name,
            "condition": self.condition,
            "threshold": self.threshold,
            "severity": self.severity.value,
            "cooldown_seconds": self.cooldown_seconds,
            "state": self.state.value,
            "last_triggered": self.last_triggered,
            "description": self.description,
        }


CONDITION_OPS: Dict[str, Callable[[float, float], bool]] = {
    "gt": lambda v, t: v > t,
    "lt": lambda v, t: v < t,
    "gte": lambda v, t: v >= t,
    "lte": lambda v, t: v <= t,
    "eq": lambda v, t: v == t,
}


# ---------------------------------------------------------------------------
# Execution Analytics
# ---------------------------------------------------------------------------

class ExecutionAnalytics:
    """Track task execution counts, success/failure rates, latency, throughput."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._executions: List[TaskExecution] = []
        self._counts_by_type: Dict[str, int] = defaultdict(int)
        self._success_by_type: Dict[str, int] = defaultdict(int)
        self._failure_by_type: Dict[str, int] = defaultdict(int)

    def record_execution(self, task_type: str, start_time: float,
                         end_time: float, success: bool,
                         error_message: str = "",
                         metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Record a task execution and return the record."""
        if end_time < start_time:
            raise ValueError("end_time must be >= start_time")
        task_id = str(uuid.uuid4())
        execution = TaskExecution(
            task_id=task_id, task_type=task_type,
            start_time=start_time, end_time=end_time,
            success=success, error_message=error_message,
            metadata=metadata or {},
        )
        with self._lock:
            capped_append(self._executions, execution)
            self._counts_by_type[task_type] += 1
            if success:
                self._success_by_type[task_type] += 1
            else:
                self._failure_by_type[task_type] += 1
        logger.debug("Recorded execution %s type=%s success=%s", task_id, task_type, success)
        return execution.to_dict()

    def get_success_rate(self, task_type: Optional[str] = None) -> Dict[str, Any]:
        """Return success/failure rates, optionally filtered by task type."""
        with self._lock:
            execs = self._executions
            if task_type:
                execs = [e for e in execs if e.task_type == task_type]
            total = len(execs)
            successes = sum(1 for e in execs if e.success)
            failures = total - successes
        return {
            "task_type": task_type,
            "total": total,
            "successes": successes,
            "failures": failures,
            "success_rate": successes / total if total else 0.0,
            "failure_rate": failures / total if total else 0.0,
        }

    def get_latency_distribution(self, task_type: Optional[str] = None) -> Dict[str, Any]:
        """Return latency statistics (min, max, mean, median, p95, p99)."""
        with self._lock:
            execs = self._executions
            if task_type:
                execs = [e for e in execs if e.task_type == task_type]
            latencies = [e.latency for e in execs]
        if not latencies:
            return {"task_type": task_type, "count": 0, "min": 0, "max": 0,
                    "mean": 0, "median": 0, "p95": 0, "p99": 0, "stdev": 0}
        sorted_lat = sorted(latencies)
        n = len(sorted_lat)
        p95_idx = min(int(n * 0.95), n - 1)
        p99_idx = min(int(n * 0.99), n - 1)
        return {
            "task_type": task_type,
            "count": n,
            "min": sorted_lat[0],
            "max": sorted_lat[-1],
            "mean": statistics.mean(sorted_lat),
            "median": statistics.median(sorted_lat),
            "p95": sorted_lat[p95_idx],
            "p99": sorted_lat[p99_idx],
            "stdev": statistics.stdev(sorted_lat) if n > 1 else 0.0,
        }

    def get_throughput(self, window_seconds: float = 60.0) -> Dict[str, Any]:
        """Return throughput (tasks/sec) over a sliding window."""
        now = time.time()
        with self._lock:
            recent = [e for e in self._executions
                      if e.end_time >= now - window_seconds]
        count = len(recent)
        return {
            "window_seconds": window_seconds,
            "task_count": count,
            "throughput_per_second": count / window_seconds if window_seconds > 0 else 0.0,
        }

    def get_counts_by_type(self) -> Dict[str, Any]:
        """Return execution counts grouped by task type."""
        with self._lock:
            return {
                "counts": dict(self._counts_by_type),
                "successes": dict(self._success_by_type),
                "failures": dict(self._failure_by_type),
                "total": sum(self._counts_by_type.values()),
            }

    def get_summary(self) -> Dict[str, Any]:
        """Return a comprehensive execution summary."""
        return {
            "counts": self.get_counts_by_type(),
            "success_rate": self.get_success_rate(),
            "latency": self.get_latency_distribution(),
            "throughput": self.get_throughput(),
        }


# ---------------------------------------------------------------------------
# Compliance Analytics
# ---------------------------------------------------------------------------

class ComplianceAnalytics:
    """Track compliance scores, violation trends, remediation effectiveness."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._records: List[ComplianceRecord] = []

    def record_assessment(self, category: str, score: float,
                          violations: Optional[List[str]] = None,
                          remediated: bool = False,
                          remediation_time: Optional[float] = None) -> Dict[str, Any]:
        """Record a compliance assessment."""
        if not 0.0 <= score <= 100.0:
            raise ValueError("score must be between 0 and 100")
        record = ComplianceRecord(
            record_id=str(uuid.uuid4()),
            timestamp=time.time(),
            category=category,
            score=score,
            violations=violations or [],
            remediated=remediated,
            remediation_time=remediation_time,
        )
        with self._lock:
            capped_append(self._records, record)
        logger.debug("Recorded compliance assessment %s category=%s score=%.1f",
                      record.record_id, category, score)
        return record.to_dict()

    def get_scores_over_time(self, category: Optional[str] = None) -> Dict[str, Any]:
        """Return compliance scores as a time series."""
        with self._lock:
            recs = self._records
            if category:
                recs = [r for r in recs if r.category == category]
            data = [{"timestamp": r.timestamp, "score": r.score, "category": r.category}
                    for r in recs]
        avg = statistics.mean([d["score"] for d in data]) if data else 0.0
        return {"category": category, "data_points": data, "average_score": avg,
                "count": len(data)}

    def get_violation_trends(self) -> Dict[str, Any]:
        """Return violation counts grouped by category."""
        with self._lock:
            by_cat: Dict[str, int] = defaultdict(int)
            total_violations = 0
            for r in self._records:
                count = len(r.violations)
                by_cat[r.category] += count
                total_violations += count
        return {"by_category": dict(by_cat), "total_violations": total_violations}

    def get_remediation_effectiveness(self) -> Dict[str, Any]:
        """Return remediation statistics."""
        with self._lock:
            with_violations = [r for r in self._records if r.violations]
            remediated = [r for r in with_violations if r.remediated]
            times = [r.remediation_time for r in remediated
                     if r.remediation_time is not None]
        total = len(with_violations)
        rem_count = len(remediated)
        return {
            "total_with_violations": total,
            "remediated_count": rem_count,
            "remediation_rate": rem_count / total if total else 0.0,
            "avg_remediation_time": statistics.mean(times) if times else 0.0,
            "min_remediation_time": min(times) if times else 0.0,
            "max_remediation_time": max(times) if times else 0.0,
        }

    def get_summary(self) -> Dict[str, Any]:
        """Return a comprehensive compliance summary."""
        return {
            "scores": self.get_scores_over_time(),
            "violations": self.get_violation_trends(),
            "remediation": self.get_remediation_effectiveness(),
        }


# ---------------------------------------------------------------------------
# Performance Metrics
# ---------------------------------------------------------------------------

class PerformanceMetrics:
    """Track system performance: CPU, memory, API response times, queue depths."""

    def __init__(self, max_samples: int = 10000) -> None:
        self._lock = threading.RLock()
        self._samples: List[PerformanceSample] = []
        self._max_samples = max_samples

    def record_sample(self, cpu_percent: float, memory_percent: float,
                      api_response_ms: float, queue_depth: int,
                      metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Record a performance sample."""
        sample = PerformanceSample(
            timestamp=time.time(),
            cpu_percent=cpu_percent,
            memory_percent=memory_percent,
            api_response_ms=api_response_ms,
            queue_depth=queue_depth,
            metadata=metadata or {},
        )
        with self._lock:
            self._samples.append(sample)
            if len(self._samples) > self._max_samples:
                self._samples = self._samples[-self._max_samples:]
        return sample.to_dict()

    def get_cpu_trends(self, last_n: int = 100) -> Dict[str, Any]:
        """Return CPU usage trend data."""
        with self._lock:
            samples = self._samples[-last_n:]
            values = [s.cpu_percent for s in samples]
        return self._build_trend("cpu_percent", values)

    def get_memory_trends(self, last_n: int = 100) -> Dict[str, Any]:
        """Return memory usage trend data."""
        with self._lock:
            samples = self._samples[-last_n:]
            values = [s.memory_percent for s in samples]
        return self._build_trend("memory_percent", values)

    def get_api_response_trends(self, last_n: int = 100) -> Dict[str, Any]:
        """Return API response time trend data."""
        with self._lock:
            samples = self._samples[-last_n:]
            values = [s.api_response_ms for s in samples]
        return self._build_trend("api_response_ms", values)

    def get_queue_depth_trends(self, last_n: int = 100) -> Dict[str, Any]:
        """Return queue depth trend data."""
        with self._lock:
            samples = self._samples[-last_n:]
            values = [float(s.queue_depth) for s in samples]
        return self._build_trend("queue_depth", values)

    @staticmethod
    def _build_trend(metric_name: str, values: List[float]) -> Dict[str, Any]:
        if not values:
            return {"metric": metric_name, "count": 0, "min": 0, "max": 0,
                    "mean": 0, "latest": 0}
        return {
            "metric": metric_name,
            "count": len(values),
            "min": min(values),
            "max": max(values),
            "mean": statistics.mean(values),
            "latest": values[-1],
        }

    def get_summary(self) -> Dict[str, Any]:
        """Return comprehensive performance summary."""
        return {
            "cpu": self.get_cpu_trends(),
            "memory": self.get_memory_trends(),
            "api_response": self.get_api_response_trends(),
            "queue_depth": self.get_queue_depth_trends(),
            "total_samples": len(self._samples),
        }


# ---------------------------------------------------------------------------
# Business Intelligence
# ---------------------------------------------------------------------------

class BusinessIntelligence:
    """Cost per task, ROI, automation savings, productivity gains."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._task_costs: List[Dict[str, Any]] = []
        self._manual_baseline: Dict[str, float] = {}
        self._automation_savings: List[Dict[str, Any]] = []

    def record_task_cost(self, task_type: str, cost: float,
                         duration_seconds: float,
                         automated: bool = True) -> Dict[str, Any]:
        """Record the cost of executing a task."""
        if cost < 0:
            raise ValueError("cost must be non-negative")
        entry = {
            "id": str(uuid.uuid4()),
            "task_type": task_type,
            "cost": cost,
            "duration_seconds": duration_seconds,
            "automated": automated,
            "timestamp": time.time(),
        }
        with self._lock:
            capped_append(self._task_costs, entry)
        return entry.copy()

    def set_manual_baseline(self, task_type: str, cost_per_task: float) -> Dict[str, Any]:
        """Set the manual (non-automated) cost baseline for a task type."""
        with self._lock:
            self._manual_baseline[task_type] = cost_per_task
        return {"task_type": task_type, "manual_cost_per_task": cost_per_task}

    def get_cost_per_task(self, task_type: Optional[str] = None) -> Dict[str, Any]:
        """Return average cost per task, optionally by type."""
        with self._lock:
            entries = self._task_costs
            if task_type:
                entries = [e for e in entries if e["task_type"] == task_type]
        if not entries:
            return {"task_type": task_type, "count": 0, "total_cost": 0,
                    "avg_cost": 0}
        total = sum(e["cost"] for e in entries)
        return {
            "task_type": task_type,
            "count": len(entries),
            "total_cost": total,
            "avg_cost": total / (len(entries) or 1),
        }

    def get_roi(self, task_type: str) -> Dict[str, Any]:
        """Calculate ROI comparing automated vs manual baseline cost."""
        with self._lock:
            baseline = self._manual_baseline.get(task_type)
            entries = [e for e in self._task_costs
                       if e["task_type"] == task_type and e["automated"]]
        if baseline is None or not entries:
            return {"task_type": task_type, "roi_percent": 0.0,
                    "savings_per_task": 0.0, "total_savings": 0.0,
                    "baseline_set": baseline is not None, "task_count": len(entries)}
        avg_auto = sum(e["cost"] for e in entries) / (len(entries) or 1)
        savings_per_task = baseline - avg_auto
        total_savings = savings_per_task * len(entries)
        roi = (total_savings / (avg_auto * len(entries)) * 100) if avg_auto > 0 else 0.0
        return {
            "task_type": task_type,
            "manual_baseline": baseline,
            "avg_automated_cost": avg_auto,
            "savings_per_task": savings_per_task,
            "total_savings": total_savings,
            "roi_percent": roi,
            "task_count": len(entries),
            "baseline_set": True,
        }

    def get_automation_savings(self) -> Dict[str, Any]:
        """Return total automation savings across all task types with baselines."""
        with self._lock:
            types = set(self._manual_baseline.keys())
        results: Dict[str, Any] = {}
        total_saved = 0.0
        for tt in types:
            roi = self.get_roi(tt)
            results[tt] = roi
            total_saved += roi.get("total_savings", 0.0)
        return {"by_type": results, "total_savings": total_saved}

    def get_productivity_gains(self) -> Dict[str, Any]:
        """Compare automated vs manual task durations."""
        with self._lock:
            auto = [e for e in self._task_costs if e["automated"]]
            manual = [e for e in self._task_costs if not e["automated"]]
        auto_avg = (statistics.mean([e["duration_seconds"] for e in auto])
                    if auto else 0.0)
        manual_avg = (statistics.mean([e["duration_seconds"] for e in manual])
                      if manual else 0.0)
        speedup = (manual_avg / auto_avg) if auto_avg > 0 else 0.0
        return {
            "automated_count": len(auto),
            "manual_count": len(manual),
            "avg_automated_duration": auto_avg,
            "avg_manual_duration": manual_avg,
            "speedup_factor": speedup,
            "time_saved_per_task": manual_avg - auto_avg if manual_avg > auto_avg else 0.0,
        }

    def get_summary(self) -> Dict[str, Any]:
        """Return comprehensive business intelligence summary."""
        return {
            "cost_per_task": self.get_cost_per_task(),
            "automation_savings": self.get_automation_savings(),
            "productivity": self.get_productivity_gains(),
        }


# ---------------------------------------------------------------------------
# Real-time Dashboard
# ---------------------------------------------------------------------------

class DashboardWidget:
    """A single dashboard widget configuration."""

    def __init__(self, widget_id: str, title: str,
                 widget_type: WidgetType,
                 data_source: str,
                 config: Optional[Dict[str, Any]] = None) -> None:
        self.widget_id = widget_id
        self.title = title
        self.widget_type = widget_type
        self.data_source = data_source
        self.config = config or {}
        self.data: Any = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "widget_id": self.widget_id,
            "title": self.title,
            "widget_type": self.widget_type.value,
            "data_source": self.data_source,
            "config": self.config.copy(),
            "data": self.data,
        }


class RealTimeDashboard:
    """Generate dashboard data structures for UI consumption."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._widgets: Dict[str, DashboardWidget] = {}
        self._layouts: Dict[str, List[str]] = {}
        self._data_providers: Dict[str, Callable[[], Any]] = {}

    def add_widget(self, title: str, widget_type: WidgetType,
                   data_source: str,
                   config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Add a widget to the dashboard."""
        widget_id = str(uuid.uuid4())
        widget = DashboardWidget(widget_id, title, widget_type, data_source, config)
        with self._lock:
            self._widgets[widget_id] = widget
        return widget.to_dict()

    def remove_widget(self, widget_id: str) -> Dict[str, Any]:
        """Remove a widget by ID."""
        with self._lock:
            if widget_id not in self._widgets:
                return {"removed": False, "error": "Widget not found"}
            del self._widgets[widget_id]
        return {"removed": True, "widget_id": widget_id}

    def register_data_provider(self, source_name: str,
                               provider: Callable[[], Any]) -> Dict[str, Any]:
        """Register a callable that provides data for a data source."""
        with self._lock:
            self._data_providers[source_name] = provider
        return {"registered": True, "source_name": source_name}

    def create_layout(self, layout_name: str,
                      widget_ids: List[str]) -> Dict[str, Any]:
        """Create a named layout of widgets."""
        with self._lock:
            missing = [wid for wid in widget_ids if wid not in self._widgets]
            if missing:
                return {"created": False, "error": f"Unknown widget IDs: {missing}"}
            self._layouts[layout_name] = list(widget_ids)
        return {"created": True, "layout_name": layout_name,
                "widget_count": len(widget_ids)}

    def get_dashboard_data(self, layout_name: Optional[str] = None) -> Dict[str, Any]:
        """Generate the complete dashboard data structure."""
        with self._lock:
            if layout_name and layout_name in self._layouts:
                widget_ids = self._layouts[layout_name]
                widgets = [self._widgets[wid] for wid in widget_ids
                           if wid in self._widgets]
            else:
                widgets = list(self._widgets.values())
            providers = dict(self._data_providers)

        result_widgets = []
        for w in widgets:
            d = w.to_dict()
            if w.data_source in providers:
                try:
                    d["data"] = providers[w.data_source]()
                except Exception as exc:
                    logger.debug("Caught exception: %s", exc)
                    d["data"] = {"error": str(exc)}
            result_widgets.append(d)

        return {
            "layout": layout_name,
            "widgets": result_widgets,
            "generated_at": time.time(),
            "widget_count": len(result_widgets),
        }

    def list_widgets(self) -> Dict[str, Any]:
        """List all registered widgets."""
        with self._lock:
            return {
                "widgets": [w.to_dict() for w in self._widgets.values()],
                "count": len(self._widgets),
            }

    def list_layouts(self) -> Dict[str, Any]:
        """List all defined layouts."""
        with self._lock:
            return {
                "layouts": {k: list(v) for k, v in self._layouts.items()},
                "count": len(self._layouts),
            }


# ---------------------------------------------------------------------------
# Alert Rules Engine
# ---------------------------------------------------------------------------

class AlertRulesEngine:
    """Define alert thresholds and trigger notifications on metric breaches."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._rules: Dict[str, AlertRule] = {}
        self._alerts_history: List[Dict[str, Any]] = []
        self._metric_values: Dict[str, float] = {}
        self._notification_callbacks: List[Callable[[Dict[str, Any]], None]] = []

    def add_rule(self, name: str, metric_name: str, condition: str,
                 threshold: float,
                 severity: AlertSeverity = AlertSeverity.WARNING,
                 cooldown_seconds: float = 60.0,
                 description: str = "") -> Dict[str, Any]:
        """Add an alert rule."""
        if condition not in CONDITION_OPS:
            raise ValueError(f"Invalid condition '{condition}'. "
                             f"Must be one of {list(CONDITION_OPS.keys())}")
        rule_id = str(uuid.uuid4())
        rule = AlertRule(
            rule_id=rule_id, name=name, metric_name=metric_name,
            condition=condition, threshold=threshold, severity=severity,
            cooldown_seconds=cooldown_seconds, description=description,
        )
        with self._lock:
            self._rules[rule_id] = rule
        logger.debug("Added alert rule %s: %s %s %s", rule_id, metric_name,
                      condition, threshold)
        return rule.to_dict()

    def remove_rule(self, rule_id: str) -> Dict[str, Any]:
        """Remove an alert rule."""
        with self._lock:
            if rule_id not in self._rules:
                return {"removed": False, "error": "Rule not found"}
            del self._rules[rule_id]
        return {"removed": True, "rule_id": rule_id}

    def register_notification_callback(
            self, callback: Callable[[Dict[str, Any]], None]) -> Dict[str, Any]:
        """Register a callback invoked when an alert fires."""
        with self._lock:
            capped_append(self._notification_callbacks, callback)
        return {"registered": True,
                "callback_count": len(self._notification_callbacks)}

    def update_metric(self, metric_name: str, value: float) -> Dict[str, Any]:
        """Update a metric value and evaluate all matching rules."""
        now = time.time()
        fired: List[Dict[str, Any]] = []
        resolved: List[Dict[str, Any]] = []
        with self._lock:
            self._metric_values[metric_name] = value
            for rule in self._rules.values():
                if rule.metric_name != metric_name:
                    continue
                op = CONDITION_OPS[rule.condition]
                breached = op(value, rule.threshold)
                if breached:
                    if rule.state != AlertState.FIRING:
                        if (rule.last_triggered is None or
                                now - rule.last_triggered >= rule.cooldown_seconds):
                            rule.state = AlertState.FIRING
                            rule.last_triggered = now
                            alert = self._create_alert_event(rule, value, now)
                            capped_append(self._alerts_history, alert)
                            fired.append(alert)
                else:
                    if rule.state == AlertState.FIRING:
                        rule.state = AlertState.RESOLVED
                        event = self._create_resolve_event(rule, value, now)
                        capped_append(self._alerts_history, event)
                        resolved.append(event)
            callbacks = list(self._notification_callbacks)

        for alert in fired:
            for cb in callbacks:
                try:
                    cb(alert)
                except Exception as exc:
                    logger.debug("Suppressed exception: %s", exc)
                    logger.exception("Alert callback failed")

        return {
            "metric_name": metric_name,
            "value": value,
            "fired": fired,
            "resolved": resolved,
        }

    @staticmethod
    def _create_alert_event(rule: AlertRule, value: float,
                            timestamp: float) -> Dict[str, Any]:
        return {
            "event": "alert_fired",
            "rule_id": rule.rule_id,
            "rule_name": rule.name,
            "metric_name": rule.metric_name,
            "condition": rule.condition,
            "threshold": rule.threshold,
            "current_value": value,
            "severity": rule.severity.value,
            "timestamp": timestamp,
        }

    @staticmethod
    def _create_resolve_event(rule: AlertRule, value: float,
                              timestamp: float) -> Dict[str, Any]:
        return {
            "event": "alert_resolved",
            "rule_id": rule.rule_id,
            "rule_name": rule.name,
            "metric_name": rule.metric_name,
            "current_value": value,
            "timestamp": timestamp,
        }

    def get_active_alerts(self) -> Dict[str, Any]:
        """Return all currently firing alert rules."""
        with self._lock:
            firing = [r.to_dict() for r in self._rules.values()
                      if r.state == AlertState.FIRING]
        return {"active_alerts": firing, "count": len(firing)}

    def get_alert_history(self, limit: int = 100) -> Dict[str, Any]:
        """Return recent alert events."""
        with self._lock:
            history = list(self._alerts_history[-limit:])
        return {"history": history, "count": len(history)}

    def get_rules(self) -> Dict[str, Any]:
        """List all defined alert rules."""
        with self._lock:
            rules = [r.to_dict() for r in self._rules.values()]
        return {"rules": rules, "count": len(rules)}

    def get_metric_values(self) -> Dict[str, Any]:
        """Return current metric values."""
        with self._lock:
            return {"metrics": dict(self._metric_values)}


# ---------------------------------------------------------------------------
# Unified Analytics Dashboard
# ---------------------------------------------------------------------------

class AnalyticsDashboard:
    """Unified analytics dashboard combining all analytics subsystems."""

    def __init__(self) -> None:
        self.execution = ExecutionAnalytics()
        self.compliance = ComplianceAnalytics()
        self.performance = PerformanceMetrics()
        self.business = BusinessIntelligence()
        self.dashboard = RealTimeDashboard()
        self.alerts = AlertRulesEngine()

    def get_full_report(self) -> Dict[str, Any]:
        """Generate a comprehensive analytics report."""
        return {
            "execution": self.execution.get_summary(),
            "compliance": self.compliance.get_summary(),
            "performance": self.performance.get_summary(),
            "business": self.business.get_summary(),
            "alerts": self.alerts.get_active_alerts(),
            "generated_at": time.time(),
        }

    def setup_default_dashboard(self) -> Dict[str, Any]:
        """Create a default dashboard layout with common widgets."""
        widgets = []

        w1 = self.dashboard.add_widget(
            "Execution Summary", WidgetType.COUNTER,
            "execution_summary")
        widgets.append(w1["widget_id"])

        w2 = self.dashboard.add_widget(
            "Latency Distribution", WidgetType.BAR_CHART,
            "latency_distribution")
        widgets.append(w2["widget_id"])

        w3 = self.dashboard.add_widget(
            "Compliance Scores", WidgetType.LINE_CHART,
            "compliance_scores")
        widgets.append(w3["widget_id"])

        w4 = self.dashboard.add_widget(
            "CPU Usage", WidgetType.GAUGE,
            "cpu_trends")
        widgets.append(w4["widget_id"])

        w5 = self.dashboard.add_widget(
            "Active Alerts", WidgetType.TABLE,
            "active_alerts")
        widgets.append(w5["widget_id"])

        # Register data providers
        self.dashboard.register_data_provider(
            "execution_summary", self.execution.get_summary)
        self.dashboard.register_data_provider(
            "latency_distribution", self.execution.get_latency_distribution)
        self.dashboard.register_data_provider(
            "compliance_scores", self.compliance.get_scores_over_time)
        self.dashboard.register_data_provider(
            "cpu_trends", self.performance.get_cpu_trends)
        self.dashboard.register_data_provider(
            "active_alerts", self.alerts.get_active_alerts)

        layout = self.dashboard.create_layout("default", widgets)
        return {"widgets_created": len(widgets), "layout": layout}
