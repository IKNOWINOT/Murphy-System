"""
Tests for DEV-002: SLORemediationBridge.

Validates the bridge between OperationalSLOTracker violations and
SelfImprovementEngine improvement proposals.

Design Label: TEST-002 / DEV-002
Owner: QA Team
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from slo_remediation_bridge import SLORemediationBridge, RemediationAction
from self_improvement_engine import SelfImprovementEngine, ImprovementProposal
from operational_slo_tracker import OperationalSLOTracker, SLOTarget, ExecutionRecord
from persistence_manager import PersistenceManager
from event_backbone import EventBackbone, EventType


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def pm(tmp_path):
    return PersistenceManager(persistence_dir=str(tmp_path / "test_persist"))


@pytest.fixture
def tracker():
    t = OperationalSLOTracker()
    t.add_slo_target(SLOTarget(
        target_name="deploy_success_rate",
        metric="success_rate",
        threshold=0.95,
        window_seconds=3600,
    ))
    return t


@pytest.fixture
def engine(pm):
    return SelfImprovementEngine(persistence_manager=pm)


@pytest.fixture
def backbone():
    return EventBackbone()


@pytest.fixture
def bridge(tracker, engine):
    return SLORemediationBridge(
        slo_tracker=tracker,
        improvement_engine=engine,
    )


@pytest.fixture
def wired_bridge(tracker, engine, backbone):
    return SLORemediationBridge(
        slo_tracker=tracker,
        improvement_engine=engine,
        event_backbone=backbone,
    )


# ------------------------------------------------------------------
# Compliant SLO — no actions
# ------------------------------------------------------------------

class TestCompliantSLO:
    def test_no_actions_when_compliant(self, bridge, tracker):
        # Record all successes → compliant
        for i in range(10):
            tracker.record_execution(ExecutionRecord(
                task_type="deploy", success=True, duration=0.5,
            ))
        actions = bridge.check_and_remediate()
        assert len(actions) == 0


# ------------------------------------------------------------------
# SLO violation → proposal
# ------------------------------------------------------------------

class TestSLOViolation:
    def test_violation_creates_proposal(self, bridge, tracker, engine):
        # Record enough failures to violate the 95% SLO
        for i in range(5):
            tracker.record_execution(ExecutionRecord(
                task_type="deploy", success=True, duration=0.5,
            ))
        for i in range(5):
            tracker.record_execution(ExecutionRecord(
                task_type="deploy", success=False, duration=0.5,
                failure_reason="timeout",
            ))
        actions = bridge.check_and_remediate()
        assert len(actions) >= 1
        # Should have created a proposal in the engine
        action = actions[0]
        assert action.proposal_id is not None
        backlog = engine.get_remediation_backlog()
        proposal_ids = [p.proposal_id for p in backlog]
        assert action.proposal_id in proposal_ids

    def test_deduplication(self, bridge, tracker):
        for i in range(10):
            tracker.record_execution(ExecutionRecord(
                task_type="deploy",
                success=(i < 4),  # 40% success rate
                duration=0.5,
            ))
        bridge.check_and_remediate()
        # Second call shouldn't create duplicate actions
        actions2 = bridge.check_and_remediate()
        assert len(actions2) == 0

    def test_clear_tracked_violations(self, bridge, tracker):
        for i in range(10):
            tracker.record_execution(ExecutionRecord(
                task_type="deploy", success=False, duration=0.5,
            ))
        bridge.check_and_remediate()
        count = bridge.clear_tracked_violations()
        assert count >= 1
        # Now can detect again
        actions = bridge.check_and_remediate()
        assert len(actions) >= 1


# ------------------------------------------------------------------
# Severity classification
# ------------------------------------------------------------------

class TestSeverityClassification:
    def test_large_gap_is_critical(self):
        priority = SLORemediationBridge._severity_from_gap(0.5, 0.95, "success_rate")
        assert priority == "critical"

    def test_medium_gap_is_high(self):
        priority = SLORemediationBridge._severity_from_gap(0.82, 0.95, "success_rate")
        assert priority == "high"

    def test_small_gap_is_medium(self):
        priority = SLORemediationBridge._severity_from_gap(0.90, 0.95, "success_rate")
        assert priority == "medium"

    def test_latency_severity(self):
        # ratio=3000/1000=3.0 → needs >3 for critical, so this is "high"
        priority = SLORemediationBridge._severity_from_gap(3000, 1000, "latency_p95")
        assert priority == "high"
        # ratio=4000/1000=4.0 → >3 → critical
        priority_crit = SLORemediationBridge._severity_from_gap(4000, 1000, "latency_p95")
        assert priority_crit == "critical"


# ------------------------------------------------------------------
# EventBackbone integration
# ------------------------------------------------------------------

class TestEventBackboneIntegration:
    def test_violation_publishes_learning_feedback(self, wired_bridge, tracker, backbone):
        recorder = []
        backbone.subscribe(EventType.LEARNING_FEEDBACK, lambda e: recorder.append(e))
        for i in range(10):
            tracker.record_execution(ExecutionRecord(
                task_type="deploy", success=False, duration=0.5,
            ))
        wired_bridge.check_and_remediate()
        backbone.process_pending()
        assert len(recorder) >= 1
        assert recorder[0].payload["source"] == "slo_remediation_bridge"


# ------------------------------------------------------------------
# Status
# ------------------------------------------------------------------

class TestStatus:
    def test_status_reflects_state(self, bridge):
        status = bridge.get_status()
        assert status["slo_tracker_attached"] is True
        assert status["engine_attached"] is True
        assert status["event_backbone_attached"] is False

    def test_no_tracker(self):
        bridge = SLORemediationBridge()
        actions = bridge.check_and_remediate()
        assert len(actions) == 0


# ------------------------------------------------------------------
# Action serialisation
# ------------------------------------------------------------------

class TestActionSerialisation:
    def test_action_to_dict(self):
        action = RemediationAction(
            action_id="test-1",
            slo_target_name="deploy_sr",
            metric="success_rate",
            threshold=0.95,
            actual_value=0.80,
        )
        d = action.to_dict()
        assert d["action_id"] == "test-1"
        assert d["actual_value"] == 0.80
