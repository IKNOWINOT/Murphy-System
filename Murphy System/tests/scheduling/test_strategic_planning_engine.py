"""
Tests for BIZ-005: StrategicPlanningEngine.

Validates signal ingestion, plan generation, opportunity scoring,
persistence integration, and EventBackbone event publishing.

Design Label: TEST-019 / BIZ-005
Owner: QA Team
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from strategic_planning_engine import (
    StrategicPlanningEngine,
    MarketSignal,
    Opportunity,
    StrategicPlan,
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
def engine():
    return StrategicPlanningEngine()


@pytest.fixture
def wired_engine(pm, backbone):
    return StrategicPlanningEngine(
        persistence_manager=pm,
        event_backbone=backbone,
    )


# ------------------------------------------------------------------
# Signal ingestion
# ------------------------------------------------------------------

class TestSignalIngestion:
    def test_ingest_signal(self, engine):
        sig = engine.ingest_signal("trend", "AI adoption", 0.9)
        assert sig.signal_id.startswith("ms-")
        assert sig.impact_score == 0.9

    def test_clamps_impact(self, engine):
        sig = engine.ingest_signal("trend", "Overshoot", 1.5)
        assert sig.impact_score == 1.0
        sig2 = engine.ingest_signal("trend", "Undershoot", -0.5)
        assert sig2.impact_score == 0.0

    def test_normalises_category(self, engine):
        sig = engine.ingest_signal("  Trend  ", "Test", 0.5)
        assert sig.category == "trend"

    def test_bounded(self):
        eng = StrategicPlanningEngine(max_signals=5)
        for i in range(10):
            eng.ingest_signal("trend", f"Signal {i}", 0.5)
        s = eng.get_status()
        assert s["total_signals"] <= 6


# ------------------------------------------------------------------
# Plan generation
# ------------------------------------------------------------------

class TestPlanGeneration:
    def test_generate_plan(self, engine):
        engine.ingest_signal("trend", "AI accelerating", 0.9)
        engine.ingest_signal("trend", "AI regulation", 0.7)
        engine.ingest_signal("competitor", "New entrant", 0.8)
        engine.ingest_signal("competitor", "Acquisition", 0.6)
        plan = engine.generate_plan("Q2 Strategy")
        assert plan.plan_id.startswith("sp-")
        assert plan.total_signals_analysed == 4
        assert plan.opportunities_identified >= 2

    def test_min_signals_threshold(self, engine):
        engine.ingest_signal("trend", "Lonely signal", 0.9)
        plan = engine.generate_plan()
        assert plan.opportunities_identified == 0

    def test_custom_min_signals(self):
        eng = StrategicPlanningEngine(min_signals=1)
        eng.ingest_signal("trend", "Single", 0.8)
        plan = eng.generate_plan()
        assert plan.opportunities_identified == 1

    def test_plan_to_dict(self, engine):
        engine.ingest_signal("trend", "A", 0.5)
        engine.ingest_signal("trend", "B", 0.6)
        plan = engine.generate_plan()
        d = plan.to_dict()
        assert "plan_id" in d
        assert "top_opportunities" in d
        assert "summary" in d

    def test_opportunity_ranking(self, engine):
        for _ in range(5):
            engine.ingest_signal("trend", "High impact", 0.95)
        for _ in range(5):
            engine.ingest_signal("competitor", "Low impact", 0.2)
        plan = engine.generate_plan()
        assert len(plan.top_opportunities) >= 2
        # First opportunity should have higher composite score
        assert plan.top_opportunities[0].composite_score >= plan.top_opportunities[1].composite_score

    def test_empty_plan(self, engine):
        plan = engine.generate_plan()
        assert plan.total_signals_analysed == 0
        assert plan.opportunities_identified == 0


# ------------------------------------------------------------------
# Query
# ------------------------------------------------------------------

class TestQuery:
    def test_get_signals(self, engine):
        engine.ingest_signal("trend", "A", 0.5)
        engine.ingest_signal("competitor", "B", 0.6)
        all_sigs = engine.get_signals()
        assert len(all_sigs) == 2
        trend_only = engine.get_signals(category="trend")
        assert len(trend_only) == 1

    def test_get_plans(self, engine):
        engine.ingest_signal("trend", "A", 0.5)
        engine.ingest_signal("trend", "B", 0.6)
        engine.generate_plan()
        plans = engine.get_plans()
        assert len(plans) == 1


# ------------------------------------------------------------------
# Persistence
# ------------------------------------------------------------------

class TestPersistence:
    def test_plan_persisted(self, wired_engine, pm):
        wired_engine.ingest_signal("trend", "A", 0.5)
        wired_engine.ingest_signal("trend", "B", 0.6)
        plan = wired_engine.generate_plan()
        loaded = pm.load_document(plan.plan_id)
        assert loaded is not None


# ------------------------------------------------------------------
# EventBackbone
# ------------------------------------------------------------------

class TestEventBackbone:
    def test_plan_publishes_event(self, wired_engine, backbone):
        received = []
        backbone.subscribe(EventType.LEARNING_FEEDBACK, lambda e: received.append(e))
        wired_engine.ingest_signal("trend", "A", 0.5)
        wired_engine.ingest_signal("trend", "B", 0.6)
        wired_engine.generate_plan()
        backbone.process_pending()
        assert len(received) >= 1


# ------------------------------------------------------------------
# Status
# ------------------------------------------------------------------

class TestStatus:
    def test_status(self, engine):
        engine.ingest_signal("trend", "A", 0.5)
        s = engine.get_status()
        assert s["total_signals"] == 1
        assert s["total_plans"] == 0
        assert s["persistence_attached"] is False

    def test_wired_status(self, wired_engine):
        s = wired_engine.get_status()
        assert s["persistence_attached"] is True
        assert s["backbone_attached"] is True
