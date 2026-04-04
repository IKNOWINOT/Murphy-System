"""
Tests for INT-001: AutomationIntegrationHub.

Validates module registration, event routing, health reporting,
persistence integration, and EventBackbone event publishing.

Design Label: TEST-009 / INT-001
Owner: QA Team
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from automation_integration_hub import (
    AutomationIntegrationHub,
    RegisteredModule,
    ModulePhase,
    RouteRecord,
    RouteStatus,
    IntegrationHealthReport,
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
def hub():
    return AutomationIntegrationHub()


@pytest.fixture
def wired_hub(pm, backbone):
    return AutomationIntegrationHub(
        event_backbone=backbone,
        persistence_manager=pm,
    )


# ------------------------------------------------------------------
# Module registration
# ------------------------------------------------------------------

class TestModuleRegistration:
    def test_register_module(self, hub):
        mod = hub.register_module("OBS-001", "HealthMonitor", ModulePhase.OBSERVABILITY)
        assert mod.design_label == "OBS-001"
        assert mod.phase == ModulePhase.OBSERVABILITY

    def test_register_with_event_types(self, hub):
        hub.register_module(
            "OBS-003", "LogAnalysis", ModulePhase.OBSERVABILITY,
            event_types=["LEARNING_FEEDBACK", "TASK_FAILED"],
        )
        routes = hub.get_event_routes()
        assert "OBS-003" in routes.get("LEARNING_FEEDBACK", [])
        assert "OBS-003" in routes.get("TASK_FAILED", [])

    def test_unregister_module(self, hub):
        hub.register_module("TEST-001", "Test", ModulePhase.INTEGRATION)
        assert hub.unregister_module("TEST-001") is True
        assert hub.get_module("TEST-001") is None

    def test_unregister_nonexistent(self, hub):
        assert hub.unregister_module("NOPE") is False

    def test_module_to_dict(self, hub):
        hub.register_module("OBS-001", "Health", ModulePhase.OBSERVABILITY)
        d = hub.get_module("OBS-001")
        assert d is not None
        assert "design_label" in d
        assert "phase" in d

    def test_list_modules(self, hub):
        hub.register_module("A-001", "Alpha", ModulePhase.DEVELOPMENT)
        hub.register_module("B-001", "Beta", ModulePhase.SUPPORT)
        mods = hub.list_modules()
        assert len(mods) == 2

    def test_list_modules_by_phase(self, hub):
        hub.register_module("A-001", "Alpha", ModulePhase.DEVELOPMENT)
        hub.register_module("B-001", "Beta", ModulePhase.SUPPORT)
        dev_only = hub.list_modules(phase=ModulePhase.DEVELOPMENT)
        assert len(dev_only) == 1
        assert dev_only[0]["design_label"] == "A-001"


# ------------------------------------------------------------------
# Event routing
# ------------------------------------------------------------------

class TestEventRouting:
    def test_route_no_handler(self, hub):
        records = hub.route_event("UNKNOWN_EVENT", source="test")
        assert len(records) == 1
        assert records[0].status == RouteStatus.NO_HANDLER

    def test_route_to_registered_module(self, hub):
        received = []
        hub.register_module(
            "OBS-003", "LogAnalysis", ModulePhase.OBSERVABILITY,
            handler=lambda et, p: received.append((et, p)),
            event_types=["LEARNING_FEEDBACK"],
        )
        records = hub.route_event("LEARNING_FEEDBACK", source="test", payload={"key": "val"})
        assert len(records) == 1
        assert records[0].status == RouteStatus.DELIVERED
        assert len(received) == 1

    def test_route_handler_error(self, hub):
        def bad_handler(et, p):
            raise ValueError("boom")
        hub.register_module(
            "BAD-001", "Bad", ModulePhase.INTEGRATION,
            handler=bad_handler,
            event_types=["TASK_FAILED"],
        )
        records = hub.route_event("TASK_FAILED", source="test")
        assert records[0].status == RouteStatus.HANDLER_ERROR

    def test_route_module_missing(self, hub):
        hub.add_event_route("TASK_COMPLETED", "GONE-001")
        records = hub.route_event("TASK_COMPLETED", source="test")
        assert records[0].status == RouteStatus.MODULE_MISSING

    def test_route_history(self, hub):
        hub.register_module(
            "X-001", "X", ModulePhase.INTEGRATION,
            event_types=["LEARNING_FEEDBACK"],
        )
        hub.route_event("LEARNING_FEEDBACK", source="test")
        history = hub.get_route_history()
        assert len(history) >= 1

    def test_add_remove_route(self, hub):
        hub.register_module("X-001", "X", ModulePhase.INTEGRATION)
        hub.add_event_route("CUSTOM_EVENT", "X-001")
        routes = hub.get_event_routes()
        assert "X-001" in routes["CUSTOM_EVENT"]
        hub.remove_event_route("CUSTOM_EVENT", "X-001")
        routes = hub.get_event_routes()
        assert "X-001" not in routes.get("CUSTOM_EVENT", [])


# ------------------------------------------------------------------
# Health reporting
# ------------------------------------------------------------------

class TestHealthReport:
    def test_generate_report(self, hub):
        hub.register_module("A-001", "A", ModulePhase.OBSERVABILITY)
        hub.register_module("B-001", "B", ModulePhase.DEVELOPMENT)
        report = hub.generate_health_report()
        assert report.total_modules == 2
        assert report.healthy_modules == 2

    def test_report_to_dict(self, hub):
        hub.register_module("A-001", "A", ModulePhase.OBSERVABILITY)
        report = hub.generate_health_report()
        d = report.to_dict()
        assert "report_id" in d
        assert "total_modules" in d


# ------------------------------------------------------------------
# Persistence
# ------------------------------------------------------------------

class TestPersistence:
    def test_report_persisted(self, wired_hub, pm):
        wired_hub.register_module("A-001", "A", ModulePhase.OBSERVABILITY)
        report = wired_hub.generate_health_report()
        loaded = pm.load_document(report.report_id)
        assert loaded is not None
        assert loaded["total_modules"] == 1


# ------------------------------------------------------------------
# EventBackbone integration
# ------------------------------------------------------------------

class TestEventBackboneIntegration:
    def test_route_publishes_event(self, wired_hub, backbone):
        received = []
        backbone.subscribe(EventType.LEARNING_FEEDBACK, lambda e: received.append(e))
        wired_hub.register_module(
            "X-001", "X", ModulePhase.INTEGRATION,
            event_types=["LEARNING_FEEDBACK"],
        )
        wired_hub.route_event("LEARNING_FEEDBACK", source="test")
        backbone.process_pending()
        assert len(received) >= 1


# ------------------------------------------------------------------
# Status
# ------------------------------------------------------------------

class TestStatus:
    def test_status(self, hub):
        hub.register_module("A-001", "A", ModulePhase.OBSERVABILITY)
        status = hub.get_status()
        assert status["total_modules"] == 1
        assert status["persistence_attached"] is False
        assert status["backbone_attached"] is False

    def test_status_wired(self, wired_hub):
        status = wired_hub.get_status()
        assert status["persistence_attached"] is True
        assert status["backbone_attached"] is True
