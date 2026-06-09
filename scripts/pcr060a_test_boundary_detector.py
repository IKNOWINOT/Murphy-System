#!/usr/bin/env python3
"""
PCR-060a — Boundary-Condition Detector test harness

Five hand-crafted cases that exercise the detector against known-shape
inputs. Run directly:

    /opt/Murphy-System/venv/bin/python3 \\
        scripts/pcr060a_test_boundary_detector.py

The detector should:

  CASE 1 (good chain)     -> satisfied=True,  score >= 0.7
  CASE 2 (no leverage)    -> satisfied=False, weakest_link=leverage_points
  CASE 3 (no collapse)    -> satisfied=False, weakest_link=collapse_points
  CASE 4 (generic margin) -> satisfied=False, weakest_link=unit_economics_at_scale
  CASE 5 (action no chain)-> satisfied=False, next_pilot_move_chain_visible=False

Pass criteria: detector must correctly identify the failure mode in
cases 2-5, and pass case 1. If LLM is being flaky, output shows the
discrepancy without crashing the test.
"""

import sys
import json
import time
from pathlib import Path

# Make src importable when running from /opt/Murphy-System
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.pcr060_boundary_condition import evaluate, summarize, BoundaryResult


# ─────────────────────────────────────────────────────────────────────
# Shared business spec for the test cases
# ─────────────────────────────────────────────────────────────────────

BUSINESS = {
    "name": "Northgrain Roastery",
    "subject_matter": "specialty coffee roasting + wholesale distribution",
    "business_class": "boutique food & beverage manufacturer",
    "scale_target": "10,000 bags/year at year 2",
    "geography": "Pacific Northwest, US",
    "channels": ["wholesale to cafés", "direct subscription"],
}

GOAL = {
    "actualized_state": "Profitable at $1.2M revenue, 28% net margin, 50/50 wholesale/DTC",
    "operational_targets": {
        "bags_per_week": 200,
        "wholesale_accounts": 35,
        "DTC_subscribers": 800,
        "weeks_inventory_on_hand": 2,
    },
    "money_ratio_targets": {
        "gross_margin": 0.62,
        "contribution_margin_wholesale": 0.38,
        "contribution_margin_DTC": 0.55,
        "operating_margin": 0.28,
    },
    "subject_matter_context": (
        "Specialty coffee has high green-bean cost volatility (~30% of COGS), "
        "physical fulfillment cost is non-trivial for DTC, wholesale margin "
        "is squeezed by distributor markups, and brand-led pricing power "
        "depends on origin storytelling and Q-grade quality consistency."
    ),
}


# ─────────────────────────────────────────────────────────────────────
# CASE 1 — Good chain. Should pass.
# ─────────────────────────────────────────────────────────────────────

