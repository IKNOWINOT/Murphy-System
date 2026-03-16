"""
Tests for SUP-002: KnowledgeBaseManager.

Validates article management, search, knowledge gap detection,
ticket knowledge extraction, and EventBackbone integration.

Design Label: TEST-003 / SUP-002
Owner: QA Team
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from knowledge_base_manager import (
    KnowledgeBaseManager,
    KBArticle,
    KBSearchResult,
    KnowledgeGap,
)
from event_backbone import EventBackbone, EventType


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def backbone():
    return EventBackbone()


@pytest.fixture
def kb():
    return KnowledgeBaseManager()


@pytest.fixture
def wired_kb(backbone):
    return KnowledgeBaseManager(event_backbone=backbone)


# ------------------------------------------------------------------
# Article management
# ------------------------------------------------------------------

class TestArticleManagement:
    def test_add_article(self, kb):
        article = kb.add_article(
            title="How to reset password",
            content="Go to settings > security > reset password.",
            category="authentication",
            tags=["password", "reset"],
        )
        assert article.article_id.startswith("kb-")
        assert article.title == "How to reset password"
        assert article.version == 1

    def test_update_article(self, kb):
        article = kb.add_article(title="Test", content="V1")
        updated = kb.update_article(
            article.article_id,
            content="V2",
            title="Updated Test",
        )
        assert updated is not None
        assert updated.content == "V2"
        assert updated.title == "Updated Test"
        assert updated.version == 2

    def test_update_nonexistent_returns_none(self, kb):
        assert kb.update_article("nonexistent", content="x") is None

    def test_get_article_increments_views(self, kb):
        article = kb.add_article(title="Test", content="Content")
        assert article.views == 0
        kb.get_article(article.article_id)
        fetched = kb.get_article(article.article_id)
        assert fetched.views == 2

    def test_list_articles(self, kb):
        kb.add_article(title="A1", content="C1", category="auth")
        kb.add_article(title="A2", content="C2", category="billing")
        kb.add_article(title="A3", content="C3", category="auth")
        all_articles = kb.list_articles()
        assert len(all_articles) == 3
        auth_only = kb.list_articles(category="auth")
        assert len(auth_only) == 2

    def test_max_articles_eviction(self):
        kb = KnowledgeBaseManager(max_articles=2)
        kb.add_article(title="A1", content="C1")
        kb.add_article(title="A2", content="C2")
        kb.add_article(title="A3", content="C3")
        articles = kb.list_articles()
        assert len(articles) == 2

    def test_article_to_dict(self, kb):
        article = kb.add_article(title="Test", content="Content")
        d = article.to_dict()
        assert "article_id" in d
        assert "title" in d
        assert "version" in d


# ------------------------------------------------------------------
# Search
# ------------------------------------------------------------------

class TestSearch:
    def test_keyword_fallback_search(self, kb):
        kb.add_article(
            title="Password reset guide",
            content="To reset your password, go to the settings page.",
        )
        results = kb.search("password reset")
        assert len(results) >= 1
        assert results[0].score > 0

    def test_no_results_for_unrelated(self, kb):
        kb.add_article(title="API docs", content="How to call the REST API")
        results = kb.search("quantum physics experiments")
        assert len(results) == 0

    def test_search_result_to_dict(self, kb):
        kb.add_article(title="Test", content="Test content here")
        results = kb.search("test")
        assert len(results) >= 1
        d = results[0].to_dict()
        assert "article_id" in d
        assert "score" in d


# ------------------------------------------------------------------
# Knowledge gap detection
# ------------------------------------------------------------------

class TestGapDetection:
    def test_detect_gap_on_poor_matches(self, kb):
        # Search for something not in KB multiple times
        kb.search("deployment automation pipeline")
        kb.search("deployment automation pipeline")
        kb.search("deployment automation pipeline")
        gaps = kb.detect_gaps(min_frequency=2)
        assert len(gaps) >= 1
        assert gaps[0].frequency >= 2
        assert gaps[0].best_score < 0.3

    def test_no_gap_for_infrequent_queries(self, kb):
        kb.search("one-off query xyz")
        gaps = kb.detect_gaps(min_frequency=2)
        assert len(gaps) == 0

    def test_no_gap_when_articles_match(self, kb):
        kb.add_article(
            title="Deployment guide",
            content="How to deploy using the automation pipeline",
        )
        kb.search("deployment automation pipeline")
        kb.search("deployment automation pipeline")
        gaps = kb.detect_gaps(min_frequency=2)
        # Gap should not be detected since articles match
        matching = [g for g in gaps if "deployment" in g.query]
        if matching:
            assert matching[0].best_score >= 0.3

    def test_gap_to_dict(self, kb):
        kb.search("missing topic abc")
        kb.search("missing topic abc")
        gaps = kb.detect_gaps(min_frequency=2)
        assert len(gaps) >= 1
        d = gaps[0].to_dict()
        assert "gap_id" in d
        assert "frequency" in d


# ------------------------------------------------------------------
# Ticket extraction
# ------------------------------------------------------------------

class TestTicketExtraction:
    def test_extract_creates_article(self, kb):
        article = kb.extract_from_ticket(
            ticket_id="TKT-001",
            title="Login failure",
            description="Users cannot log in after password change.",
            resolution="Cleared browser cache and cookies.",
            category="authentication",
        )
        assert article.source_ticket_id == "TKT-001"
        assert "Resolved:" in article.title
        assert "## Problem" in article.content
        assert "## Resolution" in article.content


# ------------------------------------------------------------------
# EventBackbone integration
# ------------------------------------------------------------------

class TestEventBackboneIntegration:
    def test_gaps_publish_learning_feedback(self, wired_kb, backbone):
        received = []
        backbone.subscribe(EventType.LEARNING_FEEDBACK, lambda e: received.append(e))
        wired_kb.search("missing knowledge xyz")
        wired_kb.search("missing knowledge xyz")
        wired_kb.detect_gaps(min_frequency=2)
        backbone.process_pending()
        assert len(received) >= 1
        assert received[0].payload["source"] == "knowledge_base_manager"


# ------------------------------------------------------------------
# Status
# ------------------------------------------------------------------

class TestStatus:
    def test_status_reflects_state(self, kb):
        kb.add_article(title="Test", content="Content", category="auth")
        status = kb.get_status()
        assert status["total_articles"] == 1
        assert "auth" in status["categories"]
        assert status["rag_attached"] is False
        assert status["backbone_attached"] is False

    def test_status_with_backbone(self, wired_kb):
        status = wired_kb.get_status()
        assert status["backbone_attached"] is True
