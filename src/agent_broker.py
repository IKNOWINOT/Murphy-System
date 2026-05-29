"""
PATCH-WIRE5-001 (2026-05-28 R51) — Agent Broker for Cross-Tenant Staffing

WHAT THIS IS:
  Query layer that answers "which agents qualify for domain X at fitness >= Y,
  given a requesting tenant T?" Returns a ranked list of agent contracts that
  can be staffed onto a chain.

WHY IT EXISTS:
  Wires #1-#4 created the substrate. Chain execution → observation → fitness
  crystallization. But there is no API yet that USES the fitness data to
  answer staffing questions. This wire is that API.

  Pre-R51: agent_contracts table is data. Nothing asks "find me an agent."
  Post-R51: chain_engine, hitl, or a future broker UI can ask "give me
            the best engineering agent" and get an evidence-ranked answer.

HOW IT FITS:
  agent_contract_fitness (R50) writes fitness_score to agent_contracts.
  THIS MODULE reads agent_contracts and returns ranked results filtered by
  domain + minimum fitness + tenant policy.

  Future Wire #6 (royalty) reads which contracts were used for which chain
  and computes revenue splits.

KEY CONCEPTS:
  - DOMAIN MATCH: agent.domain == query.domain (exact match for now)
  - FITNESS THRESHOLD: agent.fitness_score >= query.min_fitness
  - TENANT POLICY: same-tenant always allowed; cross-tenant gated by
    cross_tenant_allowed flag (default False for safety)
  - RANKING: by fitness_score DESC, then observation_count DESC

ENDPOINTS / PUBLIC SURFACE:
  find_agents(domain, min_fitness=0.0, requesting_tenant=None,
              allow_cross_tenant=False, limit=10) -> List[Dict]
  get_best_agent(domain, requesting_tenant=None) -> Optional[Dict]
  broker_stats() -> Dict

DEPENDENCIES:
  - SQLite: entity_graph.db.agent_contracts (read-only)
  - src.agent_contract_fitness for live refresh (optional)

KNOWN LIMITS:
  - Exact domain match only — no fuzzy/parent-domain matching yet
  - cross-tenant policy is a single flag, no per-tenant ACL yet
  - Does NOT actually staff (assign) — only returns candidates
  - Royalty calculation (Wire #6) is downstream

LAST UPDATED: 2026-05-28 R51
"""

import logging
import os
import sqlite3
from typing import Any, Dict, List, Optional

logger = logging.getLogger("agent_broker")

_CONTRACTS_DB = "/var/lib/murphy-production/entity_graph.db"


def _query_contracts(domain: str, min_fitness: float = 0.0,
                      include_null_fitness: bool = False) -> List[Dict]:
    """Read matching agent_contracts rows."""
    if not os.path.exists(_CONTRACTS_DB):
        return []
    try:
        conn = sqlite3.connect(f"file:{_CONTRACTS_DB}?mode=ro", uri=True, timeout=3)
        try:
            conn.row_factory = sqlite3.Row
            if include_null_fitness:
                # Return matches even without fitness data (useful for surfacing)
                sql = ("SELECT * FROM agent_contracts "
                       "WHERE domain = ? "
                       "ORDER BY fitness_score DESC NULLS LAST")
                cur = conn.execute(sql, (domain,))
            else:
                sql = ("SELECT * FROM agent_contracts "
                       "WHERE domain = ? AND fitness_score >= ? "
                       "ORDER BY fitness_score DESC, observation_count DESC")
                cur = conn.execute(sql, (domain, min_fitness))
            return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()
    except Exception as e:
        logger.debug("_query_contracts(%s) failed: %s", domain, e)
        return []


