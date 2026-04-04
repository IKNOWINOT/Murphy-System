"""
Tests for the Feature Flag System (FF-001..FF-003).

Covers: flag CRUD, boolean/percentage/MRR/tenant-list evaluation,
per-tenant overrides, rollout, and introspection.
"""

from __future__ import annotations

import pytest

from src.feature_flags.models import (
    FeatureFlag,
    FlagStatus,
    FlagType,
    RolloutConfig,
)
from src.feature_flags.flag_manager import FeatureFlagManager


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def manager():
    return FeatureFlagManager()


@pytest.fixture
def boolean_flag():
    return FeatureFlag(
        flag_id="mcp_enabled",
        name="MCP Plugin",
        description="Enable MCP plugin architecture.",
        flag_type=FlagType.BOOLEAN,
        status=FlagStatus.ACTIVE,
        default_enabled=True,
    )


@pytest.fixture
def percentage_flag():
    return FeatureFlag(
        flag_id="new_ui",
        name="New UI",
        flag_type=FlagType.PERCENTAGE,
        status=FlagStatus.ACTIVE,
        rollout=RolloutConfig(percentage=50.0),
    )


@pytest.fixture
def mrr_flag():
    return FeatureFlag(
        flag_id="premium_feature",
        name="Premium Feature",
        flag_type=FlagType.MRR_GATED,
        status=FlagStatus.ACTIVE,
        rollout=RolloutConfig(mrr_threshold_usd=1000.0),
    )


@pytest.fixture
def tenant_list_flag():
    return FeatureFlag(
        flag_id="beta_access",
        name="Beta Access",
        flag_type=FlagType.TENANT_LIST,
        status=FlagStatus.ACTIVE,
        rollout=RolloutConfig(allowed_tenants=["t1", "t2"]),
    )


# ---------------------------------------------------------------------------
# CRUD tests
# ---------------------------------------------------------------------------

class TestFlagCRUD:
    def test_create_and_get(self, manager, boolean_flag):
        manager.create_flag(boolean_flag)
        fetched = manager.get_flag("mcp_enabled")
        assert fetched.name == "MCP Plugin"

    def test_delete(self, manager, boolean_flag):
        manager.create_flag(boolean_flag)
        removed = manager.delete_flag("mcp_enabled")
        assert removed.flag_id == "mcp_enabled"
        assert manager.count() == 0

    def test_delete_not_found(self, manager):
        with pytest.raises(KeyError):
            manager.delete_flag("nonexistent")

    def test_list_flags(self, manager, boolean_flag, percentage_flag):
        manager.create_flag(boolean_flag)
        manager.create_flag(percentage_flag)
        flags = manager.list_flags()
        assert len(flags) == 2

    def test_list_by_status(self, manager, boolean_flag):
        manager.create_flag(boolean_flag)
        active = manager.list_flags(status=FlagStatus.ACTIVE)
        assert len(active) == 1
        draft = manager.list_flags(status=FlagStatus.DRAFT)
        assert len(draft) == 0

    def test_activate_and_pause(self, manager):
        flag = FeatureFlag(flag_id="test", name="Test", status=FlagStatus.DRAFT)
        manager.create_flag(flag)
        manager.activate_flag("test")
        assert manager.get_flag("test").status == FlagStatus.ACTIVE
        manager.pause_flag("test")
        assert manager.get_flag("test").status == FlagStatus.PAUSED


# ---------------------------------------------------------------------------
# Boolean evaluation tests
# ---------------------------------------------------------------------------

class TestBooleanEvaluation:
    def test_boolean_enabled(self, manager, boolean_flag):
        manager.create_flag(boolean_flag)
        assert manager.is_enabled("mcp_enabled", "any_tenant") is True

    def test_boolean_disabled(self, manager):
        flag = FeatureFlag(
            flag_id="off", name="Off", flag_type=FlagType.BOOLEAN,
            status=FlagStatus.ACTIVE, default_enabled=False,
        )
        manager.create_flag(flag)
        assert manager.is_enabled("off", "any_tenant") is False

    def test_inactive_flag_always_off(self, manager):
        flag = FeatureFlag(
            flag_id="draft", name="Draft", status=FlagStatus.DRAFT,
            default_enabled=True,
        )
        manager.create_flag(flag)
        assert manager.is_enabled("draft", "any_tenant") is False

    def test_missing_flag_uses_default(self, manager):
        assert manager.is_enabled("nonexistent", "t1", default=True) is True
        assert manager.is_enabled("nonexistent", "t1", default=False) is False


# ---------------------------------------------------------------------------
# Percentage rollout tests
# ---------------------------------------------------------------------------