CASE_1_GOOD = """
NORTHGRAIN — OPERATIONAL ECONOMICS

Roasting: 1 operator can roast 60kg/day on a Loring S15 (capex amortized
$2.10/lb over 5 yr). At 200 bags/wk (12oz bags, ~75kg green-bean throughput
when accounting for ~17% roast loss), labor is 1.0 FTE * $52k = $52k/yr,
or $0.65/bag in labor cost.

Green bean: Direct-trade Ethiopian sidamo lots at $7.20/lb green, post-roast
yield 0.83 lb roasted from 1 lb green, so $8.67/lb roasted; at 12oz/bag
that's $6.50 in green per bag.

Packaging + label: $0.72/bag. Fulfillment (DTC): $4.10/bag (USPS Priority +
mailer + labor). Wholesale fulfillment: $0.95/bag (consolidated drops to
5-10 cafés per route).

Wholesale price: $14/bag (margin: $14 - $6.50 - $0.72 - $0.95 - $0.65 = $5.18,
contribution margin = 37%).
DTC price: $22/bag (margin: $22 - $6.50 - $0.72 - $4.10 - $0.65 = $10.03,
contribution margin = 46%).

UNIT ECONOMICS AT SCALE

  1x  (200/wk, $208k rev):  GM 60%, CM-blended 41%, OM -5% (fixed cost drag)
  10x (2,000/wk, $2.08M):   GM 62%, CM 43%, OM 18% (sales hire @ $80k, eq lease)
  100x (20,000/wk, $20.8M): GM 60%, CM 41%, OM 22% (distribution/warehousing
                            adds back fixed costs, hub-and-spoke model)

Assumption between 10x->100x: distribution shifts from owner-operator dropoff
to regional distributor (margin compression of 8 pts) offset by scale procurement.

LEVERAGE POINTS (specialty coffee specific)

  L1. Green-bean direct-trade vs broker: 12-18% COGS reduction (broker
      markup is 15-25% in specialty), moves OM by ~6pts at scale.
      Why this matters specifically for Northgrain: Q-grade sourcing
      makes direct relationships actually possible (broker = no traceability).

  L2. DTC subscription mix: each 10pt shift wholesale->DTC moves
      blended CM by ~2.5pts. Hits OM by ~5pts at 10x scale.
      Why specific: roasted coffee has a 2-3 week peak freshness window,
      DTC subscription locks in flow-rate predictability.

  L3. Bag size tier (8oz vs 12oz vs 5lb): 5lb café accounts have
      40% lower fulfillment cost as % of revenue. Critical lever
      because café accounts naturally want larger formats anyway.

  L4. Cupping-score consistency: a sustained 86+ Q-grade unlocks
      $2-4/bag wholesale price premium without volume loss.
      Why specific: specialty buyers (3rd-wave cafés) make rebuy
      decisions on cupping score, not brand.

ATTRACTORS (drift states)

  A1. "Roast-everything for everyone" — bag SKUs proliferate from
      4 to 14 in year 2, fragmenting batch sizes, increasing changeover
      time per kg by 35%. Why happens: each wholesale account asks for
      a custom blend and the answer is yes.

  A2. "Subscription churn cycle" — DTC churn creeps from 6% to 14%
      monthly because new-customer freshness flow rate exceeds peak
      window. Why happens: the Loring's daily capacity hits ceiling
      and roasts get queued, missing the under-5-day-from-roast ship target.

  A3. "Wholesale margin erosion" — distributors push back on $14
      price annually, drift to $12.50 over 3 years. Why: distributors
      have category-level price benchmarking and Northgrain has no
      structural moat at the distribution layer.

COLLAPSE POINTS

  C1. Green bean cost shock (>40% spike in C-market). Mechanism:
      Brazilian frost or Vietnamese rust outbreak compresses supply.
      Lead time: 6 weeks from forecast to retail price hit. Signal:
      C-market futures + ICE differentials hit 2-std deviation.

  C2. Loss of #1 wholesale account (currently 22% of revenue).
      Mechanism: account is bought by chain that brings roasting in-house.
      Lead time: 30-90 days post-acquisition announcement. Signal:
      M&A announcement in the buyer's category.

  C3. Compliance failure (FDA/USDA recall on aflatoxin or moisture).
      Mechanism: green bean lot QC miss. Lead time: instant. Signal:
      lot-level moisture/water-activity test failures clustering.

NEXT PILOT MOVE (chain visible to goal)

Pilot: Shift 3 of the top 5 wholesale accounts to 5lb format with a
$0.50/lb price reduction trade for 25% volume commitment.

Chain:
  - Doing this moves L3 (bag size tier) by ~7pts of fulfillment cost
    as % of revenue
  - Which moves wholesale CM from 37% -> 41% (margin gain offsets price cut)
  - Which moves blended OM from current -5% to +2% at current 1x scale
  - Which moves us from present (cashflow-fragile pre-revenue) toward goal
    (28% net margin profitability) by pulling forward the OM-positive
    inflection from year 2 to mid-year 1.

Risk: account pushback (mitigation: pilot with 3 most relationship-strong
accounts first, structured as joint MoU not contract).
"""


# ─────────────────────────────────────────────────────────────────────
# CASE 2 — No leverage points. Should fail at leverage_points.
# ─────────────────────────────────────────────────────────────────────

CASE_2_NO_LEVERAGE = CASE_1_GOOD.replace(
    "LEVERAGE POINTS (specialty coffee specific)",
    "GROWTH IDEAS"
).replace(
    "  L1. Green-bean direct-trade vs broker: 12-18% COGS reduction (broker\n"
    "      markup is 15-25% in specialty), moves OM by ~6pts at scale.\n"
    "      Why this matters specifically for Northgrain: Q-grade sourcing\n"
    "      makes direct relationships actually possible (broker = no traceability).\n"
    "\n"
    "  L2. DTC subscription mix: each 10pt shift wholesale->DTC moves\n"
    "      blended CM by ~2.5pts. Hits OM by ~5pts at 10x scale.\n"
    "      Why specific: roasted coffee has a 2-3 week peak freshness window,\n"
    "      DTC subscription locks in flow-rate predictability.\n"
    "\n"
    "  L3. Bag size tier (8oz vs 12oz vs 5lb): 5lb café accounts have\n"
    "      40% lower fulfillment cost as % of revenue. Critical lever\n"
    "      because café accounts naturally want larger formats anyway.\n"
    "\n"
    "  L4. Cupping-score consistency: a sustained 86+ Q-grade unlocks\n"
    "      $2-4/bag wholesale price premium without volume loss.\n"
    "      Why specific: specialty buyers (3rd-wave cafés) make rebuy\n"
    "      decisions on cupping score, not brand.",
    "We could grow by improving marketing, increasing customer retention, "
    "and reducing customer acquisition cost. Pricing optimization is also "
    "key. We should focus on operational efficiency."
)


