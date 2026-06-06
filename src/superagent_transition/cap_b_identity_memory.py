"""Cap B.1 + B.2 + B.6 — identity / memory / user-profile.

Reuses Murphy's existing `/var/lib/murphy-production/memory.db`
`agent_memory` table (already indexed by topic + category). No new
schema needed.

Canonical categories mapping to Base44 superagent's identity files:
  identity   ← IDENTITY.md  (name, vibe, role)
  soul       ← SOUL.md      (values, behavior, ethics)
  user       ← USER.md      (the person Murphy is helping)
  memory     ← memory.md    (long-term conversation memory)
  rule       ← .agents/rules/*.md (standing rules — added in B.7)

Caps in this file:
  - add_memory(topic, content, category='memory', source='superagent',
               importance=0.5)  → B.2
  - update_identity(name, content)   → B.1 / B.6
       name in {'IDENTITY.md','SOUL.md','USER.md','memory.md'}
       Maps to category, persists the FULL canonical content as a
       single 'canon' row per name (overwrite semantics).
  - read_identity_file(name)         → companion read
  - search_memory(query, category=None, limit=50)
  - list_identity_canon()            → all 4 canon rows
"""
from __future__ import annotations
import json
import os
import sqlite3
import time
import uuid
from typing import Any, Dict, List, Optional

