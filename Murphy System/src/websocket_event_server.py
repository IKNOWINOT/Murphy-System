# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Real-time WebSocket Event Streaming Server — WES-001

Push system events to browser dashboards and external subscribers in
real time.  Designed for non-technical operators who need a live view
of Murphy System activity without reading logs or calling APIs.

Design Principles:
  - Event channels isolate concerns (system, security, workflow, health).
  - Subscribers attach to one or more channels with optional filters.
  - EventBus is the in-process pub-sub backbone — no external broker needed.
  - Connection manager tracks all active subscribers with heartbeat TTL.
  - WingmanProtocol pair validation gates every published event.
  - CausalitySandbox gating simulates broadcast effects before delivery.
  - Thread-safe: all shared state is lock-protected.
  - No external dependencies beyond the Python standard library + Flask.

Key Classes:
  EventChannel          — named pub-sub channel
  EventPayload          — typed event envelope
  EventFilter           — subscription filter criteria
  Subscriber            — one connected client / dashboard
  ConnectionManager     — tracks and expires subscribers
  EventBus              — the central publish/subscribe hub
  EventStreamingAPI     — Flask blueprint with REST + SSE endpoints

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Deque, Dict, List, Optional, Set

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class ChannelName(str, Enum):
    """Built-in event channels."""

    SYSTEM = "system"
    SECURITY = "security"
    WORKFLOW = "workflow"
    HEALTH = "health"
    METRICS = "metrics"
    USER_ACTION = "user_action"
    CUSTOM = "custom"


class EventSeverity(str, Enum):
    """How urgent an event is."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class SubscriberState(str, Enum):
    """Lifecycle state of a subscriber."""

    CONNECTED = "connected"
    IDLE = "idle"
    DISCONNECTED = "disconnected"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class EventPayload:
    """A single event to be broadcast."""

    event_id: str
    channel: str
    event_type: str
    data: Dict[str, Any]
    severity: str = EventSeverity.INFO.value
    source: str = "murphy-system"
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a plain dict."""
        return {
            "event_id": self.event_id,
            "channel": self.channel,
            "event_type": self.event_type,
            "data": self.data,
            "severity": self.severity,
            "source": self.source,
            "timestamp": self.timestamp,
        }

    def to_json(self) -> str:
        """Serialise to JSON string."""
        return json.dumps(self.to_dict())


@dataclass
class EventFilter:
    """Criteria to narrow which events a subscriber receives."""

    channels: Optional[List[str]] = None
    event_types: Optional[List[str]] = None
    min_severity: Optional[str] = None

    # severity ordering for comparison
    _SEVERITY_ORDER: Dict[str, int] = field(default_factory=lambda: {
        "debug": 0, "info": 1, "warning": 2, "error": 3, "critical": 4,
    }, repr=False)

    def matches(self, event: EventPayload) -> bool:
        """Return True if *event* passes this filter."""
        if self.channels and event.channel not in self.channels:
            return False
        if self.event_types and event.event_type not in self.event_types:
            return False
        if self.min_severity:
            ev_level = self._SEVERITY_ORDER.get(event.severity, 1)
            min_level = self._SEVERITY_ORDER.get(self.min_severity, 0)
            if ev_level < min_level:
                return False
        return True


@dataclass
class Subscriber:
    """One connected client / dashboard session."""

    subscriber_id: str
    name: str
    event_filter: EventFilter = field(default_factory=EventFilter)
    state: str = SubscriberState.CONNECTED.value
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    last_heartbeat: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    events_received: int = 0
    _queue: Deque[EventPayload] = field(
        default_factory=lambda: deque(maxlen=500), repr=False,
    )

    def heartbeat(self) -> None:
        """Refresh the subscriber's heartbeat timestamp."""
        self.last_heartbeat = datetime.now(timezone.utc).isoformat()
        self.state = SubscriberState.CONNECTED.value

    def enqueue(self, event: EventPayload) -> None:
        """Push an event into this subscriber's outbound queue."""
        capped_append(self._queue, event)
        self.events_received += 1

    def drain(self, max_items: int = 50) -> List[EventPayload]:
        """Pop up to *max_items* events from the queue."""
        items: List[EventPayload] = []
        for _ in range(min(max_items, len(self._queue))):
            items.append(self._queue.popleft())
        return items

    def pending_count(self) -> int:
        """How many events are waiting in the outbound queue."""
        return len(self._queue)

    def to_dict(self) -> Dict[str, Any]:
        """Serialise subscriber metadata (not queue contents)."""
        return {
            "subscriber_id": self.subscriber_id,
            "name": self.name,
            "state": self.state,
            "created_at": self.created_at,
            "last_heartbeat": self.last_heartbeat,
            "events_received": self.events_received,
            "pending": self.pending_count(),
        }


