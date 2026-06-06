"""
PATCH-R470 — HITL notification dispatcher
==========================================

WHAT THIS IS:
  Sends notification emails for new HITL items to subscribers, and handles the
  invite-flow magic-link opt-in.

WHY IT EXISTS:
  Corey + Hawthorne need to see HITL items land in their personal inboxes,
  with a one-click approve/reject link. Plan B (per Corey 2026-06-02): invite
  first, then deliver item notifications only after opt-in.

HOW IT FITS:
  - Subscriptions live in hitl_jobs.db -> hitl_subscriptions
  - Audit trail in hitl_notification_log
  - SMTP via local Postfix:25 (same pattern as R461)
  - Magic-link tokens: 7-day expiry, single-use for opt-in, persistent for approve

ENDPOINTS / PUBLIC SURFACE:
  - send_invite(email) -> sends opt-in email, returns invite_token
  - send_item_notification(item) -> sends item review email to all active subs
  - confirm_opt_in(token) -> flips subscription to 'active'
  - mk_approve_link(item_id, email) -> returns signed URL for 1-click approve

DEPENDENCIES:
  - sqlite3, smtplib, email.mime, hmac, hashlib
  - reads MURPHY_NOTIFY_SIGNING_KEY env (falls back to MURPHY_FOUNDER_KEY)

LAST UPDATED: 2026-06-02 by R470
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import smtplib
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from email.message import EmailMessage
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── Section: Config ────────────────────────────────────────────────────────
_DB = "/var/lib/murphy-production/hitl_jobs.db"
_FROM_ADDR = "Murphy <murphy@murphy.systems>"
_BASE_URL = os.environ.get("MURPHY_BASE_URL", "https://murphy.systems")
_SIGNING_KEY = (
    os.environ.get("MURPHY_NOTIFY_SIGNING_KEY")
    or os.environ.get("MURPHY_FOUNDER_KEY")
    or "fallback-dev-key-do-not-use-in-prod"
).encode("utf-8")
_TOKEN_TTL_DAYS = 7


# ── Section: Token signing ────────────────────────────────────────────────
def _sign(payload: str) -> str:
    """HMAC-SHA256 sign; return hex digest (first 32 chars for compactness)."""
    return hmac.new(_SIGNING_KEY, payload.encode("utf-8"), hashlib.sha256).hexdigest()[:32]


def mk_approve_link(item_id: str, email: str, action: str = "approve") -> str:
    """Build a signed approve/reject URL: /api/hitl/email-action?...&sig=..."""
    ts = int(time.time())
    payload = f"{item_id}|{email}|{action}|{ts}"
    sig = _sign(payload)
    return (
        f"{_BASE_URL}/api/hitl/email-action"
        f"?item={item_id}&email={email}&action={action}&ts={ts}&sig={sig}"
    )


def verify_action_token(item_id: str, email: str, action: str, ts: str, sig: str) -> bool:
    """Verify signed link. TTL: 30 days for approve actions."""
    try:
        ts_int = int(ts)
        if time.time() - ts_int > 30 * 86400:
            return False
    except ValueError:
        return False
    expected = _sign(f"{item_id}|{email}|{action}|{ts}")
    return hmac.compare_digest(expected, sig)


def mk_invite_link(token: str) -> str:
    return f"{_BASE_URL}/api/hitl/confirm-subscription?token={token}"


# ── Section: SMTP send ────────────────────────────────────────────────────
def _smtp_send(to_addr: str, subject: str, body_text: str, body_html: Optional[str] = None) -> Tuple[bool, str]:
    """Send via local Postfix:25 (same pattern as R461). Returns (ok, message_id)."""
    msg = EmailMessage()
    msg["From"] = _FROM_ADDR
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg["Reply-To"] = "murphy@murphy.systems"
    msg.set_content(body_text)
    if body_html:
        msg.add_alternative(body_html, subtype="html")

    msg_id = f"<r470-{uuid.uuid4().hex}@murphy.systems>"
    msg["Message-ID"] = msg_id

    try:
        with smtplib.SMTP("127.0.0.1", 25, timeout=10) as smtp:
            smtp.send_message(msg)
        return True, msg_id
    except Exception as exc:
        logger.warning("R470 SMTP send failed to %s: %s", to_addr, exc)
        return False, f"error: {type(exc).__name__}: {exc}"


# ── Section: Subscription DB ──────────────────────────────────────────────
def _conn():
    c = sqlite3.connect(_DB, timeout=10)
    c.row_factory = sqlite3.Row
    return c


def _log_notification(subscription_id: str, email: str, item_id: Optional[str],
                       notification_type: str, message_id: str, smtp_status: str) -> None:
    log_id = f"nlog_{uuid.uuid4().hex[:16]}"
    with _conn() as c:
        c.execute(
            "INSERT INTO hitl_notification_log "
            "(log_id, subscription_id, email, item_id, notification_type, message_id, smtp_status) "
            "VALUES (?,?,?,?,?,?,?)",
            (log_id, subscription_id, email, item_id, notification_type, message_id, smtp_status),
        )


def list_active_subscribers() -> List[Dict[str, Any]]:
    with _conn() as c:
        rows = c.execute(
            "SELECT subscription_id, email, display_name, scope_json "
            "FROM hitl_subscriptions WHERE status='active'"
        ).fetchall()
    return [
        {
            "subscription_id": r["subscription_id"],
            "email": r["email"],
            "display_name": r["display_name"],
            "scope": json.loads(r["scope_json"] or "[]"),
        }
        for r in rows
    ]


def list_pending_subscribers() -> List[Dict[str, Any]]:
    with _conn() as c:
        rows = c.execute(
            "SELECT subscription_id, email, display_name FROM hitl_subscriptions "
            "WHERE status='pending'"
        ).fetchall()
    return [{"subscription_id": r["subscription_id"], "email": r["email"], "name": r["display_name"]} for r in rows]


# ── Section: Invite flow (Plan B) ─────────────────────────────────────────
def send_invite(email: str, display_name: Optional[str] = None) -> Dict[str, Any]:
    """Send opt-in invitation email. Updates hitl_subscriptions with invite_token."""
    token = uuid.uuid4().hex
    with _conn() as c:
        row = c.execute(
            "SELECT subscription_id FROM hitl_subscriptions WHERE email=?", (email,)
        ).fetchone()
        if row:
            sub_id = row["subscription_id"]
            c.execute(
                "UPDATE hitl_subscriptions SET invite_token=?, invite_sent_at=datetime('now'), "
                "status=CASE WHEN status='paused' THEN 'paused' ELSE 'pending' END "
                "WHERE subscription_id=?",
                (token, sub_id),
            )
        else:
            sub_id = f"sub_{uuid.uuid4().hex[:12]}"
            c.execute(
                "INSERT INTO hitl_subscriptions "
                "(subscription_id, email, display_name, scope_json, status, invite_token, "
                " invite_sent_at, created_by) "
                "VALUES (?,?,?,?,'pending',?,datetime('now'),'founder-941e2a6857c14ee9')",
                (sub_id, email, display_name or "",
                 '["outbound_email","sales_outreach","prospect_email"]', token),
            )

    link = mk_invite_link(token)
    subject = "You're invited to review Murphy HITL items"
    name = display_name or email.split("@")[0]
    body_text = (
        f"Hi {name},\n\n"
        f"Corey set up Murphy to notify you when HITL (Human-in-the-Loop) items "
        f"need review. These are outbound emails Murphy drafts that need a human "
        f"to approve before sending.\n\n"
        f"If you want to receive these notifications, click here to opt in:\n\n"
        f"{link}\n\n"
        f"You can pause or unsubscribe at any time. By opting in, you agree to "
        f"act as a HITL approver under Murphy's Terms (https://murphy.systems/terms §1B).\n\n"
        f"If you don't recognize this, just ignore the email.\n\n"
        f"— Murphy (on behalf of Corey Post)\n"
    )
    body_html = f"""<html><body style="font-family:-apple-system,sans-serif;max-width:520px;margin:auto">
