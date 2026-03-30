# murphy-event-backbone

[![PyPI version](https://img.shields.io/pypi/v/murphy-event-backbone.svg)](https://pypi.org/project/murphy-event-backbone/)
[![Python versions](https://img.shields.io/pypi/pyversions/murphy-event-backbone.svg)](https://pypi.org/project/murphy-event-backbone/)
[![License](https://img.shields.io/badge/license-BSL--1.1-blue.svg)](LICENSE)
[![Zero dependencies](https://img.shields.io/badge/dependencies-zero-brightgreen.svg)](pyproject.toml)

**Durable in-process event bus with pub/sub, circuit breakers, dead letter queue, and retry. Zero dependencies.**

A feature-rich event backbone extracted from the [Murphy System](https://github.com/IKNOWINOT/Murphy-System) — an actively-developed AI agent platform currently in alpha. Drop it into any Python project that needs reliable in-process event routing.

---

## Status / Maturity

**Alpha.** This library is extracted from [Murphy System](https://github.com/IKNOWINOT/Murphy-System), which is under active development and has not yet reached a stable production release. The core API works and the tests cover real edge cases, but expect things to evolve.

- The core API (`publish`, `subscribe`, `process_pending`, circuit breakers, DLQ) is stable enough to build on
- Configuration options and edge-case behaviour may change between minor versions
- Feedback, bug reports, and pull requests are very welcome — your use cases directly shape the next iteration

> Hit a rough edge? Please [open an issue](https://github.com/IKNOWINOT/Murphy-System/issues). Community input is how this gets better.

---

## Features

- **Pub/Sub** — subscribe handlers to string event types; publish from anywhere in your code
- **Circuit breakers** — per-handler trip-wires that stop cascading failures
- **Dead letter queue (DLQ)** — exhausted retries land here for inspection and replay
- **Retry with backoff** — configurable `max_retries` per event
- **Idempotent publishing** — duplicate event IDs are silently dropped
- **Disk persistence** — atomic JSON snapshots survive process restarts
- **Backpressure detection** — emits `system.backpressure` events when queues get too deep
- **Background processing loop** — optional daemon thread drains queues automatically
- **Thread-safe** — all operations are lock-guarded; safe to publish/subscribe from multiple threads
- **String-based event types** — no enum lock-in; define your own vocabulary

---

## Install

```bash
pip install murphy-event-backbone
```

No dependencies are installed — just Python stdlib.

---

## Quick start

```python
from murphy_event_backbone import EventBackbone, Event

bb = EventBackbone()

# Subscribe a handler
def on_order_created(event: Event) -> None:
    print(f"New order: {event.payload}")

bb.subscribe("order.created", on_order_created)

# Publish an event
bb.publish("order.created", {"order_id": 42, "total": 99.99})

# Process pending events (manual mode)
bb.process_pending()
# → New order: {'order_id': 42, 'total': 99.99}
```

---

## Background loop (automatic processing)

```python
bb = EventBackbone(loop_interval_ms=100)
bb.subscribe("order.created", on_order_created)
bb.start()  # starts daemon thread

# Events are now processed automatically every 100 ms
bb.publish("order.created", {"order_id": 43})

import time; time.sleep(0.2)  # let the loop run

bb.stop()  # graceful shutdown
```

---

## Circuit breakers

Each subscriber gets its own circuit breaker. If a handler raises exceptions
`circuit_breaker_threshold` times in a row, the breaker opens and the handler
is skipped until `circuit_breaker_timeout` seconds have elapsed.

```python
bb = EventBackbone(
    circuit_breaker_threshold=5,   # open after 5 consecutive failures
    circuit_breaker_timeout=60.0,  # probe again after 60 seconds
)
```

Inspect circuit breaker state:

```python
status = bb.get_status()
for sub_id, state in status["circuit_breakers"].items():
    print(sub_id, state)  # {"open": True, "failures": 5}
```

---

## Dead letter queue

```python
# Events that exhaust all retries end up here
dlq = bb.get_dead_letter_queue()
for event in dlq:
    print(event.event_id, event.event_type, event.payload)

# Re-publish a DLQ event after fixing the underlying issue
bb.publish_event(event)
```

---

## Persistence

```python
bb = EventBackbone(persistence_dir="/var/lib/myapp/events")

# State is saved atomically on every publish/DLQ write.
# On restart, the queue and DLQ are restored automatically.
bb2 = EventBackbone(persistence_dir="/var/lib/myapp/events")
bb2.process_pending()  # picks up where bb left off
```

---

## Idempotent publishing

```python
from murphy_event_backbone import Event
from datetime import datetime, timezone

event = Event(
    event_id="order-42-created",   # stable ID from your system
    event_type="order.created",
    payload={"order_id": 42},
    timestamp=datetime.now(timezone.utc).isoformat(),
)

bb.publish_event(event)  # True — accepted
bb.publish_event(event)  # False — duplicate, silently dropped
```

---

## Backpressure

When the total number of pending events exceeds `backpressure_threshold`, the backbone:
1. Logs a warning
2. Publishes a `"system.backpressure"` event with `pending` and `threshold` fields

```python
bb = EventBackbone(backpressure_threshold=500)
bb.subscribe("system.backpressure", lambda e: alert_ops(e.payload))
```

---

## API reference

| Method / property | Description |
|---|---|
| `publish(event_type, payload, *, session_id, source)` | Publish a new event; returns `event_id` |
| `publish_event(event)` | Idempotent publish of a pre-built `Event`; returns `False` if duplicate |
| `subscribe(event_type, handler)` | Register a handler; returns `subscription_id` |
| `unsubscribe(subscription_id)` | Remove a handler |
| `process_pending()` | Drain all queues synchronously; returns events processed |
| `start()` | Start background processing daemon thread |
| `stop()` | Stop background thread (graceful) |
| `is_running` | `True` if background thread is alive |
| `loop_interval_ms` | Configured loop interval in milliseconds |
| `get_dead_letter_queue()` | Returns list of `Event` objects that exhausted retries |
| `get_status()` | Returns dict with counters, pending counts, DLQ size, circuit breaker states, metrics |
| `get_event_history(event_type, session_id, limit)` | Query processed event log |

### `Event` dataclass fields

| Field | Type | Description |
|---|---|---|
| `event_id` | `str` | Unique identifier (UUID by default) |
| `event_type` | `str` | String event type (user-defined) |
| `payload` | `dict` | Arbitrary JSON-serializable data |
| `timestamp` | `str` | ISO 8601 UTC timestamp |
| `session_id` | `str \| None` | Optional session correlation ID |
| `source` | `str \| None` | Optional source component name |
| `retry_count` | `int` | Current retry attempt (0 = first delivery) |
| `max_retries` | `int` | Max retries before DLQ (default: 3) |

---

## Part of Murphy System

`murphy-event-backbone` is extracted from the [Murphy System](https://github.com/IKNOWINOT/Murphy-System) — an autonomous AI agent platform for business operations. The Murphy System uses this backbone to coordinate events across 20+ internal services including the confidence engine, supervisor system, HITL monitor, and fleet manager.

The extraction philosophy: code lifted from actively-evolving alpha-stage software — real tests, real edge cases, and a zero-dependency constraint so it fits anywhere. It's not a toy project, but it's also not finished; it grows as Murphy System grows.

### Current scope and roadmap

Today the backbone is designed for **intra-process / intra-node** coordination — everything runs inside a single Python process using threads. That's the right starting point for most use cases and the niche that's genuinely underserved in the Python ecosystem.

Multi-process coordination (agent swarms, multi-cursor workflows, fleet workers) is a natural next step for Murphy System's architecture. IPC support (Unix sockets, shared memory) is a potential future direction. The library won't try to replace Kafka or RabbitMQ for cross-node messaging, but inter-process coordination within a single node is in scope for future iterations.

---

## Contributing / Feedback

This project is at an early stage and community input shapes its direction. If you:

- find a bug or rough edge — [open an issue](https://github.com/IKNOWINOT/Murphy-System/issues)
- have a use case that doesn't fit the current API — describe it in an issue; that's the best way to influence the design
- want to contribute code — PRs are welcome; please open an issue first to discuss larger changes

The goal is consensus: building something the Python community finds genuinely useful, not shipping a product. If the API feels wrong for your use case, that's useful signal.

---

## License

[Business Source License 1.1](LICENSE) — source-available, converts to Apache 2.0 on 2029-03-29.