def find_agents(
    domain: str,
    min_fitness: float = 0.0,
    requesting_tenant: Optional[str] = None,
    allow_cross_tenant: bool = False,
    include_unscored: bool = False,
    limit: int = 10,
) -> Dict[str, Any]:
    """
    Find agents matching domain + fitness threshold + tenant policy.

    Args:
        domain: required domain to match (e.g. "engineering")
        min_fitness: minimum fitness_score (0.0-1.0); 0.0 = any
        requesting_tenant: tenant making the request; None = platform
        allow_cross_tenant: if False, only same-tenant + null-tenant agents
        include_unscored: if True, include agents with null fitness_score
        limit: max results

    Returns:
        {
          "domain", "min_fitness", "requesting_tenant",
          "allow_cross_tenant", "candidates", "candidate_count",
          "wire_version", "policy_applied", "reason"
        }
        candidates: list of agent contract dicts, ranked
    """
    rows = _query_contracts(domain, min_fitness, include_null_fitness=include_unscored)

    # Apply tenant policy
    filtered = []
    for r in rows:
        agent_tenant = r.get("tenant_id")
        if requesting_tenant is None:
            # Platform-level request — always allowed
            filtered.append(r)
        elif agent_tenant == requesting_tenant:
            # Same-tenant — always allowed
            filtered.append(r)
        elif agent_tenant is None:
            # Platform agents — always rentable
            filtered.append(r)
        elif allow_cross_tenant:
            # Cross-tenant explicitly permitted
            filtered.append(r)
        # else: skip (cross-tenant blocked)

    # Trim to limit
    candidates = filtered[:limit]

    policy = "platform_request"
    if requesting_tenant:
        policy = "cross_tenant_allowed" if allow_cross_tenant else "same_tenant_only"

    return {
        "domain": domain,
        "min_fitness": min_fitness,
        "requesting_tenant": requesting_tenant,
        "allow_cross_tenant": allow_cross_tenant,
        "candidates": candidates,
        "candidate_count": len(candidates),
        "total_matched_pre_policy": len(rows),
        "wire_version": "WIRE5-001",
        "policy_applied": policy,
        "reason": "ok" if candidates else "no_match",
    }


def get_best_agent(
    domain: str,
    requesting_tenant: Optional[str] = None,
    allow_cross_tenant: bool = False,
) -> Optional[Dict[str, Any]]:
    """Convenience: return top-ranked candidate or None."""
    r = find_agents(
        domain=domain,
        min_fitness=0.0,
        requesting_tenant=requesting_tenant,
        allow_cross_tenant=allow_cross_tenant,
        limit=1,
    )
    cands = r.get("candidates", [])
    return cands[0] if cands else None


def broker_stats() -> Dict[str, Any]:
    """Inspect broker state — useful for HITL or admin."""
    if not os.path.exists(_CONTRACTS_DB):
        return {"error": "contracts_db_missing", "wire_version": "WIRE5-001"}
    try:
        conn = sqlite3.connect(f"file:{_CONTRACTS_DB}?mode=ro", uri=True, timeout=2)
        try:
            total = conn.execute("SELECT COUNT(*) FROM agent_contracts").fetchone()[0]
            with_fit = conn.execute(
                "SELECT COUNT(*) FROM agent_contracts WHERE fitness_score IS NOT NULL"
            ).fetchone()[0]
            # Per-domain breakdown
            cur = conn.execute(
                "SELECT domain, COUNT(*) as n, "
                "SUM(CASE WHEN fitness_score IS NOT NULL THEN 1 ELSE 0 END) as scored, "
                "AVG(fitness_score) as avg_fit "
                "FROM agent_contracts WHERE domain IS NOT NULL "
                "GROUP BY domain ORDER BY n DESC"
            )
            by_domain = [
                {"domain": r[0], "agents": r[1], "with_fitness": r[2],
                 "avg_fitness": round(r[3], 3) if r[3] else None}
                for r in cur.fetchall()
            ]
            return {
                "total_contracts": total,
                "with_fitness_score": with_fit,
                "by_domain": by_domain,
                "wire_version": "WIRE5-001",
            }
        finally:
            conn.close()
    except Exception as e:
        return {"error": str(e), "wire_version": "WIRE5-001"}


if __name__ == "__main__":
    import json as _j
    print("── broker_stats ──")
    print(_j.dumps(broker_stats(), indent=2, default=str))
    print("\n── find_agents(domain='engineering', min_fitness=0.5) ──")
    print(_j.dumps(find_agents("engineering", 0.5), indent=2, default=str)[:1500])
    print("\n── get_best_agent(domain='engineering') ──")
    print(_j.dumps(get_best_agent("engineering"), indent=2, default=str)[:500])


# PATCH-PROV-WRAP-001 (R65) — module-level provenance wrap
# Installs hitl_provenance trails on public functions/methods so EVERY caller
# (not just test harnesses) gets a verifiable provenance trail.
# Backward compatible — dict-returning fns get _provenance key appended.
try:
    from src.hitl_provenance import with_provenance as _hp_wrap
    if "find_agents" in dir():
        _orig_find_agents = find_agents
        find_agents = _hp_wrap(_orig_find_agents, source_kind="db", source_hint="entity_graph.agent_contracts table")
    if "get_best_agent" in dir():
        _orig_get_best_agent = get_best_agent
        get_best_agent = _hp_wrap(_orig_get_best_agent, source_kind="db", source_hint="entity_graph.agent_contracts ranked by fitness")
    if "broker_stats" in dir():
        _orig_broker_stats = broker_stats
        broker_stats = _hp_wrap(_orig_broker_stats, source_kind="db", source_hint="entity_graph.agent_contracts aggregate")
except ImportError:
    # hitl_provenance not installed — operate unwrapped (graceful degrade)
    pass