MEMORY_DB = "/var/lib/murphy-production/memory.db"
CANON_FILES = {
    "IDENTITY.md": "identity",
    "SOUL.md": "soul",
    "USER.md": "user",
    "memory.md": "memory",
}
VALID_CATEGORIES = {"identity", "soul", "user", "memory", "rule", "general", "fact", "decision"}
CANON_TOPIC = "__canon__"  # special topic for full-document canon rows


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(MEMORY_DB, timeout=10)
    c.row_factory = sqlite3.Row
    # Ensure table exists (defensive — should already exist)
    c.execute("""
        CREATE TABLE IF NOT EXISTS agent_memory (
            id TEXT PRIMARY KEY,
            topic TEXT NOT NULL,
            category TEXT DEFAULT 'general',
            content TEXT NOT NULL,
            source TEXT DEFAULT 'system',
            importance REAL DEFAULT 0.5,
            recall_count INTEGER DEFAULT 0,
            created_at TEXT,
            last_recalled TEXT
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_memory_topic ON agent_memory(topic)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_memory_category ON agent_memory(category)")
    return c


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def add_memory(
    topic: str,
    content: str,
    *,
    category: str = "memory",
    source: str = "superagent",
    importance: float = 0.5,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {"ok": False, "id": None, "error": None}
    try:
        if not topic or not topic.strip():
            out["error"] = "empty topic"; return out
        if not content or not content.strip():
            out["error"] = "empty content"; return out
        if category not in VALID_CATEGORIES:
            out["error"] = f"invalid category: {category} (valid: {sorted(VALID_CATEGORIES)})"
            return out
        importance = max(0.0, min(1.0, float(importance)))

        mid = str(uuid.uuid4())
        with _conn() as c:
            c.execute("""
                INSERT INTO agent_memory
                  (id, topic, category, content, source, importance, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (mid, topic.strip(), category, content, source, importance, _now()))
        out["id"] = mid
        out["topic"] = topic.strip()
        out["category"] = category
        out["importance"] = importance
        out["ok"] = True
        return out
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"; return out


def update_identity(name: str, content: str) -> Dict[str, Any]:
    """Persist the full canonical content of an identity/memory file.

    Overwrite semantics: only one canon row per (name, category) pair.
    Mirrors Base44 superagent's update_identity tool.
    """
    out: Dict[str, Any] = {
        "ok": False, "name": name, "category": None, "id": None, "error": None,
    }
    try:
        if name not in CANON_FILES:
            out["error"] = f"name must be one of {sorted(CANON_FILES)}"; return out
        if not content or not content.strip():
            out["error"] = "empty content"; return out
        category = CANON_FILES[name]
        with _conn() as c:
            # Delete any prior canon row for this file
            c.execute("""
                DELETE FROM agent_memory
                WHERE category = ? AND topic = ?
            """, (category, CANON_TOPIC))
            mid = str(uuid.uuid4())
            c.execute("""
                INSERT INTO agent_memory
                  (id, topic, category, content, source, importance, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (mid, CANON_TOPIC, category, content, "superagent.B.1", 1.0, _now()))
        out["category"] = category
        out["id"] = mid
        out["ok"] = True
        out["bytes"] = len(content)
        return out
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"; return out


def read_identity_file(name: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {"ok": False, "name": name, "content": None, "error": None}
    try:
        if name not in CANON_FILES:
            out["error"] = f"name must be one of {sorted(CANON_FILES)}"; return out
        category = CANON_FILES[name]
        with _conn() as c:
            row = c.execute("""
                SELECT id, content, created_at, importance
                FROM agent_memory
                WHERE category = ? AND topic = ?
                ORDER BY created_at DESC LIMIT 1
            """, (category, CANON_TOPIC)).fetchone()
        if not row:
            out["ok"] = True  # not an error; file simply hasn't been set yet
            out["content"] = ""
            out["exists"] = False
            return out
        # Bump recall_count for analytics
        with _conn() as c:
            c.execute("""
                UPDATE agent_memory
                SET recall_count = recall_count + 1, last_recalled = ?
                WHERE id = ?
            """, (_now(), row["id"]))
        out["content"] = row["content"]
        out["bytes"] = len(row["content"])
        out["created_at"] = row["created_at"]
        out["exists"] = True
        out["ok"] = True
        return out
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"; return out


def search_memory(
    query: str,
    *,
    category: Optional[str] = None,
    limit: int = 50,
) -> Dict[str, Any]:
    """Substring search over topic + content. Bumps recall_count on hits."""
    out: Dict[str, Any] = {"ok": False, "query": query, "results": [], "error": None}
    try:
        if not query or not query.strip():
            out["error"] = "empty query"; return out
        limit = max(1, min(500, int(limit)))
        params: List[Any] = []
        sql = """
            SELECT id, topic, category, content, source, importance,
                   recall_count, created_at, last_recalled
            FROM agent_memory
            WHERE (topic LIKE ? OR content LIKE ?)
        """
        like = f"%{query.strip()}%"
        params.extend([like, like])
        if category:
            if category not in VALID_CATEGORIES:
                out["error"] = f"invalid category: {category}"; return out
            sql += " AND category = ?"
            params.append(category)
        sql += " ORDER BY importance DESC, created_at DESC LIMIT ?"
        params.append(limit)
        with _conn() as c:
            rows = c.execute(sql, params).fetchall()
            for r in rows:
                out["results"].append({
                    "id": r["id"], "topic": r["topic"], "category": r["category"],
                    "content": r["content"], "source": r["source"],
                    "importance": r["importance"],
                    "recall_count": r["recall_count"],
                    "created_at": r["created_at"],
                })
            # Bump recall counts on results
            if rows:
                ids = [r["id"] for r in rows]
                c.executemany(
                    "UPDATE agent_memory SET recall_count = recall_count + 1, last_recalled = ? WHERE id = ?",
                    [(_now(), i) for i in ids],
                )
        out["count"] = len(out["results"])
        out["ok"] = True
        return out
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"; return out


def list_identity_canon() -> Dict[str, Any]:
    """Return all 4 canon-file rows (IDENTITY/SOUL/USER/memory)."""
    out: Dict[str, Any] = {"ok": False, "files": {}, "error": None}
    try:
        cat_to_name = {v: k for k, v in CANON_FILES.items()}
        with _conn() as c:
            for cat, name in [(c2, n2) for n2, c2 in CANON_FILES.items()]:
                row = c.execute("""
                    SELECT id, content, created_at, importance, recall_count
                    FROM agent_memory
                    WHERE category = ? AND topic = ?
                    ORDER BY created_at DESC LIMIT 1
                """, (cat, CANON_TOPIC)).fetchone()
                if row:
                    out["files"][name] = {
                        "exists": True,
                        "bytes": len(row["content"]),
                        "created_at": row["created_at"],
                        "recall_count": row["recall_count"],
                        "preview": row["content"][:120],
                    }
                else:
                    out["files"][name] = {"exists": False}
        out["ok"] = True
        return out
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"; return out


# ── Executor wrappers (cap protocol) ──────────────────────────────────────

def execute_add_memory(**kwargs) -> Dict[str, Any]:
    return add_memory(
        topic=kwargs.get("topic", ""),
        content=kwargs.get("content", ""),
        category=kwargs.get("category", "memory"),
        source=kwargs.get("source", "superagent"),
        importance=float(kwargs.get("importance", 0.5)),
    )


def execute_update_identity(**kwargs) -> Dict[str, Any]:
    return update_identity(
        name=kwargs.get("name", ""),
        content=kwargs.get("content", ""),
    )


def execute_read_identity_file(**kwargs) -> Dict[str, Any]:
    return read_identity_file(name=kwargs.get("name", ""))


def execute_search_memory(**kwargs) -> Dict[str, Any]:
    return search_memory(
        query=kwargs.get("query", ""),
        category=kwargs.get("category"),
        limit=int(kwargs.get("limit", 50)),
    )


def execute_list_identity_canon(**kwargs) -> Dict[str, Any]:
    return list_identity_canon()
