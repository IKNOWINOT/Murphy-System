"""
PATCH-WIRE6-001 (2026-05-28 R52) — Chain Royalty Ledger

WHAT THIS IS:
  When a chain runs, agents staffed onto it may be owned by tenant_X but
  rented by tenant_Y. This module records the revenue event and computes
  royalty splits: who pays, who receives, what platform takes.

WHY IT EXISTS:
  Wires 1-5 created the staffing substrate. Chain executes → observations
  crystallize → broker finds agents → agents get rented. But no ledger
  records "tenant Y paid for tenant X's agent — here are the splits."
  This wire closes that loop.

HOW IT FITS:
  agent_broker.find_agents (R51 Wire #5) returns candidates.
  When a candidate is staffed onto a chain, the caller invokes:
    record_chain_revenue_event(chain_id, agent_id, ...)
  Royalty math runs and chain_revenue_events table accumulates.

KEY CONCEPTS:
  - chain_revenue_event: one row per agent-rental on a chain
  - gross_amount_usd: what the renter pays for that agent's work
  - platform_share: cut Murphy keeps (default 30%)
  - owner_share: cut the agent's owning tenant gets (default 70%)
  - cross_tenant flag: was this a cross-tenant rental?

ENDPOINTS / PUBLIC SURFACE:
  record_chain_revenue_event(chain_id, agent_id, renting_tenant,
                              gross_amount_usd, ...) -> Dict
  compute_royalty_split(gross_amount_usd, platform_pct=0.30) -> Dict
  get_chain_revenue_summary(chain_id) -> Dict
  get_tenant_royalty_summary(tenant_id) -> Dict

DEPENDENCIES:
  - SQLite: own DB at /var/lib/murphy-production/chain_royalty.db
  - Optional read: entity_graph.db.agent_contracts for owning_tenant lookup

KNOWN LIMITS:
  - Hardcoded 30% platform / 70% owner default (configurable per call)
  - rate_book table (Corey's open item) not yet integrated — gross_amount
    is passed in by caller, not looked up
  - Does NOT actually move money — records intent for billing engine

LAST UPDATED: 2026-05-28 R52
"""

import logging
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("chain_royalty")

_DB_PATH = "/var/lib/murphy-production/chain_royalty.db"
_CONTRACTS_DB = "/var/lib/murphy-production/entity_graph.db"
_DEFAULT_PLATFORM_PCT = 0.30


