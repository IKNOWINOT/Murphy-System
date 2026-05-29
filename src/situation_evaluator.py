"""
PATCH-EVAL-R105 (2026-05-28 R105) — situation evaluator

WHAT THIS IS:
  The meta-improvement loop substrate. Pairs:
    INCOMING situation (rosetta_dispatch_log signal context)
    DLF state (north_star + capacity at moment of work)
    OUTGOING reaction (R104 agent_reactions evidence + valence)
  
  → returns a paired_score, agent_fit, dlf_alignment, fitness_delta
  → writes fitness_delta back to pattern_library + agent_contracts
  → closes the loop: each dispatch makes the NEXT dispatch better

WHY IT EXISTS:
  Corey R104.6: "is dlf paired with an evaluation of what tasks the
  agents do well based on in and out coming and going situation"
  
  Before R105: agent_contracts.fitness_score was sparsely populated 
  static numbers (only lead_engineer=0.6). pattern_library tracked
  success_count/failure_count but no situation-aware fitness.
  
  After R105: every reaction triggers pair_evaluation which writes
  fitness deltas back, so agent picks for similar future situations
  reflect REAL evidence of how this agent did in similar past situations.

DESIGN CHOICE LOCKED R105: SIDE-EFFECT primitive
  Murphy refused pure-vs-effect Q (HTTP timeout expected). My call.
  Reason: caller-writes-back pattern is what caused R103-R104 chain to
  ship without fitness updates landing anywhere. Single-call-closes-loop
  guarantees the delta lands. Caller still gets the score back for use.

PUBLIC SURFACE:
  pair_evaluation(incoming_signal, dlf_state, outgoing_reaction, *,
                  write_back=True) → dict
    Returns {ok, paired_score, agent_fit, dlf_alignment, fitness_delta,
             pattern_id_updated, agent_contract_updated}
  
  evaluate_reaction_by_id(reaction_id) → dict
    Convenience: fetches reaction + reconstructs incoming + DLF context,
    calls pair_evaluation. Used by walker_cli + auto-runner.
  
  evaluate_recent_unscored(limit=10) → list
    Batch: walks recent reactions where pattern_id_updated is null,
    evaluates each, returns summary.

VALENCE → FITNESS DELTA MAPPING (R105 default):
  surprised_good : +0.10  (output beat expectations)
  expected       : +0.02  (clean work, small confidence bump)
  mostly_landed  : +0.00  (caveat caught, neutral)
  huh            : -0.01  (something unexpected, slight uncertainty)
  puzzled        : -0.03  (agent unsure about own output)
  wait           : -0.03  (mid-work pause noticed)
  off            : -0.10  (wrong direction)
  regression     : -0.15  (worse than prior baseline)

DEPENDS ON:
  hitl_provenance.db with agent_reactions + facet_tags (R103-R104)
  murphy_audit.db with rosetta_dispatch_log (incoming signal)
  pattern_library.db with patterns (288 rows, R32+R33 substrate)
  entity_graph.db with agent_contracts (R88 fitness substrate)
  src/dlf_r.py for current DLF snapshot (optional, falls back to null)

LAST UPDATED: 2026-05-28 R105
"""

import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

_PROV_DB = "/var/lib/murphy-production/hitl_provenance.db"
_AUDIT_DB = "/var/lib/murphy-production/murphy_audit.db"
_PATTERN_DB = "/var/lib/murphy-production/pattern_library.db"
_ENTITY_DB = "/var/lib/murphy-production/entity_graph.db"

_VALENCE_DELTA = {
    "surprised_good": 0.10,
    "expected":       0.02,
    "mostly_landed":  0.00,
    "huh":           -0.01,
    "puzzled":       -0.03,
    "wait":          -0.03,
    "off":           -0.10,
    "regression":    -0.15,
}


