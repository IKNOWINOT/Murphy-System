"""
Murphy System - Murphy Autonomous Perception
Copyright 2024-2026 Corey Post, Inoni LLC
License: BSL 1.1
"""

from __future__ import annotations

import logging
import math
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ObjectClass(str, Enum):
    """ObjectClass enumeration."""
    VEHICLE = "vehicle"
    PEDESTRIAN = "pedestrian"
    CYCLIST = "cyclist"
    ANIMAL = "animal"
    STATIC_OBSTACLE = "static_obstacle"
    LANE_MARKING = "lane_marking"
    TRAFFIC_SIGN = "traffic_sign"
    TRAFFIC_LIGHT = "traffic_light"
    CONSTRUCTION_ZONE = "construction_zone"


class AutonomyAction(str, Enum):
    """AutonomyAction enumeration."""
    PROCEED = "proceed"
    SLOW = "slow"
    STOP = "stop"
    EMERGENCY_STOP = "emergency_stop"


class TrafficLightState(str, Enum):
    """TrafficLightState enumeration."""
    RED = "red"
    YELLOW = "yellow"
    GREEN = "green"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Geometry primitives
# ---------------------------------------------------------------------------

class Vector3D(BaseModel):
    """3D vector with x, y, z components."""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    def magnitude(self) -> float:
        return math.sqrt(self.x ** 2 + self.y ** 2 + self.z ** 2)

    def distance_to(self, other: "Vector3D") -> float:
        return math.sqrt(
            (self.x - other.x) ** 2 + (self.y - other.y) ** 2 + (self.z - other.z) ** 2
        )

    def __add__(self, other: "Vector3D") -> "Vector3D":
        return Vector3D(x=self.x + other.x, y=self.y + other.y, z=self.z + other.z)

    def __sub__(self, other: "Vector3D") -> "Vector3D":
        return Vector3D(x=self.x - other.x, y=self.y - other.y, z=self.z - other.z)

    def scale(self, factor: float) -> "Vector3D":
        return Vector3D(x=self.x * factor, y=self.y * factor, z=self.z * factor)


class BoundingBox3D(BaseModel):
    """3D bounding box for detected objects."""
    center: Vector3D = Field(default_factory=Vector3D)
    length: float = 1.0
    width: float = 1.0
    height: float = 1.0
    heading: float = 0.0  # radians

    def volume(self) -> float:
        return self.length * self.width * self.height


# ---------------------------------------------------------------------------
# Perception Object
# ---------------------------------------------------------------------------

class PerceptionObject(BaseModel):
    """PerceptionObject — perception object definition."""
    object_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    object_class: ObjectClass
    position: Vector3D = Field(default_factory=Vector3D)
    velocity: Vector3D = Field(default_factory=Vector3D)
    heading: float = 0.0
    dimensions: BoundingBox3D = Field(default_factory=BoundingBox3D)
    confidence: float = 1.0
    source_sensors: List[str] = Field(default_factory=list)
    track_id: Optional[str] = None
    last_seen: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    properties: Dict[str, Any] = Field(default_factory=dict)


class PerceptionFrame(BaseModel):
    """PerceptionFrame — perception frame definition."""
    frame_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    objects: List[PerceptionObject] = Field(default_factory=list)
    ego_position: Vector3D = Field(default_factory=Vector3D)
    ego_velocity: Vector3D = Field(default_factory=Vector3D)
    ego_heading: float = 0.0

    def get_by_class(self, cls: ObjectClass) -> List[PerceptionObject]:
        return [o for o in self.objects if o.object_class == cls]

    def get_nearest(self, position: Optional[Vector3D] = None) -> Optional[PerceptionObject]:
        """Return the nearest detected object to the given position (or ego)."""
        ref = position or self.ego_position
        if not self.objects:
            return None
        return min(self.objects, key=lambda o: o.position.distance_to(ref))


# ---------------------------------------------------------------------------
# Lane Model
# ---------------------------------------------------------------------------

class LaneModel(BaseModel):
    """LaneModel — lane model definition."""
    lane_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    polyline: List[Vector3D] = Field(default_factory=list)
    lane_type: str = "normal"
    width: float = 3.65  # meters (standard lane width)
    speed_limit_mps: Optional[float] = None

    def length(self) -> float:
        """Compute total polyline length."""
        total = 0.0
        for i in range(1, len(self.polyline)):
            total += self.polyline[i - 1].distance_to(self.polyline[i])
        return total


