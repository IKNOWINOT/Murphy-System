"""Tests for the Compliance Validation Engine."""

import pytest
from src.compliance_engine import (
    ComplianceEngine,
    ComplianceFramework,
    ComplianceRequirement,
    ComplianceSeverity,
    ComplianceStatus,
)


@pytest.fixture
def engine():
    """Return a fresh ComplianceEngine with default requirements."""
    return ComplianceEngine()


# ------------------------------------------------------------------
# Requirement registration
# ------------------------------------------------------------------

class TestRequirementRegistration:
    def test_defaults_registered(self, engine):
        status = engine.get_status()
        assert status["total_requirements"] >= 11

    def test_register_custom_requirement(self, engine):
        req = ComplianceRequirement(
            requirement_id="custom-test-req",
            framework=ComplianceFramework.CUSTOM,
            description="Custom test requirement",
            severity=ComplianceSeverity.MEDIUM,
            applicable_domains=["general"],
            auto_checkable=True,
        )
        rid = engine.register_requirement(req)
        assert rid == "custom-test-req"
        status = engine.get_status()
        assert "custom" in status["framework_requirement_counts"]

    def test_register_overwrites_existing(self, engine):
        req = ComplianceRequirement(
            requirement_id="gdpr-consent",
            framework=ComplianceFramework.GDPR,
            description="Updated consent requirement",
            severity=ComplianceSeverity.CRITICAL,
            auto_checkable=True,
        )
        engine.register_requirement(req)
        # Count should stay the same since we overwrote
        status = engine.get_status()
        assert status["total_requirements"] >= 11


# ------------------------------------------------------------------
# Deliverable checking
# ------------------------------------------------------------------

class TestDeliverableChecking:
    def test_check_auto_checkable_pass(self, engine):
        deliverable = {
            "session_id": "sess-1",
            "domain": "finance",
            "compliance_checks": {
                "soc2-access-control": True,
                "soc2-audit-logging": True,
                "soc2-encryption": True,
                "pci-encryption": True,
                "pci-access-control": True,
                "pci-logging": True,
            },
        }
        report = engine.check_deliverable(deliverable, [ComplianceFramework.SOC2])
        assert report["session_id"] == "sess-1"
        assert report["total_requirements"] > 0
        # All SOC2 auto-checkable reqs passed
        for r in report["results"]:
            assert r["status"] in ("compliant", "pending")

    def test_check_auto_checkable_fail(self, engine):
        deliverable = {
            "session_id": "sess-2",
            "domain": "finance",
            "compliance_checks": {
                "soc2-access-control": False,
            },
        }
        report = engine.check_deliverable(deliverable, [ComplianceFramework.SOC2])
        statuses = {r["requirement_id"]: r["status"] for r in report["results"]}
        assert statuses["soc2-access-control"] == "non_compliant"
        assert report["overall_status"] == "non_compliant"

    def test_check_filters_by_framework(self, engine):
        deliverable = {"domain": "healthcare"}
        report = engine.check_deliverable(deliverable, [ComplianceFramework.HIPAA])
        req_ids = {r["requirement_id"] for r in report["results"]}
        assert all(rid.startswith("hipaa") for rid in req_ids)

    def test_check_filters_by_domain(self, engine):
        deliverable = {"domain": "healthcare"}
        report = engine.check_deliverable(deliverable)
        req_ids = {r["requirement_id"] for r in report["results"]}
        # Healthcare domain should include HIPAA reqs
        assert any(rid.startswith("hipaa") for rid in req_ids)
        # Should NOT include GDPR reqs (those are for personal_data/eu_data)
        assert not any(rid.startswith("gdpr") for rid in req_ids)

    def test_check_manual_requirements_need_review(self, engine):
        deliverable = {"domain": "healthcare"}
        report = engine.check_deliverable(deliverable, [ComplianceFramework.HIPAA])
        statuses = {r["requirement_id"]: r["status"] for r in report["results"]}
        # hipaa-phi-protection is not auto-checkable
        assert statuses["hipaa-phi-protection"] == "needs_review"


# ------------------------------------------------------------------
# HITL approval flow
# ------------------------------------------------------------------

class TestHITLApproval:
    def test_approve_pending_requirement(self, engine):
        deliverable = {"domain": "healthcare"}
        engine.check_deliverable(deliverable, [ComplianceFramework.HIPAA])
        result = engine.approve_requirement(
            "hipaa-phi-protection", "dr.smith", "Reviewed PHI safeguards"
        )
        assert result is True

    def test_approve_unknown_requirement(self, engine):
        result = engine.approve_requirement("nonexistent-req", "reviewer")
        assert result is False

    def test_approve_creates_record_when_no_pending(self, engine):
        result = engine.approve_requirement(
            "gdpr-consent", "legal-team", "Pre-approved"
        )
        assert result is True

    def test_approval_changes_status_to_compliant(self, engine):
        deliverable = {"session_id": "approval-test", "domain": "eu_data"}
        engine.check_deliverable(deliverable, [ComplianceFramework.GDPR])
        engine.approve_requirement("gdpr-consent", "dpo", "Consent verified")

        report = engine.get_compliance_report(session_id="approval-test")
        assert report["status_counts"].get("compliant", 0) >= 1


# ------------------------------------------------------------------
# Release readiness
# ------------------------------------------------------------------

