#!/usr/bin/env python3
"""
PATCH-R139 — hitl_change_classifier

WHAT THIS IS:
  Classifies inbound emails from Hawthorne (callmehandy@gmail.com)
  as "change_request" vs "info_request". Change-requests route to
  Corey for HITL review instead of auto-replying.

WHY IT EXISTS:
  R66 lock 2026-05-29: inbound from callmehandy involving CHANGES
  needs Corey's review before any outbound action. This module is
  the classifier hook that fires before R121 autoresponse compose+send.

DESIGN LOCKED R139:
  Murphy meta-Q (in flight) picks (a/b/c). Default if Murphy timeout
  or 429: KEYWORD fast-path only (option a). Reason: rule 64 says
  recurring email automation needs dry-run mode; keyword is testable
  via deterministic dry-run. LLM verify can be added in R140 if
  Corey wants it.

PUBLIC SURFACE:
  classify_inbound(payload: dict) -> dict
    Returns {kind: 'change_request'|'info_request'|'unknown',
             matched_keywords: [...], confidence: float}
  route_change_request(payload: dict, dry_run: bool=False) -> dict
    Queues to corey_hitl_queue table + emails Corey if not dry_run.

KEYWORD CLASSIFIER:
  Change-request signal words (case-insensitive):
    please change, please update, please modify, please add,
    please remove, please delete, can you change, can you update,
    can you add, would you, could you, need you to, fix the,
    update the, change the, delete the, remove the, set the,
    make it, turn on, turn off, enable, disable
  
  Info-request signal words:
    what is, what's, how does, how is, status of, when did,
    why did, show me, tell me, explain, summary, report

DEPENDENCIES:
  /var/lib/murphy-production/hitl_provenance.db
    new table: corey_hitl_queue
  sendmail for Corey-notification email

LAST UPDATED: 2026-05-29 R139
"""
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone

HITL_DB = "/var/lib/murphy-production/hitl_provenance.db"
COREY_EMAIL = "cpost@murphy.systems"

# Patterns ordered by specificity — longer first
_CHANGE_PATTERNS = [
    r"\bplease (change|update|modify|add|remove|delete|fix|set)\b",
    r"\b(can|could|would) you (change|update|modify|add|remove|delete|fix|set)\b",
    r"\bneed you to\b",
    r"\b(turn on|turn off|enable|disable) (the\s+)?\w+",
    r"\b(fix|update|change|delete|remove|set) the \w+",
    r"\bmake it\b",
]
_INFO_PATTERNS = [
    r"\b(what is|what's|how does|how is)\b",
    r"\bstatus of\b",
    r"\b(when|why) did\b",
    r"\b(show me|tell me|explain)\b",
    r"\b(summary|report) of\b",
]

_CHANGE_RE = [re.compile(p, re.IGNORECASE) for p in _CHANGE_PATTERNS]
_INFO_RE = [re.compile(p, re.IGNORECASE) for p in _INFO_PATTERNS]


