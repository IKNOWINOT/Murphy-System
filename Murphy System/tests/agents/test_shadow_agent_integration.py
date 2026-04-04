"""Tests for shadow-agent + account-plane integration."""

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

from src.shadow_agent_integration import (
    AccountType,
    ShadowStatus,
    Account,
    ShadowAgent,
    ShadowBinding,
    ShadowAgentIntegration,
)


@pytest.fixture
def integration():
    return ShadowAgentIntegration()


@pytest.fixture
def user_account(integration):
    return integration.create_account("Alice", AccountType.USER)


@pytest.fixture
def org_account(integration):
    return integration.create_account("Acme Corp", AccountType.ORGANIZATION)


@pytest.fixture
def shadow(integration, user_account):
    return integration.create_shadow_agent(
        primary_role_id="role-engineer",
        account_id=user_account.account_id,
        department="engineering",
        permissions=["read", "write", "deploy"],
    )


# ------------------------------------------------------------------
# Account creation
# ------------------------------------------------------------------


class TestAccountCreation:
    def test_create_user_account(self, integration):
        acct = integration.create_account("Bob", AccountType.USER)
        assert isinstance(acct, Account)
        assert acct.account_type == AccountType.USER
        assert acct.display_name == "Bob"

    def test_create_org_account(self, integration):
        acct = integration.create_account("Acme", AccountType.ORGANIZATION, {"tier": "enterprise"})
        assert acct.account_type == AccountType.ORGANIZATION
        assert acct.metadata == {"tier": "enterprise"}

    def test_user_and_org_separation(self, integration, user_account, org_account):
        assert user_account.account_id != org_account.account_id
        assert user_account.account_type == AccountType.USER
        assert org_account.account_type == AccountType.ORGANIZATION


# ------------------------------------------------------------------
# Shadow agent creation and binding
# ------------------------------------------------------------------


class TestShadowCreation:
    def test_create_shadow_agent(self, shadow):
        assert isinstance(shadow, ShadowAgent)
        assert shadow.status == ShadowStatus.ACTIVE
        assert shadow.department == "engineering"
        assert shadow.governance_boundary == "standard"

    def test_create_shadow_requires_valid_account(self, integration):
        with pytest.raises(ValueError, match="does not exist"):
            integration.create_shadow_agent("role-x", "bad-id", "dept")

    def test_create_shadow_with_org(self, integration, user_account, org_account):
        agent = integration.create_shadow_agent(
            primary_role_id="role-pm",
            account_id=user_account.account_id,
            department="product",
            org_id=org_account.account_id,
        )
        assert agent.org_id == org_account.account_id

    def test_create_shadow_invalid_org(self, integration, user_account):
        with pytest.raises(ValueError, match="org account"):
            integration.create_shadow_agent(
                "role-x", user_account.account_id, "dept", org_id="no-such-org",
            )

    def test_bind_shadow_to_role(self, integration, shadow):
        binding = integration.bind_shadow_to_role(shadow.agent_id, "role-lead")
        assert isinstance(binding, ShadowBinding)
        assert binding.shadow_agent_id == shadow.agent_id
        assert binding.target_role_id == "role-lead"
        assert binding.scope == "department"

    def test_bind_nonexistent_shadow_raises(self, integration):
        with pytest.raises(ValueError, match="does not exist"):
            integration.bind_shadow_to_role("no-agent", "role-x")

    def test_bind_suspended_shadow_raises(self, integration, shadow):
        integration.suspend_shadow(shadow.agent_id)
        with pytest.raises(ValueError, match="suspended"):
            integration.bind_shadow_to_role(shadow.agent_id, "role-x")


# ------------------------------------------------------------------
# Permission checks (org-chart parity)
# ------------------------------------------------------------------


class TestPermissionChecks:
    def test_allowed_action(self, integration, shadow):
        allowed, reason = integration.check_shadow_permission(shadow.agent_id, "read")
        assert allowed is True
        assert "org-chart parity" in reason

    def test_denied_action(self, integration, shadow):
        allowed, reason = integration.check_shadow_permission(shadow.agent_id, "admin")
        assert allowed is False
        assert "not in shadow agent permissions" in reason
        assert shadow.primary_role_id in reason

    def test_suspended_always_denied(self, integration, shadow):
        integration.suspend_shadow(shadow.agent_id)
        allowed, reason = integration.check_shadow_permission(shadow.agent_id, "read")
        assert allowed is False
        assert "suspended" in reason

    def test_revoked_always_denied(self, integration, shadow):
        integration.revoke_shadow(shadow.agent_id)
        allowed, reason = integration.check_shadow_permission(shadow.agent_id, "read")
        assert allowed is False
        assert "revoked" in reason

    def test_nonexistent_agent_denied(self, integration):
        allowed, reason = integration.check_shadow_permission("fake", "read")
        assert allowed is False
        assert "not found" in reason

    def test_org_chart_parity_same_permissions(self, integration, user_account):
        """Shadow gets the SAME permissions as the primary role definition."""
        perms = ["read", "write", "deploy"]
        agent = integration.create_shadow_agent(
            "role-eng", user_account.account_id, "engineering", permissions=perms,
        )
        for perm in perms:
            ok, _ = integration.check_shadow_permission(agent.agent_id, perm)
            assert ok is True, f"expected {perm} to be allowed"

        ok, _ = integration.check_shadow_permission(agent.agent_id, "delete")
        assert ok is False


# ------------------------------------------------------------------
# Shadow lifecycle
# ------------------------------------------------------------------


