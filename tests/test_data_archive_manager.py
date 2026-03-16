"""
Tests for DATA-001: DataArchiveManager.

Validates:
  - Chronological archiving and retrieval
  - Time-range queries with chronological ordering
  - Metric routing to analytics
  - External content library integration (YouTube/Twitch VOD storage)
  - Externalization of high-volume data
  - Retrieval of externalized data by time period
  - Storage tier summary
  - Tag-based retrieval
  - Batch archiving

Design Label: TEST-010 / DATA-001
Owner: QA Team
"""

import pytest
from datetime import datetime, timezone, timedelta

from src.data_archive_manager import (
    DataArchiveManager,
    ArchiveCategory,
    StorageTier,
    RetrievalStatus,
    ArchiveRecord,
    ExternalContentRef,
    MetricRoutingResult,
)


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def manager():
    """Fresh archive manager."""
    return DataArchiveManager()


@pytest.fixture
def populated_manager():
    """Manager with sample data across categories."""
    m = DataArchiveManager()
    now = datetime.now(timezone.utc)
    # Add records spanning several days
    for i in range(10):
        ts = (now - timedelta(days=10 - i)).isoformat()
        m.archive(
            title=f"Metric record {i}",
            data={"channel": "seo", "metric_name": f"visits_{i}", "value": float(i * 100)},
            category=ArchiveCategory.METRIC,
            tags=["seo", f"day_{i}"],
            source_system="marketing_analytics",
        )
    for i in range(5):
        m.archive(
            title=f"Campaign record {i}",
            data={"campaign_id": f"camp-{i}", "tier": "pro"},
            category=ArchiveCategory.CAMPAIGN,
            tags=["campaign", "pro"],
            source_system="adaptive_campaign",
        )
    for i in range(3):
        m.archive(
            title=f"Session log {i}",
            data={"session_id": f"sess-{i}", "events": list(range(100))},
            category=ArchiveCategory.SESSION_LOG,
            tags=["session"],
            source_system="terminal",
            size_bytes=2_000_000,  # 2MB — above externalization threshold
        )
    return m


# ------------------------------------------------------------------
# Basic Archive Operations
# ------------------------------------------------------------------

class TestArchive:
    def test_archive_creates_record(self, manager):
        record = manager.archive(
            title="Test data",
            data={"key": "value"},
            category=ArchiveCategory.GENERAL,
        )
        assert record.record_id.startswith("arc-")
        assert record.title == "Test data"
        assert record.category == ArchiveCategory.GENERAL

    def test_archive_with_tags(self, manager):
        record = manager.archive(
            title="Tagged data",
            data={"x": 1},
            tags=["tag1", "tag2"],
        )
        assert "tag1" in record.tags
        assert "tag2" in record.tags

    def test_archive_chronological_order(self, manager):
        manager.archive(title="First", data={"order": 1})
        manager.archive(title="Second", data={"order": 2})
        manager.archive(title="Third", data={"order": 3})
        latest = manager.retrieve_latest(count=3)
        assert latest[0]["title"] == "Third"
        assert latest[2]["title"] == "First"

    def test_archive_batch(self, manager):
        items = [
            {"title": "Batch A", "data": {"a": 1}},
            {"title": "Batch B", "data": {"b": 2}},
            {"title": "Batch C", "data": {"c": 3}},
        ]
        records = manager.archive_batch(items, category=ArchiveCategory.TRACTION)
        assert len(records) == 3
        assert all(r.category == ArchiveCategory.TRACTION for r in records)


# ------------------------------------------------------------------
# Chronological Retrieval
# ------------------------------------------------------------------

class TestRetrieval:
    def test_retrieve_by_time_range(self, populated_manager):
        now = datetime.now(timezone.utc)
        start = (now - timedelta(days=15)).isoformat()
        end = now.isoformat()
        result = populated_manager.retrieve_by_time_range(start, end)
        assert result["status"] == "found"
        assert result["local_count"] > 0

    def test_retrieve_by_time_range_with_category(self, populated_manager):
        now = datetime.now(timezone.utc)
        start = (now - timedelta(days=15)).isoformat()
        end = now.isoformat()
        result = populated_manager.retrieve_by_time_range(
            start, end, category=ArchiveCategory.METRIC,
        )
        assert all(r["category"] == "metric" for r in result["local_records"])

    def test_retrieve_by_time_range_empty(self, manager):
        result = manager.retrieve_by_time_range(
            "2020-01-01T00:00:00+00:00",
            "2020-01-02T00:00:00+00:00",
        )
        assert result["status"] == "not_found"
        assert result["total"] == 0

    def test_retrieve_by_id(self, manager):
        record = manager.archive(title="Findme", data={"x": 1})
        found = manager.retrieve_by_id(record.record_id)
        assert found is not None
        assert found["title"] == "Findme"

    def test_retrieve_by_id_not_found(self, manager):
        result = manager.retrieve_by_id("nonexistent-id")
        assert result is None

    def test_retrieve_latest(self, populated_manager):
        latest = populated_manager.retrieve_latest(count=5)
        assert len(latest) == 5

    def test_retrieve_latest_with_category(self, populated_manager):
        latest = populated_manager.retrieve_latest(
            count=3, category=ArchiveCategory.CAMPAIGN,
        )
        assert all(r["category"] == "campaign" for r in latest)

    def test_retrieve_by_tags(self, populated_manager):
        results = populated_manager.retrieve_by_tags(["seo"])
        assert len(results) > 0
        assert all("seo" in r["tags"] for r in results)

    def test_retrieve_by_tags_match_all(self, populated_manager):
        results = populated_manager.retrieve_by_tags(
            ["campaign", "pro"], match_all=True,
        )
        assert len(results) > 0
        assert all("campaign" in r["tags"] and "pro" in r["tags"] for r in results)


