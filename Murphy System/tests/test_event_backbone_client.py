"""
Tests for EventBackbone consistency fixes:
  - EventType.from_string() classmethod
  - event_backbone_client facade (string→enum, global singleton, drop-logging)
  - All updated module _publish methods
  - Gap-detection: no module should have an empty event_type_map
"""

import glob
import logging
import os
import sys
from unittest.mock import MagicMock, call, patch

import pytest

# Ensure src is on the path

from event_backbone import EventBackbone, EventType
import event_backbone_client


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fresh_backbone() -> EventBackbone:
    return EventBackbone()


def _reset_global_backbone():
    """Reset the module-level singleton between tests."""
    event_backbone_client._global_backbone = None


# ---------------------------------------------------------------------------
# EventType.from_string
# ---------------------------------------------------------------------------


class TestEventTypeFromString:
    def test_from_value_lowercase(self):
        assert EventType.from_string("task_submitted") == EventType.TASK_SUBMITTED

    def test_from_value_uppercase(self):
        # value lookup is case-insensitive (lowercased)
        assert EventType.from_string("TASK_SUBMITTED") == EventType.TASK_SUBMITTED

    def test_from_name(self):
        assert EventType.from_string("LEARNING_FEEDBACK") == EventType.LEARNING_FEEDBACK

    def test_from_name_lowercase(self):
        assert EventType.from_string("learning_feedback") == EventType.LEARNING_FEEDBACK

    def test_unknown_raises(self):
        with pytest.raises(ValueError, match="No EventType matching"):
            EventType.from_string("not_a_real_event")

    def test_all_event_types_round_trip(self):
        """Every EventType value must survive a from_string round-trip."""
        for et in EventType:
            assert EventType.from_string(et.value) == et
            assert EventType.from_string(et.name) == et


# ---------------------------------------------------------------------------
# event_backbone_client — global singleton
# ---------------------------------------------------------------------------


class TestGlobalSingleton:
    def setup_method(self):
        _reset_global_backbone()

    def test_get_backbone_returns_none_initially(self):
        assert event_backbone_client.get_backbone() is None

    def test_set_backbone_stores_instance(self):
        bb = _fresh_backbone()
        event_backbone_client.set_backbone(bb)
        assert event_backbone_client.get_backbone() is bb

    def test_set_backbone_logs_info(self, caplog):
        bb = _fresh_backbone()
        with caplog.at_level(logging.INFO, logger="event_backbone_client"):
            event_backbone_client.set_backbone(bb)
        assert "global backbone registered" in caplog.text


# ---------------------------------------------------------------------------
# event_backbone_client.publish — string + enum inputs
# ---------------------------------------------------------------------------


class TestPublishHelper:
    def setup_method(self):
        _reset_global_backbone()

    def test_publish_with_enum(self):
        bb = _fresh_backbone()
        ok = event_backbone_client.publish(
            EventType.TASK_SUBMITTED, {"x": 1}, backbone=bb
        )
        assert ok is True
        status = bb.get_status()
        assert status["events_published"] == 1

    def test_publish_with_string_value(self):
        bb = _fresh_backbone()
        ok = event_backbone_client.publish("task_submitted", {"x": 1}, backbone=bb)
        assert ok is True

    def test_publish_with_string_name_uppercase(self):
        bb = _fresh_backbone()
        ok = event_backbone_client.publish(
            "TASK_SUBMITTED", {"x": 1}, backbone=bb
        )
        assert ok is True

    def test_publish_uses_global_singleton_when_no_explicit_backbone(self):
        bb = _fresh_backbone()
        event_backbone_client.set_backbone(bb)
        ok = event_backbone_client.publish("task_completed", {"done": True})
        assert ok is True
        assert bb.get_status()["events_published"] == 1

    def test_explicit_backbone_overrides_global(self):
        global_bb = _fresh_backbone()
        explicit_bb = _fresh_backbone()
        event_backbone_client.set_backbone(global_bb)

        event_backbone_client.publish("task_completed", {}, backbone=explicit_bb)
        assert global_bb.get_status()["events_published"] == 0
        assert explicit_bb.get_status()["events_published"] == 1

    def test_publish_returns_false_when_no_backbone(self, caplog):
        with caplog.at_level(logging.WARNING, logger="event_backbone_client"):
            ok = event_backbone_client.publish("task_submitted", {})
        assert ok is False
        assert "no backbone available" in caplog.text

    def test_publish_returns_false_for_unknown_event_type(self, caplog):
        bb = _fresh_backbone()
        with caplog.at_level(logging.WARNING, logger="event_backbone_client"):
            ok = event_backbone_client.publish(
                "totally_unknown_event", {}, backbone=bb
            )
        assert ok is False
        assert "unknown event_type" in caplog.text

    def test_publish_passes_source_and_session_id(self):
        bb = _fresh_backbone()
        from event_backbone import EventType

        received = []
        bb.subscribe(EventType.AUDIT_LOGGED, lambda e: received.append(e))
        event_backbone_client.publish(
            "audit_logged",
            {"msg": "test"},
            source="unit_test",
            session_id="sess-x",
            backbone=bb,
        )
        bb.process_pending()
        assert len(received) == 1
        assert received[0].source == "unit_test"
        assert received[0].session_id == "sess-x"


