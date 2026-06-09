"""
PCR-060a.2 — Boundary-Condition Detector v2

Extends PCR-060a v1 with:
  1. Labor-to-role mapping per question (Q1/Q3/Q5)
  2. Trajectory delta inputs (F(t), R(t), dDelta/dt) for convergence grading
  3. Apnea-state recommendation output for the drill loop driver

This module IMPORTS v1 (`src.pcr060_boundary_condition`) and extends it.
Existing v1 callers keep working through the re-exports below; new
v2 callers (PCR-060i drill driver) use the v2 entry point.

The v2 detector is forward-compatible: when trajectory inputs are not
provided, it grades against the 6 questions only (v1 behavior).

APNEA semantics (q1 confirmed default = pause-and-measure):
  - We commit to the next direction (the chosen weakest link) but do
    NOT re-fire immediately when the trajectory derivative is flat.
  - We pause one cycle for the trajectory plotter to update against the
    latest pass, THEN re-fire. This prevents thrashing between
    weakest-links across passes and avoids taking a derivative
    mid-mutation.
  - The pause IS the "calculus apnea" — derivative is taken at a
    stable point, not mid-flight.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple

# Re-export v1 symbols so callers can use either entry point
from src.pcr060_boundary_condition import (
    BoundaryResult,
    BOUNDARY_QUESTIONS,
    QUESTION_KEYS,
    _extract_json,
    SYSTEM_PROMPT as V1_SYSTEM_PROMPT,
    summarize as summarize_v1,
)

LOG = logging.getLogger("murphy.pcr060.boundary_v2")


# ---------------------------------------------------------------------------
# Trajectory delta input
# ---------------------------------------------------------------------------

@dataclass
class TrajectoryDelta:
    """Convergence math from the Trajectory Plotter (PCR-060e, future).

    All fields optional — if Plotter hasn't run yet (iteration 0),
    callers pass None and the detector skips trajectory grading.

    Schema designed so iteration 0..N can be tracked over time;
    the detector only needs the current and one-prior delta to compute
    derivative sign.
    """

    f_t:         List[float] = field(default_factory=list)
    """Forward trajectory samples — pilot from prompt's problem surface."""

    r_t:         List[float] = field(default_factory=list)
    """Reverse trajectory samples — pilot from goal's solution surface."""

    delta_t:     List[float] = field(default_factory=list)
    """|F(t) - R(t)| per iteration. Must be non-negative."""

    d_delta_dt:  Optional[float] = None
    """Last-two-iteration derivative. Negative = still converging (good)."""

    tolerance:   float = 0.10
    """delta(N) < tolerance to declare convergence. Default 10% gap."""

    iteration:   int = 0
    """Current iteration number (0 = pre-loop)."""

    def converging(self) -> bool:
        """True if curves are still closing the gap."""
        if self.d_delta_dt is None:
            return False
        return self.d_delta_dt < 0.0

    def converged(self) -> bool:
        """True if curves have met within tolerance."""
        if not self.delta_t:
            return False
        return self.delta_t[-1] < self.tolerance

    def flatlining(self) -> bool:
        """True if derivative has gone flat — apnea trigger."""
        if self.d_delta_dt is None:
            return False
        return abs(self.d_delta_dt) < 0.01


# ---------------------------------------------------------------------------
# Apnea constants — drill-loop reads these
# ---------------------------------------------------------------------------

APNEA_FIRE          = "fire_again"
APNEA_PAUSE         = "pause_and_measure"
APNEA_SATISFIED     = "satisfied"
APNEA_BUDGET_CAP    = "budget_cap_reached"


# ---------------------------------------------------------------------------
# v2 result type
# ---------------------------------------------------------------------------

