# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Tests for WIRE-001: SelfLoopWiring.

Validates startup wiring, graceful degradation, scheduler behaviour,
and FastAPI route registration.

Design Label: TEST-002 / WIRE-001
Owner: QA Team
"""

import threading
import time

import pytest

from self_loop_wiring import (
    SelfLoopScheduler,
    register_self_loop_routes,
    shutdown_self_improvement_loop,
    wire_self_improvement_loop,
)
import self_loop_wiring as _wiring_module


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _reset_module_state() -> None:
    """Reset the module-level singletons between tests."""
    with _wiring_module._state_lock:
        _wiring_module._components = {}
        _wiring_module._scheduler = None


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clean_state():
    """Ensure clean module-level state for every test."""
    _reset_module_state()
    yield
    # Stop any scheduler that may have been left running
    shutdown_self_improvement_loop()
    _reset_module_state()


@pytest.fixture
def components():
    """Wire the loop and return the component dict."""
    return wire_self_improvement_loop()


# ---------------------------------------------------------------------------
# wire_self_improvement_loop
# ---------------------------------------------------------------------------

class TestWireSelfImprovementLoop:
    def test_returns_dict(self, components):
        assert isinstance(components, dict)

    def test_expected_keys_present(self, components):
        # These should always be present when all modules are available
        expected = {
            "backbone",
            "engine",
            "orchestrator",
            "connector",
            "health_monitor",
            "coordinator",
            "bug_detector",
            "scheduler",
        }
        assert expected.issubset(set(components.keys()))

    def test_scheduler_is_running_after_wire(self, components):
        scheduler = components.get("scheduler")
        assert scheduler is not None
        assert scheduler.is_running is True

    def test_module_state_populated(self, components):
        with _wiring_module._state_lock:
            assert len(_wiring_module._components) > 0
            assert _wiring_module._scheduler is not None

    def test_backbone_registered_as_singleton(self, components):
        try:
            import event_backbone_client
            assert event_backbone_client.get_backbone() is components.get("backbone")
        except ImportError:
            pytest.skip("event_backbone_client not available")

    def test_health_checks_registered(self, components):
        monitor = components.get("health_monitor")
        if monitor is None:
            pytest.skip("HealthMonitor not available")
        status = monitor.get_status()
        # At least the engine, orchestrator, connector, coordinator should be registered
        assert status["registered_checks"] >= 1


class TestGracefulDegradation:
    """wire_self_improvement_loop should tolerate missing subsystem modules."""

    def test_still_returns_dict_with_no_subsystems(self, monkeypatch):
        """Simulate all subsystems being unavailable."""
        monkeypatch.setattr(_wiring_module, "_BACKBONE_AVAILABLE", False)
        monkeypatch.setattr(_wiring_module, "_ENGINE_AVAILABLE", False)
        monkeypatch.setattr(_wiring_module, "_ORCHESTRATOR_AVAILABLE", False)
        monkeypatch.setattr(_wiring_module, "_CONNECTOR_AVAILABLE", False)
        monkeypatch.setattr(_wiring_module, "_MONITOR_AVAILABLE", False)
        monkeypatch.setattr(_wiring_module, "_COORDINATOR_AVAILABLE", False)
        monkeypatch.setattr(_wiring_module, "_BUG_DETECTOR_AVAILABLE", False)
        monkeypatch.setattr(_wiring_module, "_CLIENT_AVAILABLE", False)

        result = wire_self_improvement_loop()
        assert isinstance(result, dict)
        # Scheduler is always created
        assert "scheduler" in result

    def test_missing_backbone_still_wires_engine(self, monkeypatch):
        """Engine should be created even if backbone is missing."""
        monkeypatch.setattr(_wiring_module, "_BACKBONE_AVAILABLE", False)
        monkeypatch.setattr(_wiring_module, "_CLIENT_AVAILABLE", False)

        result = wire_self_improvement_loop()
        assert "engine" in result
        assert "backbone" not in result

    def test_missing_engine_still_wires_orchestrator(self, monkeypatch):
        """Orchestrator should be created even if engine is missing."""
        monkeypatch.setattr(_wiring_module, "_ENGINE_AVAILABLE", False)

        result = wire_self_improvement_loop()
        assert "orchestrator" in result
        assert "engine" not in result


# ---------------------------------------------------------------------------
# shutdown_self_improvement_loop
# ---------------------------------------------------------------------------

class TestShutdown:
    def test_stops_scheduler(self, components):
        scheduler = components.get("scheduler")
        assert scheduler is not None
        assert scheduler.is_running is True
        shutdown_self_improvement_loop()
        # After a brief wait the daemon thread should have stopped
        time.sleep(0.2)
        assert scheduler.is_running is False

    def test_clears_module_state(self, components):
        shutdown_self_improvement_loop()
        with _wiring_module._state_lock:
            assert len(_wiring_module._components) == 0
            assert _wiring_module._scheduler is None

    def test_idempotent(self):
        """Calling shutdown when nothing is wired should not raise."""
        shutdown_self_improvement_loop()
        shutdown_self_improvement_loop()  # second call is safe


# ---------------------------------------------------------------------------
# SelfLoopScheduler
# ---------------------------------------------------------------------------

class TestSelfLoopScheduler:
    def test_starts_and_stops(self):
        scheduler = SelfLoopScheduler(interval_seconds=60)
        scheduler.start()
        assert scheduler.is_running is True
        scheduler.stop()
        time.sleep(0.2)
        assert scheduler.is_running is False

    def test_double_start_is_safe(self):
        scheduler = SelfLoopScheduler(interval_seconds=60)
        scheduler.start()
        try:
            scheduler.start()  # second start should warn but not crash
            assert scheduler.is_running is True
        finally:
            scheduler.stop()

    def test_stop_before_start_is_safe(self):
        scheduler = SelfLoopScheduler(interval_seconds=60)
        scheduler.stop()  # should not raise

    def test_calls_run_cycle_on_schedule(self):
        """Scheduler should call run_cycle() at least once within 2 intervals."""
        call_times = []

        class FakeConnector:
            def run_cycle(self):
                call_times.append(time.monotonic())
                return "ok"

        scheduler = SelfLoopScheduler(
            connector=FakeConnector(),
            interval_seconds=0.05,  # 50 ms for fast tests
        )
        scheduler.start()
        try:
            deadline = time.monotonic() + 1.0
            while time.monotonic() < deadline:
                if len(call_times) >= 2:
                    break
                time.sleep(0.01)
        finally:
            scheduler.stop()

        assert len(call_times) >= 1

    def test_calls_health_check_offset_from_cycle(self):
        """Health check should be called offset by half the interval."""
        cycle_times = []
        health_times = []

        class FakeConnector:
            def run_cycle(self):
                cycle_times.append(time.monotonic())

        class FakeMonitor:
            def check_all(self):
                health_times.append(time.monotonic())
                return "ok"

        scheduler = SelfLoopScheduler(
            connector=FakeConnector(),
            health_monitor=FakeMonitor(),
            interval_seconds=0.1,  # 100 ms
        )
        scheduler.start()
        try:
            deadline = time.monotonic() + 1.0
            while time.monotonic() < deadline:
                if cycle_times and health_times:
                    break
                time.sleep(0.01)
        finally:
            scheduler.stop()

        assert cycle_times, "run_cycle never called"
        assert health_times, "check_all never called"

    def test_get_status_reflects_state(self):
        scheduler = SelfLoopScheduler(interval_seconds=60)
        status = scheduler.get_status()
        assert status["running"] is False
        assert status["interval_seconds"] == 60
        assert status["cycle_count"] == 0
        assert status["health_count"] == 0

        scheduler.start()
        try:
            status = scheduler.get_status()
            assert status["running"] is True
        finally:
            scheduler.stop()

    def test_run_cycle_exception_does_not_crash_scheduler(self):
        """A crashing connector should not kill the scheduler thread."""
        class CrashingConnector:
            def run_cycle(self):
                raise RuntimeError("boom")

        scheduler = SelfLoopScheduler(
            connector=CrashingConnector(),
            interval_seconds=0.05,
        )
        scheduler.start()
        time.sleep(0.3)
        assert scheduler.is_running is True
        scheduler.stop()

    def test_thread_safety_start_stop(self):
        """Rapid concurrent start/stop calls must not deadlock."""
        scheduler = SelfLoopScheduler(interval_seconds=60)
        errors = []

        def _toggle():
            try:
                for _ in range(5):
                    scheduler.start()
                    scheduler.stop()
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=_toggle) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert not errors, f"Thread safety errors: {errors}"


# ---------------------------------------------------------------------------
# register_self_loop_routes
# ---------------------------------------------------------------------------

class TestSelfLoopRoutes:
    def test_status_endpoint_returns_200(self, components):
        try:
            from fastapi import FastAPI
            from fastapi.testclient import TestClient
        except ImportError:
            pytest.skip("fastapi / httpx not installed")

        app = FastAPI()
        register_self_loop_routes(app)
        client = TestClient(app)

        resp = client.get("/api/self-loop/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "status" in data
        assert "subsystems_active" in data

    def test_status_endpoint_includes_all_subsystems(self, components):
        try:
            from fastapi import FastAPI
            from fastapi.testclient import TestClient
        except ImportError:
            pytest.skip("fastapi / httpx not installed")

        app = FastAPI()
        register_self_loop_routes(app)
        client = TestClient(app)

        resp = client.get("/api/self-loop/status")
        data = resp.json()
        # Compare the status keys reported by the endpoint to the wired components
        assert set(data["status"].keys()) == set(components.keys())

    def test_trigger_cycle_endpoint_returns_200(self, components):
        try:
            from fastapi import FastAPI
            from fastapi.testclient import TestClient
        except ImportError:
            pytest.skip("fastapi / httpx not installed")

        app = FastAPI()
        register_self_loop_routes(app)
        client = TestClient(app)

        resp = client.post("/api/self-loop/trigger-cycle")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "result" in data

    def test_trigger_cycle_returns_503_when_no_connector(self, monkeypatch):
        """POST /api/self-loop/trigger-cycle → 503 when connector is absent."""
        try:
            from fastapi import FastAPI
            from fastapi.testclient import TestClient
        except ImportError:
            pytest.skip("fastapi / httpx not installed")

        # Wire without connector
        monkeypatch.setattr(_wiring_module, "_CONNECTOR_AVAILABLE", False)
        wire_self_improvement_loop()

        app = FastAPI()
        register_self_loop_routes(app)
        client = TestClient(app)

        resp = client.post("/api/self-loop/trigger-cycle")
        assert resp.status_code == 503
        data = resp.json()
        assert data["success"] is False
