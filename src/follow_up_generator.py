"""
Ship 31u — Follow-up question generator.

Design contract:
  - ONE targeted question appended to every reply (not a separate email)
  - The question must earn a reply — specific, role-aware, low-friction
  - Question goes BEFORE ad block, AFTER main reply body
  - Each follow-up is tracked so we can measure reply-back rate
  - Role-tailored: MEP engineer gets engineering questions, not generic ones

Why follow-ups matter:
  - Turn 1-shot reply into 3-shot thread (3x adoption signal density)
  - Sharpen agent ratings via per-role engagement metrics
  - Move strangers from "saw a reply" to "actually engaged"

Threshold: skip follow-up if reply is already a question itself,
or if the reply explicitly says "I'll send X tomorrow" (would feel pushy).
"""
import os
import re
import logging
import sqlite3
import json
from datetime import datetime, timezone

DB = "/var/lib/murphy-production/entity_graph.db"
logger = logging.getLogger("follow_up_generator")


# Role → question style hints. The LLM is steered, not constrained.
_ROLE_HINTS = {
    "mep_engineer": "engineering tradeoffs, code references, drawing rev levels",
    "fde": "current stack, deployment frequency, on-call rotation",
    "risk_lawyer": "jurisdiction, contract length, counterparty leverage",
    "cfo": "fiscal year cadence, board reporting style, current systems",
    "lawyer": "matter type, billable model, current case management",
    "recruiter": "role volume, sourcing channels, current ATS",
    "ceo": "team size, capital state, growth bottleneck",
    "founder": "stage (idea / mvp / scaling), team size, runway",
    "sales": "deal size, sales motion, current CRM",
    "developer": "tech stack, team size, current pain point",
    "manager": "team size, reporting cadence, current tooling",
}

_DEFAULT_HINT = "one specific operational detail that would change Murphy's answer"


def _should_skip_followup(reply_text: str) -> bool:
    """Don't append a question if the reply already ends with one,
    or if Murphy already committed to a specific next action.
    """
    if not reply_text or len(reply_text) < 100:
        return True

    tail = reply_text.strip()[-300:].lower()

    # Already ends in a question
    if tail.rstrip().endswith("?"):
        return True

    # Already committed to a concrete next step with specific deliverable
    skip_phrases = (
        "i'll send", "i will send", "i'll deliver", "i will deliver",
        "by tomorrow", "by friday", "by monday",
        "within 24 hours", "within an hour",
    )
    if any(p in tail for p in skip_phrases):
        return True

    return False


def _llm_generate_question(
    role_hint: str,
    vertical: str,
    inbound_subject: str,
    inbound_body: str,
    murphy_reply: str,
) -> str:
    """Ask the LLM for ONE pointed question. Returns "" on any failure."""
    style_hint = _ROLE_HINTS.get(role_hint, _DEFAULT_HINT)

    prompt = (
        f"You just sent this reply to a {role_hint or 'professional'} "
        f"in the {vertical or 'general'} domain:\n\n"
        f"--- their inbound ---\n"
        f"Subject: {inbound_subject}\n"
        f"Body: {inbound_body[:600]}\n\n"
        f"--- your reply ---\n"
        f"{murphy_reply[:800]}\n\n"
        f"Now generate ONE short follow-up question to ask them.\n"
        f"Rules:\n"
        f"- One sentence, under 20 words\n"
        f"- Specific and low-friction (they can answer in 30 seconds)\n"
        f"- Focused on {style_hint}\n"
        f"- DO NOT ask for budget, timeline, or company size (boring)\n"
        f"- DO NOT ask 'how can I help' (open-ended garbage)\n"
        f"- Start with a verb or a 'What/Which/How' word\n\n"
        f"Respond with JUST the question, nothing else. No prefix."
    )

    try:
        # Use production LLM helper (whatever provider it wraps)
        from src.stranger_responder import _llm_complete
        out = _llm_complete(prompt, model_hint="fast", max_tokens=80)
        if not out or not out.get("text"):
            logger.info("follow_up: _llm_complete returned nothing")
            return ""
        q = (out.get("text") or "").strip()
        # Strip any quote wrapping
        q = q.strip('"\'').strip()
        # Take only the first line (LLMs sometimes ramble)
        q = q.split("\n")[0].strip()
        # Sanity check
        if not q or len(q) > 200 or "?" not in q:
            logger.info("follow_up: rejected '%s' (len=%d)", q[:60], len(q))
            return ""
        return q
    except Exception as exc:
        logger.warning("follow_up LLM failed: %s", exc)
        return ""


