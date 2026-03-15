# Murphy System — Robotics Integration Layer
## Industrial Adapter Technical Reference (Part 2 of 3)

---

## FILE 7: `src/adapter_framework/adapters/industrial/fanuc_adapter.py`

Fanuc robots (CRX collaborative series, LR Mate, M-series, R-series) expose a **REST API** via the **Fanuc Robot Web Server (RWS)** running on the robot controller (R-30iB/R-30iB Plus).

**No external SDK required** — uses `requests` (already installed).

**Base URL:** `http://{controller_ip}/FANUC/` (default port 80)

**Authentication:** HTTP Basic Auth (`admin` / `""` by default, configurable)

**REST endpoints used:**

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/FANUC/variables/$CURRENT_POS` | GET | Current TCP position (X,Y,Z,W,P,R) |
| `/FANUC/variables/$JOINT_POS` | GET | Current joint angles (J1-J9) |
| `/FANUC/variables/$SPEED_OVERRIDE` | GET/POST | Speed override percentage (0-100) |
| `/FANUC/variables/$PROG_STATUS` | GET | Program status (RUNNING/PAUSED/ABORTED) |
| `/FANUC/variables/$ALARM_CODE` | GET | Current alarm code |
| `/FANUC/variables/$ALARM_MSG` | GET | Current alarm message |
| `/FANUC/variables/$PAYLOAD` | GET | Current payload (kg) |
| `/FANUC/variables/$TEMPERATURE` | GET | Controller temperature |
| `/FANUC/programs/{program_name}/start` | POST | Start named TP program |
| `/FANUC/programs/{program_name}/pause` | POST | Pause running program |
| `/FANUC/programs/{program_name}/abort` | POST | Abort running program |
| `/FANUC/variables/$SPEED_OVERRIDE` | POST | Set speed override |
| `/FANUC/variables/{register_name}` | POST | Write numeric/position register |
| `/FANUC/karel/run` | POST | Execute Karel program |
| `/FANUC/ioc/dout/{port}` | POST | Set digital output |
| `/FANUC/ioc/din/{port}` | GET | Read digital input |

**_get_variable(name):** `GET /FANUC/variables/{name}` → parse JSON response `{"value": ...}`

**_set_variable(name, value):** `POST /FANUC/variables/{name}` with `{"value": value}`

**read_telemetry():**
```python
current_pos = _get_variable("$CURRENT_POS")  # {X,Y,Z,W,P,R}
joint_pos = _get_variable("$JOINT_POS")       # {J1..J9}
speed_override = _get_variable("$SPEED_OVERRIDE")
prog_status = _get_variable("$PROG_STATUS")
alarm_code = _get_variable("$ALARM_CODE")
alarm_msg = _get_variable("$ALARM_MSG")
temperature = _get_variable("$TEMPERATURE")
```

**Health logic:**
- `alarm_code != 0` → `error_codes.append(f"fanuc_alarm_{alarm_code}:{alarm_msg}")`, `health = "degraded"`
- `prog_status == "ABORTED"` → `error_codes.append("program_aborted")`

**execute_command() dispatch:**

| Murphy action | Fanuc REST call |
|--------------|----------------|
| `start_program` | `POST /programs/{program_name}/start` |
| `pause_program` | `POST /programs/{program_name}/pause` |
| `abort_program` | `POST /programs/{program_name}/abort` |
| `set_speed_override` | `POST $SPEED_OVERRIDE` with `{"value": percentage}` |
| `write_register` | `POST /variables/{register_name}` with `{"value": value}` |
| `set_digital_output` | `POST /ioc/dout/{port}` with `{"value": state}` |
| `run_karel` | `POST /karel/run` with `{"program": name, "params": params}` |
| `stop` | `POST /programs/current/abort` + `POST $SPEED_OVERRIDE {"value": 0}` |

**emergency_stop():**
1. `POST /programs/current/abort`
2. `POST /variables/$SPEED_OVERRIDE {"value": 0}`
3. `POST /ioc/dout/1 {"value": true}` (assuming DO[1] = E-Stop relay, configurable)

**Manifest:**
```python
AdapterManifest(
    adapter_id=f"fanuc_{controller_ip.replace('.','_')}",
    adapter_type="industrial_robot_arm",
    version="1.0.0",
    capability=AdapterCapability.MIXED,
    safety_limits=SafetyLimits(
        max_velocity=2.0, max_acceleration=5.0,
        max_commands_per_second=2.0, min_command_interval_ms=500.0,
        kill_conditions=["fanuc_alarm","program_aborted","communication_lost"]
    ),
    manufacturer="Fanuc", model=model_name
)
```

---

## FILE 8: `src/adapter_framework/adapters/industrial/kuka_adapter.py`

KUKA robots communicate via two protocols:
- **RSI (Robot Sensor Interface)** — UDP-based real-time data exchange (1ms cycle, port 49152 default)
- **EKI (Ethernet KRL Interface)** — TCP-based KRL program communication (port 54600 default)

**No external SDK** — uses stdlib `socket` only.

**RSI Protocol:**
- KUKA controller sends XML telemetry UDP packets every 4ms (250Hz)
- Murphy sends XML command packets back within the same cycle
- XML format (receive): `<Rob TYPE="KUKA"><RIst X="..." Y="..." Z="..." A="..." B="..." C="..."/><AIPos A1="..." A2="..." A3="..." A4="..." A5="..." A6="..."/><Delay D="..."/><IPOC>...</IPOC></Rob>`
- XML format (send): `<Sen Type="ImFree"><EStr>Murphy</EStr><RKorr X="0" Y="0" Z="0" A="0" B="0" C="0"/><IPOC>{ipoc}</IPOC></Sen>`

**RSI connection (_connect_rsi()):**
1. `self._rsi_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)`
2. `self._rsi_socket.bind(("0.0.0.0", rsi_port))`
3. `self._rsi_socket.settimeout(0.1)`
4. Start RSI receive thread: `threading.Thread(target=self._rsi_receive_loop, daemon=True).start()`

**_rsi_receive_loop():**
```python
while self._rsi_running:
    data, addr = self._rsi_socket.recvfrom(4096)
    xml = ET.fromstring(data.decode())
    self._latest_rsi_state = {
        "cartesian": {k: float(xml.find("RIst").get(k)) for k in "XYZABC"},
        "joints": {f"A{i}": float(xml.find("AIPos").get(f"A{i}")) for i in range(1,7)},
        "ipoc": int(xml.find("IPOC").text)
    }
    self._rsi_addr = addr
