"""Tests for the RBAC Governance module."""

import sys
import os
import pytest

# Ensure the src package is importable
sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), os.pardir, "src"),
)

from rbac_governance import (
    Role,
    Permission,
    TenantPolicy,
    UserIdentity,
    RBACGovernance,
    DEFAULT_ROLE_PERMISSIONS,
)


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def gov():
    """Return a fresh RBACGovernance instance with one tenant and users."""
    g = RBACGovernance()
    policy = TenantPolicy(
        tenant_id="t1",
        name="Acme Corp",
        max_concurrent_tasks=5,
        budget_limit=5000.0,
        allowed_domains=["acme.com"],
        compliance_frameworks=["SOC2"],
    )
    g.create_tenant(policy)

    g.register_user(UserIdentity(
        user_id="owner1", tenant_id="t1",
        roles=[Role.OWNER], display_name="Alice Owner",
    ))
    g.register_user(UserIdentity(
        user_id="admin1", tenant_id="t1",
        roles=[Role.ADMIN], display_name="Bob Admin",
    ))
    g.register_user(UserIdentity(
        user_id="op1", tenant_id="t1",
        roles=[Role.OPERATOR], display_name="Carol Operator",
    ))
    g.register_user(UserIdentity(
        user_id="viewer1", tenant_id="t1",
        roles=[Role.VIEWER], display_name="Dave Viewer",
    ))
    g.register_user(UserIdentity(
        user_id="shadow1", tenant_id="t1",
        roles=[Role.SHADOW_AGENT], display_name="Shadow-Bot",
        is_shadow=True,
    ))
    return g


# ------------------------------------------------------------------
# Tenant creation & policy
# ------------------------------------------------------------------

class TestTenantManagement:
    def test_create_tenant(self):
        g = RBACGovernance()
        tid = g.create_tenant(TenantPolicy(tenant_id="tx", name="TestOrg"))
        assert tid == "tx"

    def test_duplicate_tenant_returns_id(self):
        g = RBACGovernance()
        g.create_tenant(TenantPolicy(tenant_id="tx", name="TestOrg"))
        tid = g.create_tenant(TenantPolicy(tenant_id="tx", name="TestOrg"))
        assert tid == "tx"

    def test_tenant_status(self, gov):
        status = gov.get_tenant_status("t1")
        assert status["tenant_id"] == "t1"
        assert status["name"] == "Acme Corp"
        assert status["total_users"] == 5
        assert status["shadow_agents"] == 1
        assert status["budget_limit"] == 5000.0

    def test_unknown_tenant_status(self, gov):
        status = gov.get_tenant_status("nonexistent")
        assert "error" in status


# ------------------------------------------------------------------
# User registration
# ------------------------------------------------------------------

class TestUserRegistration:
    def test_register_user(self, gov):
        uid = gov.register_user(UserIdentity(
            user_id="new1", tenant_id="t1",
            roles=[Role.VIEWER], display_name="New User",
        ))
        assert uid == "new1"

    def test_register_user_unknown_tenant(self):
        g = RBACGovernance()
        with pytest.raises(ValueError, match="does not exist"):
            g.register_user(UserIdentity(
                user_id="u1", tenant_id="no_such_tenant",
                roles=[Role.VIEWER],
            ))

    def test_duplicate_user_returns_id(self, gov):
        uid = gov.register_user(UserIdentity(
            user_id="owner1", tenant_id="t1",
            roles=[Role.OWNER], display_name="Alice Owner",
        ))
        assert uid == "owner1"


# ------------------------------------------------------------------
# Permission checks (positive & negative)
# ------------------------------------------------------------------

class TestPermissionChecks:
    def test_owner_has_all_org_permissions(self, gov):
        # OWNER has all permissions except platform-level ones
        # (APPROVE_HITL_DEPLOYMENT, MANAGE_PLATFORM, MANAGE_ALL_ORGS,
        #  DESIGNATE_PLATFORM_ADMIN) which are reserved for FOUNDER /
        #  PLATFORM_ADMIN.
        _platform_only = {
            Permission.APPROVE_HITL_DEPLOYMENT,
            Permission.MANAGE_PLATFORM,
            Permission.MANAGE_ALL_ORGS,
            Permission.DESIGNATE_PLATFORM_ADMIN,
        }
        for perm in Permission:
            allowed, reason = gov.check_permission("owner1", perm)
            if perm in _platform_only:
                assert not allowed, f"OWNER should NOT have {perm.value}"
            else:
                assert allowed, f"OWNER should have {perm.value}"

    def test_admin_lacks_manage_users(self, gov):
        allowed, _ = gov.check_permission("admin1", Permission.MANAGE_USERS)
        assert not allowed

    def test_admin_has_configure_system(self, gov):
        allowed, _ = gov.check_permission("admin1", Permission.CONFIGURE_SYSTEM)
        assert allowed

    def test_operator_can_execute(self, gov):
        allowed, _ = gov.check_permission("op1", Permission.EXECUTE_TASK)
        assert allowed

    def test_operator_cannot_configure(self, gov):
        allowed, _ = gov.check_permission("op1", Permission.CONFIGURE_SYSTEM)
        assert not allowed

    def test_viewer_only_view(self, gov):
        allowed, _ = gov.check_permission("viewer1", Permission.VIEW_STATUS)
        assert allowed
        allowed, _ = gov.check_permission("viewer1", Permission.EXECUTE_TASK)
        assert not allowed

    def test_shadow_agent_can_execute(self, gov):
        allowed, _ = gov.check_permission("shadow1", Permission.EXECUTE_TASK)
        assert allowed

    def test_shadow_agent_cannot_manage_users(self, gov):
        allowed, _ = gov.check_permission("shadow1", Permission.MANAGE_USERS)
        assert not allowed

    def test_shadow_agent_cannot_manage_shadows(self, gov):
        allowed, _ = gov.check_permission("shadow1", Permission.MANAGE_SHADOWS)
        assert not allowed

    def test_unknown_user_denied(self, gov):
        allowed, reason = gov.check_permission("ghost", Permission.VIEW_STATUS)
        assert not allowed
        assert reason == "unknown_user"

    def test_permission_reason_includes_role(self, gov):
        allowed, reason = gov.check_permission("owner1", Permission.VIEW_STATUS)
        assert allowed
        assert "granted_by_role:" in reason