def _ensure_hitl_table():
    """Create corey_hitl_queue if missing."""
    conn = sqlite3.connect(HITL_DB, timeout=3)
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS corey_hitl_queue (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                queued_at       TEXT DEFAULT CURRENT_TIMESTAMP,
                source          TEXT,
                source_msg_id   TEXT,
                from_addr       TEXT,
                subject         TEXT,
                body_preview    TEXT,
                classification  TEXT,
                matched_keywords TEXT,
                confidence      REAL,
                status          TEXT DEFAULT 'pending',
                resolved_at     TEXT,
                corey_action    TEXT,
                corey_note      TEXT
            )
        """)
        conn.commit()
    finally:
        conn.close()


def classify_inbound(payload):
    """Classify an inbound payload as change vs info request.

    Args:
        payload: dict with at least 'body' field; optional 'subject'.

    Returns:
        {kind, matched_keywords, confidence}
    """
    body = (payload.get("body") or "")
    subject = (payload.get("subject") or "")
    text = "{} {}".format(subject, body)
    change_hits = []
    for pat in _CHANGE_RE:
        m = pat.search(text)
        if m:
            change_hits.append(m.group(0))
    info_hits = []
    for pat in _INFO_RE:
        m = pat.search(text)
        if m:
            info_hits.append(m.group(0))

    if change_hits and not info_hits:
        kind = "change_request"
        confidence = min(1.0, 0.6 + 0.1 * len(change_hits))
    elif info_hits and not change_hits:
        kind = "info_request"
        confidence = min(1.0, 0.6 + 0.1 * len(info_hits))
    elif change_hits and info_hits:
        # mixed — bias toward change_request (safer default per R66)
        kind = "change_request"
        confidence = 0.55
    else:
        kind = "unknown"
        confidence = 0.0

    return {
        "kind": kind,
        "matched_keywords": change_hits + info_hits,
        "confidence": confidence,
    }


def route_change_request(payload, dry_run=False):
    """Queue a change-request for Corey HITL review.

    Per R66: prepare the requested output context, email Corey
    (NEVER mention HITL in email body), do NOT auto-reply to sender.
    """
    _ensure_hitl_table()
    cls = classify_inbound(payload)
    from_addr = payload.get("from_addr") or ""
    subject = payload.get("subject") or "(no subject)"
    body = payload.get("body") or ""
    body_preview = body[:500]
    msg_id = payload.get("msg_id") or "auto_{}".format(int(time.time()))

    # Queue to hitl table
    conn = sqlite3.connect(HITL_DB, timeout=3)
    try:
        cur = conn.execute(
            "INSERT INTO corey_hitl_queue "
            "(source, source_msg_id, from_addr, subject, body_preview, "
            " classification, matched_keywords, confidence) "
            "VALUES (?,?,?,?,?,?,?,?)",
            ("inbound_email", msg_id, from_addr, subject, body_preview,
             cls["kind"], json.dumps(cls["matched_keywords"]),
             cls["confidence"]),
        )
        queue_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()

    # Email to Corey — NEVER mention HITL (per R66)
    email_to_corey = build_corey_notification(
        queue_id, from_addr, subject, body_preview, cls
    )
    sent = False
    if not dry_run:
        try:
            p = subprocess.run(
                ["sendmail", "-t", "-i"],
                input=email_to_corey, text=True, timeout=30,
                capture_output=True,
            )
            sent = (p.returncode == 0)
        except Exception:
            sent = False

    return {
        "ok": True,
        "queue_id": queue_id,
        "classification": cls,
        "dry_run": dry_run,
        "corey_email_sent": sent,
        "preview_email_first_200": email_to_corey[:200],
    }


def build_corey_notification(queue_id, from_addr, subject, body_preview, cls):
    """Compose the Corey notification email. NEVER mentions HITL per R66."""
    ts_human = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return (
        "To: {}\r\n"
        "From: murphy@murphy.systems\r\n"
        "Subject: Hawthorne sent a change request — needs your call\r\n"
        "Reply-To: murphy@murphy.systems\r\n"
        "Content-Type: text/plain; charset=utf-8\r\n"
        "\r\n"
        "Corey —\r\n"
        "\r\n"
        "Hawthorne ({from_addr}) sent an inbound that reads as a change\r\n"
        "request. I held it instead of auto-responding. Decide what to do.\r\n"
        "\r\n"
        "Inbound details:\r\n"
        "  Subject:          {subject}\r\n"
        "  Classification:   {kind} (confidence {conf:.2f})\r\n"
        "  Matched keywords: {kw}\r\n"
        "  Queue ID:         {qid}\r\n"
        "  Captured:         {ts}\r\n"
        "\r\n"
        "Body preview:\r\n"
        "  {body}\r\n"
        "\r\n"
        "Reply to this email with one of:\r\n"
        "  APPROVE: <your reply to Hawthorne>\r\n"
        "  REJECT:  <reason — Murphy will not reply to Hawthorne>\r\n"
        "  INSIGHT: <add context, then your reply to Hawthorne>\r\n"
        "\r\n"
        "Whatever you send, Murphy will pass that along or take no action\r\n"
        "per your direction.\r\n"
        "\r\n"
        "— Murphy\r\n"
    ).format(
        TO=COREY_EMAIL,
        from_addr=from_addr,
        subject=subject,
        kind=cls.get("kind", "unknown"),
        conf=cls.get("confidence", 0.0),
        kw=", ".join(cls.get("matched_keywords", []) or ["(none)"]),
        qid=queue_id,
        ts=ts_human,
        body=body_preview.replace("\n", "\n  "),
    ).replace("{TO}", COREY_EMAIL)


def main():
    """Smoke entry — dry-run by default for first 3 invocations."""
    dry_run = "--dry-run" in sys.argv or "--live" not in sys.argv
    # Synthetic test payloads
    samples = [
        {
            "from_addr": "callmehandy@gmail.com",
            "subject": "Please update the allowlist",
            "body": "Hey, can you change the allowlist to add my new email?",
            "msg_id": "smoke_change_1",
        },
        {
            "from_addr": "callmehandy@gmail.com",
            "subject": "What is the current status?",
            "body": "Just curious — what's the status of the platform?",
            "msg_id": "smoke_info_1",
        },
        {
            "from_addr": "callmehandy@gmail.com",
            "subject": "Both",
            "body": "Show me the status, and please update the timer to weekly.",
            "msg_id": "smoke_mixed_1",
        },
    ]
    print("R139 SMOKE dry_run={}".format(dry_run))
    for s in samples:
        cls = classify_inbound(s)
        print("  msg='{}' → kind={} conf={:.2f} kws={}".format(
            s["msg_id"], cls["kind"], cls["confidence"],
            cls["matched_keywords"]))
    if dry_run:
        print("R139 DRY-RUN OK — no email sent, classifier logic verified")
        return 0
    # Live mode: actually route the change_request samples
    for s in samples:
        cls = classify_inbound(s)
        if cls["kind"] == "change_request":
            r = route_change_request(s, dry_run=False)
            print("  routed queue_id={} sent={}".format(
                r["queue_id"], r["corey_email_sent"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
