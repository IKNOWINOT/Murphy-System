# Murphy System — Robotics Integration Layer
## Robot Registry and Fleet Management Reference (Part 3 of 3)

---

## FILE 17: `src/adapter_framework/robot_registry.py`

Central registry that maps robot platform identifiers to their adapter classes and handles auto-discovery, health monitoring, and fleet-level emergency stop.

```python
"""
Robot Registry

Central registry for all robot adapters in the Murphy System.

Provides:
- Platform-to-adapter-class mapping
- Auto-instantiation from config dict
- Fleet-level health monitoring
- Fleet-level emergency stop
- Telemetry aggregation
"""

from typing import Dict, List, Optional, Type, Any
from .adapter_contract import AdapterAPI
from .adapter_runtime import AdapterRegistry
from .safety_hooks import SafetyHooks


# Platform type → adapter class mapping
PLATFORM_REGISTRY: Dict[str, str] = {
    # Legged robots
    "boston_dynamics_spot":     "adapters.boston_dynamics.spot_adapter.SpotAdapter",
    # Collaborative / industrial arms
    "universal_robots_ur":      "adapters.universal_robots.ur_adapter.URAdapter",
    "fanuc":                    "adapters.industrial.fanuc_adapter.FanucAdapter",
    "kuka":                     "adapters.industrial.kuka_adapter.KUKAAdapter",
    "abb":                      "adapters.industrial.abb_adapter.ABBAdapter",
    # ROS2-based platforms (generic + Clearpath)
    "ros2":                     "adapters.ros2.ros2_adapter.ROS2Adapter",
    "clearpath":                "adapters.mobile.clearpath_adapter.ClearpathAdapter",
    # Industrial protocols
    "modbus":                   "adapters.industrial.modbus_adapter.ModbusAdapter",
    "bacnet":                   "adapters.industrial.bacnet_adapter.BACnetAdapter",
    "opcua":                    "adapters.industrial.opcua_adapter.OPCUAAdapter",
    # Aerial
    "dji":                      "adapters.mobile.dji_adapter.DJIAdapter",
    # IoT
    "mqtt":                     "adapters.iot.mqtt_adapter.MQTTAdapter",
}


class RobotRegistry:
    """
    Fleet-level robot registry.
    
    Usage:
        registry = RobotRegistry()
        registry.register_from_config({
            "platform": "boston_dynamics_spot",
            "hostname": "192.168.80.3",
            "username": "user",
            "password": "password",
            "serial_number": "SPOT-12345"
        })
        registry.emergency_stop_all("Safety violation detected")
    """
    
    def __init__(self):
        self._adapter_registry = AdapterRegistry()
        self._safety_hooks = SafetyHooks()
        self._configs: Dict[str, Dict] = {}
    
    def register_from_config(self, config: Dict[str, Any]) -> AdapterAPI:
        """
        Instantiate and register adapter from config dict.
        
        Config must contain:
            platform: str  — key from PLATFORM_REGISTRY
            + platform-specific connection params
        
        Returns:
            Registered AdapterAPI instance
        
        Raises:
            ValueError: Unknown platform or missing required config
        """
        platform = config.get("platform")
        if not platform:
            raise ValueError("Config must contain 'platform' key")
        
        adapter_path = PLATFORM_REGISTRY.get(platform)
        if not adapter_path:
            raise ValueError(f"Unknown platform: {platform}. "
                           f"Known: {list(PLATFORM_REGISTRY.keys())}")
        
        # Dynamic import
        module_path, class_name = adapter_path.rsplit(".", 1)
        import importlib
        module = importlib.import_module(f"src.adapter_framework.{module_path}")
        adapter_class: Type[AdapterAPI] = getattr(module, class_name)
        
        # Instantiate (each adapter's __init__ accepts **config)
        adapter = adapter_class(**{k: v for k, v in config.items() if k != "platform"})
        
        # Register with safety hooks
        self._safety_hooks.register_adapter(
            adapter.manifest.adapter_id,
            heartbeat_interval=config.get("heartbeat_interval", 5.0),
            timeout=config.get("heartbeat_timeout", 15.0)
        )
        
        # Register with adapter registry
        public_key = config.get("public_key", "murphy_default_public_key")
        runtime = self._adapter_registry.register(adapter, public_key)
        
        self._configs[adapter.manifest.adapter_id] = config
        return adapter
    
    def get_fleet_status(self) -> Dict:
        """Get status of all registered robots."""
        return {
            "fleet_size": len(self._adapter_registry.list_adapters()),
            "adapters": self._adapter_registry.get_system_status(),
            "safety": self._safety_hooks.get_status()
        }
    
    def emergency_stop_all(self, reason: str = "Fleet-wide emergency") -> Dict[str, bool]:
        """Emergency stop all registered robots."""
        return self._adapter_registry.emergency_stop_all(reason)
    
    def get_adapter(self, adapter_id: str) -> Optional[AdapterAPI]:
        """Get adapter by ID."""
        return self._adapter_registry.get_adapter(adapter_id)
    
    def list_adapters(self) -> List[str]:
        """List all registered adapter IDs."""
        return self._adapter_registry.list_adapters()
    
    def read_all_telemetry(self) -> Dict[str, Dict]:
        """Read telemetry from all registered adapters."""
        results = {}
        for adapter_id in self._adapter_registry.list_adapters():
            adapter = self._adapter_registry.get_adapter(adapter_id)
            if adapter and not adapter.is_emergency_stopped:
                try:
                    results[adapter_id] = adapter.read_telemetry()
                except Exception as e:
                    results[adapter_id] = {"error": str(e), "health": "failed"}
        return results
```