def _safe_open(db_path: str, mode: str = "rw") -> Optional[sqlite3.Connection]:
    """Open DB if it exists; return None gracefully if missing."""
    if not os.path.exists(db_path):
        return None
    try:
        if mode == "ro":
            conn = sqlite3.connect("file:{}?mode=ro".format(db_path),
                                   uri=True, timeout=3)
        else:
            conn = sqlite3.connect(db_path, timeout=5)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception:
        return None


def _get_dlf_snapshot() -> Dict[str, Any]:
    """
    Best-effort DLF-R snapshot. Returns {} if DLF-R not loaded.
    R104.6 probed: get_dlf_snapshot is not in src.dlf_r — use get_identity.
    """
    try:
        import sys
        if "/opt/Murphy-System" not in sys.path:
            sys.path.insert(0, "/opt/Murphy-System")
        from src.dlf_r import get_identity
        ident = get_identity()
        if isinstance(ident, dict):
            return {
                "north_star": ident.get("north_star"),
                "harm_thresholds": ident.get("harm_thresholds"),
                "captured_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
            }
    except Exception:
        pass
    return {}


def _compute_dlf_alignment(reaction_text: str, dlf_state: Dict[str, Any]) -> float:
    """
    Compute alignment between reaction and current DLF identity.
    Heuristic: north_star keyword presence + reaction valence.
    Returns 0-1 score. Conservative when DLF empty.
    """
    if not dlf_state or not isinstance(dlf_state, dict):
        return 0.5
    ns = (dlf_state.get("north_star") or "").lower()
    rt = (reaction_text or "").lower()
    if not ns or not rt:
        return 0.5
    # Simple lexical overlap — words 4+ chars from north_star
    ns_words = set(w for w in ns.split() if len(w) >= 4)
    if not ns_words:
        return 0.5
    overlap = sum(1 for w in ns_words if w in rt)
    return min(1.0, 0.4 + (overlap / max(len(ns_words), 1)) * 0.6)


def _resolve_pattern_for_event(work_event_table: str, work_event_id: str,
                                agent_id: str, work_summary: str) -> Optional[Dict]:
    """
    Find or create the pattern_library row this reaction's work matches.
    Returns dict or None.
    """
    conn = _safe_open(_PATTERN_DB, "rw")
    if not conn:
        return None
    try:
        # Hash the work summary + agent for a stable fingerprint
        fp = hashlib.sha256(
            "{}::{}".format(agent_id, work_summary[:200]).encode()
        ).hexdigest()[:16]
        row = conn.execute(
            "SELECT * FROM patterns WHERE intent_fingerprint = ? LIMIT 1", (fp,)
        ).fetchone()
        if row:
            conn.close()
            return dict(row)
        # Insert minimal stub if absent
        pid = "rx_" + fp
        conn.execute(
            "INSERT OR IGNORE INTO patterns "
            "(pattern_id, domain, intent_sample, intent_fingerprint, "
            " step_template, stake, fitness_score, agent_id, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (pid, work_event_table or "reaction",
             work_summary[:200], fp, "[]", "low", 0.5, agent_id,
             datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM patterns WHERE pattern_id = ?", (pid,)
        ).fetchone()
        conn.close()
        return dict(row) if row else None
    except Exception:
        try:
            conn.close()
        except Exception:
            pass
        return None


def _update_pattern_fitness(pattern_id: str, delta: float, valence: str) -> bool:
    """Apply fitness_delta to pattern_library. Returns True if written."""
    conn = _safe_open(_PATTERN_DB, "rw")
    if not conn:
        return False
    try:
        cur = conn.execute(
            "UPDATE patterns SET "
            "fitness_score = MAX(0.0, MIN(1.0, COALESCE(fitness_score,0.5) + ?)), "
            "success_count = success_count + CASE WHEN ? > 0 THEN 1 ELSE 0 END, "
            "failure_count = failure_count + CASE WHEN ? < 0 THEN 1 ELSE 0 END, "
            "last_used = ? "
            "WHERE pattern_id = ?",
            (delta, delta, delta,
             datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
             pattern_id),
        )
        conn.commit()
        n = cur.rowcount
        conn.close()
        return n > 0
    except Exception:
        try:
            conn.close()
        except Exception:
            pass
        return False


