"""
Pydantic models for the Murphy System Robotics Integration Layer.

Defines data structures for robot configuration, sensor readings,
and actuator commands across 12 supported platforms/protocols.
"""

import logging
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class RobotType(str, Enum):
    """Supported robot platforms and protocols."""
    SPOT = "spot"
    UNIVERSAL_ROBOT = "universal_robot"
    ROS2 = "ros2"
    MODBUS = "modbus"
    BACNET = "bacnet"
    OPCUA = "opcua"
    FANUC = "fanuc"
    KUKA = "kuka"
    ABB = "abb"
    DJI = "dji"
    CLEARPATH = "clearpath"
    MQTT = "mqtt"


class RobotStatus(str, Enum):
    """Robot connection / operational status."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    READY = "ready"
    OPERATING = "operating"
    ERROR = "error"
    EMERGENCY_STOP = "emergency_stop"


class ConnectionConfig(BaseModel):
    """Network connection parameters for a robot."""
    hostname: str
    port: int = 502
    username: Optional[str] = None
    password: Optional[str] = None
    use_tls: bool = False
    timeout_seconds: float = 10.0
    extra: Dict[str, Any] = Field(default_factory=dict)


class RobotConfig(BaseModel):
    """Full configuration for a registered robot."""
    robot_id: str
    name: str
    robot_type: RobotType
    connection: ConnectionConfig
    capabilities: List[str] = Field(default_factory=list)
    tags: Dict[str, str] = Field(default_factory=dict)
    enabled: bool = True


class SensorReading(BaseModel):
    """A single sensor measurement."""
    robot_id: str
    sensor_id: str
    sensor_type: str
    value: Any
    unit: str = ""
    timestamp: datetime
    quality: float = 1.0


class ActuatorCommand(BaseModel):
    """A command to send to an actuator."""
    robot_id: str
    actuator_id: str
    command_type: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: float = 30.0


class ActuatorResult(BaseModel):
    """Result of an actuator command execution."""
    robot_id: str
    actuator_id: str
    command_type: str
    success: bool
    message: str = ""
    execution_time_seconds: float = 0.0
    timestamp: datetime
