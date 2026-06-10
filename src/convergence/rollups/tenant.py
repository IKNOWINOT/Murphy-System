"""Tenant domain — per-tenant scoped view. Requires X-Tenant-Id header."""
from typing import Dict, Any


def rollup_tenant(tenant_id: str | None = None) -> Dict[str, Any]:
    if not tenant_id:
        return {
            "summary": {"error": "tenant_id required"},
            "items": [],
            "raw_endpoints": [],
            "_errors": ["CONV_E003 X-Tenant-Id header required for tenant domain"],
        }
    # Cross-domain rollup scoped to this tenant
    from .work import rollup_work
    from .money import rollup_money
    from .identity import rollup_identity
    sub = {
        "work": rollup_work(tenant_id),
        "money": rollup_money(tenant_id),
        "identity": rollup_identity(tenant_id),
    }
    summary = {
        "tenant_id": tenant_id,
        "work_items": sub["work"]["summary"].get("active_count", 0),
        "money_30d_usd": sub["money"]["summary"].get("llm_cost_30d_usd", 0.0),
        "identity_count": sub["identity"]["summary"].get("practitioners_count", 0),
    }
    return {
        "summary": summary,
        "items": [],
        "sub_rollups": sub,
        "raw_endpoints": [],
    }
