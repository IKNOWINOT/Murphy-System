"""
Tests for ADV-004: ResourceScalingController.

Validates resource snapshot recording, utilisation analysis,
scaling recommendations, decision tracking, persistence
integration, and EventBackbone event publishing.

Design Label: TEST-008 / ADV-004
Owner: QA Team
"""

import os
import pytest


from resource_scaling_controller import (
    ResourceScalingController,
    ResourceSnapshot,
    ScalingRecommendation,
    ScalingAction,
    ScalingDecision,
)
from persistence_manager import PersistenceManager
from event_backbone import EventBackbone, EventType


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def pm(tmp_path):
    return PersistenceManager(persistence_dir=str(tmp_path / "test_persist"))


@pytest.fixture
def backbone():
    return EventBackbone()


@pytest.fixture
def controller():
    return ResourceScalingController()


@pytest.fixture
def wired_controller(pm, backbone):
    return ResourceScalingController(
        persistence_manager=pm,
        event_backbone=backbone,
    )


# ------------------------------------------------------------------
# Snapshot recording
# ------------------------------------------------------------------

class TestSnapshotRecording:
    def test_record_snapshot(self, controller):
        snap = controller.record_snapshot(resource_type="cpu", utilisation=0.72)
        assert snap.snapshot_id.startswith("snap-")
        assert snap.resource_type == "cpu"
        assert snap.utilisation == 0.72

    def test_snapshot_to_dict(self, controller):
        snap = controller.record_snapshot(resource_type="memory", utilisation=0.65)
        d = snap.to_dict()
        assert "snapshot_id" in d
        assert "resource_type" in d
        assert "utilisation" in d

    def test_bounded_snapshots(self):
        ctrl = ResourceScalingController(max_snapshots=5)
        for i in range(10):
            ctrl.record_snapshot(resource_type="cpu", utilisation=float(i) / 10)
        snapshots = ctrl.get_snapshots(limit=100)
        assert len(snapshots) <= 6  # max 5 + eviction buffer

    def test_filter_snapshots(self, controller):
        controller.record_snapshot(resource_type="cpu", utilisation=0.80)
        controller.record_snapshot(resource_type="memory", utilisation=0.60)
        controller.record_snapshot(resource_type="cpu", utilisation=0.85)
        cpu_only = controller.get_snapshots(resource_type="cpu")
        assert len(cpu_only) == 2
        assert all(s["resource_type"] == "cpu" for s in cpu_only)


# ------------------------------------------------------------------
# Utilisation analysis
# ------------------------------------------------------------------

class TestUtilisationAnalysis:
    def test_analyse_utilisation(self, controller):
        for _ in range(10):
            controller.record_snapshot(resource_type="cpu", utilisation=0.70)
        result = controller.analyse_utilisation()
        assert any(k.startswith("cpu:") for k in result)

    def test_analysis_metrics(self, controller):
        for _ in range(10):
            controller.record_snapshot(resource_type="cpu", utilisation=0.70)
        result = controller.analyse_utilisation()
        key = [k for k in result if k.startswith("cpu:")][0]
        metrics = result[key]
        assert "mean" in metrics
        assert "max" in metrics
        assert "min" in metrics
        assert "trend" in metrics
        assert "samples" in metrics


# ------------------------------------------------------------------
# Scaling recommendations
# ------------------------------------------------------------------

class TestScalingRecommendations:
    def test_recommend_scale_up(self, controller):
        for _ in range(20):
            controller.record_snapshot(resource_type="cpu", utilisation=0.95)
        recs = controller.recommend_scaling()
        actions = [r.action for r in recs]
        assert ScalingAction.SCALE_UP in actions

    def test_recommend_scale_down(self, controller):
        for _ in range(20):
            controller.record_snapshot(resource_type="cpu", utilisation=0.30)
        recs = controller.recommend_scaling()
        actions = [r.action for r in recs]
        assert ScalingAction.SCALE_DOWN in actions

    def test_recommend_no_action(self, controller):
        for _ in range(20):
            controller.record_snapshot(resource_type="cpu", utilisation=0.70)
        recs = controller.recommend_scaling()
        actions = [r.action for r in recs]
        assert ScalingAction.NO_ACTION in actions or len(recs) == 0

    def test_cost_approval_threshold(self):
        ctrl = ResourceScalingController(cost_approval_threshold=5.0)
        for _ in range(20):
            ctrl.record_snapshot(resource_type="cpu", utilisation=0.95)
        recs = ctrl.recommend_scaling(cost_per_scale_up=10.0)
        scale_ups = [r for r in recs if r.action == ScalingAction.SCALE_UP]
        assert len(scale_ups) >= 1
        assert scale_ups[0].requires_approval is True


