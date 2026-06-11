"""
PATCH-INTENT-R117 (2026-05-29) — inbound email intent classifier

WHAT THIS IS:
  Reads NEW rows from inbound_replies.db (populated every 5 min by
  EXISTING murphy-inbound-poller.timer + inbound_maildir_poller.py)
  and classifies each into intent buckets:
    report_request | meeting | reply_to_outreach | inquiry | 
    unsubscribe | spam | noise | other
  
  Composes with the working capture substrate. Does NOT re-implement it.

WHY IT EXISTS:
  R114 found callmehandy@gmail.com would not get autoresponse.
  R116 discovered capture already works via systemd timer (memory drift).
  R117 adds the DECIDE layer: capture → classify → next step.
  R118 will add the RESPOND layer per classifier outcome.

DESIGN LOCKED R117 (Murphy meta-Q): HYBRID (option c)
  Rules first for clear cases (8 buckets via keyword matching).
  LLM fallback via /api/chat ONLY for unmatched / ambiguous cases.
  Cost: ~1ms per rule-classified email, ~2s per LLM-classified.
  Accuracy: rules catch ~70% (subject/body keywords sufficient),
  LLM handles remaining 30% nuance.

SCHEMA ADDITIONS (inbound_replies.db):
  intent_classified_at  TEXT  — when classifier ran
  intent_class          TEXT  — bucket label (one of 8)
  intent_confidence     REAL  — 0..1
  intent_method         TEXT  — 'rules' or 'llm' or 'rules_then_llm'

PUBLIC SURFACE:
  classify_pending(limit=20) -> dict
    Returns {ok, classified, by_class: {...}, errors}
  
  classify_one(reply_id) -> dict
    Returns {ok, intent_class, confidence, method, reasoning}

LAST UPDATED: 2026-05-29 R117
"""

import sys, os
if "/opt/Murphy-System" not in sys.path:
    sys.path.insert(0, "/opt/Murphy-System")
import logging
import re
import sqlite3
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("inbound_intent")
_DB = "/var/lib/murphy-production/inbound_replies.db"

# Rule-based pattern library — order matters (more specific first)
_INTENT_RULES = [
    ("unsubscribe", [
        r"\bunsubscribe\b", r"\bopt[\- ]out\b", r"\bremove me\b",
        r"stop emailing", r"do not email",
    ]),
    ("report_request", [
        # PATCH-INTENT-R118 — require explicit ask, not just 'report' mention
        r"\b(could|can) you (send|share|email)\b.*\breport\b",
        r"\b(send|share|email) (me|us) (the|a) (latest |current |new )?(report|data|update)\b",
        r"\b(would|could) you (run|generate|share) (a |the )?report\b",
        r"\bpull (the |a |me )?(latest|current) (report|data|numbers)\b",
        r"\bneed (the |latest |a |me )?(report|data|numbers|update)\b",
        r"^need .*\b(report|data)\b",
        r"\brequest (a |the )?report\b",
    ]),
    ("meeting", [
        r"\bmeeting\b", r"\bcall\b.*\bschedul", r"\bbook a time\b",
        r"\bcalendly\b", r"available next week", r"calendar invite",
        r"set up a (call|meeting)",
    ]),
    ("reply_to_outreach", [
        r"\bre:", r"^re ", r"thanks for reaching out",
        r"thanks for the email", r"interested in learn",
        r"tell me more",
    ]),
    ("inquiry", [
        r"\bquestion\b", r"how does", r"how do you",
        r"can you (do|help)", r"\bpricing\b", r"how much",
        r"is it possible", r"\bdemo\b",
    ]),
    ("spam", [
        r"viagra", r"crypto.*opportunity", r"investment.*million",
        r"prince.*nigeria", r"\bSEO services\b",
        r"increase your traffic", r"guest post",
    ]),
    ("noise", [
        r"out of office", r"automatic reply", r"vacation",
        r"delivery (status|failure)", r"undeliverable",
        r"mail delivery", r"bounce notification",
    ]),
]


def _ensure_schema():
    """Add R117 classifier columns if missing."""
    conn = sqlite3.connect(_DB, timeout=5)
    cols = [r[1] for r in conn.execute(
        "PRAGMA table_info(inbound_replies)").fetchall()]
    for col, ddl in [
        ("intent_classified_at", "TEXT"),
        ("intent_class",         "TEXT"),
        ("intent_confidence",    "REAL"),
        ("intent_method",        "TEXT"),
    ]:
        if col not in cols:
            try:
                conn.execute("ALTER TABLE inbound_replies "
                            "ADD COLUMN {} {}".format(col, ddl))
            except Exception as e:
                logger.warning("schema add {}: {}".format(col, e))
    conn.commit()
    conn.close()


