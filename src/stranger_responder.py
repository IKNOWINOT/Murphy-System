"""
Ship 31c-pace — Stranger Responder (2026-06-10) — paced + budgeted
==================================================================

PATCH FROM v1 (Ship 31c initial) → v2 (this patch):
  - LLM calls now go through llm_provider.complete() directly with
    model_hint="fast" for magnify-drill (~5x faster, ~10x cheaper),
    keeping "chat" for the reply generation where quality matters
  - Replies route through outbound_email_queue (paced, audited,
    compliance-gated by PCR-090h.1) instead of raw sendmail
  - Per-day budget cap (MAX_DAILY_USD) prevents runaway cost
  - Per-cycle throughput cap respects existing 5-min timer cadence
  - Token usage logged per stranger for cost visibility

ECONOMICS (Llama-3.3-70B chat + Llama-3.1-8B fast on DeepInfra):
  Per stranger reply:
    Magnify-drill (8B fast):  ~1200 tok @ ~$0.0001 + ~3-5s
    Reply gen   (70B chat):   ~1500 tok @ ~$0.0014 + ~10-15s
    Total: ~$0.0015 + ~13-20s per stranger
  
  At 5-min cadence, limit=5 per cycle:
    Max throughput: ~60/hour, ~1,440/day
    Daily cost cap (MAX_DAILY_USD=5.00): ~3,300 strangers/day ceiling
    Realistic: 100-500/day comfortable

SAFETY LAYERS:
  1. _SHADOW_MODE (still True by default) — drafts go to founder first
  2. Rate limit: 5 per sender domain per 24h
  3. Daily $ cap: stop processing if spend > MAX_DAILY_USD
  4. Outbound queue: passes through PCR-090h.1 compliance gate
  5. Queue depth pacing: skip cycle if outbound queue > MAX_QUEUE_DEPTH

PUBLIC SURFACE:
  process_stranger_inquiries(limit=5) -> dict

LAST UPDATED: 2026-06-10 — paced + budgeted
"""

import json
import logging
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

logger = logging.getLogger("stranger_responder")

sys.path.insert(0, "/opt/Murphy-System")

_DB = "/var/lib/murphy-production/inbound_replies.db"
_MAIL_DB = "/var/lib/murphy-production/murphy_mail.db"
_FOUNDER_EMAIL = "cpost@murphy.systems"

# Safety toggles
_SHADOW_MODE = True
_MAX_PER_DOMAIN_24H = 5
_MAX_DAILY_USD = float(os.environ.get("STRANGER_MAX_DAILY_USD", "5.00"))
_MAX_QUEUE_DEPTH = int(os.environ.get("STRANGER_MAX_QUEUE_DEPTH", "50"))

_VALUE_LINE = "Murphy automates the rule-bound periodic work you've been doing manually."

_ALLOWLIST_OWNED = {
    "cpost@murphy.systems",
    "corey.gfc@gmail.com",
    "callmehandy@gmail.com",
}


def _llm_complete(prompt: str, model_hint: str = "chat", max_tokens: int = 800) -> Optional[Dict]:
    """Direct llm_provider call via the full LLMCompletion object (not the .content shortcut)."""
    try:
        from src.llm_provider import get_llm
        result = get_llm().complete(prompt, model_hint=model_hint, max_tokens=max_tokens)
        # LLMCompletion dataclass: content, prompt_tokens, completion_tokens, cost_usd (or similar)
        text = getattr(result, "content", "") or getattr(result, "text", "") or ""
        prompt_tokens = int(getattr(result, "tokens_prompt", 0) or 0)
        completion_tokens = int(getattr(result, "tokens_completion", 0) or 0)
        # cost_usd may or may not be present — estimate if missing
        cost_usd = getattr(result, "cost_usd", None)
        if cost_usd is None:
            # rough estimate: $0.88/M for Llama-70B, $0.06/M for Llama-8B
            rate = 0.06e-6 if model_hint == "fast" else 0.88e-6
            cost_usd = (prompt_tokens + completion_tokens) * rate
        return {
            "text": text,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "cost_usd": float(cost_usd),
        }
    except Exception as e:
        import traceback
        logger.error(f"_llm_complete failed (hint={model_hint}): {e}\n{traceback.format_exc()}")
        return None


def _magnify_drill(email_subject: str, email_body: str) -> Optional[Dict]:
    """Generate tailored agent description via fast model (8B)."""
    prompt = f"""You are Murphy's agent-description generator. A stranger emailed murphy@murphy.systems:

SUBJECT: {email_subject}
BODY: {email_body[:1500]}

Generate a TAILORED agent description Murphy should embody. Use exactly this format. No examples. No hedging.

WHO: [3 sentences — role identity, scope, authority for THIS request]
HOW: [3 sentences — workflow pattern for THIS request]
WHY: [3 sentences — who served, what success looks like for THIS person]
STOP: [3 sentences — when to ask first, what NOT to do]

Output ONLY the 4-field block."""
    return _llm_complete(prompt, model_hint="fast", max_tokens=600)


