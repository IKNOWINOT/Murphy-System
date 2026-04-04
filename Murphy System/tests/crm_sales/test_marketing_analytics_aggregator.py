"""
Tests for MKT-005: MarketingAnalyticsAggregator.

Validates metric ingestion, report generation, trend detection,
persistence integration, and EventBackbone event publishing.

Design Label: TEST-017 / MKT-005
Owner: QA Team
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from marketing_analytics_aggregator import (
    MarketingAnalyticsAggregator,
    ChannelMetric,
    TrendResult,
    AnalyticsReport,
    _detect_trend,
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
    return MarketingAnalyticsAggregator()


@pytest.fixture
def wired_agg(pm, backbone):
    return MarketingAnalyticsAggregator(
        persistence_manager=pm,
        event_backbone=backbone,
    )


# ------------------------------------------------------------------
# Trend detection helper
# ------------------------------------------------------------------

class TestTrendDetection:
    def test_growth(self):
        tr = _detect_trend([1.0, 2.0, 3.0, 4.0, 5.0])
        assert tr.direction == "growth"
        assert tr.slope > 0

    def test_decline(self):
        tr = _detect_trend([5.0, 4.0, 3.0, 2.0, 1.0])
        assert tr.direction == "decline"
        assert tr.slope < 0

    def test_stable(self):
        tr = _detect_trend([5.0, 5.0, 5.0, 5.0])
        assert tr.direction == "stable"

    def test_too_few_samples(self):
        tr = _detect_trend([1.0])
        assert tr.direction == "stable"


# ------------------------------------------------------------------
# Metric ingestion
# ------------------------------------------------------------------

class TestMetricIngestion:
    def test_ingest(self, agg):
        cm = agg.ingest_metric("social", "impressions", 5000)
        assert cm.metric_id.startswith("cm-")
        assert cm.channel == "social"

    def test_normalised_channel(self, agg):
        cm = agg.ingest_metric("  Social  ", "clicks", 100)
        assert cm.channel == "social"

    def test_bounded(self):
        a = MarketingAnalyticsAggregator(max_data_points=5)
        for i in range(10):
            a.ingest_metric("ch", "m", float(i))
        s = a.get_status()
        assert s["total_data_points"] <= 6


# ------------------------------------------------------------------
# Report generation
# ------------------------------------------------------------------

class TestReport:
    def test_generate_report(self, agg):
        for v in [100, 200, 300, 400]:
            agg.ingest_metric("social", "clicks", float(v))
        agg.ingest_metric("seo", "impressions", 5000)
        report = agg.generate_report()
        assert report.total_data_points == 5
        assert report.channels_covered == 2
        assert len(report.trends) >= 1

    def test_report_to_dict(self, agg):
        agg.ingest_metric("social", "clicks", 100)
        report = agg.generate_report()
        d = report.to_dict()
        assert "report_id" in d
        assert "trends" in d

    def test_channel_summaries(self, agg):
        agg.ingest_metric("seo", "clicks", 100)
        agg.ingest_metric("seo", "clicks", 200)
        report = agg.generate_report()
        assert "seo" in report.channel_summaries
        assert report.channel_summaries["seo"]["clicks"] == 300.0


# ------------------------------------------------------------------
# Persistence
# ------------------------------------------------------------------

class TestPersistence:
    def test_report_persisted(self, wired_agg, pm):
        wired_agg.ingest_metric("social", "clicks", 100)
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
        wired_agg.ingest_metric("ch", "m", 1.0)
        wired_agg.generate_report()
        backbone.process_pending()
        assert len(received) >= 1


# ------------------------------------------------------------------
# Status
# ------------------------------------------------------------------

class TestStatus:
    def test_status(self, agg):
        agg.ingest_metric("ch", "m", 1.0)
        s = agg.get_status()
        assert s["total_data_points"] == 1
        assert s["persistence_attached"] is False

    def test_wired_status(self, wired_agg):
        s = wired_agg.get_status()
        assert s["persistence_attached"] is True
