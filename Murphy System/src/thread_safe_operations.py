"""
Thread-safe operations for the Murphy System Runtime.
Provides utilities for concurrent operations without race conditions.
"""

import logging
import queue
import threading
import time
from contextlib import contextmanager
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar('T')


class ThreadSafeCounter:
    """Thread-safe counter with atomic operations."""

    def __init__(self, initial_value: int = 0):
        self._value = initial_value
        self._lock = threading.Lock()

    def increment(self, delta: int = 1) -> int:
        """Atomically increment the counter."""
        with self._lock:
            self._value += delta
            return self._value

    def decrement(self, delta: int = 1) -> int:
        """Atomically decrement the counter."""
        with self._lock:
            self._value -= delta
            return self._value

    def get(self) -> int:
        """Get current value."""
        with self._lock:
            return self._value

    def reset(self) -> int:
        """Reset counter to zero."""
        with self._lock:
            self._value = 0
            return self._value


class ThreadSafeDict:
    """Thread-safe dictionary with lock-based protection."""

    def __init__(self):
        self._dict: Dict[str, Any] = {}
        self._lock = threading.RLock()  # Reentrant lock

    def get(self, key: str, default: Any = None) -> Any:
        """Get value by key."""
        with self._lock:
            return self._dict.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set value by key."""
        with self._lock:
            self._dict[key] = value

    def delete(self, key: str) -> bool:
        """Delete key if exists."""
        with self._lock:
            if key in self._dict:
                del self._dict[key]
                return True
            return False

    def keys(self) -> List[str]:
        """Get all keys."""
        with self._lock:
            return list(self._dict.keys())

    def values(self) -> List[Any]:
        """Get all values."""
        with self._lock:
            return list(self._dict.values())

    def items(self) -> List[tuple]:
        """Get all items."""
        with self._lock:
            return list(self._dict.items())

    def update(self, other: Dict[str, Any]) -> None:
        """Update dictionary with another dictionary."""
        with self._lock:
            self._dict.update(other)

    def clear(self) -> None:
        """Clear all entries."""
        with self._lock:
            self._dict.clear()

    def get_dict(self) -> Dict[str, Any]:
        """Get a copy of the dictionary."""
        with self._lock:
            return self._dict.copy()


class ConnectionPool:
    """Thread-safe connection pool with automatic reuse."""

    def __init__(self, max_connections: int = 10):
        self.max_connections = max_connections
        self._pool: queue.Queue = queue.Queue(maxsize=max_connections)
        self._active_connections = ThreadSafeCounter()
        self._lock = threading.Lock()

    def acquire(self, timeout: float = 5.0) -> Any:
        """Acquire a connection from the pool."""
        try:
            connection = self._pool.get(block=True, timeout=timeout)
            self._active_connections.increment()
            return connection
        except queue.Empty:
            # Create new connection if pool is empty
            with self._lock:
                if self._active_connections.get() < self.max_connections:
                    self._active_connections.increment()
                    return self._create_connection()
            raise Exception("Connection pool exhausted")

    def release(self, connection: Any) -> None:
        """Release a connection back to the pool."""
        try:
            self._pool.put(connection, block=False)
            self._active_connections.decrement()
        except queue.Full:
            # Pool is full, discard connection
            self._active_connections.decrement()

    def _create_connection(self) -> Any:
        """Create a new connection (override in subclasses)."""
        return None

    def get_active_count(self) -> int:
        """Get number of active connections."""
        return self._active_connections.get()

    def get_pool_size(self) -> int:
        """Get current pool size."""
        return self._pool.qsize()


class CircuitBreaker:
    """Circuit breaker pattern for preventing cascading failures."""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: type = Exception
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self._failures = ThreadSafeCounter()
        self._last_failure_time: Optional[float] = None
        self._state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        self._lock = threading.Lock()

    def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Execute function with circuit breaker protection."""
        if self._state == "OPEN":
            if self._should_attempt_reset():
                self._state = "HALF_OPEN"
            else:
                raise Exception("Circuit breaker is OPEN")

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as exc:
            self._on_failure()
            raise exc

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if self._last_failure_time is None:
            return True
        return time.time() - self._last_failure_time >= self.recovery_timeout

    def _on_success(self) -> None:
        """Handle successful call."""
        self._failures.reset()
        if self._state == "HALF_OPEN":
            with self._lock:
                self._state = "CLOSED"

    def _on_failure(self) -> None:
        """Handle failed call."""
        self._failures.increment()
        self._last_failure_time = time.time()

        if self._failures.get() >= self.failure_threshold:
            with self._lock:
                self._state = "OPEN"

    def get_state(self) -> str:
        """Get current circuit breaker state."""
        return self._state

    def get_failure_count(self) -> int:
        """Get current failure count."""
        return self._failures.get()

    def reset(self) -> None:
        """Reset circuit breaker to CLOSED state."""
        self._failures.reset()
        self._last_failure_time = None
        with self._lock:
            self._state = "CLOSED"


def retry_on_failure(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """Decorator to retry function on failure with exponential backoff."""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception = None
            current_delay = delay

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    last_exception = exc
                    if attempt < max_retries:
                        time.sleep(current_delay)
                        current_delay *= backoff_factor
                    else:
                        raise last_exception

            raise last_exception

        return wrapper
    return decorator


@contextmanager
def atomic_operation(lock: threading.Lock):
    """Context manager for atomic operations."""
    lock.acquire()
    try:
        yield
    finally:
        lock.release()


class RateLimiter:
    """Thread-safe rate limiter."""

    def __init__(self, max_calls: int, time_window: float):
        self.max_calls = max_calls
        self.time_window = time_window
        self._calls: List[float] = []
        self._lock = threading.Lock()

    def acquire(self) -> bool:
        """Attempt to acquire permission for a call."""
        with self._lock:
            now = time.time()
            # Remove old calls outside time window
            self._calls = [call_time for call_time in self._calls
                          if now - call_time < self.time_window]

            if len(self._calls) < self.max_calls:
                capped_append(self._calls, now)
                return True
            return False

    def get_call_count(self) -> int:
        """Get current call count in time window."""
        with self._lock:
            now = time.time()
            self._calls = [call_time for call_time in self._calls
                          if now - call_time < self.time_window]
            return len(self._calls)

def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
    """Append *item* to *target_list*, trimming the oldest 10% when the
    cap is reached.  This prevents unbounded memory growth (CWE-770).

    Usage::

        capped_append(self._history, record)
        capped_append(self._audit_log, entry, max_size=5_000)
    """
    if len(target_list) >= max_size:
        del target_list[:max_size // 10]
    target_list.append(item)


def capped_append_paired(
    *lists_and_items: Any,
    max_size: int = 10_000,
) -> None:
    """Atomically append to multiple paired lists, trimming all together.

    Pass alternating (list, item) pairs::

        capped_append_paired(self._events, event, self._results, result)

    All lists are trimmed by the same amount so they stay synchronised.
    """
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