def _ensure_db() -> None:
    os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(_DB_PATH, timeout=3)
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS chain_revenue_events (
                id                    INTEGER PRIMARY KEY AUTOINCREMENT,
                chain_id              TEXT,
                agent_id              TEXT NOT NULL,
                renting_tenant        TEXT,
                owning_tenant         TEXT,
                gross_amount_usd      REAL NOT NULL,
                platform_share_usd    REAL NOT NULL,
                owner_share_usd       REAL NOT NULL,
                platform_pct          REAL NOT NULL,
                cross_tenant          INTEGER DEFAULT 0,
                domain                TEXT,
                fitness_at_staffing   REAL,
                recorded_at           TEXT DEFAULT CURRENT_TIMESTAMP,
                wire_version          TEXT DEFAULT 'WIRE6-001',
                notes                 TEXT
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_cre_chain ON chain_revenue_events(chain_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_cre_renter ON chain_revenue_events(renting_tenant)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_cre_owner ON chain_revenue_events(owning_tenant)")
        conn.commit()
    finally:
        conn.close()


def _lookup_owning_tenant(agent_id: str) -> Optional[str]:
    """Read agent_contracts.tenant_id for this agent. None if not found."""
    if not os.path.exists(_CONTRACTS_DB):
        return None
    try:
        conn = sqlite3.connect(f"file:{_CONTRACTS_DB}?mode=ro", uri=True, timeout=2)
        try:
            row = conn.execute(
                "SELECT tenant_id FROM agent_contracts WHERE agent_id = ?",
                (agent_id,)
            ).fetchone()
            return row[0] if row else None
        finally:
            conn.close()
    except Exception:
        return None


def _lookup_agent_fitness(agent_id: str) -> Optional[float]:
    if not os.path.exists(_CONTRACTS_DB):
        return None
    try:
        conn = sqlite3.connect(f"file:{_CONTRACTS_DB}?mode=ro", uri=True, timeout=2)
        try:
            row = conn.execute(
                "SELECT fitness_score FROM agent_contracts WHERE agent_id = ?",
                (agent_id,)
            ).fetchone()
            return row[0] if row else None
        finally:
            conn.close()
    except Exception:
        return None


def compute_royalty_split(
    gross_amount_usd: float,
    platform_pct: float = _DEFAULT_PLATFORM_PCT,
) -> Dict[str, float]:
    """Pure function: split gross into platform + owner shares."""
    if gross_amount_usd < 0:
        gross_amount_usd = 0.0
    if not (0.0 <= platform_pct <= 1.0):
        platform_pct = _DEFAULT_PLATFORM_PCT
    platform_share = round(gross_amount_usd * platform_pct, 2)
    owner_share = round(gross_amount_usd - platform_share, 2)
    return {
        "gross_amount_usd": round(gross_amount_usd, 2),
        "platform_share_usd": platform_share,
        "owner_share_usd": owner_share,
        "platform_pct": platform_pct,
    }


def record_chain_revenue_event(
    chain_id: str,
    agent_id: str,
    renting_tenant: Optional[str],
    gross_amount_usd: float,
    platform_pct: float = _DEFAULT_PLATFORM_PCT,
    domain: Optional[str] = None,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Record one agent-rental revenue event with royalty split.

    Looks up owning_tenant + fitness from agent_contracts.
    Computes cross_tenant flag (renting != owning).
    Writes the row, returns the recorded data.
    """
    _ensure_db()

    owning_tenant = _lookup_owning_tenant(agent_id)
    fitness = _lookup_agent_fitness(agent_id)
    split = compute_royalty_split(gross_amount_usd, platform_pct)
    cross_tenant = bool(renting_tenant and owning_tenant and
                         renting_tenant != owning_tenant)

    try:
        conn = sqlite3.connect(_DB_PATH, timeout=3)
        try:
            cur = conn.execute(
                """INSERT INTO chain_revenue_events
                   (chain_id, agent_id, renting_tenant, owning_tenant,
                    gross_amount_usd, platform_share_usd, owner_share_usd,
                    platform_pct, cross_tenant, domain, fitness_at_staffing,
                    notes)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (chain_id, agent_id, renting_tenant, owning_tenant,
                 split["gross_amount_usd"], split["platform_share_usd"],
                 split["owner_share_usd"], split["platform_pct"],
                 1 if cross_tenant else 0, domain, fitness, notes)
            )
            event_id = cur.lastrowid
            conn.commit()
            return {
                "event_id": event_id,
                "chain_id": chain_id,
                "agent_id": agent_id,
                "renting_tenant": renting_tenant,
                "owning_tenant": owning_tenant,
                "cross_tenant": cross_tenant,
                "domain": domain,
                "fitness_at_staffing": fitness,
                **split,
                "recorded": True,
                "wire_version": "WIRE6-001",
            }
        finally:
            conn.close()
    except Exception as e:
        logger.warning("record_chain_revenue_event failed: %s", e)
        return {
            "recorded": False, "error": str(e),
            "wire_version": "WIRE6-001",
        }


def get_chain_revenue_summary(chain_id: str) -> Dict[str, Any]:
    """Sum gross/platform/owner for a chain."""
    _ensure_db()
    try:
        conn = sqlite3.connect(f"file:{_DB_PATH}?mode=ro", uri=True, timeout=2)
        try:
            row = conn.execute(
                """SELECT COUNT(*), COALESCE(SUM(gross_amount_usd),0),
                          COALESCE(SUM(platform_share_usd),0),
                          COALESCE(SUM(owner_share_usd),0),
                          SUM(cross_tenant)
                   FROM chain_revenue_events WHERE chain_id = ?""",
                (chain_id,)
            ).fetchone()
            return {
                "chain_id": chain_id,
                "event_count": row[0],
                "total_gross_usd": round(row[1], 2),
                "total_platform_usd": round(row[2], 2),
                "total_owner_usd": round(row[3], 2),
                "cross_tenant_events": row[4] or 0,
                "wire_version": "WIRE6-001",
            }
        finally:
            conn.close()
    except Exception as e:
        return {"error": str(e), "wire_version": "WIRE6-001"}


def get_tenant_royalty_summary(tenant_id: str) -> Dict[str, Any]:
    """How much does this tenant earn (as owner) and pay (as renter)?"""
    _ensure_db()
    try:
        conn = sqlite3.connect(f"file:{_DB_PATH}?mode=ro", uri=True, timeout=2)
        try:
            earned = conn.execute(
                "SELECT COUNT(*), COALESCE(SUM(owner_share_usd),0) "
                "FROM chain_revenue_events WHERE owning_tenant = ?",
                (tenant_id,)
            ).fetchone()
            paid = conn.execute(
                "SELECT COUNT(*), COALESCE(SUM(gross_amount_usd),0) "
                "FROM chain_revenue_events WHERE renting_tenant = ?",
                (tenant_id,)
            ).fetchone()
            return {
                "tenant_id": tenant_id,
                "events_as_owner": earned[0],
                "earned_usd": round(earned[1], 2),
                "events_as_renter": paid[0],
                "paid_usd": round(paid[1], 2),
                "net_usd": round(earned[1] - paid[1], 2),
                "wire_version": "WIRE6-001",
            }
        finally:
            conn.close()
    except Exception as e:
        return {"error": str(e), "wire_version": "WIRE6-001"}


if __name__ == "__main__":
    import json as _j
    print("── Test compute_royalty_split ──")
    print(_j.dumps(compute_royalty_split(100.0), indent=2))
    print("\n── Test record_chain_revenue_event ──")
    r = record_chain_revenue_event("chain_smoke_1", "lead_engineer",
                                    "t1", 250.0, domain="engineering")
    print(_j.dumps(r, indent=2, default=str))
    print("\n── Test get_chain_revenue_summary ──")
    print(_j.dumps(get_chain_revenue_summary("chain_smoke_1"), indent=2))


# PATCH-PROV-WRAP-001 (R65) — module-level provenance wrap
# Installs hitl_provenance trails on public functions/methods so EVERY caller
# (not just test harnesses) gets a verifiable provenance trail.
# Backward compatible — dict-returning fns get _provenance key appended.
try:
    from src.hitl_provenance import with_provenance as _hp_wrap
    if "record_chain_revenue_event" in dir():
        _orig_record_chain_revenue_event = record_chain_revenue_event
        record_chain_revenue_event = _hp_wrap(_orig_record_chain_revenue_event, source_kind="db", source_hint="chain_royalty.db chain_revenue_events insert")
    if "get_tenant_royalty_summary" in dir():
        _orig_get_tenant_royalty_summary = get_tenant_royalty_summary
        get_tenant_royalty_summary = _hp_wrap(_orig_get_tenant_royalty_summary, source_kind="db", source_hint="chain_royalty.db aggregate by tenant_id")
except ImportError:
    # hitl_provenance not installed — operate unwrapped (graceful degrade)
    pass
