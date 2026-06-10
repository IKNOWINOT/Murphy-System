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
    eng_rows = _safe_query(
        ENGAGEMENT_DB,
        "SELECT folder_id, state, role_class, created_at, updated_at "
        "FROM engagement_folders ORDER BY updated_at DESC LIMIT 25",
    )
    for fid, state, role, created, updated in eng_rows:
        items.append({
            "id": fid,
            "type": "engagement",
            "title": f"{role or 'engagement'} {fid[:18]}",
            "state": state,
            "created_at": created,
            "updated_at": updated,
            "drill_endpoint": f"/api/converge/work/{fid}",
            "closure_forecast": None,  # PCR-090b fills this
        })

    # Boundary drills
    drill_rows = _safe_query(
        ENGAGEMENT_DB,
        "SELECT dispatch_id, boundary_state, solved_ratio, solved_count, "
        "total_count, iterations_run, created_at FROM boundary_loop_iterations "
        "WHERE iteration = (SELECT MAX(iteration) FROM boundary_loop_iterations b2 "
        "WHERE b2.dispatch_id = boundary_loop_iterations.dispatch_id) "
        "ORDER BY created_at DESC LIMIT 25",
    )
    for did, bstate, sratio, scnt, tcnt, iters, created in drill_rows:
        items.append({
            "id": did,
            "type": "boundary_drill",
            "title": f"drill {did[:18]}",
            "state": bstate,
            "solved_ratio": sratio,
            "solved_count": scnt,
            "total_count": tcnt,
            "iterations_run": iters,
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