```

**EKI Protocol:**
- TCP connection to KRL EKI server running on controller
- Send XML: `<EKI_Data><Command>{action}</Command><Param1>{p1}</Param1></EKI_Data>\n`
- Receive XML response: `<EKI_Data><Status>OK</Status><Result>{result}</Result></EKI_Data>`

**EKI connection (_connect_eki()):**
1. `self._eki_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)`
2. `self._eki_socket.connect((hostname, eki_port))`
3. `self._eki_socket.settimeout(5.0)`

**read_telemetry():** Returns `self._latest_rsi_state` (updated by RSI thread) + EKI query for program status

**execute_command() dispatch:**

| Murphy action | Protocol | Implementation |
|--------------|----------|---------------|
| `rsi_correction` | RSI UDP | Send correction XML with `RKorr` deltas (X,Y,Z,A,B,C) |
| `eki_command` | EKI TCP | Send `<Command>` XML, await `<Status>OK</Status>` |
| `move_ptp` | EKI | `<Command>MOVE_PTP</Command><A1>...</A1>...<A6>...</A6>` |
| `move_lin` | EKI | `<Command>MOVE_LIN</Command><X>...</X>...<C>...</C>` |
| `set_velocity_override` | EKI | `<Command>SET_OV</Command><OV>{percent}</OV>` |
| `set_digital_output` | EKI | `<Command>SET_DO</Command><Port>{n}</Port><Value>{v}</Value>` |
| `stop` | EKI | `<Command>HALT</Command>` |
| `resume` | EKI | `<Command>RESUME</Command>` |

**emergency_stop():**
1. Send RSI zero-correction packet immediately (stops real-time corrections)
2. Send EKI `<Command>HALT</Command>`
3. Close RSI socket to force RSI timeout on controller (controller enters safe state)

**Manifest:**
```python
AdapterManifest(
    adapter_id=f"kuka_{hostname.replace('.','_')}",
    adapter_type="industrial_robot_arm",
    version="1.0.0",
    capability=AdapterCapability.MIXED,
    safety_limits=SafetyLimits(
        max_velocity=2.5, max_acceleration=10.0,
        max_commands_per_second=250.0,  # RSI is 250Hz
        min_command_interval_ms=4.0,    # RSI cycle time
        kill_conditions=["rsi_timeout","eki_error","communication_lost"]
    ),
    manufacturer="KUKA", model=model_name
)
```

---

## FILE 9: `src/adapter_framework/adapters/industrial/abb_adapter.py`

ABB robots (IRB series, YuMi, GoFa, SWIFTI) use two protocols:
- **RWS (Robot Web Services)** — REST API over HTTP (port 80), for state/program control
- **EGM (Externally Guided Motion)** — UDP-based real-time Cartesian/joint guidance (port 6511)

**SDK install:** `pip install requests` (already installed)

**RWS Base URL:** `http://{controller_ip}/rw/`

