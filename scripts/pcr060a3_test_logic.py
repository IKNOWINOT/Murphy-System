#!/usr/bin/env python3
"""
PCR-060a.3 — pure-logic tests (no LLM required)

Verifies:
  - APNEA_RAISE_CEILING fires under correct conditions
  - Ceiling-raise honors MAX_CEILING_RAISES cap
  - Q7 production_offset_ok requires BOTH clauses (Read C)
  - Q7 is N/A when raised_goal_active=False
  - BoundaryResultV3 serializes cleanly with v3 fields
  - v2/v3 coexistence (v2 callers unaffected)

Runs in milliseconds. No network, no LLM, no DB.
"""

from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.pcr060_boundary_v3 import (
    BoundaryResultV3,
    TrajectoryDelta,
    APNEA_FIRE, APNEA_PAUSE, APNEA_SATISFIED, APNEA_BUDGET_CAP,
    APNEA_RAISE_CEILING,
    MAX_CEILING_RAISES,
    BOUNDARY_QUESTIONS_V3,
    QUESTION_KEYS_V3,
    Q7_KEY,
    _decide_apnea_v3,
    _result_from_parsed_v3,
    summarize_v3,
)


def _check(name: str, cond: bool, detail: str = "") -> bool:
    icon = "✓" if cond else "✗"
    line = f"  {icon} {name}"
    if detail:
        line += f"   ({detail})"
    print(line)
    return cond


# ---------------------------------------------------------------------------
# Test: escalation triggers correctly
# ---------------------------------------------------------------------------

def test_escalation_triggers():
    print("\n── ceiling-raise escalation triggers ──")
    ok = True

    # Branch 1: satisfied EARLY + budget headroom + raises left → RAISE
    rec, reason, early = _decide_apnea_v3(
        satisfied=True, trajectory=None,
        iteration=1, max_iterations=5,
        budget_remaining=0.8, budget_initial=1.0,
        ceiling_level=0,
    )
    ok &= _check("early+headroom+raises_left → RAISE_CEILING",
                 rec == APNEA_RAISE_CEILING, reason)
    ok &= _check("  and early_satisfied flag is True", early is True)

    # Branch 2: satisfied LATE (no early) → normal SATISFIED
    rec, reason, early = _decide_apnea_v3(
        satisfied=True, trajectory=None,
        iteration=4, max_iterations=5,
        budget_remaining=0.8, budget_initial=1.0,
        ceiling_level=0,
    )
    ok &= _check("late satisfied (iter=4/5) → SATISFIED, no raise",
                 rec == APNEA_SATISFIED, reason)
    ok &= _check("  early_satisfied flag is False", early is False)

    # Branch 3: satisfied early BUT no budget → normal SATISFIED
    rec, reason, early = _decide_apnea_v3(
        satisfied=True, trajectory=None,
        iteration=1, max_iterations=5,
        budget_remaining=0.2, budget_initial=1.0,
        ceiling_level=0,
    )
    ok &= _check("early but low budget → SATISFIED, no raise",
                 rec == APNEA_SATISFIED, reason)

    # Branch 4: satisfied early + budget BUT ceilings exhausted → SATISFIED
    rec, reason, early = _decide_apnea_v3(
        satisfied=True, trajectory=None,
        iteration=1, max_iterations=5,
        budget_remaining=0.8, budget_initial=1.0,
        ceiling_level=MAX_CEILING_RAISES,  # at the cap
    )
    ok &= _check("at ceiling cap → SATISFIED, no raise",
                 rec == APNEA_SATISFIED, reason)

    # Branch 5: ceiling level just below cap → still raises
    rec, reason, early = _decide_apnea_v3(
        satisfied=True, trajectory=None,
        iteration=1, max_iterations=5,
        budget_remaining=0.8, budget_initial=1.0,
        ceiling_level=MAX_CEILING_RAISES - 1,
    )
    ok &= _check("at ceiling cap - 1 → RAISE_CEILING (last allowed)",
                 rec == APNEA_RAISE_CEILING, reason)

    return ok


