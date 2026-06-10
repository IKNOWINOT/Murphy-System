"""Founder domain — CTAs from the executive_cta ledger (EXEC-06 wired)."""
import sqlite3
from typing import Dict, Any, List

AUDIT_DB = "/var/lib/murphy-production/murphy_audit.db"


def _safe_query(sql: str, params=()) -> List[tuple]:
    try:
        conn = sqlite3.connect(f"file:{AUDIT_DB}?mode=ro", uri=True, timeout=2.0)
        try:
            return conn.execute(sql, params).fetchall()
        finally:
            conn.close()
    except Exception:
        return []


def rollup_founder(tenant_id: str | None = None) -> Dict[str, Any]:
    """EXEC-06: read CTAs from the executive_cta table directly.

    Loops emit via executive_cta.propose_*_cta. /os reads from here.
    """
    items: List[Dict[str, Any]] = []
    rows = _safe_query(
        "SELECT cta_id, category, label, description, confidence, "
        "requires_hitl, suggested_at_ns, expires_at_ns, status, action_uri "
        "FROM executive_cta WHERE status='pending' "
        "ORDER BY suggested_at_ns DESC LIMIT 25"
    )
    for cid, cat, label, desc, conf, hitl, sug_ns, exp_ns, status, uri in rows:
        items.append({
            "id": cid,
            "type": "cta",
            "title": label or "(untitled CTA)",
            "description": desc or "",
            "category": cat,
            "confidence": conf,
            "requires_hitl": bool(hitl),
            "state": status,
            "action_uri": uri,
            "suggested_at_ns": sug_ns,
            "expires_at_ns": exp_ns,
        })

    # category counts (one query)
    cat_rows = _safe_query(
        "SELECT category, COUNT(*) FROM executive_cta WHERE status='pending' GROUP BY category"
    )
    by_category = {r[0]: r[1] for r in cat_rows}

    total_pending = sum(by_category.values())
    hitl_count = _safe_query(
        "SELECT COUNT(*) FROM executive_cta WHERE status='pending' AND requires_hitl=1"
    )
    hitl_count = hitl_count[0][0] if hitl_count else 0

    return {
        "summary": {
            "open_ctas_count": total_pending,
            "shown_ctas_count": len(items),
            "by_category": by_category,
            "pending_hitl_count": hitl_count,
        },
        "items": items,
        "raw_endpoints": [
            "/api/executive/cta/list",
            "/api/converge/founder",
        ],
    }
