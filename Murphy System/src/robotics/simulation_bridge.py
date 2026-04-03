"""
Simulation bridge -- MuJoCo / Gazebo physics integration.

Mirrors the ``ProtocolClient`` interface so that simulated robots can be
used transparently by ``RobotRegistry``, ``SensorEngine``, and
``ActuatorEngine``.

External dependencies:
* ``mujoco`` (Apache 2.0) -- single-robot physics
* ``gz-sim`` (Apache 2.0) -- multi-robot world simulation (optional)
"""

import logging
import math
import time
from datetime import datetime, timezone
from enum import Enum
from threading import Lock
from typing import Any, Dict, List, Optional

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
# Optional dependencies
# ---------------------------------------------------------------------------

try:
    import mujoco as _mujoco_mod  # type: ignore[import-untyped]
    _MUJOCO_AVAILABLE = True
except ImportError:
    _mujoco_mod = None  # type: ignore[assignment]
    _MUJOCO_AVAILABLE = False

try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Enums and models
# ---------------------------------------------------------------------------

class SimBackend(str, Enum):
    """Available simulation backends."""
    MUJOCO = "mujoco"
    GAZEBO = "gazebo"
    STUB = "stub"


class PhysicsState:
    """Snapshot of a simulated body's physics state."""

    def __init__(
        self,
        *,
        position: Optional[List[float]] = None,
        velocity: Optional[List[float]] = None,
        joint_positions: Optional[List[float]] = None,
        joint_velocities: Optional[List[float]] = None,
        sim_time: float = 0.0,
    ) -> None:
        self.position = position or [0.0, 0.0, 0.0]
        self.velocity = velocity or [0.0, 0.0, 0.0]
        self.joint_positions = joint_positions or []
        self.joint_velocities = joint_velocities or []
        self.sim_time = sim_time


# ---------------------------------------------------------------------------
# MuJoCo scene wrapper
# ---------------------------------------------------------------------------

class MuJoCoScene:
    """Thin wrapper around a MuJoCo model + data pair."""

    def __init__(
        self,
        model_xml: Optional[str] = None,
        model_path: Optional[str] = None,
    ) -> None:
        self._model: Any = None
        self._data: Any = None
        self._lock = Lock()
        self._sim_time: float = 0.0
        self._step_count: int = 0
        if _MUJOCO_AVAILABLE:
            try:
                if model_path:
                    self._model = _mujoco_mod.MjModel.from_xml_path(model_path)
                elif model_xml:
                    self._model = _mujoco_mod.MjModel.from_xml_string(model_xml)
                if self._model is not None:
                    self._data = _mujoco_mod.MjData(self._model)
            except Exception as exc:
                logger.warning("MuJoCo model load failed: %s", exc)
        if self._model is None:
            logger.info("MuJoCoScene running in stub mode")

    @property
    def is_live(self) -> bool:
        return self._model is not None and self._data is not None

    def step(self, n: int = 1) -> float:
        """Advance simulation by *n* steps.  Returns new sim time."""
        with self._lock:
            if self.is_live:
                for _ in range(n):
                    _mujoco_mod.mj_step(self._model, self._data)
                    self._step_count += 1
                self._sim_time = self._data.time
            else:
                self._step_count += n
                self._sim_time += n * 0.002  # default 500 Hz
        return self._sim_time

    def get_state(self) -> PhysicsState:
        with self._lock:
            if self.is_live:
                return PhysicsState(
                    position=list(self._data.qpos[:3]),
                    velocity=list(self._data.qvel[:3]),
                    joint_positions=list(self._data.qpos),
                    joint_velocities=list(self._data.qvel),
                    sim_time=self._sim_time,
                )
            return PhysicsState(sim_time=self._sim_time)

    def set_joint_positions(self, positions: List[float]) -> None:
        with self._lock:
            if self.is_live:
                nq = min(len(positions), self._model.nq)
                for i in range(nq):
                    self._data.qpos[i] = positions[i]

    def apply_control(self, controls: List[float]) -> None:
        with self._lock:
            if self.is_live:
                nu = min(len(controls), self._model.nu)
                for i in range(nu):
                    self._data.ctrl[i] = controls[i]

    def reset(self) -> None:
        with self._lock:
            if self.is_live:
                _mujoco_mod.mj_resetData(self._model, self._data)
            self._sim_time = 0.0
            self._step_count = 0

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "live": self.is_live,
                "sim_time": self._sim_time,
                "step_count": self._step_count,
                "backend": "mujoco" if self.is_live else "stub",
            }


# ---------------------------------------------------------------------------
# Gazebo bridge (placeholder for gz-sim integration)
# ---------------------------------------------------------------------------

class GazeboScene:
    """Placeholder for Gazebo gz-sim world integration."""

    def __init__(self, world_sdf: Optional[str] = None) -> None:
        self._world_sdf = world_sdf
        self._sim_time: float = 0.0
        self._step_count: int = 0
        self._lock = Lock()
        logger.info("GazeboScene initialised (stub mode)")

    def step(self, n: int = 1) -> float:
        with self._lock:
            self._step_count += n
            self._sim_time += n * 0.001  # 1 kHz default
        return self._sim_time

    def get_state(self) -> PhysicsState:
        with self._lock:
            return PhysicsState(sim_time=self._sim_time)

    def reset(self) -> None:
        with self._lock:
            self._sim_time = 0.0
            self._step_count = 0

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "live": False,
                "sim_time": self._sim_time,
                "step_count": self._step_count,
                "backend": "gazebo_stub",
            }


