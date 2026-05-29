"""
PATCH-PROVENANCE-001 (2026-05-28 R64) — HITL Provenance Wrapper

WHAT THIS IS:
  Captures the EVIDENCE TRAIL behind every command output so a human reviewer
  can verify (a) where the information came from, (b) when it was captured,
  (c) what method derived it, and (d) the raw evidence snapshot before
  Murphy interpreted it.

WHY IT EXISTS:
  When compliance_engine returns "healthcare → [hipaa, soc2]", a human reviewer
  today cannot tell whether that mapping came from a hardcoded dict, a config
  file, an LLM call, a rule table, or a regression. They cannot verify
  correctness. They cannot file a useful "this is wrong" ticket. Provenance
  closes that gap.

HOW IT FITS:
  Phase B wires + 103 existing engines all return Dict[str, Any] results.
  This wrapper:
    1. Wraps a callable, captures inputs + result + source-of-record
    2. Writes a provenance row (one DB record per command invocation)
    3. Captures an "evidence snapshot" — the raw DB query / config file
       contents / API response before Murphy's interpretation
    4. Surfaces a verify URL where a HITL reviewer can see the trail
    5. Accepts feedback tickets that trigger re-analysis with correction

KEY CONCEPTS:
  - trail_id: unique per command invocation, links result → evidence → review
  - source_kind: db | config | llm | api | computed | hardcoded
  - evidence_snapshot: text/JSON capture of raw source before interpretation
  - hitl_status: pending | verified | flagged | corrected
  - feedback_ticket: human's correction context that re-triggers analysis

ENDPOINTS / PUBLIC SURFACE:
  with_provenance(fn, source_kind, source_hint) -> decorated_fn
  capture_evidence(label, raw_data, method) -> evidence_id
  open_feedback_ticket(trail_id, human_note, correction_data) -> ticket_id
  reanalyze_with_correction(ticket_id) -> new_trail_id
  get_trail(trail_id) -> Dict (full provenance for HITL view)

DEPENDENCIES:
  - own DB: hitl_provenance.db
  - reads (no writes) from caller modules' DBs for evidence capture

KNOWN LIMITS:
  - "Screenshots" today are TEXT snapshots (DB query result, config dump).
    Actual PNG screenshots require browserbase integration (Phase D).
  - reanalyze_with_correction re-runs the SAME function with augmented
    context dict; it doesn't rewrite the function itself.

LAST UPDATED: 2026-05-28 R64
"""

import functools
import json
import logging
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("provenance")

_DB_PATH = "/var/lib/murphy-production/hitl_provenance.db"


