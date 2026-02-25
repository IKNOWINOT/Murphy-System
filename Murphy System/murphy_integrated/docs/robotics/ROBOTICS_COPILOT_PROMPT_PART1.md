# Murphy System — Robotics Integration Layer
## GitHub Copilot Implementation Prompt (Part 1 of 3)

---

## MISSION STATEMENT

You are implementing the **Murphy System Robotics Integration Layer** — a production-grade, safety-enforced bridge between the Murphy AI Control Plane and every major class of physical robot, industrial controller, IoT device, and autonomous platform in commercial use today.

The adapter framework skeleton already exists and is fully operational. Your job is to implement **real protocol drivers** for the major robot platforms, wire them into the existing `AdapterAPI` contract, and expose them through the `SensorEngine` / `ActuatorEngine` stubs in `universal_control_plane.py`. Every adapter you write must pass through the existing 8-step `AdapterRuntime` validation chain. No adapter may bypass `DeviceExecutionPacket`. No adapter may make autonomous decisions.

---

## EXISTING INFRASTRUCTURE — DO NOT MODIFY THESE FILES

| File | What it provides |
|------|-----------------|
| `src/adapter_framework/adapter_contract.py` | `AdapterAPI` (abstract base), `AdapterManifest`, `SafetyLimits`, `TelemetrySchema`, `CommandSchema`, `AdapterCapability` |
| `src/adapter_framework/adapter_runtime.py` | `AdapterRuntime` (8-step validation), `AdapterRegistry` |
| `src/adapter_framework/execution_packet_extension.py` | `DeviceExecutionPacket` (the ONLY way to send commands to devices) |
| `src/adapter_framework/safety_hooks.py` | `HeartbeatWatchdog`, `EmergencyStop`, `ErrorCodeMapper`, `SafetyHooks` |
| `src/adapter_framework/telemetry_artifact.py` | `TelemetryArtifact`, `TelemetryIngestionPipeline` |
| `src/adapter_framework/adapters/mock_adapter.py` | Reference implementation — study this pattern before writing any adapter |
| `src/adapter_framework/adapters/http_adapter.py` | Generic HTTP adapter — reuse for REST-based robots |
| `universal_control_plane.py` | `SensorEngine.execute()` and `ActuatorEngine.execute()` — both are TODO stubs needing real dispatch |

**The `AdapterAPI` contract requires every adapter to implement exactly these five methods:**

```python
def get_manifest(self) -> AdapterManifest
def read_telemetry(self) -> Dict          # MUST NOT modify device state
def execute_command(self, execution_packet: DeviceExecutionPacket) -> Dict
def emergency_stop(self) -> bool          # MUST halt all motion immediately
def heartbeat(self) -> Dict
```

**The `DeviceExecutionPacket` command dict always has this shape:**

```python
{
    "action": str,           # Must be in adapter's CommandSchema.allowed_actions
    "parameters": Dict,      # Validated against CommandSchema.parameter_schemas
    "timestamp": float,
    "nonce": str
}
```

**Telemetry dict returned by `read_telemetry()` MUST always contain:**

```python
{
    "timestamp": float,
    "device_id": str,
    "state_vector": Dict,    # Device-specific state
    "error_codes": List[str],
    "health": str,           # "healthy" | "degraded" | "failed"
    "checksum": str,         # SHA-256 of json.dumps(state_vector, sort_keys=True)
    "sequence_number": int
}
```

---

## PLATFORM COVERAGE MATRIX

