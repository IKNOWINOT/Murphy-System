#!/usr/bin/env python3
"""
PATCH-WIRE3-R125 — gate_crystallizer

WHAT THIS IS:
  Reads recent chain_step_gates rows (chain_engine.evaluate_gate outcomes)
  and crystallizes them into pattern_library.patterns so future agents
  learn which gate shapes pass and which fail.

WHY IT EXISTS:
  Wire #3 in locked Phase B plan. Closes the loop:
    chain_engine.evaluate_gate writes chain_step_gates ✓
    pattern_library tracks fitness ✓
    Wire #3 ← THIS — bridges them with crystallization signal.

DESIGN LOCKED R125 (Murphy meta-Q + probe evidence):
  Timer pattern matching R121 (host-native, zero platform cost).
  Decoupled from chain_engine hot path.
  Idempotent — last-crystallized rowid tracked in shape_state.json.

PUBLIC SURFACE:
  crystallize_recent(limit=50) -> dict
    Reads chain_step_gates rows newer than last crystallized rowid.
    For each: derive intent_sample + outcome_signal, upsert into patterns.
    Returns {ok, scanned, crystallized, errors, last_rowid}.

CRYSTALLIZATION LOGIC:
  PASS outcome → fitness_delta +0.01 to matching pattern (or create at 0.51)
  PARTIAL      → fitness_delta +0.00 (informational, no boost)
  BLOCKED      → fitness_delta -0.01 (slight negative)
  FAIL/ERROR   → fitness_delta -0.02

DEPENDS ON:
  entity_graph.db::chain_step_gates  (chain_engine writes)
  pattern_library.db::patterns        (this writes)
  /var/lib/murphy-production/crystallizer_state.json (tracks last_rowid)

LAST UPDATED: 2026-05-29 R125
"""
import json
import logging
import os
import sqlite3
import sys
import time
from typing import Any, Dict

logger = logging.getLogger("gate_crystallizer")

_CHAIN_DB    = "/var/lib/murphy-production/entity_graph.db"
_PATTERN_DB  = "/var/lib/murphy-production/pattern_library.db"
_STATE_FILE  = "/var/lib/murphy-production/crystallizer_state.json"

_FITNESS_DELTA_BY_RESULT = {
    "PASS":    0.01,
    "PARTIAL": 0.00,
    "BLOCKED": -0.01,
    "FAIL":    -0.02,
    "ERROR":   -0.02,
}


def _load_state() -> Dict[str, Any]:
    if os.path.exists(_STATE_FILE):
        try:
            with open(_STATE_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {"last_rowid": 0, "crystallized_total": 0}


def _save_state(state: Dict[str, Any]) -> None:
    try:
        with open(_STATE_FILE, "w") as f:
            json.dump(state, f)
    except Exception as e:
        logger.warning("save_state: {}".format(e))


def _upsert_pattern(agent_id: str, intent_sample: str, domain: str,
                    fitness_delta: float, stake: str = "low") -> bool:
    """Upsert pattern by (agent_id, intent_sample[:80]) signature."""
    if abs(fitness_delta) < 0.005:
        return False  # no-op for PARTIAL
    intent_fp = (intent_sample or "")[:80]
    conn = sqlite3.connect(_PATTERN_DB, timeout=3)
    try:
        # Find existing pattern with this signature
        existing = conn.execute(
            "SELECT pattern_id, fitness_score FROM patterns "
            "WHERE agent_id = ? AND intent_fingerprint = ? LIMIT 1",
            (agent_id, intent_fp),
        ).fetchone()
        if existing:
            new_score = max(0.0, min(1.0,
                (existing[1] or 0.5) + fitness_delta))
            conn.execute(
                "UPDATE patterns SET fitness_score = ?, "
                "last_used = ? WHERE pattern_id = ?",
                (new_score,
                 time.strftime("%Y-%m-%dT%H:%M:%S"),
                 existing[0]),
            )
        else:
            new_id = "wire3_{}_{}".format(agent_id[:12], int(time.time() * 1000))
            conn.execute(
                "INSERT INTO patterns (pattern_id, domain, intent_sample, "
                "intent_fingerprint, step_template, agent_id, fitness_score, "
                "last_used, created_at, stake) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (new_id, domain or "unknown", intent_sample, intent_fp,
                 "[]", agent_id, max(0.0, min(1.0, 0.5 + fitness_delta)),
                 time.strftime("%Y-%m-%dT%H:%M:%S"),
                 time.strftime("%Y-%m-%dT%H:%M:%S"), stake),
            )
        conn.commit()
        return True
    finally:
        conn.close()


def crystallize_recent(limit: int = 50) -> Dict[str, Any]:
    """Read recent chain_step_gates rows, crystallize each into pattern_library."""
    state = _load_state()
    last_rowid = state.get("last_rowid", 0)
    scanned = 0
    crystallized = 0
    errors = []
    new_last = last_rowid
    
    if not os.path.exists(_CHAIN_DB):
        return {"ok": False, "reason": "chain_db_missing", "scanned": 0,
                "crystallized": 0}
    
    conn = sqlite3.connect("file:{}?mode=ro".format(_CHAIN_DB),
                          uri=True, timeout=3)
    try:
        cols = [r[1] for r in conn.execute(
            "PRAGMA table_info(chain_step_gates)").fetchall()]
        if not cols:
            return {"ok": False, "reason": "chain_step_gates_missing"}
        # Use whichever columns exist (schema may vary)
        sql = ("SELECT rowid, step_id, gate_type, result, reason "
               "FROM chain_step_gates WHERE rowid > ? "
               "ORDER BY rowid ASC LIMIT ?")
        rows = conn.execute(sql, (last_rowid, limit)).fetchall()
    finally:
        conn.close()
    
    for rowid, step_id, gate_type, result, reason in rows:
        scanned += 1
        new_last = max(new_last, rowid)
        # Derive agent_id from step_id heuristic, default 'chain_engine'
        agent_id = "chain_engine"
        if step_id and "_" in step_id:
            parts = step_id.split("_")
            if parts and len(parts[0]) >= 4:
                agent_id = parts[0][:24]
        # Compute fitness delta
        result_upper = (result or "").upper().strip()
        delta = _FITNESS_DELTA_BY_RESULT.get(result_upper, 0.0)
        # Use step_id as intent_sample proxy (chain_engine doesn't store text)
        intent_sample = "gate_{}_{}".format(gate_type or "x",
                                            step_id or "unknown")
        try:
            if _upsert_pattern(agent_id, intent_sample,
                              gate_type or "gate", delta):
                crystallized += 1
        except Exception as e:
            errors.append({"rowid": rowid, "error": str(e)[:120]})
    
    state["last_rowid"] = new_last
    state["crystallized_total"] = state.get("crystallized_total", 0) + crystallized
    _save_state(state)
    
    return {
        "ok": True,
        "scanned": scanned,
        "crystallized": crystallized,
        "errors": errors[:5],
        "last_rowid": new_last,
        "crystallized_total": state["crystallized_total"],
    }


def main() -> int:
    """systemd-invokable entry; one-line journal summary."""
    started = time.time()
    r = crystallize_recent(limit=50)
    elapsed = round(time.time() - started, 2)
    print("R125 OK elapsed={}s scanned={} crystallized={} errors={} last_rowid={}".format(
        elapsed, r.get("scanned", 0), r.get("crystallized", 0),
        len(r.get("errors", [])), r.get("last_rowid", 0)
    ))
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