**RWS Authentication:** HTTP Digest Auth (`Default User` / `robotics`)

**RWS endpoints:**

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/rw/motionsystem` | GET | Robot motion state |
| `/rw/rapid/execution` | GET | RAPID execution state |
| `/rw/rapid/tasks` | GET | RAPID task list |
| `/rw/rapid/tasks/{task}/program/modules/{module}/data/{symbol}` | GET/POST | Read/write RAPID data |
| `/rw/iosystem/signals/{signal}` | GET/POST | Read/write I/O signals |
| `/rw/motionsystem/mechunits/{unit}/jointtarget` | GET | Joint positions |
| `/rw/motionsystem/mechunits/{unit}/robtarget` | GET | TCP position |
| `/rw/rapid/execution;start` | POST | Start RAPID execution |
| `/rw/rapid/execution;stop` | POST | Stop RAPID execution |
| `/rw/rapid/execution;resetpp` | POST | Reset program pointer |
| `/rw/panel/speedratio` | GET/POST | Speed ratio (0-100) |
| `/rw/panel/opmode` | GET | Operating mode (AUTO/MANUAL) |
| `/rw/panel/ctrlstate` | GET | Controller state (INIT/MOTORON/MOTOROFF/GUARDSTOP/EMERGENCYSTOP) |

**EGM Protocol:**
- ABB controller sends `EgmRobot` protobuf messages via UDP
- Murphy sends `EgmSensor` protobuf messages back
- **Protobuf install:** `pip install protobuf abb-egm-msgs` (or generate from `egm.proto`)
- EGM modes: `JOINT` (joint space guidance), `POSE` (Cartesian guidance), `PATH` (path correction)

**EGM connection (_connect_egm()):**
1. `self._egm_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)`
2. `self._egm_socket.bind(("0.0.0.0", egm_port))`
3. Start EGM receive thread

**read_telemetry():**
```python
# RWS: joint + TCP positions
joint_target = GET /rw/motionsystem/mechunits/{unit}/jointtarget
rob_target = GET /rw/motionsystem/mechunits/{unit}/robtarget
ctrl_state = GET /rw/panel/ctrlstate
speed_ratio = GET /rw/panel/speedratio
# Parse XML responses (ABB RWS returns XML)
```

**Health logic:**
- `ctrl_state in ["EMERGENCYSTOP", "EMERGENCYSTOPRESET"]` → `health = "failed"`, `error_codes.append("emergency_stop")`
- `ctrl_state == "GUARDSTOP"` → `health = "degraded"`, `error_codes.append("guard_stop")`
- `ctrl_state == "MOTOROFF"` → `error_codes.append("motors_off")`

**execute_command() dispatch:**

| Murphy action | ABB call |
|--------------|---------|
| `start_rapid` | `POST /rw/rapid/execution;start` |
| `stop_rapid` | `POST /rw/rapid/execution;stop` |
| `reset_pp` | `POST /rw/rapid/execution;resetpp` |
| `set_speed_ratio` | `POST /rw/panel/speedratio` with `{"speed-ratio": value}` |
| `write_rapid_data` | `POST /rw/rapid/tasks/{task}/program/modules/{module}/data/{symbol}` |
| `set_io_signal` | `POST /rw/iosystem/signals/{signal}` with `{"lvalue": value}` |
| `egm_joint_guide` | Send `EgmSensor` protobuf with joint targets via UDP |
| `egm_pose_guide` | Send `EgmSensor` protobuf with Cartesian pose via UDP |
| `stop` | `POST /rw/rapid/execution;stop` + zero EGM |

**emergency_stop():**
1. `POST /rw/rapid/execution;stop`
2. Send zero EGM correction packet
3. `POST /rw/panel/ctrlstate` with `{"ctrl-state": "motoroff"}` (if supported)

---

## FILE 10: `src/adapter_framework/adapters/mobile/dji_adapter.py`

DJI drones (Matrice 300/350 RTK, Matrice 30/30T, Phantom 4 RTX, Mavic 3E) use the **DJI OSDK** (Onboard SDK) for Matrice series and **DJI Mobile SDK** for consumer drones.

**SDK install:** `pip install djiosdk-python` (Matrice) or use DJI FlightHub 2 REST API

**DJI FlightHub 2 REST API** (cloud-based, works for all DJI enterprise drones):
- Base URL: `https://flighthub.dji.com/api/v1/`
- Auth: Bearer token (OAuth2)

