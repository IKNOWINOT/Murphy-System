"""Caps D.1 + D.2 + D.3 — automation CRUD.

Reads/writes Murphy's existing automations.db (67+ rows of real
history from exec_admin, user, rosetta, steve-test).

Schema we touch (already there):
  automation_requests(request_id PK, account_id, requester,
                       description, priority, status, blueprint_id,
                       schedule_job, roi_usd, created_at, built_at,
                       rejection_reason)

Surfaces:
  D.1:  create_automation(description, schedule, ...)
  D.2:  list_automations(status=None, page=1, page_size=20)
  D.3:  manage_automation(request_id, action='update'|'archive'|
                          'unarchive'|'toggle', ...)

NOT shipped in this round (honest):
  D.4 trigger conditions — Murphy has scattered gates, no unified
  conditional layer. Audit-only.
  D.5 handler dispatch — BLOCKED on BL-R9 (no live consumer of
  proposal queue). Already tracked.

Soft delete semantics:
  Schema has no `archived` column. We use status='archived' as the
  sentinel. unarchive restores to status='pending'.
"""
from __future__ import annotations
import sqlite3
import time
import uuid
from typing import Any, Dict, List, Optional

DB = "/var/lib/murphy-production/automations.db"
VALID_PRIORITIES = {"low", "normal", "high", "critical"}
VALID_STATUSES = {"pending", "built", "scheduled", "rejected", "archived"}
VALID_REQUESTERS = {"exec_admin", "prod_ops", "rosetta", "user", "ui", "superagent"}
ARCHIVE_STATUS = "archived"
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB, timeout=10)
    c.row_factory = sqlite3.Row
    return c


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())


