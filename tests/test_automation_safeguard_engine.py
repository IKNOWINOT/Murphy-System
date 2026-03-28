"""
Tests for AutomationSafeguardEngine — Murphy System

Covers all 7 guard primitives across every automation failure mode:
  1. RunawayLoopGuard — iteration cap + wall-clock timeout
  2. EventStormSuppressor — sliding window + debounce
  3. FeedbackOscillationDetector — sign-change threshold
  4. CascadeBreaker — dependency-aware circuit breaker
  5. IdempotencyGuard — SHA-256 content-hash dedup with TTL
  6. TrackingAccumulationWatcher — unbounded growth detection
  7. DeadlockDetector — wait-for graph cycle detection + starvation

Also tests:
  - AutomationSafeguardEngine top-level orchestration
  - check_all() health status
  - Thread safety across all guards
  - Command registry integration
  - Module-level get_status() and get_engine() singleton
"""

from __future__ import annotations

import sys
import os
import time
import threading
from typing import Any, Dict, List

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

from automation_safeguard_engine import (
    AutomationSafeguardEngine,
    CascadeBreaker,
    DeadlockDetector,
    EventStormSuppressor,
    FeedbackOscillationDetector,
    IdempotencyGuard,
    RunawayLoopError,
    RunawayLoopGuard,
    SafeguardEvent,
    TrackingAccumulationWatcher,
    get_engine,
    get_status,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def engine() -> AutomationSafeguardEngine:
    """Fresh engine instance for each test."""
    return AutomationSafeguardEngine()


# ===========================================================================
# 1. RunawayLoopGuard
# ===========================================================================

class TestRunawayLoopGuard:
    """SAFE-001 — Prevents runaway loops and infinite regeneration."""

    def test_normal_loop_completes_without_error(self):
        guard = RunawayLoopGuard("normal", max_iterations=100, max_seconds=10.0)
        with guard:
            for _ in range(50):
                guard.tick()

    def test_iteration_cap_raises(self):
        guard = RunawayLoopGuard("iter_cap", max_iterations=10, max_seconds=60.0)
        with guard:
            with pytest.raises(RunawayLoopError, match="iteration cap exceeded"):
                for _ in range(20):
                    guard.tick()

    def test_iteration_cap_exact_boundary(self):
        """Exactly max_iterations ticks should NOT raise."""
        guard = RunawayLoopGuard("boundary", max_iterations=5, max_seconds=60.0)
        with guard:
            for _ in range(5):
                guard.tick()  # should not raise

    def test_wall_clock_timeout_raises(self):
        guard = RunawayLoopGuard("timeout", max_iterations=1_000_000, max_seconds=0.05)
        with guard:
            with pytest.raises(RunawayLoopError, match="wall-clock timeout"):
                for _ in range(1_000_000):
                    guard.tick()
                    time.sleep(0.001)

    def test_trips_counter_increments(self):
        guard = RunawayLoopGuard("trip_count", max_iterations=3, max_seconds=60.0)
        for _ in range(3):
            try:
                with guard:
                    for _ in range(10):
                        guard.tick()
            except RunawayLoopError:
                pass
        assert guard.get_status()["trips"] == 3

    def test_on_runaway_callback_fires(self):
        fired: List[str] = []
        guard = RunawayLoopGuard(
            "callback", max_iterations=2, max_seconds=60.0,
            on_runaway=lambda name, reason: fired.append(name),
        )
        try:
            with guard:
                for _ in range(5):
                    guard.tick()
        except RunawayLoopError:
            pass
        assert "callback" in fired

    def test_tick_outside_context_is_noop(self):
        """tick() while not active must not raise."""
        guard = RunawayLoopGuard("noop", max_iterations=1, max_seconds=1.0)
        guard.tick()  # not started → noop

    def test_context_manager_resets_on_entry(self):
        guard = RunawayLoopGuard("reset", max_iterations=5, max_seconds=60.0)
        try:
            with guard:
                for _ in range(10):
                    guard.tick()
        except RunawayLoopError:
            pass
        # Second entry should reset iteration count
        with guard:
            for _ in range(3):
                guard.tick()  # should NOT raise

    def test_get_status_fields(self):
        guard = RunawayLoopGuard("status", max_iterations=100, max_seconds=30.0)
        status = guard.get_status()
        assert "name" in status
        assert "active" in status
        assert "iteration_count" in status
        assert "trips" in status

    def test_engine_loop_guard_factory(self, engine: AutomationSafeguardEngine):
        """engine.loop_guard() creates and caches guards."""
        g1 = engine.loop_guard("my_loop")
        g2 = engine.loop_guard("my_loop")
        assert g1 is g2  # Same instance

    def test_engine_loop_guard_custom_limits(self, engine: AutomationSafeguardEngine):
        g = engine.loop_guard("custom_loop", max_iterations=50, max_seconds=5.0)
        assert g.max_iterations == 50
        assert g.max_seconds == 5.0


# ===========================================================================
# 2. EventStormSuppressor
# ===========================================================================

class TestEventStormSuppressor:
    """SAFE-002 — Prevents event storms and floods."""

    def test_normal_rate_allowed(self):
        sup = EventStormSuppressor("test", max_per_window=100, window_sec=1.0)
        for i in range(50):
            assert sup.allow(f"key_{i}") is True  # unique keys avoid debounce

    def test_rate_limit_blocks_overflow(self):
        sup = EventStormSuppressor("test", max_per_window=5, window_sec=10.0, debounce_sec=0.0)
        for i in range(5):
            assert sup.allow(f"key_{i}") is True
        # 6th event should be blocked
        assert sup.allow("overflow") is False

    def test_debounce_blocks_same_key(self):
        sup = EventStormSuppressor("debounce_test", max_per_window=1000, window_sec=10.0,
                                   debounce_sec=5.0)
        assert sup.allow("same_event") is True
        # Immediate re-trigger should be blocked
        assert sup.allow("same_event") is False

    def test_different_keys_not_debounced(self):
        sup = EventStormSuppressor("diff_keys", max_per_window=1000, window_sec=10.0,
                                   debounce_sec=5.0)
        assert sup.allow("event_a") is True
        assert sup.allow("event_b") is True  # different key — allowed

    def test_blocked_count_increments(self):
        sup = EventStormSuppressor("count", max_per_window=2, window_sec=10.0, debounce_sec=0.0)
        sup.allow("a")
        sup.allow("b")
        sup.allow("c")  # blocked
        sup.allow("d")  # blocked
        assert sup.get_status()["blocked_count"] == 2

    def test_on_storm_callback_fires(self):
        fired: List[str] = []
        sup = EventStormSuppressor("storm_cb", max_per_window=1, window_sec=10.0,
                                   debounce_sec=0.0,
                                   on_storm=lambda name, detail: fired.append(name))
        sup.allow("a")
        sup.allow("b")  # triggers storm
        assert "storm_cb" in fired

    def test_window_resets_over_time(self):
        sup = EventStormSuppressor("reset_test", max_per_window=2, window_sec=0.1,
                                   debounce_sec=0.0)
        sup.allow("a")
        sup.allow("b")
        assert sup.allow("c") is False  # blocked
        time.sleep(0.15)
        assert sup.allow("c") is True  # window expired — allowed again

    def test_get_status_fields(self):
        sup = EventStormSuppressor("status_test")
        status = sup.get_status()
        assert "max_per_window" in status
        assert "window_sec" in status
        assert "blocked_count" in status
        assert "allowed_count" in status

    def test_empty_key_uses_rate_only(self):
        """Empty key skips debounce check, only rate limit applies."""
        sup = EventStormSuppressor("empty_key", max_per_window=5, window_sec=10.0,
                                   debounce_sec=100.0)
        for _ in range(5):
            assert sup.allow("") is True  # empty key skips debounce


# ===========================================================================
# 3. FeedbackOscillationDetector
# ===========================================================================

class TestFeedbackOscillationDetector:
    """SAFE-003 — Detects feedback oscillation in control loops."""

    def test_stable_signal_not_oscillating(self):
        det = FeedbackOscillationDetector("stable", window=10, max_sign_changes=4)
        for v in [10.0, 10.1, 10.2, 10.3, 10.4, 10.5]:
            det.record(v)
        assert det.is_oscillating() is False

    def test_oscillating_signal_detected(self):
        det = FeedbackOscillationDetector("osc", window=20, max_sign_changes=3)
        # Alternating up/down = maximum sign changes
        for i in range(20):
            det.record(10.0 + (5.0 * ((-1) ** i)))
        assert det.is_oscillating() is True

    def test_oscillation_trips_counter(self):
        fired: List[float] = []
        det = FeedbackOscillationDetector("trips", window=10, max_sign_changes=2,
                                          on_oscillation=lambda name, rate: fired.append(rate))
        # Inject clearly oscillating signal
        for i in range(15):
            det.record(100.0 if i % 2 == 0 else -100.0)
        assert det.get_status()["oscillation_trips"] > 0

    def test_insufficient_samples_not_oscillating(self):
        det = FeedbackOscillationDetector("few", window=20, max_sign_changes=3)
        det.record(1.0)
        det.record(2.0)
        assert det.is_oscillating() is False

    def test_pid_overshoot_recovery_detected(self):
        """Classic PID ringing pattern: overshoot, undershoot, converge."""
        det = FeedbackOscillationDetector("pid", window=20, max_sign_changes=4)
        setpoint = 100.0
        # Simulate ringing: 150, 70, 120, 85, 108, 95, 102, 98, 101 ...
        ringing = [150.0, 70.0, 120.0, 85.0, 108.0, 95.0, 102.0, 98.0, 101.0, 99.0,
                   100.5, 99.8, 100.1, 99.9, 100.0]
        for v in ringing:
            det.record(v)
        assert det.is_oscillating() is True

    def test_get_status_fields(self):
        det = FeedbackOscillationDetector("status")
        status = det.get_status()
        assert "window" in status
        assert "max_sign_changes" in status
        assert "oscillating" in status
        assert "oscillation_trips" in status
        assert "recent_sign_changes" in status


# ===========================================================================
# 4. CascadeBreaker
# ===========================================================================

class TestCascadeBreaker:
    """SAFE-004 — Dependency-aware cascade circuit breaker."""

    def test_closed_breaker_allows_calls(self):
        cb = CascadeBreaker("test")
        cb.register("db")
        assert cb.is_open("db") is False

    def test_breaker_opens_after_failure_threshold(self):
        cb = CascadeBreaker("test", trip_ratio=0.5, window_sec=60.0)
        cb.register("api")
        cb.record_failure("api")
        cb.record_failure("api")
        cb.record_failure("api")
        assert cb.is_open("api") is True

    def test_success_resets_failure_ratio(self):
        cb = CascadeBreaker("test", trip_ratio=0.5, window_sec=60.0)
        cb.register("api")
        cb.record_success("api")
        cb.record_success("api")
        cb.record_failure("api")  # 1 failure / 3 total = 33% < 50% → stays closed
        assert cb.is_open("api") is False

    def test_cascade_opens_dependents(self):
        cb = CascadeBreaker("test", trip_ratio=0.5, window_sec=60.0)
        # billing_service is the upstream provider; stripe depends on it
        cb.register("billing_service")
        cb.register("stripe", depends_on=["billing_service"])
        # billing_service fails → stripe (its dependent consumer) should also open
        for _ in range(5):
            cb.record_failure("billing_service")
        assert cb.is_open("billing_service") is True
        assert cb.is_open("stripe") is True

    def test_max_open_cap_respected(self):
        cb = CascadeBreaker("test", trip_ratio=0.5, window_sec=60.0, max_open=2)
        for i in range(5):
            comp = f"service_{i}"
            cb.register(comp)
            for _ in range(5):
                cb.record_failure(comp)
        # At most max_open=2 breakers should be open
        assert cb.get_status()["open_count"] <= 2

    def test_half_open_after_reset_timeout(self):
        cb = CascadeBreaker("test", trip_ratio=0.5, window_sec=60.0, reset_sec=0.05)
        cb.register("svc")
        for _ in range(5):
            cb.record_failure("svc")
        assert cb.is_open("svc") is True
        time.sleep(0.1)
        # After reset_sec, is_open should return False (half-open probe)
        assert cb.is_open("svc") is False

    def test_on_trip_callback_fires(self):
        fired: List[str] = []
        cb = CascadeBreaker("test", trip_ratio=0.5,
                            on_trip=lambda comp, opened: fired.append(comp))
        cb.register("svc")
        for _ in range(5):
            cb.record_failure("svc")
        assert "svc" in fired

    def test_unknown_component_treated_as_closed(self):
        cb = CascadeBreaker("test")
        assert cb.is_open("nonexistent") is False

    def test_get_status_fields(self):
        cb = CascadeBreaker("status")
        status = cb.get_status()
        assert "components" in status
        assert "open_count" in status
        assert "trip_ratio" in status


# ===========================================================================
# 5. IdempotencyGuard
# ===========================================================================

class TestIdempotencyGuard:
    """SAFE-005 — Prevents duplicate/double-trigger execution."""

    def test_new_payload_is_allowed(self):
        guard = IdempotencyGuard("test")
        assert guard.is_new({"action": "send_email", "to": "alice@example.com"}) is True

    def test_duplicate_payload_is_blocked(self):
        guard = IdempotencyGuard("test", ttl_sec=60.0)
        payload = {"action": "charge_card", "amount": 9.99, "card": "tok_xxx"}
        assert guard.is_new(payload) is True
        assert guard.is_new(payload) is False

    def test_different_payloads_both_allowed(self):
        guard = IdempotencyGuard("test")
        assert guard.is_new({"id": "order_001"}) is True
        assert guard.is_new({"id": "order_002"}) is True

    def test_ttl_expiry_allows_reprocessing(self):
        guard = IdempotencyGuard("test", ttl_sec=0.05)
        payload = {"event": "webhook_001"}
        assert guard.is_new(payload) is True
        time.sleep(0.1)
        assert guard.is_new(payload) is True  # TTL expired

    def test_mark_seen_prevents_reprocessing(self):
        guard = IdempotencyGuard("test", ttl_sec=60.0)
        payload = {"event": "payment_confirmed"}
        guard.mark_seen(payload)
        assert guard.is_new(payload) is False

    def test_blocked_count_increments(self):
        guard = IdempotencyGuard("test")
        p = {"x": 1}
        guard.is_new(p)
        guard.is_new(p)
        guard.is_new(p)
        assert guard.get_status()["blocked_count"] == 2

    def test_non_serialisable_payload_handled(self):
        """Non-JSON-serialisable objects fall back to str()."""
        guard = IdempotencyGuard("test")
        class NonSerializable:
            def __repr__(self): return "NonSer"
        obj = NonSerializable()
        assert guard.is_new(obj) is True
        assert guard.is_new(obj) is False  # str() is deterministic

    def test_large_payload_hashed_correctly(self):
        guard = IdempotencyGuard("test")
        large = {"data": "x" * 100_000}
        assert guard.is_new(large) is True
        assert guard.is_new(large) is False

    def test_key_order_invariant(self):
        """Payloads that differ only in key order should be treated as duplicates."""
        guard = IdempotencyGuard("test")
        assert guard.is_new({"a": 1, "b": 2}) is True
        assert guard.is_new({"b": 2, "a": 1}) is False  # same after sort_keys

    def test_cache_bounded(self):
        guard = IdempotencyGuard("test", ttl_sec=3600.0, max_cache=10)
        for i in range(15):
            guard.is_new({"id": i})
        assert guard.get_status()["cache_size"] <= 10

    def test_get_status_fields(self):
        guard = IdempotencyGuard("status")
        status = guard.get_status()
        assert "ttl_sec" in status
        assert "cache_size" in status
        assert "blocked_count" in status
        assert "allowed_count" in status


# ===========================================================================
# 6. TrackingAccumulationWatcher
# ===========================================================================

class TestTrackingAccumulationWatcher:
    """SAFE-006 — Detects unbounded tracking/memory accumulation."""

    def test_stable_collection_no_alert(self):
        data: List[int] = list(range(100))
        watcher = TrackingAccumulationWatcher("test", growth_threshold_pct=50.0,
                                              alert_after_n_checks=3)
        watcher.register("list", lambda: len(data))
        for _ in range(5):
            alerts = watcher.check()
            assert not alerts

    def test_growing_collection_triggers_alert(self):
        data: List[int] = []
        watcher = TrackingAccumulationWatcher("test", growth_threshold_pct=10.0,
                                              alert_after_n_checks=2)
        watcher.register("list", lambda: len(data))
        data.extend(range(100))
        watcher.check()
        data.extend(range(200))
        watcher.check()
        data.extend(range(400))
        alerts = watcher.check()
        assert len(alerts) > 0

    def test_hard_max_exceeded_triggers_alert(self):
        data: List[int] = list(range(500))
        watcher = TrackingAccumulationWatcher("test")
        watcher.register("list", lambda: len(data), max_size=200)
        alerts = watcher.check()
        assert any("exceeded max_size" in a for a in alerts)

    def test_alert_callback_fires(self):
        fired: List[str] = []
        data: List[int] = list(range(1000))
        watcher = TrackingAccumulationWatcher("test",
                                              on_accumulation=lambda name, msg: fired.append(name))
        watcher.register("big_list", lambda: len(data), max_size=100)
        watcher.check()
        assert "big_list" in fired

    def test_multiple_collections_monitored(self):
        a: List[int] = []
        b: Dict[str, int] = {}
        watcher = TrackingAccumulationWatcher("test")
        watcher.register("list_a", lambda: len(a))
        watcher.register("dict_b", lambda: len(b))
        status = watcher.get_status()
        assert "list_a" in status["monitored_collections"]
        assert "dict_b" in status["monitored_collections"]

    def test_size_fn_exception_handled_gracefully(self):
        """size_fn that raises must not crash check()."""
        def bad_fn() -> int:
            raise RuntimeError("simulated error")
        watcher = TrackingAccumulationWatcher("test")
        watcher.register("broken", bad_fn)
        alerts = watcher.check()  # should not raise

    def test_alerts_fired_counter(self):
        data = list(range(1000))
        watcher = TrackingAccumulationWatcher("test")
        watcher.register("big", lambda: len(data), max_size=100)
        watcher.check()
        watcher.check()
        assert watcher.get_status()["alerts_fired"] >= 2

    def test_get_status_fields(self):
        watcher = TrackingAccumulationWatcher("status")
        status = watcher.get_status()
        assert "monitored_collections" in status
        assert "current_sizes" in status
        assert "alerts_fired" in status


# ===========================================================================
# 7. DeadlockDetector
# ===========================================================================

class TestDeadlockDetector:
    """SAFE-007 — Detects deadlocks and lock starvation."""

    def test_no_deadlock_single_holder(self):
        det = DeadlockDetector("test")
        det.acquire("task_A", "lock_1")
        assert det.has_deadlock() is False

    def test_simple_deadlock_detected(self):
        det = DeadlockDetector("test")
        det.acquire("task_A", "lock_1")  # A holds lock_1
        det.acquire("task_B", "lock_2")  # B holds lock_2
        det.acquire("task_A", "lock_2")  # A waits for lock_2 (held by B)
        det.acquire("task_B", "lock_1")  # B waits for lock_1 (held by A) → cycle!
        assert det.has_deadlock() is True

    def test_release_resolves_cycle(self):
        det = DeadlockDetector("test")
        det.acquire("A", "lock_x")
        det.acquire("B", "lock_y")
        det.acquire("A", "lock_y")  # A waits
        det.acquire("B", "lock_x")  # deadlock
        assert det.has_deadlock() is True
        det.release("B", "lock_x")
        # After B releases lock_x, A can acquire → no cycle
        det.acquire("A", "lock_x")  # A now holds lock_x (was released)
        assert det.has_deadlock() is False

    def test_starvation_detected(self):
        det = DeadlockDetector("test", starvation_timeout_sec=0.01)
        det.acquire("A", "lock_1")  # A holds
        det.acquire("B", "lock_1")  # B waits
        time.sleep(0.05)
        starved = det.check_starvation()
        assert "B" in starved

    def test_no_starvation_within_timeout(self):
        det = DeadlockDetector("test", starvation_timeout_sec=60.0)
        det.acquire("A", "lock_1")
        det.acquire("B", "lock_1")
        starved = det.check_starvation()
        assert not starved

    def test_on_deadlock_callback_fires(self):
        fired: List[str] = []
        det = DeadlockDetector("test",
                               on_deadlock=lambda name, cycle: fired.append(name))
        det.acquire("A", "l1")
        det.acquire("B", "l2")
        det.acquire("A", "l2")
        det.acquire("B", "l1")
        assert "test" in fired

    def test_emergency_release_all(self):
        det = DeadlockDetector("test")
        det.acquire("A", "l1")
        det.acquire("B", "l2")
        count = det.emergency_release_all()
        assert count >= 2
        assert det.get_status()["held_locks"] == 0
        assert det.get_status()["waiters"] == 0

    def test_three_way_deadlock(self):
        det = DeadlockDetector("test")
        det.acquire("A", "lock_1")
        det.acquire("B", "lock_2")
        det.acquire("C", "lock_3")
        det.acquire("A", "lock_2")  # A waits for B's lock
        det.acquire("B", "lock_3")  # B waits for C's lock
        det.acquire("C", "lock_1")  # C waits for A's lock → 3-way cycle
        assert det.has_deadlock() is True

    def test_acquire_free_lock_does_not_wait(self):
        """Acquiring a free lock should set holder immediately, not register as waiter."""
        det = DeadlockDetector("test")
        det.acquire("A", "free_lock")
        status = det.get_status()
        assert status["waiters"] == 0
        assert status["held_locks"] == 1

    def test_get_status_fields(self):
        det = DeadlockDetector("status")
        status = det.get_status()
        assert "held_locks" in status
        assert "waiters" in status
        assert "deadlock_count" in status
        assert "starvation_count" in status
        assert "has_deadlock" in status


# ===========================================================================
# AutomationSafeguardEngine — top-level orchestrator
# ===========================================================================

class TestAutomationSafeguardEngine:
    """SAFE-100 — Engine orchestration, check_all(), get_status()."""

    def test_check_all_healthy_when_nothing_wrong(self, engine: AutomationSafeguardEngine):
        health = engine.check_all()
        assert health["healthy"] is True
        assert "guards" in health
        assert "event_storm" in health["guards"]
        assert "cascade_breaker" in health["guards"]
        assert "idempotency" in health["guards"]
        assert "accumulation_watcher" in health["guards"]
        assert "deadlock_detector" in health["guards"]
        assert "oscillation" in health["guards"]

    def test_check_all_unhealthy_when_cascade_open(self, engine: AutomationSafeguardEngine):
        engine.cascade_breaker.register("broken_svc")
        for _ in range(10):
            engine.cascade_breaker.record_failure("broken_svc")
        health = engine.check_all()
        assert health["healthy"] is False
        assert health["guards"]["cascade_breaker"]["open_count"] >= 1

    def test_check_all_unhealthy_when_deadlock(self, engine: AutomationSafeguardEngine):
        engine.deadlock_detector.acquire("T1", "res_X")
        engine.deadlock_detector.acquire("T2", "res_Y")
        engine.deadlock_detector.acquire("T1", "res_Y")
        engine.deadlock_detector.acquire("T2", "res_X")
        health = engine.check_all()
        assert health["healthy"] is False

    def test_check_all_unhealthy_when_oscillating(self, engine: AutomationSafeguardEngine):
        for i in range(30):
            engine.oscillation.record(100.0 if i % 2 == 0 else -100.0)
        health = engine.check_all()
        assert health["healthy"] is False

    def test_get_status_fields(self, engine: AutomationSafeguardEngine):
        status = engine.get_status()
        assert status["module"] == "automation_safeguard_engine"
        assert "version" in status
        assert "uptime_sec" in status
        assert "event_storm_blocked" in status
        assert "cascade_open" in status
        assert "idempotency_blocked" in status
        assert "loop_guard_trips" in status
        assert "deadlock_count" in status
        assert "accumulation_alerts" in status
        assert "oscillation_trips" in status

    def test_module_singleton_returns_same_instance(self):
        e1 = get_engine()
        e2 = get_engine()
        assert e1 is e2

    def test_module_get_status_returns_dict(self):
        status = get_status()
        assert isinstance(status, dict)
        assert status["module"] == "automation_safeguard_engine"

    def test_loop_guard_trips_reflected_in_status(self, engine: AutomationSafeguardEngine):
        try:
            with engine.loop_guard("trip_me", max_iterations=2):
                for _ in range(5):
                    engine.loop_guard("trip_me").tick()
        except RunawayLoopError:
            pass
        status = engine.get_status()
        assert status["loop_guard_trips"] >= 1

    def test_event_storm_blocked_reflected_in_status(self, engine: AutomationSafeguardEngine):
        for _ in range(500):
            engine.event_storm.allow("flood_event")
        status = engine.get_status()
        assert status["event_storm_blocked"] > 0

    def test_idempotency_blocked_reflected_in_status(self, engine: AutomationSafeguardEngine):
        p = {"action": "send_invoice", "invoice_id": "INV-001"}
        engine.idempotency.is_new(p)
        engine.idempotency.is_new(p)  # blocked
        status = engine.get_status()
        assert status["idempotency_blocked"] >= 1


# ===========================================================================
# Thread Safety
# ===========================================================================

class TestThreadSafety:
    """SAFE-200 — All guards must be safe under concurrent access."""

    def test_runaway_guard_concurrent_tick(self):
        """Multiple threads ticking on the same guard must not corrupt state."""
        guard = RunawayLoopGuard("concurrent", max_iterations=10_000, max_seconds=10.0)
        guard.start()
        errors: List[Exception] = []

        def tick_many():
            try:
                for _ in range(50):
                    guard.tick()
            except RunawayLoopError:
                pass  # Expected — not an error
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=tick_many) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)
        assert errors == []

    def test_event_storm_concurrent_allow(self):
        sup = EventStormSuppressor("concurrent", max_per_window=100, window_sec=1.0,
                                   debounce_sec=0.0)
        errors: List[Exception] = []

        def fire_events():
            try:
                for i in range(20):
                    sup.allow(f"key_{i}")
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=fire_events) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)
        assert errors == []

    def test_idempotency_guard_concurrent(self):
        guard = IdempotencyGuard("concurrent", ttl_sec=60.0)
        payloads = [{"id": i} for i in range(50)]
        first_allowed: List[bool] = []
        lock = threading.Lock()
        errors: List[Exception] = []

        def check_payload(p):
            try:
                result = guard.is_new(p)
                with lock:
                    first_allowed.append(result)
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=check_payload, args=(p,)) for p in payloads]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)
        assert errors == []
        # Each unique payload must have been allowed exactly once across all threads
        allowed_count = sum(1 for r in first_allowed if r)
        assert allowed_count == 50

    def test_cascade_breaker_concurrent_failures(self):
        cb = CascadeBreaker("concurrent", trip_ratio=0.6, window_sec=60.0)
        cb.register("svc")
        errors: List[Exception] = []

        def record_failures():
            try:
                for _ in range(5):
                    cb.record_failure("svc")
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=record_failures) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)
        assert errors == []

    def test_engine_check_all_concurrent(self, engine: AutomationSafeguardEngine):
        errors: List[Exception] = []

        def run_check():
            try:
                engine.check_all()
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=run_check) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)
        assert errors == []


