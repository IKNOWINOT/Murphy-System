"""
Tests for OPS-004: EmergencyStopController.

Validates global/tenant stop/resume, automatic triggers,
outcome recording, persistence, and EventBackbone integration.

Design Label: TEST-023 / OPS-004
Owner: QA Team
"""

import os
import pytest


from emergency_stop_controller import (
    EmergencyStopController,
    StopEvent,
    StopAction,
    StopScope,
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
def esc():
    return EmergencyStopController()


@pytest.fixture
def wired_esc(pm, backbone):
    return EmergencyStopController(
        persistence_manager=pm,
        event_backbone=backbone,
    )


# ------------------------------------------------------------------
# Initial state
# ------------------------------------------------------------------

class TestInitialState:
    def test_not_stopped_initially(self, esc):
        assert esc.is_stopped() is False

    def test_not_stopped_for_tenant(self, esc):
        assert esc.is_stopped(tenant_id="tenant-1") is False


# ------------------------------------------------------------------
# Global stop / resume
# ------------------------------------------------------------------

class TestGlobalStop:
    def test_activate_global(self, esc):
        evt = esc.activate_global("security breach")
        assert esc.is_stopped() is True
        assert evt.scope == StopScope.GLOBAL
        assert evt.action == StopAction.ACTIVATED

    def test_resume_global(self, esc):
        esc.activate_global("breach")
        evt = esc.resume_global("breach contained")
        assert esc.is_stopped() is False
        assert evt.action == StopAction.RESUMED

    def test_global_blocks_tenant(self, esc):
        esc.activate_global("maintenance")
        assert esc.is_stopped(tenant_id="tenant-1") is True


# ------------------------------------------------------------------
# Tenant stop / resume
# ------------------------------------------------------------------

class TestTenantStop:
    def test_activate_tenant(self, esc):
        evt = esc.activate_tenant("t1", "abuse detected")
        assert esc.is_stopped(tenant_id="t1") is True
        assert esc.is_stopped(tenant_id="t2") is False
        assert esc.is_stopped() is False  # global not affected

    def test_resume_tenant(self, esc):
        esc.activate_tenant("t1", "abuse")
        esc.resume_tenant("t1", "resolved")
        assert esc.is_stopped(tenant_id="t1") is False

    def test_multiple_tenants(self, esc):
        esc.activate_tenant("t1", "r1")
        esc.activate_tenant("t2", "r2")
        assert esc.is_stopped(tenant_id="t1") is True
        assert esc.is_stopped(tenant_id="t2") is True
        esc.resume_tenant("t1", "ok")
        assert esc.is_stopped(tenant_id="t1") is False
        assert esc.is_stopped(tenant_id="t2") is True


# ------------------------------------------------------------------
# Automatic triggers
# ------------------------------------------------------------------

class TestAutoTriggers:
    def test_consecutive_failure_trigger(self):
        esc = EmergencyStopController(failure_threshold=3)
        esc.record_outcome(False)
        esc.record_outcome(False)
        assert esc.is_stopped() is False
        evt = esc.record_outcome(False)
        assert esc.is_stopped() is True
        assert evt is not None
        assert evt.triggered_by == "auto_failure"

    def test_success_resets_counter(self):
        esc = EmergencyStopController(failure_threshold=3)
        esc.record_outcome(False)
        esc.record_outcome(False)
        esc.record_outcome(True)  # resets counter
        esc.record_outcome(False)
        assert esc.is_stopped() is False

    def test_error_rate_trigger(self):
        esc = EmergencyStopController(
            failure_threshold=100,  # disable consecutive
            error_rate_threshold=0.3,
        )
        # 4 failures out of 10 = 40% error rate
        for _ in range(6):
            esc.record_outcome(True)
        for _ in range(3):
            esc.record_outcome(False)
        assert esc.is_stopped() is False  # only 9 total
        evt = esc.record_outcome(False)  # 4/10 = 40% > 30%
        assert esc.is_stopped() is True
        assert evt is not None
        assert evt.triggered_by == "auto_error_rate"

    def test_no_auto_trigger_when_already_stopped(self):
        esc = EmergencyStopController(failure_threshold=2)
        esc.record_outcome(False)
        esc.record_outcome(False)  # triggers stop
        evt = esc.record_outcome(False)  # already stopped
        assert evt is None  # no duplicate trigger

    def test_resume_resets_counters(self, esc):
        for _ in range(4):
            esc.record_outcome(False)
        esc.resume_global("fixed")
        s = esc.get_status()
        assert s["consecutive_failures"] == 0
        assert s["recent_total"] == 0


# ------------------------------------------------------------------
# Event history
# ------------------------------------------------------------------

class TestEventHistory:
    def test_events_recorded(self, esc):
        esc.activate_global("r1")
        esc.resume_global("r2")
        events = esc.get_events()
        assert len(events) == 2

    def test_event_to_dict(self, esc):
        evt = esc.activate_global("test")
        d = evt.to_dict()
        assert "event_id" in d
        assert d["action"] == "activated"
        assert d["scope"] == "global"


# ------------------------------------------------------------------
# Persistence
# ------------------------------------------------------------------

class TestPersistence:
    def test_stop_event_persisted(self, wired_esc, pm):
        evt = wired_esc.activate_global("test persist")
        loaded = pm.load_document(evt.event_id)
        assert loaded is not None


# ------------------------------------------------------------------
# EventBackbone
# ------------------------------------------------------------------

class TestEventBackboneIntegration:
    def test_stop_publishes_event(self, wired_esc, backbone):
        received = []
        backbone.subscribe(EventType.SYSTEM_HEALTH, lambda e: received.append(e))
        wired_esc.activate_global("test")
        backbone.process_pending()
        assert len(received) >= 1


# ------------------------------------------------------------------
# Status
# ------------------------------------------------------------------

class TestStatus:
    def test_status(self, esc):
        s = esc.get_status()
        assert s["global_stopped"] is False
        assert s["persistence_attached"] is False

    def test_wired_status(self, wired_esc):
        s = wired_esc.get_status()
        assert s["persistence_attached"] is True
        assert s["backbone_attached"] is True
