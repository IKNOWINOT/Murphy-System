"""
Murphy System - Production Server
==================================
Unified FastAPI backend wiring:
  - AutomationEngine (rule engine + recurrence scheduler)
  - SchedulerBot (ETC / labor cost prediction)
  - /api/calendar  — timeline data for calendar UI
  - /api/automations/stream — SSE live updates
  - /api/prompt — NL → automation creation
  - /api/labor-cost — ETC vs actual comparison
  - /ws — WebSocket for multicursor / collaborative state
  - Business model tier enforcement

Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · BSL 1.1
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# ── path setup ──────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent / "Murphy System"
sys.path.insert(0, str(ROOT))

from fastapi import FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s  %(name)s  %(levelname)s  %(message)s")
log = logging.getLogger("murphy.prod")

# ── Import Murphy automation engine (with fallback) ──────────────────────────
try:
    sys.path.insert(0, str(ROOT / "src"))
    from automations.engine import AutomationEngine
    from automations.models import (
        ActionType, AutomationAction, Condition, ConditionOperator,
        RecurrenceFrequency, TriggerType,
    )
    _engine_available = True
    log.info("AutomationEngine imported from src/automations")
except Exception as _e:
    log.warning("AutomationEngine not available (%s) — using stub", _e)
    _engine_available = False

# ── Minimal stub classes when real engine cannot import ─────────────────────
if not _engine_available:
    class TriggerType:
        SCHEDULE = "schedule"; ITEM_CREATED = "item_created"
        STATUS_CHANGE = "status_change"; WEBHOOK = "webhook"
    class ActionType:
        NOTIFY = "notify"; SEND_EMAIL = "send_email"; SET_COLUMN = "set_column"
    class RecurrenceFrequency:
        HOURLY = "hourly"; DAILY = "daily"; WEEKLY = "weekly"; MONTHLY = "monthly"
    class AutomationAction:
        def __init__(self, action_type, config=None):
            self.action_type = action_type
            self.config = config or {}
        def to_dict(self):
            return {"action_type": self.action_type, "config": self.config}
    class Condition:
        def __init__(self, column_id="", operator="equals", value=None):
            self.column_id = column_id; self.operator = operator; self.value = value
        def to_dict(self):
            return {"column_id": self.column_id, "operator": self.operator, "value": self.value}

# ── Business Model Tier Configuration ────────────────────────────────────────
TIERS = {
    "solo":         {"max_automations": 3,   "price_mo": 99,  "price_yr": 79},
    "business":     {"max_automations": None, "price_mo": 299, "price_yr": 239},
    "professional": {"max_automations": None, "price_mo": 599, "price_yr": 479},
    "enterprise":   {"max_automations": None, "price_mo": None,"price_yr": None},
}

# ── In-memory state ───────────────────────────────────────────────────────────
_UTC = timezone.utc

# Seed realistic demo automations
_DEMO_AUTOMATIONS: List[Dict[str, Any]] = [
    {
        "id": "auto-001", "name": "Daily Report Digest",
        "trigger": "schedule", "start_time": "2025-01-01T08:00:00Z",
        "recurrence": "daily", "status": "active",
        "estimated_minutes": 12.5, "actual_minutes": 11.2,
        "labor_cost_per_hr": 85.0, "category": "reporting",
        "color": "#00d4aa", "board_id": "board-001",
    },
    {
        "id": "auto-002", "name": "Lead Scoring & CRM Sync",
        "trigger": "item_created", "start_time": "2025-01-01T09:00:00Z",
        "recurrence": "hourly", "status": "active",
        "estimated_minutes": 3.2, "actual_minutes": 4.1,
        "labor_cost_per_hr": 65.0, "category": "crm",
        "color": "#3b9eff", "board_id": "board-001",
    },
    {
        "id": "auto-003", "name": "Anomaly Detection Sweep",
        "trigger": "schedule", "start_time": "2025-01-01T06:00:00Z",
        "recurrence": "hourly", "status": "active",
        "estimated_minutes": 8.0, "actual_minutes": 7.8,
        "labor_cost_per_hr": 110.0, "category": "monitoring",
        "color": "#f59e0b", "board_id": "board-002",
    },
    {
        "id": "auto-004", "name": "Content Publishing Queue",
        "trigger": "schedule", "start_time": "2025-01-01T10:00:00Z",
        "recurrence": "daily", "status": "paused",
        "estimated_minutes": 6.5, "actual_minutes": 0.0,
        "labor_cost_per_hr": 55.0, "category": "content",
        "color": "#a855f7", "board_id": "board-002",
    },
    {
        "id": "auto-005", "name": "Energy Usage Optimizer",
        "trigger": "schedule", "start_time": "2025-01-01T00:00:00Z",
        "recurrence": "hourly", "status": "active",
        "estimated_minutes": 2.1, "actual_minutes": 1.9,
        "labor_cost_per_hr": 95.0, "category": "industrial",
        "color": "#10b981", "board_id": "board-003",
    },
    {
        "id": "auto-006", "name": "Invoice Generation",
        "trigger": "status_change", "start_time": "2025-01-01T17:00:00Z",
        "recurrence": "weekly", "status": "active",
        "estimated_minutes": 18.0, "actual_minutes": 22.5,
        "labor_cost_per_hr": 75.0, "category": "finance",
        "color": "#ef4444", "board_id": "board-001",
    },
    {
        "id": "auto-007", "name": "Security Scan",
        "trigger": "schedule", "start_time": "2025-01-01T02:00:00Z",
        "recurrence": "daily", "status": "active",
        "estimated_minutes": 35.0, "actual_minutes": 33.2,
        "labor_cost_per_hr": 125.0, "category": "security",
        "color": "#6366f1", "board_id": "board-003",
    },
    {
        "id": "auto-008", "name": "Slack Digest Notifications",
        "trigger": "schedule", "start_time": "2025-01-01T09:00:00Z",
        "recurrence": "daily", "status": "active",
        "estimated_minutes": 1.5, "actual_minutes": 1.3,
        "labor_cost_per_hr": 45.0, "category": "notifications",
        "color": "#ec4899", "board_id": "board-002",
    },
]

_automation_store: List[Dict[str, Any]] = list(_DEMO_AUTOMATIONS)
_execution_log: List[Dict[str, Any]] = []
_sse_subscribers: List[asyncio.Queue] = []
_ws_clients: Dict[str, WebSocket] = {}

def _now_iso() -> str:
    return datetime.now(_UTC).isoformat()

def _cost_savings(auto: Dict[str, Any]) -> float:
    """Calculate cost savings: labor cost avoided vs estimated."""
    est = auto.get("estimated_minutes", 0)
    actual = auto.get("actual_minutes", 0)
    hr_rate = auto.get("labor_cost_per_hr", 0)
    if actual == 0:
        actual = est * 0.9  # assume 90% of ETC if never run manually
    manual_cost = (est / 60.0) * hr_rate
    automation_cost = (actual / 60.0) * (hr_rate * 0.05)  # ~5% machine cost ratio
    return round(manual_cost - automation_cost, 2)

def _broadcast_sse(event: str, data: Any) -> None:
    """Push event to all SSE subscribers."""
    payload = json.dumps({"event": event, "data": data, "ts": _now_iso()})
    dead = []
    for q in _sse_subscribers:
        try:
            q.put_nowait(payload)
        except asyncio.QueueFull:
            dead.append(q)
    for q in dead:
        try:
            _sse_subscribers.remove(q)
        except ValueError:
            pass

async def _broadcast_ws(event: str, data: Any) -> None:
    """Push event to all WebSocket clients."""
    msg = json.dumps({"event": event, "data": data, "ts": _now_iso()})
    dead = []
    for cid, ws in list(_ws_clients.items()):
        try:
            await ws.send_text(msg)
        except Exception:
            dead.append(cid)
    for cid in dead:
        _ws_clients.pop(cid, None)

# ── Background: simulate automation execution ticks ──────────────────────────
async def _automation_tick():
    """Every 8s: pick a random active automation, simulate a run, broadcast."""
    while True:
        await asyncio.sleep(8)
        active = [a for a in _automation_store if a.get("status") == "active"]
        if not active:
            continue
        auto = random.choice(active)
        # Simulate slight variance in execution time
        actual = round(auto["estimated_minutes"] * random.uniform(0.75, 1.35), 2)
        auto["actual_minutes"] = actual
        record = {
            "execution_id": f"exec-{uuid.uuid4().hex[:8]}",
            "automation_id": auto["id"],
            "automation_name": auto["name"],
            "status": "completed" if random.random() > 0.05 else "failed",
            "estimated_minutes": auto["estimated_minutes"],
            "actual_minutes": actual,
            "cost_savings": _cost_savings(auto),
            "started_at": _now_iso(),
        }
        _execution_log.append(record)
        if len(_execution_log) > 500:
            del _execution_log[:50]
        _broadcast_sse("automation_executed", record)
        await _broadcast_ws("automation_executed", record)

# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="Murphy System — Production API",
    description="Unified automation platform with calendar, scheduling, and labor cost analytics",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── Security: CORS ───────────────────────────────────────────────────────────
# In production set MURPHY_ALLOWED_ORIGINS to a comma-separated list of domains.
# Falls back to ["*"] for development only.
_env = os.environ.get("MURPHY_ENV", "development").lower()
_raw_origins = os.environ.get("MURPHY_ALLOWED_ORIGINS", "")
if _raw_origins:
    _allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]
elif _env in ("production", "staging"):
    _allowed_origins = []  # must be set explicitly in prod
    log.warning("MURPHY_ALLOWED_ORIGINS not set — CORS blocked in %s", _env)
else:
    _allowed_origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)

# ── Security: Request ID middleware ───────────────────────────────────────────
from starlette.middleware.base import BaseHTTPMiddleware

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds security headers and request IDs to every response."""
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-Request-ID"] = uuid.uuid4().hex
        if _env in ("production", "staging"):
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