| Platform | Protocol | Adapter File | SDK/Library |
|----------|----------|-------------|-------------|
| Boston Dynamics Spot | Spot SDK (gRPC) | `boston_dynamics/spot_adapter.py` | `bosdyn-client` |
| Universal Robots UR3/5/10/16/20/30 | RTDE + Dashboard | `universal_robots/ur_adapter.py` | `ur-rtde` |
| Any ROS2 robot (Nav2, MoveIt2) | ROS2 topics/actions | `ros2/ros2_adapter.py` | `rclpy` |
| Siemens/Allen-Bradley/Schneider PLCs | Modbus TCP/RTU | `industrial/modbus_adapter.py` | `pymodbus` |
| Johnson Controls/Honeywell HVAC | BACnet/IP | `industrial/bacnet_adapter.py` | `BAC0` |
| Siemens S7-1500/Beckhoff/B&R | OPC-UA | `industrial/opcua_adapter.py` | `asyncua` |
| Fanuc CRX/LR Mate/M-series | FANUC Robot Web Server REST | `industrial/fanuc_adapter.py` | `requests` |
| KUKA KR/iiwa/KMR | RSI (UDP) + EKI (TCP) | `industrial/kuka_adapter.py` | stdlib sockets |
| ABB IRB/YuMi/GoFa | ABB RWS REST + EGM | `industrial/abb_adapter.py` | `requests` + UDP |
| DJI Matrice/Phantom/Mavic | DJI OSDK / MSDK | `mobile/dji_adapter.py` | `djiosdk-core` |
| Clearpath Husky/Jackal/Ridgeback | ROS2 + ClearCore | `mobile/clearpath_adapter.py` | `rclpy` |
| Any MQTT IoT device | MQTT v3.1/v5 | `iot/mqtt_adapter.py` | `paho-mqtt` |

---

## DIRECTORY STRUCTURE TO CREATE

```
src/adapter_framework/
├── adapters/
│   ├── boston_dynamics/
│   │   ├── __init__.py
│   │   └── spot_adapter.py          NEW
│   ├── universal_robots/
│   │   ├── __init__.py
│   │   └── ur_adapter.py            NEW
│   ├── ros2/
│   │   ├── __init__.py
│   │   └── ros2_adapter.py          NEW
│   ├── industrial/
│   │   ├── __init__.py
│   │   ├── modbus_adapter.py        NEW
│   │   ├── bacnet_adapter.py        NEW
│   │   ├── opcua_adapter.py         NEW
│   │   ├── fanuc_adapter.py         NEW
│   │   ├── kuka_adapter.py          NEW
│   │   └── abb_adapter.py           NEW
│   ├── mobile/
│   │   ├── __init__.py
│   │   ├── dji_adapter.py           NEW
│   │   └── clearpath_adapter.py     NEW
│   └── iot/
│       ├── __init__.py
│       └── mqtt_adapter.py          NEW
├── protocols/
│   ├── __init__.py
│   ├── modbus_client.py             NEW
│   ├── bacnet_client.py             NEW
│   ├── opcua_client.py              NEW
│   └── ros2_bridge.py               NEW
└── robot_registry.py                NEW
```

Also modify:
- `universal_control_plane.py` — wire `SensorEngine.execute()` and `ActuatorEngine.execute()` to `AdapterRegistry`
- `src/adapter_framework/__init__.py` — add new exports
- `src/adapter_framework/adapters/__init__.py` — add new exports

---

## FILE 1: `src/adapter_framework/adapters/boston_dynamics/spot_adapter.py`

Boston Dynamics Spot communicates via the **Spot SDK** (`bosdyn-client`). Spot exposes services over gRPC.

**SDK install:** `pip install bosdyn-client bosdyn-mission bosdyn-choreography-client`

**Spot services used:**
- `RobotStateClient` — read_telemetry()
- `RobotCommandClient` — execute_command() (mobility + arm)
- `EstopClient` — emergency_stop()
- `PowerClient` — power on/off
- `LeaseClient` — exclusive control lease management

**Safety constraints:**
- max_velocity: 1.6 m/s (Spot hardware limit)
- max_angular_velocity: 1.0 rad/s
- estop MUST be configured before any motion command
- lease MUST be acquired before any command

**Connection sequence (_connect()):**
1. `sdk = bosdyn.client.create_standard_sdk("MurphyRoboticsAdapter")`
2. `robot = sdk.create_robot(hostname)`
3. `bosdyn.client.util.authenticate(robot, username, password)`
4. `robot.time_sync.wait_for_sync()`
5. Initialize all service clients (state, command, estop, power, lease)
6. Configure E-Stop endpoint + start `EstopKeepAlive`
7. Acquire lease + start `LeaseKeepAlive`

**emergency_stop():**
- `EstopKeepAlive.stop()` — halts keepalive
- `EstopEndpoint.stop()` — cuts motor power immediately
- `self.is_emergency_stopped = True`

**Command dispatch (_dispatch_command()):**

