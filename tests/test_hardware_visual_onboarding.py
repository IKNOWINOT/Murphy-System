"""
Tests for Hardware Visual Onboarding System.

Business Source License 1.1 (BSL 1.1)
Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post

Covers:
- HardwareDeviceType, ConnectionProtocol, HardwareCapability enums
- DeviceProfile and OnboardingSession data models
- HardwareDiscoveryEngine discover/probe/identify
- HardwareOnboardingPipeline full onboarding flow
- VisualSystemRegistry CRUD operations
- DeviceDriverManager load/create/list
- HardwareHealthMonitor start/stop/health check/alert threshold
- WingmanPair creation per onboarded device
- Quarantine flow for failing devices
- Emergency stop integration when device fails repeatedly
"""

import threading
import uuid
import pytest

from src.hardware_visual_onboarding import (
    ConnectionProtocol,
    DeviceDriverManager,
    DeviceProfile,
    HardwareCapability,
    HardwareDeviceType,
    HardwareDiscoveryEngine,
    HardwareHealthMonitor,
    HardwareOnboardingPipeline,
    OnboardingSession,
    OnboardingStage,
    VisualSystemRegistry,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_profile():
    """Return a standard RGB camera DeviceProfile."""
    return DeviceProfile(
        device_id=f"dev-{uuid.uuid4().hex[:8]}",
        device_type=HardwareDeviceType.CAMERA_RGB,
        connection_protocol=ConnectionProtocol.USB,
        manufacturer="Acme",
        model="RGB-100",
        serial_number="SN-001",
        firmware_version="1.0.0",
        capabilities=[HardwareCapability.VIDEO_CAPTURE, HardwareCapability.STILL_CAPTURE],
        resolution=(1920, 1080),
        frame_rate=30.0,
        field_of_view=90.0,
    )


@pytest.fixture
def registry():
    return VisualSystemRegistry()


@pytest.fixture
def pipeline():
    return HardwareOnboardingPipeline()


@pytest.fixture
def discovery():
    return HardwareDiscoveryEngine()


@pytest.fixture
def driver_manager():
    return DeviceDriverManager()


@pytest.fixture
def health_monitor():
    return HardwareHealthMonitor()


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------

class TestEnums:
    def test_hardware_device_type_values(self):
        assert HardwareDeviceType.CAMERA_RGB.value == "camera_rgb"
        assert HardwareDeviceType.LIDAR_3D.value == "lidar_3d"
        assert HardwareDeviceType.DISPLAY_HMD.value == "display_hmd"
        assert HardwareDeviceType.PTZ_CAMERA.value == "ptz_camera"
        assert HardwareDeviceType.CUSTOM.value == "custom"

    def test_all_device_type_members(self):
        expected = [
            "camera_rgb", "camera_depth", "camera_thermal", "camera_stereo",
            "camera_fisheye", "camera_360", "lidar_2d", "lidar_3d", "radar",
            "display_monitor", "display_hmd", "display_projector", "display_led_wall",
            "sensor_imu", "sensor_ultrasonic", "sensor_infrared", "sensor_tof",
            "industrial_vision", "endoscope", "microscope", "drone_camera",
            "body_camera", "dashcam", "ptz_camera", "custom",
        ]
        values = [e.value for e in HardwareDeviceType]
        for expected_val in expected:
            assert expected_val in values

    def test_connection_protocol_values(self):
        assert ConnectionProtocol.USB.value == "usb"
        assert ConnectionProtocol.GIGE_VISION.value == "gige_vision"
        assert ConnectionProtocol.ONVIF.value == "onvif"
        assert ConnectionProtocol.OPCUA.value == "opcua"

    def test_hardware_capability_values(self):
        assert HardwareCapability.VIDEO_CAPTURE.value == "video_capture"
        assert HardwareCapability.DEPTH_SENSING.value == "depth_sensing"
        assert HardwareCapability.THERMAL_IMAGING.value == "thermal_imaging"
        assert HardwareCapability.POINT_CLOUD.value == "point_cloud"

    def test_onboarding_stage_values(self):
        assert OnboardingStage.DISCOVERED.value == "discovered"
        assert OnboardingStage.REGISTERED.value == "registered"
        assert OnboardingStage.QUARANTINED.value == "quarantined"
        assert OnboardingStage.FAILED.value == "failed"


# ---------------------------------------------------------------------------
# DeviceProfile data model
# ---------------------------------------------------------------------------

class TestDeviceProfile:
    def test_profile_creation(self, sample_profile):
        assert sample_profile.device_type == HardwareDeviceType.CAMERA_RGB
        assert sample_profile.connection_protocol == ConnectionProtocol.USB
        assert HardwareCapability.VIDEO_CAPTURE in sample_profile.capabilities
        assert sample_profile.resolution == (1920, 1080)
        assert sample_profile.frame_rate == 30.0
        assert sample_profile.health_status == "unknown"

    def test_profile_defaults(self):
        profile = DeviceProfile(
            device_id="dev-001",
            device_type=HardwareDeviceType.CUSTOM,
            connection_protocol=ConnectionProtocol.CUSTOM,
            manufacturer="X",
            model="Y",
            serial_number="SN",
            firmware_version="0.1",
        )
        assert profile.capabilities == []
        assert profile.resolution is None
        assert profile.calibration_data == {}


# ---------------------------------------------------------------------------
# OnboardingSession data model
# ---------------------------------------------------------------------------

class TestOnboardingSession:
    def test_session_creation(self):
        session = OnboardingSession(
            session_id="sess-001",
            device_id="dev-001",
            stage=OnboardingStage.DISCOVERED,
            started_at="2024-01-01T00:00:00+00:00",
        )
        assert session.stage == OnboardingStage.DISCOVERED
        assert session.errors == []
        assert session.wingman_pair_id is None


# ---------------------------------------------------------------------------
# HardwareDiscoveryEngine
# ---------------------------------------------------------------------------

class TestHardwareDiscoveryEngine:
    def test_discover_devices_returns_list(self, discovery):
        devices = discovery.discover_devices()
        assert isinstance(devices, list)

    def test_discover_empty_by_default(self, discovery):
        devices = discovery.discover_devices()
        assert len(devices) == 0

    def test_register_and_discover(self, discovery, sample_profile):
        discovery.register_device_manually(sample_profile)
        devices = discovery.discover_devices()
        assert len(devices) == 1
        assert devices[0].device_id == sample_profile.device_id

    def test_probe_existing_device(self, discovery, sample_profile):
        discovery.register_device_manually(sample_profile)
        result = discovery.probe_device(sample_profile.device_id)
        assert result["device_id"] == sample_profile.device_id
        assert result["manufacturer"] == "Acme"
        assert "capabilities" in result

    def test_probe_missing_device_returns_error(self, discovery):
        result = discovery.probe_device("nonexistent")
        assert "error" in result
        assert "recommendation" in result

    def test_identify_rgb_camera(self, discovery, sample_profile):
        discovery.register_device_manually(sample_profile)
        probe = discovery.probe_device(sample_profile.device_id)
        identified = discovery.identify_device_type(probe)
        assert identified == HardwareDeviceType.CAMERA_RGB

    def test_identify_thermal_camera(self, discovery):
        profile = DeviceProfile(
            device_id="thermal-001",
            device_type=HardwareDeviceType.CAMERA_THERMAL,
            connection_protocol=ConnectionProtocol.GIGE_VISION,
            manufacturer="FLIR",
            model="SC655",
            serial_number="T-001",
            firmware_version="2.0",
            capabilities=[HardwareCapability.THERMAL_IMAGING],
        )
        discovery.register_device_manually(profile)
        probe = discovery.probe_device("thermal-001")
        identified = discovery.identify_device_type(probe)
        assert identified == HardwareDeviceType.CAMERA_THERMAL

    def test_identify_lidar(self, discovery):
        probe_result = {
            "device_id": "lidar-001",
            "capabilities": [HardwareCapability.POINT_CLOUD.value],
            "model": "Velodyne VLP-16",
        }
        identified = discovery.identify_device_type(probe_result)
        assert identified == HardwareDeviceType.LIDAR_3D

    def test_identify_hmd_by_model(self, discovery):
        probe_result = {"device_id": "hmd-001", "capabilities": [], "model": "VR Headset Pro"}
        identified = discovery.identify_device_type(probe_result)
        assert identified == HardwareDeviceType.DISPLAY_HMD

    def test_identify_unknown_returns_custom(self, discovery):
        probe_result = {"device_id": "x-001", "capabilities": [], "model": "Widget 9000"}
        identified = discovery.identify_device_type(probe_result)
        assert identified == HardwareDeviceType.CUSTOM


# ---------------------------------------------------------------------------
# VisualSystemRegistry
# ---------------------------------------------------------------------------

class TestVisualSystemRegistry:
    def test_register_returns_device_id(self, registry, sample_profile):
        device_id = registry.register(sample_profile)
        assert device_id == sample_profile.device_id

    def test_get_registered_device(self, registry, sample_profile):
        registry.register(sample_profile)
        profile = registry.get_device(sample_profile.device_id)
        assert profile is not None
        assert profile.device_type == HardwareDeviceType.CAMERA_RGB

    def test_get_missing_device_returns_none(self, registry):
        assert registry.get_device("nonexistent") is None

    def test_unregister_existing(self, registry, sample_profile):
        registry.register(sample_profile)
        result = registry.unregister(sample_profile.device_id)
        assert result is True
        assert registry.get_device(sample_profile.device_id) is None

    def test_unregister_missing_returns_false(self, registry):
        assert registry.unregister("nonexistent") is False

    def test_list_devices_all(self, registry, sample_profile):
        registry.register(sample_profile)
        devices = registry.list_devices()
        assert len(devices) == 1

    def test_list_devices_filter_by_type(self, registry, sample_profile):
        registry.register(sample_profile)
        rgb_devices = registry.list_devices(device_type=HardwareDeviceType.CAMERA_RGB)
        assert len(rgb_devices) == 1
        depth_devices = registry.list_devices(device_type=HardwareDeviceType.CAMERA_DEPTH)
        assert len(depth_devices) == 0

    def test_list_devices_filter_by_status(self, registry, sample_profile):
        sample_profile.health_status = "healthy"
        registry.register(sample_profile)
        healthy = registry.list_devices(status="healthy")
        assert len(healthy) == 1
        unhealthy = registry.list_devices(status="unhealthy")
        assert len(unhealthy) == 0

    def test_get_device_health(self, registry, sample_profile):
        sample_profile.health_status = "healthy"
        registry.register(sample_profile)
        health = registry.get_device_health(sample_profile.device_id)
        assert health["health_status"] == "healthy"
        assert "recommendation" in health

    def test_get_device_health_missing(self, registry):
        health = registry.get_device_health("nonexistent")
        assert "error" in health

    def test_get_topology(self, registry, sample_profile):
        registry.register(sample_profile)
        topology = registry.get_topology()
        assert "nodes" in topology
        assert "edges" in topology
        assert topology["total_devices"] == 1

    def test_register_sets_timestamps(self, registry, sample_profile):
        registry.register(sample_profile)
        profile = registry.get_device(sample_profile.device_id)
        assert profile.registered_at is not None
        assert profile.last_seen is not None


# ---------------------------------------------------------------------------
# DeviceDriverManager
# ---------------------------------------------------------------------------

class TestDeviceDriverManager:
    def test_load_builtin_driver(self, driver_manager):
        driver = driver_manager.load_driver(
            HardwareDeviceType.CAMERA_RGB, ConnectionProtocol.USB
        )
        assert driver["driver_id"] == "murphy_usb_rgb_v1"

    def test_load_depth_driver(self, driver_manager):
        driver = driver_manager.load_driver(
            HardwareDeviceType.CAMERA_DEPTH, ConnectionProtocol.USB3
        )
        assert "depth" in driver["driver_id"]

    def test_load_unknown_returns_generic(self, driver_manager):
        driver = driver_manager.load_driver(
            HardwareDeviceType.ENDOSCOPE, ConnectionProtocol.COAXIAL
        )
        assert "generic" in driver["driver_id"]
        assert "recommendation" in driver

    def test_create_murphy_native_driver_no_sandbox(self, sample_profile):
        mgr = DeviceDriverManager(causality_sandbox=None)
        driver = mgr.create_murphy_native_driver(sample_profile)
        assert "driver_id" in driver
        assert driver["device_id"] == sample_profile.device_id
        assert driver["status"] in ("stub", "sandbox_approved", "sandbox_rejected", "sandbox_skipped")

    def test_create_murphy_native_driver_creates_custom(self, sample_profile):
        mgr = DeviceDriverManager(causality_sandbox=None)
        driver = mgr.create_murphy_native_driver(sample_profile)
        assert driver["device_type"] == HardwareDeviceType.CAMERA_RGB.value

    def test_list_supported_drivers(self, driver_manager):
        drivers = driver_manager.list_supported_drivers()
        assert isinstance(drivers, list)
        assert len(drivers) >= 4
        sources = {d["source"] for d in drivers}
        assert "builtin" in sources

    def test_custom_driver_appears_in_list(self, sample_profile):
        mgr = DeviceDriverManager(causality_sandbox=None)
        mgr.create_murphy_native_driver(sample_profile)
        drivers = mgr.list_supported_drivers()
        custom_drivers = [d for d in drivers if d.get("source") == "custom"]
        assert len(custom_drivers) >= 1


# ---------------------------------------------------------------------------
# HardwareHealthMonitor
# ---------------------------------------------------------------------------

class TestHardwareHealthMonitor:
    def test_start_monitoring(self, health_monitor):
        health_monitor.start_monitoring("dev-001")
        report = health_monitor.get_health_report()
        assert "dev-001" in report["devices"]

    def test_stop_monitoring(self, health_monitor):
        health_monitor.start_monitoring("dev-001")
        health_monitor.stop_monitoring("dev-001")
        report = health_monitor.get_health_report()
        assert report["devices"]["dev-001"]["monitoring_active"] is False

    def test_record_healthy_sample(self, health_monitor):
        health_monitor.start_monitoring("dev-001")
        health_monitor.record_health_sample(
            "dev-001",
            uptime_seconds=3600.0,
            frame_drops=0,
            latency_ms=5.0,
            temperature_celsius=35.0,
            bandwidth_mbps=100.0,
        )
        report = health_monitor.get_health_report()
        metrics = report["devices"]["dev-001"]["metrics"]
        assert metrics["uptime_seconds"] == 3600.0
        assert report["devices"]["dev-001"]["consecutive_failures"] == 0

    def test_record_unhealthy_sample_increments_failures(self, health_monitor):
        health_monitor.start_monitoring("dev-002")
        health_monitor.set_alert_threshold("dev-002", "latency_ms", 50.0)
        health_monitor.record_health_sample("dev-002", latency_ms=200.0)
        report = health_monitor.get_health_report()
        assert report["devices"]["dev-002"]["consecutive_failures"] >= 1

    def test_set_alert_threshold(self, health_monitor):
        health_monitor.set_alert_threshold("dev-001", "temperature_celsius", 80.0)
        health_monitor.start_monitoring("dev-001")
        health_monitor.record_health_sample("dev-001", temperature_celsius=50.0)
        report = health_monitor.get_health_report()
        assert report["devices"]["dev-001"]["consecutive_failures"] == 0

    def test_health_report_structure(self, health_monitor):
        report = health_monitor.get_health_report()
        assert "devices" in report
        assert "total_monitored" in report
        assert "generated_at" in report

    def test_emergency_stop_triggered_after_repeated_failures(self):
        class _FakeStop:
            def __init__(self):
                self.activated = False
                self.reason = ""
            def activate_global(self, reason):
                self.activated = True
                self.reason = reason

        fake_stop = _FakeStop()
        monitor = HardwareHealthMonitor(emergency_stop=fake_stop)
        monitor.start_monitoring("failing-device")
        monitor.set_alert_threshold("failing-device", "latency_ms", 10.0)

        for _ in range(4):
            monitor.record_health_sample("failing-device", latency_ms=500.0)

        assert fake_stop.activated is True
        assert "failing-device" in fake_stop.reason


# ---------------------------------------------------------------------------
# HardwareOnboardingPipeline
# ---------------------------------------------------------------------------

class TestHardwareOnboardingPipeline:
    def test_onboard_device_returns_session(self, pipeline, sample_profile):
        session = pipeline.onboard_device(sample_profile)
        assert isinstance(session, OnboardingSession)

    def test_onboard_device_reaches_registered(self, pipeline, sample_profile):
        session = pipeline.onboard_device(sample_profile)
        assert session.stage == OnboardingStage.REGISTERED

    def test_onboard_device_populates_steps(self, pipeline, sample_profile):
        session = pipeline.onboard_device(sample_profile)
        assert len(session.steps_completed) > 0

    def test_onboard_device_no_errors_on_success(self, pipeline, sample_profile):
        session = pipeline.onboard_device(sample_profile)
        assert session.errors == []

    def test_onboard_device_sets_completed_at(self, pipeline, sample_profile):
        session = pipeline.onboard_device(sample_profile)
        assert session.completed_at is not None

    def test_validate_device(self, pipeline, sample_profile):
        session = OnboardingSession(
            session_id=str(uuid.uuid4()),
            device_id=sample_profile.device_id,
            stage=OnboardingStage.VALIDATING,
            started_at="2024-01-01T00:00:00+00:00",
        )
        result = pipeline.validate_device(session)
        assert result["success"] is True
        assert "latency_ms" in result
        assert "recommendation" in result

    def test_calibrate_device(self, pipeline, sample_profile):
        session = OnboardingSession(
            session_id=str(uuid.uuid4()),
            device_id=sample_profile.device_id,
            stage=OnboardingStage.CALIBRATING,
            started_at="2024-01-01T00:00:00+00:00",
        )
        result = pipeline.calibrate_device(session)
        assert result["success"] is True
        assert "intrinsics" in result
        assert "recommendation" in result

    def test_register_device_persists_to_registry(self, pipeline, sample_profile):
        pipeline.onboard_device(sample_profile)
        profile = pipeline._registry.get_device(sample_profile.device_id)
        assert profile is not None

    def test_quarantine_device(self, pipeline, sample_profile):
        pipeline.onboard_device(sample_profile)
        pipeline.quarantine_device(sample_profile.device_id, "Test quarantine")
        profile = pipeline._registry.get_device(sample_profile.device_id)
        assert profile is not None
        assert profile.health_status == OnboardingStage.QUARANTINED.value

    def test_wingman_pair_created_on_success(self, sample_profile):
        from wingman_protocol import WingmanProtocol
        wp = WingmanProtocol()
        pl = HardwareOnboardingPipeline(wingman_protocol=wp)
        session = pl.onboard_device(sample_profile)
        assert session.wingman_pair_id is not None

    def test_run_stage_identifying(self, pipeline, sample_profile):
        session = OnboardingSession(
            session_id=str(uuid.uuid4()),
            device_id=sample_profile.device_id,
            stage=OnboardingStage.IDENTIFYING,
            started_at="2024-01-01T00:00:00+00:00",
        )
        result = pipeline.run_stage(session, OnboardingStage.IDENTIFYING)
        assert result["success"] is True

    def test_multiple_devices_independent(self, pipeline):
        profiles = [
            DeviceProfile(
                device_id=f"dev-{i}",
                device_type=HardwareDeviceType.CAMERA_RGB,
                connection_protocol=ConnectionProtocol.USB,
                manufacturer="Acme",
                model=f"RGB-{i}",
                serial_number=f"SN-{i}",
                firmware_version="1.0",
            )
            for i in range(3)
        ]
        sessions = [pipeline.onboard_device(p) for p in profiles]
        assert all(s.stage == OnboardingStage.REGISTERED for s in sessions)
        assert len({s.session_id for s in sessions}) == 3

    def test_thread_safe_onboarding(self, pipeline):
        errors: list = []
        sessions: list = []
        lock = threading.Lock()

        def onboard(i: int) -> None:
            try:
                profile = DeviceProfile(
                    device_id=f"thread-dev-{i}",
                    device_type=HardwareDeviceType.CAMERA_RGB,
                    connection_protocol=ConnectionProtocol.USB,
                    manufacturer="Acme",
                    model="RGB-T",
                    serial_number=f"SN-T-{i}",
                    firmware_version="1.0",
                )
                session = pipeline.onboard_device(profile)
                with lock:
                    sessions.append(session)
            except Exception as exc:
                with lock:
                    errors.append(exc)

        threads = [threading.Thread(target=onboard, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        assert len(sessions) == 5
