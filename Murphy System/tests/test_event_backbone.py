"""
Tests for the Murphy System Event Backbone.
"""

import json
import os
import sys
import tempfile
import threading
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from event_backbone import Event, EventBackbone, EventType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _Recorder:
    """Collects events delivered to a handler."""

    def __init__(self):
        self.events: list = []

    def __call__(self, event: Event) -> None:
        self.events.append(event)


class _FailNTimes:
    """Handler that raises for the first *n* invocations, then succeeds."""

    def __init__(self, n: int):
        self.remaining = n
        self.events: list = []

    def __call__(self, event: Event) -> None:
        if self.remaining > 0:
            self.remaining -= 1
            raise RuntimeError("transient failure")
        self.events.append(event)


class _AlwaysFail:
    """Handler that always raises."""

    def __init__(self):
        self.call_count = 0

    def __call__(self, event: Event) -> None:
        self.call_count += 1
        raise RuntimeError("permanent failure")


# ---------------------------------------------------------------------------
# Publish & Subscribe
# ---------------------------------------------------------------------------

class TestPublishSubscribe:
    def test_basic_publish_returns_event_id(self):
        bb = EventBackbone()
        eid = bb.publish(EventType.TASK_SUBMITTED, {"task": "hello"})
        assert isinstance(eid, str) and len(eid) > 0

    def test_subscribe_and_process(self):
        bb = EventBackbone()
        recorder = _Recorder()
        bb.subscribe(EventType.TASK_SUBMITTED, recorder)
        bb.publish(EventType.TASK_SUBMITTED, {"v": 1})
        count = bb.process_pending()
        assert count == 1
        assert len(recorder.events) == 1
        assert recorder.events[0].payload == {"v": 1}

    def test_multiple_subscribers(self):
        bb = EventBackbone()
        r1, r2 = _Recorder(), _Recorder()
        bb.subscribe(EventType.TASK_COMPLETED, r1)
        bb.subscribe(EventType.TASK_COMPLETED, r2)
        bb.publish(EventType.TASK_COMPLETED, {"done": True})
        bb.process_pending()
        assert len(r1.events) == 1
        assert len(r2.events) == 1

    def test_unsubscribe(self):
        bb = EventBackbone()
        recorder = _Recorder()
        sub_id = bb.subscribe(EventType.AUDIT_LOGGED, recorder)
        bb.unsubscribe(sub_id)
        bb.publish(EventType.AUDIT_LOGGED, {})
        bb.process_pending()
        assert len(recorder.events) == 0

    def test_publish_with_session_and_source(self):
        bb = EventBackbone()
        recorder = _Recorder()
        bb.subscribe(EventType.SWARM_SPAWNED, recorder)
        bb.publish(
            EventType.SWARM_SPAWNED,
            {"agents": 3},
            session_id="sess-1",
            source="orchestrator",
        )
        bb.process_pending()
        evt = recorder.events[0]
        assert evt.session_id == "sess-1"
        assert evt.source == "orchestrator"


# ---------------------------------------------------------------------------
# Event processing
# ---------------------------------------------------------------------------

class TestEventProcessing:
    def test_process_pending_returns_zero_when_empty(self):
        bb = EventBackbone()
        assert bb.process_pending() == 0

    def test_events_without_subscribers_still_processed(self):
        bb = EventBackbone()
        bb.publish(EventType.SYSTEM_HEALTH, {"cpu": 42})
        count = bb.process_pending()
        assert count == 1

    def test_multiple_events_processed_in_order(self):
        bb = EventBackbone()
        recorder = _Recorder()
        bb.subscribe(EventType.TASK_SUBMITTED, recorder)
        for i in range(5):
            bb.publish(EventType.TASK_SUBMITTED, {"seq": i})
        bb.process_pending()
        seqs = [e.payload["seq"] for e in recorder.events]
        assert seqs == [0, 1, 2, 3, 4]


# ---------------------------------------------------------------------------
# Retry logic
# ---------------------------------------------------------------------------