| Murphy action | Spot SDK call |
|--------------|---------------|
| `stand` | `RobotCommandBuilder.synchro_stand_command()` |
| `sit` | `RobotCommandBuilder.synchro_sit_command()` |
| `stop` | `RobotCommandBuilder.stop_command()` |
| `self_right` | `RobotCommandBuilder.selfright_command()` |
| `walk_velocity` | `RobotCommandBuilder.synchro_velocity_command(vx, vy, vrot)` |
| `walk_to` | `RobotCommandBuilder.synchro_se2_trajectory_point_command(x, y, heading, "odom")` |
| `rotate_body` | `RobotCommandBuilder.synchro_stand_command(footprint_R_body=EulerZXY(yaw,roll,pitch))` |
| `set_body_height` | `RobotCommandBuilder.synchro_stand_command(body_height=delta)` |
| `arm_stow` | `RobotCommandBuilder.arm_stow_command()` |
| `arm_carry` | `RobotCommandBuilder.arm_carry_command()` |
| `gripper_open` | `RobotCommandBuilder.claw_gripper_open_command()` |
| `gripper_close` | `RobotCommandBuilder.claw_gripper_close_command(maximum_torque=force*5.0)` |
| `power_on` | `PowerClient.power_on(timeout_sec=20)` |
| `power_off` | `PowerClient.safe_power_off(timeout_sec=20)` |
| `arm_reach` | `RobotCommandBuilder.arm_pose_command(x,y,z,qw,qx,qy,qz, BODY_FRAME_NAME)` |

**Telemetry fields (from RobotStateClient.get_robot_state()):**

| Field | Source |
|-------|--------|
| `body_pose` | `kinematic_state.transforms_snapshot` (position + quaternion) |
| `velocity` | `kinematic_state.velocity_of_body_in_odom` (linear + angular) |
| `foot_states` | `state.foot_state` (4 feet: fl, fr, hl, hr — contact + position) |
| `battery_percentage` | `state.battery_states[0].charge_percentage.value` |
| `estop_state` | `"ESTOPPED"` if `state.estop_states[0].state==1` else `"NOT_ESTOPPED"` |
| `power_state` | `{0:"UNKNOWN",1:"OFF",2:"ON",3:"POWERING_ON",4:"POWERING_OFF"}` |
| `joint_states` | `kinematic_state.joint_states` (12 joints: position, velocity, load) |

**Manifest:**
```python
AdapterManifest(
    adapter_id=f"spot_{serial_number.lower().replace('-','_')}",
    adapter_type="quadruped_robot",
    version="3.3.0",
    capability=AdapterCapability.MIXED,
    safety_limits=SafetyLimits(
        max_velocity=1.6, max_acceleration=2.0,
        max_commands_per_second=5.0, min_command_interval_ms=200.0,
        kill_conditions=["estop_triggered","battery_critical","communication_lost",
                         "fall_detected","motor_fault","temperature_exceeded"]
    ),
    manufacturer="Boston Dynamics", model="Spot", serial_number=serial_number
)
```

**Allowed actions:** `stand, sit, walk_to, walk_velocity, rotate_body, set_body_height, arm_reach, arm_stow, arm_carry, gripper_open, gripper_close, self_right, battery_change_pose, power_on, power_off, stop`

**Preconditions for motion actions:** `["standing", "powered_on", "estop_clear", "lease_held"]`

**Mock fallback:** If `SPOT_SDK_AVAILABLE=False` or `not self._connected`, return `_mock_telemetry()` / `_mock_execute()` with realistic placeholder values.

---

## FILE 2: `src/adapter_framework/adapters/universal_robots/ur_adapter.py`

Universal Robots communicate via **RTDE** (port 30004) for telemetry and **Dashboard Server** (port 29999) for mode control.

**SDK install:** `pip install ur-rtde`

**Model safety limits:**

| Model | max_payload_kg | max_reach_mm | max_tcp_speed |
|-------|---------------|-------------|---------------|
| UR3/UR3e | 3.0 | 500 | 1.0 m/s |
| UR5/UR5e | 5.0 | 850 | 1.0 m/s |
| UR10/UR10e | 10.0 | 1300 | 1.0 m/s |
| UR16/UR16e | 16.0 | 900 | 1.0 m/s |
| UR20 | 20.0 | 1750 | 2.0 m/s |
| UR30 | 30.0 | 1300 | 2.0 m/s |

