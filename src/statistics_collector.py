"""
Thread-safe statistics collector for accurate metrics collection.
"""

import logging
import threading
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional

try:
    from thread_safe_operations import ThreadSafeCounter, ThreadSafeDict, capped_append
except ImportError:
    import threading as _fb_threading
    class ThreadSafeCounter:
        """Minimal fallback ThreadSafeCounter."""
        def __init__(self, initial_value: int = 0):
            self._value = initial_value
            self._lock = _fb_threading.Lock()
        def increment(self, delta: int = 1) -> int:
            with self._lock:
                self._value += delta
                return self._value
        def decrement(self, delta: int = 1) -> int:
            with self._lock:
                self._value -= delta
                return self._value
        def get(self) -> int:
            with self._lock:
                return self._value
        def reset(self) -> int:
            with self._lock:
                self._value = 0
                return self._value
    class ThreadSafeDict:
        """Minimal fallback ThreadSafeDict."""
        def __init__(self):
            self._dict: dict = {}
            self._lock = _fb_threading.RLock()
        def get(self, key, default=None):
            with self._lock:
                return self._dict.get(key, default)
        def set(self, key, value) -> None:
            with self._lock:
                self._dict[key] = value
        def delete(self, key) -> bool:
            with self._lock:
                if key in self._dict:
                    del self._dict[key]
                    return True
                return False
        def keys(self):
            with self._lock:
                return list(self._dict.keys())
        def values(self):
            with self._lock:
                return list(self._dict.values())
        def items(self):
            with self._lock:
                return list(self._dict.items())
        def update(self, other: dict) -> None:
            with self._lock:
                self._dict.update(other)
        def clear(self) -> None:
            with self._lock:
                self._dict.clear()
        def get_dict(self) -> dict:
            with self._lock:
                return dict(self._dict)
        def __len__(self) -> int:
            with self._lock:
                return len(self._dict)
        def __contains__(self, key) -> bool:
            with self._lock:
                return key in self._dict
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)


class StatisticsSnapshot:
    """Snapshot of statistics at a point in time."""

    def __init__(
        self,
        timestamp: float,
        counters: Dict[str, int],
        gauges: Dict[str, float],
        histograms: Dict[str, List[float]]
    ):
        self.timestamp = timestamp
        self.counters = counters.copy()
        self.gauges = gauges.copy()
        self.histograms = {k: v.copy() for k, v in histograms.items()}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'timestamp': self.timestamp,
            'counters': self.counters,
            'gauges': self.gauges,
            'histograms': self.histograms
        }


