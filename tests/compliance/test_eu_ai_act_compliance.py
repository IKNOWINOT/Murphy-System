"""
Tests for EU AI Act Compliance Module (EUAIA-001)

Validates:
- Nine core requirement tracking
- Risk classification (Annex III mapping)
- System card generation (Article 13)
- Human oversight hooks (Article 14)
- Cryptographic audit chain (Articles 12/15)
- Compliance summary

Copyright © 2020 Inoni Limited Liability Company
License: BSL 1.1
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

_ROOT = Path(__file__).resolve().parent.parent.parent
for _p in (_ROOT, _ROOT / "src"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from src.eu_ai_act_compliance import (
    AuditSeverity,
    ComplianceStatus,
    EUAIActComplianceEngine,
    RiskLevel,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def engine():
    return EUAIActComplianceEngine()


# ---------------------------------------------------------------------------
# Requirement tracking
# ---------------------------------------------------------------------------


class TestRequirementTracking:
    """Test the nine core EU AI Act requirements."""

    def test_nine_requirements_initialized(self, engine):
        assert len(engine.requirements) == 9

    def test_all_start_non_compliant(self, engine):
        for req in engine.requirements.values():
            assert req.status == ComplianceStatus.NON_COMPLIANT

    def test_requirement_ids_are_euaia_prefixed(self, engine):
        for rid in engine.requirements:
            assert rid.startswith("EUAIA-R")

    def test_update_requirement_to_compliant(self, engine):
        req = engine.update_requirement(
            "EUAIA-R1",
            ComplianceStatus.COMPLIANT,
            evidence=["risk_management_system.py deployed"],
        )
        assert req is not None
        assert req.status == ComplianceStatus.COMPLIANT
        assert "risk_management_system.py deployed" in req.evidence

    def test_update_unknown_requirement_returns_none(self, engine):
        result = engine.update_requirement("BOGUS-001", ComplianceStatus.COMPLIANT)
        assert result is None

    def test_compliance_summary_structure(self, engine):
        summary = engine.get_compliance_summary()
        assert summary["total_requirements"] == 9
        assert summary["non_compliant"] == 9
        assert summary["compliance_score"] == 0.0
        assert "requirements" in summary

    def test_partial_compliance_score(self, engine):
        engine.update_requirement("EUAIA-R1", ComplianceStatus.COMPLIANT)
        engine.update_requirement("EUAIA-R2", ComplianceStatus.PARTIAL)
        summary = engine.get_compliance_summary()
        # 1 compliant + 0.5 partial = 1.5 / 9 ≈ 0.17
        assert summary["compliant"] == 1
        assert summary["partial"] == 1
        assert 0.15 <= summary["compliance_score"] <= 0.20


# ---------------------------------------------------------------------------
# Risk classification
# ---------------------------------------------------------------------------


class TestRiskClassification:
    """Test Annex III risk classification engine."""

    def test_classify_minimal_risk(self, engine):
        ra = engine.classify_risk("ChatBot", intended_use="customer FAQ")
        assert ra.risk_level == RiskLevel.LIMITED

    def test_classify_high_risk_safety_critical(self, engine):
        ra = engine.classify_risk("RobotController", is_safety_critical=True)
        assert ra.risk_level == RiskLevel.HIGH
        assert ra.annex_iii_category == "critical_infrastructure"

    def test_classify_high_risk_employment(self, engine):
        ra = engine.classify_risk("HRScreener", affects_employment=True)
        assert ra.risk_level == RiskLevel.HIGH
        assert ra.annex_iii_category == "employment_hr"

    def test_classify_unacceptable_biometric_law_enforcement(self, engine):
        ra = engine.classify_risk(
            "FaceScanner",
            has_biometric=True,
            used_by_law_enforcement=True,
        )
        assert ra.risk_level == RiskLevel.UNACCEPTABLE

    def test_classify_explicit_annex_iii_category(self, engine):
        ra = engine.classify_risk(
            "MigrationAssistant",
            annex_iii_category="migration_asylum",
        )
        assert ra.risk_level == RiskLevel.HIGH
        assert ra.annex_iii_category == "migration_asylum"

    def test_assessment_stored(self, engine):
        ra = engine.classify_risk("TestSystem")
        assert ra.assessment_id in engine.risk_assessments


# ---------------------------------------------------------------------------
# Audit findings
# ---------------------------------------------------------------------------


class TestAuditFindings:
    """Test compliance audit finding management."""

    def test_add_finding(self, engine):
        f = engine.add_finding(
            "EUAIA-R4",
            AuditSeverity.HIGH,
            "Logging disabled for model inference",
            remediation="Enable audit logging in model_runner.py",
        )
        assert f.finding_id
        assert f.status == "open"
        assert f.severity == AuditSeverity.HIGH

    def test_resolve_finding(self, engine):
        f = engine.add_finding("EUAIA-R1", AuditSeverity.MEDIUM, "Missing docs")
        assert engine.resolve_finding(f.finding_id) is True
        resolved = [x for x in engine.findings if x.finding_id == f.finding_id]
        assert resolved[0].status == "resolved"

    def test_resolve_nonexistent_returns_false(self, engine):
        assert engine.resolve_finding("no-such-id") is False


# ---------------------------------------------------------------------------
# System card generation (Article 13)
# ---------------------------------------------------------------------------


class TestSystemCard:
    """Test AI transparency system card generation."""

    def test_generate_card(self, engine):
        card = engine.generate_system_card(
            system_name="Murphy AI",
            version="1.0",
            purpose="Business automation",
            intended_use="Internal workflow orchestration",
            limitations="Does not handle PII",
            human_oversight_measures="HITL gates on all executions",
        )
        assert card.card_id
        assert card.system_name == "Murphy AI"
        assert card.risk_level == RiskLevel.LIMITED  # no assessment yet

    def test_card_uses_risk_from_assessment(self, engine):
        engine.classify_risk("MurphyHR", affects_employment=True)
        card = engine.generate_system_card(system_name="MurphyHR")
        assert card.risk_level == RiskLevel.HIGH


# ---------------------------------------------------------------------------
# Human oversight (Article 14)
# ---------------------------------------------------------------------------


class TestHumanOversight:
    """Test HITL governance integration hooks."""

    def test_no_oversight_needed_for_low_risk(self, engine):
        result = engine.check_human_oversight("decision-001")
        assert result["requires_human_oversight"] is False

    def test_oversight_needed_for_high_risk(self, engine):
        engine.classify_risk("CriticalBot", is_safety_critical=True)
        result = engine.check_human_oversight("decision-002")
        assert result["requires_human_oversight"] is True
        assert "CriticalBot" in result["high_risk_systems"]


# ---------------------------------------------------------------------------
# Audit log / hash chain (Articles 12/15)
# ---------------------------------------------------------------------------


class TestAuditLog:
    """Test cryptographic audit log integrity."""

    def test_audit_log_populated_after_actions(self, engine):
        engine.classify_risk("TestBot")
        engine.update_requirement("EUAIA-R1", ComplianceStatus.COMPLIANT)
        log = engine.get_audit_log()
        assert len(log) >= 2

    def test_audit_chain_integrity(self, engine):
        engine.classify_risk("Bot1")
        engine.classify_risk("Bot2")
        engine.add_finding("EUAIA-R1", AuditSeverity.LOW, "test")
        assert engine.verify_audit_chain() is True

    def test_filter_audit_by_event_type(self, engine):
        engine.classify_risk("FilterBot")
        engine.update_requirement("EUAIA-R1", ComplianceStatus.PARTIAL)
        classified = engine.get_audit_log(event_type="risk_classified")
        updated = engine.get_audit_log(event_type="requirement_updated")
        assert len(classified) >= 1
        assert len(updated) >= 1


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------


class TestSerialization:
    """Test to_dict output."""

    def test_to_dict_structure(self, engine):
        engine.classify_risk("DictBot")
        engine.update_requirement("EUAIA-R1", ComplianceStatus.COMPLIANT)
        data = engine.to_dict()
        assert "requirements" in data
        assert "risk_assessments" in data
        assert "findings" in data
        assert "system_cards" in data
        assert "summary" in data
