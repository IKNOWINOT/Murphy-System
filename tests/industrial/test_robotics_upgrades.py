"""
Comprehensive tests for the Murphy System Robotics open-source upgrades.

Covers all 11 new integration modules across Phases 1-3.
"""

import math
import threading
from datetime import datetime, timezone

import pytest

from robotics.robotics_models import (
    ActuatorCommand,
    ConnectionConfig,
    RobotConfig,
    RobotStatus,
    RobotType,
)

# ---------------------------------------------------------------------------
# Phase 1 — Foundation
# ---------------------------------------------------------------------------

from robotics.kinematics_engine import (
    CartesianPose,
    JointState,
    KinematicsEngine,
    KinematicsStatus,
    URDFModel,
)
from robotics.simulation_bridge import (
    GazeboScene,
    MuJoCoScene,
    PhysicsState,
    SimBackend,
    SimulatedProtocolClient,
    create_simulated_client,
)

# ---------------------------------------------------------------------------
# Phase 2 — Perception & Planning
# ---------------------------------------------------------------------------

from robotics.point_cloud_processor import (
    FilterType,
    PointCloudData,
    PointCloudProcessor,
    RegistrationResult,
    SegmentationResult,
)
from robotics.navigation_engine import (
    NavigationEngine,
    NavigationGoal,
    NavigationResult,
    NavigationStatus,
    PathPlannerType,
    Pose2D,
)
from robotics.motion_planner import (
    CartesianTarget,
    CollisionObject,
    JointTarget,
    MotionPlan,
    MotionPlanner,
    PlannerAlgorithm,
    PlannerStatus,
    PlanningScene,
)
from robotics.slam_engine import (
    LaserScan,
    OccupancyGrid,
    SLAMBackend,
    SLAMEngine,
    SLAMStatus,
)
from robotics.digital_twin_bridge import (
    DigitalTwinBridge,
    SyncStatus,
    ThingModel,
)

# ---------------------------------------------------------------------------
# Phase 3 — Intelligence & Operations
# ---------------------------------------------------------------------------

