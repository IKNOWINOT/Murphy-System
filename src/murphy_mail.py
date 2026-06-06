"""
src/murphy_mail.py — R300 (2026-05-30)
=======================================

WHAT THIS IS:
  Send-email module for lead_prospector + future sales engines.
  Was referenced everywhere but never written. R300 ships it.

WHY IT EXISTS:
  R300 audit found lead_prospector.py imports `from src.murphy_mail import
  send_email` but no such file existed. Prospecting infrastructure
  has been silently failing because the send path raises ImportError.
  Plus: outbound from anywhere in the codebase had no centralized logging.
  This module bridges BOTH gaps:
    1. Provides send_email() that lead_prospector imports
    2. Logs every send to /var/lib/murphy-production/email_outbound.db::email_log
    3. Uses local Postfix on port 25 (which works — proven by R297 reply-back)

HOW IT FITS:
  - Caller imports: from src.murphy_mail import send_email
  - send_email() → /usr/sbin/sendmail with murphy@ FROM
  - Always records the send to email_log (id, to, from, subject, status, deal_id)
  - Returns {ok: bool, message_id: str, log_id: str}

DEPENDENCIES:
  /usr/sbin/sendmail (Postfix)
  sqlite3
  email.mime

EVENT EMISSIONS: none yet (R301+ could publish EMAIL_SENT)

KNOWN LIMITS:
  - Synchronous send; for bulk use should be queued
  - No tracking pixel / open rate yet
  - HITL gate is opt-in via dry_run=True; caller must enforce founder approval
    per R66 for real outbound to real humans

LAST UPDATED: 2026-05-30 by R300
"""
from __future__ import annotations
import logging
import os
import sqlite3
import subprocess
import uuid
from datetime import datetime, timezone
from email.mime.text import MIMEText
from email.utils import make_msgid
from typing import Dict, Optional

logger = logging.getLogger("murphy.mail")

EMAIL_OUTBOUND_DB = "/var/lib/murphy-production/email_outbound.db"
DEFAULT_FROM = "murphy@murphy.systems"
DEFAULT_FROM_NAME = "Murphy"


# ── Schema migration ────────────────────────────────────────────────────────
def _ensure_schema() -> None:
    """email_log already exists; ensure it has needed columns."""
    con = sqlite3.connect(EMAIL_OUTBOUND_DB, timeout=5)
    try:
        # email_log already created by sales engine init; verify shape
        cols = {r[1] for r in con.execute("PRAGMA table_info(email_log)").fetchall()}
        if not cols:
            # Table missing — create minimal
            con.execute("""
                CREATE TABLE email_log (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    to_addr TEXT NOT NULL,
                    from_addr TEXT,
                    subject TEXT,
                    body_preview TEXT,
                    provider TEXT,
                    provider_message_id TEXT,
                    status TEXT NOT NULL,
                    status_detail TEXT,
                    contact_id TEXT,
                    deal_id TEXT,
                    delivered_at TEXT,
                    tenant_id TEXT DEFAULT 'platform_legacy'
                )
            """)
            con.execute("CREATE INDEX IF NOT EXISTS idx_email_log_to ON email_log(to_addr)")
            con.execute("CREATE INDEX IF NOT EXISTS idx_email_log_status ON email_log(status)")
        con.commit()
    finally:
        con.close()


# ── Logging ─────────────────────────────────────────────────────────────────
def _log_email(
    log_id: str,
    to_addr: str,
    from_addr: str,
    subject: str,
    body_preview: str,
    status: str,
    status_detail: str = "",
    provider_message_id: str = "",
    contact_id: str = "",
    deal_id: str = "",
    tenant_id: str = "platform",
) -> None:
    """Insert one row into email_log. Best-effort, never raises."""
    try:
        con = sqlite3.connect(EMAIL_OUTBOUND_DB, timeout=5)
        try:
            con.execute(
                "INSERT INTO email_log "
                "(id, to_addr, from_addr, subject, body_preview, provider, "
                " provider_message_id, status, status_detail, contact_id, deal_id, tenant_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (log_id, to_addr, from_addr, subject[:300], body_preview[:500],
                 "postfix", provider_message_id, status, status_detail[:300],
                 contact_id, deal_id, tenant_id),
            )
            con.commit()
        finally:
            con.close()
    except Exception as e:
        logger.warning("[murphy_mail] email_log INSERT failed: %s", e)