**For direct OSDK (Matrice 300/350 on-vehicle):**
- Serial connection to aircraft via OSDK port
- Or network connection via DJI Payload SDK

**Telemetry via FlightHub 2:**

| Field | Endpoint |
|-------|---------|
| GPS position | `/devices/{sn}/telemetry/location` |
| Altitude (MSL + AGL) | `/devices/{sn}/telemetry/altitude` |
| Attitude (roll/pitch/yaw) | `/devices/{sn}/telemetry/attitude` |
| Battery | `/devices/{sn}/telemetry/battery` |
| Flight mode | `/devices/{sn}/telemetry/flight_mode` |
| RC signal | `/devices/{sn}/telemetry/rc_signal` |
| Wind speed | `/devices/{sn}/telemetry/wind` |
| Camera gimbal | `/devices/{sn}/telemetry/gimbal` |

**execute_command() dispatch:**

| Murphy action | DJI call |
|--------------|---------|
| `takeoff` | `POST /devices/{sn}/commands/takeoff` |
| `land` | `POST /devices/{sn}/commands/land` |
| `return_to_home` | `POST /devices/{sn}/commands/rth` |
| `go_to` | `POST /devices/{sn}/commands/goto` with `{lat, lng, altitude, speed}` |
| `hover` | `POST /devices/{sn}/commands/hover` |
| `set_velocity` | `POST /devices/{sn}/commands/velocity` with `{vx, vy, vz, yaw_rate}` |
| `set_gimbal` | `POST /devices/{sn}/commands/gimbal` with `{pitch, roll, yaw}` |
| `take_photo` | `POST /devices/{sn}/commands/camera/photo` |
| `start_recording` | `POST /devices/{sn}/commands/camera/record/start` |
| `stop_recording` | `POST /devices/{sn}/commands/camera/record/stop` |
| `waypoint_mission` | `POST /devices/{sn}/missions/waypoint` with waypoints list |
| `stop` | `POST /devices/{sn}/commands/hover` |

