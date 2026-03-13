"""
Performance Optimization Module
Caching, parallel processing, query optimization, monitoring, and benchmarking.
"""

import asyncio
import logging
import statistics
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ============================================================================
# TASK 4.1: CACHING LAYER FOR UNCERTAINTY CALCULATIONS
# ============================================================================

class CacheStrategy(str, Enum):
    """Cache strategies."""
    LRU = "lru"  # Least Recently Used
    LFU = "lfu"  # Least Frequently Used
    TTL = "ttl"  # Time To Live
    FIFO = "fifo"  # First In First Out


class CacheEntry(BaseModel):
    """Entry in the cache."""
    key: str
    value: Any
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_accessed: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    access_count: int = 0
    ttl_seconds: Optional[int] = None


class UncertaintyCache:
    """
    High-performance cache for uncertainty calculations.
    """

    def __init__(
        self,
        max_size: int = 1000,
        default_ttl: int = 300,
        strategy: CacheStrategy = CacheStrategy.LRU
    ):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.strategy = strategy
        self.cache: Dict[str, CacheEntry] = {}
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        if key not in self.cache:
            self.misses += 1
            return None

        entry = self.cache[key]

        # Check TTL
        if entry.ttl_seconds:
            age = (datetime.now(timezone.utc) - entry.created_at).seconds
            if age > entry.ttl_seconds:
                del self.cache[key]
                self.misses += 1
                return None

        # Update access info
        entry.last_accessed = datetime.now(timezone.utc)
        entry.access_count += 1

        self.hits += 1
        return entry.value

    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """Set value in cache."""
        # Evict if at capacity
        if len(self.cache) >= self.max_size and key not in self.cache:
            self._evict()

        entry = CacheEntry(
            key=key,
            value=value,
            ttl_seconds=ttl or self.default_ttl
        )

        self.cache[key] = entry

    def invalidate(self, key: str):
        """Invalidate cache entry."""
        if key in self.cache:
            del self.cache[key]

    def clear(self):
        """Clear entire cache."""
        self.cache.clear()
        self.hits = 0
        self.misses = 0

    def _evict(self):
        """Evict entry based on strategy."""
        if not self.cache:
            return

        if self.strategy == CacheStrategy.LRU:
            # Evict least recently used
            oldest_key = min(
                self.cache.keys(),
                key=lambda k: self.cache[k].last_accessed
            )
            del self.cache[oldest_key]

        elif self.strategy == CacheStrategy.LFU:
            # Evict least frequently used
            least_used_key = min(
                self.cache.keys(),
                key=lambda k: self.cache[k].access_count
            )
            del self.cache[least_used_key]

        elif self.strategy == CacheStrategy.FIFO:
            # Evict oldest entry
            oldest_key = min(
                self.cache.keys(),
                key=lambda k: self.cache[k].created_at
            )
            del self.cache[oldest_key]

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_requests = self.hits + self.misses
        hit_rate = self.hits / total_requests if total_requests > 0 else 0

        return {
            "size": len(self.cache),
            "max_size": self.max_size,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": hit_rate,
            "strategy": self.strategy.value
        }


# ============================================================================
# TASK 4.2: PARALLEL VALIDATION PROCESSING
# ============================================================================

class ParallelProcessor:
    """
    Parallel processing for validation operations.
    """

    def __init__(self, max_workers: int = 10):
        self.max_workers = max_workers
        self.semaphore = asyncio.Semaphore(max_workers)

    async def process_batch(
        self,
        items: List[Any],
        processor: Callable,
        **kwargs
    ) -> List[Any]:
        """
        Process items in parallel.

        Args:
            items: Items to process
            processor: Async function to process each item
            **kwargs: Additional arguments for processor

        Returns:
            List of results
        """
        async def process_with_semaphore(item):
            async with self.semaphore:
                return await processor(item, **kwargs)

        tasks = [process_with_semaphore(item) for item in items]
        return await asyncio.gather(*tasks)

    async def process_with_timeout(
        self,
        item: Any,
        processor: Callable,
        timeout_seconds: float = 30.0,
        **kwargs
    ) -> Tuple[bool, Any]:
        """
        Process item with timeout.

        Returns:
            Tuple of (success, result)
        """
        try:
            result = await asyncio.wait_for(
                processor(item, **kwargs),
                timeout=timeout_seconds
            )
            return True, result
        except asyncio.TimeoutError:
            return False, None
        except Exception as exc:
            logger.debug("Caught exception: %s", exc)
            return False, str(exc)


