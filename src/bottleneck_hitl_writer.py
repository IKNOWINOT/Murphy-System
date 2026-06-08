#!/usr/bin/env python3
"""
bottleneck_hitl_writer.py — PCR-023 / Phase 6b: write bottleneck flags
to the canonical HITL queue.

Reads /var/lib/murphy-production/bottleneck_flags.json (written by
src/bottleneck_monitor.py) and INSERTs new flags into hitl_queue.db
with domain='bottleneck'.

Idempotent at the row level: each flag has a deterministic hitl_id
derived from flag_id + window. Re-running with the same input does
not duplicate rows.

Operating rule #6 (HITL queue sacred) is held by:
  - Only INSERTing, never UPDATEing existing rows
  - Only writing rows with domain='bottleneck' (own lane)
  - Never deleting any row
  - Including full evidence + dag_state_json so a human can act
"""

from __future__ import annotations
import argparse
import hashlib
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DATA_ROOT = Path("/var/lib/murphy-production")
FLAGS_JSON = DATA_ROOT / "bottleneck_flags.json"
HITL_DB = DATA_ROOT / "hitl_queue.db"

# Window for which a flag is considered "the same". A flag fired on
# 2026-06-08T22:00 belongs to a different ticket than the same flag
# fired on 2026-06-08T22:05 ONLY if they are in different windows.
# We bucket by hour by default so flooding is avoided.
WINDOW_BUCKET = "%Y-%m-%dT%H"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _expires_iso(hours: int = 24) -> str:
    from datetime import timedelta
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")


def derive_hitl_id(flag: dict[str, Any], generated_at: str) -> str:
    """Deterministic hitl_id. Same flag in same hour-bucket → same id."""
    bucket = (generated_at[:13] if generated_at else _now_iso()[:13])
    raw = f"{flag.get('flag_id', '?')}|{bucket}"
    h = hashlib.sha1(raw.encode()).hexdigest()[:12]
    return f"BTL_{h}"


def load_flags() -> dict[str, Any]:
    if not FLAGS_JSON.exists():
        return {"flags": [], "generated_at": None}
    with FLAGS_JSON.open() as f:
        return json.load(f)


def write_flags_to_hitl(dry_run: bool = False) -> dict[str, Any]:
    payload = load_flags()
    flags = payload.get("flags", [])
    generated_at = payload.get("generated_at") or _now_iso()
    result = {
        "scanned": len(flags),
        "inserted": 0,
        "skipped_existing": 0,
        "skipped_no_hitl": 0,
        "errors": [],
        "ids": [],
    }
    if not flags:
        return result
    if not HITL_DB.exists():
        result["errors"].append(f"hitl DB missing: {HITL_DB}")
        return result

    conn = sqlite3.connect(str(HITL_DB))
    cur = conn.cursor()

    for flag in flags:
        if not flag.get("hitl_required"):
            result["skipped_no_hitl"] += 1
            continue

        hitl_id = derive_hitl_id(flag, generated_at)
        cur.execute("SELECT 1 FROM hitl_queue WHERE hitl_id = ?", (hitl_id,))
        if cur.fetchone():
            result["skipped_existing"] += 1
            continue

        intent = f"{flag['flag_id']}: {flag.get('rationale', '')[:200]}"
        dag_state = {
            "source": "bottleneck_monitor",
            "phase": "6b",
            "flag": flag,
            "monitor_generated_at": generated_at,
        }

        if dry_run:
            result["ids"].append((hitl_id, "would_insert"))
            continue

        try:
            cur.execute("""
                INSERT INTO hitl_queue
                  (hitl_id, dag_id, dag_name, blocked_node_id, blocked_node_name,
                   intent, domain, stake, account, created_at, expires_at,
                   status, dag_state_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                hitl_id,
                f"bottleneck_{flag['flag_id']}",
                f"Bottleneck: {flag['flag_id']}",
                flag.get("target", ""),
                flag.get("kind", ""),
                intent,
                "bottleneck",  # NEW LANE
                flag.get("severity", "medium"),
                "system",
                _now_iso(),
                _expires_iso(24),
                "pending",
                json.dumps(dag_state),
            ))
            result["inserted"] += 1
            result["ids"].append((hitl_id, "inserted"))
        except Exception as e:
            result["errors"].append(f"{hitl_id}: {e}")

    if not dry_run:
        conn.commit()
    conn.close()
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    result = write_flags_to_hitl(dry_run=args.dry_run)
    if not args.quiet:
        print(f"Bottleneck → HITL writer ({'DRY-RUN' if args.dry_run else 'LIVE'})")
        print(f"  scanned: {result['scanned']}")
        print(f"  inserted: {result['inserted']}")
        print(f"  skipped (already in queue): {result['skipped_existing']}")
        print(f"  skipped (flag.hitl_required=False): {result['skipped_no_hitl']}")
        if result["errors"]:
            print(f"  errors: {result['errors']}")
        for hid, action in result["ids"]:
            print(f"    • {hid}: {action}")
    return 0 if not result["errors"] else 2


if __name__ == "__main__":
    sys.exit(main())
