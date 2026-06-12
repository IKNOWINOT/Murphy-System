"""
renewal_reminder_31aq — Ship 31aq

Daily job that finds tenant_subscriptions whose access expires
in the next 14 days and emails the buyer a fresh checkout link.

Since /api/payments/nowpayments/checkout creates ONE-SHOT invoices
(not recurring), this scheduler is the only thing standing between
"customer pays once" and "customer's access silently expires."

Run via: python3 -m src.renewal_reminder_31aq
Cron: daily at 09:00 UTC (02:00 LA, before US wake)
"""

from __future__ import annotations

import logging
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Dict, Any

logger = logging.getLogger("murphy.renewal_31aq")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

BILLING_DB = "/var/lib/murphy-production/billing.db"
LEDGER_DB  = "/var/lib/murphy-production/renewal_reminder_ledger.db"


def _ensure_ledger() -> None:
    Path(LEDGER_DB).parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(LEDGER_DB, timeout=2.0)
    c.execute("""
        CREATE TABLE IF NOT EXISTS renewal_reminders (
            event_id      INTEGER PRIMARY KEY AUTOINCREMENT,
            ts            TEXT NOT NULL,
            tenant_id     TEXT NOT NULL,
            tier          TEXT NOT NULL,
            paid_until    TEXT NOT NULL,
            days_until    INTEGER NOT NULL,
            reminder_kind TEXT NOT NULL,
            email_sent_to TEXT,
            outbound_id   TEXT,
            notes         TEXT
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_rr_tenant ON renewal_reminders(tenant_id)")
    c.commit()
    c.close()


def _find_expiring_subscriptions(window_days: int = 14) -> List[Dict[str, Any]]:
    """Find active subscriptions whose paid_until is within `window_days`."""
    if not Path(BILLING_DB).exists():
        logger.warning("billing.db missing")
        return []
    try:
        c = sqlite3.connect(f"file:{BILLING_DB}?mode=ro", uri=True, timeout=2.0)
        c.row_factory = sqlite3.Row
        # Skip synthetic smoke-test rows so we don't email fake addresses
        rows = c.execute("""
            SELECT tenant_id, tier, status, paid_until, nowpayments_id, updated_at
            FROM tenant_subscriptions
            WHERE COALESCE(synthetic_smoke_test, 0) = 0
              AND status NOT IN ('cancelled', 'refunded')
              AND paid_until IS NOT NULL
        """).fetchall()
        c.close()
    except Exception as e:
        logger.error("query failed: %s", e)
        return []

    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(days=window_days)
    expiring = []
    for r in rows:
        try:
            # tz-tolerant parse — SQLite datetime() returns naive,
            # ISO format from app code is aware. Normalize to UTC-aware.
            _raw = r["paid_until"].replace("Z", "+00:00").replace(" ", "T")
            paid_until = datetime.fromisoformat(_raw)
            if paid_until.tzinfo is None:
                paid_until = paid_until.replace(tzinfo=timezone.utc)
            if paid_until > now and paid_until <= cutoff:
                days_until = (paid_until - now).days
                expiring.append({
                    "tenant_id":   r["tenant_id"],
                    "tier":        r["tier"],
                    "paid_until":  r["paid_until"],
                    "days_until":  days_until,
                })
        except Exception as e:
            logger.warning("could not parse paid_until=%s for %s: %s",
                           r["paid_until"], r["tenant_id"], e)
    return expiring


def _already_reminded_today(tenant_id: str, kind: str) -> bool:
    """Don't double-send a reminder if today's job already fired."""
    _ensure_ledger()
    try:
        c = sqlite3.connect(f"file:{LEDGER_DB}?mode=ro", uri=True, timeout=2.0)
        row = c.execute(
            "SELECT 1 FROM renewal_reminders "
            "WHERE tenant_id = ? AND reminder_kind = ? "
            "  AND ts > datetime('now','-23 hours') LIMIT 1",
            (tenant_id, kind),
        ).fetchone()
        c.close()
        return bool(row)
    except Exception:
        return False


def _record_reminder(tenant_id: str, tier: str, paid_until: str,
                     days_until: int, kind: str,
                     sent_to: str = "", outbound_id: str = "",
                     notes: str = "") -> None:
    _ensure_ledger()
    try:
        c = sqlite3.connect(LEDGER_DB, timeout=2.0)
        c.execute(
            """INSERT INTO renewal_reminders
               (ts, tenant_id, tier, paid_until, days_until, reminder_kind,
                email_sent_to, outbound_id, notes)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (datetime.now(timezone.utc).isoformat(),
             tenant_id, tier, paid_until, days_until, kind,
             sent_to, outbound_id, notes),
        )
        c.commit()
        c.close()
    except Exception as e:
        logger.warning("ledger insert failed: %s", e)