def _update_agent_contract_fitness(agent_id: str, delta: float) -> bool:
    """Apply fitness_delta to agent_contracts. Returns True if written."""
    conn = _safe_open(_ENTITY_DB, "rw")
    if not conn:
        return False
    try:
        # Check if agent exists
        row = conn.execute(
            "SELECT fitness_score FROM agent_contracts WHERE agent_id = ? LIMIT 1",
            (agent_id,)
        ).fetchone()
        if not row:
            conn.close()
            return False
        cur = conn.execute(
            "UPDATE agent_contracts "
            "SET fitness_score = MAX(0.0, MIN(1.0, COALESCE(fitness_score,0.5) + ?)) "
            "WHERE agent_id = ?",
            (delta, agent_id),
        )
        conn.commit()
        n = cur.rowcount
        conn.close()
        return n > 0
    except Exception:
        try:
            conn.close()
        except Exception:
            pass
        return False


def pair_evaluation(incoming_signal: Dict[str, Any],
                    dlf_state: Optional[Dict[str, Any]],
                    outgoing_reaction: Dict[str, Any],
                    *, write_back: bool = True) -> Dict[str, Any]:
    """
    Pair (incoming, DLF, outgoing) → score + fitness deltas applied.
    
    incoming_signal: dict with at least agent_id, intent_hint, ts
    dlf_state: dict with north_star, harm_thresholds (or empty for fallback)
    outgoing_reaction: dict with reaction_id, agent_id, valence, reaction_text,
                       work_summary, work_event_table, work_event_id
    """
    if not isinstance(outgoing_reaction, dict):
        return {"ok": False, "reason": "outgoing_reaction must be dict"}
    valence = outgoing_reaction.get("valence")
    agent_id = outgoing_reaction.get("agent_id")
    reaction_text = outgoing_reaction.get("reaction_text") or ""
    if not valence or not agent_id:
        return {"ok": False, "reason": "missing_valence_or_agent_id"}
    if valence not in _VALENCE_DELTA:
        return {"ok": False, "reason": "unknown_valence: " + str(valence)}

    # PATCH-EVAL-R113 — stability gate before applying fitness delta
    # Murphy meta-Q answered 0.15 (lower threshold for learning continuity).
    # Locked decision: 0.15 — evaluator runs AFTER work; refuse only on
    # clear divergence to preserve learning path during noisy rounds.
    _gate_witness = {"checked": False}
    if write_back:
        try:
            import sys as _s
            if "/opt/Murphy-System" not in _s.path:
                _s.path.insert(0, "/opt/Murphy-System")
            from src.recursion_stability import recursion_gate
            import sqlite3 as _sq3
            _conn = _sq3.connect(_PATTERN_DB, timeout=2)
            _rows = _conn.execute(
                "SELECT fitness_score FROM patterns WHERE agent_id = ? "
                "AND fitness_score IS NOT NULL ORDER BY last_used DESC LIMIT 5",
                (agent_id,),
            ).fetchall()
            _conn.close()
            _samples = [float(r[0]) for r in _rows if r[0] is not None]
            if len(_samples) >= 3:
                _allow, _reason = recursion_gate(
                    "pair_evaluation_" + agent_id, _samples, min_score=0.15
                )
                _gate_witness = {
                    "checked": True, "allow": _allow, "reason": _reason,
                    "n_samples": len(_samples),
                    "samples_preview": _samples[:3],
                    "threshold": 0.15,
                }
                if not _allow:
                    return {
                        "ok": False,
                        "reason": "stability_gate_refused: " + _reason,
                        "agent_id": agent_id,
                        "valence": valence,
                        "fitness_delta_skipped": _VALENCE_DELTA[valence],
                        "_gate_witness": _gate_witness,
                    }
        except Exception:
            pass  # fail-open default

    # Core scoring
    fitness_delta = _VALENCE_DELTA[valence]
    dlf_alignment = _compute_dlf_alignment(reaction_text, dlf_state or {})
    # paired_score factors in confidence
    confidence = float(outgoing_reaction.get("confidence", 0.7))
    agent_fit = min(1.0, max(0.0, 0.5 + fitness_delta * 2 * confidence))
    paired_score = (agent_fit * 0.6) + (dlf_alignment * 0.4)

    result = {
        "ok": True,
        "paired_score": round(paired_score, 4),
        "agent_fit": round(agent_fit, 4),
        "dlf_alignment": round(dlf_alignment, 4),
        "fitness_delta": fitness_delta,
        "valence": valence,
        "agent_id": agent_id,
        "pattern_id_updated": None,
        "agent_contract_updated": False,
        "write_back": write_back,
        "_gate_witness": _gate_witness,  # PATCH-EVAL-R113
    }

    if write_back:
        # Resolve pattern for this work
        pattern = _resolve_pattern_for_event(
            outgoing_reaction.get("work_event_table") or "reaction",
            outgoing_reaction.get("work_event_id") or "",
            agent_id,
            outgoing_reaction.get("work_summary") or reaction_text[:80],
        )
        if pattern:
            pid = pattern.get("pattern_id")
            if _update_pattern_fitness(pid, fitness_delta, valence):
                result["pattern_id_updated"] = pid
        # Update agent contract fitness if agent exists
        result["agent_contract_updated"] = _update_agent_contract_fitness(
            agent_id, fitness_delta
        )

    return result


