"""Work domain — engagement folders + boundary drills + active dispatches."""
import sqlite3
import time
from typing import Dict, Any, List

ENGAGEMENT_DB = "/var/lib/murphy-production/engagement_folders.db"


def _safe_query(db_path: str, sql: str, params=()) -> List[tuple]:
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=2.0)
        try:
            cur = conn.execute(sql, params)
            return cur.fetchall()
        finally:
            conn.close()
    except Exception:
        return []


def rollup_work(tenant_id: str | None = None) -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []

    # Engagement folders
    # PCR-054q: surface engagement folders (was broken — column name mismatch)
    eng_rows = _safe_query(
        ENGAGEMENT_DB,
        "SELECT engagement_id, state, role_id, artifact_type, "
        "practitioner_email, rate_quote_usd, deadline_at, created_at, updated_at "
        "FROM engagement_folders ORDER BY updated_at DESC LIMIT 25",
    )
    for fid, state, role, artifact, prac, rate, deadline, created, updated in eng_rows:
        # Human-friendly title
        title = f"{role or 'engagement'} — {artifact or 'artifact'} ({fid[:12]})"
        items.append({
            "id": fid,
            "type": "engagement",
            "title": title,
            "state": state,
            "role_id": role,
            "artifact_type": artifact,
            "practitioner_email": prac,
            "rate_quote_usd": rate,
            "deadline_at": deadline,
            "created_at": created,
            "updated_at": updated,
            "drill_endpoint": f"/api/converge/work/{fid}",
            "closure_forecast": None,  # PCR-090b enrichment fills this
        })

    # Boundary drills
    # PCR-060l: surface boundary drills with |S|/|R̂| markers (was broken — bad column)
    # Group by dispatch_id, take latest iteration per drill
    drill_rows = _safe_query(
        ENGAGEMENT_DB,
        "SELECT dispatch_id, boundary_state, solved_ratio, solved_count, "
        "total_count, MAX(iteration), MAX(created_at), MAX(cumulative_cost_usd) "
        "FROM boundary_loop_iterations "
        "GROUP BY dispatch_id "
        "ORDER BY MAX(created_at) DESC LIMIT 25",
    )
    for did, bstate, sratio, scnt, tcnt, iters, created, cost in drill_rows:
        items.append({
            "id": did,
            "type": "boundary_drill",
            "title": f"drill {did[:18]} — {bstate or 'pending'}",
            "state": bstate or "pending",
            "solved_ratio": sratio,
            "solved_count": scnt,
            "total_count": tcnt,
            "iterations_run": iters,
            "cumulative_cost_usd": cost,
            "created_at": created,
            "drill_endpoint": f"/api/converge/work/{did}",
            "closure_forecast": None,
        })

    # Summary
    summary = {
        "active_count": len(items),
        "engagements_count": len(eng_rows),
        "drills_count": len(drill_rows),
    }
    return {
        "summary": summary,
        "items": items,
        "raw_endpoints": [
            "/api/engagement/folders",
            "/api/boundary/drills",
        ],
    }