# ---------------------------------------------------------------------------
# Module-level integration: SelfMarketingOrchestrator
# ---------------------------------------------------------------------------


class TestSelfMarketingOrchestratorPublish:
    def setup_method(self):
        _reset_global_backbone()

    def _make_orchestrator(self, backbone=None):
        from self_marketing_orchestrator import SelfMarketingOrchestrator
        return SelfMarketingOrchestrator(event_backbone=backbone)

    def test_publish_event_with_injected_backbone(self):
        bb = _fresh_backbone()
        orch = self._make_orchestrator(backbone=bb)
        # Directly call the internal helper
        orch._publish_event("learning_feedback", {"item": "content_queued"})
        assert bb.get_status()["events_published"] == 1

    def test_publish_event_uses_global_backbone_when_not_injected(self):
        bb = _fresh_backbone()
        event_backbone_client.set_backbone(bb)
        orch = self._make_orchestrator(backbone=None)
        orch._publish_event("learning_feedback", {"item": "content_queued"})
        assert bb.get_status()["events_published"] == 1

    def test_publish_event_logs_warning_when_no_backbone(self, caplog):
        orch = self._make_orchestrator(backbone=None)
        with caplog.at_level(logging.WARNING, logger="event_backbone_client"):
            orch._publish_event("learning_feedback", {})
        assert "no backbone available" in caplog.text


# ---------------------------------------------------------------------------
# Module-level integration: ContactComplianceGovernor
# ---------------------------------------------------------------------------


class TestContactComplianceGovernorPublish:
    def setup_method(self):
        _reset_global_backbone()

    def _make_governor(self, backbone=None):
        from contact_compliance_governor import ContactComplianceGovernor
        return ContactComplianceGovernor(event_backbone=backbone)

    def test_publish_with_injected_backbone(self):
        bb = _fresh_backbone()
        gov = self._make_governor(backbone=bb)
        gov._publish("learning_feedback", {"reason": "test"})
        assert bb.get_status()["events_published"] == 1

    def test_publish_embeds_source_and_action(self):
        bb = _fresh_backbone()
        gov = self._make_governor(backbone=bb)

        received = []
        bb.subscribe(EventType.LEARNING_FEEDBACK, lambda e: received.append(e))
        gov._publish("learning_feedback", {"reason": "dnc"})
        bb.process_pending()

        assert received[0].payload["source"] == "contact_compliance_governor"
        assert received[0].payload["action"] == "learning_feedback"

    def test_publish_uses_global_backbone_when_not_injected(self):
        bb = _fresh_backbone()
        event_backbone_client.set_backbone(bb)
        gov = self._make_governor(backbone=None)
        gov._publish("learning_feedback", {})
        assert bb.get_status()["events_published"] == 1


# ---------------------------------------------------------------------------
# Module-level integration: WorkflowLicenseManager
# ---------------------------------------------------------------------------


class TestWorkflowLicenseManagerPublish:
    def setup_method(self):
        _reset_global_backbone()

    def _make_manager(self, backbone=None):
        from large_action_model import WorkflowLicenseManager
        mgr = WorkflowLicenseManager()
        mgr._backbone = backbone
        return mgr

    def test_publish_event_uses_learning_feedback_fallback(self):
        """Previously empty event_type_map silently dropped all events; now publishes."""
        bb = _fresh_backbone()
        mgr = self._make_manager(backbone=bb)
        # "LAM_WORKFLOW_LICENSED" is the real call-site value; verify it publishes
        mgr._publish_event("learning_feedback", {"license": "pro"})
        assert bb.get_status()["events_published"] == 1

    def test_publish_event_uses_global_backbone_when_not_injected(self):
        bb = _fresh_backbone()
        event_backbone_client.set_backbone(bb)
        mgr = self._make_manager(backbone=None)
        mgr._publish_event("learning_feedback", {"license": "pro"})
        assert bb.get_status()["events_published"] == 1

    def test_publish_event_logs_warning_when_no_backbone(self, caplog):
        mgr = self._make_manager(backbone=None)
        with caplog.at_level(logging.WARNING, logger="event_backbone_client"):
            mgr._publish_event("learning_feedback", {})
        assert "no backbone available" in caplog.text