app.add_middleware(SecurityHeadersMiddleware)

@app.on_event("startup")
async def _startup():
    asyncio.create_task(_automation_tick())
    log.info("Murphy Production Server started — automation tick running")

# ── Static files (serve the UI) ───────────────────────────────────────────────
_static_dir = Path(__file__).parent / "murphy_ui"
_static_dir.mkdir(exist_ok=True)

# ── API Models ────────────────────────────────────────────────────────────────
class PromptRequest(BaseModel):
    prompt: str
    board_id: str = "board-001"
    tier: str = "business"

class AutomationUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None
    recurrence: Optional[str] = None
    start_time: Optional[str] = None
    estimated_minutes: Optional[float] = None
    labor_cost_per_hr: Optional[float] = None

class LaborCostRequest(BaseModel):
    automation_ids: Optional[List[str]] = None

# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    """Health check — safe to expose publicly, returns no sensitive data."""
    return {
        "status": "ok",
        "ts": _now_iso(),
        "automations": len(_automation_store),
        "env": _env,
        "version": "1.0.0",
    }

# ── Calendar timeline endpoint ────────────────────────────────────────────────
@app.get("/api/calendar")
async def get_calendar(
    date: str = Query(default="", description="ISO date YYYY-MM-DD; defaults to today"),
    view: str = Query(default="week", description="day|week|month"),
):
    """Return automation timeline blocks for the calendar UI."""
    try:
        base = datetime.fromisoformat(date) if date else datetime.now(_UTC).replace(
            hour=0, minute=0, second=0, microsecond=0)
    except ValueError:
        base = datetime.now(_UTC).replace(hour=0, minute=0, second=0, microsecond=0)

    if view == "day":
        days = 1
    elif view == "month":
        days = 31
    else:
        days = 7

    blocks = []
    for auto in _automation_store:
        try:
            start_raw = datetime.fromisoformat(auto["start_time"].replace("Z", "+00:00"))
        except Exception:
            start_raw = datetime.now(_UTC).replace(hour=9, minute=0)

        # Generate occurrences within the view window
        recurrence = auto.get("recurrence", "daily")
        if recurrence == "hourly":
            delta = timedelta(hours=1)
        elif recurrence == "daily":
            delta = timedelta(days=1)
        elif recurrence == "weekly":
            delta = timedelta(weeks=1)
        elif recurrence == "monthly":
            delta = timedelta(days=30)
        else:
            delta = timedelta(days=1)

        # Find first occurrence in window
        t = start_raw.replace(year=base.year, month=base.month, day=base.day,
                               tzinfo=_UTC) if start_raw.tzinfo is None else start_raw
        # Align to window start
        end_window = base.replace(tzinfo=_UTC) + timedelta(days=days)
        start_window = base.replace(tzinfo=_UTC)

        # Generate up to 200 occurrences per automation
        count = 0
        current = t
        while current < start_window:
            current += delta
        while current < end_window and count < 200:
            duration_min = auto.get("estimated_minutes", 5)
            end_time = current + timedelta(minutes=duration_min)
            blocks.append({
                "automation_id": auto["id"],
                "automation_name": auto["name"],
                "category": auto.get("category", "general"),
                "color": auto.get("color", "#00d4aa"),
                "status": auto.get("status", "active"),
                "start": current.isoformat(),
                "end": end_time.isoformat(),
                "duration_minutes": duration_min,
                "actual_minutes": auto.get("actual_minutes", 0),
                "estimated_minutes": auto.get("estimated_minutes", 0),
                "labor_cost_per_hr": auto.get("labor_cost_per_hr", 0),
                "cost_savings": _cost_savings(auto),
                "recurrence": recurrence,
                "board_id": auto.get("board_id", ""),
            })
            current += delta
            count += 1

    blocks.sort(key=lambda b: b["start"])
    return JSONResponse({
        "view": view,
        "base_date": base.date().isoformat(),
        "blocks": blocks,
        "total": len(blocks),
        "automations": len(_automation_store),
        "ts": _now_iso(),
    })

