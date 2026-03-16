"""
Tests for ORCH-003: OperationalDashboardAggregator.

Validates module registration, status collection, health classification,
snapshot generation, persistence, and EventBackbone integration.

Design Label: TEST-031 / ORCH-003
Owner: QA Team
"""

import os
import pytest


from operational_dashboard_aggregator import (
    OperationalDashboardAggregator,
    ModuleHealth,
    ModuleStatusEntry,
    DashboardSnapshot,
)
from persistence_manager import PersistenceManager
from event_backbone import EventBackbone, EventType


@pytest.fixture
def pm(tmp_path):
    return PersistenceManager(persistence_dir=str(tmp_path / "test_persist"))

@pytest.fixture
def backbone():
    return EventBackbone()

@pytest.fixture
def dash():
    return OperationalDashboardAggregator()

@pytest.fixture
def wired_dash(pm, backbone):
    return OperationalDashboardAggregator(persistence_manager=pm, event_backbone=backbone)


class TestModuleRegistration:
    def test_register_module(self, dash):
        dash.register_module("OPS-001", "ReadinessEvaluator", lambda: {"ok": True})
        s = dash.get_status()
        assert s["registered_modules"] == 1

    def test_unregister_module(self, dash):
        dash.register_module("OPS-001", "Test", lambda: {})
        assert dash.unregister_module("OPS-001") is True
        assert dash.unregister_module("OPS-001") is False

    def test_register_multiple(self, dash):
        dash.register_module("A", "ModA", lambda: {})
        dash.register_module("B", "ModB", lambda: {})
        assert dash.get_status()["registered_modules"] == 2


class TestStatusCollection:
    def test_empty_dashboard(self, dash):
        snap = dash.collect()
        assert snap.total_modules == 0
        assert snap.system_health == "unknown"

    def test_all_healthy(self, dash):
        dash.register_module("A", "Mod", lambda: {"status": "ok"})
        dash.register_module("B", "Mod", lambda: {"status": "ok"})
        snap = dash.collect()
        assert snap.healthy_count == 2
        assert snap.system_health == "healthy"

    def test_degraded_module(self, dash):
        dash.register_module("A", "Mod", lambda: {"system_status": "degraded"})
        snap = dash.collect()
        assert snap.degraded_count == 1
        assert snap.system_health == "degraded"

    def test_unreachable_module(self, dash):
        def fail():
            raise RuntimeError("down")
        dash.register_module("A", "Mod", fail)
        snap = dash.collect()
        assert snap.unreachable_count == 1

    def test_mixed_health(self, dash):
        dash.register_module("A", "Mod", lambda: {})
        dash.register_module("B", "Mod", lambda: (_ for _ in ()).throw(RuntimeError("err")))
        snap = dash.collect()
        assert snap.healthy_count == 1
        assert snap.unreachable_count == 1
        assert snap.system_health == "degraded"


class TestSnapshot:
    def test_snapshot_to_dict(self, dash):
        dash.register_module("A", "Mod", lambda: {})
        snap = dash.collect()
        d = snap.to_dict()
        assert "snapshot_id" in d
        assert "modules" in d
        assert len(d["modules"]) == 1

    def test_module_entry_has_latency(self, dash):
        dash.register_module("A", "Mod", lambda: {})
        snap = dash.collect()
        assert snap.modules[0].latency_ms >= 0


class TestPersistence:
    def test_snapshot_persisted(self, wired_dash, pm):
        wired_dash.register_module("A", "Mod", lambda: {})
        snap = wired_dash.collect()
        loaded = pm.load_document(snap.snapshot_id)
        assert loaded is not None


class TestEventBackbone:
    def test_collect_publishes_event(self, wired_dash, backbone):
        received = []
        backbone.subscribe(EventType.SYSTEM_HEALTH, lambda e: received.append(e))
        wired_dash.register_module("A", "Mod", lambda: {})
        wired_dash.collect()
        backbone.process_pending()
        assert len(received) >= 1


class TestStatus:
    def test_status(self, dash):
        s = dash.get_status()
        assert s["registered_modules"] == 0
        assert s["persistence_attached"] is False

    def test_wired_status(self, wired_dash):
        s = wired_dash.get_status()
        assert s["persistence_attached"] is True
