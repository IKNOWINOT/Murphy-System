"""
Tests for MKT-003: CampaignOrchestrator.

Validates campaign creation, lifecycle transitions, budget enforcement,
spend tracking, query operations, persistence integration,
and EventBackbone event publishing.

Design Label: TEST-007 / MKT-003
Owner: QA Team
"""

import os
import pytest


from campaign_orchestrator import (
    CampaignOrchestrator,
    Campaign,
    CampaignChannel,
    CampaignStatus,
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
    return CampaignOrchestrator()


@pytest.fixture
def wired_engine(pm, backbone):
    return CampaignOrchestrator(
        persistence_manager=pm,
        event_backbone=backbone,
    )


def _channels(budgets=None):
    """Helper to build a channel list."""
    budgets = budgets or [("email", 2000), ("social", 3000)]
    return [{"name": n, "budget": b} for n, b in budgets]


# ------------------------------------------------------------------
# Campaign creation
# ------------------------------------------------------------------

class TestCampaignCreation:
    def test_create_campaign(self, engine):
        campaign = engine.create_campaign(
            name="Summer Sale",
            total_budget=5000.0,
            channels=_channels(),
        )
        assert campaign.campaign_id.startswith("cmp-")
        assert campaign.name == "Summer Sale"
        assert campaign.total_budget == 5000.0

    def test_campaign_to_dict(self, engine):
        campaign = engine.create_campaign(
            name="Test Campaign",
            total_budget=1000.0,
            channels=_channels(),
        )
        d = campaign.to_dict()
        assert "campaign_id" in d
        assert "name" in d
        assert "status" in d
        assert "total_budget" in d
        assert "total_spent" in d
        assert "budget_remaining" in d
        assert "channels" in d
        assert "created_at" in d
        assert "updated_at" in d

    def test_channels_created(self, engine):
        campaign = engine.create_campaign(
            name="Multi-channel",
            total_budget=5000.0,
            channels=_channels([("email", 2000), ("social", 3000)]),
        )
        assert len(campaign.channels) == 2


# ------------------------------------------------------------------
# Campaign lifecycle
# ------------------------------------------------------------------

class TestCampaignLifecycle:
    def _make_campaign(self, engine):
        return engine.create_campaign(
            name="Lifecycle Campaign",
            total_budget=5000.0,
            channels=_channels(),
        )

    def test_launch_campaign(self, engine):
        c = self._make_campaign(engine)
        result = engine.launch_campaign(c.campaign_id)
        assert result is not None
        assert result.status == CampaignStatus.ACTIVE

    def test_record_spend(self, engine):
        c = self._make_campaign(engine)
        engine.launch_campaign(c.campaign_id)
        result = engine.record_spend(c.campaign_id, "email", 150.0, impressions=5000)
        assert result is not None
        assert result.channels["email"].spent == 150.0

    def test_budget_enforcement(self, engine):
        c = self._make_campaign(engine)
        engine.launch_campaign(c.campaign_id)
        result = engine.record_spend(c.campaign_id, "email", 9999.0)
        assert result is None  # rejected: exceeds channel budget

    def test_pause_campaign(self, engine):
        c = self._make_campaign(engine)
        engine.launch_campaign(c.campaign_id)
        result = engine.pause_campaign(c.campaign_id)
        assert result is not None
        assert result.status == CampaignStatus.PAUSED

    def test_resume_campaign(self, engine):
        c = self._make_campaign(engine)
        engine.launch_campaign(c.campaign_id)
        engine.pause_campaign(c.campaign_id)
        result = engine.resume_campaign(c.campaign_id)
        assert result is not None
        assert result.status == CampaignStatus.ACTIVE

    def test_complete_campaign(self, engine):
        c = self._make_campaign(engine)
        engine.launch_campaign(c.campaign_id)
        result = engine.complete_campaign(c.campaign_id)
        assert result is not None
        assert result.status == CampaignStatus.COMPLETED

    def test_cancel_planned(self, engine):
        c = self._make_campaign(engine)
        result = engine.cancel_campaign(c.campaign_id)
        assert result is not None
        assert result.status == CampaignStatus.CANCELLED


# ------------------------------------------------------------------
# Performance
# ------------------------------------------------------------------

class TestPerformance:
    def test_get_performance(self, engine):
        c = engine.create_campaign(
            name="Perf Campaign",
            total_budget=5000.0,
            channels=_channels(),
        )
        engine.launch_campaign(c.campaign_id)
        engine.record_spend(c.campaign_id, "email", 200.0, impressions=1000, clicks=50)
        perf = engine.get_performance(c.campaign_id)
        assert perf is not None
        assert "roi_indicators" in perf


# ------------------------------------------------------------------
# Query
# ------------------------------------------------------------------

class TestQuery:
    def test_get_campaign(self, engine):
        c = engine.create_campaign(
            name="Query Campaign",
            total_budget=1000.0,
            channels=_channels(),
        )
        result = engine.get_campaign(c.campaign_id)
        assert result is not None
        assert result["name"] == "Query Campaign"

    def test_list_campaigns(self, engine):
        for i in range(3):
            engine.create_campaign(
                name=f"Campaign {i}",
                total_budget=1000.0,
                channels=_channels(),
            )
        results = engine.list_campaigns()
        assert len(results) == 3

    def test_filter_by_status(self, engine):
        c1 = engine.create_campaign(name="A", total_budget=1000.0, channels=_channels())
        c2 = engine.create_campaign(name="B", total_budget=1000.0, channels=_channels())
        engine.launch_campaign(c1.campaign_id)
        active = engine.list_campaigns(status="active")
        assert len(active) == 1


# ------------------------------------------------------------------
# Persistence integration
# ------------------------------------------------------------------

class TestPersistence:
    def test_campaign_persisted(self, wired_engine, pm):
        c = wired_engine.create_campaign(
            name="Persist Campaign",
            total_budget=3000.0,
            channels=_channels(),
        )
        wired_engine.launch_campaign(c.campaign_id)
        loaded = pm.load_document(c.campaign_id)
        assert loaded is not None
        assert loaded["status"] == "active"


# ------------------------------------------------------------------
# EventBackbone integration
# ------------------------------------------------------------------

class TestEventBackboneIntegration:
    def test_launch_publishes_event(self, wired_engine, backbone):
        received = []
        backbone.subscribe(EventType.LEARNING_FEEDBACK, lambda e: received.append(e))
        c = wired_engine.create_campaign(
            name="Event Campaign",
            total_budget=2000.0,
            channels=_channels(),
        )
        wired_engine.launch_campaign(c.campaign_id)
        backbone.process_pending()
        assert len(received) >= 1
        assert received[-1].payload["source"] == "campaign_orchestrator"


# ------------------------------------------------------------------
# Status
# ------------------------------------------------------------------

class TestStatus:
    def test_status(self, engine):
        engine.create_campaign(name="S1", total_budget=1000.0, channels=_channels())
        engine.create_campaign(name="S2", total_budget=2000.0, channels=_channels())
        status = engine.get_status()
        assert status["total_campaigns"] == 2
        assert status["total_budget_allocated"] == 3000.0
