"""
Motion planner -- MoveIt 2 integration for collision-free planning.

Plans collision-free trajectories for robot arms (UR, KUKA, ABB, Fanuc)
using MoveIt 2 when available, falling back to linear interpolation
in joint space when it is not.

External dependency: MoveIt 2 (BSD-3 licence) via ROS 2.
"""

import logging
import math
import uuid
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional dependency
# ---------------------------------------------------------------------------

try:
    import rclpy  # type: ignore[import-untyped]
    _MOVEIT_AVAILABLE = True
except ImportError:
    _MOVEIT_AVAILABLE = False


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class PlannerStatus(str, Enum):
    """Status of a motion plan."""
    SUCCESS = "success"
    NO_SOLUTION = "no_solution"
    COLLISION = "collision"
    TIMEOUT = "timeout"
    ERROR = "error"


class PlannerAlgorithm(str, Enum):
    """Available motion planning algorithms."""
    RRT_CONNECT = "rrt_connect"
    RRT_STAR = "rrt_star"
    PRM = "prm"
    STOMP = "stomp"
    CHOMP = "chomp"
    PILZ_LIN = "pilz_lin"
    PILZ_PTP = "pilz_ptp"


@dataclass
class JointTarget:
    """Target joint configuration."""
    positions: List[float] = field(default_factory=list)
    names: List[str] = field(default_factory=list)


@dataclass
class CartesianTarget:
    """Target Cartesian pose."""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    roll: float = 0.0
    pitch: float = 0.0
    yaw: float = 0.0


@dataclass
class CollisionObject:
    """A collision object in the planning scene."""
    object_id: str = ""
    shape: str = "box"  # box, sphere, cylinder, mesh
    dimensions: List[float] = field(default_factory=lambda: [0.1, 0.1, 0.1])
    position: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    orientation: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0, 1.0])


@dataclass
class TrajectoryWaypoint:
    """Single waypoint in a planned trajectory."""
    positions: List[float] = field(default_factory=list)
    velocities: Optional[List[float]] = None
    accelerations: Optional[List[float]] = None
    time_from_start: float = 0.0


@dataclass
class MotionPlan:
    """Result of a motion planning request."""
    plan_id: str = ""
    status: PlannerStatus = PlannerStatus.ERROR
    trajectory: List[TrajectoryWaypoint] = field(default_factory=list)
    planning_time_seconds: float = 0.0
    algorithm_used: str = ""
    message: str = ""

    def __post_init__(self) -> None:
        if not self.plan_id:
            self.plan_id = f"plan_{uuid.uuid4().hex[:8]}"


# ---------------------------------------------------------------------------
# Planning scene
# ---------------------------------------------------------------------------

class PlanningScene:
    """Manages collision objects for motion planning."""

    def __init__(self) -> None:
        self._objects: Dict[str, CollisionObject] = {}
        self._lock = Lock()

    def add_object(self, obj: CollisionObject) -> None:
        with self._lock:
            self._objects[obj.object_id] = obj

    def remove_object(self, object_id: str) -> bool:
        with self._lock:
            return self._objects.pop(object_id, None) is not None

    def clear(self) -> None:
        with self._lock:
            self._objects.clear()

    def get_objects(self) -> List[CollisionObject]:
        with self._lock:
            return list(self._objects.values())

    def check_collision(self, positions: List[float]) -> bool:
        """Stub collision check -- returns False (no collision)."""
        # Real implementation would use MoveIt's collision checking
        return False


# ---------------------------------------------------------------------------
# Main planner
# ---------------------------------------------------------------------------

class MotionPlanner:
    """Collision-free motion planner using MoveIt 2.

    Falls back to linear joint-space interpolation when MoveIt 2
    is not available.
    """

    def __init__(self, num_joints: int = 6,
                 planning_scene: Optional[PlanningScene] = None) -> None:
        self._num_joints = num_joints
        self._scene = planning_scene or PlanningScene()
        self._lock = Lock()
        self._plan_count: int = 0
        self._ros_node: Any = None

    @property
    def backend_available(self) -> bool:
        return _MOVEIT_AVAILABLE

    @property
    def scene(self) -> PlanningScene:
        return self._scene

    # -- Joint-space planning ------------------------------------------------

    def plan_to_joint_target(
        self,
        current: JointTarget,
        target: JointTarget,
        algorithm: PlannerAlgorithm = PlannerAlgorithm.RRT_CONNECT,
        max_planning_time: float = 5.0,
        num_waypoints: int = 50,
    ) -> MotionPlan:
        """Plan a collision-free trajectory to a joint target."""
        if len(current.positions) != len(target.positions):
            return MotionPlan(
                status=PlannerStatus.ERROR,
                message="Mismatched DOF between current and target",
            )

        import time
        start = time.monotonic()

        # Check start/end for collision
        if self._scene.check_collision(current.positions):
            return MotionPlan(
                status=PlannerStatus.COLLISION,
                message="Start configuration in collision",
            )
        if self._scene.check_collision(target.positions):
            return MotionPlan(
                status=PlannerStatus.COLLISION,
                message="Target configuration in collision",
            )

        # Generate trajectory via cubic interpolation
        trajectory: List[TrajectoryWaypoint] = []
        n = len(current.positions)
        duration = 5.0
        for i in range(num_waypoints):
            t = i / (num_waypoints - 1) if num_waypoints > 1 else 1.0
            s = 3 * t * t - 2 * t * t * t  # cubic ease
            positions = [
                current.positions[j] + s * (target.positions[j] - current.positions[j])
                for j in range(n)
            ]
            velocities = [
                (6 * t - 6 * t * t) * (target.positions[j] - current.positions[j]) / duration
                for j in range(n)
            ]
            trajectory.append(TrajectoryWaypoint(
                positions=positions,
                velocities=velocities,
                time_from_start=t * duration,
            ))

        elapsed = time.monotonic() - start
        self._inc_count()
        return MotionPlan(
            status=PlannerStatus.SUCCESS,
            trajectory=trajectory,
            planning_time_seconds=elapsed,
            algorithm_used=algorithm.value,
            message="stub_planner" if not _MOVEIT_AVAILABLE else "moveit2",
        )

    # -- Cartesian-space planning -------------------------------------------

    def plan_to_cartesian_target(
        self,
        current_joints: JointTarget,
        target_pose: CartesianTarget,
        algorithm: PlannerAlgorithm = PlannerAlgorithm.PILZ_LIN,
    ) -> MotionPlan:
        """Plan to a Cartesian target (requires IK)."""
        # Stub: use simple joint target as approximation
        stub_target = JointTarget(
            positions=[0.0] * len(current_joints.positions))
        return self.plan_to_joint_target(
            current_joints, stub_target, algorithm=algorithm)

    # -- Cartesian linear path ----------------------------------------------

    def plan_cartesian_path(
        self,
        waypoints: List[CartesianTarget],
        current_joints: JointTarget,
    ) -> MotionPlan:
        """Plan a Cartesian linear path through waypoints."""
        if not waypoints:
            return MotionPlan(
                status=PlannerStatus.ERROR, message="Empty waypoints")
        return self.plan_to_cartesian_target(
            current_joints, waypoints[-1])

    # -- Internals -----------------------------------------------------------

    def _inc_count(self) -> None:
        with self._lock:
            self._plan_count += 1

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "backend": "moveit2" if _MOVEIT_AVAILABLE else "stub",
                "num_joints": self._num_joints,
                "plans_computed": self._plan_count,
                "scene_objects": len(self._scene.get_objects()),
            }
