"""
Point cloud processor -- Open3D integration for spatial analysis.

Extends the Murphy sensor fusion layer with real point cloud processing:
filtering, downsampling, registration, segmentation, and 3D reconstruction.

External dependency: ``open3d`` (MIT licence).
When the library is not installed the processor operates in a lightweight
stub mode that passes data through without transformation.
"""

import logging
import math
import time
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional dependency
# ---------------------------------------------------------------------------

try:
    import open3d as o3d  # type: ignore[import-untyped]
    _OPEN3D_AVAILABLE = True
except ImportError:
    o3d = None  # type: ignore[assignment]
    _OPEN3D_AVAILABLE = False

try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class FilterType(str, Enum):
    """Point cloud filter types."""
    VOXEL_DOWNSAMPLE = "voxel_downsample"
    STATISTICAL_OUTLIER = "statistical_outlier"
    RADIUS_OUTLIER = "radius_outlier"
    PASSTHROUGH = "passthrough"
    CROP_BOX = "crop_box"


class RegistrationMethod(str, Enum):
    """Point cloud registration algorithms."""
    ICP_POINT_TO_POINT = "icp_point_to_point"
    ICP_POINT_TO_PLANE = "icp_point_to_plane"
    RANSAC = "ransac"
    FAST_GLOBAL = "fast_global"


@dataclass
class PointCloudData:
    """Lightweight point cloud representation."""
    points: List[List[float]] = field(default_factory=list)
    colors: Optional[List[List[float]]] = None
    normals: Optional[List[List[float]]] = None
    timestamp: float = 0.0

    @property
    def num_points(self) -> int:
        return len(self.points)


@dataclass
class RegistrationResult:
    """Result of a point cloud registration."""
    transformation: List[List[float]] = field(default_factory=lambda: [
        [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1],
    ])
    fitness: float = 0.0
    inlier_rmse: float = 0.0
    success: bool = False


@dataclass
class SegmentationResult:
    """Result of a plane/object segmentation."""
    plane_model: List[float] = field(default_factory=lambda: [0, 0, 1, 0])
    inlier_indices: List[int] = field(default_factory=list)
    outlier_indices: List[int] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Main processor
# ---------------------------------------------------------------------------