**emergency_stop():**
1. `POST /devices/{sn}/commands/rth` — Return to home (safest option for drones)
2. If RTH fails: `POST /devices/{sn}/commands/land` — Force land immediately
3. `self.is_emergency_stopped = True`

**Safety constraints:**
- max_velocity: 15.0 m/s (Matrice 300 limit in P-mode)
- max_altitude: configurable (default 120.0m AGL — regulatory limit)
- `kill_conditions: ["battery_critical", "gps_lost", "rc_signal_lost", "geofence_breach", "wind_exceeded"]`

**Health logic:**
- `battery.percentage < 20.0` → `error_codes.append("battery_low")`
- `battery.percentage < 10.0` → `error_codes.append("battery_critical")`, `health = "failed"`
- `flight_mode == "EMERGENCY"` → `health = "failed"`
- `rc_signal < -90` dBm → `error_codes.append("rc_signal_weak")`

**Manifest:**
```python
AdapterManifest(
    adapter_id=f"dji_{serial_number.lower()}",
    adapter_type="aerial_drone",
    version="1.0.0",
    capability=AdapterCapability.MIXED,
    safety_limits=SafetyLimits(
        max_velocity=15.0, max_acceleration=5.0,
        max_commands_per_second=2.0, min_command_interval_ms=500.0,
        kill_conditions=["battery_critical","gps_lost","rc_signal_lost",
                         "geofence_breach","wind_exceeded","communication_lost"]
    ),
    manufacturer="DJI", model=model_name, serial_number=serial_number
)
```

---

## FILE 11: `src/adapter_framework/adapters/mobile/clearpath_adapter.py`

Clearpath Robotics platforms (Husky, Jackal, Ridgeback, Dingo, Warthog, Boxer) all run **ROS2** natively. This adapter extends `ROS2Adapter` with Clearpath-specific topics and the **ClearCore** motion controller API.

**Extends:** `ROS2Adapter` from `ros2/ros2_adapter.py`

**Additional Clearpath-specific topics:**

| Topic | Type | Direction |
|-------|------|-----------|
| `/platform/battery_state` | `sensor_msgs/BatteryState` | Subscribe |
| `/platform/imu/data` | `sensor_msgs/Imu` | Subscribe |
| `/platform/front_laser/scan` | `sensor_msgs/LaserScan` | Subscribe |
| `/platform/rear_laser/scan` | `sensor_msgs/LaserScan` | Subscribe |
| `/platform/front_camera/image_raw` | `sensor_msgs/Image` | Subscribe |
| `/platform/cmd_vel` | `geometry_msgs/Twist` | Publish |
| `/platform/e_stop` | `std_msgs/Bool` | Publish |
| `/platform/lights/cmd` | `clearpath_platform_msgs/Lights` | Publish |

**ClearCore REST API** (optional, for direct motor control bypassing ROS2):
- Base URL: `http://{clearcore_ip}:8080/`
- `GET /status` → `{motors: [{id, enabled, position, velocity, torque}], estop: bool}`
- `POST /motor/{id}/velocity` → `{"velocity": float}`
- `POST /motor/{id}/position` → `{"position": float, "velocity": float}`
- `POST /estop` → `{"active": bool}`

**Additional actions beyond ROS2Adapter:**

| Murphy action | Implementation |
|--------------|---------------|
| `set_lights` | Publish `Lights` message to `/platform/lights/cmd` |
| `clearcore_velocity` | `POST /motor/{id}/velocity` to ClearCore REST |
| `clearcore_position` | `POST /motor/{id}/position` to ClearCore REST |
| `clearcore_estop` | `POST /estop {"active": true}` |
| `dock` | Navigate to dock pose + publish dock command |
| `undock` | Publish undock command |

