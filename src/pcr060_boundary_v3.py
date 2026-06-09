"""
PCR-060a.3 — Boundary-Condition Detector v3

Goal Escalation + Production Capacity Offset (Read C: both clauses required)

Founder principle (locked 2026-06-09):
  "When you meet goals early you adjust for a larger goal and you
   offset production as it will need to boom."

This module IMPORTS v2 (`src.pcr060_boundary_v2`) and extends it.
v1 and v2 callers continue to work unchanged.

THREE EXTENSIONS over v2:

  1. APNEA_RAISE_CEILING — new apnea state
     When `satisfied=true` AND iteration is in the early half of the
     budget AND budget_remaining is healthy, the detector recommends
     RAISING THE GOAL instead of exiting. The drill driver calls the
     Goal Plotter's raise_ceiling() pass and re-runs with the new R(t).

  2. Q7 — Production Capacity Offset (conditional on raised_goal_active)
     A 7th boundary question, graded only when the goal has been
     raised at least once. Requires both clauses:
       (A) Capacity ramp pre-positioning — what gets ordered/hired/
           built BEFORE the demand wave, with lead-time and owner.
       (B) Over/undershoot risk model — money-ratio impact of being
           20% under vs. 20% over capacity, with named hedge direction.
     Missing either clause = FAIL.

  3. BoundaryResultV3 — adds escalation fields:
       - raised_goal_active: bool
       - ceiling_level: int (0 = original goal, 1 = first raise, ...)
       - production_offset_ok: bool (Q7 result)
       - early_satisfied: bool (the trigger condition itself)

Spec: .agents/memory/pcr060_magnify_boundary_loop_spec.md (v3)
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple

# Re-export v2 + v1 symbols; v3 is purely additive
from src.pcr060_boundary_v2 import (
    BoundaryResultV2,
    TrajectoryDelta,
    BOUNDARY_QUESTIONS_V2,
    SYSTEM_PROMPT_V2,
    APNEA_FIRE,
    APNEA_PAUSE,
    APNEA_SATISFIED,
    APNEA_BUDGET_CAP,
    _extract_json,
    _build_audit_prompt_v2,
)
from src.pcr060_boundary_condition import QUESTION_KEYS as V1_QUESTION_KEYS

LOG = logging.getLogger("murphy.pcr060.boundary_v3")


# ---------------------------------------------------------------------------
# New apnea state
# ---------------------------------------------------------------------------

APNEA_RAISE_CEILING = "raise_goal_ceiling"
"""New state: convergence happened earlier than expected with budget
left. Don't exit — raise the ceiling and re-run."""

# v3 escalation policy constants
EARLY_SATISFIED_ITERATION_FRACTION = 0.5
"""If iteration / max_iterations <= this AND satisfied, trigger raise."""

EARLY_SATISFIED_BUDGET_THRESHOLD = 0.5
"""Need at least 50% of original budget remaining to justify a raise."""

MAX_CEILING_RAISES = 3
"""Hard cap on how many times we can raise the ceiling per dispatch.
Prevents runaway escalation if every raise also converges fast."""


# ---------------------------------------------------------------------------
# Q7 — Production Capacity Offset
# ---------------------------------------------------------------------------

Q7_KEY = "production_capacity_offset"

Q7_TEXT = (
    "Given the raised goal projects materially higher demand/output than "
    "the original target, does the deliverable explicitly contain BOTH "
    "of the following clauses (failure on either = FAIL):\n"
    "  (A) CAPACITY RAMP PRE-POSITIONING — a stated capacity curve "
    "      showing what gets ordered/hired/built/leased BEFORE the demand "
    "      wave arrives, with lead-time per item and the role-owner who "
    "      pulls the trigger. 'We will scale up' = FAIL.\n"
    "  (B) OVER/UNDERSHOOT RISK MODEL — explicit money-ratio impact of "
    "      being 20% under vs. 20% over capacity at the raised goal, "
    "      with the chosen hedge direction stated and justified. "
    "      A single capacity number = FAIL. Both directions must be "
    "      modeled and the hedge stance must be picked."
)

BOUNDARY_QUESTIONS_V3 = dict(BOUNDARY_QUESTIONS_V2)
BOUNDARY_QUESTIONS_V3[Q7_KEY] = Q7_TEXT