---

## FILE 18: MODIFY `universal_control_plane.py`

**Replace the TODO stubs in `SensorEngine.execute()` and `ActuatorEngine.execute()`.**

The `SensorEngine` and `ActuatorEngine` must dispatch through the `AdapterRegistry`. Import `RobotRegistry` at the top of the file and wire it in.

### Changes to `SensorEngine.execute()`:

**Find this block:**
```python
# TODO: Implement actual sensor reading
# For now, return mock data
return {
    'sensor_id': sensor_id,
    'value': 72.5,  # Mock temperature
    'unit': 'fahrenheit',
    'timestamp': datetime.now().isoformat(),
    'protocol': protocol
}
```

**Replace with:**
```python
# Dispatch to registered adapter via AdapterRegistry
from src.adapter_framework.robot_registry import RobotRegistry
_registry = RobotRegistry._instance  # Singleton access
if _registry and sensor_id:
    adapter = _registry.get_adapter(sensor_id)
    if adapter:
        telemetry = adapter.read_telemetry()
        return {
            'sensor_id': sensor_id,
            'value': telemetry.get('state_vector', {}),
            'health': telemetry.get('health', 'unknown'),
            'error_codes': telemetry.get('error_codes', []),
            'timestamp': telemetry.get('timestamp', datetime.now().timestamp()),
            'protocol': protocol,
            'raw_telemetry': telemetry
        }

# Fallback: no adapter registered for this sensor_id
return {
    'sensor_id': sensor_id,
    'value': None,
    'health': 'unregistered',
    'error_codes': [f'no_adapter_registered:{sensor_id}'],
    'timestamp': datetime.now().isoformat(),
    'protocol': protocol
}
```

### Changes to `ActuatorEngine.execute()`:

**Find this block:**
```python
# TODO: Implement actual actuator control
# For now, return mock response
return {
    'actuator_id': actuator_id,
    'command': command,
    'status': 'executed',
    'timestamp': datetime.now().isoformat(),
    'protocol': protocol
}
```

