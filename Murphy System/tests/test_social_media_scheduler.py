"""
Tests for MKT-004: SocialMediaScheduler.

Validates post lifecycle, scheduling, engagement tracking,
platform analytics, persistence, and EventBackbone integration.

Design Label: TEST-016 / MKT-004
Owner: QA Team
"""

import os
import pytest


from social_media_scheduler import (
    SocialMediaScheduler,
    SocialPost,
    PostStatus,
    EngagementMetric,
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
def sched():
    return SocialMediaScheduler()


@pytest.fixture
def wired_sched(pm, backbone):
    return SocialMediaScheduler(
        persistence_manager=pm,
        event_backbone=backbone,
    )


# ------------------------------------------------------------------
# Post lifecycle
# ------------------------------------------------------------------

class TestPostLifecycle:
    def test_create_post(self, sched):
        post = sched.create_post("twitter", "Hello world!")
        assert post.post_id.startswith("smp-")
        assert post.status == PostStatus.DRAFT

    def test_schedule_post(self, sched):
        post = sched.create_post("linkedin", "Update")
        assert sched.schedule_post(post.post_id, "2026-03-01T12:00:00Z") is True
        info = sched.get_post(post.post_id)
        assert info["status"] == "scheduled"

    def test_publish_post(self, sched):
        post = sched.create_post("twitter", "News")
        assert sched.publish_post(post.post_id) is True
        info = sched.get_post(post.post_id)
        assert info["status"] == "published"

    def test_cannot_publish_twice(self, sched):
        post = sched.create_post("twitter", "Once")
        sched.publish_post(post.post_id)
        assert sched.publish_post(post.post_id) is False

    def test_schedule_nonexistent(self, sched):
        assert sched.schedule_post("nope", "2026-01-01T00:00:00Z") is False

    def test_get_post_nonexistent(self, sched):
        assert sched.get_post("nope") is None


# ------------------------------------------------------------------
# Engagement tracking
# ------------------------------------------------------------------

class TestEngagement:
    def test_record_engagement(self, sched):
        post = sched.create_post("twitter", "test")
        sched.publish_post(post.post_id)
        metric = sched.record_engagement(post.post_id, likes=10, shares=5)
        assert metric is not None
        assert metric.likes == 10
        assert metric.engagement_score == 10 + 5 * 2

    def test_engagement_nonexistent_post(self, sched):
        assert sched.record_engagement("nope") is None

    def test_get_metrics(self, sched):
        post = sched.create_post("twitter", "test")
        sched.record_engagement(post.post_id, likes=1)
        sched.record_engagement(post.post_id, likes=2)
        metrics = sched.get_metrics(post_id=post.post_id)
        assert len(metrics) == 2


# ------------------------------------------------------------------
# Analytics
# ------------------------------------------------------------------

class TestAnalytics:
    def test_platform_summary(self, sched):
        p1 = sched.create_post("twitter", "tw1")
        sched.publish_post(p1.post_id)
        sched.record_engagement(p1.post_id, likes=10)
        p2 = sched.create_post("linkedin", "li1")
        sched.publish_post(p2.post_id)
        sched.record_engagement(p2.post_id, likes=20)
        summary = sched.platform_summary()
        assert "twitter" in summary
        assert summary["twitter"]["likes"] == 10


# ------------------------------------------------------------------
# Query
# ------------------------------------------------------------------

class TestQuery:
    def test_list_posts(self, sched):
        sched.create_post("twitter", "t1")
        sched.create_post("linkedin", "l1")
        assert len(sched.list_posts()) == 2
        assert len(sched.list_posts(platform="twitter")) == 1


# ------------------------------------------------------------------
# Persistence
# ------------------------------------------------------------------

class TestPersistence:
    def test_post_persisted(self, wired_sched, pm):
        post = wired_sched.create_post("twitter", "persisted")
        loaded = pm.load_document(post.post_id)
        assert loaded is not None


# ------------------------------------------------------------------
# EventBackbone
# ------------------------------------------------------------------

class TestEventBackbone:
    def test_publish_fires_event(self, wired_sched, backbone):
        received = []
        backbone.subscribe(EventType.LEARNING_FEEDBACK, lambda e: received.append(e))
        post = wired_sched.create_post("twitter", "evt")
        wired_sched.publish_post(post.post_id)
        backbone.process_pending()
        assert len(received) >= 1


# ------------------------------------------------------------------
# Status
# ------------------------------------------------------------------

class TestStatus:
    def test_status(self, sched):
        sched.create_post("twitter", "t")
        s = sched.get_status()
        assert s["total_posts"] == 1
        assert s["persistence_attached"] is False

    def test_wired_status(self, wired_sched):
        s = wired_sched.get_status()
        assert s["persistence_attached"] is True
