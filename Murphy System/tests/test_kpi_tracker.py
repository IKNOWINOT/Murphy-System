"""
Tests for OPS-002: KPITracker.

Validates KPI definition, recording, snapshot generation,
target comparison, persistence, and EventBackbone integration.

Design Label: TEST-021 / OPS-002
Owner: QA Team
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from kpi_tracker import (
    KPITracker,
    KPIDefinition,
    KPIDirection,
    KPIStatus,
    KPIResult,
    KPISnapshot,
    KPIObservation,
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
def tracker():
    return KPITracker()


@pytest.fixture
def wired_tracker(pm, backbone):
    return KPITracker(persistence_manager=pm, event_backbone=backbone)


# ------------------------------------------------------------------
# KPI definition
# ------------------------------------------------------------------

class TestKPIDefinition:
    def test_default_kpis_loaded(self, tracker):
        kpis = tracker.list_kpis()
        assert len(kpis) >= 8

    def test_define_custom_kpi(self, tracker):
        kpi = KPIDefinition("custom-1", "Custom Metric", 99.0, "%")
        tracker.define_kpi(kpi)
        kpis = tracker.list_kpis()
        ids = [k["kpi_id"] for k in kpis]
        assert "custom-1" in ids

    def test_remove_kpi(self, tracker):
        assert tracker.remove_kpi("kpi-automation-rate") is True
        assert tracker.remove_kpi("nonexistent") is False


# ------------------------------------------------------------------
# Recording
# ------------------------------------------------------------------

class TestRecording:
    def test_record_known_kpi(self, tracker):
        obs = tracker.record("kpi-success-rate", 96.5)
        assert obs is not None
        assert obs.value == 96.5

    def test_record_unknown_kpi(self, tracker):
        obs = tracker.record("nonexistent", 1.0)
        assert obs is None

    def test_bounded_observations(self):
        t = KPITracker(kpi_definitions=[
            KPIDefinition("k", "K", 1.0)
        ], max_observations=10)
        for i in range(20):
            t.record("k", float(i))
        s = t.get_status()
        assert s["total_observations"] <= 11


# ------------------------------------------------------------------
# Snapshot
# ------------------------------------------------------------------

class TestSnapshot:
    def test_no_data_snapshot(self, tracker):
        snap = tracker.snapshot()
        assert snap.no_data_count >= 1

    def test_target_met_higher_is_better(self, tracker):
        for _ in range(5):
            tracker.record("kpi-success-rate", 97.0)
        snap = tracker.snapshot()
        result = [r for r in snap.results if r.kpi_id == "kpi-success-rate"]
        assert len(result) == 1
        assert result[0].status == KPIStatus.MET

    def test_target_not_met(self, tracker):
        for _ in range(5):
            tracker.record("kpi-success-rate", 50.0)
        snap = tracker.snapshot()
        result = [r for r in snap.results if r.kpi_id == "kpi-success-rate"]
        assert result[0].status == KPIStatus.NOT_MET

    def test_lower_is_better_met(self, tracker):
        for _ in range(5):
            tracker.record("kpi-error-rate", 0.05)
        snap = tracker.snapshot()
        result = [r for r in snap.results if r.kpi_id == "kpi-error-rate"]
        assert result[0].status == KPIStatus.MET

    def test_lower_is_better_not_met(self, tracker):
        for _ in range(5):
            tracker.record("kpi-error-rate", 5.0)
        snap = tracker.snapshot()
        result = [r for r in snap.results if r.kpi_id == "kpi-error-rate"]
        assert result[0].status == KPIStatus.NOT_MET

    def test_snapshot_to_dict(self, tracker):
        snap = tracker.snapshot()
        d = snap.to_dict()
        assert "snapshot_id" in d
        assert "results" in d

    def test_multiple_snapshots(self, tracker):
        tracker.snapshot()
        tracker.snapshot()
        snaps = tracker.get_snapshots()
        assert len(snaps) == 2


# ------------------------------------------------------------------
# Persistence
# ------------------------------------------------------------------

class TestPersistence:
    def test_snapshot_persisted(self, wired_tracker, pm):
        snap = wired_tracker.snapshot()
        loaded = pm.load_document(snap.snapshot_id)
        assert loaded is not None


# ------------------------------------------------------------------
# EventBackbone
# ------------------------------------------------------------------

class TestEventBackbone:
    def test_snapshot_publishes_event(self, wired_tracker, backbone):
        received = []
        backbone.subscribe(EventType.LEARNING_FEEDBACK, lambda e: received.append(e))
        wired_tracker.snapshot()
        backbone.process_pending()
        assert len(received) >= 1


# ------------------------------------------------------------------
# Status
# ------------------------------------------------------------------

class TestStatus:
    def test_status(self, tracker):
        s = tracker.get_status()
        assert s["total_kpis"] >= 8
        assert s["persistence_attached"] is False

    def test_wired_status(self, wired_tracker):
        s = wired_tracker.get_status()
        assert s["persistence_attached"] is True


# ------------------------------------------------------------------
# Business metrics integration (ARCH-007)
# ------------------------------------------------------------------

class TestBusinessKPIs:
    def test_business_kpis_included(self, tracker):
        """Verify all business KPIs are in the default set."""
        kpis = {k["kpi_id"]: k for k in tracker.list_kpis()}
        assert "kpi-crm-leads" in kpis
        assert "kpi-deal-close-rate" in kpis
        assert "kpi-ticket-resolution-time" in kpis
        assert "kpi-customer-satisfaction" in kpis
        assert "kpi-feature-adoption" in kpis
        assert "kpi-monthly-revenue" in kpis

    def test_crm_source_mapping(self, tracker):
        obs = tracker.record_from_source("crm", {"lead_count": 15.0, "deal_close_rate": 22.0})
        non_null = [o for o in obs if o is not None]
        assert len(non_null) == 2
        recorded_kpis = {o.kpi_id for o in non_null}
        assert "kpi-crm-leads" in recorded_kpis
        assert "kpi-deal-close-rate" in recorded_kpis

    def test_billing_source_mapping(self, tracker):
        obs = tracker.record_from_source("billing", {"monthly_revenue_usd": 5000.0})
        non_null = [o for o in obs if o is not None]
        assert len(non_null) == 1
        assert non_null[0].kpi_id == "kpi-monthly-revenue"
        assert non_null[0].value == 5000.0

    def test_service_source_mapping(self, tracker):
        obs = tracker.record_from_source("service", {"avg_resolution_hours": 6.0})
        non_null = [o for o in obs if o is not None]
        assert len(non_null) == 1
        assert non_null[0].kpi_id == "kpi-ticket-resolution-time"

    def test_unknown_source_returns_empty(self, tracker):
        obs = tracker.record_from_source("unknown_source", {"foo": 1.0})
        assert obs == []

    def test_crm_partial_metrics(self, tracker):
        obs = tracker.record_from_source("crm", {"lead_count": 5.0})
        non_null = [o for o in obs if o is not None]
        assert len(non_null) == 1
        assert non_null[0].kpi_id == "kpi-crm-leads"

    def test_record_from_source_updates_snapshot(self, tracker):
        tracker.record_from_source("billing", {"monthly_revenue_usd": 2000.0})
        snap = tracker.snapshot()
        revenue_result = next(
            (r for r in snap.results if r.kpi_id == "kpi-monthly-revenue"), None
        )
        assert revenue_result is not None
        assert revenue_result.current_value == pytest.approx(2000.0)
        assert revenue_result.status.value == "met"

    def test_total_kpis_includes_business(self, tracker):
        kpis = tracker.list_kpis()
        # Default system (8) + business (6) = 14
        assert len(kpis) >= 14