# ===========================================================================
# Automation-Type Scenario Tests
# ===========================================================================

class TestAutomationTypeScenarios:
    """End-to-end scenarios across real automation types."""

    def test_proposal_regeneration_loop_is_stopped(self, engine: AutomationSafeguardEngine):
        """Simulates a self-improvement engine regenerating proposals endlessly."""
        guard = engine.loop_guard("proposal_gen", max_iterations=50)
        with pytest.raises(RunawayLoopError):
            with guard:
                while True:
                    guard.tick()  # Will trip at 50

    def test_email_webhook_storm_is_suppressed(self, engine: AutomationSafeguardEngine):
        """Simulates 1000 emails/min flooding the webhook endpoint."""
        allowed = sum(1 for _ in range(1000) if engine.event_storm.allow("email_webhook"))
        assert allowed <= engine.event_storm.max_per_window

    def test_market_data_feed_oscillation_caught(self, engine: AutomationSafeguardEngine):
        """Simulates a market data PID control loop oscillating around target price."""
        price_series = [100.0, 115.0, 85.0, 112.0, 88.0, 108.0, 91.0, 105.0,
                        94.0, 103.0, 97.0, 102.0, 98.0, 101.0, 99.0, 100.5]
        for p in price_series:
            engine.oscillation.record(p)
        assert engine.oscillation.is_oscillating() is True

    def test_api_cascade_failure_contained(self, engine: AutomationSafeguardEngine):
        """Simulates billing service outage cascading to stripe (its consumer)."""
        engine.cascade_breaker.register("billing_service")
        engine.cascade_breaker.register("stripe_api", depends_on=["billing_service"])
        for _ in range(8):
            engine.cascade_breaker.record_failure("billing_service")
        assert engine.cascade_breaker.is_open("billing_service") is True
        assert engine.cascade_breaker.is_open("stripe_api") is True

    def test_webhook_deduplication_prevents_double_charge(self, engine: AutomationSafeguardEngine):
        """Simulates duplicate Stripe webhook (delivery retry) — must not double-charge."""
        webhook = {
            "type": "payment_intent.succeeded",
            "id": "pi_3NqX123",
            "amount": 4999,
        }
        first = engine.idempotency.is_new(webhook)
        duplicate = engine.idempotency.is_new(webhook)  # Stripe retry
        assert first is True
        assert duplicate is False  # Prevented double charge

    def test_audit_log_accumulation_detected(self, engine: AutomationSafeguardEngine):
        """Simulates audit log growing without bound."""
        audit_log: List[Dict[str, Any]] = []
        engine.accumulation_watcher.register("audit_log", lambda: len(audit_log), max_size=100)
        for _ in range(200):
            audit_log.append({"event": "tick"})
        alerts = engine.accumulation_watcher.check()
        assert any("audit_log" in a for a in alerts)

    def test_multi_bot_deadlock_resolved_by_emergency_release(
        self, engine: AutomationSafeguardEngine
    ):
        """Simulates two bots deadlocking on shared resources."""
        det = engine.deadlock_detector
        det.acquire("trading_bot", "market_data_feed")
        det.acquire("compliance_bot", "audit_queue")
        det.acquire("trading_bot", "audit_queue")   # trading waits
        det.acquire("compliance_bot", "market_data_feed")  # compliance waits → deadlock
        assert det.has_deadlock() is True
        released = det.emergency_release_all()
        assert released >= 2
        assert det.has_deadlock() is False

    def test_self_improvement_loop_bounded(self, engine: AutomationSafeguardEngine):
        """SelfImprovementEngine pattern: runs 100 cycle, never exceeds max."""
        guard = engine.loop_guard("self_improvement_cycle", max_iterations=100)
        with guard:
            for _ in range(100):
                guard.tick()
        # Completed 100 exactly — should NOT have raised
        assert guard.get_status()["iteration_count"] == 100

    def test_chaos_experiment_not_double_triggered(self, engine: AutomationSafeguardEngine):
        """ChaosResilienceLoop pattern: same experiment must not fire twice."""
        experiment = {
            "hypothesis": "confidence_engine_recovers_from_memory_pressure",
            "target": "confidence_engine",
            "run_id": "exp_abc123",
        }
        assert engine.idempotency.is_new(experiment) is True
        # Retry (e.g., orchestrator requeues the job)
        assert engine.idempotency.is_new(experiment) is False

    def test_3d_printer_temperature_pid_oscillation(self, engine: AutomationSafeguardEngine):
        """3D printer hotend PID: runaway oscillation in temperature control."""
        detector = FeedbackOscillationDetector("hotend_pid", window=15, max_sign_changes=5)
        # Typical runaway oscillation pattern: target=200°C
        temps = [215, 183, 212, 186, 208, 191, 205, 194, 202, 197, 201, 198, 200.5, 199.7, 200.1]
        for t in temps:
            detector.record(float(t))
        assert detector.is_oscillating() is True

    def test_recipe_engine_event_deduplication(self, engine: AutomationSafeguardEngine):
        """RecipeEngine: same status_change event must not fire actions twice."""
        event = {"type": "status_change", "item_id": "task_456", "to_value": "done"}
        assert engine.idempotency.is_new(event) is True
        assert engine.idempotency.is_new(event) is False  # same event, blocked

    def test_bot_proposal_loop_with_event_storm_guard(
        self, engine: AutomationSafeguardEngine
    ):
        """Combined scenario: loop guard + event storm working together."""
        guard = engine.loop_guard("proposal_loop", max_iterations=200)
        accepted = 0
        suppressed = 0

        with guard:
            for i in range(200):
                guard.tick()
                if engine.event_storm.allow(f"proposal_{i % 10}"):
                    accepted += 1
                else:
                    suppressed += 1

        assert accepted > 0
        assert accepted <= engine.event_storm.max_per_window
        assert accepted + suppressed == 200