@dataclass
class BoundaryResultV2:
    """Extended boundary result — superset of v1 BoundaryResult."""

    # v1 fields
    satisfied:                       bool
    score:                           float
    weakest_link:                    Optional[str]
    missing_density_for:             List[str]
    per_question:                    Dict[str, Dict[str, Any]]
    next_pilot_move_chain_visible:   bool
    reason:                          str
    raw_response:                    str = ""
    latency_seconds:                 float = 0.0
    provider:                        str = "unknown"
    error:                           Optional[str] = None

    # v2 additions
    function_to_role_map:            Dict[str, List[Dict[str, str]]] = field(default_factory=dict)
    """Per-question labor mapping (Q1/Q3/Q5 only)."""

    role_coverage_ok:                bool = False
    trajectory_converging:           bool = False
    trajectory_converged:            bool = False
    trajectory_flatlining:           bool = False
    trajectory_delta_last:           Optional[float] = None
    trajectory_d_delta_dt:           Optional[float] = None
    apnea_recommendation:            str = APNEA_FIRE
    apnea_reason:                    str = ""
    iteration:                       int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# v2 question text — labor mapping added to Q1/Q3/Q5
# ---------------------------------------------------------------------------

BOUNDARY_QUESTIONS_V2 = dict(BOUNDARY_QUESTIONS)

BOUNDARY_QUESTIONS_V2["operational_cost_per_function"] = (
    BOUNDARY_QUESTIONS_V2["operational_cost_per_function"]
    + " ALSO: each function MUST be mapped to a named role with explicit "
    "labor separation (what they own, what they hand off, who they hand off to). "
    "An operational cost without a named owner = FAIL."
)

BOUNDARY_QUESTIONS_V2["leverage_points"] = (
    BOUNDARY_QUESTIONS_V2["leverage_points"]
    + " ALSO: each leverage point MUST name the role(s) responsible for pulling that lever. "
    "Lever without an owner = FAIL."
)

BOUNDARY_QUESTIONS_V2["collapse_points"] = (
    BOUNDARY_QUESTIONS_V2["collapse_points"]
    + " ALSO: each collapse point MUST name the role responsible for watching the early signal. "
    "Risk without a watcher = FAIL."
)


# ---------------------------------------------------------------------------
# v2 system prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT_V2 = (
    V1_SYSTEM_PROMPT
    + "\n\nADDITIONAL v2 REQUIREMENTS:\n"
    "  - Every operational function, leverage point, and collapse point in the\n"
    "    deliverable MUST be mapped to a named org-chart role with labor\n"
    "    separation stated. Generic 'we will...' without a named owner = FAIL.\n"
    "  - You return a function_to_role_map for Q1/Q3/Q5 with that mapping.\n"
    "  - If trajectory_delta is supplied, you also grade whether the deliverable\n"
    "    contains evidence of the F(t)<->R(t) convergence (i.e. the next-pilot-move\n"
    "    explicitly cites how it closes the gap between forward and reverse\n"
    "    trajectories). If trajectory_delta is null, skip this grading.\n"
)


# ---------------------------------------------------------------------------
# v2 prompt builder
# ---------------------------------------------------------------------------

V2_SCHEMA_BLOCK = (
    '{\n'
    '  "per_question": {\n'
    '    "operational_cost_per_function": {\n'
    '      "answered": bool, "quality": 0.0-1.0,\n'
    '      "gaps": ["..."], "notes": "...",\n'
    '      "function_to_role_map": [\n'
    '        {"function": "...", "role": "...", "labor_separation": "...",\n'
    '         "cost_per_unit": "...", "cost_basis": "..."}\n'
    '      ]\n'
    '    },\n'
    '    "unit_economics_at_scale": {\n'
    '      "answered": bool, "quality": 0.0-1.0, "gaps": ["..."], "notes": "..."\n'
    '    },\n'
    '    "leverage_points": {\n'
    '      "answered": bool, "quality": 0.0-1.0, "gaps": ["..."], "notes": "...",\n'
    '      "function_to_role_map": [\n'
    '        {"function": "<lever>", "role": "<owner>", "labor_separation": "..."}\n'
    '      ]\n'
    '    },\n'
    '    "attractors": {\n'
    '      "answered": bool, "quality": 0.0-1.0, "gaps": ["..."], "notes": "..."\n'
    '    },\n'
    '    "collapse_points": {\n'
    '      "answered": bool, "quality": 0.0-1.0, "gaps": ["..."], "notes": "...",\n'
    '      "function_to_role_map": [\n'
    '        {"function": "<collapse mode>", "role": "<watcher>", "labor_separation": "..."}\n'
    '      ]\n'
    '    },\n'
    '    "next_pilot_move_chain_visible": {\n'
    '      "answered": bool, "quality": 0.0-1.0, "gaps": ["..."], "notes": "..."\n'
    '    }\n'
    '  },\n'
    '  "next_pilot_move_chain_visible": bool,\n'
    '  "role_coverage_ok":              bool,\n'
    '  "trajectory_evidence_in_text":   bool,\n'
    '  "satisfied":                     bool,\n'
    '  "score":                         0.0-1.0,\n'
    '  "weakest_link":                  "<key or null>",\n'
    '  "missing_density_for":           ["<topic for next pass>"],\n'
    '  "reason":                        "<one paragraph>"\n'
    '}'
)


