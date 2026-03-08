"""
Tests for Murphy Autonomous Perception (Subsystem 5).
Murphy System - Copyright 2024-2026 Corey Post, Inoni LLC - License: BSL 1.1
"""

import math
import pytest

from src.murphy_autonomous_perception import (
    AutonomyAction,
    AutonomyDecisionSupport,
    BoundingBox3D,
    DrivableArea,
    LaneModel,
    ObjectClass,
    ObjectTracker,
    PerceptionFrame,
    PerceptionObject,
    PerceptionPipeline,
    SafetyEnvelope,
    TrafficLightState,
    Vector3D,
)


# ---------------------------------------------------------------------------
# Vector3D
# ---------------------------------------------------------------------------

class TestVector3D:

    def test_magnitude(self):
        v = Vector3D(x=3.0, y=4.0, z=0.0)
        assert abs(v.magnitude() - 5.0) < 1e-9

    def test_distance_to(self):
        a = Vector3D(x=0.0, y=0.0)
        b = Vector3D(x=3.0, y=4.0)
        assert abs(a.distance_to(b) - 5.0) < 1e-9

    def test_add(self):
        a = Vector3D(x=1.0, y=2.0, z=3.0)
        b = Vector3D(x=4.0, y=5.0, z=6.0)
        c = a + b
        assert c.x == 5.0 and c.y == 7.0 and c.z == 9.0

    def test_sub(self):
        a = Vector3D(x=5.0, y=7.0)
        b = Vector3D(x=2.0, y=3.0)
        c = a - b
        assert c.x == 3.0 and c.y == 4.0

    def test_scale(self):
        v = Vector3D(x=1.0, y=2.0, z=3.0)
        v2 = v.scale(2.0)
        assert v2.x == 2.0 and v2.y == 4.0 and v2.z == 6.0

    def test_zero_magnitude(self):
        v = Vector3D()
        assert v.magnitude() == 0.0


# ---------------------------------------------------------------------------
# BoundingBox3D
# ---------------------------------------------------------------------------

class TestBoundingBox3D:

    def test_volume(self):
        bb = BoundingBox3D(length=2.0, width=3.0, height=4.0)
        assert abs(bb.volume() - 24.0) < 1e-9


# ---------------------------------------------------------------------------
# PerceptionObject
# ---------------------------------------------------------------------------

class TestPerceptionObject:

    def test_creation(self):
        obj = PerceptionObject(
            object_class=ObjectClass.VEHICLE,
            position=Vector3D(x=10.0, y=0.0),
            confidence=0.9,
        )
        assert obj.object_class == ObjectClass.VEHICLE
        assert obj.object_id is not None

    def test_all_classes(self):
        for cls in ObjectClass:
            obj = PerceptionObject(object_class=cls)
            assert obj.object_class == cls


# ---------------------------------------------------------------------------
# PerceptionFrame
# ---------------------------------------------------------------------------

class TestPerceptionFrame:

    def test_get_by_class(self):
        frame = PerceptionFrame(objects=[
            PerceptionObject(object_class=ObjectClass.VEHICLE),
            PerceptionObject(object_class=ObjectClass.PEDESTRIAN),
            PerceptionObject(object_class=ObjectClass.VEHICLE),
        ])
        vehicles = frame.get_by_class(ObjectClass.VEHICLE)
        assert len(vehicles) == 2

    def test_get_nearest(self):
        ego = Vector3D(x=0, y=0)
        frame = PerceptionFrame(
            ego_position=ego,
            objects=[
                PerceptionObject(object_class=ObjectClass.VEHICLE, position=Vector3D(x=5.0)),
                PerceptionObject(object_class=ObjectClass.VEHICLE, position=Vector3D(x=50.0)),
            ],
        )
        nearest = frame.get_nearest()
        assert nearest is not None
        assert nearest.position.x == 5.0

    def test_get_nearest_empty(self):
        frame = PerceptionFrame()
        assert frame.get_nearest() is None


