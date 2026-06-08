#!/usr/bin/env python3
"""
provenance_writer.py — PCR-025 / Phase 7.

Closes Shape-of-Complete gate (d) for Phases 4-6:
  - result_provenance table existed (Phase 4a) but had no producer
  - drill-down UI displayed it (Phase 4b) but always saw empty
  - canvas linking surfaced it (Phase 5) but had nothing to surface
  - bottleneck monitor scanned it (Phase 6a) but saw 0 rows
  - HITL writer was fed by it (Phase 6b) but never fired

This module supplies the missing producer. One row per non-trivial HTTP
request, written by audit_middleware as a fire-and-forget side effect.

Design constraints (rule #6, rule #7):
  - INSERT-only. Never UPDATE/DELETE existing rows.
  - Audit-failure-tolerant: any error here logs WARNING and continues.
    The request must succeed even if provenance can't be written.
  - Skip noise: don't write provenance for static/health/probe requests
    that would flood the table without providing operator value.
  - One transaction per write. No batching = no lost rows on crash.
"""

from __future__ import annotations
import json
import logging
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("murphy.provenance_writer")

DB_PATH = Path("/var/lib/murphy-production/entity_graph.db")

# Skip these paths — they're high-frequency probes/health checks and
# would flood the provenance table without operator value.
SKIP_PREFIXES = (
    "/static/",
    "/favicon",
    "/api/health",
    "/api/conductor/healthz",
    "/api/public/stats",
    "/api/self/status",
    "/api/self/summary",
    "/api/swarm/status",
    "/api/swarm/scheduler",
    "/api/swarm/patterns",
    "/api/swarm/critic",
    "/api/lcm/status",
    "/api/self-fix/status",
    "/api/confidence/status",
    "/api/ambient/stats",
    "/api/repair/proposals",
    "/api/gate-synthesis/health",
    "/api/provenance/",       # don't audit reads of the audit table
    "/api/bottleneck/",
    "/api/canvas/hotspots",
)


def _should_skip(path: str) -> bool:
    """High-frequency probe filter. Returns True if we should not write."""
    if not path:
        return True
    for prefix in SKIP_PREFIXES:
        if path.startswith(prefix):
            return True
    return False


def write_provenance(
    *,
    result_id: str,
    produced_by: str,
    action_name: str,
    inputs_json: Optional[str] = None,
    output_summary: Optional[str] = None,
    cost_usd: Optional[float] = None,
    tenant_id: Optional[str] = None,
    job_id: Optional[str] = None,
    parent_result_id: Optional[str] = None,
) -> bool:
    """
    Write one provenance row. Returns True on success, False on any error
    (caller should not raise — fire-and-forget pattern).
    """
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=2.0)
        try:
            conn.execute(
                """
                INSERT INTO result_provenance (
                    result_id, produced_at, produced_by, action_name,
                    inputs_json, output_summary, cost_usd,
                    tenant_id, job_id, parent_result_id
                ) VALUES (?, datetime('now'), ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    result_id, produced_by, action_name,
                    inputs_json, output_summary, cost_usd,
                    tenant_id, job_id, parent_result_id,
                ),
            )
            conn.commit()
            return True
        finally:
            conn.close()
    except sqlite3.IntegrityError:
        # PK collision (rare — UUID generation duplicated). Not fatal.
        logger.debug("provenance: PK collision for result_id=%s", result_id)
        return False
    except Exception as e:
        logger.warning("provenance: write failed: %s", e)
        return False


def write_from_request(
    *,
    path: str,
    method: str,
    status_code: int,
    latency_ms: int,
    actor: Optional[str] = None,
    body_hash: Optional[str] = None,
    response_size: int = 0,
) -> Optional[str]:
    """
    Wrapper meant to be called from audit_middleware._write_event.
    Returns the new result_id, or None if skipped/failed.
    """
    if _should_skip(path):
        return None

    # Only write for "meaningful" responses — skip 304/204/etc.
    if status_code in (204, 304):
        return None

    result_id = uuid.uuid4().hex
    action_name = f"{method.upper()} {path}"
    produced_by = actor or "anonymous"

    output_summary = (
        f"HTTP {status_code} · {latency_ms}ms · {response_size}b"
    )

    inputs = {
        "method": method.upper(),
        "path": path,
        "body_hash": body_hash,
    }

    ok = write_provenance(
        result_id=result_id,
        produced_by=produced_by,
        action_name=action_name,
        inputs_json=json.dumps(inputs, separators=(",", ":")),
        output_summary=output_summary,
    )
    return result_id if ok else None


# ── self-test ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("provenance_writer self-test")
    print("=" * 60)

    # 1. skip filter
    skip_tests = [
        ("/api/health", True),
        ("/api/auth/verify-email", False),
        ("/api/billing/checkout", False),
        ("/", False),
        ("/api/provenance/abc123", True),
        ("/static/foo.css", True),
        ("/api/canvas/hotspots", True),
        ("/api/canvas", False),
    ]
    for path, expected in skip_tests:
        got = _should_skip(path)
        marker = "✓" if got == expected else "✗"
        print(f"  {marker} _should_skip({path!r}) = {got} (expected {expected})")

    # 2. live write (will succeed if table exists)
    print()
    rid = write_provenance(
        result_id=uuid.uuid4().hex,
        produced_by="self-test",
        action_name="provenance_writer.self_test",
        output_summary="this is a self-test row",
    )
    print(f"  {'✓' if rid else '✗'} live write: {rid}")