class TestShadowLifecycle:
    def test_suspend_active(self, integration, shadow):
        assert integration.suspend_shadow(shadow.agent_id) is True

    def test_suspend_non_active_fails(self, integration, shadow):
        integration.suspend_shadow(shadow.agent_id)
        assert integration.suspend_shadow(shadow.agent_id) is False

    def test_revoke_active(self, integration, shadow):
        assert integration.revoke_shadow(shadow.agent_id) is True

    def test_revoke_suspended(self, integration, shadow):
        integration.suspend_shadow(shadow.agent_id)
        assert integration.revoke_shadow(shadow.agent_id) is True

    def test_revoke_already_revoked(self, integration, shadow):
        integration.revoke_shadow(shadow.agent_id)
        assert integration.revoke_shadow(shadow.agent_id) is False

    def test_reactivate_suspended(self, integration, shadow):
        integration.suspend_shadow(shadow.agent_id)
        assert integration.reactivate_shadow(shadow.agent_id) is True
        ok, _ = integration.check_shadow_permission(shadow.agent_id, "read")
        assert ok is True

    def test_reactivate_revoked_fails(self, integration, shadow):
        integration.revoke_shadow(shadow.agent_id)
        assert integration.reactivate_shadow(shadow.agent_id) is False

    def test_reactivate_active_fails(self, integration, shadow):
        assert integration.reactivate_shadow(shadow.agent_id) is False

    def test_suspend_nonexistent_fails(self, integration):
        assert integration.suspend_shadow("nope") is False

    def test_revoke_nonexistent_fails(self, integration):
        assert integration.revoke_shadow("nope") is False

    def test_reactivate_nonexistent_fails(self, integration):
        assert integration.reactivate_shadow("nope") is False


# ------------------------------------------------------------------
# Account / org filtering
# ------------------------------------------------------------------


class TestFiltering:
    def test_get_shadows_for_account(self, integration, user_account):
        integration.create_shadow_agent("r1", user_account.account_id, "d1")
        integration.create_shadow_agent("r2", user_account.account_id, "d2")
        shadows = integration.get_shadows_for_account(user_account.account_id)
        assert len(shadows) == 2

    def test_get_shadows_for_org(self, integration, user_account, org_account):
        integration.create_shadow_agent(
            "r1", user_account.account_id, "d1", org_id=org_account.account_id,
        )
        integration.create_shadow_agent(
            "r2", user_account.account_id, "d2", org_id=org_account.account_id,
        )
        integration.create_shadow_agent("r3", user_account.account_id, "d3")
        shadows = integration.get_shadows_for_org(org_account.account_id)
        assert len(shadows) == 2

    def test_empty_results(self, integration):
        assert integration.get_shadows_for_account("none") == []
        assert integration.get_shadows_for_org("none") == []


# ------------------------------------------------------------------
# Governance boundary enforcement
# ------------------------------------------------------------------


class TestGovernanceBoundary:
    def test_default_boundary(self, integration, shadow):
        boundary = integration.get_shadow_governance_boundary(shadow.agent_id)
        assert boundary == "standard"

    def test_nonexistent_returns_none(self, integration):
        assert integration.get_shadow_governance_boundary("nope") is None

    def test_boundary_matches_primary_role(self, integration, shadow):
        """Shadow governance boundary must match the primary role boundary."""
        boundary = integration.get_shadow_governance_boundary(shadow.agent_id)
        assert boundary == shadow.governance_boundary


# ------------------------------------------------------------------
# Status reporting
# ------------------------------------------------------------------


class TestStatus:
    def test_empty_status(self, integration):
        status = integration.get_status()
        assert status["total_accounts"] == 0
        assert status["total_shadow_agents"] == 0
        assert status["total_bindings"] == 0

    def test_status_after_operations(self, integration, user_account, shadow):
        integration.bind_shadow_to_role(shadow.agent_id, "role-lead")
        integration.suspend_shadow(shadow.agent_id)
        status = integration.get_status()
        assert status["total_accounts"] == 1
        assert status["total_shadow_agents"] == 1
        assert status["suspended_shadows"] == 1
        assert status["active_shadows"] == 0
        assert status["total_bindings"] == 1
        assert status["total_audit_entries"] > 0


# ------------------------------------------------------------------
# Thread safety
# ------------------------------------------------------------------


class TestThreadSafety:
    def test_concurrent_shadow_creation(self, integration, user_account):
        """Multiple threads creating shadows must not corrupt state."""
        errors = []

        def create(idx):
            try:
                integration.create_shadow_agent(
                    f"role-{idx}", user_account.account_id, f"dept-{idx}",
                )
            except Exception as exc:
                errors.append(exc)

        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = [pool.submit(create, i) for i in range(50)]
            for f in as_completed(futures):
                f.result()

        assert errors == []
        shadows = integration.get_shadows_for_account(user_account.account_id)
        assert len(shadows) == 50

    def test_concurrent_permission_checks(self, integration, shadow):
        """Concurrent permission checks must be consistent."""
        results = []

        def check(_):
            ok, _ = integration.check_shadow_permission(shadow.agent_id, "read")
            results.append(ok)

        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = [pool.submit(check, i) for i in range(50)]
            for f in as_completed(futures):
                f.result()

        assert all(results)
        assert len(results) == 50

    def test_concurrent_lifecycle(self, integration, user_account):
        """Suspend/reactivate cycles under concurrency."""
        agent = integration.create_shadow_agent(
            "role-lc", user_account.account_id, "dept", permissions=["act"],
        )
        barrier = threading.Barrier(2)

        def suspend():
            barrier.wait()
            integration.suspend_shadow(agent.agent_id)

        def reactivate():
            barrier.wait()
            integration.reactivate_shadow(agent.agent_id)

        t1 = threading.Thread(target=suspend)
        t2 = threading.Thread(target=reactivate)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Agent should be in a valid state regardless of ordering
        assert agent.status in (ShadowStatus.ACTIVE, ShadowStatus.SUSPENDED)
