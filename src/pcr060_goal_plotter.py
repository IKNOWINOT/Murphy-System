"""
PCR-060b — Goal Plotter

Producer for the Boundary-Condition Loop. PCR-060a/v2/v3 are the consumers.

Two callable pair, designed together so the loop driver can plug them
in interchangeably:

  1. project_goal(prompt, business_spec) -> GoalPlot
     Initial pass at iteration 0. Reads the prompt + business spec,
     projects an actualized success state, and plots R(t) — the reverse
     trajectory curve from goal back to present.

  2. raise_ceiling(prior_goal, achieved_iteration, achieved_score,
                   ceilings_so_far, business_spec) -> GoalPlot
     Called when PCR-060a v3 emits APNEA_RAISE_CEILING. Reads the prior
     goal + how-fast-we-got-there and projects a stretched goal that is
     plausibly reachable in remaining budget. Returns a new GoalPlot
     with a new R(t).

Pure callable: framework-free, no FastAPI, no DB writes. Only depends
on MurphyLLMProvider (lazy-imported) for the actual LLM calls.

When `llm=None` and no provider available, both callables return a
deterministic stub GoalPlot so test harnesses can run without network.

Spec: .agents/memory/pcr060_magnify_boundary_loop_spec.md (v3 addendum)
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

# Re-use the permissive JSON extractor from v1 — no need to duplicate
from src.pcr060_boundary_condition import _extract_json

LOG = logging.getLogger("murphy.pcr060.goal_plotter")


# ---------------------------------------------------------------------------
# Output type
# ---------------------------------------------------------------------------

@dataclass
class TrajectoryPoint:
    """One point on the R(t) reverse trajectory curve.

    R(t) is the path FROM goal BACK TO present. t=0 is the goal state;
    t=1.0 is the present state. Each point names what must be true at
    that intermediate state.
    """

    t:                   float
    """Normalized timeline position. 0.0 = goal, 1.0 = present."""

    state_name:          str
    """Short human-readable label for this intermediate state."""

    operational_targets: Dict[str, Any] = field(default_factory=dict)
    """Operational KPIs at this state (e.g. headcount, output/wk)."""

    money_ratio_targets: Dict[str, Any] = field(default_factory=dict)
    """Margin / unit-economics targets at this state."""

    role_skeleton:       List[str] = field(default_factory=list)
    """Org-chart roles that must exist by this point."""

    notes:               str = ""


@dataclass
class GoalPlot:
    """The output of the Goal Plotter.

    Includes:
      - The projected actualized success state
      - Operational + money-ratio targets at that state
      - The R(t) reverse trajectory curve (3-6 points typical)
      - Org-chart skeleton inferred for this business class
      - Ceiling metadata (level + parent goal, when escalated)
    """

    actualized_state:     str
    """One paragraph describing what 'success' looks like."""

    operational_targets:  Dict[str, Any] = field(default_factory=dict)
    money_ratio_targets:  Dict[str, Any] = field(default_factory=dict)
    subject_matter:       str = ""
    business_class:       str = ""

    r_curve:              List[TrajectoryPoint] = field(default_factory=list)
    """The reverse trajectory: goal -> ... -> present. 3-6 points."""

    role_skeleton:        List[str] = field(default_factory=list)
    """Roles required to operate this business at the goal state."""

    ceiling_level:        int = 0
    """0 = original goal. Increments on each raise_ceiling() call."""

    parent_goal:          Optional[str] = None
    """When ceiling_level > 0, the prior actualized_state we raised from."""

    rationale:            str = ""
    """LLM's stated reasoning for the goal projection / escalation."""

    raw_response:         str = ""
    latency_seconds:      float = 0.0
    provider:             str = "unknown"
    error:                Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

