"""Tests for the Durable Swarm Orchestrator module."""

import threading
from datetime import datetime, timezone

import pytest

import os


from durable_swarm_orchestrator import (
    CircuitBreaker,
    CircuitState,
    DurableSwarmOrchestrator,
    SwarmTaskState,
)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _make_orchestrator(**kwargs):
    defaults = dict(
        total_budget=1000.0,
        max_per_task=100.0,
        max_spawn_depth=5,
        max_retries=3,
        failure_threshold=5,
    )
    defaults.update(kwargs)
    return DurableSwarmOrchestrator(**defaults)


# ------------------------------------------------------------------
# Spawning tasks
# ------------------------------------------------------------------

class TestSpawnTask:
    def test_spawn_success(self):
        orch = _make_orchestrator()
        ok, task_id, key = orch.spawn_task("do stuff", budget=50.0)
        assert ok is True
        assert task_id.startswith("swarm-")
        assert len(key) > 0

    def test_spawn_returns_idempotency_key(self):
        orch = _make_orchestrator()
        ok, _, key = orch.spawn_task("a", budget=10.0, idempotency_key="my-key")
        assert ok is True
        assert key == "my-key"

    def test_spawn_budget_exhaustion(self):
        orch = _make_orchestrator(total_budget=100.0)
        ok1, _, _ = orch.spawn_task("a", budget=80.0)
        assert ok1 is True
        ok2, reason, _ = orch.spawn_task("b", budget=30.0)
        assert ok2 is False
        assert reason == "budget_exhausted"

    def test_spawn_exceeds_per_task_limit(self):
        orch = _make_orchestrator(max_per_task=50.0)
        ok, reason, _ = orch.spawn_task("big", budget=60.0)
        assert ok is False
        assert reason == "exceeds_per_task_limit"

    def test_spawn_depth_limit(self):
        orch = _make_orchestrator(max_spawn_depth=2)
        ok1, id1, _ = orch.spawn_task("root", budget=10.0)
        assert ok1
        ok2, id2, _ = orch.spawn_task("child", budget=10.0, parent_id=id1)
        assert ok2
        ok3, id3, _ = orch.spawn_task("grandchild", budget=10.0, parent_id=id2)
        assert ok3
        ok4, reason, _ = orch.spawn_task("too deep", budget=10.0, parent_id=id3)
        assert ok4 is False
        assert reason == "max_depth_exceeded"

    def test_spawn_parent_not_found(self):
        orch = _make_orchestrator()
        ok, reason, _ = orch.spawn_task("orphan", budget=10.0, parent_id="nonexistent")
        assert ok is False
        assert reason == "parent_not_found"


# ------------------------------------------------------------------
# Completing tasks
# ------------------------------------------------------------------

class TestCompleteTask:
    def test_complete_success(self):
        orch = _make_orchestrator()
        _, tid, _ = orch.spawn_task("work", budget=50.0)
        assert orch.complete_task(tid, {"output": "ok"}, cost=10.0) is True
        task = orch.get_task(tid)
        assert task.state == SwarmTaskState.COMPLETED
        assert task.result == {"output": "ok"}
        assert task.budget_spent == 10.0

    def test_complete_unknown_task(self):
        orch = _make_orchestrator()
        assert orch.complete_task("nope", {}) is False


# ------------------------------------------------------------------
# Failing tasks & retry logic
# ------------------------------------------------------------------

class TestFailTask:
    def test_retry_on_first_failure(self):
        orch = _make_orchestrator(max_retries=3)
        _, tid, _ = orch.spawn_task("work", budget=10.0)
        should_retry, action = orch.fail_task(tid, "oops")
        assert should_retry is True
        assert action == "retry"
        task = orch.get_task(tid)
        assert task.state == SwarmTaskState.RETRYING
        assert task.retries == 1

    def test_rollback_after_max_retries(self):
        orch = _make_orchestrator(max_retries=2)
        _, tid, _ = orch.spawn_task("work", budget=10.0)
        orch.fail_task(tid, "e1")
        orch.fail_task(tid, "e2")
        should_retry, action = orch.fail_task(tid, "e3")
        assert should_retry is False
        assert action == "rollback"
        assert orch.get_task(tid).state == SwarmTaskState.FAILED

    def test_fail_unknown_task(self):
        orch = _make_orchestrator()
        should_retry, action = orch.fail_task("missing", "err")
        assert should_retry is False
        assert action == "rollback"


