"""
Tests for DEV-004: BugPatternDetector.

Validates error ingestion, pattern detection, severity classification,
persistence integration, and EventBackbone event publishing.

Design Label: TEST-011 / DEV-004
Owner: QA Team
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from bug_pattern_detector import (
    BugPatternDetector,
    ErrorRecord,
    BugPattern,
    BugReport,
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
def detector():
    return BugPatternDetector()


@pytest.fixture
def wired_detector(pm, backbone):
    return BugPatternDetector(
        persistence_manager=pm,
        event_backbone=backbone,
    )


# ------------------------------------------------------------------
# Error ingestion
# ------------------------------------------------------------------

class TestErrorIngestion:
    def test_ingest_error(self, detector):
        err = detector.ingest_error(message="Connection timeout", component="api-gw")
        assert err.error_id.startswith("err-")
        assert err.message == "Connection timeout"
        assert err.fingerprint != ""

    def test_fingerprint_stability(self, detector):
        e1 = detector.ingest_error(message="Connection timeout", component="api-gw")
        e2 = detector.ingest_error(message="Connection timeout", component="api-gw")
        assert e1.fingerprint == e2.fingerprint

    def test_fingerprint_varies(self, detector):
        e1 = detector.ingest_error(message="Connection timeout", component="api-gw")
        e2 = detector.ingest_error(message="Memory overflow", component="worker")
        assert e1.fingerprint != e2.fingerprint

    def test_error_to_dict(self, detector):
        err = detector.ingest_error(message="Test error")
        d = err.to_dict()
        assert "error_id" in d
        assert "message" in d
        assert "fingerprint" in d

    def test_bounded_errors(self):
        det = BugPatternDetector(max_errors=5)
        for i in range(10):
            det.ingest_error(message=f"Error {i}", component="test")
        errors = det.get_errors(limit=100)
        assert len(errors) <= 6


# ------------------------------------------------------------------
# Pattern detection
# ------------------------------------------------------------------

class TestPatternDetection:
    def test_detect_pattern(self, detector):
        for _ in range(5):
            detector.ingest_error(message="Connection timeout", component="api-gw")
        report = detector.run_detection_cycle()
        assert report.patterns_detected >= 1
        assert report.total_errors_analysed == 5

    def test_no_pattern_below_threshold(self, detector):
        detector.ingest_error(message="One-off error")
        report = detector.run_detection_cycle()
        assert report.patterns_detected == 0

    def test_severity_classification(self, detector):
        for _ in range(25):
            detector.ingest_error(message="Critical failure", component="core")
        report = detector.run_detection_cycle()
        assert report.critical_count >= 1

    def test_fix_suggestion(self, detector):
        for _ in range(5):
            detector.ingest_error(message="Connection timeout on db")
        report = detector.run_detection_cycle()
        patterns = detector.get_patterns()
        assert len(patterns) >= 1
        assert "timeout" in patterns[0]["suggested_fix"].lower() or "connection" in patterns[0]["suggested_fix"].lower()

    def test_report_to_dict(self, detector):
        for _ in range(5):
            detector.ingest_error(message="Test error")
        report = detector.run_detection_cycle()
        d = report.to_dict()
        assert "report_id" in d
        assert "patterns_detected" in d
        assert "patterns" in d


# ------------------------------------------------------------------
# Query
# ------------------------------------------------------------------

class TestQuery:
    def test_get_errors(self, detector):
        detector.ingest_error(message="Error A")
        detector.ingest_error(message="Error B")
        errors = detector.get_errors()
        assert len(errors) == 2

    def test_get_patterns(self, detector):
        for _ in range(5):
            detector.ingest_error(message="Recurring issue")
        detector.run_detection_cycle()
        patterns = detector.get_patterns()
        assert len(patterns) >= 1

    def test_get_reports(self, detector):
        for _ in range(5):
            detector.ingest_error(message="Test error")
        detector.run_detection_cycle()
        reports = detector.get_reports()
        assert len(reports) == 1


# ------------------------------------------------------------------
# Persistence
# ------------------------------------------------------------------

class TestPersistence:
    def test_report_persisted(self, wired_detector, pm):
        for _ in range(5):
            wired_detector.ingest_error(message="Persisted error")
        report = wired_detector.run_detection_cycle()
        loaded = pm.load_document(report.report_id)
        assert loaded is not None


# ------------------------------------------------------------------
# EventBackbone integration
# ------------------------------------------------------------------

class TestEventBackboneIntegration:
    def test_detection_publishes_event(self, wired_detector, backbone):
        received = []
        backbone.subscribe(EventType.LEARNING_FEEDBACK, lambda e: received.append(e))
        for _ in range(5):
            wired_detector.ingest_error(message="Event error")
        wired_detector.run_detection_cycle()
        backbone.process_pending()
        assert len(received) >= 1
        assert received[0].payload["source"] == "bug_pattern_detector"


# ------------------------------------------------------------------
# Status
# ------------------------------------------------------------------

class TestStatus:
    def test_status(self, detector):
        detector.ingest_error(message="Error A")
        status = detector.get_status()
        assert status["total_errors"] == 1
        assert status["total_patterns"] == 0
        assert status["persistence_attached"] is False

    def test_status_wired(self, wired_detector):
        status = wired_detector.get_status()
        assert status["persistence_attached"] is True
        assert status["backbone_attached"] is True
