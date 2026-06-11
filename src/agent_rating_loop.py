"""
Ship 31s — Agent memory + rating loop.

The contract:
  - Every stranger reply is RATED after the fact by an LLM judge
  - Each (role, vertical) pair persists fitness via EMA blending
  - Top-rated agent per role_signature wins the next routing decision
  - Persisted souls are reused above fitness threshold; otherwise re-synth
  - All decisions are logged for the leaderboard dashboard

Threshold:
  PERSISTED_SOUL_TRUST = 0.65 fitness — below this, re-synthesize fresh
  Above this, reuse cached soul → instant, free, learned-from-history.
"""
import sqlite3
import json
import logging
import os
from datetime import datetime, timezone

DB = "/var/lib/murphy-production/entity_graph.db"
PERSISTED_SOUL_TRUST = 0.65
EMA_ALPHA = 0.30  # new score weight; 0.7 * old + 0.3 * new
LLM_JUDGE_TIMEOUT_S = 12

logger = logging.getLogger("agent_rating_loop")


def role_signature(role_hint: str, vertical: str) -> str:
    """Canonical key: 'mep_engineer:construction', 'cfo:finance', etc."""
    return f"{(role_hint or 'unknown').strip().lower()}:" \
           f"{(vertical or 'general').strip().lower()}"


def get_best_agent_for(role_hint: str, vertical: str):
    """Return persisted soul + fitness for this (role, vertical) if any.

    Returns dict with: agent_id, fitness, soul, deployments, last_used_ts
    or None if no qualifying agent exists.
    """
    sig = role_signature(role_hint, vertical)
    try:
        c = sqlite3.connect(DB)
        c.row_factory = sqlite3.Row
        row = c.execute("""SELECT agent_id, fitness_score, persisted_soul,
                                  deployments, last_used_ts, last_quality_score
            FROM agent_contracts
            WHERE role_signature = ? AND persisted_soul IS NOT NULL
            ORDER BY fitness_score DESC LIMIT 1""", (sig,)).fetchone()
        c.close()
        if not row:
            return None
        return dict(row)
    except Exception as exc:
        logger.warning("get_best_agent_for failed: %s", exc)
        return None


def should_reuse_persisted(agent: dict) -> bool:
    """Trust gate: only reuse souls above fitness threshold."""
    if not agent:
        return False
    fit = agent.get("fitness_score") or 0
    soul = agent.get("persisted_soul") or ""
    return fit >= PERSISTED_SOUL_TRUST and len(soul) > 200


def persist_soul(role_hint: str, vertical: str, soul_text: str,
                  agent_id: str = None):
    """Save a freshly synthesized soul for future routing.

    Idempotent: insert-or-update on role_signature.
    """
    sig = role_signature(role_hint, vertical)
    aid = agent_id or f"stranger_{sig.replace(':', '_')}"
    now = datetime.now(timezone.utc).isoformat()
    try:
        c = sqlite3.connect(DB)
        # Check if already exists
        existing = c.execute(
            "SELECT id, fitness_score FROM agent_contracts WHERE role_signature=?",
            (sig,)
        ).fetchone()
        if existing:
            c.execute("""UPDATE agent_contracts
                SET persisted_soul = ?, persisted_soul_ts = ?
                WHERE role_signature = ?""",
                (soul_text[:8000], now, sig))
        else:
            c.execute("""INSERT INTO agent_contracts
                (id, agent_id, agent_name, role_title, domain, role_signature,
                 fitness_score, persisted_soul, persisted_soul_ts,
                 deployments, total_quality_score, last_quality_score,
                 created_at, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (aid, aid, f"Auto-{sig}", role_hint, vertical, sig,
                 0.6, soul_text[:8000], now,
                 0, 0.0, 0.0,
                 now, now))
        c.commit()
        c.close()
        return True
    except Exception as exc:
        logger.warning("persist_soul failed for %s: %s", sig, exc)
        return False


def record_use_and_rate(role_hint: str, vertical: str,
                         reply_text: str, subject: str = "",
                         body: str = "", cost_usd: float = 0.0,
                         latency_s: float = 0.0,
                         used_persisted_soul: bool = False,
                         routing_decision: str = "",
                         consumer: str = "stranger_responder"):
    """Score this reply via LLM judge, update EMA fitness, log the use.

    Score scale 0.0 - 1.0. Updates agent_contracts.fitness_score using EMA.
    """
    sig = role_signature(role_hint, vertical)
    aid = f"stranger_{sig.replace(':', '_')}"
    now = datetime.now(timezone.utc).isoformat()

    # 1. LLM judge — second opinion on reply quality
    score, rubric = _llm_judge(reply_text, subject, body, role_hint)
    score = max(0.0, min(1.0, score))  # clamp

    # 2. EMA-update fitness
    try:
        c = sqlite3.connect(DB)
        row = c.execute(
            "SELECT fitness_score, deployments, total_quality_score FROM agent_contracts WHERE role_signature=?",
            (sig,)
        ).fetchone()
        if row:
            old_fit, old_dep, old_total = row
            old_fit = old_fit if old_fit is not None else 0.6
            old_dep = old_dep or 0
            old_total = old_total or 0.0
            new_fit = (1 - EMA_ALPHA) * old_fit + EMA_ALPHA * score
            c.execute("""UPDATE agent_contracts
                SET fitness_score = ?,
                    deployments = ?,
                    total_quality_score = ?,
                    last_quality_score = ?,
                    last_used_ts = ?,
                    updated_at = ?
                WHERE role_signature = ?""",
                (new_fit, old_dep + 1, old_total + score, score, now, now, sig))

        # 3. Append to use log
        c.execute("""INSERT INTO agent_use_log
            (used_ts, role_signature, agent_id, consumer, judge_score,
             judge_rubric, reply_excerpt, cost_usd, latency_s,
             used_persisted_soul, routing_decision)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (now, sig, aid, consumer, score, json.dumps(rubric),
             (reply_text or "")[:500], cost_usd, latency_s,
             1 if used_persisted_soul else 0, routing_decision))
        c.commit()
        c.close()
        return {"score": score, "rubric": rubric}
    except Exception as exc:
        logger.warning("record_use_and_rate failed: %s", exc)
        return {"score": score, "rubric": rubric, "persist_error": str(exc)}


