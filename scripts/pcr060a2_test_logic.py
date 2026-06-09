#!/usr/bin/env python3
"""
PCR-060a.2 — pure-logic tests (no LLM required)

Verifies:
  - TrajectoryDelta math (converging / converged / flatlining)
  - _decide_apnea routes correctly through all branches
  - BoundaryResultV2 serializes cleanly
  - Module imports cleanly and is forward-compatible with v1

Runs in milliseconds. Safe to run anywhere with Python + the v1/v2 modules.
"""

from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.pcr060_boundary_v2 import (
    TrajectoryDelta, BoundaryResultV2,
    APNEA_FIRE, APNEA_PAUSE, APNEA_SATISFIED, APNEA_BUDGET_CAP,
    _decide_apnea, summarize_v2,
)


def _check(name: str, cond: bool, detail: str = "") -> bool:
    icon = "✓" if cond else "✗"
    line = f"  {icon} {name}"
    if detail:
        line += f"   ({detail})"
    print(line)
    return cond


def test_trajectory_math():
    print("\n── TrajectoryDelta math ──")
    ok = True

    # Empty delta — no signal
    t = TrajectoryDelta()
    ok &= _check("empty.converging() is False", t.converging() is False)
    ok &= _check("empty.converged() is False",  t.converged()  is False)
    ok &= _check("empty.flatlining() is False", t.flatlining() is False)

    # Closing curves — derivative negative
    t = TrajectoryDelta(
        f_t=[0.1, 0.2, 0.3, 0.4],
        r_t=[1.0, 0.7, 0.5, 0.42],
        delta_t=[0.9, 0.5, 0.2, 0.02],
        d_delta_dt=-0.18,
        tolerance=0.10,
        iteration=4,
    )
    ok &= _check("closing.converging() is True", t.converging() is True)
    ok &= _check("closing.converged() is True (last delta 0.02 < tol 0.10)", t.converged() is True)
    ok &= _check("closing.flatlining() is False", t.flatlining() is False)

    # Diverging curves — derivative positive
    t = TrajectoryDelta(
        f_t=[0.1, 0.2],
        r_t=[0.5, 0.9],
        delta_t=[0.4, 0.7],
        d_delta_dt=0.3,
        tolerance=0.10,
        iteration=2,
    )
    ok &= _check("diverging.converging() is False", t.converging() is False)

    # Flatlining — derivative near zero
    t = TrajectoryDelta(
        delta_t=[0.5, 0.5, 0.5],
        d_delta_dt=0.001,
        iteration=3,
    )
    ok &= _check("flat.flatlining() is True (|d| < 0.01)", t.flatlining() is True)

    return ok


def test_apnea_decisions():
    print("\n── _decide_apnea branches ──")
    ok = True

    # Branch 1: satisfied → exit
    rec, reason = _decide_apnea(
        satisfied=True, trajectory=None, iteration=2,
        max_iterations=5, budget_remaining=0.5,
    )
    ok &= _check("satisfied → APNEA_SATISFIED", rec == APNEA_SATISFIED, reason)

    # Branch 2: budget cap
    rec, reason = _decide_apnea(
        satisfied=False, trajectory=None, iteration=2,
        max_iterations=5, budget_remaining=0.0,
    )
    ok &= _check("budget=0 → APNEA_BUDGET_CAP", rec == APNEA_BUDGET_CAP, reason)

    # Branch 3: iteration cap
    rec, reason = _decide_apnea(
        satisfied=False, trajectory=None, iteration=5,
        max_iterations=5, budget_remaining=0.5,
    )
    ok &= _check("iter=max → APNEA_BUDGET_CAP", rec == APNEA_BUDGET_CAP, reason)

    # Branch 4: flatlining + iteration > 0 → PAUSE
    flat = TrajectoryDelta(
        delta_t=[0.5, 0.5], d_delta_dt=0.001, iteration=2,
    )
    rec, reason = _decide_apnea(
        satisfied=False, trajectory=flat, iteration=2,
        max_iterations=5, budget_remaining=0.5,
    )
    ok &= _check("flat + iter>0 → APNEA_PAUSE", rec == APNEA_PAUSE, reason)

    # Branch 5: flatlining BUT iter=0 → FIRE (no flat-detection at start)
    rec, reason = _decide_apnea(
        satisfied=False, trajectory=flat, iteration=0,
        max_iterations=5, budget_remaining=0.5,
    )
    ok &= _check("flat + iter=0 → APNEA_FIRE", rec == APNEA_FIRE, reason)

    # Branch 6: converging but not satisfied → FIRE
    closing = TrajectoryDelta(
        delta_t=[0.5, 0.3, 0.2], d_delta_dt=-0.15, iteration=3,
    )
    rec, reason = _decide_apnea(
        satisfied=False, trajectory=closing, iteration=3,
        max_iterations=5, budget_remaining=0.5,
    )
    ok &= _check("closing not-satisfied → APNEA_FIRE", rec == APNEA_FIRE, reason)

    # Branch 7: no trajectory data → FIRE (default)
    rec, reason = _decide_apnea(
        satisfied=False, trajectory=None, iteration=2,
        max_iterations=5, budget_remaining=0.5,
    )
    ok &= _check("no trajectory → APNEA_FIRE", rec == APNEA_FIRE, reason)

    return ok