class DrivableArea(BaseModel):
    """DrivableArea — drivable area definition."""
    area_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    boundary_polygon: List[Vector3D] = Field(default_factory=list)

    def contains_point(self, point: Vector3D) -> bool:
        """Ray casting point-in-polygon for 2D (ignores z)."""
        poly = self.boundary_polygon
        n = len(poly)
        if n < 3:
            return False
        inside = False
        px, py = point.x, point.y
        j = n - 1
        for i in range(n):
            xi, yi = poly[i].x, poly[i].y
            xj, yj = poly[j].x, poly[j].y
            intersect = ((yi > py) != (yj > py)) and (
                px < (xj - xi) * (py - yi) / ((yj - yi) or 1e-12) + xi
            )
            if intersect:
                inside = not inside
            j = i
        return inside


# ---------------------------------------------------------------------------
# Safety Envelope
# ---------------------------------------------------------------------------

class SafetyEnvelope:
    """Compute safe stopping distance, time-to-collision, required deceleration."""

    def __init__(
        self,
        max_deceleration_mps2: float = 8.0,
        reaction_time_s: float = 0.3,
    ) -> None:
        self.max_deceleration = max_deceleration_mps2
        self.reaction_time = reaction_time_s

    def stopping_distance(self, speed_mps: float) -> float:
        """Minimum stopping distance (m) at the given speed."""
        if self.max_deceleration <= 0:
            raise ValueError(f"max_deceleration must be > 0, got {self.max_deceleration}")
        reaction_dist = speed_mps * self.reaction_time
        braking_dist = (speed_mps ** 2) / (2 * self.max_deceleration)
        return reaction_dist + braking_dist

    def time_to_collision(
        self,
        ego_pos: Vector3D,
        ego_vel: Vector3D,
        obj_pos: Vector3D,
        obj_vel: Vector3D,
    ) -> float:
        """
        Estimate time to collision (seconds). Returns inf if no collision detected.
        Uses constant-velocity prediction in 2D.
        """
        rel_pos_x = obj_pos.x - ego_pos.x
        rel_pos_y = obj_pos.y - ego_pos.y
        rel_vel_x = obj_vel.x - ego_vel.x
        rel_vel_y = obj_vel.y - ego_vel.y

        dv2 = rel_vel_x ** 2 + rel_vel_y ** 2
        if dv2 < 1e-6:
            return float("inf")

        # Time until closest approach
        t_closest = -(rel_pos_x * rel_vel_x + rel_pos_y * rel_vel_y) / dv2
        if t_closest < 0:
            return float("inf")

        # Closest distance
        cx = rel_pos_x + rel_vel_x * t_closest
        cy = rel_pos_y + rel_vel_y * t_closest
        closest_dist = math.sqrt(cx ** 2 + cy ** 2)

        # Collision threshold: 2m
        if closest_dist < 2.0:
            return t_closest
        return float("inf")

    def required_deceleration(self, speed_mps: float, distance_m: float) -> float:
        """Compute required deceleration to stop within distance_m."""
        if distance_m <= 0:
            return self.max_deceleration
        return (speed_mps ** 2) / (2 * distance_m)


# ---------------------------------------------------------------------------
# Object Tracker (Simple Hungarian + Kalman-like prediction)
# ---------------------------------------------------------------------------

@dataclass
class Track:
    """Track — track definition."""
    track_id: str
    object_class: ObjectClass
    position: Vector3D
    velocity: Vector3D
    heading: float
    last_updated: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    age_frames: int = 0
    missed_frames: int = 0


class ObjectTracker:
    """Simple multi-object tracker using greedy nearest-neighbor assignment."""

    def __init__(self, max_missed_frames: int = 5, max_distance_m: float = 10.0) -> None:
        self._tracks: Dict[str, Track] = {}
        self._max_missed = max_missed_frames
        self._max_distance = max_distance_m

    def update(self, detections: List[PerceptionObject]) -> List[PerceptionObject]:
        """
        Associate detections with existing tracks, update, and return tracked objects.
        """
        matched_track_ids: set = set()
        result: List[PerceptionObject] = []

        for det in detections:
            best_track_id: Optional[str] = None
            best_dist = float("inf")

            for tid, track in self._tracks.items():
                if tid in matched_track_ids:
                    continue
                if track.object_class != det.object_class:
                    continue
                d = det.position.distance_to(track.position)
                if d < self._max_distance and d < best_dist:
                    best_dist = d
                    best_track_id = tid

            if best_track_id:
                track = self._tracks[best_track_id]
                track.position = det.position
                track.velocity = det.velocity
                track.heading = det.heading
                track.age_frames += 1
                track.missed_frames = 0
                track.last_updated = datetime.now(timezone.utc).isoformat()
                matched_track_ids.add(best_track_id)
                try:
                    tracked_obj = det.model_copy(update={"track_id": best_track_id})
                except AttributeError:
                    tracked_obj = det.copy(update={"track_id": best_track_id})
            else:
                # New track
                new_tid = f"track-{uuid.uuid4().hex[:8]}"
                self._tracks[new_tid] = Track(
                    track_id=new_tid,
                    object_class=det.object_class,
                    position=det.position,
                    velocity=det.velocity,
                    heading=det.heading,
                )
                matched_track_ids.add(new_tid)
                try:
                    tracked_obj = det.model_copy(update={"track_id": new_tid})
                except AttributeError:
                    tracked_obj = det.copy(update={"track_id": new_tid})

            result.append(tracked_obj)

        # Increment missed frames for unmatched tracks and prune stale ones
        stale = [
            tid for tid, track in self._tracks.items()
            if tid not in matched_track_ids
        ]
        for tid in stale:
            self._tracks[tid].missed_frames += 1
        self._tracks = {
            tid: t for tid, t in self._tracks.items()
            if t.missed_frames <= self._max_missed
        }

        return result

    def get_tracks(self) -> List[Track]:
        return list(self._tracks.values())


