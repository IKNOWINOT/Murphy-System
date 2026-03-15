"""
Tests for SUP-003: FAQGenerationEngine.

Validates question recording, FAQ management, generation cycles,
search, persistence integration, and EventBackbone event publishing.

Design Label: TEST-012 / SUP-003
Owner: QA Team
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from faq_generation_engine import (
    FAQGenerationEngine,
    FAQEntry,
    QuestionRecord,
    FAQGenerationReport,
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
    return FAQGenerationEngine()


@pytest.fixture
def wired_engine(pm, backbone):
    return FAQGenerationEngine(
        persistence_manager=pm,
        event_backbone=backbone,
    )


# ------------------------------------------------------------------
# Question recording
# ------------------------------------------------------------------

class TestQuestionRecording:
    def test_record_question(self, engine):
        q = engine.record_question("How do I reset my password?")
        assert q.question_id.startswith("qst-")
        assert q.normalised != ""

    def test_normalisation(self, engine):
        q1 = engine.record_question("How do I reset my password?")
        q2 = engine.record_question("how do i reset my password")
        assert q1.normalised == q2.normalised

    def test_bounded_questions(self):
        eng = FAQGenerationEngine(max_questions=5)
        for i in range(10):
            eng.record_question(f"Question {i}")
        status = eng.get_status()
        assert status["total_questions"] <= 6


# ------------------------------------------------------------------
# FAQ management
# ------------------------------------------------------------------

class TestFAQManagement:
    def test_add_faq(self, engine):
        faq = engine.add_faq("How to reset?", "Go to settings.", category="account")
        assert faq.faq_id.startswith("faq-")
        assert faq.category == "account"

    def test_update_faq(self, engine):
        faq = engine.add_faq("Q?", "Old answer")
        updated = engine.update_faq(faq.faq_id, answer="New answer")
        assert updated is not None
        assert updated.answer == "New answer"
        assert updated.version == 2

    def test_update_nonexistent(self, engine):
        assert engine.update_faq("nope", answer="X") is None

    def test_record_view(self, engine):
        faq = engine.add_faq("Q?", "A.")
        engine.record_view(faq.faq_id)
        engine.record_view(faq.faq_id)
        result = engine.get_faq(faq.faq_id)
        assert result["views"] == 2

    def test_vote_helpful(self, engine):
        faq = engine.add_faq("Q?", "A.")
        engine.vote_helpful(faq.faq_id, helpful=True)
        engine.vote_helpful(faq.faq_id, helpful=False)
        result = engine.get_faq(faq.faq_id)
        assert result["helpful_votes"] == 1
        assert result["not_helpful_votes"] == 1

    def test_faq_to_dict(self, engine):
        faq = engine.add_faq("Q?", "A.")
        d = faq.to_dict()
        assert "faq_id" in d
        assert "question" in d
        assert "answer" in d


# ------------------------------------------------------------------
# Generation cycle
# ------------------------------------------------------------------

class TestGenerationCycle:
    def test_detect_gaps(self, engine):
        for _ in range(5):
            engine.record_question("How do I export data?")
        report = engine.run_generation_cycle()
        assert report.questions_analysed == 5
        assert report.gaps_detected >= 1

    def test_covered_questions(self, engine):
        for _ in range(5):
            engine.record_question("How do I reset my password?")
        engine.add_faq("How do I reset my password?", "Go to settings.")
        report = engine.run_generation_cycle()
        assert report.faqs_updated >= 1

    def test_below_frequency_threshold(self, engine):
        engine.record_question("Rare question")
        report = engine.run_generation_cycle()
        assert report.gaps_detected == 0

    def test_report_to_dict(self, engine):
        for _ in range(5):
            engine.record_question("Test?")
        report = engine.run_generation_cycle()
        d = report.to_dict()
        assert "report_id" in d
        assert "gaps_detected" in d


# ------------------------------------------------------------------
# Search
# ------------------------------------------------------------------

class TestSearch:
    def test_search_faqs(self, engine):
        engine.add_faq("How to reset password?", "Go to settings.")
        engine.add_faq("How to export data?", "Use the export button.")
        results = engine.search_faqs("reset")
        assert len(results) == 1

    def test_search_no_results(self, engine):
        engine.add_faq("Q?", "A.")
        results = engine.search_faqs("nonexistent")
        assert len(results) == 0


# ------------------------------------------------------------------
# Query
# ------------------------------------------------------------------

class TestQuery:
    def test_get_faq(self, engine):
        faq = engine.add_faq("Q?", "A.")
        result = engine.get_faq(faq.faq_id)
        assert result is not None
        assert result["question"] == "Q?"

    def test_get_faq_not_found(self, engine):
        assert engine.get_faq("nope") is None

    def test_list_faqs(self, engine):
        engine.add_faq("Q1?", "A1.")
        engine.add_faq("Q2?", "A2.")
        faqs = engine.list_faqs()
        assert len(faqs) == 2

    def test_list_faqs_by_category(self, engine):
        engine.add_faq("Q1?", "A1.", category="account")
        engine.add_faq("Q2?", "A2.", category="billing")
        account_only = engine.list_faqs(category="account")
        assert len(account_only) == 1

    def test_frequent_questions(self, engine):
        for _ in range(5):
            engine.record_question("Popular question")
        for _ in range(2):
            engine.record_question("Rare question")
        freq = engine.get_frequent_questions(limit=5)
        assert len(freq) >= 1
        assert freq[0]["count"] >= 5


# ------------------------------------------------------------------
# Persistence
# ------------------------------------------------------------------

class TestPersistence:
    def test_faq_persisted(self, wired_engine, pm):
        faq = wired_engine.add_faq("Q?", "A.")
        loaded = pm.load_document(faq.faq_id)
        assert loaded is not None
        assert loaded["question"] == "Q?"


# ------------------------------------------------------------------
# EventBackbone integration
# ------------------------------------------------------------------

class TestEventBackboneIntegration:
    def test_generation_publishes_event(self, wired_engine, backbone):
        received = []
        backbone.subscribe(EventType.LEARNING_FEEDBACK, lambda e: received.append(e))
        for _ in range(5):
            wired_engine.record_question("Test?")
        wired_engine.run_generation_cycle()
        backbone.process_pending()
        assert len(received) >= 1
        assert received[0].payload["source"] == "faq_generation_engine"


# ------------------------------------------------------------------
# Status
# ------------------------------------------------------------------

class TestStatus:
    def test_status(self, engine):
        engine.add_faq("Q?", "A.")
        engine.record_question("Q?")
        status = engine.get_status()
        assert status["total_faqs"] == 1
        assert status["total_questions"] == 1
        assert status["persistence_attached"] is False

    def test_status_wired(self, wired_engine):
        status = wired_engine.get_status()
        assert status["persistence_attached"] is True
        assert status["backbone_attached"] is True
