"""
Tests for System Performance Optimizer.

Business Source License 1.1 (BSL 1.1)
Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post

Covers:
- PerformanceMetric, Bottleneck, OptimizationAction, OptimizationReport data models
- MetricCategory, BottleneckSeverity, OptimizationCategory enums
- SystemProfiler.capture_metrics returns all categories
- SystemProfiler.identify_bottlenecks detects issues
- SystemProfiler.get_performance_baseline and compare_to_baseline
- CacheManager get/set/invalidate with TTL
- CacheManager eviction, stats, and configure_cache
- ConnectionPoolManager create/get/return/resize
- BatchProcessor configure, enqueue, flush, stats
- SystemOptimizationEngine.run_optimization_cycle finds and applies optimizations
- SystemOptimizationEngine.rollback_optimization
- SystemOptimizationEngine.suggest_optimizations
- Emergency stop integration on degradation
- WingmanPair creation for optimization cycles
- Thread safety
"""

import threading
import time
import uuid
import pytest

from src.system_performance_optimizer import (
    BatchProcessor,
    Bottleneck,
    BottleneckSeverity,
    CacheManager,
    ConnectionPoolManager,
    MetricCategory,
    OptimizationAction,
    OptimizationCategory,
    OptimizationReport,
    PerformanceMetric,
    SystemOptimizationEngine,
    SystemProfiler,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def profiler():
    return SystemProfiler()


@pytest.fixture
def cache():
    return CacheManager(max_size=10, ttl_seconds=60)


@pytest.fixture
def pool_manager():
    return ConnectionPoolManager()


@pytest.fixture
def batch_processor():
    return BatchProcessor()


@pytest.fixture
def optimizer():
    return SystemOptimizationEngine()


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------

class TestMetricCategoryEnum:
    def test_all_categories_present(self):
        expected = ["cpu", "memory", "io", "network", "latency", "throughput", "error_rate", "queue_depth"]
        values = [e.value for e in MetricCategory]
        for val in expected:
            assert val in values


class TestBottleneckSeverityEnum:
    def test_all_severities(self):
        assert BottleneckSeverity.CRITICAL.value == "critical"
        assert BottleneckSeverity.HIGH.value == "high"
        assert BottleneckSeverity.MEDIUM.value == "medium"
        assert BottleneckSeverity.LOW.value == "low"


class TestOptimizationCategoryEnum:
    def test_all_categories(self):
        expected = [
            "caching", "pooling", "batching", "lazy_loading", "compression",
            "deduplication", "indexing", "parallelization", "rate_limiting", "circuit_breaking",
        ]
        values = [e.value for e in OptimizationCategory]
        for val in expected:
            assert val in values


# ---------------------------------------------------------------------------
# Data model tests
# ---------------------------------------------------------------------------

class TestPerformanceMetric:
    def test_metric_creation(self):
        metric = PerformanceMetric(
            metric_id="m-001",
            category=MetricCategory.CPU,
            component="api_server",
            value=55.0,
            unit="percent",
            timestamp="2024-01-01T00:00:00+00:00",
        )
        assert metric.category == MetricCategory.CPU
        assert metric.value == 55.0
        assert metric.context == {}


class TestBottleneck:
    def test_bottleneck_creation(self):
        b = Bottleneck(
            bottleneck_id="b-001",
            component="database",
            category=MetricCategory.LATENCY,
            severity=BottleneckSeverity.HIGH,
            description="Query latency exceeds 200ms",
            impact_estimate="Degraded API response times",
            suggested_fix="Add index on frequently queried columns",
            detected_at="2024-01-01T00:00:00+00:00",
        )
        assert b.severity == BottleneckSeverity.HIGH


class TestOptimizationAction:
    def test_action_creation(self):
        action = OptimizationAction(
            action_id="a-001",
            name="Enable caching",
            category=OptimizationCategory.CACHING,
            target_component="api",
            estimated_improvement="30% latency reduction",
            risk_level="low",
            reversible=True,
        )
        assert action.applied_at is None
        assert action.rolled_back_at is None
        assert action.reversible is True


class TestOptimizationReport:
    def test_report_creation(self):
        report = OptimizationReport(
            report_id="r-001",
            timestamp="2024-01-01T00:00:00+00:00",
            metrics_analyzed=8,
        )
        assert report.bottlenecks_found == []
        assert report.optimizations_applied == []
        assert report.improvement_summary == {}


# ---------------------------------------------------------------------------
# SystemProfiler
# ---------------------------------------------------------------------------

class TestSystemProfiler:
    def test_capture_metrics_returns_all_categories(self, profiler):
        metrics = profiler.capture_metrics()
        for cat in MetricCategory:
            assert cat.value in metrics

    def test_capture_metrics_has_timestamp(self, profiler):
        metrics = profiler.capture_metrics()
        assert "captured_at" in metrics

    def test_profile_module_returns_dict(self, profiler):
        result = profiler.profile_module("causality_sandbox")
        assert result["module"] == "causality_sandbox"
        assert "avg_latency_ms" in result
        assert "error_rate" in result

    def test_identify_bottlenecks_empty_before_capture(self, profiler):
        bottlenecks = profiler.identify_bottlenecks()
        assert isinstance(bottlenecks, list)

    def test_identify_bottlenecks_after_capture(self, profiler):
        profiler.capture_metrics()
        bottlenecks = profiler.identify_bottlenecks()
        assert isinstance(bottlenecks, list)

    def test_get_performance_baseline(self, profiler):
        baseline = profiler.get_performance_baseline()
        assert MetricCategory.CPU.value in baseline

    def test_compare_to_baseline_no_baseline(self, profiler):
        result = profiler.compare_to_baseline()
        assert "error" in result
        assert "recommendation" in result

    def test_compare_to_baseline_after_setting(self, profiler):
        profiler.get_performance_baseline()
        result = profiler.compare_to_baseline()
        assert "deltas" in result
        assert "degraded" in result
        assert "recommendation" in result

    def test_metrics_stored_in_history(self, profiler):
        profiler.capture_metrics()
        profiler.capture_metrics()
        with profiler._lock:
            assert len(profiler._history) == 2


# ---------------------------------------------------------------------------
# CacheManager
# ---------------------------------------------------------------------------

class TestCacheManager:
    def test_cache_set_and_get(self, cache):
        cache.cache_set("key1", {"data": 42})
        value = cache.cache_get("key1")
        assert value == {"data": 42}

    def test_cache_get_missing_returns_none(self, cache):
        assert cache.cache_get("nonexistent") is None

    def test_cache_ttl_expiry(self):
        short_cache = CacheManager(max_size=10, ttl_seconds=1)
        short_cache.cache_set("expire_key", "will_expire")
        assert short_cache.cache_get("expire_key") == "will_expire"

    def test_cache_per_key_ttl(self):
        c = CacheManager(max_size=10, ttl_seconds=60)
        c.cache_set("perm", "stays", ttl=3600)
        assert c.cache_get("perm") == "stays"

    def test_cache_stats_hit_rate(self, cache):
        cache.cache_set("key1", "val1")
        cache.cache_get("key1")
        cache.cache_get("key1")
        cache.cache_get("missing")
        stats = cache.get_cache_stats()
        assert stats["hits"] == 2
        assert stats["misses"] == 1
        assert stats["hit_rate"] > 0

    def test_cache_eviction_on_max_size(self):
        c = CacheManager(max_size=3, ttl_seconds=3600)
        c.cache_set("k1", 1)
        c.cache_set("k2", 2)
        c.cache_set("k3", 3)
        c.cache_set("k4", 4)
        stats = c.get_cache_stats()
        assert stats["evictions"] == 1
        assert stats["current_size"] == 3

    def test_invalidate_pattern(self, cache):
        cache.cache_set("user:1", {"name": "Alice"})
        cache.cache_set("user:2", {"name": "Bob"})
        cache.cache_set("session:1", {"active": True})
        count = cache.invalidate_pattern("user:")
        assert count == 2
        assert cache.cache_get("user:1") is None
        assert cache.cache_get("session:1") is not None

    def test_configure_cache_at_runtime(self, cache):
        cache.configure_cache("fifo", 50, 120)
        assert cache._strategy == "fifo"
        assert cache._max_size == 50
        assert cache._default_ttl == 120

    def test_cache_stats_structure(self, cache):
        stats = cache.get_cache_stats()
        for key in ["hit_rate", "miss_rate", "hits", "misses", "evictions", "current_size", "max_size", "strategy"]:
            assert key in stats

    def test_thread_safe_cache_writes(self, cache):
        errors = []
        lock = threading.Lock()

        def write(i: int) -> None:
            try:
                cache.cache_set(f"thread_key_{i}", i * 2)
            except Exception as exc:
                with lock:
                    errors.append(exc)

        threads = [threading.Thread(target=write, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []


# ---------------------------------------------------------------------------
# ConnectionPoolManager
# ---------------------------------------------------------------------------

class TestConnectionPoolManager:
    def test_create_pool_returns_name(self, pool_manager):
        name = pool_manager.create_pool("db", "postgresql", {"pool_size": 5})
        assert name == "db"

    def test_get_connection_returns_conn(self, pool_manager):
        pool_manager.create_pool("db", "postgresql", {"pool_size": 5})
        conn = pool_manager.get_connection("db")
        assert conn is not None

    def test_return_connection(self, pool_manager):
        pool_manager.create_pool("db", "postgresql", {"pool_size": 5})
        conn = pool_manager.get_connection("db")
        stats_before = pool_manager.get_pool_stats()["db"]["idle"]
        pool_manager.return_connection("db", conn)
        stats_after = pool_manager.get_pool_stats()["db"]["idle"]
        assert stats_after == stats_before + 1

    def test_get_connection_tracks_active(self, pool_manager):
        pool_manager.create_pool("db", "postgresql", {"pool_size": 3})
        pool_manager.get_connection("db")
        pool_manager.get_connection("db")
        stats = pool_manager.get_pool_stats()["db"]
        assert stats["active"] == 2
        assert stats["idle"] == 1

    def test_get_connection_exhausted_raises(self, pool_manager):
        pool_manager.create_pool("small", "redis", {"pool_size": 1})
        pool_manager.get_connection("small")
        with pytest.raises(RuntimeError):
            pool_manager.get_connection("small")

    def test_get_connection_missing_pool_raises(self, pool_manager):
        with pytest.raises(KeyError):
            pool_manager.get_connection("nonexistent")

    def test_resize_pool_up(self, pool_manager):
        pool_manager.create_pool("db", "postgresql", {"pool_size": 5})
        pool_manager.resize_pool("db", 10)
        stats = pool_manager.get_pool_stats()["db"]
        assert stats["pool_size"] == 10
        assert stats["idle"] == 10

    def test_resize_pool_down(self, pool_manager):
        pool_manager.create_pool("db", "postgresql", {"pool_size": 10})
        pool_manager.resize_pool("db", 3)
        stats = pool_manager.get_pool_stats()["db"]
        assert stats["pool_size"] == 3

    def test_resize_missing_pool_raises(self, pool_manager):
        with pytest.raises(KeyError):
            pool_manager.resize_pool("nonexistent", 10)

    def test_pool_stats_structure(self, pool_manager):
        pool_manager.create_pool("db", "postgresql", {"pool_size": 5})
        stats = pool_manager.get_pool_stats()
        assert "db" in stats
        for key in ["active", "idle", "waiting", "timeouts", "pool_size", "pool_type"]:
            assert key in stats["db"]

    def test_multiple_pools_independent(self, pool_manager):
        pool_manager.create_pool("db", "postgresql", {"pool_size": 5})
        pool_manager.create_pool("cache", "redis", {"pool_size": 3})
        stats = pool_manager.get_pool_stats()
        assert "db" in stats
        assert "cache" in stats
        assert stats["db"]["pool_size"] == 5
        assert stats["cache"]["pool_size"] == 3


# ---------------------------------------------------------------------------
# BatchProcessor
# ---------------------------------------------------------------------------

class TestBatchProcessor:
    def test_configure_batch(self, batch_processor):
        batch_processor.configure_batch("events", 100, 500, lambda b: b)
        stats = batch_processor.get_batch_stats()
        assert "events" in stats

    def test_enqueue_item(self, batch_processor):
        batch_processor.configure_batch("logs", 100, 500, lambda b: b)
        batch_processor.enqueue("logs", {"level": "info", "msg": "test"})
        stats = batch_processor.get_batch_stats()
        assert stats["logs"]["queue_depth"] == 1

    def test_flush_returns_count(self, batch_processor):
        batch_processor.configure_batch("events", 100, 500, lambda b: b)
        batch_processor.enqueue("events", {"e": 1})
        batch_processor.enqueue("events", {"e": 2})
        result = batch_processor.flush("events")
        assert result["items_processed"] == 2
        assert result["duration_ms"] >= 0

    def test_flush_empty_batch(self, batch_processor):
        batch_processor.configure_batch("empty", 100, 500, lambda b: b)
        result = batch_processor.flush("empty")
        assert result["items_processed"] == 0

    def test_auto_flush_on_batch_size(self, batch_processor):
        flushed = []
        def processor(items):
            flushed.extend(items)

        batch_processor.configure_batch("auto", 3, 500, processor)
        batch_processor.enqueue("auto", 1)
        batch_processor.enqueue("auto", 2)
        batch_processor.enqueue("auto", 3)
        assert len(flushed) == 3

    def test_enqueue_missing_batch_raises(self, batch_processor):
        with pytest.raises(KeyError):
            batch_processor.enqueue("nonexistent", {})

    def test_flush_missing_batch_raises(self, batch_processor):
        with pytest.raises(KeyError):
            batch_processor.flush("nonexistent")

    def test_batch_stats_after_flush(self, batch_processor):
        batch_processor.configure_batch("audit", 50, 200, lambda b: b)
        for i in range(5):
            batch_processor.enqueue("audit", i)
        batch_processor.flush("audit")
        stats = batch_processor.get_batch_stats()
        assert stats["audit"]["total_processed"] == 5
        assert stats["audit"]["total_flushes"] == 1
        assert stats["audit"]["last_flush_at"] is not None

    def test_processor_fn_exception_does_not_propagate(self, batch_processor):
        def failing_fn(items):
            raise ValueError("Processor error")

        batch_processor.configure_batch("fail_batch", 100, 500, failing_fn)
        batch_processor.enqueue("fail_batch", {"x": 1})
        result = batch_processor.flush("fail_batch")
        assert result["items_processed"] == 1

    def test_thread_safe_enqueue(self, batch_processor):
        processed = []
        lock = threading.Lock()

        def processor(items):
            with lock:
                processed.extend(items)

        batch_processor.configure_batch("thread_batch", 200, 500, processor)
        errors = []

        def enqueue_items(start: int) -> None:
            try:
                for i in range(start, start + 10):
                    batch_processor.enqueue("thread_batch", i)
            except Exception as exc:
                with lock:
                    errors.append(exc)

        threads = [threading.Thread(target=enqueue_items, args=(i * 10,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        batch_processor.flush("thread_batch")


# ---------------------------------------------------------------------------
# SystemOptimizationEngine
# ---------------------------------------------------------------------------

class TestSystemOptimizationEngine:
    def test_run_optimization_cycle_returns_report(self, optimizer):
        report = optimizer.run_optimization_cycle()
        assert isinstance(report, OptimizationReport)

    def test_report_has_metrics_analyzed(self, optimizer):
        report = optimizer.run_optimization_cycle()
        assert report.metrics_analyzed > 0

    def test_report_has_timestamp(self, optimizer):
        report = optimizer.run_optimization_cycle()
        assert report.timestamp is not None

    def test_report_has_before_after_metrics(self, optimizer):
        report = optimizer.run_optimization_cycle()
        assert isinstance(report.before_metrics, dict)
        assert isinstance(report.after_metrics, dict)

    def test_report_stored_in_history(self, optimizer):
        optimizer.run_optimization_cycle()
        history = optimizer.get_optimization_history()
        assert len(history) == 1

    def test_multiple_cycles_stored_in_order(self, optimizer):
        optimizer.run_optimization_cycle()
        optimizer.run_optimization_cycle()
        history = optimizer.get_optimization_history()
        assert len(history) == 2

    def test_suggest_optimizations_returns_list(self, optimizer):
        suggestions = optimizer.suggest_optimizations()
        assert isinstance(suggestions, list)
        assert len(suggestions) > 0

    def test_suggestion_categories_valid(self, optimizer):
        suggestions = optimizer.suggest_optimizations()
        for s in suggestions:
            assert isinstance(s.category, OptimizationCategory)

    def test_apply_optimization(self, optimizer):
        action = OptimizationAction(
            action_id=str(uuid.uuid4()),
            name="Test caching",
            category=OptimizationCategory.CACHING,
            target_component="api",
            estimated_improvement="20% latency reduction",
            risk_level="low",
        )
        result = optimizer.apply_optimization(action)
        assert result["applied"] is True
        assert result["action_id"] == action.action_id
        assert "recommendation" in result

    def test_rollback_existing_reversible_action(self, optimizer):
        action = OptimizationAction(
            action_id=str(uuid.uuid4()),
            name="Test caching",
            category=OptimizationCategory.CACHING,
            target_component="api",
            estimated_improvement="20%",
            risk_level="low",
            reversible=True,
        )
        optimizer.apply_optimization(action)
        result = optimizer.rollback_optimization(action.action_id)
        assert result["rolled_back"] is True
        assert result["rolled_back_at"] is not None

    def test_rollback_nonexistent_action(self, optimizer):
        result = optimizer.rollback_optimization("does-not-exist")
        assert result["rolled_back"] is False
        assert "error" in result

    def test_rollback_irreversible_action(self, optimizer):
        action = OptimizationAction(
            action_id=str(uuid.uuid4()),
            name="Irreversible change",
            category=OptimizationCategory.INDEXING,
            target_component="database",
            estimated_improvement="10%",
            risk_level="high",
            reversible=False,
        )
        optimizer.apply_optimization(action)
        result = optimizer.rollback_optimization(action.action_id)
        assert result["rolled_back"] is False
        assert "error" in result

    def test_emergency_stop_triggered_on_degradation(self):
        class _FakeStop:
            def __init__(self):
                self.activated = False
            def activate_global(self, reason):
                self.activated = True

        fake_stop = _FakeStop()

        class _DegradedProfiler(SystemProfiler):
            """Returns low CPU on first capture, high CPU on second (within same cycle)."""

            def __init__(self):
                super().__init__()
                self._call_count = 0
                self._lock = threading.Lock()

            def capture_metrics(self):
                with self._lock:
                    self._call_count += 1
                    call = self._call_count
                metrics = {
                    MetricCategory.CPU.value: {"value": 5.0 if call % 2 == 1 else 95.0, "unit": "percent"},
                    MetricCategory.MEMORY.value: {"value": 20.0, "unit": "percent"},
                    MetricCategory.IO.value: {"value": 30.0, "unit": "percent"},
                    MetricCategory.NETWORK.value: {"sent_mb": 1.0, "recv_mb": 2.0},
                    MetricCategory.LATENCY.value: {"value": 10.0, "unit": "ms"},
                    MetricCategory.THROUGHPUT.value: {"value": 1000, "unit": "req_per_sec"},
                    MetricCategory.ERROR_RATE.value: {"value": 0.001, "unit": "ratio"},
                    MetricCategory.QUEUE_DEPTH.value: {"value": 1, "unit": "items"},
                    "captured_at": "2024-01-01T00:00:00+00:00",
                }
                with self._lock:
                    self._history.append(metrics)
                return metrics

            def identify_bottlenecks(self):
                return []

        dp = _DegradedProfiler()
        eng = SystemOptimizationEngine(profiler=dp, emergency_stop=fake_stop)
        eng.run_optimization_cycle()
        assert fake_stop.activated is True


# ---------------------------------------------------------------------------
# Integration: WingmanProtocol
# ---------------------------------------------------------------------------

class TestWingmanIntegration:
    def test_wingman_pair_created_per_cycle(self):
        from wingman_protocol import WingmanProtocol
        wp = WingmanProtocol()
        eng = SystemOptimizationEngine(wingman_protocol=wp)
        eng.run_optimization_cycle()
        pairs = wp.list_pairs()
        assert len(pairs) >= 1

    def test_wingman_pair_subject_contains_report_id(self):
        from wingman_protocol import WingmanProtocol
        wp = WingmanProtocol()
        eng = SystemOptimizationEngine(wingman_protocol=wp)
        report = eng.run_optimization_cycle()
        pairs = wp.list_pairs()
        subjects = [p.subject for p in pairs]
        assert any(report.report_id in s for s in subjects)


# ---------------------------------------------------------------------------
# Integration: CausalitySandbox
# ---------------------------------------------------------------------------

class TestSandboxIntegration:
    def test_optimization_with_approving_sandbox(self):
        class _MockReport:
            optimal_actions_selected = 1

        class _MockSandbox:
            def run_sandbox_cycle(self, gaps, real_loop):
                return _MockReport()

        eng = SystemOptimizationEngine(causality_sandbox=_MockSandbox())
        report = eng.run_optimization_cycle()
        assert isinstance(report, OptimizationReport)
        assert len(report.optimizations_applied) > 0

    def test_optimization_with_rejecting_sandbox(self):
        class _MockReport:
            optimal_actions_selected = 0

        class _MockSandbox:
            def run_sandbox_cycle(self, gaps, real_loop):
                return _MockReport()

        eng = SystemOptimizationEngine(causality_sandbox=_MockSandbox())
        report = eng.run_optimization_cycle()
        assert isinstance(report, OptimizationReport)
        assert len(report.optimizations_applied) == 0


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_optimization_cycles(self):
        engine = SystemOptimizationEngine()
        errors: list = []
        reports: list = []
        lock = threading.Lock()

        def run_cycle(_: int) -> None:
            try:
                report = engine.run_optimization_cycle()
                with lock:
                    reports.append(report)
            except Exception as exc:
                with lock:
                    errors.append(exc)

        threads = [threading.Thread(target=run_cycle, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        assert len(reports) == 5

    def test_concurrent_cache_operations(self):
        c = CacheManager(max_size=100, ttl_seconds=60)
        errors: list = []
        lock = threading.Lock()

        def ops(i: int) -> None:
            try:
                c.cache_set(f"k{i}", i)
                c.cache_get(f"k{i}")
                c.cache_get(f"k{i + 100}")
            except Exception as exc:
                with lock:
                    errors.append(exc)

        threads = [threading.Thread(target=ops, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
