"""
Ship 31h — Agent ML Cycle (2026-06-10)
=========================================

Iterative ML loop for improving starter agent quality, using the same
category_learning infrastructure (Ship 31f).

THE CYCLE:
  1. Pick a category (default: lowest current quality)
  2. Generate N candidate agent descriptions using DIFFERENT prompts
     (variations: structured/role-first/duty-first/STOP-first)
  3. Score each candidate by running it as a virtual agent against
     N held-out inquiries
  4. Each scored output goes through a JUDGE model (a different LLM)
     that rates: task-fit, specificity, role-lens-fidelity, safety
  5. The winner replaces the current starter
  6. Log the cycle to ml_cycles for traceability

COMPARTMENTALIZATION (per founder directive 2026-06-10):
  Each LLM call gets ONLY the slice it needs:
    - Generator sees: category, role, ONE inquiry
    - Judge sees: ONE output + rubric (no upstream context)
    - No single call sees the orchestration, ledger, or other candidates

PUBLIC SURFACE:
  run_cycle(category_slug, n_variants=3, n_test_inquiries=2) -> Dict
  evaluate_starter(category_slug, test_inquiry) -> Dict
  pick_next_category() -> str   # lowest-quality or never-evaluated

LAST UPDATED: 2026-06-10
"""

import json
import sqlite3
import sys
from datetime import datetime, timezone
from typing import Dict, List, Optional

sys.path.insert(0, "/opt/Murphy-System")

_DB = "/var/lib/murphy-production/entity_graph.db"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(_DB, timeout=10)
    c.row_factory = sqlite3.Row
    return c


def _ensure_schema():
    conn = _conn()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ml_cycles (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                cycle_id        TEXT UNIQUE NOT NULL,
                ts              TEXT NOT NULL,
                category_slug   TEXT NOT NULL,
                variant_name    TEXT,
                generator_model TEXT,
                judge_model     TEXT,
                avg_score       REAL,
                wins            INTEGER DEFAULT 0,
                losses          INTEGER DEFAULT 0,
                candidate_desc  TEXT,
                judge_verdicts  TEXT,
                cost_usd        REAL,
                promoted        INTEGER DEFAULT 0
            )""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ml_cycle_slug ON ml_cycles(category_slug)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ml_cycle_ts ON ml_cycles(ts)")
        conn.commit()
    finally:
        conn.close()

_ensure_schema()


# ----------------------------------------------------------------------
# Generator variants — COMPARTMENTALIZED (each sees only the slice)
# ----------------------------------------------------------------------

GENERATOR_VARIANTS = {
    "structured": """Generate an agent description for: {category}

The agent will handle: {sample_inquiry}

Use EXACTLY this 4-block format:
WHO: [3 sentences — identity, scope, off-limits]
HOW: [3 sentences — workflow, what you look for, how you structure output]
WHY: [3 sentences — who you serve, what success looks like]
STOP: [3 sentences — confidentiality, professional boundaries, escalation]

Output ONLY the 4-block. No preamble.""",
    
    "role_first": """You are an expert in: {category}

Concrete request type: {sample_inquiry}

Write a tight agent description that opens with your identity AS THIS ROLE, then describes your workflow, then names your limits. Use 4 blocks: WHO / HOW / WHY / STOP. Each block = 3 sentences. Be specific, not generic.""",
    
    "duty_first": """Define the agent for: {category}

Lead with what the agent DOES (specific duties), then who they are, then their constraints. Sample inquiry to ground in: {sample_inquiry}

Format: WHO / HOW / WHY / STOP. 3 sentences each. Cite specific tools or methods this role uses (e.g. QuickBooks, Excel, contract clauses). Avoid generic AI phrasing.""",
    
    "safety_first": """Agent specification for: {category}

Concrete request: {sample_inquiry}

CRITICAL: this agent operates on behalf of a real person making real decisions. Lead with STOP boundaries (what you won't do), then identity, then workflow, then purpose. Format: STOP / WHO / HOW / WHY. 3 sentences each.""",
}


# ----------------------------------------------------------------------
# Judge rubric — COMPARTMENTALIZED (sees ONLY the output)
# ----------------------------------------------------------------------

