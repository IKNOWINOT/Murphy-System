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


# ---------------------------------------------------------------------------
# Production-readiness tests (30+ new cases)
# ---------------------------------------------------------------------------

class TestVector3DProduction:

    def test_zero_vector_magnitude(self):
        from src.murphy_autonomous_perception import Vector3D
        v = Vector3D(x=0, y=0, z=0)
        assert v.magnitude() == 0.0

    def test_magnitude_3d(self):
        from src.murphy_autonomous_perception import Vector3D
        import math
        v = Vector3D(x=3, y=4, z=0)
        assert abs(v.magnitude() - 5.0) < 1e-6

    def test_distance_to_self(self):
        from src.murphy_autonomous_perception import Vector3D
        v = Vector3D(x=5, y=5, z=5)
        assert v.distance_to(v) == 0.0

    def test_add_vectors(self):
        from src.murphy_autonomous_perception import Vector3D
        a = Vector3D(x=1, y=2, z=3)
        b = Vector3D(x=4, y=5, z=6)
        c = a + b
        assert c.x == 5 and c.y == 7 and c.z == 9

    def test_sub_vectors(self):
        from src.murphy_autonomous_perception import Vector3D
        a = Vector3D(x=5, y=5, z=5)
        b = Vector3D(x=2, y=3, z=1)
        c = a - b
        assert c.x == 3 and c.y == 2 and c.z == 4

    def test_scale_vector(self):
        from src.murphy_autonomous_perception import Vector3D
        v = Vector3D(x=2, y=3, z=4)
        s = v.scale(2.0)
        assert s.x == 4.0 and s.y == 6.0 and s.z == 8.0

    def test_scale_by_zero(self):
        from src.murphy_autonomous_perception import Vector3D
        v = Vector3D(x=5, y=5, z=5)
        s = v.scale(0.0)
        assert s.magnitude() == 0.0


class TestBoundingBox3DProduction:

    def test_volume_unit_box(self):
        from src.murphy_autonomous_perception import BoundingBox3D
        bb = BoundingBox3D(length=1.0, width=1.0, height=1.0)
        assert bb.volume() == 1.0

    def test_volume_rectangular(self):
        from src.murphy_autonomous_perception import BoundingBox3D
        bb = BoundingBox3D(length=2.0, width=3.0, height=4.0)
        assert abs(bb.volume() - 24.0) < 1e-6

    def test_volume_car_dimensions(self):
        from src.murphy_autonomous_perception import BoundingBox3D
        bb = BoundingBox3D(length=4.5, width=1.8, height=1.5)
        assert abs(bb.volume() - 12.15) < 0.001


class TestObjectTrackerProduction:

    def test_new_detection_creates_track(self):
        from src.murphy_autonomous_perception import ObjectTracker, PerceptionObject, ObjectClass, Vector3D
        tracker = ObjectTracker()
        det = PerceptionObject(object_class=ObjectClass.VEHICLE, position=Vector3D(x=5, y=0))
        result = tracker.update([det])
        assert len(result) == 1
        assert result[0].track_id is not None

    def test_same_object_same_track_id(self):
        from src.murphy_autonomous_perception import ObjectTracker, PerceptionObject, ObjectClass, Vector3D
        tracker = ObjectTracker()
        det = PerceptionObject(object_class=ObjectClass.VEHICLE, position=Vector3D(x=5, y=0))
        r1 = tracker.update([det])
        det2 = PerceptionObject(object_class=ObjectClass.VEHICLE, position=Vector3D(x=5.1, y=0))
        r2 = tracker.update([det2])
        assert r1[0].track_id == r2[0].track_id

    def test_different_class_different_track(self):
        from src.murphy_autonomous_perception import ObjectTracker, PerceptionObject, ObjectClass, Vector3D
        tracker = ObjectTracker()
        r1 = tracker.update([PerceptionObject(object_class=ObjectClass.VEHICLE, position=Vector3D(x=5, y=0))])
        r2 = tracker.update([PerceptionObject(object_class=ObjectClass.PEDESTRIAN, position=Vector3D(x=5, y=0))])
        assert r1[0].track_id != r2[0].track_id

    def test_stale_tracks_pruned(self):
        from src.murphy_autonomous_perception import ObjectTracker, PerceptionObject, ObjectClass, Vector3D
        tracker = ObjectTracker(max_missed_frames=2)
        det = PerceptionObject(object_class=ObjectClass.VEHICLE, position=Vector3D(x=5, y=0))
        tracker.update([det])
        # Miss 3 frames
        for _ in range(3):
            tracker.update([])
        assert len(tracker.get_tracks()) == 0

    def test_multiple_objects_tracked(self):
        from src.murphy_autonomous_perception import ObjectTracker, PerceptionObject, ObjectClass, Vector3D
        tracker = ObjectTracker()
        dets = [
            PerceptionObject(object_class=ObjectClass.VEHICLE, position=Vector3D(x=0, y=0)),
            PerceptionObject(object_class=ObjectClass.PEDESTRIAN, position=Vector3D(x=100, y=100)),
        ]
        result = tracker.update(dets)
        assert len(result) == 2
        ids = {r.track_id for r in result}
        assert len(ids) == 2


