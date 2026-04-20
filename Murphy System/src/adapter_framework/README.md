# `src/adapter_framework` — Sensor / Robot Adapter Framework

Standardises device telemetry ingestion and actuation across all physical interfaces with strict safety enforcement.

![License: BSL 1.1](https://img.shields.io/badge/License-BSL%201.1-blue.svg)

## Overview

The adapter framework defines the contract every sensor and robot adapter must satisfy before it may receive or emit data. All telemetry flows through a typed ingestion pipeline that converts raw device readings into `TelemetryArtifact` objects consumable by the Control Plane. Actuation is only possible through compiled `DeviceExecutionPacket` objects — no free-form commands are ever forwarded to hardware. Safety hooks including an emergency-stop and a heartbeat watchdog guard every registered adapter at runtime.

## Key Components

| Module | Purpose |
|--------|---------|
| `adapter_contract.py` | `AdapterAPI`, `AdapterCapability`, and `AdapterManifest` interface definitions |
| `adapter_runtime.py` | `AdapterRuntime` execution loop and `AdapterRegistry` for managing live adapters |
| `execution_packet_extension.py` | `DeviceExecutionPacket` — compiled hardware command with gate checks |
| `safety_hooks.py` | `SafetyHooks`, `EmergencyStop`, and `HeartbeatWatchdog` enforcement layer |
| `telemetry_artifact.py` | `TelemetryArtifact` model and `TelemetryIngestionPipeline` normalisation logic |
| `adapters/` | Built-in adapter implementations for common device categories |

## Usage

```python
from adapter_framework import AdapterRegistry, AdapterRuntime, SafetyHooks

registry = AdapterRegistry()
runtime = AdapterRuntime(registry=registry, safety_hooks=SafetyHooks())

# Register a device adapter
registry.register(my_sensor_adapter)

# Start ingestion
runtime.start()
```

---
*Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1*
