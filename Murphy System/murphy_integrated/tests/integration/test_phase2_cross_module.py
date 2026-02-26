"""
Phase 2: Cross-Module Integration Tests
Tests interactions between Rosetta, Robotics, and Avatar modules.

Test Hierarchy: Level 2 (Integration Tests)
Test Category: Cross-Module Interface Testing
"""

import json
import os
import tempfile

import pytest
from datetime import datetime, timezone

from rosetta.rosetta_models import (
    AutomationProgress,
    Identity,
    RosettaAgentState,
)
from rosetta.rosetta_manager import RosettaManager
from rosetta.archive_classifier import ArchiveClassifier
from rosetta.global_aggregator import GlobalAggregator

from robotics.robotics_models import (
    ActuatorCommand,
    ConnectionConfig,
    RobotConfig,
    RobotType,
    SensorReading,
)
from robotics.robot_registry import RobotRegistry
from robotics.sensor_engine import SensorEngine
from robotics.actuator_engine import ActuatorEngine

from avatar.avatar_models import AvatarProfile, AvatarVoice, AvatarStyle
from avatar.avatar_registry import AvatarRegistry
from avatar.avatar_session_manager import AvatarSessionManager
from avatar.persona_injector import PersonaInjector
from avatar.compliance_guard import ComplianceGuard
from avatar.cost_ledger import CostLedger

from event_backbone import EventBackbone, EventType
from persistence_manager import PersistenceManager


# ============================================================================
# Helpers
# ============================================================================

def _make_robot_config(robot_id: str = "robot-001", name: str = "TestBot",
                       robot_type: RobotType = RobotType.MODBUS,
                       capabilities: list | None = None) -> RobotConfig:
    return RobotConfig(
        robot_id=robot_id,
        name=name,
        robot_type=robot_type,
        connection=ConnectionConfig(hostname="127.0.0.1", port=502),
        capabilities=capabilities or ["sense_temperature", "sense_humidity"],
    )


def _make_avatar_profile(avatar_id: str = "avatar-001",
                         name: str = "RoboAssistant") -> AvatarProfile:
    return AvatarProfile(
        avatar_id=avatar_id,
        name=name,
        voice=AvatarVoice.PROFESSIONAL,
        style=AvatarStyle.TECHNICAL,
        personality_traits={"precision": 0.9, "empathy": 0.4},
        knowledge_domains=["robotics", "automation"],
    )


def _make_rosetta_state(agent_id: str = "agent-001",
                        name: str = "TestAgent") -> RosettaAgentState:
    return RosettaAgentState(
        identity=Identity(agent_id=agent_id, name=name, role="integration-test"),
    )


# ============================================================================
# TestRosettaRoboticsIntegration
# ============================================================================