# ------------------------------------------------------------------
# Circuit breaker
# ------------------------------------------------------------------

class TestCircuitBreaker:
    def test_initial_state_closed(self):
        cb = CircuitBreaker(failure_threshold=3)
        assert cb.state == CircuitState.CLOSED
        assert cb.is_open() is False

    def test_opens_after_threshold(self):
        cb = CircuitBreaker(failure_threshold=3)
        for _ in range(3):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert cb.is_open() is True

    def test_success_resets(self):
        cb = CircuitBreaker(failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        assert cb.state == CircuitState.CLOSED
        assert cb.is_open() is False

    def test_half_open_after_timeout(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.0)
        cb.record_failure()
        cb.record_failure()
        assert cb.is_open() is False  # recovery_timeout=0 → immediate half-open
        assert cb.state == CircuitState.HALF_OPEN

    def test_get_status(self):
        cb = CircuitBreaker(failure_threshold=5, recovery_timeout=30.0)
        status = cb.get_status()
        assert status["state"] == "closed"
        assert status["failure_threshold"] == 5

    def test_spawn_denied_when_circuit_open(self):
        orch = _make_orchestrator(failure_threshold=2, max_retries=0)
        _, t1, _ = orch.spawn_task("a", budget=10.0)
        _, t2, _ = orch.spawn_task("b", budget=10.0)
        orch.fail_task(t1, "e")
        orch.fail_task(t2, "e")
        ok, reason, _ = orch.spawn_task("c", budget=10.0)
        assert ok is False
        assert reason == "circuit_open"


# ------------------------------------------------------------------
# Idempotency
# ------------------------------------------------------------------

class TestIdempotency:
    def test_duplicate_key_blocked(self):
        orch = _make_orchestrator()
        ok1, _, _ = orch.spawn_task("a", budget=10.0, idempotency_key="k1")
        assert ok1 is True
        ok2, reason, _ = orch.spawn_task("b", budget=10.0, idempotency_key="k1")
        assert ok2 is False
        assert reason == "duplicate_idempotency_key"

    def test_reuse_key_after_cancel(self):
        orch = _make_orchestrator()
        ok1, tid1, _ = orch.spawn_task("a", budget=10.0, idempotency_key="k2")
        assert ok1
        orch.cancel_task(tid1)
        ok2, tid2, _ = orch.spawn_task("a-retry", budget=10.0, idempotency_key="k2")
        assert ok2 is True
        assert tid2 != tid1

    def test_reuse_key_after_fail(self):
        orch = _make_orchestrator(max_retries=0)
        ok1, tid1, _ = orch.spawn_task("a", budget=10.0, idempotency_key="k3")
        orch.fail_task(tid1, "err")
        ok2, tid2, _ = orch.spawn_task("a-v2", budget=10.0, idempotency_key="k3")
        assert ok2 is True


# ------------------------------------------------------------------
# Rollback & cancellation
# ------------------------------------------------------------------

class TestRollbackAndCancel:
    def test_rollback_releases_budget(self):
        orch = _make_orchestrator(total_budget=100.0)
        _, tid, _ = orch.spawn_task("x", budget=60.0)
        assert orch.get_budget_status()["allocated"] == 60.0
        orch.rollback_task(tid)
        assert orch.get_budget_status()["allocated"] == 0.0
        assert orch.get_task(tid).state == SwarmTaskState.ROLLED_BACK

    def test_cancel_releases_budget(self):
        orch = _make_orchestrator(total_budget=100.0)
        _, tid, _ = orch.spawn_task("x", budget=40.0)
        orch.cancel_task(tid)
        assert orch.get_budget_status()["allocated"] == 0.0
        assert orch.get_task(tid).state == SwarmTaskState.CANCELLED

    def test_rollback_unknown(self):
        orch = _make_orchestrator()
        assert orch.rollback_task("nope") is False

    def test_cancel_unknown(self):
        orch = _make_orchestrator()
        assert orch.cancel_task("nope") is False


# ------------------------------------------------------------------
# Budget tracking accuracy
# ------------------------------------------------------------------

class TestBudgetTracking:
    def test_budget_after_spawn_and_complete(self):
        orch = _make_orchestrator(total_budget=200.0)
        _, tid, _ = orch.spawn_task("work", budget=80.0)
        status = orch.get_budget_status()
        assert status["allocated"] == 80.0
        assert status["remaining"] == 120.0
        orch.complete_task(tid, {"done": True}, cost=30.0)
        status = orch.get_budget_status()
        assert status["spent"] == 30.0

    def test_multiple_tasks_budget(self):
        orch = _make_orchestrator(total_budget=100.0)
        orch.spawn_task("a", budget=30.0)
        orch.spawn_task("b", budget=25.0)
        orch.spawn_task("c", budget=20.0)
        status = orch.get_budget_status()
        assert status["allocated"] == 75.0
        assert status["remaining"] == 25.0


# ------------------------------------------------------------------
# Anti-recursion (max depth)
# ------------------------------------------------------------------

class TestAntiRecursion:
    def test_chain_up_to_max_depth(self):
        orch = _make_orchestrator(max_spawn_depth=3, total_budget=10000.0)
        _, parent_id, _ = orch.spawn_task("d0", budget=10.0)
        for d in range(1, 4):  # depths 1,2,3 should succeed
            ok, parent_id, _ = orch.spawn_task(f"d{d}", budget=10.0, parent_id=parent_id)
            assert ok is True, f"depth {d} should succeed"
        ok, reason, _ = orch.spawn_task("d4", budget=10.0, parent_id=parent_id)
        assert ok is False
        assert reason == "max_depth_exceeded"


# ------------------------------------------------------------------
# Status reporting
# ------------------------------------------------------------------

class TestStatusReporting:
    def test_get_status(self):
        orch = _make_orchestrator()
        orch.spawn_task("a", budget=10.0)
        orch.spawn_task("b", budget=20.0)
        status = orch.get_status()
        assert status["total_tasks"] == 2
        assert "budget" in status
        assert "circuit_breaker" in status

    def test_list_tasks_filter(self):
        orch = _make_orchestrator()
        _, tid, _ = orch.spawn_task("x", budget=10.0)
        orch.complete_task(tid, {"ok": True})
        orch.spawn_task("y", budget=10.0)
        assert len(orch.list_tasks(SwarmTaskState.COMPLETED)) == 1
        assert len(orch.list_tasks(SwarmTaskState.PENDING)) == 1
        assert len(orch.list_tasks()) == 2

    def test_get_task(self):
        orch = _make_orchestrator()
        _, tid, _ = orch.spawn_task("hi", budget=5.0)
        task = orch.get_task(tid)
        assert task is not None
        assert task.description == "hi"
        assert orch.get_task("nonexistent") is None


# ------------------------------------------------------------------
# Thread safety
# ------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_spawns(self):
        orch = _make_orchestrator(total_budget=100_000.0)
        results = []
        barrier = threading.Barrier(20)

        def _spawn(i):
            barrier.wait()
            ok, tid_or_reason, _ = orch.spawn_task(f"task-{i}", budget=1.0)
            results.append((ok, tid_or_reason))

        threads = [threading.Thread(target=_spawn, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        successes = [r for r in results if r[0]]
        assert len(successes) == 20
        assert orch.get_budget_status()["allocated"] == 20.0

    def test_concurrent_fail_and_complete(self):
        orch = _make_orchestrator(total_budget=10_000.0, failure_threshold=100)
        tids = []
        for i in range(10):
            _, tid, _ = orch.spawn_task(f"t{i}", budget=10.0)
            tids.append(tid)

        barrier = threading.Barrier(10)

        def _op(idx):
            barrier.wait()
            if idx % 2 == 0:
                orch.complete_task(tids[idx], {"i": idx}, cost=1.0)
            else:
                orch.fail_task(tids[idx], "err")

        threads = [threading.Thread(target=_op, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        completed = orch.list_tasks(SwarmTaskState.COMPLETED)
        assert len(completed) == 5