SYSTEM_PROMPT_PROJECT = (
    "You are a senior business strategist. Your job is to read a "
    "business intent (prompt + spec) and project what 'success' looks "
    "like as a concrete actualized state, then reverse-engineer the "
    "intermediate states between that goal and the present.\n"
    "\n"
    "You return ONLY a valid JSON object with the schema described. "
    "No markdown fences. No commentary outside the JSON.\n"
    "\n"
    "Be subject-matter-specific. Generic SaaS goals applied to a coffee "
    "roastery = FAIL. Anchor every number and role in the business's "
    "actual class and subject matter."
)

SYSTEM_PROMPT_RAISE = (
    "You are a senior business strategist evaluating whether and how to "
    "raise a goal that was met EARLIER than expected. The fact that "
    "the boundary condition was satisfied at iteration {iter}/{max} "
    "(score={score:.2f}) suggests the original goal under-projected what "
    "this business can actually achieve in the remaining budget.\n"
    "\n"
    "Raise the goal to a level that is:\n"
    "  - Materially more ambitious than the prior goal (not incremental)\n"
    "  - Plausibly reachable in the remaining budget given the "
    "    convergence speed shown\n"
    "  - Consistent with the same subject matter and business class\n"
    "  - Forcing the production curve to BOOM (capacity ramp must now "
    "    pre-position aggressively because demand will outpace baseline)\n"
    "\n"
    "Return ONLY a valid JSON object with the schema described. No "
    "markdown. No commentary outside the JSON."
)


# ---------------------------------------------------------------------------
# JSON schema strings
# ---------------------------------------------------------------------------

PROJECT_SCHEMA = (
    '{\n'
    '  "actualized_state":    "<one paragraph describing success>",\n'
    '  "operational_targets": {<keys named in subject-matter terms>: <numeric or short string>},\n'
    '  "money_ratio_targets": {"gross_margin": <0-1>, "contribution_margin": <0-1>, "operating_margin": <0-1>, ...},\n'
    '  "subject_matter":      "<echo from business_spec>",\n'
    '  "business_class":      "<echo from business_spec>",\n'
    '  "r_curve": [\n'
    '    {"t": 0.0, "state_name": "actualized goal",\n'
    '     "operational_targets": {...}, "money_ratio_targets": {...},\n'
    '     "role_skeleton": ["<role>", "<role>"], "notes": "..."},\n'
    '    {"t": 0.33, "state_name": "<intermediate state>", ...},\n'
    '    {"t": 0.66, "state_name": "<intermediate state>", ...},\n'
    '    {"t": 1.0, "state_name": "present", ...}\n'
    '  ],\n'
    '  "role_skeleton": ["<role 1>", "<role 2>", "..."],\n'
    '  "rationale":     "<one paragraph on why this is the right goal shape>"\n'
    '}'
)

RAISE_SCHEMA = (
    '{\n'
    '  "actualized_state":    "<one paragraph — RAISED goal>",\n'
    '  "operational_targets": {<materially-stretched targets>},\n'
    '  "money_ratio_targets": {<may stay similar or improve>},\n'
    '  "r_curve":             [<3-5 points from raised goal -> present>],\n'
    '  "role_skeleton":       [<may add new roles for boom>],\n'
    '  "rationale":           "<one paragraph — why this stretch is reachable and what the boom requires>"\n'
    '}'
)


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

def _build_project_prompt(prompt: str, business_spec: Dict[str, Any]) -> str:
    return (
        "=== USER PROMPT ===\n" + prompt[:4000]
        + "\n\n=== BUSINESS SPEC ===\n" + json.dumps(business_spec, indent=2)[:2000]
        + "\n\n=== TASK ===\n"
          "Project the actualized success state for this business in this "
          "subject matter. Then reverse-engineer a 3-6 point R(t) curve "
          "from the goal back to the present, naming what must be true "
          "at each intermediate state. Identify the org-chart skeleton "
          "(roles required) for the goal state.\n"
          "\n"
          "=== RETURN ONLY THIS JSON ===\n"
        + PROJECT_SCHEMA + "\n"
    )