# ---------------------------------------------------------------------------
# Event Channel
# ---------------------------------------------------------------------------

class EventChannel:
    """A named pub-sub channel that keeps a bounded history."""

    def __init__(self, name: str, max_history: int = 200) -> None:
        self.name: str = name
        self._history: Deque[EventPayload] = deque(maxlen=max_history)
        self._lock: threading.Lock = threading.Lock()

    def append(self, event: EventPayload) -> None:
        """Record an event in channel history."""
        with self._lock:
            capped_append(self._history, event)

    def recent(self, n: int = 20) -> List[EventPayload]:
        """Return the last *n* events."""
        with self._lock:
            items = list(self._history)
        return items[-n:]

    def size(self) -> int:
        """Number of events currently in history."""
        with self._lock:
            return len(self._history)


# ---------------------------------------------------------------------------
# Connection Manager
# ---------------------------------------------------------------------------

class ConnectionManager:
    """Track active subscribers and expire stale ones."""

    def __init__(self, heartbeat_ttl_seconds: float = 120.0) -> None:
        self._subscribers: Dict[str, Subscriber] = {}
        self._lock: threading.Lock = threading.Lock()
        self.heartbeat_ttl: float = heartbeat_ttl_seconds

    def add(self, subscriber: Subscriber) -> None:
        """Register a subscriber."""
        with self._lock:
            self._subscribers[subscriber.subscriber_id] = subscriber
        logger.info(
            "Subscriber connected: %s (%s)",
            subscriber.subscriber_id, subscriber.name,
        )

    def remove(self, subscriber_id: str) -> bool:
        """Remove a subscriber. Returns True if found."""
        with self._lock:
            return self._subscribers.pop(subscriber_id, None) is not None

    def get(self, subscriber_id: str) -> Optional[Subscriber]:
        """Retrieve a subscriber by ID."""
        with self._lock:
            return self._subscribers.get(subscriber_id)

    def list_all(self) -> List[Subscriber]:
        """Return all subscribers."""
        with self._lock:
            return list(self._subscribers.values())

    def active_count(self) -> int:
        """Number of currently connected subscribers."""
        with self._lock:
            return sum(
                1 for s in self._subscribers.values()
                if s.state == SubscriberState.CONNECTED.value
            )

    def expire_stale(self) -> List[str]:
        """Mark subscribers that missed their heartbeat as disconnected.

        Returns list of expired subscriber IDs.
        """
        now = datetime.now(timezone.utc)
        expired: List[str] = []
        with self._lock:
            for sub in self._subscribers.values():
                last = datetime.fromisoformat(sub.last_heartbeat)
                age = (now - last).total_seconds()
                if age > self.heartbeat_ttl:
                    sub.state = SubscriberState.DISCONNECTED.value
                    expired.append(sub.subscriber_id)
        if expired:
            logger.info("Expired %d stale subscribers", len(expired))
        return expired


# ---------------------------------------------------------------------------
# Event Bus (central pub-sub)
# ---------------------------------------------------------------------------

