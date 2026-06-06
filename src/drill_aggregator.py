"""
R64d — Drill aggregator

Pulls the 4 views (Timeline / Causality DAG / Agents / ROI) for a single
dispatch event keyed by signal_id (or correlation_id).

Reads, in order:
  - murphy_audit.db        rosetta_dispatch_log   (timeline + DAG)
  - rosetta_learning.db    agent_corrections, agent_success_map (agents)
  - roi_ledger.db          roi_entries            (ROI actual + projected)

Read-only. Composes with R64a/b/c — never writes.
"""
from __future__ import annotations
import sqlite3
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

AUDIT_DB    = "/var/lib/murphy-production/murphy_audit.db"
LEARNING_DB = "/var/lib/murphy-production/rosetta_learning.db"
ROI_DB      = "/var/lib/murphy-production/roi_ledger.db"


def _safe_conn(path: str) -> Optional[sqlite3.Connection]:
    try:
        c = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=2.0)
        c.row_factory = sqlite3.Row
        return c
    except Exception as e:
        logger.warning("drill_aggregator: cannot open %s: %s", path, e)
        return None


def _resolve_event(event_key: str) -> Optional[Dict[str, Any]]:
    """Find the dispatch row by signal_id or correlation_id."""
    c = _safe_conn(AUDIT_DB)
    if c is None:
        return None
    try:
        row = c.execute(
            "SELECT * FROM rosetta_dispatch_log "
            "WHERE signal_id=? OR correlation_id=? "
            "ORDER BY ts DESC LIMIT 1",
            (event_key, event_key),
        ).fetchone()
        return dict(row) if row else None
    finally:
        c.close()