**Replace with:**
```python
# Dispatch to registered adapter via AdapterRegistry
from src.adapter_framework.robot_registry import RobotRegistry
from src.adapter_framework.execution_packet_extension import DeviceExecutionPacket
_registry = RobotRegistry._instance  # Singleton access
if _registry and actuator_id:
    runtime = _registry._adapter_registry.get_runtime(actuator_id)
    if runtime and isinstance(command, DeviceExecutionPacket):
        # command IS a DeviceExecutionPacket — execute directly
        result = runtime.execute(command)
        return {
            'actuator_id': actuator_id,
            'command': command.command.get('action'),
            'status': 'executed' if result.get('success') else 'failed',
            'error': result.get('error'),
            'telemetry': result.get('telemetry'),
            'timestamp': datetime.now().isoformat(),
            'protocol': protocol
        }
    elif runtime and isinstance(command, dict):
        # Raw dict command — log warning, reject (must use DeviceExecutionPacket)
        return {
            'actuator_id': actuator_id,
            'command': command,
            'status': 'rejected',
            'error': 'Commands must be DeviceExecutionPacket. Raw dicts are not accepted.',
            'timestamp': datetime.now().isoformat(),
            'protocol': protocol
        }

# Fallback: no adapter registered
return {
    'actuator_id': actuator_id,
    'command': command,
    'status': 'unregistered',
    'error': f'No adapter registered for actuator_id: {actuator_id}',
    'timestamp': datetime.now().isoformat(),
    'protocol': protocol
}
```

### Add `RobotRegistry` singleton pattern to `robot_registry.py`:

Add to `RobotRegistry.__init__()`:
```python
RobotRegistry._instance = self  # Singleton for UCP access
```

---

## FILE 19: MODIFY `src/adapter_framework/__init__.py`

Add these imports to the existing `__all__` list:

```python
# New robotics imports
from .robot_registry import RobotRegistry, PLATFORM_REGISTRY
from .protocols.modbus_client import MurphyModbusClient
from .protocols.bacnet_client import MurphyBACnetClient
from .protocols.opcua_client import MurphyOPCUAClient
from .protocols.ros2_bridge import ROS2Bridge

# Append to __all__:
__all__ += [
    'RobotRegistry',
    'PLATFORM_REGISTRY',
    'MurphyModbusClient',
    'MurphyBACnetClient',
    'MurphyOPCUAClient',
    'ROS2Bridge',
]
```

---

## FILE 20: MODIFY `src/adapter_framework/adapters/__init__.py`

Replace the existing content with:

```python
"""
Murphy System Robot Adapters

All major robot platform adapters, organized by category.
"""

# Reference implementations (always available)
from .mock_adapter import MockAdapter
from .http_adapter import HTTPAdapter

# Conditional imports (graceful degradation if SDK not installed)
_available_adapters = ['MockAdapter', 'HTTPAdapter']

try:
    from .boston_dynamics.spot_adapter import SpotAdapter
    _available_adapters.append('SpotAdapter')
except ImportError:
    pass  # bosdyn-client not installed

try:
    from .universal_robots.ur_adapter import URAdapter
    _available_adapters.append('URAdapter')
except ImportError:
    pass  # ur-rtde not installed

try:
    from .ros2.ros2_adapter import ROS2Adapter
    _available_adapters.append('ROS2Adapter')
except ImportError:
    pass  # rclpy not installed

try:
    from .mobile.clearpath_adapter import ClearpathAdapter
    _available_adapters.append('ClearpathAdapter')
except ImportError:
    pass  # rclpy not installed

from .industrial.modbus_adapter import ModbusAdapter
from .industrial.bacnet_adapter import BACnetAdapter
from .industrial.opcua_adapter import OPCUAAdapter
from .industrial.fanuc_adapter import FanucAdapter
from .industrial.kuka_adapter import KUKAAdapter
from .industrial.abb_adapter import ABBAdapter
from .mobile.dji_adapter import DJIAdapter
from .iot.mqtt_adapter import MQTTAdapter

_available_adapters += [
    'ModbusAdapter', 'BACnetAdapter', 'OPCUAAdapter',
    'FanucAdapter', 'KUKAAdapter', 'ABBAdapter',
    'DJIAdapter', 'MQTTAdapter'
]

__all__ = _available_adapters


def list_available_adapters() -> list:
    """Return list of adapter class names available in this environment."""
    return _available_adapters.copy()
```

---

## IMPLEMENTATION RULES — READ BEFORE WRITING ANY CODE

### Rule 1: The AdapterAPI Contract Is Sacred
Every adapter MUST implement all five abstract methods. No exceptions. No partial implementations. If a platform doesn't support a feature (e.g., Modbus has no heartbeat endpoint), implement a synthetic heartbeat that reads a status register and returns `{"alive": True/False}`.

