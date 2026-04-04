# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Test Suite: Real-time WebSocket Event Streaming Server — WES-001

Comprehensive tests for the websocket_event_server module:
  - Data model serialisation (EventPayload, EventFilter, Subscriber)
  - EventChannel history (bounded deque, thread-safe access)
  - ConnectionManager (add, remove, expire, heartbeat)
  - EventBus pub/sub (publish, poll, subscribe, channel history)
  - Flask API endpoints (subscribe, publish, poll, SSE, stats)
  - Thread safety under concurrent publish/subscribe
  - Wingman pair validation gate
  - Causality Sandbox gating simulation
  - User-agent operation testing (non-technical user workflows)

Tests use the storyline-actuals record() pattern for cause/effect/lesson tracking.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import datetime
import json
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List

import pytest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SRC_DIR))

from websocket_event_server import (
    ChannelName,
    ConnectionManager,
    EventBus,
    EventChannel,
    EventFilter,
    EventPayload,
    EventSeverity,
    Subscriber,
    SubscriberState,
    create_event_streaming_api,
)


# ---------------------------------------------------------------------------
# Record infrastructure (storyline-actuals pattern)
# ---------------------------------------------------------------------------

@dataclass
class WESRecord:
    """One WES check record."""
    check_id: str
    description: str
    expected: Any
    actual: Any
    passed: bool
    cause: str = ""
    effect: str = ""
    lesson: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.now(
            datetime.timezone.utc
        ).isoformat()
    )


_records: List[WESRecord] = []


def record(
    check_id: str,
    description: str,
    expected: Any,
    actual: Any,
    cause: str = "",
    effect: str = "",
    lesson: str = "",
) -> bool:
    """Record a check and return whether expected == actual."""
    passed = expected == actual
    _records.append(WESRecord(
        check_id=check_id,
        description=description,
        expected=expected,
        actual=actual,
        passed=passed,
        cause=cause,
        effect=effect,
        lesson=lesson,
    ))
    return passed


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def bus() -> EventBus:
    """Return a fresh EventBus."""
    return EventBus()


@pytest.fixture()
def subscriber(bus: EventBus) -> Subscriber:
    """Return a subscriber registered on the bus."""
    return bus.subscribe("test-dashboard")


@pytest.fixture()
def sample_event() -> EventPayload:
    """Return a sample EventPayload."""
    return EventPayload(
        event_id="evt-001",
        channel="system",
        event_type="status_change",
        data={"module": "llm", "status": "healthy"},
        severity=EventSeverity.INFO.value,
    )


@pytest.fixture()
def flask_client():
    """Return a Flask test client with the event streaming API."""
    from flask import Flask
    app = Flask(__name__)
    api, bus = create_event_streaming_api()
    app.register_blueprint(api)
    app.config["TESTING"] = True
    client = app.test_client()
    client._bus = bus  # expose for test assertions
    return client


# ============================================================================
# DATA MODEL TESTS
# ============================================================================

class TestDataModels:
    """WES-010: Event data model serialisation."""

    def test_event_payload_to_dict(self, sample_event: EventPayload):
        """WES-010: EventPayload serialises to dict."""
        d = sample_event.to_dict()
        assert record(
            "WES-010", "EventPayload.to_dict() has all keys",
            True,
            all(k in d for k in [
                "event_id", "channel", "event_type",
                "data", "severity", "source", "timestamp",
            ]),
            cause="Serialise an event payload",
            effect="All required keys are present",
            lesson="Events must be fully serialisable for wire transport",
        )

    def test_event_payload_to_json(self, sample_event: EventPayload):
        """WES-011: EventPayload serialises to valid JSON."""
        j = sample_event.to_json()
        parsed = json.loads(j)
        assert record(
            "WES-011", "EventPayload.to_json() round-trips",
            "evt-001", parsed["event_id"],
            cause="JSON serialise then parse",
            effect="event_id survives round-trip",
            lesson="JSON transport must be lossless",
        )

    def test_subscriber_to_dict(self):
        """WES-012: Subscriber metadata serialises correctly."""
        sub = Subscriber(
            subscriber_id="sub-001", name="dash-1",
        )
        d = sub.to_dict()
        assert record(
            "WES-012", "Subscriber.to_dict() has subscriber_id",
            "sub-001", d["subscriber_id"],
            cause="Serialise subscriber",
            effect="subscriber_id preserved",
            lesson="Dashboard clients need stable IDs",
        )


