"""Caps C.9 + C.10 + C.11 + C.12 — dynamic entity CRUD + schemas.

Mirrors Base44's entity model:
  - Every entity has a JSON schema (properties + type).
  - Every record auto-gets id, created_date, updated_date, created_by.
  - Filter, paginate, sort, project.

Storage: /var/lib/murphy-production/entities.db
  __schemas table  — schema definitions per entity name
  entity__<name>   — one table per entity, JSON column for record body

Surfaces:
  C.9   create_entity_records(entity_name, data: list[dict])
  C.10  update_entities(entity_name, query, data)
  C.11  delete_entities(entity_name, query)
  C.12  manage_entity_schemas(action='list'|'create'|'update'|'delete', ...)
  bonus read_entities(entity_name, query=None, limit, skip, sort, fields)

Schema format example (Base44 shape):
  {
    "type": "object",
    "properties": {
      "name":   {"type": "string"},
      "status": {"type": "string", "enum": ["Active", "Done"]},
      "price":  {"type": "number"}
    },
    "required": ["name"]
  }
"""
from __future__ import annotations
import json
import re
import sqlite3
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

DB = "/var/lib/murphy-production/entities.db"

ALLOWED_TYPES = {"string", "number", "integer", "boolean", "object", "array"}
NAME_RE = re.compile(r"^[A-Z][A-Za-z0-9]{0,63}$")
MAX_RECORDS_BULK = 500
DEFAULT_LIMIT = 50
MAX_LIMIT = 500


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB, timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("""
        CREATE TABLE IF NOT EXISTS __schemas (
            name        TEXT PRIMARY KEY,
            schema_json TEXT NOT NULL,
            created_at  TEXT NOT NULL,
            updated_at  TEXT NOT NULL
        )
    """)
    return c


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())


def _table(name: str) -> str:
    return f"entity__{name}"


def _ensure_table(c: sqlite3.Connection, name: str) -> None:
    c.execute(f"""
        CREATE TABLE IF NOT EXISTS {_table(name)} (
            id           TEXT PRIMARY KEY,
            body         TEXT NOT NULL,
            created_date TEXT NOT NULL,
            updated_date TEXT NOT NULL,
            created_by   TEXT
        )
    """)


def _validate_schema(schema: Dict[str, Any]) -> Optional[str]:
    if not isinstance(schema, dict):
        return "schema must be an object"
    if schema.get("type") not in (None, "object"):
        return "schema.type must be 'object' or omitted"
    props = schema.get("properties", {})
    if not isinstance(props, dict):
        return "schema.properties must be an object"
    for k, v in props.items():
        if not isinstance(v, dict) or v.get("type") not in ALLOWED_TYPES:
            return f"property {k!r}: type must be one of {sorted(ALLOWED_TYPES)}"
    required = schema.get("required") or []
    if not isinstance(required, list):
        return "schema.required must be a list"
    return None


def _validate_record(record: Dict[str, Any], schema: Dict[str, Any]) -> Optional[str]:
    if not isinstance(record, dict):
        return "record must be a dict"
    props = schema.get("properties") or {}
    required = schema.get("required") or []
    for k in required:
        if k not in record:
            return f"missing required field: {k}"
    for k, v in record.items():
        if k in props:
            expected = props[k].get("type")
            if expected == "string" and not isinstance(v, str):
                return f"{k}: expected string, got {type(v).__name__}"
            if expected == "number" and not isinstance(v, (int, float)):
                return f"{k}: expected number, got {type(v).__name__}"
            if expected == "integer" and not isinstance(v, int):
                return f"{k}: expected integer, got {type(v).__name__}"
            if expected == "boolean" and not isinstance(v, bool):
                return f"{k}: expected boolean, got {type(v).__name__}"
            if expected == "array" and not isinstance(v, list):
                return f"{k}: expected array, got {type(v).__name__}"
            if expected == "object" and not isinstance(v, dict):
                return f"{k}: expected object, got {type(v).__name__}"
            enum = props[k].get("enum")
            if enum and v not in enum:
                return f"{k}: value {v!r} not in enum {enum}"
    return None


def _get_schema(c: sqlite3.Connection, name: str) -> Optional[Dict[str, Any]]:
    row = c.execute("SELECT schema_json FROM __schemas WHERE name = ?", (name,)).fetchone()
    return json.loads(row["schema_json"]) if row else None


# ── C.12  manage_entity_schemas ───────────────────────────────────────────