### Rule 2: Mock Fallback Is Mandatory
Every adapter MUST have a `_mock_mode: bool` flag. When `mock_mode=True` OR when the SDK is not installed OR when the device is unreachable:
- `read_telemetry()` returns `_mock_telemetry()` with realistic placeholder values
- `execute_command()` returns `_mock_execute(packet)` with `{"success": True, "telemetry": _mock_telemetry()}`
- `emergency_stop()` returns `True`
- `heartbeat()` returns `{"alive": True, "mock": True}`

This ensures the Murphy System can run in simulation mode without any physical hardware.

### Rule 3: Connection Is Lazy
Never connect in `__init__()`. Always connect lazily in `read_telemetry()` and `execute_command()` via `_ensure_connected()`. This prevents startup failures when hardware is offline.

```python
def _ensure_connected(self) -> bool:
    if self._connected:
        return True
    try:
        self._connect()
        self._connected = True
        return True
    except Exception as e:
        self._last_connection_error = str(e)
        self._connected = False
        return False
```

### Rule 4: Telemetry Checksum Is Non-Negotiable
Every `read_telemetry()` MUST compute and include the SHA-256 checksum of `state_vector`:
```python
import json, hashlib
checksum = hashlib.sha256(
    json.dumps(state_vector, sort_keys=True).encode()
).hexdigest()
```
The `TelemetryIngestionPipeline` will reject artifacts with mismatched checksums.

### Rule 5: Emergency Stop Must Be Instantaneous
`emergency_stop()` must:
1. Execute the platform's native E-Stop mechanism FIRST (before any logging)
2. Set `self.is_emergency_stopped = True`
3. Return `True` if the E-Stop signal was sent (even if confirmation is pending)
4. NEVER raise an exception — catch all errors and return `False` on failure

### Rule 6: Safety Limits Are Enforced at Two Layers
The `AdapterRuntime` already enforces `SafetyLimits` via `validate_safety_limits()`. Your adapter's `execute_command()` MUST also call `self.validate_safety_limits(packet.command)` as a second layer. Defense in depth.

### Rule 7: All Adapters Must Handle SDK Import Failures Gracefully
Wrap all SDK imports in try/except at the module level:
```python
try:
    import bosdyn.client
    import bosdyn.client.util
    SPOT_SDK_AVAILABLE = True
except ImportError:
    SPOT_SDK_AVAILABLE = False
```
If `SDK_AVAILABLE = False`, the adapter constructor sets `self._mock_mode = True` automatically.

### Rule 8: Thread Safety for Telemetry Caches
Adapters that use background threads (ROS2, KUKA RSI, MQTT) MUST protect their telemetry caches with `threading.Lock()`:
```python
self._telemetry_lock = threading.Lock()

# In background thread:
with self._telemetry_lock:
    self._latest_state = new_state

# In read_telemetry():
with self._telemetry_lock:
    state = self._latest_state.copy()
```

### Rule 9: Sequence Numbers Must Be Monotonically Increasing
Every `read_telemetry()` call MUST increment `self._sequence_number` by 1. The `TelemetryIngestionPipeline` rejects non-monotonic sequences.

### Rule 10: Error Codes Must Use Murphy Standard Format
All error codes in `error_codes` list must follow the format defined in `ErrorCodeMapper.ERROR_SEVERITY`:
- Use existing codes where applicable: `"communication_lost"`, `"temperature_exceeded"`, `"force_exceeded"`, `"sensor_failure"`, `"actuator_failure"`, `"power_failure"`, `"emergency_stop"`
- For platform-specific errors, prefix with platform name: `"spot_estop"`, `"ur_protective_stop"`, `"fanuc_alarm_1234"`, `"kuka_rsi_timeout"`

---

## DEPENDENCY INSTALLATION

Add to `requirements_murphy_1.0.txt` (or `requirements-robotics.txt`):

```
# Boston Dynamics Spot
bosdyn-client>=3.3.0
bosdyn-mission>=3.3.0
bosdyn-choreography-client>=3.3.0

# Universal Robots
ur-rtde>=1.5.5

# ROS2 (install via apt, not pip — but rclpy is pip-installable in some envs)
# rclpy  # Install via: sudo apt install ros-humble-rclpy

# Industrial Protocols
pymodbus>=3.5.0
BAC0>=22.9.21
asyncua>=1.0.5

# DJI (FlightHub 2 REST — no special SDK needed, uses requests)
# requests already in requirements_murphy_1.0.txt

# MQTT
paho-mqtt>=1.6.1

# Protobuf (for ABB EGM)
protobuf>=4.24.0

# Utilities
numpy>=1.24.0        # For coordinate transforms in ROS2 bridge
scipy>=1.11.0        # For quaternion math
```