**Manifest:**
```python
AdapterManifest(
    adapter_id=f"clearpath_{robot_name}",
    adapter_type="mobile_robot",
    version="2.0.0",
    capability=AdapterCapability.MIXED,
    safety_limits=SafetyLimits(
        max_velocity=2.0, max_acceleration=2.0,
        max_commands_per_second=10.0, min_command_interval_ms=100.0,
        kill_conditions=["battery_critical","estop_triggered","communication_lost","cliff_detected"]
    ),
    manufacturer="Clearpath Robotics", model=model_name
)
```

---

## FILE 12: `src/adapter_framework/adapters/iot/mqtt_adapter.py`

MQTT v3.1/v5 — the universal IoT protocol. Covers smart sensors, conveyor systems, warehouse robots, AGVs, environmental monitors, and any device publishing to an MQTT broker.

**SDK install:** `pip install paho-mqtt`

**MQTTTopicMap** — configurable topic mapping:
```python
class MQTTTopicMap:
    telemetry_topics: Dict[str, str]  # {murphy_name: "factory/line1/sensor/temperature"}
    command_topics: Dict[str, str]    # {murphy_name: "factory/line1/actuator/valve/set"}
    status_topic: str                 # "factory/line1/status"
    emergency_stop_topic: str         # "factory/line1/estop"
    heartbeat_topic: str              # "factory/line1/heartbeat"
    qos: int = 1                      # 0=at most once, 1=at least once, 2=exactly once
    retain: bool = False
```

**_connect():**
1. `self._client = mqtt.Client(client_id=f"murphy_{adapter_id}", protocol=mqtt.MQTTv5)`
2. If username/password: `client.username_pw_set(username, password)`
3. If TLS: `client.tls_set(ca_certs, certfile, keyfile)`
4. `client.on_connect = self._on_connect`
5. `client.on_message = self._on_message`
6. `client.connect(broker_host, broker_port, keepalive=60)`
7. `client.loop_start()` — background thread

**_on_connect():** Subscribe to all `telemetry_topics.values()` + `status_topic` + `heartbeat_topic`

**_on_message():** Parse JSON payload, update `self._latest_values[topic]` under `self._lock`

**read_telemetry():**
```python
with self._lock:
    for name, topic in self.topic_map.telemetry_topics.items():
        state_vector[name] = self._latest_values.get(topic)
```

**execute_command() dispatch:**

| Murphy action | MQTT call |
|--------------|----------|
| `publish` | `client.publish(topic, json.dumps(payload), qos=qos, retain=retain)` |
| `publish_command` | `client.publish(command_topics[command_name], json.dumps(value), qos=qos)` |
| `publish_raw` | `client.publish(topic, payload_str, qos=qos)` |
| `subscribe` | `client.subscribe(topic, qos=qos)` |
| `stop` | Publish `{"command": "stop"}` to all command_topics |

**emergency_stop():**
1. `client.publish(emergency_stop_topic, json.dumps({"estop": True, "source": "murphy"}), qos=2)`
2. Publish `{"command": "stop"}` to all command_topics with QoS 2
3. `self.is_emergency_stopped = True`

**Payload format:** All published payloads are JSON: `{"value": ..., "timestamp": float, "source": "murphy", "nonce": str}`

**Manifest:**
```python
AdapterManifest(
    adapter_id=f"mqtt_{broker_host.replace('.','_')}_{device_id}",
    adapter_type="iot_device",
    version="1.0.0",
    capability=AdapterCapability.MIXED,
    safety_limits=SafetyLimits(
        max_commands_per_second=10.0, min_command_interval_ms=100.0,
        kill_conditions=["broker_disconnected","communication_lost"]
    ),
    manufacturer=manufacturer, model=model
)
```

---

## FILE 13: `src/adapter_framework/protocols/modbus_client.py`

Thin wrapper around `pymodbus` that handles reconnection, register caching, and Murphy error mapping.