def _build_audit_prompt_v2(
    deliverable: str,
    business_spec: Dict[str, Any],
    goal_plot: Optional[Dict[str, Any]] = None,
    trajectory_delta: Optional[TrajectoryDelta] = None,
) -> str:
    """v2 audit prompt — adds labor map + trajectory blocks."""

    questions_block = "\n\n".join(
        "  Q" + str(i + 1) + ". " + key + "\n     " + text
        for i, (key, text) in enumerate(BOUNDARY_QUESTIONS_V2.items())
    )

    business_block = json.dumps(business_spec, indent=2)[:2000]
    goal_block = (
        json.dumps(goal_plot, indent=2)[:1500]
        if goal_plot else "(no goal plot provided)"
    )

    if trajectory_delta is not None:
        traj_block = json.dumps({
            "F_t":       trajectory_delta.f_t[-5:],
            "R_t":       trajectory_delta.r_t[-5:],
            "delta_t":   trajectory_delta.delta_t[-5:],
            "dDelta_dt": trajectory_delta.d_delta_dt,
            "tolerance": trajectory_delta.tolerance,
            "iteration": trajectory_delta.iteration,
        }, indent=2)
    else:
        traj_block = "(no trajectory delta — skip trajectory grading)"

    deliverable_block = deliverable[:12000]

    return (
        "=== BUSINESS SPEC ===\n" + business_block
        + "\n\n=== GOAL PLOT ===\n" + goal_block
        + "\n\n=== TRAJECTORY DELTA (forward/reverse pilot curves) ===\n" + traj_block
        + "\n\n=== DRAFT DELIVERABLE TO AUDIT ===\n" + deliverable_block
        + "\n\n=== AUDIT AGAINST 6 BOUNDARY-CONDITION QUESTIONS (v2) ===\n"
        + questions_block
        + "\n\n=== v2 DECISION RULES ===\n"
          "  - All v1 rules apply.\n"
          "  - role_coverage_ok = true ONLY if EVERY function/lever/collapse-mode\n"
          "    in the deliverable is mapped to a named role with labor separation.\n"
          "  - If trajectory_delta supplied, trajectory_evidence_in_text = true\n"
          "    ONLY if deliverable's next-pilot-move explicitly addresses closing\n"
          "    the forward/reverse trajectory gap.\n"
          "  - satisfied = (v1 satisfied) AND role_coverage_ok AND\n"
          "                (trajectory_delta is null OR trajectory_evidence_in_text)\n"
          "  - per_question[Q1/Q3/Q5].function_to_role_map must be populated when\n"
          "    answered=true. If missing, downgrade quality by 0.3.\n"
          "\n"
          "=== RETURN ONLY THIS JSON SCHEMA ===\n" + V2_SCHEMA_BLOCK + "\n"
    )


# ---------------------------------------------------------------------------
# Apnea decision logic
# ---------------------------------------------------------------------------

