# Robotics

The `robotics` package provides sensor fusion, actuator control, and
robot-fleet management capabilities for Murphy's physical-automation
integrations.

## Key Modules

| Module | Purpose |
|--------|---------|
| `robot_registry.py` | `RobotRegistry` — fleet registry; registers and tracks robots by ID |
| `sensor_engine.py` | `SensorEngine` — aggregates multi-modal sensor streams |
| `actuator_engine.py` | `ActuatorEngine` — dispatches control commands to actuators |
| `protocol_clients.py` | Low-level communication clients (MQTT, OPC-UA, Modbus) |
| `robotics_models.py` | `Robot`, `SensorReading`, `ActuatorCommand` Pydantic models |

## Usage

```python
from robotics.robot_registry import RobotRegistry
from robotics.sensor_engine import SensorEngine

registry = RobotRegistry()
robot = registry.register(robot_id="arm-001", capabilities=["pick", "place"])

sensors = SensorEngine(robot)
reading = await sensors.read(sensor_type="depth_camera")
```