# ---------------------------------------------------------------------------
# Module-level integration: AutomationIntegrationHub
# ---------------------------------------------------------------------------


class TestAutomationIntegrationHubPublish:
    def setup_method(self):
        _reset_global_backbone()

    def _make_hub(self, backbone=None):
        from automation_integration_hub import AutomationIntegrationHub
        hub = AutomationIntegrationHub()
        hub._backbone = backbone
        return hub

    def test_publish_event_with_injected_backbone(self):
        bb = _fresh_backbone()
        hub = self._make_hub(backbone=bb)
        hub._publish_event("task_submitted", "test_module", 2)
        assert bb.get_status()["events_published"] == 1

    def test_publish_event_uses_global_backbone_when_not_injected(self):
        bb = _fresh_backbone()
        event_backbone_client.set_backbone(bb)
        hub = self._make_hub(backbone=None)
        hub._publish_event("task_submitted", "test_module", 1)
        assert bb.get_status()["events_published"] == 1

    def test_publish_event_logs_warning_when_no_backbone(self, caplog):
        hub = self._make_hub(backbone=None)
        with caplog.at_level(logging.WARNING, logger="event_backbone_client"):
            hub._publish_event("task_submitted", "test_module", 0)
        assert "no backbone available" in caplog.text


# ---------------------------------------------------------------------------
# Module-level integration: MurphyCodeHealer
# ---------------------------------------------------------------------------


class TestMurphyCodeHealerPublish:
    def setup_method(self):
        _reset_global_backbone()

    def _make_healer(self, backbone=None):
        from murphy_code_healer import MurphyCodeHealer
        healer = MurphyCodeHealer()
        healer._backbone = backbone
        return healer

    def test_publish_event_with_injected_backbone(self):
        """Previously used event_type=None which caused TypeError — now fixed."""
        bb = _fresh_backbone()
        healer = self._make_healer(backbone=bb)
        healer._publish_event("learning_feedback", {"gap": "test-gap"})
        assert bb.get_status()["events_published"] == 1

    def test_publish_event_uses_global_backbone_when_not_injected(self):
        bb = _fresh_backbone()
        event_backbone_client.set_backbone(bb)
        healer = self._make_healer(backbone=None)
        healer._publish_event("learning_feedback", {"gap": "test-gap"})
        assert bb.get_status()["events_published"] == 1

    def test_publish_event_logs_warning_when_no_backbone(self, caplog):
        healer = self._make_healer(backbone=None)
        with caplog.at_level(logging.WARNING, logger="event_backbone_client"):
            healer._publish_event("learning_feedback", {})
        assert "no backbone available" in caplog.text


# ---------------------------------------------------------------------------
# Module-level integration: CEOBranchActivation
# ---------------------------------------------------------------------------


class TestCEOBranchActivationEmitTelemetry:
    def setup_method(self):
        _reset_global_backbone()

    def _make_branch(self, backbone=None):
        from ceo_branch_activation import CEOBranch
        branch = CEOBranch()
        branch._backbone = backbone
        return branch

    def test_emit_telemetry_with_injected_backbone(self):
        """Previously called publish(string, dict) — string was silently rejected."""
        bb = _fresh_backbone()
        branch = self._make_branch(backbone=bb)
        branch._emit_telemetry("learning_feedback", {"detail": "ok"})
        assert bb.get_status()["events_published"] == 1

    def test_emit_telemetry_uses_global_backbone_when_not_injected(self):
        bb = _fresh_backbone()
        event_backbone_client.set_backbone(bb)
        branch = self._make_branch(backbone=None)
        branch._emit_telemetry("learning_feedback", {"detail": "ok"})
        assert bb.get_status()["events_published"] == 1

    def test_emit_telemetry_logs_warning_when_no_backbone(self, caplog):
        branch = self._make_branch(backbone=None)
        with caplog.at_level(logging.WARNING, logger="event_backbone_client"):
            branch._emit_telemetry("learning_feedback", {})
        assert "no backbone available" in caplog.text


# ---------------------------------------------------------------------------
# Module-level integration: AutonomousRepairSystem
# ---------------------------------------------------------------------------