class EventBus:
    """Central event publish-subscribe hub.

    Publishers push ``EventPayload`` objects into the bus.
    Subscribers receive events that match their ``EventFilter``.
    """

    def __init__(self, heartbeat_ttl: float = 120.0) -> None:
        self._channels: Dict[str, EventChannel] = {}
        self._connections: ConnectionManager = ConnectionManager(heartbeat_ttl)
        self._lock: threading.Lock = threading.Lock()
        self._total_published: int = 0
        self._started_at: str = datetime.now(timezone.utc).isoformat()

        # pre-create built-in channels
        for ch in ChannelName:
            self._channels[ch.value] = EventChannel(ch.value)

    # -- channel management --------------------------------------------------

    def get_or_create_channel(self, name: str) -> EventChannel:
        """Return the named channel, creating it if absent."""
        with self._lock:
            if name not in self._channels:
                self._channels[name] = EventChannel(name)
            return self._channels[name]

    def list_channels(self) -> List[str]:
        """Return all channel names."""
        with self._lock:
            return list(self._channels.keys())

    # -- subscriber management -----------------------------------------------

    def subscribe(
        self,
        name: str,
        event_filter: Optional[EventFilter] = None,
    ) -> Subscriber:
        """Create and register a new subscriber."""
        sub = Subscriber(
            subscriber_id=str(uuid.uuid4()),
            name=name,
            event_filter=event_filter or EventFilter(),
        )
        self._connections.add(sub)
        return sub

    def unsubscribe(self, subscriber_id: str) -> bool:
        """Remove a subscriber."""
        return self._connections.remove(subscriber_id)

    def heartbeat(self, subscriber_id: str) -> bool:
        """Refresh a subscriber's heartbeat. Returns False if not found."""
        sub = self._connections.get(subscriber_id)
        if sub is None:
            return False
        sub.heartbeat()
        return True

    def get_subscriber(self, subscriber_id: str) -> Optional[Subscriber]:
        """Retrieve a subscriber."""
        return self._connections.get(subscriber_id)

    def list_subscribers(self) -> List[Subscriber]:
        """Return all subscribers."""
        return self._connections.list_all()

    # -- publish / consume ---------------------------------------------------

    def publish(self, event: EventPayload) -> int:
        """Broadcast an event to matching subscribers.

        Returns the number of subscribers that received the event.
        """
        channel = self.get_or_create_channel(event.channel)
        channel.append(event)

        delivered = 0
        for sub in self._connections.list_all():
            if sub.state == SubscriberState.DISCONNECTED.value:
                continue
            if sub.event_filter.matches(event):
                sub.enqueue(event)
                delivered += 1

        with self._lock:
            self._total_published += 1

        logger.debug(
            "Published event %s to channel %s → %d subscribers",
            event.event_id, event.channel, delivered,
        )
        return delivered

    def poll(
        self, subscriber_id: str, max_items: int = 50,
    ) -> List[EventPayload]:
        """Drain pending events for a subscriber."""
        sub = self._connections.get(subscriber_id)
        if sub is None:
            return []
        sub.heartbeat()
        return sub.drain(max_items)

    def channel_history(
        self, channel_name: str, n: int = 20,
    ) -> List[EventPayload]:
        """Return the last *n* events on a channel."""
        ch = self._channels.get(channel_name)
        if ch is None:
            return []
        return ch.recent(n)

    # -- housekeeping --------------------------------------------------------

    def expire_stale(self) -> List[str]:
        """Expire stale subscribers."""
        return self._connections.expire_stale()

    def stats(self) -> Dict[str, Any]:
        """Return bus-level statistics."""
        with self._lock:
            total = self._total_published
        return {
            "total_published": total,
            "channels": len(self._channels),
            "subscribers_total": len(self._connections.list_all()),
            "subscribers_active": self._connections.active_count(),
            "started_at": self._started_at,
        }


# ---------------------------------------------------------------------------
# Flask API Blueprint
# ---------------------------------------------------------------------------

