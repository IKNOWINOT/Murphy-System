"""
PCR-053c — Regulatory Floor lookup table

Implements the multi-dimensional N gate model defined in PCR-053b.
The schema fields (decision_ceiling_usd, distinct_operators_required,
primary_jurisdiction, observation_window_days, success_rate) describe
WHAT a role wants. This table describes WHAT THE LAW REQUIRES before
that role's work can be auto-substituted.

Locked defaults (Corey approved 2026-06-09):
  - Missing-jurisdiction at gate time: FAIL CLOSED with loud alert.
  - Jurisdiction source: tenant onboarding form + role-level override.

Some roles in some jurisdictions are PERMANENTLY non-promotable
(e.g. Swiss banking compliance officer). The table encodes that as
`never_promote=True` — not a bug, a feature.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────
# DATA TYPES
# ─────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class FloorPolicy:
    """Regulatory floor for one (jurisdiction, industry, role_family) tuple.

    All thresholds are MINIMUMS — a RoleTemplate's own fields may be
    stricter, never looser. The SubstitutionGate uses this as the
    fail-closed baseline.
    """
    # Time floor: how many calendar days of observation are required
    min_observation_days: int

    # Operators floor: how many distinct humans must have done the work
    min_distinct_operators: int

    # Money ceiling: max USD decision authority the auto-agent may exercise
    # None means "no automation of monetary decisions allowed for this role"
    max_decision_ceiling_usd: Optional[float]

    # Hard kill switch — some jurisdictions/roles never auto-promote, by law
    never_promote: bool = False

    # Regulations that MUST be flagged as immutable compliance constraints
    # on the role template before the gate can pass.
    required_regulations: Tuple[str, ...] = field(default_factory=tuple)

    # Free-form citation so the audit trail can explain WHY this floor exists
    citation: str = ""


@dataclass(frozen=True)
class GateVerdict:
    """Result of comparing a RoleTemplate (+ observed telemetry) against a
    FloorPolicy. Verdict is intentionally rich so the UI/audit can explain
    exactly which dimension blocks promotion."""
    passes: bool
    reasons: Tuple[str, ...]  # one human-readable line per dimension
    floor_source: str         # which table entry was used
    fail_closed: bool = False  # true if we failed because lookup was missing


class FloorMissingError(LookupError):
    """Raised when (jurisdiction, industry, role_family) is not in the table.

    Per Corey's locked default 2026-06-09: FAIL CLOSED with loud alert.
    Callers should catch this, block promotion, and surface to the founder.
    """
    def __init__(self, key: Tuple[str, str, str]):
        self.key = key
        super().__init__(
            f"No regulatory floor entry for {key}. "
            f"Promotion BLOCKED per fail-closed policy. "
            f"Add a REGULATORY_FLOOR row for this combination."
        )


# ─────────────────────────────────────────────────────────────────────────
# THE TABLE
# Curated baseline. Hand-maintained for v1. Long-term aspiration is to
# augment with an external compliance feed (SOC2 / HIPAA / GDPR mappings).
# ─────────────────────────────────────────────────────────────────────────


REGULATORY_FLOOR: Dict[Tuple[str, str, str], FloorPolicy] = {

    # ───── US-CA, SaaS — the Inoni baseline ─────
    ("US-CA", "saas", "sales_rep"): FloorPolicy(
        min_observation_days=14,
        min_distinct_operators=3,
        max_decision_ceiling_usd=50_000.0,
        required_regulations=("audit_trail",),
        citation="CCPA / general commercial; modest revenue authority",
    ),
    ("US-CA", "saas", "engineer"): FloorPolicy(
        min_observation_days=30,
        min_distinct_operators=2,
        max_decision_ceiling_usd=0.0,  # engineers don't auto-spend
        required_regulations=("audit_trail", "code_review"),
        citation="Code authority requires deterministic verification",
    ),
    ("US-CA", "saas", "ceo"): FloorPolicy(
        min_observation_days=365,
        min_distinct_operators=1,
        max_decision_ceiling_usd=None,  # CEO authority is not auto-substitutable
        never_promote=True,
        citation="Executive fiduciary duty is non-delegatable to automation",
    ),

    # ───── EU-DE, SaaS — GDPR multiplier ─────
    ("EU-DE", "saas", "sales_rep"): FloorPolicy(
        min_observation_days=28,           # 2x US-CA per GDPR caution
        min_distinct_operators=5,
        max_decision_ceiling_usd=50_000.0,
        required_regulations=("audit_trail", "GDPR_consent", "right_to_erasure"),
        citation="GDPR Art.22 — automated individual decisions require safeguards",
    ),

    # ───── US-TX, Health Insurance — HIPAA + state regs ─────
    ("US-TX", "health_ins", "claims_adjuster"): FloorPolicy(
        min_observation_days=90,
        min_distinct_operators=8,
        max_decision_ceiling_usd=25_000.0,
        required_regulations=("HIPAA", "audit_trail", "TX_ins_code_542"),
        citation="HIPAA PHI handling + TX prompt-pay statute",
    ),

    # ───── US-NY, Broker-Dealer — FINRA + SEC ─────
    ("US-NY", "broker_dealer", "trading_principal"): FloorPolicy(
        min_observation_days=365,
        min_distinct_operators=12,
        max_decision_ceiling_usd=float("inf"),
        required_regulations=("FINRA_3110", "SEC_15c3-5", "audit_trail"),
        citation="FINRA principal supervision; SEC market-access rule",
    ),

    # ───── CH, Banking — never auto-promote ─────
    ("CH", "banking", "compliance_officer"): FloorPolicy(
        min_observation_days=99_999,
        min_distinct_operators=99,
        max_decision_ceiling_usd=None,
        never_promote=True,
        required_regulations=("FINMA", "Swiss_banking_secrecy"),
        citation="Swiss Banking Act Art.47 — compliance authority non-delegatable",
    ),
}


# ─────────────────────────────────────────────────────────────────────────
# LOOKUP + EVALUATION
# ─────────────────────────────────────────────────────────────────────────


def lookup_floor(
    jurisdiction: Optional[str],
    industry: str,
    role_family: str,
) -> FloorPolicy:
    """Return the FloorPolicy for a (jurisdiction, industry, role_family) tuple.

    Raises FloorMissingError if not found. Per locked policy, the caller MUST
    treat this as fail-closed (block promotion) and surface a founder alert.

    Args:
        jurisdiction: e.g. "US-CA", "EU-DE", "CH"; None triggers fail-closed
        industry:     e.g. "saas", "health_ins", "broker_dealer", "banking"
        role_family:  canonical role family, e.g. "sales_rep", "engineer"
    """
    if jurisdiction is None:
        logger.warning(
            "lookup_floor called with jurisdiction=None — "
            "fail-closed per PCR-053b policy (industry=%s role=%s)",
            industry, role_family,
        )
        raise FloorMissingError(("<missing-jurisdiction>", industry, role_family))

    key = (jurisdiction, industry, role_family)
    if key in REGULATORY_FLOOR:
        return REGULATORY_FLOOR[key]

    logger.warning(
        "No regulatory floor for %s — fail-closed; add a row to REGULATORY_FLOOR",
        key,
    )
    raise FloorMissingError(key)


def evaluate_against_floor(
    *,
    jurisdiction: Optional[str],
    industry: str,
    role_family: str,
    observation_window_days: int,
    distinct_operators_observed: int,
    decision_ceiling_usd: Optional[float],
    compliance_regulations: Tuple[str, ...],
) -> GateVerdict:
    """Compare observed evidence against the regulatory floor for this role.

    Returns a GateVerdict. Verdict.passes is True only if EVERY dimension
    meets or exceeds the floor.

    On missing jurisdiction/lookup, returns a fail-closed GateVerdict
    rather than raising — so the SubstitutionGate can record the verdict
    in the audit trail with the rest of the gates.
    """
    try:
        floor = lookup_floor(jurisdiction, industry, role_family)
    except FloorMissingError as e:
        return GateVerdict(
            passes=False,
            reasons=(f"FAIL-CLOSED: {e}",),
            floor_source=f"<missing:{(jurisdiction, industry, role_family)}>",
            fail_closed=True,
        )

    reasons: List[str] = []

    # Hard kill: never_promote
    if floor.never_promote:
        reasons.append(
            f"never_promote=True for ({jurisdiction}, {industry}, {role_family}). "
            f"Citation: {floor.citation}"
        )
        return GateVerdict(
            passes=False,
            reasons=tuple(reasons),
            floor_source=f"{jurisdiction}/{industry}/{role_family}",
        )

    # Time dimension
    if observation_window_days < floor.min_observation_days:
        reasons.append(
            f"TIME: observed {observation_window_days}d "
            f"< required {floor.min_observation_days}d"
        )
    else:
        reasons.append(
            f"TIME: ok ({observation_window_days}d ≥ {floor.min_observation_days}d)"
        )

    # Operators dimension
    if distinct_operators_observed < floor.min_distinct_operators:
        reasons.append(
            f"OPERATORS: observed {distinct_operators_observed} distinct "
            f"< required {floor.min_distinct_operators}"
        )
    else:
        reasons.append(
            f"OPERATORS: ok ({distinct_operators_observed} ≥ {floor.min_distinct_operators})"
        )

    # Money dimension
    if floor.max_decision_ceiling_usd is None:
        if decision_ceiling_usd is not None and decision_ceiling_usd > 0:
            reasons.append(
                f"MONEY: this role family may not exercise monetary authority "
                f"(requested ${decision_ceiling_usd})"
            )
        else:
            reasons.append("MONEY: ok (no monetary authority requested)")
    elif decision_ceiling_usd is None:
        reasons.append("MONEY: ok (no ceiling requested)")
    elif decision_ceiling_usd > floor.max_decision_ceiling_usd:
        reasons.append(
            f"MONEY: requested ${decision_ceiling_usd:,.0f} "
            f"> ceiling ${floor.max_decision_ceiling_usd:,.0f}"
        )
    else:
        reasons.append(
            f"MONEY: ok (${decision_ceiling_usd:,.0f} ≤ ${floor.max_decision_ceiling_usd:,.0f})"
        )

    # Regulatory regulations — all required must be present
    missing_regs = tuple(r for r in floor.required_regulations if r not in compliance_regulations)
    if missing_regs:
        reasons.append(
            f"REGS: missing required regulations {list(missing_regs)} "
            f"(role has {list(compliance_regulations)})"
        )
    elif floor.required_regulations:
        reasons.append(
            f"REGS: ok ({len(floor.required_regulations)} required regulations all present)"
        )
    else:
        reasons.append("REGS: ok (no jurisdiction-specific regulations required)")

    # Aggregate
    passes = not any(r.startswith(("TIME:", "OPERATORS:", "MONEY:", "REGS:")) and " ok " not in r and not r.endswith(" ok") and "ok (" not in r
                     for r in reasons)
    # Simpler/safer: check that no reason starts with a failure marker.
    # Rebuild more strictly:
    failed = any(
        (r.startswith("TIME:") and "ok" not in r) or
        (r.startswith("OPERATORS:") and "ok" not in r) or
        (r.startswith("MONEY:") and "ok" not in r) or
        (r.startswith("REGS:") and "ok" not in r)
        for r in reasons
    )

    return GateVerdict(
        passes=not failed,
        reasons=tuple(reasons),
        floor_source=f"{jurisdiction}/{industry}/{role_family}",
    )


# ─────────────────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────────────────


def list_known_combinations() -> List[Tuple[str, str, str]]:
    """Useful for the founder UI: show every (jurisdiction, industry, role)
    currently in the table so missing rows are obvious."""
    return list(REGULATORY_FLOOR.keys())


__all__ = [
    "FloorPolicy",
    "GateVerdict",
    "FloorMissingError",
    "REGULATORY_FLOOR",
    "lookup_floor",
    "evaluate_against_floor",
    "list_known_combinations",
]