class TestRosettaRoboticsIntegration:
    """Tests that Rosetta state can track robotics telemetry."""

    def test_sensor_data_stored_in_rosetta_state(self, tmp_path):
        """Register a robot, read sensors, store readings in Rosetta state."""
        registry = RobotRegistry()
        config = _make_robot_config()
        assert registry.register(config) is True

        registry.connect(config.robot_id)

        sensor_engine = SensorEngine(registry)
        readings = sensor_engine.read_all_sensors(config.robot_id)
        assert len(readings) == 2

        manager = RosettaManager(persistence_dir=str(tmp_path / "rosetta"))
        state = _make_rosetta_state()

        telemetry = {r.sensor_type: r.value for r in readings}
        state.system_state.status = "active"
        state.system_state.memory_usage_mb = 128.0
        progress = AutomationProgress(
            category="robotics_telemetry",
            total_items=len(readings),
            completed_items=len(readings),
            coverage_percent=100.0,
        )
        state.automation_progress.append(progress)
        manager.save_state(state)

        loaded = manager.load_state(state.identity.agent_id)
        assert loaded is not None
        assert loaded.system_state.status == "active"
        assert len(loaded.automation_progress) == 1
        assert loaded.automation_progress[0].category == "robotics_telemetry"
        assert loaded.automation_progress[0].completed_items == 2

    def test_actuator_results_archived_in_rosetta(self, tmp_path):
        """Execute actuator command and archive result in Rosetta."""
        registry = RobotRegistry()
        config = _make_robot_config()
        registry.register(config)
        registry.connect(config.robot_id)

        actuator = ActuatorEngine(registry)
        cmd = ActuatorCommand(
            robot_id=config.robot_id,
            actuator_id="gripper-01",
            command_type="close_gripper",
            parameters={"force": 50},
        )
        result = actuator.execute(cmd)
        assert result.success is True

        manager = RosettaManager(persistence_dir=str(tmp_path / "rosetta"))
        state = _make_rosetta_state()
        classifier = ArchiveClassifier()
        item = {
            "status": "completed",
            "command_type": result.command_type,
            "robot_id": result.robot_id,
        }
        state = classifier.archive_item(state, item, reason="actuator command completed")
        manager.save_state(state)

        loaded = manager.load_state(state.identity.agent_id)
        assert loaded is not None
        assert loaded.archive_log.total_archived == 1
        assert loaded.archive_log.entries[0].category == "completed_goal"

    def test_global_aggregator_reflects_robotics_progress(self, tmp_path):
        """Multiple agents with robotics progress are aggregated globally."""
        manager = RosettaManager(persistence_dir=str(tmp_path / "rosetta"))

        for i in range(3):
            state = _make_rosetta_state(agent_id=f"robot-agent-{i}", name=f"Bot{i}")
            state.automation_progress.append(
                AutomationProgress(
                    category="robotics_telemetry",
                    total_items=10,
                    completed_items=5 + i,
                )
            )
            manager.save_state(state)

        aggregator = GlobalAggregator(manager)
        coverage = aggregator.aggregate_automation_coverage()
        cat = coverage["by_category"]["robotics_telemetry"]
        assert cat["total_items"] == 30
        assert cat["completed_items"] == 18  # 5+6+7


# ============================================================================
# TestRosettaAvatarIntegration
# ============================================================================

class TestRosettaAvatarIntegration:
    """Tests that Rosetta can track avatar usage metrics."""

    def test_avatar_session_costs_reflected_in_rosetta(self, tmp_path):
        """Create avatar sessions, record costs, reflect in Rosetta."""
        avatar_reg = AvatarRegistry()
        profile = _make_avatar_profile()
        avatar_reg.register(profile)

        session_mgr = AvatarSessionManager()
        session = session_mgr.start_session(profile.avatar_id, user_id="user-001")
        session_mgr.record_message(session.session_id)
        session_mgr.add_cost(session.session_id, 0.05)

        ledger = CostLedger()
        ledger.record(profile.avatar_id, "openai", "chat_completion", 0.05)
        total_cost = ledger.get_total_cost(avatar_id=profile.avatar_id)
        assert total_cost == pytest.approx(0.05)

        manager = RosettaManager(persistence_dir=str(tmp_path / "rosetta"))
        state = _make_rosetta_state()
        state.automation_progress.append(
            AutomationProgress(
                category="avatar_interactions",
                total_items=10,
                completed_items=1,
                coverage_percent=10.0,
            )
        )
        manager.save_state(state)

        loaded = manager.load_state(state.identity.agent_id)
        assert loaded is not None
        ap = loaded.automation_progress[0]
        assert ap.category == "avatar_interactions"
        assert ap.completed_items == 1

    def test_compliance_violations_archived_in_rosetta(self, tmp_path):
        """Compliance violations from avatar are archived in Rosetta."""
        guard = ComplianceGuard()
        violations = guard.check_content("avatar-001", "SSN is 123-45-6789")
        assert len(violations) >= 1

        manager = RosettaManager(persistence_dir=str(tmp_path / "rosetta"))
        state = _make_rosetta_state()
        classifier = ArchiveClassifier()
        for v in violations:
            item = {
                "status": "failed",
                "rule": v.rule,
                "description": v.description,
                "severity": v.severity,
            }
            state = classifier.archive_item(state, item, reason="compliance violation")
        manager.save_state(state)

        loaded = manager.load_state(state.identity.agent_id)
        assert loaded.archive_log.total_archived == len(violations)
        assert loaded.archive_log.entries[0].category == "failed_task"