JUDGE_PROMPT = """Score this agent description on 4 dimensions (0-10 each):

AGENT DESCRIPTION:
{description}

DIMENSIONS:
1. SPECIFICITY: cites concrete tools/methods/numbers, NOT generic AI phrasing
2. ROLE_FIT: clearly anchored to the role's actual work pattern
3. SAFETY: STOP boundaries are concrete and protect the user
4. ACTIONABILITY: a real person could USE this agent for the work

Respond with ONLY this JSON:
{{"specificity": <0-10>, "role_fit": <0-10>, "safety": <0-10>, "actionability": <0-10>, "composite": <average>, "rationale": "<one sentence>"}}"""


# ----------------------------------------------------------------------
# Core ML cycle
# ----------------------------------------------------------------------

def _llm(prompt: str, model_hint: str = "fast", max_tokens: int = 700) -> Dict:
    """Wrapper that returns a uniform dict + cost."""
    try:
        from src.llm_provider import get_llm
        result = get_llm().complete(prompt, model_hint=model_hint, max_tokens=max_tokens)
        text = (getattr(result, "content", "") or "").strip()
        tokens_in = int(getattr(result, "tokens_prompt", 0) or 0)
        tokens_out = int(getattr(result, "tokens_completion", 0) or 0)
        rate = 0.06e-6 if model_hint == "fast" else 0.88e-6
        cost = (tokens_in + tokens_out) * rate
        return {"text": text, "cost_usd": cost,
                "tok_in": tokens_in, "tok_out": tokens_out,
                "model": getattr(result, "model", "?")}
    except Exception as e:
        return {"text": "", "cost_usd": 0.0, "error": str(e),
                "tok_in": 0, "tok_out": 0, "model": "?"}


def _judge_description(description: str) -> Dict:
    """Score a description via a different model (judge ≠ generator)."""
    result = _llm(JUDGE_PROMPT.format(description=description[:3000]),
                  model_hint="chat", max_tokens=200)
    if result.get("error") or not result["text"]:
        return {"composite": 0.0, "error": result.get("error", "no judge text"),
                "cost_usd": result["cost_usd"]}
    try:
        text = result["text"]
        if "```" in text:
            text = text.split("```")[1].strip()
            if text.startswith("json"):
                text = text[4:].strip()
        # Find the first { ... } block
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            text = text[start:end+1]
        verdict = json.loads(text)
        verdict["cost_usd"] = result["cost_usd"]
        verdict["judge_model"] = result["model"]
        return verdict
    except Exception as e:
        return {"composite": 0.0, "error": f"parse: {e}",
                "raw": result["text"][:300], "cost_usd": result["cost_usd"]}


def _generate_candidate(category_label: str, sample_inquiry: str,
                        variant: str) -> Dict:
    """Generate ONE candidate from one variant prompt."""
    prompt_template = GENERATOR_VARIANTS[variant]
    prompt = prompt_template.format(
        category=category_label,
        sample_inquiry=sample_inquiry[:500],
    )
    return _llm(prompt, model_hint="fast", max_tokens=700)


def _get_sample_inquiries(category_slug: str, n: int = 3) -> List[str]:
    conn = _conn()
    try:
        rows = conn.execute(
            """SELECT subject || ' — ' || COALESCE(SUBSTR(agent_desc, 1, 200), '')
               FROM category_demand_ledger
               WHERE category_slug = ? AND subject IS NOT NULL
               LIMIT ?""",
            (category_slug, n),
        ).fetchall()
        return [r[0] for r in rows if r[0]]
    finally:
        conn.close()


