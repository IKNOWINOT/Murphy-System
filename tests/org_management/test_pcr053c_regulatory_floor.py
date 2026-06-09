"""PCR-053c — RegulatoryFloor lookup & evaluation regression suite.

Verifies the multi-dim N gate model produces the right verdicts across
the canonical (jurisdiction, industry, role_family) combinations.
"""
import pytest
from src.org_compiler.regulatory_floor import (
    REGULATORY_FLOOR,
    FloorPolicy,
    FloorMissingError,
    GateVerdict,
    lookup_floor,
    evaluate_against_floor,
    list_known_combinations,
)


# ──────────────────────────────────────────────────────────────────
# Table integrity
# ──────────────────────────────────────────────────────────────────


class TestTableIntegrity:
    def test_table_is_not_empty(self):
        assert len(REGULATORY_FLOOR) >= 7

    def test_every_entry_is_floor_policy(self):
        for k, v in REGULATORY_FLOOR.items():
            assert isinstance(v, FloorPolicy), f"{k} is not a FloorPolicy"

    def test_every_entry_has_citation(self):
        for k, v in REGULATORY_FLOOR.items():
            assert v.citation, f"{k} missing citation"

    def test_list_known_combinations_works(self):
        combos = list_known_combinations()
        assert ("US-CA", "saas", "sales_rep") in combos
        assert ("CH", "banking", "compliance_officer") in combos


# ──────────────────────────────────────────────────────────────────
# lookup_floor — fail-closed semantics
# ──────────────────────────────────────────────────────────────────


class TestLookupFloor:
    def test_known_combination_returns_policy(self):
        p = lookup_floor("US-CA", "saas", "sales_rep")
        assert p.min_observation_days == 14
        assert p.min_distinct_operators == 3
        assert p.max_decision_ceiling_usd == 50_000.0

    def test_missing_jurisdiction_fail_closed(self):
        """Per locked policy: missing jurisdiction = fail closed, loud alert."""
        with pytest.raises(FloorMissingError):
            lookup_floor(None, "saas", "sales_rep")

    def test_unknown_combination_fail_closed(self):
        """Per locked policy: unmapped combinations = fail closed."""
        with pytest.raises(FloorMissingError):
            lookup_floor("MARS", "interplanetary", "rover_operator")

    def test_fail_closed_error_includes_key_for_alerting(self):
        try:
            lookup_floor("AQ", "biotech", "researcher")
            pytest.fail("expected FloorMissingError")
        except FloorMissingError as e:
            assert e.key == ("AQ", "biotech", "researcher")
            assert "BLOCKED" in str(e)


# ──────────────────────────────────────────────────────────────────
# evaluate_against_floor — multi-dim verdicts
# ──────────────────────────────────────────────────────────────────