# ============================================================================
# TASK 4.3: DATABASE QUERY OPTIMIZATION
# ============================================================================

class QueryOptimizer:
    """
    Optimizes database queries for risk patterns and historical data.
    """

    def __init__(self):
        self.query_cache = UncertaintyCache(max_size=500, default_ttl=60)
        self.query_stats: Dict[str, List[float]] = defaultdict(list)

    def optimize_pattern_search(
        self,
        filters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Optimize pattern search query.

        Args:
            filters: Search filters

        Returns:
            Optimized filters
        """
        optimized = filters.copy()

        # Use indexes for common filters
        if 'category' in optimized and 'severity' in optimized:
            # Composite index optimization
            optimized['_use_composite_index'] = True

        # Limit result set
        if 'limit' not in optimized:
            optimized['limit'] = 100

        # Add pagination for large results
        if optimized.get('limit', 0) > 1000:
            optimized['use_pagination'] = True
            optimized['page_size'] = 100

        return optimized

    def batch_queries(
        self,
        queries: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Batch multiple queries for efficiency.

        Args:
            queries: List of query dictionaries

        Returns:
            Optimized batch queries
        """
        # Group similar queries
        grouped = defaultdict(list)
        for query in queries:
            key = self._get_query_key(query)
            grouped[key].append(query)

        # Merge queries with same key
        batched = []
        for key, group in grouped.items():
            if len(group) > 1:
                # Merge into single query
                merged = self._merge_queries(group)
                batched.append(merged)
            else:
                batched.extend(group)

        return batched

    def _get_query_key(self, query: Dict[str, Any]) -> str:
        """Generate key for query grouping."""
        key_parts = []
        for field in ['category', 'severity', 'table']:
            if field in query:
                key_parts.append(f"{field}:{query[field]}")
        return "|".join(key_parts)

    def _merge_queries(self, queries: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Merge similar queries."""
        merged = queries[0].copy()

        # Combine IDs if present
        all_ids = []
        for query in queries:
            if 'id' in query:
                all_ids.append(query['id'])

        if all_ids:
            merged['id__in'] = all_ids
            merged.pop('id', None)

        return merged

    def record_query_time(self, query_type: str, duration: float):
        """Record query execution time."""
        self.query_stats[query_type].append(duration)

    def get_query_stats(self) -> Dict[str, Any]:
        """Get query performance statistics."""
        stats = {}

        for query_type, durations in self.query_stats.items():
            if durations:
                stats[query_type] = {
                    "count": len(durations),
                    "avg_duration": statistics.mean(durations),
                    "min_duration": min(durations),
                    "max_duration": max(durations),
                    "total_duration": sum(durations)
                }

        return stats


# ============================================================================
# TASK 4.4: PERFORMANCE MONITORING
# ============================================================================

class PerformanceMetric(BaseModel):
    """Performance metric data point."""
    name: str
    value: float
    unit: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PerformanceMonitor:
    """
    Monitors system performance metrics.
    """

    def __init__(self):
        self.metrics: Dict[str, List[PerformanceMetric]] = defaultdict(list)
        self.thresholds: Dict[str, float] = {}
        self.alerts: List[str] = []

    def record_metric(
        self,
        name: str,
        value: float,
        unit: str = "ms",
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Record a performance metric."""
        metric = PerformanceMetric(
            name=name,
            value=value,
            unit=unit,
            metadata=metadata or {}
        )

        self.metrics[name].append(metric)

        # Check threshold
        if name in self.thresholds and value > self.thresholds[name]:
            self.alerts.append(
                f"ALERT: {name} exceeded threshold ({value} > {self.thresholds[name]})"
            )

        # Keep only recent metrics (last 1000)
        if len(self.metrics[name]) > 1000:
            self.metrics[name] = self.metrics[name][-1000:]

    def set_threshold(self, metric_name: str, threshold: float):
        """Set alert threshold for a metric."""
        self.thresholds[metric_name] = threshold

    def get_metric_stats(
        self,
        metric_name: str,
        time_window_minutes: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get statistics for a metric."""
        metrics = self.metrics.get(metric_name, [])

        if not metrics:
            return {"count": 0}

        # Filter by time window
        if time_window_minutes:
            cutoff = datetime.now(timezone.utc) - timedelta(minutes=time_window_minutes)
            metrics = [m for m in metrics if m.timestamp >= cutoff]

        if not metrics:
            return {"count": 0}

        values = [m.value for m in metrics]

        return {
            "count": len(values),
            "mean": statistics.mean(values),
            "median": statistics.median(values),
            "min": min(values),
            "max": max(values),
            "stdev": statistics.stdev(values) if len(values) > 1 else 0,
            "p95": self._percentile(values, 0.95),
            "p99": self._percentile(values, 0.99)
        }

    def _percentile(self, values: List[float], percentile: float) -> float:
        """Calculate percentile."""
        sorted_values = sorted(values)
        index = int(len(sorted_values) * percentile)
        return sorted_values[min(index, len(sorted_values) - 1)]

    def get_all_stats(self) -> Dict[str, Any]:
        """Get statistics for all metrics."""
        return {
            name: self.get_metric_stats(name)
            for name in self.metrics.keys()
        }

    def get_alerts(self) -> List[str]:
        """Get recent alerts."""
        return self.alerts[-100:]  # Last 100 alerts


# ============================================================================
# TASK 4.5: PERFORMANCE BENCHMARKS
# ============================================================================

class BenchmarkResult(BaseModel):
    """Result of a benchmark test."""
    name: str
    duration_ms: float
    operations_per_second: float
    memory_mb: Optional[float] = None
    success: bool = True
    error: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PerformanceBenchmark:
    """
    Benchmarking suite for performance testing.
    """

    def __init__(self):
        self.results: List[BenchmarkResult] = []

    async def benchmark_function(
        self,
        name: str,
        func: Callable,
        iterations: int = 100,
        *args,
        **kwargs
    ) -> BenchmarkResult:
        """
        Benchmark a function.

        Args:
            name: Benchmark name
            func: Function to benchmark
            iterations: Number of iterations
            *args, **kwargs: Arguments for function

        Returns:
            BenchmarkResult
        """
        start_time = time.time()
        success = True
        error = None

        try:
            for _ in range(iterations):
                if asyncio.iscoroutinefunction(func):
                    await func(*args, **kwargs)
                else:
                    func(*args, **kwargs)
        except Exception as exc:
            logger.debug("Caught exception: %s", exc)
            success = False
            error = str(exc)

        end_time = time.time()
        duration_ms = (end_time - start_time) * 1000
        ops_per_second = iterations / (duration_ms / 1000) if duration_ms > 0 else 0

        result = BenchmarkResult(
            name=name,
            duration_ms=duration_ms,
            operations_per_second=ops_per_second,
            success=success,
            error=error
        )

        self.results.append(result)
        return result

    def benchmark_cache_performance(
        self,
        cache: UncertaintyCache,
        num_operations: int = 1000
    ) -> BenchmarkResult:
        """Benchmark cache performance."""
        start_time = time.time()

        # Write operations
        for i in range(num_operations // 2):
            cache.set(f"key_{i}", f"value_{i}")

        # Read operations
        for i in range(num_operations // 2):
            cache.get(f"key_{i}")

        end_time = time.time()
        duration_ms = (end_time - start_time) * 1000
        ops_per_second = num_operations / (duration_ms / 1000)

        result = BenchmarkResult(
            name="cache_performance",
            duration_ms=duration_ms,
            operations_per_second=ops_per_second
        )

        self.results.append(result)
        return result

    def compare_implementations(
        self,
        implementations: Dict[str, Callable],
        test_data: Any,
        iterations: int = 100
    ) -> Dict[str, BenchmarkResult]:
        """
        Compare multiple implementations.

        Args:
            implementations: Dict of name -> function
            test_data: Data to test with
            iterations: Number of iterations

        Returns:
            Dict of results
        """
        results = {}

        for name, func in implementations.items():
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None
            if loop and loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    result = pool.submit(
                        asyncio.run,
                        self.benchmark_function(name, func, iterations, test_data)
                    ).result()
            else:
                result = asyncio.run(
                    self.benchmark_function(name, func, iterations, test_data)
                )
            results[name] = result

        return results

    def get_summary(self) -> Dict[str, Any]:
        """Get benchmark summary."""
        if not self.results:
            return {"total_benchmarks": 0}

        successful = [r for r in self.results if r.success]

        return {
            "total_benchmarks": len(self.results),
            "successful": len(successful),
            "failed": len(self.results) - len(successful),
            "avg_duration_ms": statistics.mean([r.duration_ms for r in successful]) if successful else 0,
            "avg_ops_per_second": statistics.mean([r.operations_per_second for r in successful]) if successful else 0
        }


# ============================================================================
# UNIFIED PERFORMANCE SYSTEM
# ============================================================================

class PerformanceOptimizationSystem:
    """
    Complete performance optimization system.
    """

    def __init__(self):
        self.cache = UncertaintyCache()
        self.parallel_processor = ParallelProcessor()
        self.query_optimizer = QueryOptimizer()
        self.hitl_monitor = PerformanceMonitor()
        self.benchmark = PerformanceBenchmark()

        # Set default thresholds
        self.hitl_monitor.set_threshold("uncertainty_calculation_ms", 1000)
        self.hitl_monitor.set_threshold("risk_lookup_ms", 500)
        self.hitl_monitor.set_threshold("validation_ms", 2000)

    # Caching
    def get_cached(self, key: str) -> Optional[Any]:
        """Get from cache."""
        return self.cache.get(key)

    def set_cached(self, key: str, value: Any, ttl: Optional[int] = None):
        """Set in cache."""
        self.cache.set(key, value, ttl)

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return self.cache.get_stats()

    # Parallel Processing
    async def process_parallel(
        self,
        items: List[Any],
        processor: Callable,
        **kwargs
    ) -> List[Any]:
        """Process items in parallel."""
        return await self.parallel_processor.process_batch(items, processor, **kwargs)

    # Query Optimization
    def optimize_query(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Optimize query."""
        return self.query_optimizer.optimize_pattern_search(filters)

    # Monitoring
    def record_performance(self, name: str, value: float, unit: str = "ms"):
        """Record performance metric."""
        self.hitl_monitor.record_metric(name, value, unit)

    def get_performance_stats(self) -> Dict[str, Any]:
        """Get all performance statistics."""
        return {
            "cache": self.cache.get_stats(),
            "queries": self.query_optimizer.get_query_stats(),
            "metrics": self.hitl_monitor.get_all_stats(),
            "alerts": self.hitl_monitor.get_alerts()
        }

    # Benchmarking
    async def run_benchmark(
        self,
        name: str,
        func: Callable,
        iterations: int = 100
    ) -> BenchmarkResult:
        """Run benchmark."""
        return await self.benchmark.benchmark_function(name, func, iterations)

    def get_benchmark_summary(self) -> Dict[str, Any]:
        """Get benchmark summary."""
        return self.benchmark.get_summary()
