# `src/telemetry_system` — Telemetry System

Lightweight telemetry collection facade providing `TelemetryCollector` for system-wide metrics and event capture.

![License: BSL 1.1](https://img.shields.io/badge/License-BSL%201.1-blue.svg)

## Overview

The telemetry system package provides the primary entry point for emitting telemetry events from any Murphy subsystem. `TelemetryCollector` is a thin, import-safe façade that buffers metrics and events before forwarding them to the configured backend (Prometheus, Datadog, or the `telemetry_learning` bus). It is designed to be imported with zero overhead even when the full observability stack is not configured, making it safe to use in every package without creating hard dependencies.

## Key Components

| Module | Purpose |
|--------|---------|
| `telemetry.py` | `TelemetryCollector` — event emission, counter increments, and latency recording |

## Usage

```python
from telemetry_system import TelemetryCollector

collector = TelemetryCollector(service="execution_orchestrator")
collector.increment("steps_executed")
collector.record_latency("step_duration_ms", value=42)
collector.emit_event("execution_completed", metadata={"packet_id": "pkt-001"})
```

---
*Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1*
