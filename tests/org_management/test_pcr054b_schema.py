"""PCR-054b — schema additions regression suite.

Verifies:
  1. RoleClass enum has exactly 3 values
  2. RoleTemplate.role_class defaults to OPERATION (backcompat)
  3. role_class participates in integrity hash
  4. LicensedPractitioner currency check
  5. LicensedPractitioner scope check across all 5 license types
"""
import pytest
from datetime import datetime, timedelta, timezone

from src.org_compiler.schemas import (
    AuthorityLevel,
    LicensedPractitioner,
    RoleClass,
    RoleMetrics,
    RoleTemplate,
)


# ──────────────────────────────────────────────────────────────
# RoleClass enum
# ──────────────────────────────────────────────────────────────


class TestRoleClassEnum:
    def test_three_values(self):
        assert {c.value for c in RoleClass} == {"operation", "creation", "hybrid"}

    def test_default_string_roundtrip(self):
        assert RoleClass("operation") is RoleClass.OPERATION
        assert RoleClass("creation") is RoleClass.CREATION
        assert RoleClass("hybrid") is RoleClass.HYBRID


# ──────────────────────────────────────────────────────────────
# RoleTemplate.role_class
# ──────────────────────────────────────────────────────────────


def _make_minimal_role(**overrides):
    """Build a RoleTemplate with minimum required fields for tests."""
    defaults = {
        "role_id": "test_role",
        "role_name": "Test Role",
        "responsibilities": ["do stuff"],
        "decision_authority": AuthorityLevel.LOW,
        "input_artifacts": [],
        "output_artifacts": [],
        "escalation_paths": [],
        "compliance_constraints": [],
        "requires_human_signoff": [],
        "metrics": RoleMetrics(
            sla_targets={},
            quality_gates=[],
        ),
    }
    defaults.update(overrides)
    return RoleTemplate(**defaults)


class TestRoleClassOnTemplate:
    def test_defaults_to_operation(self):
        r = _make_minimal_role()
        assert r.role_class is RoleClass.OPERATION

    def test_can_set_creation(self):
        r = _make_minimal_role(role_class=RoleClass.CREATION)
        assert r.role_class is RoleClass.CREATION

    def test_can_set_hybrid(self):
        r = _make_minimal_role(role_class=RoleClass.HYBRID)
        assert r.role_class is RoleClass.HYBRID

    def test_role_class_participates_in_integrity_hash(self):
        r_op = _make_minimal_role(role_class=RoleClass.OPERATION)
        r_cr = _make_minimal_role(role_class=RoleClass.CREATION)
        assert r_op.integrity_hash != r_cr.integrity_hash, (
            "role_class must be part of the integrity hash so a CREATION role "
            "cannot silently degrade to OPERATION"
        )

    def test_default_role_preserves_pcr053_hash_shape(self):
        # The hash function must still include all PCR-053b fields.
        r = _make_minimal_role(
            decision_ceiling_usd=50000,
            distinct_operators_required=3,
            primary_jurisdiction="US-CA",
        )
        assert r.verify_integrity()


# ──────────────────────────────────────────────────────────────
# LicensedPractitioner
# ──────────────────────────────────────────────────────────────


def _make_practitioner(**overrides):
    defaults = {
        "practitioner_id": "p1",
        "full_name": "Jane Doe",
        "license_type": "CPA",
        "license_number": "12345",
        "license_jurisdiction": "US-CA",
        "license_status": "active",
        "last_verified_at": datetime.now(timezone.utc),
    }
    defaults.update(overrides)
    return LicensedPractitioner(**defaults)


class TestLicensedPractitionerCurrency:
    def test_active_recent_is_current(self):
        p = _make_practitioner()
        assert p.is_current()

    def test_inactive_status_not_current(self):
        p = _make_practitioner(license_status="suspended")
        assert not p.is_current()

    def test_expired_not_current(self):
        p = _make_practitioner(
            expires_at=datetime.now(timezone.utc) - timedelta(days=1)
        )
        assert not p.is_current()

    def test_never_verified_not_current(self):
        p = _make_practitioner(last_verified_at=None)
        assert not p.is_current()

    def test_verified_too_long_ago_not_current(self):
        p = _make_practitioner(
            last_verified_at=datetime.now(timezone.utc) - timedelta(days=45)
        )
        assert not p.is_current(max_age_days=30)

    def test_custom_max_age_allows_older(self):
        p = _make_practitioner(
            last_verified_at=datetime.now(timezone.utc) - timedelta(days=45)
        )
        assert p.is_current(max_age_days=60)


class TestLicensedPractitionerScope:
    def test_cpa_covers_tax_return(self):
        p = _make_practitioner(license_type="CPA")
        assert p.covers("tax_return")
        assert p.covers("audited_financials")

    def test_cpa_does_not_cover_court_filing(self):
        p = _make_practitioner(license_type="CPA")
        assert not p.covers("court_filing")

    def test_attorney_covers_court_filing_not_tax_return(self):
        p = _make_practitioner(license_type="Attorney")
        assert p.covers("court_filing")
        assert not p.covers("tax_return")

    def test_notary_only_covers_notarial_acts(self):
        p = _make_practitioner(license_type="Notary")
        assert p.covers("notarized_affidavit")
        assert not p.covers("tax_return")
        assert not p.covers("structural_plan")

    def test_pe_requires_structural_endorsement_for_structural_plan(self):
        p = _make_practitioner(
            license_type="PE",
            scope_endorsements=["electrical"],
        )
        assert not p.covers("structural_plan"), (
            "an electrical PE cannot stamp structural plans"
        )

    def test_pe_with_structural_endorsement_covers_structural(self):
        p = _make_practitioner(
            license_type="PE",
            scope_endorsements=["structural"],
        )
        assert p.covers("structural_plan")

    def test_unknown_artifact_type_not_covered(self):
        p = _make_practitioner(license_type="CPA")
        assert not p.covers("nuclear_reactor_license")

    def test_unknown_license_type_covers_nothing(self):
        p = _make_practitioner(license_type="Astrologer")
        assert not p.covers("tax_return")