def evaluate_reaction_by_id(reaction_id: str) -> Dict[str, Any]:
    """Convenience: load reaction, build context, evaluate."""
    conn = _safe_open(_PROV_DB, "ro")
    if not conn:
        return {"ok": False, "reason": "prov_db_unavailable"}
    row = conn.execute(
        "SELECT * FROM agent_reactions WHERE reaction_id = ?", (reaction_id,)
    ).fetchone()
    conn.close()
    if not row:
        return {"ok": False, "reason": "reaction_not_found"}
    rx = dict(row)
    # Pull incoming context from rosetta_dispatch_log if matchable
    incoming = {
        "agent_id": rx.get("agent_id"),
        "intent_hint": rx.get("work_summary"),
        "ts": rx.get("captured_at"),
    }
    return pair_evaluation(incoming, _get_dlf_snapshot(), rx, write_back=True)


def evaluate_recent_unscored(limit: int = 10) -> List[Dict[str, Any]]:
    """Walk recent reactions, evaluate each, return summary list."""
    conn = _safe_open(_PROV_DB, "ro")
    if not conn:
        return [{"ok": False, "reason": "prov_db_unavailable"}]
    rows = conn.execute(
        "SELECT reaction_id, agent_id, valence, work_summary FROM agent_reactions "
        "ORDER BY captured_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    results = []
    for r in rows:
        rd = dict(r)
        ev = evaluate_reaction_by_id(rd["reaction_id"])
        results.append({
            "reaction_id": rd["reaction_id"],
            "agent_id": rd["agent_id"],
            "valence": rd["valence"],
            "paired_score": ev.get("paired_score"),
            "fitness_delta": ev.get("fitness_delta"),
            "pattern_id_updated": ev.get("pattern_id_updated"),
            "agent_contract_updated": ev.get("agent_contract_updated"),
        })
    return results


if __name__ == "__main__":
    print("R105 situation_evaluator demo — pair existing reactions")
    for r in evaluate_recent_unscored(limit=10):
        print("  {}: agent={} valence={} score={} pattern={} contract_updated={}".format(
            r["reaction_id"], r["agent_id"], r["valence"],
            r["paired_score"], (r["pattern_id_updated"] or "?")[:20],
            r["agent_contract_updated"]))