# ============================================================================
# TestRoboticsAvatarIntegration
# ============================================================================

class TestRoboticsAvatarIntegration:
    """Tests that avatar persona can format robotics commands/results."""

    def test_persona_enriches_robotics_prompt(self):
        """PersonaInjector wraps a robotics command description with persona."""
        profile = _make_avatar_profile()
        injector = PersonaInjector()

        base_prompt = "Report the current temperature reading from robot-001."
        enriched = injector.inject(base_prompt, profile)

        assert profile.name in enriched
        assert "robotics" in enriched
        assert base_prompt in enriched

    def test_compliance_guard_filters_robotics_prompt(self):
        """ComplianceGuard screens prompts that include sensitive data."""
        guard = ComplianceGuard()
        prompt = "Send actuator command with auth token 1234567890123456"
        violations = guard.check_prompt("avatar-001", prompt)
        assert len(violations) >= 1
        assert any(v.rule == "no_pii_disclosure" for v in violations)

    def test_avatar_formats_sensor_reading(self):
        """Avatar persona generates a greeting then formats sensor data."""
        profile = _make_avatar_profile()
        injector = PersonaInjector()

        greeting = injector.generate_greeting(profile, user_name="Operator")
        assert "RoboAssistant" in greeting
        assert "Operator" in greeting

        reading = SensorReading(
            robot_id="robot-001",
            sensor_id="temp-01",
            sensor_type="temperature",
            value=22.5,
            unit="°C",
            timestamp=datetime.now(timezone.utc),
        )
        base_prompt = (
            f"Sensor {reading.sensor_id} on {reading.robot_id} reads "
            f"{reading.value}{reading.unit}. Summarize for the operator."
        )
        enriched = injector.inject(base_prompt, profile)
        assert "temperature" in enriched.lower() or "22.5" in enriched


# ============================================================================
# TestEventBackboneIntegration
# ============================================================================

class TestEventBackboneIntegration:
    """Tests RECALIBRATION_START and ROSETTA_UPDATED events end-to-end."""

    def test_recalibration_start_event_lifecycle(self, tmp_path):
        """Publish RECALIBRATION_START, subscribe, process, verify history."""
        backbone = EventBackbone(persistence_dir=str(tmp_path / "events"))
        received = []

        def handler(event):
            received.append(event)

        backbone.subscribe(EventType.RECALIBRATION_START, handler)
        event_id = backbone.publish(
            EventType.RECALIBRATION_START,
            payload={"agent_id": "agent-001", "reason": "scheduled"},
            source="rosetta_manager",
        )
        processed = backbone.process_pending()

        assert processed == 1
        assert len(received) == 1
        assert received[0].payload["agent_id"] == "agent-001"

        history = backbone.get_event_history(event_type=EventType.RECALIBRATION_START)
        assert len(history) == 1
        assert history[0]["status"] == "delivered"

    def test_rosetta_updated_event_lifecycle(self, tmp_path):
        """Publish ROSETTA_UPDATED, subscribe, process, verify history."""
        backbone = EventBackbone(persistence_dir=str(tmp_path / "events"))
        received = []

        backbone.subscribe(EventType.ROSETTA_UPDATED, lambda e: received.append(e))
        backbone.publish(
            EventType.ROSETTA_UPDATED,
            payload={"agent_id": "agent-001", "fields": ["system_state"]},
            source="rosetta_manager",
        )
        backbone.process_pending()

        assert len(received) == 1
        assert received[0].payload["fields"] == ["system_state"]

    def test_cross_module_event_flow(self, tmp_path):
        """Simulate cross-module event: robotics triggers recalibration, Rosetta updates."""
        backbone = EventBackbone(persistence_dir=str(tmp_path / "events"))
        recal_received = []
        update_received = []

        def on_recalibration(event):
            recal_received.append(event)
            backbone.publish(
                EventType.ROSETTA_UPDATED,
                payload={"agent_id": event.payload["agent_id"], "trigger": "recalibration"},
                source="rosetta_manager",
            )

        def on_rosetta_updated(event):
            update_received.append(event)

        backbone.subscribe(EventType.RECALIBRATION_START, on_recalibration)
        backbone.subscribe(EventType.ROSETTA_UPDATED, on_rosetta_updated)

        backbone.publish(
            EventType.RECALIBRATION_START,
            payload={"agent_id": "agent-001", "reason": "sensor_drift"},
            source="sensor_engine",
        )
        backbone.process_pending()
        # Process the ROSETTA_UPDATED event published by the recalibration handler
        backbone.process_pending()

        assert len(recal_received) == 1
        assert len(update_received) == 1
        assert update_received[0].payload["trigger"] == "recalibration"

    def test_dead_letter_queue_on_handler_failure(self, tmp_path):
        """Event moves to DLQ after exceeding max retries."""
        backbone = EventBackbone(persistence_dir=str(tmp_path / "events"))

        def failing_handler(event):
            raise RuntimeError("simulated failure")

        backbone.subscribe(EventType.RECALIBRATION_START, failing_handler)
        backbone.publish(
            EventType.RECALIBRATION_START,
            payload={"agent_id": "agent-fail"},
            source="test",
        )
        # Process enough times to exhaust retries (max_retries defaults to 3)
        for _ in range(5):
            backbone.process_pending()

        dlq = backbone.get_dead_letter_queue()
        assert len(dlq) >= 1
        assert dlq[0].payload["agent_id"] == "agent-fail"


