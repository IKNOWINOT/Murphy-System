"""
R608 — Contract Loader
======================

Helper that reads agent_contracts from entity_graph.db so any agent
script can load its own contract and act as the contracted executive.

This bridges R603* (cron scripts) to the IS system Murphy already had.

Used by R608-aware agents:
  contract = load_contract("platform_cto")
  # → {role, duties, reports_to, kpis, authorised_actions, off_limits, ...}

Per founder canon: agents work by what their contract says they ARE doing.
This loader is the read side of that relationship.
"""
import sqlite3, json, logging
from typing import Optional, Dict, Any, List
from pathlib import Path

ENTITY_DB = "/var/lib/murphy-production/entity_graph.db"
log = logging.getLogger("r608_contract_loader")


def _conn():
    """Read-only connection."""
    return sqlite3.connect(f"file:{ENTITY_DB}?mode=ro", uri=True)


def load_contract(agent_id: str) -> Optional[Dict[str, Any]]:
    """Return a fully-parsed contract dict, or None if not found."""
    conn = _conn()
    cur = conn.cursor()
    row = cur.execute("""
        SELECT id, agent_id, agent_name, role_title, department, domain,
               management_layer, duties_text, pipeline_touchpoints,
               escalation_paths, hitl_threshold, ocean_json, persona_label,
               communication_style, decision_style, stress_response, kpis_json,
               authorised_actions, off_limits, recalibration_triggers,
               reports_to, tenant_id, fitness_score, last_fitness_refresh
        FROM agent_contracts WHERE agent_id = ?
    """, (agent_id,)).fetchone()
    conn.close()
    if not row:
        return None

    def _maybe_json(s, default):
        if not s:
            return default
        try:
            v = json.loads(s)
            # double-encoded strings
            if isinstance(v, str):
                try: v = json.loads(v)
                except Exception: pass
            return v
        except Exception:
            return default

    return {
        "id": row[0],
        "agent_id": row[1],
        "agent_name": row[2] or row[3],  # fall back to role_title
        "role_title": row[3],
        "department": row[4] or "",
        "domain": row[5] or "",
        "management_layer": row[6] or "",
        "duties_text": row[7] or "",
        "pipeline_touchpoints": _maybe_json(row[8], []),
        "escalation_paths": _maybe_json(row[9], []),
        "hitl_threshold": row[10] or 0.0,
        "ocean": _maybe_json(row[11], {}),
        "persona_label": row[12] or "",
        "communication_style": row[13] or "",
        "decision_style": row[14] or "",
        "stress_response": row[15] or "",
        "kpis": _maybe_json(row[16], []),
        "authorised_actions": _maybe_json(row[17], []),
        "off_limits": _maybe_json(row[18], []),
        "recalibration_triggers": _maybe_json(row[19], []),
        "reports_to": row[20] or None,
        "tenant_id": row[21] or None,
        "fitness_score": row[22] or 0.0,
        "last_fitness_refresh": row[23] or None,
    }


def get_subordinates(agent_id: str) -> List[Dict[str, Any]]:
    """All agents whose reports_to = this agent_id (one layer below)."""
    conn = _conn()
    rows = conn.execute(
        "SELECT agent_id, role_title, department FROM agent_contracts "
        "WHERE reports_to = ? ORDER BY role_title", (agent_id,)
    ).fetchall()
    conn.close()
    return [{"agent_id": r[0], "role_title": r[1], "department": r[2]} for r in rows]


def get_chain_of_command(agent_id: str) -> List[str]:
    """Walk reports_to up to the root. Returns [self, manager, manager's manager, ...]."""
    chain = []
    current = agent_id
    seen = set()
    for _ in range(16):  # bounded
        if current in seen or not current:
            break
        seen.add(current)
        chain.append(current)
        c = _conn()
        row = c.execute(
            "SELECT reports_to FROM agent_contracts WHERE agent_id = ?", (current,)
        ).fetchone()
        c.close()
        if not row or not row[0]:
            break
        current = row[0]
    return chain


def list_org_chart() -> List[Dict[str, Any]]:
    """All contracts, light projection — for org-tree rendering."""
    conn = _conn()
    rows = conn.execute(
        "SELECT agent_id, role_title, department, reports_to, management_layer "
        "FROM agent_contracts ORDER BY management_layer, role_title"
    ).fetchall()
    conn.close()
    return [{"agent_id": r[0], "role_title": r[1], "department": r[2],
             "reports_to": r[3], "management_layer": r[4]} for r in rows]


if __name__ == "__main__":
    import sys
    target = sys.argv[1] if len(sys.argv) > 1 else "platform_cto"
    c = load_contract(target)
    if not c:
        print(f"No contract: {target}"); sys.exit(1)
    print(json.dumps({
        "agent_id": c["agent_id"], "role_title": c["role_title"],
        "reports_to": c["reports_to"], "duties": c["duties_text"][:100],
        "authorised_actions": c["authorised_actions"][:3] if isinstance(c["authorised_actions"], list) else c["authorised_actions"],
        "chain_of_command": get_chain_of_command(target),
        "subordinates": get_subordinates(target),
    }, indent=2))