# ------------------------------------------------------------------
# Metric Routing
# ------------------------------------------------------------------

class TestMetricRouting:
    def test_metric_auto_routed(self, manager):
        manager.archive(
            title="Page views",
            data={"channel": "seo", "metric_name": "views", "value": 1500.0},
            category=ArchiveCategory.METRIC,
        )
        metrics = manager.get_routed_metrics()
        assert len(metrics) == 1
        assert metrics[0]["channel"] == "seo"
        assert metrics[0]["value"] == 1500.0

    def test_non_metric_not_routed(self, manager):
        manager.archive(
            title="Campaign data",
            data={"x": 1},
            category=ArchiveCategory.CAMPAIGN,
        )
        metrics = manager.get_routed_metrics()
        assert len(metrics) == 0

    def test_multiple_metrics_routed(self, populated_manager):
        metrics = populated_manager.get_routed_metrics(limit=100)
        assert len(metrics) == 10  # 10 metric records in populated fixture


# ------------------------------------------------------------------
# External Content Library (YouTube/Twitch VOD Storage)
# ------------------------------------------------------------------

class TestExternalContentLibrary:
    def test_externalize_to_youtube(self, populated_manager):
        # Get session log record IDs (high volume)
        latest = populated_manager.retrieve_latest(
            count=3, category=ArchiveCategory.SESSION_LOG,
        )
        record_ids = [r["record_id"] for r in latest]
        ref = populated_manager.externalize_to_platform(
            record_ids=record_ids,
            platform="youtube",
            url="https://youtube.com/watch?v=abc123",
            title="Murphy System Session Logs — Week 9",
            description="Archived session logs for chronological review",
        )
        assert ref is not None
        assert ref.platform == "youtube"
        assert len(ref.archive_record_ids) == 3

    def test_externalize_to_twitch(self, populated_manager):
        latest = populated_manager.retrieve_latest(
            count=2, category=ArchiveCategory.SESSION_LOG,
        )
        record_ids = [r["record_id"] for r in latest]
        ref = populated_manager.externalize_to_platform(
            record_ids=record_ids,
            platform="twitch",
            url="https://twitch.tv/videos/999999",
            title="Telemetry Stream Archive",
        )
        assert ref is not None
        assert ref.platform == "twitch"

    def test_externalized_records_marked(self, populated_manager):
        latest = populated_manager.retrieve_latest(
            count=1, category=ArchiveCategory.SESSION_LOG,
        )
        record_id = latest[0]["record_id"]
        populated_manager.externalize_to_platform(
            record_ids=[record_id],
            platform="youtube",
            url="https://youtube.com/watch?v=xyz",
            title="Test VOD",
        )
        record = populated_manager.retrieve_by_id(record_id)
        assert record["storage_tier"] == "external_youtube"
        assert record["external_url"] == "https://youtube.com/watch?v=xyz"

    def test_externalize_empty_ids_returns_none(self, manager):
        ref = manager.externalize_to_platform(
            record_ids=[],
            platform="youtube",
            url="https://youtube.com/test",
            title="Empty",
        )
        assert ref is None

    def test_externalize_nonexistent_returns_none(self, manager):
        ref = manager.externalize_to_platform(
            record_ids=["fake-id"],
            platform="youtube",
            url="https://youtube.com/test",
            title="Nonexistent",
        )
        assert ref is None

    def test_get_external_refs(self, populated_manager):
        latest = populated_manager.retrieve_latest(
            count=2, category=ArchiveCategory.SESSION_LOG,
        )
        ids = [r["record_id"] for r in latest]
        populated_manager.externalize_to_platform(
            ids, "youtube", "https://youtube.com/v1", "VOD 1",
        )
        populated_manager.externalize_to_platform(
            ids[:1], "twitch", "https://twitch.tv/v2", "VOD 2",
        )
        all_refs = populated_manager.get_external_refs()
        assert len(all_refs) == 2
        yt_refs = populated_manager.get_external_refs(platform="youtube")
        assert len(yt_refs) == 1

    def test_find_externalized_for_period(self, populated_manager):
        latest = populated_manager.retrieve_latest(
            count=2, category=ArchiveCategory.SESSION_LOG,
        )
        ids = [r["record_id"] for r in latest]
        populated_manager.externalize_to_platform(
            ids, "youtube", "https://youtube.com/v1", "Logs Week 9",
        )
        now = datetime.now(timezone.utc)
        start = (now - timedelta(days=30)).isoformat()
        end = now.isoformat()
        refs = populated_manager.find_externalized_for_period(start, end)
        assert len(refs) >= 1
        assert refs[0]["platform"] == "youtube"