# ============================================================================
# EVENT FILTER TESTS
# ============================================================================

class TestEventFilter:
    """WES-020: Filter matching logic."""

    def test_empty_filter_matches_all(self, sample_event: EventPayload):
        """WES-020: An empty filter accepts every event."""
        ef = EventFilter()
        assert record(
            "WES-020", "Empty filter matches all events",
            True, ef.matches(sample_event),
            cause="No criteria set",
            effect="Event passes through",
            lesson="Default filter is permissive for onboarding ease",
        )

    def test_channel_filter(self, sample_event: EventPayload):
        """WES-021: Channel filter rejects non-matching channels."""
        ef = EventFilter(channels=["security"])
        assert record(
            "WES-021", "Channel filter rejects system event",
            False, ef.matches(sample_event),
            cause="Filter requires 'security', event is 'system'",
            effect="Event is rejected",
            lesson="Channel isolation prevents dashboard noise",
        )

    def test_event_type_filter(self, sample_event: EventPayload):
        """WES-022: Event type filter selects matching types."""
        ef = EventFilter(event_types=["status_change"])
        assert record(
            "WES-022", "Event type filter accepts matching event",
            True, ef.matches(sample_event),
            cause="Filter matches event_type='status_change'",
            effect="Event accepted",
            lesson="Type filters let users focus on relevant events",
        )

    def test_severity_filter(self):
        """WES-023: Severity filter rejects low-severity events."""
        ef = EventFilter(min_severity="warning")
        low_event = EventPayload(
            "e1", "system", "heartbeat", {},
            severity=EventSeverity.DEBUG.value,
        )
        high_event = EventPayload(
            "e2", "system", "alert", {},
            severity=EventSeverity.ERROR.value,
        )
        assert record(
            "WES-023a", "Debug event rejected by warning filter",
            False, ef.matches(low_event),
            cause="Debug < warning",
            effect="Low-severity event filtered out",
            lesson="Non-technical users should not see debug noise",
        )
        assert record(
            "WES-023b", "Error event accepted by warning filter",
            True, ef.matches(high_event),
            cause="Error >= warning",
            effect="High-severity event passes through",
            lesson="Important alerts always reach the dashboard",
        )


# ============================================================================
# EVENT CHANNEL TESTS
# ============================================================================

class TestEventChannel:
    """WES-030: Channel history management."""

    def test_channel_append_and_recent(self):
        """WES-030: Events are stored and retrievable."""
        ch = EventChannel("test", max_history=5)
        for i in range(3):
            ch.append(EventPayload(f"e{i}", "test", "ping", {}))
        recent = ch.recent(10)
        assert record(
            "WES-030", "Channel stores and returns events",
            3, len(recent),
            cause="Three events appended",
            effect="Three events returned by recent()",
            lesson="Channel history is the replay buffer for late joiners",
        )

    def test_channel_bounded_history(self):
        """WES-031: History is bounded by max_history."""
        ch = EventChannel("test", max_history=3)
        for i in range(10):
            ch.append(EventPayload(f"e{i}", "test", "ping", {}))
        assert record(
            "WES-031", "History bounded at max_history=3",
            3, ch.size(),
            cause="10 events pushed into a channel with max_history=3",
            effect="Only last 3 are retained",
            lesson="Memory is bounded to prevent unbounded growth",
        )


# ============================================================================
# CONNECTION MANAGER TESTS
# ============================================================================