def _decide_apnea(
    satisfied:         bool,
    trajectory:        Optional[TrajectoryDelta],
    iteration:         int,
    max_iterations:    int,
    budget_remaining:  float,
) -> Tuple[str, str]:
    """Compute the drill-loop's next action.

    Pause-and-measure semantics (confirmed default):
      - When trajectory is flat AND we just fired, pause one cycle
        before re-firing. Take derivative at a settled point.
      - Otherwise fire on weakest link.
      - Exit on satisfied OR budget cap OR iteration cap.
    """

    if satisfied:
        return APNEA_SATISFIED, "All 6 questions answered + role coverage + trajectory converged"

    if budget_remaining <= 0.0:
        return APNEA_BUDGET_CAP, "Budget cap reached — returning best chain so far"

    if iteration >= max_iterations:
        return APNEA_BUDGET_CAP, "Iteration cap N=" + str(max_iterations) + " reached"

    # Pause-and-measure: flat derivative right after firing -> pause
    if trajectory is not None:
        if trajectory.flatlining() and iteration > 0:
            return APNEA_PAUSE, (
                "Delta(t) derivative flat ({:.4f}) — apnea pause "
                "to take a clean measurement before re-firing"
                .format(trajectory.d_delta_dt if trajectory.d_delta_dt is not None else 0.0)
            )

    return APNEA_FIRE, "Boundary not satisfied — firing Magnify on weakest link"


# ---------------------------------------------------------------------------
# Result builder
# ---------------------------------------------------------------------------

def _result_from_parsed_v2(
    parsed:           Dict[str, Any],
    raw:              str,
    elapsed:          float,
    provider:         str,
    trajectory:       Optional[TrajectoryDelta],
    iteration:        int,
    max_iterations:   int,
    budget_remaining: float,
) -> BoundaryResultV2:
    """Build a BoundaryResultV2 from parsed LLM JSON with defensive defaults."""

    per_q_raw = parsed.get("per_question") or {}
    per_q: Dict[str, Dict[str, Any]] = {}
    role_map: Dict[str, List[Dict[str, str]]] = {}

    role_map_keys = ("operational_cost_per_function", "leverage_points", "collapse_points")

    for key in QUESTION_KEYS:
        entry = per_q_raw.get(key) or {}
        per_q[key] = {
            "answered": bool(entry.get("answered", False)),
            "quality":  float(entry.get("quality", 0.0) or 0.0),
            "gaps":     list(entry.get("gaps", []) or [])[:10],
            "notes":    str(entry.get("notes", ""))[:1000],
        }
        if key in role_map_keys:
            raw_map = entry.get("function_to_role_map", []) or []
            cleaned = []
            for m in raw_map[:20]:
                if isinstance(m, dict):
                    cleaned.append({
                        "function":         str(m.get("function", ""))[:200],
                        "role":             str(m.get("role", ""))[:120],
                        "labor_separation": str(m.get("labor_separation", ""))[:400],
                        "cost_per_unit":    str(m.get("cost_per_unit", ""))[:80],
                        "cost_basis":       str(m.get("cost_basis", ""))[:200],
                    })
            role_map[key] = cleaned
            per_q[key]["function_to_role_map"] = cleaned

            # Downgrade quality if role-map missing on answered=true
            if per_q[key]["answered"] and not cleaned:
                per_q[key]["quality"] = max(0.0, per_q[key]["quality"] - 0.3)
                per_q[key]["gaps"].append("function_to_role_map missing")

    qualities = [v["quality"] for v in per_q.values()]
    derived_score = sum(qualities) / len(qualities) if qualities else 0.0
    score = float(parsed.get("score", derived_score) or derived_score)

    chain_visible = bool(parsed.get("next_pilot_move_chain_visible", False))
    role_ok       = bool(parsed.get("role_coverage_ok", False))
    traj_evidence = bool(parsed.get("trajectory_evidence_in_text", False))

    all_answered     = all(v["answered"] for v in per_q.values())
    all_quality_pass = all(v["quality"] >= 0.7 for v in per_q.values())

    if trajectory is not None:
        traj_ok = traj_evidence and trajectory.converging()
    else:
        traj_ok = True

    satisfied = (
        all_answered
        and all_quality_pass
        and chain_visible
        and role_ok
        and traj_ok
    )

    weakest = parsed.get("weakest_link")
    if not satisfied:
        lowest_key, lowest_q = None, 1.1
        for k, v in per_q.items():
            if v["quality"] < lowest_q:
                lowest_q, lowest_key = v["quality"], k
        if not role_ok and lowest_q >= 0.6:
            lowest_key = "role_coverage"
        weakest = lowest_key or weakest

    missing = list(parsed.get("missing_density_for", []) or [])[:5]
    missing = [str(m)[:300] for m in missing]

    reason = str(parsed.get("reason", ""))[:2000]
    if not reason:
        reason = (
            "score={:.2f} chain={} role_ok={} traj_ok={} satisfied={}"
            .format(score, chain_visible, role_ok, traj_ok, satisfied)
        )

    apnea_rec, apnea_reason = _decide_apnea(
        satisfied=satisfied,
        trajectory=trajectory,
        iteration=iteration,
        max_iterations=max_iterations,
        budget_remaining=budget_remaining,
    )

    return BoundaryResultV2(
        satisfied=satisfied,
        score=score,
        weakest_link=weakest if not satisfied else None,
        missing_density_for=missing,
        per_question=per_q,
        next_pilot_move_chain_visible=chain_visible,
        reason=reason,
        raw_response=raw[:5000],
        latency_seconds=elapsed,
        provider=provider,
        function_to_role_map=role_map,
        role_coverage_ok=role_ok,
        trajectory_converging=(trajectory.converging() if trajectory else False),
        trajectory_converged=(trajectory.converged() if trajectory else False),
        trajectory_flatlining=(trajectory.flatlining() if trajectory else False),
        trajectory_delta_last=(trajectory.delta_t[-1] if trajectory and trajectory.delta_t else None),
        trajectory_d_delta_dt=(trajectory.d_delta_dt if trajectory else None),
        apnea_recommendation=apnea_rec,
        apnea_reason=apnea_reason,
        iteration=iteration,
    )


