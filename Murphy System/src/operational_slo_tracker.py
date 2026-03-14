"""
Operational SLO Tracker for Murphy System Runtime

This module provides Service Level Objective tracking for the Murphy
automation system, including:
- Execution recording with success/failure and latency data
- Per-task-type metrics: success rates, latency percentiles, failure causes
- Approval ratio tracking per task type
- SLO target registration with threshold checks
- Sliding-window SLO compliance evaluation
- Thread-safe operation for concurrent use
"""

import logging
import threading
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)


@dataclass
class SLOTarget:
    """Defines a Service Level Objective target."""
    target_name: str
    metric: str  # success_rate, latency_p50, latency_p95, latency_p99, approval_ratio
    threshold: float
    window_seconds: float


@dataclass
class ExecutionRecord:
    """Records the result of a single task execution."""
    task_type: str
    success: bool
    duration: float
    timestamp: Optional[str] = None
    failure_reason: Optional[str] = None
    required_approval: bool = False
    approved: Optional[bool] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc).isoformat()


class OperationalSLOTracker:
    """Tracks operational metrics and evaluates SLO compliance.

    Records task executions, computes per-task-type metrics including success
    rates, latency percentiles, failure cause breakdowns, and approval ratios.
    Evaluates registered SLO targets over sliding time windows.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._records: List[ExecutionRecord] = []
        self._slo_targets: Dict[str, SLOTarget] = {}

    # ------------------------------------------------------------------
    # Execution recording
    # ------------------------------------------------------------------

    def record_execution(self, record: ExecutionRecord) -> str:
        """Record an execution and return a unique record id."""
        record_id = uuid.uuid4().hex[:12]
        with self._lock:
            capped_append(self._records, record)
        logger.info(
            "Recorded execution for task_type=%s success=%s (id=%s)",
            record.task_type, record.success, record_id,
        )
        return record_id

    # ------------------------------------------------------------------
    # SLO target management
    # ------------------------------------------------------------------

    def add_slo_target(self, target: SLOTarget) -> None:
        """Register an SLO target for compliance checking."""
        with self._lock:
            self._slo_targets[target.target_name] = target
        logger.info("Added SLO target %s: %s <= %s (window %ss)",
                     target.target_name, target.metric,
                     target.threshold, target.window_seconds)

    # ------------------------------------------------------------------
    # SLO compliance
    # ------------------------------------------------------------------

    def check_slo_compliance(self) -> Dict[str, Any]:
        """Check all registered SLO targets and return compliance results."""
        with self._lock:
            targets = dict(self._slo_targets)
            records = list(self._records)

        now = datetime.now(timezone.utc)
        results: Dict[str, Any] = {}

        for name, target in targets.items():
            windowed = _filter_by_window(records, now, target.window_seconds)
            actual = _compute_metric(windowed, target.metric)
            compliant = _check_threshold(target.metric, actual, target.threshold)
            results[name] = {
                "target_name": name,
                "metric": target.metric,
                "threshold": target.threshold,
                "actual": actual,
                "compliant": compliant,
                "window_seconds": target.window_seconds,
                "sample_size": len(windowed),
            }

        return results

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self, task_type: Optional[str] = None) -> Dict[str, Any]:
        """Return an aggregated metrics summary, optionally filtered by task type."""
        with self._lock:
            records = list(self._records)

        if task_type is not None:
            records = [r for r in records if r.task_type == task_type]

        if not records:
            return {
                "task_type": task_type,
                "sample_size": 0,
                "success_rate": 0.0,
                "latency_p50": 0.0,
                "latency_p95": 0.0,
                "latency_p99": 0.0,
                "failure_causes": {},
                "approval_ratio": 0.0,
            }

        total = len(records)
        successes = sum(1 for r in records if r.success)
        success_rate = successes / total

        durations = sorted(r.duration for r in records)
        p50 = _percentile(durations, 50)
        p95 = _percentile(durations, 95)
        p99 = _percentile(durations, 99)

        failure_causes: Dict[str, int] = defaultdict(int)
        for r in records:
            if not r.success and r.failure_reason:
                failure_causes[r.failure_reason] += 1

        approval_required = [r for r in records if r.required_approval]
        if approval_required:
            approved_count = sum(1 for r in approval_required if r.approved)
            approval_ratio = approved_count / (len(approval_required) or 1)
        else:
            approval_ratio = 0.0

        return {
            "task_type": task_type,
            "sample_size": total,
            "success_rate": round(success_rate, 4),
            "latency_p50": round(p50, 4),
            "latency_p95": round(p95, 4),
            "latency_p99": round(p99, 4),
            "failure_causes": dict(failure_causes),
            "approval_ratio": round(approval_ratio, 4),
        }

    # ------------------------------------------------------------------
    # Status / summary
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """Return current tracker status."""
        with self._lock:
            total_records = len(self._records)
            total_targets = len(self._slo_targets)
            task_types = list({r.task_type for r in self._records})

        return {
            "total_records": total_records,
            "total_slo_targets": total_targets,
            "task_types_tracked": sorted(task_types),
            "tracking_active": total_records > 0,
        }


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _percentile(sorted_values: List[float], pct: float) -> float:
    """Return the *pct*-th percentile from an already-sorted list."""
    if not sorted_values:
        return 0.0
    n = len(sorted_values)
    k = (pct / 100.0) * (n - 1)
    f = int(k)
    c = f + 1
    if c >= n:
        return sorted_values[-1]
    d = k - f
    return sorted_values[f] + d * (sorted_values[c] - sorted_values[f])


def _filter_by_window(
    records: List[ExecutionRecord],
    now: datetime,
    window_seconds: float,
) -> List[ExecutionRecord]:
    """Return records whose timestamp falls within the sliding window."""
    result: List[ExecutionRecord] = []
    for r in records:
        try:
            ts = datetime.fromisoformat(r.timestamp)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            delta = (now - ts).total_seconds()
            if delta <= window_seconds:
                result.append(r)
        except (ValueError, TypeError):
            # Skip records with unparseable timestamps
            continue
    return result


def _compute_metric(records: List[ExecutionRecord], metric: str) -> float:
    """Compute a single metric value from a list of execution records."""
    if not records:
        return 0.0

    if metric == "success_rate":
        return sum(1 for r in records if r.success) / len(records)

    durations = sorted(r.duration for r in records)
    if metric == "latency_p50":
        return _percentile(durations, 50)
    if metric == "latency_p95":
        return _percentile(durations, 95)
    if metric == "latency_p99":
        return _percentile(durations, 99)

    if metric == "approval_ratio":
        approval_required = [r for r in records if r.required_approval]
        if not approval_required:
            return 0.0
        return sum(1 for r in approval_required if r.approved) / len(approval_required)

    return 0.0


def _check_threshold(metric: str, actual: float, threshold: float) -> bool:
    """Check whether *actual* satisfies the SLO threshold for *metric*.

    For success_rate and approval_ratio the actual value must be >= threshold.
    For latency metrics the actual value must be <= threshold.
    """
    if metric in ("success_rate", "approval_ratio"):
        return actual >= threshold
    if metric.startswith("latency_"):
        return actual <= threshold
    return actual >= threshold
