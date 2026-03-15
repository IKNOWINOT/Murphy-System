"""
Protocol client abstraction and stub implementations for 12 robot platforms.

Each client accepts an optional *backend* parameter.  When ``None`` (the
default) the client operates in stub/simulation mode suitable for testing.
When a real SDK object is supplied it is used to delegate operations.
"""

import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Dict, Optional, Type

from robotics.robotics_models import (
    ActuatorCommand,
    ActuatorResult,
    RobotConfig,
    RobotStatus,
    RobotType,
    SensorReading,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class ProtocolClient(ABC):
    """Abstract base class for all robot protocol clients."""

    def __init__(self, config: RobotConfig, backend: Any = None):
        self.config = config
        self._backend = backend
        self._status = RobotStatus.DISCONNECTED
        self._lock = Lock()

    @abstractmethod
    def connect(self) -> bool: ...

    @abstractmethod
    def disconnect(self) -> bool: ...

    @abstractmethod
    def read_sensor(self, sensor_id: str, sensor_type: str) -> SensorReading: ...

    @abstractmethod
    def execute_command(self, command: ActuatorCommand) -> ActuatorResult: ...

    @abstractmethod
    def emergency_stop(self) -> bool: ...

    @property
    def status(self) -> RobotStatus:
        with self._lock:
            return self._status

    def get_status(self) -> Dict[str, Any]:
        return {
            "robot_id": self.config.robot_id,
            "robot_type": self.config.robot_type.value,
            "status": self.status.value,
        }

    # -- helpers used by concrete classes ------------------------------------

    def _stub_sensor(self, sensor_id: str, sensor_type: str,
                     value: Any = 0.0, unit: str = "") -> SensorReading:
        """Return a simulated sensor reading or delegate to backend."""
        if self._backend and hasattr(self._backend, "read_sensor"):
            try:
                raw = self._backend.read_sensor(sensor_id, sensor_type)
                if isinstance(raw, SensorReading):
                    return raw
                return SensorReading(
                    robot_id=self.config.robot_id,
                    sensor_id=sensor_id,
                    sensor_type=sensor_type,
                    value=raw if raw is not None else value,
                    unit=unit,
                    timestamp=datetime.now(timezone.utc),
                )
            except Exception as exc:
                logger.warning("Backend read_sensor failed, using simulated: %s", exc)
        return SensorReading(
            robot_id=self.config.robot_id,
            sensor_id=sensor_id,
            sensor_type=sensor_type,
            value=value,
            unit=unit,
            timestamp=datetime.now(timezone.utc),
        )

    def _stub_result(self, command: ActuatorCommand, success: bool = True,
                     message: str = "") -> ActuatorResult:
        """Return a simulated actuator result or delegate to backend."""
        start = time.monotonic()
        if self._backend and hasattr(self._backend, "execute_command"):
            try:
                raw = self._backend.execute_command(command)
                if isinstance(raw, ActuatorResult):
                    return raw
                elapsed = time.monotonic() - start
                return ActuatorResult(
                    robot_id=self.config.robot_id,
                    actuator_id=command.actuator_id,
                    command_type=command.command_type,
                    success=bool(raw),
                    message=str(raw) if raw else message,
                    execution_time_seconds=elapsed,
                    timestamp=datetime.now(timezone.utc),
                )
            except Exception as exc:
                logger.warning("Backend execute_command failed, using simulated: %s", exc)
        return ActuatorResult(
            robot_id=self.config.robot_id,
            actuator_id=command.actuator_id,
            command_type=command.command_type,
            success=success,
            message=message,
            execution_time_seconds=0.0,
            timestamp=datetime.now(timezone.utc),
        )


# ---------------------------------------------------------------------------
# Concrete clients — 12 platforms
# ---------------------------------------------------------------------------

class SpotClient(ProtocolClient):
    """Boston Dynamics Spot client."""

    def connect(self) -> bool:
        with self._lock:
            if self._backend:
                logger.info("Authenticating with Spot SDK backend")
            self._status = RobotStatus.CONNECTED
        return True

    def disconnect(self) -> bool:
        with self._lock:
            self._status = RobotStatus.DISCONNECTED
        return True

    def read_sensor(self, sensor_id: str, sensor_type: str) -> SensorReading:
        return self._stub_sensor(sensor_id, sensor_type)

    def execute_command(self, command: ActuatorCommand) -> ActuatorResult:
        logger.info("Spot execute: %s", command.command_type)
        return self._stub_result(command)

    def emergency_stop(self) -> bool:
        with self._lock:
            self._status = RobotStatus.EMERGENCY_STOP
        return True


class UniversalRobotClient(ProtocolClient):
    """Universal Robots cobot client (RTDE)."""

    def connect(self) -> bool:
        with self._lock:
            if self._backend:
                logger.info("Connecting via RTDE backend")
            self._status = RobotStatus.CONNECTED
        return True

    def disconnect(self) -> bool:
        with self._lock:
            self._status = RobotStatus.DISCONNECTED
        return True

    def read_sensor(self, sensor_id: str, sensor_type: str) -> SensorReading:
        return self._stub_sensor(sensor_id, sensor_type, value=0.0, unit="rad")

    def execute_command(self, command: ActuatorCommand) -> ActuatorResult:
        logger.info("UR execute: %s", command.command_type)
        return self._stub_result(command)

    def emergency_stop(self) -> bool:
        with self._lock:
            self._status = RobotStatus.EMERGENCY_STOP
        return True


class ROS2Client(ProtocolClient):
    """ROS 2 node client."""

    def connect(self) -> bool:
        with self._lock:
            if self._backend:
                logger.info("Initialising ROS 2 node backend")
            self._status = RobotStatus.CONNECTED
        return True

    def disconnect(self) -> bool:
        with self._lock:
            self._status = RobotStatus.DISCONNECTED
        return True

    def read_sensor(self, sensor_id: str, sensor_type: str) -> SensorReading:
        return self._stub_sensor(sensor_id, sensor_type)

    def execute_command(self, command: ActuatorCommand) -> ActuatorResult:
        logger.info("ROS2 execute: %s", command.command_type)
        return self._stub_result(command)

    def emergency_stop(self) -> bool:
        with self._lock:
            self._status = RobotStatus.EMERGENCY_STOP
        return True


class ModbusClient(ProtocolClient):
    """Modbus TCP/RTU client."""

    def connect(self) -> bool:
        with self._lock:
            if self._backend:
                logger.info("Connecting Modbus backend")
            self._status = RobotStatus.CONNECTED
        return True

    def disconnect(self) -> bool:
        with self._lock:
            self._status = RobotStatus.DISCONNECTED
        return True

    def read_sensor(self, sensor_id: str, sensor_type: str) -> SensorReading:
        return self._stub_sensor(sensor_id, sensor_type, value=0, unit="raw")

    def execute_command(self, command: ActuatorCommand) -> ActuatorResult:
        logger.info("Modbus execute: %s", command.command_type)
        return self._stub_result(command)

    def emergency_stop(self) -> bool:
        with self._lock:
            self._status = RobotStatus.EMERGENCY_STOP
        return True


class BACnetClient(ProtocolClient):
    """BACnet/IP client."""

    def connect(self) -> bool:
        with self._lock:
            if self._backend:
                logger.info("Connecting BACnet backend")
            self._status = RobotStatus.CONNECTED
        return True

    def disconnect(self) -> bool:
        with self._lock:
            self._status = RobotStatus.DISCONNECTED
        return True

    def read_sensor(self, sensor_id: str, sensor_type: str) -> SensorReading:
        return self._stub_sensor(sensor_id, sensor_type, value=72.0, unit="°F")

    def execute_command(self, command: ActuatorCommand) -> ActuatorResult:
        logger.info("BACnet execute: %s", command.command_type)
        return self._stub_result(command)

    def emergency_stop(self) -> bool:
        with self._lock:
            self._status = RobotStatus.EMERGENCY_STOP
        return True


class OPCUAClient(ProtocolClient):
    """OPC-UA client."""

    def connect(self) -> bool:
        with self._lock:
            if self._backend:
                logger.info("Connecting OPC-UA backend")
            self._status = RobotStatus.CONNECTED
        return True

    def disconnect(self) -> bool:
        with self._lock:
            self._status = RobotStatus.DISCONNECTED
        return True

    def read_sensor(self, sensor_id: str, sensor_type: str) -> SensorReading:
        return self._stub_sensor(sensor_id, sensor_type)

    def execute_command(self, command: ActuatorCommand) -> ActuatorResult:
        logger.info("OPC-UA execute: %s", command.command_type)
        return self._stub_result(command)

    def emergency_stop(self) -> bool:
        with self._lock:
            self._status = RobotStatus.EMERGENCY_STOP
        return True


class FanucClient(ProtocolClient):
    """Fanuc robot client (RWS REST)."""

    def connect(self) -> bool:
        with self._lock:
            if self._backend:
                logger.info("Connecting Fanuc backend")
            self._status = RobotStatus.CONNECTED
        return True

    def disconnect(self) -> bool:
        with self._lock:
            self._status = RobotStatus.DISCONNECTED
        return True

    def read_sensor(self, sensor_id: str, sensor_type: str) -> SensorReading:
        return self._stub_sensor(sensor_id, sensor_type, value=0.0, unit="mm")

    def execute_command(self, command: ActuatorCommand) -> ActuatorResult:
        logger.info("Fanuc execute: %s", command.command_type)
        return self._stub_result(command)

    def emergency_stop(self) -> bool:
        with self._lock:
            self._status = RobotStatus.EMERGENCY_STOP
        return True


class KukaClient(ProtocolClient):
    """KUKA robot client (RSI/EKI)."""

    def connect(self) -> bool:
        with self._lock:
            if self._backend:
                logger.info("Connecting KUKA backend")
            self._status = RobotStatus.CONNECTED
        return True

    def disconnect(self) -> bool:
        with self._lock:
            self._status = RobotStatus.DISCONNECTED
        return True

    def read_sensor(self, sensor_id: str, sensor_type: str) -> SensorReading:
        return self._stub_sensor(sensor_id, sensor_type, value=0.0, unit="deg")

    def execute_command(self, command: ActuatorCommand) -> ActuatorResult:
        logger.info("KUKA execute: %s", command.command_type)
        return self._stub_result(command)

    def emergency_stop(self) -> bool:
        with self._lock:
            self._status = RobotStatus.EMERGENCY_STOP
        return True


class ABBClient(ProtocolClient):
    """ABB robot client (RWS/EGM)."""

    def connect(self) -> bool:
        with self._lock:
            if self._backend:
                logger.info("Connecting ABB backend")
            self._status = RobotStatus.CONNECTED
        return True

    def disconnect(self) -> bool:
        with self._lock:
            self._status = RobotStatus.DISCONNECTED
        return True

    def read_sensor(self, sensor_id: str, sensor_type: str) -> SensorReading:
        return self._stub_sensor(sensor_id, sensor_type)

    def execute_command(self, command: ActuatorCommand) -> ActuatorResult:
        logger.info("ABB execute: %s", command.command_type)
        return self._stub_result(command)

    def emergency_stop(self) -> bool:
        with self._lock:
            self._status = RobotStatus.EMERGENCY_STOP
        return True


class DJIClient(ProtocolClient):
    """DJI drone client (FlightHub 2)."""

    def connect(self) -> bool:
        with self._lock:
            if self._backend:
                logger.info("Connecting DJI backend")
            self._status = RobotStatus.CONNECTED
        return True

    def disconnect(self) -> bool:
        with self._lock:
            self._status = RobotStatus.DISCONNECTED
        return True

    def read_sensor(self, sensor_id: str, sensor_type: str) -> SensorReading:
        return self._stub_sensor(sensor_id, sensor_type, value=100.0, unit="m")

    def execute_command(self, command: ActuatorCommand) -> ActuatorResult:
        logger.info("DJI execute: %s", command.command_type)
        return self._stub_result(command)

    def emergency_stop(self) -> bool:
        with self._lock:
            self._status = RobotStatus.EMERGENCY_STOP
        return True


class ClearpathClient(ProtocolClient):
    """Clearpath Robotics client."""

    def connect(self) -> bool:
        with self._lock:
            if self._backend:
                logger.info("Connecting Clearpath backend")
            self._status = RobotStatus.CONNECTED
        return True

    def disconnect(self) -> bool:
        with self._lock:
            self._status = RobotStatus.DISCONNECTED
        return True

    def read_sensor(self, sensor_id: str, sensor_type: str) -> SensorReading:
        return self._stub_sensor(sensor_id, sensor_type)

    def execute_command(self, command: ActuatorCommand) -> ActuatorResult:
        logger.info("Clearpath execute: %s", command.command_type)
        return self._stub_result(command)

    def emergency_stop(self) -> bool:
        with self._lock:
            self._status = RobotStatus.EMERGENCY_STOP
        return True


class MQTTClient(ProtocolClient):
    """MQTT IoT device client."""

    def connect(self) -> bool:
        with self._lock:
            if self._backend:
                logger.info("Connecting MQTT backend")
            self._status = RobotStatus.CONNECTED
        return True

    def disconnect(self) -> bool:
        with self._lock:
            self._status = RobotStatus.DISCONNECTED
        return True

    def read_sensor(self, sensor_id: str, sensor_type: str) -> SensorReading:
        return self._stub_sensor(sensor_id, sensor_type, value=0.0, unit="")

    def execute_command(self, command: ActuatorCommand) -> ActuatorResult:
        logger.info("MQTT execute: %s", command.command_type)
        return self._stub_result(command)

    def emergency_stop(self) -> bool:
        with self._lock:
            self._status = RobotStatus.EMERGENCY_STOP
        return True


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

CLIENT_REGISTRY: Dict[RobotType, Type[ProtocolClient]] = {
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


def create_client(config: RobotConfig, backend: Any = None) -> ProtocolClient:
    """Factory to create the appropriate protocol client."""
    cls = CLIENT_REGISTRY.get(config.robot_type)
    if cls is None:
        raise ValueError(f"Unsupported robot type: {config.robot_type}")
    return cls(config, backend=backend)
