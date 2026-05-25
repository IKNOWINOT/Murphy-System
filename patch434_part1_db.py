"""PATCH-434 Part 1 — Schema + seed for agent_action_policy table."""
import sqlite3
from datetime import datetime, timezone

DB = "/var/lib/murphy-production/murphy_mail.db"
conn = sqlite3.connect(DB)
conn.execute("""
    CREATE TABLE IF NOT EXISTS agent_action_policy (
        role             TEXT NOT NULL,
        action_type      TEXT NOT NULL,
        has_audit_gate   INTEGER NOT NULL DEFAULT 0,
        master_enabled   INTEGER NOT NULL DEFAULT 0,
        min_confidence   REAL    NOT NULL DEFAULT 0.95,
        max_per_day      INTEGER NOT NULL DEFAULT 0,
        runs_today       INTEGER NOT NULL DEFAULT 0,
        runs_total       INTEGER NOT NULL DEFAULT 0,
        last_reset_utc   TEXT,
        last_changed_at  TEXT,
        last_changed_by  TEXT,
        last_change_reason TEXT,
        PRIMARY KEY (role, action_type)
    )
""")
conn.execute("""
    CREATE TABLE IF NOT EXISTS agent_action_policy_history (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        role             TEXT NOT NULL,
        action_type      TEXT NOT NULL,
        field_name       TEXT NOT NULL,
        old_value        TEXT,
        new_value        TEXT,
        changed_by       TEXT NOT NULL,
        reason           TEXT,
        changed_at       TEXT NOT NULL
    )
""")

ACTION_TYPES = [
    ("email_outbound",      1),
    ("phone_call_outbound", 0),
    ("sms_outbound",        0),
    ("proposal_send",       0),
    ("quote_send",          0),
    ("contract_send",       0),
]
CUSTOMER_FACING_ROLES = ["vp-sales", "vp-marketing", "vp-cs", "ceo"]

now = datetime.now(timezone.utc).isoformat()
seeded = 0
for role in CUSTOMER_FACING_ROLES:
    for action_type, has_gate in ACTION_TYPES:
        cur = conn.execute(
            "SELECT 1 FROM agent_action_policy WHERE role=? AND action_type=?",
            (role, action_type)
        ).fetchone()
        if cur:
            continue
        conn.execute("""
            INSERT INTO agent_action_policy
            (role, action_type, has_audit_gate, master_enabled, min_confidence,
             max_per_day, last_reset_utc, last_changed_at, last_changed_by, last_change_reason)
            VALUES (?, ?, ?, 0, 0.95, 0, ?, ?, 'patch434-seed', 'Seeded — all blocked by default')
        """, (role, action_type, has_gate, now, now))
        seeded += 1
conn.commit()
print(f"  ✓ agent_action_policy seeded with {seeded} rows")

cols = [r[1] for r in conn.execute("PRAGMA table_info(outbound_email_queue)").fetchall()]
if "action_type" not in cols:
    conn.execute("ALTER TABLE outbound_email_queue ADD COLUMN action_type TEXT DEFAULT 'email_outbound'")
    conn.commit()
    print("  ✓ outbound_email_queue.action_type column added")
else:
    print("  ⚠ outbound_email_queue.action_type already present")
conn.close()
print("  ✓ Part 1 complete")