# ------------------------------------------------------------------
# Scaling decisions
# ------------------------------------------------------------------

class TestScalingDecisions:
    def test_record_decision(self, controller):
        for _ in range(20):
            controller.record_snapshot(resource_type="cpu", utilisation=0.95)
        recs = controller.recommend_scaling()
        rec = recs[0]
        decision = controller.record_decision(
            recommendation_id=rec.recommendation_id,
            approved=True,
        )
        assert decision.decision_id.startswith("dec-")
        assert decision.approved is True

    def test_decision_to_dict(self, controller):
        for _ in range(20):
            controller.record_snapshot(resource_type="cpu", utilisation=0.95)
        recs = controller.recommend_scaling()
        rec = recs[0]
        decision = controller.record_decision(
            recommendation_id=rec.recommendation_id,
            approved=True,
            actual_cost=5.0,
        )
        d = decision.to_dict()
        assert "decision_id" in d
        assert "recommendation_id" in d
        assert "approved" in d
        assert "actual_cost" in d


# ------------------------------------------------------------------
# Query
# ------------------------------------------------------------------

class TestQuery:
    def test_get_snapshots(self, controller):
        controller.record_snapshot(resource_type="cpu", utilisation=0.70)
        snapshots = controller.get_snapshots()
        assert isinstance(snapshots, list)
        assert len(snapshots) >= 1

    def test_get_recommendations(self, controller):
        for _ in range(20):
            controller.record_snapshot(resource_type="cpu", utilisation=0.95)
        controller.recommend_scaling()
        recs = controller.get_recommendations()
        assert isinstance(recs, list)
        assert len(recs) >= 1

    def test_get_decisions(self, controller):
        for _ in range(20):
            controller.record_snapshot(resource_type="cpu", utilisation=0.95)
        recs = controller.recommend_scaling()
        controller.record_decision(
            recommendation_id=recs[0].recommendation_id,
            approved=True,
        )
        decisions = controller.get_decisions()
        assert isinstance(decisions, list)
        assert len(decisions) >= 1


# ------------------------------------------------------------------
# Persistence integration
# ------------------------------------------------------------------

class TestPersistence:
    def test_recommendation_persisted(self, wired_controller, pm):
        for _ in range(20):
            wired_controller.record_snapshot(resource_type="cpu", utilisation=0.95)
        recs = wired_controller.recommend_scaling()
        assert len(recs) >= 1
        loaded = pm.load_document(recs[0].recommendation_id)
        assert loaded is not None
        assert loaded["resource_type"] == "cpu"


# ------------------------------------------------------------------
# EventBackbone integration
# ------------------------------------------------------------------

class TestEventBackboneIntegration:
    def test_recommend_publishes_event(self, wired_controller, backbone):
        received = []
        backbone.subscribe(EventType.LEARNING_FEEDBACK, lambda e: received.append(e))
        for _ in range(20):
            wired_controller.record_snapshot(resource_type="cpu", utilisation=0.95)
        wired_controller.recommend_scaling()
        backbone.process_pending()
        assert len(received) >= 1
        assert received[0].payload["source"] == "resource_scaling_controller"


# ------------------------------------------------------------------
# Status
# ------------------------------------------------------------------

class TestStatus:
    def test_status(self, controller):
        for _ in range(20):
            controller.record_snapshot(resource_type="cpu", utilisation=0.95)
        controller.recommend_scaling()
        status = controller.get_status()
        assert status["total_snapshots"] == 20
        assert status["total_recommendations"] >= 1
        assert status["persistence_attached"] is False

    def test_cost_tracking(self, controller):
        for _ in range(20):
            controller.record_snapshot(resource_type="cpu", utilisation=0.95)
        recs = controller.recommend_scaling()
        controller.record_decision(
            recommendation_id=recs[0].recommendation_id,
            approved=True,
            actual_cost=25.50,
        )
        status = controller.get_status()
        assert status["total_cost"] == 25.50
