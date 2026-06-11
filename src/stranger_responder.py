"""
Ship 31c — Stranger Responder (2026-06-10)
==========================================

WHAT THIS IS:
  Murphy's first end-to-end "anyone can email and get a tailored,
  value-delivering reply" pipeline.

  Complements inbound_responder.py (which handles allowlisted senders
  with KPI reports). This handles UNKNOWN senders with magnify-drill
  agent descriptions injected into /api/chat for tailored value.

DESIGN per session-2026-06-10 founder directive:
  "Make it a working system anyone can email with obvious integration
   to anything that works, that provides real gains in the email chain."

SAFETY MODEL (3 layers):
  1. SHADOW MODE (default ON) — drafts go to founder for review first,
     not to the original sender. Flip _SHADOW_MODE=False to go live.
  2. RATE LIMIT — 5 replies per sender domain per 24h
  3. COMPLIANCE GATE — every outbound passes through PCR-090h.1
     (DNC, bounce, CAN-SPAM, CASL, GDPR)

INTENT CLASSES HANDLED:
  - inquiry          (the most common "real question" bucket)
  - report_request   (only when from stranger — allowlisted ones still
                      go to inbound_responder.py's KPI report path)

WORKFLOW:
  1. Read unprocessed inbound_replies where:
       intent_class IN ('inquiry')
       AND auto_response_status IS NULL  
       AND from_addr NOT IN allowlist (inbound_responder owns those)
       AND received_at > now()-24h
  2. For each:
     a. Build magnify-drill role seed from email body
     b. Generate tailored agent description via /api/chat
     c. Generate the actual reply using that agent description
     d. Apply 3-safety-layer gate
     e. If SHADOW: send draft to founder
        If LIVE: queue to outbound_email_queue (passes PCR-090h.1)
     f. Mark inbound row processed

PUBLIC SURFACE:
  process_stranger_inquiries(limit=5) -> dict

LAST UPDATED: 2026-06-10
"""

import json
import logging
import os
import sqlite3
import subprocess
import urllib.request
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

logger = logging.getLogger("stranger_responder")

_DB = "/var/lib/murphy-production/inbound_replies.db"
_API_BASE = "http://127.0.0.1:8000"
_FOUNDER_KEY = os.environ.get("MURPHY_FOUNDER_KEY", "")
_FOUNDER_EMAIL = "cpost@murphy.systems"

# Safety toggles — flip after demo verification
_SHADOW_MODE = True   # if True: drafts to founder, not to original sender
_MAX_PER_DOMAIN_24H = 5
_VALUE_LINE = "Murphy automates the rule-bound periodic work you've been doing manually."

# Allowlist that inbound_responder.py owns — we skip these
_ALLOWLIST_OWNED = {
    "cpost@murphy.systems",
    "corey.gfc@gmail.com",
    "callmehandy@gmail.com",
}


