"""
Tests for OBS-003: LogAnalysisEngine.

Validates log ingestion, pattern detection, report generation,
and EventBackbone integration.

Design Label: TEST-002 / OBS-003
Owner: QA Team
"""

import os
import pytest


from log_analysis_engine import (
    LogAnalysisEngine,
    LogEntry,
    LogLevel,
    ErrorPattern,
    ErrorReport,
)
from event_backbone import EventBackbone, EventType


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def engine():
    return LogAnalysisEngine()


@pytest.fixture
def backbone():
    return EventBackbone()


@pytest.fixture
def wired_engine(backbone):
    return LogAnalysisEngine(event_backbone=backbone)


# ------------------------------------------------------------------
# Ingestion
# ------------------------------------------------------------------

class TestIngestion:
    def test_ingest_single_entry(self, engine):
        entry = LogEntry(message="test message", level=LogLevel.INFO)
        entry_id = engine.ingest(entry)
        assert entry_id == entry.entry_id
        assert engine.get_status()["total_entries"] == 1

    def test_ingest_batch(self, engine):
        entries = [
            LogEntry(message=f"msg-{i}", level=LogLevel.INFO) for i in range(5)
        ]
        count = engine.ingest_batch(entries)
        assert count == 5
        assert engine.get_status()["total_entries"] == 5

    def test_bounded_buffer(self):
        engine = LogAnalysisEngine(max_entries=3)
        for i in range(5):
            engine.ingest(LogEntry(message=f"msg-{i}"))
        assert engine.get_status()["total_entries"] == 3


# ------------------------------------------------------------------
# Pattern detection
# ------------------------------------------------------------------

class TestPatternDetection:
    def test_detect_recurring_errors(self, engine):
        for _ in range(3):
            engine.ingest(LogEntry(
                message="Connection refused on port 5432",
                level=LogLevel.ERROR,
                source="db",
            ))
        patterns = engine.detect_patterns()
        assert len(patterns) >= 1
        assert patterns[0].occurrences >= 2

    def test_no_pattern_below_threshold(self, engine):
        engine.ingest(LogEntry(message="unique error", level=LogLevel.ERROR))
        patterns = engine.detect_patterns()
        assert len(patterns) == 0

    def test_normalisation_groups_variants(self, engine):
        engine.ingest(LogEntry(
            message="Timeout after 30s on host 192.168.1.1",
            level=LogLevel.ERROR,
        ))
        engine.ingest(LogEntry(
            message="Timeout after 60s on host 10.0.0.1",
            level=LogLevel.ERROR,
        ))
        patterns = engine.detect_patterns()
        assert len(patterns) == 1
        assert patterns[0].occurrences == 2

    def test_info_excluded_by_default(self, engine):
        for _ in range(3):
            engine.ingest(LogEntry(message="info msg", level=LogLevel.INFO))
        patterns = engine.detect_patterns()
        assert len(patterns) == 0

    def test_custom_min_level(self, engine):
        for _ in range(3):
            engine.ingest(LogEntry(message="debug noise", level=LogLevel.DEBUG))
        patterns = engine.detect_patterns(min_level=LogLevel.DEBUG)
        assert len(patterns) >= 1

    def test_patterns_sorted_by_occurrences(self, engine):
        for _ in range(5):
            engine.ingest(LogEntry(message="error A", level=LogLevel.ERROR))
        for _ in range(3):
            engine.ingest(LogEntry(message="error B", level=LogLevel.ERROR))
        patterns = engine.detect_patterns()
        assert patterns[0].occurrences >= patterns[-1].occurrences


# ------------------------------------------------------------------
# Report generation
# ------------------------------------------------------------------

class TestReportGeneration:
    def test_generate_report(self, engine):
        engine.ingest(LogEntry(message="ok", level=LogLevel.INFO))
        engine.ingest(LogEntry(message="err1", level=LogLevel.ERROR))
        engine.ingest(LogEntry(message="err1", level=LogLevel.ERROR))
        engine.ingest(LogEntry(message="warn1", level=LogLevel.WARNING))
        report = engine.generate_report()
        assert report.total_entries_analysed == 4
        assert report.error_count == 2
        assert report.warning_count == 1

    def test_report_to_dict(self, engine):
        engine.ingest(LogEntry(message="err", level=LogLevel.ERROR))
        engine.ingest(LogEntry(message="err", level=LogLevel.ERROR))
        report = engine.generate_report()
        d = report.to_dict()
        assert "report_id" in d
        assert "patterns" in d
        assert d["error_count"] == 2


# ------------------------------------------------------------------
# EventBackbone integration
# ------------------------------------------------------------------

class TestEventBackboneIntegration:
    def test_patterns_publish_learning_feedback(self, wired_engine, backbone):
        recorder = []
        backbone.subscribe(EventType.LEARNING_FEEDBACK, lambda e: recorder.append(e))
        for _ in range(3):
            wired_engine.ingest(LogEntry(message="critical fail", level=LogLevel.ERROR))
        wired_engine.detect_patterns()
        backbone.process_pending()
        assert len(recorder) >= 1
        assert recorder[0].payload["source"] == "log_analysis_engine"


# ------------------------------------------------------------------
# Status
# ------------------------------------------------------------------

class TestStatus:
    def test_status_reflects_state(self, engine):
        engine.ingest(LogEntry(message="x", level=LogLevel.INFO))
        status = engine.get_status()
        assert status["total_entries"] == 1
        assert status["rag_attached"] is False
        assert status["event_backbone_attached"] is False
