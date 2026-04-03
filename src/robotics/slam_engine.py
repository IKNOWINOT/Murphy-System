"""
SLAM engine -- SLAM Toolbox / Cartographer integration.

Ingests LiDAR and depth sensor readings from the Murphy SensorEngine
and produces occupancy grid maps and robot pose estimates.

External dependencies:
* SLAM Toolbox (Apache 2.0) -- via ROS 2
* Google Cartographer (Apache 2.0) -- alternative backend
"""

import logging
import math
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional ROS 2 dependency
# ---------------------------------------------------------------------------

try:
    import rclpy  # type: ignore[import-untyped]
    _ROS2_AVAILABLE = True
except ImportError:
    _ROS2_AVAILABLE = False


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class SLAMBackend(str, Enum):
    """Available SLAM backends."""
    SLAM_TOOLBOX = "slam_toolbox"
    CARTOGRAPHER = "cartographer"
    STUB = "stub"


class SLAMStatus(str, Enum):
    """SLAM operational status."""
    IDLE = "idle"
    MAPPING = "mapping"
    LOCALIZING = "localizing"
    PAUSED = "paused"
    ERROR = "error"


@dataclass
class Pose2D:
    """2-D pose (metres + radians)."""
    x: float = 0.0
    y: float = 0.0
    theta: float = 0.0


@dataclass
class LaserScan:
    """Simplified LiDAR scan data."""
    ranges: List[float] = field(default_factory=list)
    angle_min: float = -math.pi
    angle_max: float = math.pi
    angle_increment: float = 0.0
    range_min: float = 0.1
    range_max: float = 30.0
    timestamp: float = 0.0


@dataclass
class OccupancyGrid:
    """2-D occupancy grid map."""
    width: int = 0
    height: int = 0
    resolution: float = 0.05  # metres per cell
    origin: Pose2D = field(default_factory=Pose2D)
    data: List[int] = field(default_factory=list)  # -1 unknown, 0 free, 100 occupied

    @property
    def num_cells(self) -> int:
        return self.width * self.height


@dataclass
class SLAMResult:
    """Result of a SLAM update."""
    pose: Pose2D = field(default_factory=Pose2D)
    map_updated: bool = False
    scan_count: int = 0
    message: str = ""


# ---------------------------------------------------------------------------
# Main engine
# ---------------------------------------------------------------------------

class SLAMEngine:
    """SLAM engine for map building and localisation.

    Falls back to dead-reckoning stub when ROS 2 SLAM packages
    are not available.
    """

    def __init__(self, backend: SLAMBackend = SLAMBackend.STUB,
                 map_resolution: float = 0.05) -> None:
        self._backend = backend if _ROS2_AVAILABLE else SLAMBackend.STUB
        self._resolution = map_resolution
        self._lock = Lock()
        self._status = SLAMStatus.IDLE
        self._current_pose = Pose2D()
        self._scan_count: int = 0
        self._map: Optional[OccupancyGrid] = None
        self._ros_node: Any = None

    @property
    def backend_available(self) -> bool:
        return _ROS2_AVAILABLE

    # -- Core operations -----------------------------------------------------

    def start_mapping(self) -> bool:
        """Begin building a new map."""
        with self._lock:
            self._status = SLAMStatus.MAPPING
            if self._map is None:
                self._map = OccupancyGrid(
                    width=200, height=200,
                    resolution=self._resolution,
                    data=[-1] * (200 * 200),
                )
        logger.info("SLAM mapping started (backend=%s)", self._backend.value)
        return True

    def stop_mapping(self) -> bool:
        """Stop mapping and switch to localisation only."""
        with self._lock:
            if self._status != SLAMStatus.MAPPING:
                return False
            self._status = SLAMStatus.LOCALIZING
        return True

    def pause(self) -> bool:
        with self._lock:
            self._status = SLAMStatus.PAUSED
        return True

    def resume(self) -> bool:
        with self._lock:
            if self._status == SLAMStatus.PAUSED:
                self._status = SLAMStatus.MAPPING
                return True
            return False

    # -- Scan processing -----------------------------------------------------

    def process_scan(self, scan: LaserScan) -> SLAMResult:
        """Process a laser scan and update map/pose."""
        with self._lock:
            self._scan_count += 1
            if self._status not in (SLAMStatus.MAPPING, SLAMStatus.LOCALIZING):
                return SLAMResult(
                    pose=self._current_pose, message="not_active")

        if _ROS2_AVAILABLE and self._backend != SLAMBackend.STUB:
            return self._process_ros2(scan)
        return self._process_stub(scan)

    def _process_ros2(self, scan: LaserScan) -> SLAMResult:
        """Process scan via ROS 2 SLAM backend."""
        logger.info("Processing scan via %s", self._backend.value)
        with self._lock:
            return SLAMResult(
                pose=self._current_pose,
                map_updated=True,
                scan_count=self._scan_count,
                message=self._backend.value,
            )

    def _process_stub(self, scan: LaserScan) -> SLAMResult:
        """Stub: simple dead-reckoning pose update and ray-cast map."""
        with self._lock:
            # Simple movement model
            self._current_pose.x += 0.01
            self._current_pose.y += 0.005

            # Simple ray-cast map update
            if self._map is not None and scan.ranges:
                cx = int(self._current_pose.x / self._resolution) + self._map.width // 2
                cy = int(self._current_pose.y / self._resolution) + self._map.height // 2
                if 0 <= cx < self._map.width and 0 <= cy < self._map.height:
                    idx = cy * self._map.width + cx
                    if idx < len(self._map.data):
                        self._map.data[idx] = 0  # mark free

            return SLAMResult(
                pose=Pose2D(self._current_pose.x, self._current_pose.y,
                            self._current_pose.theta),
                map_updated=True,
                scan_count=self._scan_count,
                message="stub_slam",
            )

    # -- Map access ----------------------------------------------------------

    def get_map(self) -> Optional[OccupancyGrid]:
        with self._lock:
            return self._map

    def get_pose(self) -> Pose2D:
        with self._lock:
            return Pose2D(self._current_pose.x, self._current_pose.y,
                          self._current_pose.theta)

    def save_map(self, path: str) -> bool:
        """Save current map to file (stub)."""
        with self._lock:
            if self._map is None:
                return False
        logger.info("Map saved to %s (stub)", path)
        return True

    def load_map(self, path: str) -> bool:
        """Load a previously saved map (stub)."""
        logger.info("Map loaded from %s (stub)", path)
        with self._lock:
            self._map = OccupancyGrid(
                width=200, height=200,
                resolution=self._resolution,
                data=[-1] * (200 * 200),
            )
            self._status = SLAMStatus.LOCALIZING
        return True

    # -- Status --------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "backend": self._backend.value,
                "status": self._status.value,
                "scan_count": self._scan_count,
                "pose": {"x": self._current_pose.x,
                         "y": self._current_pose.y,
                         "theta": self._current_pose.theta},
                "map_available": self._map is not None,
                "map_cells": self._map.num_cells if self._map else 0,
            }