# ------------------------------------------------------------------
# Tenant isolation
# ------------------------------------------------------------------

class TestTenantIsolation:
    def test_same_tenant_allowed(self, gov):
        assert gov.enforce_tenant_isolation("owner1", "t1") is True

    def test_cross_tenant_denied(self, gov):
        gov.create_tenant(TenantPolicy(tenant_id="t2", name="Other Corp"))
        assert gov.enforce_tenant_isolation("owner1", "t2") is False

    def test_unknown_user_denied(self, gov):
        assert gov.enforce_tenant_isolation("ghost", "t1") is False


# ------------------------------------------------------------------
# Shadow agent governance
# ------------------------------------------------------------------

class TestShadowAgentGovernance:
    def test_shadow_is_flagged(self, gov):
        caps = gov.get_user_capabilities("shadow1")
        assert caps["is_shadow"] is True

    def test_shadow_restricted_permissions(self, gov):
        caps = gov.get_user_capabilities("shadow1")
        assert "manage_users" not in caps["permissions"]
        assert "manage_shadows" not in caps["permissions"]
        assert "execute_task" in caps["permissions"]
        assert "view_status" in caps["permissions"]

    def test_shadow_tenant_isolation(self, gov):
        gov.create_tenant(TenantPolicy(tenant_id="t2", name="Other"))
        assert gov.enforce_tenant_isolation("shadow1", "t2") is False


# ------------------------------------------------------------------
# Role assignment authorisation
# ------------------------------------------------------------------

class TestRoleAssignment:
    def test_owner_can_assign_role(self, gov):
        result = gov.assign_role("viewer1", Role.OPERATOR, assigner_id="owner1")
        assert result is True
        caps = gov.get_user_capabilities("viewer1")
        assert "operator" in caps["roles"]

    def test_admin_can_assign_role(self, gov):
        result = gov.assign_role("viewer1", Role.OPERATOR, assigner_id="admin1")
        assert result is True

    def test_operator_cannot_assign_role(self, gov):
        result = gov.assign_role("viewer1", Role.OPERATOR, assigner_id="op1")
        assert result is False

    def test_viewer_cannot_assign_role(self, gov):
        result = gov.assign_role("op1", Role.ADMIN, assigner_id="viewer1")
        assert result is False

    def test_cross_tenant_assignment_denied(self, gov):
        gov.create_tenant(TenantPolicy(tenant_id="t2", name="Other"))
        gov.register_user(UserIdentity(
            user_id="other_owner", tenant_id="t2",
            roles=[Role.OWNER], display_name="Other Owner",
        ))
        result = gov.assign_role("viewer1", Role.ADMIN, assigner_id="other_owner")
        assert result is False

    def test_remove_role(self, gov):
        result = gov.remove_role("op1", Role.OPERATOR, remover_id="owner1")
        assert result is True
        caps = gov.get_user_capabilities("op1")
        assert "operator" not in caps["roles"]

    def test_unauthorised_remove_role(self, gov):
        result = gov.remove_role("op1", Role.OPERATOR, remover_id="viewer1")
        assert result is False


# ------------------------------------------------------------------
# User capabilities
# ------------------------------------------------------------------

class TestUserCapabilities:
    def test_capabilities_structure(self, gov):
        caps = gov.get_user_capabilities("owner1")
        assert caps["user_id"] == "owner1"
        assert caps["tenant_id"] == "t1"
        assert "roles" in caps
        assert "permissions" in caps
        assert "max_concurrent_tasks" in caps
        assert "budget_limit" in caps

    def test_unknown_user_capabilities(self, gov):
        caps = gov.get_user_capabilities("ghost")
        assert "error" in caps


# ------------------------------------------------------------------
# Status reporting
# ------------------------------------------------------------------

class TestStatusReporting:
    def test_overall_status(self, gov):
        status = gov.get_status()
        assert status["total_tenants"] == 1
        assert status["total_users"] == 5
        assert status["total_shadow_agents"] == 1
        assert status["audit_log_size"] > 0

    def test_tenant_status_audit_events(self, gov):
        status = gov.get_tenant_status("t1")
        assert status["audit_events"] >= 1
