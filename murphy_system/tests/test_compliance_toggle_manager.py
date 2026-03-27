"""
Tests for ComplianceToggleManager — Murphy System.

Covers:
  - Recommended framework detection for various country/industry combos
  - Saving and loading tenant frameworks
  - Compliance report generation
  - Framework ID validation (unknown IDs are rejected)
  - ALL_FRAMEWORKS list completeness
"""

import os


import pytest
from compliance_toggle_manager import (
    ComplianceToggleManager,
    ALL_FRAMEWORKS,
    COMPLIANCE_ENGINE_MAP,
    TenantFrameworkConfig,
    _COUNTRY_FRAMEWORKS,
    _INDUSTRY_FRAMEWORKS,
)


# ---------------------------------------------------------------------------
# Framework catalog completeness
# ---------------------------------------------------------------------------

class TestFrameworkCatalog:
    def test_all_frameworks_non_empty(self):
        assert len(ALL_FRAMEWORKS) > 30

    def test_core_gdpr_present(self):
        assert "gdpr" in ALL_FRAMEWORKS

    def test_core_hipaa_present(self):
        assert "hipaa" in ALL_FRAMEWORKS

    def test_core_soc2_present(self):
        assert "soc2" in ALL_FRAMEWORKS

    def test_core_pci_dss_present(self):
        assert "pci_dss" in ALL_FRAMEWORKS

    def test_no_duplicates_in_all_frameworks(self):
        assert len(ALL_FRAMEWORKS) == len(set(ALL_FRAMEWORKS))

    def test_compliance_engine_map_values_are_valid(self):
        """Engine map values must be recognisable by the compliance_engine if available."""
        valid_native = {"gdpr", "soc2", "hipaa", "pci_dss", "iso27001"}
        for fw_id, native_id in COMPLIANCE_ENGINE_MAP.items():
            assert native_id in valid_native, f"{fw_id} maps to unknown engine ID: {native_id}"


# ---------------------------------------------------------------------------
# get_recommended_frameworks()
# ---------------------------------------------------------------------------