class ThreadSafeStatisticsCollector:
    """Thread-safe statistics collector with atomic operations."""

    def __init__(self):
        self._counters = ThreadSafeDict()
        self._gauges = ThreadSafeDict()
        self._histograms = ThreadSafeDict()
        self._snapshots: List[StatisticsSnapshot] = []
        self._snapshot_lock = threading.Lock()
        self._start_time = time.time()

    def increment_counter(
        self,
        name: str,
        value: int = 1,
        labels: Optional[Dict[str, str]] = None
    ) -> int:
        """Atomically increment a counter."""
        key = self._make_key(name, labels)
        with self._counters._lock:
            current = self._counters._dict.get(key, 0)
            new_value = current + value
            self._counters._dict[key] = new_value
        return new_value

    def decrement_counter(
        self,
        name: str,
        value: int = 1,
        labels: Optional[Dict[str, str]] = None
    ) -> int:
        """Atomically decrement a counter."""
        key = self._make_key(name, labels)
        with self._counters._lock:
            current = self._counters._dict.get(key, 0)
            new_value = max(0, current - value)
            self._counters._dict[key] = new_value
        return new_value

    def set_gauge(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None
    ) -> None:
        """Atomically set a gauge value."""
        key = self._make_key(name, labels)
        self._gauges.set(key, value)

    def increment_gauge(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None
    ) -> float:
        """Atomically increment a gauge value."""
        key = self._make_key(name, labels)
        with self._gauges._lock:
            current = self._gauges._dict.get(key, 0.0)
            new_value = current + value
            self._gauges._dict[key] = new_value
        return new_value

    def record_histogram(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None
    ) -> None:
        """Record a value in a histogram."""
        key = self._make_key(name, labels)
        with self._histograms._lock:
            histogram = self._histograms._dict.get(key, []).copy()
            histogram.append(value)
            self._histograms._dict[key] = histogram

    def get_counter(
        self,
        name: str,
        labels: Optional[Dict[str, str]] = None
    ) -> int:
        """Get counter value."""
        key = self._make_key(name, labels)
        return self._counters.get(key, 0)

    def get_gauge(
        self,
        name: str,
        labels: Optional[Dict[str, str]] = None
    ) -> float:
        """Get gauge value."""
        key = self._make_key(name, labels)
        return self._gauges.get(key, 0.0)

    def get_histogram(
        self,
        name: str,
        labels: Optional[Dict[str, str]] = None
    ) -> List[float]:
        """Get histogram values."""
        key = self._make_key(name, labels)
        return self._histograms.get(key, [])

    def get_histogram_stats(
        self,
        name: str,
        labels: Optional[Dict[str, str]] = None
    ) -> Dict[str, float]:
        """Get histogram statistics."""
        values = self.get_histogram(name, labels)
        if not values:
            return {
                'count': 0,
                'min': 0.0,
                'max': 0.0,
                'mean': 0.0,
                'median': 0.0,
                'p50': 0.0,
                'p95': 0.0,
                'p99': 0.0
            }

        values_sorted = sorted(values)
        count = len(values_sorted)

        return {
            'count': count,
            'min': values_sorted[0],
            'max': values_sorted[-1],
            'mean': sum(values_sorted) / count,
            'median': values_sorted[count // 2],
            'p50': values_sorted[int(count * 0.5)],
            'p95': values_sorted[int(count * 0.95)],
            'p99': values_sorted[int(count * 0.99)]
        }

    def take_snapshot(self) -> StatisticsSnapshot:
        """Take a snapshot of current statistics."""
        return StatisticsSnapshot(
            timestamp=time.time(),
            counters=self._counters.get_dict(),
            gauges=self._gauges.get_dict(),
            histograms=self._histograms.get_dict()
        )

    def save_snapshot(self) -> None:
        """Save a snapshot for later retrieval."""
        snapshot = self.take_snapshot()
        with self._snapshot_lock:
            capped_append(self._snapshots, snapshot)

    def get_snapshots(
        self,
        limit: Optional[int] = None
    ) -> List[StatisticsSnapshot]:
        """Get saved snapshots."""
        with self._snapshot_lock:
            if limit is None:
                return self._snapshots.copy()
            return self._snapshots[-limit:]

    def clear_snapshots(self) -> None:
        """Clear all saved snapshots."""
        with self._snapshot_lock:
            self._snapshots.clear()

    def get_all_counters(self) -> Dict[str, int]:
        """Get all counters."""
        return self._counters.get_dict()

    def get_all_gauges(self) -> Dict[str, float]:
        """Get all gauges."""
        return self._gauges.get_dict()

    def get_all_histograms(self) -> Dict[str, List[float]]:
        """Get all histograms."""
        return self._histograms.get_dict()

    def reset(self) -> None:
        """Reset all statistics."""
        self._counters.clear()
        self._gauges.clear()
        self._histograms.clear()
        self._snapshots.clear()

    def get_uptime(self) -> float:
        """Get uptime in seconds."""
        return time.time() - self._start_time

    def _make_key(
        self,
        name: str,
        labels: Optional[Dict[str, str]] = None
    ) -> str:
        """Create a key with optional labels."""
        if labels:
            label_str = ','.join(f"{k}={v}" for k, v in sorted(labels.items()))
            return f"{name}{{{label_str}}}"
        return name


class OperationTimer:
    """Context manager for timing operations."""

    def __init__(self, collector: ThreadSafeStatisticsCollector, name: str):
        self.collector = collector
        self.name = name
        self.start_time: Optional[float] = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time is not None:
            duration = time.time() - self.start_time
            self.collector.increment_counter(f"{self.name}_count")
            self.collector.record_histogram(f"{self.name}_duration", duration)


class ErrorTracker:
    """Track errors with thread-safe operations."""

    def __init__(self):
        self._error_counts = ThreadSafeDict()
        self._error_types = ThreadSafeDict()
        self._lock = threading.Lock()

    def record_error(
        self,
        error_type: str,
        error_message: str,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """Record an error occurrence."""
        # Increment error count
        key = f"{error_type}:{error_message}"
        current = self._error_counts.get(key, 0)
        self._error_counts.set(key, current + 1)

        # Track error types
        type_count = self._error_types.get(error_type, 0)
        self._error_types.set(error_type, type_count + 1)

    def get_error_count(
        self,
        error_type: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> int:
        """Get error count."""
        if error_type and error_message:
            key = f"{error_type}:{error_message}"
            return self._error_counts.get(key, 0)
        elif error_type:
            return self._error_types.get(error_type, 0)
        else:
            return sum(self._error_counts.values())

    def get_top_errors(self, limit: int = 10) -> List[tuple]:
        """Get top errors by count."""
        items = self._error_counts.items()
        sorted_items = sorted(items, key=lambda x: x[1], reverse=True)
        return sorted_items[:limit]

    def reset(self) -> None:
        """Reset all error tracking."""
        self._error_counts.clear()
        self._error_types.clear()
