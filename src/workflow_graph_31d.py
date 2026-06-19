"""
Ship 14 (2026-06-18) — Workflow graph synthesis.

Returns a normalized graph (nodes + edges + timings) for ANY ROI event,
regardless of whether it has a real DAG or just an automation_request.

Per canon: scheduled automations get a 3-node synthesized graph
(trigger → action → output), HITL inserted if review-implied.
Real workflow_runs DAGs pass through as-is.
"""
import sqlite3
import json
import re
from typing import Dict, Any, List, Optional

AUTOMATIONS_DB = "/var/lib/murphy-production/automations.db"
WORKFLOW_DB    = "/var/lib/murphy-production/workflow_runs.db"
PROVENANCE_DB  = "/var/lib/murphy-production/entity_graph.db"
HITL_DB        = "/var/lib/murphy-production/hitl_queue.db"

_HITL_VERBS    = {"draft","review","compose","write","compile","approve",
                  "decide","assess","evaluate","critique","analyze","check"}
_AGENT_VERBS   = {"send","email","slack","post","generate","summarize","fetch",
                  "scrape","scan","extract","collect","monitor","watch","detect",
                  "calculate","compute","query","search","build","create","make"}


def _q(db_path: str, sql: str, params=()) -> List[tuple]:
    try:
        with sqlite3.connect(db_path, timeout=5) as c:
            return c.execute(sql, params).fetchall()
    except Exception:
        return []


def _classify_verb(text: str) -> str:
    """Return 'hitl' | 'agent' | 'output' based on description verbs."""
    blob = text.lower()
    for v in _HITL_VERBS:
        if v in blob:
            return "hitl"
    for v in _AGENT_VERBS:
        if v in blob:
            return "agent"
    return "agent"


def _extract_trigger(desc: str) -> str:
    """Extract schedule rule from description."""
    d = desc.lower()
    m = re.search(r"every\s+(morning|day|weekday|weekend|monday|tuesday|"
                  r"wednesday|thursday|friday|saturday|sunday|hour|"
                  r"month|week)", d)
    if m:
        time_match = re.search(r"at\s+(\d{1,2}\s*(am|pm)|\d{1,2}:\d{2})", d)
        when = f" {time_match.group(1).strip()}" if time_match else ""
        return f"every {m.group(1)}{when}"
    m = re.search(r"(when|if|on)\s+([a-z\s]{3,30})", d)
    if m:
        return f"{m.group(1)} {m.group(2).strip()[:25]}"
    return "on schedule"


def _extract_action(desc: str) -> str:
    """Extract the verb phrase."""
    d = desc.lower()
    for v in sorted(_AGENT_VERBS | _HITL_VERBS, key=len, reverse=True):
        if v in d:
            # grab a few words around it
            i = d.index(v)
            chunk = d[i:i+40].split(",")[0].split(".")[0]
            return chunk.strip()[:35]
    return "execute"


def _extract_output(desc: str) -> str:
    """Extract the noun/object being produced."""
    d = desc.lower()
    nouns = ["slack message", "email", "report", "summary", "invoice",
             "document", "notification", "alert", "snapshot", "digest",
             "post", "update", "file", "drawing"]
    for n in nouns:
        if n in d:
            return n
    return "result"


def _build_synthesized_graph(req_row: Dict[str, Any]) -> Dict[str, Any]:
    """3- or 4-node graph derived from automation_request fields.

    Sizes (time): use human_cost_estimate / human_time_estimate split across
    nodes proportionally. Agent nodes shrink to ~2% of human estimate.
    HITL nodes default to ~10% of human time (real review time).
    """
    desc = req_row.get("description", "")
    human_hrs = req_row.get("human_time_estimate_hours", 1.5)
    human_cost = req_row.get("human_cost_estimate", 90.0)
    agent_cost = req_row.get("agent_compute_cost", 1.62)
    has_hitl = _classify_verb(desc) == "hitl"
    is_complete = req_row.get("status") == "complete"

    trigger_label = _extract_trigger(desc)
    action_label = _extract_action(desc)
    output_label = _extract_output(desc)

    nodes = []
    # 1. Trigger
    nodes.append({
        "id": "trigger",
        "label": trigger_label,
        "kind": "trigger",
        "estimated_minutes": 0.1,
        "actual_minutes": 0.1,
        "status": "complete" if is_complete else "active",
    })
    # 2. Agent action
    agent_minutes_est = human_hrs * 60 * 0.6  # human would take 60% of total
    agent_minutes_actual = max(0.5, agent_minutes_est * 0.02)  # Murphy ~2% of human
    nodes.append({
        "id": "action",
        "label": action_label,
        "kind": "agent",
        "estimated_minutes": round(agent_minutes_est, 1),
        "actual_minutes": round(agent_minutes_actual, 2) if is_complete else None,
        "status": "complete" if is_complete else "active",
        "cost_usd": agent_cost,
    })
    # 3. HITL review (inserted only if description implies review)
    if has_hitl:
        hitl_minutes = human_hrs * 60 * 0.3
        nodes.append({
            "id": "hitl",
            "label": "human review",
            "kind": "hitl",
            "estimated_minutes": round(hitl_minutes, 1),
            "actual_minutes": round(hitl_minutes, 1) if is_complete else None,
            "status": "complete" if is_complete else "pending",
            "cost_usd": round(hitl_minutes * (human_cost / (human_hrs * 60)), 2),
        })
    # 4. Output
    nodes.append({
        "id": "output",
        "label": output_label,
        "kind": "output",
        "estimated_minutes": 0.5,
        "actual_minutes": 0.5 if is_complete else None,
        "status": "complete" if is_complete else "queued",
    })

    edges = []
    for i in range(len(nodes) - 1):
        edges.append({"from": nodes[i]["id"], "to": nodes[i+1]["id"]})

    return {
        "synthesized": True,
        "nodes": nodes,
        "edges": edges,
        "total_estimated_minutes": sum(n.get("estimated_minutes") or 0 for n in nodes),
        "total_actual_minutes": sum(n.get("actual_minutes") or 0 for n in nodes),
    }