# ---------------------------------------------------------------------------
# SimulatedProtocolClient -- drop-in for ProtocolClient
# ---------------------------------------------------------------------------

class SimulatedProtocolClient:
    """A ProtocolClient-compatible object backed by a physics simulation.

    Can be registered in ``RobotRegistry`` exactly like any hardware
    client.  The ``backend`` parameter for ``create_client`` may be a
    ``MuJoCoScene`` or ``GazeboScene`` instance.
    """

    def __init__(
        self,
        config: RobotConfig,
        scene: Optional[Any] = None,
        backend_type: SimBackend = SimBackend.STUB,
    ) -> None:
        self.config = config
        self._scene = scene
        self._backend_type = backend_type
        self._status = RobotStatus.DISCONNECTED
        self._lock = Lock()
        self._sensor_noise: float = 0.01
        self._step_counter: int = 0

    @property
    def status(self) -> RobotStatus:
        with self._lock:
            return self._status

    def connect(self) -> bool:
        with self._lock:
            self._status = RobotStatus.CONNECTED
        logger.info(
            "SimulatedClient %s connected (backend=%s)",
            self.config.robot_id,
            self._backend_type.value,
        )
        return True

    def disconnect(self) -> bool:
        with self._lock:
            self._status = RobotStatus.DISCONNECTED
        return True

    def read_sensor(self, sensor_id: str, sensor_type: str) -> SensorReading:
        """Read a sensor from the simulation scene."""
        value: Any = 0.0
        unit = ""
        if self._scene is not None and hasattr(self._scene, "get_state"):
            state = self._scene.get_state()
            if sensor_type == "position":
                value = state.position
                unit = "m"
            elif sensor_type == "velocity":
                value = state.velocity
                unit = "m/s"
            elif sensor_type in ("joint_position", "joint"):
                value = state.joint_positions
                unit = "rad"
            elif sensor_type == "joint_velocity":
                value = state.joint_velocities
                unit = "rad/s"
            else:
                value = state.sim_time
                unit = "s"
        # Add small noise to simulate real sensors
        if isinstance(value, (int, float)):
            import random
            value = value + random.gauss(0, self._sensor_noise)
        return SensorReading(
            robot_id=self.config.robot_id,
            sensor_id=sensor_id,
            sensor_type=sensor_type,
            value=value,
            unit=unit,
            timestamp=datetime.now(timezone.utc),
        )

    def execute_command(self, command: ActuatorCommand) -> ActuatorResult:
        """Apply an actuator command in the simulation."""
        start = time.monotonic()
        success = True
        message = ""
        if self._scene is not None:
            try:
                if command.command_type == "set_joints":
                    positions = command.parameters.get("positions", [])
                    if hasattr(self._scene, "set_joint_positions"):
                        self._scene.set_joint_positions(positions)
                elif command.command_type == "apply_control":
                    controls = command.parameters.get("controls", [])
                    if hasattr(self._scene, "apply_control"):
                        self._scene.apply_control(controls)
                elif command.command_type == "step":
                    n = command.parameters.get("steps", 1)
                    if hasattr(self._scene, "step"):
                        self._scene.step(n)
                elif command.command_type == "reset":
                    if hasattr(self._scene, "reset"):
                        self._scene.reset()
                else:
                    message = f"sim_passthrough: {command.command_type}"
            except Exception as exc:
                success = False
                message = str(exc)
        else:
            message = "stub_mode"
        self._step_counter += 1
        return ActuatorResult(
            robot_id=self.config.robot_id,
            actuator_id=command.actuator_id,
            command_type=command.command_type,
            success=success,
            message=message,
            execution_time_seconds=time.monotonic() - start,
            timestamp=datetime.now(timezone.utc),
        )

    def emergency_stop(self) -> bool:
        with self._lock:
            self._status = RobotStatus.EMERGENCY_STOP
        if self._scene and hasattr(self._scene, "reset"):
            self._scene.reset()
        return True

    def get_status(self) -> Dict[str, Any]:
        scene_status = {}
        if self._scene and hasattr(self._scene, "get_status"):
            scene_status = self._scene.get_status()
        return {
            "robot_id": self.config.robot_id,
            "robot_type": self.config.robot_type.value,
            "status": self.status.value,
            "backend": self._backend_type.value,
            "scene": scene_status,
            "total_steps": self._step_counter,
        }


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def create_simulated_client(
    config: RobotConfig,
    *,
    model_xml: Optional[str] = None,
    model_path: Optional[str] = None,
    world_sdf: Optional[str] = None,
    backend: SimBackend = SimBackend.STUB,
) -> SimulatedProtocolClient:
    """Create a simulation-backed protocol client."""
    scene: Any = None
    if backend == SimBackend.MUJOCO:
        scene = MuJoCoScene(model_xml=model_xml, model_path=model_path)
    elif backend == SimBackend.GAZEBO:
        scene = GazeboScene(world_sdf=world_sdf)
    return SimulatedProtocolClient(config, scene=scene, backend_type=backend)
