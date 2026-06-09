#!/usr/bin/env python3
"""
PCR-060b — pure-logic tests for the Goal Plotter pair

Verifies:
  - project_goal with fake LLM returns well-formed GoalPlot
  - raise_ceiling honors ceiling_level + parent_goal lineage
  - r_curve parsing is defensive (handles bad input)
  - Stub fallback works when LLM unavailable
  - Empty/missing inputs handled gracefully

Uses an in-process FakeLLM so no network, no tokens spent.
Runs in milliseconds.
"""

from __future__ import annotations
import json
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.pcr060_goal_plotter import (
    project_goal, raise_ceiling, summarize,
    GoalPlot, TrajectoryPoint, _parse_r_curve, _stub_goal,
)


# ---------------------------------------------------------------------------
# FakeLLM — mimics MurphyLLMProvider.complete() signature
# ---------------------------------------------------------------------------

@dataclass
class FakeCompletion:
    content: str
    provider: str = "fake"
    success: bool = True
    error: str = None


class FakeLLM:
    """In-process LLM that returns canned JSON for tests."""
    def __init__(self, canned_json: str):
        self.canned_json = canned_json
        self.calls = []

    def complete(self, prompt, *, system, max_tokens, temperature, deterministic=False):
        self.calls.append({"prompt": prompt, "system": system, "max_tokens": max_tokens})
        return FakeCompletion(content=self.canned_json)


class CrashLLM:
    """LLM that raises on every call — tests fallback paths."""
    def complete(self, **kw):
        raise RuntimeError("simulated LLM crash")


# ---------------------------------------------------------------------------
# Canned LLM responses
# ---------------------------------------------------------------------------

CANNED_PROJECT_GOAL = json.dumps({
    "actualized_state": (
        "Northgrain Roastery operating at $1.2M ARR, 28% net margin, "
        "50/50 wholesale/DTC split, 35 active wholesale accounts, "
        "800 DTC subscribers, with consistent 86+ Q-grade quality."
    ),
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
    "subject_matter": "specialty coffee roasting + wholesale distribution",
    "business_class": "boutique food & beverage manufacturer",
    "r_curve": [
        {"t": 0.0, "state_name": "actualized goal",
         "operational_targets": {"bags_per_week": 200}, "money_ratio_targets": {"operating_margin": 0.28},
         "role_skeleton": ["Founder/Head Roaster", "Account Operations Lead", "DTC Coordinator", "Compliance & QC Lead"],
         "notes": "All four roles staffed, Loring S15 at design capacity"},
        {"t": 0.33, "state_name": "wholesale scale-up complete",
         "operational_targets": {"bags_per_week": 120, "wholesale_accounts": 20},
         "money_ratio_targets": {"operating_margin": 0.15},
         "role_skeleton": ["Founder/Head Roaster", "Account Operations Lead"],
         "notes": "First sales hire ramped"},
        {"t": 0.66, "state_name": "DTC subscription launched",
         "operational_targets": {"bags_per_week": 60, "DTC_subscribers": 200},
         "money_ratio_targets": {"operating_margin": -0.02},
         "role_skeleton": ["Founder/Head Roaster"],
         "notes": "Fulfillment workflow proven"},
        {"t": 1.0, "state_name": "present — pre-revenue",
         "operational_targets": {"bags_per_week": 0},
         "money_ratio_targets": {"operating_margin": -1.0},
         "role_skeleton": ["Founder/Head Roaster"],
         "notes": "Equipment in place, no customers yet"},
    ],
    "role_skeleton": ["Founder/Head Roaster", "Account Operations Lead", "DTC Coordinator", "Compliance & QC Lead"],
    "rationale": "Goal calibrated to PNW specialty market: 200 bags/wk on a Loring S15 is sustained capacity, 35 wholesale accounts is the route density a single Ops Lead can serve, 800 DTC subs gives the freshness flow-rate predictability the business needs.",
})

