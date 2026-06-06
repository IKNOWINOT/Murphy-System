"""Caps F.1 + F.2 + F.3 + F.4 — backend function lifecycle.

Wraps Murphy's ForgeEngine (73 deployed items, hot-import pipeline,
AST safety check). Provides Base44 contract:
  - F.1 deploy_backend_function(function_name, code [or description])
  - F.2 test_backend_function(function_name, payload)
  - F.3 delete_backend_function(function_name)
  - F.4 get_backend_function_logs(function_name, limit=50)

Two deploy paths:
  1. code given → skip LLM, AST-check, write, hot-import (Base44 contract)
  2. description given → ForgeEngine.create (Murphy NL superpower)

Storage tier: tenant_id='superagent' (kept separate from 'default'
so the 31 existing default-tenant items aren't disturbed).
"""
from __future__ import annotations
import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import forge_engine as _fe

DB = "/var/lib/murphy-production/forge.db"
TENANT = "superagent"
LOG_PATH = Path("/var/lib/murphy-production/forge_invocations.log")  # /var/log not writable by murphy user


def _conn():
    c = sqlite3.connect(DB, timeout=10)
    c.row_factory = sqlite3.Row
    return c


def _log_invocation(name: str, status: str, wall_ms: int, error: Optional[str] = None):
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a") as f:
            entry = {
                "ts": time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime()),
                "tenant": TENANT, "name": name, "status": status,
                "wall_ms": wall_ms, "error": error,
            }
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass


# ── F.1 deploy_backend_function ───────────────────────────────────────────