def manage_entity_schemas(
    action: str,
    *,
    entity_name: Optional[str] = None,
    schema: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {"ok": False, "action": action, "error": None}
    try:
        action = (action or "").strip().lower()
        if action not in {"list", "create", "update", "delete"}:
            out["error"] = f"invalid action: {action}"; return out

        with _conn() as c:
            if action == "list":
                rows = c.execute(
                    "SELECT name, schema_json, created_at, updated_at FROM __schemas ORDER BY name"
                ).fetchall()
                out["entities"] = [
                    {"name": r["name"], "schema": json.loads(r["schema_json"]),
                     "created_at": r["created_at"], "updated_at": r["updated_at"],
                     "record_count": c.execute(f"SELECT count(*) FROM {_table(r['name'])}").fetchone()[0]
                     if c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                                   (_table(r['name']),)).fetchone() else 0}
                    for r in rows
                ]
                out["count"] = len(out["entities"])
                out["ok"] = True
                return out

            if not entity_name:
                out["error"] = "entity_name required for create/update/delete"; return out
            if not NAME_RE.match(entity_name):
                out["error"] = "entity_name must be PascalCase alphanumeric (1-64 chars)"; return out

            if action == "create":
                if not schema:
                    out["error"] = "schema required for create"; return out
                err = _validate_schema(schema)
                if err: out["error"] = f"schema invalid: {err}"; return out
                if c.execute("SELECT 1 FROM __schemas WHERE name = ?", (entity_name,)).fetchone():
                    out["error"] = f"entity {entity_name!r} already exists"; return out
                now = _now()
                c.execute(
                    "INSERT INTO __schemas(name, schema_json, created_at, updated_at) VALUES (?, ?, ?, ?)",
                    (entity_name, json.dumps(schema), now, now),
                )
                _ensure_table(c, entity_name)
                out["entity_name"] = entity_name
                out["ok"] = True
                return out

            if action == "update":
                if not schema:
                    out["error"] = "schema required for update"; return out
                err = _validate_schema(schema)
                if err: out["error"] = f"schema invalid: {err}"; return out
                cur = c.execute(
                    "UPDATE __schemas SET schema_json = ?, updated_at = ? WHERE name = ?",
                    (json.dumps(schema), _now(), entity_name),
                )
                if cur.rowcount == 0:
                    out["error"] = f"entity {entity_name!r} not found"; return out
                out["entity_name"] = entity_name
                out["ok"] = True
                return out

            if action == "delete":
                # Refuse if any records exist
                tbl = _table(entity_name)
                if c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (tbl,)).fetchone():
                    cnt = c.execute(f"SELECT count(*) FROM {tbl}").fetchone()[0]
                    if cnt > 0:
                        out["error"] = f"refusing delete: {cnt} records exist (delete records first)"; return out
                    c.execute(f"DROP TABLE {tbl}")
                cur = c.execute("DELETE FROM __schemas WHERE name = ?", (entity_name,))
                if cur.rowcount == 0:
                    out["error"] = f"entity {entity_name!r} not found"; return out
                out["entity_name"] = entity_name
                out["ok"] = True
                return out
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"; return out
    return out


# ── C.9  create_entity_records ────────────────────────────────────────────

def create_entity_records(entity_name: str, data: List[Dict[str, Any]],
                          *, created_by: str = "superagent") -> Dict[str, Any]:
    out: Dict[str, Any] = {"ok": False, "entity_name": entity_name, "ids": [], "error": None}
    try:
        if not entity_name: out["error"] = "empty entity_name"; return out
        if not isinstance(data, list): out["error"] = "data must be a list of dicts"; return out
        if not data: out["error"] = "empty data list"; return out
        if len(data) > MAX_RECORDS_BULK:
            out["error"] = f"bulk limit exceeded ({len(data)} > {MAX_RECORDS_BULK})"; return out

        with _conn() as c:
            schema = _get_schema(c, entity_name)
            if not schema: out["error"] = f"entity {entity_name!r} has no schema"; return out
            _ensure_table(c, entity_name)
            now = _now()
            for i, record in enumerate(data):
                err = _validate_record(record, schema)
                if err:
                    out["error"] = f"record[{i}]: {err}"
                    return out
                rid = str(uuid.uuid4())
                c.execute(
                    f"INSERT INTO {_table(entity_name)}(id, body, created_date, updated_date, created_by) "
                    f"VALUES (?, ?, ?, ?, ?)",
                    (rid, json.dumps(record), now, now, created_by),
                )
                out["ids"].append(rid)
        out["count"] = len(out["ids"])
        out["ok"] = True
        return out
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"; return out


# ── read_entities (bonus, since C.9-C.12 are useless without read) ────────

def read_entities(entity_name: str, *, query: Optional[Dict[str, Any]] = None,
                  limit: int = DEFAULT_LIMIT, skip: int = 0,
                  sort: Optional[str] = None,
                  fields: Optional[List[str]] = None) -> Dict[str, Any]:
    out: Dict[str, Any] = {"ok": False, "entity_name": entity_name, "results": [], "error": None}
    try:
        limit = max(1, min(MAX_LIMIT, int(limit)))
        skip = max(0, int(skip))
        with _conn() as c:
            if not _get_schema(c, entity_name):
                out["error"] = f"entity {entity_name!r} has no schema"; return out
            _ensure_table(c, entity_name)
            # Pull all then filter in Python (simple, fine at small N)
            rows = c.execute(
                f"SELECT id, body, created_date, updated_date, created_by FROM {_table(entity_name)}"
            ).fetchall()
        records: List[Dict[str, Any]] = []
        for r in rows:
            body = json.loads(r["body"])
            rec = {"id": r["id"], **body,
                   "created_date": r["created_date"],
                   "updated_date": r["updated_date"],
                   "created_by":   r["created_by"]}
            if query:
                if not all(rec.get(k) == v for k, v in query.items()):
                    continue
            records.append(rec)
        # Sort
        if sort:
            reverse = sort.startswith("-")
            key = sort.lstrip("-")
            records.sort(key=lambda x: (x.get(key) is None, x.get(key)), reverse=reverse)
        total = len(records)
        records = records[skip:skip + limit]
        # Field projection
        if fields:
            records = [{k: rec.get(k) for k in fields if k in rec} for rec in records]
        out["results"] = records
        out["total"] = total
        out["count"] = len(records)
        out["has_more"] = (skip + len(records)) < total
        out["ok"] = True
        return out
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"; return out