QUESTION_KEYS_V3 = list(BOUNDARY_QUESTIONS_V3.keys())
"""Note: Q7 is in this list but is conditionally graded — only when
raised_goal_active=True. See _result_from_parsed_v3 below."""


# ---------------------------------------------------------------------------
# v3 result type
# ---------------------------------------------------------------------------

@dataclass
class BoundaryResultV3:
    """Extended boundary result — superset of v2 result + escalation fields."""

    # v1 + v2 fields (carried through)
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

    function_to_role_map:            Dict[str, List[Dict[str, str]]] = field(default_factory=dict)
    role_coverage_ok:                bool = False
    trajectory_converging:           bool = False
    trajectory_converged:            bool = False
    trajectory_flatlining:           bool = False
    trajectory_delta_last:           Optional[float] = None
    trajectory_d_delta_dt:           Optional[float] = None
    apnea_recommendation:            str = APNEA_FIRE
    apnea_reason:                    str = ""
    iteration:                       int = 0

    # v3 additions — goal escalation + production offset
    raised_goal_active:              bool = False
    """True if the goal has been raised at least once this dispatch."""

    ceiling_level:                   int = 0
    """0 = original goal, 1 = first raise, 2 = second raise, ..."""

    early_satisfied:                 bool = False
    """True if satisfied was triggered in the early-iteration zone
    AND budget had headroom — i.e. the raise-ceiling trigger fired."""

    production_offset_ok:            bool = False
    """Q7 result. Only meaningful when raised_goal_active=True.
    Both clauses (A pre-positioning + B over/undershoot model) must
    pass for this to be True."""

    production_offset_clauses:       Dict[str, bool] = field(default_factory=dict)
    """Per-clause breakdown of Q7: {'pre_positioning': bool,
    'risk_model': bool}. Both must be True for production_offset_ok."""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# v3 system prompt — extends v2 with escalation language
# ---------------------------------------------------------------------------

SYSTEM_PROMPT_V3 = (
    SYSTEM_PROMPT_V2
    + "\n\nADDITIONAL v3 REQUIREMENTS:\n"
    "  - When raised_goal_active=true, you ALSO grade Q7 "
    "    (production_capacity_offset).\n"
    "  - Q7 requires BOTH clauses: (A) capacity ramp pre-positioning AND\n"
    "    (B) over/undershoot risk model with hedge direction. If either\n"
    "    clause is missing or generic, Q7 fails.\n"
    "  - You return per-clause flags for Q7: production_offset_clauses\n"
    "    = {pre_positioning: bool, risk_model: bool}\n"
    "  - When raised_goal_active=false, Q7 is N/A — set Q7.answered=false,\n"
    "    Q7.quality=0.0, and exclude it from score computation.\n"
)


# ---------------------------------------------------------------------------
# v3 prompt builder
# ---------------------------------------------------------------------------

def _q7_schema_clause() -> str:
    return (
        '    "production_capacity_offset": {\n'
        '      "answered": bool, "quality": 0.0-1.0,\n'
        '      "gaps": ["..."], "notes": "...",\n'
        '      "clauses": {"pre_positioning": bool, "risk_model": bool}\n'
        '    }'
    )


def _build_audit_prompt_v3(
    deliverable: str,
    business_spec: Dict[str, Any],
    goal_plot: Optional[Dict[str, Any]] = None,
    trajectory_delta: Optional[TrajectoryDelta] = None,
    raised_goal_active: bool = False,
    ceiling_level: int = 0,
) -> str:
    """v3 audit prompt — adds Q7 (conditionally) + raised-goal context."""

    # Build the v2 prompt first
    base = _build_audit_prompt_v2(deliverable, business_spec, goal_plot, trajectory_delta)

    # Inject v3-specific header + Q7 block
    raised_block = (
        "=== GOAL ESCALATION CONTEXT ===\n"
        + json.dumps({
            "raised_goal_active": raised_goal_active,
            "ceiling_level":      ceiling_level,
        }, indent=2)
    )

    if raised_goal_active:
        q7_block = (
            "\n\n=== Q7 — PRODUCTION CAPACITY OFFSET (active because goal was raised) ===\n"
            "  " + Q7_TEXT
            + "\n\n=== v3 DECISION RULES (in addition to v1/v2) ===\n"
              "  - Q7 must be graded. Both clauses (pre_positioning AND risk_model)\n"
              "    are required to pass. Missing either = Q7.answered=false.\n"
              "  - Q7 contributes to score and to satisfied gate.\n"
              "  - satisfied = (v2 satisfied) AND production_offset_ok\n"
              "  - Add Q7 result to per_question with the schema clause shown below.\n"
              "  - Set production_offset_clauses at top level mirroring Q7.clauses.\n"
              "\n=== ADDITIONAL JSON SCHEMA FRAGMENT FOR Q7 ===\n"
            + _q7_schema_clause()
            + "\n  (Add this to the per_question object alongside the v2 keys.)\n"
              "  Also add top-level: \"production_offset_clauses\": "
              "{\"pre_positioning\": bool, \"risk_model\": bool}\n"
        )
    else:
        q7_block = (
            "\n\n=== Q7 N/A — goal has not been raised yet ===\n"
            "  Do NOT grade Q7. Do not include production_capacity_offset in per_question.\n"
            "  Do not include production_offset_clauses at top level.\n"
        )

    return raised_block + "\n\n" + base + q7_block


