"""
PATCH-136 — src/automation_request.py
Murphy System — Automation Request Interface (v2)

Upgraded: LLM-backed NL parsing for cron, trigger, and step sequences.
Any agent, org-chart node, or UI component can call:
    request_automation(description, account_id, requester, priority)

Returns full WorkflowBlueprint with canvas representation, schedule job,
and ROI estimate. Rosetta, exec_admin, and prod_ops call this autonomously.

Copyright © 2020-2026 Inoni LLC — Corey Post | License: BSL 1.1
"""
from __future__ import annotations

import json
import logging
import re
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
        requester    TEXT NOT NULL,
        description  TEXT NOT NULL,
        priority     TEXT DEFAULT 'normal',
        status       TEXT DEFAULT 'pending',
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
        status       TEXT NOT NULL,
        started_at   TEXT NOT NULL,
        ended_at     TEXT,
        step_log     TEXT,
        final_output TEXT
    )""")
    conn.commit()
    return conn


# ── NL → Schedule / Trigger parser ──────────────────────────────────────────

_SCHEDULE_PATTERNS = [
    # daily at specific hour
    (r'daily.{0,10}\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b', 'daily'),
    (r'every\s+day.{0,15}\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b', 'daily'),
    # weekly
    (r'every\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)', 'weekly'),
    (r'weekly\s+on\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)', 'weekly'),
    # hourly
    (r'every\s+(\d+)\s+hour', 'hourly'),
    (r'hourly', 'hourly'),
    # on-demand / triggered
    (r'when\b', 'event'),
    (r'trigger\b', 'event'),
    (r'if\b.{0,20}then\b', 'event'),
    (r'overdue', 'event'),
    (r'new\s+\w+\s+(?:is\s+)?created', 'event'),
    (r'on\s+(?:each|every)\s+new', 'event'),
]

_DOW_MAP = {
    'monday': '1', 'tuesday': '2', 'wednesday': '3',
    'thursday': '4', 'friday': '5', 'saturday': '6', 'sunday': '0'
}


def _parse_nl_schedule(description: str) -> Dict:
    """
    Parse NL description into trigger dict with cron expression.
    Returns:
        {"type": "cron"|"event"|"on_demand", "expr": "0 8 * * *"|None, "label": str}
    """
    desc = description.lower()

    # Event-driven trigger?
    for pattern, kind in _SCHEDULE_PATTERNS:
        if kind == 'event' and re.search(pattern, desc):
            return {"type": "event", "expr": None,
                    "label": "Event-driven",
                    "event_hint": _extract_event_hint(desc)}

    # Daily schedule?
    m = re.search(r'\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b', desc)
    if m and ('daily' in desc or 'every day' in desc or 'each day' in desc or 'morning' in desc or 'night' in desc):
        hour, minute, meridiem = m.group(1), m.group(2) or "00", m.group(3)
        h = int(hour)
        if meridiem == 'pm' and h != 12:
            h += 12
        elif meridiem == 'am' and h == 12:
            h = 0
        expr = f'{minute} {h} * * *'
        return {"type": "cron", "expr": expr, "label": f"Daily at {hour}:{minute} {meridiem.upper()}"}

    # Weekly?
    for day_word, dow in _DOW_MAP.items():
        if day_word in desc:
            m2 = re.search(r'\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b', desc)
            if m2:
                hour, minute, meridiem = m2.group(1), m2.group(2) or "00", m2.group(3)
                h = int(hour)
                if meridiem == 'pm' and h != 12:
                    h += 12
                expr = f'{minute} {h} * * {dow}'
            else:
                expr = f'0 9 * * {dow}'
            return {"type": "cron", "expr": expr, "label": f"Every {day_word.title()}"}

    # Hourly?
    m3 = re.search(r'every\s+(\d+)\s+hour', desc)
    if m3:
        n = m3.group(1)
        expr = f'0 */{n} * * *'
        return {"type": "cron", "expr": expr, "label": f"Every {n} hour(s)"}
    if 'hourly' in desc:
        return {"type": "cron", "expr": "0 * * * *", "label": "Every hour"}

    # Morning shorthand
    if 'morning' in desc or '8am' in desc:
        return {"type": "cron", "expr": "0 8 * * *", "label": "Daily at 8:00 AM"}

    return {"type": "on_demand", "expr": None, "label": "On demand"}


def _extract_event_hint(desc: str) -> str:
    """Extract the event condition from NL."""
    for keyword in ['when ', 'if ', 'trigger ', 'on ']:
        idx = desc.find(keyword)
        if idx >= 0:
            snippet = desc[idx:idx+60].split('then')[0].strip()
            return snippet
    return "condition met"


def _parse_nl_steps(description: str, trigger: Dict) -> List[Dict]:
    """
    Parse NL description into a list of workflow steps with proper types.
    """
    desc  = description.lower()
    steps = []

    # Step 0: trigger node
    if trigger["type"] == "cron":
        steps.append({
            "id": "step_00_trigger",
            "type": "schedule",
            "label": f"Schedule: {trigger['label']}",
            "config": {"cron": trigger.get("expr")},
            "depends_on": []
        })
    elif trigger["type"] == "event":
        steps.append({
            "id": "step_00_trigger",
            "type": "event_trigger",
            "label": f"Event: {trigger.get('event_hint', 'condition met')}",
            "config": {"event": trigger.get("event_hint", "")},
            "depends_on": []
        })
    else:
        steps.append({
            "id": "step_00_trigger",
            "type": "manual",
            "label": "Manual trigger",
            "config": {},
            "depends_on": []
        })

    # Step 1+: action steps based on keywords
    action_keywords = [
        (r'send.{0,20}email',          "send_email",   "Send email notification"),
        (r'email.{0,20}(ceo|manager|team|admin)', "send_email", "Send email to stakeholder"),
        (r'escalat',                   "escalate",     "Escalate to next tier"),
        (r'log.{0,20}(crm|system|db)', "log_record",   "Log record in CRM/system"),
        (r'crm',                       "crm_update",   "Update CRM record"),
        (r'generate.{0,20}report',     "generate_report", "Generate report"),
        (r'summar',                    "summarize",    "Summarize data"),
        (r'collect.{0,20}data',        "fetch_data",   "Fetch data from source"),
        (r'fetch',                     "fetch_data",   "Fetch data from source"),
        (r'notif',                     "notify",       "Send notification"),
        (r'slack',                     "send_slack",   "Send Slack message"),
        (r'webhook',                   "webhook",      "Call webhook"),
        (r'api',                       "api_call",     "Make API call"),
        (r'updat',                     "update_record","Update record"),
        (r'creat',                     "create_record","Create record"),
        (r'block',                     "block_action", "Block / halt action"),
        (r'approv',                    "approval_gate","Wait for approval"),
        (r'invoice',                   "fetch_data",   "Fetch invoice data"),
        (r'payment',                   "payment_action","Process payment action"),
        (r'revenue',                   "fetch_data",   "Fetch revenue data"),
    ]

    seen_types = set()
    prev_id    = "step_00_trigger"
    for i, (pattern, step_type, label) in enumerate(action_keywords):
        if step_type not in seen_types and re.search(pattern, desc):
            step_id = f"step_{i+1:02d}_{step_type}"
            steps.append({
                "id":        step_id,
                "type":      step_type,
                "label":     label,
                "config":    {"auto_configured": True},
                "depends_on": [prev_id]
            })
            seen_types.add(step_type)
            prev_id = step_id

    # Always end with an output/done step if we have actions
    if len(steps) > 1:
        steps.append({
            "id":        "step_final_output",
            "type":      "output",
            "label":     "Complete & log result",
            "config":    {},
            "depends_on": [prev_id]
        })

    return steps


def _steps_to_canvas(steps: List[Dict]) -> Dict:
    """Convert steps to canvas node/edge format for the UI."""
    icon_map = {
        "schedule":      "\u23f0",  # clock
        "event_trigger": "\u26a1",  # lightning
        "manual":        "\U0001f449", # point
        "send_email":    "\U0001f4e7", # email
        "escalate":      "\U0001f6a8", # siren
        "log_record":    "\U0001f4dd", # memo
        "crm_update":    "\U0001f4ca", # chart
        "generate_report":"\U0001f4c8",
        "summarize":     "\U0001f9e0",
        "fetch_data":    "\U0001f310", # globe
        "notify":        "\U0001f514", # bell
        "send_slack":    "\U0001f4ac", # speech
        "webhook":       "\U0001f517", # link
        "api_call":      "\U0001f517",
        "update_record": "\u270f",   # pen
        "create_record": "\u2795",   # plus
        "block_action":  "\u274c",   # X
        "approval_gate": "\u2705",   # check
        "payment_action":"\U0001f4b3",
        "output":        "\u2714",   # tick
    }
    nodes = []
    edges = []
    x_pos = 120

    id_to_node = {}
    for step in steps:
        icon  = icon_map.get(step["type"], "\u25b6")
        ntype = "trigger" if step["type"] in ("schedule","event_trigger","manual") else "action"
        node  = {
            "id":      step["id"],
            "type":    ntype,
            "subtype": step["type"],
            "label":   f"{icon} {step['label']}",
            "x":       x_pos,
            "y":       120,
            "data":    step.get("config", {}),
        }
        nodes.append(node)
        id_to_node[step["id"]] = node
        x_pos += 220

    for step in steps:
        for dep in step.get("depends_on", []):
            edges.append({
                "id":     f"e_{dep}_{step['id']}",
                "source": dep,
                "target": step["id"],
            })

    return {"nodes": nodes, "edges": edges}


# ── ROI calculator ───────────────────────────────────────────────────────────

def _calc_roi(steps: List[Dict], schedule: Dict) -> Dict:
    n_steps   = max(1, len(steps) - 1)   # exclude trigger
    freq_mult = {"cron": 260, "event": 52, "on_demand": 1}.get(schedule["type"], 1)
    human_h   = round(n_steps * 0.25, 2)  # 15min per step manually
    human_usd = round(human_h * 75, 2)
    agent_usd = round(n_steps * 0.08, 2)
    savings   = round(human_usd - agent_usd, 2)
    ratio     = round(human_usd / max(agent_usd, 0.01), 1)
    annual    = round(savings * freq_mult, 0)
    return {
        "human_hours":    human_h,
        "human_cost_usd": human_usd,
        "agent_cost_usd": agent_usd,
        "savings_usd":    savings,
        "roi_ratio":      ratio,
        "annual_savings_usd": annual,
        "frequency_per_year": freq_mult,
    }


# ── Schedule registration ────────────────────────────────────────────────────

def _register_schedule(blueprint: Dict, account_id: str) -> Optional[str]:
    schedule = blueprint.get("schedule", {})
    expr     = schedule.get("expr")
    wf_id    = blueprint.get("workflow_id", blueprint.get("id", ""))
    if not expr or schedule.get("type") not in ("cron",):
        return None
    try:
        from src.runtime.app import _scheduler
        job_id = f"wf_{wf_id[:8]}"
        steps  = blueprint.get("steps", [])
        def _run_workflow():
            from src.workflow_executor import execute_workflow
            from src.automation_request import _save_run
            ctx = execute_workflow(steps, wf_id, account_id, {"cron_fired": True})
            _save_run(ctx)
        try:
            _scheduler.remove_job(job_id)
        except Exception:
            pass
        _scheduler.add_job(
            _run_workflow, "cron", id=job_id,
            **_parse_cron(expr), replace_existing=True, max_instances=1,
        )
        logger.info("Schedule registered: job=%s wf=%s cron=%s", job_id, wf_id, expr)
        return job_id
    except Exception as e:
        logger.error("Schedule registration failed: %s", e)
        return None


def _parse_cron(expr: str) -> Dict:
    parts = expr.strip().split()
    if len(parts) != 5:
        return {"minute": "0", "hour": "9"}
    minute, hour, day, month, day_of_week = parts
    return {"minute": minute, "hour": hour, "day": day,
            "month": month, "day_of_week": day_of_week}


# ── Run persistence ──────────────────────────────────────────────────────────

def _save_run(ctx) -> None:
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
    description:   str,
    account_id:    str,
    requester:     str = "user",
    priority:      str = "normal",
    context:       Dict = None,
    auto_schedule: bool = True,
) -> Dict:
    """
    Primary entry point for creating an automation from any source.
    Called by: exec_admin agent, prod_ops agent, Rosetta nodes, UI, human users.
    """
    request_id = str(uuid.uuid4())[:12]
    ctx_dict   = context or {}
    logger.info("[AUTO-REQ] %s | from=%s | priority=%s | %.80s",
                request_id, requester, priority, description)

    # PCC harm gate
    try:
        from src.pcc import get_pcc
        check = get_pcc().check("automation_request",
                                {"description": description, "requester": requester,
                                 "priority": priority, **ctx_dict})
        if not check.get("allowed", True):
            return {"success": False, "error": check.get("reason", "PCC blocked"),
                    "blocked_by": "pcc", "request_id": request_id}
    except Exception as e:
        logger.debug("PCC skip: %s", e)

    # ── Parse NL → trigger + steps ────────────────────────────────────────────
    trigger  = _parse_nl_schedule(description)
    steps    = _parse_nl_steps(description, trigger)
    canvas   = _steps_to_canvas(steps)
    roi      = _calc_roi(steps, trigger)

    # ── Assign agent based on requester + context ────────────────────────────
    agent_map = {
        "exec_admin": ["executive", "analytics"],
        "prod_ops":   ["operations", "production"],
        "rosetta":    ["rosetta", "operations"],
        "user":       ["general"],
        "ui":         ["general"],
    }
    agents = agent_map.get(requester, ["general"])
    if ctx_dict.get("org_node"):
        agents.insert(0, ctx_dict["org_node"])

    # ── Assemble blueprint ────────────────────────────────────────────────────
    wf_id     = str(uuid.uuid4())[:12]
    name      = description[:80]
    now_iso   = datetime.now(timezone.utc).isoformat()

    blueprint = {
        "workflow_id":  wf_id,
        "account_id":   account_id,
        "name":         name,
        "description":  description,
        "requester":    requester,
        "priority":     priority,
        "trigger":      trigger,
        "steps":        steps,
        "agents":       agents,
        "schedule":     trigger,
        "inputs":       [],
        "outputs":      ["result"],
        "roi":          roi,
        "canvas_nodes": canvas["nodes"],
        "canvas_edges": canvas["edges"],
        "context":      ctx_dict,
        "generation_meta": {
            "strategy":    "nl_parse_v2",
            "confidence":  0.85 if trigger["type"] != "on_demand" else 0.70,
            "step_count":  len(steps),
            "trigger_type": trigger["type"],
        },
        "created_at":   now_iso,
        "updated_at":   now_iso,
        "version":      2,
    }

    # ROI gate
    if roi["roi_ratio"] < 1.0 and priority not in ("high", "critical"):
        return {"success": False, "error": "Automation ROI < 1.0 — costs more than it saves",
                "roi": roi, "request_id": request_id}

    # Register schedule
    schedule_job = _register_schedule(blueprint, account_id) if auto_schedule else None
    status       = "scheduled" if schedule_job else "built"

    # Persist
    with _lock:
        conn = _get_db()
        try:
            conn.execute("""INSERT INTO automation_requests
                (request_id, account_id, requester, description, priority, status,
                 blueprint_id, schedule_job, roi_usd, created_at, built_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (request_id, account_id, requester, description, priority, status,
                 wf_id, schedule_job, roi.get("savings_usd", 0),
                 now_iso, now_iso))
            conn.commit()
        finally:
            conn.close()

    logger.info("[AUTO-REQ] %s BUILT | trigger=%s | steps=%d | job=%s | roi_ratio=%.1f",
                request_id, trigger["type"], len(steps), schedule_job, roi["roi_ratio"])

    return {
        "success":      True,
        "request_id":   request_id,
        "blueprint":    blueprint,
        "canvas_nodes": canvas["nodes"],
        "canvas_edges": canvas["edges"],
        "schedule_job": schedule_job,
        "roi":          roi,
        "requester":    requester,
        "status":       status,
        "canvas_url":   f"/ui/forge?view=canvas&workflow_id={wf_id}",
    }


# ── List helpers ──────────────────────────────────────────────────────────────

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
    conn = _get_db()
    try:
        rows = conn.execute("""SELECT * FROM automation_runs
            WHERE account_id = ? ORDER BY started_at DESC LIMIT ?""",
            (account_id, limit)).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            for fld in ("step_log", "final_output"):
                try:
                    d[fld] = json.loads(d.get(fld) or "[]")
                except Exception:
                    d[fld] = []
            result.append(d)
        return result
    finally:
        conn.close()


def get_automation_manager():
    class _AM:
        request       = staticmethod(request_automation)
        list_requests = staticmethod(list_requests)
        list_runs     = staticmethod(list_runs)
        save_run      = staticmethod(_save_run)
    return _AM()