def _generate_reply(agent_desc: str, email_subject: str, email_body: str, from_addr: str) -> Optional[Dict]:
    """Generate the actual reply email body (full chat model for quality)."""
    prompt = f"""You are now this agent:

=== AGENT DESCRIPTION ===
{agent_desc}
=== END AGENT DESCRIPTION ===

The person who emailed you (from {from_addr}) wrote:

SUBJECT: {email_subject}
BODY: {email_body[:2000]}

Write a SHORT email reply (under 200 words) that:
1. Opens with one line: "{_VALUE_LINE}"
2. Directly addresses their actual question or need
3. Names ONE concrete next step Murphy can take to help them
4. Closes with: "— Murphy (automated reply; reply STOP to opt out)"

Do NOT make up specific commitments about pricing, timelines, or features. Be concrete about what Murphy CAN do, honest about what it CAN'T."""
    return _llm_complete(prompt, model_hint="chat", max_tokens=400)


def _today_spend_usd(conn: sqlite3.Connection) -> float:
    """Sum cost_usd of stranger replies sent today. Defensive against legacy non-JSON targets."""
    cutoff = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rows = conn.execute(
        """SELECT auto_response_target FROM inbound_replies 
           WHERE auto_response_status IN ('stranger_sent','stranger_shadow_sent','stranger_queued')
           AND auto_response_sent_at LIKE ?""",
        (cutoff + "%",),
    ).fetchall()
    total = 0.0
    for r in rows:
        target = r[0] if r else None
        if not target:
            continue
        try:
            d = json.loads(target)
            total += float(d.get("cost_usd", 0.0))
        except Exception:
            pass  # legacy row with plain email — skip
    return total


def _outbound_queue_depth() -> int:
    try:
        conn = sqlite3.connect(_MAIL_DB)
        n = conn.execute(
            "SELECT COUNT(*) FROM outbound_email_queue WHERE status IN ('pending_review','pending')",
        ).fetchone()[0]
        conn.close()
        return int(n)
    except Exception:
        return 0


def _rate_limit_ok(from_addr: str, conn: sqlite3.Connection) -> bool:
    domain = from_addr.split("@")[-1].lower() if "@" in from_addr else from_addr
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    count = conn.execute(
        """SELECT COUNT(*) FROM inbound_replies 
           WHERE from_domain = ? 
           AND auto_response_status IN ('stranger_sent','stranger_queued')
           AND auto_response_sent_at > ?""",
        (domain, cutoff),
    ).fetchone()[0]
    return count < _MAX_PER_DOMAIN_24H


def _queue_outbound(to_addr: str, subject: str, body: str, urgency: str = "normal") -> Optional[str]:
    """Submit to outbound_email_queue. Returns queue_id on success."""
    try:
        import secrets
        conn = sqlite3.connect(_MAIL_DB)
        queue_id = "oeq_" + secrets.token_hex(8)
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            """INSERT INTO outbound_email_queue (
                 queue_id, from_address, to_addresses, subject, body, body_format,
                 agent_profile_id, agent_role, agent_class, urgency, status,
                 created_at, updated_at, action_type
               ) VALUES (?, ?, ?, ?, ?, 'plain', 
                         'stranger_responder', 'auto_responder', 'system', ?, 'pending_review',
                         ?, ?, 'email_outbound')""",
            (queue_id, "murphy@murphy.systems", json.dumps([to_addr]),
             subject, body, urgency, now, now),
        )
        conn.commit()
        conn.close()
        return queue_id
    except Exception as e:
        logger.error(f"_queue_outbound failed: {e}")
        return None


def _send_sendmail(to_addr: str, subject: str, body: str) -> bool:
    """Direct sendmail (used only for SHADOW drafts to founder)."""
    try:
        msg = f"""To: {to_addr}
From: murphy@murphy.systems
Subject: {subject}
Content-Type: text/plain; charset=utf-8

{body}
"""
        result = subprocess.run(
            ["/usr/sbin/sendmail", "-t", "-f", "murphy@murphy.systems"],
            input=msg.encode(), capture_output=True, timeout=10,
        )
        return result.returncode == 0
    except Exception as e:
        logger.error(f"_send_sendmail failed: {e}")
        return False