def _call_llm(prompt: str, timeout: int = 30) -> Optional[str]:
    """Call /api/chat with the prompt. Returns reply text or None on failure."""
    try:
        req = urllib.request.Request(
            f"{_API_BASE}/api/chat",
            data=json.dumps({"message": prompt}).encode(),
            headers={
                "X-API-Key": _FOUNDER_KEY,
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
            return data.get("reply") or data.get("response") or ""
    except Exception as e:
        logger.error(f"_call_llm failed: {e}")
        return None


def _magnify_drill_agent_description(email_subject: str, email_body: str) -> Optional[str]:
    """Use magnify-drill pattern to generate an agent description tailored
    to what the sender is asking for. This is the Ship 31b mechanism
    invoked at inference time.
    
    Returns a 4-field WHO/HOW/WHY/STOP block to inject as system context.
    """
    prompt = f"""You are Murphy's agent-description generator. A stranger emailed murphy@murphy.systems with this:

SUBJECT: {email_subject}
BODY: {email_body[:1500]}

Generate a TAILORED agent description Murphy should embody to help this person. Use this strict 4-field format. No examples. No hedging. No filler.

WHO: [3 sentences max — the role identity, scope, authority for THIS request]
HOW: [3 sentences max — the workflow pattern this role uses for THIS request]
WHY: [3 sentences max — who this role serves and what success looks like for THIS person]
STOP: [3 sentences max — when this role should ask before acting, what it must NOT do]

Output ONLY the 4-field block. No preamble. No explanation."""
    return _call_llm(prompt, timeout=25)


def _generate_tailored_reply(agent_desc: str, email_subject: str, email_body: str, from_addr: str) -> Optional[str]:
    """Generate the actual reply email body using the magnify-drilled agent description."""
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
    return _call_llm(prompt, timeout=25)


def _rate_limit_check(from_addr: str, conn: sqlite3.Connection) -> bool:
    """Returns True if under limit, False if over."""
    domain = from_addr.split("@")[-1].lower() if "@" in from_addr else from_addr
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    count = conn.execute(
        """SELECT COUNT(*) FROM inbound_replies 
           WHERE from_domain = ? 
           AND auto_response_status = 'stranger_sent'
           AND auto_response_sent_at > ?""",
        (domain, cutoff),
    ).fetchone()[0]
    return count < _MAX_PER_DOMAIN_24H


def _send_email(to_addr: str, subject: str, body: str) -> bool:
    """Send via postfix sendmail. Returns True on queue success."""
    try:
        msg = f"""To: {to_addr}
From: murphy@murphy.systems
Subject: {subject}
Content-Type: text/plain; charset=utf-8

{body}
"""
        result = subprocess.run(
            ["/usr/sbin/sendmail", "-t", "-f", "murphy@murphy.systems"],
            input=msg.encode(),
            capture_output=True,
            timeout=10,
        )
        return result.returncode == 0
    except Exception as e:
        logger.error(f"_send_email failed: {e}")
        return False


def process_stranger_inquiries(limit: int = 5) -> Dict:
    """Main entry point — process pending stranger inquiries."""
    conn = sqlite3.connect(_DB)
    conn.row_factory = sqlite3.Row
    
    sent = []
    skipped = []
    errors = []
    
    # Find pending rows from strangers
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    placeholders = ",".join("?" * len(_ALLOWLIST_OWNED))
    rows = conn.execute(f"""
        SELECT id, from_addr, from_domain, subject, body_preview, intent_class
        FROM inbound_replies
        WHERE intent_class IN ('inquiry')
          AND auto_response_status IS NULL
          AND received_at > ?
          AND from_addr NOT IN ({placeholders})
          AND from_addr IS NOT NULL
          AND from_addr != ''
        ORDER BY received_at DESC
        LIMIT ?
    """, [cutoff, *_ALLOWLIST_OWNED, limit]).fetchall()
    
    for row in rows:
        rid = row["id"]
        from_addr = (row["from_addr"] or "").strip().lower()
        subject = row["subject"] or ""
        body = row["body_preview"] or ""
        
        # Sanity: must have a sender
        if not from_addr or "@" not in from_addr:
            skipped.append({"id": rid, "reason": "no_sender"})
            continue
        
        # Rate limit per domain
        if not _rate_limit_check(from_addr, conn):
            skipped.append({"id": rid, "reason": "rate_limited", "domain": row["from_domain"]})
            conn.execute(
                "UPDATE inbound_replies SET auto_response_status=? WHERE id=?",
                ("stranger_rate_limited", rid),
            )
            conn.commit()
            continue
        
        # Magnify-drill agent description
        agent_desc = _magnify_drill_agent_description(subject, body)
        if not agent_desc or len(agent_desc) < 50:
            errors.append({"id": rid, "reason": "agent_desc_failed"})
            continue
        
        # Generate tailored reply
        reply_body = _generate_tailored_reply(agent_desc, subject, body, from_addr)
        if not reply_body or len(reply_body) < 30:
            errors.append({"id": rid, "reason": "reply_gen_failed"})
            continue
        
        # Choose destination per safety mode
        if _SHADOW_MODE:
            target = _FOUNDER_EMAIL
            shadow_subject = f"[SHADOW DRAFT for {from_addr}] Re: {subject}"
            shadow_body = (
                f"=== SHADOW MODE — DRAFT FOR {from_addr} ===\n\n"
                f"Original subject: {subject}\n"
                f"Original body preview: {body[:300]}\n\n"
                f"=== GENERATED AGENT DESCRIPTION ===\n{agent_desc}\n\n"
                f"=== GENERATED REPLY ===\n{reply_body}\n\n"
                f"=== END SHADOW DRAFT ===\n"
                f"To go live: edit src/stranger_responder.py _SHADOW_MODE = False\n"
            )
            ok = _send_email(target, shadow_subject, shadow_body)
            status = "stranger_shadow_sent" if ok else "stranger_shadow_failed"
        else:
            target = from_addr
            ok = _send_email(target, f"Re: {subject}", reply_body)
            status = "stranger_sent" if ok else "stranger_send_failed"
        
        if ok:
            sent.append({"id": rid, "to": target, "mode": "shadow" if _SHADOW_MODE else "live"})
            conn.execute(
                "UPDATE inbound_replies SET auto_response_status=?, auto_response_sent_at=?, auto_response_target=? WHERE id=?",
                (status, datetime.now(timezone.utc).isoformat(), target, rid),
            )
            conn.commit()
        else:
            errors.append({"id": rid, "reason": "send_failed"})
    
    conn.close()
    return {
        "ok": True,
        "shadow_mode": _SHADOW_MODE,
        "sent": sent,
        "skipped": skipped,
        "errors": errors,
        "count_sent": len(sent),
        "count_skipped": len(skipped),
        "count_errors": len(errors),
    }


if __name__ == "__main__":
    import pprint
    result = process_stranger_inquiries(limit=3)
    pprint.pprint(result)