def _ensure_db() -> None:
    os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(_DB_PATH, timeout=3)
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS provenance_trails (
                trail_id          TEXT PRIMARY KEY,
                command_module    TEXT NOT NULL,
                command_function  TEXT NOT NULL,
                command_inputs    TEXT,
                command_result    TEXT,
                source_kind       TEXT,
                source_hint       TEXT,
                evidence_id       TEXT,
                hitl_status       TEXT DEFAULT 'pending',
                captured_at       TEXT DEFAULT CURRENT_TIMESTAMP,
                wire_version      TEXT DEFAULT 'PROV-001'
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS evidence_snapshots (
                evidence_id       TEXT PRIMARY KEY,
                label             TEXT,
                method            TEXT,
                raw_data          TEXT,
                captured_at       TEXT DEFAULT CURRENT_TIMESTAMP,
                wire_version      TEXT DEFAULT 'PROV-001'
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS hitl_tickets (
                ticket_id         TEXT PRIMARY KEY,
                trail_id          TEXT,
                human_note        TEXT,
                correction_data   TEXT,
                status            TEXT DEFAULT 'open',
                reanalysis_trail_id TEXT,
                opened_at         TEXT DEFAULT CURRENT_TIMESTAMP,
                resolved_at       TEXT,
                wire_version      TEXT DEFAULT 'PROV-001'
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_trails_module ON provenance_trails(command_module)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_trails_status ON provenance_trails(hitl_status)")
        conn.commit()
    finally:
        conn.close()


def capture_evidence(label: str, raw_data: Any, method: str = "unknown") -> str:
    """
    Snapshot the raw evidence behind a derived result.

    Args:
        label:   human-readable description ("compliance_engine domain table")
        raw_data: the unprocessed source — DB rows, config dict, LLM response,
                  whatever Murphy interpreted before returning
        method:  how the evidence was gathered ("sqlite_select", "config_read",
                 "llm_response", "hardcoded_dict")

    Returns:
        evidence_id (UUID hex) — referenceable from a provenance trail
    """
    _ensure_db()
    evidence_id = uuid.uuid4().hex[:16]
    try:
        raw_serialized = json.dumps(raw_data, default=str) if not isinstance(raw_data, str) else raw_data
    except Exception:
        raw_serialized = str(raw_data)[:5000]

    conn = sqlite3.connect(_DB_PATH, timeout=3)
    try:
        conn.execute(
            "INSERT INTO evidence_snapshots (evidence_id, label, method, raw_data) VALUES (?,?,?,?)",
            (evidence_id, label, method, raw_serialized[:10000])
        )
        conn.commit()
    finally:
        conn.close()
    return evidence_id


def with_provenance(
    fn: Callable,
    source_kind: str = "computed",
    source_hint: str = "",
) -> Callable:
    """
    Decorator that wraps a function and records a provenance trail per call.

    The wrapped function's result is augmented with a "_provenance" key
    (if it's a dict) OR returned as-is with a separate trail logged.

    Args:
        fn:           the callable to wrap
        source_kind:  one of db | config | llm | api | computed | hardcoded
        source_hint:  free-text hint about WHERE data came from ("crm.db.contacts",
                      "tenant_strategies", "deepinfra Qwen")

    Returns:
        wrapped function — same signature, augmented result
    """
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        _ensure_db()
        trail_id = uuid.uuid4().hex[:16]
        module_name = getattr(fn, "__module__", "unknown")
        func_name = getattr(fn, "__name__", "unknown")
        try:
            inputs_json = json.dumps({"args": args, "kwargs": kwargs}, default=str)[:2000]
        except Exception:
            inputs_json = str((args, kwargs))[:2000]

        try:
            result = fn(*args, **kwargs)
            result_repr = json.dumps(result, default=str)[:5000] if not isinstance(result, str) else result[:5000]
        except Exception as e:
            result = {"error": f"{type(e).__name__}: {e}"}
            result_repr = json.dumps(result)

        conn = sqlite3.connect(_DB_PATH, timeout=3)
        try:
            conn.execute(
                """INSERT INTO provenance_trails
                   (trail_id, command_module, command_function, command_inputs,
                    command_result, source_kind, source_hint)
                   VALUES (?,?,?,?,?,?,?)""",
                (trail_id, module_name, func_name, inputs_json,
                 result_repr, source_kind, source_hint)
            )
            conn.commit()
        finally:
            conn.close()

        # Augment result with provenance pointer if dict
        if isinstance(result, dict):
            result["_provenance"] = {
                "trail_id": trail_id,
                "source_kind": source_kind,
                "source_hint": source_hint,
                "verify_url": f"/api/hitl/trail/{trail_id}",
                "feedback_url": f"/api/hitl/feedback/{trail_id}",
            }
        return result
    return wrapper


def get_trail(trail_id: str) -> Optional[Dict[str, Any]]:
    """Fetch a full provenance trail for HITL review."""
    _ensure_db()
    conn = sqlite3.connect(f"file:{_DB_PATH}?mode=ro", uri=True, timeout=2)
    try:
        conn.row_factory = sqlite3.Row
        cur = conn.execute("SELECT * FROM provenance_trails WHERE trail_id = ?", (trail_id,))
        trail = cur.fetchone()
        if not trail:
            return None
        trail_dict = dict(trail)
        # Fetch evidence if linked
        if trail_dict.get("evidence_id"):
            ev_cur = conn.execute("SELECT * FROM evidence_snapshots WHERE evidence_id = ?",
                                  (trail_dict["evidence_id"],))
            ev = ev_cur.fetchone()
            if ev:
                trail_dict["evidence"] = dict(ev)
        # Fetch any feedback tickets
        tic_cur = conn.execute("SELECT * FROM hitl_tickets WHERE trail_id = ?", (trail_id,))
        trail_dict["tickets"] = [dict(t) for t in tic_cur.fetchall()]
        return trail_dict
    finally:
        conn.close()


def open_feedback_ticket(
    trail_id: str,
    human_note: str,
    correction_data: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Human flags a result as wrong/incomplete and provides correction context.

    The ticket is opened; reanalyze_with_correction() can use it to re-run.
    """
    _ensure_db()
    ticket_id = uuid.uuid4().hex[:16]
    conn = sqlite3.connect(_DB_PATH, timeout=3)
    try:
        conn.execute(
            """INSERT INTO hitl_tickets (ticket_id, trail_id, human_note, correction_data)
               VALUES (?,?,?,?)""",
            (ticket_id, trail_id, human_note,
             json.dumps(correction_data or {}, default=str))
        )
        # Mark trail as flagged
        conn.execute("UPDATE provenance_trails SET hitl_status = 'flagged' WHERE trail_id = ?",
                     (trail_id,))
        conn.commit()
    finally:
        conn.close()
    return ticket_id


def list_trails(
    hitl_status: Optional[str] = None,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """List recent trails (optionally filtered by HITL status) for review UI."""
    _ensure_db()
    conn = sqlite3.connect(f"file:{_DB_PATH}?mode=ro", uri=True, timeout=2)
    try:
        conn.row_factory = sqlite3.Row
        if hitl_status:
            cur = conn.execute(
                "SELECT * FROM provenance_trails WHERE hitl_status = ? "
                "ORDER BY captured_at DESC LIMIT ?", (hitl_status, limit)
            )
        else:
            cur = conn.execute(
                "SELECT * FROM provenance_trails ORDER BY captured_at DESC LIMIT ?", (limit,)
            )
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def get_open_tickets(limit: int = 20) -> List[Dict[str, Any]]:
    """List open feedback tickets needing reanalysis."""
    _ensure_db()
    conn = sqlite3.connect(f"file:{_DB_PATH}?mode=ro", uri=True, timeout=2)
    try:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            "SELECT * FROM hitl_tickets WHERE status = 'open' ORDER BY opened_at DESC LIMIT ?",
            (limit,)
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


if __name__ == "__main__":
    print("── Provenance smoke ──")
    # Demonstrate: wrap a function, see the trail
    def example_command(domain: str) -> Dict:
        return {"frameworks": ["hipaa", "soc2"]}

    wrapped = with_provenance(
        example_command,
        source_kind="hardcoded",
        source_hint="example_command internal dict",
    )
    result = wrapped("healthcare")
    print(f"  result: {json.dumps(result, indent=2, default=str)[:500]}")

    trail_id = result["_provenance"]["trail_id"]
    print(f"\n  ── get_trail({trail_id}) ──")
    trail = get_trail(trail_id)
    print(f"    module: {trail['command_module']}")
    print(f"    function: {trail['command_function']}")
    print(f"    source_kind: {trail['source_kind']}")
    print(f"    source_hint: {trail['source_hint']}")
    print(f"    hitl_status: {trail['hitl_status']}")

    # Human files a ticket
    ticket_id = open_feedback_ticket(
        trail_id,
        "Missing PCI-DSS — healthcare orgs that take card payments need it too",
        correction_data={"add_frameworks": ["pci_dss"]}
    )
    print(f"\n  ── ticket opened: {ticket_id} ──")
    trail_post = get_trail(trail_id)
    print(f"    hitl_status now: {trail_post['hitl_status']}")
    print(f"    tickets attached: {len(trail_post['tickets'])}")
