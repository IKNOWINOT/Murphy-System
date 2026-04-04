"""
Tests for BIZ-004: ComplianceReportAggregator.

Validates check ingestion, violation detection, report generation,
framework scoring, persistence, and EventBackbone integration.

Design Label: TEST-018 / BIZ-004
Owner: QA Team
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from compliance_report_aggregator import (
    ComplianceReportAggregator,
    ComplianceCheck,
    ComplianceViolation,
    ComplianceSummaryReport,
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
def agg():
    return ComplianceReportAggregator()


@pytest.fixture
def wired_agg(pm, backbone):
    return ComplianceReportAggregator(
        persistence_manager=pm,
        event_backbone=backbone,
    )


# ------------------------------------------------------------------
# Check ingestion
# ------------------------------------------------------------------

class TestCheckIngestion:
    def test_ingest_check(self, agg):
        check = agg.ingest_check("GDPR", "GDPR-1", "Data minimisation", True)
        assert check.check_id.startswith("cc-")
        assert check.framework == "GDPR"
        assert check.passed is True

    def test_normalises_framework(self, agg):
        check = agg.ingest_check("  gdpr  ", "G-1", "Test", True)
        assert check.framework == "GDPR"

    def test_bounded(self):
        a = ComplianceReportAggregator(max_checks=5)
        for i in range(10):
            a.ingest_check("SOC2", f"C{i}", f"Control {i}", True)
        s = a.get_status()
        assert s["total_checks"] <= 6


# ------------------------------------------------------------------
# Report generation
# ------------------------------------------------------------------

class TestReportGeneration:
    def test_all_pass(self, agg):
        agg.ingest_check("GDPR", "G-1", "Data min", True)
        agg.ingest_check("GDPR", "G-2", "Consent", True)
        report = agg.generate_report()
        assert report.total_passed == 2
        assert report.total_failed == 0
        assert report.overall_score == 1.0
        assert len(report.violations) == 0

    def test_mixed_results(self, agg):
        agg.ingest_check("SOC2", "CC6.1", "Logical access", True)
        agg.ingest_check("SOC2", "CC6.2", "Encryption", False, "Weak cipher")
        report = agg.generate_report()
        assert report.total_passed == 1
        assert report.total_failed == 1
        assert report.overall_score == 0.5
        assert len(report.violations) == 1

    def test_multi_framework(self, agg):
        agg.ingest_check("GDPR", "G-1", "Test", True)
        agg.ingest_check("SOC2", "CC1", "Test", False)
        report = agg.generate_report()
        assert "GDPR" in report.framework_scores
        assert "SOC2" in report.framework_scores
        assert report.framework_scores["GDPR"] == 1.0
        assert report.framework_scores["SOC2"] == 0.0

    def test_report_to_dict(self, agg):
        agg.ingest_check("HIPAA", "H-1", "PHI", True)
        report = agg.generate_report()
        d = report.to_dict()
        assert "report_id" in d
        assert "overall_score" in d
        assert "violations" in d

    def test_empty_report(self, agg):
        report = agg.generate_report()
        assert report.total_checks == 0
        assert report.overall_score == 1.0


# ------------------------------------------------------------------
# Violations query
# ------------------------------------------------------------------

class TestViolations:
    def test_get_violations(self, agg):
        agg.ingest_check("SOC2", "C1", "Test", False, "Issue")
        agg.ingest_check("SOC2", "C2", "Test2", True)
        violations = agg.get_violations()
        assert len(violations) == 1

    def test_filter_by_framework(self, agg):
        agg.ingest_check("GDPR", "G-1", "Test", False)
        agg.ingest_check("SOC2", "C1", "Test", False)
        gdpr_only = agg.get_violations(framework="GDPR")
        assert len(gdpr_only) == 1


# ------------------------------------------------------------------
# Persistence
# ------------------------------------------------------------------

class TestPersistence:
    def test_report_persisted(self, wired_agg, pm):
        wired_agg.ingest_check("GDPR", "G-1", "Test", True)
        report = wired_agg.generate_report()
        loaded = pm.load_document(report.report_id)
        assert loaded is not None


# ------------------------------------------------------------------
# EventBackbone
# ------------------------------------------------------------------

class TestEventBackbone:
    def test_report_publishes_event(self, wired_agg, backbone):
        received = []
        backbone.subscribe(EventType.LEARNING_FEEDBACK, lambda e: received.append(e))
        wired_agg.ingest_check("GDPR", "G-1", "Test", True)
        wired_agg.generate_report()
        backbone.process_pending()
        assert len(received) >= 1


# ------------------------------------------------------------------
# Status
# ------------------------------------------------------------------

class TestStatus:
    def test_status(self, agg):
        agg.ingest_check("GDPR", "G-1", "Test", True)
        s = agg.get_status()
        assert s["total_checks"] == 1
        assert s["persistence_attached"] is False

    def test_wired_status(self, wired_agg):
        s = wired_agg.get_status()
        assert s["persistence_attached"] is True