def _resolve_email(tenant_id: str) -> str:
    """Tenant_id is often the buyer's email in our schema. Return as-is when valid."""
    if "@" in tenant_id and "." in tenant_id:
        return tenant_id
    return ""


def _render_reminder(tier: str, days_until: int, paid_until: str) -> tuple[str, str]:
    """Return (subject, body_text). Murphy voice."""
    subject = f"Your Murphy access expires in {days_until} days"
    body = f"""Hi,

Quick heads-up: your Murphy {tier.title()} access expires on {paid_until[:10]}.

That's {days_until} days from now. When it expires, your agent stops answering
emails, your queue stops processing, and your data stays right where it is —
nothing's deleted, but Murphy goes quiet.

To keep going, renew here:

  https://murphy.systems/pricing?renew=1&tier={tier}

Same price you paid last cycle. Same crypto checkout, no KYC, no card on file.

If you're done with Murphy, you don't need to do anything — access just expires
on {paid_until[:10]}.

Questions? Just hit reply.

— Murphy
"""
    return subject, body


def _send_reminder_via_outbound_queue(email: str, subject: str, body: str,
                                       tenant_id: str) -> str:
    """Queue the reminder through the existing outbound_email_queue so it picks
    up the multipart/HTML branded shell. Returns the queue_id or ''."""
    try:
        import json
        import uuid as _uuid
        mail_db = "/var/lib/murphy-production/murphy_mail.db"
        c = sqlite3.connect(mail_db, timeout=2.0)
        qid = f"oeq_{_uuid.uuid4().hex[:16]}"
        c.execute(
            """INSERT INTO outbound_email_queue
               (queue_id, from_address, to_addresses, subject, body, body_format,
                status, created_at, updated_at, metadata)
               VALUES (?, ?, ?, ?, ?, 'plain', 'pending_review',
                       datetime('now'), datetime('now'), ?)""",
            (qid, "murphy@murphy.systems", json.dumps([email]), subject, body,
             json.dumps({"kind": "renewal_reminder_31aq",
                         "tenant_id": tenant_id})),
        )
        c.commit()
        c.close()
        return qid
    except Exception as e:
        logger.warning("queue insert failed: %s", e)
        return ""


def run() -> Dict[str, Any]:
    """Main entry — find expiring subs, queue reminders, return summary."""
    _ensure_ledger()
    expiring = _find_expiring_subscriptions(window_days=14)
    logger.info("31aq found %d expiring subscriptions in the next 14 days", len(expiring))

    summary = {
        "ts":         datetime.now(timezone.utc).isoformat(),
        "considered": len(expiring),
        "reminded":   0,
        "skipped":    0,
        "errors":     0,
        "details":    [],
    }

    for sub in expiring:
        tenant_id  = sub["tenant_id"]
        tier       = sub["tier"]
        paid_until = sub["paid_until"]
        days       = sub["days_until"]

        # Reminder kind buckets — 14, 7, 1 days out
        if days >= 13:
            kind = "T-14"
        elif days >= 6:
            kind = "T-7"
        elif days >= 0:
            kind = "T-1"
        else:
            summary["skipped"] += 1
            continue

        if _already_reminded_today(tenant_id, kind):
            summary["skipped"] += 1
            summary["details"].append({
                "tenant_id": tenant_id, "kind": kind,
                "result": "already_reminded_today",
            })
            continue

        email = _resolve_email(tenant_id)
        if not email:
            summary["errors"] += 1
            summary["details"].append({
                "tenant_id": tenant_id, "kind": kind,
                "result": "no_email_resolved",
            })
            _record_reminder(tenant_id, tier, paid_until, days, kind,
                             notes="no_email_resolved")
            continue

        subject, body = _render_reminder(tier, days, paid_until)
        qid = _send_reminder_via_outbound_queue(email, subject, body, tenant_id)
        if qid:
            summary["reminded"] += 1
            summary["details"].append({
                "tenant_id": tenant_id, "kind": kind,
                "result": "queued", "queue_id": qid,
            })
            _record_reminder(tenant_id, tier, paid_until, days, kind,
                             sent_to=email, outbound_id=qid,
                             notes="queued_pending_review")
        else:
            summary["errors"] += 1
            _record_reminder(tenant_id, tier, paid_until, days, kind,
                             notes="queue_insert_failed")

    logger.info("31aq summary: %s", summary)
    return summary


if __name__ == "__main__":
    result = run()
    print(f"\n31aq RENEWAL REMINDER — {result['considered']} considered, "
          f"{result['reminded']} reminded, {result['skipped']} skipped, "
          f"{result['errors']} errors")
    sys.exit(0 if result["errors"] == 0 else 1)