class TestConnectionManager:
    """WES-040: Subscriber lifecycle management."""

    def test_add_and_list(self):
        """WES-040: Add a subscriber and list it."""
        cm = ConnectionManager()
        sub = Subscriber("s1", "dashboard-a")
        cm.add(sub)
        assert record(
            "WES-040", "Subscriber is listed after add",
            1, len(cm.list_all()),
            cause="One subscriber added",
            effect="list_all returns 1",
            lesson="Connection tracking is essential for broadcast",
        )

    def test_remove(self):
        """WES-041: Remove a subscriber."""
        cm = ConnectionManager()
        sub = Subscriber("s1", "dashboard-a")
        cm.add(sub)
        removed = cm.remove("s1")
        assert record(
            "WES-041", "Subscriber is removed",
            True, removed,
            cause="Remove existing subscriber",
            effect="Returns True",
            lesson="Clean disconnects free resources",
        )

    def test_expire_stale(self):
        """WES-042: Stale subscribers are marked disconnected."""
        cm = ConnectionManager(heartbeat_ttl_seconds=0.01)
        sub = Subscriber("s1", "dashboard-a")
        sub.last_heartbeat = "2020-01-01T00:00:00+00:00"
        cm.add(sub)
        expired = cm.expire_stale()
        assert record(
            "WES-042", "Stale subscriber expires",
            True, "s1" in expired,
            cause="Heartbeat is ancient",
            effect="Subscriber marked disconnected",
            lesson="Auto-expire prevents ghost subscribers",
        )


# ============================================================================
# EVENT BUS PUB/SUB TESTS
# ============================================================================

class TestEventBus:
    """WES-050: Central event hub."""

    def test_publish_delivers_to_matching_subscriber(
        self, bus: EventBus, subscriber: Subscriber, sample_event: EventPayload,
    ):
        """WES-050: Publish reaches matching subscriber."""
        delivered = bus.publish(sample_event)
        assert record(
            "WES-050", "Event delivered to 1 subscriber",
            1, delivered,
            cause="One subscriber with no filter, one event published",
            effect="Delivered to 1",
            lesson="Default subscription receives everything",
        )

    def test_poll_returns_events(
        self, bus: EventBus, subscriber: Subscriber, sample_event: EventPayload,
    ):
        """WES-051: Poll drains the subscriber queue."""
        bus.publish(sample_event)
        events = bus.poll(subscriber.subscriber_id)
        assert record(
            "WES-051", "Poll returns published event",
            1, len(events),
            cause="One event published, then polled",
            effect="One event returned",
            lesson="Polling is the simplest consumption model",
        )

    def test_poll_empty_on_no_events(self, bus: EventBus, subscriber: Subscriber):
        """WES-052: Poll returns empty when no events pending."""
        events = bus.poll(subscriber.subscriber_id)
        assert record(
            "WES-052", "Poll with no events returns empty list",
            0, len(events),
            cause="No events published",
            effect="Empty list",
            lesson="Non-blocking poll returns immediately",
        )

    def test_channel_history(self, bus: EventBus, sample_event: EventPayload):
        """WES-053: Channel history records published events."""
        bus.publish(sample_event)
        history = bus.channel_history("system")
        assert record(
            "WES-053", "Channel history has 1 event",
            1, len(history),
            cause="One event published to system channel",
            effect="Channel history contains it",
            lesson="Late-joining dashboards can catch up via history",
        )

    def test_stats(self, bus: EventBus, sample_event: EventPayload):
        """WES-054: Stats reflect published count."""
        bus.publish(sample_event)
        s = bus.stats()
        assert record(
            "WES-054", "Stats show 1 total_published",
            1, s["total_published"],
            cause="One event published",
            effect="Stats counter incremented",
            lesson="Operators need visibility into bus throughput",
        )

    def test_filtered_subscriber_ignores_mismatch(self, bus: EventBus):
        """WES-055: Filtered subscriber ignores non-matching events."""
        sub = bus.subscribe("security-dash", EventFilter(channels=["security"]))
        event = EventPayload("e1", "system", "test", {})
        delivered = bus.publish(event)
        pending = bus.poll(sub.subscriber_id)
        assert record(
            "WES-055", "Filtered subscriber receives 0 mismatched events",
            0, len(pending),
            cause="Subscriber listens on 'security', event on 'system'",
            effect="No events delivered",
            lesson="Filters reduce noise for focused dashboards",
        )

    def test_unsubscribe(self, bus: EventBus, subscriber: Subscriber):
        """WES-056: Unsubscribe removes the subscriber."""
        result = bus.unsubscribe(subscriber.subscriber_id)
        assert record(
            "WES-056", "Unsubscribe returns True",
            True, result,
            cause="Unsubscribe existing subscriber",
            effect="Returns True, subscriber gone",
            lesson="Clean disconnects are essential for resource management",
        )

    def test_heartbeat_refreshes(self, bus: EventBus, subscriber: Subscriber):
        """WES-057: Heartbeat keeps subscriber alive."""
        old_hb = subscriber.last_heartbeat
        time.sleep(0.01)
        bus.heartbeat(subscriber.subscriber_id)
        assert record(
            "WES-057", "Heartbeat updates timestamp",
            True, subscriber.last_heartbeat != old_hb,
            cause="Heartbeat called after a delay",
            effect="Timestamp updated",
            lesson="Heartbeats prevent premature expiry",
        )