# ---------------------------------------------------------------------------
# Test: non-satisfied paths still work (v2 behavior preserved)
# ---------------------------------------------------------------------------

def test_v2_behavior_preserved():
    print("\n── v2 behaviour preserved when not-satisfied ──")
    ok = True

    # Budget cap
    rec, reason, early = _decide_apnea_v3(
        satisfied=False, trajectory=None,
        iteration=2, max_iterations=5,
        budget_remaining=0.0, budget_initial=1.0,
        ceiling_level=0,
    )
    ok &= _check("budget=0 → BUDGET_CAP", rec == APNEA_BUDGET_CAP, reason)

    # Iteration cap
    rec, reason, early = _decide_apnea_v3(
        satisfied=False, trajectory=None,
        iteration=5, max_iterations=5,
        budget_remaining=0.5, budget_initial=1.0,
        ceiling_level=0,
    )
    ok &= _check("iter=max → BUDGET_CAP", rec == APNEA_BUDGET_CAP, reason)

    # Flat trajectory + iter>0 → PAUSE
    flat = TrajectoryDelta(delta_t=[0.5, 0.5], d_delta_dt=0.001, iteration=2)
    rec, reason, early = _decide_apnea_v3(
        satisfied=False, trajectory=flat,
        iteration=2, max_iterations=5,
        budget_remaining=0.5, budget_initial=1.0,
        ceiling_level=0,
    )
    ok &= _check("flat + iter>0 → PAUSE", rec == APNEA_PAUSE, reason)

    # Default
    rec, reason, early = _decide_apnea_v3(
        satisfied=False, trajectory=None,
        iteration=2, max_iterations=5,
        budget_remaining=0.5, budget_initial=1.0,
        ceiling_level=0,
    )
    ok &= _check("default not-satisfied → FIRE", rec == APNEA_FIRE, reason)

    return ok


# ---------------------------------------------------------------------------
# Test: Q7 both-clause logic (Read C)
# ---------------------------------------------------------------------------

