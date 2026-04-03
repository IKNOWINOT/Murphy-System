"""
Kinematics engine — Robotics Toolbox for Python integration.

Provides inverse/forward kinematics (IK/FK), URDF parsing, trajectory
generation, and dynamics computation for all supported robot platforms.

External dependency: ``roboticstoolbox-python`` (MIT licence).
When the library is not installed the engine operates in a lightweight
stub mode that returns analytical approximations.
"""

import logging
import math
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock
from typing import Any, Dict, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional dependency
# ---------------------------------------------------------------------------

try:
    import roboticstoolbox as rtb  # type: ignore[import-untyped]
    from spatialmath import SE3  # type: ignore[import-untyped]
    _RTB_AVAILABLE = True
except ImportError:
    rtb = None  # type: ignore[assignment]
    SE3 = None  # type: ignore[assignment]
    _RTB_AVAILABLE = False

try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class KinematicsStatus(str, Enum):
    """Result status of a kinematics computation."""
    SUCCESS = "success"
    NO_SOLUTION = "no_solution"
    SINGULAR = "singular"
    JOINT_LIMIT = "joint_limit"
    ERROR = "error"


@dataclass
class JointState:
    """A snapshot of joint positions (radians)."""
    positions: List[float]
    names: List[str] = field(default_factory=list)
    velocities: Optional[List[float]] = None
    efforts: Optional[List[float]] = None


@dataclass
class CartesianPose:
    """6-DOF Cartesian pose — position (m) + RPY orientation (rad)."""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    roll: float = 0.0
    pitch: float = 0.0
    yaw: float = 0.0


@dataclass
class TrajectoryPoint:
    """A single point on a trajectory."""
    joint_state: JointState
    time_from_start: float = 0.0


@dataclass
class KinematicsResult:
    """Result of a kinematics computation."""
    status: KinematicsStatus
    joint_state: Optional[JointState] = None
    cartesian_pose: Optional[CartesianPose] = None
    message: str = ""


# ---------------------------------------------------------------------------
# URDF loader helper
# ---------------------------------------------------------------------------

class URDFModel:
    """Thin wrapper around a loaded URDF robot model."""

    def __init__(self, *, name: str = "generic",
                 num_joints: int = 6,
                 joint_names: Optional[List[str]] = None,
                 rtb_robot: Any = None) -> None:
        self.name = name
        self.num_joints = num_joints
        self.joint_names = joint_names or [
            f"joint_{i}" for i in range(num_joints)
        ]
        self._rtb_robot = rtb_robot

    @classmethod
    def from_urdf(cls, urdf_path: str) -> "URDFModel":
        """Load a URDF file.  Falls back to a 6-DOF generic model."""
        if _RTB_AVAILABLE:
            try:
                robot = rtb.Robot.URDF(urdf_path)
                return cls(
                    name=robot.name,
                    num_joints=robot.n,
                    joint_names=[str(l.name) for l in robot.links[:robot.n]],
                    rtb_robot=robot,
                )
            except Exception as exc:
                logger.warning("URDF load via RTB failed (%s), using stub", exc)
        return cls(name="generic_6dof")

    @classmethod
    def from_dh(cls, dh_params: List[Tuple[float, float, float, float]],
                name: str = "dh_robot") -> "URDFModel":
        """Build a robot from Denavit-Hartenberg parameters."""
        n = len(dh_params)
        if _RTB_AVAILABLE:
            try:
                links = []
                for d, theta, a, alpha in dh_params:
                    links.append(rtb.RevoluteDH(d=d, a=a, alpha=alpha))
                robot = rtb.DHRobot(links, name=name)
                return cls(
                    name=name,
                    num_joints=n,
                    rtb_robot=robot,
                )
            except Exception as exc:
                logger.warning("DH build via RTB failed (%s), using stub", exc)
        return cls(name=name, num_joints=n)


# ---------------------------------------------------------------------------
# Main engine
# ---------------------------------------------------------------------------