# ---------------------------------------------------------------------------
# v3 apnea decision — adds escalation branch
# ---------------------------------------------------------------------------

def _decide_apnea_v3(
    satisfied:           bool,
    trajectory:          Optional[TrajectoryDelta],
    iteration:           int,
    max_iterations:      int,
    budget_remaining:    float,
    budget_initial:      float,
    ceiling_level:       int,
    max_ceiling_raises:  int = MAX_CEILING_RAISES,
) -> Tuple[str, str, bool]:
    """v3 apnea decision — extends v2 with raise-ceiling branch.

    Returns (apnea_recommendation, apnea_reason, early_satisfied).

    The early_satisfied flag tells the caller WHY satisfied happened —
    if True, satisfied was achieved fast enough to raise the ceiling.

    Escalation rules:
      - satisfied AND iteration/max <= EARLY_SATISFIED_ITERATION_FRACTION
        AND budget_remaining/budget_initial >= EARLY_SATISFIED_BUDGET_THRESHOLD
        AND ceiling_level < max_ceiling_raises
        --> APNEA_RAISE_CEILING

      - satisfied AND no escalation criteria
        --> APNEA_SATISFIED

      - otherwise: same as v2 (BUDGET_CAP / PAUSE / FIRE)
    """

    # ESCALATION CHECK — only fires when satisfied
    if satisfied:
        iteration_fraction = (
            iteration / float(max_iterations) if max_iterations > 0 else 1.0
        )
        budget_fraction = (
            budget_remaining / float(budget_initial) if budget_initial > 0 else 0.0
        )
        ceilings_left = max_ceiling_raises - ceiling_level

        early_iter      = iteration_fraction <= EARLY_SATISFIED_ITERATION_FRACTION
        budget_headroom = budget_fraction    >= EARLY_SATISFIED_BUDGET_THRESHOLD
        raises_left     = ceilings_left > 0

        if early_iter and budget_headroom and raises_left:
            return (
                APNEA_RAISE_CEILING,
                ("Early convergence at iter={}/{} ({:.0%}) with budget "
                 "{:.0%} remaining and {} raise(s) left — raising goal "
                 "ceiling and re-projecting R(t)").format(
                    iteration, max_iterations, iteration_fraction,
                    budget_fraction, ceilings_left,
                ),
                True,
            )
        # Satisfied without escalation criteria — normal exit
        return (
            APNEA_SATISFIED,
            ("Goal met at iter={}/{} ({:.0%}); ceiling_level={}; "
             "no escalation criteria triggered (early_iter={}, "
             "budget_headroom={}, raises_left={})").format(
                iteration, max_iterations, iteration_fraction,
                ceiling_level, early_iter, budget_headroom, raises_left,
            ),
            False,
        )

    # Not satisfied — fall through to v2-equivalent logic
    if budget_remaining <= 0.0:
        return APNEA_BUDGET_CAP, "Budget cap reached — returning best chain so far", False

    if iteration >= max_iterations:
        return APNEA_BUDGET_CAP, "Iteration cap N={} reached".format(max_iterations), False

    if trajectory is not None and trajectory.flatlining() and iteration > 0:
        return (
            APNEA_PAUSE,
            "Delta(t) derivative flat ({:.4f}) — apnea pause to take a "
            "clean measurement before re-firing".format(
                trajectory.d_delta_dt if trajectory.d_delta_dt is not None else 0.0
            ),
            False,
        )

    return APNEA_FIRE, "Boundary not satisfied — firing Magnify on weakest link", False


