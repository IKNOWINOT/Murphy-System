"""PCR-053b regression test — multi-dim N gate fields work end-to-end."""
from src.org_compiler.schemas import (
    AuthorityLevel, ArtifactType, RoleTemplate, EscalationPath,
    ComplianceConstraint, RoleMetrics,
)


def _minimal_template(**overrides):
    """Build a valid RoleTemplate with the minimum required fields."""
    base = dict(
        role_id="sales_rep",
        role_name="Sales Rep",
        responsibilities=["qualify leads", "send quotes"],
        decision_authority=AuthorityLevel.LOW,
        input_artifacts=[ArtifactType.EMAIL],
        output_artifacts=[ArtifactType.DOCUMENT],
        escalation_paths=[
            EscalationPath(
                path_id="esc_1",
                from_role="sales_rep",
                to_role="ceo",
                trigger_conditions=["deal > ceiling"],
                sla_hours=1.0,
            )
        ],
        compliance_constraints=[
            ComplianceConstraint(
                constraint_id="cc_audit",
                regulation="audit_trail",
                description="All decisions logged",
                verification_required=True,
                human_signoff_required=False,
                audit_trail_required=True,
            )
        ],
        requires_human_signoff=["before_external_email"],
        metrics=RoleMetrics(sla_targets={"response_time_hours": 24}, quality_gates=["peer_review"]),
    )
    base.update(overrides)
    return RoleTemplate(**base)


class TestMultiDimNGateFields:
    """PCR-053b — verify the three new fields load with safe defaults
    AND accept caller-supplied values AND participate in integrity hash."""

    def test_defaults_are_safe_and_dont_break_old_constructors(self):
        tpl = _minimal_template()
        assert tpl.decision_ceiling_usd is None
        assert tpl.distinct_operators_required == 1
        assert tpl.primary_jurisdiction is None

    def test_caller_can_set_money_axis(self):
        tpl = _minimal_template(decision_ceiling_usd=50_000.0)
        assert tpl.decision_ceiling_usd == 50_000.0

    def test_caller_can_set_operators_axis(self):
        tpl = _minimal_template(distinct_operators_required=5)
        assert tpl.distinct_operators_required == 5

    def test_caller_can_set_jurisdiction_axis(self):
        tpl = _minimal_template(primary_jurisdiction="US-CA")
        assert tpl.primary_jurisdiction == "US-CA"

    def test_integrity_hash_changes_when_new_fields_change(self):
        """If someone tampers with the money/operator/jurisdiction fields,
        the integrity hash must catch it. Otherwise the gate is bypassable."""
        a = _minimal_template(decision_ceiling_usd=10_000.0, primary_jurisdiction="US-CA")
        b = _minimal_template(decision_ceiling_usd=10_000_000.0, primary_jurisdiction="US-CA")
        assert a.integrity_hash != b.integrity_hash, "money axis must affect hash"

        c = _minimal_template(distinct_operators_required=1)
        d = _minimal_template(distinct_operators_required=10)
        assert c.integrity_hash != d.integrity_hash, "operators axis must affect hash"

        e = _minimal_template(primary_jurisdiction="US-CA")
        f = _minimal_template(primary_jurisdiction="EU-DE")
        assert e.integrity_hash != f.integrity_hash, "jurisdiction axis must affect hash"

    def test_compliance_constraint_carries_jurisdiction(self):
        cc = ComplianceConstraint(
            constraint_id="cc_gdpr",
            regulation="GDPR",
            description="EU data residency",
            verification_required=True,
            human_signoff_required=True,
            audit_trail_required=True,
            jurisdiction="EU-DE",
        )
        assert cc.jurisdiction == "EU-DE"

    def test_compliance_constraint_defaults_jurisdiction_to_none_global(self):
        cc = ComplianceConstraint(
            constraint_id="cc_audit",
            regulation="audit_trail",
            description="Universal audit logging",
            verification_required=True,
            human_signoff_required=False,
            audit_trail_required=True,
        )
        assert cc.jurisdiction is None, "no jurisdiction = global scope"