# ── C.10  update_entities ─────────────────────────────────────────────────

def update_entities(entity_name: str, query: Dict[str, Any],
                    data: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {"ok": False, "entity_name": entity_name, "updated_count": 0, "error": None}
    try:
        if not entity_name: out["error"] = "empty entity_name"; return out
        if not isinstance(query, dict) or not query:
            out["error"] = "query must be a non-empty dict"; return out
        if not isinstance(data, dict) or not data:
            out["error"] = "data must be a non-empty dict"; return out

        with _conn() as c:
            schema = _get_schema(c, entity_name)
            if not schema: out["error"] = f"entity {entity_name!r} has no schema"; return out

            # Read all rows, filter, write back updated
            rows = c.execute(
                f"SELECT id, body FROM {_table(entity_name)}"
            ).fetchall()
            now = _now()
            updated = 0
            for r in rows:
                body = json.loads(r["body"])
                rec_view = {"id": r["id"], **body}
                if not all(rec_view.get(k) == v for k, v in query.items()):
                    continue
                # Apply update
                new_body = {**body, **data}
                # Drop any auto fields from data side
                for auto in ("id", "created_date", "updated_date", "created_by"):
                    new_body.pop(auto, None)
                err = _validate_record(new_body, schema)
                if err:
                    out["error"] = f"id={r['id']}: {err}"
                    return out
                c.execute(
                    f"UPDATE {_table(entity_name)} SET body = ?, updated_date = ? WHERE id = ?",
                    (json.dumps(new_body), now, r["id"]),
                )
                updated += 1
        out["updated_count"] = updated
        out["ok"] = True
        return out
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"; return out


# ── C.11  delete_entities ─────────────────────────────────────────────────

def delete_entities(entity_name: str, query: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {"ok": False, "entity_name": entity_name, "deleted_count": 0, "error": None}
    try:
        if not entity_name: out["error"] = "empty entity_name"; return out
        if not isinstance(query, dict) or not query:
            out["error"] = "query must be a non-empty dict (safety guard)"; return out

        with _conn() as c:
            if not _get_schema(c, entity_name):
                out["error"] = f"entity {entity_name!r} has no schema"; return out
            rows = c.execute(
                f"SELECT id, body FROM {_table(entity_name)}"
            ).fetchall()
            to_delete: List[str] = []
            for r in rows:
                body = json.loads(r["body"])
                rec_view = {"id": r["id"], **body}
                if all(rec_view.get(k) == v for k, v in query.items()):
                    to_delete.append(r["id"])
            for rid in to_delete:
                c.execute(f"DELETE FROM {_table(entity_name)} WHERE id = ?", (rid,))
        out["deleted_count"] = len(to_delete)
        out["ok"] = True
        return out
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"; return out


# ── Executor wrappers ─────────────────────────────────────────────────────

def execute_manage_entity_schemas(**kwargs) -> Dict[str, Any]:
    return manage_entity_schemas(
        action=kwargs.get("action", ""),
        entity_name=kwargs.get("entity_name"),
        schema=kwargs.get("schema"),
    )


def execute_create_entity_records(**kwargs) -> Dict[str, Any]:
    return create_entity_records(
        entity_name=kwargs.get("entity_name", ""),
        data=kwargs.get("data") or [],
        created_by=kwargs.get("created_by", "superagent"),
    )


def execute_read_entities(**kwargs) -> Dict[str, Any]:
    return read_entities(
        entity_name=kwargs.get("entity_name", ""),
        query=kwargs.get("query"),
        limit=int(kwargs.get("limit", DEFAULT_LIMIT)),
        skip=int(kwargs.get("skip", 0)),
        sort=kwargs.get("sort"),
        fields=kwargs.get("fields"),
    )


def execute_update_entities(**kwargs) -> Dict[str, Any]:
    return update_entities(
        entity_name=kwargs.get("entity_name", ""),
        query=kwargs.get("query") or {},
        data=kwargs.get("data") or {},
    )


def execute_delete_entities(**kwargs) -> Dict[str, Any]:
    return delete_entities(
        entity_name=kwargs.get("entity_name", ""),
        query=kwargs.get("query") or {},
    )
