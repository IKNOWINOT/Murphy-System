"""
PATCH-R122 — pattern_library queryable exposure

WHAT THIS IS:
  Lightweight read-only access to pattern_library.db so future agents
  (and HITL) can introspect WHICH patterns work, WHICH agents converge,
  and WHICH intent shapes have evidence. Composes with R105 paired-loop
  fitness updates already firing.

WHY IT EXISTS:
  326 patterns exist with fitness_score 0.4-0.52 across multiple agents.
  Today the ONLY way to query them is direct sqlite3. Future selection
  logic (which agent for which intent) needs a queryable substrate.

PUBLIC SURFACE:
  pattern_summary() -> dict
    Total counts, agent breakdown, fitness distribution.
  
  query_patterns(agent_id=None, min_fitness=None, intent_keyword=None,
                 limit=20) -> list[dict]
    Filtered pattern rows for caller inspection.
  
  best_agents_for(intent_keyword, limit=3) -> list[dict]
    Top agents by avg fitness for patterns matching keyword.
    Composes with R105 fitness updates — fresh evidence.

DESIGN LOCKED R122:
  Read-only — no INSERT/UPDATE paths. Mutation lives in R105 substrate.
  No web endpoint this round — Python API only (composes with
  reaction_recorder which already imports across substrate).
  R123 wires HTTP exposure if HITL needs it.

LAST UPDATED: 2026-05-29 R122
"""
import logging
import sqlite3
from typing import Any, Dict, List, Optional

logger = logging.getLogger("pattern_library_api")
_DB = "/var/lib/murphy-production/pattern_library.db"


def pattern_summary() -> Dict[str, Any]:
    """Top-level snapshot of pattern_library state."""
    conn = sqlite3.connect("file:{}?mode=ro".format(_DB),
                          uri=True, timeout=3)
    try:
        total = conn.execute(
            "SELECT COUNT(*) FROM patterns").fetchone()[0]
        with_fit = conn.execute(
            "SELECT COUNT(*) FROM patterns "
            "WHERE fitness_score IS NOT NULL").fetchone()[0]
        agg = conn.execute(
            "SELECT COUNT(DISTINCT agent_id), "
            "ROUND(AVG(fitness_score),4), "
            "ROUND(MIN(fitness_score),4), "
            "ROUND(MAX(fitness_score),4) "
            "FROM patterns WHERE fitness_score IS NOT NULL"
        ).fetchone()
        by_agent = conn.execute(
            "SELECT agent_id, COUNT(*) AS n, "
            "ROUND(AVG(fitness_score),4) AS avg_fit "
            "FROM patterns WHERE fitness_score IS NOT NULL "
            "GROUP BY agent_id ORDER BY avg_fit DESC LIMIT 10"
        ).fetchall()
    finally:
        conn.close()
    return {
        "ok": True,
        "total_patterns": total,
        "patterns_with_fitness": with_fit,
        "distinct_agents": agg[0] if agg else 0,
        "fitness": {
            "avg": agg[1] if agg else None,
            "min": agg[2] if agg else None,
            "max": agg[3] if agg else None,
        },
        "top_agents_by_avg_fitness": [
            {"agent_id": r[0], "n_patterns": r[1], "avg_fit": r[2]}
            for r in by_agent
        ],
    }


def query_patterns(agent_id: Optional[str] = None,
                   min_fitness: Optional[float] = None,
                   intent_keyword: Optional[str] = None,
                   limit: int = 20) -> List[Dict[str, Any]]:
    """Filtered pattern lookup."""
    where = ["fitness_score IS NOT NULL"]
    args: List[Any] = []
    if agent_id:
        where.append("agent_id = ?"); args.append(agent_id)
    if min_fitness is not None:
        where.append("fitness_score >= ?"); args.append(min_fitness)
    if intent_keyword:
        where.append("(intent_sample LIKE ? OR domain LIKE ?)")
        args.extend(["%{}%".format(intent_keyword)] * 2)
    sql = (
        "SELECT pattern_id, agent_id, domain, "
        "substr(intent_sample, 1, 80) AS intent, "
        "ROUND(fitness_score, 4) AS fit, last_used, stake "
        "FROM patterns WHERE " + " AND ".join(where) +
        " ORDER BY fitness_score DESC LIMIT ?"
    )
    args.append(limit)
    conn = sqlite3.connect("file:{}?mode=ro".format(_DB),
                          uri=True, timeout=3)
    try:
        rows = conn.execute(sql, args).fetchall()
    finally:
        conn.close()
    return [
        {"pattern_id": r[0], "agent_id": r[1], "domain": r[2],
         "intent": r[3], "fitness_score": r[4],
         "last_used": r[5], "stake": r[6]}
        for r in rows
    ]


def best_agents_for(intent_keyword: str, limit: int = 3) -> List[Dict[str, Any]]:
    """Return top agents by avg fitness for patterns matching keyword."""
    conn = sqlite3.connect("file:{}?mode=ro".format(_DB),
                          uri=True, timeout=3)
    try:
        rows = conn.execute(
            "SELECT agent_id, COUNT(*) AS n, "
            "ROUND(AVG(fitness_score), 4) AS avg_fit "
            "FROM patterns "
            "WHERE fitness_score IS NOT NULL "
            "AND (intent_sample LIKE ? OR domain LIKE ?) "
            "GROUP BY agent_id "
            "ORDER BY avg_fit DESC LIMIT ?",
            ("%{}%".format(intent_keyword),
             "%{}%".format(intent_keyword), limit),
        ).fetchall()
    finally:
        conn.close()
    return [
        {"agent_id": r[0], "n_patterns": r[1], "avg_fit": r[2]}
        for r in rows
    ]


if __name__ == "__main__":
    import json
    print(json.dumps(pattern_summary(), indent=2, default=str))