def _build_raise_prompt(
    prior_goal:           GoalPlot,
    achieved_iteration:   int,
    max_iterations:       int,
    achieved_score:       float,
    ceilings_so_far:      int,
    business_spec:        Dict[str, Any],
) -> str:
    prior_serialized = json.dumps({
        "actualized_state":    prior_goal.actualized_state,
        "operational_targets": prior_goal.operational_targets,
        "money_ratio_targets": prior_goal.money_ratio_targets,
        "ceiling_level":       prior_goal.ceiling_level,
    }, indent=2)[:2500]

    return (
        "=== PRIOR GOAL (just satisfied) ===\n" + prior_serialized
        + "\n\n=== BUSINESS SPEC ===\n" + json.dumps(business_spec, indent=2)[:2000]
        + "\n\n=== CONVERGENCE STATS ===\n"
        + json.dumps({
            "achieved_at_iteration":  achieved_iteration,
            "max_iterations":         max_iterations,
            "iteration_fraction":     achieved_iteration / float(max_iterations) if max_iterations else 1.0,
            "achieved_score":         achieved_score,
            "ceilings_already_raised": ceilings_so_far,
        }, indent=2)
        + "\n\n=== TASK ===\n"
          "The prior goal was satisfied EARLIER than expected. Raise it.\n"
          "Project a materially more ambitious actualized state that is\n"
          "still plausibly reachable in remaining budget. Re-plot the\n"
          "R(t) curve from the raised goal back to present. The role\n"
          "skeleton may need new positions to handle the production\n"
          "boom that the raised demand will require.\n"
          "\n"
          "=== RETURN ONLY THIS JSON ===\n"
        + RAISE_SCHEMA + "\n"
    )


# ---------------------------------------------------------------------------
# Result builders
# ---------------------------------------------------------------------------

def _parse_r_curve(raw_curve: Any) -> List[TrajectoryPoint]:
    """Defensive parse of the r_curve list."""
    if not isinstance(raw_curve, list):
        return []
    points = []
    for entry in raw_curve[:8]:  # cap at 8 points
        if not isinstance(entry, dict):
            continue
        try:
            t = float(entry.get("t", 0.0))
        except (TypeError, ValueError):
            t = 0.0
        t = max(0.0, min(1.0, t))
        points.append(TrajectoryPoint(
            t=t,
            state_name=str(entry.get("state_name", ""))[:200],
            operational_targets=dict(entry.get("operational_targets") or {}),
            money_ratio_targets=dict(entry.get("money_ratio_targets") or {}),
            role_skeleton=[str(r)[:120] for r in (entry.get("role_skeleton") or [])[:10]],
            notes=str(entry.get("notes", ""))[:500],
        ))
    # Sort by t ascending (goal first)
    points.sort(key=lambda p: p.t)
    return points


def _stub_goal(
    prompt: str,
    business_spec: Dict[str, Any],
    error: str,
) -> GoalPlot:
    """Return a deterministic stub GoalPlot when LLM isn't available.

    The drill driver can still progress with a stub — the detector
    will reject low-quality deliverables, but at least the loop
    runs without crashing.
    """
    return GoalPlot(
        actualized_state=(
            "(stub) Operate " + str(business_spec.get("name", "this business"))
            + " profitably at modest scale in " + str(business_spec.get("subject_matter", "the stated subject matter")) + "."
        ),
        operational_targets={"output_per_week": "TBD", "headcount": "TBD"},
        money_ratio_targets={"gross_margin": 0.50, "operating_margin": 0.10},
        subject_matter=str(business_spec.get("subject_matter", "")),
        business_class=str(business_spec.get("business_class", "")),
        r_curve=[
            TrajectoryPoint(t=0.0, state_name="actualized goal (stub)", notes="LLM unavailable"),
            TrajectoryPoint(t=0.5, state_name="midpoint (stub)", notes="LLM unavailable"),
            TrajectoryPoint(t=1.0, state_name="present (stub)", notes="LLM unavailable"),
        ],
        role_skeleton=["Founder", "Operator"],
        ceiling_level=0,
        rationale="Stub goal because LLM was unavailable. Deliverable quality will be low.",
        error=error,
    )


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

