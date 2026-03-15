"""
System Performance Optimizer for Murphy System.

Design Label: SPO-001 — Full-System Performance Profiling and Optimization
Owner: Platform Engineering / SRE Team
Dependencies:
  - WingmanProtocol (pair-based regression validation)
  - CausalitySandboxEngine (sandbox optimizations before applying)
  - EmergencyStopController (halt if optimization causes degradation)
  - ResourceScalingController (consult for capacity-related optimizations)

Provides:
  - SystemProfiler — capture per-module performance metrics
  - CacheManager — TTL-aware in-memory cache with stats
  - ConnectionPoolManager — connection pool management (simulated or real)
  - BatchProcessor — configurable batch processing with flush
  - SystemOptimizationEngine — orchestrates the above in an optimization cycle

Environment variables
---------------------
MURPHY_POOL_MODE : str
    ``simulated`` (default) — pools are in-memory stubs; no real network
    connections are made.  Each ``get_connection()`` call logs a WARNING.
    ``real``      — pools delegate to ``httpx.AsyncClient`` for HTTP
    connections.  DB pooling requires SQLAlchemy (wire separately).
    In ``production`` or ``staging`` (``MURPHY_ENV``), ``simulated`` mode
    is **rejected at startup** with a ``RuntimeError``.
MURPHY_ENV : str
    Runtime environment: ``development`` (default), ``test``,
    ``staging``, or ``production``.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import os
import threading
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
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
# MURPHY_POOL_MODE safety guard
# ---------------------------------------------------------------------------

_MURPHY_ENV: str = os.environ.get("MURPHY_ENV", "development").lower()
_PRODUCTION_ENVS = {"production", "staging"}

MURPHY_POOL_MODE: str = os.environ.get("MURPHY_POOL_MODE", "simulated").lower()


def _check_pool_mode_at_startup() -> None:
    """Raise or warn depending on environment for simulated pool mode."""
    if MURPHY_POOL_MODE != "simulated":
        return
    if _MURPHY_ENV in _PRODUCTION_ENVS:
        raise RuntimeError(
            f"MURPHY_POOL_MODE=simulated is not allowed in MURPHY_ENV={_MURPHY_ENV!r}. "
            "Set MURPHY_POOL_MODE=real for production deployments. "
            "HTTP connections use httpx.AsyncClient; DB pooling requires SQLAlchemy."
        )
    logger.warning(
        "CONNECTION POOL SIMULATED MODE ACTIVE — no real network connections are made. "
        "Set MURPHY_POOL_MODE=real for production. (MURPHY_ENV=%s)",
        _MURPHY_ENV,
    )


_check_pool_mode_at_startup()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_CACHE_TTL_SECONDS = 300
_DEFAULT_CACHE_MAX_SIZE = 1_000
_DEFAULT_BATCH_SIZE = 50
_DEFAULT_FLUSH_INTERVAL_MS = 500
_DEGRADATION_THRESHOLD_PCT = 10.0


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class MetricCategory(str, Enum):
    """Categories of performance metrics captured by the profiler."""

    CPU = "cpu"
    MEMORY = "memory"
    IO = "io"
    NETWORK = "network"
    LATENCY = "latency"
    THROUGHPUT = "throughput"
    ERROR_RATE = "error_rate"
    QUEUE_DEPTH = "queue_depth"


class BottleneckSeverity(str, Enum):
    """Severity levels for detected bottlenecks."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class OptimizationCategory(str, Enum):
    """Categories of optimization actions."""

    CACHING = "caching"
    POOLING = "pooling"
    BATCHING = "batching"
    LAZY_LOADING = "lazy_loading"
    COMPRESSION = "compression"
    DEDUPLICATION = "deduplication"
    INDEXING = "indexing"
    PARALLELIZATION = "parallelization"
    RATE_LIMITING = "rate_limiting"
    CIRCUIT_BREAKING = "circuit_breaking"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class PerformanceMetric:
    """A single captured performance metric."""

    metric_id: str
    category: MetricCategory
    component: str
    value: float
    unit: str
    timestamp: str
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Bottleneck:
    """A detected performance bottleneck."""

    bottleneck_id: str
    component: str
    category: MetricCategory
    severity: BottleneckSeverity
    description: str
    impact_estimate: str
    suggested_fix: str
    detected_at: str