---

## TESTING REQUIREMENTS

### Unit Tests: `tests/test_robotics/`

Create one test file per adapter:

**`test_spot_adapter.py`:**
```python
def test_spot_mock_telemetry():
    adapter = SpotAdapter(hostname="192.168.80.3", mock_mode=True)
    telemetry = adapter.read_telemetry()
    assert "state_vector" in telemetry
    assert "checksum" in telemetry
    assert telemetry["health"] in ["healthy", "degraded", "failed"]
    # Verify checksum
    import json, hashlib
    expected = hashlib.sha256(
        json.dumps(telemetry["state_vector"], sort_keys=True).encode()
    ).hexdigest()
    assert telemetry["checksum"] == expected

def test_spot_emergency_stop_mock():
    adapter = SpotAdapter(hostname="192.168.80.3", mock_mode=True)
    result = adapter.emergency_stop()
    assert result == True
    assert adapter.is_emergency_stopped == True

def test_spot_manifest():
    adapter = SpotAdapter(hostname="192.168.80.3", mock_mode=True)
    manifest = adapter.get_manifest()
    assert manifest.adapter_type == "quadruped_robot"
    assert manifest.manufacturer == "Boston Dynamics"
    assert manifest.safety_limits.max_velocity == 1.6
```

**Apply the same test pattern to every adapter:**
- `test_ur_adapter.py`
- `test_ros2_adapter.py`
- `test_modbus_adapter.py`
- `test_bacnet_adapter.py`
- `test_opcua_adapter.py`
- `test_fanuc_adapter.py`
- `test_kuka_adapter.py`
- `test_abb_adapter.py`
- `test_dji_adapter.py`
- `test_clearpath_adapter.py`
- `test_mqtt_adapter.py`
- `test_robot_registry.py`

**`test_robot_registry.py`:**
```python
def test_register_from_config_spot():
    registry = RobotRegistry()
    adapter = registry.register_from_config({
        "platform": "boston_dynamics_spot",
        "hostname": "192.168.80.3",
        "mock_mode": True
    })
    assert adapter is not None
    assert "spot_" in adapter.manifest.adapter_id

def test_fleet_emergency_stop():
    registry = RobotRegistry()
    registry.register_from_config({"platform": "boston_dynamics_spot", "hostname": "192.168.80.3", "mock_mode": True})
    registry.register_from_config({"platform": "modbus", "host": "192.168.1.100", "mock_mode": True})
    results = registry.emergency_stop_all("Test E-Stop")
    assert all(results.values())

def test_unknown_platform_raises():
    registry = RobotRegistry()
    with pytest.raises(ValueError, match="Unknown platform"):
        registry.register_from_config({"platform": "nonexistent_robot"})
```

**`test_ucp_wiring.py`:**
```python
def test_sensor_engine_dispatches_to_adapter():
    registry = RobotRegistry()
    adapter = registry.register_from_config({
        "platform": "modbus", "host": "192.168.1.100", "mock_mode": True
    })
    sensor_engine = SensorEngine()
    action = Action(
        action_id="read_temp",
        action_type=ActionType.READ_SENSOR,
        parameters={"sensor_id": adapter.manifest.adapter_id, "protocol": "Modbus"},
        ...
    )
    result = sensor_engine.execute(action)
    assert result["sensor_id"] == adapter.manifest.adapter_id
    assert result["health"] in ["healthy", "degraded", "failed", "unregistered"]

def test_actuator_engine_rejects_raw_dict():
    registry = RobotRegistry()
    adapter = registry.register_from_config({
        "platform": "modbus", "host": "192.168.1.100", "mock_mode": True
    })
    actuator_engine = ActuatorEngine()
    action = Action(
        action_id="write_coil",
        action_type=ActionType.WRITE_ACTUATOR,
        parameters={
            "actuator_id": adapter.manifest.adapter_id,
            "command": {"action": "write_coil", "address": 0, "value": True},  # Raw dict
            "protocol": "Modbus"
        },
        ...
    )
    result = actuator_engine.execute(action)
    assert result["status"] == "rejected"
    assert "DeviceExecutionPacket" in result["error"]
```

