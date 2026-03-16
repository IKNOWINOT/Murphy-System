# Telemetry System

The `telemetry_system` package is the central observability backbone for
the Murphy System.  It receives structured events from all subsystems,
buffers them, forwards to configured sinks (Prometheus, Loki, file), and
drives the learning-feedback loop.

## Key Module

| Module | Purpose |
|--------|---------|
| `telemetry.py` | `TelemetrySystem` — singleton event bus, metric registry, log forwarder |

## Key Concepts

- **Events** are emitted via `telemetry.emit(event_type, payload)`.
- **Metrics** are incremented via `telemetry.increment(metric_name, labels)`.
- **Sinks** are registered at startup; multiple sinks can be active.

## Usage

```python
from telemetry_system.telemetry import TelemetrySystem
tel = TelemetrySystem.instance()
tel.emit("TASK_COMPLETED", {"task_id": "t-123", "duration_ms": 450})
```
