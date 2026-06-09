"""
PCR-060a — Boundary-Condition Detector

The heart of the Magnify Boundary Loop.

Pure callable: takes a draft deliverable + business spec, returns a
structured BoundaryResult that says whether the
operational <-> money-ratio chain has connected for this business in
this subject matter.

If satisfied=True, the Magnify loop may terminate and Simplify may run.
If satisfied=False, the result names the weakest link and what density
is missing — the caller fires another Magnify pass scoped to that link.

The 6 questions encode the boundary condition:

    1. Operational cost per function (subject-matter anchored)
    2. Unit economics at 1x / 10x / 100x scale, with stated assumptions
    3. 3-5 leverage points specific to this subject matter
    4. 3-5 attractors with "why is this happening" mechanism
    5. 3-5 collapse points with mechanism + early signal
    6. Next pilot move with chain visible back to goal-plot

This module is intentionally framework-free:
    - No FastAPI imports
    - No app.py dependencies
    - No DB writes
    - Only depends on src.llm_provider.MurphyLLMProvider

That means it can be tested in isolation by any script or notebook.

Spec: .agents/memory/pcr060_magnify_boundary_loop_spec.md
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

LOG = logging.getLogger("murphy.pcr060.boundary")


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class BoundaryResult:
    """The output of one boundary-condition evaluation pass."""

    satisfied: bool
    """True if the operational<->money-ratio chain connects end-to-end."""

    score: float
    """0.0 - 1.0 confidence in the chain-connection assessment."""

    weakest_link: Optional[str]
    """Which of the 6 questions failed hardest. None if satisfied."""

    missing_density_for: List[str]
    """Specific topics the next Magnify pass should drill on."""

    per_question: Dict[str, Dict[str, Any]]
    """
    For each of the 6 questions:
        {answered: bool, quality: 0.0-1.0, gaps: [str], notes: str}
    """

    next_pilot_move_chain_visible: bool
    """Q6 has stricter requirement — the causal chain must be visible
    end-to-end (move -> leverage -> margin -> goal). Tracked separately
    because it's the hardest gate."""

    reason: str
    """Human-readable summary the loop driver can log + show in UI."""

    raw_response: str = ""
    """Raw LLM output for debugging; truncated when stored."""

    latency_seconds: float = 0.0
    provider: str = "unknown"
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# The 6 questions (canonical wording — do NOT edit casually)
# ---------------------------------------------------------------------------

BOUNDARY_QUESTIONS = {
    "operational_cost_per_function": (
        "What does each operational function (sales, fulfillment, support, "
        "finance, ops, R&D — whichever are relevant) cost in time and money "
        "per unit of output, ANCHORED IN THIS SUBJECT MATTER's norms? "
        "Generic SaaS unit economics applied to a non-SaaS business = FAIL."
    ),
    "unit_economics_at_scale": (
        "What are gross margin -> contribution margin -> operating margin "
        "at 1x, 10x, 100x scale, with stated assumptions on what changes "
        "between scale tiers (e.g. fixed-cost amortization, sales-team "
        "structure, COGS curves)? A single margin number = FAIL."
    ),
    "leverage_points": (
        "Which 3-5 SPECIFIC levers, when moved 10%, change the money-ratio "
        "by more than 10%? AND, critically: why are these the leverage "
        "points specifically for THIS subject matter? Generic answers like "
        "'pricing, retention, CAC' without subject-matter justification = FAIL."
    ),
    "attractors": (
        "What 3-5 states will this business naturally drift toward if not "
        "actively piloted? Each must include the 'why is this happening' "
        "mechanism — not just the destination state. 'We'll lose focus' = FAIL."
    ),
    "collapse_points": (
        "What 3-5 states destroy the business? Each must include mechanism, "
        "lead-time, and a detectable early signal that operators can watch "
        "for. Risk register entries without mechanism or signal = FAIL."
    ),
    "next_pilot_move_chain_visible": (
        "Given the goal-plot and the present, what is the SINGLE most "
        "leveraged concrete next move, AND is the causal chain visible "
        "end-to-end? Format must be: 'doing X moves leverage point Y by Z%, "
        "which moves margin M by N%, which moves us from present P toward "
        "goal G.' Action list without the chain = FAIL."
    ),
}

