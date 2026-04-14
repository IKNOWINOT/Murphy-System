"""
Comprehensive tests for the Murphy System Robotics Integration Layer.
"""

import threading
from datetime import datetime, timezone

import pytest

from robotics.robotics_models import (
    ActuatorCommand,
    ActuatorResult,
    ConnectionConfig,
    RobotConfig,
    RobotStatus,
    RobotType,
    SensorReading,
)
from robotics.protocol_clients import (
    ABBClient,
    BACnetClient,
    ClearpathClient,
    CLIENT_REGISTRY,
    DJIClient,
    FanucClient,
    KukaClient,
    ModbusClient,
    MQTTClient,
    OPCUAClient,
    ProtocolClient,
    ROS2Client,
    SpotClient,
    UniversalRobotClient,
    create_client,
)
from robotics.robot_registry import RobotRegistry
from robotics.sensor_engine import SensorEngine
from robotics.actuator_engine import ActuatorEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config(robot_id: str = "r1",
                 robot_type: RobotType = RobotType.SPOT,
                 capabilities: list | None = None,
                 enabled: bool = True) -> RobotConfig:
    return RobotConfig(
        robot_id=robot_id,
        name=f"Test {robot_type.value}",
        robot_type=robot_type,
        connection=ConnectionConfig(hostname="127.0.0.1", port=5000),
        capabilities=capabilities or [],
        enabled=enabled,
    )


def _make_command(robot_id: str = "r1",
                  actuator_id: str = "arm",
                  command_type: str = "move_to") -> ActuatorCommand:
    return ActuatorCommand(
        robot_id=robot_id,
        actuator_id=actuator_id,
        command_type=command_type,
        parameters={"x": 1.0, "y": 2.0},
    )


# ===================================================================
# Model tests
# ===================================================================

class TestModels:

    def test_robot_type_values(self):
        assert len(RobotType) == 13  # 12 original + PICARX

    def test_robot_status_values(self):
        assert RobotStatus.DISCONNECTED == "disconnected"
        assert RobotStatus.EMERGENCY_STOP == "emergency_stop"

    def test_connection_config_defaults(self):
        cfg = ConnectionConfig(hostname="10.0.0.1")
        assert cfg.port == 502
        assert cfg.use_tls is False
        assert cfg.timeout_seconds == 10.0
        assert cfg.extra == {}

    def test_robot_config_serialisation(self):
        cfg = _make_config()
        d = cfg.model_dump()
        assert d["robot_id"] == "r1"
        assert d["robot_type"] == RobotType.SPOT
        reloaded = RobotConfig(**d)
        assert reloaded.robot_id == cfg.robot_id

    def test_sensor_reading(self):
        r = SensorReading(
            robot_id="r1",
            sensor_id="temp1",
            sensor_type="temperature",
            value=23.5,
            unit="°C",
            timestamp=datetime.now(timezone.utc),
            quality=0.95,
        )
        assert r.quality == 0.95
        d = r.model_dump()
        assert "sensor_type" in d

    def test_actuator_command_defaults(self):
        cmd = ActuatorCommand(
            robot_id="r1",
            actuator_id="gripper",
            command_type="grip",
        )
        assert cmd.timeout_seconds == 30.0
        assert cmd.parameters == {}

    def test_actuator_result(self):
        res = ActuatorResult(
            robot_id="r1",
            actuator_id="gripper",
            command_type="grip",
            success=True,
            message="ok",
            execution_time_seconds=0.1,
            timestamp=datetime.now(timezone.utc),
        )
        d = res.model_dump()
        assert d["success"] is True


# ===================================================================
# Protocol client tests — every platform
# ===================================================================

ALL_TYPES = list(RobotType)