def test_q7_clause_logic():
    print("\n── Q7 production_offset both-clauses required (Read C) ──")
    ok = True

    # Helper: build a parsed result that passes everything EXCEPT Q7 variants
    def parsed_with_q7(pre_pos: bool, risk: bool, q7_answered: bool = True):
        per_q = {}
        for k in BOUNDARY_QUESTIONS_V3.keys():
            if k == Q7_KEY:
                continue
            per_q[k] = {"answered": True, "quality": 0.85, "gaps": [], "notes": ""}
        # Add labor maps for v2 keys
        for k in ("operational_cost_per_function", "leverage_points", "collapse_points"):
            per_q[k]["function_to_role_map"] = [
                {"function": "test", "role": "test", "labor_separation": "test"}
            ]
        per_q[Q7_KEY] = {
            "answered": q7_answered,
            "quality":  0.85 if q7_answered else 0.0,
            "gaps":     [],
            "notes":    "",
            "clauses":  {"pre_positioning": pre_pos, "risk_model": risk},
        }
        return {
            "per_question": per_q,
            "next_pilot_move_chain_visible": True,
            "role_coverage_ok":              True,
            "trajectory_evidence_in_text":   True,
            "satisfied":                     True,  # LLM claims it — strict gate will recompute
            "score":                         0.85,
            "weakest_link":                  None,
            "missing_density_for":           [],
            "reason":                        "test",
            "production_offset_clauses":     {"pre_positioning": pre_pos, "risk_model": risk},
        }

    # Both clauses present → satisfied
    r = _result_from_parsed_v3(
        parsed=parsed_with_q7(True, True),
        raw="", elapsed=0.0, provider="test",
        trajectory=None, iteration=2, max_iterations=5,
        budget_remaining=0.5, budget_initial=1.0,
        raised_goal_active=True, ceiling_level=1,
    )
    ok &= _check("both clauses → production_offset_ok=True",
                 r.production_offset_ok is True)
    ok &= _check("both clauses → satisfied=True", r.satisfied is True)

    # Only pre_positioning → NOT satisfied
    r = _result_from_parsed_v3(
        parsed=parsed_with_q7(True, False),
        raw="", elapsed=0.0, provider="test",
        trajectory=None, iteration=2, max_iterations=5,
        budget_remaining=0.5, budget_initial=1.0,
        raised_goal_active=True, ceiling_level=1,
    )
    ok &= _check("only pre_positioning → production_offset_ok=False",
                 r.production_offset_ok is False)
    ok &= _check("only pre_positioning → satisfied=False",
                 r.satisfied is False)
    ok &= _check("only pre_positioning → weakest is Q7",
                 r.weakest_link == Q7_KEY)

    # Only risk_model → NOT satisfied
    r = _result_from_parsed_v3(
        parsed=parsed_with_q7(False, True),
        raw="", elapsed=0.0, provider="test",
        trajectory=None, iteration=2, max_iterations=5,
        budget_remaining=0.5, budget_initial=1.0,
        raised_goal_active=True, ceiling_level=1,
    )
    ok &= _check("only risk_model → production_offset_ok=False",
                 r.production_offset_ok is False)
    ok &= _check("only risk_model → satisfied=False", r.satisfied is False)

    # Neither clause → NOT satisfied + per-clause gaps reported
    r = _result_from_parsed_v3(
        parsed=parsed_with_q7(False, False),
        raw="", elapsed=0.0, provider="test",
        trajectory=None, iteration=2, max_iterations=5,
        budget_remaining=0.5, budget_initial=1.0,
        raised_goal_active=True, ceiling_level=1,
    )
    ok &= _check("neither clause → production_offset_ok=False",
                 r.production_offset_ok is False)
    q7_gaps = r.per_question.get(Q7_KEY, {}).get("gaps", [])
    ok &= _check("neither clause → gaps name both A and B",
                 any("clause A" in g for g in q7_gaps) and
                 any("clause B" in g for g in q7_gaps),
                 f"gaps={q7_gaps}")

    return ok


# ---------------------------------------------------------------------------
# Test: Q7 N/A when raised_goal_active=False
# ---------------------------------------------------------------------------

def test_q7_skipped_when_no_raise():
    print("\n── Q7 N/A when raised_goal_active=False ──")
    ok = True

    # Build parsed with all v2 questions passing
    per_q = {}
    for k in BOUNDARY_QUESTIONS_V3.keys():
        if k == Q7_KEY:
            continue
        per_q[k] = {"answered": True, "quality": 0.85, "gaps": [], "notes": ""}
    for k in ("operational_cost_per_function", "leverage_points", "collapse_points"):
        per_q[k]["function_to_role_map"] = [
            {"function": "test", "role": "test", "labor_separation": "test"}
        ]

    parsed = {
        "per_question": per_q,
        "next_pilot_move_chain_visible": True,
        "role_coverage_ok":              True,
        "trajectory_evidence_in_text":   True,
        "score":                         0.85,
        "weakest_link":                  None,
        "missing_density_for":           [],
        "reason":                        "no raise",
    }

    r = _result_from_parsed_v3(
        parsed=parsed,
        raw="", elapsed=0.0, provider="test",
        trajectory=None, iteration=4, max_iterations=5,
        budget_remaining=0.3, budget_initial=1.0,
        raised_goal_active=False, ceiling_level=0,
    )
    ok &= _check("no raise → satisfied=True without Q7", r.satisfied is True)
    ok &= _check("no raise → Q7 not in per_question", Q7_KEY not in r.per_question)
    ok &= _check("no raise → production_offset_ok=False (default)",
                 r.production_offset_ok is False)
    ok &= _check("no raise + late iter → apnea=SATISFIED",
                 r.apnea_recommendation == APNEA_SATISFIED,
                 r.apnea_reason)

    return ok


