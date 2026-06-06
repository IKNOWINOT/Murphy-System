"""
PATCH-WIRE4-001 (2026-05-28 R50) — Agent Contract Fitness Crystallizer

WHAT THIS IS:
  Cross-module bridge: reads observed domain fitness from pattern_library
  (Wire #3 R49 substrate) and writes evidence-based fitness_score to
  agent_contracts. Turns observed chain execution data into agent staffing
  scores.

WHY IT EXISTS:
  Before R49, agent_contracts.fitness_score was either NULL or hardcoded.
  No data tied an agent's "fitness" to actual observed performance.
  R49 created gate_observations (real chain step outcomes per domain).
  This wire crystallizes those observations into per-agent scores.

HOW IT FITS:
  evaluate_gate (R48 Wire #2) → observe_gate_outcome (R49 Wire #3) →
  get_domain_fitness (R49 read API) → THIS MODULE → agent_contracts.fitness_score

KEY CONCEPTS:
  - primary_domain: each agent_contract has a domain it specializes in
  - fitness_score: 0.0-1.0, derived from gate_observations pass_rate
  - min_observations: don't write a score until we have enough data (>= 3)

ENDPOINTS / PUBLIC SURFACE:
  refresh_agent_fitness(agent_id) -> Dict
  refresh_all_agents() -> Dict[agent_id, score]
  get_agent_fitness_snapshot() -> List of agent fitness rows

DEPENDENCIES:
  - src.pattern_library.get_domain_fitness (R49)
  - SQLite: entity_graph.db.agent_contracts table

KNOWN LIMITS:
  - If agent_contracts schema lacks `fitness_score` column, this module
    silently adds it via ALTER TABLE (idempotent).
  - If pattern_library is empty for a domain, fitness_score is left null
    (caller can decide default).
  - Does NOT call observe — read-only on pattern_library, write on contracts.

LAST UPDATED: 2026-05-28 R50
"""

import logging
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("agent_contract_fitness")

_CONTRACTS_DB = "/var/lib/murphy-production/entity_graph.db"
_MIN_OBSERVATIONS = 3   # don't crystallize until we have enough data


def _ensure_fitness_column() -> bool:
    """Idempotent: ensure agent_contracts has fitness_score + last_fitness_refresh."""
    if not os.path.exists(_CONTRACTS_DB):
        return False
    try:
        conn = sqlite3.connect(_CONTRACTS_DB, timeout=3)
        try:
            cur = conn.execute("PRAGMA table_info(agent_contracts)")
            cols = {row[1] for row in cur.fetchall()}
            if "fitness_score" not in cols:
                conn.execute("ALTER TABLE agent_contracts ADD COLUMN fitness_score REAL")
                logger.info("Wire #4: added fitness_score column")
            if "last_fitness_refresh" not in cols:
                conn.execute("ALTER TABLE agent_contracts ADD COLUMN last_fitness_refresh TEXT")
                logger.info("Wire #4: added last_fitness_refresh column")
            if "wire_version_fitness" not in cols:
                conn.execute("ALTER TABLE agent_contracts ADD COLUMN wire_version_fitness TEXT")
                logger.info("Wire #4: added wire_version_fitness column")
            conn.commit()
            return True
        finally:
            conn.close()
    except Exception as e:
        logger.warning("ensure_fitness_column failed: %s", e)
        return False


def _get_contract(agent_id: str) -> Optional[Dict]:
    """Read one agent_contract row by agent_id."""
    if not os.path.exists(_CONTRACTS_DB):
        return None
    try:
        conn = sqlite3.connect(f"file:{_CONTRACTS_DB}?mode=ro", uri=True, timeout=2)
        try:
            conn.row_factory = sqlite3.Row
            # Try a few common ID columns since schema may vary
            for sql in [
                "SELECT * FROM agent_contracts WHERE agent_id = ?",
                "SELECT * FROM agent_contracts WHERE id = ?",
                "SELECT * FROM agent_contracts WHERE contract_id = ?",
            ]:
                try:
                    row = conn.execute(sql, (agent_id,)).fetchone()
                    if row:
                        return dict(row)
                except sqlite3.OperationalError:
                    continue
        finally:
            conn.close()
    except Exception as e:
        logger.debug("_get_contract(%s) failed: %s", agent_id, e)
    return None


def _list_all_contracts() -> List[Dict]:
    """Return all agent_contracts rows."""
    if not os.path.exists(_CONTRACTS_DB):
        return []
    try:
        conn = sqlite3.connect(f"file:{_CONTRACTS_DB}?mode=ro", uri=True, timeout=2)
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM agent_contracts").fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
    except Exception as e:
        logger.warning("_list_all_contracts failed: %s", e)
        return []


