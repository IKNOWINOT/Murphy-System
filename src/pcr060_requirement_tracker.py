"""PCR-060j — Requirements-as-set tracker for the boundary loop.

Founder reframe: the prompt dictates requirements; solving them shows
progress; math is the flow of that and predicting it in terms of
surface space + success/failure boundaries.

This module captures the requirements layer:
- extract_requirements(prompt) → list[Requirement] (LLM, iter 0, cached)
- evaluate_solved(deliverable, requirements) → SolvedSet (LLM, sampled)
- compute_boundary(solved_set, delta) → BoundaryVerdict (deterministic)

Per Murphy consult A/Z/ω/γ 2026-06-10 05:30 UTC.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

log = logging.getLogger("murphy.pcr060j")


@dataclass
class Requirement:
    """A discrete requirement extracted from a prompt."""
    id: str                  # e.g. "req_001"
    text: str                # natural-language statement
    category: str            # "functional" | "quality" | "constraint" | "jurisdiction"
    evaluable_question: str  # yes/no question for the evaluator


@dataclass
class RequirementStatus:
    """Evaluation result for one requirement against one deliverable."""
    requirement_id: str
    status: str              # "addressed" | "partial" | "unaddressed" | "impossible"
    evidence: str = ""       # what in the deliverable supports the verdict
    confidence: str = "medium"  # "high" | "medium" | "low"


@dataclass
class SolvedSet:
    """All requirement statuses for one iteration."""
    iteration: int
    statuses: List[RequirementStatus] = field(default_factory=list)
    solved_count: int = 0
    partial_count: int = 0
    unaddressed_count: int = 0
    impossible_count: int = 0
    total_count: int = 0

    @property
    def solved_ratio(self) -> float:
        """|S| / |R̂| treating partial as 0.5."""
        if self.total_count == 0:
            return 0.0
        return (self.solved_count + 0.5 * self.partial_count) / self.total_count

    @property
    def has_impossible(self) -> bool:
        return self.impossible_count > 0


@dataclass
class BoundaryVerdict:
    """The success/failure call after looking at all signals."""
    state: str               # "success" | "failure_impossible" | "failure_stalled" | "polish" | "drilling"
    reason: str
    solved_ratio: float
    delta: float
    has_impossible: bool = False


# ─────────────────────────────────────────────────────────────────────
# Extraction (LLM at iter 0, cached for the drill)
# ─────────────────────────────────────────────────────────────────────

EXTRACT_PROMPT_TEMPLATE = """You are extracting REQUIREMENTS from a user prompt.
A requirement is a discrete, testable thing the deliverable must do or be.
DO NOT include style/quality preferences; those are measured separately.

For this prompt:
{prompt}

Enumerate up to 12 requirements as JSON. Each must have:
- id: "req_001", "req_002", etc.
- text: the requirement in plain English (≤20 words)
- category: one of "functional", "constraint", "jurisdiction", "domain"
- evaluable_question: a yes/no question to check if a deliverable addresses it

Return ONLY a JSON array, no preamble. Example shape:
[
  {{"id":"req_001","text":"Targets CPAs as primary user","category":"domain",
    "evaluable_question":"Does the deliverable identify CPAs as the primary user?"}}
]
"""


def extract_requirements(
    prompt: str,
    *,
    api_key: Optional[str] = None,
    max_requirements: int = 12,
) -> List[Requirement]:
    """LLM-extract discrete requirements from a prompt.

    Returns empty list on any failure (caller falls back to Δ-only loop).
    """
    if not prompt or not isinstance(prompt, str) or len(prompt.strip()) < 5:
        return []

    api_key = api_key or os.environ.get("MURPHY_FOUNDER_KEY")
    if not api_key:
        log.warning("[060j] no api_key; skipping requirement extraction")
        return []

    extract_prompt = EXTRACT_PROMPT_TEMPLATE.format(prompt=prompt.strip())

    try:
        # Use murphy.systems chat-v2 endpoint
        import urllib.request
        import urllib.error

        body = json.dumps({
            "session_id": f"req_extract_{abs(hash(prompt)) % 10**10}",
            "message": extract_prompt,
        }).encode("utf-8")

        req = urllib.request.Request(
            "https://murphy.systems/api/chat-v2",
            data=body,
            headers={
                "Content-Type": "application/json",
                "X-API-Key": api_key,
                "User-Agent": "Murphy-Internal/1.0 (PCR-060j)",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        reply = data.get("reply", "")
        # Extract first JSON array from the reply
        start = reply.find("[")
        end = reply.rfind("]")
        if start == -1 or end == -1 or end < start:
            log.warning("[060j] no JSON array in reply")
            return []

        items = json.loads(reply[start:end + 1])
        if not isinstance(items, list):
            return []

        reqs: List[Requirement] = []
        for i, item in enumerate(items[:max_requirements]):
            if not isinstance(item, dict):
                continue
            try:
                reqs.append(Requirement(
                    id=str(item.get("id", f"req_{i+1:03d}")),
                    text=str(item.get("text", "")).strip(),
                    category=str(item.get("category", "functional")).lower(),
                    evaluable_question=str(item.get("evaluable_question", "")).strip(),
                ))
            except Exception:
                continue
        return [r for r in reqs if r.text and r.evaluable_question]
    except Exception as e:
        log.warning("[060j] extract_requirements failed: %s", e)
        return []


# ─────────────────────────────────────────────────────────────────────
# Evaluation (LLM, sampled — only re-check unaddressed)
# ─────────────────────────────────────────────────────────────────────

EVALUATE_PROMPT_TEMPLATE = """You are judging whether a deliverable addresses specific requirements.
For EACH requirement, answer with one verdict:
- "addressed": deliverable clearly addresses this
- "partial": deliverable touches this but incompletely
- "unaddressed": deliverable does not address this
- "impossible": this requirement CANNOT be addressed (out of scope, jurisdiction, capability)