class TestRecommendedFrameworks:
    def test_germany_includes_gdpr(self):
        mgr = ComplianceToggleManager()
        rec = mgr.get_recommended_frameworks("DE", "technology")
        assert "gdpr" in rec

    def test_germany_includes_dsgvo(self):
        mgr = ComplianceToggleManager()
        rec = mgr.get_recommended_frameworks("DE", "general")
        assert "dsgvo" in rec

    def test_us_healthcare_includes_hipaa(self):
        mgr = ComplianceToggleManager()
        rec = mgr.get_recommended_frameworks("US", "healthcare")
        assert "hipaa" in rec

    def test_us_finance_includes_pci_and_sox(self):
        mgr = ComplianceToggleManager()
        rec = mgr.get_recommended_frameworks("US", "finance")
        assert "pci_dss" in rec
        assert "sox" in rec

    def test_california_includes_ccpa(self):
        mgr = ComplianceToggleManager()
        rec = mgr.get_recommended_frameworks("US-CA", "retail")
        assert "ccpa" in rec

    def test_brazil_includes_lgpd(self):
        mgr = ComplianceToggleManager()
        rec = mgr.get_recommended_frameworks("BR", "technology")
        assert "lgpd" in rec

    def test_canada_includes_pipeda(self):
        mgr = ComplianceToggleManager()
        rec = mgr.get_recommended_frameworks("CA", "hr")
        assert "pipeda" in rec

    def test_australia_includes_privacy_act(self):
        mgr = ComplianceToggleManager()
        rec = mgr.get_recommended_frameworks("AU", "general")
        assert "privacy_act_au" in rec

    def test_singapore_includes_pdpa(self):
        mgr = ComplianceToggleManager()
        rec = mgr.get_recommended_frameworks("SG", "technology")
        assert "pdpa" in rec

    def test_government_industry_includes_fedramp(self):
        mgr = ComplianceToggleManager()
        rec = mgr.get_recommended_frameworks("US", "government")
        assert "fedramp" in rec

    def test_defense_industry_includes_cmmc(self):
        mgr = ComplianceToggleManager()
        rec = mgr.get_recommended_frameworks("US", "defense")
        assert "cmmc" in rec

    def test_education_includes_ferpa(self):
        mgr = ComplianceToggleManager()
        rec = mgr.get_recommended_frameworks("US", "education")
        assert "ferpa" in rec

    def test_banking_includes_mifid_ii(self):
        mgr = ComplianceToggleManager()
        rec = mgr.get_recommended_frameworks("DE", "banking")
        assert "mifid_ii" in rec

    def test_unknown_country_returns_industry_frameworks(self):
        mgr = ComplianceToggleManager()
        rec = mgr.get_recommended_frameworks("XX", "healthcare")
        assert "hipaa" in rec

    def test_unknown_industry_uses_general_fallback(self):
        mgr = ComplianceToggleManager()
        rec = mgr.get_recommended_frameworks("US", "unknown_industry_xyz")
        assert "soc2" in rec  # general fallback always includes soc2

    def test_no_duplicates_in_recommendations(self):
        mgr = ComplianceToggleManager()
        rec = mgr.get_recommended_frameworks("DE", "finance")
        assert len(rec) == len(set(rec))

    def test_all_returned_ids_are_valid(self):
        mgr = ComplianceToggleManager()
        for country in ["US", "GB", "DE", "BR", "JP", "AU"]:
            for industry in ["finance", "healthcare", "technology", "general"]:
                rec = mgr.get_recommended_frameworks(country, industry)
                for fw_id in rec:
                    assert fw_id in ALL_FRAMEWORKS, f"Invalid framework ID {fw_id} for {country}/{industry}"

    def test_country_codes_case_insensitive(self):
        mgr = ComplianceToggleManager()
        upper = mgr.get_recommended_frameworks("DE", "technology")
        lower = mgr.get_recommended_frameworks("de", "technology")
        assert upper == lower


# ---------------------------------------------------------------------------
# save_tenant_frameworks() / get_tenant_frameworks()
# ---------------------------------------------------------------------------

class TestSaveTenantFrameworks:
    def test_save_and_load(self):
        mgr = ComplianceToggleManager()
        mgr.save_tenant_frameworks("tenant-1", ["gdpr", "soc2", "hipaa"])
        loaded = mgr.get_tenant_frameworks("tenant-1")
        assert set(loaded) == {"gdpr", "soc2", "hipaa"}

    def test_unknown_framework_ids_filtered(self):
        mgr = ComplianceToggleManager()
        mgr.save_tenant_frameworks("tenant-2", ["gdpr", "totally_fake_framework"])
        loaded = mgr.get_tenant_frameworks("tenant-2")
        assert "totally_fake_framework" not in loaded
        assert "gdpr" in loaded

    def test_empty_list_saves_empty(self):
        mgr = ComplianceToggleManager()
        mgr.save_tenant_frameworks("tenant-3", [])
        loaded = mgr.get_tenant_frameworks("tenant-3")
        assert loaded == []

    def test_unknown_tenant_returns_empty(self):
        mgr = ComplianceToggleManager()
        assert mgr.get_tenant_frameworks("never-seen") == []

    def test_overwrite_previous_selection(self):
        mgr = ComplianceToggleManager()
        mgr.save_tenant_frameworks("tenant-4", ["gdpr", "soc2"])
        mgr.save_tenant_frameworks("tenant-4", ["hipaa", "pci_dss"])
        loaded = mgr.get_tenant_frameworks("tenant-4")
        assert "hipaa" in loaded
        assert "pci_dss" in loaded
        assert "gdpr" not in loaded

    def test_returns_tenant_config_object(self):
        mgr = ComplianceToggleManager()
        cfg = mgr.save_tenant_frameworks("tenant-5", ["gdpr"], updated_by="admin@example.com")
        assert isinstance(cfg, TenantFrameworkConfig)
        assert cfg.tenant_id == "tenant-5"
        assert cfg.updated_by == "admin@example.com"

    def test_full_framework_list_accepted(self):
        """All known framework IDs should be saveable without filtering."""
        mgr = ComplianceToggleManager()
        cfg = mgr.save_tenant_frameworks("tenant-full", ALL_FRAMEWORKS)
        loaded = mgr.get_tenant_frameworks("tenant-full")
        assert len(loaded) == len(ALL_FRAMEWORKS)