```python
class MurphyModbusClient:
    """
    Reconnecting Modbus client with Murphy error integration.
    
    Features:
    - Auto-reconnect on connection loss
    - Register read caching (configurable TTL)
    - Exception code → Murphy error code mapping
    - Coil/register batch read optimization
    """
    
    EXCEPTION_CODE_MAP = {
        1: "illegal_function",
        2: "illegal_data_address", 
        3: "illegal_data_value",
        4: "server_device_failure",
        5: "acknowledge",
        6: "server_device_busy",
        8: "memory_parity_error",
        10: "gateway_path_unavailable",
        11: "gateway_target_device_failed"
    }
    
    def __init__(self, host: str, port: int = 502, timeout: float = 3.0,
                 retries: int = 3, reconnect_delay: float = 5.0,
                 cache_ttl_seconds: float = 0.1):
        ...
    
    def read_holding_registers(self, address: int, count: int, unit: int = 1) -> List[int]:
        """Read holding registers with retry and cache."""
        ...
    
    def read_input_registers(self, address: int, count: int, unit: int = 1) -> List[int]:
        """Read input registers with retry and cache."""
        ...
    
    def read_coils(self, address: int, count: int, unit: int = 1) -> List[bool]:
        """Read coils with retry."""
        ...
    
    def read_discrete_inputs(self, address: int, count: int, unit: int = 1) -> List[bool]:
        """Read discrete inputs with retry."""
        ...
    
    def write_register(self, address: int, value: int, unit: int = 1) -> bool:
        """Write single holding register."""
        ...
    
    def write_registers(self, address: int, values: List[int], unit: int = 1) -> bool:
        """Write multiple holding registers."""
        ...
    
    def write_coil(self, address: int, value: bool, unit: int = 1) -> bool:
        """Write single coil."""
        ...
    
    def write_coils(self, address: int, values: List[bool], unit: int = 1) -> bool:
        """Write multiple coils."""
        ...
    
    def _ensure_connected(self) -> bool:
        """Ensure connection is active, reconnect if needed."""
        ...
    
    def _map_exception(self, exception_code: int) -> str:
        """Map Modbus exception code to Murphy error string."""
        return self.EXCEPTION_CODE_MAP.get(exception_code, f"modbus_exception_{exception_code}")
```

---

## FILE 14: `src/adapter_framework/protocols/bacnet_client.py`

Thin wrapper around `BAC0` with Murphy error integration.

```python
class MurphyBACnetClient:
    """
    BAC0 wrapper with Murphy error integration.
    
    Features:
    - Device discovery (Who-Is / I-Am)
    - Point caching with configurable TTL
    - Priority array management
    - COV (Change of Value) subscriptions
    """
    
    OBJECT_TYPE_MAP = {
        "analogInput": "AI", "analogOutput": "AO", "analogValue": "AV",
        "binaryInput": "BI", "binaryOutput": "BO", "binaryValue": "BV",
        "multiStateInput": "MSI", "multiStateOutput": "MSO", "multiStateValue": "MSV"
    }
    
    def __init__(self, local_ip: str, local_port: int = 47808):
        ...
    
    def connect_device(self, device_address: str, device_instance: int) -> bool:
        """Connect to BACnet device."""
        ...
    
    def read_point(self, device_instance: int, object_type: str, 
                   instance: int, property_id: str = "presentValue") -> Any:
        """Read BACnet object property."""
        ...
    
    def write_point(self, device_instance: int, object_type: str,
                    instance: int, value: Any, priority: int = 8) -> bool:
        """Write BACnet object property at given priority."""
        ...
    
    def release_point(self, device_instance: int, object_type: str,
                      instance: int, priority: int = 8) -> bool:
        """Release BACnet output at given priority (write NULL)."""
        ...
    
    def discover_devices(self, timeout: float = 5.0) -> List[Dict]:
        """Discover BACnet devices on network (Who-Is broadcast)."""
        ...
    
    def subscribe_cov(self, device_instance: int, object_type: str,
                      instance: int, callback: Callable) -> bool:
        """Subscribe to Change of Value notifications."""
        ...
```