# ------------------------------------------------------------------
# Externalization Candidates
# ------------------------------------------------------------------

class TestExternalizationCandidates:
    def test_candidates_found(self, populated_manager):
        candidates = populated_manager.get_externalization_candidates(
            threshold_bytes=1_000_000,
        )
        assert len(candidates) == 3  # 3 session logs with 2MB each

    def test_no_candidates_below_threshold(self, populated_manager):
        candidates = populated_manager.get_externalization_candidates(
            threshold_bytes=10_000_000,  # 10MB — none qualify
        )
        assert len(candidates) == 0


# ------------------------------------------------------------------
# Storage Summary
# ------------------------------------------------------------------

class TestStorageSummary:
    def test_storage_summary(self, populated_manager):
        summary = populated_manager.get_storage_summary()
        assert summary["total_records"] == 18  # 10 + 5 + 3
        assert summary["local_records"] == 18
        assert summary["external_youtube"] == 0

    def test_storage_summary_after_externalize(self, populated_manager):
        latest = populated_manager.retrieve_latest(
            count=1, category=ArchiveCategory.SESSION_LOG,
        )
        populated_manager.externalize_to_platform(
            [latest[0]["record_id"]],
            "youtube", "https://youtube.com/v1", "VOD",
        )
        summary = populated_manager.get_storage_summary()
        assert summary["external_youtube"] == 1
        assert summary["local_records"] == 17


# ------------------------------------------------------------------
# Status
# ------------------------------------------------------------------

class TestStatus:
    def test_get_status(self, populated_manager):
        status = populated_manager.get_status()
        assert status["total_records"] == 18
        assert status["categories"]["metric"] == 10
        assert status["categories"]["campaign"] == 5
        assert status["categories"]["session_log"] == 3

    def test_event_log_grows(self, manager):
        manager.archive(title="A", data={})
        manager.archive(title="B", data={})
        status = manager.get_status()
        assert status["event_log_count"] >= 2


# ------------------------------------------------------------------
# Integration: Time-range retrieval includes external refs
# ------------------------------------------------------------------

class TestIntegration:
    def test_time_range_includes_external(self, populated_manager):
        """Retrieval by time range includes both local records and
        external content refs for watching back logs."""
        latest = populated_manager.retrieve_latest(
            count=2, category=ArchiveCategory.SESSION_LOG,
        )
        ids = [r["record_id"] for r in latest]
        populated_manager.externalize_to_platform(
            ids, "youtube", "https://youtube.com/logs", "Session Logs",
        )
        now = datetime.now(timezone.utc)
        result = populated_manager.retrieve_by_time_range(
            (now - timedelta(days=30)).isoformat(),
            now.isoformat(),
        )
        assert result["external_count"] >= 1
        assert result["local_count"] >= 1

    def test_full_archive_retrieve_externalize_cycle(self, manager):
        """Full cycle: archive → retrieve → externalize → retrieve external."""
        # 1. Archive high-volume data
        records = []
        for i in range(5):
            r = manager.archive(
                title=f"Telemetry stream {i}",
                data={"stream": f"data-{i}"},
                category=ArchiveCategory.TELEMETRY,
                size_bytes=5_000_000,
                tags=["telemetry", "high_volume"],
            )
            records.append(r)

        # 2. Retrieve locally
        latest = manager.retrieve_latest(count=5, category=ArchiveCategory.TELEMETRY)
        assert len(latest) == 5

        # 3. Externalize to YouTube
        ids = [r.record_id for r in records]
        ref = manager.externalize_to_platform(
            ids, "youtube",
            "https://youtube.com/watch?v=telemetry_archive",
            "Murphy Telemetry Archive — Full Stream",
        )
        assert ref is not None

        # 4. Retrieve by time period — should include external ref
        now = datetime.now(timezone.utc)
        result = manager.retrieve_by_time_range(
            (now - timedelta(hours=1)).isoformat(),
            now.isoformat(),
        )
        assert result["external_count"] >= 1
        assert result["external_refs"][0]["url"] == "https://youtube.com/watch?v=telemetry_archive"

        # 5. Storage summary shows externalization
        summary = manager.get_storage_summary()
        assert summary["external_youtube"] == 5