DELIVERABLE:
{deliverable}

REQUIREMENTS TO JUDGE:
{requirements}

Return ONLY a JSON array, no preamble:
[
  {{"requirement_id":"req_001","status":"addressed","evidence":"mentions CPA workflow in section 2","confidence":"high"}},
  ...
]
"""


def evaluate_solved(
    deliverable: Dict[str, Any],
    requirements: List[Requirement],
    *,
    iteration: int = 0,
    prior: Optional[SolvedSet] = None,
    api_key: Optional[str] = None,
) -> SolvedSet:
    """Judge each requirement against the deliverable.

    Sampling per Murphy A/Z: only re-evaluate requirements that were
    unaddressed/partial last time. Previously-addressed reqs carry forward
    (assumes deliverable doesn't regress within a drill).
    """
    if not requirements:
        return SolvedSet(iteration=iteration, total_count=0)

    api_key = api_key or os.environ.get("MURPHY_FOUNDER_KEY")
    if not api_key:
        return SolvedSet(iteration=iteration, total_count=len(requirements))

    # Determine which reqs need re-evaluation (Z: sampled)
    carry_forward: Dict[str, RequirementStatus] = {}
    to_evaluate: List[Requirement] = []
    if prior is None:
        to_evaluate = list(requirements)
    else:
        prior_map = {s.requirement_id: s for s in prior.statuses}
        for req in requirements:
            ps = prior_map.get(req.id)
            if ps and ps.status in ("addressed", "impossible"):
                carry_forward[req.id] = ps  # stable verdicts carry
            else:
                to_evaluate.append(req)

    statuses: List[RequirementStatus] = list(carry_forward.values())

    if to_evaluate:
        # Compact deliverable for the prompt
        deliverable_text = json.dumps(deliverable, indent=2)[:4000]
        req_text = "\n".join(
            f"  - {r.id}: {r.evaluable_question}" for r in to_evaluate
        )
        eval_prompt = EVALUATE_PROMPT_TEMPLATE.format(
            deliverable=deliverable_text,
            requirements=req_text,
        )

        try:
            import urllib.request

            body = json.dumps({
                "session_id": f"req_eval_iter{iteration}_{abs(hash(deliverable_text)) % 10**10}",
                "message": eval_prompt,
            }).encode("utf-8")

            req = urllib.request.Request(
                "https://murphy.systems/api/chat-v2",
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "X-API-Key": api_key,
                "User-Agent": "Murphy-Internal/1.0 (PCR-060j)",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=45) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            reply = data.get("reply", "")
            start = reply.find("[")
            end = reply.rfind("]")
            if start != -1 and end > start:
                items = json.loads(reply[start:end + 1])
                if isinstance(items, list):
                    for item in items:
                        if not isinstance(item, dict):
                            continue
                        rid = str(item.get("requirement_id", ""))
                        status = str(item.get("status", "unaddressed")).lower()
                        if status not in ("addressed", "partial", "unaddressed", "impossible"):
                            status = "unaddressed"
                        statuses.append(RequirementStatus(
                            requirement_id=rid,
                            status=status,
                            evidence=str(item.get("evidence", ""))[:200],
                            confidence=str(item.get("confidence", "medium")).lower(),
                        ))
        except Exception as e:
            log.warning("[060j] evaluate_solved failed: %s", e)
            # Fill missing with unaddressed verdicts so we don't lie
            evaluated_ids = {s.requirement_id for s in statuses}
            for req in to_evaluate:
                if req.id not in evaluated_ids:
                    statuses.append(RequirementStatus(
                        requirement_id=req.id, status="unaddressed",
                        evidence="evaluation failed", confidence="low",
                    ))

    # Tally
    solved = sum(1 for s in statuses if s.status == "addressed")
    partial = sum(1 for s in statuses if s.status == "partial")
    unaddressed = sum(1 for s in statuses if s.status == "unaddressed")
    impossible = sum(1 for s in statuses if s.status == "impossible")

    return SolvedSet(
        iteration=iteration,
        statuses=statuses,
        solved_count=solved,
        partial_count=partial,
        unaddressed_count=unaddressed,
        impossible_count=impossible,
        total_count=len(requirements),
    )


# ─────────────────────────────────────────────────────────────────────
# Boundary verdict (deterministic — combines |S|/|R̂| with Δ)
# ─────────────────────────────────────────────────────────────────────

def compute_boundary(
    solved_set: Optional[SolvedSet],
    delta: float,
    *,
    solved_threshold: float = 0.85,
    delta_threshold: float = 0.20,
    d_solved_dt: Optional[float] = None,
    d_delta_dt: Optional[float] = None,
    flatline_epsilon: float = 0.02,
    flatline_streak: int = 0,
    max_flatline_streak: int = 2,
) -> BoundaryVerdict:
    """Combine |S|/|R̂| and Δ into a single boundary verdict.

    Per Murphy Q3=ω: |S|/|R̂| is the gate, Δ is the polish.
    Per Murphy Q4=γ: discrete failure (impossible) AND continuous (stalled).

    States:
      success            — solved_ratio >= threshold AND delta <= polish_threshold
      polish             — solved_ratio >= threshold but delta still high (keep going on quality)
      failure_impossible — any requirement marked impossible (discrete failure α)
      failure_stalled    — dS/dt and dΔ/dt both flat for max_flatline_streak (continuous failure β)
      drilling           — neither success nor failure yet, keep iterating
    """
    if solved_set is None:
        # Fall back to Δ-only behavior
        if delta <= delta_threshold:
            return BoundaryVerdict("success", "no requirements tracked; Δ converged",
                                    0.0, delta)
        return BoundaryVerdict("drilling", "no requirements tracked; Δ above threshold",
                                0.0, delta)

    ratio = solved_set.solved_ratio

    # γ-α: discrete failure on impossible requirement
    if solved_set.has_impossible:
        return BoundaryVerdict(
            state="failure_impossible",
            reason=f"{solved_set.impossible_count} requirement(s) marked impossible",
            solved_ratio=ratio, delta=delta, has_impossible=True,
        )

    # Success: gate AND polish both pass
    if ratio >= solved_threshold and delta <= delta_threshold:
        return BoundaryVerdict(
            state="success",
            reason=f"|S|/|R̂|={ratio:.2f}>={solved_threshold} and Δ={delta:.3f}<={delta_threshold}",
            solved_ratio=ratio, delta=delta,
        )

    # Polish: gate passed, quality not yet
    if ratio >= solved_threshold:
        return BoundaryVerdict(
            state="polish",
            reason=f"|S|/|R̂|={ratio:.2f} OK, Δ={delta:.3f} still > {delta_threshold} (polishing)",
            solved_ratio=ratio, delta=delta,
        )

    # γ-β: continuous failure if both signals flat
    if (d_solved_dt is not None and d_delta_dt is not None
            and abs(d_solved_dt) < flatline_epsilon
            and abs(d_delta_dt) < flatline_epsilon
            and flatline_streak >= max_flatline_streak):
        return BoundaryVerdict(
            state="failure_stalled",
            reason=f"|dS/dt|={abs(d_solved_dt):.3f} and |dΔ/dt|={abs(d_delta_dt):.3f} "
                   f"both < {flatline_epsilon} for {flatline_streak} iterations",
            solved_ratio=ratio, delta=delta,
        )

    return BoundaryVerdict(
        state="drilling",
        reason=f"|S|/|R̂|={ratio:.2f} (need {solved_threshold}), Δ={delta:.3f}",
        solved_ratio=ratio, delta=delta,
    )


def solved_set_to_dict(ss: SolvedSet) -> Dict[str, Any]:
    """Serialize for storage/logging."""
    return {
        "iteration": ss.iteration,
        "solved_count": ss.solved_count,
        "partial_count": ss.partial_count,
        "unaddressed_count": ss.unaddressed_count,
        "impossible_count": ss.impossible_count,
        "total_count": ss.total_count,
        "solved_ratio": ss.solved_ratio,
        "statuses": [asdict(s) for s in ss.statuses],
    }
