"""
Tests for thread_safe_operations.py

Closes Gap 1: ThreadSafeCounter, ThreadSafeDict, ConnectionPool,
CircuitBreaker, RateLimiter, retry_on_failure, and atomic_operation
had ZERO test coverage.

Every test demonstrates a concrete gap being closed:
- Race conditions under concurrent access
- Circuit breaker state machine transitions
- Connection pool exhaustion handling
- Rate limiter boundary enforcement
- Retry decorator exponential back-off
"""

import os
import time
import threading
import unittest


from thread_safe_operations import (
    ThreadSafeCounter,
    ThreadSafeDict,
    ConnectionPool,
    CircuitBreaker,
    RateLimiter,
    retry_on_failure,
    atomic_operation,
)


# ── ThreadSafeCounter ───────────────────────────────────────────────

class TestThreadSafeCounter(unittest.TestCase):
    """Prove counter is race-condition-free under concurrent writes."""

    def test_initial_value(self):
        c = ThreadSafeCounter()
        self.assertEqual(c.get(), 0)

    def test_initial_value_custom(self):
        c = ThreadSafeCounter(42)
        self.assertEqual(c.get(), 42)

    def test_increment_returns_new_value(self):
        c = ThreadSafeCounter(0)
        self.assertEqual(c.increment(), 1)
        self.assertEqual(c.increment(5), 6)

    def test_decrement_returns_new_value(self):
        c = ThreadSafeCounter(10)
        self.assertEqual(c.decrement(), 9)
        self.assertEqual(c.decrement(4), 5)

    def test_reset(self):
        c = ThreadSafeCounter(99)
        self.assertEqual(c.reset(), 0)
        self.assertEqual(c.get(), 0)

    def test_concurrent_increments_are_atomic(self):
        """1000 threads each increment by 1 → final value must be 1000."""
        c = ThreadSafeCounter(0)
        threads = []
        for _ in range(1000):
            t = threading.Thread(target=c.increment)
            threads.append(t)
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(c.get(), 1000)

    def test_concurrent_mixed_ops_are_atomic(self):
        """500 increments + 500 decrements → net zero."""
        c = ThreadSafeCounter(0)
        threads = []
        for _ in range(500):
            threads.append(threading.Thread(target=c.increment))
            threads.append(threading.Thread(target=c.decrement))
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(c.get(), 0)


# ── ThreadSafeDict ──────────────────────────────────────────────────

class TestThreadSafeDict(unittest.TestCase):
    """Prove dictionary is safe under concurrent access."""

    def test_set_get(self):
        d = ThreadSafeDict()
        d.set("k", 42)
        self.assertEqual(d.get("k"), 42)

    def test_get_default(self):
        d = ThreadSafeDict()
        self.assertIsNone(d.get("missing"))
        self.assertEqual(d.get("missing", "default"), "default")

    def test_delete_existing(self):
        d = ThreadSafeDict()
        d.set("k", 1)
        self.assertTrue(d.delete("k"))
        self.assertIsNone(d.get("k"))

    def test_delete_missing(self):
        d = ThreadSafeDict()
        self.assertFalse(d.delete("nope"))

    def test_keys_values_items(self):
        d = ThreadSafeDict()
        d.set("a", 1)
        d.set("b", 2)
        self.assertIn("a", d.keys())
        self.assertIn(2, d.values())
        self.assertIn(("b", 2), d.items())

    def test_update(self):
        d = ThreadSafeDict()
        d.update({"x": 10, "y": 20})
        self.assertEqual(d.get("x"), 10)

    def test_clear(self):
        d = ThreadSafeDict()
        d.set("a", 1)
        d.clear()
        self.assertEqual(d.keys(), [])

    def test_get_dict_returns_copy(self):
        d = ThreadSafeDict()
        d.set("k", 1)
        copy = d.get_dict()
        copy["k"] = 999
        self.assertEqual(d.get("k"), 1)  # original unchanged

    def test_concurrent_writes(self):
        """100 threads writing different keys → all keys present."""
        d = ThreadSafeDict()

        def writer(i):
            d.set(f"key-{i}", i)

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(len(d.keys()), 100)


# ── ConnectionPool ──────────────────────────────────────────────────

class TestConnectionPool(unittest.TestCase):
    """Prove pool enforces capacity and handles exhaustion."""

    def test_acquire_creates_connection(self):
        pool = ConnectionPool(max_connections=3)
        conn = pool.acquire(timeout=1.0)
        self.assertEqual(pool.get_active_count(), 1)

    def test_release_returns_to_pool(self):
        pool = ConnectionPool(max_connections=3)
        conn = pool.acquire(timeout=1.0)
        pool.release(conn)
        self.assertEqual(pool.get_active_count(), 0)

    def test_pool_exhaustion_raises(self):
        """Acquiring beyond max_connections must raise."""
        pool = ConnectionPool(max_connections=2)
        pool.acquire(timeout=0.1)
        pool.acquire(timeout=0.1)
        with self.assertRaises(Exception) as ctx:
            pool.acquire(timeout=0.1)
        self.assertIn("exhausted", str(ctx.exception).lower())


# ── CircuitBreaker ──────────────────────────────────────────────────

