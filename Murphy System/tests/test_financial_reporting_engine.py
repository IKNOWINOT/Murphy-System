"""
Tests for BIZ-001: FinancialReportingEngine.

Validates entry recording, report generation, trend computation,
persistence integration, and EventBackbone event publishing.

Design Label: TEST-005 / BIZ-001
Owner: QA Team
"""

import os
import pytest


from financial_reporting_engine import (
    FinancialReportingEngine,
    FinancialEntry,
    FinancialReport,
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
    return FinancialReportingEngine()


@pytest.fixture
def wired_engine(pm, backbone):
    return FinancialReportingEngine(
        persistence_manager=pm,
        event_backbone=backbone,
    )


# ------------------------------------------------------------------
# Entry recording
# ------------------------------------------------------------------

class TestEntryRecording:
    def test_record_entry(self, engine):
        entry = engine.record_entry(category="revenue", amount=1000.0, source="customer-A")
        assert entry.entry_id.startswith("fin-")
        assert entry.category == "revenue"
        assert entry.amount == 1000.0

    def test_record_multiple_entries(self, engine):
        engine.record_entry(category="revenue", amount=500.0)
        engine.record_entry(category="expense", amount=200.0)
        engine.record_entry(category="refund", amount=50.0)
        entries = engine.get_entries()
        assert len(entries) == 3

    def test_entry_to_dict(self, engine):
        entry = engine.record_entry(category="revenue", amount=100.0)
        d = entry.to_dict()
        assert "entry_id" in d
        assert "category" in d
        assert "amount" in d

    def test_bounded_entries(self):
        eng = FinancialReportingEngine(max_entries=5)
        for i in range(10):
            eng.record_entry(category="revenue", amount=float(i))
        entries = eng.get_entries(limit=100)
        assert len(entries) <= 6  # max 5 + eviction buffer

    def test_filter_by_category(self, engine):
        engine.record_entry(category="revenue", amount=100.0)
        engine.record_entry(category="expense", amount=50.0)
        revenue_only = engine.get_entries(category="revenue")
        assert len(revenue_only) == 1
        assert revenue_only[0]["category"] == "revenue"


# ------------------------------------------------------------------
# Report generation
# ------------------------------------------------------------------

class TestReportGeneration:
    def test_generate_report(self, engine):
        engine.record_entry(category="revenue", amount=1000.0)
        engine.record_entry(category="expense", amount=300.0)
        engine.record_entry(category="refund", amount=50.0)
        report = engine.generate_report(period_label="2026-Q1")
        assert report.report_id.startswith("rpt-")
        assert report.total_revenue == 1000.0
        assert report.total_expenses == 350.0  # expense + refund
        assert report.net_income == 650.0
        assert report.entry_count == 3

    def test_report_trends(self, engine):
        engine.record_entry(category="revenue", amount=1000.0)
        engine.record_entry(category="expense", amount=500.0)
        report = engine.generate_report()
        assert report.trend_indicators["profit_margin"] == 0.5
        assert report.trend_indicators["revenue_expense_ratio"] == 2.0

    def test_report_with_no_entries(self, engine):
        report = engine.generate_report()
        assert report.total_revenue == 0.0
        assert report.net_income == 0.0

    def test_report_to_dict(self, engine):
        engine.record_entry(category="revenue", amount=100.0)
        report = engine.generate_report()
        d = report.to_dict()
        assert "report_id" in d
        assert "total_revenue" in d
        assert "trend_indicators" in d

    def test_report_history(self, engine):
        engine.record_entry(category="revenue", amount=100.0)
        engine.generate_report(period_label="Q1")
        engine.generate_report(period_label="Q2")
        reports = engine.get_reports()
        assert len(reports) == 2


# ------------------------------------------------------------------
# Persistence integration
# ------------------------------------------------------------------

class TestPersistence:
    def test_report_persisted(self, wired_engine, pm):
        wired_engine.record_entry(category="revenue", amount=500.0)
        report = wired_engine.generate_report()
        loaded = pm.load_document(report.report_id)
        assert loaded is not None
        assert loaded["total_revenue"] == 500.0


# ------------------------------------------------------------------
# EventBackbone integration
# ------------------------------------------------------------------

class TestEventBackboneIntegration:
    def test_report_publishes_event(self, wired_engine, backbone):
        received = []
        backbone.subscribe(EventType.LEARNING_FEEDBACK, lambda e: received.append(e))
        wired_engine.record_entry(category="revenue", amount=200.0)
        wired_engine.generate_report()
        backbone.process_pending()
        assert len(received) >= 1
        assert received[0].payload["source"] == "financial_reporting_engine"


# ------------------------------------------------------------------
# Status
# ------------------------------------------------------------------

class TestStatus:
    def test_status_reflects_state(self, engine):
        engine.record_entry(category="revenue", amount=100.0)
        status = engine.get_status()
        assert status["total_entries"] == 1
        assert status["total_reports"] == 0
        assert status["persistence_attached"] is False

    def test_status_with_persistence(self, wired_engine):
        status = wired_engine.get_status()
        assert status["persistence_attached"] is True
        assert status["backbone_attached"] is True