**_connect():**
1. `self._rtde_receive = rtde_receive.RTDEReceiveInterface(hostname)`
2. `self._rtde_control = rtde_control.RTDEControlInterface(hostname)`
3. Connect Dashboard Server socket to port 29999

**RTDE variables read in read_telemetry():**

| Variable | Description |
|----------|-------------|
| `getActualQ()` | joint positions (6 floats, radians) |
| `getActualQd()` | joint velocities (6 floats, rad/s) |
| `getActualCurrents()` | joint currents (6 floats, amps) |
| `getActualTCPPose()` | TCP pose [x,y,z,rx,ry,rz] |
| `getActualTCPSpeed()` | TCP speed [vx,vy,vz,wx,wy,wz] |
| `getRobotMode()` | int (-1..8) |
| `getSafetyMode()` | int (1..11) |
| `getActualDigitalInputBits()` | bitmask (18 bits) |
| `getActualDigitalOutputBits()` | bitmask (18 bits) |
| `getStandardAnalogInput0/1()` | float |
| `getJointTemperatures()` | 6 floats, Celsius |

**robot_mode_map:** `-1:NO_CONTROLLER, 0:DISCONNECTED, 1:CONFIRM_SAFETY, 2:BOOTING, 3:POWER_OFF, 4:POWER_ON, 5:IDLE, 6:BACKDRIVE, 7:RUNNING, 8:UPDATING_FIRMWARE`

**safety_mode_map:** `1:NORMAL, 2:REDUCED, 3:PROTECTIVE_STOP, 4:RECOVERY, 5:SAFEGUARD_STOP, 6:SYSTEM_EMERGENCY_STOP, 7:ROBOT_EMERGENCY_STOP, 8:VIOLATION, 9:FAULT`

**RTDE control methods (execute_command()):**

| Murphy action | RTDE call |
|--------------|-----------|
| `moveJ` | `c.moveJ(q, speed, acceleration, asynchronous)` |
| `moveL` | `c.moveL(pose, speed, acceleration, asynchronous)` |
| `moveP` | `c.moveP(pose, speed, acceleration, blend)` |
| `speedJ` | `c.speedJ(qd, acceleration, time)` |
| `speedL` | `c.speedL(xd, acceleration, time)` |
| `stopJ` | `c.stopJ(deceleration)` |
| `stopL` | `c.stopL(deceleration)` |
| `set_digital_output` | `c.setDigitalOutput(output_id, value)` |
| `set_analog_output` | `c.setAnalogOutput(output_id, value)` |
| `set_payload` | `c.setPayload(mass, cog)` |
| `freedrive_mode` | `c.freedriveMode()` |
| `end_freedrive_mode` | `c.endFreedriveMode()` |
| `zero_ftsensor` | `c.zeroFtSensor()` |
| `protective_stop_reset` | `c.reuploadScript()` |
| `power_on` | dashboard: `"power on"` then `"brake release"` |
| `power_off` | dashboard: `"power off"` |
| `brake_release` | dashboard: `"brake release"` |

**emergency_stop():**
1. `self._rtde_control.stopJ(10.0)` — max deceleration
2. `self._dashboard_send("stop")`
3. `self.is_emergency_stopped = True`

---

## FILE 3: `src/adapter_framework/adapters/ros2/ros2_adapter.py`

ROS2 bridges Murphy to any ROS2-enabled robot (Nav2, MoveIt2, Clearpath, Fetch, PAL TIAGo, Franka, etc.).

**SDK install:** `pip install rclpy` (requires ROS2 Humble/Iron/Jazzy sourced in environment)

**ROS2NodeConfig class** — configurable topic/service/action names with defaults:
```python
class ROS2NodeConfig:
    joint_states_topic: str = "/joint_states"
    odom_topic: str = "/odom"
    battery_topic: str = "/battery_state"
    diagnostics_topic: str = "/diagnostics"
    cmd_vel_pub_topic: str = "/cmd_vel"
    emergency_stop_topic: str = "/emergency_stop"
    navigate_to_pose_action: str = "/navigate_to_pose"
    move_group_action: str = "/move_action"
    clear_costmaps_service: str = "/clear_all_costmaps"
```

**_init_ros2() sequence:**
1. `rclpy.init()`
2. `self._node = rclpy.create_node(f"murphy_{robot_name}")`
3. Create subscribers: `/joint_states` (JointState), `/odom` (Odometry), `/battery_state` (BatteryState), `/diagnostics` (DiagnosticArray)
4. Create publishers: `/cmd_vel` (Twist), `/emergency_stop` (Bool)
5. Start spin thread: `threading.Thread(target=lambda: rclpy.spin(self._node), daemon=True).start()`

