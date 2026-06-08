#!/usr/bin/env python3
"""
pcr020_migrate_provenance.py — schema migration for PCR-020 / Phase 4a.

Adds the `result_provenance` table to entity_graph.db. This is the canonical
backing store for the drill-down readout system.

Schema:
  result_id       TEXT PRIMARY KEY    UUID/ULID; the public handle a UI uses
  produced_at     TEXT NOT NULL       ISO timestamp
  produced_by     TEXT NOT NULL       agent/role/module that produced it
  action_name     TEXT NOT NULL       human-language description of what happened
  inputs_json     TEXT                JSON of inputs that produced this result
  source_refs_json TEXT               JSON list of (kind, id) pointers to upstream data
  parent_result_id TEXT               result_id of the upstream result (chain)
  output_summary  TEXT                short human-language summary of the output
  output_json     TEXT                full output payload (or pointer)
  cost_usd        REAL                optional cost attribution
  job_id          TEXT                optional job attribution
  tenant_id       TEXT                optional tenant attribution

Indexes:
  idx_provenance_produced_at      for time-window queries
  idx_provenance_parent_result_id for chain walks
  idx_provenance_job_id           for per-job rollups
  idx_provenance_tenant_id        for per-tenant rollups

Operating rules:
- Idempotent: safe to run multiple times. Uses CREATE TABLE IF NOT EXISTS.
- Snapshot taken before run (see state_snapshots/PCR-020_pre/).
- Read-only on existing tables; no destructive changes.

Usage:
    python3 scripts/pcr020_migrate_provenance.py            # do it
    python3 scripts/pcr020_migrate_provenance.py --verify   # just check schema
    python3 scripts/pcr020_migrate_provenance.py --dry-run  # print SQL, don't execute
"""

from __future__ import annotations
import argparse
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path("/var/lib/murphy-production/entity_graph.db")

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS result_provenance (
    result_id        TEXT PRIMARY KEY,
    produced_at      TEXT NOT NULL,
    produced_by      TEXT NOT NULL,
    action_name      TEXT NOT NULL,
    inputs_json      TEXT,
    source_refs_json TEXT,
    parent_result_id TEXT,
    output_summary   TEXT,
    output_json      TEXT,
    cost_usd         REAL,
    job_id           TEXT,
    tenant_id        TEXT
);

CREATE INDEX IF NOT EXISTS idx_provenance_produced_at      ON result_provenance(produced_at);
CREATE INDEX IF NOT EXISTS idx_provenance_parent_result_id ON result_provenance(parent_result_id);
CREATE INDEX IF NOT EXISTS idx_provenance_job_id           ON result_provenance(job_id);
CREATE INDEX IF NOT EXISTS idx_provenance_tenant_id        ON result_provenance(tenant_id);
"""

VERIFY_SQL = "SELECT name FROM sqlite_master WHERE type='table' AND name='result_provenance';"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--verify", action="store_true",
                    help="check schema exists, don't migrate")
    ap.add_argument("--dry-run", action="store_true",
                    help="print SQL, don't execute")
    args = ap.parse_args()

    if not DB_PATH.exists():
        print(f"  ✗ DB missing: {DB_PATH}")
        return 2

    if args.dry_run:
        print("─── SQL (dry-run, not executed) ───")
        print(SCHEMA_SQL)
        return 0

    conn = sqlite3.connect(str(DB_PATH))
    try:
        cur = conn.cursor()

        if args.verify:
            cur.execute(VERIFY_SQL)
            row = cur.fetchone()
            if row:
                print(f"  ✓ result_provenance table exists")
                # Also check indexes
                cur.execute("SELECT name FROM sqlite_master WHERE type='index' "
                            "AND tbl_name='result_provenance';")
                idx = [r[0] for r in cur.fetchall()]
                print(f"  ✓ indexes: {idx}")
                # And smoke row count
                cur.execute("SELECT COUNT(*) FROM result_provenance;")
                n = cur.fetchone()[0]
                print(f"  ✓ row count: {n}")
                return 0
            print(f"  ✗ result_provenance table missing — run without --verify to create")
            return 2

        # Execute schema
        cur.executescript(SCHEMA_SQL)
        conn.commit()
        print(f"  ✓ schema applied to {DB_PATH}")

        # Verify
        cur.execute(VERIFY_SQL)
        if cur.fetchone():
            print(f"  ✓ result_provenance table created/confirmed")
        else:
            print(f"  ✗ post-migrate verify failed")
            return 2
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
