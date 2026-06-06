"""
agent_employment_bridge.py — R428
=================================
Connects the existing engines (no rewrites):

  DynamicRosettaPlanner.plan(task)  → DispatchPacket
      ↓
  SoulForge.forge_soul(pos, dom, ctx) → ForgedSoul (LLM-written L2)
      ↓
  edge:8011/api/identity/spawn-agent → real profile_id + api_key
      ↓
  agent_souls table                 → persist soul keyed to profile_id
      ↓
  RosettaSoulRenderer-style envelope ready to inject when agent runs

Per founder direction 2026-06-01: "let the LLM decide the best qualities"
— the planner's analyze_task is LLM-driven via DynamicRosettaPlanner._llm.
"""
from __future__ import annotations
import json
import logging
import os
import sqlite3
import sys
import time
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional

sys.path.insert(0, "/opt/Murphy-System/src")
sys.path.insert(0, "/opt/Murphy-System")

logger = logging.getLogger("murphy.employment_bridge")

EDGE_BASE = os.environ.get("MURPHY_EDGE_BASE", "http://127.0.0.1:8011")
FOUNDER_KEY = os.environ.get(
    "MURPHY_FOUNDER_KEY",
    "founder_ad6b1fade355dc1c6dfa89db96d77608886bf63b01b4fb70",
)
DB_PATH = "/var/lib/murphy-production/murphy_identity.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS agent_souls (
    profile_id    TEXT PRIMARY KEY,
    team_id       TEXT,
    position_id   TEXT,
    title         TEXT,
    domain        TEXT,
    zoom_level    TEXT,
    soul_l0       TEXT,
    soul_l1       TEXT,
    soul_l2       TEXT,
    soul_l3       TEXT,
    knowledge_base TEXT,   -- json list
    authority     TEXT,    -- json list
    boundaries    TEXT,    -- json list
    task_context  TEXT,
    api_key_hash_short TEXT,
    created_at    REAL
);
CREATE INDEX IF NOT EXISTS idx_agent_souls_team ON agent_souls(team_id);
"""

def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH, timeout=15)
    c.executescript(_SCHEMA)
    return c


def _spawn_one(role_class: str, department: str, name_hint: str) -> Dict[str, Any]:
    body = json.dumps({
        "class": role_class,
        "department": department,
        "name_hint": name_hint,
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{EDGE_BASE}/api/identity/spawn-agent",
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-API-Key": FOUNDER_KEY,
            "X-User-ID": "founder",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"ok": False, "error": f"http_{e.code}", "detail": e.read().decode("utf-8", "ignore")}
    except Exception as e:
        return {"ok": False, "error": "spawn_exception", "detail": str(e)}


def _bounded_llm(timeout_s: float = 180.0):  # R479: was 8.0, swarm-floor 180s
    """Wrap llm_provider.complete with a hard timeout — soul forge can hang on slow upstreams."""
    try:
        from llm_provider import complete as _raw
    except Exception as e:
        logger.warning("R428: llm_provider unavailable: %s", e)
        return None
    import concurrent.futures
    _pool = concurrent.futures.ThreadPoolExecutor(max_workers=4)
    def _wrapped(prompt: str, max_tokens: int = 200, temperature: float = 0.4, **kw):
        try:
            fut = _pool.submit(_raw, prompt=prompt, max_tokens=max_tokens, temperature=temperature, **kw)
            return fut.result(timeout=timeout_s)
        except concurrent.futures.TimeoutError:
            logger.warning("R428: LLM call exceeded %.1fs — returning empty", timeout_s)
            return ""
        except Exception as e:
            logger.warning("R428: LLM call failed: %s", e)
            return ""
    return _wrapped


def employ_team(task_prompt: str, llm_controller=None) -> Dict[str, Any]:
    """
    Plan a team for the task → spawn each agent → forge + persist souls.
    Returns {team_id, agents: [...]} with real profile_ids ready to run.
    """
    t0 = time.time()

    # Lazy imports so a missing engine fails loud
    from dynamic_rosetta_planner import DynamicRosettaPlanner
    from soul_forge import SoulForge, POSITION_TEMPLATES

    # R428: bound LLM calls so a slow provider doesnt hang the whole employment
    if llm_controller is None:
        llm_controller = _bounded_llm(timeout_s=180.0)  # R479: was 8.0, swarm-floor 180s

    planner = DynamicRosettaPlanner(llm_controller=llm_controller)
    forge = SoulForge(llm_complete_fn=llm_controller)

    packet = planner.plan(task_prompt)
    logger.info("R428: planner produced %d blueprints for team %s",
                len(packet.team), packet.team_id)

    agents_out: List[Dict[str, Any]] = []
    conn = _conn()
    cur = conn.cursor()

    for blueprint in packet.team:
        # Map blueprint role_class to a soul-forge position_id
        pos = blueprint.role_class.lower()
        if pos not in POSITION_TEMPLATES:
            # Fall back to domain_expert + use the role_class as the domain
            forge_pos = "domain_expert"
            forge_domain = blueprint.role_class
        else:
            forge_pos = pos
            forge_domain = packet.task_profile.domain

        try:
            forged = forge.forge_soul(forge_pos, forge_domain, task_prompt)
        except Exception as e:
            logger.warning("R428: forge failed for %s: %s", blueprint.role_class, e)
            continue

        # Spawn a real agent on edge:8011
        spawn_class = blueprint.role_class.upper().replace("-", "_")[:32]
        spawn = _spawn_one(spawn_class, blueprint.department, blueprint.agent_id)
        if not spawn.get("ok"):
            logger.warning("R428: spawn failed for %s: %s", blueprint.role_class, spawn)
            continue

        profile_id = spawn["profile_id"]
        api_key = spawn["api_key"]

        cur.execute("""
            INSERT OR REPLACE INTO agent_souls (
                profile_id, team_id, position_id, title, domain, zoom_level,
                soul_l0, soul_l1, soul_l2, soul_l3,
                knowledge_base, authority, boundaries,
                task_context, api_key_hash_short, created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            profile_id, packet.team_id, forged.position_id, forged.title,
            forged.domain, forged.zoom_level,
            forged.soul.l0, forged.soul.l1, forged.soul.l2, forged.soul.l3,
            json.dumps(forged.knowledge_base),
            json.dumps(forged.authority),
            json.dumps(forged.boundaries),
            task_prompt[:2000],
            api_key[-8:],  # last 8 only — auditable but not reversible
            time.time(),
        ))

        agents_out.append({
            "profile_id": profile_id,
            "api_key": api_key,           # returned ONCE to caller
            "role": forged.title,
            "position_id": forged.position_id,
            "domain": forged.domain,
            "zoom_level": forged.zoom_level,
            "emoji": forged.emoji,
            "reports_to": blueprint.reports_to,
            "soul_envelope": forge.inject_soul_into_prompt(forged, task_prompt),
        })

    conn.commit()
    conn.close()

    return {
        "ok": True,
        "team_id": packet.team_id,
        "coordinator_id": packet.coordinator_id,
        "task_profile": {
            "domain": packet.task_profile.domain,
            "complexity": packet.task_profile.complexity,
            "stake": packet.task_profile.stake,
            "estimated_agents": packet.task_profile.estimated_agents,
        },
        "org_chart": packet.org_chart.to_dict(),
        "agents": agents_out,
        "elapsed_ms": int((time.time() - t0) * 1000),
    }


