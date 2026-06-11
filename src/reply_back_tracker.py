"""
Ship 31x — Reply-back tracker.

LEAK 2: We send follow-up questions and ask domains to verify but never
mark whether they REPLIED. This module reconciles inbound_replies
against followup_log and verification_tokens to populate the
reply_back_received columns.

Runs as a periodic task — every inbound from an address we previously
followed-up-with within 30 days is counted as a reply-back.
"""
import sqlite3
import logging
from datetime import datetime, timezone, timedelta

DB_ENTITY = "/var/lib/murphy-production/entity_graph.db"
DB_INBOUND = "/var/lib/murphy-production/inbound_replies.db"
LOOKBACK_DAYS = 30
logger = logging.getLogger("reply_back_tracker")


def reconcile_replies() -> dict:
    """For every unreplied followup_log row, check if the address sent
    any inbound since the followup was sent. Mark accordingly.

    Returns stats dict.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)).isoformat()
    stats = {"checked": 0, "newly_replied": 0, "no_change": 0}

    try:
        # Attach inbound_replies DB so we can JOIN
        c = sqlite3.connect(DB_ENTITY)
        c.execute(f"ATTACH DATABASE '{DB_INBOUND}' AS inb")
        c.row_factory = sqlite3.Row

        pending = c.execute("""SELECT id, sent_ts, from_addr FROM followup_log
            WHERE reply_back_received = 0 AND sent_ts > ?""",
            (cutoff,)).fetchall()
        stats["checked"] = len(pending)

        for row in pending:
            # Normalize sent_ts for comparison: inbound uses 'YYYY-MM-DD HH:MM:SS'
            # while followup uses ISO with 'T' separator and tz. Strip both to
            # 'YYYY-MM-DD HH:MM:SS' so string > works correctly.
            sent_norm = row["sent_ts"].replace("T", " ")[:19]
            ib = c.execute("""SELECT received_at FROM inb.inbound_replies
                WHERE from_addr = ?
                  AND REPLACE(substr(received_at,1,19),'T',' ') > ?
                ORDER BY received_at ASC LIMIT 1""",
                (row["from_addr"], sent_norm)).fetchone()
            if ib:
                c.execute("""UPDATE followup_log
                    SET reply_back_received = 1, reply_back_ts = ?
                    WHERE id = ?""", (ib["received_at"], row["id"]))
                stats["newly_replied"] += 1
            else:
                stats["no_change"] += 1
        c.commit()
        c.close()
    except Exception as exc:
        logger.warning("reconcile_replies failed: %s", exc)
        stats["error"] = str(exc)
    return stats


def get_stats() -> dict:
    """Aggregate metrics for /os/agent-leaderboard."""
    try:
        c = sqlite3.connect(DB_ENTITY)
        c.row_factory = sqlite3.Row
        # Overall
        total = c.execute("SELECT COUNT(*) FROM followup_log").fetchone()[0]
        replied = c.execute(
            "SELECT COUNT(*) FROM followup_log WHERE reply_back_received=1"
        ).fetchone()[0]
        # Per-role
        by_role = c.execute("""SELECT role_hint, COUNT(*) sent,
            SUM(reply_back_received) replied
            FROM followup_log GROUP BY role_hint
            ORDER BY sent DESC""").fetchall()
        # 7-day window
        cutoff_7d = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        sent_7d = c.execute(
            "SELECT COUNT(*) FROM followup_log WHERE sent_ts > ?",
            (cutoff_7d,)
        ).fetchone()[0]
        replied_7d = c.execute(
            "SELECT COUNT(*) FROM followup_log WHERE sent_ts > ? AND reply_back_received=1",
            (cutoff_7d,)
        ).fetchone()[0]
        c.close()
        return {
            "total_sent": total,
            "total_replied": replied,
            "reply_rate": (replied / total) if total else 0,
            "sent_7d": sent_7d,
            "replied_7d": replied_7d,
            "reply_rate_7d": (replied_7d / sent_7d) if sent_7d else 0,
            "by_role": [dict(r) for r in by_role],
        }
    except Exception:
        return {"total_sent": 0, "total_replied": 0, "reply_rate": 0,
                "sent_7d": 0, "replied_7d": 0, "reply_rate_7d": 0,
                "by_role": []}