CANNED_RAISE_GOAL = json.dumps({
    "actualized_state": (
        "Northgrain at $3.5M ARR, 30% net margin, opening a satellite "
        "roastery in Seattle to handle the demand boom that the early "
        "pilot proved out, with 70 wholesale accounts and 2,200 DTC "
        "subscribers across two regional hubs."
    ),
    "operational_targets": {
        "bags_per_week": 600,
        "wholesale_accounts": 70,
        "DTC_subscribers": 2200,
        "roasting_sites": 2,
    },
    "money_ratio_targets": {
        "gross_margin": 0.63,
        "operating_margin": 0.30,
    },
    "r_curve": [
        {"t": 0.0, "state_name": "raised goal — dual-hub operation",
         "role_skeleton": ["Founder/Head Roaster", "Account Operations Lead",
                           "DTC Coordinator", "Compliance & QC Lead",
                           "Satellite Site Lead", "Capacity Planning Owner"]},
        {"t": 0.5, "state_name": "Seattle site soft-launched"},
        {"t": 1.0, "state_name": "present — original goal just hit"},
    ],
    "role_skeleton": ["Founder/Head Roaster", "Account Operations Lead",
                      "DTC Coordinator", "Compliance & QC Lead",
                      "Satellite Site Lead", "Capacity Planning Owner"],
    "rationale": "Convergence at iteration 2/5 with budget headroom means the original ceiling was 2-3x under-projected. Stretch to a dual-hub model because the production curve needs to boom: pre-position the second Loring + Seattle lease 4 months before the demand wave, hire Capacity Planning Owner to watch the ramp.",
})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BUSINESS = {
    "name": "Northgrain Roastery",
    "subject_matter": "specialty coffee roasting + wholesale distribution",
    "business_class": "boutique food & beverage manufacturer",
}


def _check(name, cond, detail=""):
    icon = "✓" if cond else "✗"
    line = f"  {icon} {name}"
    if detail:
        line += f"   ({detail[:120]})"
    print(line)
    return cond


# ---------------------------------------------------------------------------
# Test suites
# ---------------------------------------------------------------------------

def test_project_goal_happy_path():
    print("\n── project_goal happy path ──")
    ok = True
    llm = FakeLLM(CANNED_PROJECT_GOAL)

    g = project_goal("Build a specialty coffee roastery", BUSINESS, llm=llm)

    ok &= _check("returns GoalPlot", isinstance(g, GoalPlot))
    ok &= _check("error is None", g.error is None)
    ok &= _check("ceiling_level=0 (original)", g.ceiling_level == 0)
    ok &= _check("parent_goal is None", g.parent_goal is None)
    ok &= _check("actualized_state populated (>50 chars)", len(g.actualized_state) > 50)
    ok &= _check("subject_matter set", "specialty coffee" in g.subject_matter)
    ok &= _check("r_curve has 4 points", len(g.r_curve) == 4)
    ok &= _check("r_curve sorted by t (goal first, present last)",
                 g.r_curve[0].t == 0.0 and g.r_curve[-1].t == 1.0)
    ok &= _check("role_skeleton has 4 roles", len(g.role_skeleton) == 4)
    ok &= _check("operational_targets contains bags_per_week",
                 "bags_per_week" in g.operational_targets)
    ok &= _check("money_ratio_targets contains operating_margin",
                 "operating_margin" in g.money_ratio_targets)
    ok &= _check("LLM was called exactly once", len(llm.calls) == 1)
    return ok


def test_raise_ceiling_happy_path():
    print("\n── raise_ceiling happy path ──")
    ok = True

    # First, build a prior goal
    prior = project_goal("test", BUSINESS, llm=FakeLLM(CANNED_PROJECT_GOAL))
    ok &= _check("prior goal at ceiling 0", prior.ceiling_level == 0)

    # Now raise
    llm = FakeLLM(CANNED_RAISE_GOAL)
    raised = raise_ceiling(
        prior_goal=prior,
        achieved_iteration=2, max_iterations=5,
        achieved_score=0.82, ceilings_so_far=0,
        business_spec=BUSINESS, llm=llm,
    )

    ok &= _check("raised ceiling_level=1", raised.ceiling_level == 1)
    ok &= _check("parent_goal set to prior actualized_state",
                 raised.parent_goal is not None and "Northgrain" in (raised.parent_goal or ""))
    ok &= _check("raised goal mentions dual-hub or boom or stretch",
                 "dual" in raised.actualized_state.lower() or
                 "satellite" in raised.actualized_state.lower() or
                 "boom" in raised.rationale.lower())
    ok &= _check("raised goal has more roles than prior",
                 len(raised.role_skeleton) > len(prior.role_skeleton))
    ok &= _check("raised goal preserves subject_matter",
                 raised.subject_matter == prior.subject_matter)
    ok &= _check("LLM was called once for raise", len(llm.calls) == 1)

    # Chain another raise
    raised2 = raise_ceiling(
        prior_goal=raised,
        achieved_iteration=1, max_iterations=5,
        achieved_score=0.88, ceilings_so_far=1,
        business_spec=BUSINESS, llm=FakeLLM(CANNED_RAISE_GOAL),
    )
    ok &= _check("second raise → ceiling_level=2", raised2.ceiling_level == 2)
    ok &= _check("second raise parent_goal points at first raise",
                 raised2.parent_goal == raised.actualized_state[:500])
    return ok