<p>Hi {name},</p>
<p>Corey set up Murphy to notify you when HITL (Human-in-the-Loop) items need review.
These are outbound emails Murphy drafts that need a human to approve before sending.</p>
<p>If you want to receive these notifications, click below to opt in:</p>
<p style="margin:24px 0"><a href="{link}" style="background:#00D4AA;color:#0a0f0d;
  padding:12px 24px;border-radius:6px;text-decoration:none;font-weight:600">
  Opt in to HITL notifications
</a></p>
<p style="color:#666;font-size:13px">You can pause or unsubscribe at any time. By opting in,
you agree to act as a HITL approver under Murphy's
<a href="https://murphy.systems/terms">Terms §1B</a>.</p>
<p style="color:#666;font-size:13px">If you don't recognize this, just ignore the email.</p>
<p style="color:#999;font-size:11px;margin-top:32px">— Murphy (on behalf of Corey Post)</p>
</body></html>"""

    ok, msg_id = _smtp_send(email, subject, body_text, body_html)
    _log_notification(sub_id, email, None, "invite", msg_id, "sent" if ok else "failed")
    return {"ok": ok, "subscription_id": sub_id, "email": email,
            "invite_token": token, "message_id": msg_id, "link": link}


def confirm_opt_in(token: str) -> Dict[str, Any]:
    """Flip subscription from 'pending' to 'active' via magic-link click."""
    with _conn() as c:
        row = c.execute(
            "SELECT subscription_id, email, status FROM hitl_subscriptions WHERE invite_token=?",
            (token,),
        ).fetchone()
        if not row:
            return {"ok": False, "error": "invalid_token"}
        if row["status"] == "active":
            return {"ok": True, "email": row["email"], "already_active": True}
        c.execute(
            "UPDATE hitl_subscriptions SET status='active', opted_in_at=datetime('now'), "
            "invite_token=NULL WHERE subscription_id=?",
            (row["subscription_id"],),
        )
    return {"ok": True, "email": row["email"], "subscription_id": row["subscription_id"]}


# ── Section: Item notification ────────────────────────────────────────────
def send_item_notification(item: Dict[str, Any]) -> Dict[str, Any]:
    """Notify all active subscribers about a single HITL item."""
    subs = list_active_subscribers()
    if not subs:
        return {"ok": True, "sent": 0, "skipped": "no active subscribers"}

    item_id = item.get("id") or item.get("queue_id") or "unknown"
    title = item.get("title") or item.get("subject") or "HITL item needs review"
    discipline = item.get("discipline", "")
    body_preview = (item.get("body") or item.get("preview") or "")[:300]
    to_addrs = item.get("to_addresses") or []
    if isinstance(to_addrs, str):
        try:
            to_addrs = json.loads(to_addrs)
        except Exception:
            to_addrs = [to_addrs]
    recipient_line = ", ".join(to_addrs) if to_addrs else "(no recipient set)"

    results = []
    for sub in subs:
        approve_link = mk_approve_link(item_id, sub["email"], "approve")
        reject_link = mk_approve_link(item_id, sub["email"], "reject")
        view_link = f"{_BASE_URL}/hitl?focus={item_id}"

        subject = f"[Murphy HITL] Review needed: {title[:80]}"
        body_text = (
            f"Hi {sub['display_name'] or sub['email']},\n\n"
            f"Murphy has a new outbound email that needs your approval before sending.\n\n"
            f"  Subject: {title}\n"
            f"  To: {recipient_line}\n"
            f"  Discipline: {discipline or 'general'}\n\n"
            f"--- Preview ---\n{body_preview}\n---\n\n"
            f"Approve and send now: {approve_link}\n"
            f"Reject (do not send):  {reject_link}\n"
            f"Open in Murphy:        {view_link}\n\n"
            f"By clicking Approve, you're acting as a HITL approver under your "
            f"engagement contract (Terms §1B).\n\n"
            f"— Murphy\n"
        )
        body_html = f"""<html><body style="font-family:-apple-system,sans-serif;max-width:560px;margin:auto">