class TestProtocolClients:
    """Verify connect / disconnect / read / execute / estop for all 12."""

    @pytest.mark.parametrize("rtype", ALL_TYPES)
    def test_connect_disconnect(self, rtype: RobotType):
        cfg = _make_config(robot_type=rtype)
        client = create_client(cfg)
        assert client.status == RobotStatus.DISCONNECTED
        assert client.connect() is True
        assert client.status == RobotStatus.CONNECTED
        assert client.disconnect() is True
        assert client.status == RobotStatus.DISCONNECTED

    @pytest.mark.parametrize("rtype", ALL_TYPES)
    def test_read_sensor(self, rtype: RobotType):
        cfg = _make_config(robot_type=rtype)
        client = create_client(cfg)
        client.connect()
        reading = client.read_sensor("s1", "temperature")
        assert isinstance(reading, SensorReading)
        assert reading.robot_id == cfg.robot_id
        assert reading.sensor_id == "s1"
        assert reading.sensor_type == "temperature"

    @pytest.mark.parametrize("rtype", ALL_TYPES)
    def test_execute_command(self, rtype: RobotType):
        cfg = _make_config(robot_type=rtype)
        client = create_client(cfg)
        client.connect()
        cmd = _make_command(robot_id=cfg.robot_id)
        result = client.execute_command(cmd)
        assert isinstance(result, ActuatorResult)
        assert result.success is True

    @pytest.mark.parametrize("rtype", ALL_TYPES)
    def test_emergency_stop(self, rtype: RobotType):
        cfg = _make_config(robot_type=rtype)
        client = create_client(cfg)
        client.connect()
        assert client.emergency_stop() is True
        assert client.status == RobotStatus.EMERGENCY_STOP

    @pytest.mark.parametrize("rtype", ALL_TYPES)
    def test_get_status(self, rtype: RobotType):
        cfg = _make_config(robot_type=rtype)
        client = create_client(cfg)
        s = client.get_status()
        assert s["robot_id"] == cfg.robot_id
        assert s["status"] == RobotStatus.DISCONNECTED.value


class TestClientFactory:

    def test_registry_has_all_types(self):
        for rtype in RobotType:
            assert rtype in CLIENT_REGISTRY

    def test_create_client_returns_correct_type(self):
        mapping = {
            RobotType.SPOT: SpotClient,
            RobotType.UNIVERSAL_ROBOT: UniversalRobotClient,
            RobotType.ROS2: ROS2Client,
            RobotType.MODBUS: ModbusClient,
            RobotType.BACNET: BACnetClient,
            RobotType.OPCUA: OPCUAClient,
            RobotType.FANUC: FanucClient,
            RobotType.KUKA: KukaClient,
            RobotType.ABB: ABBClient,
            RobotType.DJI: DJIClient,
            RobotType.CLEARPATH: ClearpathClient,
            RobotType.MQTT: MQTTClient,
        }
        for rtype, expected_cls in mapping.items():
            cfg = _make_config(robot_type=rtype)
            client = create_client(cfg)
            assert isinstance(client, expected_cls)

    def test_create_client_unsupported_type(self):
        cfg = _make_config()
        cfg.robot_type = "nonexistent"  # type: ignore[assignment]
        with pytest.raises(ValueError, match="Unsupported robot type"):
            create_client(cfg)

    def test_backend_passthrough(self):
        cfg = _make_config()
        fake_backend = object()
        client = create_client(cfg, backend=fake_backend)
        assert client._backend is fake_backend


# ===================================================================
# RobotRegistry tests
# ===================================================================