def maybe_append_followup(
    reply_text: str,
    role_hint: str = "",
    vertical: str = "",
    inbound_subject: str = "",
    inbound_body: str = "",
    from_addr: str = "",
) -> tuple:
    """Append a follow-up question to a reply if appropriate.

    Returns (modified_reply, followup_metadata_dict).
    On any failure or skip, returns (original_reply, {"appended": False, ...}).
    """
    meta = {"appended": False, "reason": "", "question": "", "role": role_hint}

    if _should_skip_followup(reply_text):
        meta["reason"] = "skipped_natural_ending"
        return reply_text, meta

    question = _llm_generate_question(
        role_hint, vertical, inbound_subject, inbound_body, reply_text
    )
    if not question:
        meta["reason"] = "llm_no_question"
        return reply_text, meta

    # Inject question BEFORE the ad block (if any) — find the "— — —" marker
    ad_marker = "\n— — —\n"
    if ad_marker in reply_text:
        before, sep, after = reply_text.partition(ad_marker)
        # Strip trailing signature line if present, then append question
        modified = before.rstrip() + "\n\n" + question + "\n" + sep + after
    else:
        modified = reply_text.rstrip() + "\n\n" + question

    meta["appended"] = True
    meta["question"] = question
    meta["reason"] = "ok"

    # Persist to log
    _log_followup(role_hint, vertical, from_addr, question)

    return modified, meta


def _log_followup(role_hint: str, vertical: str, from_addr: str, question: str):
    """Record the follow-up so we can measure reply-back rate later."""
    try:
        c = sqlite3.connect(DB)
        c.execute("""CREATE TABLE IF NOT EXISTS followup_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sent_ts TEXT NOT NULL,
            role_hint TEXT,
            vertical TEXT,
            from_addr TEXT,
            question TEXT,
            reply_back_received INTEGER DEFAULT 0,
            reply_back_ts TEXT
        )""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_fu_from ON followup_log(from_addr)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_fu_ts ON followup_log(sent_ts DESC)")
        c.execute("""INSERT INTO followup_log
            (sent_ts, role_hint, vertical, from_addr, question)
            VALUES (?,?,?,?,?)""",
            (datetime.now(timezone.utc).isoformat(),
             role_hint, vertical, from_addr, question))
        c.commit()
        c.close()
    except Exception as exc:
        logger.warning("_log_followup failed: %s", exc)


def get_followup_stats():
    """Return aggregate stats for /os/agent-leaderboard or a dashboard."""
    try:
        c = sqlite3.connect(DB)
        c.row_factory = sqlite3.Row
        total = c.execute("SELECT COUNT(*) FROM followup_log").fetchone()[0]
        replied = c.execute(
            "SELECT COUNT(*) FROM followup_log WHERE reply_back_received=1"
        ).fetchone()[0]
        by_role = c.execute("""SELECT role_hint, COUNT(*) sent,
            SUM(reply_back_received) replied
            FROM followup_log GROUP BY role_hint
            ORDER BY sent DESC""").fetchall()
        c.close()
        return {
            "total_sent": total,
            "total_replied": replied,
            "reply_rate": (replied / total) if total else 0,
            "by_role": [dict(r) for r in by_role],
        }
    except Exception as exc:
        logger.warning("get_followup_stats failed: %s", exc)
        return {"total_sent": 0, "total_replied": 0, "reply_rate": 0, "by_role": []}