class TestRetryLogic:
    def test_transient_failure_retried(self):
        bb = EventBackbone()
        handler = _FailNTimes(2)
        bb.subscribe(EventType.GATE_EVALUATED, handler)
        bb.publish(EventType.GATE_EVALUATED, {"gate": "quality"})

        # First attempt — fails (retry_count becomes 1)
        bb.process_pending()
        assert len(handler.events) == 0

        # Second attempt — fails again (retry_count becomes 2)
        bb.process_pending()
        assert len(handler.events) == 0

        # Third attempt — succeeds
        bb.process_pending()
        assert len(handler.events) == 1

    def test_exhausted_retries_go_to_dlq(self):
        bb = EventBackbone()
        handler = _AlwaysFail()
        bb.subscribe(EventType.DELIVERY_REQUESTED, handler)
        bb.publish(EventType.DELIVERY_REQUESTED, {"target": "email"})

        # max_retries defaults to 3: initial + 3 retries = 4 process calls
        for _ in range(4):
            bb.process_pending()

        dlq = bb.get_dead_letter_queue()
        assert len(dlq) == 1
        assert dlq[0].event_type == EventType.DELIVERY_REQUESTED


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------

class TestIdempotency:
    def test_duplicate_event_rejected(self):
        bb = EventBackbone()
        recorder = _Recorder()
        bb.subscribe(EventType.AUDIT_LOGGED, recorder)

        event = Event(
            event_id="dup-001",
            event_type=EventType.AUDIT_LOGGED,
            payload={"msg": "first"},
            timestamp="2025-01-01T00:00:00+00:00",
        )
        assert bb.publish_event(event) is True
        assert bb.publish_event(event) is False  # duplicate

        bb.process_pending()
        assert len(recorder.events) == 1

    def test_different_ids_both_accepted(self):
        bb = EventBackbone()
        recorder = _Recorder()
        bb.subscribe(EventType.AUDIT_LOGGED, recorder)

        for i in range(3):
            e = Event(
                event_id=f"unique-{i}",
                event_type=EventType.AUDIT_LOGGED,
                payload={"i": i},
                timestamp="2025-01-01T00:00:00+00:00",
            )
            assert bb.publish_event(e) is True

        bb.process_pending()
        assert len(recorder.events) == 3


# ---------------------------------------------------------------------------
# Dead letter queue
# ---------------------------------------------------------------------------

class TestDeadLetterQueue:
    def test_dlq_empty_initially(self):
        bb = EventBackbone()
        assert bb.get_dead_letter_queue() == []

    def test_dlq_contains_failed_event(self):
        bb = EventBackbone()
        bb.subscribe(EventType.TASK_FAILED, _AlwaysFail())
        bb.publish(EventType.TASK_FAILED, {"reason": "timeout"})
        for _ in range(4):
            bb.process_pending()
        dlq = bb.get_dead_letter_queue()
        assert len(dlq) == 1
        assert dlq[0].payload == {"reason": "timeout"}

    def test_dlq_does_not_grow_from_successful_events(self):
        bb = EventBackbone()
        bb.subscribe(EventType.TASK_COMPLETED, _Recorder())
        for _ in range(10):
            bb.publish(EventType.TASK_COMPLETED, {})
        bb.process_pending()
        assert len(bb.get_dead_letter_queue()) == 0


# ---------------------------------------------------------------------------
# Circuit breaker
# ---------------------------------------------------------------------------

class TestCircuitBreaker:
    def test_breaker_opens_after_threshold(self):
        bb = EventBackbone(circuit_breaker_threshold=3, circuit_breaker_timeout=300)
        fail = _AlwaysFail()
        bb.subscribe(EventType.LEARNING_FEEDBACK, fail)

        # Publish and exhaust retries for enough events to trip breaker
        for _ in range(3):
            bb.publish(EventType.LEARNING_FEEDBACK, {"x": 1})
            for _ in range(4):
                bb.process_pending()

        status = bb.get_status()
        # At least one circuit breaker should be open
        open_breakers = [
            v for v in status["circuit_breakers"].values() if v["open"]
        ]
        assert len(open_breakers) > 0

    def test_breaker_blocks_handler(self):
        bb = EventBackbone(circuit_breaker_threshold=2, circuit_breaker_timeout=300)
        fail = _AlwaysFail()
        sub_id = bb.subscribe(EventType.HITL_REQUIRED, fail)

        # Trip the breaker (2 failures needed)
        bb.publish(EventType.HITL_REQUIRED, {})
        for _ in range(4):
            bb.process_pending()

        bb.publish(EventType.HITL_REQUIRED, {})
        for _ in range(4):
            bb.process_pending()

        # Breaker should now be open — new events go to DLQ because handler is skipped
        call_count_before = fail.call_count
        bb.publish(EventType.HITL_REQUIRED, {})
        for _ in range(4):
            bb.process_pending()

        # Handler should NOT have been called again (or at most once for half-open probe)
        assert fail.call_count <= call_count_before + 1