class TestRobotRegistry:

    def test_register_and_get(self):
        reg = RobotRegistry()
        cfg = _make_config()
        assert reg.register(cfg) is True
        assert reg.get("r1") is cfg

    def test_register_duplicate(self):
        reg = RobotRegistry()
        cfg = _make_config()
        reg.register(cfg)
        assert reg.register(cfg) is False

    def test_unregister(self):
        reg = RobotRegistry()
        reg.register(_make_config())
        assert reg.unregister("r1") is True
        assert reg.get("r1") is None

    def test_unregister_unknown(self):
        reg = RobotRegistry()
        assert reg.unregister("nope") is False

    def test_unregister_disconnects_client(self):
        reg = RobotRegistry()
        cfg = _make_config()
        reg.register(cfg)
        reg.connect("r1")
        client = reg.get_client("r1")
        assert client.status == RobotStatus.CONNECTED
        reg.unregister("r1")
        assert client.status == RobotStatus.DISCONNECTED

    def test_get_client_creates_lazily(self):
        reg = RobotRegistry()
        reg.register(_make_config())
        client = reg.get_client("r1")
        assert isinstance(client, ProtocolClient)
        assert reg.get_client("r1") is client  # same instance

    def test_get_client_unknown(self):
        reg = RobotRegistry()
        assert reg.get_client("nope") is None

    def test_list_robots_all(self):
        reg = RobotRegistry()
        reg.register(_make_config("a", RobotType.SPOT))
        reg.register(_make_config("b", RobotType.MQTT))
        assert len(reg.list_robots()) == 2

    def test_list_robots_filtered(self):
        reg = RobotRegistry()
        reg.register(_make_config("a", RobotType.SPOT))
        reg.register(_make_config("b", RobotType.MQTT))
        assert len(reg.list_robots(RobotType.SPOT)) == 1

    def test_connect_disconnect(self):
        reg = RobotRegistry()
        reg.register(_make_config())
        assert reg.connect("r1") is True
        assert reg.get_client("r1").status == RobotStatus.CONNECTED
        assert reg.disconnect("r1") is True
        assert reg.get_client("r1").status == RobotStatus.DISCONNECTED

    def test_connect_unknown(self):
        reg = RobotRegistry()
        assert reg.connect("nope") is False

    def test_disconnect_unknown(self):
        reg = RobotRegistry()
        assert reg.disconnect("nope") is False

    def test_emergency_stop_all(self):
        reg = RobotRegistry()
        for i in range(3):
            cfg = _make_config(f"r{i}", RobotType.SPOT)
            reg.register(cfg)
            reg.connect(f"r{i}")
        results = reg.emergency_stop_all()
        assert all(results.values())
        for i in range(3):
            assert reg.get_client(f"r{i}").status == RobotStatus.EMERGENCY_STOP

    def test_get_status(self):
        reg = RobotRegistry()
        reg.register(_make_config())
        reg.connect("r1")
        s = reg.get_status()
        assert s["total_robots"] == 1
        assert "r1" in s["clients"]


# ===================================================================
# SensorEngine tests
# ===================================================================

class TestSensorEngine:

    def _setup(self):
        reg = RobotRegistry()
        cfg = _make_config(capabilities=["sense_temperature", "sense_force"])
        reg.register(cfg)
        reg.connect(cfg.robot_id)
        return SensorEngine(reg), reg

    def test_read_sensor(self):
        engine, _ = self._setup()
        reading = engine.read_sensor("r1", "temperature", "temp1")
        assert isinstance(reading, SensorReading)
        assert reading.sensor_type == "temperature"

    def test_read_sensor_unknown_robot(self):
        engine, _ = self._setup()
        with pytest.raises(ValueError, match="Unknown robot"):
            engine.read_sensor("nope", "temperature", "temp1")

    def test_read_sensor_disconnected(self):
        reg = RobotRegistry()
        reg.register(_make_config())
        # do NOT connect
        reg.get_client("r1")  # create client but leave disconnected
        engine = SensorEngine(reg)
        with pytest.raises(RuntimeError, match="disconnected"):
            engine.read_sensor("r1", "temperature", "temp1")

    def test_caching(self):
        engine, _ = self._setup()
        engine.read_sensor("r1", "temperature", "temp1")
        cached = engine.get_cached_reading("r1", "temp1")
        assert cached is not None
        assert cached.sensor_type == "temperature"

    def test_cache_miss(self):
        engine, _ = self._setup()
        assert engine.get_cached_reading("r1", "nonexist") is None

    def test_read_all_sensors(self):
        engine, _ = self._setup()
        readings = engine.read_all_sensors("r1")
        assert len(readings) == 2
        types = {r.sensor_type for r in readings}
        assert types == {"temperature", "force"}

    def test_read_all_sensors_unknown(self):
        engine, _ = self._setup()
        with pytest.raises(ValueError):
            engine.read_all_sensors("nope")

    def test_get_status(self):
        engine, _ = self._setup()
        engine.read_sensor("r1", "temperature", "t1")
        s = engine.get_status()
        assert s["cached_readings"] == 1


