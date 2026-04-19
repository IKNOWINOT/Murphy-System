"""Tests for RBAC Platform Roles — FOUNDER and PLATFORM_ADMIN (PATCH-010)."""

import sys
import os
import pytest

# Ensure the src package is importable
sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "src"),
)

from rbac_governance import (
    Role,
    Permission,
    TenantPolicy,
    UserIdentity,
    RBACGovernance,
    DEFAULT_ROLE_PERMISSIONS,
    HITL_DEPLOYMENT_REVIEWER_ROLES,
)


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def gov():
    """Return a governance instance with platform-level users."""
    g = RBACGovernance()
    policy = TenantPolicy(
        tenant_id="platform",
        name="Murphy Platform",
    )
    g.create_tenant(policy)

    g.register_user(UserIdentity(
        user_id="founder1", tenant_id="platform",
        roles=[Role.FOUNDER], display_name="Platform Founder",
    ))
    g.register_user(UserIdentity(
        user_id="padmin1", tenant_id="platform",
        roles=[Role.PLATFORM_ADMIN], display_name="Platform Admin",
    ))
    g.register_user(UserIdentity(
        user_id="owner1", tenant_id="platform",
        roles=[Role.OWNER], display_name="Org Owner",
    ))
    g.register_user(UserIdentity(
        user_id="viewer1", tenant_id="platform",
        roles=[Role.VIEWER], display_name="Viewer",
    ))
    return g


# ------------------------------------------------------------------
# Role enum
# ------------------------------------------------------------------

class TestPlatformRoles:
    def test_founder_role_exists(self):
        assert Role.FOUNDER.value == "founder"

    def test_platform_admin_role_exists(self):
        assert Role.PLATFORM_ADMIN.value == "platform_admin"


# ------------------------------------------------------------------
# Permissions
# ------------------------------------------------------------------

class TestPlatformPermissions:
    def test_approve_hitl_deployment_exists(self):
        assert Permission.APPROVE_HITL_DEPLOYMENT.value == "approve_hitl_deployment"

    def test_manage_platform_exists(self):
        assert Permission.MANAGE_PLATFORM.value == "manage_platform"

    def test_manage_all_orgs_exists(self):
        assert Permission.MANAGE_ALL_ORGS.value == "manage_all_orgs"

    def test_designate_platform_admin_exists(self):
        assert Permission.DESIGNATE_PLATFORM_ADMIN.value == "designate_platform_admin"


# ------------------------------------------------------------------
# Default role permissions
# ------------------------------------------------------------------

class TestDefaultRolePermissions:
    def test_founder_has_all_permissions(self):
        founder_perms = DEFAULT_ROLE_PERMISSIONS[Role.FOUNDER]
        for perm in Permission:
            assert perm in founder_perms, f"FOUNDER should have {perm.value}"

    def test_platform_admin_has_most_permissions(self):
        padmin_perms = DEFAULT_ROLE_PERMISSIONS[Role.PLATFORM_ADMIN]
        # Should have approve_hitl_deployment
        assert Permission.APPROVE_HITL_DEPLOYMENT in padmin_perms
        assert Permission.MANAGE_PLATFORM in padmin_perms
        assert Permission.MANAGE_ALL_ORGS in padmin_perms
        # Should NOT have designate_platform_admin
        assert Permission.DESIGNATE_PLATFORM_ADMIN not in padmin_perms

    def test_owner_no_platform_perms(self):
        owner_perms = DEFAULT_ROLE_PERMISSIONS[Role.OWNER]
        assert Permission.APPROVE_HITL_DEPLOYMENT not in owner_perms
        assert Permission.MANAGE_PLATFORM not in owner_perms
        assert Permission.MANAGE_ALL_ORGS not in owner_perms
        assert Permission.DESIGNATE_PLATFORM_ADMIN not in owner_perms

    def test_admin_no_platform_perms(self):
        admin_perms = DEFAULT_ROLE_PERMISSIONS[Role.ADMIN]
        assert Permission.APPROVE_HITL_DEPLOYMENT not in admin_perms
        assert Permission.MANAGE_PLATFORM not in admin_perms

    def test_viewer_minimal_perms(self):
        viewer_perms = DEFAULT_ROLE_PERMISSIONS[Role.VIEWER]
        assert Permission.VIEW_STATUS in viewer_perms
        assert Permission.EXECUTE_TASK not in viewer_perms


# ------------------------------------------------------------------
# HITL deployment reviewer roles
# ------------------------------------------------------------------

class TestHITLDeploymentReviewerRoles:
    def test_founder_is_reviewer(self):
        assert Role.FOUNDER in HITL_DEPLOYMENT_REVIEWER_ROLES

    def test_platform_admin_is_reviewer(self):
        assert Role.PLATFORM_ADMIN in HITL_DEPLOYMENT_REVIEWER_ROLES

    def test_owner_is_not_reviewer(self):
        assert Role.OWNER not in HITL_DEPLOYMENT_REVIEWER_ROLES

    def test_admin_is_not_reviewer(self):
        assert Role.ADMIN not in HITL_DEPLOYMENT_REVIEWER_ROLES


# ------------------------------------------------------------------
# Permission checks via governance instance
# ------------------------------------------------------------------

class TestPlatformPermissionChecks:
    def test_founder_can_approve_hitl(self, gov):
        allowed, _ = gov.check_permission("founder1", Permission.APPROVE_HITL_DEPLOYMENT)
        assert allowed

    def test_founder_can_designate_admin(self, gov):
        allowed, _ = gov.check_permission("founder1", Permission.DESIGNATE_PLATFORM_ADMIN)
        assert allowed

    def test_platform_admin_can_approve_hitl(self, gov):
        allowed, _ = gov.check_permission("padmin1", Permission.APPROVE_HITL_DEPLOYMENT)
        assert allowed

    def test_platform_admin_cannot_designate_admin(self, gov):
        allowed, _ = gov.check_permission("padmin1", Permission.DESIGNATE_PLATFORM_ADMIN)
        assert not allowed

    def test_owner_cannot_approve_hitl_deployment(self, gov):
        allowed, _ = gov.check_permission("owner1", Permission.APPROVE_HITL_DEPLOYMENT)
        assert not allowed

    def test_viewer_cannot_manage_platform(self, gov):
        allowed, _ = gov.check_permission("viewer1", Permission.MANAGE_PLATFORM)
        assert not allowed