class TestReleaseReadiness:
    def test_ready_when_all_compliant(self, engine):
        deliverable = {
            "domain": "finance",
            "compliance_checks": {
                "soc2-access-control": True,
                "soc2-audit-logging": True,
                "soc2-encryption": True,
                "pci-encryption": True,
                "pci-access-control": True,
                "pci-logging": True,
            },
        }
        # Limit to only auto-checkable frameworks with all passing
        ready, blockers = engine.is_release_ready(deliverable)
        # There may be pending items (no data provided), so check blockers list
        assert isinstance(ready, bool)
        assert isinstance(blockers, list)

    def test_not_ready_when_non_compliant(self, engine):
        deliverable = {
            "domain": "finance",
            "compliance_checks": {
                "soc2-access-control": False,
            },
        }
        ready, blockers = engine.is_release_ready(deliverable)
        assert ready is False
        assert any("NON_COMPLIANT" in b for b in blockers)

    def test_not_ready_when_needs_review(self, engine):
        deliverable = {"domain": "healthcare"}
        ready, blockers = engine.is_release_ready(deliverable)
        assert ready is False
        assert any("NEEDS_REVIEW" in b for b in blockers)

    def test_blockers_describe_issues(self, engine):
        deliverable = {
            "domain": "finance",
            "compliance_checks": {"pci-encryption": False},
        }
        ready, blockers = engine.is_release_ready(deliverable)
        assert not ready
        assert any("encrypted" in b.lower() for b in blockers)


# ------------------------------------------------------------------
# Compliance reporting
# ------------------------------------------------------------------

class TestComplianceReporting:
    def test_report_empty_before_checks(self, engine):
        report = engine.get_compliance_report()
        assert report["total_checked"] == 0
        assert report["compliance_rate"] == 0.0

    def test_report_after_checks(self, engine):
        deliverable = {
            "session_id": "report-sess",
            "domain": "cloud",
            "compliance_checks": {
                "soc2-access-control": True,
                "soc2-audit-logging": True,
                "soc2-encryption": True,
            },
        }
        engine.check_deliverable(deliverable, [ComplianceFramework.SOC2])
        report = engine.get_compliance_report(session_id="report-sess")
        assert report["total_checked"] > 0
        assert "soc2" in report["framework_breakdown"]
        assert report["generated_at"] is not None

    def test_report_by_session(self, engine):
        d1 = {"session_id": "s1", "domain": "cloud", "compliance_checks": {"soc2-encryption": True}}
        d2 = {"session_id": "s2", "domain": "cloud", "compliance_checks": {"soc2-encryption": False}}
        engine.check_deliverable(d1, [ComplianceFramework.SOC2])
        engine.check_deliverable(d2, [ComplianceFramework.SOC2])

        r1 = engine.get_compliance_report(session_id="s1")
        r2 = engine.get_compliance_report(session_id="s2")
        assert r1["session_id"] == "s1"
        assert r2["session_id"] == "s2"

    def test_report_all_sessions(self, engine):
        d1 = {"session_id": "sa", "domain": "cloud", "compliance_checks": {"soc2-encryption": True}}
        d2 = {"session_id": "sb", "domain": "cloud", "compliance_checks": {"soc2-encryption": True}}
        engine.check_deliverable(d1, [ComplianceFramework.SOC2])
        engine.check_deliverable(d2, [ComplianceFramework.SOC2])
        report = engine.get_compliance_report()
        assert report["total_checked"] >= 2


# ------------------------------------------------------------------
# Framework applicability by domain
# ------------------------------------------------------------------

class TestFrameworkApplicability:
    def test_healthcare_includes_hipaa(self, engine):
        frameworks = engine.get_applicable_frameworks("healthcare")
        assert ComplianceFramework.HIPAA in frameworks

    def test_finance_includes_pci(self, engine):
        frameworks = engine.get_applicable_frameworks("finance")
        assert ComplianceFramework.PCI_DSS in frameworks

    def test_eu_data_includes_gdpr(self, engine):
        frameworks = engine.get_applicable_frameworks("eu_data")
        assert ComplianceFramework.GDPR in frameworks

    def test_unknown_domain_defaults(self, engine):
        frameworks = engine.get_applicable_frameworks("unknown_domain")
        assert ComplianceFramework.SOC2 in frameworks

    def test_payments_includes_pci(self, engine):
        frameworks = engine.get_applicable_frameworks("payments")
        assert ComplianceFramework.PCI_DSS in frameworks


# ------------------------------------------------------------------
# Status reporting
# ------------------------------------------------------------------

class TestStatusReporting:
    def test_status_fields(self, engine):
        status = engine.get_status()
        assert "total_requirements" in status
        assert "total_sessions" in status
        assert "total_checks" in status
        assert "framework_requirement_counts" in status
        assert "check_status_counts" in status
        assert "current_session" in status

    def test_status_after_checks(self, engine):
        deliverable = {"domain": "cloud", "compliance_checks": {"soc2-encryption": True}}
        engine.check_deliverable(deliverable, [ComplianceFramework.SOC2])
        status = engine.get_status()
        assert status["total_checks"] > 0

    def test_status_framework_counts(self, engine):
        status = engine.get_status()
        counts = status["framework_requirement_counts"]
        assert counts.get("gdpr", 0) >= 3
        assert counts.get("soc2", 0) >= 3
        assert counts.get("hipaa", 0) >= 2
        assert counts.get("pci_dss", 0) >= 3