---

## IMPLEMENTATION CHECKLIST

Work through these in order. Do not skip ahead.

### Phase 1 — Protocol Clients (no hardware needed)
- [ ] `src/adapter_framework/protocols/__init__.py`
- [ ] `src/adapter_framework/protocols/modbus_client.py` — `MurphyModbusClient`
- [ ] `src/adapter_framework/protocols/bacnet_client.py` — `MurphyBACnetClient`
- [ ] `src/adapter_framework/protocols/opcua_client.py` — `MurphyOPCUAClient`
- [ ] `src/adapter_framework/protocols/ros2_bridge.py` — `ROS2Bridge`

### Phase 2 — Industrial Adapters (most deployable)
- [ ] `src/adapter_framework/adapters/industrial/__init__.py`
- [ ] `src/adapter_framework/adapters/industrial/modbus_adapter.py` — `ModbusAdapter`
- [ ] `src/adapter_framework/adapters/industrial/bacnet_adapter.py` — `BACnetAdapter`
- [ ] `src/adapter_framework/adapters/industrial/opcua_adapter.py` — `OPCUAAdapter`
- [ ] `src/adapter_framework/adapters/industrial/fanuc_adapter.py` — `FanucAdapter`
- [ ] `src/adapter_framework/adapters/industrial/kuka_adapter.py` — `KUKAAdapter`
- [ ] `src/adapter_framework/adapters/industrial/abb_adapter.py` — `ABBAdapter`

### Phase 3 — IoT & Mobile
- [ ] `src/adapter_framework/adapters/iot/__init__.py`
- [ ] `src/adapter_framework/adapters/iot/mqtt_adapter.py` — `MQTTAdapter`
- [ ] `src/adapter_framework/adapters/mobile/__init__.py`
- [ ] `src/adapter_framework/adapters/mobile/dji_adapter.py` — `DJIAdapter`
- [ ] `src/adapter_framework/adapters/mobile/clearpath_adapter.py` — `ClearpathAdapter`

### Phase 4 — Advanced Platforms
- [ ] `src/adapter_framework/adapters/ros2/__init__.py`
- [ ] `src/adapter_framework/adapters/ros2/ros2_adapter.py` — `ROS2Adapter`
- [ ] `src/adapter_framework/adapters/boston_dynamics/__init__.py`
- [ ] `src/adapter_framework/adapters/boston_dynamics/spot_adapter.py` — `SpotAdapter`
- [ ] `src/adapter_framework/adapters/universal_robots/__init__.py`
- [ ] `src/adapter_framework/adapters/universal_robots/ur_adapter.py` — `URAdapter`

### Phase 5 — Registry & Wiring
- [ ] `src/adapter_framework/robot_registry.py` — `RobotRegistry`
- [ ] Modify `src/adapter_framework/__init__.py` — add new exports
- [ ] Modify `src/adapter_framework/adapters/__init__.py` — conditional imports
- [ ] Modify `universal_control_plane.py` — wire `SensorEngine` + `ActuatorEngine`

### Phase 6 — Tests
- [ ] `tests/test_robotics/__init__.py`
- [ ] `tests/test_robotics/test_modbus_adapter.py`
- [ ] `tests/test_robotics/test_bacnet_adapter.py`
- [ ] `tests/test_robotics/test_opcua_adapter.py`
- [ ] `tests/test_robotics/test_fanuc_adapter.py`
- [ ] `tests/test_robotics/test_kuka_adapter.py`
- [ ] `tests/test_robotics/test_abb_adapter.py`
- [ ] `tests/test_robotics/test_mqtt_adapter.py`
- [ ] `tests/test_robotics/test_dji_adapter.py`
- [ ] `tests/test_robotics/test_clearpath_adapter.py`
- [ ] `tests/test_robotics/test_ros2_adapter.py`
- [ ] `tests/test_robotics/test_spot_adapter.py`
- [ ] `tests/test_robotics/test_ur_adapter.py`
- [ ] `tests/test_robotics/test_robot_registry.py`
- [ ] `tests/test_robotics/test_ucp_wiring.py`