# ---------------------------------------------------------------------------
# v3 result builder
# ---------------------------------------------------------------------------

def _result_from_parsed_v3(
    parsed:              Dict[str, Any],
    raw:                 str,
    elapsed:             float,
    provider:            str,
    trajectory:          Optional[TrajectoryDelta],
    iteration:           int,
    max_iterations:      int,
    budget_remaining:    float,
    budget_initial:      float,
    raised_goal_active:  bool,
    ceiling_level:       int,
) -> BoundaryResultV3:
    """Build a BoundaryResultV3 from parsed LLM JSON with defensive defaults."""

    per_q_raw = parsed.get("per_question") or {}
    per_q: Dict[str, Dict[str, Any]] = {}
    role_map: Dict[str, List[Dict[str, str]]] = {}

    role_map_keys = ("operational_cost_per_function", "leverage_points", "collapse_points")

    # Grade the v1/v2 six questions exactly as v2 does
    for key in V1_QUESTION_KEYS:
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

            if per_q[key]["answered"] and not cleaned:
                per_q[key]["quality"] = max(0.0, per_q[key]["quality"] - 0.3)
                per_q[key]["gaps"].append("function_to_role_map missing")

    # v3: Grade Q7 only if raised_goal_active
    production_offset_ok = False
    offset_clauses = {"pre_positioning": False, "risk_model": False}

    if raised_goal_active:
        q7_entry = per_q_raw.get(Q7_KEY) or {}
        per_q[Q7_KEY] = {
            "answered": bool(q7_entry.get("answered", False)),
            "quality":  float(q7_entry.get("quality", 0.0) or 0.0),
            "gaps":     list(q7_entry.get("gaps", []) or [])[:10],
            "notes":    str(q7_entry.get("notes", ""))[:1000],
        }

        # Per-clause check (Read C: both required)
        q7_clauses_raw = q7_entry.get("clauses") or {}
        offset_clauses["pre_positioning"] = bool(q7_clauses_raw.get("pre_positioning", False))
        offset_clauses["risk_model"]      = bool(q7_clauses_raw.get("risk_model", False))

        # Also check top-level mirror if LLM emitted it there
        top_level_clauses = parsed.get("production_offset_clauses") or {}
        if top_level_clauses:
            offset_clauses["pre_positioning"] = (
                offset_clauses["pre_positioning"]
                or bool(top_level_clauses.get("pre_positioning", False))
            )
            offset_clauses["risk_model"] = (
                offset_clauses["risk_model"]
                or bool(top_level_clauses.get("risk_model", False))
            )

        # Both clauses required
        production_offset_ok = (
            offset_clauses["pre_positioning"] and offset_clauses["risk_model"]
        )

        # If Q7 answered=true but a clause is missing, downgrade
        if per_q[Q7_KEY]["answered"] and not production_offset_ok:
            per_q[Q7_KEY]["quality"] = max(0.0, per_q[Q7_KEY]["quality"] - 0.4)
            if not offset_clauses["pre_positioning"]:
                per_q[Q7_KEY]["gaps"].append("missing clause A: capacity ramp pre-positioning")
            if not offset_clauses["risk_model"]:
                per_q[Q7_KEY]["gaps"].append("missing clause B: over/undershoot risk model")

        per_q[Q7_KEY]["clauses"] = offset_clauses

    # Score computation — includes Q7 only when graded
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

    # v3 satisfied — adds production_offset_ok when applicable
    if raised_goal_active:
        satisfied = (
            all_answered and all_quality_pass and chain_visible
            and role_ok and traj_ok and production_offset_ok
        )
    else:
        satisfied = (
            all_answered and all_quality_pass and chain_visible
            and role_ok and traj_ok
        )

    weakest = parsed.get("weakest_link")
    if not satisfied:
        lowest_key, lowest_q = None, 1.1
        for k, v in per_q.items():
            if v["quality"] < lowest_q:
                lowest_q, lowest_key = v["quality"], k
        if not role_ok and lowest_q >= 0.6:
            lowest_key = "role_coverage"
        if raised_goal_active and not production_offset_ok and lowest_q >= 0.6:
            lowest_key = Q7_KEY
        weakest = lowest_key or weakest

    missing = list(parsed.get("missing_density_for", []) or [])[:5]
    missing = [str(m)[:300] for m in missing]

    reason = str(parsed.get("reason", ""))[:2000]
    if not reason:
        reason = (
            "score={:.2f} chain={} role_ok={} traj_ok={} "
            "raised={} ceiling={} offset_ok={} satisfied={}"
            .format(
                score, chain_visible, role_ok, traj_ok,
                raised_goal_active, ceiling_level,
                production_offset_ok, satisfied,
            )
        )

    apnea_rec, apnea_reason, early_satisfied = _decide_apnea_v3(
        satisfied=satisfied,
        trajectory=trajectory,
        iteration=iteration,
        max_iterations=max_iterations,
        budget_remaining=budget_remaining,
        budget_initial=budget_initial,
        ceiling_level=ceiling_level,
    )

    return BoundaryResultV3(
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
        raised_goal_active=raised_goal_active,
        ceiling_level=ceiling_level,
        early_satisfied=early_satisfied,
        production_offset_ok=production_offset_ok,
        production_offset_clauses=offset_clauses,
    )