def _build_real_graph(graph_json: str, ev: Dict[str, Any]) -> Dict[str, Any]:
    """When workflow_runs.graph_json exists, normalize it to our format."""
    try:
        g = json.loads(graph_json)
    except Exception:
        return _build_synthesized_graph(ev)

    nodes_out = []
    for n in g.get("nodes", []):
        kind = "agent"
        if n.get("node_type") in ("trigger", "schedule"):
            kind = "trigger"
        elif n.get("node_type") in ("hitl", "review", "approval"):
            kind = "hitl"
        elif n.get("node_type") in ("output", "deliverable", "sink"):
            kind = "output"
        # Time: derive from started_at/finished_at if both present
        actual = None
        try:
            from datetime import datetime
            sa = n.get("started_at"); fa = n.get("finished_at")
            if sa and fa:
                actual = round((datetime.fromisoformat(fa.replace("Z","+00:00")) -
                                datetime.fromisoformat(sa.replace("Z","+00:00"))).total_seconds() / 60.0, 2)
        except Exception:
            pass
        nodes_out.append({
            "id": n.get("node_id") or n.get("name") or "node",
            "label": (n.get("name") or n.get("node_id") or "node")[:35],
            "kind": kind,
            "estimated_minutes": 1.0,  # without explicit estimate, use placeholder
            "actual_minutes": actual,
            "status": n.get("status", "unknown"),
        })
    edges = []
    for n in g.get("nodes", []):
        for dep in n.get("depends_on", []):
            edges.append({"from": dep, "to": n.get("node_id")})
    return {
        "synthesized": False,
        "nodes": nodes_out,
        "edges": edges,
        "total_estimated_minutes": sum(n.get("estimated_minutes") or 0 for n in nodes_out),
        "total_actual_minutes": sum(n.get("actual_minutes") or 0 for n in nodes_out),
    }


def get_graph_for_event(event_id: str) -> Dict[str, Any]:
    if not event_id or not event_id.startswith("auto-"):
        return {"ok": False, "error": "unknown event id shape"}

    prefix = event_id[5:]
    rows = _q(AUTOMATIONS_DB,
        "SELECT request_id, description, status, roi_usd, created_at, built_at "
        "FROM automation_requests WHERE request_id LIKE ? LIMIT 1",
        (prefix + "%",))
    if not rows:
        return {"ok": False, "error": "event not found"}

    rid, desc, status, roi_usd, created_at, built_at = rows[0]
    roi_usd = float(roi_usd or 0)
    words = len((desc or "").split())
    human_hrs = min(max(words / 8, 1.5), 10.0)
    human_cost = round(human_hrs * 60.0, 2)
    agent_cost = round(human_cost * 0.018, 4)

    ev = {
        "event_id": event_id, "request_id": rid, "description": desc or "",
        "status": "complete" if status in ("built", "complete") else "active",
        "human_time_estimate_hours": round(human_hrs, 2),
        "human_cost_estimate": human_cost,
        "agent_compute_cost": agent_cost,
        "roi_usd": roi_usd,
    }

    # Look for real workflow
    real = _q(WORKFLOW_DB,
        "SELECT graph_json FROM workflow_runs "
        "WHERE origin_signal LIKE ? OR origin_nl LIKE ? "
        "ORDER BY created_at DESC LIMIT 1",
        (f"%{rid}%", f"%{rid}%"))
    if real and real[0][0]:
        graph = _build_real_graph(real[0][0], ev)
    else:
        graph = _build_synthesized_graph(ev)

    # Compute ROI per canon formula
    actual_min = graph["total_actual_minutes"]
    est_min = human_hrs * 60
    saved_min = max(0, est_min - actual_min)
    hourly_rate = human_cost / (human_hrs * 60) if human_hrs > 0 else 0.6
    saved_usd = saved_min * hourly_rate

    return {
        "ok": True,
        "event": ev,
        "graph": graph,
        "roi_formula": {
            "human_estimate_minutes": round(est_min, 1),
            "actual_minutes": round(actual_min, 1),
            "saved_minutes": round(saved_min, 1),
            "saved_usd": round(saved_usd, 2),
            "label": f"${human_cost:.0f} estimate − ${human_cost - saved_usd:.2f} actual = ${saved_usd:.2f} ROI",
        },
    }


if __name__ == "__main__":
    import sys
    eid = sys.argv[1] if len(sys.argv) > 1 else "auto-016f4390-7ca"
    print(json.dumps(get_graph_for_event(eid), indent=2, default=str))
