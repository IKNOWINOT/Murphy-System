"""
Ship 31bj — retention sweeper.

POLICY (founder direction 2026-06-13)
  - Any thread with no reply for 5 business days → marked for deletion
  - Marked threads are deleted from Murphy's server 10 days later
  - Replies always include full chain — no need to preserve archives

Runs hourly via /api/health/retention_sweep (called by cron or
manually). Idempotent: re-running does nothing harmful.
"""
import sqlite3
from datetime import datetime, timezone, timedelta
from typing import Dict


def _init_db():
    conn = sqlite3.connect("/var/lib/murphy-production/inbound_replies.db", timeout=10.0)
    # Add retention columns if not present
    cols = [r[1] for r in conn.execute("PRAGMA table_info(inbound_replies)").fetchall()]
    if "retention_status" not in cols:
        conn.execute("ALTER TABLE inbound_replies ADD COLUMN retention_status TEXT DEFAULT 'active'")
    if "marked_for_delete_at" not in cols:
        conn.execute("ALTER TABLE inbound_replies ADD COLUMN marked_for_delete_at TEXT")
    if "deleted_at" not in cols:
        conn.execute("ALTER TABLE inbound_replies ADD COLUMN deleted_at TEXT")
    conn.commit()
    conn.close()


def sweep() -> Dict:
    """Run one retention sweep. Returns counts."""
    _init_db()
    now = datetime.now(timezone.utc)
    # 5 business days ≈ 7 calendar days (conservative)
    mark_cutoff = (now - timedelta(days=7)).isoformat()
    # marked threads delete 10 calendar days after being marked
    delete_cutoff = (now - timedelta(days=10)).isoformat()
    
    conn = sqlite3.connect("/var/lib/murphy-production/inbound_replies.db", timeout=10.0)
    
    # STEP 1: mark stale threads
    marked = conn.execute("""
        UPDATE inbound_replies
        SET retention_status = 'marked_for_delete',
            marked_for_delete_at = ?
        WHERE retention_status = 'active'
          AND received_at < ?
          AND from_addr NOT LIKE '%@murphy.systems'
    """, (now.isoformat(), mark_cutoff)).rowcount
    
    # STEP 2: delete (zero-out body) threads marked more than 10 days ago
    deleted = conn.execute("""
        UPDATE inbound_replies
        SET body_preview = '[deleted per retention policy]',
            retention_status = 'deleted',
            deleted_at = ?
        WHERE retention_status = 'marked_for_delete'
          AND marked_for_delete_at < ?
    """, (now.isoformat(), delete_cutoff)).rowcount
    
    # STEP 3: bring "active" back for threads that received a NEW reply
    # (any from_addr that sent something in the last 7 days resets all their threads)
    reactivated = conn.execute("""
        UPDATE inbound_replies
        SET retention_status = 'active',
            marked_for_delete_at = NULL
        WHERE retention_status = 'marked_for_delete'
          AND from_addr IN (
            SELECT DISTINCT from_addr FROM inbound_replies
            WHERE received_at > ? AND from_addr NOT LIKE '%@murphy.systems'
          )
    """, (mark_cutoff,)).rowcount
    
    conn.commit()
    
    # COUNTS
    counts = dict(conn.execute("""
        SELECT retention_status, COUNT(*) FROM inbound_replies
        WHERE from_addr NOT LIKE '%@murphy.systems'
        GROUP BY retention_status
    """).fetchall())
    
    conn.close()
    return {
        "swept_at":     now.isoformat(),
        "marked":       marked,
        "deleted":      deleted,
        "reactivated":  reactivated,
        "totals":       counts,
        "policy":       "5 business days → mark; 10 calendar days → delete; reply resets.",
    }


if __name__ == "__main__":
    import json
    print(json.dumps(sweep(), indent=2))
