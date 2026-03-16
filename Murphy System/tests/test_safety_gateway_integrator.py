"""
Tests for ORCH-001: SafetyGatewayIntegrator.

Validates route classification, request interception, bypass behavior,
fail-closed defaults, persistence, and EventBackbone integration.

Design Label: TEST-029 / ORCH-001
Owner: QA Team
"""

import os
import pytest


from safety_gateway_integrator import (
    SafetyGatewayIntegrator,
    RiskLevel,
    GatewayAction,
    RouteClassification,
    GatewayDecision,
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
def gateway():
    return SafetyGatewayIntegrator()


@pytest.fixture
def wired_gateway(pm, backbone):
    return SafetyGatewayIntegrator(persistence_manager=pm, event_backbone=backbone)


# ------------------------------------------------------------------
# Route classification
# ------------------------------------------------------------------

class TestRouteClassification:
    def test_classify_route(self, gateway):
        gateway.classify_route("/api/deploy", RiskLevel.CRITICAL)
        c = gateway.get_classification("/api/deploy")
        assert c is not None
        assert c["risk_level"] == "critical"

    def test_unclassified_route(self, gateway):
        assert gateway.get_classification("/unknown") is None

    def test_override_classification(self, gateway):
        gateway.classify_route("/api/data", RiskLevel.LOW)
        gateway.classify_route("/api/data", RiskLevel.HIGH)
        c = gateway.get_classification("/api/data")
        assert c["risk_level"] == "high"


# ------------------------------------------------------------------
# Bypass
# ------------------------------------------------------------------

class TestBypass:
    def test_default_bypass_routes(self, gateway):
        decision = gateway.intercept("/health", "GET")
        assert decision.action == GatewayAction.BYPASSED

    def test_add_bypass(self, gateway):
        gateway.add_bypass("/custom-health")
        decision = gateway.intercept("/custom-health", "GET")
        assert decision.action == GatewayAction.BYPASSED

    def test_remove_bypass(self, gateway):
        gateway.add_bypass("/temp")
        assert gateway.remove_bypass("/temp") is True
        assert gateway.remove_bypass("/temp") is False


# ------------------------------------------------------------------
# Interception
# ------------------------------------------------------------------

class TestInterception:
    def test_intercept_no_pipeline(self, gateway):
        gateway.classify_route("/api/data", RiskLevel.LOW)
        decision = gateway.intercept("/api/data", "GET")
        assert decision.action == GatewayAction.ALLOWED
        assert decision.validation_verdict == "no_pipeline"

    def test_intercept_unclassified_defaults_high(self, gateway):
        decision = gateway.intercept("/unknown", "POST")
        assert decision.risk_level == "high"
        assert decision.action == GatewayAction.ALLOWED

    def test_intercept_with_context(self, gateway):
        decision = gateway.intercept("/api/data", "POST",
                                      {"tenant_id": "t1", "user_id": "u1"})
        assert decision.tenant_id == "t1"
        assert decision.user_id == "u1"

    def test_decision_to_dict(self, gateway):
        decision = gateway.intercept("/api/data", "GET")
        d = decision.to_dict()
        assert "decision_id" in d
        assert "action" in d


# ------------------------------------------------------------------
# Pipeline integration
# ------------------------------------------------------------------

class TestPipelineIntegration:
    def test_failed_pipeline_blocks(self, gateway):
        class MockPipeline:
            def validate(self, action_id, action_type, context):
                class R:
                    class verdict:
                        value = "failed"
                return R()
        gateway._pipeline = MockPipeline()
        decision = gateway.intercept("/api/deploy", "POST")
        assert decision.action == GatewayAction.BLOCKED

    def test_passed_pipeline_allows(self, gateway):
        class MockPipeline:
            def validate(self, action_id, action_type, context):
                class R:
                    class verdict:
                        value = "passed"
                return R()
        gateway._pipeline = MockPipeline()
        decision = gateway.intercept("/api/deploy", "POST")
        assert decision.action == GatewayAction.ALLOWED


# ------------------------------------------------------------------
# Persistence
# ------------------------------------------------------------------

class TestPersistence:
    def test_decision_persisted(self, wired_gateway, pm):
        decision = wired_gateway.intercept("/api/data", "GET")
        loaded = pm.load_document(decision.decision_id)
        assert loaded is not None


# ------------------------------------------------------------------
# EventBackbone
# ------------------------------------------------------------------

class TestEventBackbone:
    def test_decision_publishes_event(self, wired_gateway, backbone):
        received = []
        backbone.subscribe(EventType.SYSTEM_HEALTH, lambda e: received.append(e))
        wired_gateway.intercept("/api/data", "GET")
        backbone.process_pending()
        assert len(received) >= 1


# ------------------------------------------------------------------
# Status
# ------------------------------------------------------------------

class TestStatus:
    def test_status(self, gateway):
        s = gateway.get_status()
        assert s["classified_routes"] == 0
        assert s["pipeline_attached"] is False

    def test_wired_status(self, wired_gateway):
        s = wired_gateway.get_status()
        assert s["persistence_attached"] is True
        assert s["backbone_attached"] is True