def project_goal(
    prompt: str,
    business_spec: Dict[str, Any],
    *,
    llm=None,
    max_tokens: int = 3000,
    temperature: float = 0.4,
) -> GoalPlot:
    """Initial goal projection. Called once per dispatch, at iteration 0.

    Args:
        prompt:        User's stated intent.
        business_spec: {name, subject_matter, business_class, ...}.
        llm:           Override for testing. None = lazy-load
                       MurphyLLMProvider; if unavailable, returns stub.
        max_tokens:    LLM output cap.
        temperature:   0.4 — some creativity in goal-shape, but constrained.

    Returns:
        GoalPlot — never raises for normal LLM/parse failures.
    """

    if not prompt or not prompt.strip():
        return _stub_goal("", business_spec or {}, "empty_prompt")

    if not business_spec or not isinstance(business_spec, dict):
        return _stub_goal(prompt, {}, "missing_business_spec")

    if llm is None:
        try:
            from src.llm_provider import MurphyLLMProvider
            llm = MurphyLLMProvider()
        except Exception as e:
            LOG.exception("LLM provider instantiation failed")
            return _stub_goal(prompt, business_spec, "llm_unavailable:" + str(e))

    audit_prompt = _build_project_prompt(prompt, business_spec)

    t0 = time.time()
    try:
        resp = llm.complete(
            prompt=audit_prompt,
            system=SYSTEM_PROMPT_PROJECT,
            max_tokens=max_tokens,
            temperature=temperature,
            deterministic=False,
        )
    except Exception as e:
        LOG.exception("project_goal LLM call failed")
        stub = _stub_goal(prompt, business_spec, "llm_call_failed:" + str(e))
        stub.latency_seconds = time.time() - t0
        return stub

    elapsed = time.time() - t0
    raw      = (resp.content  or "") if resp else ""
    provider = (resp.provider or "unknown") if resp else "unknown"

    parsed = _extract_json(raw)
    if parsed is None:
        stub = _stub_goal(prompt, business_spec, "unparseable_json")
        stub.latency_seconds = elapsed
        stub.provider = provider
        stub.raw_response = raw[:5000]
        return stub

    return GoalPlot(
        actualized_state=str(parsed.get("actualized_state", ""))[:3000],
        operational_targets=dict(parsed.get("operational_targets") or {}),
        money_ratio_targets=dict(parsed.get("money_ratio_targets") or {}),
        subject_matter=str(parsed.get("subject_matter", business_spec.get("subject_matter", "")))[:200],
        business_class=str(parsed.get("business_class", business_spec.get("business_class", "")))[:200],
        r_curve=_parse_r_curve(parsed.get("r_curve")),
        role_skeleton=[str(r)[:120] for r in (parsed.get("role_skeleton") or [])[:20]],
        ceiling_level=0,
        parent_goal=None,
        rationale=str(parsed.get("rationale", ""))[:2000],
        raw_response=raw[:5000],
        latency_seconds=elapsed,
        provider=provider,
    )