def get_timeline(event_key: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Chronological events sharing this correlation_id (or signal_id)."""
    c = _safe_conn(AUDIT_DB)
    if c is None:
        return []
    try:
        rows = c.execute(
            "SELECT ts, agent_id, domain, intent_hint, verdict_decision, "
            "outcome_status, latency_ms "
            "FROM rosetta_dispatch_log "
            "WHERE signal_id=? OR correlation_id=? "
            "ORDER BY ts ASC LIMIT ?",
            (event_key, event_key, limit),
        ).fetchall()
        return [
            {
                "ts": r["ts"],
                "actor": r["agent_id"] or r["domain"] or "?",
                "event_type": r["verdict_decision"] or r["outcome_status"] or "dispatch",
                "summary": (r["intent_hint"] or "")[:140],
                "latency_ms": r["latency_ms"],
            }
            for r in rows
        ]
    finally:
        c.close()


def get_causality(event_key: str) -> Dict[str, Any]:
    """Nodes + edges keyed on correlation_id chain (limited graph)."""
    c = _safe_conn(AUDIT_DB)
    if c is None:
        return {"nodes": [], "edges": []}
    try:
        # All rows sharing the correlation_id (or signal_id) — sequential edges
        rows = c.execute(
            "SELECT id, ts, agent_id, domain, intent_hint, verdict_decision "
            "FROM rosetta_dispatch_log "
            "WHERE signal_id=? OR correlation_id=? "
            "ORDER BY ts ASC LIMIT 50",
            (event_key, event_key),
        ).fetchall()
        nodes = []
        edges = []
        prev_id = None
        for r in rows:
            nodes.append({
                "id":    str(r["id"]),
                "label": r["agent_id"] or r["domain"] or "?",
                "kind":  r["verdict_decision"] or "dispatch",
                "ts":    r["ts"],
            })
            if prev_id is not None:
                edges.append({
                    "from":   prev_id,
                    "to":     str(r["id"]),
                    "reason": (r["intent_hint"] or "next")[:60],
                })
            prev_id = str(r["id"])
        return {"nodes": nodes, "edges": edges}
    finally:
        c.close()


def get_agents(event_key: str) -> List[Dict[str, Any]]:
    """For each agent that touched this event, pull stats + last correction."""
    audit = _safe_conn(AUDIT_DB)
    if audit is None:
        return []
    try:
        agent_rows = audit.execute(
            "SELECT DISTINCT agent_id FROM rosetta_dispatch_log "
            "WHERE signal_id=? OR correlation_id=?",
            (event_key, event_key),
        ).fetchall()
        agent_ids = [r["agent_id"] for r in agent_rows if r["agent_id"]]
    finally:
        audit.close()

    if not agent_ids:
        return []

    learning = _safe_conn(LEARNING_DB)
    if learning is None:
        return [{"agent_type": a, "runs": 0, "success_rate": 0.0,
                 "last_correction": None} for a in agent_ids]
    try:
        out = []
        for a in agent_ids:
            a_key = (a or "").lower()
            sm = learning.execute(
                "SELECT total, success_rate, applied, rejected, revised "
                "FROM agent_success_map WHERE agent_type=?",
                (a_key,),
            ).fetchone()
            cx = learning.execute(
                "SELECT decision, reason, importance, decided_at "
                "FROM agent_corrections WHERE agent_type=? "
                "ORDER BY importance DESC, decided_at DESC LIMIT 1",
                (a_key,),
            ).fetchone()
            out.append({
                "agent_type":   a,
                "runs":         (sm["total"] if sm else 0),
                "success_rate": round((sm["success_rate"] or 0.0) * 100, 1) if sm else 0.0,
                "applied":      (sm["applied"]  if sm else 0),
                "rejected":     (sm["rejected"] if sm else 0),
                "revised":      (sm["revised"]  if sm else 0),
                "last_correction": (
                    {"decision": cx["decision"], "reason": cx["reason"],
                     "importance": cx["importance"], "at": cx["decided_at"]}
                    if cx else None
                ),
            })
        return out
    finally:
        learning.close()


def get_roi(event_key: str) -> Dict[str, Any]:
    """ROI projected vs actual. Uses workflow_id match or agent_id contribution."""
    audit = _safe_conn(AUDIT_DB)
    workflow_id = None
    agent_ids: List[str] = []
    if audit is not None:
        try:
            r = audit.execute(
                "SELECT correlation_id, agent_id FROM rosetta_dispatch_log "
                "WHERE signal_id=? OR correlation_id=? LIMIT 1",
                (event_key, event_key),
            ).fetchone()
            if r:
                workflow_id = r["correlation_id"] or event_key
            agent_ids = [
                row["agent_id"] for row in audit.execute(
                    "SELECT DISTINCT agent_id FROM rosetta_dispatch_log "
                    "WHERE signal_id=? OR correlation_id=?",
                    (event_key, event_key),
                ).fetchall() if row["agent_id"]
            ]
        finally:
            audit.close()

    roi = _safe_conn(ROI_DB)
    if roi is None:
        return {"projected": None, "actual": None, "delta_pct": None,
                "note": "roi_ledger unavailable"}
    try:
        # Actuals: any roi_entries tagged with our workflow_id OR our agents
        if workflow_id:
            actual_rows = roi.execute(
                "SELECT time_spent_s, money_value_usd FROM roi_entries "
                "WHERE workflow_id=?",
                (workflow_id,),
            ).fetchall()
        else:
            actual_rows = []
        actual_time = sum((r["time_spent_s"] or 0.0) for r in actual_rows)
        actual_money = sum((r["money_value_usd"] or 0.0) for r in actual_rows)

        # Projected: pulled from any matching roi_targets, else None
        proj_row = roi.execute(
            "SELECT target_time_s, target_value_usd FROM roi_targets "
            "WHERE id=? OR target_name=? LIMIT 1",
            (event_key, event_key),
        ).fetchone()
        if proj_row:
            projected = {
                "time_s": proj_row["target_time_s"],
                "money_usd": proj_row["target_value_usd"],
            }
        else:
            projected = None

        delta_pct = None
        if projected and projected.get("money_usd"):
            delta_pct = round(
                (actual_money - projected["money_usd"]) / projected["money_usd"] * 100, 1
            )

        return {
            "projected": projected,
            "actual": {"time_s": actual_time, "money_usd": actual_money,
                       "entry_count": len(actual_rows)},
            "delta_pct": delta_pct,
            "workflow_id": workflow_id,
            "note": None if actual_rows else "no actuals recorded yet",
        }
    finally:
        roi.close()


def aggregate(event_key: str) -> Dict[str, Any]:
    """Build the full 4-view payload. Returns None if event not found."""
    head = _resolve_event(event_key)
    if head is None:
        return None
    return {
        "ok": True,
        "event_id": event_key,
        "head": {
            "ts":          head.get("ts"),
            "agent_id":    head.get("agent_id"),
            "domain":      head.get("domain"),
            "tenant_id":   head.get("tenant_id"),
            "verdict":     head.get("verdict_decision"),
            "outcome":     head.get("outcome_status"),
            "intent_hint": head.get("intent_hint"),
        },
        "timeline":  get_timeline(event_key),
        "causality": get_causality(event_key),
        "agents":    get_agents(event_key),
        "roi":       get_roi(event_key),
        "redispatch": {
            "url": "/api/rosetta/dispatch",
            "payload_hint": {
                "prompt": head.get("intent_hint") or "",
                "tenant_id": head.get("tenant_id") or "",
            },
        },
    }
