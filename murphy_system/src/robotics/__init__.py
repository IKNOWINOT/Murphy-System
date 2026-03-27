"""
Murphy System — Robotics Integration Layer.

Provides a unified interface for controlling robots and reading sensors
across 12 different platforms/protocols.
"""

from robotics.actuator_engine import ActuatorEngine
from robotics.protocol_clients import ProtocolClient, create_client
from robotics.robot_registry import RobotRegistry
from robotics.robotics_models import (
    RobotConfig,
    RobotStatus,
    RobotType,
)
from robotics.sensor_engine import SensorEngine

__all__ = [
    "ActuatorEngine",
    "ProtocolClient",
    "RobotConfig",
    "RobotRegistry",
    "RobotStatus",
    "RobotType",
    "SensorEngine",
    "create_client",
]
