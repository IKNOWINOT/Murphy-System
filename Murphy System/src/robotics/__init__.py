"""
Murphy System — Robotics Integration Layer.

Provides a unified interface for controlling robots and reading sensors
across 12 different platforms/protocols, with open-source integrations
for kinematics, simulation, navigation, SLAM, motion planning,
point cloud processing, digital twins, AI policies, fleet orchestration,
and telemetry visualisation.
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

# Phase 1 — Foundation
from robotics.kinematics_engine import KinematicsEngine
from robotics.simulation_bridge import SimulatedProtocolClient, SimBackend

# Phase 2 — Perception & Planning
from robotics.point_cloud_processor import PointCloudProcessor
from robotics.navigation_engine import NavigationEngine
from robotics.motion_planner import MotionPlanner
from robotics.slam_engine import SLAMEngine
from robotics.digital_twin_bridge import DigitalTwinBridge

# Phase 3 — Intelligence & Operations
from robotics.learned_policy_engine import LearnedPolicyEngine
from robotics.fleet_orchestrator import FleetOrchestrator
from robotics.telemetry_publisher import TelemetryPublisher

# Phase 4 — PiCar-X / Reason (AI Butler)
from robotics.picarx_hardware import PiCarXHardware
from robotics.picarx_butler import PiCarXButler

__all__ = [
    # Core
    "ActuatorEngine",
    "ProtocolClient",
    "RobotConfig",
    "RobotRegistry",
    "RobotStatus",
    "RobotType",
    "SensorEngine",
    "create_client",
    # Phase 1
    "KinematicsEngine",
    "SimulatedProtocolClient",
    "SimBackend",
    # Phase 2
    "PointCloudProcessor",
    "NavigationEngine",
    "MotionPlanner",
    "SLAMEngine",
    "DigitalTwinBridge",
    # Phase 3
    "LearnedPolicyEngine",
    "FleetOrchestrator",
    "TelemetryPublisher",
    # Phase 4 — PiCar-X / Reason
    "PiCarXHardware",
    "PiCarXButler",
]
