"""
PATCH-R570 (2026-06-04) — surface real inbound to HITL queue

WHAT THIS IS:
  Closes the silent-signal-loss pattern. Rafael at AllQuotas booked a real
  meeting Jun 3 2026 and Murphy never told the founder. The signal sat in
  inbound_replies for 2 days because no module routed external customer
  replies into hitl_queue.

  This module is the bridge. Runs every 5 min via apscheduler.

DESIGN:
  source: inbound_replies WHERE
    received_at > now - 14 days
    AND from_addr does NOT end with @murphy.systems
    AND from_addr does NOT contain noreply / no-reply / dmarcreport / reddit-events
    AND is_test_fixture = 0
    AND intent_class IN ('reply_to_outreach','meeting','inquiry','general_query')
    AND id NOT IN (SELECT inbound_id FROM hitl_dedup)

  for each row:
    - draft apology/thank-you with rules-based templating
    - insert into hitl_queue with stake = high(meeting) / medium(reply) / low(inquiry)
    - record inbound_id in hitl_dedup so it doesn't re-fire

PUBLIC SURFACE:
  surface_pending(limit=20) -> {ok, surfaced, skipped, errors}
"""
import logging
import sqlite3
import json
from datetime import datetime, timezone

logger = logging.getLogger("inbound_to_hitl")
_INBOUND = "/var/lib/murphy-production/inbound_replies.db"
_HITL = "/var/lib/murphy-production/hitl_queue.db"
_DEDUP_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS hitl_dedup (
    inbound_id INTEGER PRIMARY KEY,
    hitl_id TEXT NOT NULL,
    surfaced_at TEXT NOT NULL
)
"""

_STAKE_BY_CLASS = {
    "meeting": "high",
    "reply_to_outreach": "medium",
    "inquiry": "medium",
    "general_query": "low",
}


def _ensure_dedup():
    c = sqlite3.connect(_INBOUND, timeout=5)
    c.execute(_DEDUP_TABLE_SQL)
    c.commit()
    c.close()


def _draft_reply(from_addr: str, subject: str, body: str, intent: str) -> str:
    name = from_addr.split("@")[0].split(".")[0].title() if "@" in from_addr else "there"
    if intent == "meeting":
        return f"Hi {name} — confirming our meeting. Let me know if anything has changed on your end. — Corey"
    if intent == "reply_to_outreach":
        return f"Hi {name} — thanks for getting back to me. Want to set up 15 min to dig in? — Corey"
    if intent == "inquiry":
        return f"Hi {name} — thanks for reaching out. Happy to answer — what specifically are you trying to figure out? — Corey"
    return f"Hi {name} — thanks for the note. — Corey"


def surface_pending(limit: int = 20) -> dict:
    _ensure_dedup()
    cin = sqlite3.connect(_INBOUND, timeout=5)
    cin.row_factory = sqlite3.Row
    chitl = sqlite3.connect(_HITL, timeout=5)

    rows = cin.execute("""
        SELECT id, received_at, from_addr, subject, body_preview, intent_class
        FROM inbound_replies
        WHERE received_at > datetime('now','-14 days')
          AND from_addr NOT LIKE '%@murphy.systems'
          AND from_addr NOT LIKE '%noreply%'
          AND from_addr NOT LIKE '%no-reply%'
          AND from_addr NOT LIKE '%dmarcreport%'
          AND from_addr NOT LIKE '%reddit-events%'
          AND from_addr NOT LIKE '%cpost%'
          AND from_addr NOT LIKE '%corey.gfc%'
          AND COALESCE(is_test_fixture, 0) = 0
          AND intent_class IN ('reply_to_outreach','meeting','inquiry','general_query')
          AND id NOT IN (SELECT inbound_id FROM hitl_dedup)
        ORDER BY received_at DESC
        LIMIT ?
    """, (limit,)).fetchall()

    surfaced = 0
    errors = []
    for r in rows:
        try:
            intent = r["intent_class"]
            stake = _STAKE_BY_CLASS.get(intent, "low")
            hitl_id = f"INB_{r['id']}_{intent}"
            draft = _draft_reply(r["from_addr"], r["subject"] or "", r["body_preview"] or "", intent)
            chitl.execute("""
                INSERT OR IGNORE INTO hitl_queue
                (hitl_id, dag_id, dag_name, blocked_node_id, blocked_node_name,
                 intent, domain, stake, account, created_at, expires_at, status, dag_state_json)
                VALUES (?, 'inbound_auto_surface', ?, 'reply_node', ?,
                        ?, 'sales', ?, ?, datetime('now'), datetime('now','+14 days'), 'pending', ?)
            """, (
                hitl_id,
                f"{intent}: {(r['subject'] or '')[:60]}",
                f"Reply to {r['from_addr']}",
                intent,
                stake,
                r["from_addr"],
                json.dumps({
                    "inbound_id": r["id"],
                    "from": r["from_addr"],
                    "subject": r["subject"],
                    "body_preview": (r["body_preview"] or "")[:500],
                    "received": r["received_at"],
                    "draft": draft,
                })
            ))
            cin.execute(
                "INSERT OR IGNORE INTO hitl_dedup(inbound_id, hitl_id, surfaced_at) VALUES (?,?,datetime('now'))",
                (r["id"], hitl_id)
            )
            surfaced += 1
        except Exception as e:
            errors.append({"id": r["id"], "error": str(e)})

    chitl.commit()
    cin.commit()
    chitl.close()
    cin.close()

    return {"ok": True, "surfaced": surfaced, "errors": errors, "scanned": len(rows)}


if __name__ == "__main__":
    print(surface_pending(limit=10))
