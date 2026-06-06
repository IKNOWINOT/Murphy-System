"""Cap B.3 — read past sessions: read_session_log, list_sessions, search_sessions.

Reuses Murphy's existing `/var/lib/murphy-production/murphy_mind.db`
`chat_sessions` table (9,245+ rows of real conversation history).

Schema there:
  session_id TEXT PRIMARY KEY,
  turns      TEXT (JSON array of turn objects),
  updated    REAL (epoch float)

Each turn looks like {"u": "<user msg>", "a": "<agent reply>"}.

Surfaces:
  - list_sessions(page=1, page_size=10)        # newest first
  - read_session_log(session_id)               # full turns + summary
  - search_sessions(query, page=1, page_size=10)
                                               # substring search over turns

Performance notes:
  - The turns TEXT column has no FTS index. Substring search is
    a full table scan with sqlite LIKE — acceptable at 9k rows
    (~15ms in practice), revisit if rows > 100k.
  - list_sessions hits idx_chat_updated (DESC index) → cheap.
"""
from __future__ import annotations
import json
import sqlite3
import time
from typing import Any, Dict, List, Optional

MIND_DB = "/var/lib/murphy-production/murphy_mind.db"
MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 10


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(MIND_DB, timeout=10)
    c.row_factory = sqlite3.Row
    return c


def _summarize_turns(turns_json: str, max_len: int = 200) -> Dict[str, Any]:
    try:
        turns = json.loads(turns_json) if turns_json else []
    except Exception:
        return {"turn_count": 0, "first_user_msg": "", "last_user_msg": "",
                "parse_error": "turns blob not valid JSON"}
    if not turns:
        return {"turn_count": 0, "first_user_msg": "", "last_user_msg": ""}
    first = turns[0]
    last = turns[-1]
    # Tolerate different turn shapes
    def _user_msg(t):
        if isinstance(t, dict):
            return t.get("u") or t.get("user") or t.get("prompt") or ""
        return ""
    return {
        "turn_count": len(turns),
        "first_user_msg": _user_msg(first)[:max_len],
        "last_user_msg": _user_msg(last)[:max_len],
    }


def list_sessions(*, page: int = 1, page_size: int = DEFAULT_PAGE_SIZE) -> Dict[str, Any]:
    out: Dict[str, Any] = {"ok": False, "page": page, "results": [], "error": None}
    try:
        page = max(1, int(page))
        page_size = max(1, min(MAX_PAGE_SIZE, int(page_size)))
        offset = (page - 1) * page_size
        with _conn() as c:
            total = c.execute("SELECT count(*) FROM chat_sessions").fetchone()[0]
            rows = c.execute("""
                SELECT session_id, turns, updated
                FROM chat_sessions
                ORDER BY updated DESC
                LIMIT ? OFFSET ?
            """, (page_size, offset)).fetchall()
        for r in rows:
            s = _summarize_turns(r["turns"])
            s["session_id"] = r["session_id"]
            s["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(r["updated"]))
            out["results"].append(s)
        out["total"] = total
        out["has_more"] = (offset + len(rows)) < total
        out["count"] = len(out["results"])
        out["ok"] = True
        return out
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"; return out


def read_session_log(session_id: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {"ok": False, "session_id": session_id, "error": None}
    try:
        if not session_id or not session_id.strip():
            out["error"] = "empty session_id"; return out
        with _conn() as c:
            row = c.execute("""
                SELECT session_id, turns, updated
                FROM chat_sessions
                WHERE session_id = ?
            """, (session_id.strip(),)).fetchone()
        if not row:
            out["error"] = "session not found"; return out
        try:
            turns = json.loads(row["turns"]) if row["turns"] else []
        except Exception as e:
            out["error"] = f"turns blob unreadable: {e}"; return out
        out["turns"] = turns
        out["turn_count"] = len(turns)
        out["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(row["updated"]))
        out["bytes"] = len(row["turns"] or "")
        out["ok"] = True
        return out
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"; return out


def search_sessions(
    query: str, *, page: int = 1, page_size: int = DEFAULT_PAGE_SIZE,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {"ok": False, "query": query, "results": [], "error": None}
    try:
        if not query or not query.strip():
            out["error"] = "empty query"; return out
        page = max(1, int(page))
        page_size = max(1, min(MAX_PAGE_SIZE, int(page_size)))
        offset = (page - 1) * page_size
        like = f"%{query.strip()}%"
        with _conn() as c:
            total = c.execute(
                "SELECT count(*) FROM chat_sessions WHERE turns LIKE ?",
                (like,),
            ).fetchone()[0]
            rows = c.execute("""
                SELECT session_id, turns, updated
                FROM chat_sessions
                WHERE turns LIKE ?
                ORDER BY updated DESC
                LIMIT ? OFFSET ?
            """, (like, page_size, offset)).fetchall()
        for r in rows:
            s = _summarize_turns(r["turns"])
            s["session_id"] = r["session_id"]
            s["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(r["updated"]))
            out["results"].append(s)
        out["total_matches"] = total
        out["has_more"] = (offset + len(rows)) < total
        out["count"] = len(out["results"])
        out["ok"] = True
        return out
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"; return out


def execute_list_sessions(**kwargs) -> Dict[str, Any]:
    return list_sessions(
        page=int(kwargs.get("page", 1)),
        page_size=int(kwargs.get("page_size", DEFAULT_PAGE_SIZE)),
    )


def execute_read_session_log(**kwargs) -> Dict[str, Any]:
    return read_session_log(session_id=kwargs.get("session_id", ""))


def execute_search_sessions(**kwargs) -> Dict[str, Any]:
    return search_sessions(
        query=kwargs.get("query", ""),
        page=int(kwargs.get("page", 1)),
        page_size=int(kwargs.get("page_size", DEFAULT_PAGE_SIZE)),
    )
