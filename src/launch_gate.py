"""
Ship 31p — Launch gate primitives.

Three primitives that move stranger_responder from SHADOW-only to a
controlled live launch:

  1. is_allowlisted(domain) - org-level allowlist for live-mode reply
  2. is_unsubscribed(email) - check STOP registry
  3. compliance_footer() - CAN-SPAM required physical address + STOP

Plus adoption tracking:
  record_adoption_signal(domain, addr, role, vertical, ...) -
    rolling org-level ledger of who's emailing in.

Hard rule: if NOT allowlisted -> shadow mode (founder cc)
           if unsubscribed -> NO email at all
           every live email -> compliance footer mandatory
"""
import sqlite3
from datetime import datetime, timezone

DB = "/var/lib/murphy-production/entity_graph.db"

# CAN-SPAM physical address requirement
PHYSICAL_ADDRESS = ("Inoni LLC · Murphy Systems\n"
                    "5900 Balcones Dr STE 100\n"
                    "Austin, TX 78731")

UNSUBSCRIBE_INSTRUCTIONS = ("To stop receiving emails from Murphy, "
                            "reply with the word STOP in the body. "
                            "We process opt-outs within 10 minutes.")


def is_allowlisted(domain: str) -> bool:
    """Org-level live-mode allowlist. Domains not on list stay in shadow."""
    if not domain:
        return False
    domain = domain.lower().strip()
    try:
        c = sqlite3.connect(DB)
        row = c.execute(
            "SELECT 1 FROM launch_allowlist WHERE domain=? AND status='active'",
            (domain,)
        ).fetchone()
        c.close()
        return bool(row)
    except Exception:
        return False


def is_unsubscribed(email_addr: str) -> bool:
    """Hard block on unsubscribed contacts. Checked before EVERY outbound."""
    if not email_addr:
        return False
    addr = email_addr.lower().strip()
    domain = addr.split("@")[-1] if "@" in addr else ""
    try:
        c = sqlite3.connect(DB)
        # Email-level OR domain-level unsubscribe both count
        row = c.execute(
            "SELECT 1 FROM unsubscribe_registry WHERE email_addr=? OR (domain=? AND email_addr=domain)",
            (addr, domain)
        ).fetchone()
        c.close()
        return bool(row)
    except Exception:
        # Fail SAFE: if we can't verify, do not send
        return True


def register_unsubscribe(email_addr: str, method: str = "stop_keyword",
                          raw_signal: str = None):
    """Record an opt-out. Idempotent."""
    if not email_addr:
        return False
    addr = email_addr.lower().strip()
    domain = addr.split("@")[-1] if "@" in addr else ""
    try:
        c = sqlite3.connect(DB)
        c.execute("""INSERT OR IGNORE INTO unsubscribe_registry
            (email_addr, domain, registered_ts, method, raw_signal)
            VALUES (?,?,?,?,?)""",
            (addr, domain, datetime.now(timezone.utc).isoformat(),
             method, (raw_signal or "")[:500]))
        c.commit(); c.close()
        return True
    except Exception:
        return False


def compliance_footer(reply_to_addr: str = None) -> str:
    """CAN-SPAM compliant footer to append to every live outbound.

    Includes physical address (required), clear opt-out instructions,
    and (Ship 31v) a domain-verification claim link.
    """
    verify_line = ""
    if reply_to_addr:
        try:
            from src.verification_unlock import verify_link_for_email
            link = verify_link_for_email(reply_to_addr)
            if link:
                verify_line = (
                    "\n\nClaim your domain to make future Murphy replies go live "
                    "instead of being held for review:\n" + link
                )
        except Exception:
            pass
    return ("\n\n---\n"
            f"{PHYSICAL_ADDRESS}\n\n"
            f"{UNSUBSCRIBE_INSTRUCTIONS}"
            f"{verify_line}")


def add_to_allowlist(domain: str, org_name: str = None,
                      contact_name: str = None, notes: str = None) -> bool:
    """Add a domain to the live-mode allowlist."""
    if not domain:
        return False
    domain = domain.lower().strip()
    try:
        c = sqlite3.connect(DB)
        c.execute("""INSERT OR REPLACE INTO launch_allowlist
            (domain, org_name, contact_name, notes, added_ts, status)
            VALUES (?, ?, ?, ?, ?, 'active')""",
            (domain, org_name, contact_name, notes,
             datetime.now(timezone.utc).isoformat()))
        c.commit(); c.close()
        return True
    except Exception:
        return False


def record_adoption_signal(org_domain: str, contact_addr: str = None,
                            role: str = None, vertical: str = None,
                            actionable_count: int = 0,
                            last_action: str = None,
                            direction: str = "inbound"):
    """Track which orgs are actually engaging with Murphy over time.

    direction = 'inbound' (they emailed us) | 'outbound' (we replied)
    """
    if not org_domain:
        return
    try:
        c = sqlite3.connect(DB)
        now = datetime.now(timezone.utc).isoformat()
        existing = c.execute(
            "SELECT id, inbound_count, outbound_count FROM adoption_signal WHERE org_domain=?",
            (org_domain,)
        ).fetchone()
        if existing:
            row_id, in_count, out_count = existing
            if direction == "inbound":
                in_count = (in_count or 0) + 1
            else:
                out_count = (out_count or 0) + 1
            c.execute("""UPDATE adoption_signal
                SET last_seen_ts=?, inbound_count=?, outbound_count=?,
                    actionable_count=actionable_count + ?,
                    last_action=COALESCE(?, last_action)
                WHERE id=?""",
                (now, in_count, out_count, actionable_count or 0,
                 last_action, row_id))
        else:
            c.execute("""INSERT INTO adoption_signal
                (org_domain, contact_addr, first_seen_ts, last_seen_ts,
                 inbound_count, outbound_count, role_first_detected,
                 vertical_first_detected, actionable_count, last_action)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (org_domain, contact_addr, now, now,
                 1 if direction == "inbound" else 0,
                 0 if direction == "inbound" else 1,
                 role, vertical, actionable_count or 0, last_action))
        c.commit(); c.close()
    except Exception:
        pass


def check_stop_keyword(body: str) -> bool:
    """Detect STOP keyword (case-insensitive, word-boundary) in inbound."""
    if not body:
        return False
    import re
    # Word-boundary STOP/UNSUBSCRIBE/REMOVE in body
    return bool(re.search(r"\b(stop|unsubscribe|remove me)\b",
                           body.lower()[:2000]))


def get_adoption_summary(limit: int = 25):
    """Return current adoption ledger for /os/adoption dashboard."""
    try:
        c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
        rows = c.execute("""SELECT * FROM adoption_signal
            ORDER BY last_seen_ts DESC LIMIT ?""", (limit,)).fetchall()
        c.close()
        return [dict(r) for r in rows]
    except Exception:
        return []
