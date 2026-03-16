# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Tests for org_build_plan.compliance_profiler module."""
import os


import pytest
from src.org_build_plan.organization_intake import OrganizationIntakeProfile
from src.org_build_plan.compliance_profiler import (
    ComplianceProfileResult,
    ComplianceProfiler,
    FRAMEWORK_MAP,
)


def make_profile(frameworks=None) -> OrganizationIntakeProfile:
    return OrganizationIntakeProfile(
        org_name="Compliance Test",
        industry="manufacturing",
        regulatory_frameworks=frameworks or [],
    )


def test_hipaa_security_hardened():
    """HIPAA framework activates hardened security."""
    profiler = ComplianceProfiler()
    result = profiler.profile(make_profile(["HIPAA"]))
    assert result.security_level == "hardened"


def test_hipaa_audit_quarterly():
    """HIPAA requires quarterly audit."""
    profiler = ComplianceProfiler()
    result = profiler.profile(make_profile(["HIPAA"]))
    assert result.audit_frequency == "quarterly"


def test_soc2_audit_annual():
    """SOC2 alone requires annual audit."""
    profiler = ComplianceProfiler()
    result = profiler.profile(make_profile(["SOC2"]))
    assert result.audit_frequency == "annual"


def test_gdpr_data_residency():
    """GDPR framework triggers data_residency_required=True."""
    profiler = ComplianceProfiler()
    result = profiler.profile(make_profile(["GDPR"]))
    assert result.data_residency_required is True


def test_no_gdpr_no_data_residency():
    """Without GDPR, data_residency_required stays False."""
    profiler = ComplianceProfiler()
    result = profiler.profile(make_profile(["OSHA", "SOC2"]))
    assert result.data_residency_required is False


def test_multiple_frameworks_combined():
    """Most restrictive security/audit wins across multiple frameworks."""
    profiler = ComplianceProfiler()
    # OSHA=standard/annual, PCI_DSS=hardened/quarterly
    result = profiler.profile(make_profile(["OSHA", "PCI_DSS"]))
    assert result.security_level == "hardened"
    assert result.audit_frequency == "quarterly"


def test_no_frameworks_returns_defaults():
    """Empty frameworks list returns standard security, annual audit."""
    profiler = ComplianceProfiler()
    result = profiler.profile(make_profile([]))
    assert result.security_level == "standard"
    assert result.audit_frequency == "annual"
    assert result.frameworks_activated == []


def test_all_frameworks_mapped():
    """Every key in FRAMEWORK_MAP is correctly processed."""
    profiler = ComplianceProfiler()
    for fw in FRAMEWORK_MAP.keys():
        result = profiler.profile(make_profile([fw]))
        assert fw in result.frameworks_activated


def test_nerc_hardened_quarterly():
    """NERC requires hardened security and quarterly audit."""
    profiler = ComplianceProfiler()
    result = profiler.profile(make_profile(["NERC"]))
    assert result.security_level == "hardened"
    assert result.audit_frequency == "quarterly"


def test_iso27001_hardened():
    """ISO27001 requires hardened security."""
    profiler = ComplianceProfiler()
    result = profiler.profile(make_profile(["ISO27001"]))
    assert result.security_level == "hardened"


def test_compliance_modules_populated():
    """Activated frameworks populate compliance_modules list."""
    profiler = ComplianceProfiler()
    result = profiler.profile(make_profile(["HIPAA", "SOC2"]))
    assert "compliance_engine" in result.compliance_modules
    # HIPAA and SOC2 together should include compliance_region_validator and contractual_audit
    assert len(result.compliance_modules) >= 2


def test_result_to_dict():
    """ComplianceProfileResult.to_dict is JSON-serialisable."""
    import json
    profiler = ComplianceProfiler()
    result = profiler.profile(make_profile(["SOC2", "GDPR"]))
    d = result.to_dict()
    assert "frameworks_activated" in d
    json.dumps(d)
