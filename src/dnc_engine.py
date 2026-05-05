"""
dnc_engine.py — Do Not Contact Engine (PATCH-190)
Enforces DNC suppression before any outreach. Sources: manual, opt-out reply, domain block.
"""
import sqlite3 as _sq3
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

DNC_DB = "/var/lib/murphy-production/crm.db"

# ── Opt-out trigger phrases (case-insensitive scan) ──────────────────────────
OPT_OUT_PHRASES = [
    "unsubscribe", "remove me", "opt out", "opt-out", "do not contact",
    "stop emailing", "stop contacting", "take me off", "remove from list",
    "don't contact", "don't email", "not interested", "please stop",
    "leave me alone", "no more emails", "cease contact",
]

def _db() -> _sq3.Connection:
    conn = _sq3.connect(DNC_DB, timeout=5)
    conn.row_factory = _sq3.Row
    return conn


def ensure_table() -> None:
    """Create dnc_suppression table if it doesn't exist."""
    with _db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS dnc_suppression (
                id          TEXT PRIMARY KEY,
                email       TEXT DEFAULT '',
                phone       TEXT DEFAULT '',
                domain      TEXT DEFAULT '',
                reason      TEXT DEFAULT '',
                source      TEXT DEFAULT 'manual',
                added_by    TEXT DEFAULT 'system',
                added_at    TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_dnc_email  ON dnc_suppression(email)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_dnc_domain ON dnc_suppression(domain)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_dnc_phone  ON dnc_suppression(phone)")
        conn.commit()
    logger.info("[DNC] Table ready")


def _extract_domain(email: str) -> str:
    if email and '@' in email:
        return email.split('@', 1)[1].lower().strip()
    return ''


def check(email: str = '', phone: str = '') -> Tuple[bool, str]:
    """
    Returns (blocked: bool, reason: str).
    blocked=True means DO NOT CONTACT.
    Checks: exact email, email domain, exact phone.
    """
    email  = (email  or '').lower().strip()
    phone  = re.sub(r'[^\d+]', '', phone or '')
    domain = _extract_domain(email)

    try:
        with _db() as conn:
            # Check exact email
            if email:
                row = conn.execute(
                    "SELECT reason FROM dnc_suppression WHERE LOWER(email)=? LIMIT 1", (email,)
                ).fetchone()
                if row:
                    return True, f"Email on DNC list: {row['reason'] or 'opt-out'}"

            # Check domain-level block
            if domain:
                row = conn.execute(
                    "SELECT reason FROM dnc_suppression WHERE domain=? AND email='' LIMIT 1", (domain,)
                ).fetchone()
                if row:
                    return True, f"Domain on DNC list: {domain} ({row['reason'] or 'domain block'})"

            # Check phone
            if phone:
                row = conn.execute(
                    "SELECT reason FROM dnc_suppression WHERE phone=? LIMIT 1", (phone,)
                ).fetchone()
                if row:
                    return True, f"Phone on DNC list: {row['reason'] or 'opt-out'}"

    except Exception as e:
        logger.error("[DNC] check() error: %s", e)
        # Fail OPEN — do not block on DB error, but log it
        return False, ''

    return False, ''


def add(email: str = '', phone: str = '', domain: str = '',
        reason: str = 'manual', source: str = 'manual', added_by: str = 'system') -> str:
    """Add a contact to the DNC list. Returns the record ID."""
    record_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    email  = (email  or '').lower().strip()
    phone  = re.sub(r'[^\d+]', '', phone or '')
    domain = (domain or _extract_domain(email)).lower().strip()

    try:
        with _db() as conn:
            # Check for exact duplicate first
            existing = conn.execute(
                "SELECT id FROM dnc_suppression WHERE email=? OR (phone!='' AND phone=?)",
                (email, phone or '__NO_PHONE__')
            ).fetchone()
            if existing:
                logger.info("[DNC] Already suppressed: %s", email or phone)
                return existing['id']

            conn.execute(
                "INSERT INTO dnc_suppression (id,email,phone,domain,reason,source,added_by,added_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (record_id, email, phone, domain, reason, source, added_by, now)
            )
            conn.commit()
            logger.info("[DNC] Added: %s (%s) — reason: %s", email or phone or domain, source, reason)
    except Exception as e:
        logger.error("[DNC] add() error: %s", e)

    return record_id


def remove(email: str = '', phone: str = '') -> bool:
    """Remove a contact from DNC (re-authorize contact). Returns True if removed."""
    email = (email or '').lower().strip()
    phone = re.sub(r'[^\d+]', '', phone or '')
    try:
        with _db() as conn:
            cur = conn.execute(
                "DELETE FROM dnc_suppression WHERE email=? OR (phone!='' AND phone=?)",
                (email, phone or '__NONE__')
            )
            conn.commit()
            removed = cur.rowcount > 0
            if removed:
                logger.info("[DNC] Removed: %s", email or phone)
            return removed
    except Exception as e:
        logger.error("[DNC] remove() error: %s", e)
        return False


def list_all(limit: int = 200) -> list:
    """Return all DNC records."""
    try:
        with _db() as conn:
            rows = conn.execute(
                "SELECT id,email,phone,domain,reason,source,added_by,added_at "
                "FROM dnc_suppression ORDER BY added_at DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]
    except Exception as e:
        logger.error("[DNC] list_all() error: %s", e)
        return []


def scan_for_opt_out(text: str) -> bool:
    """Return True if text contains an opt-out phrase."""
    low = text.lower()
    return any(phrase in low for phrase in OPT_OUT_PHRASES)


def process_inbound_reply(sender_email: str, body: str, source: str = 'email_reply') -> bool:
    """
    Call this when an inbound email arrives.
    If the body contains an opt-out phrase, auto-add sender to DNC.
    Returns True if suppressed.
    """
    if scan_for_opt_out(body):
        add(
            email=sender_email,
            reason='opt-out reply',
            source=source,
            added_by='auto'
        )
        logger.warning("[DNC] Auto-suppressed %s after opt-out reply", sender_email)
        return True
    return False