# ---------------------------------------------------------------------------
# v3 entry point
# ---------------------------------------------------------------------------

def evaluate_v3(
    deliverable:        str,
    business_spec:      Dict[str, Any],
    goal_plot:          Optional[Dict[str, Any]] = None,
    trajectory:         Optional[TrajectoryDelta] = None,
    *,
    iteration:          int = 0,
    max_iterations:     int = 5,
    budget_remaining:   float = 1.0,
    budget_initial:     float = 1.0,
    raised_goal_active: bool = False,
    ceiling_level:      int = 0,
    llm=None,
    max_tokens:         int = 4000,
    temperature:        float = 0.2,
) -> BoundaryResultV3:
    """
    v3 audit — extends v2 with goal escalation + production capacity offset.

    New args vs. v2:
        budget_initial:     Original budget at iteration 0. Needed to
                            compute fractional headroom for escalation.
        raised_goal_active: True if the goal has been raised already.
                            When True, Q7 (production_capacity_offset)
                            is graded; both clauses required (Read C).
        ceiling_level:      0 = original goal. Caps at MAX_CEILING_RAISES.

    Returns:
        BoundaryResultV3 — superset of v2 result. Never raises for
        normal LLM/parse failures.

    Escalation flow:
        - If satisfied AND early AND budget_headroom AND raises_left:
            apnea_recommendation = APNEA_RAISE_CEILING
            early_satisfied = True
          (caller: invoke Goal Plotter.raise_ceiling(), bump ceiling_level,
           re-run evaluate_v3 with raised_goal_active=True)
        - If satisfied AND no escalation criteria:
            apnea_recommendation = APNEA_SATISFIED
            (caller: exit loop)
    """

    if not deliverable or not deliverable.strip():
        return BoundaryResultV3(
            satisfied=False, score=0.0,
            weakest_link=None,
            missing_density_for=["deliverable is empty — fire Magnify pass 1"],
            per_question={
                k: {"answered": False, "quality": 0.0, "gaps": ["empty"], "notes": ""}
                for k in V1_QUESTION_KEYS
            },
            next_pilot_move_chain_visible=False,
            reason="Empty deliverable — cannot audit. Fire initial Magnify pass.",
            error="empty_deliverable",
            apnea_recommendation=APNEA_FIRE,
            apnea_reason="Empty deliverable — initial Magnify pass required",
            iteration=iteration,
            raised_goal_active=raised_goal_active,
            ceiling_level=ceiling_level,
        )

    if not business_spec or not isinstance(business_spec, dict):
        return BoundaryResultV3(
            satisfied=False, score=0.0,
            weakest_link=None,
            missing_density_for=["business_spec missing — Goal Plotter must run first"],
            per_question={
                k: {"answered": False, "quality": 0.0, "gaps": ["no spec"], "notes": ""}
                for k in V1_QUESTION_KEYS
            },
            next_pilot_move_chain_visible=False,
            reason="No business_spec — cannot audit subject-matter specificity.",
            error="missing_business_spec",
            apnea_recommendation=APNEA_BUDGET_CAP,
            apnea_reason="Missing business_spec — cannot proceed",
            iteration=iteration,
            raised_goal_active=raised_goal_active,
            ceiling_level=ceiling_level,
        )

    if llm is None:
        try:
            from src.llm_provider import MurphyLLMProvider
            llm = MurphyLLMProvider()
        except Exception as e:
            LOG.exception("LLM provider instantiation failed")
            return BoundaryResultV3(
                satisfied=False, score=0.0,
                weakest_link=None,
                missing_density_for=[],
                per_question={
                    k: {"answered": False, "quality": 0.0, "gaps": ["no llm"], "notes": ""}
                    for k in V1_QUESTION_KEYS
                },
                next_pilot_move_chain_visible=False,
                reason="LLM provider unavailable: " + str(e),
                error="llm_unavailable:" + str(e),
                apnea_recommendation=APNEA_BUDGET_CAP,
                apnea_reason="LLM provider unavailable",
                iteration=iteration,
                raised_goal_active=raised_goal_active,
                ceiling_level=ceiling_level,
            )

    audit_prompt = _build_audit_prompt_v3(
        deliverable, business_spec, goal_plot, trajectory,
        raised_goal_active=raised_goal_active,
        ceiling_level=ceiling_level,
    )

    t0 = time.time()
    try:
        resp = llm.complete(
            prompt=audit_prompt,
            system=SYSTEM_PROMPT_V3,
            max_tokens=max_tokens,
            temperature=temperature,
            deterministic=False,
        )
    except Exception as e:
        LOG.exception("v3 detector LLM call failed")
        return BoundaryResultV3(
            satisfied=False, score=0.0,
            weakest_link=None,
            missing_density_for=[],
            per_question={
                k: {"answered": False, "quality": 0.0, "gaps": ["llm fail"], "notes": ""}
                for k in V1_QUESTION_KEYS
            },
            next_pilot_move_chain_visible=False,
            reason="LLM call failed: " + str(e),
            error="llm_call_failed:" + str(e),
            latency_seconds=time.time() - t0,
            apnea_recommendation=APNEA_PAUSE,
            apnea_reason="LLM call failed — apnea pause before retry",
            iteration=iteration,
            raised_goal_active=raised_goal_active,
            ceiling_level=ceiling_level,
        )

    elapsed = time.time() - t0
    raw      = (resp.content  or "") if resp else ""
    provider = (resp.provider or "unknown") if resp else "unknown"

    parsed = _extract_json(raw)
    if parsed is None:
        return BoundaryResultV3(
            satisfied=False, score=0.0,
            weakest_link=None,
            missing_density_for=["detector returned unparseable JSON"],
            per_question={
                k: {"answered": False, "quality": 0.0, "gaps": ["parse fail"], "notes": ""}
                for k in V1_QUESTION_KEYS
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
            raised_goal_active=raised_goal_active,
            ceiling_level=ceiling_level,
        )

    return _result_from_parsed_v3(
        parsed=parsed,
        raw=raw,
        elapsed=elapsed,
        provider=provider,
        trajectory=trajectory,
        iteration=iteration,
        max_iterations=max_iterations,
        budget_remaining=budget_remaining,
        budget_initial=budget_initial,
        raised_goal_active=raised_goal_active,
        ceiling_level=ceiling_level,
    )


# ---------------------------------------------------------------------------
# v3 summarizer
# ---------------------------------------------------------------------------

def summarize_v3(result: BoundaryResultV3) -> str:
    """One-line v3 summary suitable for logs — includes escalation state."""
    icon = "✓" if result.satisfied else "✗"
    ceiling_tag = ""
    if result.raised_goal_active:
        ceiling_tag = " ceiling=L{}".format(result.ceiling_level)
        if result.production_offset_ok:
            ceiling_tag += " offset_OK"
        else:
            ceiling_tag += " offset_MISS"
    early_tag = " EARLY" if result.early_satisfied else ""
    return (
        icon + " v3 satisfied=" + str(result.satisfied)
        + " score=" + "{:.2f}".format(result.score)
        + " chain=" + str(result.next_pilot_move_chain_visible)
        + " role_ok=" + str(result.role_coverage_ok)
        + " apnea=" + result.apnea_recommendation
        + ceiling_tag + early_tag
        + " weakest=" + (result.weakest_link or "-")
        + " iter=" + str(result.iteration)
        + " provider=" + result.provider
        + " lat=" + "{:.1f}s".format(result.latency_seconds)
    )
