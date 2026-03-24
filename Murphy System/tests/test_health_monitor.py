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


# ------------------------------------------------------------------
# Kubernetes probe tests
# ------------------------------------------------------------------

class TestKubernetesProbeAdapter:
    """Tests for KubernetesProbeAdapter readiness / liveness probes."""

    def setup_method(self):
        from health_monitor import HealthMonitor, KubernetesProbeAdapter
        self.monitor = HealthMonitor()
        self.probe = KubernetesProbeAdapter(self.monitor)

    def test_is_alive_always_true(self):
        """Liveness probe always returns True when the monitor is callable."""
        assert self.probe.is_alive() is True

    def test_liveness_returns_alive_key(self):
        """liveness() response contains alive=True."""
        result = self.probe.liveness()
        assert result["alive"] is True
        assert result["status"] == "ok"

    def test_is_ready_with_no_checks_is_healthy(self):
        """is_ready() returns True when there are no registered checks (vacuously healthy)."""
        assert self.probe.is_ready() is True

    def test_is_ready_false_when_unhealthy_check_registered(self):
        """is_ready() returns False when at least one check is unhealthy."""
        from health_monitor import HealthMonitor, KubernetesProbeAdapter
        m = HealthMonitor()
        m.register("db", lambda: {"status": "unhealthy", "message": "down"})
        probe = KubernetesProbeAdapter(m)
        assert probe.is_ready() is False

    def test_readiness_returns_required_keys(self):
        """readiness() response contains all expected keys."""
        result = self.probe.readiness()
        for key in ("ready", "system_status", "healthy_count", "degraded_count",
                    "unhealthy_count", "total_latency_ms", "generated_at"):
            assert key in result, f"Missing key: {key}"

    def test_readiness_ready_when_all_checks_pass(self):
        """readiness() reports ready=True when all checks are healthy."""
        from health_monitor import HealthMonitor, KubernetesProbeAdapter
        m = HealthMonitor()
        m.register("api", lambda: {"status": "healthy", "message": "ok"})
        m.register("db", lambda: {"status": "healthy", "message": "ok"})
        probe = KubernetesProbeAdapter(m)
        result = probe.readiness()
        assert result["ready"] is True
        assert result["system_status"] == "healthy"


class TestDependencyHealthCheckFactories:
    """Tests for make_database_health_check, make_redis_health_check, make_llm_health_check."""

    def test_database_health_check_no_url(self):
        """Database health check returns unhealthy when no URL is configured."""
        import os
        from health_monitor import make_database_health_check
        check = make_database_health_check(database_url="")
        env_backup = os.environ.pop("DATABASE_URL", None)
        try:
            result = check()
            assert result["status"] in ("unhealthy", "degraded")
        finally:
            if env_backup is not None:
                os.environ["DATABASE_URL"] = env_backup

    def test_redis_health_check_no_url(self):
        """Redis health check returns degraded when no URL is configured."""
        import os
        from health_monitor import make_redis_health_check
        check = make_redis_health_check(redis_url="")
        env_backup = os.environ.pop("REDIS_URL", None)
        try:
            result = check()
            assert result["status"] in ("degraded", "unhealthy")
        finally:
            if env_backup is not None:
                os.environ["REDIS_URL"] = env_backup

    def test_llm_health_check_unreachable_url(self):
        """LLM health check returns degraded when the server is unreachable."""
        from health_monitor import make_llm_health_check
        check = make_llm_health_check(llm_url="http://127.0.0.1:19999")
        result = check()
        assert result["status"] in ("degraded", "unhealthy")

    def test_llm_health_check_returns_status_key(self):
        """LLM health check always returns a dict with a 'status' key."""
        from health_monitor import make_llm_health_check
        check = make_llm_health_check(llm_url="http://127.0.0.1:19999")
        result = check()
        assert "status" in result
        assert "message" in result