# ============================================================================
# FLASK API ENDPOINT TESTS
# ============================================================================

class TestFlaskAPI:
    """WES-060: REST API endpoints."""

    def test_subscribe_endpoint(self, flask_client):
        """WES-060: POST /api/events/subscribe creates subscriber."""
        resp = flask_client.post(
            "/api/events/subscribe",
            json={"name": "dashboard-1", "channels": ["system"]},
        )
        assert record(
            "WES-060", "Subscribe endpoint returns 201",
            201, resp.status_code,
            cause="POST subscribe request",
            effect="201 Created with subscriber_id",
            lesson="REST subscribe is the entry point for dashboards",
        )
        data = resp.get_json()
        assert "subscriber_id" in data

    def test_publish_endpoint(self, flask_client):
        """WES-061: POST /api/events/publish broadcasts an event."""
        resp = flask_client.post(
            "/api/events/publish",
            json={
                "channel": "system",
                "event_type": "test",
                "data": {"key": "value"},
            },
        )
        assert record(
            "WES-061", "Publish endpoint returns 201",
            201, resp.status_code,
            cause="POST publish with valid event",
            effect="201 Created with event_id",
            lesson="Events must be publishable via REST for integrations",
        )

    def test_publish_invalid_data(self, flask_client):
        """WES-062: Publish rejects non-dict data field."""
        resp = flask_client.post(
            "/api/events/publish",
            json={"channel": "system", "data": "not-a-dict"},
        )
        assert record(
            "WES-062", "Publish rejects invalid data",
            400, resp.status_code,
            cause="data field is a string, not a dict",
            effect="400 Bad Request",
            lesson="Input validation prevents malformed events",
        )

    def test_poll_endpoint(self, flask_client):
        """WES-063: GET /api/events/poll/<id> returns events."""
        # subscribe first
        sub_resp = flask_client.post(
            "/api/events/subscribe", json={"name": "poller"},
        )
        sub_id = sub_resp.get_json()["subscriber_id"]
        # publish an event
        flask_client.post(
            "/api/events/publish",
            json={"channel": "system", "event_type": "ping", "data": {}},
        )
        # poll
        poll_resp = flask_client.get(f"/api/events/poll/{sub_id}")
        data = poll_resp.get_json()
        assert record(
            "WES-063", "Poll returns published event",
            True, data["count"] >= 1,
            cause="Subscribe, publish, then poll",
            effect="At least 1 event returned",
            lesson="REST polling is the simplest real-time pattern",
        )

    def test_channels_endpoint(self, flask_client):
        """WES-064: GET /api/events/channels lists channels."""
        resp = flask_client.get("/api/events/channels")
        data = resp.get_json()
        assert record(
            "WES-064", "Channels endpoint returns built-in channels",
            True, "system" in data["channels"],
            cause="GET channels",
            effect="system channel listed",
            lesson="Channel discovery helps UI auto-populate dropdowns",
        )

    def test_stats_endpoint(self, flask_client):
        """WES-065: GET /api/events/stats returns statistics."""
        resp = flask_client.get("/api/events/stats")
        data = resp.get_json()
        assert record(
            "WES-065", "Stats endpoint returns total_published",
            True, "total_published" in data,
            cause="GET stats",
            effect="total_published field present",
            lesson="Stats give operators a health pulse of the event bus",
        )

    def test_unsubscribe_not_found(self, flask_client):
        """WES-066: Unsubscribe unknown ID returns 404."""
        resp = flask_client.delete("/api/events/unsubscribe/nonexistent")
        assert record(
            "WES-066", "Unsubscribe unknown returns 404",
            404, resp.status_code,
            cause="DELETE with fake subscriber_id",
            effect="404 Not Found",
            lesson="Graceful error for stale dashboard references",
        )

    def test_history_endpoint(self, flask_client):
        """WES-067: GET /api/events/history/<channel> returns history."""
        flask_client.post(
            "/api/events/publish",
            json={"channel": "health", "event_type": "check", "data": {}},
        )
        resp = flask_client.get("/api/events/history/health")
        data = resp.get_json()
        assert record(
            "WES-067", "History endpoint returns events",
            True, data["count"] >= 1,
            cause="Publish to health, then GET history",
            effect="At least 1 event in history",
            lesson="History lets new dashboards catch up on missed events",
        )

    def test_subscribers_endpoint(self, flask_client):
        """WES-068: GET /api/events/subscribers lists all subscribers."""
        flask_client.post(
            "/api/events/subscribe", json={"name": "dash-x"},
        )
        resp = flask_client.get("/api/events/subscribers")
        data = resp.get_json()
        assert record(
            "WES-068", "Subscribers endpoint returns count >= 1",
            True, data["count"] >= 1,
            cause="Subscribe then list",
            effect="At least 1 subscriber returned",
            lesson="Subscriber list helps admins see who is connected",
        )