# ── Public API ──────────────────────────────────────────────────────────────
def send_email(
    to_addr: str,
    subject: str,
    body: str,
    from_addr: str = DEFAULT_FROM,
    from_name: str = DEFAULT_FROM_NAME,
    reply_to: Optional[str] = None,
    contact_id: str = "",
    deal_id: str = "",
    tenant_id: str = "platform",
    dry_run: bool = False,
) -> Dict:
    """
    Send an email via Postfix and log it to email_log.

    Args:
        to_addr: recipient email
        subject: subject line
        body: plain text body
        from_addr: envelope FROM (default: murphy@)
        from_name: display name (default: "Murphy")
        reply_to: optional Reply-To header
        contact_id: CRM contact ID for correlation
        deal_id: CRM deal ID for correlation
        tenant_id: tenant scope
        dry_run: if True, log status='dry_run' and don't send (HITL gate hook)

    Returns:
        {ok: bool, log_id: str, message_id: str, status: str}
    """
    _ensure_schema()
    log_id = f"em_{uuid.uuid4().hex[:12]}"
    message_id = make_msgid(domain="murphy.systems")
    body_preview = body[:500]

    if dry_run:
        _log_email(
            log_id=log_id, to_addr=to_addr, from_addr=from_addr,
            subject=subject, body_preview=body_preview,
            status="dry_run", status_detail="caller opted dry-run",
            provider_message_id=message_id,
            contact_id=contact_id, deal_id=deal_id, tenant_id=tenant_id,
        )
        logger.info("[murphy_mail] dry-run logged: to=%s subject=%r", to_addr, subject)
        return {"ok": True, "log_id": log_id, "message_id": message_id, "status": "dry_run"}

    msg = MIMEText(body, "plain", "utf-8")
    msg["From"] = f"{from_name} <{from_addr}>"
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg["Message-ID"] = message_id
    if reply_to:
        msg["Reply-To"] = reply_to

    try:
        proc = subprocess.run(
            ["/usr/sbin/sendmail", "-f", from_addr, to_addr],
            input=msg.as_bytes(),
            timeout=20,
            check=False,
            capture_output=True,
        )
        if proc.returncode == 0:
            _log_email(
                log_id=log_id, to_addr=to_addr, from_addr=from_addr,
                subject=subject, body_preview=body_preview,
                status="sent", status_detail="sendmail exit=0",
                provider_message_id=message_id,
                contact_id=contact_id, deal_id=deal_id, tenant_id=tenant_id,
            )
            logger.info("[murphy_mail] sent: to=%s subject=%r", to_addr, subject)
            return {"ok": True, "log_id": log_id, "message_id": message_id, "status": "sent"}
        else:
            err = (proc.stderr or b"").decode("utf-8", "replace")[:200]
            _log_email(
                log_id=log_id, to_addr=to_addr, from_addr=from_addr,
                subject=subject, body_preview=body_preview,
                status="failed", status_detail=f"sendmail exit={proc.returncode}: {err}",
                provider_message_id=message_id,
                contact_id=contact_id, deal_id=deal_id, tenant_id=tenant_id,
            )
            logger.warning("[murphy_mail] failed: to=%s exit=%s err=%s",
                           to_addr, proc.returncode, err)
            return {"ok": False, "log_id": log_id, "message_id": message_id,
                    "status": "failed", "error": err}
    except Exception as e:
        _log_email(
            log_id=log_id, to_addr=to_addr, from_addr=from_addr,
            subject=subject, body_preview=body_preview,
            status="error", status_detail=f"{type(e).__name__}: {e}",
            provider_message_id=message_id,
            contact_id=contact_id, deal_id=deal_id, tenant_id=tenant_id,
        )
        logger.warning("[murphy_mail] exception: %s", e)
        return {"ok": False, "log_id": log_id, "message_id": message_id,
                "status": "error", "error": str(e)}
