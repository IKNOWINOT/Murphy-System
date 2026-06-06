"""Cap B.7 — rule file management.

Standing rules / decisions that always apply. Mirrors Base44's
`.agents/rules/*.md` model.

Storage: memory.db agent_memory table, category='rule'.
Each rule = one row, addressable by topic (rule name).

Surfaces:
  - add_rule(name, content, importance=1.0)
  - update_rule(name, content)
  - get_rule(name)
  - list_rules()
  - delete_rule(name)
"""
from __future__ import annotations
import sqlite3
import time
import uuid
from typing import Any, Dict, List, Optional

MEMORY_DB = "/var/lib/murphy-production/memory.db"
RULE_CATEGORY = "rule"


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(MEMORY_DB, timeout=10)
    c.row_factory = sqlite3.Row
    return c


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def add_rule(name: str, content: str, *, importance: float = 1.0) -> Dict[str, Any]:
    out: Dict[str, Any] = {"ok": False, "name": name, "id": None, "error": None}
    try:
        if not name or not name.strip():
            out["error"] = "empty name"; return out
        if not content or not content.strip():
            out["error"] = "empty content"; return out
        importance = max(0.0, min(1.0, float(importance)))
        name = name.strip()
        with _conn() as c:
            existing = c.execute(
                "SELECT id FROM agent_memory WHERE category = ? AND topic = ?",
                (RULE_CATEGORY, name),
            ).fetchone()
            if existing:
                out["error"] = f"rule '{name}' already exists (use update_rule)"
                return out
            rid = str(uuid.uuid4())
            c.execute("""
                INSERT INTO agent_memory
                  (id, topic, category, content, source, importance, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (rid, name, RULE_CATEGORY, content, "superagent.B.7", importance, _now()))
        out["id"] = rid
        out["importance"] = importance
        out["bytes"] = len(content)
        out["ok"] = True
        return out
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"; return out


def update_rule(name: str, content: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {"ok": False, "name": name, "error": None}
    try:
        if not name or not content:
            out["error"] = "name and content required"; return out
        with _conn() as c:
            row = c.execute(
                "SELECT id FROM agent_memory WHERE category = ? AND topic = ?",
                (RULE_CATEGORY, name.strip()),
            ).fetchone()
            if not row:
                out["error"] = f"rule '{name}' not found (use add_rule)"
                return out
            c.execute("""
                UPDATE agent_memory
                SET content = ?, last_recalled = ?
                WHERE id = ?
            """, (content, _now(), row["id"]))
        out["bytes"] = len(content)
        out["ok"] = True
        return out
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"; return out


def get_rule(name: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {"ok": False, "name": name, "error": None}
    try:
        if not name:
            out["error"] = "empty name"; return out
        with _conn() as c:
            row = c.execute("""
                SELECT id, content, importance, recall_count, created_at
                FROM agent_memory
                WHERE category = ? AND topic = ?
            """, (RULE_CATEGORY, name.strip())).fetchone()
            if not row:
                out["ok"] = True
                out["exists"] = False
                return out
            c.execute(
                "UPDATE agent_memory SET recall_count = recall_count + 1, last_recalled = ? WHERE id = ?",
                (_now(), row["id"]),
            )
        out["exists"] = True
        out["content"] = row["content"]
        out["importance"] = row["importance"]
        out["bytes"] = len(row["content"])
        out["created_at"] = row["created_at"]
        out["ok"] = True
        return out
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"; return out


def list_rules() -> Dict[str, Any]:
    out: Dict[str, Any] = {"ok": False, "rules": [], "error": None}
    try:
        with _conn() as c:
            rows = c.execute("""
                SELECT topic, importance, recall_count, created_at, length(content) AS bytes
                FROM agent_memory
                WHERE category = ?
                ORDER BY importance DESC, created_at ASC
            """, (RULE_CATEGORY,)).fetchall()
        for r in rows:
            out["rules"].append({
                "name": r["topic"], "importance": r["importance"],
                "bytes": r["bytes"], "recall_count": r["recall_count"],
                "created_at": r["created_at"],
            })
        out["count"] = len(out["rules"])
        out["ok"] = True
        return out
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"; return out


def delete_rule(name: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {"ok": False, "name": name, "deleted": False, "error": None}
    try:
        if not name:
            out["error"] = "empty name"; return out
        with _conn() as c:
            cur = c.execute(
                "DELETE FROM agent_memory WHERE category = ? AND topic = ?",
                (RULE_CATEGORY, name.strip()),
            )
            out["deleted"] = cur.rowcount > 0
        out["ok"] = True
        return out
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"; return out


def execute_add_rule(**kwargs) -> Dict[str, Any]:
    return add_rule(
        name=kwargs.get("name", ""), content=kwargs.get("content", ""),
        importance=float(kwargs.get("importance", 1.0)),
    )


def execute_update_rule(**kwargs) -> Dict[str, Any]:
    return update_rule(name=kwargs.get("name", ""), content=kwargs.get("content", ""))


def execute_get_rule(**kwargs) -> Dict[str, Any]:
    return get_rule(name=kwargs.get("name", ""))


def execute_list_rules(**kwargs) -> Dict[str, Any]:
    return list_rules()


def execute_delete_rule(**kwargs) -> Dict[str, Any]:
    return delete_rule(name=kwargs.get("name", ""))