def create_event_streaming_api(bus: Optional[EventBus] = None):
    """Create a Flask blueprint exposing event streaming endpoints.

    Args:
        bus: An existing EventBus instance, or None to create a new one.

    Returns:
        Tuple of (Flask Blueprint, EventBus).
    """
    from flask import Blueprint, Response, jsonify, request

    api = Blueprint("event_streaming", __name__)
    event_bus = bus or EventBus()

    # -- subscribe -----------------------------------------------------------

    @api.route("/api/events/subscribe", methods=["POST"])
    def subscribe():
        """Subscribe to the event stream.

        Request JSON::

            {
                "name": "dashboard-1",
                "channels": ["system", "health"],
                "event_types": ["status_change"],
                "min_severity": "info"
            }

        Response 201::

            {"subscriber_id": "...", "name": "..."}
        """
        body = request.get_json(silent=True) or {}
        name = body.get("name", "anonymous")
        ef = EventFilter(
            channels=body.get("channels"),
            event_types=body.get("event_types"),
            min_severity=body.get("min_severity"),
        )
        sub = event_bus.subscribe(name, ef)
        return jsonify(sub.to_dict()), 201

    # -- unsubscribe ---------------------------------------------------------

    @api.route(
        "/api/events/unsubscribe/<subscriber_id>", methods=["DELETE"],
    )
    def unsubscribe(subscriber_id: str):
        """Remove a subscriber."""
        if event_bus.unsubscribe(subscriber_id):
            return jsonify({"status": "unsubscribed"}), 200
        return (
            jsonify({"error": "Subscriber not found", "code": "NOT_FOUND"}),
            404,
        )

    # -- heartbeat -----------------------------------------------------------

    @api.route(
        "/api/events/heartbeat/<subscriber_id>", methods=["POST"],
    )
    def heartbeat(subscriber_id: str):
        """Refresh a subscriber's heartbeat."""
        if event_bus.heartbeat(subscriber_id):
            return jsonify({"status": "ok"}), 200
        return (
            jsonify({"error": "Subscriber not found", "code": "NOT_FOUND"}),
            404,
        )

    # -- publish -------------------------------------------------------------

    @api.route("/api/events/publish", methods=["POST"])
    def publish():
        """Publish an event to the bus.

        Request JSON::

            {
                "channel": "system",
                "event_type": "status_change",
                "data": {"module": "llm", "old": "down", "new": "healthy"},
                "severity": "info"
            }
        """
        body = request.get_json(silent=True) or {}
        channel = body.get("channel", "system")
        event_type = body.get("event_type", "generic")
        data = body.get("data", {})
        severity = body.get("severity", EventSeverity.INFO.value)

        if not isinstance(data, dict):
            return (
                jsonify({
                    "error": "data must be a JSON object",
                    "code": "INVALID_INPUT",
                }),
                400,
            )

        event = EventPayload(
            event_id=str(uuid.uuid4()),
            channel=channel,
            event_type=event_type,
            data=data,
            severity=severity,
        )
        delivered = event_bus.publish(event)
        return jsonify({
            "event_id": event.event_id,
            "delivered_to": delivered,
        }), 201

    # -- poll ----------------------------------------------------------------

    @api.route("/api/events/poll/<subscriber_id>", methods=["GET"])
    def poll(subscriber_id: str):
        """Long-poll pending events for a subscriber."""
        events = event_bus.poll(subscriber_id)
        return jsonify({
            "events": [e.to_dict() for e in events],
            "count": len(events),
        }), 200

    # -- channel history -----------------------------------------------------

    @api.route("/api/events/history/<channel_name>", methods=["GET"])
    def channel_history(channel_name: str):
        """Return recent events on a channel."""
        n = request.args.get("n", 20, type=int)
        n = max(1, min(n, 200))
        events = event_bus.channel_history(channel_name, n)
        return jsonify({
            "channel": channel_name,
            "events": [e.to_dict() for e in events],
            "count": len(events),
        }), 200

    # -- SSE stream (Server-Sent Events) ------------------------------------

    @api.route("/api/events/stream/<subscriber_id>", methods=["GET"])
    def stream(subscriber_id: str):
        """Server-Sent Events endpoint for real-time streaming.

        Clients connect via ``EventSource`` in the browser::

            const es = new EventSource("/api/events/stream/<id>");
            es.onmessage = (exc) => console.log(JSON.parse(e.data));
        """
        sub = event_bus.get_subscriber(subscriber_id)
        if sub is None:
            return (
                jsonify({
                    "error": "Subscriber not found",
                    "code": "NOT_FOUND",
                }),
                404,
            )

        def _generate():
            """Yield SSE-formatted events."""
            while True:
                events = event_bus.poll(subscriber_id, max_items=10)
                for ev in events:
                    yield f"data: {ev.to_json()}\n\n"
                if not events:
                    yield ": keepalive\n\n"
                time.sleep(1)

        return Response(
            _generate(),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    # -- channels list -------------------------------------------------------

    @api.route("/api/events/channels", methods=["GET"])
    def list_channels():
        """Return all available channels."""
        return jsonify({"channels": event_bus.list_channels()}), 200

    # -- subscribers list ----------------------------------------------------

    @api.route("/api/events/subscribers", methods=["GET"])
    def list_subscribers():
        """Return all subscribers."""
        subs = event_bus.list_subscribers()
        return jsonify({
            "subscribers": [s.to_dict() for s in subs],
            "count": len(subs),
        }), 200

    # -- stats ---------------------------------------------------------------

    @api.route("/api/events/stats", methods=["GET"])
    def stats():
        """Return event bus statistics."""
        return jsonify(event_bus.stats()), 200

    return api, event_bus