def refresh_agent_fitness(agent_id: str, primary_domain: Optional[str] = None) -> Dict[str, Any]:
    """
    Refresh fitness_score for one agent from pattern_library observations.

    Args:
        agent_id: The agent identifier in agent_contracts.
        primary_domain: Override; if None, read from contract row.

    Returns:
        {
          "agent_id", "domain", "fitness_score", "observations_used",
          "updated", "wire_version", "reason"
        }
        updated=False means no write happened (insufficient data, etc).
    """
    _ensure_fitness_column()

    contract = _get_contract(agent_id)
    if not contract:
        return {
            "agent_id": agent_id, "domain": None, "fitness_score": None,
            "observations_used": 0, "updated": False,
            "wire_version": "WIRE4-001", "reason": "contract_not_found",
        }

    domain = primary_domain or contract.get("primary_domain") or \
             contract.get("domain") or contract.get("specialization")
    if not domain:
        return {
            "agent_id": agent_id, "domain": None, "fitness_score": None,
            "observations_used": 0, "updated": False,
            "wire_version": "WIRE4-001", "reason": "no_domain_set",
        }

    # Read fitness from pattern_library (R49 substrate)
    try:
        from src.pattern_library import get_domain_fitness
        fit = get_domain_fitness(domain)
    except Exception as e:
        return {
            "agent_id": agent_id, "domain": domain, "fitness_score": None,
            "observations_used": 0, "updated": False,
            "wire_version": "WIRE4-001", "reason": f"pattern_lib_unavailable:{e}",
        }

    total = fit.get("total", 0)
    if total < _MIN_OBSERVATIONS:
        return {
            "agent_id": agent_id, "domain": domain,
            "fitness_score": fit.get("pass_rate"), "observations_used": total,
            "updated": False, "wire_version": "WIRE4-001",
            "reason": f"insufficient_data:{total}<{_MIN_OBSERVATIONS}",
        }

    score = fit.get("pass_rate", 0.0)
    now = datetime.now(timezone.utc).isoformat()

    # Write to agent_contracts
    try:
        conn = sqlite3.connect(_CONTRACTS_DB, timeout=3)
        try:
            # Pick the right ID column based on which match returned the contract
            for sql in [
                "UPDATE agent_contracts SET fitness_score=?, last_fitness_refresh=?, wire_version_fitness=? WHERE agent_id=?",
                "UPDATE agent_contracts SET fitness_score=?, last_fitness_refresh=?, wire_version_fitness=? WHERE id=?",
                "UPDATE agent_contracts SET fitness_score=?, last_fitness_refresh=?, wire_version_fitness=? WHERE contract_id=?",
            ]:
                try:
                    cur = conn.execute(sql, (score, now, "WIRE4-001", agent_id))
                    if cur.rowcount > 0:
                        conn.commit()
                        return {
                            "agent_id": agent_id, "domain": domain,
                            "fitness_score": score, "observations_used": total,
                            "updated": True, "wire_version": "WIRE4-001",
                            "reason": "updated_from_observations",
                        }
                except sqlite3.OperationalError:
                    continue
            return {
                "agent_id": agent_id, "domain": domain, "fitness_score": score,
                "observations_used": total, "updated": False,
                "wire_version": "WIRE4-001", "reason": "no_id_column_matched",
            }
        finally:
            conn.close()
    except Exception as e:
        return {
            "agent_id": agent_id, "domain": domain, "fitness_score": None,
            "observations_used": total, "updated": False,
            "wire_version": "WIRE4-001", "reason": f"write_failed:{e}",
        }


def refresh_all_agents() -> Dict[str, Any]:
    """
    Walk all agent_contracts rows, refresh each one's fitness.

    Returns: {"refreshed": int, "skipped": int, "results": [per-agent dicts]}
    """
    contracts = _list_all_contracts()
    results = []
    refreshed = 0
    skipped = 0
    for c in contracts:
        agent_id = c.get("agent_id") or c.get("id") or c.get("contract_id")
        if not agent_id:
            skipped += 1
            continue
        r = refresh_agent_fitness(str(agent_id))
        results.append(r)
        if r.get("updated"):
            refreshed += 1
        else:
            skipped += 1
    return {
        "refreshed": refreshed,
        "skipped": skipped,
        "total_contracts": len(contracts),
        "results": results,
        "wire_version": "WIRE4-001",
    }


def get_agent_fitness_snapshot() -> List[Dict[str, Any]]:
    """Read current fitness state across all agents (for inspection)."""
    return _list_all_contracts()


if __name__ == "__main__":
    import json as _j
    print("── Ensure column ──")
    print(_ensure_fitness_column())
    print("\n── Refresh all ──")
    r = refresh_all_agents()
    print(_j.dumps(r, indent=2, default=str))
