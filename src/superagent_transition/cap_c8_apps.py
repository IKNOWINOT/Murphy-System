"""Cap C.8 — list_user_apps + cross-app read_entities.

Murphy IS one app (Murphy.systems / Inoni LLC) but has internal
"pillars" (subsystems) registered in murphy_registry.db. This cap
treats each pillar as an app for Base44 contract parity.

Also enumerates every *.db in /var/lib/murphy-production/ as a
data source the user can read entities from cross-app.

Surfaces:
  list_user_apps()  — pillars + standalone databases
  read_entities_cross_app(app_id, entity_name, limit, skip, query)
"""
from __future__ import annotations
import json
import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

REGISTRY_DB = "/var/lib/murphy-production/murphy_registry.db"
DB_ROOT = Path("/var/lib/murphy-production")


def _safe_query(db_path: str, sql: str, args=()) -> List[Dict[str, Any]]:
    try:
        c = sqlite3.connect(db_path, timeout=5)
        c.row_factory = sqlite3.Row
        rows = c.execute(sql, args).fetchall()
        c.close()
        return [dict(r) for r in rows]
    except Exception:
        return []


def list_user_apps() -> Dict[str, Any]:
    out: Dict[str, Any] = {"ok": False, "apps": [], "error": None}
    try:
        apps: List[Dict[str, Any]] = []

        # Murphy itself
        apps.append({
            "app_id": "murphy_system",
            "name": "Murphy / Inoni LLC",
            "type": "platform",
            "description": "Autonomous AI business platform — the host app",
            "database_path": "/var/lib/murphy-production",
        })

        # Pillars from registry
        pillars = _safe_query(REGISTRY_DB,
            "SELECT pillar_id, name, description FROM registry_pillars")
        for p in pillars:
            apps.append({
                "app_id": f"pillar_{p.get('pillar_id', p.get('name','?'))}",
                "name": p.get("name") or p.get("pillar_id"),
                "type": "pillar",
                "description": p.get("description") or "",
            })

        # Notable standalone databases (sample — not exhaustive)
        notable = ["crm.db", "investment.db", "forge.db", "entities.db",
                   "agent_substrate.db", "function_registry.db",
                   "entity_graph.db", "automations.db"]
        for db_name in notable:
            db_path = DB_ROOT / db_name
            if db_path.exists():
                tables = _safe_query(str(db_path),
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name LIMIT 50")
                apps.append({
                    "app_id": f"db_{db_name.replace('.db','')}",
                    "name": db_name.replace(".db","").replace("_"," ").title(),
                    "type": "database",
                    "database_path": str(db_path),
                    "table_count": len(tables),
                    "tables": [t["name"] for t in tables][:20],
                })

        out["apps"] = apps
        out["count"] = len(apps)
        out["ok"] = True
        return out
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"; return out


def read_entities_cross_app(app_id: str, entity_name: str,
                            limit: int = 50, skip: int = 0,
                            query: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    out: Dict[str, Any] = {"ok": False, "results": [], "error": None}
    try:
        if not app_id or not entity_name:
            out["error"] = "app_id and entity_name required"; return out
        limit = max(1, min(500, int(limit)))
        skip = max(0, int(skip))

        # Resolve app_id → db_path
        if app_id.startswith("db_"):
            db_path = DB_ROOT / f"{app_id[3:]}.db"
        elif app_id == "murphy_system":
            db_path = DB_ROOT / "murphy_registry.db"
        else:
            out["error"] = f"unknown app_id pattern: {app_id} (must be 'db_*' or 'murphy_system')"
            return out

        if not db_path.exists():
            out["error"] = f"database not found: {db_path}"; return out

        # Validate table exists
        tables = _safe_query(str(db_path),
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (entity_name,))
        if not tables:
            out["error"] = f"entity {entity_name!r} not found in {app_id}"
            # Help with hint
            avail = _safe_query(str(db_path),
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' LIMIT 20")
            out["available_entities"] = [t["name"] for t in avail]
            return out

        # Build WHERE
        where_sql = ""; args: List[Any] = []
        if query:
            clauses = []
            for k, v in query.items():
                # Light identifier guard
                if not k.replace("_","").isalnum():
                    out["error"] = f"invalid query key: {k}"; return out
                clauses.append(f'"{k}" = ?'); args.append(v)
            if clauses:
                where_sql = " WHERE " + " AND ".join(clauses)

        sql = f'SELECT * FROM "{entity_name}"{where_sql} LIMIT ? OFFSET ?'
        args.extend([limit, skip])
        rows = _safe_query(str(db_path), sql, tuple(args))

        # Total
        count_sql = f'SELECT count(*) AS n FROM "{entity_name}"{where_sql}'
        total_rows = _safe_query(str(db_path), count_sql, tuple(args[:-2] if where_sql else ()))
        total = total_rows[0]["n"] if total_rows else len(rows)

        out["app_id"] = app_id
        out["entity_name"] = entity_name
        out["results"] = rows
        out["count"] = len(rows)
        out["total"] = total
        out["has_more"] = (skip + len(rows)) < total
        out["ok"] = True
        return out
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"; return out


def execute_list_user_apps(**kwargs) -> Dict[str, Any]:
    return list_user_apps()

def execute_read_entities_cross_app(**kwargs) -> Dict[str, Any]:
    return read_entities_cross_app(
        app_id=kwargs.get("app_id", ""),
        entity_name=kwargs.get("entity_name", ""),
        limit=int(kwargs.get("limit", 50)),
        skip=int(kwargs.get("skip", 0)),
        query=kwargs.get("query"),
    )