# ---------------------------------------------------------------------------
# Event history
# ---------------------------------------------------------------------------

class TestEventHistory:
    def test_history_records_processed_events(self):
        bb = EventBackbone()
        bb.subscribe(EventType.GATE_EVALUATED, _Recorder())
        bb.publish(EventType.GATE_EVALUATED, {"g": 1})
        bb.process_pending()

        history = bb.get_event_history()
        assert len(history) == 1
        assert history[0]["event_type"] == "gate_evaluated"
        assert history[0]["status"] == "delivered"

    def test_history_filter_by_event_type(self):
        bb = EventBackbone()
        bb.subscribe(EventType.TASK_SUBMITTED, _Recorder())
        bb.subscribe(EventType.TASK_COMPLETED, _Recorder())
        bb.publish(EventType.TASK_SUBMITTED, {})
        bb.publish(EventType.TASK_COMPLETED, {})
        bb.process_pending()

        submitted = bb.get_event_history(event_type=EventType.TASK_SUBMITTED)
        assert len(submitted) == 1

    def test_history_filter_by_session_id(self):
        bb = EventBackbone()
        bb.subscribe(EventType.AUDIT_LOGGED, _Recorder())
        bb.publish(EventType.AUDIT_LOGGED, {}, session_id="s1")
        bb.publish(EventType.AUDIT_LOGGED, {}, session_id="s2")
        bb.process_pending()

        s1 = bb.get_event_history(session_id="s1")
        assert len(s1) == 1

    def test_history_respects_limit(self):
        bb = EventBackbone()
        bb.subscribe(EventType.SYSTEM_HEALTH, _Recorder())
        for _ in range(10):
            bb.publish(EventType.SYSTEM_HEALTH, {})
        bb.process_pending()

        limited = bb.get_event_history(limit=3)
        assert len(limited) == 3


# ---------------------------------------------------------------------------
# Status reporting
# ---------------------------------------------------------------------------

class TestStatus:
    def test_initial_status(self):
        bb = EventBackbone()
        status = bb.get_status()
        assert status["events_published"] == 0
        assert status["events_processed"] == 0
        assert status["events_failed"] == 0
        assert status["dlq_size"] == 0

    def test_status_after_publish_and_process(self):
        bb = EventBackbone()
        bb.subscribe(EventType.TASK_SUBMITTED, _Recorder())
        bb.publish(EventType.TASK_SUBMITTED, {})
        bb.publish(EventType.TASK_SUBMITTED, {})
        bb.process_pending()

        status = bb.get_status()
        assert status["events_published"] == 2
        assert status["events_processed"] == 2

    def test_status_pending_counts(self):
        bb = EventBackbone()
        bb.publish(EventType.TASK_SUBMITTED, {})
        status = bb.get_status()
        assert status["pending_counts"].get("task_submitted") == 1


# ---------------------------------------------------------------------------
# Event ordering
# ---------------------------------------------------------------------------

class TestEventOrdering:
    def test_fifo_ordering_within_type(self):
        bb = EventBackbone()
        recorder = _Recorder()
        bb.subscribe(EventType.TASK_SUBMITTED, recorder)

        for i in range(20):
            bb.publish(EventType.TASK_SUBMITTED, {"order": i})

        bb.process_pending()
        orders = [e.payload["order"] for e in recorder.events]
        assert orders == list(range(20))

    def test_retry_preserves_ordering(self):
        """An event that fails should block later events in the same queue."""
        bb = EventBackbone()
        handler = _FailNTimes(1)  # fail once then succeed
        bb.subscribe(EventType.DELIVERY_REQUESTED, handler)
        bb.publish(EventType.DELIVERY_REQUESTED, {"seq": "A"})
        bb.publish(EventType.DELIVERY_REQUESTED, {"seq": "B"})

        # First process: A fails, B not attempted
        bb.process_pending()
        assert len(handler.events) == 0

        # Second process: A succeeds now, then B succeeds
        bb.process_pending()
        seqs = [e.payload["seq"] for e in handler.events]
        assert seqs == ["A", "B"]