def process_stranger_inquiries(limit: int = 5) -> Dict:
    """Main entry point — paced, budgeted, queue-aware."""
    conn = sqlite3.connect(_DB)
    conn.row_factory = sqlite3.Row

    # Pacing gate: if outbound queue is backed up, back off
    qdepth = _outbound_queue_depth()
    if qdepth > _MAX_QUEUE_DEPTH:
        conn.close()
        return {"ok": True, "skipped_cycle": True, "reason": "queue_full",
                "outbound_queue_depth": qdepth, "max": _MAX_QUEUE_DEPTH,
                "count_sent": 0, "count_skipped": 0, "count_errors": 0}

    # Budget gate
    daily_spend = _today_spend_usd(conn)
    if daily_spend >= _MAX_DAILY_USD:
        conn.close()
        return {"ok": True, "skipped_cycle": True, "reason": "daily_budget_exhausted",
                "daily_spend_usd": daily_spend, "max_daily_usd": _MAX_DAILY_USD,
                "count_sent": 0, "count_skipped": 0, "count_errors": 0}

    sent = []
    skipped = []
    errors = []
    cycle_cost = 0.0

    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    placeholders = ",".join("?" * len(_ALLOWLIST_OWNED))
    rows = conn.execute(f"""
        SELECT id, from_addr, from_domain, subject, body_preview, intent_class
        FROM inbound_replies
        WHERE intent_class IN ('inquiry')
          AND auto_response_status IS NULL
          AND received_at > ?
          AND from_addr NOT IN ({placeholders})
          AND from_addr IS NOT NULL AND from_addr != ''
        ORDER BY received_at DESC
        LIMIT ?
    """, [cutoff, *_ALLOWLIST_OWNED, limit]).fetchall()

    for row in rows:
        rid = row["id"]
        from_addr = (row["from_addr"] or "").strip().lower()
        subject = row["subject"] or ""
        body = row["body_preview"] or ""

        if not from_addr or "@" not in from_addr:
            skipped.append({"id": rid, "reason": "no_sender"})
            continue

        if not _rate_limit_ok(from_addr, conn):
            skipped.append({"id": rid, "reason": "rate_limited"})
            conn.execute("UPDATE inbound_replies SET auto_response_status=? WHERE id=?",
                         ("stranger_rate_limited", rid))
            conn.commit()
            continue

        # Magnify-drill via fast model
        md = _magnify_drill(subject, body)
        if not md or len(md.get("text", "")) < 50:
            errors.append({"id": rid, "reason": "magnify_drill_failed"})
            continue
        agent_desc = md["text"]
        cycle_cost += md["cost_usd"]

        # Reply gen via chat model
        rep = _generate_reply(agent_desc, subject, body, from_addr)
        if not rep or len(rep.get("text", "")) < 30:
            errors.append({"id": rid, "reason": "reply_gen_failed"})
            continue
        reply_body = rep["text"]
        cycle_cost += rep["cost_usd"]

        total_cost = md["cost_usd"] + rep["cost_usd"]
        target_meta = json.dumps({
            "to": _FOUNDER_EMAIL if _SHADOW_MODE else from_addr,
            "cost_usd": total_cost,
            "magnify_tok": md["prompt_tokens"] + md["completion_tokens"],
            "reply_tok": rep["prompt_tokens"] + rep["completion_tokens"],
        })

        if _SHADOW_MODE:
            # Shadow draft via sendmail (founder-direct, fast)
            shadow_body = (
                f"=== SHADOW DRAFT for {from_addr} ===\n\n"
                f"Original subject: {subject}\nOriginal body: {body[:300]}\n\n"
                f"Cost: ${total_cost:.4f}  |  Magnify tok: {md['prompt_tokens']+md['completion_tokens']}  |  Reply tok: {rep['prompt_tokens']+rep['completion_tokens']}\n\n"
                f"=== AGENT DESCRIPTION ===\n{agent_desc}\n\n"
                f"=== REPLY ===\n{reply_body}\n\n"
                f"=== END ===\nFlip _SHADOW_MODE=False to go live.\n"
            )
            ok = _send_sendmail(_FOUNDER_EMAIL,
                                f"[SHADOW {total_cost:.4f}$ for {from_addr}] Re: {subject}",
                                shadow_body)
            status = "stranger_shadow_sent" if ok else "stranger_shadow_failed"
            mode = "shadow"
        else:
            # Live: queue through outbound_email_queue (paced + compliance-gated)
            qid = _queue_outbound(from_addr, f"Re: {subject}", reply_body, "normal")
            ok = bool(qid)
            status = "stranger_queued" if ok else "stranger_queue_failed"
            mode = "queued"

        if ok:
            sent.append({"id": rid, "mode": mode, "cost_usd": round(total_cost, 4)})
            conn.execute(
                "UPDATE inbound_replies SET auto_response_status=?, auto_response_sent_at=?, auto_response_target=? WHERE id=?",
                (status, datetime.now(timezone.utc).isoformat(), target_meta, rid),
            )
            conn.commit()
        else:
            errors.append({"id": rid, "reason": "send_or_queue_failed"})

        # Mid-cycle budget check
        if daily_spend + cycle_cost >= _MAX_DAILY_USD:
            skipped.append({"reason": "budget_cap_mid_cycle"})
            break

    conn.close()
    return {
        "ok": True,
        "shadow_mode": _SHADOW_MODE,
        "outbound_queue_depth": qdepth,
        "daily_spend_usd_before": round(daily_spend, 4),
        "cycle_cost_usd": round(cycle_cost, 4),
        "daily_spend_usd_after": round(daily_spend + cycle_cost, 4),
        "max_daily_usd": _MAX_DAILY_USD,
        "sent": sent,
        "skipped": skipped,
        "errors": errors,
        "count_sent": len(sent),
        "count_skipped": len(skipped),
        "count_errors": len(errors),
    }


if __name__ == "__main__":
    import pprint
    pprint.pprint(process_stranger_inquiries(limit=5))
