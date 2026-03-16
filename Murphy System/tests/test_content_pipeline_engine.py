"""
Tests for MKT-001: ContentPipelineEngine.

Validates brief creation, content lifecycle transitions, metrics tracking,
query operations, persistence integration, and EventBackbone event publishing.

Design Label: TEST-007 / MKT-001
Owner: QA Team
"""

import os
import pytest


from content_pipeline_engine import (
    ContentPipelineEngine,
    ContentBrief,
    ContentItem,
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
    return ContentPipelineEngine()


@pytest.fixture
def wired_engine(pm, backbone):
    return ContentPipelineEngine(
        persistence_manager=pm,
        event_backbone=backbone,
    )


# ------------------------------------------------------------------
# Brief creation
# ------------------------------------------------------------------

class TestBriefCreation:
    def test_create_brief(self, engine):
        brief = engine.create_brief(
            topic="Q3 Product Update",
            content_type="blog",
            target_channels=["blog", "twitter"],
        )
        assert brief.brief_id.startswith("brief-")
        assert brief.topic == "Q3 Product Update"
        assert brief.content_type == "blog"

    def test_brief_to_dict(self, engine):
        brief = engine.create_brief(topic="Test", content_type="email")
        d = brief.to_dict()
        assert "brief_id" in d
        assert "topic" in d
        assert "content_type" in d
        assert "target_channels" in d
        assert "keywords" in d
        assert "tone" in d
        assert "created_at" in d

    def test_list_briefs(self, engine):
        engine.create_brief(topic="Topic A", content_type="blog")
        engine.create_brief(topic="Topic B", content_type="social")
        briefs = engine.get_briefs()
        assert len(briefs) == 2


# ------------------------------------------------------------------
# Content lifecycle
# ------------------------------------------------------------------

class TestContentLifecycle:
    def _make_draft(self, engine):
        brief = engine.create_brief(topic="Lifecycle test", content_type="blog")
        return engine.create_draft(brief.brief_id, "Title", "Body text")

    def test_create_draft(self, engine):
        draft = self._make_draft(engine)
        assert draft.item_id.startswith("cnt-")
        assert draft.status == "draft"

    def test_submit_for_review(self, engine):
        draft = self._make_draft(engine)
        item = engine.submit_for_review(draft.item_id)
        assert item.status == "review"

    def test_approve_content(self, engine):
        draft = self._make_draft(engine)
        engine.submit_for_review(draft.item_id)
        item = engine.approve_content(draft.item_id)
        assert item.status == "approved"

    def test_schedule_content(self, engine):
        draft = self._make_draft(engine)
        engine.submit_for_review(draft.item_id)
        engine.approve_content(draft.item_id)
        item = engine.schedule_content(draft.item_id, "2026-07-01T10:00:00Z")
        assert item.status == "scheduled"

    def test_publish_content(self, engine):
        draft = self._make_draft(engine)
        engine.submit_for_review(draft.item_id)
        engine.approve_content(draft.item_id)
        item = engine.publish_content(draft.item_id)
        assert item.status == "published"
        assert item.published_at is not None

    def test_full_lifecycle(self, engine):
        draft = self._make_draft(engine)
        engine.submit_for_review(draft.item_id)
        engine.approve_content(draft.item_id)
        engine.schedule_content(draft.item_id, "2026-07-01T10:00:00Z")
        item = engine.publish_content(draft.item_id)
        assert item.status == "published"

    def test_cannot_publish_draft(self, engine):
        draft = self._make_draft(engine)
        with pytest.raises(ValueError):
            engine.publish_content(draft.item_id)


# ------------------------------------------------------------------
# Metrics
# ------------------------------------------------------------------

class TestMetrics:
    def test_record_metrics(self, engine):
        brief = engine.create_brief(topic="Metrics test", content_type="blog")
        draft = engine.create_draft(brief.brief_id, "Title", "Body")
        engine.submit_for_review(draft.item_id)
        engine.approve_content(draft.item_id)
        engine.publish_content(draft.item_id)
        item = engine.record_metrics(draft.item_id, views=100, clicks=10)
        assert item.performance_metrics["views"] == 100
        assert item.performance_metrics["clicks"] == 10

    def test_metrics_in_dict(self, engine):
        brief = engine.create_brief(topic="Dict test", content_type="blog")
        draft = engine.create_draft(brief.brief_id, "Title", "Body")
        engine.submit_for_review(draft.item_id)
        engine.approve_content(draft.item_id)
        engine.publish_content(draft.item_id)
        engine.record_metrics(draft.item_id, views=50, clicks=5)
        d = engine.get_content(draft.item_id)
        assert "views" in d["performance_metrics"]
        assert "clicks" in d["performance_metrics"]


# ------------------------------------------------------------------
# Query
# ------------------------------------------------------------------

class TestQuery:
    def test_get_content(self, engine):
        brief = engine.create_brief(topic="Query test", content_type="blog")
        draft = engine.create_draft(brief.brief_id, "My Title", "Body")
        result = engine.get_content(draft.item_id)
        assert result is not None
        assert result["title"] == "My Title"

    def test_list_content(self, engine):
        brief = engine.create_brief(topic="List test", content_type="blog")
        engine.create_draft(brief.brief_id, "A", "Body A")
        engine.create_draft(brief.brief_id, "B", "Body B")
        engine.create_draft(brief.brief_id, "C", "Body C")
        items = engine.list_content()
        assert len(items) == 3

    def test_filter_by_status(self, engine):
        brief = engine.create_brief(topic="Filter test", content_type="blog")
        d1 = engine.create_draft(brief.brief_id, "Draft", "Body")
        d2 = engine.create_draft(brief.brief_id, "Approved", "Body")
        engine.submit_for_review(d2.item_id)
        engine.approve_content(d2.item_id)
        approved = engine.list_content(status="approved")
        assert len(approved) == 1


# ------------------------------------------------------------------
# Persistence integration
# ------------------------------------------------------------------

class TestPersistence:
    def test_content_persisted(self, wired_engine, pm):
        brief = wired_engine.create_brief(topic="Persist test", content_type="blog")
        draft = wired_engine.create_draft(brief.brief_id, "Title", "Body")
        wired_engine.submit_for_review(draft.item_id)
        wired_engine.approve_content(draft.item_id)
        wired_engine.publish_content(draft.item_id)
        loaded = pm.load_document(draft.item_id)
        assert loaded is not None
        assert loaded["status"] == "published"


# ------------------------------------------------------------------
# EventBackbone integration
# ------------------------------------------------------------------

class TestEventBackboneIntegration:
    def test_publish_publishes_event(self, wired_engine, backbone):
        received = []
        backbone.subscribe(EventType.LEARNING_FEEDBACK, lambda e: received.append(e))
        brief = wired_engine.create_brief(topic="Event test", content_type="blog")
        draft = wired_engine.create_draft(brief.brief_id, "Title", "Body")
        wired_engine.submit_for_review(draft.item_id)
        wired_engine.approve_content(draft.item_id)
        wired_engine.publish_content(draft.item_id)
        backbone.process_pending()
        assert len(received) >= 1
        assert received[-1].payload["source"] == "content_pipeline_engine"


# ------------------------------------------------------------------
# Status
# ------------------------------------------------------------------

class TestStatus:
    def test_status_reflects_state(self, engine):
        brief = engine.create_brief(topic="Status test", content_type="blog")
        engine.create_draft(brief.brief_id, "A", "Body A")
        engine.create_draft(brief.brief_id, "B", "Body B")
        status = engine.get_status()
        assert status["total_content"] == 2
        assert status["total_briefs"] == 1
        assert status["persistence_attached"] is False

    def test_status_with_persistence(self, wired_engine):
        status = wired_engine.get_status()
        assert status["persistence_attached"] is True
        assert status["backbone_attached"] is True
