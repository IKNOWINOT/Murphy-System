# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Tests for org_build_plan.tenant_provisioner module."""
import os


import pytest
from src.org_build_plan.organization_intake import OrganizationIntakeProfile
from src.org_build_plan.tenant_provisioner import ProvisionResult, TenantProvisioner


def make_profile(**kwargs) -> OrganizationIntakeProfile:
    defaults = {
        "org_name": "Test Org",
        "industry": "manufacturing",
        "org_type": "corporation",
        "labor_model": "union",
        "company_size": "medium",
        "ip_protection_level": "standard",
    }
    defaults.update(kwargs)
    return OrganizationIntakeProfile(**defaults)


def test_provision_small_company():
    """Small company gets 256 MB / 10k API / 20 member limits."""
    p = TenantProvisioner()
    result = p.provision(make_profile(company_size="small"))
    assert result.resource_limits["max_storage_mb"] == 256
    assert result.resource_limits["max_api_calls"] == 10_000
    assert result.resource_limits["max_members"] == 20


def test_provision_medium_company():
    """Medium company gets 1024 MB / 100k API / 50 member limits."""
    p = TenantProvisioner()
    result = p.provision(make_profile(company_size="medium"))
    assert result.resource_limits["max_storage_mb"] == 1024
    assert result.resource_limits["max_api_calls"] == 100_000
    assert result.resource_limits["max_members"] == 50


def test_provision_enterprise_company():
    """Enterprise company gets 4096 MB / 500k API / 200 member limits."""
    p = TenantProvisioner()
    result = p.provision(make_profile(company_size="enterprise"))
    assert result.resource_limits["max_storage_mb"] == 4096
    assert result.resource_limits["max_api_calls"] == 500_000
    assert result.resource_limits["max_members"] == 200


def test_isolation_level_patent_pending():
    """patent_pending IP level → strict isolation."""
    p = TenantProvisioner()
    result = p.provision(make_profile(ip_protection_level="patent_pending"))
    assert result.isolation_level == "strict"


def test_isolation_level_trade_secret():
    """trade_secret IP level → strict isolation."""
    p = TenantProvisioner()
    result = p.provision(make_profile(ip_protection_level="trade_secret"))
    assert result.isolation_level == "strict"


def test_isolation_level_standard():
    """standard IP level → standard isolation."""
    p = TenantProvisioner()
    result = p.provision(make_profile(ip_protection_level="standard"))
    assert result.isolation_level == "standard"


def test_owner_member_added():
    """Provisioning adds an owner role to the workspace."""
    p = TenantProvisioner()
    result = p.provision(make_profile())
    assert result.owner_added is True


def test_get_tenant_after_provision():
    """get_tenant returns a config after provisioning."""
    p = TenantProvisioner()
    result = p.provision(make_profile())
    config = p.get_tenant(result.tenant_id)
    assert config is not None
    assert config.name == "Test Org"


def test_get_tenant_unknown_returns_none():
    """get_tenant returns None for an unknown tenant_id."""
    p = TenantProvisioner()
    assert p.get_tenant("does_not_exist") is None


def test_provision_result_has_tenant_id():
    """ProvisionResult must have a non-empty tenant_id."""
    p = TenantProvisioner()
    result = p.provision(make_profile())
    assert result.tenant_id
    assert len(result.tenant_id) > 0


def test_provision_with_franchise_model():
    """Provisioning with franchise_model=True includes it in custom_settings."""
    p = TenantProvisioner()
    result = p.provision(make_profile(franchise_model=True))
    assert result.workspace_config["custom_settings"]["franchise_model"] is True


def test_provision_with_budget_tracking():
    """Provisioning with budget_tracking=True includes it in custom_settings."""
    p = TenantProvisioner()
    result = p.provision(make_profile(budget_tracking=True))
    assert result.workspace_config["custom_settings"]["budget_tracking"] is True


def test_provision_result_to_dict():
    """to_dict returns a JSON-serialisable dict."""
    import json
    p = TenantProvisioner()
    result = p.provision(make_profile())
    d = result.to_dict()
    assert "tenant_id" in d
    json.dumps(d)
