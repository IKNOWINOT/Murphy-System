"""
R&D Tax Credits — Federal §41 + State R&D Credits stackable with federal.

Key for Track A (Murphy/Inoni LLC) to offset development costs.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

# Federal §41 is defined in federal_tax_credits.py — re-exported here for convenience
from src.billing.grants.federal_tax_credits import RD_CREDIT_SEC41
from src.billing.grants.models import Grant, GrantCategory, GrantTrack

# ---------------------------------------------------------------------------
# State R&D Credits (stackable with federal §41)
# ---------------------------------------------------------------------------

STATE_RD_CREDITS = Grant(
    id="state_rd_credits",
    name="State R&D Tax Credits (Multiple States — stackable with federal §41)",
    category=GrantCategory.RD_TAX_CREDIT,
    track=GrantTrack.TRACK_A,
    short_description="State-level R&D credits (3–25% depending on state) stackable with federal §41 R&D credit.",
    long_description=(
        "Many U.S. states offer R&D tax credits that stack on top of the federal §41 credit. "
        "Combined, state + federal R&D credits can reduce the effective cost of qualifying "
        "R&D by 20–40%. Key states for Inoni LLC / Murphy System: "
        "\n\n"
        "• Oregon: No state R&D credit (but R&D wages are deductible). "
        "• California: 15% incremental credit on QREs above base; 24% for small businesses "
        "  with QREs under $1M. California is the most valuable state R&D credit. "
        "• Massachusetts: 10% of QREs above prior 3-year avg (or 15% for small businesses). "
        "• New York: 9% of QREs for qualified emerging technology companies (QETCs). "
        "• Texas: No state income tax, so no state R&D credit; but the state has a "
        "  franchise tax R&D credit (5% of qualifying costs). "
        "• Georgia: 10% of QREs above base year for technology companies. "
        "• Pennsylvania: 10% or 20% for small businesses on QREs. "
        "\n\n"
        "For Murphy/Inoni, the federal §41 payroll tax offset (up to $500K/yr) combined "
        "with a California or Massachusetts state credit provides the highest value "
        "if Inoni has nexus in those states."
    ),
    agency_or_provider="State revenue departments (varies by state)",
    program_url="https://taxfoundation.org/research/all/state/state-rd-tax-credits/",
    application_url=None,
    min_amount_usd=None,
    max_amount_usd=None,
    value_description="3–25% depending on state; California 15–24% most valuable",
    eligible_entity_types=["small_business", "corporation", "startup"],
    eligible_project_types=["agentic", "ai_platform", "software_rd", "automation_rd", "industrial_iot"],
    requires_rd_activity=True,
    is_recurring=True,
    longevity_note="Permanent state credits in most states; California most stable",
    stackable_with=["rd_credit_sec41", "sbir_phase1", "sec_48c"],
    tags=["state", "rd_credit", "stackable", "california", "massachusetts", "new_york", "track_a"],
    last_updated="2024-01",
)


def get_rd_tax_credits() -> list:
    """Return all R&D tax credit objects."""
    return [RD_CREDIT_SEC41, STATE_RD_CREDITS]