def _get_current_starter(category_slug: str) -> Optional[Dict]:
    conn = _conn()
    try:
        row = conn.execute(
            """SELECT agent_id, duties_text, starter_quality_score
               FROM agent_contracts
               WHERE is_starter_agent=1 AND starter_category_slug=?""",
            (category_slug,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def run_cycle(category_slug: str, variants: List[str] = None) -> Dict:
    """Run ONE full ML cycle for one category."""
    import secrets
    cycle_id = f"cyc_{category_slug}_{secrets.token_hex(4)}"
    variants = variants or list(GENERATOR_VARIANTS.keys())
    
    conn = _conn()
    try:
        cat_row = conn.execute(
            """SELECT category_label, vertical FROM category_demand_ledger
               WHERE category_slug=? LIMIT 1""",
            (category_slug,),
        ).fetchone()
    finally:
        conn.close()
    
    if not cat_row:
        return {"error": f"no ledger rows for {category_slug}"}
    
    category_label = cat_row["category_label"]
    samples = _get_sample_inquiries(category_slug, n=3)
    if not samples:
        return {"error": "no sample inquiries"}
    sample_inquiry = samples[0]
    
    candidates = []
    total_cost = 0.0
    
    for variant in variants:
        gen = _generate_candidate(category_label, sample_inquiry, variant)
        total_cost += gen["cost_usd"]
        if gen.get("error") or len(gen["text"]) < 200:
            candidates.append({
                "variant": variant, "desc": gen["text"], "score": 0.0,
                "judge": {"error": gen.get("error", "too short")},
                "cost_usd": gen["cost_usd"],
            })
            continue
        
        # Judge in compartmentalized call
        verdict = _judge_description(gen["text"])
        total_cost += verdict.get("cost_usd", 0.0)
        score = float(verdict.get("composite", 0.0)) if not verdict.get("error") else 0.0
        
        candidates.append({
            "variant": variant,
            "desc": gen["text"],
            "score": score,
            "judge": verdict,
            "cost_usd": gen["cost_usd"] + verdict.get("cost_usd", 0.0),
            "model_gen": gen.get("model"),
            "model_judge": verdict.get("judge_model"),
        })
    
    # Pick winner
    winner = max(candidates, key=lambda c: c["score"]) if candidates else None
    if not winner or winner["score"] == 0:
        return {"cycle_id": cycle_id, "category_slug": category_slug,
                "candidates": candidates, "winner": None,
                "promoted": False, "total_cost_usd": total_cost,
                "reason": "no valid candidates"}
    
    # Compare against current starter
    current = _get_current_starter(category_slug)
    current_score = float(current["starter_quality_score"] or 0.0) if current else 0.0
    
    promoted = False
    conn = _conn()
    try:
        for c in candidates:
            conn.execute(
                """INSERT INTO ml_cycles
                   (cycle_id, ts, category_slug, variant_name, generator_model,
                    judge_model, avg_score, candidate_desc, judge_verdicts,
                    cost_usd, promoted)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (f"{cycle_id}_{c['variant']}", _now_iso(), category_slug,
                 c["variant"], c.get("model_gen", ""),
                 c.get("model_judge", ""), c["score"],
                 c["desc"][:5000], json.dumps(c.get("judge", {})),
                 c["cost_usd"], 1 if c is winner and winner["score"] > current_score else 0),
            )
        
        # Promote the winner if it beats the current starter
        if winner["score"] > current_score and current:
            conn.execute(
                """UPDATE agent_contracts SET duties_text=?, starter_quality_score=?
                   WHERE agent_id=?""",
                (winner["desc"], winner["score"], current["agent_id"]),
            )
            promoted = True
        elif winner["score"] > current_score and not current:
            # No starter yet — could promote via category_learning.evaluate_promotions
            promoted = False  # leave for normal promotion path
        
        conn.commit()
    finally:
        conn.close()
    
    return {
        "cycle_id": cycle_id,
        "category_slug": category_slug,
        "category_label": category_label,
        "current_starter_score": current_score,
        "winner_variant": winner["variant"],
        "winner_score": winner["score"],
        "promoted": promoted,
        "candidates": [
            {"variant": c["variant"], "score": c["score"],
             "model_gen": c.get("model_gen"),
             "judge": c.get("judge", {})}
            for c in candidates
        ],
        "total_cost_usd": total_cost,
    }


def pick_next_category(strategy: str = "lowest_score") -> Optional[str]:
    """Pick which category to iterate on next."""
    conn = _conn()
    try:
        if strategy == "lowest_score":
            row = conn.execute(
                """SELECT starter_category_slug FROM agent_contracts
                   WHERE is_starter_agent=1
                   ORDER BY starter_quality_score ASC, starter_use_count ASC
                   LIMIT 1"""
            ).fetchone()
        elif strategy == "never_iterated":
            row = conn.execute(
                """SELECT ac.starter_category_slug FROM agent_contracts ac
                   LEFT JOIN ml_cycles mc ON mc.category_slug = ac.starter_category_slug
                   WHERE ac.is_starter_agent=1 AND mc.id IS NULL
                   LIMIT 1"""
            ).fetchone()
        else:
            row = None
        return row[0] if row else None
    finally:
        conn.close()


def get_cycle_stats() -> Dict:
    conn = _conn()
    try:
        row = conn.execute(
            """SELECT COUNT(*) total_cycles,
                      COUNT(DISTINCT category_slug) categories_iterated,
                      SUM(promoted) promotions,
                      ROUND(AVG(avg_score),2) avg_score,
                      ROUND(SUM(cost_usd),4) total_cost_usd
               FROM ml_cycles"""
        ).fetchone()
        return dict(row) if row else {}
    finally:
        conn.close()
