"""
Tests for SAF-005: RiskMitigationTracker.

Validates risk registration, status updates, summary generation,
history tracking, persistence, and EventBackbone integration.

Design Label: TEST-028 / SAF-005
Owner: QA Team
"""

import os
import pytest


from risk_mitigation_tracker import (
    RiskMitigationTracker,
    Risk,
    RiskCategory,
    RiskStatus,
    Likelihood,
    Impact,
    StatusChange,
    RiskSummary,
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
def tracker():
    return RiskMitigationTracker()

@pytest.fixture
def wired_tracker(pm, backbone):
    return RiskMitigationTracker(persistence_manager=pm, event_backbone=backbone)


class TestDefaultRisks:
    def test_defaults_loaded(self, tracker):
        risks = tracker.list_risks()
        assert len(risks) == 9

    def test_risk_categories(self, tracker):
        risks = tracker.list_risks()
        categories = {r["category"] for r in risks}
        assert "technical" in categories
        assert "operational" in categories
        assert "business" in categories


class TestRiskManagement:
    def test_add_risk(self, tracker):
        risk = Risk("custom-1", "Custom Risk", RiskCategory.TECHNICAL,
                     Likelihood.LOW, Impact.LOW, "Do nothing")
        tracker.add_risk(risk)
        assert tracker.get_risk("custom-1") is not None

    def test_get_unknown(self, tracker):
        assert tracker.get_risk("nonexistent") is None

    def test_filter_by_category(self, tracker):
        tech = tracker.list_risks(category=RiskCategory.TECHNICAL)
        assert all(r["category"] == "technical" for r in tech)

    def test_filter_by_status(self, tracker):
        open_risks = tracker.list_risks(status=RiskStatus.OPEN)
        assert all(r["status"] == "open" for r in open_risks)

    def test_risk_score(self, tracker):
        r = tracker.get_risk("risk-market")
        assert r is not None
        assert r["risk_score"] == 9  # HIGH * HIGH = 3 * 3


class TestStatusUpdates:
    def test_update_status(self, tracker):
        change = tracker.update_status("risk-code-gen", RiskStatus.MITIGATING, "Started sandbox")
        assert change is not None
        assert change.to_status == "mitigating"
        r = tracker.get_risk("risk-code-gen")
        assert r["status"] == "mitigating"

    def test_update_unknown(self, tracker):
        assert tracker.update_status("fake", RiskStatus.CLOSED) is None

    def test_history_tracked(self, tracker):
        tracker.update_status("risk-code-gen", RiskStatus.MITIGATING, "started")
        tracker.update_status("risk-code-gen", RiskStatus.MITIGATED, "done")
        history = tracker.get_history(risk_id="risk-code-gen")
        assert len(history) == 2

    def test_status_change_to_dict(self, tracker):
        change = tracker.update_status("risk-code-gen", RiskStatus.MITIGATING)
        d = change.to_dict()
        assert "change_id" in d
        assert d["from_status"] == "open"


class TestSummary:
    def test_summary_generated(self, tracker):
        summary = tracker.summarize()
        assert summary.total_risks == 9
        assert summary.avg_risk_score > 0

    def test_summary_to_dict(self, tracker):
        d = tracker.summarize().to_dict()
        assert "summary_id" in d
        assert "by_category" in d
        assert "by_status" in d


class TestPersistence:
    def test_change_persisted(self, wired_tracker, pm):
        change = wired_tracker.update_status("risk-code-gen", RiskStatus.MITIGATING)
        loaded = pm.load_document(change.change_id)
        assert loaded is not None

    def test_summary_persisted(self, wired_tracker, pm):
        summary = wired_tracker.summarize()
        loaded = pm.load_document(summary.summary_id)
        assert loaded is not None


class TestEventBackbone:
    def test_status_change_publishes_event(self, wired_tracker, backbone):
        received = []
        backbone.subscribe(EventType.LEARNING_FEEDBACK, lambda e: received.append(e))
        wired_tracker.update_status("risk-code-gen", RiskStatus.MITIGATING)
        backbone.process_pending()
        assert len(received) >= 1


class TestStatus:
    def test_status(self, tracker):
        s = tracker.get_status()
        assert s["total_risks"] == 9
        assert s["persistence_attached"] is False

    def test_wired_status(self, wired_tracker):
        s = wired_tracker.get_status()
        assert s["persistence_attached"] is True