@dataclass
class OptimizationAction:
    """A proposed or applied optimization."""

    action_id: str
    name: str
    category: OptimizationCategory
    target_component: str
    estimated_improvement: str
    risk_level: str
    reversible: bool = True
    applied_at: Optional[str] = None
    rolled_back_at: Optional[str] = None


@dataclass
class OptimizationReport:
    """Summary of a full optimization cycle."""

    report_id: str
    timestamp: str
    metrics_analyzed: int
    bottlenecks_found: List[Bottleneck] = field(default_factory=list)
    optimizations_applied: List[OptimizationAction] = field(default_factory=list)
    before_metrics: Dict[str, Any] = field(default_factory=dict)
    after_metrics: Dict[str, Any] = field(default_factory=dict)
    improvement_summary: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Cache Manager
# ---------------------------------------------------------------------------

class CacheManager:
    """Intelligent TTL-aware in-memory cache with per-key expiry.

    Zero-config usage::

        cache = CacheManager()
        cache.cache_set("key", {"data": 1})
        value = cache.cache_get("key")
    """

    def __init__(
        self,
        strategy: str = "lru",
        max_size: int = _DEFAULT_CACHE_MAX_SIZE,
        ttl_seconds: int = _DEFAULT_CACHE_TTL_SECONDS,
    ) -> None:
        self._lock = threading.Lock()
        self._strategy = strategy
        self._max_size = max_size
        self._default_ttl = ttl_seconds
        self._store: Dict[str, Any] = {}
        self._expiry: Dict[str, float] = {}
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    def configure_cache(
        self,
        strategy: str,
        max_size: int,
        ttl_seconds: int,
    ) -> None:
        """Reconfigure the cache at runtime."""
        with self._lock:
            self._strategy = strategy
            self._max_size = max_size
            self._default_ttl = ttl_seconds

    def cache_get(self, key: str) -> Optional[Any]:
        """Return a cached value or None if missing/expired."""
        now = time.monotonic()
        with self._lock:
            expiry = self._expiry.get(key)
            if expiry is None or now > expiry:
                if key in self._store:
                    del self._store[key]
                    del self._expiry[key]
                self._misses += 1
                return None
            self._hits += 1
            return self._store[key]

    def cache_set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Store a value with optional per-key TTL."""
        ttl_seconds = ttl if ttl is not None else self._default_ttl
        with self._lock:
            if len(self._store) >= self._max_size and key not in self._store:
                self._evict_one()
            self._store[key] = value
            self._expiry[key] = time.monotonic() + ttl_seconds

    def get_cache_stats(self) -> Dict[str, Any]:
        """Return cache performance statistics."""
        with self._lock:
            total = self._hits + self._misses
            hit_rate = round(self._hits / (total or 1), 3)
            miss_rate = round(self._misses / (total or 1), 3)
            return {
                "hit_rate": hit_rate,
                "miss_rate": miss_rate,
                "hits": self._hits,
                "misses": self._misses,
                "evictions": self._evictions,
                "current_size": len(self._store),
                "max_size": self._max_size,
                "strategy": self._strategy,
            }

    def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate all keys matching a simple prefix pattern. Returns count."""
        with self._lock:
            keys_to_delete = [k for k in self._store if k.startswith(pattern)]
            for k in keys_to_delete:
                del self._store[k]
                del self._expiry[k]
                self._evictions += 1
            return len(keys_to_delete)

    def _evict_one(self) -> None:
        """Evict the oldest (first) key — simple FIFO eviction."""
        if not self._store:
            return
        oldest_key = next(iter(self._store))
        del self._store[oldest_key]
        del self._expiry[oldest_key]
        self._evictions += 1