# ============================================================================
# THREAD SAFETY TESTS
# ============================================================================

class TestThreadSafety:
    """WES-070: Concurrent access to the event bus."""

    def test_concurrent_publish(self):
        """WES-070: Many threads publishing concurrently."""
        bus = EventBus()
        sub = bus.subscribe("concurrent-test")
        errors: List[str] = []

        def _publish(n: int) -> None:
            try:
                for i in range(20):
                    bus.publish(EventPayload(
                        f"e-{n}-{i}", "system", "load",
                        {"thread": n, "seq": i},
                    ))
            except Exception as exc:
                errors.append(str(exc))

        threads = [threading.Thread(target=_publish, args=(t,)) for t in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        events = bus.poll(sub.subscriber_id, max_items=200)
        assert record(
            "WES-070", "100 events published concurrently without errors",
            True, len(errors) == 0 and len(events) == 100,
            cause="5 threads × 20 events = 100",
            effect=f"Got {len(events)} events, {len(errors)} errors",
            lesson="Thread-safe bus is critical for real-time streaming",
        )


# ============================================================================
# WINGMAN PAIR VALIDATION
# ============================================================================

class TestWingmanGate:
    """WES-080: Wingman pair validation for event publishing."""

    def test_wingman_validates_event(self, bus: EventBus, sample_event: EventPayload):
        """WES-080: Wingman protocol validates a published event."""
        from wingman_protocol import (
            ExecutionRunbook,
            ValidationRule,
            ValidationSeverity,
            WingmanProtocol,
        )

        bus.publish(sample_event)

        protocol = WingmanProtocol()
        runbook = ExecutionRunbook(
            runbook_id="rb-wes-v1",
            name="Event Publisher Validator",
            domain="event_streaming",
            validation_rules=[
                ValidationRule(
                    "r-001", "Must produce output",
                    "check_has_output", ValidationSeverity.BLOCK,
                ),
                ValidationRule(
                    "r-002", "No PII in output",
                    "check_no_pii", ValidationSeverity.WARN,
                ),
            ],
        )
        protocol.register_runbook(runbook)
        pair = protocol.create_pair(
            subject="event-streaming-publish",
            executor_id="event-bus",
            validator_id="event-integrity-checker",
            runbook_id="rb-wes-v1",
        )

        output = {"result": sample_event.to_dict(), "confidence": 0.95}
        validation = protocol.validate_output(pair.pair_id, output)

        assert record(
            "WES-080", "Wingman approves published event",
            True, validation["approved"],
            cause="Event payload passes runbook checks",
            effect="Event approved by wingman validator",
            lesson="Gate all event publishing through Wingman pairs",
        )


# ============================================================================
# CAUSALITY SANDBOX GATING
# ============================================================================

class TestCausalitySandboxGate:
    """WES-090: Causality Sandbox simulates event broadcast effects."""

    def test_sandbox_simulates_broadcast(self):
        """WES-090: CausalitySandboxEngine runs a cycle for broadcast validation."""
        from causality_sandbox import CausalitySandboxEngine

        class _BroadcastGap:
            gap_id = "gap-wes-broadcast-001"
            category = "event_streaming"
            severity = "medium"
            description = "Proposed event broadcast needs impact simulation"

        class _FakeLoop:
            config = {"state": "nominal"}
            metrics = {"uptime": 99.9}
            def get_state(self):
                return {"healthy": True}

        engine = CausalitySandboxEngine(
            self_fix_loop_factory=lambda: _FakeLoop(),
        )

        report = engine.run_sandbox_cycle([_BroadcastGap()], _FakeLoop())

        assert record(
            "WES-090", "Sandbox cycle completes for broadcast gap",
            True, report.gaps_analyzed >= 1,
            cause="One broadcast gap submitted",
            effect="Sandbox simulates candidate actions",
            lesson="Never broadcast events without sandbox validation",
        )


# ============================================================================
# USER-AGENT OPERATION TESTS (non-technical user workflows)
# ============================================================================

class TestUserAgentWorkflows:
    """WES-100: End-to-end workflows as a non-technical user would operate."""

    def test_full_dashboard_lifecycle(self, flask_client):
        """WES-100: Subscribe → receive events → heartbeat → unsubscribe."""
        # Step 1: User opens dashboard and subscribes
        sub = flask_client.post(
            "/api/events/subscribe",
            json={"name": "operator-dashboard", "channels": ["system", "health"]},
        )
        assert sub.status_code == 201
        sub_id = sub.get_json()["subscriber_id"]

        # Step 2: System publishes health event
        flask_client.post(
            "/api/events/publish",
            json={
                "channel": "health",
                "event_type": "status_check",
                "data": {"all_services": "healthy"},
                "severity": "info",
            },
        )

        # Step 3: Dashboard polls for events
        poll = flask_client.get(f"/api/events/poll/{sub_id}")
        assert poll.get_json()["count"] >= 1

        # Step 4: Dashboard sends heartbeat
        hb = flask_client.post(f"/api/events/heartbeat/{sub_id}")
        assert hb.status_code == 200

        # Step 5: User closes dashboard
        unsub = flask_client.delete(f"/api/events/unsubscribe/{sub_id}")
        assert record(
            "WES-100", "Full dashboard lifecycle completes",
            200, unsub.status_code,
            cause="Subscribe → publish → poll → heartbeat → unsubscribe",
            effect="All steps succeed with correct status codes",
            lesson="Non-technical users need a simple lifecycle",
        )

    def test_multi_dashboard_isolation(self, flask_client):
        """WES-101: Two dashboards see only their filtered events."""
        # Dashboard A watches system events
        a = flask_client.post(
            "/api/events/subscribe",
            json={"name": "dash-system", "channels": ["system"]},
        )
        a_id = a.get_json()["subscriber_id"]

        # Dashboard B watches security events
        b = flask_client.post(
            "/api/events/subscribe",
            json={"name": "dash-security", "channels": ["security"]},
        )
        b_id = b.get_json()["subscriber_id"]

        # Publish a system event
        flask_client.post(
            "/api/events/publish",
            json={"channel": "system", "event_type": "restart", "data": {}},
        )

        events_a = flask_client.get(f"/api/events/poll/{a_id}").get_json()
        events_b = flask_client.get(f"/api/events/poll/{b_id}").get_json()

        assert record(
            "WES-101", "Dashboard isolation: A gets event, B does not",
            True, events_a["count"] >= 1 and events_b["count"] == 0,
            cause="System event published; A filters system, B filters security",
            effect="Only A receives the event",
            lesson="Channel filters prevent information overload",
        )


# ============================================================================
# SUMMARY
# ============================================================================

@pytest.fixture(autouse=True, scope="session")
def print_summary():
    """Print a summary at the end of the session."""
    yield
    total = len(_records)
    passed = sum(1 for r in _records if r.passed)
    failed = total - passed
    print(f"\n{'=' * 60}")
    print(f"WES-001 Results: {passed}/{total} passed, {failed} failed")
    if failed:
        for r in _records:
            if not r.passed:
                print(f"  FAIL {r.check_id}: {r.description}")
                print(f"       expected={r.expected!r} actual={r.actual!r}")
    print(f"{'=' * 60}")
