"""
Comprehensive tests for the PiCar-X AI Butler — Reason.

Covers:
  - Hardware abstraction (picarx_hardware.py)
  - Protocol client (PiCarXClient in protocol_clients.py)
  - Butler module (picarx_butler.py)
  - Rosetta identity registration
  - HITL notification (chronological ordering)
  - Voice command dispatch
  - Battery management / charge requests
  - Patrol lifecycle
  - Learning engine feedback
  - Emergency stop
  - Soul.md existence
"""

import os
import threading
import time
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from robotics.robotics_models import (
    ActuatorCommand,
    ConnectionConfig,
    RobotConfig,
    RobotStatus,
    RobotType,
)
from robotics.protocol_clients import (
    CLIENT_REGISTRY,
    PiCarXClient,
    create_client,
)
from robotics.picarx_hardware import (
    BATTERY_CRITICAL_VOLTAGE,
    BATTERY_FULL_VOLTAGE,
    CHARGE_REQUEST_THRESHOLD,
    CameraState,
    MotorState,
    PiCarXHardware,
    PiCarXPin,
    SensorSnapshot,
)
from robotics.picarx_butler import (
    AGENT_NAME,
    AGENT_VERSION,
    ORGANISATION,
    OWNER,
    ROSETTA_ID,
    HITLNotification,
    PatrolStatus,
    PiCarXButler,
    ReasonState,
    ReasonStatus,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def hw():
    """Fresh PiCarXHardware in stub mode."""
    h = PiCarXHardware()
    h.connect()
    yield h
    h.disconnect()


@pytest.fixture
def picarx_config():
    return RobotConfig(
        robot_id="picarx_01",
        name="Test PiCar-X",
        robot_type=RobotType.PICARX,
        connection=ConnectionConfig(hostname="192.168.1.100", port=22),
        capabilities=[
            "sense_ultrasonic", "sense_grayscale", "sense_battery",
            "sense_battery_percent",
        ],
    )


@pytest.fixture
def mock_hitl_items():
    """Fake HITL queue items in non-chronological order."""
    return [
        {
            "id": "hitl-aaa",
            "type": "campaign_approval",
            "title": "Ad spend $500",
            "description": "Approve ad campaign",
            "priority": "high",
            "status": "pending",
            "created_at": "2026-04-14T03:00:00Z",
        },
        {
            "id": "hitl-bbb",
            "type": "proposal_approval",
            "title": "Contractor proposal",
            "description": "Approve contractor",
            "priority": "normal",
            "status": "pending",
            "created_at": "2026-04-14T01:00:00Z",  # OLDER — should come first
        },
        {
            "id": "hitl-ccc",
            "type": "step_approval",
            "title": "Deploy v2.1",
            "description": "Approve deployment",
            "priority": "critical",
            "status": "approved",  # Already approved — should be filtered
            "created_at": "2026-04-14T02:00:00Z",
        },
    ]


@pytest.fixture
def tts_log():
    """Capture TTS announcements."""
    log: list = []
    def capture(text: str):
        log.append(text)
    return log, capture


@pytest.fixture
def learning_mock():
    mock = MagicMock()
    mock.record_metric = MagicMock()
    return mock


@pytest.fixture
def butler(mock_hitl_items, tts_log, learning_mock):
    """PiCarXButler with all mocks wired."""
    log, tts_fn = tts_log
    b = PiCarXButler(
        hitl_fetch_fn=lambda: mock_hitl_items,
        tts_fn=tts_fn,
        learning_engine=learning_mock,
    )
    yield b
    if b._state.status == ReasonStatus.RUNNING:
        b.stop()


# ===================================================================
# 1. Hardware Abstraction Tests
# ===================================================================

class TestPiCarXHardware:

    def test_connect_disconnect(self, hw):
        assert hw.is_connected
        assert hw.is_stub  # No SDK installed → stub mode
        hw.disconnect()
        assert not hw.is_connected

    def test_motor_speed_clamp(self, hw):
        hw.set_speed(200, -200)
        ms = hw.get_motor_state()
        assert ms.speed_left == 100
        assert ms.speed_right == -100

    def test_steering_clamp(self, hw):
        hw.set_steering(99.9)
        ms = hw.get_motor_state()
        assert ms.steering_angle == 40.0
        hw.set_steering(-99.9)
        assert hw.get_motor_state().steering_angle == -40.0

    def test_camera_pan_tilt(self, hw):
        hw.set_camera_pan(45.0)
        hw.set_camera_tilt(30.0)
        cs = hw.get_camera_state()
        assert cs.pan == 45.0
        assert cs.tilt == 30.0

    def test_camera_pan_clamp(self, hw):
        hw.set_camera_pan(200.0)
        assert hw.get_camera_state().pan == 90.0

    def test_camera_tilt_clamp(self, hw):
        hw.set_camera_tilt(100.0)
        assert hw.get_camera_state().tilt == 65.0

    def test_stop_zeros_motors(self, hw):
        hw.set_speed(50, 60)
        hw.stop()
        ms = hw.get_motor_state()
        assert ms.speed_left == 0 and ms.speed_right == 0

    def test_read_ultrasonic(self, hw):
        val = hw.read_ultrasonic()
        assert isinstance(val, float)
        assert val > 0  # stub returns random 5..200

    def test_read_grayscale(self, hw):
        gs = hw.read_grayscale()
        assert len(gs) == 3
        assert all(isinstance(v, int) for v in gs)

    def test_read_battery(self, hw):
        v = hw.read_battery_voltage()
        assert isinstance(v, float)
        assert v > 0

    def test_read_all_snapshot(self, hw):
        snap = hw.read_all()
        assert isinstance(snap, SensorSnapshot)
        assert snap.battery_voltage > 0
        assert 0.0 <= snap.battery_percent <= 100.0
        assert snap.timestamp > 0

    def test_idempotent_connect(self, hw):
        # Already connected from fixture
        assert hw.connect() is True
        assert hw.is_connected

    def test_picarx_pin_enum(self):
        assert PiCarXPin.SERVO_STEERING.value == "P0"
        assert PiCarXPin.BATTERY_ADC.value == "A4"


# ===================================================================
# 2. Protocol Client Tests
# ===================================================================

class TestPiCarXClient:

    def test_picarx_in_registry(self):
        assert RobotType.PICARX in CLIENT_REGISTRY
        assert CLIENT_REGISTRY[RobotType.PICARX] is PiCarXClient

    def test_create_client_factory(self, picarx_config):
        client = create_client(picarx_config)
        assert isinstance(client, PiCarXClient)

    def test_connect_disconnect(self, picarx_config):
        client = PiCarXClient(picarx_config)
        assert client.connect()
        assert client.status == RobotStatus.CONNECTED
        assert client.disconnect()
        assert client.status == RobotStatus.DISCONNECTED

    def test_read_sensor_stub(self, picarx_config):
        client = PiCarXClient(picarx_config)
        client.connect()
        reading = client.read_sensor("us_01", "ultrasonic")
        assert reading.robot_id == "picarx_01"
        assert reading.sensor_type == "ultrasonic"

    def test_read_sensor_with_hardware_backend(self, picarx_config, hw):
        client = PiCarXClient(picarx_config, backend=hw)
        client.connect()
        reading = client.read_sensor("bat_01", "battery")
        assert reading.unit == "V"
        assert reading.value > 0

    def test_execute_drive_command(self, picarx_config, hw):
        client = PiCarXClient(picarx_config, backend=hw)
        client.connect()
        cmd = ActuatorCommand(
            robot_id="picarx_01", actuator_id="motors",
            command_type="drive", parameters={"left": 30, "right": 30})
        result = client.execute_command(cmd)
        assert result.success

    def test_execute_steer_command(self, picarx_config, hw):
        client = PiCarXClient(picarx_config, backend=hw)
        client.connect()
        cmd = ActuatorCommand(
            robot_id="picarx_01", actuator_id="steering",
            command_type="steer", parameters={"angle": 15.0})
        result = client.execute_command(cmd)
        assert result.success

    def test_execute_stop_command(self, picarx_config, hw):
        client = PiCarXClient(picarx_config, backend=hw)
        client.connect()
        cmd = ActuatorCommand(
            robot_id="picarx_01", actuator_id="motors",
            command_type="stop", parameters={})
        result = client.execute_command(cmd)
        assert result.success

    def test_execute_cam_pan(self, picarx_config, hw):
        client = PiCarXClient(picarx_config, backend=hw)
        client.connect()
        cmd = ActuatorCommand(
            robot_id="picarx_01", actuator_id="camera",
            command_type="cam_pan", parameters={"angle": 25.0})
        result = client.execute_command(cmd)
        assert result.success

    def test_emergency_stop(self, picarx_config, hw):
        client = PiCarXClient(picarx_config, backend=hw)
        client.connect()
        assert client.emergency_stop()
        assert client.status == RobotStatus.EMERGENCY_STOP

    def test_get_status_dict(self, picarx_config):
        client = PiCarXClient(picarx_config)
        s = client.get_status()
        assert s["robot_id"] == "picarx_01"
        assert s["robot_type"] == "picarx"


# ===================================================================
# 3. Butler — Identity & Rosetta Tests
# ===================================================================

class TestReasonIdentity:

    def test_rosetta_id(self, butler):
        assert ROSETTA_ID == "reason"

    def test_agent_name(self, butler):
        assert AGENT_NAME == "Reason"

    def test_owner(self, butler):
        assert OWNER == "Corey Post"

    def test_get_rosetta_identity(self, butler):
        ident = butler.get_rosetta_identity()
        assert ident["agent_id"] == "reason"
        assert ident["name"] == "Reason"
        assert ident["owner"] == "Corey Post"
        assert ident["agent_type"] == "automation"
        assert ident["reports_to"] == "Corey Post"
        assert "hitl_notify" in ident["authorised_actions"]

    def test_employee_contract(self, butler):
        contract = butler.build_employee_contract()
        assert contract["role_title"] == "AI Butler"
        assert "Corey Post" in contract["role_description"]
        assert contract["management_layer"] == "individual"
        assert contract["reports_to"] == "Corey Post"

    def test_repr(self, butler):
        r = repr(butler)
        assert "Reason" in r
        assert "reason" in r

    def test_rosetta_registers_on_init(self):
        mgr = MagicMock()
        mgr.save_state = MagicMock(return_value="reason")
        b = PiCarXButler(rosetta_manager=mgr)
        mgr.save_state.assert_called_once()
        call_args = mgr.save_state.call_args
        state = call_args[0][0]
        assert state.identity.agent_id == "reason"
        assert state.identity.name == "Reason"


# ===================================================================
# 4. HITL Notification Tests
# ===================================================================

class TestHITLNotification:

    def test_fetch_filters_non_pending(self, butler):
        items = butler.fetch_pending_hitl()
        ids = [n.hitl_id for n in items]
        assert "hitl-ccc" not in ids  # approved item filtered out

    def test_fetch_chronological_order(self, butler):
        items = butler.fetch_pending_hitl()
        assert len(items) == 2
        # hitl-bbb (01:00) should come before hitl-aaa (03:00)
        assert items[0].hitl_id == "hitl-bbb"
        assert items[1].hitl_id == "hitl-aaa"

    def test_announce_hitl_tts(self, butler, tts_log):
        log, _ = tts_log
        announcements = butler.announce_hitl()
        assert len(announcements) == 3  # header + 2 items
        assert "2 pending approvals" in announcements[0]
        # TTS was called
        assert len(log) == 3

    def test_announce_empty_queue(self, tts_log, learning_mock):
        log, tts_fn = tts_log
        b = PiCarXButler(
            hitl_fetch_fn=lambda: [],
            tts_fn=tts_fn,
            learning_engine=learning_mock,
        )
        announcements = b.announce_hitl()
        assert announcements == []
        assert len(log) == 0

    def test_hitl_items_marked_announced(self, butler):
        butler.announce_hitl()
        items = butler._state.hitl_pending
        assert all(n.announced for n in items)

    def test_hitl_announced_counter(self, butler):
        butler.announce_hitl()
        assert butler._state.total_hitl_announced == 2


# ===================================================================
# 5. Voice Command Tests
# ===================================================================

class TestVoiceCommands:

    def test_hitl_voice(self, butler):
        result = butler.handle_voice("what needs approval")
        assert result["type"] == "hitl"
        assert result["count"] == 2

    def test_battery_voice(self, butler):
        result = butler.handle_voice("how much battery")
        assert result["type"] == "battery"
        assert "voltage" in result

    def test_patrol_voice(self, butler):
        result = butler.handle_voice("go patrol the house")
        assert result["type"] == "patrol"

    def test_stop_voice(self, butler):
        result = butler.handle_voice("stop now")
        assert result["type"] == "stop"

    def test_charge_voice(self, butler):
        result = butler.handle_voice("go charge yourself")
        assert result["type"] == "charge"

    def test_status_voice(self, butler):
        result = butler.handle_voice("give me a status report")
        assert result["type"] == "status"
        assert result["agent_id"] == "reason"

    def test_automations_voice(self, butler):
        result = butler.handle_voice("what automations are running")
        assert result["type"] == "automations"

    def test_help_voice(self, butler):
        result = butler.handle_voice("help")
        assert result["type"] == "help"
        assert len(result["capabilities"]) >= 7

    def test_unknown_voice(self, butler):
        result = butler.handle_voice("xyzzy foobar")
        assert result["type"] == "unknown"

    def test_voice_counter_increments(self, butler):
        butler.handle_voice("status")
        butler.handle_voice("battery")
        assert butler._state.total_voice_commands == 2


# ===================================================================
# 6. Battery & Charge Tests
# ===================================================================

class TestBatteryManagement:

    def test_battery_status_with_hardware(self, butler, hw):
        butler._hw = hw
        status = butler.get_battery_status()
        assert "voltage" in status
        assert "percent" in status
        assert isinstance(status["needs_charge"], bool)

    def test_request_charge(self, butler, tts_log):
        log, _ = tts_log
        butler.request_charge()
        assert butler._state.charge_requested is True
        assert butler._state.patrol_status == PatrolStatus.RETURNING_TO_CHARGE
        assert any("charger" in msg.lower() for msg in log)

    def test_charge_emits_learning(self, butler, learning_mock):
        butler.request_charge()
        learning_mock.record_metric.assert_called()
        call_name = learning_mock.record_metric.call_args[0][0]
        assert "charge_requested" in call_name


# ===================================================================
# 7. Patrol Tests
# ===================================================================

class TestPatrol:

    def test_start_patrol(self, butler):
        butler.start_patrol()
        assert butler._state.patrol_status == PatrolStatus.PATROLLING

    def test_stop_patrol(self, butler):
        butler.start_patrol()
        butler.stop_patrol()
        assert butler._state.patrol_status == PatrolStatus.IDLE

    def test_start_patrol_idempotent(self, butler):
        butler.start_patrol()
        butler.start_patrol()  # should not crash
        assert butler._state.patrol_status == PatrolStatus.PATROLLING

    def test_emergency_stop(self, butler):
        butler.start_patrol()
        butler.emergency_stop()
        assert butler._state.patrol_status == PatrolStatus.EMERGENCY_STOPPED


# ===================================================================
# 8. Lifecycle Tests
# ===================================================================

class TestLifecycle:

    def test_start_stop(self, butler):
        butler.start()
        assert butler._state.status == ReasonStatus.RUNNING
        assert len(butler._threads) == 3
        butler.stop()
        assert butler._state.status == ReasonStatus.STOPPED

    def test_start_idempotent(self, butler):
        butler.start()
        assert butler.start() is True
        butler.stop()

    def test_full_status(self, butler):
        butler.start()
        status = butler.get_full_status()
        assert status["agent_id"] == "reason"
        assert status["name"] == "Reason"
        assert status["owner"] == "Corey Post"
        assert status["status"] == "running"
        butler.stop()


# ===================================================================
# 9. Learning Feedback Tests
# ===================================================================

class TestLearningFeedback:

    def test_learning_on_voice(self, butler, learning_mock):
        butler.handle_voice("status")
        learning_mock.record_metric.assert_called()
        names = [c[0][0] for c in learning_mock.record_metric.call_args_list]
        assert any("voice_command" in n for n in names)

    def test_learning_on_hitl_announce(self, butler, learning_mock):
        butler.announce_hitl()
        names = [c[0][0] for c in learning_mock.record_metric.call_args_list]
        assert any("hitl_announced" in n for n in names)

    def test_learning_on_patrol(self, butler, learning_mock):
        butler.start_patrol()
        names = [c[0][0] for c in learning_mock.record_metric.call_args_list]
        assert any("patrol_started" in n for n in names)

    def test_learning_counter(self, butler, learning_mock):
        butler.handle_voice("battery")
        butler.announce_hitl()
        assert butler._state.total_learning_events >= 2


# ===================================================================
# 10. Soul.md Tests
# ===================================================================

class TestSoulMd:

    def test_soul_md_exists(self):
        soul_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "..", "src", "robotics", "soul.md"
        )
        # Also try the direct path
        alt_path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "src", "robotics", "soul.md"
        )
        found = os.path.exists(soul_path) or os.path.exists(alt_path)
        # Fallback: search upward
        if not found:
            base = os.path.dirname(__file__)
            for _ in range(5):
                candidate = os.path.join(base, "src", "robotics", "soul.md")
                if os.path.exists(candidate):
                    found = True
                    break
                base = os.path.dirname(base)
        assert found, "soul.md must exist in src/robotics/"

    def test_soul_md_content(self):
        """Verify soul.md contains Reason's core identity."""
        base = os.path.dirname(__file__)
        content = ""
        for _ in range(5):
            candidate = os.path.join(base, "src", "robotics", "soul.md")
            if os.path.exists(candidate):
                with open(candidate, encoding="utf-8") as f:
                    content = f.read()
                break
            base = os.path.dirname(base)
        if not content:
            pytest.skip("soul.md not found in traversal")
        assert "Reason" in content
        assert "reason" in content.lower()
        assert "Corey Post" in content
        assert "HITL" in content
        assert "chronological" in content.lower()
        assert "loyal" in content.lower()
        assert "butler" in content.lower()
        assert "voice" in content.lower()