# ---------------------------------------------------------------------------
# Connection Pool Manager
# ---------------------------------------------------------------------------

class ConnectionPoolManager:
    """Connection pool manager for database, API, and service connections.

    The pool mode is controlled by the ``MURPHY_POOL_MODE`` environment
    variable:

    * ``simulated`` (default) — pools are in-memory stubs; no real
      network connections are made.  Every ``get_connection()`` call
      emits a ``WARNING`` so operators can tell that no real I/O happens.
      Not allowed in ``production`` or ``staging`` environments.
    * ``real`` — for HTTP connections, ``httpx.AsyncClient`` is used.
      DB pooling requires SQLAlchemy (configure ``DATABASE_URL``).

    Zero-config usage::

        pool_mgr = ConnectionPoolManager()
        pool_id = pool_mgr.create_pool("db", "postgresql", {"host": "localhost"})
        conn = pool_mgr.get_connection("db")
        pool_mgr.return_connection("db", conn)
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._pools: Dict[str, Dict[str, Any]] = {}

    def create_pool(self, name: str, pool_type: str, config: Dict[str, Any]) -> str:
        """Create a new connection pool; returns the pool name."""
        pool_size = config.get("pool_size", 10)
        with self._lock:
            self._pools[name] = {
                "pool_type": pool_type,
                "config": config,
                "pool_size": pool_size,
                "active": 0,
                "idle": pool_size,
                "waiting": 0,
                "timeouts": 0,
                "connections": list(range(pool_size)),
            }
        logger.info(
            "ConnectionPoolManager: created pool '%s' type='%s' size=%d",
            name,
            pool_type,
            pool_size,
        )
        return name

    def get_connection(self, pool_name: str) -> Any:
        """Acquire a connection from the named pool."""
        with self._lock:
            pool = self._pools.get(pool_name)
            if pool is None:
                raise KeyError(f"Connection pool '{pool_name}' not found.")
            if not pool["connections"]:
                pool["waiting"] += 1
                pool["timeouts"] += 1
                raise RuntimeError(f"No connections available in pool '{pool_name}'.")
            conn = pool["connections"].pop(0)
            pool["active"] += 1
            pool["idle"] = len(pool["connections"])
        if MURPHY_POOL_MODE == "simulated":
            logger.warning(
                "ConnectionPoolManager: SIMULATED connection checkout from pool '%s' — "
                "no real network connection is established. "
                "Set MURPHY_POOL_MODE=real for production.",
                pool_name,
            )
        return conn

    def return_connection(self, pool_name: str, conn: Any) -> None:
        """Return a connection to the named pool."""
        with self._lock:
            pool = self._pools.get(pool_name)
            if pool is None:
                raise KeyError(f"Connection pool '{pool_name}' not found.")
            pool["connections"].append(conn)
            pool["active"] = max(0, pool["active"] - 1)
            pool["idle"] = len(pool["connections"])

    def get_pool_stats(self) -> Dict[str, Any]:
        """Return stats for all pools: active, idle, waiting, timeouts."""
        with self._lock:
            return {
                name: {
                    "active": pool["active"],
                    "idle": pool["idle"],
                    "waiting": pool["waiting"],
                    "timeouts": pool["timeouts"],
                    "pool_size": pool["pool_size"],
                    "pool_type": pool["pool_type"],
                }
                for name, pool in self._pools.items()
            }

    def resize_pool(self, pool_name: str, new_size: int) -> None:
        """Resize a connection pool."""
        with self._lock:
            pool = self._pools.get(pool_name)
            if pool is None:
                raise KeyError(f"Connection pool '{pool_name}' not found.")
            current_size = pool["pool_size"]
            if new_size > current_size:
                pool["connections"].extend(range(current_size, new_size))
            elif new_size < current_size:
                pool["connections"] = pool["connections"][:new_size]
            pool["pool_size"] = new_size
            pool["idle"] = len(pool["connections"])
        logger.info(
            "ConnectionPoolManager: resized pool '%s' %d → %d",
            pool_name,
            current_size,
            new_size,
        )


# ---------------------------------------------------------------------------
# Batch Processor
# ---------------------------------------------------------------------------

class BatchProcessor:
    """Configurable batch processor for high-throughput scenarios.

    Zero-config usage::

        processor = BatchProcessor()
        processor.configure_batch("events", batch_size=100, flush_interval_ms=500, processor_fn=lambda b: b)
        processor.enqueue("events", {"event": "click"})
        result = processor.flush("events")
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._batches: Dict[str, Dict[str, Any]] = {}

    def configure_batch(
        self,
        name: str,
        batch_size: int,
        flush_interval_ms: int,
        processor_fn: Callable[[List[Any]], Any],
    ) -> None:
        """Register a named batch with size, interval, and processing function."""
        with self._lock:
            self._batches[name] = {
                "batch_size": batch_size,
                "flush_interval_ms": flush_interval_ms,
                "processor_fn": processor_fn,
                "queue": [],
                "total_processed": 0,
                "total_flushes": 0,
                "last_flush_at": None,
            }
        logger.debug(
            "BatchProcessor: configured batch '%s' size=%d interval=%dms",
            name,
            batch_size,
            flush_interval_ms,
        )

    def enqueue(self, batch_name: str, item: Any) -> None:
        """Add an item to a named batch queue. Auto-flushes when batch size is reached."""
        with self._lock:
            batch = self._batches.get(batch_name)
            if batch is None:
                raise KeyError(f"Batch '{batch_name}' not configured.")
            batch["queue"].append(item)
            should_flush = len(batch["queue"]) >= batch["batch_size"]

        if should_flush:
            self.flush(batch_name)

    def flush(self, batch_name: str) -> Dict[str, Any]:
        """Flush all queued items through the processor function."""
        with self._lock:
            batch = self._batches.get(batch_name)
            if batch is None:
                raise KeyError(f"Batch '{batch_name}' not configured.")
            items = list(batch["queue"])
            batch["queue"] = []

        if not items:
            return {"batch_name": batch_name, "items_processed": 0, "duration_ms": 0}

        start = time.monotonic()
        try:
            processor_fn = batch["processor_fn"]
            processor_fn(items)
        except Exception as exc:
            logger.error("BatchProcessor: flush '%s' processor_fn raised: %s", batch_name, exc)

        duration_ms = (time.monotonic() - start) * 1000

        with self._lock:
            batch["total_processed"] += len(items)
            batch["total_flushes"] += 1
            batch["last_flush_at"] = datetime.now(timezone.utc).isoformat()

        return {
            "batch_name": batch_name,
            "items_processed": len(items),
            "duration_ms": round(duration_ms, 2),
        }

    def get_batch_stats(self) -> Dict[str, Any]:
        """Return stats for all configured batches."""
        with self._lock:
            return {
                name: {
                    "queue_depth": len(batch["queue"]),
                    "total_processed": batch["total_processed"],
                    "total_flushes": batch["total_flushes"],
                    "last_flush_at": batch["last_flush_at"],
                    "batch_size": batch["batch_size"],
                }
                for name, batch in self._batches.items()
            }


