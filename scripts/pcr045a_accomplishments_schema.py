#!/usr/bin/env python3
"""
PCR-045a — persistent-agent accomplishments storage

FOUNDER DIRECTION (2026-06-09 00:10 PT):
  "All of these agents become a saved on what they accomplished and
   re utilized when they are useable for other tasks."

PRIOR FINDINGS (Ask-Murphy-First, SD-56):
  - src/agent_employment_bridge.py (R428) already persists souls to
    agent_souls table (16 rows from June 2 swarm work).
  - NO accomplishments tracking anywhere.
  - /api/rosetta/dispatch does NOT call employ_team() — persistence
    layer is BUILT but DORMANT.

THIS PCR (045a) — storage layer only.
  Adds an agent_accomplishments table. Append-only. Indexed for fast
  cross-domain reuse lookup by role + task signature.

  Schema:
    accomplishment_id TEXT PK
    profile_id        TEXT FK → agent_souls.profile_id
    role_class        TEXT     (e.g. "Lead Engineer", denormalized for filter speed)
    domain            TEXT     (the planner domain that hired them)
    task_prompt       TEXT     (what they were asked to do)
    task_keywords     TEXT     (extracted keywords, json list — supports cross-domain match)
    output_type       TEXT     (what they produced: architecture_decision, deliverable, ...)
    output_summary    TEXT     (first 500 chars of their output)
    success           INTEGER  (0/1)
    pass_number       INTEGER  (1 = kickoff, 2+ = refinement)
    refined_from      TEXT     (NULL or prior accomplishment_id if this was a refinement)
    fired_at          REAL     (epoch seconds)
    elapsed_us        INTEGER  (PCR-036b timer)

  Indexes:
    (role_class, success)            — "find Lead Engineers who succeeded"
    (domain, role_class)             — "find sales-domain Outreach Writers"
    (profile_id, fired_at DESC)      — "what did THIS agent do, newest first"

  NO writes happen yet. Writers come in PCR-045b.
  NO dispatch wiring yet. That comes in PCR-045c.

  This is the foundation: a place to put the receipts.

PRE-FLIGHT:
  - Idempotent: CREATE TABLE IF NOT EXISTS; re-runs are safe.
  - Reversible: --revert drops the table (only safe before any writes
    land; 045b will add a guard that prevents revert with rows present).
"""

from __future__ import annotations
import argparse
import sqlite3
import sys
from pathlib import Path

DB_PATH = "/var/lib/murphy-production/murphy_identity.db"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS agent_accomplishments (
    accomplishment_id TEXT PRIMARY KEY,
    profile_id        TEXT NOT NULL,
    role_class        TEXT NOT NULL,
    domain            TEXT,
    task_prompt       TEXT,
    task_keywords     TEXT,
    output_type       TEXT,
    output_summary    TEXT,
    success           INTEGER DEFAULT 1,
    pass_number       INTEGER DEFAULT 1,
    refined_from      TEXT,
    fired_at          REAL,
    elapsed_us        INTEGER
);

CREATE INDEX IF NOT EXISTS idx_accomplishments_role
    ON agent_accomplishments (role_class, success);

CREATE INDEX IF NOT EXISTS idx_accomplishments_domain_role
    ON agent_accomplishments (domain, role_class);

CREATE INDEX IF NOT EXISTS idx_accomplishments_profile_time
    ON agent_accomplishments (profile_id, fired_at DESC);
"""


def apply(verify: bool, revert: bool) -> int:
    print(f"PCR-045a accomplishments schema  verify={verify}  revert={revert}")
    if not Path(DB_PATH).exists():
        print(f"  ✗ DB not found: {DB_PATH}")
        return 1

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    if revert:
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='agent_accomplishments'"
        )
        if not cur.fetchone():
            print("  · already absent"); conn.close(); return 0
        cur.execute("SELECT COUNT(*) FROM agent_accomplishments")
        rows = cur.fetchone()[0]
        if rows > 0:
            print(f"  ✗ REFUSING revert: {rows} accomplishment row(s) present")
            print(f"    Drop manually if you really mean it.")
            conn.close(); return 1
        if verify:
            print("  ✓ would drop empty table"); conn.close(); return 0
        cur.executescript("""
            DROP INDEX IF EXISTS idx_accomplishments_role;
            DROP INDEX IF EXISTS idx_accomplishments_domain_role;
            DROP INDEX IF EXISTS idx_accomplishments_profile_time;
            DROP TABLE IF EXISTS agent_accomplishments;
        """)
        conn.commit(); conn.close()
        print("  ✓ table + indexes dropped"); return 0

    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='agent_accomplishments'"
    )
    if cur.fetchone():
        print("  · already present (idempotent re-run)")
        if verify:
            print("  ✓ schema check only — no changes")
        # Verify indexes too
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='agent_accomplishments'"
        )
        idx = [r[0] for r in cur.fetchall()]
        print(f"    indexes: {idx}")
        conn.close(); return 0

    if verify:
        print("  ✓ would create agent_accomplishments + 3 indexes")
        conn.close(); return 0

    cur.executescript(SCHEMA_SQL)
    conn.commit()
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='agent_accomplishments'"
    )
    idx = [r[0] for r in cur.fetchall()]
    conn.close()
    print(f"  ✓ table created + 3 indexes: {idx}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--revert", action="store_true")
    a = ap.parse_args()
    return apply(a.verify, a.revert)


if __name__ == "__main__":
    sys.exit(main())