# ===========================================================================
# Command Registry Integration
# ===========================================================================

class TestCommandRegistryIntegration:
    """Safeguard commands must be registered in the Murphy command registry."""

    def test_safeguard_commands_in_registry(self):
        from src.murphy_terminal.command_registry import build_registry, CommandCategory
        registry = build_registry()

        # All 3 commands must be present
        cmd_status = registry.get_by_module("automation_safeguard_engine")
        assert cmd_status is not None
        assert cmd_status.slash_command == "/safeguard status"

        cmd_check = registry.get_by_module("automation_safeguard_check")
        assert cmd_check is not None
        assert cmd_check.slash_command == "/safeguard check"

        cmd_reset = registry.get_by_module("automation_safeguard_reset")
        assert cmd_reset is not None
        assert cmd_reset.slash_command == "/safeguard reset"

    def test_safeguard_commands_in_automation_category(self):
        from src.murphy_terminal.command_registry import build_registry, CommandCategory
        registry = build_registry()
        automation_cmds = {c.slash_command for c in registry.get_by_category(CommandCategory.AUTOMATION)}
        assert "/safeguard status" in automation_cmds
        assert "/safeguard check" in automation_cmds
        assert "/safeguard reset" in automation_cmds

    def test_safeguard_commands_discoverable_by_keyword(self):
        from src.murphy_terminal.command_registry import build_registry
        registry = build_registry()
        suggestions = registry.suggest("safeguard")
        assert any("safeguard" in s for s in suggestions)
