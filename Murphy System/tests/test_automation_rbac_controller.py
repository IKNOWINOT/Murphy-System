"""
Tests for SAF-002: AutomationRBACController.

Validates role assignment, permission checking, default-deny,
audit logging, persistence, and EventBackbone integration.

Design Label: TEST-025 / SAF-002
Owner: QA Team
"""

import os
import pytest


from automation_rbac_controller import (
    AutomationRBACController,
    AutomationPermission,
    AutomationRole,
    AuthDecision,
    AuditEntry,
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
def rbac():
    return AutomationRBACController()


@pytest.fixture
def wired_rbac(pm, backbone):
    return AutomationRBACController(persistence_manager=pm, event_backbone=backbone)


# ------------------------------------------------------------------
# Role assignment
# ------------------------------------------------------------------

class TestRoleAssignment:
    def test_assign_role(self, rbac):
        rbac.assign_role("u1", "t1", AutomationRole.ADMIN)
        assert "admin" in rbac.get_roles("u1", "t1")

    def test_assign_multiple_roles(self, rbac):
        rbac.assign_role("u1", "t1", AutomationRole.ADMIN)
        rbac.assign_role("u1", "t1", AutomationRole.OPERATOR)
        roles = rbac.get_roles("u1", "t1")
        assert "admin" in roles
        assert "operator" in roles

    def test_revoke_role(self, rbac):
        rbac.assign_role("u1", "t1", AutomationRole.VIEWER)
        assert rbac.revoke_role("u1", "t1", AutomationRole.VIEWER) is True
        assert rbac.revoke_role("u1", "t1", AutomationRole.VIEWER) is False

    def test_no_roles_initially(self, rbac):
        assert rbac.get_roles("unknown", "tenant") == []


# ------------------------------------------------------------------
# Permission checking
# ------------------------------------------------------------------

class TestPermissionChecking:
    def test_admin_all_permissions(self, rbac):
        rbac.assign_role("u1", "t1", AutomationRole.ADMIN)
        for perm in AutomationPermission:
            assert rbac.check_permission("u1", "t1", perm) is True

    def test_viewer_limited(self, rbac):
        rbac.assign_role("u1", "t1", AutomationRole.VIEWER)
        assert rbac.check_permission("u1", "t1", AutomationPermission.VIEW_AUTOMATION_METRICS) is True
        assert rbac.check_permission("u1", "t1", AutomationPermission.TOGGLE_FULL_AUTOMATION) is False

    def test_default_deny(self, rbac):
        assert rbac.check_permission("unknown", "t1", AutomationPermission.TOGGLE_FULL_AUTOMATION) is False

    def test_tenant_isolation(self, rbac):
        rbac.assign_role("u1", "t1", AutomationRole.ADMIN)
        assert rbac.check_permission("u1", "t1", AutomationPermission.TOGGLE_FULL_AUTOMATION) is True
        assert rbac.check_permission("u1", "t2", AutomationPermission.TOGGLE_FULL_AUTOMATION) is False

    def test_operator_approve_action(self, rbac):
        rbac.assign_role("u1", "t1", AutomationRole.OPERATOR)
        assert rbac.check_permission("u1", "t1", AutomationPermission.APPROVE_AUTONOMOUS_ACTION) is True
        assert rbac.check_permission("u1", "t1", AutomationPermission.OVERRIDE_AUTOMATION) is False


# ------------------------------------------------------------------
# Audit log
# ------------------------------------------------------------------

class TestAuditLog:
    def test_audit_logged(self, rbac):
        rbac.check_permission("u1", "t1", AutomationPermission.VIEW_AUTOMATION_METRICS)
        log = rbac.get_audit_log()
        assert len(log) == 1
        assert log[0]["decision"] == "denied"

    def test_audit_entry_to_dict(self, rbac):
        rbac.assign_role("u1", "t1", AutomationRole.ADMIN)
        rbac.check_permission("u1", "t1", AutomationPermission.TOGGLE_FULL_AUTOMATION)
        log = rbac.get_audit_log()
        assert log[0]["decision"] == "allowed"
        assert "entry_id" in log[0]


# ------------------------------------------------------------------
# Persistence
# ------------------------------------------------------------------

class TestPersistence:
    def test_audit_persisted(self, wired_rbac, pm):
        wired_rbac.assign_role("u1", "t1", AutomationRole.ADMIN)
        wired_rbac.check_permission("u1", "t1", AutomationPermission.TOGGLE_FULL_AUTOMATION)
        log = wired_rbac.get_audit_log()
        loaded = pm.load_document(log[0]["entry_id"])
        assert loaded is not None


# ------------------------------------------------------------------
# EventBackbone
# ------------------------------------------------------------------

class TestEventBackbone:
    def test_check_publishes_event(self, wired_rbac, backbone):
        received = []
        backbone.subscribe(EventType.AUDIT_LOGGED, lambda e: received.append(e))
        wired_rbac.check_permission("u1", "t1", AutomationPermission.VIEW_AUTOMATION_METRICS)
        backbone.process_pending()
        assert len(received) >= 1


# ------------------------------------------------------------------
# Status
# ------------------------------------------------------------------

class TestStatus:
    def test_status(self, rbac):
        s = rbac.get_status()
        assert s["total_assignments"] == 0
        assert s["persistence_attached"] is False

    def test_wired_status(self, wired_rbac):
        s = wired_rbac.get_status()
        assert s["persistence_attached"] is True