# ---------------------------------------------------------------------------
# v2 entry point
# ---------------------------------------------------------------------------

def evaluate_v2(
    deliverable:       str,
    business_spec:     Dict[str, Any],
    goal_plot:         Optional[Dict[str, Any]] = None,
    trajectory:        Optional[TrajectoryDelta] = None,
    *,
    iteration:         int = 0,
    max_iterations:    int = 5,
    budget_remaining:  float = 1.0,
    llm=None,
    max_tokens:        int = 3500,
    temperature:       float = 0.2,
) -> BoundaryResultV2:
    """
    v2 audit — extends v1 with labor mapping, trajectory grading, apnea decision.

    Args:
        deliverable, business_spec, goal_plot: same as v1.
        trajectory:        Optional TrajectoryDelta. If None, trajectory
                           grading is skipped (v1-equivalent behavior).
        iteration:         Current iteration number (0 = pre-loop).
        max_iterations:    Hard cap (default 5 per v2 spec).
        budget_remaining:  Dollars left in LLM budget (default $1.00).
        llm:               Override LLM provider for testing.
        max_tokens:        v2 emits more JSON, default 3500.
        temperature:       0.2 — consistent audit, not creative.

    Returns:
        BoundaryResultV2 — superset of v1 result. Never raises for
        normal LLM/parse failures.
    """

    if not deliverable or not deliverable.strip():
        return BoundaryResultV2(
            satisfied=False, score=0.0,
            weakest_link=None,
            missing_density_for=["deliverable is empty — fire Magnify pass 1"],
            per_question={
                k: {"answered": False, "quality": 0.0, "gaps": ["empty"], "notes": ""}
                for k in QUESTION_KEYS
            },
            next_pilot_move_chain_visible=False,
            reason="Empty deliverable — cannot audit. Fire initial Magnify pass.",
            error="empty_deliverable",
            apnea_recommendation=APNEA_FIRE,
            apnea_reason="Empty deliverable — initial Magnify pass required",
            iteration=iteration,
        )

    if not business_spec or not isinstance(business_spec, dict):
        return BoundaryResultV2(
            satisfied=False, score=0.0,
            weakest_link=None,
            missing_density_for=["business_spec missing — Goal Plotter must run first"],
            per_question={
                k: {"answered": False, "quality": 0.0, "gaps": ["no spec"], "notes": ""}
                for k in QUESTION_KEYS
            },
            next_pilot_move_chain_visible=False,
            reason="No business_spec — cannot audit subject-matter specificity.",
            error="missing_business_spec",
            apnea_recommendation=APNEA_BUDGET_CAP,
            apnea_reason="Missing business_spec — cannot proceed",
            iteration=iteration,
        )

    if llm is None:
        try:
            from src.llm_provider import MurphyLLMProvider
            llm = MurphyLLMProvider()
        except Exception as e:
            LOG.exception("LLM provider instantiation failed")
            return BoundaryResultV2(
                satisfied=False, score=0.0,
                weakest_link=None,
                missing_density_for=[],
                per_question={
                    k: {"answered": False, "quality": 0.0, "gaps": ["no llm"], "notes": ""}
                    for k in QUESTION_KEYS
                },
                next_pilot_move_chain_visible=False,
                reason="LLM provider unavailable: " + str(e),
                error="llm_unavailable:" + str(e),
                apnea_recommendation=APNEA_BUDGET_CAP,
                apnea_reason="LLM provider unavailable",
                iteration=iteration,
            )

    audit_prompt = _build_audit_prompt_v2(
        deliverable, business_spec, goal_plot, trajectory
    )

    t0 = time.time()
    try:
        resp = llm.complete(
            prompt=audit_prompt,
            system=SYSTEM_PROMPT_V2,
            max_tokens=max_tokens,
            temperature=temperature,
            deterministic=False,
        )
    except Exception as e:
        LOG.exception("v2 detector LLM call failed")
        return BoundaryResultV2(
            satisfied=False, score=0.0,
            weakest_link=None,
            missing_density_for=[],
            per_question={
                k: {"answered": False, "quality": 0.0, "gaps": ["llm fail"], "notes": ""}
                for k in QUESTION_KEYS
            },
            next_pilot_move_chain_visible=False,
            reason="LLM call failed: " + str(e),
            error="llm_call_failed:" + str(e),
            latency_seconds=time.time() - t0,
            apnea_recommendation=APNEA_PAUSE,
            apnea_reason="LLM call failed — apnea pause before retry",
            iteration=iteration,
        )

    elapsed = time.time() - t0
    raw      = (resp.content  or "") if resp else ""
    provider = (resp.provider or "unknown") if resp else "unknown"

    parsed = _extract_json(raw)
    if parsed is None:
        return BoundaryResultV2(
            satisfied=False, score=0.0,
            weakest_link=None,
            missing_density_for=["detector returned unparseable JSON"],
            per_question={
                k: {"answered": False, "quality": 0.0, "gaps": ["parse fail"], "notes": ""}
                for k in QUESTION_KEYS
            },
            next_pilot_move_chain_visible=False,
            reason="Detector LLM returned unparseable JSON.",
            error="unparseable_json",
            raw_response=raw[:5000],
            latency_seconds=elapsed,
            provider=provider,
            apnea_recommendation=APNEA_PAUSE,
            apnea_reason="Parse failure — apnea pause before retry",
            iteration=iteration,
        )

    return _result_from_parsed_v2(
        parsed=parsed,
        raw=raw,
        elapsed=elapsed,
        provider=provider,
        trajectory=trajectory,
        iteration=iteration,
        max_iterations=max_iterations,
        budget_remaining=budget_remaining,
    )


# ---------------------------------------------------------------------------
# v2 summarizer
# ---------------------------------------------------------------------------

def summarize_v2(result: BoundaryResultV2) -> str:
    """One-line v2 summary suitable for logs."""
    icon = "✓" if result.satisfied else "✗"
    return (
        icon + " v2 satisfied=" + str(result.satisfied)
        + " score=" + "{:.2f}".format(result.score)
        + " chain=" + str(result.next_pilot_move_chain_visible)
        + " role_ok=" + str(result.role_coverage_ok)
        + " traj_conv=" + str(result.trajectory_converging)
        + " apnea=" + result.apnea_recommendation
        + " weakest=" + (result.weakest_link or "-")
        + " iter=" + str(result.iteration)
        + " provider=" + result.provider
        + " lat=" + "{:.1f}s".format(result.latency_seconds)
    )