class TestPercentageRollout:
    def test_percentage_deterministic(self, manager, percentage_flag):
        manager.create_flag(percentage_flag)
        # Same tenant/flag always gets the same result
        r1 = manager.is_enabled("new_ui", "tenant_x")
        r2 = manager.is_enabled("new_ui", "tenant_x")
        assert r1 == r2

    def test_percentage_100_always_on(self, manager):
        flag = FeatureFlag(
            flag_id="full", name="Full",
            flag_type=FlagType.PERCENTAGE,
            status=FlagStatus.ACTIVE,
            rollout=RolloutConfig(percentage=100.0),
        )
        manager.create_flag(flag)
        assert manager.is_enabled("full", "any_tenant") is True

    def test_percentage_0_always_off(self, manager):
        flag = FeatureFlag(
            flag_id="none", name="None",
            flag_type=FlagType.PERCENTAGE,
            status=FlagStatus.ACTIVE,
            rollout=RolloutConfig(percentage=0.0),
        )
        manager.create_flag(flag)
        assert manager.is_enabled("none", "any_tenant") is False


# ---------------------------------------------------------------------------
# MRR-gated tests
# ---------------------------------------------------------------------------

class TestMRRGated:
    def test_mrr_below_threshold(self, manager, mrr_flag):
        manager.create_flag(mrr_flag)
        manager.update_tenant_mrr("t1", 500.0)
        assert manager.is_enabled("premium_feature", "t1") is False

    def test_mrr_at_threshold(self, manager, mrr_flag):
        manager.create_flag(mrr_flag)
        manager.update_tenant_mrr("t1", 1000.0)
        assert manager.is_enabled("premium_feature", "t1") is True

    def test_mrr_above_threshold(self, manager, mrr_flag):
        manager.create_flag(mrr_flag)
        manager.update_tenant_mrr("t1", 2000.0)
        assert manager.is_enabled("premium_feature", "t1") is True

    def test_mrr_no_data(self, manager, mrr_flag):
        manager.create_flag(mrr_flag)
        assert manager.is_enabled("premium_feature", "t1") is False


# ---------------------------------------------------------------------------
# Tenant list tests
# ---------------------------------------------------------------------------

class TestTenantList:
    def test_tenant_in_list(self, manager, tenant_list_flag):
        manager.create_flag(tenant_list_flag)
        assert manager.is_enabled("beta_access", "t1") is True
        assert manager.is_enabled("beta_access", "t2") is True

    def test_tenant_not_in_list(self, manager, tenant_list_flag):
        manager.create_flag(tenant_list_flag)
        assert manager.is_enabled("beta_access", "t3") is False


# ---------------------------------------------------------------------------
# Override tests
# ---------------------------------------------------------------------------

class TestOverrides:
    def test_tenant_override_enables(self, manager, boolean_flag):
        boolean_flag.default_enabled = False
        manager.create_flag(boolean_flag)
        manager.set_tenant_override("mcp_enabled", "t1", True, "VIP customer")
        assert manager.is_enabled("mcp_enabled", "t1") is True
        assert manager.is_enabled("mcp_enabled", "t2") is False

    def test_tenant_override_disables(self, manager, boolean_flag):
        manager.create_flag(boolean_flag)
        manager.set_tenant_override("mcp_enabled", "t1", False, "billing issue")
        assert manager.is_enabled("mcp_enabled", "t1") is False
        assert manager.is_enabled("mcp_enabled", "t2") is True

    def test_remove_override(self, manager, boolean_flag):
        manager.create_flag(boolean_flag)
        manager.set_tenant_override("mcp_enabled", "t1", False)
        manager.remove_tenant_override("mcp_enabled", "t1")
        assert manager.is_enabled("mcp_enabled", "t1") is True

    def test_blocked_tenant(self, manager, boolean_flag):
        boolean_flag.rollout.blocked_tenants = ["t_blocked"]
        manager.create_flag(boolean_flag)
        assert manager.is_enabled("mcp_enabled", "t_blocked") is False

    def test_override_nonexistent_flag(self, manager):
        with pytest.raises(KeyError):
            manager.set_tenant_override("nonexistent", "t1", True)


# ---------------------------------------------------------------------------
# Introspection tests
# ---------------------------------------------------------------------------

class TestIntrospection:
    def test_count(self, manager, boolean_flag, percentage_flag):
        manager.create_flag(boolean_flag)
        manager.create_flag(percentage_flag)
        assert manager.count() == 2

    def test_evaluation_log(self, manager, boolean_flag):
        manager.create_flag(boolean_flag)
        manager.is_enabled("mcp_enabled", "t1")
        log = manager.get_evaluation_log()
        assert len(log) >= 1

    def test_status_summary(self, manager, boolean_flag, percentage_flag):
        manager.create_flag(boolean_flag)
        manager.create_flag(percentage_flag)
        summary = manager.get_status_summary()
        assert summary["total_flags"] == 2
        assert "status_distribution" in summary
        assert "type_distribution" in summary