# ---------------------------------------------------------------------------
# Persistence / durability
# ---------------------------------------------------------------------------

class TestPersistence:
    def test_events_survive_restart(self, tmp_path):
        pdir = str(tmp_path / "events")

        # Publish without processing
        bb1 = EventBackbone(persistence_dir=pdir)
        bb1.publish(EventType.TASK_SUBMITTED, {"key": "value"})

        # Simulate restart
        bb2 = EventBackbone(persistence_dir=pdir)
        recorder = _Recorder()
        bb2.subscribe(EventType.TASK_SUBMITTED, recorder)
        bb2.process_pending()

        assert len(recorder.events) == 1
        assert recorder.events[0].payload == {"key": "value"}

    def test_dlq_survives_restart(self, tmp_path):
        pdir = str(tmp_path / "events")

        bb1 = EventBackbone(persistence_dir=pdir)
        bb1.subscribe(EventType.TASK_FAILED, _AlwaysFail())
        bb1.publish(EventType.TASK_FAILED, {"err": "oops"})
        for _ in range(4):
            bb1.process_pending()

        bb2 = EventBackbone(persistence_dir=pdir)
        dlq = bb2.get_dead_letter_queue()
        assert len(dlq) == 1
        assert dlq[0].payload == {"err": "oops"}

    def test_idempotency_survives_restart(self, tmp_path):
        pdir = str(tmp_path / "events")

        bb1 = EventBackbone(persistence_dir=pdir)
        event = Event(
            event_id="persist-dup",
            event_type=EventType.AUDIT_LOGGED,
            payload={},
            timestamp="2025-01-01T00:00:00+00:00",
        )
        assert bb1.publish_event(event) is True

        bb2 = EventBackbone(persistence_dir=pdir)
        assert bb2.publish_event(event) is False


# ---------------------------------------------------------------------------
# Event / EventType serialization
# ---------------------------------------------------------------------------

class TestEventSerialization:
    def test_event_round_trip(self):
        event = Event(
            event_id="rt-1",
            event_type=EventType.GATE_BLOCKED,
            payload={"gate": "safety", "score": 0.2},
            timestamp="2025-06-01T12:00:00+00:00",
            session_id="sess-42",
            source="gate_engine",
            retry_count=1,
            max_retries=5,
        )
        d = event.to_dict()
        restored = Event.from_dict(d)
        assert restored.event_id == event.event_id
        assert restored.event_type == event.event_type
        assert restored.payload == event.payload
        assert restored.session_id == event.session_id
        assert restored.retry_count == 1
        assert restored.max_retries == 5

    def test_all_event_types_serializable(self):
        for et in EventType:
            d = {"event_type": et.value}
            assert EventType(d["event_type"]) == et


# ---------------------------------------------------------------------------
# Background processing loop
# ---------------------------------------------------------------------------

