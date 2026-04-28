"""
PATCH-135b — src/automation_request.py
Murphy System — Automation Request Interface

Any agent, org-chart node, or UI component can call:
    request_automation(description, account_id, requester, priority)

This builds a full WorkflowBlueprint, registers the schedule with APScheduler
(if applicable), and returns the blueprint with canvas representation.

Think of it as the "create automation" API that the entire Murphy system
can call — agents, Rosetta, exec_admin, prod_ops, and the UI.

Copyright © 2020-2026 Inoni LLC — Corey Post | License: BSL 1.1
"""
from __future__ import annotations

import logging
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("murphy.automation_request")

_DB_PATH = Path("/var/lib/murphy-production/automations.db")
_lock    = threading.Lock()

# ── DB init ──────────────────────────────────────────────────────────────────

def _get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("""CREATE TABLE IF NOT EXISTS automation_requests (
        request_id   TEXT PRIMARY KEY,
        account_id   TEXT NOT NULL,
        requester    TEXT NOT NULL,          -- 'exec_admin' | 'prod_ops' | 'rosetta' | 'user' | 'ui'
        description  TEXT NOT NULL,
        priority     TEXT DEFAULT 'normal',  -- 'low' | 'normal' | 'high' | 'critical'
        status       TEXT DEFAULT 'pending', -- 'pending' | 'built' | 'scheduled' | 'rejected'
        blueprint_id TEXT,
        schedule_job TEXT,
        roi_usd      REAL,
        created_at   TEXT NOT NULL,
        built_at     TEXT,
        rejection_reason TEXT
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS automation_runs (
        run_id       TEXT PRIMARY KEY,
        workflow_id  TEXT NOT NULL,
        account_id   TEXT NOT NULL,
        status       TEXT NOT NULL,          -- 'running' | 'completed' | 'failed' | 'blocked'
        started_at   TEXT NOT NULL,
        ended_at     TEXT,
        step_log     TEXT,                   -- JSON
        final_output TEXT                    -- JSON
    )""")
    conn.commit()
    return conn


# ── Schedule registration ────────────────────────────────────────────────────

def _register_schedule(blueprint: Dict, account_id: str) -> Optional[str]:
    """
    Register a cron/schedule trigger with APScheduler if the workflow has one.
    Returns job_id or None if no schedule.
    """
    schedule = blueprint.get("schedule", {})
    expr     = schedule.get("expr")
    wf_id    = blueprint.get("workflow_id", blueprint.get("id", ""))
    if not expr or schedule.get("type") == "on_demand":
        return None

    try:
        from src.runtime.app import _scheduler  # APScheduler instance
        job_id   = f"wf_{wf_id[:8]}"
        steps    = blueprint.get("steps", [])

        def _run_workflow():
            from src.workflow_executor import execute_workflow
            from src.automation_request import _save_run
            ctx = execute_workflow(steps, wf_id, account_id, {"cron_fired": True})
            _save_run(ctx)

        # Remove any existing job with same id
        try:
            _scheduler.remove_job(job_id)
        except Exception:
            pass

        _scheduler.add_job(
            _run_workflow,
            "cron",
            id=job_id,
            **_parse_cron(expr),
            replace_existing=True,
            max_instances=1,
        )
        logger.info("Registered schedule job %s for workflow %s | cron=%s", job_id, wf_id, expr)
        return job_id
    except Exception as e:
        logger.error("Schedule registration failed: %s", e)
        return None


def _parse_cron(expr: str) -> Dict:
    """Convert 5-field cron expression to APScheduler kwargs."""
    parts = expr.strip().split()
    if len(parts) != 5:
        return {"minute": "0", "hour": "9"}
    minute, hour, day, month, day_of_week = parts
    return {
        "minute":      minute,
        "hour":        hour,
        "day":         day,
        "month":       month,
        "day_of_week": day_of_week,
    }


# ── Run persistence ──────────────────────────────────────────────────────────

def _save_run(ctx) -> None:
    """Persist a completed StepContext to automation_runs."""
    import json
    with _lock:
        conn = _get_db()
        try:
            conn.execute("""INSERT OR REPLACE INTO automation_runs
                (run_id, workflow_id, account_id, status, started_at, ended_at, step_log, final_output)
                VALUES (?,?,?,?,?,?,?,?)""",
                (ctx.run_id, ctx.workflow_id, ctx.account_id, ctx.status,
                 ctx.started_at, datetime.now(timezone.utc).isoformat(),
                 json.dumps(ctx.log), json.dumps(ctx.get("final_output", {}))))
            conn.commit()
        finally:
            conn.close()


# ── Core: request_automation ─────────────────────────────────────────────────

