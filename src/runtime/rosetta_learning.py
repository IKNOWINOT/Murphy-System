"""
R64a — Rosetta Learning Store
=============================
Single canonical store for "what each agent type knows from past HITL feedback."

DB: /var/lib/murphy-production/rosetta_learning.db
Tables: agent_success_map, agent_corrections, agent_distilled_lessons

This module is the ONLY place anything writes to or reads from rosetta_learning.db.
All other code (HITL /decide endpoints, persona injection, OS UI) calls these
functions. One truth, no drift.

Canon: SD-73 (120s timeouts), Founder lock 2026-06-06 Q1=C Q2=C Q3=A Q4=B Q5=this.
"""
from __future__ import annotations
import sqlite3
import json
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any
from pathlib import Path

DB_PATH = Path("/var/lib/murphy-production/rosetta_learning.db")

# ─── kind → agent_type map (Q-b = A) ──────────────────────────────────────
# Maps HITL item `kind` field to the canonical agent_type that proposed it.
# Extend this as new HITL kinds appear.
KIND_TO_AGENT_TYPE: Dict[str, str] = {
    "form_intake":       "form_intake_agent",
    "outbound_email":    "executor",
    "outbound_message":  "executor",
    "prospect_email":    "vp-sales",
    "sales_outreach":    "vp-sales",
    "deployment-review": "cto",
    "qc":                "auditor",
    "acceptance":        "exec_admin",
    "dag_blocked":       None,  # carries its own blocked_node_name; caller resolves
}

def derive_agent_type(kind: Optional[str], fallback: Optional[str] = None) -> str:
    """Map a HITL item's kind → agent_type. Falls back to `fallback` or 'unknown'."""
    if not kind:
        return fallback or "unknown"
    return KIND_TO_AGENT_TYPE.get(kind, fallback or "unknown")


# ─── Connection helper ────────────────────────────────────────────────────
def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(str(DB_PATH), timeout=30.0)  # ≥30s curl-side, SD-73 spirit
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    return c


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─── READS ────────────────────────────────────────────────────────────────
def get_agent_success_map(agent_type: str) -> Optional[Dict[str, Any]]:
    """Return the success_map row for an agent_type, or None if missing."""
    with _conn() as c:
        row = c.execute(
            "SELECT * FROM agent_success_map WHERE agent_type=?",
            (agent_type,),
        ).fetchone()
    return dict(row) if row else None


def list_all_agent_success_maps() -> List[Dict[str, Any]]:
    """Return all agent rows, ordered by fail_rate desc then total desc."""
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM agent_success_map ORDER BY fail_rate DESC, total DESC, agent_type"
        ).fetchall()
    return [dict(r) for r in rows]


def get_top_corrections(agent_type: str, limit: int = 10,
                        only_undistilled: bool = False) -> List[Dict[str, Any]]:
    """Top-N corrections by importance for an agent, for persona injection (R64c)."""
    q = "SELECT * FROM agent_corrections WHERE agent_type=?"
    args: List[Any] = [agent_type]
    if only_undistilled:
        q += " AND distilled=0"
    q += " ORDER BY importance DESC, decided_at DESC LIMIT ?"
    args.append(limit)
    with _conn() as c:
        rows = c.execute(q, args).fetchall()
    return [dict(r) for r in rows]


def get_distilled_lessons(agent_type: str, limit: int = 5) -> List[Dict[str, Any]]:
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM agent_distilled_lessons WHERE agent_type=? "
            "ORDER BY importance DESC, created_at DESC LIMIT ?",
            (agent_type, limit),
        ).fetchall()
    return [dict(r) for r in rows]