def create_automation(
    description: str,
    *,
    requester: str = "superagent",
    account_id: str = "platform_legacy",
    priority: str = "normal",
    schedule_job: Optional[str] = None,
    blueprint_id: Optional[str] = None,
    roi_usd: Optional[float] = None,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {"ok": False, "request_id": None, "error": None}
    try:
        if not description or not description.strip():
            out["error"] = "empty description"; return out
        if priority not in VALID_PRIORITIES:
            out["error"] = f"invalid priority: {priority}"; return out
        if requester not in VALID_REQUESTERS:
            out["error"] = f"invalid requester: {requester}"; return out
        if len(description) > 4000:
            out["error"] = "description too long (>4000)"; return out

        rid = str(uuid.uuid4())
        status = "scheduled" if schedule_job else "pending"
        with _conn() as c:
            c.execute("""
                INSERT INTO automation_requests
                  (request_id, account_id, requester, description, priority,
                   status, blueprint_id, schedule_job, roi_usd, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (rid, account_id, requester, description.strip(), priority,
                  status, blueprint_id, schedule_job, roi_usd, _now()))
        out["request_id"] = rid
        out["status"] = status
        out["requester"] = requester
        out["priority"] = priority
        out["ok"] = True
        return out
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"; return out


def list_automations(
    *,
    status: Optional[str] = None,
    requester: Optional[str] = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {"ok": False, "results": [], "error": None}
    try:
        page = max(1, int(page))
        page_size = max(1, min(MAX_PAGE_SIZE, int(page_size)))
        offset = (page - 1) * page_size
        where: List[str] = []
        params: List[Any] = []
        if status:
            if status not in VALID_STATUSES:
                out["error"] = f"invalid status filter: {status}"; return out
            where.append("status = ?"); params.append(status)
        if requester:
            where.append("requester = ?"); params.append(requester)
        wclause = (" WHERE " + " AND ".join(where)) if where else ""

        with _conn() as c:
            total = c.execute(
                f"SELECT count(*) FROM automation_requests{wclause}", params,
            ).fetchone()[0]
            rows = c.execute(f"""
                SELECT request_id, requester, description, priority, status,
                       schedule_job, blueprint_id, created_at, built_at
                FROM automation_requests{wclause}
                ORDER BY created_at DESC LIMIT ? OFFSET ?
            """, params + [page_size, offset]).fetchall()
        for r in rows:
            out["results"].append({
                "request_id":   r["request_id"],
                "requester":    r["requester"],
                "description":  r["description"],
                "priority":     r["priority"],
                "status":       r["status"],
                "schedule_job": r["schedule_job"],
                "blueprint_id": r["blueprint_id"],
                "created_at":   r["created_at"],
                "built_at":     r["built_at"],
            })
        # Status histogram (cheap, useful)
        hist: Dict[str, int] = {}
        with _conn() as c:
            for s, cnt in c.execute(
                f"SELECT status, count(*) FROM automation_requests{wclause} GROUP BY status",
                params,
            ).fetchall():
                hist[s] = cnt
        out["status_histogram"] = hist
        out["total"] = total
        out["has_more"] = (offset + len(rows)) < total
        out["count"] = len(rows)
        out["page"] = page
        out["ok"] = True
        return out
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"; return out


def _fetch_one(request_id: str) -> Optional[sqlite3.Row]:
    with _conn() as c:
        return c.execute(
            "SELECT * FROM automation_requests WHERE request_id = ?",
            (request_id,),
        ).fetchone()


def manage_automation(
    request_id: str,
    action: str,
    *,
    description: Optional[str] = None,
    priority: Optional[str] = None,
    schedule_job: Optional[str] = None,
    rejection_reason: Optional[str] = None,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "ok": False, "request_id": request_id, "action": action, "error": None,
    }
    try:
        if not request_id or not request_id.strip():
            out["error"] = "empty request_id"; return out
        action = (action or "").strip().lower()
        if action not in {"update", "archive", "unarchive", "toggle"}:
            out["error"] = f"invalid action: {action}"; return out

        row = _fetch_one(request_id)
        if not row:
            out["error"] = "request not found"; return out
        out["old_status"] = row["status"]

        sets: List[str] = []
        params: List[Any] = []

        if action == "archive":
            sets.append("status = ?"); params.append(ARCHIVE_STATUS)
            if rejection_reason:
                sets.append("rejection_reason = ?"); params.append(rejection_reason)
        elif action == "unarchive":
            if row["status"] != ARCHIVE_STATUS:
                out["error"] = f"can only unarchive archived rows (status={row['status']})"
                return out
            sets.append("status = ?"); params.append("pending")
            sets.append("rejection_reason = NULL"); # no param
            # Re-form for NULL: use a separate update path
        elif action == "toggle":
            # toggle pending <-> archived as a pause/resume mechanic
            new_status = ARCHIVE_STATUS if row["status"] != ARCHIVE_STATUS else "pending"
            sets.append("status = ?"); params.append(new_status)
        elif action == "update":
            if description is not None:
                if not description.strip():
                    out["error"] = "empty description on update"; return out
                sets.append("description = ?"); params.append(description.strip())
            if priority is not None:
                if priority not in VALID_PRIORITIES:
                    out["error"] = f"invalid priority: {priority}"; return out
                sets.append("priority = ?"); params.append(priority)
            if schedule_job is not None:
                sets.append("schedule_job = ?"); params.append(schedule_job)
            if not sets:
                out["error"] = "update requires at least one field to change"; return out

        # Build SQL — handle the NULL case for unarchive specially
        if action == "unarchive":
            sql = "UPDATE automation_requests SET status = ?, rejection_reason = NULL WHERE request_id = ?"
            params = ["pending", request_id]
        else:
            sql = f"UPDATE automation_requests SET {', '.join(sets)} WHERE request_id = ?"
            params.append(request_id)

        with _conn() as c:
            cur = c.execute(sql, params)
        if cur.rowcount == 0:
            out["error"] = "update affected 0 rows"; return out

        # Read back
        new_row = _fetch_one(request_id)
        out["new_status"] = new_row["status"]
        out["new_description"] = new_row["description"]
        out["new_priority"] = new_row["priority"]
        out["ok"] = True
        return out
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"; return out


# ── Executor wrappers ─────────────────────────────────────────────────────

def execute_create_automation(**kwargs) -> Dict[str, Any]:
    return create_automation(
        description=kwargs.get("description", ""),
        requester=kwargs.get("requester", "superagent"),
        account_id=kwargs.get("account_id", "platform_legacy"),
        priority=kwargs.get("priority", "normal"),
        schedule_job=kwargs.get("schedule_job"),
        blueprint_id=kwargs.get("blueprint_id"),
        roi_usd=kwargs.get("roi_usd"),
    )


def execute_list_automations(**kwargs) -> Dict[str, Any]:
    return list_automations(
        status=kwargs.get("status"),
        requester=kwargs.get("requester"),
        page=int(kwargs.get("page", 1)),
        page_size=int(kwargs.get("page_size", DEFAULT_PAGE_SIZE)),
    )


def execute_manage_automation(**kwargs) -> Dict[str, Any]:
    return manage_automation(
        request_id=kwargs.get("request_id", ""),
        action=kwargs.get("action", ""),
        description=kwargs.get("description"),
        priority=kwargs.get("priority"),
        schedule_job=kwargs.get("schedule_job"),
        rejection_reason=kwargs.get("rejection_reason"),
    )