---

## PLATFORM QUICK-REFERENCE CARD

| Platform | Protocol | Port | SDK | Auth | Real-time Hz |
|----------|----------|------|-----|------|-------------|
| Boston Dynamics Spot | gRPC | 443 | bosdyn-client | username/password | 10 |
| Universal Robots | RTDE | 30004 | ur-rtde | none (IP whitelist) | 500 |
| Universal Robots Dashboard | TCP | 29999 | stdlib socket | none | on-demand |
| Fanuc RWS | HTTP REST | 80 | requests | Basic Auth | on-demand |
| KUKA RSI | UDP | 49152 | stdlib socket | none (network) | 250 |
| KUKA EKI | TCP | 54600 | stdlib socket | none (network) | on-demand |
| ABB RWS | HTTP REST | 80 | requests | Digest Auth | on-demand |
| ABB EGM | UDP | 6511 | protobuf | none (network) | 250 |
| Modbus TCP | TCP | 502 | pymodbus | none | on-demand |
| Modbus RTU | Serial | /dev/ttyS0 | pymodbus | none | on-demand |
| BACnet/IP | UDP | 47808 | BAC0 | none | on-demand |
| OPC-UA | TCP | 4840 | asyncua | user/cert | on-demand |
| DJI FlightHub 2 | HTTPS REST | 443 | requests | OAuth2 Bearer | on-demand |
| MQTT | TCP | 1883/8883 | paho-mqtt | user/TLS | async push |
| ROS2 | DDS/UDP | dynamic | rclpy | none | configurable |
| Clearpath ClearCore | HTTP REST | 8080 | requests | none | on-demand |

---

## ARCHITECTURE DIAGRAM

```
Murphy Control Plane
        │
        ▼
Universal Control Plane
  ┌─────────────────────────────────────────────────────────┐
  │  SensorEngine.execute()  ←→  ActuatorEngine.execute()   │
  │         │                           │                    │
  │         └──────────┬────────────────┘                   │
  │                    ▼                                     │
  │             RobotRegistry                                │
  │          (singleton, fleet mgmt)                         │
  └─────────────────────────────────────────────────────────┘
                       │
                       ▼
               AdapterRegistry
            (per-adapter runtimes)
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
    AdapterRuntime  AdapterRuntime  AdapterRuntime
    (8-step valid.) (8-step valid.) (8-step valid.)
          │            │            │
          ▼            ▼            ▼
    SpotAdapter    URAdapter    ModbusAdapter
    (bosdyn SDK)  (ur-rtde)    (pymodbus)
          │            │            │
          ▼            ▼            ▼
    Spot Robot    UR Arm       PLC/VFD
    (gRPC/443)   (RTDE/30004) (TCP/502)

    SafetyHooks (cross-cutting)
    ├── HeartbeatWatchdog (per adapter)
    ├── EmergencyStop (→ Orchestrator /control-signal)
    └── ErrorCodeMapper (→ Murphy Index)

    TelemetryIngestionPipeline (cross-cutting)
    └── TelemetryArtifact → ArtifactGraph → ControlPlane
```

---

## CRITICAL CONSTRAINTS SUMMARY

1. **Adapters are EXECUTION TARGETS only** — they cannot decide, gate, or authorize
2. **DeviceExecutionPacket is the ONLY command pathway** — raw dicts are rejected at `ActuatorEngine`
3. **All commands pass through 8-step AdapterRuntime validation** — signature → replay → target → authority → schema → rate limit → safety → execute
4. **Emergency stop propagates to Orchestrator** via `POST /control-signal` with `mode: "emergency"` — this freezes the entire Murphy System, not just the robot
5. **Mock mode is always available** — no physical hardware required for development or CI
6. **Telemetry flows through ArtifactGraph** — adapters do not push directly to Control Plane
7. **Safety limits are enforced at two layers** — AdapterRuntime AND adapter's own `execute_command()`
8. **Heartbeat timeout triggers fleet-wide freeze** — 15 second default, configurable per adapter