def load_soul(profile_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve the persisted soul for an employed agent — used at runtime."""
    conn = _conn()
    cur = conn.cursor()
    cur.execute("""SELECT team_id, position_id, title, domain, zoom_level,
                          soul_l0, soul_l1, soul_l2, soul_l3,
                          knowledge_base, authority, boundaries, task_context, created_at
                   FROM agent_souls WHERE profile_id = ?""", (profile_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "profile_id": profile_id,
        "team_id": row[0], "position_id": row[1], "title": row[2],
        "domain": row[3], "zoom_level": row[4],
        "soul_l0": row[5], "soul_l1": row[6], "soul_l2": row[7], "soul_l3": row[8],
        "knowledge_base": json.loads(row[9] or "[]"),
        "authority": json.loads(row[10] or "[]"),
        "boundaries": json.loads(row[11] or "[]"),
        "task_context": row[12], "created_at": row[13],
    }


def list_team(team_id: str) -> List[Dict[str, Any]]:
    conn = _conn(); cur = conn.cursor()
    cur.execute("SELECT profile_id FROM agent_souls WHERE team_id = ?", (team_id,))
    ids = [r[0] for r in cur.fetchall()]
    conn.close()
    return [load_soul(pid) for pid in ids if load_soul(pid)]


if __name__ == "__main__":
    # Smoke test
    out = employ_team("Interview the founder about Murphy.systems for a PR brief and press kit.")
    print(json.dumps({
        "ok": out.get("ok"),
        "team_id": out.get("team_id"),
        "domain": out.get("task_profile", {}).get("domain"),
        "agents": [{"profile_id": a["profile_id"], "role": a["role"],
                    "position": a["position_id"], "emoji": a["emoji"]}
                   for a in out.get("agents", [])],
        "elapsed_ms": out.get("elapsed_ms"),
    }, indent=2))