def deploy_backend_function(
    function_name: str,
    *,
    code: Optional[str] = None,
    description: Optional[str] = None,
) -> Dict[str, Any]:
    """Deploy a backend function — code-direct or description-driven."""
    out: Dict[str, Any] = {"ok": False, "function_name": function_name, "error": None}
    try:
        if not function_name or not function_name.strip():
            out["error"] = "empty function_name"; return out
        if not code and not description:
            out["error"] = "must provide either 'code' or 'description'"; return out
        if code and description:
            out["error"] = "provide only one of 'code' or 'description'"; return out

        name = function_name.strip()
        fe = _fe.get_forge()

        # Code-direct path (no LLM)
        if code:
            safe, reason = _fe._safety_check(code)
            if not safe:
                out["error"] = f"safety check failed: {reason}"; return out
            # Detect main function name in the source if function_name differs
            try:
                mod, file_path = _fe._write_and_import(name, code, TENANT)
            except Exception as e:
                out["error"] = f"write_and_import failed: {type(e).__name__}: {e}"
                return out
            # Persist row
            import uuid
            item_id = str(uuid.uuid4())
            now = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())
            with _conn() as c:
                c.execute("""
                    INSERT INTO forge_items
                      (id, name, item_type, description, source_code, file_path,
                       status, tenant_id, critic_verdict, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (item_id, name, "function",
                      description or "(code-direct deploy)", code,
                      str(file_path), "active", TENANT,
                      "skipped_code_direct", now, now))
            out["item_id"] = item_id
            out["file_path"] = str(file_path)
            out["status"] = "active"
            out["mode"] = "code_direct"
            out["ok"] = True
            return out

        # Description-driven path (LLM via forge)
        r = fe.create(description=description, item_type="function",
                       name=name, tenant_id=TENANT)
        if not r.get("ok"):
            out["error"] = f"forge.create: {r.get('error') or r.get('reason')}"
            return out
        out["item_id"] = r.get("item_id") or r.get("id")
        out["status"] = r.get("status")
        out["mode"] = "forge_llm"
        out["source_preview"] = (r.get("source_code") or "")[:160]
        out["ok"] = True
        return out
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"; return out


# ── F.2 test_backend_function ─────────────────────────────────────────────

def test_backend_function(function_name: str,
                          payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    out: Dict[str, Any] = {"ok": False, "function_name": function_name, "error": None}
    try:
        if not function_name: out["error"] = "empty function_name"; return out
        payload = payload or {}
        if not isinstance(payload, dict):
            out["error"] = "payload must be a dict"; return out
        fe = _fe.get_forge()
        t0 = time.time()
        r = fe.invoke(name=function_name, args=payload, tenant_id=TENANT)
        wall_ms = int((time.time() - t0) * 1000)
        out["wall_ms"] = wall_ms
        out["payload"] = payload
        # ForgeEngine.invoke returns {error: "..."} on fail, otherwise the result dict directly.
        # Check the error key explicitly — no 'ok' key in contract.
        if isinstance(r, dict) and r.get("error"):
            out["error"] = r["error"]
            _log_invocation(function_name, "fail", wall_ms, out["error"])
        else:
            out["result"] = r
            out["ok"] = True
            _log_invocation(function_name, "ok", wall_ms)
        return out
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"; return out


# ── F.3 delete_backend_function ───────────────────────────────────────────

def delete_backend_function(function_name: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {"ok": False, "function_name": function_name,
                            "deleted": False, "error": None}
    try:
        if not function_name: out["error"] = "empty function_name"; return out
        # Find by name in our tenant
        with _conn() as c:
            row = c.execute(
                "SELECT id, file_path FROM forge_items WHERE name = ? AND tenant_id = ?",
                (function_name.strip(), TENANT),
            ).fetchone()
        if not row:
            out["error"] = f"function {function_name!r} not found in tenant '{TENANT}'"
            return out
        fe = _fe.get_forge()
        r = fe.delete_item(item_id=row["id"], tenant_id=TENANT)
        # ForgeEngine.delete_item returns {"status": "deleted", "id": ...} on success
        if isinstance(r, dict) and r.get("status") == "deleted":
            out["item_id"] = row["id"]
            out["file_path"] = row["file_path"]
            out["deleted"] = True
            out["ok"] = True
        else:
            out["error"] = (r or {}).get("error") or "delete failed"
        return out
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"; return out


# ── F.4 get_backend_function_logs ─────────────────────────────────────────

def get_backend_function_logs(function_name: str, *,
                              limit: int = 50) -> Dict[str, Any]:
    out: Dict[str, Any] = {"ok": False, "function_name": function_name,
                            "entries": [], "error": None}
    try:
        if not function_name: out["error"] = "empty function_name"; return out
        limit = max(1, min(500, int(limit)))
        if not LOG_PATH.exists():
            out["ok"] = True; out["count"] = 0
            return out
        entries: List[Dict[str, Any]] = []
        with LOG_PATH.open() as f:
            for line in f:
                try:
                    entry = json.loads(line)
                except Exception:
                    continue
                if entry.get("name") == function_name:
                    entries.append(entry)
        # Newest first
        entries = entries[-limit:][::-1]
        out["entries"] = entries
        out["count"] = len(entries)
        out["ok"] = True
        return out
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"; return out


def list_backend_functions(*, limit: int = 100) -> Dict[str, Any]:
    """Bonus: list every superagent-tenant function deployed."""
    out: Dict[str, Any] = {"ok": False, "functions": [], "error": None}
    try:
        fe = _fe.get_forge()
        items = fe.list_items(tenant_id=TENANT) or []
        items = [it for it in items if it.get("status") == "active"]
        out["functions"] = [
            {"id": it.get("id"), "name": it.get("name"),
             "item_type": it.get("item_type"), "status": it.get("status"),
             "created_at": it.get("created_at")}
            for it in items[:limit]
        ]
        out["count"] = len(out["functions"])
        out["ok"] = True
        return out
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"; return out


# ── Executor wrappers ─────────────────────────────────────────────────────

def execute_deploy_backend_function(**kwargs) -> Dict[str, Any]:
    return deploy_backend_function(
        function_name=kwargs.get("function_name", ""),
        code=kwargs.get("code"),
        description=kwargs.get("description"),
    )

def execute_test_backend_function(**kwargs) -> Dict[str, Any]:
    return test_backend_function(
        function_name=kwargs.get("function_name", ""),
        payload=kwargs.get("payload") or {},
    )

def execute_delete_backend_function(**kwargs) -> Dict[str, Any]:
    return delete_backend_function(function_name=kwargs.get("function_name", ""))

def execute_get_backend_function_logs(**kwargs) -> Dict[str, Any]:
    return get_backend_function_logs(
        function_name=kwargs.get("function_name", ""),
        limit=int(kwargs.get("limit", 50)),
    )

def execute_list_backend_functions(**kwargs) -> Dict[str, Any]:
    return list_backend_functions(limit=int(kwargs.get("limit", 100)))