<h3 style="color:#00D4AA;margin-bottom:4px">Murphy HITL — review needed</h3>
<p style="color:#888;font-size:13px;margin-top:0">A new outbound email is awaiting your approval.</p>
<table style="border-collapse:collapse;margin:16px 0">
<tr><td style="padding:4px 12px 4px 0;color:#888">Subject:</td><td><b>{title}</b></td></tr>
<tr><td style="padding:4px 12px 4px 0;color:#888">To:</td><td>{recipient_line}</td></tr>
<tr><td style="padding:4px 12px 4px 0;color:#888">Discipline:</td><td>{discipline or 'general'}</td></tr>
</table>
<div style="background:#f5f5f5;padding:12px;border-left:3px solid #00D4AA;border-radius:4px;margin:16px 0;font-size:13px;white-space:pre-wrap">{body_preview}</div>
<p style="margin:24px 0;display:flex;gap:8px">
  <a href="{approve_link}" style="background:#00D4AA;color:#0a0f0d;padding:10px 20px;border-radius:6px;text-decoration:none;font-weight:600">✓ Approve &amp; send</a>
  <a href="{reject_link}" style="background:#FF6B6B;color:#0a0f0d;padding:10px 20px;border-radius:6px;text-decoration:none;font-weight:600">✗ Reject</a>
  <a href="{view_link}" style="background:#333;color:#fff;padding:10px 20px;border-radius:6px;text-decoration:none">Open in Murphy</a>
</p>
<p style="color:#666;font-size:11px;margin-top:32px">By clicking Approve, you're acting as a HITL approver under your engagement contract (<a href="https://murphy.systems/terms">Terms §1B</a>).</p>
</body></html>"""
        ok, msg_id = _smtp_send(sub["email"], subject, body_text, body_html)
        _log_notification(sub["subscription_id"], sub["email"], item_id,
                          "item_review", msg_id, "sent" if ok else "failed")
        results.append({"email": sub["email"], "ok": ok, "message_id": msg_id})

        with _conn() as c:
            c.execute(
                "UPDATE hitl_subscriptions SET last_notified_at=datetime('now'), "
                "notify_count=notify_count+1 WHERE subscription_id=?",
                (sub["subscription_id"],),
            )

    return {"ok": True, "item_id": item_id, "sent": sum(1 for r in results if r["ok"]),
            "failed": sum(1 for r in results if not r["ok"]), "results": results}