# ---------------------------------------------------------------------------
# get_tenant_config()
# ---------------------------------------------------------------------------

class TestGetTenantConfig:
    def test_returns_none_for_unknown(self):
        mgr = ComplianceToggleManager()
        assert mgr.get_tenant_config("not-set") is None

    def test_returns_config_after_save(self):
        mgr = ComplianceToggleManager()
        mgr.save_tenant_frameworks("cfg-tenant", ["gdpr"])
        cfg = mgr.get_tenant_config("cfg-tenant")
        assert cfg is not None
        assert cfg.tenant_id == "cfg-tenant"
        assert "gdpr" in cfg.enabled_frameworks


# ---------------------------------------------------------------------------
# generate_compliance_report()
# ---------------------------------------------------------------------------

class TestGenerateComplianceReport:
    def test_report_structure(self):
        mgr = ComplianceToggleManager()
        mgr.save_tenant_frameworks("report-tenant", ["gdpr", "soc2"])
        report = mgr.generate_compliance_report("report-tenant")
        assert "tenant_id" in report
        assert "enabled_count" in report
        assert "enabled_frameworks" in report
        assert "framework_statuses" in report
        assert "generated_at" in report

    def test_report_enabled_count(self):
        mgr = ComplianceToggleManager()
        mgr.save_tenant_frameworks("report-t2", ["gdpr", "hipaa", "pci_dss"])
        report = mgr.generate_compliance_report("report-t2")
        assert report["enabled_count"] == 3

    def test_all_enabled_frameworks_in_statuses(self):
        mgr = ComplianceToggleManager()
        frameworks = ["gdpr", "soc2"]
        mgr.save_tenant_frameworks("report-t3", frameworks)
        report = mgr.generate_compliance_report("report-t3")
        for fw in frameworks:
            assert fw in report["framework_statuses"]

    def test_each_status_has_configured_flag(self):
        mgr = ComplianceToggleManager()
        mgr.save_tenant_frameworks("report-t4", ["gdpr"])
        report = mgr.generate_compliance_report("report-t4")
        assert report["framework_statuses"]["gdpr"]["configured"] is True

    def test_empty_tenant_report(self):
        mgr = ComplianceToggleManager()
        mgr.save_tenant_frameworks("report-empty", [])
        report = mgr.generate_compliance_report("report-empty")
        assert report["enabled_count"] == 0
        assert report["framework_statuses"] == {}

    def test_report_tenant_id_matches(self):
        mgr = ComplianceToggleManager()
        mgr.save_tenant_frameworks("rpt-id", ["hipaa"])
        report = mgr.generate_compliance_report("rpt-id")
        assert report["tenant_id"] == "rpt-id"


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------

class TestAuditLog:
    def test_save_action_appears_in_audit_log(self):
        mgr = ComplianceToggleManager()
        mgr.save_tenant_frameworks("audit-t", ["gdpr"])
        log = mgr.get_audit_log()
        assert any(e["action"] == "save_frameworks" for e in log)

    def test_audit_log_contains_tenant_id(self):
        mgr = ComplianceToggleManager()
        mgr.save_tenant_frameworks("audit-tid", ["soc2"])
        log = mgr.get_audit_log()
        assert any(e.get("tenant_id") == "audit-tid" for e in log)