# ---------------------------------------------------------------------------
# Test: result serialization + summarize
# ---------------------------------------------------------------------------

def test_v3_serialization():
    print("\n── BoundaryResultV3 serialization ──")
    ok = True

    r = BoundaryResultV3(
        satisfied=True, score=0.88, weakest_link=None,
        missing_density_for=[],
        per_question={},
        next_pilot_move_chain_visible=True,
        reason="test",
        role_coverage_ok=True,
        apnea_recommendation=APNEA_RAISE_CEILING,
        apnea_reason="early convergence",
        iteration=1,
        raised_goal_active=False,  # first raise hasn't happened yet
        ceiling_level=0,
        early_satisfied=True,
        production_offset_ok=False,
        production_offset_clauses={"pre_positioning": False, "risk_model": False},
    )
    d = r.to_dict()
    ok &= _check("to_dict() returns dict", isinstance(d, dict))
    ok &= _check("includes raised_goal_active",     "raised_goal_active" in d)
    ok &= _check("includes ceiling_level",          "ceiling_level"      in d)
    ok &= _check("includes early_satisfied",        "early_satisfied"    in d)
    ok &= _check("includes production_offset_ok",   "production_offset_ok" in d)
    ok &= _check("includes production_offset_clauses",
                 "production_offset_clauses" in d)

    summary = summarize_v3(r)
    ok &= _check("summary mentions EARLY tag", "EARLY" in summary)
    ok &= _check("summary includes apnea state", APNEA_RAISE_CEILING in summary)

    return ok


# ---------------------------------------------------------------------------
# Test: v2/v3 coexistence
# ---------------------------------------------------------------------------

def test_v2_v3_coexistence():
    print("\n── v2/v3 coexistence ──")
    ok = True

    from src.pcr060_boundary_v2 import (
        BOUNDARY_QUESTIONS_V2,
        evaluate_v2,
        BoundaryResultV2,
    )
    from src.pcr060_boundary_v3 import (
        BOUNDARY_QUESTIONS_V3,
        evaluate_v3,
        BoundaryResultV3,
        Q7_KEY,
    )

    ok &= _check("v3 has all v2 questions",
                 all(k in BOUNDARY_QUESTIONS_V3 for k in BOUNDARY_QUESTIONS_V2))
    ok &= _check("v3 adds exactly Q7",
                 len(BOUNDARY_QUESTIONS_V3) == len(BOUNDARY_QUESTIONS_V2) + 1)
    ok &= _check("Q7 is in v3 question keys", Q7_KEY in BOUNDARY_QUESTIONS_V3)
    ok &= _check("Q7 is NOT in v2 question keys",
                 Q7_KEY not in BOUNDARY_QUESTIONS_V2)
    ok &= _check("v3 evaluate_v3 callable", callable(evaluate_v3))
    ok &= _check("v2 evaluate_v2 still callable (unchanged)", callable(evaluate_v2))

    return ok


def main():
    print("PCR-060a.3 — pure-logic test harness")

    suites = [
        ("escalation triggers",      test_escalation_triggers),
        ("v2 behaviour preserved",   test_v2_behavior_preserved),
        ("Q7 both clauses required", test_q7_clause_logic),
        ("Q7 N/A when no raise",     test_q7_skipped_when_no_raise),
        ("v3 serialization",         test_v3_serialization),
        ("v2/v3 coexistence",        test_v2_v3_coexistence),
    ]

    results = {}
    for name, fn in suites:
        try:
            results[name] = fn()
        except Exception as e:
            import traceback
            print(f"  ✗ SUITE EXCEPTION: {name}: {e}")
            traceback.print_exc()
            results[name] = False

    print("\n── SUMMARY ──")
    passed = sum(1 for v in results.values() if v)
    total  = len(results)
    for name, ok in results.items():
        icon = "✓" if ok else "✗"
        print(f"  {icon} {name}")
    print(f"\n  {passed}/{total} suites passed")

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