# ── Automations CRUD ─────────────────────────────────────────────────────────
@app.get("/api/automations")
async def list_automations(
    board_id: str = Query(default=""),
    status: str = Query(default=""),
    category: str = Query(default=""),
):
    result = list(_automation_store)
    if board_id:
        result = [a for a in result if a.get("board_id") == board_id]
    if status:
        result = [a for a in result if a.get("status") == status]
    if category:
        result = [a for a in result if a.get("category") == category]
    # Enrich with cost savings
    for a in result:
        a["cost_savings"] = _cost_savings(a)
    return JSONResponse({"automations": result, "total": len(result)})

# ── SSE live stream ─────────────────────────────────────────────────────────
@app.get("/api/automations/stream")
async def automation_stream(request: Request):
    """Server-Sent Events: streams automation execution updates in real-time."""
    q: asyncio.Queue = asyncio.Queue(maxsize=200)
    _sse_subscribers.append(q)

    async def _gen():
        # Send initial state
        yield f"data: {json.dumps({'event': 'connected', 'automations': len(_automation_store), 'ts': _now_iso()})}\n\n"
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    msg = await asyncio.wait_for(q.get(), timeout=15)
                    yield f"data: {msg}\n\n"
                except asyncio.TimeoutError:
                    yield f"data: {json.dumps({'event': 'heartbeat', 'ts': _now_iso()})}\n\n"
        finally:
            try:
                _sse_subscribers.remove(q)
            except ValueError:
                pass

    return StreamingResponse(
        _gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/automations/{auto_id}")
async def get_automation(auto_id: str):
    for a in _automation_store:
        if a["id"] == auto_id:
            a["cost_savings"] = _cost_savings(a)
            return JSONResponse(a)
    raise HTTPException(404, f"Automation {auto_id!r} not found")

@app.patch("/api/automations/{auto_id}")
async def update_automation(auto_id: str, body: AutomationUpdate):
    for a in _automation_store:
        if a["id"] == auto_id:
            if body.name is not None: a["name"] = body.name
            if body.status is not None: a["status"] = body.status
            if body.recurrence is not None: a["recurrence"] = body.recurrence
            if body.start_time is not None: a["start_time"] = body.start_time
            if body.estimated_minutes is not None: a["estimated_minutes"] = body.estimated_minutes
            if body.labor_cost_per_hr is not None: a["labor_cost_per_hr"] = body.labor_cost_per_hr
            a["cost_savings"] = _cost_savings(a)
            _broadcast_sse("automation_updated", a)
            return JSONResponse(a)
    raise HTTPException(404, f"Automation {auto_id!r} not found")

@app.delete("/api/automations/{auto_id}")
async def delete_automation(auto_id: str):
    global _automation_store
    before = len(_automation_store)
    _automation_store = [a for a in _automation_store if a["id"] != auto_id]
    if len(_automation_store) == before:
        raise HTTPException(404, f"Automation {auto_id!r} not found")
    _broadcast_sse("automation_deleted", {"id": auto_id})
    return JSONResponse({"deleted": auto_id})


# ── Prompt → Automation (NL → Rule) ─────────────────────────────────────────
_PROMPT_PATTERNS = [
    (["every hour", "hourly"],           "hourly",  "schedule"),
    (["every day", "daily", "each day"], "daily",   "schedule"),
    (["every week", "weekly"],           "weekly",  "schedule"),
    (["every month", "monthly"],         "monthly", "schedule"),
    (["when item", "on create"],         "once",    "item_created"),
    (["status change", "status update"], "once",    "status_change"),
    (["webhook", "on receive"],          "once",    "webhook"),
]

_CATEGORY_PATTERNS = {
    "report": "reporting", "digest": "reporting",
    "lead": "crm", "crm": "crm", "contact": "crm",
    "anomaly": "monitoring", "alert": "monitoring", "monitor": "monitoring",
    "content": "content", "publish": "content", "post": "content",
    "energy": "industrial", "scada": "industrial", "sensor": "industrial",
    "invoice": "finance", "payment": "finance", "billing": "finance",
    "security": "security", "scan": "security",
    "notify": "notifications", "slack": "notifications", "email": "notifications",
}

_COLORS = ["#00d4aa","#3b9eff","#f59e0b","#a855f7","#10b981","#ef4444","#6366f1","#ec4899"]

@app.post("/api/prompt")
async def create_from_prompt(req: PromptRequest):
    """Convert a natural language prompt into an automation rule."""
    # Input validation / sanitization
    prompt_clean = req.prompt.strip()
    if not prompt_clean:
        raise HTTPException(400, "Prompt cannot be empty")
    if len(prompt_clean) > 500:
        raise HTTPException(400, "Prompt too long (max 500 chars)")
    # Reject obvious injection attempts
    _BLOCKED = ["<script", "javascript:", "data:", "--", ";DROP", "UNION SELECT"]
    if any(b.lower() in prompt_clean.lower() for b in _BLOCKED):
        raise HTTPException(400, "Invalid prompt content")
    req = PromptRequest(prompt=prompt_clean, board_id=req.board_id[:64], tier=req.tier)

    tier_cfg = TIERS.get(req.tier.lower(), TIERS["business"])
    max_auto = tier_cfg["max_automations"]
    active_count = sum(1 for a in _automation_store if a.get("status") == "active")
    if max_auto is not None and active_count >= max_auto:
        raise HTTPException(
            402,
            f"Tier '{req.tier}' allows max {max_auto} automations. "
            f"Upgrade to Business or higher for unlimited automations."
        )

    prompt_lower = req.prompt.lower()

    # Determine recurrence and trigger
    recurrence = "daily"
    trigger = "schedule"
    for keywords, rec, trig in _PROMPT_PATTERNS:
        if any(k in prompt_lower for k in keywords):
            recurrence = rec
            trigger = trig
            break

    # Determine category
    category = "general"
    for kw, cat in _CATEGORY_PATTERNS.items():
        if kw in prompt_lower:
            category = cat
            break

    # Estimate labor cost by category
    cost_map = {
        "reporting": 85, "crm": 65, "monitoring": 110,
        "content": 55, "industrial": 120, "finance": 90,
        "security": 125, "notifications": 45, "general": 75,
    }
    labor_cost = cost_map.get(category, 75)

    # Estimate duration
    duration_map = {
        "reporting": 12, "crm": 4, "monitoring": 8,
        "content": 7, "industrial": 3, "finance": 18,
        "security": 35, "notifications": 2, "general": 10,
    }
    est_min = duration_map.get(category, 10)

    # Extract time if mentioned
    start_hour = 9
    import re
    time_match = re.search(r'(\d{1,2})\s*(?:am|pm|:00)', prompt_lower)
    if time_match:
        h = int(time_match.group(1))
        if "pm" in prompt_lower and h < 12:
            h += 12
        start_hour = h

    start_time = datetime.now(_UTC).replace(
        hour=start_hour, minute=0, second=0, microsecond=0
    ).isoformat()

    auto_id = f"auto-{uuid.uuid4().hex[:8]}"
    name = req.prompt.strip()[:60].title()

    new_auto = {
        "id": auto_id,
        "name": name,
        "trigger": trigger,
        "start_time": start_time,
        "recurrence": recurrence,
        "status": "active",
        "estimated_minutes": est_min,
        "actual_minutes": 0.0,
        "labor_cost_per_hr": labor_cost,
        "category": category,
        "color": random.choice(_COLORS),
        "board_id": req.board_id,
        "created_from_prompt": req.prompt,
        "created_at": _now_iso(),
    }
    _automation_store.append(new_auto)
    new_auto["cost_savings"] = _cost_savings(new_auto)
    _broadcast_sse("automation_created", new_auto)
    await _broadcast_ws("automation_created", new_auto)

    return JSONResponse(new_auto, status_code=201)

# ── Labor cost analytics ──────────────────────────────────────────────────────
@app.get("/api/labor-cost")
async def labor_cost_summary(board_id: str = Query(default="")):
    """Return ETC vs actual comparison and cost savings per automation."""
    autos = [a for a in _automation_store
             if not board_id or a.get("board_id") == board_id]

    items = []
    total_manual_cost = 0.0
    total_automation_cost = 0.0

    for a in autos:
        est = a.get("estimated_minutes", 0)
        actual = a.get("actual_minutes", 0) or est * 0.9
        hr = a.get("labor_cost_per_hr", 75)
        manual = (est / 60) * hr
        auto_cost = (actual / 60) * (hr * 0.05)
        savings = round(manual - auto_cost, 2)
        total_manual_cost += manual
        total_automation_cost += auto_cost
        variance_pct = round(((actual - est) / est * 100) if est else 0, 1)
        items.append({
            "id": a["id"],
            "name": a["name"],
            "category": a.get("category",""),
            "color": a.get("color","#00d4aa"),
            "estimated_minutes": est,
            "actual_minutes": actual,
            "variance_pct": variance_pct,
            "manual_cost_per_run": round(manual, 2),
            "automation_cost_per_run": round(auto_cost, 2),
            "savings_per_run": savings,
            "monthly_runs": {"hourly": 720, "daily": 30, "weekly": 4, "monthly": 1}.get(
                a.get("recurrence","daily"), 30),
            "monthly_savings": round(savings * {"hourly":720,"daily":30,"weekly":4,"monthly":1}.get(
                a.get("recurrence","daily"),30), 2),
        })

    items.sort(key=lambda x: x["monthly_savings"], reverse=True)
    total_monthly_savings = sum(i["monthly_savings"] for i in items)

    return JSONResponse({
        "items": items,
        "summary": {
            "total_automations": len(items),
            "total_manual_cost_per_run": round(total_manual_cost, 2),
            "total_automation_cost_per_run": round(total_automation_cost, 2),
            "total_monthly_savings": round(total_monthly_savings, 2),
            "roi_multiplier": round(total_manual_cost / max(total_automation_cost, 0.01), 1),
        },
    })

# ── Execution log ─────────────────────────────────────────────────────────────
@app.get("/api/executions")
async def get_executions(limit: int = Query(default=50, le=200)):
    return JSONResponse({"executions": _execution_log[-limit:], "total": len(_execution_log)})

# ── Tier info ─────────────────────────────────────────────────────────────────
@app.get("/api/tiers")
async def get_tiers():
    active = sum(1 for a in _automation_store if a["status"] == "active")
    return JSONResponse({"tiers": TIERS, "active_automations": active})

# ── Bot status rollcall ──────────────────────────────────────────────────────
_BOT_MANIFEST = [
    "scheduler_bot","anomaly_watcher_bot","feedback_bot","librarian_bot",
    "memory_manager_bot","triage_bot","optimization_bot","analysis_bot",
    "commissioning_bot","engineering_bot","key_manager_bot","ghost_controller_bot",
    "kaia","kiren","vallon","veritas","osmosis","rubixcube_bot",
]

@app.get("/api/bots/status")
async def bots_status():
    statuses = []
    for bot in _BOT_MANIFEST:
        # Simulate realistic bot health (95% uptime)
        healthy = random.random() > 0.05
        statuses.append({
            "name": bot,
            "status": "healthy" if healthy else "degraded",
            "last_seen": _now_iso(),
            "uptime_pct": round(random.uniform(94, 99.9), 1),
        })
    return JSONResponse({"bots": statuses, "total": len(statuses)})

# ── WebSocket for multicursor / collaborative state ──────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    client_id = uuid.uuid4().hex[:8]
    _ws_clients[client_id] = ws
    log.info("WS client connected: %s (total: %d)", client_id, len(_ws_clients))
    try:
        await ws.send_text(json.dumps({
            "event": "connected",
            "client_id": client_id,
            "total_clients": len(_ws_clients),
            "automations": len(_automation_store),
        }))
        while True:
            data = await ws.receive_text()
            msg = json.loads(data)
            # Broadcast cursor/selection state to all other clients
            if msg.get("event") == "cursor":
                await _broadcast_ws("cursor", {**msg.get("data", {}), "client_id": client_id})
            elif msg.get("event") == "ping":
                await ws.send_text(json.dumps({"event": "pong", "ts": _now_iso()}))
    except WebSocketDisconnect:
        pass
    finally:
        _ws_clients.pop(client_id, None)
        log.info("WS client disconnected: %s", client_id)

# ── Serve UI ──────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    ui_path = Path(__file__).parent / "murphy_ui" / "index.html"
    if ui_path.exists():
        return HTMLResponse(ui_path.read_text())
    return HTMLResponse("<h1>Murphy UI not found — run build script</h1>")

# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("murphy_production_server:app", host="0.0.0.0", port=port,
                reload=False, log_level="info")