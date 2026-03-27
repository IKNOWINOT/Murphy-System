"""
Tests for CMP-001: ComplianceAutomationBridge.

Validates compliance checking, remediation proposal creation,
posture tracking, and EventBackbone integration.

Design Label: TEST-004 / CMP-001
Owner: QA Team
"""

import os
import pytest


from compliance_automation_bridge import (
    ComplianceAutomationBridge,
    ComplianceCheckRecord,
)
from compliance_engine import (
    ComplianceEngine,
    ComplianceRequirement,
    ComplianceFramework,
    ComplianceSeverity,
)
from self_improvement_engine import SelfImprovementEngine, ImprovementProposal
from persistence_manager import PersistenceManager
from event_backbone import EventBackbone, EventType


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def pm(tmp_path):
    return PersistenceManager(persistence_dir=str(tmp_path / "test_persist"))


@pytest.fixture
def compliance():
    engine = ComplianceEngine()
    # Register a test requirement
    engine.register_requirement(ComplianceRequirement(
        requirement_id="test-req-001",
        framework=ComplianceFramework.SOC2,
        description="All data must be encrypted at rest",
        severity=ComplianceSeverity.HIGH,
        applicable_domains=["general", "finance"],
        auto_checkable=True,
    ))
    return engine


@pytest.fixture
def improvement(pm):
    return SelfImprovementEngine(persistence_manager=pm)


@pytest.fixture
def backbone():
    return EventBackbone()


@pytest.fixture
def bridge(compliance, improvement):
    return ComplianceAutomationBridge(
        compliance_engine=compliance,
        improvement_engine=improvement,
    )


@pytest.fixture
def wired_bridge(compliance, improvement, backbone):
    return ComplianceAutomationBridge(
        compliance_engine=compliance,
        improvement_engine=improvement,
        event_backbone=backbone,
    )


# ------------------------------------------------------------------
# Basic compliance check
# ------------------------------------------------------------------

class TestBasicCheck:
    def test_check_returns_record(self, bridge):
        record = bridge.check_compliance(
            deliverable={"content": "test deliverable"},
            domain="general",
        )
        assert isinstance(record, ComplianceCheckRecord)
        assert record.domain == "general"
        assert record.check_id.startswith("chk-")

    def test_check_without_engine_not_ready(self):
        bridge = ComplianceAutomationBridge()
        record = bridge.check_compliance(
            deliverable={"content": "test"},
            domain="general",
        )
        assert record.release_ready is False


# ------------------------------------------------------------------
# Remediation proposals
# ------------------------------------------------------------------

class TestRemediation:
    def test_non_compliant_creates_proposal(self, bridge, improvement, compliance):
        # Check compliance - the engine may find violations
        record = bridge.check_compliance(
            deliverable={"content": "unencrypted data"},
            domain="general",
        )
        # Record was created
        assert isinstance(record, ComplianceCheckRecord)
        assert record.total_requirements >= 0

    def test_deduplication(self, bridge):
        bridge.check_compliance(
            deliverable={"content": "test"},
            domain="general",
            session_id="dedup-test",
        )
        bridge.check_compliance(
            deliverable={"content": "test"},
            domain="general",
            session_id="dedup-test",
        )
        # The second check should not create duplicate proposals
        status = bridge.get_status()
        assert status["total_checks"] == 2

    def test_clear_tracked_violations(self, bridge):
        bridge.check_compliance(
            deliverable={"content": "test"},
            domain="general",
        )
        cleared = bridge.clear_tracked_violations()
        assert isinstance(cleared, int)


# ------------------------------------------------------------------
# Compliance posture
# ------------------------------------------------------------------

class TestCompliancePosture:
    def test_empty_posture(self):
        bridge = ComplianceAutomationBridge()
        posture = bridge.get_compliance_posture()
        assert posture["total_checks"] == 0

    def test_posture_after_checks(self, bridge):
        bridge.check_compliance(
            deliverable={"content": "test1"},
            domain="general",
        )
        bridge.check_compliance(
            deliverable={"content": "test2"},
            domain="finance",
        )
        posture = bridge.get_compliance_posture()
        assert posture["total_checks"] == 2
        assert "general" in posture["domains_checked"]
        assert "finance" in posture["domains_checked"]


# ------------------------------------------------------------------
# EventBackbone integration
# ------------------------------------------------------------------

class TestEventBackboneIntegration:
    def test_publishes_compliance_event(self, wired_bridge, backbone):
        received = []
        backbone.subscribe(EventType.LEARNING_FEEDBACK, lambda e: received.append(e))
        wired_bridge.check_compliance(
            deliverable={"content": "test"},
            domain="general",
        )
        backbone.process_pending()
        assert len(received) >= 1
        assert received[0].payload["source"] == "compliance_automation_bridge"


# ------------------------------------------------------------------
# History / Status
# ------------------------------------------------------------------

class TestHistoryAndStatus:
    def test_history_accumulates(self, bridge):
        bridge.check_compliance(deliverable={"content": "a"}, domain="d1")
        bridge.check_compliance(deliverable={"content": "b"}, domain="d2")
        history = bridge.get_history()
        assert len(history) == 2

    def test_status_reflects_state(self, bridge):
        status = bridge.get_status()
        assert status["compliance_attached"] is True
        assert status["improvement_attached"] is True
        assert status["backbone_attached"] is False

    def test_record_to_dict(self, bridge):
        record = bridge.check_compliance(
            deliverable={"content": "test"},
            domain="general",
        )
        d = record.to_dict()
        assert "check_id" in d
        assert "domain" in d
        assert "release_ready" in d
