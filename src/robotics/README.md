# `src/robotics` — Robotics Integration Layer

Unified interface for commanding robots and reading sensors across 12 hardware platforms and protocols.

![License: BSL 1.1](https://img.shields.io/badge/License-BSL%201.1-blue.svg)

## Overview

The robotics package provides a hardware-agnostic abstraction over physical robots and sensors. The `RobotRegistry` maintains a catalogue of all configured robots with their capabilities, connection parameters, and current status. `SensorEngine` continuously polls registered sensors and normalises readings into typed telemetry artifacts. `ActuatorEngine` accepts compiled `ExecutionPacket` commands and dispatches them to the appropriate robot via the correct `ProtocolClient`. All 12 supported robot platforms share the `RobotConfig` model to simplify cross-platform operations.

## Key Components

| Module | Purpose |
|--------|---------|
| `robot_registry.py` | `RobotRegistry` — robot catalogue, status tracking, and capability lookup |
| `sensor_engine.py` | `SensorEngine` — sensor polling, normalisation, and telemetry emission |
| `actuator_engine.py` | `ActuatorEngine` — command dispatch to robot actuators |
| `protocol_clients.py` | `ProtocolClient` base class and `create_client` factory for all platforms |
| `robotics_models.py` | `RobotConfig`, `RobotStatus`, `RobotType` |

## Usage

```python
from robotics import RobotRegistry, SensorEngine, RobotType

registry = RobotRegistry()
registry.add(RobotConfig(robot_id="arm-01", type=RobotType.INDUSTRIAL_ARM, host="192.168.1.50"))

sensor_engine = SensorEngine(registry=registry)
readings = sensor_engine.poll_all()
```

---
*Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1*
