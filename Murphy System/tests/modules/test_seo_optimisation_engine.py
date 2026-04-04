"""
Tests for MKT-002: SEOOptimisationEngine.

Validates SEO content analysis, keyword extraction, meta-tag generation,
scoring, query operations, persistence integration, and EventBackbone publishing.

Design Label: TEST-007 / MKT-002
Owner: QA Team
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from seo_optimisation_engine import (
    SEOOptimisationEngine,
    SEOAnalysis,
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
    return SEOOptimisationEngine()


@pytest.fixture
def wired_engine(pm, backbone):
    return SEOOptimisationEngine(
        persistence_manager=pm,
        event_backbone=backbone,
    )


# ------------------------------------------------------------------
# SEO analysis
# ------------------------------------------------------------------

class TestSEOAnalysis:
    def test_analyse_content_basic(self, engine):
        title = "Best practices for Python testing today"  # ~40 chars
        body = " ".join(["python testing best practices guide"] * 20)  # 500+ chars
        analysis = engine.analyse_content(title=title, body=body, url="https://example.com")
        assert analysis.seo_score > 0

    def test_keyword_extraction(self, engine):
        title = "Python testing guide for developers"
        body = " ".join(["python testing framework unittest pytest"] * 30)
        analysis = engine.analyse_content(title=title, body=body)
        assert len(analysis.top_keywords) > 0

    def test_meta_suggestions(self, engine):
        title = "Comprehensive guide to modern web development"
        body = " ".join(["web development javascript react framework"] * 25)
        analysis = engine.analyse_content(title=title, body=body)
        assert "title_tag" in analysis.meta_suggestions
        assert "description_tag" in analysis.meta_suggestions
        assert "keyword_tags" in analysis.meta_suggestions

    def test_analysis_to_dict(self, engine):
        title = "Testing data model serialisation output"
        body = " ".join(["serialisation data model output testing"] * 20)
        analysis = engine.analyse_content(title=title, body=body)
        d = analysis.to_dict()
        assert "analysis_id" in d
        assert "url" in d
        assert "title" in d
        assert "content_length" in d
        assert "keyword_count" in d
        assert "top_keywords" in d
        assert "meta_suggestions" in d
        assert "seo_score" in d
        assert "issues" in d
        assert "created_at" in d


# ------------------------------------------------------------------
# SEO scoring
# ------------------------------------------------------------------

class TestSEOScoring:
    def test_high_score_content(self, engine):
        # Title 40-60 chars with keyword, body 1500+ chars with 3+ keywords
        title = "Python testing best practices for developers"  # ~45 chars
        body = " ".join(["python testing best practices unittest pytest framework guide"] * 50)
        analysis = engine.analyse_content(title=title, body=body)
        assert analysis.seo_score >= 80

    def test_low_score_content(self, engine):
        title = "Hi"
        body = "Short body text only."
        analysis = engine.analyse_content(title=title, body=body)
        assert analysis.seo_score < 40

    def test_issues_short_title(self, engine):
        title = "Hello"
        body = " ".join(["keyword content text analysis"] * 40)
        analysis = engine.analyse_content(title=title, body=body)
        assert "Title too short" in analysis.issues

    def test_issues_short_body(self, engine):
        title = "A reasonable title for SEO analysis tests"
        body = "Very short body text that is under limit."
        analysis = engine.analyse_content(title=title, body=body)
        assert any("Body" in issue or "body" in issue for issue in analysis.issues)


# ------------------------------------------------------------------
# Query
# ------------------------------------------------------------------

class TestQuery:
    def test_get_analysis(self, engine):
        title = "Query test title for SEO engine analysis"
        body = " ".join(["query test keyword analysis seo"] * 20)
        analysis = engine.analyse_content(title=title, body=body)
        result = engine.get_analysis(analysis.analysis_id)
        assert result is not None
        assert result["analysis_id"] == analysis.analysis_id

    def test_list_analyses(self, engine):
        for i in range(3):
            engine.analyse_content(
                title=f"Title number {i} for listing test here",
                body=" ".join(["listing test keyword content"] * 20),
            )
        results = engine.list_analyses()
        assert len(results) == 3


# ------------------------------------------------------------------
# Persistence integration
# ------------------------------------------------------------------

class TestPersistence:
    def test_analysis_persisted(self, wired_engine, pm):
        title = "Persistence test title for SEO analysis"
        body = " ".join(["persistence test keyword content data"] * 20)
        analysis = wired_engine.analyse_content(title=title, body=body)
        loaded = pm.load_document(analysis.analysis_id)
        assert loaded is not None
        assert loaded["title"] == title


# ------------------------------------------------------------------
# EventBackbone integration
# ------------------------------------------------------------------

class TestEventBackboneIntegration:
    def test_analysis_publishes_event(self, wired_engine, backbone):
        received = []
        backbone.subscribe(EventType.LEARNING_FEEDBACK, lambda e: received.append(e))
        wired_engine.analyse_content(
            title="Event backbone test title for analysis",
            body=" ".join(["event backbone keyword content"] * 20),
        )
        backbone.process_pending()
        assert len(received) >= 1
        assert received[0].payload["source"] == "seo_optimisation_engine"


# ------------------------------------------------------------------
# Status
# ------------------------------------------------------------------

class TestStatus:
    def test_status(self, engine):
        engine.analyse_content(
            title="Status test title for SEO optimisation",
            body=" ".join(["status test keyword content data"] * 20),
        )
        status = engine.get_status()
        assert status["total_analyses"] == 1
        assert status["avg_seo_score"] > 0