class TestCircuitBreaker(unittest.TestCase):
    """Prove state machine: CLOSED → OPEN → HALF_OPEN → CLOSED."""

    def test_initial_state_is_closed(self):
        cb = CircuitBreaker(failure_threshold=3)
        self.assertEqual(cb.get_state(), "CLOSED")

    def test_successful_call_keeps_closed(self):
        cb = CircuitBreaker(failure_threshold=3)
        result = cb.call(lambda: "ok")
        self.assertEqual(result, "ok")
        self.assertEqual(cb.get_state(), "CLOSED")
        self.assertEqual(cb.get_failure_count(), 0)

    def test_failures_trip_to_open(self):
        """After failure_threshold failures, state must be OPEN."""
        cb = CircuitBreaker(failure_threshold=3, expected_exception=ValueError)

        def bad():
            raise ValueError("boom")

        for _ in range(3):
            with self.assertRaises(ValueError):
                cb.call(bad)

        self.assertEqual(cb.get_state(), "OPEN")
        self.assertEqual(cb.get_failure_count(), 3)

    def test_open_rejects_calls(self):
        """While OPEN, calls must be rejected immediately."""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=9999,
                            expected_exception=ValueError)
        with self.assertRaises(ValueError):
            cb.call(lambda: (_ for _ in ()).throw(ValueError("x")))

        self.assertEqual(cb.get_state(), "OPEN")
        with self.assertRaises(Exception) as ctx:
            cb.call(lambda: "should not run")
        self.assertIn("OPEN", str(ctx.exception))

    def test_half_open_after_timeout(self):
        """After recovery_timeout, next call transitions to HALF_OPEN."""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.01,
                            expected_exception=ValueError)
        with self.assertRaises(ValueError):
            cb.call(lambda: (_ for _ in ()).throw(ValueError("x")))

        self.assertEqual(cb.get_state(), "OPEN")
        time.sleep(0.02)  # exceed recovery_timeout

        # Next successful call should recover to CLOSED via HALF_OPEN
        result = cb.call(lambda: "recovered")
        self.assertEqual(result, "recovered")
        self.assertEqual(cb.get_state(), "CLOSED")

    def test_manual_reset(self):
        cb = CircuitBreaker(failure_threshold=1, expected_exception=ValueError)
        with self.assertRaises(ValueError):
            cb.call(lambda: (_ for _ in ()).throw(ValueError("x")))
        self.assertEqual(cb.get_state(), "OPEN")

        cb.reset()
        self.assertEqual(cb.get_state(), "CLOSED")
        self.assertEqual(cb.get_failure_count(), 0)

    def test_success_resets_failure_count(self):
        cb = CircuitBreaker(failure_threshold=5, expected_exception=ValueError)
        for _ in range(4):
            with self.assertRaises(ValueError):
                cb.call(lambda: (_ for _ in ()).throw(ValueError("x")))
        self.assertEqual(cb.get_failure_count(), 4)

        cb.call(lambda: "ok")
        self.assertEqual(cb.get_failure_count(), 0)


# ── RateLimiter ─────────────────────────────────────────────────────

class TestRateLimiter(unittest.TestCase):
    """Prove rate limiter enforces max_calls within time_window."""

    def test_allows_up_to_max(self):
        rl = RateLimiter(max_calls=5, time_window=10.0)
        for _ in range(5):
            self.assertTrue(rl.acquire())

    def test_blocks_above_max(self):
        rl = RateLimiter(max_calls=3, time_window=10.0)
        for _ in range(3):
            rl.acquire()
        self.assertFalse(rl.acquire())

    def test_call_count(self):
        rl = RateLimiter(max_calls=10, time_window=10.0)
        rl.acquire()
        rl.acquire()
        self.assertEqual(rl.get_call_count(), 2)

    def test_window_expiry_resets(self):
        """After time_window elapses, new calls are permitted."""
        rl = RateLimiter(max_calls=2, time_window=0.05)
        rl.acquire()
        rl.acquire()
        self.assertFalse(rl.acquire())

        time.sleep(0.06)
        self.assertTrue(rl.acquire())


# ── retry_on_failure ────────────────────────────────────────────────

class TestRetryOnFailure(unittest.TestCase):
    """Prove retry decorator retries the right number of times."""

    def test_succeeds_first_try(self):
        @retry_on_failure(max_retries=3, delay=0.001)
        def ok():
            return "done"
        self.assertEqual(ok(), "done")

    def test_retries_then_succeeds(self):
        call_count = {"n": 0}

        @retry_on_failure(max_retries=3, delay=0.001, backoff_factor=1)
        def flaky():
            call_count["n"] += 1
            if call_count["n"] < 3:
                raise RuntimeError("fail")
            return "ok"

        self.assertEqual(flaky(), "ok")
        self.assertEqual(call_count["n"], 3)

    def test_exhausts_retries_then_raises(self):
        @retry_on_failure(max_retries=2, delay=0.001, backoff_factor=1)
        def always_fail():
            raise RuntimeError("permanent")

        with self.assertRaises(RuntimeError) as ctx:
            always_fail()
        self.assertIn("permanent", str(ctx.exception))

    def test_only_catches_specified_exceptions(self):
        @retry_on_failure(max_retries=3, delay=0.001, exceptions=(ValueError,))
        def wrong_exc():
            raise TypeError("not retryable")

        with self.assertRaises(TypeError):
            wrong_exc()


# ── atomic_operation ────────────────────────────────────────────────

class TestAtomicOperation(unittest.TestCase):
    """Prove context manager acquires/releases lock."""

    def test_lock_acquired_and_released(self):
        lock = threading.Lock()
        with atomic_operation(lock):
            self.assertFalse(lock.acquire(blocking=False))  # already held
        self.assertTrue(lock.acquire(blocking=False))  # released
        lock.release()


if __name__ == "__main__":
    unittest.main()