class TestEvaluateAgainstFloor:

    def test_inoni_sales_rep_passes_with_sufficient_evidence(self):
        v = evaluate_against_floor(
            jurisdiction="US-CA", industry="saas", role_family="sales_rep",
            observation_window_days=21,
            distinct_operators_observed=4,
            decision_ceiling_usd=10_000.0,
            compliance_regulations=("audit_trail",),
        )
        assert v.passes, f"expected pass, reasons={v.reasons}"
        assert v.fail_closed is False

    def test_inoni_sales_rep_blocked_by_time(self):
        v = evaluate_against_floor(
            jurisdiction="US-CA", industry="saas", role_family="sales_rep",
            observation_window_days=7,    # too few — floor is 14
            distinct_operators_observed=4,
            decision_ceiling_usd=10_000.0,
            compliance_regulations=("audit_trail",),
        )
        assert v.passes is False
        assert any("TIME:" in r and "7d" in r for r in v.reasons)

    def test_inoni_sales_rep_blocked_by_operators(self):
        v = evaluate_against_floor(
            jurisdiction="US-CA", industry="saas", role_family="sales_rep",
            observation_window_days=21,
            distinct_operators_observed=1,  # too few — floor is 3
            decision_ceiling_usd=10_000.0,
            compliance_regulations=("audit_trail",),
        )
        assert v.passes is False
        assert any("OPERATORS:" in r for r in v.reasons)

    def test_inoni_sales_rep_blocked_by_money(self):
        v = evaluate_against_floor(
            jurisdiction="US-CA", industry="saas", role_family="sales_rep",
            observation_window_days=21,
            distinct_operators_observed=4,
            decision_ceiling_usd=500_000.0,  # too high — ceiling is 50k
            compliance_regulations=("audit_trail",),
        )
        assert v.passes is False
        assert any("MONEY:" in r and "500,000" in r for r in v.reasons)

    def test_inoni_sales_rep_blocked_by_missing_regulation(self):
        v = evaluate_against_floor(
            jurisdiction="US-CA", industry="saas", role_family="sales_rep",
            observation_window_days=21,
            distinct_operators_observed=4,
            decision_ceiling_usd=10_000.0,
            compliance_regulations=(),  # missing audit_trail
        )
        assert v.passes is False
        assert any("REGS:" in r for r in v.reasons)

    def test_eu_sales_rep_needs_more_observation_than_us(self):
        """GDPR multiplier — same role, stricter floor in EU."""
        us = lookup_floor("US-CA", "saas", "sales_rep")
        eu = lookup_floor("EU-DE", "saas", "sales_rep")
        assert eu.min_observation_days > us.min_observation_days
        assert eu.min_distinct_operators > us.min_distinct_operators
        assert "GDPR_consent" in eu.required_regulations

    def test_eu_blocks_when_gdpr_consent_missing(self):
        v = evaluate_against_floor(
            jurisdiction="EU-DE", industry="saas", role_family="sales_rep",
            observation_window_days=30,
            distinct_operators_observed=6,
            decision_ceiling_usd=10_000.0,
            compliance_regulations=("audit_trail",),  # missing GDPR_consent + right_to_erasure
        )
        assert v.passes is False
        assert any("GDPR_consent" in r or "right_to_erasure" in r for r in v.reasons)

    def test_ceo_role_is_never_promote(self):
        """Executive fiduciary duty is non-delegatable, even with perfect evidence."""
        v = evaluate_against_floor(
            jurisdiction="US-CA", industry="saas", role_family="ceo",
            observation_window_days=10_000,
            distinct_operators_observed=999,
            decision_ceiling_usd=0.0,
            compliance_regulations=("audit_trail", "code_review"),
        )
        assert v.passes is False
        assert any("never_promote" in r for r in v.reasons)

    def test_ch_banking_compliance_officer_is_never_promote(self):
        """Swiss banking secrecy — hard legal block."""
        v = evaluate_against_floor(
            jurisdiction="CH", industry="banking", role_family="compliance_officer",
            observation_window_days=10_000,
            distinct_operators_observed=999,
            decision_ceiling_usd=None,
            compliance_regulations=("FINMA", "Swiss_banking_secrecy"),
        )
        assert v.passes is False
        assert any("never_promote" in r for r in v.reasons)

    def test_unmapped_combination_returns_fail_closed_verdict(self):
        """Caller gets a verdict, not an exception — so audit trail records it."""
        v = evaluate_against_floor(
            jurisdiction="ZW", industry="agriculture", role_family="harvester",
            observation_window_days=999,
            distinct_operators_observed=999,
            decision_ceiling_usd=100.0,
            compliance_regulations=(),
        )
        assert v.passes is False
        assert v.fail_closed is True
        assert any("FAIL-CLOSED" in r for r in v.reasons)

    def test_none_jurisdiction_returns_fail_closed_verdict(self):
        """Most common real-world failure: onboarding didn't capture jurisdiction."""
        v = evaluate_against_floor(
            jurisdiction=None, industry="saas", role_family="sales_rep",
            observation_window_days=30,
            distinct_operators_observed=5,
            decision_ceiling_usd=10_000.0,
            compliance_regulations=("audit_trail",),
        )
        assert v.passes is False
        assert v.fail_closed is True


# ──────────────────────────────────────────────────────────────────
# Engineer / no-monetary role
# ──────────────────────────────────────────────────────────────────


class TestEngineerRole:
    def test_engineer_blocked_if_money_authority_requested(self):
        """Engineers have ceiling=0; any nonzero request blocks."""
        v = evaluate_against_floor(
            jurisdiction="US-CA", industry="saas", role_family="engineer",
            observation_window_days=60,
            distinct_operators_observed=3,
            decision_ceiling_usd=5_000.0,   # nonzero — should block
            compliance_regulations=("audit_trail", "code_review"),
        )
        assert v.passes is False
        assert any("MONEY:" in r for r in v.reasons)

    def test_engineer_passes_with_zero_money_authority(self):
        v = evaluate_against_floor(
            jurisdiction="US-CA", industry="saas", role_family="engineer",
            observation_window_days=60,
            distinct_operators_observed=3,
            decision_ceiling_usd=0.0,
            compliance_regulations=("audit_trail", "code_review"),
        )
        assert v.passes, f"expected pass, reasons={v.reasons}"