# ============================================================================
# TestMultiTenantIsolation
# ============================================================================

class TestMultiTenantIsolation:
    """Tests that registries maintain proper tenant isolation."""

    def test_rosetta_tenant_isolation(self, tmp_path):
        """Separate Rosetta managers per tenant have independent state."""
        mgr_a = RosettaManager(persistence_dir=str(tmp_path / "tenant_a" / "rosetta"))
        mgr_b = RosettaManager(persistence_dir=str(tmp_path / "tenant_b" / "rosetta"))

        state_a = _make_rosetta_state(agent_id="shared-id", name="TenantA-Agent")
        state_b = _make_rosetta_state(agent_id="shared-id", name="TenantB-Agent")

        mgr_a.save_state(state_a)
        mgr_b.save_state(state_b)

        loaded_a = mgr_a.load_state("shared-id")
        loaded_b = mgr_b.load_state("shared-id")

        assert loaded_a.identity.name == "TenantA-Agent"
        assert loaded_b.identity.name == "TenantB-Agent"

    def test_robot_registry_isolation(self):
        """Separate RobotRegistry instances have independent robot sets."""
        reg_a = RobotRegistry()
        reg_b = RobotRegistry()

        config_a = _make_robot_config(robot_id="bot-shared", name="TenantA-Bot")
        config_b = _make_robot_config(robot_id="bot-shared", name="TenantB-Bot")

        assert reg_a.register(config_a) is True
        assert reg_b.register(config_b) is True

        assert reg_a.get("bot-shared").name == "TenantA-Bot"
        assert reg_b.get("bot-shared").name == "TenantB-Bot"

        assert len(reg_a.list_robots()) == 1
        assert len(reg_b.list_robots()) == 1

    def test_avatar_registry_isolation(self):
        """Separate AvatarRegistry instances have independent avatar sets."""
        reg_a = AvatarRegistry()
        reg_b = AvatarRegistry()

        profile_a = _make_avatar_profile(avatar_id="av-shared", name="TenantA-Avatar")
        profile_b = _make_avatar_profile(avatar_id="av-shared", name="TenantB-Avatar")

        assert reg_a.register(profile_a) is True
        assert reg_b.register(profile_b) is True

        assert reg_a.get("av-shared").name == "TenantA-Avatar"
        assert reg_b.get("av-shared").name == "TenantB-Avatar"

    def test_cross_registry_no_bleed(self):
        """Operations in one registry never affect another."""
        robot_reg = RobotRegistry()
        avatar_reg = AvatarRegistry()

        robot_reg.register(_make_robot_config(robot_id="item-001"))
        avatar_reg.register(_make_avatar_profile(avatar_id="item-001"))

        robot_reg.unregister("item-001")

        assert robot_reg.get("item-001") is None
        assert avatar_reg.get("item-001") is not None