def test_result_serialization():
    print("\n── BoundaryResultV2 serialization ──")
    ok = True

    r = BoundaryResultV2(
        satisfied=False, score=0.42, weakest_link="leverage_points",
        missing_density_for=["lever-X drill"],
        per_question={
            "operational_cost_per_function": {"answered": True, "quality": 0.8, "gaps": [], "notes": ""},
        },
        next_pilot_move_chain_visible=False,
        reason="test",
        function_to_role_map={"operational_cost_per_function": []},
        role_coverage_ok=False,
        trajectory_converging=False,
        apnea_recommendation=APNEA_FIRE,
        apnea_reason="weakest is leverage_points",
        iteration=1,
    )
    d = r.to_dict()
    ok &= _check("to_dict() returns dict", isinstance(d, dict))
    ok &= _check("includes apnea_recommendation", "apnea_recommendation" in d)
    ok &= _check("includes function_to_role_map", "function_to_role_map" in d)
    ok &= _check("includes trajectory_converging",  "trajectory_converging"  in d)

    summary = summarize_v2(r)
    ok &= _check("summarize_v2() returns string", isinstance(summary, str) and len(summary) > 20)
    ok &= _check("summary contains apnea token", APNEA_FIRE in summary)

    return ok


def test_v1_v2_coexistence():
    print("\n── v1/v2 coexistence ──")
    ok = True

    from src.pcr060_boundary_condition import (
        evaluate, BoundaryResult, BOUNDARY_QUESTIONS, QUESTION_KEYS
    )
    from src.pcr060_boundary_v2 import (
        BOUNDARY_QUESTIONS as V2_INHERITED,
        BOUNDARY_QUESTIONS_V2,
        QUESTION_KEYS as V2_KEYS,
    )

    ok &= _check("v2 re-exports v1 BOUNDARY_QUESTIONS", BOUNDARY_QUESTIONS is V2_INHERITED)
    ok &= _check("v2 question keys match v1 (same 6)", set(QUESTION_KEYS) == set(V2_KEYS))
    ok &= _check("v2 questions extend Q1", len(BOUNDARY_QUESTIONS_V2["operational_cost_per_function"]) > len(BOUNDARY_QUESTIONS["operational_cost_per_function"]))
    ok &= _check("v2 questions extend Q3", len(BOUNDARY_QUESTIONS_V2["leverage_points"]) > len(BOUNDARY_QUESTIONS["leverage_points"]))
    ok &= _check("v2 questions extend Q5", len(BOUNDARY_QUESTIONS_V2["collapse_points"]) > len(BOUNDARY_QUESTIONS["collapse_points"]))

    return ok


def main():
    print("PCR-060a.2 — pure-logic test harness")

    suites = [
        ("trajectory math",        test_trajectory_math),
        ("apnea decisions",        test_apnea_decisions),
        ("result serialization",   test_result_serialization),
        ("v1/v2 coexistence",      test_v1_v2_coexistence),
    ]

    results = {}
    for name, fn in suites:
        try:
            results[name] = fn()
        except Exception as e:
            print(f"  ✗ SUITE EXCEPTION: {name}: {e}")
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
