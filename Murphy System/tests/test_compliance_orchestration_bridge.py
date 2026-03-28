"""
Tests for ORCH-004: ComplianceOrchestrationBridge.

Validates framework management, evidence registration, assessment
execution, verdict computation, persistence, and EventBackbone integration.

Design Label: TEST-032 / ORCH-004
Owner: QA Team
"""

import os
import pytest


from compliance_orchestration_bridge import (
    ComplianceOrchestrationBridge,
    ComplianceFramework,
    ComplianceControl,
    ControlStatus,
    FrameworkVerdict,
    ComplianceAssessment,
)
from persistence_manager import PersistenceManager
from event_backbone import EventBackbone, EventType


@pytest.fixture
def pm(tmp_path):
    return PersistenceManager(persistence_dir=str(tmp_path / "test_persist"))

@pytest.fixture
def backbone():
    return EventBackbone()

@pytest.fixture
def bridge():
    return ComplianceOrchestrationBridge()

@pytest.fixture
def wired_bridge(pm, backbone):
    return ComplianceOrchestrationBridge(persistence_manager=pm, event_backbone=backbone)


class TestFrameworkManagement:
    def test_default_frameworks_loaded(self, bridge):
        frameworks = bridge.list_frameworks()
        assert len(frameworks) == 5
        names = {f["name"] for f in frameworks}
        assert "GDPR" in names
        assert "SOC2" in names

    def test_add_framework(self, bridge):
        fw = ComplianceFramework("custom", "Custom Framework", [
            ComplianceControl("c1", "Test Control"),
        ])
        bridge.add_framework(fw)
        assert len(bridge.list_frameworks()) == 6

    def test_remove_framework(self, bridge):
        assert bridge.remove_framework("gdpr") is True
        assert bridge.remove_framework("gdpr") is False
        assert len(bridge.list_frameworks()) == 4


class TestEvidenceRegistration:
    def test_register_evidence(self, bridge):
        bridge.register_evidence("gdpr-01", lambda: ("met", "Encryption OK"))
        s = bridge.get_status()
        assert s["total_evidence_sources"] == 1

    def test_unregister_evidence(self, bridge):
        bridge.register_evidence("gdpr-01", lambda: ("met", "OK"))
        assert bridge.unregister_evidence("gdpr-01") is True
        assert bridge.unregister_evidence("gdpr-01") is False


class TestAssessment:
    def test_no_evidence_all_unknown(self, bridge):
        assessment = bridge.assess()
        for fw in assessment.frameworks:
            assert fw.unknown_count > 0

    def test_all_met_is_compliant(self):
        fw = ComplianceFramework("test", "Test", [
            ComplianceControl("t1", "Control 1"),
            ComplianceControl("t2", "Control 2"),
        ])
        bridge = ComplianceOrchestrationBridge(frameworks=[fw])
        bridge.register_evidence("t1", lambda: ("met", "OK"))
        bridge.register_evidence("t2", lambda: ("met", "OK"))
        assessment = bridge.assess()
        assert assessment.frameworks[0].verdict == FrameworkVerdict.COMPLIANT
        assert assessment.compliant_count == 1

    def test_partial_compliance(self):
        fw = ComplianceFramework("test", "Test", [
            ComplianceControl("t1", "Control 1"),
            ComplianceControl("t2", "Control 2"),
        ])
        bridge = ComplianceOrchestrationBridge(frameworks=[fw])
        bridge.register_evidence("t1", lambda: ("met", "OK"))
        assessment = bridge.assess()
        assert assessment.frameworks[0].verdict == FrameworkVerdict.PARTIAL

    def test_evidence_exception_is_unknown(self):
        fw = ComplianceFramework("test", "Test", [
            ComplianceControl("t1", "Control 1"),
        ])
        bridge = ComplianceOrchestrationBridge(frameworks=[fw])
        bridge.register_evidence("t1", lambda: (_ for _ in ()).throw(RuntimeError("err")))
        assessment = bridge.assess()
        assert assessment.frameworks[0].unknown_count == 1

    def test_assessment_to_dict(self, bridge):
        a = bridge.assess()
        d = a.to_dict()
        assert "assessment_id" in d
        assert "frameworks" in d


class TestPersistence:
    def test_assessment_persisted(self, wired_bridge, pm):
        assessment = wired_bridge.assess()
        loaded = pm.load_document(assessment.assessment_id)
        assert loaded is not None


class TestEventBackbone:
    def test_assessment_publishes_event(self, wired_bridge, backbone):
        received = []
        backbone.subscribe(EventType.LEARNING_FEEDBACK, lambda e: received.append(e))
        wired_bridge.assess()
        backbone.process_pending()
        assert len(received) >= 1


class TestStatus:
    def test_status(self, bridge):
        s = bridge.get_status()
        assert s["total_frameworks"] == 5
        assert s["persistence_attached"] is False

    def test_wired_status(self, wired_bridge):
        s = wired_bridge.get_status()
        assert s["persistence_attached"] is True