def _llm_judge(reply_text: str, subject: str, body: str,
                role_hint: str) -> tuple:
    """Cheap judge on reply quality. Returns (score 0-1, rubric dict).

    Falls back to heuristic scoring if LLM is unavailable.
    """
    try:
        # Use production LLM helper
        from src.stranger_responder import _llm_complete

        prompt = (
            "You are an impartial quality judge for an AI assistant's email replies.\n\n"
            f"ROLE the assistant was playing: {role_hint}\n\n"
            f"INBOUND SUBJECT: {subject}\n\n"
            f"INBOUND BODY:\n{body[:1200]}\n\n"
            f"ASSISTANT REPLY:\n{reply_text[:1500]}\n\n"
            "Score this reply on a 0.0-1.0 scale across 4 dimensions, then "
            "give an overall score. Respond ONLY with valid JSON in this exact shape:\n"
            "{\"relevance\": 0.X, \"actionability\": 0.X, \"role_fit\": 0.X, "
            "\"clarity\": 0.X, \"overall\": 0.X, \"notes\": \"one line\"}"
        )
        out = _llm_complete(prompt, model_hint="fast", max_tokens=200)
        if not out or not out.get("text"):
            return _heuristic_score(reply_text, body)
        raw = (out.get("text") or "").strip()
        # Extract JSON from response
        import re
        m = re.search(r"\{[^}]+\}", raw, re.DOTALL)
        if m:
            data = json.loads(m.group(0))
            overall = float(data.get("overall", 0.5))
            return overall, data
    except Exception as exc:
        logger.info("LLM judge fell back: %s", exc)

    return _heuristic_score(reply_text, body)


def _heuristic_score(reply_text: str, body: str) -> tuple:
    """Fallback scorer if LLM judge unavailable. Conservative defaults."""
    if not reply_text or len(reply_text) < 50:
        return 0.2, {"reason": "too short", "fallback": "heuristic"}
    score = 0.5
    rt = reply_text.lower()
    if any(t in rt for t in ("next step", "i can", "i will", "i'll")):
        score += 0.15
    if any(t in rt for t in ("schedule", "review", "draft", "generate", "analyze")):
        score += 0.10
    if len(reply_text) > 300:
        score += 0.05
    if "—" in reply_text or "->" in reply_text:
        score += 0.05
    return min(score, 0.85), {"fallback": "heuristic", "score": round(score, 2)}


def get_leaderboard(limit: int = 25):
    """Top agents by fitness with deployment counts. For dashboard."""
    try:
        c = sqlite3.connect(DB)
        c.row_factory = sqlite3.Row
        rows = c.execute("""SELECT role_signature, agent_id, fitness_score,
                                   deployments, total_quality_score,
                                   last_quality_score, last_used_ts,
                                   LENGTH(COALESCE(persisted_soul,'')) AS soul_len
            FROM agent_contracts
            WHERE role_signature IS NOT NULL
            ORDER BY fitness_score DESC, deployments DESC
            LIMIT ?""", (limit,)).fetchall()
        c.close()
        return [dict(r) for r in rows]
    except Exception:
        return []


def get_recent_uses(limit: int = 50):
    """Recent agent_use_log entries for dashboard."""
    try:
        c = sqlite3.connect(DB)
        c.row_factory = sqlite3.Row
        rows = c.execute(
            "SELECT * FROM agent_use_log ORDER BY used_ts DESC LIMIT ?",
            (limit,)
        ).fetchall()
        c.close()
        return [dict(r) for r in rows]
    except Exception:
        return []