# ─────────────────────────────────────────────────────────────────────
# CASE 3 — No collapse points. Should fail at collapse_points.
# ─────────────────────────────────────────────────────────────────────

CASE_3_NO_COLLAPSE = CASE_1_GOOD.replace(
    "COLLAPSE POINTS\n\n"
    "  C1. Green bean cost shock (>40% spike in C-market). Mechanism:\n"
    "      Brazilian frost or Vietnamese rust outbreak compresses supply.\n"
    "      Lead time: 6 weeks from forecast to retail price hit. Signal:\n"
    "      C-market futures + ICE differentials hit 2-std deviation.\n"
    "\n"
    "  C2. Loss of #1 wholesale account (currently 22% of revenue).\n"
    "      Mechanism: account is bought by chain that brings roasting in-house.\n"
    "      Lead time: 30-90 days post-acquisition announcement. Signal:\n"
    "      M&A announcement in the buyer's category.\n"
    "\n"
    "  C3. Compliance failure (FDA/USDA recall on aflatoxin or moisture).\n"
    "      Mechanism: green bean lot QC miss. Lead time: instant. Signal:\n"
    "      lot-level moisture/water-activity test failures clustering.",
    "RISKS\n\n"
    "  - Market risk\n"
    "  - Operational risk\n"
    "  - Reputation risk"
)


# ─────────────────────────────────────────────────────────────────────
# CASE 4 — Single generic margin, no scaling. Should fail unit_economics.
# ─────────────────────────────────────────────────────────────────────

CASE_4_GENERIC_MARGIN = CASE_1_GOOD.replace(
    "UNIT ECONOMICS AT SCALE\n\n"
    "  1x  (200/wk, $208k rev):  GM 60%, CM-blended 41%, OM -5% (fixed cost drag)\n"
    "  10x (2,000/wk, $2.08M):   GM 62%, CM 43%, OM 18% (sales hire @ $80k, eq lease)\n"
    "  100x (20,000/wk, $20.8M): GM 60%, CM 41%, OM 22% (distribution/warehousing\n"
    "                            adds back fixed costs, hub-and-spoke model)\n"
    "\n"
    "Assumption between 10x->100x: distribution shifts from owner-operator dropoff\n"
    "to regional distributor (margin compression of 8 pts) offset by scale procurement.",
    "MARGIN\n\nOur gross margin is roughly 60%. We expect profitability at scale."
)


# ─────────────────────────────────────────────────────────────────────
# CASE 5 — Action list with no chain back to goal.
# Should set next_pilot_move_chain_visible=False.
# ─────────────────────────────────────────────────────────────────────

CASE_5_NO_CHAIN = CASE_1_GOOD.replace(
    "NEXT PILOT MOVE (chain visible to goal)\n\n"
    "Pilot: Shift 3 of the top 5 wholesale accounts to 5lb format with a\n"
    "$0.50/lb price reduction trade for 25% volume commitment.\n"
    "\n"
    "Chain:\n"
    "  - Doing this moves L3 (bag size tier) by ~7pts of fulfillment cost\n"
    "    as % of revenue\n"
    "  - Which moves wholesale CM from 37% -> 41% (margin gain offsets price cut)\n"
    "  - Which moves blended OM from current -5% to +2% at current 1x scale\n"
    "  - Which moves us from present (cashflow-fragile pre-revenue) toward goal\n"
    "    (28% net margin profitability) by pulling forward the OM-positive\n"
    "    inflection from year 2 to mid-year 1.\n"
    "\n"
    "Risk: account pushback (mitigation: pilot with 3 most relationship-strong\n"
    "accounts first, structured as joint MoU not contract).",
    "NEXT STEPS\n\n"
    "  1. Hire a sales lead\n"
    "  2. Launch DTC subscription\n"
    "  3. Apply for SBA loan\n"
    "  4. Build inventory buffer\n"
    "  5. Onboard 5 new wholesale accounts"
)


