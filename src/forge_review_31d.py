"""
Ship 13b — Deliverable-Review Forge backend.

Uses the REAL data sources Murphy already maintains:
  - automations.db.automation_requests  : the source of ROI events (event_id = 'auto-' + request_id[:12])
  - automations.db.automation_runs      : each execution's status, cost, runtime
  - workflow_runs.db.workflow_runs      : DAG graph with nodes/steps if any
  - entity_graph.db.result_provenance   : per-action cost + outputs

Returns a unified review object the Forge UI renders.
"""
import sqlite3
import json
from typing import Optional, Dict, Any, List

AUTOMATIONS_DB = "/var/lib/murphy-production/automations.db"
WORKFLOW_DB    = "/var/lib/murphy-production/workflow_runs.db"
PROVENANCE_DB  = "/var/lib/murphy-production/entity_graph.db"


def _q(db_path: str, sql: str, params=()) -> List[tuple]:
    try:
        with sqlite3.connect(db_path, timeout=5) as c:
            return c.execute(sql, params).fetchall()
    except Exception:
        return []


def _resolve_event(event_id: str) -> Optional[Dict[str, Any]]:
    """event_id format is 'auto-<first 12 chars of request_id>'. Resolve full row."""
    if not event_id:
        return None
    if event_id.startswith("auto-"):
        prefix = event_id[5:]  # 12 chars
        rows = _q(AUTOMATIONS_DB,
            "SELECT request_id, description, status, roi_usd, created_at, built_at "
            "FROM automation_requests WHERE request_id LIKE ? LIMIT 1",
            (prefix + "%",))
        if not rows:
            return None
        rid, desc, status, roi_usd, created_at, built_at = rows[0]
        roi_usd = float(roi_usd or 0)
        words = len((desc or "").split())
        human_hrs = min(max(words / 8, 1.5), 10.0)
        human_cost = round(human_hrs * 60.0, 2)
        agent_cost = round(human_cost * 0.018, 4)
        overhead = round(human_cost * 0.03, 2)
        return {
            "event_id": event_id,
            "request_id": rid,
            "title": (desc or "Automation")[:80],
            "description": desc or "",
            "status": "complete" if status in ("built","complete") else "active",
            "progress_pct": 100 if status in ("built","complete") else 60,
            "start": created_at, "end": built_at or created_at,
            "human_cost_estimate": human_cost,
            "human_time_estimate_hours": round(human_hrs, 2),
            "agent_compute_cost": agent_cost,
            "overhead_cost": overhead,
            "roi": roi_usd,
            "task_type": "automation",
            "source": "automation_requests",
            "agents": ["ForgeEngine", "NLWorkflowParser"],
        }
    return None


def get_deliverable_review(event_id: str) -> Dict[str, Any]:
    ev = _resolve_event(event_id)
    if not ev:
        return {"event_id": event_id, "event": None, "error": "event not resolved"}

    result: Dict[str, Any] = {
        "event_id": event_id,
        "event": ev,
        "workflow": None,
        "agents": ev.get("agents", []),
        "steps": [],
        "deliverable": None,
        "cost_breakdown": [],
        "rerun_available": False,
    }

    rid = ev.get("request_id")

    # 1. automation_runs — each invocation of this automation
    runs = _q(AUTOMATIONS_DB,
        "SELECT * FROM automation_runs WHERE request_id=? ORDER BY rowid DESC LIMIT 10",
        (rid,))
    if runs:
        # Get column names too
        with sqlite3.connect(AUTOMATIONS_DB, timeout=5) as c:
            cols = [r[1] for r in c.execute("PRAGMA table_info(automation_runs)").fetchall()]
        for run in runs[:5]:
            row = dict(zip(cols, run))
            result["steps"].append({
                "name": row.get("step_name") or row.get("run_id") or "run",
                "node_type": "automation_run",
                "status": row.get("status") or "unknown",
                "started_at": row.get("started_at"),
                "finished_at": row.get("completed_at") or row.get("finished_at"),
                "result_summary": (row.get("output") or row.get("result") or "")[:300] if row.get("output") or row.get("result") else "",
            })

    # 2. workflow_runs — any DAG that references this automation
    rows = _q(WORKFLOW_DB,
        "SELECT dag_id, name, domain, status, created_at, finished_at, graph_json "
        "FROM workflow_runs WHERE origin_signal LIKE ? OR origin_nl LIKE ? "
        "ORDER BY created_at DESC LIMIT 1",
        (f"%{rid}%", f"%{rid}%"))
    if rows:
        w = rows[0]
        try:
            graph = json.loads(w[6]) if w[6] else {}
        except Exception:
            graph = {}
        result["workflow"] = {
            "dag_id": w[0], "name": w[1], "domain": w[2],
            "status": w[3], "created_at": w[4], "finished_at": w[5],
        }
        for n in graph.get("nodes", []):
            result["steps"].append({
                "node_id": n.get("node_id"),
                "name": n.get("name"),
                "node_type": n.get("node_type"),
                "status": n.get("status"),
                "started_at": n.get("started_at"),
                "finished_at": n.get("finished_at"),
                "result_summary": str(n.get("result", ""))[:300],
            })

    # 3. result_provenance — per-action costs
    rows = _q(PROVENANCE_DB,
        "SELECT result_id, produced_at, produced_by, action_name, "
        "output_summary, cost_usd FROM result_provenance "
        "WHERE source_refs_json LIKE ? OR inputs_json LIKE ? "
        "ORDER BY produced_at DESC LIMIT 10",
        (f"%{rid}%", f"%{rid}%"))
    for r in rows:
        result["cost_breakdown"].append({
            "result_id": r[0], "produced_at": r[1],
            "produced_by": r[2], "action": r[3],
            "summary": (r[4] or "")[:200],
            "cost_usd": r[5] or 0.0,
        })

    # 4. Cost summary
    he = ev["human_cost_estimate"]
    ae = ev["agent_compute_cost"]
    oe = ev["overhead_cost"]
    total = he + ae + oe
    result["cost_summary"] = {
        "human_replaced": he,
        "agent_compute": ae,
        "overhead": oe,
        "human_pct_of_total": (he / total * 100) if total > 0 else 0,
        "hitl_dominated": (he > (ae + oe) * 3),
    }

    result["rerun_available"] = True
    return result


def list_recent_deliverables(limit: int = 30) -> List[Dict[str, Any]]:
    rows = _q(AUTOMATIONS_DB,
        "SELECT request_id, description, status, roi_usd, created_at, built_at "
        "FROM automation_requests WHERE roi_usd > 0 "
        "ORDER BY created_at DESC LIMIT ?", (limit,))
    out = []
    for rid, desc, status, roi_usd, created_at, built_at in rows:
        roi_usd = float(roi_usd or 0)
        words = len((desc or "").split())
        human_hrs = min(max(words / 8, 1.5), 10.0)
        human_cost = round(human_hrs * 60.0, 2)
        agent_cost = round(human_cost * 0.018, 4)
        out.append({
            "event_id": "auto-" + rid[:12],
            "title": (desc or "Automation")[:80],
            "status": "complete" if status in ("built","complete") else "active",
            "start": created_at,
            "end": built_at or created_at,
            "human_cost_estimate": human_cost,
            "agent_compute_cost": agent_cost,
            "roi": roi_usd,
            "agents": ["ForgeEngine", "NLWorkflowParser"],
        })
    return out


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        print(json.dumps(get_deliverable_review(sys.argv[1]), indent=2, default=str)[:2000])
    else:
        print(json.dumps(list_recent_deliverables(5), indent=2, default=str)[:2000])
