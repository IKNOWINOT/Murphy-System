"""Founder domain — CTAs, queue, decisions."""
from typing import Dict, Any


def rollup_founder(tenant_id: str | None = None) -> Dict[str, Any]:
    items = []
    try:
        from src.executive_wiring import build_status_payload
        live = build_status_payload()
        ctas = live.get("recent_ctas", []) or []
        for c in ctas[:25]:
            items.append({
                "id": c.get("cta_id") or c.get("id"),
                "type": "cta",
                "title": c.get("title", "(untitled CTA)"),
                "state": c.get("status", "open"),
                "category": c.get("category"),
                "confidence": c.get("confidence"),
            })
    except Exception:
        pass

    summary = {
        "open_ctas_count": sum(1 for i in items if i.get("state") == "open"),
        "total_ctas_count": len(items),
        "pending_hitl_count": 0,  # PCR-080d will fill
    }
    return {
        "summary": summary,
        "items": items,
        "raw_endpoints": [
            "/api/executive/cta/list",
            "/api/hitl/queue",
            "/api/queue/suggestions",
        ],
    }