**Subscriber callbacks** update thread-safe cached dicts under `self._telemetry_lock`:
- `_joint_states_callback` → `self._latest_joint_states = {names, positions, velocities, efforts, timestamp}`
- `_odom_callback` → `self._latest_odom = {position:{x,y,z}, orientation:{x,y,z,w}, linear_velocity, angular_velocity}`
- `_battery_callback` → `self._latest_battery = {percentage, voltage, current, temperature}`
- `_diagnostics_callback` → `self._latest_diagnostics = [{name, level, message}]`

**Command dispatch:**

| Murphy action | ROS2 call |
|--------------|-----------|
| `cmd_vel` | Publish `Twist` to `/cmd_vel`; if `duration_seconds>0`, sleep then publish zero |
| `stop` | Publish zero `Twist` |
| `emergency_stop` | Publish zero `Twist` + publish `True` to `/emergency_stop` |
| `navigate_to_pose` | Send `NavigateToPose` action goal (nav2_msgs) |
| `cancel_navigation` | Cancel active navigation goal |
| `clear_costmaps` | Call `/clear_all_costmaps` service |
| `move_joints` | `moveit_py`: set joint goal + plan + execute |
| `move_cartesian` | `moveit_py`: set pose goal + plan + execute |

**Health determination in read_telemetry():**
- Any diagnostic with `level >= 2` (ERROR) → `error_codes.append(f"diagnostic_error:{name}")`, `health = "degraded"`
- `battery.percentage < 10.0` → `error_codes.append("battery_critical")`, `health = "degraded"`

---

## FILE 4: `src/adapter_framework/adapters/industrial/modbus_adapter.py`

Modbus TCP/RTU — most widely deployed industrial protocol. Used by PLCs, conveyor systems, CNC machines, VFDs.

**SDK install:** `pip install pymodbus`

**ModbusRegisterMap** — configurable register addresses:
```python
class ModbusRegisterMap:
    status_register: int = 0        # Holding reg: device status word
    error_register: int = 1         # Holding reg: error code
    temperature_register: int = 2   # Holding reg: temperature (x0.1 degC)
    analog_input_start: int = 100   # Input regs: analog inputs start
    analog_input_count: int = 8
    digital_input_start: int = 0    # Discrete inputs start
    digital_input_count: int = 16
    command_register: int = 10      # Holding reg: command word
    setpoint_register: int = 11     # Holding reg: setpoint
    digital_output_start: int = 0   # Coils start
    digital_output_count: int = 16
    unit_id: int = 1
```

**_connect():**
- TCP: `ModbusTcpClient(host=host, port=port, timeout=timeout)`
- RTU: `ModbusSerialClient(method="rtu", port=serial_port, baudrate=baudrate, timeout=timeout)`
- Both: `self._connected = self._client.connect()`

**read_telemetry():**
1. `read_holding_registers(status_register, 3, slave=unit_id)` → status_word, error_code, temperature (×0.1)
2. `read_input_registers(analog_input_start, analog_input_count, slave=unit_id)` → analog_inputs list
3. `read_discrete_inputs(digital_input_start, digital_input_count, slave=unit_id)` → digital_inputs list

**Health logic:**
- `error_code != 0` → `error_codes.append(f"device_error_{error_code}")`, `health = "degraded"`
- `temperature > max_temperature` → `error_codes.append("temperature_exceeded")`
- `status_word & 0x8000` (bit 15 = fault) → `health = "failed"`

**execute_command() dispatch:**

| Action | Modbus call |
|--------|-------------|
| `write_coil` | `client.write_coil(address, value, slave=unit_id)` |
| `write_coils` | `client.write_coils(address, values, slave=unit_id)` |
| `write_register` | `client.write_register(address, value, slave=unit_id)` |
| `write_registers` | `client.write_registers(address, values, slave=unit_id)` |
| `write_command_word` | `client.write_register(command_register, command, slave=unit_id)` |
| `set_setpoint` | `client.write_register(setpoint_register, value, slave=unit_id)` |
| `read_holding_registers` | `client.read_holding_registers(address, count, slave=unit_id)` |
| `read_input_registers` | `client.read_input_registers(address, count, slave=unit_id)` |
| `stop` | `client.write_register(command_register, 0, slave=unit_id)` |