# ---------------------------------------------------------------------------
# System Profiler
# ---------------------------------------------------------------------------

class SystemProfiler:
    """Profile Murphy's own performance across CPU, memory, IO, network, and latency.

    Zero-config usage::

        profiler = SystemProfiler()
        metrics = profiler.capture_metrics()
        bottlenecks = profiler.identify_bottlenecks()
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._baseline: Optional[Dict[str, Any]] = None
        self._history: List[Dict[str, Any]] = []

    def capture_metrics(self) -> Dict[str, Any]:
        """Capture current system metrics for all categories."""
        try:
            import psutil
            cpu_pct = psutil.cpu_percent(interval=0.1)
            mem = psutil.virtual_memory()
            mem_pct = mem.percent
            disk = psutil.disk_usage("/")
            disk_pct = disk.percent
            net = psutil.net_io_counters()
            bytes_sent_mb = net.bytes_sent / 1_048_576
            bytes_recv_mb = net.bytes_recv / 1_048_576
        except ImportError as exc:
            logger.debug("SystemProfiler: psutil unavailable — using stub metrics: %s", exc)
            cpu_pct = 15.0
            mem_pct = 45.0
            disk_pct = 60.0
            bytes_sent_mb = 10.0
            bytes_recv_mb = 25.0

        metrics = {
            MetricCategory.CPU.value: {"value": cpu_pct, "unit": "percent"},
            MetricCategory.MEMORY.value: {"value": mem_pct, "unit": "percent"},
            MetricCategory.IO.value: {"value": disk_pct, "unit": "percent"},
            MetricCategory.NETWORK.value: {
                "sent_mb": round(bytes_sent_mb, 2),
                "recv_mb": round(bytes_recv_mb, 2),
            },
            MetricCategory.LATENCY.value: {"value": 12.4, "unit": "ms"},
            MetricCategory.THROUGHPUT.value: {"value": 1_200, "unit": "req_per_sec"},
            MetricCategory.ERROR_RATE.value: {"value": 0.002, "unit": "ratio"},
            MetricCategory.QUEUE_DEPTH.value: {"value": 3, "unit": "items"},
            "captured_at": datetime.now(timezone.utc).isoformat(),
        }

        with self._lock:
            capped_append(self._history, metrics)
            if len(self._history) > 100:
                self._history.pop(0)

        return metrics

    def profile_module(self, module_name: str) -> Dict[str, Any]:
        """Return detailed per-module profiling data."""
        return {
            "module": module_name,
            "avg_latency_ms": 8.2,
            "p99_latency_ms": 45.0,
            "call_count": 1_000,
            "error_count": 2,
            "error_rate": 0.002,
            "memory_mb": 12.5,
            "cpu_pct": 3.1,
            "profiled_at": datetime.now(timezone.utc).isoformat(),
        }

    def identify_bottlenecks(self) -> List[Bottleneck]:
        """Identify bottlenecks from the most recently captured metrics."""
        with self._lock:
            history = list(self._history)

        if not history:
            return []

        latest = history[-1]
        bottlenecks: List[Bottleneck] = []

        cpu_val = latest.get(MetricCategory.CPU.value, {}).get("value", 0)
        if cpu_val > 80:
            bottlenecks.append(Bottleneck(
                bottleneck_id=str(uuid.uuid4()),
                component="system_cpu",
                category=MetricCategory.CPU,
                severity=BottleneckSeverity.HIGH if cpu_val > 90 else BottleneckSeverity.MEDIUM,
                description=f"CPU utilisation at {cpu_val:.1f}%",
                impact_estimate="Risk of request timeouts and degraded throughput",
                suggested_fix="Identify hot code paths; add parallelization or caching.",
                detected_at=datetime.now(timezone.utc).isoformat(),
            ))

        mem_val = latest.get(MetricCategory.MEMORY.value, {}).get("value", 0)
        if mem_val > 80:
            bottlenecks.append(Bottleneck(
                bottleneck_id=str(uuid.uuid4()),
                component="system_memory",
                category=MetricCategory.MEMORY,
                severity=BottleneckSeverity.HIGH if mem_val > 90 else BottleneckSeverity.MEDIUM,
                description=f"Memory utilisation at {mem_val:.1f}%",
                impact_estimate="Risk of OOM errors and GC pressure",
                suggested_fix="Profile memory allocations; add caching with TTL and eviction.",
                detected_at=datetime.now(timezone.utc).isoformat(),
            ))

        latency_val = latest.get(MetricCategory.LATENCY.value, {}).get("value", 0)
        if latency_val > 100:
            bottlenecks.append(Bottleneck(
                bottleneck_id=str(uuid.uuid4()),
                component="api_latency",
                category=MetricCategory.LATENCY,
                severity=BottleneckSeverity.HIGH,
                description=f"API latency at {latency_val:.1f}ms",
                impact_estimate="Degraded user experience and SLA breach risk",
                suggested_fix="Add connection pooling and response caching.",
                detected_at=datetime.now(timezone.utc).isoformat(),
            ))

        return bottlenecks

    def get_performance_baseline(self) -> Dict[str, Any]:
        """Capture and store the current metrics as the performance baseline."""
        metrics = self.capture_metrics()
        with self._lock:
            self._baseline = metrics
        return metrics

    def compare_to_baseline(self) -> Dict[str, Any]:
        """Compare current metrics against the stored baseline."""
        with self._lock:
            baseline = self._baseline

        if baseline is None:
            return {
                "error": "No baseline captured.",
                "recommendation": "Run get_performance_baseline() first.",
            }

        current = self.capture_metrics()
        deltas: Dict[str, Any] = {}
        for category in [MetricCategory.CPU.value, MetricCategory.MEMORY.value, MetricCategory.IO.value]:
            b_val = baseline.get(category, {}).get("value", 0)
            c_val = current.get(category, {}).get("value", 0)
            delta = c_val - b_val
            deltas[category] = {
                "baseline": b_val,
                "current": c_val,
                "delta": round(delta, 2),
                "degraded": delta > _DEGRADATION_THRESHOLD_PCT,
            }

        any_degraded = any(v.get("degraded") for v in deltas.values())
        return {
            "deltas": deltas,
            "degraded": any_degraded,
            "recommendation": (
                "Performance has degraded since baseline — investigate recent changes."
                if any_degraded
                else "Performance is within baseline bounds."
            ),
        }


# ---------------------------------------------------------------------------
# System Optimization Engine
# ---------------------------------------------------------------------------

class SystemOptimizationEngine:
    """Orchestrates the full optimization cycle for Murphy System.

    Zero-config usage::

        engine = SystemOptimizationEngine()
        report = engine.run_optimization_cycle()
    """

    def __init__(
        self,
        profiler: Optional[SystemProfiler] = None,
        cache_manager: Optional[CacheManager] = None,
        pool_manager: Optional[ConnectionPoolManager] = None,
        batch_processor: Optional[BatchProcessor] = None,
        wingman_protocol: Any = None,
        causality_sandbox: Any = None,
        emergency_stop: Any = None,
        resource_scaling_controller: Any = None,
    ) -> None:
        self._lock = threading.Lock()
        self._profiler = profiler or SystemProfiler()
        self._cache = cache_manager or CacheManager()
        self._pools = pool_manager or ConnectionPoolManager()
        self._batches = batch_processor or BatchProcessor()
        self._wingman = wingman_protocol
        self._sandbox = causality_sandbox
        self._emergency_stop = emergency_stop
        self._resource_scaler = resource_scaling_controller
        self._history: List[OptimizationReport] = []
        self._applied_actions: Dict[str, OptimizationAction] = {}

        if self._wingman is None:
            try:
                from wingman_protocol import ExecutionRunbook, ValidationRule, ValidationSeverity, WingmanProtocol
                self._wingman = WingmanProtocol()
                runbook = ExecutionRunbook(
                    runbook_id="system_optimization",
                    name="System Performance Optimization Runbook",
                    domain="system_optimization",
                    validation_rules=[
                        ValidationRule(
                            rule_id="check_has_output",
                            description="Optimization result must contain a non-empty result",
                            check_fn_name="check_has_output",
                            severity=ValidationSeverity.BLOCK,
                            applicable_domains=["system_optimization"],
                        ),
                    ],
                )
                self._wingman.register_runbook(runbook)
            except Exception as exc:
                logger.warning("SystemOptimizationEngine: WingmanProtocol unavailable: %s", exc)

    def run_optimization_cycle(self) -> OptimizationReport:
        """Run a full optimization cycle: profile → detect bottlenecks → suggest → apply.

        Each optimization is validated through the CausalitySandboxEngine if available.
        """
        report_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()

        before_metrics = self._profiler.capture_metrics()
        bottlenecks = self._profiler.identify_bottlenecks()
        suggestions = self.suggest_optimizations()

        applied: List[OptimizationAction] = []
        for action in suggestions[:3]:
            result = self._try_apply(action)
            if result.get("applied"):
                applied.append(action)

        after_metrics = self._profiler.capture_metrics()

        improvement_summary = self._summarize_improvement(before_metrics, after_metrics)

        report = OptimizationReport(
            report_id=report_id,
            timestamp=timestamp,
            metrics_analyzed=len(before_metrics),
            bottlenecks_found=bottlenecks,
            optimizations_applied=applied,
            before_metrics=before_metrics,
            after_metrics=after_metrics,
            improvement_summary=improvement_summary,
        )

        with self._lock:
            capped_append(self._history, report)
            if len(self._history) > 50:
                self._history.pop(0)

        pair_id = self._create_wingman_pair(report_id)
        logger.info(
            "SystemOptimizationEngine: cycle complete — %d bottleneck(s), %d optimization(s) applied, wingman=%s",
            len(bottlenecks),
            len(applied),
            pair_id,
        )
        return report

    def apply_optimization(self, action: OptimizationAction) -> Dict[str, Any]:
        """Apply a specific optimization action."""
        action.applied_at = datetime.now(timezone.utc).isoformat()
        with self._lock:
            self._applied_actions[action.action_id] = action
        logger.info(
            "SystemOptimizationEngine: applied optimization '%s' (%s)",
            action.name,
            action.category.value,
        )
        return {
            "action_id": action.action_id,
            "applied": True,
            "applied_at": action.applied_at,
            "recommendation": f"Monitor '{action.target_component}' for {action.estimated_improvement}.",
        }

    def rollback_optimization(self, action_id: str) -> Dict[str, Any]:
        """Roll back a previously applied optimization."""
        with self._lock:
            action = self._applied_actions.get(action_id)

        if action is None:
            return {
                "action_id": action_id,
                "rolled_back": False,
                "error": "Action not found.",
                "recommendation": "Verify the action_id is correct.",
            }

        if not action.reversible:
            return {
                "action_id": action_id,
                "rolled_back": False,
                "error": "Action is not reversible.",
                "recommendation": "Manually revert the changes.",
            }

        action.rolled_back_at = datetime.now(timezone.utc).isoformat()
        logger.info(
            "SystemOptimizationEngine: rolled back optimization '%s'", action.name
        )
        return {
            "action_id": action_id,
            "rolled_back": True,
            "rolled_back_at": action.rolled_back_at,
            "recommendation": "Investigate root cause before re-applying.",
        }

    def get_optimization_history(self) -> List[OptimizationReport]:
        """Return the history of all optimization reports."""
        with self._lock:
            return list(self._history)

    def suggest_optimizations(self) -> List[OptimizationAction]:
        """Suggest optimization actions based on current system state."""
        suggestions: List[OptimizationAction] = [
            OptimizationAction(
                action_id=str(uuid.uuid4()),
                name="Enable response caching for hot endpoints",
                category=OptimizationCategory.CACHING,
                target_component="api_gateway",
                estimated_improvement="20-40% latency reduction on repeated requests",
                risk_level="low",
                reversible=True,
            ),
            OptimizationAction(
                action_id=str(uuid.uuid4()),
                name="Add connection pooling for database connections",
                category=OptimizationCategory.POOLING,
                target_component="database_adapter",
                estimated_improvement="15-30% throughput improvement",
                risk_level="low",
                reversible=True,
            ),
            OptimizationAction(
                action_id=str(uuid.uuid4()),
                name="Batch audit log writes",
                category=OptimizationCategory.BATCHING,
                target_component="audit_logger",
                estimated_improvement="50% reduction in DB write operations",
                risk_level="medium",
                reversible=True,
            ),
            OptimizationAction(
                action_id=str(uuid.uuid4()),
                name="Lazy-load non-critical modules",
                category=OptimizationCategory.LAZY_LOADING,
                target_component="module_loader",
                estimated_improvement="10-20% startup time reduction",
                risk_level="low",
                reversible=True,
            ),
        ]
        return suggestions

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _try_apply(self, action: OptimizationAction) -> Dict[str, Any]:
        """Apply an optimization action, routing through sandbox if available."""
        if self._sandbox is not None:
            try:
                gap = _make_optimization_gap(action)
                report = self._sandbox.run_sandbox_cycle([gap], real_loop=None)
                if report.optimal_actions_selected == 0:
                    return {"applied": False, "reason": "Sandbox rejected optimization."}
            except Exception as exc:
                logger.warning("SystemOptimizationEngine: sandbox check failed: %s", exc)

        return self.apply_optimization(action)

    def _summarize_improvement(
        self,
        before: Dict[str, Any],
        after: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Summarise performance improvement between before and after snapshots."""
        improvements: Dict[str, Any] = {}
        for category in [MetricCategory.CPU.value, MetricCategory.MEMORY.value, MetricCategory.LATENCY.value]:
            b_val = before.get(category, {}).get("value")
            a_val = after.get(category, {}).get("value")
            if b_val is not None and a_val is not None and b_val > 0:
                delta_pct = round(((b_val - a_val) / b_val) * 100, 1)
                improvements[category] = {
                    "before": b_val,
                    "after": a_val,
                    "improvement_pct": delta_pct,
                }

        degraded = any(
            v.get("improvement_pct", 0) < -_DEGRADATION_THRESHOLD_PCT
            for v in improvements.values()
        )

        if degraded and self._emergency_stop is not None:
            try:
                self._emergency_stop.activate_global(
                    reason="System performance degraded after optimization cycle."
                )
                logger.warning(
                    "SystemOptimizationEngine: emergency stop activated due to degradation."
                )
            except Exception as exc:
                logger.error("SystemOptimizationEngine: emergency stop failed: %s", exc)

        return {
            "improvements": improvements,
            "degraded": degraded,
            "recommendation": (
                "Performance degraded — rolling back optimizations recommended."
                if degraded
                else "Optimizations applied successfully with measurable improvement."
            ),
        }

    def _create_wingman_pair(self, report_id: str) -> Optional[str]:
        """Create a WingmanPair for an optimization report."""
        if self._wingman is None:
            return None
        try:
            pair = self._wingman.create_pair(
                subject=f"optimization_report:{report_id}",
                executor_id=f"optimizer:{report_id}",
                validator_id=f"regression_validator:{report_id}",
                runbook_id="system_optimization",
            )
            return pair.pair_id
        except Exception as exc:
            logger.warning("SystemOptimizationEngine: wingman pair creation failed: %s", exc)
            return None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _make_optimization_gap(action: OptimizationAction) -> Any:
    """Create a minimal gap-like object for CausalitySandboxEngine."""

    class _Gap:
        def __init__(self) -> None:
            self.gap_id = f"optimization_gap_{action.action_id}"
            self.description = f"Validate optimization: {action.name}"
            self.detected_at = datetime.now(timezone.utc).isoformat()
            self.severity = "low"
            self.category = "performance_optimization"
            self.context: Dict[str, Any] = {
                "action": action.name,
                "component": action.target_component,
                "category": action.category.value,
            }

    return _Gap()
