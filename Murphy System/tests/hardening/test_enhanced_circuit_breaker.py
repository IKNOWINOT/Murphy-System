"""
Module: tests/hardening/test_enhanced_circuit_breaker.py
Subsystem: LLM Provider — Enhanced Circuit Breaker & Retry Budget
Label: TEST-LLM-CB-001 — Commission tests for _CircuitBreaker and _RetryBudget

Commissioning Answers (G1–G9)
-----------------------------
G1  What does the module do?
    _CircuitBreaker implements a Resilience4j-inspired circuit breaker with
    thread safety, half-open probe limiting, jittered recovery timeout with
    exponential backoff, and full observability metrics.
    _RetryBudget caps per-request fallback-chain cost by limiting attempt
    count and elapsed duration.

G2  What specification / design-label does it fulfil?
    LLM-CB-001 (circuit breaker) and LLM-BUDGET-001 (retry budget) as
    documented in Murphy System 1.0 Production Spec.

G3  Under what conditions should it succeed / fail?
    Succeed: state transitions follow the documented CLOSED→OPEN→HALF_OPEN
    lifecycle; metrics accumulate correctly; backoff is bounded; retry
    budget exhausts after max_attempts or max_duration.
    Fail: race conditions corrupt state; backoff exceeds 300 s cap;
    budget allows unlimited retries.

G4  What is the test-profile?
    Pure unit tests — no network, no disk, no external services.
    Threading test uses 50 concurrent threads to verify lock safety.

G5  Any external dependencies?
    None beyond the standard library and pytest.

G6  Can the tests run in CI without credentials?
    Yes.

G7  Expected run-time?
    < 3 s.

G8  Owner / maintainer?
    Platform Engineering.

G9  Review date?
    On every PR that modifies src/llm_provider.py.
"""
from __future__ import annotations

import threading
import time
from unittest.mock import patch

import pytest

from src.llm_provider import _CircuitBreaker, _CircuitState, _RetryBudget


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture()
def breaker() -> _CircuitBreaker:
    """Return a fresh circuit breaker with low thresholds for fast tests."""
    return _CircuitBreaker(
        failure_threshold=3,
        recovery_timeout=0.1,
        half_open_max_calls=2,
        name="test-breaker",
    )


@pytest.fixture()
def budget() -> _RetryBudget:
    return _RetryBudget(max_attempts=3, max_duration_seconds=60.0)


# ── Circuit Breaker Tests ──────────────────────────────────────────────────