# ---------------------------------------------------------------------------
# Autonomy Decision Support
# ---------------------------------------------------------------------------

@dataclass
class AutonomyDecision:
    """AutonomyDecision — autonomy decision definition."""
    decision_id: str
    action: AutonomyAction
    reason: str
    confidence: float
    ttc_seconds: float
    stopping_distance_m: float
    objects_considered: int
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class AutonomyDecisionSupport:
    """Given perception frame + safety envelope → recommend action."""

    def __init__(self, safety_envelope: Optional[SafetyEnvelope] = None) -> None:
        self._envelope = safety_envelope or SafetyEnvelope()

    def assess(self, frame: PerceptionFrame) -> AutonomyDecision:
        """
        Compute the recommended autonomy action based on the perception frame.
        """
        ego_speed = frame.ego_velocity.magnitude()
        stop_dist = self._envelope.stopping_distance(ego_speed)

        min_ttc = float("inf")
        closest_obj: Optional[PerceptionObject] = None
        critical_classes = {ObjectClass.VEHICLE, ObjectClass.PEDESTRIAN, ObjectClass.CYCLIST}

        for obj in frame.objects:
            if obj.object_class not in critical_classes:
                continue
            ttc = self._envelope.time_to_collision(
                frame.ego_position, frame.ego_velocity,
                obj.position, obj.velocity,
            )
            if ttc < min_ttc:
                min_ttc = ttc
                closest_obj = obj

        # Decision logic
        action: AutonomyAction
        reason: str
        confidence: float

        # Check traffic lights
        red_lights = [o for o in frame.objects if o.object_class == ObjectClass.TRAFFIC_LIGHT
                      and o.properties.get("state") == TrafficLightState.RED]
        if red_lights:
            action = AutonomyAction.STOP
            reason = "Red traffic light detected"
            confidence = 0.95
        elif min_ttc < 1.5:
            action = AutonomyAction.EMERGENCY_STOP
            reason = f"TTC {min_ttc:.2f}s < 1.5s threshold"
            confidence = 0.99
        elif min_ttc < 4.0:
            action = AutonomyAction.SLOW
            reason = f"TTC {min_ttc:.2f}s < 4.0s threshold"
            confidence = 0.9
        elif ego_speed > 0 and closest_obj and closest_obj.position.distance_to(frame.ego_position) < stop_dist:
            action = AutonomyAction.STOP
            reason = f"Object within stopping distance {stop_dist:.1f}m"
            confidence = 0.85
        else:
            action = AutonomyAction.PROCEED
            reason = "No immediate hazards detected"
            confidence = 0.8

        return AutonomyDecision(
            decision_id=str(uuid.uuid4()),
            action=action,
            reason=reason,
            confidence=confidence,
            ttc_seconds=min_ttc if min_ttc != float("inf") else -1.0,
            stopping_distance_m=stop_dist,
            objects_considered=len(frame.objects),
        )


# ---------------------------------------------------------------------------
# Perception Pipeline
# ---------------------------------------------------------------------------

class PerceptionPipeline:
    """Full pipeline: raw sensor data → object detection → tracking → prediction → safety."""

    def __init__(self) -> None:
        self._tracker = ObjectTracker()
        self._safety = SafetyEnvelope()
        self._decision_support = AutonomyDecisionSupport(self._safety)

    def process(
        self,
        raw_detections: List[PerceptionObject],
        ego_position: Optional[Vector3D] = None,
        ego_velocity: Optional[Vector3D] = None,
        ego_heading: float = 0.0,
    ) -> Tuple[PerceptionFrame, AutonomyDecision]:
        """
        Process raw detections → tracked frame → autonomy decision.
        Returns (PerceptionFrame, AutonomyDecision).
        """
        tracked = self._tracker.update(raw_detections)
        frame = PerceptionFrame(
            objects=tracked,
            ego_position=ego_position or Vector3D(),
            ego_velocity=ego_velocity or Vector3D(),
            ego_heading=ego_heading,
        )
        decision = self._decision_support.assess(frame)
        return frame, decision