# ---------------------------------------------------------------------------
# LaneModel
# ---------------------------------------------------------------------------

class TestLaneModel:

    def test_lane_length(self):
        lane = LaneModel(
            polyline=[
                Vector3D(x=0, y=0),
                Vector3D(x=3, y=4),  # distance = 5
            ]
        )
        assert abs(lane.length() - 5.0) < 1e-9

    def test_empty_lane_length(self):
        lane = LaneModel()
        assert lane.length() == 0.0


# ---------------------------------------------------------------------------
# DrivableArea
# ---------------------------------------------------------------------------

class TestDrivableArea:

    def test_point_inside(self):
        area = DrivableArea(
            boundary_polygon=[
                Vector3D(x=0, y=0),
                Vector3D(x=10, y=0),
                Vector3D(x=10, y=10),
                Vector3D(x=0, y=10),
            ]
        )
        assert area.contains_point(Vector3D(x=5, y=5)) is True

    def test_point_outside(self):
        area = DrivableArea(
            boundary_polygon=[
                Vector3D(x=0, y=0),
                Vector3D(x=10, y=0),
                Vector3D(x=10, y=10),
                Vector3D(x=0, y=10),
            ]
        )
        assert area.contains_point(Vector3D(x=15, y=15)) is False

    def test_insufficient_polygon(self):
        area = DrivableArea(boundary_polygon=[Vector3D(), Vector3D(x=1)])
        assert area.contains_point(Vector3D(x=0, y=0)) is False


# ---------------------------------------------------------------------------
# Safety Envelope
# ---------------------------------------------------------------------------

class TestSafetyEnvelope:

    def test_stopping_distance(self):
        env = SafetyEnvelope(max_deceleration_mps2=8.0, reaction_time_s=0.3)
        # At 10 m/s: reaction = 3m, braking = 100/16 = 6.25m → total ≈ 9.25m
        dist = env.stopping_distance(10.0)
        assert 8.0 < dist < 12.0

    def test_zero_speed(self):
        env = SafetyEnvelope()
        assert env.stopping_distance(0.0) == 0.0

    def test_ttc_no_collision(self):
        env = SafetyEnvelope()
        ego = Vector3D(x=0, y=0)
        ego_vel = Vector3D(x=10, y=0)
        obj = Vector3D(x=0, y=100)
        obj_vel = Vector3D(x=0, y=0)
        ttc = env.time_to_collision(ego, ego_vel, obj, obj_vel)
        assert ttc == float("inf")

    def test_ttc_head_on(self):
        env = SafetyEnvelope()
        ego = Vector3D(x=0, y=0)
        ego_vel = Vector3D(x=10, y=0)
        obj = Vector3D(x=5, y=0)
        obj_vel = Vector3D(x=-10, y=0)
        ttc = env.time_to_collision(ego, ego_vel, obj, obj_vel)
        assert ttc < float("inf")
        assert ttc > 0

    def test_required_deceleration(self):
        env = SafetyEnvelope()
        decel = env.required_deceleration(20.0, 50.0)
        assert decel > 0

    def test_required_deceleration_zero_distance(self):
        env = SafetyEnvelope()
        decel = env.required_deceleration(10.0, 0.0)
        assert decel == env.max_deceleration


# ---------------------------------------------------------------------------
# Object Tracker
# ---------------------------------------------------------------------------