def raise_ceiling(
    prior_goal:         GoalPlot,
    achieved_iteration: int,
    max_iterations:     int,
    achieved_score:     float,
    ceilings_so_far:    int,
    business_spec:      Dict[str, Any],
    *,
    llm=None,
    max_tokens:         int = 2500,
    temperature:        float = 0.5,
) -> GoalPlot:
    """Goal escalation pass. Called when v3 detector emits APNEA_RAISE_CEILING.

    Args:
        prior_goal:         The GoalPlot we just satisfied.
        achieved_iteration: Iteration at which satisfaction happened.
        max_iterations:     Original max (default 5).
        achieved_score:     Detector's score at satisfaction.
        ceilings_so_far:    How many raises have already happened (0+).
        business_spec:      Same as project_goal.
        llm:                Override for testing.
        max_tokens:         LLM output cap.
        temperature:        0.5 — escalation needs more creativity than initial.

    Returns:
        GoalPlot with ceiling_level = ceilings_so_far + 1, parent_goal
        set to prior_goal.actualized_state. Never raises.
    """

    if not isinstance(prior_goal, GoalPlot):
        return _stub_goal("", business_spec or {}, "invalid_prior_goal")

    if not business_spec or not isinstance(business_spec, dict):
        return _stub_goal("", {}, "missing_business_spec")

    if llm is None:
        try:
            from src.llm_provider import MurphyLLMProvider
            llm = MurphyLLMProvider()
        except Exception as e:
            LOG.exception("LLM provider instantiation failed")
            stub = _stub_goal("", business_spec, "llm_unavailable:" + str(e))
            stub.ceiling_level = ceilings_so_far + 1
            stub.parent_goal = prior_goal.actualized_state[:500]
            return stub

    audit_prompt = _build_raise_prompt(
        prior_goal=prior_goal,
        achieved_iteration=achieved_iteration,
        max_iterations=max_iterations,
        achieved_score=achieved_score,
        ceilings_so_far=ceilings_so_far,
        business_spec=business_spec,
    )

    # Format the system prompt with the actual stats
    system = SYSTEM_PROMPT_RAISE.format(
        iter=achieved_iteration,
        max=max_iterations,
        score=achieved_score,
    )

    t0 = time.time()
    try:
        resp = llm.complete(
            prompt=audit_prompt,
            system=system,
            max_tokens=max_tokens,
            temperature=temperature,
            deterministic=False,
        )
    except Exception as e:
        LOG.exception("raise_ceiling LLM call failed")
        stub = _stub_goal("", business_spec, "llm_call_failed:" + str(e))
        stub.ceiling_level = ceilings_so_far + 1
        stub.parent_goal = prior_goal.actualized_state[:500]
        stub.latency_seconds = time.time() - t0
        return stub

    elapsed  = time.time() - t0
    raw      = (resp.content  or "") if resp else ""
    provider = (resp.provider or "unknown") if resp else "unknown"

    parsed = _extract_json(raw)
    if parsed is None:
        stub = _stub_goal("", business_spec, "unparseable_json")
        stub.ceiling_level = ceilings_so_far + 1
        stub.parent_goal = prior_goal.actualized_state[:500]
        stub.latency_seconds = elapsed
        stub.provider = provider
        stub.raw_response = raw[:5000]
        return stub

    return GoalPlot(
        actualized_state=str(parsed.get("actualized_state", ""))[:3000],
        operational_targets=dict(parsed.get("operational_targets") or {}),
        money_ratio_targets=dict(parsed.get("money_ratio_targets") or prior_goal.money_ratio_targets),
        subject_matter=prior_goal.subject_matter,
        business_class=prior_goal.business_class,
        r_curve=_parse_r_curve(parsed.get("r_curve")),
        role_skeleton=[str(r)[:120] for r in (parsed.get("role_skeleton") or prior_goal.role_skeleton)[:25]],
        ceiling_level=ceilings_so_far + 1,
        parent_goal=prior_goal.actualized_state[:500],
        rationale=str(parsed.get("rationale", ""))[:2000],
        raw_response=raw[:5000],
        latency_seconds=elapsed,
        provider=provider,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def summarize(goal: GoalPlot) -> str:
    """One-line log summary."""
    icon = "✓" if not goal.error else "✗"
    ceiling = ""
    if goal.ceiling_level > 0:
        ceiling = " ceiling=L" + str(goal.ceiling_level)
    return (
        icon + " goal" + ceiling
        + " state='" + (goal.actualized_state[:60] + "...") + "'"
        + " r_curve=" + str(len(goal.r_curve)) + "pts"
        + " roles=" + str(len(goal.role_skeleton))
        + " provider=" + goal.provider
        + " lat=" + "{:.1f}s".format(goal.latency_seconds)
        + (" err=" + goal.error if goal.error else "")
    )