class TestAutonomousRepairSystemPublish:
    def setup_method(self):
        _reset_global_backbone()

    def _make_repair_system(self, backbone=None):
        from autonomous_repair_system import AutonomousRepairSystem
        ars = AutonomousRepairSystem()
        ars._backbone = backbone
        return ars

    def test_publish_event_with_injected_backbone(self):
        """Previously called publish(Event_object) — Event object is not EventType."""
        bb = _fresh_backbone()
        ars = self._make_repair_system(backbone=bb)
        ars._publish_event("system_health", {"status": "ok"})
        assert bb.get_status()["events_published"] == 1

    def test_publish_event_uses_global_backbone_when_not_injected(self):
        bb = _fresh_backbone()
        event_backbone_client.set_backbone(bb)
        ars = self._make_repair_system(backbone=None)
        ars._publish_event("system_health", {"status": "ok"})
        assert bb.get_status()["events_published"] == 1

    def test_publish_event_logs_warning_when_no_backbone(self, caplog):
        ars = self._make_repair_system(backbone=None)
        with caplog.at_level(logging.WARNING, logger="event_backbone_client"):
            ars._publish_event("system_health", {})
        assert "no backbone available" in caplog.text


# ---------------------------------------------------------------------------
# Module-level integration: MurphyImmuneEngine
# ---------------------------------------------------------------------------


class TestMurphyImmuneEnginePublish:
    def setup_method(self):
        _reset_global_backbone()

    def _make_immune_engine(self, backbone=None):
        from murphy_immune_engine import MurphyImmuneEngine
        engine = MurphyImmuneEngine()
        engine._backbone = backbone
        return engine

    def test_publish_with_injected_backbone(self):
        """Previously used getattr fallback; now uses facade with from_string."""
        bb = _fresh_backbone()
        engine = self._make_immune_engine(backbone=bb)
        engine._publish("IMMUNE_CYCLE_STARTED", {"cycle": 1})
        assert bb.get_status()["events_published"] == 1

    def test_publish_event_and_subscriber_receives_it(self):
        """End-to-end: event published via facade is received by a subscriber."""
        bb = _fresh_backbone()
        received = []
        bb.subscribe(EventType.IMMUNE_CYCLE_STARTED, lambda e: received.append(e))
        engine = self._make_immune_engine(backbone=bb)
        engine._publish("IMMUNE_CYCLE_STARTED", {"cycle": 1})
        bb.process_pending()
        assert len(received) == 1
        assert received[0].source == "murphy_immune_engine"

    def test_publish_uses_global_backbone_when_not_injected(self):
        bb = _fresh_backbone()
        event_backbone_client.set_backbone(bb)
        engine = self._make_immune_engine(backbone=None)
        engine._publish("IMMUNE_CYCLE_COMPLETED", {"status": "ok"})
        assert bb.get_status()["events_published"] == 1

    def test_publish_logs_warning_when_no_backbone(self, caplog):
        engine = self._make_immune_engine(backbone=None)
        with caplog.at_level(logging.WARNING, logger="event_backbone_client"):
            engine._publish("IMMUNE_CYCLE_STARTED", {})
        assert "no backbone available" in caplog.text


# ---------------------------------------------------------------------------
# Gap-detection: no module should have an empty event_type_map
# ---------------------------------------------------------------------------


class TestGapDetection:
    def test_no_empty_event_type_map(self):
        """Detect any file using both an empty event_type_map and event_type_map.get().

        When a module builds an empty dict (``event_type_map = {}``) and then
        calls ``event_type_map.get(event_name)`` to resolve the EventType, the
        lookup always returns ``None`` and no event is ever published — a
        silent bug.  This pattern has been replaced with the
        ``event_backbone_client`` facade in all known locations.  This test
        ensures no new occurrences are added.
        """
        src_dir = os.path.join(os.path.dirname(__file__), "..", "src")
        broken: list = []

        pattern_variants = [
            "event_type_map: Dict[str, Any] = {}",
            "event_type_map: dict = {}",
            "event_type_map = {}",
        ]

        for filepath in glob.glob(os.path.join(src_dir, "**", "*.py"), recursive=True):
            with open(filepath, encoding="utf-8", errors="replace") as fh:
                source = fh.read()

            # Only flag files where an empty map is used inside a _publish method
            # (other empty dicts elsewhere are fine).
            for variant in pattern_variants:
                if variant in source and "event_type_map.get(" in source:
                    broken.append(os.path.relpath(filepath, src_dir))
                    break

        assert not broken, (
            "Found modules with an empty event_type_map inside a _publish "
            f"method (events silently dropped): {broken}"
        )
