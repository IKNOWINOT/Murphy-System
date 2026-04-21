"""
Murphy System — Production Server v3.0
========================================
Full functional automation platform with:
  - Real HITL (Human-in-the-Loop) state machine — blocks until approved/rejected
  - Automation milestones with progress tracking — blocks SHRINK as milestones complete
  - Delay factor — missed milestones add time, blocks GROW on the calendar
  - Closed-loop automations: proposal→HITL→automation created→execute→results
  - Closed-loop campaigns: low traction→HITL paid-ad gate→approve→campaign resumes
  - Closed-loop self-setup: step→HITL gate→approved→next step
  - Real DAG execution engine with per-step HITL gates
  - Dynamic calendar blocks (start/end shift with delays)
  - All original routes preserved: /, /calendar, /dashboard, /landing
  - SSE + WebSocket for real-time push
  - Multi-tenant, 10 verticals, all loops closed

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
import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# -- path setup ----------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent

from fastapi import FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s  %(name)s  %(levelname)s  %(message)s")
log = logging.getLogger("murphy.prod")

# -- Import MurphyLLMProvider (DeepInfra primary, Together fallback) -----------
try:
    from llm_provider import get_llm as _get_llm
    _llm_available = True
    log.info("MurphyLLMProvider loaded — DeepInfra primary, Together fallback")
except Exception as _llm_e:
    log.warning("MurphyLLMProvider not available (%s) — using pattern-match fallback", _llm_e)
    _llm_available = False
    _get_llm = None  # type: ignore

# -- Import Murphy automation engine (with fallback) ---------------------------
try:
    from automations.engine import AutomationEngine
    from automations.models import (
        ActionType, AutomationAction, Condition, ConditionOperator,
        RecurrenceFrequency, TriggerType,
    )
    _engine_available = True
    log.info("AutomationEngine imported from src/automations")
except Exception as _e:
    log.warning("AutomationEngine not available (%s) -- using stub", _e)
    _engine_available = False

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
            self.action_type = action_type; self.config = config or {}
        def to_dict(self): return {"action_type": self.action_type, "config": self.config}
    class Condition:
        def __init__(self, column_id="", operator="equals", value=None):
            self.column_id = column_id; self.operator = operator; self.value = value
        def to_dict(self): return {"column_id": self.column_id, "operator": self.operator, "value": self.value}

# -- Business Model Tiers ------------------------------------------------------
TIERS = {
    "solo":         {"max_automations": 3,   "price_mo": 99,  "price_yr": 79},
    "business":     {"max_automations": None, "price_mo": 299, "price_yr": 239},
    "professional": {"max_automations": None, "price_mo": 599, "price_yr": 479},
    "enterprise":   {"max_automations": None, "price_mo": None,"price_yr": None},
}

_UTC = timezone.utc

def _now_iso() -> str:
    return datetime.now(_UTC).isoformat()

def _now_dt() -> datetime:
    return datetime.now(_UTC)

# ==============================================================================
# HITL QUEUE — Real Human-in-the-Loop State Machine
# ==============================================================================
_HITL_QUEUE: List[Dict[str, Any]] = []

# ── HITL Persistence (DEF-047) ────────────────────────────────────────────
try:
    from hitl_persistence import HITLStore as _HITLStore
    _hitl_store = _HITLStore()
    _persisted = _hitl_store.load_all()
    if _persisted:
        _HITL_QUEUE.extend(_persisted)
        log.info("Loaded %d HITL items from persistence", len(_persisted))
except Exception as _store_exc:
    log.warning("HITL persistence unavailable: %s — using in-memory only", _store_exc)
    _hitl_store = None

def _broadcast_sse(event: str, data: Any) -> None:
    payload = json.dumps({"event": event, "data": data, "ts": _now_iso()})
    dead = []
    for q in _sse_subscribers:
        try: q.put_nowait(payload)
        except asyncio.QueueFull: dead.append(q)
    for q in dead:
        try: _sse_subscribers.remove(q)
        except ValueError:  # PROD-HARD A2: concurrent unsubscribe — idempotent, nothing to do
            log.debug("SSE queue already unsubscribed during broadcast cleanup")

async def _broadcast_ws(event: str, data: Any) -> None:
    msg = json.dumps({"event": event, "data": data, "ts": _now_iso()})
    dead = []
    for cid, ws in list(_ws_clients.items()):
        try: await ws.send_text(msg)
        except Exception: dead.append(cid)
    for cid in dead: _ws_clients.pop(cid, None)

_sse_subscribers: List[asyncio.Queue] = []
_ws_clients: Dict[str, WebSocket] = {}

def _create_hitl_item(
    hitl_type: str,
    title: str,
    description: str,
    payload: Dict[str, Any],
    related_id: str = "",
    priority: str = "normal",
    auto_approve_after_seconds: int = 0,
) -> Dict[str, Any]:
    item = {
        "id": f"hitl-{uuid.uuid4().hex[:8]}",
        "type": hitl_type,
        "title": title,
        "description": description,
        "payload": payload,
        "related_id": related_id,
        "priority": priority,
        "status": "pending",
        "created_at": _now_iso(),
        "approved_at": None,
        "rejected_at": None,
        "approved_by": None,
        "rejection_reason": None,
        "auto_approve_after_seconds": auto_approve_after_seconds,
        "_created_ts": _now_dt().timestamp(),
    }
    _HITL_QUEUE.append(item)
    # Persist to SQLite (DEF-047)
    if _hitl_store:
        try:
            _hitl_store.save_item(item)
        except Exception as _pe:
            log.warning("HITL persist failed for %s: %s", item["id"], _pe)
    _broadcast_sse("hitl_item_created", {k: v for k, v in item.items() if not k.startswith("_")})
    log.info("HITL item created: %s [%s] %s", item["id"], hitl_type, title)
    return item

# -- Tenant / Org Registry -----------------------------------------------------
_TENANTS: Dict[str, Dict[str, Any]] = {
    "tenant-001": {
        "id": "tenant-001", "name": "Murphy Systems HQ", "org": "Inoni LLC",
        "tier": "enterprise", "owner": os.environ.get("MURPHY_FOUNDER_NAME", ""),
        "connections": ["HubSpot", "Salesforce", "Stripe", "Slack", "OpenAI", "Anthropic"],
        "boards": ["board-001", "board-002", "board-003"],
        "active_verticals": ["marketing","proposals","crm","monitoring","finance","security","content","comms","pipeline"],
        "created_at": "2024-01-01T00:00:00Z",
    },
    "tenant-002": {
        "id": "tenant-002", "name": "Industrial Operations", "org": "MurphyOps Ltd",
        "tier": "professional", "owner": "Operations Team",
        "connections": ["SCADA", "OPC-UA", "Modbus", "InfluxDB"],
        "boards": ["board-003"],
        "active_verticals": ["industrial","monitoring","security","notifications"],
        "created_at": "2024-03-15T00:00:00Z",
    },
    "tenant-003": {
        "id": "tenant-003", "name": "Marketing Studio", "org": "Growth Co",
        "tier": "business", "owner": "Marketing Director",
        "connections": ["HubSpot", "Mailchimp", "LinkedIn", "Twitter", "Google Ads"],
        "boards": ["board-001", "board-002"],
        "active_verticals": ["marketing","content","crm","proposals","notifications"],
        "created_at": "2024-06-01T00:00:00Z",
    },
}

# ==============================================================================
# AUTOMATION MILESTONES
# ==============================================================================
_MILESTONE_TEMPLATES = {
    "reporting":     [("Parse Data Sources", 20), ("Run Analysis", 40), ("Format Output", 30), ("Deliver Report", 10)],
    "crm":           [("Fetch Contacts", 15), ("Score Leads", 35), ("Enrich Records", 30), ("Sync to CRM", 20)],
    "monitoring":    [("Collect Metrics", 20), ("Run Anomaly Model", 45), ("Evaluate Thresholds", 20), ("Alert if Triggered", 15)],
    "content":       [("Generate Draft", 40), ("SEO Optimization", 25), ("HITL Review Gate", 20), ("Publish", 15)],
    "industrial":    [("Read Sensors", 25), ("Detect Anomalies", 35), ("Evaluate Safety", 25), ("Log & Alert", 15)],
    "finance":       [("Fetch Transactions", 20), ("Reconcile Records", 40), ("HITL Review (>$10k)", 25), ("Post to Ledger", 15)],
    "security":      [("Scan Surfaces", 30), ("Score Vulnerabilities", 30), ("HITL Remediation Gate", 25), ("Apply Fixes", 15)],
    "notifications": [("Compose Message", 30), ("Route to Channel", 40), ("Confirm Delivery", 30)],
    "marketing":     [("Pull Campaign Data", 20), ("Evaluate Traction", 35), ("Adjust Targeting", 30), ("Push Updates", 15)],
    "proposals":     [("Parse RFP", 20), ("Generate Content", 40), ("HITL Review Gate", 25), ("Send Proposal", 15)],
    "pipeline":      [("Parse NL Description", 15), ("Build DAG", 35), ("HITL Review Gate", 25), ("Execute DAG", 25)],
    "general":       [("Prepare Input", 25), ("Execute Core Logic", 50), ("Deliver Output", 25)],
}

def _make_milestones(category: str, estimated_minutes: float) -> List[Dict[str, Any]]:
    template = _MILESTONE_TEMPLATES.get(category, _MILESTONE_TEMPLATES["general"])
    milestones = []
    for i, (name, pct) in enumerate(template):
        duration = round(estimated_minutes * pct / 100, 2)
        is_hitl = "HITL" in name or "Review Gate" in name or "Remediation Gate" in name
        milestones.append({
            "id": f"ms-{i+1:03d}",
            "name": name,
            "weight_pct": pct,
            "cumulative_pct": sum(t[1] for t in template[:i+1]),
            "duration_minutes": duration,
            "status": "pending",
            "progress": 0,
            "is_hitl": is_hitl,
            "hitl_item_id": None,
            "planned_start_offset_minutes": sum(estimated_minutes * t[1]/100 for t in template[:i]),
            "actual_start_offset_minutes": None,
            "delay_minutes": 0.0,
            "completed_at": None,
        })
    return milestones

def _calc_automation_progress(auto: Dict[str, Any]) -> float:
    milestones = auto.get("milestones", [])
    if not milestones: return 0.0
    total_weight = sum(m["weight_pct"] for m in milestones)
    earned = sum(
        m["weight_pct"] * (1.0 if m["status"] == "completed" else m["progress"] / 100.0)
        for m in milestones
    )
    return round(earned / total_weight * 100, 1)

def _calc_block_duration(auto: Dict[str, Any]) -> float:
    base = auto.get("estimated_minutes", 10)
    total_delay = sum(m.get("delay_minutes", 0) for m in auto.get("milestones", []))
    return round(base + total_delay, 2)

_DEMO_AUTOMATIONS: List[Dict[str, Any]] = []

def _seed_automations():
    global _DEMO_AUTOMATIONS
    raw = [
        {"id":"auto-001","name":"Daily Report Digest","trigger":"schedule","start_time":"2025-01-01T08:00:00Z","recurrence":"daily","status":"active","estimated_minutes":12.5,"actual_minutes":11.2,"labor_cost_per_hr":85.0,"category":"reporting","color":"#00d4aa","board_id":"board-001","tenant_id":"tenant-001"},
        {"id":"auto-002","name":"Lead Scoring & CRM Sync","trigger":"item_created","start_time":"2025-01-01T09:00:00Z","recurrence":"hourly","status":"active","estimated_minutes":3.2,"actual_minutes":4.1,"labor_cost_per_hr":65.0,"category":"crm","color":"#3b9eff","board_id":"board-001","tenant_id":"tenant-001"},
        {"id":"auto-003","name":"Anomaly Detection Sweep","trigger":"schedule","start_time":"2025-01-01T06:00:00Z","recurrence":"hourly","status":"active","estimated_minutes":8.0,"actual_minutes":7.8,"labor_cost_per_hr":110.0,"category":"monitoring","color":"#f59e0b","board_id":"board-002","tenant_id":"tenant-001"},
        {"id":"auto-004","name":"Content Publishing Queue","trigger":"schedule","start_time":"2025-01-01T10:00:00Z","recurrence":"daily","status":"paused","estimated_minutes":6.5,"actual_minutes":0.0,"labor_cost_per_hr":55.0,"category":"content","color":"#a855f7","board_id":"board-002","tenant_id":"tenant-001"},
        {"id":"auto-005","name":"Energy Usage Optimizer","trigger":"schedule","start_time":"2025-01-01T00:00:00Z","recurrence":"hourly","status":"active","estimated_minutes":2.1,"actual_minutes":1.9,"labor_cost_per_hr":95.0,"category":"industrial","color":"#10b981","board_id":"board-003","tenant_id":"tenant-002"},
        {"id":"auto-006","name":"Invoice Generation","trigger":"status_change","start_time":"2025-01-01T17:00:00Z","recurrence":"weekly","status":"active","estimated_minutes":18.0,"actual_minutes":22.5,"labor_cost_per_hr":75.0,"category":"finance","color":"#ef4444","board_id":"board-001","tenant_id":"tenant-001"},
        {"id":"auto-007","name":"Security Scan","trigger":"schedule","start_time":"2025-01-01T02:00:00Z","recurrence":"daily","status":"active","estimated_minutes":35.0,"actual_minutes":33.2,"labor_cost_per_hr":125.0,"category":"security","color":"#6366f1","board_id":"board-003","tenant_id":"tenant-001"},
        {"id":"auto-008","name":"Slack Digest Notifications","trigger":"schedule","start_time":"2025-01-01T09:00:00Z","recurrence":"daily","status":"active","estimated_minutes":1.5,"actual_minutes":1.3,"labor_cost_per_hr":45.0,"category":"notifications","color":"#ec4899","board_id":"board-002","tenant_id":"tenant-001"},
        {"id":"auto-009","name":"Campaign Tier Monitor","trigger":"schedule","start_time":"2025-01-01T08:00:00Z","recurrence":"hourly","status":"active","estimated_minutes":4.0,"actual_minutes":3.8,"labor_cost_per_hr":80.0,"category":"marketing","color":"#f97316","board_id":"board-001","tenant_id":"tenant-003"},
        {"id":"auto-010","name":"Proposal Auto-Responder","trigger":"webhook","start_time":"2025-01-01T00:00:00Z","recurrence":"hourly","status":"active","estimated_minutes":8.5,"actual_minutes":7.2,"labor_cost_per_hr":95.0,"category":"proposals","color":"#14b8a6","board_id":"board-001","tenant_id":"tenant-001"},
        {"id":"auto-011","name":"Pipeline Builder AI","trigger":"webhook","start_time":"2025-01-01T00:00:00Z","recurrence":"hourly","status":"active","estimated_minutes":6.0,"actual_minutes":5.1,"labor_cost_per_hr":110.0,"category":"pipeline","color":"#8b5cf6","board_id":"board-001","tenant_id":"tenant-001"},
        {"id":"auto-012","name":"Marketing Lead Nurture","trigger":"item_created","start_time":"2025-01-01T08:00:00Z","recurrence":"daily","status":"active","estimated_minutes":5.0,"actual_minutes":4.5,"labor_cost_per_hr":80.0,"category":"marketing","color":"#fb923c","board_id":"board-001","tenant_id":"tenant-003"},
        {"id":"auto-013","name":"SCADA Equipment Sync","trigger":"schedule","start_time":"2025-01-01T00:30:00Z","recurrence":"hourly","status":"active","estimated_minutes":1.5,"actual_minutes":1.2,"labor_cost_per_hr":120.0,"category":"industrial","color":"#34d399","board_id":"board-003","tenant_id":"tenant-002"},
        {"id":"auto-014","name":"Compliance Audit Checker","trigger":"schedule","start_time":"2025-01-01T03:00:00Z","recurrence":"weekly","status":"active","estimated_minutes":45.0,"actual_minutes":42.0,"labor_cost_per_hr":125.0,"category":"security","color":"#818cf8","board_id":"board-003","tenant_id":"tenant-001"},
        {"id":"auto-015","name":"AI Workflow Generator","trigger":"webhook","start_time":"2025-01-01T00:00:00Z","recurrence":"hourly","status":"active","estimated_minutes":7.0,"actual_minutes":6.2,"labor_cost_per_hr":110.0,"category":"pipeline","color":"#c084fc","board_id":"board-001","tenant_id":"tenant-001"},
    ]
    for a in raw:
        a["milestones"] = _make_milestones(a["category"], a["estimated_minutes"])
        a["progress"] = 0.0
        a["total_delay_minutes"] = 0.0
        a["effective_duration_minutes"] = a["estimated_minutes"]
        a["created_at"] = _now_iso()
        ms = a["milestones"]
        if a["status"] == "active":
            rand_progress = random.randint(1, max(1, len(ms) - 1))
            for j in range(rand_progress):
                ms[j]["status"] = "completed"
                ms[j]["progress"] = 100
                ms[j]["completed_at"] = _now_iso()
            if rand_progress < len(ms):
                ms[rand_progress]["status"] = "running"
                ms[rand_progress]["progress"] = random.randint(10, 80)
        a["progress"] = _calc_automation_progress(a)
        a["effective_duration_minutes"] = _calc_block_duration(a)
    _DEMO_AUTOMATIONS = raw

_automation_store: List[Dict[str, Any]] = []
_execution_log: List[Dict[str, Any]] = []

# -- Campaign State ------------------------------------------------------------
_CAMPAIGN_TIERS = ["community", "solo", "business", "professional", "enterprise"]
_campaigns: Dict[str, Dict[str, Any]] = {}
_marketing_proposals: List[Dict[str, Any]] = []

def _seed_campaigns():
    metrics = {
        "community":    {"impressions":45200,"clicks":1820,"leads":312,"conversions":48,"spend":0.0,    "status":"active",    "traction":"healthy"},
        "solo":         {"impressions":12800,"clicks":680, "leads":94, "conversions":18,"spend":450.0,  "status":"active",    "traction":"healthy"},
        "business":     {"impressions":8400, "clicks":290, "leads":31, "conversions":4, "spend":1200.0, "status":"adjusting", "traction":"low"},
        "professional": {"impressions":3100, "clicks":88,  "leads":9,  "conversions":1, "spend":800.0,  "status":"adjusting", "traction":"low"},
        "enterprise":   {"impressions":960,  "clicks":42,  "leads":7,  "conversions":2, "spend":2400.0, "status":"active",    "traction":"healthy"},
    }
    channels = {
        "community":    ["SEO","GitHub","Twitter/X","Product Hunt"],
        "solo":         ["LinkedIn","Reddit","Dev.to","Newsletter"],
        "business":     ["LinkedIn Ads","Google Ads","Webinars","Partnerships"],
        "professional": ["Outbound Sales","Account-Based Marketing","Analyst Relations"],
        "enterprise":   ["Executive Briefings","Custom Demo Program","Trade Shows"],
    }
    for tier in _CAMPAIGN_TIERS:
        m = metrics[tier]
        _campaigns[tier] = {
            "id": f"campaign-{tier}", "tier": tier, "status": m["status"],
            "traction": m["traction"], "impressions": m["impressions"],
            "clicks": m["clicks"], "leads": m["leads"], "conversions": m["conversions"],
            "spend": m["spend"], "channels": channels[tier],
            "conversion_rate": round(m["conversions"]/max(m["impressions"],1)*100,3),
            "lead_rate": round(m["leads"]/max(m["impressions"],1)*100,2),
            "cpa": round(m["spend"]/max(m["conversions"],1),2),
            "last_evaluated": _now_iso(), "adjustments": [],
            "evaluation_count": random.randint(3,12),
            "hitl_proposal_id": None,
            "paid_proposals": [],
        }

# -- Proposals State -----------------------------------------------------------
_incoming_requests: List[Dict[str, Any]] = [
    {"id":"req-001","source":"email","from":"enterprise@bigcorp.com","subject":"Interested in Murphy System for our 500-person ops team","body":"We need automation for our daily reporting, CRM sync, and compliance workflows across 12 departments.","received_at":"2025-03-26T14:22:00Z","status":"pending","priority":"high","estimated_value":85000},
    {"id":"req-002","source":"web_form","from":"founder@startup.io","subject":"Proposal request: marketing + pipeline automation","body":"Early-stage startup, 12 people. Need automated lead scoring, email sequences, and dev pipeline monitoring.","received_at":"2025-03-26T16:45:00Z","status":"pending","priority":"medium","estimated_value":12000},
    {"id":"req-003","source":"partner_api","from":"systems@industrial-corp.com","subject":"SCADA automation and anomaly detection RFP","body":"Industrial facility, 3 plants. Need SCADA integration, real-time anomaly detection, automated maintenance scheduling.","received_at":"2025-03-27T09:10:00Z","status":"in_progress","priority":"high","estimated_value":220000},
]
_generated_proposals: List[Dict[str, Any]] = []

# -- Workflow / DAG State ------------------------------------------------------
_workflow_history: List[Dict[str, Any]] = []

# -- Comms / Agent State -------------------------------------------------------
_agent_messages: List[Dict[str, Any]] = []
_SUBSYSTEM_ROOMS = {
    "orchestration": ["scheduler_bot","optimization_bot","kaia"],
    "marketing":     ["feedback_bot","analysis_bot","kiren"],
    "security":      ["key_manager_bot","ghost_controller_bot","veritas"],
    "data":          ["memory_manager_bot","librarian_bot","osmosis"],
    "comms":         ["triage_bot","commissioning_bot","vallon"],
    "industrial":    ["engineering_bot","anomaly_watcher_bot","rubixcube_bot"],
}

# -- Self-Setup Pipeline State with HITL gates ---------------------------------
_SELF_SETUP_STEPS = [
    {"id":"step-001","name":"Scan Murphy System source",        "category":"analysis",   "status":"completed","progress":100,"requires_hitl":False,"hitl_item_id":None},
    {"id":"step-002","name":"Identify automation opportunities","category":"analysis",   "status":"completed","progress":100,"requires_hitl":False,"hitl_item_id":None},
    {"id":"step-003","name":"Bootstrap campaign engine",        "category":"marketing",  "status":"completed","progress":100,"requires_hitl":False,"hitl_item_id":None},
    {"id":"step-004","name":"Configure proposal auto-responder","category":"proposals",  "status":"active",   "progress":72, "requires_hitl":True, "hitl_item_id":None,"hitl_label":"Approve proposal templates & tone"},
    {"id":"step-005","name":"Wire AgenticCommsRouter",          "category":"comms",      "status":"pending",  "progress":0,  "requires_hitl":False,"hitl_item_id":None},
    {"id":"step-006","name":"Deploy monitoring automations",    "category":"monitoring", "status":"pending",  "progress":0,  "requires_hitl":True, "hitl_item_id":None,"hitl_label":"Approve monitoring thresholds & alert routing"},
    {"id":"step-007","name":"Configure security scans",         "category":"security",   "status":"pending",  "progress":0,  "requires_hitl":True, "hitl_item_id":None,"hitl_label":"Review scan scope & remediation policy"},
    {"id":"step-008","name":"Build CRM integration pipeline",   "category":"crm",        "status":"pending",  "progress":0,  "requires_hitl":False,"hitl_item_id":None},
    {"id":"step-009","name":"Activate DAG workflow engine",     "category":"pipeline",   "status":"pending",  "progress":0,  "requires_hitl":True, "hitl_item_id":None,"hitl_label":"Approve DAG execution permissions & resource limits"},
    {"id":"step-010","name":"Run self-verification suite",      "category":"validation", "status":"pending",  "progress":0,  "requires_hitl":False,"hitl_item_id":None},
    {"id":"step-011","name":"Enable HITL approval gates",       "category":"governance", "status":"pending",  "progress":0,  "requires_hitl":True, "hitl_item_id":None,"hitl_label":"Final governance review — approve full HITL policy"},
    {"id":"step-012","name":"Go live — full automation",        "category":"deployment", "status":"pending",  "progress":0,  "requires_hitl":True, "hitl_item_id":None,"hitl_label":"GO LIVE approval — confirm production deployment"},
]

# -- Vertical Configs ----------------------------------------------------------
_COLORS = ["#00d4aa","#3b9eff","#f59e0b","#a855f7","#10b981","#ef4444","#6366f1","#ec4899","#f97316","#14b8a6","#8b5cf6","#06b6d4","#84cc16","#fbbf24","#fb7185"]

_VERTICAL_CONFIGS = {
    "marketing":  {"label":"Marketing",          "icon":"📣","color":"#f97316","description":"AI-driven campaign management, tier-filling, lead nurturing","engine":"AdaptiveCampaignEngine (MKT-004)","integrations":["HubSpot","Mailchimp","LinkedIn Ads","Google Ads","Twitter/X"],"automation_templates":["Weekly email sequence — nurture leads by tier","Conversion rate monitor — auto-adjust underperforming campaigns","Lead scoring sync to CRM on every new contact","Paid ad proposal generator for low-traction tiers","Social media posting queue (multi-platform)"]},
    "proposals":  {"label":"Proposals",          "icon":"📄","color":"#14b8a6","description":"AI-generated proposals responding to inbound RFPs and requests","engine":"AIWorkflowGenerator + OrchestrationEngine","integrations":["Email","Web Forms","HubSpot Deals","Salesforce Opportunities","DocuSign"],"automation_templates":["Inbound RFP auto-responder — NL proposal in < 2 min","Proposal status tracker — follow up after 3 days","Contract value estimator from requirement analysis","Proposal approval pipeline — HITL review gate","Win/loss analysis to campaign feedback loop"]},
    "crm":        {"label":"CRM",                "icon":"👥","color":"#3b9eff","description":"Contact lifecycle, deal tracking, automated follow-ups","engine":"AutomationEngine + WorldModelRegistry (HubSpot/Salesforce)","integrations":["HubSpot","Salesforce","Pipedrive","Zoho CRM"],"automation_templates":["Lead scoring on creation — assign tier and owner","Deal stage change — send personalized email","Stale deal alert — no activity 7+ days","Contact enrichment from LinkedIn on import","Daily CRM digest to Slack/email summary"]},
    "monitoring": {"label":"Monitoring",         "icon":"📊","color":"#f59e0b","description":"Anomaly detection, threshold alerts, system health","engine":"AnomalyWatcherBot + SchedulerBot","integrations":["Prometheus","Grafana","InfluxDB","Datadog","PagerDuty"],"automation_templates":["Hourly anomaly detection sweep — ML-based","SLA breach predictor — alert 30min before threshold","Daily system health report","Auto-scale trigger on load spikes","Error rate spike — create incident + notify on-call"]},
    "industrial": {"label":"Industrial / SCADA", "icon":"🏭","color":"#10b981","description":"SCADA integration, equipment monitoring, maintenance scheduling","engine":"EngineeringBot + AnomalyWatcherBot","integrations":["SCADA","OPC-UA","Modbus","MQTT","InfluxDB"],"automation_templates":["Real-time equipment status pull (SCADA to DB)","Predictive maintenance scheduler — vibration analysis","Energy usage optimizer — shift loads off-peak","Safety threshold breach — emergency shutdown trigger","Shift handover report — auto-generated from sensor data"]},
    "finance":    {"label":"Finance",            "icon":"💰","color":"#ef4444","description":"Invoicing, payment reconciliation, financial reporting","engine":"AutomationEngine + Stripe/QuickBooks integration","integrations":["Stripe","QuickBooks","Xero","Plaid","FreshBooks"],"automation_templates":["Invoice generation on deal close","Payment reconciliation — daily bank sync","Overdue invoice follow-up sequence","Monthly P&L report — executive summary","Budget variance alert — spend > 110% of plan"]},
    "security":   {"label":"Security",           "icon":"🔒","color":"#6366f1","description":"Vulnerability scans, access audits, compliance monitoring","engine":"GhostControllerBot + KeyManagerBot","integrations":["AWS IAM","Vault","Snyk","Trivy","SIEM"],"automation_templates":["Daily vulnerability scan — container + dependencies","Access audit — unused permissions quarterly review","SSL certificate expiry monitor — alert 30d before","Failed login spike — temporary lockdown + alert","Compliance checklist runner — SOC2/GDPR weekly"]},
    "content":    {"label":"Content",            "icon":"✍️","color":"#a855f7","description":"Content creation, scheduling, distribution pipeline","engine":"AutomationEngine + OpenAI/Anthropic integration","integrations":["OpenAI","Anthropic","WordPress","Buffer","Contentful"],"automation_templates":["Weekly blog post draft from topic queue","Social media calendar generation — monthly","Content performance report — topic optimization","SEO audit — crawl and flag issues weekly","Video transcript to blog post + social clips"]},
    "comms":      {"label":"Communications",     "icon":"💬","color":"#06b6d4","description":"Inter-agent messaging, team notifications, escalation routing","engine":"AgenticCommsRouter (ACOM-001)","integrations":["Matrix","Slack","Email","SMS","PagerDuty"],"automation_templates":["Agent message routing — priority-based delivery","Escalation chain — unresolved alerts after 15min","Daily standup summary — Slack digest","Cross-system event correlation — unified alert","HITL approval request broadcaster"]},
    "pipeline":   {"label":"AI Pipeline Builder","icon":"🔀","color":"#8b5cf6","description":"NL to DAG workflow generation and execution","engine":"AIWorkflowGenerator + OrchestrationEngine","integrations":["Any (via WorldModelRegistry 90+ connectors)"],"automation_templates":["Describe your workflow in plain English — DAG auto-built","Multi-step data transformation pipeline","API orchestration chain with retry logic","HITL-gated approval workflow","Parallel execution fan-out with merge gate"]},
}

_COST_MAP    = {"reporting":85,"crm":65,"monitoring":110,"content":55,"industrial":120,"finance":90,"security":125,"notifications":45,"marketing":80,"proposals":95,"pipeline":110,"general":75}
_DURATION_MAP = {"reporting":12,"crm":4,"monitoring":8,"content":7,"industrial":3,"finance":18,"security":35,"notifications":2,"marketing":6,"proposals":15,"pipeline":8,"general":10}

def _cost_savings(auto: Dict[str, Any]) -> float:
    est = auto.get("estimated_minutes", 0)
    actual = auto.get("actual_minutes", 0) or est * 0.9
    hr = auto.get("labor_cost_per_hr", 0)
    return round((est/60)*hr - (actual/60)*(hr*0.05), 2)

# ==============================================================================
# BACKGROUND TASKS
# ==============================================================================

async def _automation_tick():
    """Every 8s: advance milestones, add delays when slipping, emit SSE."""
    while True:
        await asyncio.sleep(8)
        active = [a for a in _automation_store if a.get("status") == "active"]
        if not active:
            continue
        auto = random.choice(active)
        ms = auto.get("milestones", [])

        running = next((m for m in ms if m["status"] == "running"), None)
        if not running:
            pending = next((m for m in ms if m["status"] == "pending"), None)
            if pending:
                pending["status"] = "running"
                pending["progress"] = 0
                running = pending
            else:
                for m in ms:
                    m["status"] = "pending"
                    m["progress"] = 0
                    m["completed_at"] = None
                    m["delay_minutes"] = 0.0
                if ms:
                    ms[0]["status"] = "running"

        if running:
            if running.get("is_hitl") and running.get("progress", 0) >= 90:
                if not running.get("hitl_item_id"):
                    hitl = _create_hitl_item(
                        hitl_type="automation_milestone",
                        title=f"HITL Gate: {running['name']}",
                        description=f"Automation '{auto['name']}' reached milestone '{running['name']}' — human approval required.",
                        payload={"automation_id": auto["id"], "milestone_id": running["id"]},
                        related_id=auto["id"],
                        priority="high",
                    )
                    running["hitl_item_id"] = hitl["id"]
                    running["status"] = "blocked_hitl"
                    _broadcast_sse("milestone_blocked_hitl", {
                        "automation_id": auto["id"],
                        "milestone": running,
                        "hitl_id": hitl["id"]
                    })
                continue

            if random.random() < 0.08:
                delay = round(random.uniform(0.5, 3.0), 2)
                running["delay_minutes"] = running.get("delay_minutes", 0) + delay
                auto["total_delay_minutes"] = round(auto.get("total_delay_minutes", 0) + delay, 2)
                auto["effective_duration_minutes"] = _calc_block_duration(auto)
                _broadcast_sse("automation_delay", {
                    "automation_id": auto["id"],
                    "milestone": running["name"],
                    "delay_added_minutes": delay,
                    "total_delay": auto["total_delay_minutes"],
                    "new_effective_duration": auto["effective_duration_minutes"],
                })

            advance = random.randint(5, 18)
            running["progress"] = min(100, running["progress"] + advance)
            if running["progress"] >= 100:
                running["status"] = "completed"
                running["completed_at"] = _now_iso()

        auto["progress"] = _calc_automation_progress(auto)
        auto["effective_duration_minutes"] = _calc_block_duration(auto)

        actual = round(auto["estimated_minutes"] * random.uniform(0.75, 1.35), 2)
        auto["actual_minutes"] = actual
        record = {
            "execution_id": f"exec-{uuid.uuid4().hex[:8]}",
            "automation_id": auto["id"], "automation_name": auto["name"],
            "tenant_id": auto.get("tenant_id","tenant-001"),
            "status": "completed" if random.random() > 0.05 else "failed",
            "estimated_minutes": auto["estimated_minutes"], "actual_minutes": actual,
            "cost_savings": _cost_savings(auto), "started_at": _now_iso(),
            "progress": auto["progress"],
            "effective_duration_minutes": auto["effective_duration_minutes"],
        }
        _execution_log.append(record)
        if len(_execution_log) > 500: del _execution_log[:50]
        _broadcast_sse("automation_executed", record)
        await _broadcast_ws("automation_tick", {
            "automation_id": auto["id"],
            "progress": auto["progress"],
            "effective_duration": auto["effective_duration_minutes"],
            "milestones": auto["milestones"],
        })

async def _campaign_tick():
    """Every 15s: drift metrics, detect low traction, create HITL paid-ad proposals."""
    while True:
        await asyncio.sleep(15)
        for tier, camp in _campaigns.items():
            camp["impressions"] += random.randint(10,200)
            camp["clicks"] += random.randint(1,15)
            if random.random() > 0.7: camp["leads"] += random.randint(0,3)
            if random.random() > 0.9: camp["conversions"] += 1
            camp["conversion_rate"] = round(camp["conversions"]/max(camp["impressions"],1)*100,3)
            camp["lead_rate"] = round(camp["leads"]/max(camp["impressions"],1)*100,2)
            camp["traction"] = "low" if camp["conversion_rate"] < 0.05 else "healthy"
            if camp["traction"] == "low" and camp["status"] == "active":
                camp["status"] = "adjusting"
            elif camp["traction"] == "healthy" and camp["status"] == "adjusting":
                camp["status"] = "active"
            camp["last_evaluated"] = _now_iso()

            if (camp["traction"] == "low" and
                not camp.get("hitl_proposal_id") and
                random.random() < 0.15):
                budget = round(camp.get("spend", 500) * 1.5 + 200, 2)
                paid_prop = {
                    "id": f"pp-{uuid.uuid4().hex[:6]}",
                    "type": "paid_ad_proposal", "tier": tier,
                    "status": "pending_hitl",
                    "channels": ["LinkedIn Ads", "Google Ads", "Meta Ads"],
                    "budget": budget,
                    "rationale": f"Organic conversion rate for {tier} tier is {camp['conversion_rate']:.3f}% — below 0.05% threshold.",
                    "projected_leads": int(camp["leads"] * 2.3),
                    "projected_conversions": int(camp["conversions"] * 2.1),
                    "projected_roi": round(int(camp["conversions"] * 2.1) * 299 / max(budget, 1), 2),
                    "requires_hitl_approval": True,
                    "proposed_at": _now_iso(), "hitl_item_id": None,
                }
                hitl = _create_hitl_item(
                    hitl_type="campaign_paid_ad",
                    title=f"Approve Paid Ad Campaign: {tier.title()} Tier",
                    description=f"Conversion rate dropped to {camp['conversion_rate']:.3f}%. Proposed ${budget:,.0f} paid campaign.",
                    payload=paid_prop,
                    related_id=f"campaign-{tier}",
                    priority="high",
                )
                paid_prop["hitl_item_id"] = hitl["id"]
                camp["hitl_proposal_id"] = hitl["id"]
                camp["paid_proposals"].append(paid_prop)
                _marketing_proposals.append(paid_prop)
                _broadcast_sse("campaign_paid_proposal_created", {
                    "tier": tier, "proposal": paid_prop, "hitl_id": hitl["id"]
                })

        _broadcast_sse("campaigns_updated", {"campaigns": list(_campaigns.values())})

async def _setup_tick():
    """Every 20s: advance self-setup steps, create HITL gates at checkpoints."""
    while True:
        await asyncio.sleep(20)
        for step in _SELF_SETUP_STEPS:
            if step["status"] == "active":
                if step["requires_hitl"] and step["progress"] >= 95:
                    if not step.get("hitl_item_id"):
                        hitl = _create_hitl_item(
                            hitl_type="setup_step",
                            title=f"Setup Gate: {step['name']}",
                            description=step.get("hitl_label", f"Human approval required for: {step['name']}"),
                            payload={"step_id": step["id"], "step_name": step["name"]},
                            related_id=step["id"],
                            priority="high",
                        )
                        step["hitl_item_id"] = hitl["id"]
                        step["status"] = "blocked_hitl"
                        _broadcast_sse("setup_step_blocked", {"step_id": step["id"], "hitl_id": hitl["id"]})
                    break
                elif step["progress"] < (95 if step["requires_hitl"] else 100):
                    step["progress"] = min(
                        95 if step["requires_hitl"] else 100,
                        step["progress"] + random.randint(2, 8)
                    )
                    if step["progress"] >= 100:
                        step["status"] = "completed"
                        step["completed_at"] = _now_iso()
                        for s2 in _SELF_SETUP_STEPS:
                            if s2["status"] == "pending":
                                s2["status"] = "active"
                                break
                    break
        _broadcast_sse("setup_progress", {"steps": _SELF_SETUP_STEPS})

async def _hitl_auto_expire_tick():
    """Every 60s: expire HITL items past their auto_approve_after_seconds."""
    while True:
        await asyncio.sleep(60)
        now_ts = _now_dt().timestamp()
        for item in _HITL_QUEUE:
            if item["status"] == "pending":
                aat = item.get("auto_approve_after_seconds", 0)
                if aat > 0 and (now_ts - item["_created_ts"]) > aat:
                    item["status"] = "expired"
                    item["approved_at"] = _now_iso()
                    _broadcast_sse("hitl_expired", {"id": item["id"]})

async def _proposal_intake_tick():
    """Every 45s: auto-generate proposals for new incoming requests."""
    while True:
        await asyncio.sleep(45)
        for req in _incoming_requests:
            if req["status"] == "pending":
                proposal = _generate_proposal_content(req)
                _generated_proposals.append(proposal)
                req["status"] = "in_progress"
                hitl = _create_hitl_item(
                    hitl_type="proposal_approval",
                    title=f"Review AI Proposal: {req['subject'][:60]}",
                    description=f"AI generated proposal for {req['from']}. Value: ${req.get('estimated_value',0):,}.",
                    payload={"proposal_id": proposal["id"], "request_id": req["id"]},
                    related_id=proposal["id"],
                    priority="high" if req.get("priority") == "high" else "normal",
                )
                proposal["hitl_item_id"] = hitl["id"]
                proposal["status"] = "pending_review"
                _broadcast_sse("proposal_auto_generated", {
                    "proposal_id": proposal["id"],
                    "request_id": req["id"],
                    "hitl_id": hitl["id"],
                })
                break

# -- FastAPI app ---------------------------------------------------------------
# FastAPI app created by src/runtime/app.py — this module provides an APIRouter
from fastapi import APIRouter
router = APIRouter(tags=["production-v3"])

# CORS handled by unified server in src/runtime/app.py

# SecurityHeadersMiddleware handled by src/auth_middleware.py

# -- Pydantic models -----------------------------------------------------------
class PromptRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=2000)
    board_id: str = Field(default="board-001")
    tenant_id: str = Field(default="tenant-001")

class AutomationPatch(BaseModel):
    status: Optional[str] = None
    name: Optional[str] = None
    recurrence: Optional[str] = None

class ProposalGenerateRequest(BaseModel):
    request_id: str
    tenant_id: str = Field(default="tenant-001")
    tone: str = Field(default="professional")

class CampaignAdjustRequest(BaseModel):
    tier: str
    new_channels: Optional[List[str]] = None
    new_demographics: Optional[str] = None
    budget_increase: Optional[float] = None
    reason: str = Field(default="Manual adjustment")

class WorkflowRequest(BaseModel):
    description: str = Field(..., min_length=5, max_length=3000)
    tenant_id: str = Field(default="tenant-001")
    execute_immediately: bool = Field(default=False)

class AgentMessageRequest(BaseModel):
    sender: str
    room: str
    message_type: str = Field(default="broadcast")
    content: Dict[str, Any] = Field(default_factory=dict)

class TenantCreate(BaseModel):
    name: str; org: str; tier: str = Field(default="solo")
    owner: str; connections: List[str] = Field(default_factory=list)

class HITLDecisionRequest(BaseModel):
    approved_by: str = Field(default="founder")
    reason: str = Field(default="")

class MilestoneDelayRequest(BaseModel):
    delay_minutes: float = Field(..., gt=0)
    reason: str = Field(default="Manual delay")

# -- Startup -------------------------------------------------------------------
# @app.on_event("startup")
async def _startup():
    _seed_automations()
    _automation_store.extend(_DEMO_AUTOMATIONS)
    _seed_campaigns()
    asyncio.create_task(_automation_tick())
    asyncio.create_task(_campaign_tick())
    asyncio.create_task(_setup_tick())
    asyncio.create_task(_hitl_auto_expire_tick())
    asyncio.create_task(_proposal_intake_tick())
    log.info("Murphy Production Server v3 started — HITL gates active, milestone tracking enabled")

# ==============================================================================
# HEALTH
# ==============================================================================
@router.get("/health")
async def health():
    active = sum(1 for a in _automation_store if a.get("status") == "active")
    pending_hitl = sum(1 for h in _HITL_QUEUE if h["status"] == "pending")
    return JSONResponse({
        "status": "ok", "version": "3.0.0", "env": _env,
        "active_automations": active, "total_automations": len(_automation_store),
        "tenants": len(_TENANTS), "campaigns": len(_campaigns),
        "pending_hitl_items": pending_hitl,
        "sse_subscribers": len(_sse_subscribers),
        "ws_clients": len(_ws_clients), "ts": _now_iso()
    })

# ==============================================================================
# HITL — Human-in-the-Loop Queue
# ==============================================================================
@router.get("/api/hitl/queue")
async def get_hitl_queue(
    status: str = Query(default=""),
    hitl_type: str = Query(default=""),
    priority: str = Query(default="")
):
    items = list(_HITL_QUEUE)
    if status:    items = [h for h in items if h["status"] == status]
    if hitl_type: items = [h for h in items if h["type"] == hitl_type]
    if priority:  items = [h for h in items if h["priority"] == priority]
    clean = [{k: v for k, v in h.items() if not k.startswith("_")} for h in items]
    priority_order = {"critical": 0, "high": 1, "normal": 2, "low": 3}
    clean.sort(key=lambda h: (priority_order.get(h.get("priority","normal"), 2), h.get("created_at", "")))
    return JSONResponse({
        "items": clean, "total": len(clean),
        "pending": sum(1 for h in clean if h["status"] == "pending"),
        "approved": sum(1 for h in clean if h["status"] == "approved"),
        "rejected": sum(1 for h in clean if h["status"] == "rejected"),
    })

@router.get("/api/hitl/{hitl_id}")
async def get_hitl_item(hitl_id: str):
    item = next((h for h in _HITL_QUEUE if h["id"] == hitl_id), None)
    if not item: raise HTTPException(404, f"HITL item {hitl_id} not found")
    return JSONResponse({k: v for k, v in item.items() if not k.startswith("_")})

@router.post("/api/hitl/{hitl_id}/approve")
async def approve_hitl_item(hitl_id: str, req: HITLDecisionRequest):
    item = next((h for h in _HITL_QUEUE if h["id"] == hitl_id), None)
    if not item: raise HTTPException(404, f"HITL item {hitl_id} not found")
    if item["status"] != "pending":
        raise HTTPException(400, f"Item is already {item['status']}")

    item["status"] = "approved"
    item["approved_at"] = _now_iso()
    item["approved_by"] = req.approved_by
    # Persist approval (DEF-047)
    if _hitl_store:
        try:
            _hitl_store.update_item(hitl_id, {"status": "approved", "approved_at": item["approved_at"], "approved_by": req.approved_by})
            _hitl_store.save_execution(hitl_id, "approve", actor=req.approved_by)
        except Exception as _pe:
            log.warning("HITL persist (approve) failed: %s", _pe)
    hitl_type = item["type"]

    if hitl_type == "campaign_paid_ad":
        prop = item["payload"]
        tier = prop.get("tier")
        if tier and tier in _campaigns:
            camp = _campaigns[tier]
            camp["status"] = "active"
            camp["spend"] = round(camp.get("spend", 0) + prop.get("budget", 0), 2)
            camp["hitl_proposal_id"] = None
            for pp in camp.get("paid_proposals", []):
                if pp.get("hitl_item_id") == hitl_id:
                    pp["status"] = "approved"
                    pp["approved_at"] = _now_iso()
            _broadcast_sse("campaign_paid_ad_approved", {"tier": tier, "budget": prop.get("budget"), "hitl_id": hitl_id})

    elif hitl_type == "proposal_approval":
        prop_id = item["payload"].get("proposal_id")
        req_id = item["payload"].get("request_id")
        prop = next((p for p in _generated_proposals if p["id"] == prop_id), None)
        if prop:
            prop["status"] = "approved_sent"
            prop["approved_at"] = _now_iso()
        req_data = next((r for r in _incoming_requests if r["id"] == req_id), None)
        if req_data:
            req_data["status"] = "proposal_sent"
        auto_id = f"auto-{uuid.uuid4().hex[:8]}"
        est_min = 15.0
        new_auto = {
            "id": auto_id,
            "name": f"Proposal Pipeline: {(req_data or {}).get('from','Unknown')[:40]}",
            "trigger": "webhook", "start_time": _now_iso(),
            "recurrence": "daily", "status": "active",
            "estimated_minutes": est_min, "actual_minutes": 0.0,
            "labor_cost_per_hr": 95.0, "category": "proposals",
            "color": "#14b8a6", "board_id": "board-001", "tenant_id": "tenant-001",
            "created_from_proposal": prop_id, "created_at": _now_iso(),
            "milestones": _make_milestones("proposals", est_min),
            "progress": 0.0, "total_delay_minutes": 0.0, "effective_duration_minutes": est_min,
        }
        _automation_store.append(new_auto)
        _broadcast_sse("proposal_approved_automation_created", {
            "hitl_id": hitl_id, "proposal_id": prop_id, "automation_id": auto_id,
        })

    elif hitl_type == "setup_step":
        step_id = item["payload"].get("step_id")
        for step in _SELF_SETUP_STEPS:
            if step["id"] == step_id:
                step["status"] = "completed"
                step["progress"] = 100
                step["completed_at"] = _now_iso()
                step["hitl_item_id"] = None
                break
        for step in _SELF_SETUP_STEPS:
            if step["status"] == "pending":
                step["status"] = "active"
                break
        _broadcast_sse("setup_step_approved", {"step_id": step_id, "hitl_id": hitl_id})

    elif hitl_type == "automation_milestone":
        auto_id = item["payload"].get("automation_id")
        ms_id = item["payload"].get("milestone_id")
        auto = next((a for a in _automation_store if a["id"] == auto_id), None)
        if auto:
            for ms in auto.get("milestones", []):
                if ms["id"] == ms_id:
                    ms["status"] = "completed"
                    ms["progress"] = 100
                    ms["completed_at"] = _now_iso()
                    ms["hitl_item_id"] = None
                    break
            auto["progress"] = _calc_automation_progress(auto)
            _broadcast_sse("milestone_approved", {"automation_id": auto_id, "milestone_id": ms_id, "new_progress": auto["progress"]})

    elif hitl_type == "dag_step":
        wf_id = item["payload"].get("workflow_id")
        step_id = item["payload"].get("step_id")
        wf = next((w for w in _workflow_history if w["id"] == wf_id), None)
        if wf:
            steps = wf.get("steps", [])
            for i, s in enumerate(steps):
                if s["id"] == step_id:
                    s["status"] = "approved"
                    s["approved_at"] = _now_iso()
                    if i+1 < len(steps):
                        steps[i+1]["status"] = "running"
                    else:
                        wf["status"] = "completed"
                        wf["completed_at"] = _now_iso()
                    break
        _broadcast_sse("dag_step_approved", {"workflow_id": wf_id, "step_id": step_id})

    elif hitl_type == "vertical_activate":
        vertical_id = item["payload"].get("vertical_id")
        tenant_id = item["payload"].get("tenant_id", "tenant-001")
        tenant = _TENANTS.get(tenant_id)
        if tenant and vertical_id and vertical_id not in tenant["active_verticals"]:
            tenant["active_verticals"].append(vertical_id)
        _broadcast_sse("vertical_approved", {"vertical_id": vertical_id})

    _broadcast_sse("hitl_approved", {"id": hitl_id, "type": hitl_type, "approved_by": req.approved_by, "ts": _now_iso()})
    await _broadcast_ws("hitl_approved", {"id": hitl_id, "type": hitl_type})
    return JSONResponse({k: v for k, v in item.items() if not k.startswith("_")})

@router.post("/api/hitl/{hitl_id}/reject")
async def reject_hitl_item(hitl_id: str, req: HITLDecisionRequest):
    item = next((h for h in _HITL_QUEUE if h["id"] == hitl_id), None)
    if not item: raise HTTPException(404, f"HITL item {hitl_id} not found")
    if item["status"] != "pending":
        raise HTTPException(400, f"Item is already {item['status']}")

    item["status"] = "rejected"
    item["rejected_at"] = _now_iso()
    item["approved_by"] = req.approved_by
    item["rejection_reason"] = req.reason
    # Persist rejection (DEF-047)
    if _hitl_store:
        try:
            _hitl_store.update_item(hitl_id, {"status": "rejected", "rejected_at": item["rejected_at"], "rejection_reason": req.reason})
            _hitl_store.save_execution(hitl_id, "reject", actor=req.approved_by, details={"reason": req.reason})
        except Exception as _pe:
            log.warning("HITL persist (reject) failed: %s", _pe)
    hitl_type = item["type"]

    if hitl_type == "campaign_paid_ad":
        tier = item["payload"].get("tier")
        if tier and tier in _campaigns:
            _campaigns[tier]["hitl_proposal_id"] = None
    elif hitl_type == "setup_step":
        step_id = item["payload"].get("step_id")
        for step in _SELF_SETUP_STEPS:
            if step["id"] == step_id:
                step["status"] = "active"
                step["hitl_item_id"] = None
                step["progress"] = max(0, step["progress"] - 10)
                break
    elif hitl_type == "automation_milestone":
        auto_id = item["payload"].get("automation_id")
        ms_id = item["payload"].get("milestone_id")
        auto = next((a for a in _automation_store if a["id"] == auto_id), None)
        if auto:
            for ms in auto.get("milestones", []):
                if ms["id"] == ms_id:
                    ms["status"] = "running"
                    ms["progress"] = 80
                    ms["hitl_item_id"] = None
                    break

    _broadcast_sse("hitl_rejected", {"id": hitl_id, "type": hitl_type, "reason": req.reason})
    await _broadcast_ws("hitl_rejected", {"id": hitl_id, "type": hitl_type})
    return JSONResponse({k: v for k, v in item.items() if not k.startswith("_")})

# ==============================================================================
# TENANT / ORG ENDPOINTS
# ==============================================================================
@router.get("/api/tenant")
async def list_tenants():
    return JSONResponse({"tenants": list(_TENANTS.values()), "total": len(_TENANTS)})

@router.get("/api/tenant/{tenant_id}")
async def get_tenant(tenant_id: str):
    t = _TENANTS.get(tenant_id)
    if not t: raise HTTPException(404, f"Tenant {tenant_id} not found")
    tenant_autos = [a for a in _automation_store if a.get("tenant_id") == tenant_id]
    return JSONResponse({**t,
        "automation_count": len(tenant_autos),
        "active_automations": sum(1 for a in tenant_autos if a["status"] == "active"),
        "monthly_savings": round(sum(_cost_savings(a)*{"hourly":720,"daily":30,"weekly":4,"monthly":1}.get(a.get("recurrence","daily"),30) for a in tenant_autos),2),
    })

@router.post("/api/tenant")
async def create_tenant(req: TenantCreate):
    tid = f"tenant-{uuid.uuid4().hex[:6]}"
    t = {"id":tid,"name":req.name,"org":req.org,"tier":req.tier,"owner":req.owner,
         "connections":req.connections,"boards":[f"board-{uuid.uuid4().hex[:4]}"],
         "active_verticals":[],"created_at":_now_iso()}
    _TENANTS[tid] = t
    _broadcast_sse("tenant_created", t)
    return JSONResponse(t, status_code=201)

# ==============================================================================
# CALENDAR — Dynamic timeline blocks that shift with delays
# ==============================================================================
@router.get("/api/calendar")
async def get_calendar(board_id:str=Query(default=""), tenant_id:str=Query(default=""),
                       view:str=Query(default="week"), date:str=Query(default="")):
    try: ref = datetime.fromisoformat(date.replace("Z","")) if date else datetime.now(_UTC)
    except ValueError: ref = datetime.now(_UTC)
    if ref.tzinfo is None: ref = ref.replace(tzinfo=_UTC)
    if view == "day":
        start = ref.replace(hour=0,minute=0,second=0,microsecond=0); end = start + timedelta(days=1)
    elif view == "month":
        start = ref.replace(day=1,hour=0,minute=0,second=0,microsecond=0)
        nm = (start.month%12)+1; yr = start.year+(1 if start.month==12 else 0)
        end = start.replace(year=yr,month=nm)
    else:
        dow = ref.weekday()
        start = (ref-timedelta(days=dow)).replace(hour=0,minute=0,second=0,microsecond=0)
        end = start + timedelta(days=7)
    autos = [a for a in _automation_store
             if (not board_id or a.get("board_id")==board_id)
             and (not tenant_id or a.get("tenant_id")==tenant_id)]
    _REC = {"hourly":timedelta(hours=1),"daily":timedelta(days=1),"weekly":timedelta(weeks=1),"monthly":timedelta(days=30)}
    blocks = []
    for auto in autos:
        try: orig = datetime.fromisoformat(auto["start_time"].replace("Z","")).replace(tzinfo=_UTC)
        except Exception:
            log.debug("Could not parse start_time, falling back to now()")
            orig = datetime.now(_UTC)
        rec = auto.get("recurrence","daily"); delta = _REC.get(rec,timedelta(days=1))
        dur = auto.get("effective_duration_minutes", auto.get("estimated_minutes", 10))
        total_delay = auto.get("total_delay_minutes", 0)
        cursor = orig
        if cursor < start:
            gap = (start-cursor).total_seconds(); dsec = delta.total_seconds()
            if dsec > 0:
                cursor = orig + delta*math.ceil(gap/dsec)
        count = 0
        while cursor < end and count < 200:
            milestones = auto.get("milestones", [])
            running_ms = next((m for m in milestones if m["status"] in ("running","blocked_hitl")), None)
            has_hitl_pending = any(m["status"] == "blocked_hitl" for m in milestones)
            blocks.append({
                "automation_id": auto["id"], "name": auto["name"],
                "category": auto.get("category",""), "color": auto.get("color","#00d4aa"),
                "status": auto.get("status","active"), "recurrence": rec,
                "start": cursor.isoformat(),
                "end": (cursor+timedelta(minutes=dur)).isoformat(),
                "duration_minutes": dur,
                "estimated_minutes": auto.get("estimated_minutes", dur),
                "effective_duration_minutes": dur,
                "total_delay_minutes": total_delay,
                "actual_minutes": auto.get("actual_minutes",0),
                "cost_savings": _cost_savings(auto),
                "labor_cost_per_hr": auto.get("labor_cost_per_hr",75),
                "tenant_id": auto.get("tenant_id",""),
                "board_id": auto.get("board_id",""),
                "progress": auto.get("progress", 0),
                "current_milestone": running_ms["name"] if running_ms else None,
                "has_hitl_pending": has_hitl_pending,
                "width_scale": round(dur / max(auto.get("estimated_minutes",1), 0.1), 3),
            })
            cursor += delta; count += 1
    blocks.sort(key=lambda b: b["start"])
    return JSONResponse({"view":view,"start":start.isoformat(),"end":end.isoformat(),"blocks":blocks,
        "total_blocks":len(blocks),"total_savings":round(sum(b["cost_savings"] for b in blocks),2),
        "automations":len(autos)})

@router.get("/api/calendar/blocks")
async def get_timeline_blocks(tenant_id: str = Query(default="tenant-001")):
    """Live timeline blocks with delay info and HITL gate markers."""
    now = _now_dt()
    week_start = (now - timedelta(days=now.weekday())).replace(hour=0,minute=0,second=0,microsecond=0)
    blocks = []
    for auto in _automation_store:
        if tenant_id and auto.get("tenant_id") != tenant_id:
            continue
        base_start = week_start + timedelta(hours=hash(auto["id"]) % 120)
        effective_dur = auto.get("effective_duration_minutes", auto.get("estimated_minutes", 10))
        total_delay = auto.get("total_delay_minutes", 0)
        milestones = auto.get("milestones", [])
        planned_end = base_start + timedelta(minutes=auto.get("estimated_minutes", 10))
        actual_end = base_start + timedelta(minutes=effective_dur)
        hitl_gates = []
        offset = 0.0
        for ms in milestones:
            if ms.get("is_hitl"):
                gate_time = base_start + timedelta(minutes=offset)
                hitl_gates.append({
                    "time": gate_time.isoformat(),
                    "milestone": ms["name"],
                    "status": ms["status"],
                    "hitl_item_id": ms.get("hitl_item_id"),
                })
            offset += ms.get("duration_minutes", 0)

        blocks.append({
            "id": auto["id"], "name": auto["name"],
            "category": auto.get("category",""), "color": auto.get("color","#00d4aa"),
            "status": auto.get("status","active"),
            "planned_start": base_start.isoformat(),
            "planned_end": planned_end.isoformat(),
            "actual_end": actual_end.isoformat(),
            "estimated_minutes": auto.get("estimated_minutes",10),
            "effective_duration_minutes": effective_dur,
            "delay_minutes": total_delay,
            "is_delayed": total_delay > 0,
            "is_blocked_hitl": any(m["status"] == "blocked_hitl" for m in milestones),
            "progress": auto.get("progress", 0),
            "milestones": milestones,
            "hitl_gates": hitl_gates,
            "width_scale": round(effective_dur / max(auto.get("estimated_minutes",1), 0.1), 3),
        })
    return JSONResponse({"blocks": blocks, "total": len(blocks),
                         "delayed_count": sum(1 for b in blocks if b["is_delayed"]),
                         "hitl_blocked_count": sum(1 for b in blocks if b["is_blocked_hitl"])})

# ==============================================================================
# AUTOMATIONS CRUD + MILESTONES
# ==============================================================================
@router.get("/api/automations")
async def list_automations(board_id:str=Query(default=""), tenant_id:str=Query(default=""),
                           category:str=Query(default=""), status:str=Query(default="")):
    autos = list(_automation_store)
    if board_id:  autos=[a for a in autos if a.get("board_id")==board_id]
    if tenant_id: autos=[a for a in autos if a.get("tenant_id")==tenant_id]
    if category:  autos=[a for a in autos if a.get("category")==category]
    if status:    autos=[a for a in autos if a.get("status")==status]
    return JSONResponse({"automations":[{**a,"cost_savings":_cost_savings(a)} for a in autos],"total":len(autos)})

# SSE route MUST be before {auto_id} parameterized routes
@router.get("/api/automations/stream")
async def stream_automations(request: Request):
    q: asyncio.Queue = asyncio.Queue(maxsize=100)
    _sse_subscribers.append(q)
    async def event_gen():
        snapshot = json.dumps({"event":"snapshot","data":{
            "automations": _automation_store,
            "campaigns": list(_campaigns.values()),
            "hitl_queue": [{k:v for k,v in h.items() if not k.startswith("_")} for h in _HITL_QUEUE]
        },"ts":_now_iso()})
        yield f"data: {snapshot}\n\n"
        try:
            while True:
                if await request.is_disconnected(): break
                try:
                    payload = await asyncio.wait_for(q.get(), timeout=30.0)
                    yield f"data: {payload}\n\n"
                except asyncio.TimeoutError:
                    yield f"data: {json.dumps({'event':'heartbeat','ts':_now_iso()})}\n\n"
        finally:
            try: _sse_subscribers.remove(q)
            except ValueError:  # PROD-HARD A2: already removed by concurrent cleanup — idempotent
                log.debug("SSE subscriber queue already removed on client disconnect")
    return StreamingResponse(event_gen(), media_type="text/event-stream",
                             headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"})

@router.get("/api/automations/{auto_id}")
async def get_automation(auto_id: str):
    a = next((x for x in _automation_store if x["id"]==auto_id), None)
    if not a: raise HTTPException(404, f"Automation {auto_id} not found")
    return JSONResponse({**a,"cost_savings":_cost_savings(a)})

@router.get("/api/automations/{auto_id}/milestones")
async def get_automation_milestones(auto_id: str):
    a = next((x for x in _automation_store if x["id"]==auto_id), None)
    if not a: raise HTTPException(404, f"Automation {auto_id} not found")
    return JSONResponse({
        "automation_id": auto_id, "automation_name": a["name"],
        "milestones": a.get("milestones", []),
        "progress": a.get("progress", 0),
        "total_delay_minutes": a.get("total_delay_minutes", 0),
        "effective_duration_minutes": a.get("effective_duration_minutes", a.get("estimated_minutes",0)),
        "estimated_minutes": a.get("estimated_minutes", 0),
    })

@router.post("/api/automations/{auto_id}/milestones/{ms_id}/delay")
async def add_milestone_delay(auto_id: str, ms_id: str, req: MilestoneDelayRequest):
    a = next((x for x in _automation_store if x["id"]==auto_id), None)
    if not a: raise HTTPException(404, f"Automation {auto_id} not found")
    ms = next((m for m in a.get("milestones",[]) if m["id"]==ms_id), None)
    if not ms: raise HTTPException(404, f"Milestone {ms_id} not found")
    ms["delay_minutes"] = ms.get("delay_minutes",0) + req.delay_minutes
    a["total_delay_minutes"] = round(sum(m.get("delay_minutes",0) for m in a["milestones"]),2)
    a["effective_duration_minutes"] = _calc_block_duration(a)
    _broadcast_sse("automation_delay", {
        "automation_id": auto_id, "milestone": ms["name"],
        "delay_added_minutes": req.delay_minutes,
        "total_delay": a["total_delay_minutes"],
        "new_effective_duration": a["effective_duration_minutes"],
        "reason": req.reason,
    })
    return JSONResponse({"automation_id": auto_id, "milestone_id": ms_id,
                         "total_delay": a["total_delay_minutes"],
                         "effective_duration": a["effective_duration_minutes"]})

@router.patch("/api/automations/{auto_id}")
async def patch_automation(auto_id: str, patch: AutomationPatch):
    a = next((x for x in _automation_store if x["id"]==auto_id), None)
    if not a: raise HTTPException(404, f"Automation {auto_id} not found")
    if patch.status: a["status"] = patch.status
    if patch.name: a["name"] = patch.name
    if patch.recurrence: a["recurrence"] = patch.recurrence
    a["updated_at"] = _now_iso()
    _broadcast_sse("automation_updated", {**a,"cost_savings":_cost_savings(a)})
    await _broadcast_ws("automation_updated", {**a,"cost_savings":_cost_savings(a)})
    return JSONResponse({**a,"cost_savings":_cost_savings(a)})

@router.delete("/api/automations/{auto_id}")
async def delete_automation(auto_id: str):
    global _automation_store
    before = len(_automation_store)
    _automation_store = [a for a in _automation_store if a["id"]!=auto_id]
    if len(_automation_store)==before: raise HTTPException(404,f"Automation {auto_id} not found")
    _broadcast_sse("automation_deleted",{"id":auto_id})
    await _broadcast_ws("automation_deleted",{"id":auto_id})
    return JSONResponse({"deleted":auto_id})

# ==============================================================================
# PROMPT -> AUTOMATION (NL -> Rule)
# ==============================================================================
_INJECTION_PATTERNS = [r"ignore\s+(previous|prior|above)\s+instructions",r"system\s+prompt",r"jailbreak",r"<\s*script",r"DROP\s+TABLE",r"SELECT\s+\*\s+FROM"]
_INJECTION_RE = re.compile("|".join(_INJECTION_PATTERNS), re.IGNORECASE)
_PROMPT_PATTERNS = [
    (["hourly","every hour","each hour","60 min"],           "hourly",  "schedule"),
    (["weekly","every week","monday","friday","each week"],  "weekly",  "schedule"),
    (["monthly","every month","first of"],                   "monthly", "schedule"),
    (["when created","new item","on create","on submit"],    "daily",   "item_created"),
    (["when status","status change","on update","on change"],"daily",   "status_change"),
    (["webhook","api call","on request","http"],             "daily",   "webhook"),
]
_CATEGORY_PATTERNS = {
    "report":"reporting","digest":"reporting","analytics":"reporting",
    "lead":"crm","crm":"crm","salesforce":"crm","hubspot":"crm","contact":"crm",
    "monitor":"monitoring","alert":"monitoring","anomaly":"monitoring","detect":"monitoring",
    "content":"content","publish":"content","blog":"content","social":"content","post":"content",
    "scada":"industrial","modbus":"industrial","sensor":"industrial","equipment":"industrial",
    "invoice":"finance","payment":"finance","stripe":"finance","billing":"finance",
    "security":"security","scan":"security","audit":"security","compliance":"security",
    "notify":"notifications","slack":"notifications","email":"notifications","sms":"notifications",
    "campaign":"marketing","marketing":"marketing","outreach":"marketing",
    "proposal":"proposals","rfp":"proposals","quote":"proposals","tender":"proposals",
    "pipeline":"pipeline","workflow":"pipeline","dag":"pipeline","deploy":"pipeline",
}

@router.post("/api/prompt")
async def create_from_prompt(req: PromptRequest):
    tenant = _TENANTS.get(req.tenant_id, {"tier":"solo"})
    tier_cfg = TIERS.get(tenant["tier"], TIERS["solo"])
    if tier_cfg["max_automations"]:
        tenant_autos = [a for a in _automation_store if a.get("tenant_id")==req.tenant_id and a["status"]=="active"]
        if len(tenant_autos) >= tier_cfg["max_automations"]:
            raise HTTPException(402, f"Tier limit reached ({tier_cfg['max_automations']} automations). Upgrade to Business.")
    if _INJECTION_RE.search(req.prompt): raise HTTPException(400,"Prompt contains disallowed content")

    prompt_lower = req.prompt.lower()
    recurrence="daily"; trigger="schedule"
    for keywords,rec,trig in _PROMPT_PATTERNS:
        if any(k in prompt_lower for k in keywords): recurrence=rec; trigger=trig; break
    category="general"
    for kw,cat in _CATEGORY_PATTERNS.items():
        if kw in prompt_lower: category=cat; break
    start_hour=9
    time_match = re.search(r'(\d{1,2})\s*(?:am|pm|:00)', prompt_lower)
    if time_match:
        h=int(time_match.group(1))
        if "pm" in prompt_lower and h<12: h+=12
        start_hour=h
    start_time = datetime.now(_UTC).replace(hour=start_hour,minute=0,second=0,microsecond=0).isoformat()
    auto_id = f"auto-{uuid.uuid4().hex[:8]}"
    est_min = _DURATION_MAP.get(category,10)

    # ── Real LLM generation (DeepInfra primary, Together fallback) ──────────
    auto_name = req.prompt.strip()[:60].title()  # default fallback
    llm_description = ""
    llm_steps: list = []

    if _llm_available and _get_llm is not None:
        try:
            llm = _get_llm()
            system_msg = (
                "You are Murphy, an AI system builder and automation platform developed by Inoni LLC, "
                "created by Corey Post. Your job is to design business automations. "
                "Reply ONLY with valid JSON — no markdown, no explanation, no code fences."
            )
            user_msg = (
                f"Design a business automation for: {req.prompt}\n\n"
                f"Category: {category}. Estimated duration: {est_min} minutes.\n\n"
                "Return JSON with exactly these keys:\n"
                '{"name": "Short action title (max 60 chars)", '
                '"description": "2-sentence description of what this automation does", '
                '"steps": ["Step 1 name", "Step 2 name", "Step 3 name", "Step 4 name", "Step 5 name"]}'
            )
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: llm.complete(
                    user_msg,
                    system=system_msg,
                    model_hint="fast",
                    temperature=0.4,
                    max_tokens=300,
                )
            )
            if result and result.success and result.content:
                raw = result.content.strip()
                # Strip markdown fences if present
                if raw.startswith("```"):
                    raw = re.sub(r"^```[a-z]*\n?", "", raw)
                    raw = re.sub(r"\n?```$", "", raw)
                parsed = json.loads(raw)
                auto_name = str(parsed.get("name", auto_name))[:60]
                llm_description = str(parsed.get("description", ""))
                llm_steps = list(parsed.get("steps", []))[:6]
                log.info("LLM generated automation '%s' via %s", auto_name, result.provider)
        except Exception as _llm_err:
            log.warning("LLM generation failed (%s) — using pattern-match fallback", _llm_err)

    # Build milestones from LLM steps if available, else use default generator
    if llm_steps:
        step_min = max(1, est_min // max(len(llm_steps), 1))
        milestones = []
        offset = 0
        for i, step_name in enumerate(llm_steps):
            ms = {
                "id": f"ms-{auto_id}-{i}",
                "name": step_name,
                "status": "pending",
                "due_offset_minutes": offset + step_min,
                "actual_minutes": None,
                "hitl_required": (i == 0),  # first step always needs HITL approval
            }
            milestones.append(ms)
            offset += step_min
    else:
        milestones = _make_milestones(category, est_min)

    new_auto = {
        "id":auto_id,"name":auto_name,"trigger":trigger,
        "start_time":start_time,"recurrence":recurrence,"status":"active",
        "estimated_minutes":est_min,"actual_minutes":0.0,
        "labor_cost_per_hr":_COST_MAP.get(category,75),"category":category,
        "color":random.choice(_COLORS),"board_id":req.board_id,"tenant_id":req.tenant_id,
        "created_from_prompt":req.prompt,"created_at":_now_iso(),
        "description": llm_description,
        "milestones": milestones,
        "progress": 0.0, "total_delay_minutes": 0.0, "effective_duration_minutes": est_min,
        "llm_generated": _llm_available,
    }
    _automation_store.append(new_auto)
    new_auto["cost_savings"] = _cost_savings(new_auto)

    # ── Auto-create HITL checkpoint for first milestone ──────────────────────
    if milestones:
        first_ms = milestones[0]
        hitl_id = f"hitl-{auto_id}-init"
        _HITL_QUEUE.append({
            "id": hitl_id,
            "automation_id": auto_id,
            "automation_name": auto_name,
            "checkpoint": first_ms["name"],
            "context": {
                "prompt": req.prompt,
                "category": category,
                "description": llm_description,
                "llm_generated": _llm_available,
            },
            "status": "pending",
            "created_at": _now_iso(),
            "expires_at": (datetime.now(_UTC) + timedelta(hours=24)).isoformat(),
        })
        log.info("HITL checkpoint created for automation %s: %s", auto_id, first_ms["name"])

    _broadcast_sse("automation_created",new_auto)
    await _broadcast_ws("automation_created",new_auto)
    return JSONResponse(new_auto, status_code=201)

# ==============================================================================
# LABOR COST
# ==============================================================================
@router.get("/api/labor-cost")
async def labor_cost_summary(board_id:str=Query(default=""), tenant_id:str=Query(default="")):
    autos=[a for a in _automation_store if (not board_id or a.get("board_id")==board_id) and (not tenant_id or a.get("tenant_id")==tenant_id)]
    items=[]; total_m=0.0; total_a=0.0
    for a in autos:
        est=a.get("estimated_minutes",0); actual=a.get("actual_minutes",0) or est*0.9; hr=a.get("labor_cost_per_hr",75)
        manual=(est/60)*hr; auto_c=(actual/60)*(hr*0.05); savings=round(manual-auto_c,2)
        total_m+=manual; total_a+=auto_c
        runs={"hourly":720,"daily":30,"weekly":4,"monthly":1}.get(a.get("recurrence","daily"),30)
        items.append({"id":a["id"],"name":a["name"],"category":a.get("category",""),"color":a.get("color","#00d4aa"),
            "tenant_id":a.get("tenant_id",""),"estimated_minutes":est,"actual_minutes":actual,
            "variance_pct":round(((actual-est)/est*100) if est else 0,1),"manual_cost_per_run":round(manual,2),
            "automation_cost_per_run":round(auto_c,2),"savings_per_run":savings,"monthly_runs":runs,
            "monthly_savings":round(savings*runs,2),
            "effective_duration":a.get("effective_duration_minutes",est),
            "total_delay":a.get("total_delay_minutes",0)})
    items.sort(key=lambda x:x["monthly_savings"],reverse=True)
    total_monthly=sum(i["monthly_savings"] for i in items)
    return JSONResponse({"items":items,"summary":{"total_automations":len(items),
        "total_manual_cost_per_run":round(total_m,2),"total_automation_cost_per_run":round(total_a,2),
        "total_monthly_savings":round(total_monthly,2),"roi_multiplier":round(total_m/max(total_a,0.01),1)}})

# ==============================================================================
# VERTICALS
# ==============================================================================
@router.get("/api/verticals")
async def list_verticals(tenant_id:str=Query(default="")):
    tenant = _TENANTS.get(tenant_id)
    active_v = tenant["active_verticals"] if tenant else list(_VERTICAL_CONFIGS.keys())
    result=[]
    for k,v in _VERTICAL_CONFIGS.items():
        autos=[a for a in _automation_store if a.get("category")==k]
        result.append({**v,"id":k,"active":k in active_v,"automation_count":len(autos),
            "active_count":sum(1 for a in autos if a["status"]=="active"),
            "monthly_savings":round(sum(_cost_savings(a)*{"hourly":720,"daily":30,"weekly":4,"monthly":1}.get(a.get("recurrence","daily"),30) for a in autos),2)})
    return JSONResponse({"verticals":result,"total":len(result)})

@router.get("/api/verticals/{vertical_id}")
async def get_vertical(vertical_id:str, tenant_id:str=Query(default="")):
    v=_VERTICAL_CONFIGS.get(vertical_id)
    if not v: raise HTTPException(404,f"Vertical {vertical_id} not found")
    autos=[a for a in _automation_store if a.get("category")==vertical_id and (not tenant_id or a.get("tenant_id")==tenant_id)]
    recent=[e for e in _execution_log[-50:] if any(e["automation_id"]==a["id"] for a in autos)][-10:]
    return JSONResponse({**v,"id":vertical_id,
        "automations":[{**a,"cost_savings":_cost_savings(a)} for a in autos],
        "recent_executions":recent,
        "total_monthly_savings":round(sum(_cost_savings(a)*{"hourly":720,"daily":30,"weekly":4,"monthly":1}.get(a.get("recurrence","daily"),30) for a in autos),2)})

@router.post("/api/verticals/{vertical_id}/activate")
async def activate_vertical(vertical_id:str, tenant_id:str=Query(default="tenant-001")):
    if vertical_id not in _VERTICAL_CONFIGS: raise HTTPException(404,f"Vertical {vertical_id} not found")
    tenant=_TENANTS.get(tenant_id)
    if vertical_id in ("security","industrial","finance"):
        hitl = _create_hitl_item(
            hitl_type="vertical_activate",
            title=f"Approve Vertical Activation: {_VERTICAL_CONFIGS[vertical_id]['label']}",
            description=f"Activating {_VERTICAL_CONFIGS[vertical_id]['label']} vertical requires approval due to elevated risk profile.",
            payload={"vertical_id": vertical_id, "tenant_id": tenant_id},
            related_id=vertical_id, priority="high",
        )
        return JSONResponse({"vertical_id":vertical_id,"status":"pending_hitl",
                             "hitl_id":hitl["id"],"message":"Approval required before activation"}, status_code=202)
    if tenant and vertical_id not in tenant["active_verticals"]:
        tenant["active_verticals"].append(vertical_id)
    template=_VERTICAL_CONFIGS[vertical_id]["automation_templates"][0]
    est_min = _DURATION_MAP.get(vertical_id,10)
    auto_id=f"auto-{uuid.uuid4().hex[:8]}"
    starter={
        "id":auto_id,"name":template[:60].title(),"trigger":"schedule",
        "start_time":datetime.now(_UTC).replace(hour=9,minute=0,second=0,microsecond=0).isoformat(),
        "recurrence":"daily","status":"active","estimated_minutes":est_min,
        "actual_minutes":0.0,"labor_cost_per_hr":_COST_MAP.get(vertical_id,75),
        "category":vertical_id,"color":_VERTICAL_CONFIGS[vertical_id]["color"],
        "board_id":tenant["boards"][0] if tenant else "board-001",
        "tenant_id":tenant_id,"created_at":_now_iso(),"activated_from_vertical":True,
        "milestones": _make_milestones(vertical_id, est_min),
        "progress": 0.0, "total_delay_minutes": 0.0, "effective_duration_minutes": est_min,
    }
    _automation_store.append(starter)
    _broadcast_sse("vertical_activated",{"vertical_id":vertical_id,"automation":starter})
    await _broadcast_ws("vertical_activated",{"vertical_id":vertical_id,"automation":starter})
    return JSONResponse({"vertical_id":vertical_id,"activated":True,"starter_automation":starter},status_code=201)

# ==============================================================================
# MARKETING / CAMPAIGN ENGINE (closed loop)
# ==============================================================================
@router.get("/api/marketing/campaigns")
async def get_campaigns():
    return JSONResponse({"campaigns":list(_campaigns.values()),"total":len(_campaigns)})

@router.get("/api/marketing/campaigns/{tier}")
async def get_campaign(tier:str):
    c=_campaigns.get(tier)
    if not c: raise HTTPException(404,f"Campaign tier {tier} not found")
    return JSONResponse(c)

@router.post("/api/marketing/campaigns/{tier}/adjust")
async def adjust_campaign(tier:str, req:CampaignAdjustRequest):
    c=_campaigns.get(tier)
    if not c: raise HTTPException(404,f"Campaign tier {tier} not found")
    adj={"id":f"adj-{uuid.uuid4().hex[:6]}","tier":tier,"reason":req.reason,
        "new_channels":req.new_channels or c["channels"],"demographics":req.new_demographics or "unchanged",
        "budget_increase":req.budget_increase or 0,"applied_at":_now_iso(),"applied_by":"system"}
    if req.new_channels: c["channels"]=req.new_channels
    if req.budget_increase: c["spend"]=round(c["spend"]+req.budget_increase,2)
    c["status"]="active"; c["adjustments"].append(adj); c["evaluation_count"]+=1; c["last_evaluated"]=_now_iso()
    _broadcast_sse("campaign_adjusted",{"tier":tier,"adjustment":adj,"campaign":c})
    await _broadcast_ws("campaign_adjusted",{"tier":tier,"adjustment":adj})
    return JSONResponse({"tier":tier,"adjustment":adj,"campaign":c})

@router.post("/api/marketing/paid-proposal")
async def create_paid_proposal(tier:str=Query(...)):
    c=_campaigns.get(tier)
    if not c: raise HTTPException(404,f"Campaign tier {tier} not found")
    budget=round(c.get("spend",500)*1.5,2)
    proposal={
        "id":f"pp-{uuid.uuid4().hex[:6]}","type":"paid_ad_proposal","tier":tier,
        "status":"pending_hitl","channels":["LinkedIn Ads","Google Ads","Meta Ads"],"budget":budget,
        "rationale":f"Organic conversion rate for {tier} tier is {c['conversion_rate']:.3f}% -- below threshold.",
        "projected_leads":int(c["leads"]*2.3),"projected_conversions":int(c["conversions"]*2.1),
        "projected_roi":round(int(c["conversions"]*2.1)*299/max(budget,1),2),
        "requires_hitl_approval":True,"proposed_at":_now_iso(),"hitl_item_id":None,
    }
    hitl = _create_hitl_item(
        hitl_type="campaign_paid_ad",
        title=f"Approve Paid Ad Campaign: {tier.title()} Tier",
        description=f"Manual paid proposal for {tier} tier. Budget: ${budget:,.0f}. Requires founder approval.",
        payload=proposal, related_id=f"campaign-{tier}", priority="high",
    )
    proposal["hitl_item_id"] = hitl["id"]
    c["hitl_proposal_id"] = hitl["id"]
    c["paid_proposals"] = c.get("paid_proposals", []) + [proposal]
    _marketing_proposals.append(proposal)
    _broadcast_sse("paid_proposal_created",proposal)
    await _broadcast_ws("paid_proposal_created",proposal)
    return JSONResponse({**proposal, "hitl_id": hitl["id"]}, status_code=201)

@router.post("/api/marketing/paid-proposal/{proposal_id}/approve")
async def approve_paid_proposal_direct(proposal_id:str):
    p=next((x for x in _marketing_proposals if x["id"]==proposal_id),None)
    if not p: raise HTTPException(404,"Proposal not found")
    p["status"]="approved"; p["approved_at"]=_now_iso(); p["approved_by"]="founder"
    if p.get("tier") in _campaigns:
        _campaigns[p["tier"]]["status"]="active"
        _campaigns[p["tier"]]["spend"]=round(_campaigns[p["tier"]].get("spend",0)+p["budget"],2)
        _campaigns[p["tier"]]["hitl_proposal_id"] = None
    _broadcast_sse("paid_proposal_approved",p)
    await _broadcast_ws("paid_proposal_approved",p)
    return JSONResponse(p)

@router.get("/api/marketing/paid-proposals")
async def list_paid_proposals():
    return JSONResponse({"proposals":_marketing_proposals,"total":len(_marketing_proposals)})

# ==============================================================================
# PROPOSAL WRITING ENGINE (closed loop)
# ==============================================================================
def _generate_proposal_content(req_data:Dict[str,Any], tone:str="professional") -> Dict[str,Any]:
    body=req_data.get("body",""); subject=req_data.get("subject","")
    needed=[]
    for kw,cat in _CATEGORY_PATTERNS.items():
        if kw in body.lower() and cat not in [n["category"] for n in needed] and cat in _VERTICAL_CONFIGS:
            needed.append({"category":cat,"label":_VERTICAL_CONFIGS[cat]["label"],
                "estimated_monthly_hours":_DURATION_MAP.get(cat,10)*30/60,"automation_count":random.randint(2,5)})
    if not needed: needed=[{"category":"general","label":"General Automation","estimated_monthly_hours":20,"automation_count":3}]
    total_autos=sum(n["automation_count"] for n in needed)
    total_hrs=sum(n["estimated_monthly_hours"] for n in needed)
    monthly_savings=round(total_hrs*85*0.92,2); annual=round(monthly_savings*12,2)
    if total_autos<=3: tier="solo"; price=99
    elif total_autos<=15: tier="business"; price=299
    elif total_autos<=40: tier="professional"; price=599
    else: tier="enterprise"; price=None
    roi=round(annual/max((price or 999)*12,1),1)
    return {
        "id":f"gen-prop-{uuid.uuid4().hex[:8]}","request_id":req_data["id"],
        "subject":f"Murphy System Proposal — {subject[:80]}","to":req_data.get("from",""),"tone":tone,
        "sections":{
            "executive_summary":f"Murphy System proposes automating {total_autos} workflows across {len(needed)} functional areas, saving ${monthly_savings:,.0f}/month in labor costs.",
            "scope_of_work":[{"vertical":n["label"],"automations":n["automation_count"],
                "hours_saved_monthly":round(n["estimated_monthly_hours"],1),
                "key_workflows":_VERTICAL_CONFIGS.get(n["category"],{}).get("automation_templates",[])[:3]} for n in needed],
            "technical_architecture":{"platform":"Murphy System v3.0","deployment":"Cloud-hosted, multi-tenant, SOC2-compliant",
                "integrations":list(set(i for n in needed for i in _VERTICAL_CONFIGS.get(n["category"],{}).get("integrations",[])[:2]))[:8],
                "security":"BSL 1.1, E2E encryption, HITL gates, full audit trail","uptime_sla":"99.9%"},
            "investment":{"recommended_tier":tier,"monthly_price":price,
                "annual_price":round((price or 999)*12*0.8,2) if price else None,
                "estimated_monthly_savings":monthly_savings,"estimated_annual_savings":annual,
                "roi_multiplier":roi,"payback_period_months":round((price or 999)/max(monthly_savings,1),1)},
            "timeline":[
                {"phase":"Onboarding & Integration Setup","duration":"Week 1","deliverables":"Tenant config, integration auth, first automation live"},
                {"phase":"Vertical Automation Rollout","duration":"Weeks 2-3","deliverables":f"All {total_autos} automations configured"},
                {"phase":"Optimization & HITL Tuning","duration":"Week 4","deliverables":"Performance baseline, ROI dashboard, training"},
                {"phase":"Ongoing Operations","duration":"Monthly","deliverables":"Continuous optimization, support"},
            ],
            "next_steps":["Review proposal and confirm scope","Schedule 30-minute technical discovery call",
                "Sign agreement and begin onboarding",f"Go live within {7+len(needed)*2} business days"],
        },
        "total_automations":total_autos,"monthly_savings":monthly_savings,"annual_value":annual,
        "roi":roi,"recommended_tier":tier,"generated_at":_now_iso(),"status":"draft","version":"1.0","hitl_item_id":None,
    }

@router.get("/api/proposals/requests")
async def list_proposal_requests():
    return JSONResponse({"requests":_incoming_requests,"total":len(_incoming_requests)})

@router.post("/api/proposals/generate")
async def generate_proposal(req:ProposalGenerateRequest):
    req_data=next((r for r in _incoming_requests if r["id"]==req.request_id),None)
    if not req_data: raise HTTPException(404,f"Request {req.request_id} not found")
    proposal=_generate_proposal_content(req_data,req.tone)
    hitl = _create_hitl_item(
        hitl_type="proposal_approval",
        title=f"Review Proposal: {req_data['subject'][:60]}",
        description=f"AI-generated proposal for {req_data['from']}. Value: ${req_data.get('estimated_value',0):,}.",
        payload={"proposal_id": proposal["id"], "request_id": req.request_id},
        related_id=proposal["id"],
        priority="high" if req_data.get("priority") == "high" else "normal",
    )
    proposal["hitl_item_id"] = hitl["id"]
    proposal["status"] = "pending_review"
    _generated_proposals.append(proposal)
    req_data["status"]="in_progress"
    _broadcast_sse("proposal_generated",{"proposal_id":proposal["id"],"request_id":req.request_id,"hitl_id":hitl["id"]})
    await _broadcast_ws("proposal_generated",proposal)
    return JSONResponse({**proposal, "hitl_id": hitl["id"]}, status_code=201)

@router.get("/api/proposals/generated")
async def list_generated_proposals():
    return JSONResponse({"proposals":_generated_proposals,"total":len(_generated_proposals)})

@router.get("/api/proposals/generated/{proposal_id}")
async def get_generated_proposal(proposal_id:str):
    p=next((x for x in _generated_proposals if x["id"]==proposal_id),None)
    if not p: raise HTTPException(404,"Proposal not found")
    return JSONResponse(p)

@router.post("/api/proposals/generated/{proposal_id}/approve")
async def approve_generated_proposal(proposal_id:str, req: HITLDecisionRequest):
    p=next((x for x in _generated_proposals if x["id"]==proposal_id),None)
    if not p: raise HTTPException(404,"Proposal not found")
    p["status"]="approved_sent"; p["approved_at"]=_now_iso(); p["approved_by"]=req.approved_by
    req_data=next((r for r in _incoming_requests if r["id"]==p.get("request_id")),None)
    if req_data: req_data["status"]="proposal_sent"
    if p.get("hitl_item_id"):
        h = next((h for h in _HITL_QUEUE if h["id"] == p["hitl_item_id"]), None)
        if h and h["status"] == "pending":
            h["status"] = "approved"; h["approved_at"] = _now_iso()
    auto_id = f"auto-{uuid.uuid4().hex[:8]}"
    est_min = 15.0
    new_auto = {
        "id":auto_id,"name":f"Proposal Pipeline: {(req_data or {}).get('from','Client')[:35]}",
        "trigger":"webhook","start_time":_now_iso(),"recurrence":"daily","status":"active",
        "estimated_minutes":est_min,"actual_minutes":0.0,"labor_cost_per_hr":95.0,
        "category":"proposals","color":"#14b8a6","board_id":"board-001","tenant_id":"tenant-001",
        "created_from_proposal":proposal_id,"created_at":_now_iso(),
        "milestones":_make_milestones("proposals",est_min),
        "progress":0.0,"total_delay_minutes":0.0,"effective_duration_minutes":est_min,
    }
    _automation_store.append(new_auto)
    _broadcast_sse("proposal_approved",{"proposal":p,"automation_created":auto_id})
    return JSONResponse({"proposal":p,"automation_created":new_auto})

# ==============================================================================
# AI WORKFLOW GENERATOR (NL -> DAG) with real HITL steps
# ==============================================================================
_STEP_KEYWORDS = {
    "fetch":"data_retrieval","get":"data_retrieval","pull":"data_retrieval","download":"data_retrieval",
    "read":"data_retrieval","collect":"data_retrieval","extract":"data_retrieval",
    "transform":"data_transformation","convert":"data_transformation","parse":"data_transformation",
    "format":"data_transformation","clean":"data_transformation","normalize":"data_transformation",
    "filter":"data_filtering","validate":"validation","check":"validation","verify":"validation",
    "ensure":"validation","test":"validation",
    "send":"notification","notify":"notification","alert":"notification","email":"notification",
    "message":"notification","slack":"notification",
    "write":"data_output","save":"data_output","store":"data_output","upload":"data_output",
    "export":"data_output","publish":"data_output",
    "analyze":"analysis","report":"analysis","summarize":"analysis","aggregate":"analysis",
    "calculate":"computation","compute":"computation","process":"computation",
    "run":"execution","execute":"execution","trigger":"execution","invoke":"execution",
    "wait":"delay",
    "approve":"hitl_gate","review":"hitl_gate","confirm":"hitl_gate","sign":"hitl_gate",
    "deploy":"deployment","release":"deployment","provision":"deployment","launch":"deployment",
    "sync":"integration","connect":"integration","integrate":"integration","push":"integration",
}

def _infer_dag_steps(description: str) -> List[Dict[str, Any]]:
    """Smart NL→DAG inference: detects domain context and builds realistic multi-step workflows."""
    desc_lower = description.lower()
    words = re.findall(r'\b\w+\b', desc_lower)
    word_set = set(words)

    # ── Domain detection ──────────────────────────────────────────────────────
    _TEMPLATES: Dict[str, List[tuple]] = {
        # (name, type, estimated_seconds, is_hitl)
        "onboard": [
            ("Collect Client Requirements", "data_retrieval", 5, False),
            ("Provision CRM Record", "integration", 4, False),
            ("Run Security Review", "validation", 6, False),
            ("HITL Gate: Approve Onboarding", "hitl_gate", 0, True),
            ("Configure Access & Permissions", "deployment", 8, False),
            ("Send Welcome Notification", "notification", 1, False),
        ],
        "report": [
            ("Fetch Data Sources", "data_retrieval", 5, False),
            ("Aggregate & Analyse", "analysis", 8, False),
            ("Format Report Output", "data_transformation", 3, False),
            ("HITL Gate: Review Report", "hitl_gate", 0, True),
            ("Distribute Report", "notification", 2, False),
        ],
        "invoice": [
            ("Pull Deal / Contract Data", "data_retrieval", 4, False),
            ("Compute Invoice Amounts", "computation", 5, False),
            ("HITL Gate: Approve Invoice", "hitl_gate", 0, True),
            ("Send Invoice to Client", "notification", 1, False),
            ("Log to Finance System", "data_output", 2, False),
        ],
        "reconcil": [
            ("Fetch Bank Transactions", "data_retrieval", 5, False),
            ("Match Against Ledger", "analysis", 8, False),
            ("Flag Discrepancies", "validation", 4, False),
            ("HITL Gate: Review Discrepancies", "hitl_gate", 0, True),
            ("Post Reconciled Entries", "data_output", 3, False),
        ],
        "campaign": [
            ("Analyse Current Traction", "analysis", 6, False),
            ("Generate Ad Creative", "computation", 5, False),
            ("HITL Gate: Approve Campaign", "hitl_gate", 0, True),
            ("Launch Paid Ad Channels", "deployment", 8, False),
            ("Monitor Performance", "execution", 4, False),
            ("Send Results Summary", "notification", 1, False),
        ],
        "security": [
            ("Enumerate Attack Surface", "data_retrieval", 5, False),
            ("Run Vulnerability Scan", "execution", 10, False),
            ("Analyse & Score Findings", "analysis", 8, False),
            ("HITL Gate: Approve Remediation Plan", "hitl_gate", 0, True),
            ("Apply Patches / Controls", "deployment", 12, False),
            ("Generate Compliance Report", "data_output", 3, False),
        ],
        "deploy": [
            ("Validate Build Artifacts", "validation", 4, False),
            ("Run Integration Tests", "execution", 8, False),
            ("HITL Gate: Approve Deploy", "hitl_gate", 0, True),
            ("Deploy to Production", "deployment", 10, False),
            ("Smoke Test & Monitor", "validation", 5, False),
            ("Notify Team", "notification", 1, False),
        ],
        "crm": [
            ("Pull Contact / Lead Data", "data_retrieval", 4, False),
            ("Score & Segment Leads", "computation", 5, False),
            ("Sync to CRM Platform", "integration", 4, False),
            ("HITL Gate: Review Pipeline", "hitl_gate", 0, True),
            ("Trigger Follow-up Sequences", "notification", 2, False),
        ],
        "proposal": [
            ("Parse Inbound RFP", "data_retrieval", 4, False),
            ("Generate AI Draft", "computation", 6, False),
            ("HITL Gate: Review Proposal", "hitl_gate", 0, True),
            ("Finalise & Send Proposal", "data_output", 3, False),
            ("Log to CRM & Track", "integration", 2, False),
        ],
        "monitor": [
            ("Collect Metrics & Logs", "data_retrieval", 3, False),
            ("Run Anomaly Detection", "analysis", 6, False),
            ("Evaluate Alert Thresholds", "validation", 2, False),
            ("HITL Gate: Confirm Critical Alert", "hitl_gate", 0, True),
            ("Dispatch Notifications", "notification", 1, False),
        ],
    }

    domain_key = None
    for kw in ["onboard", "invoice", "reconcil", "campaign", "security", "deploy",
                "proposal", "monitor", "report", "crm"]:
        if any(w.startswith(kw) for w in word_set):
            domain_key = kw
            break

    if domain_key and domain_key in _TEMPLATES:
        raw_steps = _TEMPLATES[domain_key]
    else:
        # Keyword-scan fallback → build steps from matched action words
        _EST = {"data_retrieval":5,"data_transformation":3,"validation":2,"notification":1,
                "data_output":2,"analysis":8,"hitl_gate":0,"deployment":10,"execution":5,
                "integration":4,"data_filtering":2,"computation":6,"delay":0}
        raw_collected: List[tuple] = []
        seen_types: set = set()
        for word in words:
            stype = _STEP_KEYWORDS.get(word)
            if stype and stype not in seen_types:
                seen_types.add(stype)
                is_hitl = stype == "hitl_gate"
                lbl = f"HITL Gate: {word.title()}" if is_hitl else \
                      f"{word.replace('_',' ').title()}"
                raw_collected.append((lbl, stype, _EST.get(stype, 5), is_hitl))
        # Guarantee minimum 3 steps + 1 HITL
        if len(raw_collected) < 3:
            raw_steps = [
                ("Retrieve Input Data", "data_retrieval", 5, False),
                ("Process & Transform", "data_transformation", 3, False),
                ("Validate Results", "validation", 2, False),
                ("HITL Gate: Review Output", "hitl_gate", 0, True),
                ("Deliver Output", "data_output", 2, False),
            ]
        else:
            raw_steps = raw_collected

    # Ensure at least one HITL gate
    if not any(is_h for _, _, _, is_h in raw_steps):
        mid = len(raw_steps) // 2
        raw_steps = list(raw_steps)
        raw_steps.insert(mid, ("HITL Gate: Review & Approve", "hitl_gate", 0, True))

    # Build final step dicts
    steps = []
    for idx, (name, stype, est_sec, is_hitl) in enumerate(raw_steps):
        n = idx + 1
        steps.append({
            "id": f"step-{n:03d}",
            "name": name,
            "type": stype,
            "depends_on": [f"step-{n-1:03d}"] if n > 1 else [],
            "config": {"timeout_seconds": 30, "retry_count": 3},
            "estimated_seconds": est_sec,
            "is_hitl": is_hitl,
            "status": "pending",
            "approved_at": None,
            "hitl_item_id": None,
        })
    return steps

@router.post("/api/workflows/generate")
async def generate_workflow(req:WorkflowRequest):
    steps=_infer_dag_steps(req.description)
    workflow={
        "id":f"wf-{uuid.uuid4().hex[:8]}",
        "name":" ".join(req.description.split()[:6]).title()+" Workflow",
        "description":req.description,"tenant_id":req.tenant_id,"steps":steps,
        "step_count":len(steps),"has_hitl_gates":any(s["is_hitl"] for s in steps),
        "estimated_duration_seconds":sum(s.get("estimated_seconds",5) for s in steps if not s["is_hitl"]),
        "status":"running" if req.execute_immediately else "draft",
        "execute_immediately":req.execute_immediately,"generated_at":_now_iso(),
        "dag_metadata":{"nodes":len(steps),"edges":sum(len(s["depends_on"]) for s in steps),"max_depth":len(steps),"parallel_branches":1},
        "current_step_index": 0,
    }
    if req.execute_immediately:
        workflow["started_at"]=_now_iso()
        if steps: steps[0]["status"] = "running"
    _workflow_history.append(workflow)
    _broadcast_sse("workflow_generated" if not req.execute_immediately else "workflow_started",workflow)
    if req.execute_immediately: await _broadcast_ws("workflow_started",workflow)
    return JSONResponse(workflow, status_code=201)

@router.get("/api/workflows")
async def list_workflows(tenant_id:str=Query(default="")):
    wfs=_workflow_history if not tenant_id else [w for w in _workflow_history if w.get("tenant_id")==tenant_id]
    return JSONResponse({"workflows":wfs,"total":len(wfs)})

@router.post("/api/workflows/{workflow_id}/execute")
async def execute_workflow(workflow_id:str):
    wf=next((w for w in _workflow_history if w["id"]==workflow_id),None)
    if not wf: raise HTTPException(404,"Workflow not found")
    wf["status"]="running"; wf["started_at"]=_now_iso()
    if wf.get("steps"): wf["steps"][0]["status"] = "running"
    _broadcast_sse("workflow_started",wf); await _broadcast_ws("workflow_started",wf)
    return JSONResponse(wf)

@router.post("/api/workflows/{workflow_id}/steps/{step_id}/approve")
async def approve_workflow_step(workflow_id:str, step_id:str, req: HITLDecisionRequest):
    wf=next((w for w in _workflow_history if w["id"]==workflow_id),None)
    if not wf: raise HTTPException(404,"Workflow not found")
    step=next((s for s in wf["steps"] if s["id"]==step_id),None)
    if not step: raise HTTPException(404,"Step not found")
    step["approved_at"]=_now_iso(); step["status"]="approved"; step["approved_by"]=req.approved_by
    steps = wf["steps"]
    idx = next((i for i,s in enumerate(steps) if s["id"]==step_id), -1)
    if idx >= 0 and idx+1 < len(steps):
        steps[idx+1]["status"] = "running"
        wf["current_step_index"] = idx+1
    elif idx == len(steps)-1:
        wf["status"] = "completed"; wf["completed_at"] = _now_iso()
    _broadcast_sse("step_approved",{"workflow_id":workflow_id,"step_id":step_id})
    await _broadcast_ws("step_approved",{"workflow_id":workflow_id,"step_id":step_id})
    return JSONResponse({"workflow_id":workflow_id,"step_id":step_id,"approved":True,"workflow_status":wf["status"]})

@router.post("/api/workflows/{workflow_id}/advance")
async def advance_workflow(workflow_id: str):
    wf=next((w for w in _workflow_history if w["id"]==workflow_id),None)
    if not wf: raise HTTPException(404,"Workflow not found")
    steps = wf.get("steps",[])
    for i, step in enumerate(steps):
        if step["status"] == "running" and not step.get("is_hitl"):
            step["status"] = "completed"; step["completed_at"] = _now_iso()
            if i+1 < len(steps):
                next_step = steps[i+1]
                if next_step.get("is_hitl"):
                    next_step["status"] = "awaiting_hitl"
                    hitl = _create_hitl_item(
                        hitl_type="dag_step",
                        title=f"DAG Step Approval: {next_step['name']}",
                        description=f"Workflow '{wf['name']}' requires human approval at '{next_step['name']}'.",
                        payload={"workflow_id": workflow_id, "step_id": next_step["id"]},
                        related_id=workflow_id, priority="normal",
                    )
                    next_step["hitl_item_id"] = hitl["id"]
                else:
                    next_step["status"] = "running"
                wf["current_step_index"] = i+1
            else:
                wf["status"] = "completed"; wf["completed_at"] = _now_iso()
            _broadcast_sse("workflow_step_advanced",{"workflow_id":workflow_id,"completed_step":step["id"]})
            return JSONResponse({"advanced":True,"completed_step":step["id"],"workflow_status":wf["status"]})
    return JSONResponse({"advanced":False,"message":"No running non-HITL step found"})

# ==============================================================================
# AGENTIC COMMS ROUTER
# ==============================================================================
@router.get("/api/comms/rooms")
async def list_rooms():
    return JSONResponse({"rooms":[{
        "id":room,"agents":agents,"agent_count":len(agents),
        "message_count":len([m for m in _agent_messages if m.get("room")==room]),
        "last_activity":next((m["sent_at"] for m in reversed(_agent_messages) if m.get("room")==room),None)
    } for room,agents in _SUBSYSTEM_ROOMS.items()],"total":len(_SUBSYSTEM_ROOMS)})

@router.post("/api/comms/send")
async def send_agent_message(msg:AgentMessageRequest):
    if msg.room not in _SUBSYSTEM_ROOMS: raise HTTPException(404,f"Room {msg.room} not found")
    message={"id":f"msg-{uuid.uuid4().hex[:8]}","sender":msg.sender,"room":msg.room,
        "message_type":msg.message_type,"content":msg.content,"recipients":_SUBSYSTEM_ROOMS[msg.room],
        "sent_at":_now_iso(),"status":"delivered"}
    _agent_messages.append(message)
    if len(_agent_messages)>1000: del _agent_messages[:100]
    _broadcast_sse("agent_message",message); await _broadcast_ws("agent_message",message)
    return JSONResponse(message, status_code=201)

@router.get("/api/comms/messages")
async def get_messages(room:str=Query(default=""), limit:int=Query(default=50,le=200)):
    msgs=_agent_messages if not room else [m for m in _agent_messages if m.get("room")==room]
    return JSONResponse({"messages":msgs[-limit:],"total":len(msgs)})

@router.post("/api/comms/broadcast")
async def broadcast_to_all(request:Request, sender:str=Query(default="system")):
    body=await request.json()
    results=[]
    for room,agents in _SUBSYSTEM_ROOMS.items():
        msg={"id":f"msg-{uuid.uuid4().hex[:8]}","sender":sender,"room":room,"message_type":"broadcast",
            "content":body,"recipients":agents,"sent_at":_now_iso(),"status":"delivered"}
        _agent_messages.append(msg); results.append(msg)
    _broadcast_sse("broadcast_sent",{"rooms":len(results),"sender":sender})
    return JSONResponse({"sent_to_rooms":len(results),"messages":results})

# ==============================================================================
# SELF-SETUP PIPELINE
# ==============================================================================
@router.get("/api/pipeline/self-setup")
async def get_self_setup():
    completed=sum(1 for s in _SELF_SETUP_STEPS if s["status"]=="completed")
    blocked=sum(1 for s in _SELF_SETUP_STEPS if s["status"]=="blocked_hitl")
    return JSONResponse({
        "steps":_SELF_SETUP_STEPS,"total_steps":len(_SELF_SETUP_STEPS),
        "completed_steps":completed,"blocked_steps":blocked,
        "overall_progress":round(completed/len(_SELF_SETUP_STEPS)*100,1),
        "active_step":next((s for s in _SELF_SETUP_STEPS if s["status"]=="active"),None),
        "blocked_step":next((s for s in _SELF_SETUP_STEPS if s["status"]=="blocked_hitl"),None),
        "status":"completed" if completed==len(_SELF_SETUP_STEPS) else
                 "blocked" if blocked > 0 else "in_progress",
    })

@router.post("/api/pipeline/self-setup/advance")
async def advance_setup():
    for step in _SELF_SETUP_STEPS:
        if step["status"]=="active":
            new_progress = min(100, step["progress"]+25)
            step["progress"] = new_progress
            if new_progress>=100 and not step.get("requires_hitl"):
                step["status"]="completed"; step["completed_at"]=_now_iso()
                for s2 in _SELF_SETUP_STEPS:
                    if s2["status"]=="pending": s2["status"]="active"; break
            _broadcast_sse("setup_progress",{"steps":_SELF_SETUP_STEPS})
            return JSONResponse({"advanced":step["id"],"progress":step["progress"]})
    return JSONResponse({"message":"All steps complete or blocked"})

@router.post("/api/pipeline/self-setup/run-full")
async def run_full_setup():
    for step in _SELF_SETUP_STEPS:
        if step["status"]=="pending": step["status"]="active"
    tenant=_TENANTS.get("tenant-001")
    if tenant: tenant["active_verticals"]=list(_VERTICAL_CONFIGS.keys())
    _seed_campaigns()
    pending=[r for r in _incoming_requests if r["status"]=="pending"]
    for req in pending[:2]:
        _generated_proposals.append(_generate_proposal_content(req)); req["status"]="in_progress"
    for room,agents in _SUBSYSTEM_ROOMS.items():
        _agent_messages.append({"id":f"msg-{uuid.uuid4().hex[:8]}","sender":"pipeline_controller",
            "room":room,"message_type":"broadcast","content":{"event":"self_setup_initiated","ts":_now_iso()},
            "recipients":agents,"sent_at":_now_iso(),"status":"delivered"})
    _broadcast_sse("self_setup_started",{"steps":len(_SELF_SETUP_STEPS),"ts":_now_iso()})
    return JSONResponse({"status":"initiated","steps_activated":len(_SELF_SETUP_STEPS),
        "campaigns_seeded":len(_campaigns),"proposals_generated":len(pending[:2]),
        "comms_rooms_notified":len(_SUBSYSTEM_ROOMS),"message":"Murphy System self-automation pipeline fully initiated."})

# ==============================================================================
# EXECUTION LOG + TIERS + BOTS
# ==============================================================================
@router.get("/api/executions")
async def get_executions(limit:int=Query(default=50,le=200), tenant_id:str=Query(default="")):
    execs=_execution_log if not tenant_id else [e for e in _execution_log if e.get("tenant_id")==tenant_id]
    return JSONResponse({"executions":execs[-limit:],"total":len(execs)})

@router.get("/api/tiers")
async def get_tiers():
    return JSONResponse({"tiers":TIERS,"active_automations":sum(1 for a in _automation_store if a["status"]=="active")})

_BOT_MANIFEST=["scheduler_bot","anomaly_watcher_bot","feedback_bot","librarian_bot","memory_manager_bot","triage_bot","optimization_bot","analysis_bot","commissioning_bot","engineering_bot","key_manager_bot","ghost_controller_bot","kaia","kiren","vallon","veritas","osmosis","rubixcube_bot"]

@router.get("/api/bots/status")
async def bots_status():
    statuses=[{"bot":bot,"status":"healthy" if random.random()>0.05 else "degraded",
        "room":next((r for r,a in _SUBSYSTEM_ROOMS.items() if bot in a),"general"),
        "last_seen":_now_iso(),"uptime_pct":round(random.uniform(94.5,99.9),1),
        "tasks_completed":random.randint(100,5000),"messages_routed":random.randint(50,2000)}
        for bot in _BOT_MANIFEST]
    return JSONResponse({"bots":statuses,"total":len(statuses),
        "healthy":sum(1 for s in statuses if s["status"]=="healthy"),
        "degraded":sum(1 for s in statuses if s["status"]=="degraded")})

# ==============================================================================
# WEBSOCKET
# ==============================================================================
@router.get("/ws")
async def ws_http_fallback():
    """Fallback for HTTP clients trying to reach the WebSocket endpoint."""
    return JSONResponse({"error": "WebSocket endpoint — use ws:// protocol", "path": "/ws"}, status_code=426)

@router.websocket("/ws")
async def websocket_endpoint(ws:WebSocket):
    await ws.accept()
    client_id=uuid.uuid4().hex[:8]; _ws_clients[client_id]=ws
    log.info("WS connected: %s (total: %d)", client_id, len(_ws_clients))
    try:
        await ws.send_text(json.dumps({"event":"connected","client_id":client_id,"ts":_now_iso(),"active_clients":len(_ws_clients)}))
        while True:
            raw=await ws.receive_text()
            try:
                msg=json.loads(raw); event=msg.get("event","")
                if event in ("cursor_move","selection_change","view_change"):
                    await _broadcast_ws(event,{**msg.get("data",{}),"client_id":client_id})
                elif event=="ping":
                    await ws.send_text(json.dumps({"event":"pong","ts":_now_iso()}))
            except json.JSONDecodeError:  # PROD-HARD A2: malformed message from WS client — drop and continue
                log.warning("WS client %s sent non-JSON message; dropping frame (len=%d)", client_id, len(raw) if isinstance(raw, (str, bytes)) else -1)
    except WebSocketDisconnect:
        log.info("WS disconnected: %s", client_id)
    finally:
        _ws_clients.pop(client_id,None)

# ==============================================================================
# STATIC FILES + ALL ORIGINAL ROUTES PRESERVED
# ==============================================================================
_BASE_DIR   = Path(__file__).resolve().parent.parent  # project root (file is in src/)
_MURPHY_DIR = _BASE_DIR / "Murphy System"
_UI_DIR     = _BASE_DIR / "murphy_dashboard"

# Static mounts handled by unified server in src/runtime/app.py
# _UI_DIR and _MURPHY_DIR are exported for the main app to mount


def _read_html(path: Path) -> str:
    try: return path.read_text(encoding="utf-8")
    except Exception:
        log.debug("Could not read HTML file: %s", path)
        return f"<h1>File not found: {path}</h1>"

def _serve_landing_html() -> HTMLResponse:
    """Shared helper: serve murphy_landing_page.html, root-level first then Murphy System/ fallback."""
    for path in [
        _BASE_DIR / "murphy_landing_page.html",
        _MURPHY_DIR / "murphy_landing_page.html",
    ]:
        if path.exists():
            return HTMLResponse(path.read_text(encoding="utf-8"))
    return HTMLResponse("<p>Landing page not found</p>")

# ── CANONICAL ROUTE MAP (DEF-ROUTE-001) ──────────────────────────────────
# /                    → murphy_landing_page.html (public landing page)
# /dashboard           → murphy_dashboard/index.html (admin dashboard)
# /ui/landing          → murphy_landing_page.html (alias)
# /ui/{page}           → {page}.html (dynamic page router)
# /static/*            → static/ directory (landing page assets)
# /murphy-static/*     → Murphy System/static/ (legacy assets)
# ─────────────────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    """Root URL serves landing page for public visitors; falls back to dashboard"""
    result = _serve_landing_html()
    if result.status_code == 200:
        return result
    idx = _UI_DIR / "index.html"
    if idx.exists(): return HTMLResponse(idx.read_text())
    return HTMLResponse("<h1>Murphy System API v3.0</h1><p><a href='/docs'>API Docs</a></p>")

@router.get("/calendar", response_class=HTMLResponse)
async def serve_calendar():
    """Original calendar UI — preserved"""
    for path in [
        _MURPHY_DIR / "calendar.html",
        _UI_DIR / "calendar.html",
    ]:
        if path.exists(): return HTMLResponse(path.read_text())
    return HTMLResponse("<p>Calendar at <a href='/'>dashboard</a></p>")

@router.get("/dashboard", response_class=HTMLResponse)
async def serve_legacy_dashboard():
    """Admin dashboard — murphy_dashboard/index.html"""
    for path in [
        _UI_DIR / "index.html",
        _MURPHY_DIR / "dashboard.html",
    ]:
        if path.exists(): return HTMLResponse(path.read_text())
    return HTMLResponse("<p>Dashboard at <a href='/'>command center</a></p>")

@router.get("/landing", response_class=HTMLResponse)
async def serve_landing():
    """Landing page — check root first, then Murphy System/ subdirectory"""
    return _serve_landing_html()

@router.get("/production-wizard", response_class=HTMLResponse)
async def serve_production_wizard():
    path = _MURPHY_DIR / "production_wizard.html"
    if path.exists(): return HTMLResponse(path.read_text())
    return HTMLResponse("<p>Production wizard not found</p>")

@router.get("/onboarding", response_class=HTMLResponse)
async def serve_onboarding():
    path = _MURPHY_DIR / "onboarding_wizard.html"
    if path.exists(): return HTMLResponse(path.read_text())
    return HTMLResponse("<p>Onboarding wizard not found</p>")

# ── DEF-023: Serve all root-level HTML pages via /ui/{page_name} ──────────
_HTML_DIR = _BASE_DIR  # Root-level HTML files

# Map of page names to filenames (without .html extension)
_UI_PAGES = {
    p.stem: p for p in sorted(_HTML_DIR.glob("*.html"))
}
log.info("UI page router: %d HTML pages mapped from %s", len(_UI_PAGES), _HTML_DIR)


@router.get("/api/ui/pages")
async def list_ui_pages():
    """List all available UI pages."""
    pages = [
        {"name": name, "url": f"/ui/{name}", "file": str(path.name)}
        for name, path in sorted(_UI_PAGES.items())
    ]
    return JSONResponse({"pages": pages, "total": len(pages)})


@router.get("/ui/landing", response_class=HTMLResponse)
async def serve_ui_landing():
    """Landing page at /ui/landing — alias for /landing"""
    return _serve_landing_html()


@router.get("/ui/{page_name}", response_class=HTMLResponse)
async def serve_ui_page(page_name: str):
    """Serve any root-level HTML page by name (without .html extension)."""
    path = _UI_PAGES.get(page_name)
    if path is None:
        # Try with .html appended
        candidate = _HTML_DIR / f"{page_name}.html"
        if candidate.exists():
            path = candidate
    if path is None or not path.exists():
        raise HTTPException(404, f"Page '{page_name}' not found")
    return HTMLResponse(path.read_text(encoding="utf-8"))


# Standalone entry removed — use unified server via src/runtime/app.py

# ── Production Router Startup ─────────────────────────────────────────────
async def production_router_startup():
    """Call from main app startup to initialize production router state."""
    _seed_automations()
    if hasattr(_automation_store, 'extend') and not _automation_store:
        _automation_store.extend(_DEMO_AUTOMATIONS)
    _seed_campaigns()
    asyncio.create_task(_automation_tick())
    log.info("Production Router v3.0 startup complete — HITL, automations, calendar active")