---

## FILE 15: `src/adapter_framework/protocols/opcua_client.py`

Thin wrapper around `asyncua` (sync mode) with Murphy error integration.

```python
class MurphyOPCUAClient:
    """
    asyncua sync wrapper with Murphy error integration.
    
    Features:
    - Certificate-based security (Basic256Sha256)
    - Node browsing and discovery
    - Subscription-based value monitoring
    - Batch read/write optimization
    """
    
    SECURITY_POLICIES = {
        "none": None,
        "basic256sha256_sign": "Basic256Sha256,Sign",
        "basic256sha256_sign_encrypt": "Basic256Sha256,SignAndEncrypt"
    }
    
    def __init__(self, url: str, username: str = None, password: str = None,
                 security_policy: str = "none", cert_path: str = None,
                 key_path: str = None, timeout: float = 10.0):
        ...
    
    def connect(self) -> bool:
        """Connect to OPC-UA server."""
        ...
    
    def disconnect(self):
        """Disconnect from OPC-UA server."""
        ...
    
    def read_node(self, node_id: str) -> Any:
        """Read node value by NodeId string."""
        ...
    
    def read_nodes(self, node_ids: List[str]) -> Dict[str, Any]:
        """Batch read multiple nodes."""
        ...
    
    def write_node(self, node_id: str, value: Any, variant_type: str = None) -> bool:
        """Write node value."""
        ...
    
    def write_nodes(self, writes: Dict[str, Any]) -> Dict[str, bool]:
        """Batch write multiple nodes."""
        ...
    
    def call_method(self, object_node_id: str, method_node_id: str, *args) -> Any:
        """Call OPC-UA method."""
        ...
    
    def browse(self, node_id: str = "i=85") -> List[Dict]:
        """Browse OPC-UA node tree."""
        ...
    
    def subscribe(self, node_ids: List[str], callback: Callable,
                  interval_ms: int = 100) -> int:
        """Subscribe to node value changes. Returns subscription handle."""
        ...
```

---

## FILE 16: `src/adapter_framework/protocols/ros2_bridge.py`

ROS2 bridge utilities — handles ROS2 availability detection, message type imports, and action client management.

```python
class ROS2Bridge:
    """
    ROS2 availability bridge.
    
    Handles graceful degradation when ROS2 is not available.
    Provides type-safe message construction helpers.
    """
    
    @staticmethod
    def is_available() -> bool:
        """Check if ROS2 (rclpy) is importable and initialized."""
        try:
            import rclpy
            return True
        except ImportError:
            return False
    
    @staticmethod
    def make_twist(vx: float = 0.0, vy: float = 0.0, vz: float = 0.0,
                   wx: float = 0.0, wy: float = 0.0, wz: float = 0.0) -> Any:
        """Create geometry_msgs/Twist message."""
        ...
    
    @staticmethod
    def make_pose_stamped(x: float, y: float, z: float,
                          qx: float, qy: float, qz: float, qw: float,
                          frame_id: str = "map") -> Any:
        """Create geometry_msgs/PoseStamped message."""
        ...
    
    @staticmethod
    def make_joint_trajectory(joint_names: List[str],
                               positions: List[float],
                               time_from_start_sec: float = 2.0) -> Any:
        """Create trajectory_msgs/JointTrajectory message."""
        ...
    
    @staticmethod
    def euler_to_quaternion(roll: float, pitch: float, yaw: float) -> Tuple[float,float,float,float]:
        """Convert Euler angles to quaternion (x,y,z,w)."""
        ...
    
    @staticmethod
    def quaternion_to_euler(qx: float, qy: float, qz: float, qw: float) -> Tuple[float,float,float]:
        """Convert quaternion to Euler angles (roll,pitch,yaw)."""
        ...
```