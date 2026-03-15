"""
Tests for OBS-001 + OBS-002: HealthMonitor module.

Validates component registration, health check execution,
aggregate reporting, and EventBackbone integration.

Design Label: TEST-001 / OBS-001 / OBS-002
Owner: QA Team
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from health_monitor import (
    HealthMonitor,
    ComponentStatus,
    SystemStatus,
    ComponentHealth,
    HealthReport,
)
from event_backbone import EventBackbone, EventType


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def monitor():
    return HealthMonitor()


@pytest.fixture
def backbone():
    return EventBackbone()


@pytest.fixture
def wired_monitor(backbone):
    return HealthMonitor(event_backbone=backbone)


def _healthy_check():
    return {"status": "healthy", "message": "all good"}


def _degraded_check():
    return {"status": "degraded", "message": "slow responses"}


def _unhealthy_check():
    return {"status": "unhealthy", "message": "connection refused"}


def _crashing_check():
    raise RuntimeError("check exploded")


# ------------------------------------------------------------------
# Registration
# ------------------------------------------------------------------

class TestRegistration:
    def test_register_component(self, monitor):
        monitor.register("db", _healthy_check)
        assert "db" in monitor.get_status()["component_ids"]

    def test_unregister_component(self, monitor):
        monitor.register("db", _healthy_check)
        assert monitor.unregister("db") is True
        assert "db" not in monitor.get_status()["component_ids"]

    def test_unregister_missing_returns_false(self, monitor):
        assert monitor.unregister("nonexistent") is False


# ------------------------------------------------------------------
# Single component check
# ------------------------------------------------------------------

class TestSingleCheck:
    def test_check_healthy_component(self, monitor):
        monitor.register("db", _healthy_check)
        result = monitor.check_component("db")
        assert result is not None
        assert result.status == ComponentStatus.HEALTHY
        assert result.latency_ms >= 0

    def test_check_missing_component_returns_none(self, monitor):
        assert monitor.check_component("nope") is None

    def test_check_crashing_component(self, monitor):
        monitor.register("bad", _crashing_check)
        result = monitor.check_component("bad")
        assert result.status == ComponentStatus.UNHEALTHY
        assert "exploded" in result.message


# ------------------------------------------------------------------
# Aggregate check
# ------------------------------------------------------------------

class TestCheckAll:
    def test_all_healthy(self, monitor):
        monitor.register("a", _healthy_check)
        monitor.register("b", _healthy_check)
        report = monitor.check_all()
        assert report.system_status == SystemStatus.HEALTHY
        assert report.healthy_count == 2

    def test_degraded_if_one_degraded(self, monitor):
        monitor.register("a", _healthy_check)
        monitor.register("b", _degraded_check)
        report = monitor.check_all()
        assert report.system_status == SystemStatus.DEGRADED

    def test_unhealthy_if_one_unhealthy(self, monitor):
        monitor.register("a", _healthy_check)
        monitor.register("b", _unhealthy_check)
        report = monitor.check_all()
        assert report.system_status == SystemStatus.UNHEALTHY

    def test_empty_is_healthy(self, monitor):
        report = monitor.check_all()
        assert report.system_status == SystemStatus.HEALTHY
        assert report.healthy_count == 0

    def test_report_has_component_details(self, monitor):
        monitor.register("a", _healthy_check)
        report = monitor.check_all()
        assert len(report.components) == 1
        assert report.components[0].component_id == "a"

    def test_report_to_dict(self, monitor):
        monitor.register("a", _healthy_check)
        report = monitor.check_all()
        d = report.to_dict()
        assert d["system_status"] == "healthy"
        assert len(d["components"]) == 1

    def test_crashing_check_marks_unhealthy(self, monitor):
        monitor.register("a", _healthy_check)
        monitor.register("bad", _crashing_check)
        report = monitor.check_all()
        assert report.system_status == SystemStatus.UNHEALTHY
        assert report.unhealthy_count == 1


# ------------------------------------------------------------------
# History
# ------------------------------------------------------------------

class TestHistory:
    def test_history_accumulates(self, monitor):
        monitor.register("a", _healthy_check)
        monitor.check_all()
        monitor.check_all()
        history = monitor.get_history(limit=5)
        assert len(history) == 2

    def test_get_latest_report(self, monitor):
        monitor.register("a", _healthy_check)
        monitor.check_all()
        latest = monitor.get_latest_report()
        assert latest is not None
        assert latest.system_status == SystemStatus.HEALTHY

    def test_get_latest_report_none_before_check(self, monitor):
        assert monitor.get_latest_report() is None


# ------------------------------------------------------------------
# EventBackbone integration  [OBS-002]
# ------------------------------------------------------------------

class TestEventBackboneIntegration:
    def test_check_all_publishes_system_health_event(self, wired_monitor, backbone):
        recorder = []
        backbone.subscribe(EventType.SYSTEM_HEALTH, lambda e: recorder.append(e))
        wired_monitor.register("a", _healthy_check)
        wired_monitor.check_all()
        backbone.process_pending()
        assert len(recorder) == 1
        assert recorder[0].payload["system_status"] == "healthy"

    def test_no_event_without_backbone(self, monitor):
        monitor.register("a", _healthy_check)
        report = monitor.check_all()
        assert report.system_status == SystemStatus.HEALTHY


# ------------------------------------------------------------------
# Status
# ------------------------------------------------------------------

class TestStatus:
    def test_status_reflects_state(self, monitor):
        monitor.register("a", _healthy_check)
        monitor.register("b", _degraded_check)
        status = monitor.get_status()
        assert status["registered_checks"] == 2
        assert set(status["component_ids"]) == {"a", "b"}
        assert status["event_backbone_attached"] is False

    def test_status_with_backbone(self, wired_monitor):
        assert wired_monitor.get_status()["event_backbone_attached"] is True