# ===================================================================
# ActuatorEngine tests
# ===================================================================

class TestActuatorEngine:

    def _setup(self):
        reg = RobotRegistry()
        cfg = _make_config()
        reg.register(cfg)
        reg.connect(cfg.robot_id)
        return ActuatorEngine(reg), reg

    def test_execute(self):
        engine, _ = self._setup()
        result = engine.execute(_make_command())
        assert result.success is True
        assert result.execution_time_seconds >= 0

    def test_execute_unknown_robot(self):
        engine, _ = self._setup()
        with pytest.raises(ValueError, match="Unknown robot"):
            engine.execute(_make_command(robot_id="nope"))

    def test_execute_disconnected(self):
        reg = RobotRegistry()
        reg.register(_make_config())
        reg.get_client("r1")  # create but don't connect
        engine = ActuatorEngine(reg)
        with pytest.raises(RuntimeError, match="disconnected"):
            engine.execute(_make_command())

    def test_batch_execute(self):
        engine, _ = self._setup()
        cmds = [_make_command(actuator_id=f"a{i}") for i in range(3)]
        results = engine.batch_execute(cmds)
        assert len(results) == 3
        assert all(r.success for r in results)

    def test_command_log(self):
        engine, _ = self._setup()
        engine.execute(_make_command())
        engine.execute(_make_command(actuator_id="gripper"))
        log = engine.get_command_log()
        assert len(log) == 2
        assert log[0]["actuator_id"] == "arm"

    def test_command_log_filtered(self):
        reg = RobotRegistry()
        for rid in ("a", "b"):
            reg.register(_make_config(rid))
            reg.connect(rid)
        engine = ActuatorEngine(reg)
        engine.execute(_make_command(robot_id="a"))
        engine.execute(_make_command(robot_id="b"))
        assert len(engine.get_command_log(robot_id="a")) == 1

    def test_command_log_limit(self):
        engine, _ = self._setup()
        for _ in range(10):
            engine.execute(_make_command())
        assert len(engine.get_command_log(limit=3)) == 3

    def test_get_status(self):
        engine, _ = self._setup()
        engine.execute(_make_command())
        s = engine.get_status()
        assert s["total_commands_executed"] == 1


# ===================================================================
# Thread-safety tests
# ===================================================================

class TestThreadSafety:

    def test_concurrent_register(self):
        reg = RobotRegistry()
        results: list[bool] = []

        def register_one(idx: int):
            cfg = _make_config(f"r{idx}", RobotType.SPOT)
            results.append(reg.register(cfg))

        threads = [threading.Thread(target=register_one, args=(i,))
                    for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert sum(results) == 20
        assert len(reg.list_robots()) == 20

    def test_concurrent_sensor_reads(self):
        reg = RobotRegistry()
        cfg = _make_config(capabilities=["sense_temperature"])
        reg.register(cfg)
        reg.connect(cfg.robot_id)
        engine = SensorEngine(reg)
        errors: list[Exception] = []

        def read_once():
            try:
                engine.read_sensor("r1", "temperature", "temp1")
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=read_once) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0

    def test_concurrent_execute(self):
        reg = RobotRegistry()
        cfg = _make_config()
        reg.register(cfg)
        reg.connect(cfg.robot_id)
        engine = ActuatorEngine(reg)
        errors: list[Exception] = []

        def exec_once():
            try:
                engine.execute(_make_command())
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=exec_once) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert engine.get_status()["total_commands_executed"] == 20