**emergency_stop():**
1. `client.write_coils(digital_output_start, [False]*digital_output_count, slave=unit_id)`
2. `client.write_register(command_register, 0xFFFF, slave=unit_id)`

---

## FILE 5: `src/adapter_framework/adapters/industrial/bacnet_adapter.py`

BACnet/IP — dominant protocol for building automation (HVAC, elevators, fire suppression, lighting).

**SDK install:** `pip install BAC0`

**BACnetPointMap** — maps Murphy names to BACnet object identifiers:
```python
class BACnetPointMap:
    points: Dict[str, Tuple[str, int]]
    # Format: {murphy_name: (object_type_str, instance_number)}
    # object_type_str: "analogInput", "analogOutput", "analogValue",
    #                  "binaryInput", "binaryOutput", "binaryValue"
    # Default map covers generic HVAC controller with 20 points
```

**_connect():**
1. `ip_str = f"{local_ip}:{port}" if local_ip else str(port)`
2. `self._bacnet = BAC0.lite(ip=ip_str)`
3. `self._device = BAC0.device(f"{device_address}:{port}", device_instance, self._bacnet)`

**read_telemetry():**
```python
for point_name, (obj_type, instance) in self.point_map.points.items():
    bacnet_id = f"{obj_type}:{instance}"
    value = self._device[bacnet_id].lastValue
    state_vector[point_name] = float(value)
```
Check `fire_alarm` binaryInput → `error_codes.append("fire_alarm")`, `health = "failed"`

**execute_command() dispatch:**

| Action | BAC0 call |
|--------|-----------|
| `write_point` | `self._device[bacnet_id].write(value, priority=priority)` |
| `write_points` | Loop write_point for each entry in `parameters["points"]` |
| `release_point` | `self._device[bacnet_id].release(priority)` |
| `read_point` | `return self._device[bacnet_id].lastValue` |
| `stop` | Release all Output points at priority 8 |

**emergency_stop():** Release all Output points at priority 1 (highest BACnet priority = Manual-Life Safety)

**BACnet write priority levels:** 1=Manual-Life Safety (highest), 8=Manual Operator (default for Murphy), 16=lowest

---

## FILE 6: `src/adapter_framework/adapters/industrial/opcua_adapter.py`

OPC-UA — Industry 4.0 standard. Used by Siemens S7-1500, Beckhoff TwinCAT, B&R, Bosch Rexroth, KUKA OfficeLite, ABB IRC5/OmniCore, Fanuc CNC.

**SDK install:** `pip install asyncua`

**OPCUANodeMap** — maps Murphy names to OPC-UA NodeId strings:
```python
class OPCUANodeMap:
    read_nodes: Dict[str, str]   # {murphy_name: "ns=2;s=PLC1.DB1.Temperature"}
    write_nodes: Dict[str, str]  # {murphy_name: "ns=2;s=PLC1.DB1.Setpoint"}
    method_nodes: Dict[str, tuple]  # {murphy_name: (object_node_id, method_node_id)}
    emergency_stop_node: str     # NodeId to write True for E-Stop
```

**_connect():**
1. `self._client = SyncClient(url)` (e.g. `"opc.tcp://192.168.1.100:4840"`)
2. If username/password: `client.set_user(username); client.set_password(password)`
3. If security_string: `client.set_security_string(security_string)`
4. `client.connect()`

**read_telemetry():**
```python
for name, node_id in self.node_map.read_nodes.items():
    node = self._client.get_node(node_id)
    value = node.read_value()
    state_vector[name] = value
```

**execute_command() dispatch:**

| Action | asyncua call |
|--------|-------------|
| `write_node` | `client.get_node(node_id).write_value(value)` |
| `write_nodes` | Loop write_node for each entry |
| `read_node` | `return client.get_node(node_id).read_value()` |
| `call_method` | `node.call_method(method_id, *args)` |
| `stop` | Write 0/False to all write_nodes |

**emergency_stop():** Write `True` to `emergency_stop_node`, write `0` to all write_nodes

**Security modes:** `None` (dev), `Basic256Sha256,SignAndEncrypt,cert.pem,key.pem` (production)