QUESTION_KEYS = list(BOUNDARY_QUESTIONS.keys())


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "You are a senior business operations analyst and auditor. Your job "
    "is NOT to write the business plan. Your job is to AUDIT a draft "
    "deliverable against 6 specific boundary-condition questions and "
    "determine whether the operational <-> money-ratio chain CONNECTS "
    "for this specific business in this specific subject matter.\n"
    "\n"
    "You are deliberately skeptical. Generic answers fail. Subject-matter "
    "specificity is required at every gate. The 'next pilot move' question "
    "is the strictest gate — the causal chain back to the goal must be "
    "visible end-to-end, not implied.\n"
    "\n"
    "Return ONLY a valid JSON object with the exact schema described. "
    "No markdown fences. No commentary outside the JSON."
)


def _build_audit_prompt(
    deliverable: str,
    business_spec: Dict[str, Any],
    goal_plot: Optional[Dict[str, Any]] = None,
) -> str:
    """Assemble the audit prompt the detector sends to the LLM."""

    questions_block = "\n\n".join(
        f"  Q{i+1}. {key}\n     {text}"
        for i, (key, text) in enumerate(BOUNDARY_QUESTIONS.items())
    )

    business_block = json.dumps(business_spec, indent=2)[:2000]
    goal_block = (
        json.dumps(goal_plot, indent=2)[:1500]
        if goal_plot else "(no goal plot provided — judge against the business_spec only)"
    )

    deliverable_block = deliverable[:12000]  # cap to avoid token blowout

    schema_block = '''{
  "per_question": {
    "operational_cost_per_function":      {"answered": bool, "quality": 0.0-1.0, "gaps": ["..."], "notes": "..."},
    "unit_economics_at_scale":            {"answered": bool, "quality": 0.0-1.0, "gaps": ["..."], "notes": "..."},
    "leverage_points":                    {"answered": bool, "quality": 0.0-1.0, "gaps": ["..."], "notes": "..."},
    "attractors":                         {"answered": bool, "quality": 0.0-1.0, "gaps": ["..."], "notes": "..."},
    "collapse_points":                    {"answered": bool, "quality": 0.0-1.0, "gaps": ["..."], "notes": "..."},
    "next_pilot_move_chain_visible":      {"answered": bool, "quality": 0.0-1.0, "gaps": ["..."], "notes": "..."}
  },
  "next_pilot_move_chain_visible": bool,
  "satisfied":                     bool,
  "score":                         0.0-1.0,
  "weakest_link":                  "<key from per_question, or null>",
  "missing_density_for":           ["<specific topic for next Magnify pass>", "..."],
  "reason":                        "<one paragraph summary of the chain-connection state>"
}'''

    return (
        "=== BUSINESS SPEC ===\n" + business_block +
        "\n\n=== GOAL PLOT ===\n" + goal_block +
        "\n\n=== DRAFT DELIVERABLE TO AUDIT ===\n" + deliverable_block +
        "\n\n=== AUDIT AGAINST THESE 6 BOUNDARY-CONDITION QUESTIONS ===\n" +
        questions_block +
        "\n\n=== DECISION RULES ===\n"
        "  - per_question[k].answered = true ONLY if the deliverable actually answers Q[k]\n"
        "    with subject-matter-specific content (not generic templating).\n"
        "  - per_question[k].quality = 0.0-1.0 measures how well it is answered.\n"
        "    quality >= 0.7 means the gate passes for that question.\n"
        "  - next_pilot_move_chain_visible = true ONLY if Q6 shows the full causal\n"
        "    chain: move -> leverage point -> margin -> distance to goal.\n"
        "  - satisfied = true ONLY if ALL of:\n"
        "      * every per_question[k].answered is true\n"
        "      * every per_question[k].quality >= 0.7\n"
        "      * next_pilot_move_chain_visible is true\n"
        "  - score = average of all per_question quality values.\n"
        "  - weakest_link = the question key with the lowest quality. null if satisfied.\n"
        "  - missing_density_for = 1-5 specific topics the next Magnify pass should\n"
        "    drill into to close the gap. Each must be a concrete, specific topic\n"
        "    (e.g. 'wholesale-vs-DTC contribution-margin breakdown for boutique\n"
        "    coffee roasters at 10k bags/year'), not a generic category.\n"
        "  - reason = one paragraph, plain English, suitable for a status log.\n"
        "\n"
        "=== RETURN ONLY THIS JSON SCHEMA ===\n" + schema_block + "\n"
    )


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------

