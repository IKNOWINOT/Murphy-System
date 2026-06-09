"""
query_outreach.py — outreach activity queries against the real CRM schema.

History:
  Originally a placeholder querying a non-existent `outreach_log` table
  at the wrong DB path (`src/db/crm.db`). PCR-028 rewires it to the real
  CRM database and the real `activities` table that lead_prospector.py
  actually writes to.

Canonical CRM data location:
  /var/lib/murphy-production/crm.db  → table: activities

  activity_type values (live as of 2026-06-09):
    email_sent (78), email_followup (62), email_followup_unverified (34),
    email_send_failed (34), email_followup_failed (7), follow_up (63),
    note (1)

  Schema: (id, activity_type, contact_id, deal_id, user_id,
           summary, details, created_at)

Reply tracking note:
  We never wrote 'reply' as an activity_type — replies are tracked
  separately in `deal_reply_correlations`. get_last_reply_timestamp()
  is preserved for backward compat; it now returns from the real
  reply correlations table.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional

# Canonical paths (per shape_of_complete + audit-first rule)
CRM_DB = Path("/var/lib/murphy-production/crm.db")


def _connect() -> Optional[sqlite3.Connection]:
    """Return a CRM DB connection, or None if the DB isn't available."""
    if not CRM_DB.exists():
        return None
    return sqlite3.connect(str(CRM_DB), timeout=5)


def get_last_reply_timestamp() -> str:
    """Return the most recent reply timestamp from deal_reply_correlations,
       or 'No replies' if no replies have been recorded yet."""
    conn = _connect()
    if conn is None:
        return "No replies"
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT MAX(created_at) FROM deal_reply_correlations"
        )
        row = cur.fetchone()
        return row[0] if row and row[0] else "No replies"
    except sqlite3.OperationalError:
        # Table doesn't exist yet — that's fine, it'll be created on
        # first reply.
        return "No replies"
    finally:
        conn.close()


def get_last_outreach_timestamp(contact_id: Optional[str] = None) -> str:
    """Return the most recent outreach activity timestamp for a given
       contact, or globally if contact_id is None. Returns 'No outreach'
       if nothing has been sent yet."""
    conn = _connect()
    if conn is None:
        return "No outreach"
    try:
        cur = conn.cursor()
        if contact_id:
            cur.execute(
                "SELECT MAX(created_at) FROM activities "
                "WHERE contact_id = ? "
                "AND activity_type LIKE 'email_%'",
                (contact_id,)
            )
        else:
            cur.execute(
                "SELECT MAX(created_at) FROM activities "
                "WHERE activity_type LIKE 'email_%'"
            )
        row = cur.fetchone()
        return row[0] if row and row[0] else "No outreach"
    finally:
        conn.close()


def get_outreach_summary() -> dict:
    """Return counts per activity_type for outreach-related activities.
       Useful for dashboards and health checks."""
    conn = _connect()
    if conn is None:
        return {"error": "CRM DB unavailable"}
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT activity_type, COUNT(*) FROM activities "
            "WHERE activity_type LIKE 'email_%' "
            "GROUP BY activity_type"
        )
        rows = cur.fetchall()
        return {row[0]: row[1] for row in rows}
    finally:
        conn.close()


if __name__ == "__main__":
    print("Last reply:    ", get_last_reply_timestamp())
    print("Last outreach: ", get_last_outreach_timestamp())
    print("Summary:       ", get_outreach_summary())