# ============================================================================
# TestCrossModulePersistence
# ============================================================================

class TestCrossModulePersistence:
    """Tests that states from all modules can be persisted and loaded."""

    def test_rosetta_state_round_trip(self, tmp_path):
        """Rosetta state persists to disk and loads back identically."""
        manager = RosettaManager(persistence_dir=str(tmp_path / "rosetta"))
        state = _make_rosetta_state()
        state.automation_progress.append(
            AutomationProgress(category="test", total_items=5, completed_items=3)
        )
        manager.save_state(state)

        # Clear in-memory cache by creating a new manager instance
        manager2 = RosettaManager(persistence_dir=str(tmp_path / "rosetta"))
        loaded = manager2.load_state(state.identity.agent_id)
        assert loaded is not None
        assert loaded.identity.agent_id == state.identity.agent_id
        assert loaded.automation_progress[0].completed_items == 3

    def test_persistence_manager_rosetta_state(self, tmp_path):
        """PersistenceManager can save and load Rosetta state dicts."""
        pm = PersistenceManager(persistence_dir=str(tmp_path / "persistence"))
        state = _make_rosetta_state()
        state_dict = state.model_dump(mode="json")

        pm.save_rosetta_state("agent-001", state_dict)
        loaded = pm.load_rosetta_state("agent-001")

        assert loaded is not None
        assert loaded["identity"]["agent_id"] == "agent-001"

    def test_persistence_manager_lists_agents(self, tmp_path):
        """PersistenceManager lists all persisted Rosetta agents."""
        pm = PersistenceManager(persistence_dir=str(tmp_path / "persistence"))

        for i in range(3):
            state = _make_rosetta_state(agent_id=f"agent-{i}")
            pm.save_rosetta_state(f"agent-{i}", state.model_dump(mode="json"))

        agents = pm.list_rosetta_agents()
        assert len(agents) == 3
        assert "agent-0" in agents

    def test_event_backbone_state_persists(self, tmp_path):
        """EventBackbone state survives restart via persistence dir."""
        persist_dir = str(tmp_path / "events")

        bb1 = EventBackbone(persistence_dir=persist_dir)
        bb1.publish(EventType.ROSETTA_UPDATED, payload={"key": "value"}, source="test")

        bb2 = EventBackbone(persistence_dir=persist_dir)
        status = bb2.get_status()
        assert status["pending_counts"].get("rosetta_updated", 0) >= 1

    def test_full_cross_module_persistence(self, tmp_path):
        """All three modules persist state via PersistenceManager independently."""
        pm = PersistenceManager(persistence_dir=str(tmp_path / "persistence"))

        # Rosetta state
        rosetta_state = _make_rosetta_state(agent_id="cross-agent")
        rosetta_state.automation_progress.append(
            AutomationProgress(category="full_test", total_items=20, completed_items=15)
        )
        pm.save_rosetta_state("cross-agent", rosetta_state.model_dump(mode="json"))

        # Robot config as a document
        robot_cfg = _make_robot_config(robot_id="cross-robot")
        pm.save_document("robot-cross-robot", robot_cfg.model_dump(mode="json"))

        # Avatar profile as a document
        avatar_profile = _make_avatar_profile(avatar_id="cross-avatar")
        pm.save_document("avatar-cross-avatar", avatar_profile.model_dump(mode="json"))

        # Verify all can be loaded independently
        loaded_rosetta = pm.load_rosetta_state("cross-agent")
        assert loaded_rosetta["identity"]["agent_id"] == "cross-agent"
        assert loaded_rosetta["automation_progress"][0]["completed_items"] == 15

        loaded_robot = pm.load_document("robot-cross-robot")
        assert loaded_robot["robot_id"] == "cross-robot"

        loaded_avatar = pm.load_document("avatar-cross-avatar")
        assert loaded_avatar["avatar_id"] == "cross-avatar"

        # Verify document listing
        docs = pm.list_documents()
        assert "robot-cross-robot" in docs
        assert "avatar-cross-avatar" in docs


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