class TestSafetyEnvelopeProduction:

    def test_stopping_distance_stationary(self):
        from src.murphy_autonomous_perception import SafetyEnvelope
        se = SafetyEnvelope()
        assert se.stopping_distance(0.0) == 0.0

    def test_stopping_distance_highway_speed(self):
        from src.murphy_autonomous_perception import SafetyEnvelope
        se = SafetyEnvelope(max_deceleration_mps2=8.0, reaction_time_s=0.3)
        # 30 m/s (~108 km/h)
        d = se.stopping_distance(30.0)
        # reaction dist = 30*0.3 = 9m; braking = 30^2/(2*8) = 56.25m; total = 65.25m
        assert abs(d - 65.25) < 0.01

    def test_stopping_distance_invalid_deceleration(self):
        from src.murphy_autonomous_perception import SafetyEnvelope
        import pytest
        se = SafetyEnvelope(max_deceleration_mps2=0.0)
        with pytest.raises(ValueError):
            se.stopping_distance(10.0)

    def test_ttc_approaching_object(self):
        from src.murphy_autonomous_perception import SafetyEnvelope, Vector3D
        se = SafetyEnvelope()
        # Ego at origin moving at 10 m/s in +x, object at x=15 moving at -10 m/s
        # Closing speed = 20 m/s, gap = 15 m → TTC = 0.75s
        ttc = se.time_to_collision(
            Vector3D(x=0, y=0),
            Vector3D(x=10, y=0),
            Vector3D(x=15, y=0),
            Vector3D(x=-10, y=0),
        )
        assert ttc != float("inf")
        assert ttc > 0

    def test_ttc_receding_object_returns_inf(self):
        from src.murphy_autonomous_perception import SafetyEnvelope, Vector3D
        se = SafetyEnvelope()
        # Object moving away faster than ego
        ttc = se.time_to_collision(
            Vector3D(x=0, y=0), Vector3D(x=5, y=0),
            Vector3D(x=20, y=0), Vector3D(x=15, y=0),
        )
        assert ttc == float("inf")

    def test_required_deceleration_zero_distance(self):
        from src.murphy_autonomous_perception import SafetyEnvelope
        se = SafetyEnvelope(max_deceleration_mps2=8.0)
        d = se.required_deceleration(10.0, 0.0)
        assert d == se.max_deceleration