# ─────────────────────────────────────────────────────────────────────
# Test runner
# ─────────────────────────────────────────────────────────────────────

CASES = [
    ("CASE 1 — good chain (should PASS)",                   CASE_1_GOOD,         True,  None),
    ("CASE 2 — no leverage (should FAIL at leverage)",      CASE_2_NO_LEVERAGE,  False, "leverage_points"),
    ("CASE 3 — no collapse (should FAIL at collapse)",      CASE_3_NO_COLLAPSE,  False, "collapse_points"),
    ("CASE 4 — generic margin (should FAIL at unit_econ)",  CASE_4_GENERIC_MARGIN, False, "unit_economics_at_scale"),
    ("CASE 5 — no chain (chain_visible=False)",             CASE_5_NO_CHAIN,     False, "next_pilot_move_chain_visible"),
]


def _grade_case(label, deliverable, expected_satisfied, expected_weakest):
    print("=" * 72)
    print(label)
    print(f"  deliverable: {len(deliverable)} chars")

    t0 = time.time()
    result = evaluate(deliverable, BUSINESS, GOAL)
    elapsed = time.time() - t0

    print(f"  {summarize(result)}")
    print(f"  per_question quality scores:")
    for k, v in result.per_question.items():
        marker = "✓" if v["quality"] >= 0.7 else "✗"
        print(f"    {marker} {k:38s} q={v['quality']:.2f} answered={v['answered']}")
    if result.missing_density_for:
        print(f"  missing_density_for:")
        for m in result.missing_density_for:
            print(f"    - {m[:120]}")
    if result.error:
        print(f"  ⚠ error: {result.error}")

    # Grade
    ok_satisfied = (result.satisfied == expected_satisfied)
    if expected_weakest is None:
        ok_weakest = True
    elif expected_weakest == "next_pilot_move_chain_visible":
        ok_weakest = (result.next_pilot_move_chain_visible is False)
    else:
        ok_weakest = (result.weakest_link == expected_weakest)

    if ok_satisfied and ok_weakest:
        verdict = "✓ PASS"
    elif ok_satisfied or ok_weakest:
        verdict = "~ PARTIAL"
    else:
        verdict = "✗ FAIL"

    print(f"  expected: satisfied={expected_satisfied} weakest={expected_weakest}")
    print(f"  actual:   satisfied={result.satisfied}     weakest={result.weakest_link}")
    print(f"  VERDICT:  {verdict}    (eval took {elapsed:.1f}s)")
    print()

    return {
        "label": label,
        "expected_satisfied": expected_satisfied,
        "expected_weakest":   expected_weakest,
        "actual_satisfied":   result.satisfied,
        "actual_weakest":     result.weakest_link,
        "score":              result.score,
        "ok":                 ok_satisfied and ok_weakest,
        "partial":            (ok_satisfied or ok_weakest) and not (ok_satisfied and ok_weakest),
        "elapsed_seconds":    elapsed,
        "provider":           result.provider,
        "error":              result.error,
    }


def main():
    print()
    print("PCR-060a — Boundary-Condition Detector test harness")
    print(f"business: {BUSINESS['name']} ({BUSINESS['subject_matter']})")
    print()

    results = []
    for label, deliverable, exp_sat, exp_weak in CASES:
        results.append(_grade_case(label, deliverable, exp_sat, exp_weak))

    print("=" * 72)
    print("SUMMARY")
    full_pass = sum(1 for r in results if r["ok"])
    partial = sum(1 for r in results if r["partial"])
    fail = sum(1 for r in results if not r["ok"] and not r["partial"])
    print(f"  full pass: {full_pass}/{len(results)}")
    print(f"  partial:   {partial}/{len(results)}")
    print(f"  fail:      {fail}/{len(results)}")
    total_time = sum(r["elapsed_seconds"] for r in results)
    print(f"  total LLM time: {total_time:.1f}s")
    print()
    print("PER-CASE:")
    for r in results:
        flag = "✓" if r["ok"] else ("~" if r["partial"] else "✗")
        print(f"  {flag} {r['label'][:60]:60s} score={r['score']:.2f} {r['elapsed_seconds']:.1f}s")
    print()

    # Exit 0 if at least 4/5 are full-pass (allows for one LLM flakiness).
    # Detector is for an audit decision, not a regression test of itself —
    # but we want strong signal it's working at all.
    return 0 if full_pass >= 4 else 1


if __name__ == "__main__":
    sys.exit(main())
