"""
Tests for ADV-002: DeploymentAutomationController.

Validates deployment lifecycle, gate management, approval workflows,
health checks, rollback, and EventBackbone integration.

Design Label: TEST-006 / ADV-002
Owner: QA Team
"""

import os
import pytest


from deployment_automation_controller import (
    DeploymentAutomationController,
    DeploymentRequest,
    DeploymentStatus,
    Environment,
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
def controller():
    return DeploymentAutomationController()


@pytest.fixture
def wired_controller(pm, backbone):
    return DeploymentAutomationController(
        persistence_manager=pm,
        event_backbone=backbone,
    )


# ------------------------------------------------------------------
# Deployment creation
# ------------------------------------------------------------------

class TestDeploymentCreation:
    def test_create_deployment(self, controller):
        dep = controller.create_deployment(
            artifact="murphy-system",
            version="1.2.0",
            environment="staging",
        )
        assert dep.deployment_id.startswith("dep-")
        assert dep.artifact == "murphy-system"
        assert dep.version == "1.2.0"
        assert dep.environment == Environment.STAGING
        assert dep.status == DeploymentStatus.REQUESTED

    def test_deployment_to_dict(self, controller):
        dep = controller.create_deployment("app", "1.0", "dev")
        d = dep.to_dict()
        assert "deployment_id" in d
        assert "environment" in d
        assert "status" in d


# ------------------------------------------------------------------
# Gate management
# ------------------------------------------------------------------

class TestGateManagement:
    def test_register_gate(self, controller):
        gate_id = controller.register_gate("tests_pass", lambda: True)
        assert gate_id.startswith("gate-")

    def test_list_gates(self, controller):
        controller.register_gate("test_gate", lambda: True)
        gates = controller.list_gates()
        assert len(gates) == 1
        assert gates[0]["name"] == "test_gate"

    def test_run_gates_pass(self, controller):
        controller.register_gate("always_pass", lambda: True)
        dep = controller.create_deployment("app", "1.0", "staging")
        result = controller.run_gates(dep.deployment_id)
        assert result.status == DeploymentStatus.GATES_PASSED

    def test_run_gates_fail(self, controller):
        controller.register_gate("always_fail", lambda: False)
        dep = controller.create_deployment("app", "1.0", "staging")
        result = controller.run_gates(dep.deployment_id)
        assert result.status == DeploymentStatus.GATES_FAILED

    def test_production_requires_approval(self, controller):
        controller.register_gate("pass", lambda: True)
        dep = controller.create_deployment("app", "1.0", "production")
        result = controller.run_gates(dep.deployment_id)
        assert result.status == DeploymentStatus.PENDING_APPROVAL

    def test_run_gates_nonexistent_returns_none(self, controller):
        assert controller.run_gates("nonexistent") is None


# ------------------------------------------------------------------
# Approval workflow
# ------------------------------------------------------------------

class TestApproval:
    def test_approve_production(self, controller):
        controller.register_gate("pass", lambda: True)
        dep = controller.create_deployment("app", "1.0", "production")
        controller.run_gates(dep.deployment_id)
        result = controller.approve(dep.deployment_id, approver="cto")
        assert result.status == DeploymentStatus.APPROVED
        assert result.approver == "cto"

    def test_approve_nonpending_unchanged(self, controller):
        dep = controller.create_deployment("app", "1.0", "dev")
        result = controller.approve(dep.deployment_id, "admin")
        assert result.status == DeploymentStatus.REQUESTED  # unchanged


# ------------------------------------------------------------------
# Deployment execution
# ------------------------------------------------------------------

class TestDeployment:
    def test_deploy_staging(self, controller):
        controller.register_gate("pass", lambda: True)
        dep = controller.create_deployment("app", "1.0", "staging")
        controller.run_gates(dep.deployment_id)
        result = controller.deploy(dep.deployment_id)
        assert result.status == DeploymentStatus.DEPLOYED

    def test_deploy_production_after_approval(self, controller):
        controller.register_gate("pass", lambda: True)
        dep = controller.create_deployment("app", "1.0", "production")
        controller.run_gates(dep.deployment_id)
        controller.approve(dep.deployment_id, "cto")
        result = controller.deploy(dep.deployment_id)
        assert result.status == DeploymentStatus.DEPLOYED

    def test_deploy_without_gates_unchanged(self, controller):
        dep = controller.create_deployment("app", "1.0", "staging")
        result = controller.deploy(dep.deployment_id)
        assert result.status == DeploymentStatus.REQUESTED  # unchanged


# ------------------------------------------------------------------
# Health checks & rollback
# ------------------------------------------------------------------

class TestHealthCheck:
    def test_healthy_deployment(self, controller):
        controller.register_gate("pass", lambda: True)
        dep = controller.create_deployment("app", "1.0", "staging")
        controller.run_gates(dep.deployment_id)
        controller.deploy(dep.deployment_id)
        result = controller.check_health(dep.deployment_id, healthy=True)
        assert result.status == DeploymentStatus.HEALTHY
        assert result.health_checks_passed is True

    def test_unhealthy_triggers_rollback(self, controller):
        controller.register_gate("pass", lambda: True)
        dep = controller.create_deployment(
            "app", "2.0", "staging", rollback_version="1.0"
        )
        controller.run_gates(dep.deployment_id)
        controller.deploy(dep.deployment_id)
        result = controller.check_health(dep.deployment_id, healthy=False)
        assert result.status == DeploymentStatus.ROLLED_BACK

    def test_unhealthy_no_rollback_version(self, controller):
        controller.register_gate("pass", lambda: True)
        dep = controller.create_deployment("app", "2.0", "staging")
        controller.run_gates(dep.deployment_id)
        controller.deploy(dep.deployment_id)
        result = controller.check_health(dep.deployment_id, healthy=False)
        assert result.status == DeploymentStatus.UNHEALTHY


# ------------------------------------------------------------------
# Query
# ------------------------------------------------------------------

class TestQuery:
    def test_get_deployment(self, controller):
        dep = controller.create_deployment("app", "1.0", "dev")
        result = controller.get_deployment(dep.deployment_id)
        assert result is not None
        assert result["artifact"] == "app"

    def test_list_deployments(self, controller):
        controller.create_deployment("app", "1.0", "dev")
        controller.create_deployment("app", "2.0", "staging")
        deps = controller.list_deployments()
        assert len(deps) == 2

    def test_filter_by_environment(self, controller):
        controller.create_deployment("app", "1.0", "dev")
        controller.create_deployment("app", "2.0", "staging")
        staging = controller.list_deployments(environment="staging")
        assert len(staging) == 1


# ------------------------------------------------------------------
# EventBackbone integration
# ------------------------------------------------------------------

class TestEventBackboneIntegration:
    def test_deploy_publishes_event(self, wired_controller, backbone):
        received = []
        backbone.subscribe(EventType.LEARNING_FEEDBACK, lambda e: received.append(e))
        wired_controller.register_gate("pass", lambda: True)
        dep = wired_controller.create_deployment("app", "1.0", "staging")
        wired_controller.run_gates(dep.deployment_id)
        wired_controller.deploy(dep.deployment_id)
        backbone.process_pending()
        assert len(received) >= 1
        sources = [e.payload["source"] for e in received]
        assert "deployment_automation_controller" in sources


# ------------------------------------------------------------------
# Status
# ------------------------------------------------------------------

class TestStatus:
    def test_status_reflects_state(self, controller):
        controller.register_gate("pass", lambda: True)
        controller.create_deployment("app", "1.0", "dev")
        status = controller.get_status()
        assert status["total_deployments"] == 1
        assert status["registered_gates"] == 1
