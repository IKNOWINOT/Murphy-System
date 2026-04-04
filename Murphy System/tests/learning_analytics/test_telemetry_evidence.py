"""
Tests for ARCH-007: TelemetryEvidenceStore.

Validates telemetry snapshot recording, querying, trend detection,
persistence integration, and EventBackbone integration.

Design Label: TEST-ARCH007-TEV
Owner: QA Team
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from telemetry_evidence import (
    TelemetryEvidenceStore,
    TelemetrySnapshot,
    EvidenceQuery,
    SnapshotKind,
)
from persistence_manager import PersistenceManager
from event_backbone import EventBackbone, EventType


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def store():
    return TelemetryEvidenceStore()


@pytest.fixture
def pm(tmp_path):
    return PersistenceManager(persistence_dir=str(tmp_path / "test_persist"))


@pytest.fixture
def backbone():
    return EventBackbone()


@pytest.fixture
def wired_store(pm, backbone):
    return TelemetryEvidenceStore(persistence_manager=pm, event_backbone=backbone)


# ------------------------------------------------------------------
# Module-level imports
# ------------------------------------------------------------------

class TestImports:
    def test_import_telemetry_evidence_package(self):
        import telemetry_evidence
        assert hasattr(telemetry_evidence, "TelemetryEvidenceStore")
        assert hasattr(telemetry_evidence, "TelemetrySnapshot")
        assert hasattr(telemetry_evidence, "EvidenceQuery")
        assert hasattr(telemetry_evidence, "SnapshotKind")


# ------------------------------------------------------------------
# Recording
# ------------------------------------------------------------------

class TestRecording:
    def test_record_returns_snapshot(self, store):
        snap = store.record(SnapshotKind.SYSTEM_HEALTH, "test", {"healthy": 5})
        assert isinstance(snap, TelemetrySnapshot)
        assert snap.snapshot_id.startswith("ev-")
        assert snap.kind == SnapshotKind.SYSTEM_HEALTH
        assert snap.source == "test"
        assert snap.payload == {"healthy": 5}

    def test_record_auto_timestamp(self, store):
        snap = store.record(SnapshotKind.KPI_SNAPSHOT, "kpi", {})
        assert snap.recorded_at is not None
        assert "T" in snap.recorded_at  # ISO format

    def test_record_with_tags(self, store):
        snap = store.record(
            SnapshotKind.AGENT_METRICS, "agent_monitor",
            {"total": 5}, tags=["env:prod", "region:us"]
        )
        assert "env:prod" in snap.tags
        assert "region:us" in snap.tags

    def test_record_multiple_kinds(self, store):
        store.record(SnapshotKind.SYSTEM_HEALTH, "s1", {})
        store.record(SnapshotKind.AGENT_METRICS, "s2", {})
        store.record(SnapshotKind.SLO_COMPLIANCE, "s3", {})
        status = store.get_status()
        assert status["total_snapshots"] == 3

    def test_record_updates_status(self, store):
        assert store.get_status()["total_snapshots"] == 0
        store.record(SnapshotKind.FOUNDER_DIGEST, "digest", {"period": "daily"})
        assert store.get_status()["total_snapshots"] == 1

    def test_snapshot_id_unique(self, store):
        snaps = [store.record(SnapshotKind.CUSTOM, "s", {}) for _ in range(5)]
        ids = {s.snapshot_id for s in snaps}
        assert len(ids) == 5


# ------------------------------------------------------------------
# Query
# ------------------------------------------------------------------

class TestQuery:
    def test_query_empty(self, store):
        results = store.query()
        assert results == []

    def test_query_returns_dict(self, store):
        store.record(SnapshotKind.SYSTEM_HEALTH, "src", {"ok": True})
        results = store.query()
        assert isinstance(results[0], dict)
        assert "snapshot_id" in results[0]
        assert "kind" in results[0]
        assert "source" in results[0]
        assert "payload" in results[0]

    def test_query_by_kind(self, store):
        store.record(SnapshotKind.SYSTEM_HEALTH, "s1", {})
        store.record(SnapshotKind.AGENT_METRICS, "s2", {})
        store.record(SnapshotKind.SYSTEM_HEALTH, "s3", {})
        results = store.query(EvidenceQuery(kind=SnapshotKind.SYSTEM_HEALTH))
        assert len(results) == 2
        assert all(r["kind"] == "system_health" for r in results)

    def test_query_by_source(self, store):
        store.record(SnapshotKind.CUSTOM, "dashboard", {"a": 1})
        store.record(SnapshotKind.CUSTOM, "agent", {"b": 2})
        store.record(SnapshotKind.CUSTOM, "dashboard", {"c": 3})
        results = store.query(EvidenceQuery(source="dashboard"))
        assert len(results) == 2

    def test_query_by_tags(self, store):
        store.record(SnapshotKind.CUSTOM, "s", {}, tags=["env:prod"])
        store.record(SnapshotKind.CUSTOM, "s", {}, tags=["env:staging"])
        store.record(SnapshotKind.CUSTOM, "s", {}, tags=["env:prod", "region:eu"])
        results = store.query(EvidenceQuery(tags=["env:prod"]))
        assert len(results) == 2

    def test_query_limit(self, store):
        for i in range(10):
            store.record(SnapshotKind.CUSTOM, "s", {"i": i})
        results = store.query(EvidenceQuery(limit=3))
        assert len(results) == 3

    def test_query_combined_filters(self, store):
        store.record(SnapshotKind.SYSTEM_HEALTH, "dash", {"ok": True})
        store.record(SnapshotKind.AGENT_METRICS, "dash", {"agents": 5})
        store.record(SnapshotKind.SYSTEM_HEALTH, "other", {})
        results = store.query(EvidenceQuery(
            kind=SnapshotKind.SYSTEM_HEALTH, source="dash"
        ))
        assert len(results) == 1
        assert results[0]["source"] == "dash"

    def test_get_snapshot_by_id(self, store):
        snap = store.record(SnapshotKind.KPI_SNAPSHOT, "kpi", {"met": 7})
        retrieved = store.get_snapshot(snap.snapshot_id)
        assert retrieved is not None
        assert retrieved["snapshot_id"] == snap.snapshot_id
        assert retrieved["payload"]["met"] == 7

    def test_get_snapshot_not_found(self, store):
        assert store.get_snapshot("nonexistent") is None


# ------------------------------------------------------------------
# Trend detection
# ------------------------------------------------------------------

class TestTrendDetection:
    def test_trend_insufficient_data_empty(self, store):
        result = store.detect_trend(SnapshotKind.SYSTEM_HEALTH, "healthy_count")
        assert result["trend"] == "insufficient_data"
        assert result["count"] == 0

    def test_trend_insufficient_data_single(self, store):
        store.record(SnapshotKind.SYSTEM_HEALTH, "s", {"healthy_count": 5})
        result = store.detect_trend(SnapshotKind.SYSTEM_HEALTH, "healthy_count")
        assert result["trend"] == "insufficient_data"
        assert result["count"] == 1

    def test_trend_rising(self, store):
        for v in [1, 3, 5, 7, 10]:
            store.record(SnapshotKind.SYSTEM_HEALTH, "s", {"healthy_count": v})
        result = store.detect_trend(SnapshotKind.SYSTEM_HEALTH, "healthy_count")
        assert result["trend"] == "rising"
        assert result["delta"] > 0

    def test_trend_falling(self, store):
        for v in [10, 8, 6, 4, 2]:
            store.record(SnapshotKind.SYSTEM_HEALTH, "s", {"healthy_count": v})
        result = store.detect_trend(SnapshotKind.SYSTEM_HEALTH, "healthy_count")
        assert result["trend"] == "falling"
        assert result["delta"] < 0

    def test_trend_stable(self, store):
        for v in [5, 5, 5, 5, 5]:
            store.record(SnapshotKind.SYSTEM_HEALTH, "s", {"healthy_count": v})
        result = store.detect_trend(SnapshotKind.SYSTEM_HEALTH, "healthy_count")
        assert result["trend"] == "stable"

    def test_trend_values_returned(self, store):
        for v in [1, 2, 3]:
            store.record(SnapshotKind.SYSTEM_HEALTH, "s", {"healthy_count": v})
        result = store.detect_trend(SnapshotKind.SYSTEM_HEALTH, "healthy_count")
        assert result["values"] == [1.0, 2.0, 3.0]

    def test_trend_filters_by_kind(self, store):
        store.record(SnapshotKind.SYSTEM_HEALTH, "s", {"val": 1})
        store.record(SnapshotKind.AGENT_METRICS, "s", {"val": 100})  # different kind
        store.record(SnapshotKind.SYSTEM_HEALTH, "s", {"val": 2})
        result = store.detect_trend(SnapshotKind.SYSTEM_HEALTH, "val")
        # Only SYSTEM_HEALTH snapshots considered
        assert result["values"] == [1.0, 2.0]


# ------------------------------------------------------------------
# Status
# ------------------------------------------------------------------

class TestStatus:
    def test_empty_status(self, store):
        s = store.get_status()
        assert s["total_snapshots"] == 0
        assert s["by_kind"] == {}
        assert s["persistence_attached"] is False
        assert s["backbone_attached"] is False

    def test_status_after_recording(self, store):
        store.record(SnapshotKind.SYSTEM_HEALTH, "s", {})
        store.record(SnapshotKind.SYSTEM_HEALTH, "s", {})
        store.record(SnapshotKind.AGENT_METRICS, "s", {})
        s = store.get_status()
        assert s["total_snapshots"] == 3
        assert s["by_kind"]["system_health"] == 2
        assert s["by_kind"]["agent_metrics"] == 1

    def test_wired_status(self, wired_store):
        s = wired_store.get_status()
        assert s["persistence_attached"] is True
        assert s["backbone_attached"] is True


# ------------------------------------------------------------------
# Persistence
# ------------------------------------------------------------------

class TestPersistence:
    def test_record_persists(self, wired_store, pm):
        snap = wired_store.record(SnapshotKind.FOUNDER_DIGEST, "digest", {"period": "daily"})
        loaded = pm.load_document(snap.snapshot_id)
        assert loaded is not None
        assert loaded["kind"] == "founder_digest"


# ------------------------------------------------------------------
# EventBackbone
# ------------------------------------------------------------------

class TestEventBackbone:
    def test_record_publishes_event(self, wired_store, backbone):
        received = []
        backbone.subscribe(EventType.SYSTEM_HEALTH, lambda e: received.append(e))
        wired_store.record(SnapshotKind.SYSTEM_HEALTH, "test", {"ok": True})
        backbone.process_pending()
        assert len(received) >= 1


# ------------------------------------------------------------------
# Bounded storage (CWE-770)
# ------------------------------------------------------------------

class TestBoundedStorage:
    def test_max_snapshots_respected(self):
        store = TelemetryEvidenceStore(max_snapshots=10)
        for i in range(25):
            store.record(SnapshotKind.CUSTOM, "s", {"i": i})
        s = store.get_status()
        assert s["total_snapshots"] <= 11  # 10 + one after eviction


# ------------------------------------------------------------------
# SnapshotKind enum
# ------------------------------------------------------------------

class TestSnapshotKindEnum:
    def test_all_kinds_have_values(self):
        for kind in SnapshotKind:
            assert isinstance(kind.value, str)
            assert len(kind.value) > 0

    def test_to_dict_serialises_kind(self, store):
        snap = store.record(SnapshotKind.MAINTENANCE_ALERT, "maint", {})
        d = snap.to_dict()
        assert d["kind"] == "maintenance_alert"