# ─── WRITES ───────────────────────────────────────────────────────────────
def record_decision(
    agent_type: str,
    decision: str,                  # 'approved' | 'rejected' | 'revised' | 'regenerated'
    hitl_item_id: Optional[str] = None,
    source_kind: Optional[str] = None,
    reason: Optional[str] = None,
    diff_json: Optional[str] = None,
    importance: float = 0.5,
    stake: Optional[str] = None,
    decided_by: Optional[str] = None,
) -> str:
    """
    Single write path for all HITL decisions. Hooked from all three /decide
    endpoints in app.py. Atomically:
      1. Insert agent_corrections row
      2. Increment counters on agent_success_map
      3. Recompute fail_rate / success_rate
    Returns the new correction_id.
    """
    decision = decision.lower().strip()
    if decision not in {"approved", "rejected", "revised", "regenerated"}:
        raise ValueError(f"Unknown decision verb: {decision}")
    if not agent_type:
        agent_type = "unknown"

    correction_id = uuid.uuid4().hex
    now = _now_iso()

    # Map decision verb → counter column
    counter_col = {
        "approved":    "applied",
        "rejected":    "rejected",
        "revised":     "revised",
        "regenerated": "revised",   # treat regen as revision for the map
    }[decision]

    with _conn() as c:
        # 1. detail row
        c.execute(
            """INSERT INTO agent_corrections
               (correction_id, agent_type, hitl_item_id, source_kind,
                decision, reason, diff_json, importance, stake,
                decided_by, decided_at, distilled)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,0)""",
            (correction_id, agent_type, hitl_item_id, source_kind,
             decision, reason, diff_json, importance, stake,
             decided_by, now),
        )
        # 2. upsert success_map + increment counter atomically
        c.execute(
            "INSERT OR IGNORE INTO agent_success_map (agent_type, updated_at) VALUES (?,?)",
            (agent_type, now),
        )
        c.execute(
            f"""UPDATE agent_success_map
                SET total            = total + 1,
                    {counter_col}    = {counter_col} + 1,
                    last_decision_at = ?,
                    updated_at       = ?
                WHERE agent_type = ?""",
            (now, now, agent_type),
        )
        # 3. recompute rates
        row = c.execute(
            "SELECT total, applied, rejected, revised FROM agent_success_map WHERE agent_type=?",
            (agent_type,),
        ).fetchone()
        if row and row["total"] > 0:
            fr = (row["rejected"] + row["revised"]) / row["total"]
            sr = row["applied"] / row["total"]
            c.execute(
                "UPDATE agent_success_map SET fail_rate=?, success_rate=? WHERE agent_type=?",
                (fr, sr, agent_type),
            )
        c.commit()

    return correction_id


def write_distilled_lesson(agent_type: str, lesson_text: str,
                           source_correction_ids: List[str],
                           importance: float = 0.7) -> str:
    """Background distill job writes here. Marks sources distilled=1."""
    lesson_id = uuid.uuid4().hex
    now = _now_iso()
    with _conn() as c:
        c.execute(
            "INSERT INTO agent_distilled_lessons "
            "(lesson_id, agent_type, lesson_text, source_corrections_json, importance, created_at) "
            "VALUES (?,?,?,?,?,?)",
            (lesson_id, agent_type, lesson_text,
             json.dumps(source_correction_ids), importance, now),
        )
        # Mark sources distilled
        if source_correction_ids:
            qmarks = ",".join("?" * len(source_correction_ids))
            c.execute(
                f"UPDATE agent_corrections SET distilled=1, distilled_into=? "
                f"WHERE correction_id IN ({qmarks})",
                [lesson_id, *source_correction_ids],
            )
        c.commit()
    return lesson_id


# ─── ROI ACTUALS (R64a part 2) ────────────────────────────────────────────
ROI_DB = Path("/var/lib/murphy-production/roi_calendar.db")

def capture_roi_actuals(event_id: str, actuals: Dict[str, float]) -> bool:
    """
    Merge actuals into an existing roi_events JSON blob.
    `actuals` keys: human_cost_actual, human_time_actual_hours,
                    agent_compute_cost_actual, roi_actual.
    Only writes keys present in `actuals`.
    Returns True on success, False if event not found.
    """
    if not ROI_DB.exists():
        return False
    with sqlite3.connect(str(ROI_DB), timeout=30.0) as c:
        row = c.execute(
            "SELECT data FROM roi_events WHERE event_id=?", (event_id,)
        ).fetchone()
        if not row:
            return False
        try:
            blob = json.loads(row[0])
        except Exception:
            return False
        # Only allow the 4 documented actual keys
        allowed = {
            "human_cost_actual", "human_time_actual_hours",
            "agent_compute_cost_actual", "roi_actual",
        }
        for k, v in actuals.items():
            if k in allowed:
                blob[k] = v
        blob["actuals_captured_at"] = _now_iso()
        c.execute(
            "UPDATE roi_events SET data=?, updated_at=? WHERE event_id=?",
            (json.dumps(blob), _now_iso(), event_id),
        )
        c.commit()
    return True


# ─── HEALTH ───────────────────────────────────────────────────────────────
def health() -> Dict[str, Any]:
    """Quick self-check for the /api/rosetta-learning/health endpoint."""
    out: Dict[str, Any] = {"db_path": str(DB_PATH), "ok": False}
    try:
        with _conn() as c:
            out["agents_seeded"] = c.execute(
                "SELECT COUNT(*) FROM agent_success_map"
            ).fetchone()[0]
            out["corrections_total"] = c.execute(
                "SELECT COUNT(*) FROM agent_corrections"
            ).fetchone()[0]
            out["lessons_total"] = c.execute(
                "SELECT COUNT(*) FROM agent_distilled_lessons"
            ).fetchone()[0]
            out["agents_with_data"] = c.execute(
                "SELECT COUNT(*) FROM agent_success_map WHERE total > 0"
            ).fetchone()[0]
        out["ok"] = True
    except Exception as e:
        out["error"] = str(e)
    return out