class TestBackgroundLoop:
    def test_start_creates_running_thread(self):
        bb = EventBackbone(loop_interval_ms=50)
        assert not bb.is_running
        bb.start()
        assert bb.is_running
        bb.stop()
        assert not bb.is_running

    def test_start_is_idempotent(self):
        bb = EventBackbone(loop_interval_ms=50)
        bb.start()
        thread_first = bb._bg_thread
        bb.start()  # second start should be a no-op
        assert bb._bg_thread is thread_first
        bb.stop()

    def test_stop_is_safe_before_start(self):
        bb = EventBackbone(loop_interval_ms=50)
        bb.stop()  # should not raise
        assert not bb.is_running

    def test_background_loop_processes_events_automatically(self):
        """Events should be delivered to subscribers without calling process_pending()."""
        bb = EventBackbone(loop_interval_ms=20)
        received = []
        lock = threading.Lock()

        def handler(event):
            with lock:
                received.append(event.payload)

        bb.subscribe(EventType.TASK_SUBMITTED, handler)
        bb.start()
        try:
            bb.publish(EventType.TASK_SUBMITTED, {"auto": True})
            # Give the background loop up to 2 seconds to process
            deadline = time.time() + 2.0
            while time.time() < deadline:
                with lock:
                    if received:
                        break
                time.sleep(0.01)
        finally:
            bb.stop()

        assert len(received) == 1
        assert received[0] == {"auto": True}

    def test_background_loop_processes_multiple_events(self):
        bb = EventBackbone(loop_interval_ms=20)
        received = []
        lock = threading.Lock()

        def handler(event):
            with lock:
                received.append(event.payload["seq"])

        bb.subscribe(EventType.TASK_SUBMITTED, handler)
        bb.start()
        try:
            for i in range(5):
                bb.publish(EventType.TASK_SUBMITTED, {"seq": i})
            deadline = time.time() + 2.0
            while time.time() < deadline:
                with lock:
                    if len(received) >= 5:
                        break
                time.sleep(0.01)
        finally:
            bb.stop()

        assert received == [0, 1, 2, 3, 4]

    def test_status_reports_background_loop_running(self):
        bb = EventBackbone(loop_interval_ms=50)
        assert bb.get_status()["background_loop_running"] is False
        bb.start()
        assert bb.get_status()["background_loop_running"] is True
        bb.stop()
        assert bb.get_status()["background_loop_running"] is False

    def test_status_includes_metrics(self):
        bb = EventBackbone(loop_interval_ms=20)
        bb.subscribe(EventType.SYSTEM_HEALTH, lambda e: None)
        bb.start()
        try:
            bb.publish(EventType.SYSTEM_HEALTH, {"cpu": 5})
            deadline = time.time() + 2.0
            while time.time() < deadline:
                status = bb.get_status()
                if status["events_processed"] >= 1:
                    break
                time.sleep(0.01)
        finally:
            bb.stop()

        status = bb.get_status()
        assert "metrics" in status
        metrics = status["metrics"]
        assert "queue_depth" in metrics
        assert "events_per_second" in metrics
        assert "last_loop_latency_ms" in metrics
        assert "loop_iterations" in metrics
        assert metrics["loop_iterations"] > 0

    def test_loop_interval_from_env_var(self, monkeypatch):
        monkeypatch.setenv("MURPHY_EVENT_LOOP_INTERVAL_MS", "200")
        bb = EventBackbone()
        assert abs(bb.loop_interval_ms - 200.0) < 0.1

    def test_loop_interval_explicit_overrides_env(self, monkeypatch):
        monkeypatch.setenv("MURPHY_EVENT_LOOP_INTERVAL_MS", "999")
        bb = EventBackbone(loop_interval_ms=50)
        assert abs(bb.loop_interval_ms - 50.0) < 0.1


# ---------------------------------------------------------------------------
# Backpressure handling
# ---------------------------------------------------------------------------

class TestBackpressure:
    def test_backpressure_emits_system_health_event(self):
        """When queue depth exceeds threshold, a SYSTEM_HEALTH event is published."""
        bb = EventBackbone(loop_interval_ms=20, backpressure_threshold=2)
        health_events = []
        lock = threading.Lock()

        def health_handler(event):
            with lock:
                health_events.append(event.payload)

        bb.subscribe(EventType.SYSTEM_HEALTH, health_handler)
        # Publish events that exceed the backpressure threshold WITHOUT processing
        # We do this while the loop is stopped so we can stage the condition
        bb.publish(EventType.TASK_SUBMITTED, {"a": 1})
        bb.publish(EventType.TASK_SUBMITTED, {"b": 2})
        bb.publish(EventType.TASK_SUBMITTED, {"c": 3})

        bb.start()
        try:
            deadline = time.time() + 2.0
            while time.time() < deadline:
                with lock:
                    if health_events:
                        break
                time.sleep(0.01)
        finally:
            bb.stop()

        assert len(health_events) >= 1
        bp_events = [e for e in health_events if e.get("type") == "backpressure"]
        assert len(bp_events) >= 1
        assert bp_events[0]["threshold"] == 2
