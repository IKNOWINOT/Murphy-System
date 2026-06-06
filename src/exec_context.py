"""
PATCH-EXEC-CONTEXT-001 (2026-05-28 R34) — Executive Context Provider

Wires three existing substrates into one read function that exec_admin (or any
agent) can call to ground its decisions in real business state instead of
running blind on heartbeats:

  - BUSINESS PLAN (fixed governing doc):
      • tenant_strategies.strategy_json WHERE is_active=1 (per-tenant)
      • RosettaSoul.NORTH_STAR (platform-level)
      • founder_profile.mindset_goals (per-founder)

  - LIVE ANALYTICS (variable current state):
      • crm.deals count WHERE archived=0
      • chain_engine.chain_requests count WHERE status='active'
      • hitl_jobs count WHERE status='open'
      • economic_pulse.economic_state latest row
      • world_context_provider.get_current_world_context() if available

This module DOES NOT inject anything into agent prompts yet. It's the read
substrate. The next wire (R34+1) takes this dict and threads it into
exec_admin's system prompt at dispatch time. Same pattern as PIPELINE-001:
ship the read first, then wire it into the live path.

Safe to call from any context — never raises, always returns a dict.
Missing data shows as None rather than a thrown exception.
"""

import logging
import os
import sqlite3
from typing import Any, Dict, Optional

logger = logging.getLogger("exec_context")

_DB_BASE = "/var/lib/murphy-production"


def _safe_query(db_name: str, sql: str, params: tuple = ()) -> Optional[Any]:
    """Query a sqlite DB, return first cell or None. Never raises."""
    path = os.path.join(_DB_BASE, db_name)
    if not os.path.exists(path):
        return None
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=2)
        try:
            cur = conn.execute(sql, params)
            row = cur.fetchone()
            return row[0] if row else None
        finally:
            conn.close()
    except Exception as exc:
        logger.warning("exec_context: query %s failed: %s", db_name, exc)
        return None


def _safe_query_row(db_name: str, sql: str, params: tuple = ()) -> Optional[Dict]:
    """Query a sqlite DB, return first row as dict or None."""
    path = os.path.join(_DB_BASE, db_name)
    if not os.path.exists(path):
        return None
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=2)
        try:
            conn.row_factory = sqlite3.Row
            cur = conn.execute(sql, params)
            row = cur.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()
    except Exception as exc:
        logger.warning("exec_context: query_row %s failed: %s", db_name, exc)
        return None


def _get_business_plan(tenant_id: str) -> Dict[str, Any]:
    """Per-tenant business plan from tenant_strategies + Murphy's north star."""
    plan: Dict[str, Any] = {
        "tenant_id": tenant_id,
        "tenant_strategy": None,
        "north_star": None,
        "founder_goals": [],
    }

    # Per-tenant strategy
    row = _safe_query_row(
        "tenants.db",
        "SELECT id, strategy_json, created_at FROM tenant_strategies "
        "WHERE tenant_id = ? AND is_active = 1 LIMIT 1",
        (tenant_id,),
    )
    if row:
        import json as _j
        try:
            plan["tenant_strategy"] = _j.loads(row["strategy_json"])
        except Exception:
            plan["tenant_strategy"] = {"raw": row["strategy_json"][:300]}

    # Platform north star
    try:
        from src.rosetta_core import RosettaSoul
        plan["north_star"] = RosettaSoul.NORTH_STAR
    except Exception as exc:
        logger.warning("north_star unavailable: %s", exc)

    # Founder mindset goals
    path = os.path.join(_DB_BASE, "founder_profile.db")
    if os.path.exists(path):
        try:
            conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=2)
            try:
                conn.row_factory = sqlite3.Row
                cur = conn.execute(
                    "SELECT goal, category, status FROM mindset_goals "
                    "WHERE status = 'active' LIMIT 10"
                )
                plan["founder_goals"] = [dict(r) for r in cur.fetchall()]
            finally:
                conn.close()
        except Exception as exc:
            logger.warning("founder_goals unavailable: %s", exc)

    return plan