def test_r_curve_defensive_parsing():
    print("\n── r_curve defensive parsing ──")
    ok = True

    # Bad input: not a list
    pts = _parse_r_curve("not a list")
    ok &= _check("non-list returns empty", pts == [])

    # Bad input: list of non-dicts
    pts = _parse_r_curve(["string", 42, None])
    ok &= _check("list of non-dicts returns empty", pts == [])

    # Mixed: some valid, some not
    pts = _parse_r_curve([
        {"t": 0.5, "state_name": "midpoint"},
        "junk",
        {"t": 0.0, "state_name": "goal"},
        {"t": 1.0, "state_name": "present"},
    ])
    ok &= _check("mixed input yields 3 valid points", len(pts) == 3)
    ok &= _check("auto-sorted by t (0.0, 0.5, 1.0)",
                 [p.t for p in pts] == [0.0, 0.5, 1.0])

    # Out-of-range t gets clamped
    pts = _parse_r_curve([{"t": -0.5, "state_name": "a"}, {"t": 2.0, "state_name": "b"}])
    ok &= _check("negative t clamped to 0.0", pts[0].t == 0.0)
    ok &= _check("t > 1.0 clamped to 1.0", pts[1].t == 1.0)

    # Cap at 8 points
    big = [{"t": i / 20.0, "state_name": f"s{i}"} for i in range(20)]
    pts = _parse_r_curve(big)
    ok &= _check("capped at 8 points", len(pts) == 8)

    return ok


def test_stub_fallback():
    print("\n── stub fallback paths ──")
    ok = True

    # Crashing LLM → stub
    g = project_goal("test", BUSINESS, llm=CrashLLM())
    ok &= _check("crash → returns GoalPlot (not exception)", isinstance(g, GoalPlot))
    ok &= _check("crash → error is set", g.error is not None)
    ok &= _check("crash → still has stub r_curve", len(g.r_curve) > 0)
    ok &= _check("crash → ceiling_level still 0", g.ceiling_level == 0)

    # Crash on raise → stub with ceiling bumped
    prior = project_goal("test", BUSINESS, llm=FakeLLM(CANNED_PROJECT_GOAL))
    raised = raise_ceiling(prior, 2, 5, 0.8, 0, BUSINESS, llm=CrashLLM())
    ok &= _check("crash on raise → ceiling_level=1", raised.ceiling_level == 1)
    ok &= _check("crash on raise → parent_goal preserved",
                 raised.parent_goal is not None)
    ok &= _check("crash on raise → error set",
                 raised.error is not None and "llm" in raised.error.lower())

    return ok


def test_input_validation():
    print("\n── input validation ──")
    ok = True

    # Empty prompt
    g = project_goal("", BUSINESS, llm=FakeLLM(CANNED_PROJECT_GOAL))
    ok &= _check("empty prompt → stub w/ error", g.error == "empty_prompt")

    # Missing business_spec
    g = project_goal("test", None, llm=FakeLLM(CANNED_PROJECT_GOAL))
    ok &= _check("None business_spec → stub w/ error", g.error == "missing_business_spec")

    g = project_goal("test", "not a dict", llm=FakeLLM(CANNED_PROJECT_GOAL))
    ok &= _check("non-dict business_spec → stub w/ error",
                 g.error == "missing_business_spec")

    # Raise with non-GoalPlot prior
    raised = raise_ceiling("not a goalplot", 2, 5, 0.8, 0, BUSINESS,
                           llm=FakeLLM(CANNED_RAISE_GOAL))
    ok &= _check("invalid prior_goal → stub w/ error",
                 raised.error == "invalid_prior_goal")

    return ok


def test_summarize():
    print("\n── summarize() ──")
    ok = True

    g = project_goal("test", BUSINESS, llm=FakeLLM(CANNED_PROJECT_GOAL))
    s = summarize(g)
    ok &= _check("summary returns string", isinstance(s, str))
    ok &= _check("summary mentions r_curve count", "r_curve=4pts" in s)
    ok &= _check("summary mentions roles", "roles=4" in s)

    # With ceiling
    raised = raise_ceiling(g, 2, 5, 0.82, 0, BUSINESS, llm=FakeLLM(CANNED_RAISE_GOAL))
    s2 = summarize(raised)
    ok &= _check("raised summary includes ceiling tag", "ceiling=L1" in s2)

    return ok


def main():
    print("PCR-060b — pure-logic test harness")

    suites = [
        ("project_goal happy path",    test_project_goal_happy_path),
        ("raise_ceiling happy path",   test_raise_ceiling_happy_path),
        ("r_curve defensive parsing",  test_r_curve_defensive_parsing),
        ("stub fallback paths",        test_stub_fallback),
        ("input validation",           test_input_validation),
        ("summarize()",                test_summarize),
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