def request_automation(
    description:  str,
    account_id:   str,
    requester:    str = "user",
    priority:     str = "normal",
    context:      Dict = None,
    auto_schedule: bool = True,
) -> Dict:
    """
    Primary entry point for creating an automation from any source.

    Parameters
    ----------
    description  : Natural language description of the automation needed
    account_id   : Tenant account ID
    requester    : Who is requesting ('exec_admin' | 'prod_ops' | 'rosetta' | 'user' | 'ui')
    priority     : 'low' | 'normal' | 'high' | 'critical'
    context      : Optional dict of additional context (signals, org chart info, etc.)
    auto_schedule: If True and the blueprint has a cron, register it with APScheduler

    Returns
    -------
    {
        "success": bool,
        "request_id": str,
        "blueprint": {...},          # Full WorkflowBlueprint dict
        "canvas_nodes": [...],       # Canvas-ready nodes for UI
        "canvas_edges": [...],       # Canvas-ready edges for UI
        "schedule_job": str | None,  # APScheduler job ID if scheduled
        "roi": {...},                # ROI estimate
        "requester": str,
        "status": "built" | "scheduled"
    }
    """
    request_id = str(uuid.uuid4())[:12]
    logger.info("[AUTOMATION-REQ] %s | requester=%s | priority=%s | desc=%.80s",
                request_id, requester, priority, description)

    # ── PCC / harm check ──────────────────────────────────────────────────────
    try:
        from src.pcc import get_pcc
        pcc    = get_pcc()
        check  = pcc.check("automation_request",
                            {"description": description, "requester": requester,
                             "priority": priority, **(context or {})})
        if not check.get("allowed", True):
            reason = check.get("reason", "PCC blocked this automation request")
            logger.warning("[AUTOMATION-REQ] %s BLOCKED by PCC: %s", request_id, reason)
            return {"success": False, "error": reason, "blocked_by": "pcc",
                    "request_id": request_id}
    except Exception as e:
        logger.debug("PCC check skipped: %s", e)

    # ── Build blueprint via NLWorkflowEngine ──────────────────────────────────
    try:
        from src.nl_workflow_engine import get_engine
        engine    = get_engine()
        blueprint = engine.build(description, account_id, context=context or {})
    except Exception as e:
        logger.error("[AUTOMATION-REQ] %s blueprint build failed: %s", request_id, e)
        return {"success": False, "error": f"Blueprint build failed: {e}",
                "request_id": request_id}

    bp_dict   = blueprint.to_dict() if hasattr(blueprint, "to_dict") else blueprint
    canvas    = blueprint.to_canvas_payload() if hasattr(blueprint, "to_canvas_payload") else {}
    roi       = blueprint.to_roi_event() if hasattr(blueprint, "to_roi_event") else {}

    # ── ROI gate: must save more than it costs ─────────────────────────────────
    roi_ratio = bp_dict.get("roi", {}).get("roi_ratio", 1.0)
    if roi_ratio < 1.0 and priority not in ("high", "critical"):
        logger.warning("[AUTOMATION-REQ] %s ROI below 1.0 (%.2f) — rejecting normal/low priority",
                       request_id, roi_ratio)
        return {"success": False, "error": "Automation ROI < 1.0 — would cost more than it saves",
                "roi": roi, "request_id": request_id}

    # ── Register schedule ──────────────────────────────────────────────────────
    schedule_job = None
    if auto_schedule:
        schedule_job = _register_schedule(bp_dict, account_id)

    status = "scheduled" if schedule_job else "built"

    # ── Persist request record ────────────────────────────────────────────────
    with _lock:
        conn = _get_db()
        try:
            conn.execute("""INSERT INTO automation_requests
                (request_id, account_id, requester, description, priority, status,
                 blueprint_id, schedule_job, roi_usd, created_at, built_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (request_id, account_id, requester, description, priority, status,
                 bp_dict.get("workflow_id", bp_dict.get("id", "")),
                 schedule_job,
                 roi.get("savings_usd", 0),
                 datetime.now(timezone.utc).isoformat(),
                 datetime.now(timezone.utc).isoformat()))
            conn.commit()
        finally:
            conn.close()

    logger.info("[AUTOMATION-REQ] %s BUILT | status=%s | job=%s | roi_ratio=%.1f",
                request_id, status, schedule_job, roi_ratio)

    return {
        "success":      True,
        "request_id":   request_id,
        "blueprint":    bp_dict,
        "canvas_nodes": canvas.get("nodes", []),
        "canvas_edges": canvas.get("edges", []),
        "schedule_job": schedule_job,
        "roi":          roi,
        "requester":    requester,
        "status":       status,
        "canvas_url":   f"/ui/forge?view=canvas&workflow_id={bp_dict.get('workflow_id', '')}",
    }


# ── List requests ─────────────────────────────────────────────────────────────

def list_requests(account_id: str, limit: int = 50) -> List[Dict]:
    conn = _get_db()
    try:
        rows = conn.execute("""SELECT * FROM automation_requests
            WHERE account_id = ? ORDER BY created_at DESC LIMIT ?""",
            (account_id, limit)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def list_runs(account_id: str, limit: int = 50) -> List[Dict]:
    import json
    conn = _get_db()
    try:
        rows = conn.execute("""SELECT * FROM automation_runs
            WHERE account_id = ? ORDER BY started_at DESC LIMIT ?""",
            (account_id, limit)).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            try:
                d["step_log"] = json.loads(d.get("step_log") or "[]")
            except Exception:
                d["step_log"] = []
            try:
                d["final_output"] = json.loads(d.get("final_output") or "{}")
            except Exception:
                d["final_output"] = {}
            result.append(d)
        return result
    finally:
        conn.close()


# ── Singleton convenience ─────────────────────────────────────────────────────

def get_automation_manager():
    """Return a simple namespace with the public functions."""
    class _AM:
        request = staticmethod(request_automation)
        list_requests = staticmethod(list_requests)
        list_runs = staticmethod(list_runs)
        save_run  = staticmethod(_save_run)
    return _AM()