from robotics.learned_policy_engine import (
    InferenceResult,
    InferenceStatus,
    LearnedPolicyEngine,
    Observation,
    PolicyConfig,
    PolicyType,
)
from robotics.fleet_orchestrator import (
    FleetOrchestrator,
    FleetTask,
    TaskPriority,
    TaskStatus,
    TaskType,
)
from robotics.telemetry_publisher import (
    ChannelConfig,
    ChannelType,
    TelemetryMessage,
    TelemetryPublisher,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _robot_config(robot_id: str = "sim1") -> RobotConfig:
    return RobotConfig(
        robot_id=robot_id,
        name="Test Robot",
        robot_type=RobotType.ROS2,
        connection=ConnectionConfig(hostname="127.0.0.1", port=5000),
    )


# ===================================================================
# Phase 1: Kinematics Engine
# ===================================================================

class TestKinematicsEngine:

    def test_default_model(self):
        engine = KinematicsEngine()
        assert engine.model.num_joints == 6
        assert engine.model.name == "generic"

    def test_custom_model(self):
        model = URDFModel(name="test_arm", num_joints=7)
        engine = KinematicsEngine(model=model)
        assert engine.model.num_joints == 7

    def test_forward_kinematics_success(self):
        engine = KinematicsEngine()
        js = JointState(positions=[0.0] * 6)
        result = engine.forward_kinematics(js)
        assert result.status == KinematicsStatus.SUCCESS
        assert result.cartesian_pose is not None

    def test_forward_kinematics_wrong_dof(self):
        engine = KinematicsEngine()
        js = JointState(positions=[0.0] * 3)
        result = engine.forward_kinematics(js)
        assert result.status == KinematicsStatus.ERROR

    def test_inverse_kinematics(self):
        engine = KinematicsEngine()
        target = CartesianPose(x=1.0, y=0.0, z=0.5)
        result = engine.inverse_kinematics(target)
        assert result.status == KinematicsStatus.SUCCESS
        assert result.joint_state is not None
        assert len(result.joint_state.positions) == 6

    def test_trajectory_generation(self):
        engine = KinematicsEngine()
        start = JointState(positions=[0.0] * 6)
        end = JointState(positions=[1.0] * 6)
        traj = engine.generate_trajectory(start, end, num_points=10)
        assert len(traj) == 10
        assert traj[0].time_from_start == 0.0
        assert traj[-1].time_from_start == 5.0

    def test_trajectory_wrong_dof(self):
        engine = KinematicsEngine()
        start = JointState(positions=[0.0] * 6)
        end = JointState(positions=[1.0] * 3)
        with pytest.raises(ValueError):
            engine.generate_trajectory(start, end)

    def test_trajectory_min_points(self):
        engine = KinematicsEngine()
        start = JointState(positions=[0.0] * 6)
        end = JointState(positions=[1.0] * 6)
        with pytest.raises(ValueError):
            engine.generate_trajectory(start, end, num_points=1)

    def test_jacobian(self):
        engine = KinematicsEngine()
        js = JointState(positions=[0.0] * 6)
        J = engine.compute_jacobian(js)
        assert len(J) == 6
        assert len(J[0]) == 6

    def test_gravity_torques(self):
        engine = KinematicsEngine()
        js = JointState(positions=[0.0] * 6)
        g = engine.gravity_torques(js)
        assert len(g) == 6

    def test_get_status(self):
        engine = KinematicsEngine()
        s = engine.get_status()
        assert s["backend"] == "stub"
        assert s["num_joints"] == 6

    def test_urdf_from_dh(self):
        dh = [(0, 0, 0.5, 0)] * 3
        model = URDFModel.from_dh(dh, name="test_dh")
        assert model.num_joints == 3


# ===================================================================
# Phase 1: Simulation Bridge
# ===================================================================

class TestSimulationBridge:

    def test_mujoco_scene_stub(self):
        scene = MuJoCoScene()
        assert not scene.is_live
        t = scene.step(10)
        assert t > 0
        state = scene.get_state()
        assert isinstance(state, PhysicsState)

    def test_mujoco_scene_reset(self):
        scene = MuJoCoScene()
        scene.step(100)
        scene.reset()
        s = scene.get_status()
        assert s["step_count"] == 0

    def test_gazebo_scene_stub(self):
        scene = GazeboScene()
        t = scene.step(5)
        assert t > 0
        s = scene.get_status()
        assert s["backend"] == "gazebo_stub"

    def test_simulated_client_connect(self):
        cfg = _robot_config()
        client = SimulatedProtocolClient(cfg)
        assert client.status == RobotStatus.DISCONNECTED
        assert client.connect() is True
        assert client.status == RobotStatus.CONNECTED
        assert client.disconnect() is True

    def test_simulated_client_read_sensor(self):
        cfg = _robot_config()
        client = SimulatedProtocolClient(cfg)
        client.connect()
        reading = client.read_sensor("s1", "position")
        assert reading.robot_id == "sim1"
        assert reading.sensor_type == "position"

    def test_simulated_client_execute(self):
        cfg = _robot_config()
        scene = MuJoCoScene()
        client = SimulatedProtocolClient(cfg, scene=scene)
        client.connect()
        cmd = ActuatorCommand(
            robot_id="sim1", actuator_id="arm",
            command_type="step", parameters={"steps": 5})
        result = client.execute_command(cmd)
        assert result.success is True

    def test_simulated_client_emergency_stop(self):
        cfg = _robot_config()
        client = SimulatedProtocolClient(cfg)
        client.connect()
        assert client.emergency_stop() is True
        assert client.status == RobotStatus.EMERGENCY_STOP

    def test_create_simulated_client_factory(self):
        cfg = _robot_config()
        client = create_simulated_client(cfg, backend=SimBackend.STUB)
        assert client.connect() is True
        s = client.get_status()
        assert s["backend"] == "stub"

    def test_simulated_client_with_mujoco(self):
        cfg = _robot_config()
        client = create_simulated_client(cfg, backend=SimBackend.MUJOCO)
        client.connect()
        s = client.get_status()
        assert s["backend"] == "mujoco"

    def test_simulated_client_with_gazebo(self):
        cfg = _robot_config()
        client = create_simulated_client(cfg, backend=SimBackend.GAZEBO)
        client.connect()
        s = client.get_status()
        assert s["backend"] == "gazebo"


# ===================================================================
# Phase 2: Point Cloud Processor
# ===================================================================

class TestPointCloudProcessor:

    def _sample_cloud(self, n: int = 100) -> PointCloudData:
        return PointCloudData(
            points=[[float(i), float(i % 10), float(i % 5)] for i in range(n)],
            timestamp=1000.0,
        )

    def test_voxel_downsample(self):
        proc = PointCloudProcessor()
        cloud = self._sample_cloud(100)
        result = proc.voxel_downsample(cloud)
        assert result.num_points <= cloud.num_points

    def test_statistical_outlier_removal(self):
        proc = PointCloudProcessor()
        cloud = self._sample_cloud(50)
        result = proc.statistical_outlier_removal(cloud)
        assert result.num_points > 0

    def test_estimate_normals(self):
        proc = PointCloudProcessor()
        cloud = self._sample_cloud(20)
        result = proc.estimate_normals(cloud)
        assert result.normals is not None
        assert len(result.normals) == 20

    def test_segment_plane(self):
        proc = PointCloudProcessor()
        cloud = self._sample_cloud(50)
        result = proc.segment_plane(cloud)
        assert isinstance(result, SegmentationResult)
        assert len(result.inlier_indices) == 50

    def test_register_icp(self):
        proc = PointCloudProcessor()
        src = self._sample_cloud(30)
        tgt = self._sample_cloud(30)
        result = proc.register_icp(src, tgt)
        assert isinstance(result, RegistrationResult)
        assert result.success is True

    def test_bounding_box(self):
        proc = PointCloudProcessor()
        cloud = PointCloudData(points=[[0, 0, 0], [1, 2, 3]])
        bb = proc.compute_bounding_box(cloud)
        assert bb["min"] == [0, 0, 0]
        assert bb["max"] == [1, 2, 3]

    def test_bounding_box_empty(self):
        proc = PointCloudProcessor()
        cloud = PointCloudData()
        bb = proc.compute_bounding_box(cloud)
        assert bb["min"] == [0, 0, 0]

    def test_cache(self):
        proc = PointCloudProcessor()
        cloud = self._sample_cloud(10)
        proc.cache_cloud("test", cloud)
        assert proc.get_cached("test") is cloud
        assert proc.get_cached("nonexist") is None

    def test_get_status(self):
        proc = PointCloudProcessor()
        s = proc.get_status()
        assert s["backend"] == "stub"
        assert s["processed_count"] == 0


# ===================================================================
# Phase 2: Navigation Engine
# ===================================================================

class TestNavigationEngine:

    def test_navigate_to(self):
        engine = NavigationEngine(robot_id="nav1")
        goal = NavigationGoal(target=Pose2D(x=5.0, y=3.0))
        result = engine.navigate_to(goal)
        assert result.status == NavigationStatus.SUCCEEDED
        assert result.message == "stub_navigation"

    def test_cancel_navigation(self):
        engine = NavigationEngine()
        # Nothing navigating
        assert engine.cancel_navigation() is False

    def test_compute_path(self):
        engine = NavigationEngine()
        path = engine.compute_path(Pose2D(0, 0), Pose2D(10, 0))
        assert path.total_distance == pytest.approx(10.0)
        assert len(path.waypoints) >= 2

    def test_follow_waypoints_empty(self):
        engine = NavigationEngine()
        result = engine.follow_waypoints([])
        assert result.status == NavigationStatus.FAILED

    def test_follow_waypoints(self):
        engine = NavigationEngine()
        wps = [Pose2D(1, 0), Pose2D(2, 0), Pose2D(3, 0)]
        result = engine.follow_waypoints(wps)
        assert result.status == NavigationStatus.SUCCEEDED

    def test_history(self):
        engine = NavigationEngine()
        engine.navigate_to(NavigationGoal(target=Pose2D(1, 1)))
        engine.navigate_to(NavigationGoal(target=Pose2D(2, 2)))
        history = engine.get_history()
        assert len(history) == 2

    def test_get_status(self):
        engine = NavigationEngine(robot_id="test_nav")
        s = engine.get_status()
        assert s["backend"] == "stub"
        assert s["robot_id"] == "test_nav"


# ===================================================================
# Phase 2: Motion Planner
# ===================================================================

class TestMotionPlanner:

    def test_plan_to_joint_target(self):
        planner = MotionPlanner(num_joints=6)
        current = JointTarget(positions=[0.0] * 6)
        target = JointTarget(positions=[1.0] * 6)
        plan = planner.plan_to_joint_target(current, target)
        assert plan.status == PlannerStatus.SUCCESS
        assert len(plan.trajectory) == 50

    def test_plan_mismatched_dof(self):
        planner = MotionPlanner()
        current = JointTarget(positions=[0.0] * 6)
        target = JointTarget(positions=[1.0] * 3)
        plan = planner.plan_to_joint_target(current, target)
        assert plan.status == PlannerStatus.ERROR

    def test_plan_to_cartesian_target(self):
        planner = MotionPlanner()
        current = JointTarget(positions=[0.0] * 6)
        target = CartesianTarget(x=0.5, y=0.0, z=0.5)
        plan = planner.plan_to_cartesian_target(current, target)
        assert plan.status == PlannerStatus.SUCCESS

    def test_cartesian_path_empty(self):
        planner = MotionPlanner()
        current = JointTarget(positions=[0.0] * 6)
        plan = planner.plan_cartesian_path([], current)
        assert plan.status == PlannerStatus.ERROR

    def test_planning_scene(self):
        scene = PlanningScene()
        obj = CollisionObject(object_id="box1")
        scene.add_object(obj)
        assert len(scene.get_objects()) == 1
        assert scene.remove_object("box1") is True
        assert scene.remove_object("nonexist") is False

    def test_collision_check_stub(self):
        scene = PlanningScene()
        assert scene.check_collision([0.0] * 6) is False

    def test_get_status(self):
        planner = MotionPlanner()
        s = planner.get_status()
        assert s["backend"] == "stub"
        assert s["plans_computed"] == 0


# ===================================================================
# Phase 2: SLAM Engine
# ===================================================================

class TestSLAMEngine:

    def test_start_stop_mapping(self):
        engine = SLAMEngine()
        assert engine.start_mapping() is True
        s = engine.get_status()
        assert s["status"] == "mapping"
        assert engine.stop_mapping() is True
        s = engine.get_status()
        assert s["status"] == "localizing"

    def test_stop_when_not_mapping(self):
        engine = SLAMEngine()
        assert engine.stop_mapping() is False

    def test_pause_resume(self):
        engine = SLAMEngine()
        engine.start_mapping()
        assert engine.pause() is True
        assert engine.resume() is True

    def test_process_scan_stub(self):
        engine = SLAMEngine()
        engine.start_mapping()
        scan = LaserScan(ranges=[1.0] * 360)
        result = engine.process_scan(scan)
        assert result.map_updated is True
        assert result.message == "stub_slam"

    def test_process_scan_not_active(self):
        engine = SLAMEngine()
        scan = LaserScan(ranges=[1.0] * 10)
        result = engine.process_scan(scan)
        assert result.message == "not_active"

    def test_get_map(self):
        engine = SLAMEngine()
        assert engine.get_map() is None
        engine.start_mapping()
        m = engine.get_map()
        assert m is not None
        assert m.num_cells == 200 * 200

    def test_get_pose(self):
        engine = SLAMEngine()
        pose = engine.get_pose()
        assert pose.x == 0.0

    def test_save_load_map(self):
        engine = SLAMEngine()
        assert engine.save_map("/tmp/test.map") is False  # no map
        engine.start_mapping()
        assert engine.save_map("/tmp/test.map") is True
        assert engine.load_map("/tmp/test.map") is True

    def test_get_status(self):
        engine = SLAMEngine()
        s = engine.get_status()
        assert s["backend"] == "stub"


# ===================================================================
# Phase 2: Digital Twin Bridge
# ===================================================================

class TestDigitalTwinBridge:

    def test_create_twin(self):
        bridge = DigitalTwinBridge()
        r = bridge.create_twin("robot1")
        assert r.thing_id == "murphy.robotics:robot1"
        assert r.status in (SyncStatus.SYNCED, SyncStatus.PENDING)

    def test_update_twin(self):
        bridge = DigitalTwinBridge()
        bridge.create_twin("robot1")
        r = bridge.update_twin("robot1", attributes={"speed": 1.5})
        assert r.status in (SyncStatus.SYNCED, SyncStatus.PENDING)
        twin = bridge.get_twin("robot1")
        assert twin.attributes["speed"] == 1.5

    def test_update_nonexistent(self):
        bridge = DigitalTwinBridge()
        r = bridge.update_twin("nope")
        assert r.status == SyncStatus.FAILED

    def test_delete_twin(self):
        bridge = DigitalTwinBridge()
        bridge.create_twin("robot1")
        r = bridge.delete_twin("robot1")
        assert r.status == SyncStatus.SYNCED
        assert bridge.get_twin("robot1") is None

    def test_delete_nonexistent(self):
        bridge = DigitalTwinBridge()
        r = bridge.delete_twin("nope")
        assert r.status == SyncStatus.FAILED

    def test_list_twins(self):
        bridge = DigitalTwinBridge()
        bridge.create_twin("r1")
        bridge.create_twin("r2")
        assert len(bridge.list_twins()) == 2

    def test_sync_sensor(self):
        bridge = DigitalTwinBridge()
        bridge.create_twin("robot1")
        r = bridge.sync_sensor_reading("robot1", "temp1", 23.5, "C")
        assert r.status in (SyncStatus.SYNCED, SyncStatus.PENDING)

    def test_sync_robot_status(self):
        bridge = DigitalTwinBridge()
        bridge.create_twin("robot1")
        r = bridge.sync_robot_status("robot1", "connected")
        assert r.status in (SyncStatus.SYNCED, SyncStatus.PENDING)

    def test_sync_all(self):
        bridge = DigitalTwinBridge()
        bridge.create_twin("r1")
        bridge.create_twin("r2")
        results = bridge.sync_all({
            "r1": {"attributes": {"status": "ok"}},
            "r2": {"features": {"sensor": {"properties": {"v": 1}}}},
        })
        assert len(results) == 2

    def test_get_status(self):
        bridge = DigitalTwinBridge()
        s = bridge.get_status()
        assert s["namespace"] == "murphy.robotics"


# ===================================================================
# Phase 3: Learned Policy Engine
# ===================================================================

class TestLearnedPolicyEngine:

    def test_load_policy(self):
        engine = LearnedPolicyEngine()
        config = PolicyConfig(model_name="test_act", policy_type=PolicyType.ACT)
        assert engine.load_policy(config) is True
        assert "test_act" in engine.list_policies()

    def test_unload_policy(self):
        engine = LearnedPolicyEngine()
        engine.load_policy(PolicyConfig(model_name="p1"))
        assert engine.unload_policy("p1") is True
        assert engine.unload_policy("p1") is False

    def test_set_active_policy(self):
        engine = LearnedPolicyEngine()
        engine.load_policy(PolicyConfig(model_name="p1"))
        engine.load_policy(PolicyConfig(model_name="p2"))
        assert engine.set_active_policy("p1") is True
        assert engine.set_active_policy("nonexist") is False

    def test_infer_no_policy(self):
        engine = LearnedPolicyEngine()
        obs = Observation(joint_positions=[0.0] * 6)
        result = engine.infer(obs)
        assert result.status == InferenceStatus.NO_MODEL

    def test_infer_stub(self):
        engine = LearnedPolicyEngine()
        engine.load_policy(PolicyConfig(model_name="test", action_horizon=5))
        obs = Observation(joint_positions=[0.1] * 6)
        result = engine.infer(obs)
        assert result.status == InferenceStatus.SUCCESS
        assert len(result.actions) == 5
        assert result.actions[0].joint_targets == [0.0] * 6

    def test_infer_by_name(self):
        engine = LearnedPolicyEngine()
        engine.load_policy(PolicyConfig(model_name="p1"))
        engine.load_policy(PolicyConfig(model_name="p2"))
        obs = Observation(joint_positions=[0.0] * 3)
        result = engine.infer(obs, policy_name="p1")
        assert result.status == InferenceStatus.SUCCESS

    def test_get_status(self):
        engine = LearnedPolicyEngine()
        s = engine.get_status()
        assert s["backend"] == "stub"


# ===================================================================
# Phase 3: Fleet Orchestrator
# ===================================================================

class TestFleetOrchestrator:

    def test_register_robot(self):
        orch = FleetOrchestrator()
        orch.register_robot("r1")
        orch.register_robot("r2")
        s = orch.get_fleet_status()
        assert s.total_robots == 2

    def test_submit_task(self):
        orch = FleetOrchestrator()
        task = FleetTask(task_type=TaskType.NAVIGATE)
        returned = orch.submit_task(task)
        assert returned.task_id == task.task_id
        assert len(orch.get_queue()) == 1

    def test_dispatch_next(self):
        orch = FleetOrchestrator()
        orch.register_robot("r1")
        orch.submit_task(FleetTask(task_type=TaskType.NAVIGATE))
        dispatched = orch.dispatch_next()
        assert dispatched is not None
        assert dispatched.status == TaskStatus.DISPATCHED
        assert dispatched.robot_id == "r1"

    def test_dispatch_no_robots(self):
        orch = FleetOrchestrator()
        orch.submit_task(FleetTask())
        assert orch.dispatch_next() is None

    def test_dispatch_no_tasks(self):
        orch = FleetOrchestrator()
        orch.register_robot("r1")
        assert orch.dispatch_next() is None

    def test_dispatch_all(self):
        orch = FleetOrchestrator()
        orch.register_robot("r1")
        orch.register_robot("r2")
        orch.submit_task(FleetTask(task_type=TaskType.NAVIGATE))
        orch.submit_task(FleetTask(task_type=TaskType.DELIVER))
        orch.submit_task(FleetTask(task_type=TaskType.PATROL))
        dispatched = orch.dispatch_all()
        assert len(dispatched) == 2  # only 2 robots

    def test_priority_ordering(self):
        orch = FleetOrchestrator()
        orch.register_robot("r1")
        orch.submit_task(FleetTask(priority=TaskPriority.LOW))
        orch.submit_task(FleetTask(priority=TaskPriority.CRITICAL))
        dispatched = orch.dispatch_next()
        assert dispatched.priority == TaskPriority.CRITICAL

    def test_complete_task(self):
        orch = FleetOrchestrator()
        orch.register_robot("r1")
        orch.submit_task(FleetTask(task_type=TaskType.NAVIGATE))
        task = orch.dispatch_next()
        assert orch.complete_task(task.task_id) is True
        completed = orch.get_completed_tasks()
        assert len(completed) == 1
        assert completed[0].status == TaskStatus.COMPLETED

    def test_complete_unknown_task(self):
        orch = FleetOrchestrator()
        assert orch.complete_task("nonexist") is False

    def test_cancel_queued(self):
        orch = FleetOrchestrator()
        task = FleetTask()
        orch.submit_task(task)
        assert orch.cancel_task(task.task_id) is True
        assert len(orch.get_queue()) == 0

    def test_cancel_active(self):
        orch = FleetOrchestrator()
        orch.register_robot("r1")
        orch.submit_task(FleetTask())
        task = orch.dispatch_next()
        assert orch.cancel_task(task.task_id) is True

    def test_get_status(self):
        orch = FleetOrchestrator()
        s = orch.get_status()
        assert s["backend"] == "stub"


# ===================================================================
# Phase 3: Telemetry Publisher
# ===================================================================

class TestTelemetryPublisher:

    def test_publish(self):
        pub = TelemetryPublisher()
        msg = TelemetryMessage(channel="test", data={"value": 42})
        assert pub.publish(msg) is True
        buf = pub.get_buffer()
        assert len(buf) == 1

    def test_publish_sensor(self):
        pub = TelemetryPublisher()
        assert pub.publish_sensor("r1", "temp", 23.5, "C") is True
        buf = pub.get_buffer(channel="r1/sensors/temp")
        assert len(buf) == 1

    def test_publish_actuator(self):
        pub = TelemetryPublisher()
        assert pub.publish_actuator("r1", "arm", "move", True, 0.5) is True

    def test_publish_diagnostic(self):
        pub = TelemetryPublisher()
        assert pub.publish_diagnostic("cpu", {"usage": 45.2}) is True

    def test_register_channel(self):
        pub = TelemetryPublisher()
        pub.register_channel(ChannelConfig(name="ch1", channel_type=ChannelType.SENSOR))
        assert "ch1" in pub.list_channels()
        assert pub.unregister_channel("ch1") is True
        assert pub.unregister_channel("ch1") is False

    def test_subscribe(self):
        pub = TelemetryPublisher()
        received = []
        pub.subscribe(lambda m: received.append(m))
        pub.publish(TelemetryMessage(channel="test", data={"v": 1}))
        assert len(received) == 1

    def test_unsubscribe(self):
        pub = TelemetryPublisher()
        cb = lambda m: None
        pub.subscribe(cb)
        assert pub.unsubscribe(cb) is True
        assert pub.unsubscribe(cb) is False

    def test_clear_buffer(self):
        pub = TelemetryPublisher()
        pub.publish(TelemetryMessage(channel="c1"))
        pub.publish(TelemetryMessage(channel="c2"))
        count = pub.clear_buffer()
        assert count == 2
        assert len(pub.get_buffer()) == 0

    def test_buffer_bounded(self):
        pub = TelemetryPublisher(max_buffer=10)
        for i in range(20):
            pub.publish(TelemetryMessage(channel="c", data={"i": i}))
        buf = pub.get_buffer()
        assert len(buf) <= 15  # bounded by trim

    def test_export_mcap_empty(self):
        pub = TelemetryPublisher()
        assert pub.export_mcap("/tmp/test.mcap") is False

    def test_export_mcap(self):
        pub = TelemetryPublisher()
        pub.publish(TelemetryMessage(channel="c1"))
        assert pub.export_mcap("/tmp/test.mcap") is True

    def test_get_status(self):
        pub = TelemetryPublisher()
        s = pub.get_status()
        assert s["backend"] == "stub"
        assert s["total_published"] == 0


# ===================================================================
# Thread-safety tests for new modules
# ===================================================================

class TestThreadSafetyUpgrades:

    def test_concurrent_twin_sync(self):
        bridge = DigitalTwinBridge()
        for i in range(5):
            bridge.create_twin(f"r{i}")
        errors: list = []

        def sync_one(idx: int) -> None:
            try:
                bridge.sync_sensor_reading(f"r{idx % 5}", "temp", float(idx))
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=sync_one, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0

    def test_concurrent_fleet_dispatch(self):
        orch = FleetOrchestrator()
        for i in range(10):
            orch.register_robot(f"r{i}")
        for i in range(20):
            orch.submit_task(FleetTask(task_type=TaskType.NAVIGATE))
        errors: list = []

        def dispatch() -> None:
            try:
                orch.dispatch_next()
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=dispatch) for _ in range(15)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0

    def test_concurrent_telemetry_publish(self):
        pub = TelemetryPublisher()
        errors: list = []

        def pub_one(i: int) -> None:
            try:
                pub.publish_sensor("r1", f"s{i}", float(i))
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=pub_one, args=(i,)) for i in range(30)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0
        assert pub.get_status()["total_published"] == 30