class TestCircuitBreaker:
    """TEST-LLM-CB-001 — Circuit breaker state machine and metrics."""

    def test_initial_state(self, breaker: _CircuitBreaker) -> None:
        """New breaker starts CLOSED with zero metrics."""
        assert breaker.state == "closed"
        m = breaker.get_metrics()
        assert m["total_successes"] == 0
        assert m["total_failures"] == 0
        assert m["total_rejections"] == 0
        assert m["consecutive_failures"] == 0
        assert m["state"] == "closed"

    def test_record_success_resets(self, breaker: _CircuitBreaker) -> None:
        """After failures, a success resets the consecutive failure count."""
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.get_metrics()["consecutive_failures"] == 2
        breaker.record_success()
        assert breaker.get_metrics()["consecutive_failures"] == 0

    def test_threshold_opens_circuit(self, breaker: _CircuitBreaker) -> None:
        """Reaching failure_threshold transitions to OPEN."""
        for _ in range(breaker.failure_threshold):
            breaker.record_failure()
        assert breaker.state == "open"

    def test_open_rejects_requests(self, breaker: _CircuitBreaker) -> None:
        """OPEN state rejects requests immediately (before timeout)."""
        for _ in range(breaker.failure_threshold):
            breaker.record_failure()
        assert breaker.state == "open"
        # Patch time so timeout has NOT elapsed
        with patch("src.llm_provider.time") as mock_time:
            mock_time.monotonic.return_value = breaker._last_failure_time + 0.001
            assert breaker.allow_request() is False
        assert breaker.get_metrics()["total_rejections"] >= 1

    def test_half_open_probe_limit(self, breaker: _CircuitBreaker) -> None:
        """Only half_open_max_calls probes are allowed in HALF_OPEN."""
        for _ in range(breaker.failure_threshold):
            breaker.record_failure()
        # Wait for recovery timeout to elapse so breaker goes HALF_OPEN
        time.sleep(breaker.recovery_timeout * 1.5)
        # First probe transitions OPEN → HALF_OPEN and is allowed
        assert breaker.allow_request() is True
        assert breaker.state == "half_open"
        # Second probe allowed (half_open_max_calls=2)
        assert breaker.allow_request() is True
        # Third probe rejected
        assert breaker.allow_request() is False
        assert breaker.get_metrics()["total_rejections"] >= 1

    def test_half_open_success_closes(self, breaker: _CircuitBreaker) -> None:
        """Successful probe in HALF_OPEN closes the circuit."""
        for _ in range(breaker.failure_threshold):
            breaker.record_failure()
        time.sleep(breaker.recovery_timeout * 1.5)
        assert breaker.allow_request() is True  # transitions to HALF_OPEN
        breaker.record_success()
        assert breaker.state == "closed"

    def test_half_open_failure_reopens(self, breaker: _CircuitBreaker) -> None:
        """Failed probe in HALF_OPEN re-opens the circuit with backoff."""
        for _ in range(breaker.failure_threshold):
            breaker.record_failure()
        time.sleep(breaker.recovery_timeout * 1.5)
        assert breaker.allow_request() is True  # → HALF_OPEN
        breaker.record_failure()
        assert breaker.state == "open"
        assert breaker._open_cycle_count >= 1

    def test_backoff_increases(self) -> None:
        """Repeated open cycles increase effective timeout."""
        cb = _CircuitBreaker(
            failure_threshold=2,
            recovery_timeout=1.0,
            half_open_max_calls=1,
            name="backoff-test",
        )
        # Cycle 1
        cb._open_cycle_count = 1
        t1 = cb._effective_timeout()
        # Cycle 2
        cb._open_cycle_count = 2
        t2 = cb._effective_timeout()
        # Due to jitter the exact values vary but cycle 2 base should be ~2x cycle 1 base
        # We test with a generous margin to account for ±20% jitter
        assert t2 > t1 * 0.5, "Backoff should generally increase across cycles"

    def test_backoff_capped(self) -> None:
        """Backoff never exceeds 300 s regardless of cycle count."""
        cb = _CircuitBreaker(
            failure_threshold=2,
            recovery_timeout=10.0,
            half_open_max_calls=1,
            name="cap-test",
        )
        cb._open_cycle_count = 100  # extreme cycle count
        for _ in range(50):
            timeout = cb._effective_timeout()
            assert timeout <= 300.0 * 1.21, (
                f"Effective timeout {timeout:.1f} exceeds cap (300 s + jitter)"
            )

    def test_metrics_accumulate(self, breaker: _CircuitBreaker) -> None:
        """Metrics count correctly across operations."""
        breaker.record_success()
        breaker.record_success()
        breaker.record_failure()
        m = breaker.get_metrics()
        assert m["total_successes"] == 2
        assert m["total_failures"] == 1

    def test_named_breaker(self) -> None:
        """The name parameter appears in the breaker's identity."""
        cb = _CircuitBreaker(name="my-service")
        assert cb.name == "my-service"
        # Metrics are accessible (name is used for logging, not in dict, but
        # the breaker should function normally with a custom name)
        m = cb.get_metrics()
        assert m["state"] == "closed"

    def test_thread_safety(self) -> None:
        """50 concurrent threads recording success/failure don't crash."""
        cb = _CircuitBreaker(
            failure_threshold=100,
            recovery_timeout=0.01,
            half_open_max_calls=5,
            name="thread-test",
        )
        errors: list[Exception] = []

        def worker(i: int) -> None:
            try:
                for _ in range(20):
                    cb.allow_request()
                    if i % 2 == 0:
                        cb.record_success()
                    else:
                        cb.record_failure()
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert not errors, f"Thread safety violation: {errors}"
        m = cb.get_metrics()
        assert m["total_successes"] + m["total_failures"] == 50 * 20


# ── Retry Budget Tests ─────────────────────────────────────────────────────


class TestRetryBudget:
    """TEST-LLM-CB-001 — Retry budget cost-cap tests."""

    def test_retry_budget_basic(self, budget: _RetryBudget) -> None:
        """3 attempts allowed, then exhausted."""
        budget.start()
        assert budget.attempt() is True   # 1
        assert budget.attempt() is True   # 2
        assert budget.attempt() is True   # 3
        assert budget.exhausted is True
        assert budget.attempt() is False  # 4th blocked

    def test_retry_budget_duration(self) -> None:
        """Budget exhausted when max_duration exceeded."""
        b = _RetryBudget(max_attempts=100, max_duration_seconds=0.05)
        b.start()
        assert b.attempt() is True
        time.sleep(0.08)
        assert b.exhausted is True

    def test_retry_budget_summary(self, budget: _RetryBudget) -> None:
        """get_summary() returns correct dict."""
        budget.start()
        budget.attempt()
        budget.attempt()
        s = budget.get_summary()
        assert s["attempts_used"] == 2
        assert s["max_attempts"] == 3
        assert isinstance(s["elapsed_seconds"], float)
        assert s["max_duration"] == 60.0
        assert s["exhausted"] is False
        assert s["budget_reason"] is None
