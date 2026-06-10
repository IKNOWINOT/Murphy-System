"""Identity domain — tenants, practitioners, users."""
import sqlite3
from typing import Dict, Any, List

ENGAGEMENT_DB = "/var/lib/murphy-production/engagement_folders.db"


def _safe_query(db_path: str, sql: str, params=()) -> List[tuple]:
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=2.0)
        try:
            return conn.execute(sql, params).fetchall()
        finally:
            conn.close()
    except Exception:
        return []


def rollup_identity(tenant_id: str | None = None) -> Dict[str, Any]:
    # Practitioners
    pract_rows = _safe_query(
        ENGAGEMENT_DB,
        "SELECT practitioner_id, role_class, jurisdiction, created_at "
        "FROM licensed_practitioners ORDER BY created_at DESC LIMIT 25",
    )
    items = [
        {
            "id": pid,
            "type": "practitioner",
            "title": f"{role or 'practitioner'} ({juris or 'no_jurisdiction'})",
            "created_at": created,
        }
        for pid, role, juris, created in pract_rows
    ]
    summary = {"practitioners_count": len(pract_rows)}
    return {
        "summary": summary,
        "items": items,
        "raw_endpoints": [
            "/api/auth/users",
            "/api/tenant/list",
            "/api/practitioner/bench",
        ],
    }