def _get_live_kpis() -> Dict[str, Any]:
    """Snapshot of business state right now."""
    kpis: Dict[str, Any] = {}

    kpis["active_deals"] = _safe_query(
        "crm.db",
        "SELECT COUNT(*) FROM deals WHERE archived = 0",
    )

    kpis["open_chains"] = _safe_query(
        "chain_engine.db",
        "SELECT COUNT(*) FROM chain_requests WHERE status = 'active'",
    )

    kpis["pending_hitl"] = _safe_query(
        "hitl_jobs.db",
        "SELECT COUNT(*) FROM hitl_jobs WHERE status = 'open'",
    )

    kpis["lead_contacts"] = _safe_query(
        "crm.db",
        "SELECT COUNT(*) FROM contacts WHERE contact_type='lead' OR contact_type IS NULL",
    )

    # Economic state — note: may be stale, caller should check last_updated
    econ = _safe_query_row(
        "economic_pulse.db",
        "SELECT total_revenue_usd, total_costs_usd, surplus_usd, "
        "autonomy_tier, last_updated FROM economic_state ORDER BY id DESC LIMIT 1",
    )
    kpis["economic_state"] = econ
    if econ and econ.get("last_updated"):
        from datetime import datetime, timezone
        try:
            then = datetime.fromisoformat(econ["last_updated"].replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            kpis["economic_state_age_days"] = (now - then).days
        except Exception:
            kpis["economic_state_age_days"] = None

    return kpis


def _get_world_context() -> Optional[Dict[str, Any]]:
    """Best-effort world context from existing provider."""
    try:
        from src.world_context_provider import get_current_world_context
        return get_current_world_context()
    except Exception as exc:
        logger.info("world_context unavailable: %s", exc)
        return None


def build_exec_context(
    tenant_id: str = "platform",
    agent_id: str = "exec_admin",
) -> Dict[str, Any]:
    """
    Return the full executive context for an agent dispatch.

    Args:
        tenant_id: which tenant's business plan to load. "platform" = Murphy's own.
        agent_id: which agent is asking (for logging/audit).

    Returns:
        {
          "tenant_id": str,
          "agent_id": str,
          "business_plan": {tenant_strategy, north_star, founder_goals},
          "live_kpis": {active_deals, open_chains, pending_hitl, ...},
          "world_context": dict | None,
          "wire_version": "EXEC-CONTEXT-001",
        }

    Never raises. Missing data shows as None.
    """
    ctx = {
        "tenant_id": tenant_id,
        "agent_id": agent_id,
        "business_plan": _get_business_plan(tenant_id),
        "live_kpis": _get_live_kpis(),
        "world_context": _get_world_context(),
        "wire_version": "EXEC-CONTEXT-001",
    }
    logger.info(
        "exec_context built for tenant=%s agent=%s: deals=%s chains=%s hitl=%s",
        tenant_id, agent_id,
        ctx["live_kpis"].get("active_deals"),
        ctx["live_kpis"].get("open_chains"),
        ctx["live_kpis"].get("pending_hitl"),
    )
    return ctx


if __name__ == "__main__":
    import json as _j
    print("─── Test 1: tenant t1 (Apex Plumbing) ───")
    ctx1 = build_exec_context(tenant_id="t1", agent_id="exec_admin")
    print(_j.dumps({
        "tenant_id": ctx1["tenant_id"],
        "has_tenant_strategy": ctx1["business_plan"]["tenant_strategy"] is not None,
        "tenant_primary_goal": (ctx1["business_plan"]["tenant_strategy"] or {}).get("primary_goal"),
        "has_north_star": ctx1["business_plan"]["north_star"] is not None,
        "founder_goal_count": len(ctx1["business_plan"]["founder_goals"]),
        "live_kpis": ctx1["live_kpis"],
        "world_context_available": ctx1["world_context"] is not None,
        "wire_version": ctx1["wire_version"],
    }, indent=2, default=str))

    print("\n─── Test 2: platform-level (Murphy's own ops) ───")
    ctx2 = build_exec_context(tenant_id="platform", agent_id="exec_admin")
    print(_j.dumps({
        "tenant_id": ctx2["tenant_id"],
        "has_tenant_strategy": ctx2["business_plan"]["tenant_strategy"] is not None,
        "has_north_star": ctx2["business_plan"]["north_star"] is not None,
        "north_star_preview": (ctx2["business_plan"]["north_star"] or "")[:120],
        "live_kpis": ctx2["live_kpis"],
        "wire_version": ctx2["wire_version"],
    }, indent=2, default=str))