class TestObjectTracker:

    def test_new_tracks_created(self):
        tracker = ObjectTracker()
        detections = [
            PerceptionObject(object_class=ObjectClass.VEHICLE, position=Vector3D(x=10)),
            PerceptionObject(object_class=ObjectClass.PEDESTRIAN, position=Vector3D(x=5, y=5)),
        ]
        result = tracker.update(detections)
        assert len(result) == 2
        for obj in result:
            assert obj.track_id is not None

    def test_track_id_persists(self):
        tracker = ObjectTracker()
        det1 = [PerceptionObject(object_class=ObjectClass.VEHICLE, position=Vector3D(x=10))]
        tracked1 = tracker.update(det1)
        tid1 = tracked1[0].track_id

        # Same vehicle slightly moved
        det2 = [PerceptionObject(object_class=ObjectClass.VEHICLE, position=Vector3D(x=10.1))]
        tracked2 = tracker.update(det2)
        assert tracked2[0].track_id == tid1

    def test_stale_tracks_pruned(self):
        tracker = ObjectTracker(max_missed_frames=2)
        det = [PerceptionObject(object_class=ObjectClass.VEHICLE, position=Vector3D(x=10))]
        tracker.update(det)
        # Update with empty detections to increment missed frames
        tracker.update([])
        tracker.update([])
        tracker.update([])  # > max_missed_frames=2
        assert len(tracker.get_tracks()) == 0


# ---------------------------------------------------------------------------
# Autonomy Decision Support
# ---------------------------------------------------------------------------

class TestAutonomyDecisionSupport:

    def test_proceed_no_hazards(self):
        ads = AutonomyDecisionSupport()
        frame = PerceptionFrame(
            ego_velocity=Vector3D(x=5.0),
            objects=[
                PerceptionObject(
                    object_class=ObjectClass.STATIC_OBSTACLE,
                    position=Vector3D(x=100.0),
                ),
            ],
        )
        decision = ads.assess(frame)
        assert decision.action == AutonomyAction.PROCEED

    def test_emergency_stop_low_ttc(self):
        ads = AutonomyDecisionSupport()
        frame = PerceptionFrame(
            ego_position=Vector3D(x=0),
            ego_velocity=Vector3D(x=10.0),
            objects=[
                PerceptionObject(
                    object_class=ObjectClass.VEHICLE,
                    position=Vector3D(x=2.0),
                    velocity=Vector3D(x=-10.0),
                ),
            ],
        )
        decision = ads.assess(frame)
        assert decision.action in (AutonomyAction.EMERGENCY_STOP, AutonomyAction.SLOW, AutonomyAction.STOP)

    def test_stop_at_red_light(self):
        ads = AutonomyDecisionSupport()
        frame = PerceptionFrame(
            ego_velocity=Vector3D(x=5.0),
            objects=[
                PerceptionObject(
                    object_class=ObjectClass.TRAFFIC_LIGHT,
                    position=Vector3D(x=20.0),
                    properties={"state": TrafficLightState.RED},
                ),
            ],
        )
        decision = ads.assess(frame)
        assert decision.action == AutonomyAction.STOP

    def test_empty_frame_proceed(self):
        ads = AutonomyDecisionSupport()
        frame = PerceptionFrame()
        decision = ads.assess(frame)
        assert decision.action == AutonomyAction.PROCEED


# ---------------------------------------------------------------------------
# Perception Pipeline (integration)
# ---------------------------------------------------------------------------

class TestPerceptionPipeline:

    def test_process_returns_frame_and_decision(self):
        pipe = PerceptionPipeline()
        detections = [
            PerceptionObject(object_class=ObjectClass.VEHICLE, position=Vector3D(x=50.0)),
        ]
        frame, decision = pipe.process(
            raw_detections=detections,
            ego_position=Vector3D(x=0),
            ego_velocity=Vector3D(x=5.0),
        )
        assert isinstance(frame, PerceptionFrame)
        assert decision.action in AutonomyAction.__members__.values()

    def test_empty_detections(self):
        pipe = PerceptionPipeline()
        frame, decision = pipe.process([])
        assert frame.objects == []
        assert decision.action == AutonomyAction.PROCEED

    def test_tracked_ids_assigned(self):
        pipe = PerceptionPipeline()
        detections = [
            PerceptionObject(object_class=ObjectClass.PEDESTRIAN, position=Vector3D(x=5, y=2)),
        ]
        frame, _ = pipe.process(detections)
        assert all(o.track_id is not None for o in frame.objects)
