"""
Memory management utilities for handling large datasets efficiently.
Provides streaming, pagination, and memory optimization capabilities.
"""

import gc
import logging
import sys
from typing import Any, Callable, Dict, Generator, Iterator, List, Optional, TypeVar

T = TypeVar("T")

logger = logging.getLogger(__name__)


class StreamProcessor:
    """Process large datasets in streams to avoid memory issues."""

    def __init__(self, batch_size: int = 1000):
        self.batch_size = batch_size

    def stream_data(
        self,
        data_source: List[Any],
        processor: Callable[[List[Any]], Any]
    ) -> Generator[Any, None, None]:
        """Process data in batches."""
        for i in range(0, len(data_source), self.batch_size):
            batch = data_source[i:i + self.batch_size]
            result = processor(batch)
            yield result
            # Allow garbage collection
            if i % (self.batch_size * 10) == 0:
                gc.collect()

    def stream_file_lines(
        self,
        file_path: str,
        processor: Callable[[str], Any],
        encoding: str = 'utf-8'
    ) -> Generator[Any, None, None]:
        """Process file line by line."""
        with open(file_path, 'r', encoding=encoding) as f:
            batch = []
            for line in f:
                batch.append(line.strip())
                if len(batch) >= self.batch_size:
                    result = processor(batch)
                    yield result
                    batch = []

            # Process remaining lines
            if batch:
                result = processor(batch)
                yield result


class PaginatedResult:
    """Paginated result container for large datasets."""

    def __init__(
        self,
        data: List[Any],
        page: int,
        page_size: int,
        total: int
    ):
        self.data = data
        self.page = page
        self.page_size = page_size
        self.total = total
        self.total_pages = (total + page_size - 1) // page_size

    def has_next(self) -> bool:
        """Check if there's a next page."""
        return self.page < self.total_pages

    def has_previous(self) -> bool:
        """Check if there's a previous page."""
        return self.page > 1

    def get_next_page_number(self) -> Optional[int]:
        """Get next page number."""
        return self.page + 1 if self.has_next() else None

    def get_previous_page_number(self) -> Optional[int]:
        """Get previous page number."""
        return self.page - 1 if self.has_previous() else None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'data': self.data,
            'page': self.page,
            'page_size': self.page_size,
            'total': self.total,
            'total_pages': self.total_pages,
            'has_next': self.has_next(),
            'has_previous': self.has_previous()
        }


class MemoryMonitor:
    """Monitor memory usage and enforce limits."""

    def __init__(self, max_memory_mb: Optional[int] = None):
        self.max_memory_mb = max_memory_mb
        self._initial_memory = self.get_memory_usage()

    def get_memory_usage(self) -> float:
        """Get current memory usage in MB."""
        process = psutil.Process()
        return process.memory_info().rss / (1024 * 1024)

    def is_memory_exceeded(self) -> bool:
        """Check if memory limit exceeded."""
        if self.max_memory_mb is None:
            return False
        return self.get_memory_usage() > self.max_memory_mb

    def get_memory_increase(self) -> float:
        """Get memory increase since initialization in MB."""
        return self.get_memory_usage() - self._initial_memory

    def force_gc(self) -> None:
        """Force garbage collection."""
        gc.collect()


try:
    import psutil
except ImportError:
    psutil = None


class DataCache:
    """Memory-efficient cache with size limits."""

    def __init__(self, max_size_mb: int = 100):
        self.max_size_mb = max_size_mb
        self._cache: Dict[str, Any] = {}
        self._access_order: List[str] = []
        self._lock = threading.Lock()
        self._current_size_mb = 0.0

    def get(self, key: str) -> Optional[Any]:
        """Get item from cache."""
        with self._lock:
            if key in self._cache:
                # Update access order
                self._access_order.remove(key)
                self._access_order.append(key)  # bounded by max cache size
                return self._cache[key]
            return None

    def set(self, key: str, value: Any) -> bool:
        """Set item in cache, respecting size limit."""
        with self._lock:
            # Calculate size of value
            size_mb = self._estimate_size(value)

            # Remove old value if exists
            if key in self._cache:
                self._current_size_mb -= self._estimate_size(self._cache[key])
                self._access_order.remove(key)

            # Evict if necessary
            while (self._current_size_mb + size_mb) > self.max_size_mb and self._access_order:
                self._evict_oldest()

            # Add new value
            self._cache[key] = value
            self._access_order.append(key)  # LRU: bounded by cache eviction
            self._current_size_mb += size_mb

            return True

    def _evict_oldest(self) -> None:
        """Evict oldest item from cache."""
        if self._access_order:
            oldest_key = self._access_order.pop(0)
            self._current_size_mb -= self._estimate_size(self._cache[oldest_key])
            del self._cache[oldest_key]

    def _estimate_size(self, obj: Any) -> float:
        """Estimate size of object in MB."""
        try:
            size = sys.getsizeof(obj)
            # For collections, estimate recursively
            if isinstance(obj, (list, tuple, set)):
                size += sum(self._estimate_size(item) for item in obj)
            elif isinstance(obj, dict):
                size += sum(self._estimate_size(k) + self._estimate_size(v)
                           for k, v in obj.items())
            return size / (1024 * 1024)
        except Exception as exc:
            logger.debug("Suppressed exception: %s", exc)
            return 0.01  # Default small size

    def clear(self) -> None:
        """Clear all cache."""
        with self._lock:
            self._cache.clear()
            self._access_order.clear()
            self._current_size_mb = 0.0

    def get_size(self) -> float:
        """Get current cache size in MB."""
        with self._lock:
            return self._current_size_mb

    def get_item_count(self) -> int:
        """Get number of items in cache."""
        with self._lock:
            return len(self._cache)