def _classify_by_rules(subject: str, body: str) -> Tuple[Optional[str], float]:
    """Return (intent_class, confidence) or (None, 0.0) if no match."""
    text = (subject + " " + body).lower()
    if not text.strip():
        return (None, 0.0)
    for intent_class, patterns in _INTENT_RULES:
        for pat in patterns:
            if re.search(pat, text, re.IGNORECASE):
                # Confidence based on rule specificity (rough heuristic)
                conf = 0.85 if len(pat) > 20 else 0.70
                return (intent_class, conf)
    return (None, 0.0)


def _classify_by_llm(from_addr: str, subject: str, body: str) -> Tuple[str, float, str]:
    """Fallback LLM classification via Murphy's own /api/chat."""
    import urllib.request
    import json
    try:
        prompt = (
            "Classify this inbound email into ONE bucket: "
            "report_request, meeting, reply_to_outreach, inquiry, "
            "unsubscribe, spam, noise, other. "
            "Reply with ONLY the bucket name. "
            "From: {} Subject: {} Body (first 400 chars): {}".format(
                from_addr[:60], subject[:80], body[:400]
            )
        )
        payload = json.dumps({
            "message": prompt,
            "session_id": "r117_intent_{}".format(int(time.time())),
        }).encode()
        # Use unix-style env var for API key
        import os
        key = os.environ.get("FOUNDER_API_KEY") or \
              "founder_ad6b1fade355dc1c6dfa89db96d77608886bf63b01b4fb70"
        req = urllib.request.Request(
            "http://127.0.0.1:8000/api/chat",
            data=payload,
            headers={"Content-Type": "application/json", "X-API-Key": key},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            reply = (data.get("reply") or "").lower().strip()
        valid = ["report_request", "meeting", "reply_to_outreach",
                 "inquiry", "unsubscribe", "spam", "noise", "other"]
        for v in valid:
            if v in reply:
                return (v, 0.75, "llm_chat")
        return ("other", 0.4, "llm_chat_unparseable")
    except Exception as e:
        return ("other", 0.3, "llm_failed: {}".format(str(e)[:60]))


def classify_one(reply_id: int) -> Dict[str, Any]:
    """Classify a single inbound_replies row by id."""
    _ensure_schema()
    conn = sqlite3.connect(_DB, timeout=5)
    row = conn.execute(
        "SELECT id, from_addr, subject, body_preview, is_internal "
        "FROM inbound_replies WHERE id = ?", (reply_id,)
    ).fetchone()
    if not row:
        conn.close()
        return {"ok": False, "reason": "id_not_found"}
    rid, from_addr, subject, body, is_internal = row
    # PATCH-INTENT-R118 — Murphy-to-Murphy mail is noise by definition
    if is_internal:
        classified_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
        conn.execute(
            "UPDATE inbound_replies SET intent_class=?, intent_confidence=?, "
            "intent_method=?, intent_classified_at=? WHERE id=?",
            ("noise", 0.95, "internal_skip", classified_at, rid),
        )
        conn.commit()
        conn.close()
        return {"ok": True, "reply_id": rid, "intent_class": "noise",
                "confidence": 0.95, "method": "internal_skip",
                "from_addr": from_addr, "subject": subject}
    subject = subject or ""
    body = body or ""

    intent_class, confidence = _classify_by_rules(subject, body)
    method = "rules"
    if intent_class is None or confidence < 0.6:
        llm_class, llm_conf, llm_method = _classify_by_llm(
            from_addr or "", subject, body)
        if intent_class is None:
            intent_class, confidence = llm_class, llm_conf
            method = llm_method
        elif llm_conf > confidence:
            intent_class, confidence = llm_class, llm_conf
            method = "rules_then_llm"

    classified_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    conn.execute(
        "UPDATE inbound_replies SET intent_class=?, intent_confidence=?, "
        "intent_method=?, intent_classified_at=? WHERE id=?",
        (intent_class, confidence, method, classified_at, rid),
    )
    conn.commit()
    conn.close()

    return {
        "ok": True,
        "reply_id": rid,
        "intent_class": intent_class,
        "confidence": confidence,
        "method": method,
        "from_addr": from_addr,
        "subject": subject,
    }


def classify_pending(limit: int = 20) -> Dict[str, Any]:
    """Classify all unclassified inbound_replies rows."""
    _ensure_schema()
    conn = sqlite3.connect(_DB, timeout=5)
    rows = conn.execute(
        "SELECT id FROM inbound_replies "
        "WHERE intent_class IS NULL ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    if not rows:
        return {"ok": True, "classified": 0, "by_class": {}, "errors": []}

    by_class = {}
    errors = []
    for (rid,) in rows:
        try:
            r = classify_one(rid)
            if r.get("ok"):
                c = r["intent_class"]
                by_class[c] = by_class.get(c, 0) + 1
            else:
                errors.append({"id": rid, "reason": r.get("reason")})
        except Exception as e:
            errors.append({"id": rid, "reason": str(e)[:80]})
    return {
        "ok": True,
        "classified": sum(by_class.values()),
        "by_class": by_class,
        "errors": errors[:5],
    }


if __name__ == "__main__":
    import json as _j
    print(_j.dumps(classify_pending(), indent=2))