class PointCloudProcessor:
    """Point cloud processing engine using Open3D.

    Falls back to stub passthrough when Open3D is not installed.
    """

    def __init__(self, voxel_size: float = 0.05) -> None:
        self._voxel_size = voxel_size
        self._lock = Lock()
        self._processed_count: int = 0
        self._cache: Dict[str, PointCloudData] = {}
        self._max_cache: int = 50

    @property
    def backend_available(self) -> bool:
        return _OPEN3D_AVAILABLE

    # -- Filtering -----------------------------------------------------------

    def voxel_downsample(self, cloud: PointCloudData,
                         voxel_size: Optional[float] = None) -> PointCloudData:
        """Downsample using a voxel grid filter."""
        vs = voxel_size or self._voxel_size
        if _OPEN3D_AVAILABLE and np is not None and cloud.points:
            try:
                pcd = o3d.geometry.PointCloud()
                pcd.points = o3d.utility.Vector3dVector(
                    np.asarray(cloud.points, dtype=np.float64))
                ds = pcd.voxel_down_sample(vs)
                self._inc_count()
                return PointCloudData(
                    points=[list(p) for p in np.asarray(ds.points)],
                    timestamp=cloud.timestamp,
                )
            except Exception as exc:
                logger.warning("Open3D voxel_down_sample failed: %s", exc)

        # Stub: simple stride-based downsampling
        stride = max(1, int(1.0 / vs)) if vs > 0 else 1
        result = PointCloudData(
            points=cloud.points[::stride],
            colors=cloud.colors[::stride] if cloud.colors else None,
            normals=cloud.normals[::stride] if cloud.normals else None,
            timestamp=cloud.timestamp,
        )
        self._inc_count()
        return result

    def statistical_outlier_removal(self, cloud: PointCloudData,
                                    nb_neighbors: int = 20,
                                    std_ratio: float = 2.0) -> PointCloudData:
        """Remove statistical outliers."""
        if _OPEN3D_AVAILABLE and np is not None and cloud.points:
            try:
                pcd = o3d.geometry.PointCloud()
                pcd.points = o3d.utility.Vector3dVector(
                    np.asarray(cloud.points, dtype=np.float64))
                clean, _ = pcd.remove_statistical_outlier(nb_neighbors, std_ratio)
                self._inc_count()
                return PointCloudData(
                    points=[list(p) for p in np.asarray(clean.points)],
                    timestamp=cloud.timestamp,
                )
            except Exception as exc:
                logger.warning("Statistical outlier removal failed: %s", exc)
        self._inc_count()
        return cloud

    def estimate_normals(self, cloud: PointCloudData,
                         radius: float = 0.1,
                         max_nn: int = 30) -> PointCloudData:
        """Estimate point normals."""
        if _OPEN3D_AVAILABLE and np is not None and cloud.points:
            try:
                pcd = o3d.geometry.PointCloud()
                pcd.points = o3d.utility.Vector3dVector(
                    np.asarray(cloud.points, dtype=np.float64))
                pcd.estimate_normals(
                    search_param=o3d.geometry.KDTreeSearchParamHybrid(
                        radius=radius, max_nn=max_nn))
                self._inc_count()
                return PointCloudData(
                    points=cloud.points,
                    normals=[list(n) for n in np.asarray(pcd.normals)],
                    timestamp=cloud.timestamp,
                )
            except Exception as exc:
                logger.warning("Normal estimation failed: %s", exc)
        # Stub: default up-normals
        normals = [[0.0, 0.0, 1.0]] * len(cloud.points)
        self._inc_count()
        return PointCloudData(
            points=cloud.points, normals=normals, timestamp=cloud.timestamp)

    def segment_plane(self, cloud: PointCloudData,
                      distance_threshold: float = 0.01,
                      ransac_n: int = 3,
                      num_iterations: int = 1000) -> SegmentationResult:
        """Segment the dominant plane using RANSAC."""
        if _OPEN3D_AVAILABLE and np is not None and cloud.points:
            try:
                pcd = o3d.geometry.PointCloud()
                pcd.points = o3d.utility.Vector3dVector(
                    np.asarray(cloud.points, dtype=np.float64))
                model, inliers = pcd.segment_plane(
                    distance_threshold, ransac_n, num_iterations)
                all_idx = set(range(len(cloud.points)))
                outliers = sorted(all_idx - set(inliers))
                self._inc_count()
                return SegmentationResult(
                    plane_model=list(model),
                    inlier_indices=list(inliers),
                    outlier_indices=outliers,
                )
            except Exception as exc:
                logger.warning("Plane segmentation failed: %s", exc)
        # Stub: everything is inlier
        self._inc_count()
        return SegmentationResult(
            inlier_indices=list(range(len(cloud.points))))

    def register_icp(self, source: PointCloudData,
                     target: PointCloudData,
                     max_correspondence_distance: float = 0.05,
                     ) -> RegistrationResult:
        """Register two point clouds using ICP."""
        if _OPEN3D_AVAILABLE and np is not None and source.points and target.points:
            try:
                src_pcd = o3d.geometry.PointCloud()
                src_pcd.points = o3d.utility.Vector3dVector(
                    np.asarray(source.points, dtype=np.float64))
                tgt_pcd = o3d.geometry.PointCloud()
                tgt_pcd.points = o3d.utility.Vector3dVector(
                    np.asarray(target.points, dtype=np.float64))
                init = np.eye(4)
                result = o3d.pipelines.registration.registration_icp(
                    src_pcd, tgt_pcd, max_correspondence_distance, init,
                    o3d.pipelines.registration.TransformationEstimationPointToPoint())
                self._inc_count()
                return RegistrationResult(
                    transformation=[list(r) for r in result.transformation],
                    fitness=result.fitness,
                    inlier_rmse=result.inlier_rmse,
                    success=result.fitness > 0,
                )
            except Exception as exc:
                logger.warning("ICP registration failed: %s", exc)
        # Stub: identity transform
        self._inc_count()
        return RegistrationResult(success=True, fitness=1.0)

    def compute_bounding_box(self, cloud: PointCloudData
                             ) -> Dict[str, List[float]]:
        """Compute axis-aligned bounding box."""
        if not cloud.points:
            return {"min": [0, 0, 0], "max": [0, 0, 0], "center": [0, 0, 0]}
        xs = [p[0] for p in cloud.points]
        ys = [p[1] for p in cloud.points]
        zs = [p[2] for p in cloud.points]
        mn = [min(xs), min(ys), min(zs)]
        mx = [max(xs), max(ys), max(zs)]
        center = [(mn[i] + mx[i]) / 2.0 for i in range(3)]
        return {"min": mn, "max": mx, "center": center}

    # -- Cache ---------------------------------------------------------------

    def cache_cloud(self, key: str, cloud: PointCloudData) -> None:
        with self._lock:
            if len(self._cache) >= self._max_cache:
                oldest = next(iter(self._cache))
                del self._cache[oldest]
            self._cache[key] = cloud

    def get_cached(self, key: str) -> Optional[PointCloudData]:
        with self._lock:
            return self._cache.get(key)

    # -- Status --------------------------------------------------------------

    def _inc_count(self) -> None:
        with self._lock:
            self._processed_count += 1

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "backend": "open3d" if _OPEN3D_AVAILABLE else "stub",
                "processed_count": self._processed_count,
                "cached_clouds": len(self._cache),
                "voxel_size": self._voxel_size,
            }