import threading

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)


class MemoryEfficientList:
    """Memory-efficient list that uses generators where possible."""

    def __init__(self, data: Optional[List[Any]] = None):
        self._data = data if data is not None else []
        self._iterator = None
        self._lock = threading.Lock()

    def append(self, item: Any) -> None:
        """Append item."""
        with self._lock:
            capped_append(self._data, item)

    def extend(self, items: List[Any]) -> None:
        """Extend list with bounded growth."""
        with self._lock:
            for item in items:
                capped_append(self._data, item)

    def batch_iter(self, batch_size: int) -> Generator[List[Any], None, None]:
        """Iterate in batches."""
        for i in range(0, len(self._data), batch_size):
            yield self._data[i:i + batch_size]

    def stream_filter(
        self,
        predicate: Callable[[Any], bool]
    ) -> Generator[Any, None, None]:
        """Stream filtered items."""
        for item in self._data:
            if predicate(item):
                yield item

    def stream_map(
        self,
        transform: Callable[[Any], Any]
    ) -> Generator[Any, None, None]:
        """Stream transformed items."""
        for item in self._data:
            yield transform(item)

    def get_size_estimate(self) -> float:
        """Estimate memory size in MB."""
        try:
            size = sum(sys.getsizeof(item) for item in self._data)
            return size / (1024 * 1024)
        except Exception as exc:
            logger.debug("Suppressed exception: %s", exc)
            return 0.0

    def __len__(self) -> int:
        return len(self._data)

    def __getitem__(self, index: int) -> Any:
        return self._data[index]


class LargeDataHandler:
    """Handle large datasets with memory management."""

    def __init__(self, memory_limit_mb: int = 500):
        self.memory_limit_mb = memory_limit_mb
        self.monitor = MemoryMonitor(memory_limit_mb)
        self.streamer = StreamProcessor(batch_size=1000)
        self.cache = DataCache(max_size_mb=memory_limit_mb // 2)

    def process_large_dataset(
        self,
        dataset: List[Any],
        processor: Callable[[List[Any]], List[Any]]
    ) -> List[Any]:
        """Process large dataset with memory management."""
        results = MemoryEfficientList()

        try:
            for batch_result in self.streamer.stream_data(dataset, processor):
                results.extend(batch_result)

                # Check memory usage
                if self.monitor.is_memory_exceeded():
                    self.monitor.force_gc()

                    if self.monitor.is_memory_exceeded():
                        # Force cache eviction
                        self.cache.clear()
                        self.monitor.force_gc()

        except MemoryError:
            # Handle out of memory gracefully
            self.monitor.force_gc()
            self.cache.clear()
            raise MemoryError("Memory limit exceeded. Try smaller batch sizes.")

        return results._data

    def paginated_query(
        self,
        data_source: List[Any],
        page: int,
        page_size: int
    ) -> PaginatedResult:
        """Get paginated results."""
        total = len(data_source)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size

        data = data_source[start_idx:end_idx]

        return PaginatedResult(
            data=data,
            page=page,
            page_size=page_size,
            total=total
        )

    def get_memory_status(self) -> Dict[str, Any]:
        """Get memory status information."""
        return {
            'current_memory_mb': self.monitor.get_memory_usage(),
            'memory_increase_mb': self.monitor.get_memory_increase(),
            'memory_limit_mb': self.memory_limit_mb,
            'cache_size_mb': self.cache.get_size(),
            'cache_items': self.cache.get_item_count()
        }


def optimize_for_memory(func: Callable[..., T]) -> Callable[..., T]:
    """Decorator to optimize function for memory usage."""
    def wrapper(*args, **kwargs) -> T:
        # Force garbage collection before execution
        gc.collect()

        try:
            result = func(*args, **kwargs)
            return result
        finally:
            # Clean up after execution
            gc.collect()

    return wrapper


def memory_efficient_map(
    data: List[Any],
    transform: Callable[[Any], Any],
    batch_size: int = 1000
) -> Generator[Any, None, None]:
    """Memory-efficient map operation."""
    for i in range(0, len(data), batch_size):
        batch = data[i:i + batch_size]
        for item in batch:
            yield transform(item)
        # Allow garbage collection
        gc.collect()


def memory_efficient_filter(
    data: List[Any],
    predicate: Callable[[Any], bool],
    batch_size: int = 1000
) -> Generator[Any, None, None]:
    """Memory-efficient filter operation."""
    for i in range(0, len(data), batch_size):
        batch = data[i:i + batch_size]
        for item in batch:
            if predicate(item):
                yield item
        # Allow garbage collection
        gc.collect()
