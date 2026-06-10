"""Money domain — vault balances, ledger, costs, subscriptions."""
import sqlite3
from typing import Dict, Any, List

LLM_DB = "/var/lib/murphy-production/llm_cost_ledger.db"


def _safe_query(db_path: str, sql: str, params=()) -> List[tuple]:
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=2.0)
        try:
            return conn.execute(sql, params).fetchall()
        finally:
            conn.close()
    except Exception:
        return []


def rollup_money(tenant_id: str | None = None) -> Dict[str, Any]:
    # Recent LLM cost
    rows = _safe_query(
        LLM_DB,
        "SELECT COUNT(*), COALESCE(SUM(cost_usd),0) FROM calls WHERE ts > strftime('%s','now','-30 days')",
    )
    call_count = rows[0][0] if rows else 0
    cost_30d = float(rows[0][1]) if rows else 0.0

    summary = {
        "llm_cost_30d_usd": round(cost_30d, 4),
        "llm_calls_30d": call_count,
        "active_subscriptions": 0,  # TODO PCR-090b: pull from billing
    }
    items: List[Dict[str, Any]] = []
    return {
        "summary": summary,
        "items": items,
        "raw_endpoints": [
            "/api/llm/cost/summary",
            "/api/payments/subscriptions",
            "/api/vault/balance",
        ],
    }