def _extract_json(raw: str) -> Optional[Dict[str, Any]]:
    """Permissive JSON extraction from an LLM response.

    Strategies in order:
        1. Direct json.loads
        2. Strip ```json fences if present
        3. Greedy {...} regex match
        4. Return None if all fail (caller decides what to do)
    """
    if not raw:
        return None

    # Strategy 1
    try:
        return json.loads(raw)
    except Exception:
        pass

    # Strategy 2 — strip code fences
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.MULTILINE)
    if cleaned != raw:
        try:
            return json.loads(cleaned)
        except Exception:
            pass

    # Strategy 3 — greedy object match
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            return None

    return None


def _result_from_parsed(
    parsed: Dict[str, Any],
    raw: str,
    elapsed: float,
    provider: str,
) -> BoundaryResult:
    """Build a BoundaryResult from parsed LLM JSON, with defensive defaults."""

    per_q_raw = parsed.get("per_question") or {}
    per_q: Dict[str, Dict[str, Any]] = {}

    for key in QUESTION_KEYS:
        entry = per_q_raw.get(key) or {}
        per_q[key] = {
            "answered": bool(entry.get("answered", False)),
            "quality":  float(entry.get("quality", 0.0) or 0.0),
            "gaps":     list(entry.get("gaps", []) or [])[:10],
            "notes":    str(entry.get("notes", ""))[:1000],
        }

    # Derive score if LLM didn't compute it sensibly
    qualities = [v["quality"] for v in per_q.values()]
    derived_score = sum(qualities) / len(qualities) if qualities else 0.0
    score = float(parsed.get("score", derived_score) or derived_score)

    # Pin the strict gate
    chain_visible = bool(parsed.get("next_pilot_move_chain_visible", False))

    # Recompute satisfied locally — never trust LLM self-report on this
    all_answered = all(v["answered"] for v in per_q.values())
    all_quality_pass = all(v["quality"] >= 0.7 for v in per_q.values())
    satisfied_strict = all_answered and all_quality_pass and chain_visible

    # If LLM says satisfied but we say no, defer to strict.
    # (This is intentionally conservative — false positives are worse
    # than false negatives because they let the loop terminate too early.)
    satisfied = satisfied_strict

    # Weakest link
    weakest = parsed.get("weakest_link")
    if not satisfied:
        lowest_key, lowest_q = None, 1.1
        for k, v in per_q.items():
            if v["quality"] < lowest_q:
                lowest_q, lowest_key = v["quality"], k
        weakest = lowest_key or weakest

    missing = list(parsed.get("missing_density_for", []) or [])[:5]
    missing = [str(m)[:300] for m in missing]

    reason = str(parsed.get("reason", ""))[:2000]
    if not reason:
        reason = (
            f"score={score:.2f}, chain_visible={chain_visible}, "
            f"weakest_link={weakest}, satisfied={satisfied}"
        )

    return BoundaryResult(
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
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def evaluate(
    deliverable: str,
    business_spec: Dict[str, Any],
    goal_plot: Optional[Dict[str, Any]] = None,
    *,
    llm=None,
    max_tokens: int = 3000,
    temperature: float = 0.2,
) -> BoundaryResult:
    """
    Audit a draft deliverable for boundary-condition satisfaction.

    Args:
        deliverable:   The draft text being audited. The full content
                       field from the executor, typically 6-30k chars.
        business_spec: Structured business definition. Required keys:
                       {name, subject_matter, business_class}.
                       Optional keys: {scale, geography, channels, ...}.
        goal_plot:     Output of the Goal Plotter (PCR-060b). Optional —
                       if not provided, the detector judges against
                       business_spec alone (slightly more permissive).
        llm:           Override LLM provider for testing. If None,
                       constructs MurphyLLMProvider() lazily so this
                       module is importable without env credentials.
        max_tokens:    Cap on detector's own JSON output. 3000 is plenty.
        temperature:   Low (0.2) — we want consistent audit judgments,
                       not creative ones.

    Returns:
        BoundaryResult — see dataclass docstring.

    Raises:
        Never raises for normal LLM/parse failures. Returns a
        BoundaryResult with satisfied=False, error=<reason>.
        Caller can branch on result.error.
    """

    if not deliverable or not deliverable.strip():
        return BoundaryResult(
            satisfied=False, score=0.0,
            weakest_link=None,
            missing_density_for=["deliverable is empty — fire Magnify pass 1"],
            per_question={
                k: {"answered": False, "quality": 0.0, "gaps": ["empty deliverable"], "notes": ""}
                for k in QUESTION_KEYS
            },
            next_pilot_move_chain_visible=False,
            reason="Empty deliverable — cannot audit. Fire initial Magnify pass.",
            error="empty_deliverable",
        )

    if not business_spec or not isinstance(business_spec, dict):
        return BoundaryResult(
            satisfied=False, score=0.0,
            weakest_link=None,
            missing_density_for=["business_spec is missing — Goal Plotter must run first"],
            per_question={
                k: {"answered": False, "quality": 0.0, "gaps": ["no business_spec"], "notes": ""}
                for k in QUESTION_KEYS
            },
            next_pilot_move_chain_visible=False,
            reason="No business_spec — cannot audit subject-matter specificity.",
            error="missing_business_spec",
        )

    # Lazy import — keeps module importable in environments without creds
    if llm is None:
        try:
            from src.llm_provider import MurphyLLMProvider
            llm = MurphyLLMProvider()
        except Exception as e:
            LOG.exception("failed to instantiate MurphyLLMProvider")
            return BoundaryResult(
                satisfied=False, score=0.0,
                weakest_link=None,
                missing_density_for=[],
                per_question={
                    k: {"answered": False, "quality": 0.0, "gaps": ["no llm provider"], "notes": ""}
                    for k in QUESTION_KEYS
                },
                next_pilot_move_chain_visible=False,
                reason=f"LLM provider unavailable: {e}",
                error=f"llm_unavailable:{e}",
            )

    audit_prompt = _build_audit_prompt(deliverable, business_spec, goal_plot)

    t0 = time.time()
    try:
        resp = llm.complete(
            prompt=audit_prompt,
            system=SYSTEM_PROMPT,
            max_tokens=max_tokens,
            temperature=temperature,
            deterministic=False,
        )
    except Exception as e:
        LOG.exception("boundary detector LLM call failed")
        return BoundaryResult(
            satisfied=False, score=0.0,
            weakest_link=None,
            missing_density_for=[],
            per_question={
                k: {"answered": False, "quality": 0.0, "gaps": ["llm call failed"], "notes": ""}
                for k in QUESTION_KEYS
            },
            next_pilot_move_chain_visible=False,
            reason=f"LLM call failed: {e}",
            error=f"llm_call_failed:{e}",
            latency_seconds=time.time() - t0,
        )

    elapsed = time.time() - t0
    raw = (resp.content or "") if resp else ""
    provider = (resp.provider or "unknown") if resp else "unknown"

    parsed = _extract_json(raw)
    if parsed is None:
        return BoundaryResult(
            satisfied=False, score=0.0,
            weakest_link=None,
            missing_density_for=["detector returned unparseable JSON — retry Magnify"],
            per_question={
                k: {"answered": False, "quality": 0.0, "gaps": ["unparseable detector output"], "notes": ""}
                for k in QUESTION_KEYS
            },
            next_pilot_move_chain_visible=False,
            reason="Detector LLM returned unparseable JSON. Treating as not-satisfied.",
            error="unparseable_json",
            raw_response=raw[:5000],
            latency_seconds=elapsed,
            provider=provider,
        )

    return _result_from_parsed(parsed, raw, elapsed, provider)


# ---------------------------------------------------------------------------
# Convenience: stringify for logs
# ---------------------------------------------------------------------------

def summarize(result: BoundaryResult) -> str:
    """One-line summary suitable for log lines and bus notifications."""
    icon = "✓" if result.satisfied else "✗"
    return (
        f"{icon} boundary satisfied={result.satisfied} "
        f"score={result.score:.2f} "
        f"chain_visible={result.next_pilot_move_chain_visible} "
        f"weakest={result.weakest_link or '-'} "
        f"missing={len(result.missing_density_for)} "
        f"provider={result.provider} "
        f"latency={result.latency_seconds:.1f}s"
    )