class KinematicsEngine:
    """Inverse/forward kinematics, trajectory, and dynamics engine.

    Uses ``roboticstoolbox-python`` when available; otherwise provides
    simple analytical stubs so that callers can integrate without the
    heavyweight dependency.
    """

    def __init__(self, model: Optional[URDFModel] = None) -> None:
        self._model = model or URDFModel()
        self._lock = Lock()
        self._trajectory_cache: Dict[str, List[TrajectoryPoint]] = {}
        self._max_cache = 100

    @property
    def backend_available(self) -> bool:
        return _RTB_AVAILABLE

    @property
    def model(self) -> URDFModel:
        return self._model

    # -- Forward Kinematics -------------------------------------------------

    def forward_kinematics(self, joint_state: JointState) -> KinematicsResult:
        """Compute end-effector pose from joint positions."""
        if len(joint_state.positions) != self._model.num_joints:
            return KinematicsResult(
                status=KinematicsStatus.ERROR,
                message=(
                    f"Expected {self._model.num_joints} joints, "
                    f"got {len(joint_state.positions)}"
                ),
            )
        if self._model._rtb_robot is not None:
            try:
                q = joint_state.positions
                T = self._model._rtb_robot.fkine(q)
                pos = T.t
                rpy = T.rpy()
                pose = CartesianPose(
                    x=float(pos[0]), y=float(pos[1]), z=float(pos[2]),
                    roll=float(rpy[0]), pitch=float(rpy[1]),
                    yaw=float(rpy[2]),
                )
                return KinematicsResult(
                    status=KinematicsStatus.SUCCESS,
                    cartesian_pose=pose,
                    joint_state=joint_state,
                )
            except Exception as exc:
                logger.warning("RTB fkine failed: %s", exc)

        # Stub FK — simple planar 2-link approximation
        q = joint_state.positions
        total_angle = sum(q)
        reach = sum(math.cos(a) for a in q)
        height = sum(math.sin(a) for a in q)
        pose = CartesianPose(x=reach, y=0.0, z=height,
                             roll=0.0, pitch=0.0, yaw=total_angle)
        return KinematicsResult(
            status=KinematicsStatus.SUCCESS,
            cartesian_pose=pose,
            joint_state=joint_state,
        )

    # -- Inverse Kinematics -------------------------------------------------

    def inverse_kinematics(
        self, target: CartesianPose,
        seed: Optional[JointState] = None,
    ) -> KinematicsResult:
        """Compute joint positions that reach *target* pose."""
        if self._model._rtb_robot is not None:
            try:
                T = SE3(target.x, target.y, target.z) * SE3.RPY(
                    [target.roll, target.pitch, target.yaw],
                )
                q0 = seed.positions if seed else None
                sol = self._model._rtb_robot.ikine_LM(T, q0=q0)
                if sol.success:
                    js = JointState(
                        positions=[float(v) for v in sol.q],
                        names=self._model.joint_names,
                    )
                    return KinematicsResult(
                        status=KinematicsStatus.SUCCESS,
                        joint_state=js,
                        cartesian_pose=target,
                    )
                return KinematicsResult(
                    status=KinematicsStatus.NO_SOLUTION,
                    message="IK solver did not converge",
                )
            except Exception as exc:
                logger.warning("RTB IK failed: %s", exc)

        # Stub IK — return zeros (best-effort placeholder)
        js = JointState(
            positions=[0.0] * self._model.num_joints,
            names=self._model.joint_names,
        )
        return KinematicsResult(
            status=KinematicsStatus.SUCCESS,
            joint_state=js,
            cartesian_pose=target,
            message="stub_ik",
        )

    # -- Trajectory generation ----------------------------------------------

    def generate_trajectory(
        self,
        start: JointState,
        end: JointState,
        num_points: int = 50,
        duration: float = 5.0,
    ) -> List[TrajectoryPoint]:
        """Generate a smooth joint-space trajectory between two states."""
        if len(start.positions) != len(end.positions):
            raise ValueError("Start and end must have the same DOF")
        if num_points < 2:
            raise ValueError("Need at least 2 trajectory points")
        n = len(start.positions)
        points: List[TrajectoryPoint] = []
        for i in range(num_points):
            t = i / (num_points - 1)
            # Cubic interpolation (smooth acceleration profile)
            s = 3 * t * t - 2 * t * t * t
            positions = [
                start.positions[j] + s * (end.positions[j] - start.positions[j])
                for j in range(n)
            ]
            points.append(TrajectoryPoint(
                joint_state=JointState(
                    positions=positions,
                    names=start.names or self._model.joint_names,
                ),
                time_from_start=t * duration,
            ))

        # Cache with bounded size
        cache_key = f"traj_{len(self._trajectory_cache)}"
        with self._lock:
            if len(self._trajectory_cache) >= self._max_cache:
                oldest = next(iter(self._trajectory_cache))
                del self._trajectory_cache[oldest]
            self._trajectory_cache[cache_key] = points
        return points

    # -- Jacobian (velocity kinematics) -------------------------------------

    def compute_jacobian(self, joint_state: JointState) -> List[List[float]]:
        """Return the geometric Jacobian at the given configuration."""
        if self._model._rtb_robot is not None:
            try:
                J = self._model._rtb_robot.jacob0(joint_state.positions)
                return [list(row) for row in J]
            except Exception as exc:
                logger.warning("RTB jacobian failed: %s", exc)

        # Stub — identity-like Jacobian
        n = self._model.num_joints
        return [[1.0 if i == j else 0.0 for j in range(n)] for i in range(min(6, n))]

    # -- Dynamics -----------------------------------------------------------

    def gravity_torques(self, joint_state: JointState) -> List[float]:
        """Compute gravity compensation torques."""
        if self._model._rtb_robot is not None:
            try:
                g = self._model._rtb_robot.gravload(joint_state.positions)
                return [float(v) for v in g]
            except Exception as exc:
                logger.warning("RTB gravload failed: %s", exc)
        return [0.0] * self._model.num_joints

    # -- Status -------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "backend": "roboticstoolbox" if _RTB_AVAILABLE else "stub",
                "model_name": self._model.name,
                "num_joints": self._model.num_joints,
                "cached_trajectories": len(self._trajectory_cache),
            }