class TestAutonomyDecisionSupportProduction:

    def test_proceed_when_clear(self):
        from src.murphy_autonomous_perception import (AutonomyDecisionSupport, PerceptionFrame,
            AutonomyAction, Vector3D)
        ads = AutonomyDecisionSupport()
        frame = PerceptionFrame(objects=[], ego_velocity=Vector3D(x=5, y=0))
        decision = ads.assess(frame)
        assert decision.action == AutonomyAction.PROCEED

    def test_emergency_stop_imminent_collision(self):
        from src.murphy_autonomous_perception import (AutonomyDecisionSupport, PerceptionFrame,
            PerceptionObject, ObjectClass, Vector3D, AutonomyAction)
        ads = AutonomyDecisionSupport()
        # Object very close and approaching fast
        obj = PerceptionObject(object_class=ObjectClass.VEHICLE,
                               position=Vector3D(x=3, y=0),
                               velocity=Vector3D(x=-20, y=0))
        frame = PerceptionFrame(
            objects=[obj],
            ego_velocity=Vector3D(x=20, y=0),
        )
        decision = ads.assess(frame)
        assert decision.action == AutonomyAction.EMERGENCY_STOP

    def test_red_light_causes_stop(self):
        from src.murphy_autonomous_perception import (AutonomyDecisionSupport, PerceptionFrame,
            PerceptionObject, ObjectClass, Vector3D, AutonomyAction, TrafficLightState)
        ads = AutonomyDecisionSupport()
        obj = PerceptionObject(
            object_class=ObjectClass.TRAFFIC_LIGHT,
            position=Vector3D(x=20, y=0),
            properties={"state": TrafficLightState.RED},
        )
        frame = PerceptionFrame(objects=[obj], ego_velocity=Vector3D(x=5, y=0))
        decision = ads.assess(frame)
        assert decision.action == AutonomyAction.STOP

    def test_slow_when_object_nearby_ttc(self):
        from src.murphy_autonomous_perception import (AutonomyDecisionSupport, PerceptionFrame,
            PerceptionObject, ObjectClass, Vector3D, AutonomyAction)
        ads = AutonomyDecisionSupport()
        # Object at medium distance with moderate closing speed
        obj = PerceptionObject(
            object_class=ObjectClass.VEHICLE,
            position=Vector3D(x=30, y=0),
            velocity=Vector3D(x=-5, y=0),
        )
        frame = PerceptionFrame(objects=[obj], ego_velocity=Vector3D(x=10, y=0))
        decision = ads.assess(frame)
        assert decision.action in (AutonomyAction.SLOW, AutonomyAction.STOP, AutonomyAction.PROCEED)

    def test_decision_includes_confidence(self):
        from src.murphy_autonomous_perception import AutonomyDecisionSupport, PerceptionFrame, Vector3D
        ads = AutonomyDecisionSupport()
        frame = PerceptionFrame(objects=[], ego_velocity=Vector3D())
        decision = ads.assess(frame)
        assert 0.0 <= decision.confidence <= 1.0


class TestDrivableAreaProduction:

    def test_point_inside_polygon(self):
        from src.murphy_autonomous_perception import DrivableArea, Vector3D
        da = DrivableArea(boundary_polygon=[
            Vector3D(x=0, y=0), Vector3D(x=10, y=0),
            Vector3D(x=10, y=10), Vector3D(x=0, y=10),
        ])
        assert da.contains_point(Vector3D(x=5, y=5)) is True

    def test_point_outside_polygon(self):
        from src.murphy_autonomous_perception import DrivableArea, Vector3D
        da = DrivableArea(boundary_polygon=[
            Vector3D(x=0, y=0), Vector3D(x=10, y=0),
            Vector3D(x=10, y=10), Vector3D(x=0, y=10),
        ])
        assert da.contains_point(Vector3D(x=20, y=20)) is False

    def test_polygon_with_fewer_than_3_points(self):
        from src.murphy_autonomous_perception import DrivableArea, Vector3D
        da = DrivableArea(boundary_polygon=[Vector3D(x=0, y=0), Vector3D(x=5, y=5)])
        assert da.contains_point(Vector3D(x=2, y=2)) is False


class TestPerceptionFrameProduction:

    def test_get_by_class(self):
        from src.murphy_autonomous_perception import PerceptionFrame, PerceptionObject, ObjectClass, Vector3D
        frame = PerceptionFrame(objects=[
            PerceptionObject(object_class=ObjectClass.VEHICLE, position=Vector3D()),
            PerceptionObject(object_class=ObjectClass.PEDESTRIAN, position=Vector3D()),
        ])
        vehicles = frame.get_by_class(ObjectClass.VEHICLE)
        assert len(vehicles) == 1

    def test_get_nearest_returns_closest(self):
        from src.murphy_autonomous_perception import PerceptionFrame, PerceptionObject, ObjectClass, Vector3D
        frame = PerceptionFrame(
            objects=[
                PerceptionObject(object_class=ObjectClass.VEHICLE, position=Vector3D(x=5, y=0)),
                PerceptionObject(object_class=ObjectClass.VEHICLE, position=Vector3D(x=100, y=0)),
            ],
            ego_position=Vector3D(x=0, y=0),
        )
        nearest = frame.get_nearest()
        assert nearest.position.x == 5.0

    def test_perception_pipeline_end_to_end(self):
        from src.murphy_autonomous_perception import (PerceptionPipeline, PerceptionObject,
            ObjectClass, Vector3D, AutonomyAction)
        pipeline = PerceptionPipeline()
        dets = [
            PerceptionObject(object_class=ObjectClass.VEHICLE, position=Vector3D(x=50, y=0)),
        ]
        frame, decision = pipeline.process(dets, ego_velocity=Vector3D(x=10, y=0))
        assert len(frame.objects) == 1
        assert decision.action in AutonomyAction.__members__.values()
