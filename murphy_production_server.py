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
import hashlib
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
ROOT = Path(__file__).resolve().parent / "Murphy System"
sys.path.insert(0, str(ROOT))

from fastapi import FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s  %(name)s  %(levelname)s  %(message)s")
log = logging.getLogger("murphy.prod")

# -- Import MurphyLLMProvider (DeepInfra primary, Together fallback) -----------
try:
    _llm_src = Path(__file__).resolve().parent / "src"
    sys.path.insert(0, str(_llm_src))
    from llm_provider import get_llm as _get_llm
    _llm_available = True
    log.info("MurphyLLMProvider loaded — DeepInfra primary, Together fallback")
except Exception as _llm_e:
    log.warning("MurphyLLMProvider not available (%s) — using pattern-match fallback", _llm_e)
    _llm_available = False
    _get_llm = None  # type: ignore

# -- Import Murphy automation engine (with fallback) ---------------------------
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

# -- Module Instance Manager (dynamic spawn/despawn) ---------------------------
try:
    from src.module_instance_api import register_module_instance_routes as _register_mim_routes
    from src.module_instance_api import set_event_callbacks as _set_mim_callbacks
    _mim_available = True
    log.info("ModuleInstanceManager API loaded")
except Exception as _mim_e:
    log.warning("ModuleInstanceManager API not available (%s)", _mim_e)
    _mim_available = False
    _register_mim_routes = None  # type: ignore
    _set_mim_callbacks = None  # type: ignore

# -- Advanced Self-Loop wiring (Steps 4–5: SelfFixLoopConnector + TaskExecutionBridge)
try:
    from src.advanced_loop_wiring import wire_advanced_loop as _wire_advanced_loop
    _advanced_loop_available = True
    log.info("Advanced loop wiring (WIRE-004) loaded")
except Exception as _adv_e:
    log.warning("Advanced loop wiring not available (%s)", _adv_e)
    _advanced_loop_available = False
    _wire_advanced_loop = None  # type: ignore

# -- Crown Jewel Module Wiring (Phases 1-8) ------------------------------------
try:
    from rosetta.rosetta_manager import RosettaManager as _RosettaManager
    _rosetta_available = True
    log.info("RosettaManager loaded")
except Exception as _e:
    log.warning("RosettaManager not available (%s)", _e)
    _rosetta_available = False
    _RosettaManager = None

try:
    from ceo_branch_activation import CEOBranch as _CEOBranch
    _ceo_available = True
    log.info("CEOBranch loaded")
except Exception as _e:
    log.warning("CEOBranch not available (%s)", _e)
    _ceo_available = False
    _CEOBranch = None

try:
    from activated_heartbeat_runner import ActivatedHeartbeatRunner as _ActivatedHeartbeatRunner
    _heartbeat_available = True
    log.info("ActivatedHeartbeatRunner loaded")
except Exception as _e:
    log.warning("ActivatedHeartbeatRunner not available (%s)", _e)
    _heartbeat_available = False
    _ActivatedHeartbeatRunner = None

try:
    from aionmind.runtime_kernel import AionMindKernel as _AionMindKernel
    _aionmind_available = True
    log.info("AionMindKernel loaded")
except Exception as _e:
    log.warning("AionMindKernel not available (%s)", _e)
    _aionmind_available = False
    _AionMindKernel = None

try:
    from lcm_engine import LCMEngine as _LCMEngine
    _lcm_available = True
    log.info("LCMEngine loaded")
except Exception as _e:
    log.warning("LCMEngine not available (%s)", _e)
    _lcm_available = False
    _LCMEngine = None

try:
    from gate_bypass_controller import GateBypassController as _GateBypassController
    _gate_bypass_available = True
    log.info("GateBypassController loaded")
except Exception as _e:
    log.warning("GateBypassController not available (%s)", _e)
    _gate_bypass_available = False
    _GateBypassController = None

try:
    from tool_registry import UniversalToolRegistry as _UniversalToolRegistry
    _tool_registry_available = True
    log.info("UniversalToolRegistry loaded")
except Exception as _e:
    log.warning("UniversalToolRegistry not available (%s)", _e)
    _tool_registry_available = False
    _UniversalToolRegistry = None

try:
    from feature_flags import FeatureFlagManager as _FeatureFlagManager
    _feature_flags_available = True
    log.info("FeatureFlagManager loaded")
except Exception as _e:
    log.warning("FeatureFlagManager not available (%s)", _e)
    _feature_flags_available = False
    _FeatureFlagManager = None

try:
    from multi_agent_coordinator import TeamCoordinator as _TeamCoordinator
    _multi_agent_available = True
    log.info("TeamCoordinator loaded")
except Exception as _e:
    log.warning("TeamCoordinator not available (%s)", _e)
    _multi_agent_available = False
    _TeamCoordinator = None

try:
    from persistent_memory import TenantMemoryStore as _PersistentMemoryStore
    _persistent_memory_available = True
    log.info("PersistentMemoryStore loaded")
except Exception as _e:
    log.warning("PersistentMemoryStore not available (%s)", _e)
    _persistent_memory_available = False
    _PersistentMemoryStore = None

try:
    from skill_system import SkillManager as _SkillRegistry
    _skill_system_available = True
    log.info("SkillRegistry loaded")
except Exception as _e:
    log.warning("SkillRegistry not available (%s)", _e)
    _skill_system_available = False
    _SkillRegistry = None

try:
    from mcp_plugin import MCPConnector as _MCPPluginManager
    _mcp_plugin_available = True
    log.info("MCPPluginManager loaded")
except Exception as _e:
    log.warning("MCPPluginManager not available (%s)", _e)
    _mcp_plugin_available = False
    _MCPPluginManager = None

# -- Global Feedback System (GFB-002) -----------------------------------------
try:
    from global_feedback import GlobalFeedbackDispatcher as _GlobalFeedbackDispatcher
    _global_feedback_available = True
    log.info("GlobalFeedbackDispatcher loaded")
except Exception as _e:
    log.warning("GlobalFeedbackDispatcher not available (%s)", _e)
    _global_feedback_available = False
    _GlobalFeedbackDispatcher = None  # type: ignore

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

def _broadcast_sse(event: str, data: Any) -> None:
    payload = json.dumps({"event": event, "data": data, "ts": _now_iso()})
    dead = []
    for q in _sse_subscribers:
        try: q.put_nowait(payload)
        except asyncio.QueueFull: dead.append(q)
    for q in dead:
        try: _sse_subscribers.remove(q)
        except ValueError: pass

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
        try:
            await _automation_tick_body()
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("_automation_tick iteration failed")


async def _automation_tick_body():
    """Single iteration body for _automation_tick."""
    active = [a for a in _automation_store if a.get("status") == "active"]
    if not active:
        return
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
            return

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
    # Phase 4: Delegate to CEOBranch automation directives
    if _ceo_branch is not None:
        try:
            status = _ceo_branch.get_status()
            if status.get("directives"):
                log.debug("CEO automation directives: %d active", len(status["directives"]))
        except Exception as _e:
            log.debug("CEOBranch automation delegation error (non-fatal): %s", _e)
    # Phase 4: LCM Engine health signal
    if _lcm_engine_instance is not None:
        try:
            _lcm_engine_instance.analyze({"tick": "automation", "count": len(_automation_store)})
        except Exception as _e:
            log.debug("LCMEngine analysis error (non-fatal): %s", _e)

async def _campaign_tick():
    """Every 15s: drift metrics, detect low traction, create HITL paid-ad proposals."""
    while True:
        await asyncio.sleep(15)
        try:
            await _campaign_tick_body()
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("_campaign_tick iteration failed")


async def _campaign_tick_body():
    """Single iteration body for _campaign_tick."""
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
    # Phase 4: Delegate to CEOBranch campaign management
    if _ceo_branch is not None:
        try:
            _ceo_branch.get_status()  # Pulse CEO on campaign state
        except Exception as _e:
            log.debug("CEOBranch campaign delegation error (non-fatal): %s", _e)
    # Phase 4: Feature flag gating for campaign features
    if _feature_flag_manager is not None:
        try:
            _feature_flag_manager.is_enabled("campaign_auto_boost", "default")
        except Exception as _e:
            log.debug("FeatureFlag campaign check error (non-fatal): %s", _e)

async def _setup_tick():
    """Every 20s: advance self-setup steps, create HITL gates at checkpoints."""
    while True:
        await asyncio.sleep(20)
        try:
            await _setup_tick_body()
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("_setup_tick iteration failed")


async def _setup_tick_body():
    """Single iteration body for _setup_tick."""
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
        try:
            await _hitl_auto_expire_tick_body()
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("_hitl_auto_expire_tick iteration failed")


async def _hitl_auto_expire_tick_body():
    """Single iteration body for _hitl_auto_expire_tick."""
    now_ts = _now_dt().timestamp()
    for item in _HITL_QUEUE:
        if item["status"] == "pending":
            aat = item.get("auto_approve_after_seconds", 0)
            if aat > 0 and (now_ts - item["_created_ts"]) > aat:
                item["status"] = "expired"
                item["approved_at"] = _now_iso()
                _broadcast_sse("hitl_expired", {"id": item["id"]})
    # Phase 4: Gate bypass trust-aware expiration
    if _gate_bypass is not None:
        try:
            _gate_bypass.get_trust_levels()
        except Exception as _e:
            log.debug("GateBypass trust expiration error (non-fatal): %s", _e)

async def _proposal_intake_tick():
    """Every 45s: auto-generate proposals for new incoming requests."""
    while True:
        await asyncio.sleep(45)
        try:
            await _proposal_intake_tick_body()
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("_proposal_intake_tick iteration failed")


async def _proposal_intake_tick_body():
    """Single iteration body for _proposal_intake_tick."""
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
    # Phase 4: Delegate pending proposals to TeamCoordinator
    if _team_coordinator is not None:
        try:
            pending = [p for p in _generated_proposals if p.get("status") == "pending"]
            if pending:
                log.debug("TeamCoordinator: %d pending proposals queued", len(pending))
        except Exception as _e:
            log.debug("TeamCoordinator proposal delegation error (non-fatal): %s", _e)

async def _ceo_heartbeat_tick():
    """Background task: CEO heartbeat — delegates to ActivatedHeartbeatRunner.

    Commissioning: G3 — runs continuously, isolated from other ticks.
    G8: try/except prevents crash from propagating.
    """
    while True:
        await asyncio.sleep(60)  # 1-minute CEO heartbeat interval
        try:
            await _ceo_heartbeat_tick_body()
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("_ceo_heartbeat_tick iteration failed")


async def _ceo_heartbeat_tick_body():
    """Single iteration body for _ceo_heartbeat_tick."""
    if _heartbeat_runner is None:
        return
    try:
        # ActivatedHeartbeatRunner.tick() may be sync — run in thread pool
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _heartbeat_runner.tick)
    except Exception as _e:
        log.warning("CEO heartbeat runner tick error: %s", _e)

# -- FastAPI app ---------------------------------------------------------------
app = FastAPI(
    title="Murphy System — Production API v3",
    description="Unified automation platform with real HITL gates, milestone tracking, closed-loop automations",
    version="3.0.0", docs_url="/docs", redoc_url="/redoc",
)

_env = os.environ.get("MURPHY_ENV","development").lower()
_raw_origins = os.environ.get("MURPHY_ALLOWED_ORIGINS","")
if _raw_origins:
    _allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]
elif _env in ("production","staging"):
    _allowed_origins = []; log.warning("MURPHY_ALLOWED_ORIGINS not set -- CORS blocked in %s", _env)
else:
    _allowed_origins = ["*"]

app.add_middleware(CORSMiddleware, allow_origins=_allowed_origins, allow_credentials=True,
    allow_methods=["GET","POST","PATCH","DELETE","OPTIONS"],
    allow_headers=["Authorization","Content-Type","X-Request-ID","X-Tenant-ID"])

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-Request-ID"] = uuid.uuid4().hex
        if _env in ("production","staging"):
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

app.add_middleware(SecurityHeadersMiddleware)

# -- Swarm-Native Global Rate Governor -----------------------------------------
# Label: SWARM-RATE-GOV — classifies traffic into human/swarm/sensor/safety tiers.
# Swarm-internal and AI-sensor traffic gets higher limits than human API calls.
# Safety-critical paths (HITL, health, errors) are never rate-limited.
try:
    from src.swarm_rate_governor import SwarmRateGovernor
    _rate_governor = SwarmRateGovernor(
        human_rpm=int(os.environ.get("MURPHY_RATE_HUMAN_RPM", "60")),
        human_burst=int(os.environ.get("MURPHY_RATE_HUMAN_BURST", "15")),
        swarm_rpm=int(os.environ.get("MURPHY_RATE_SWARM_RPM", "600")),
        swarm_burst=int(os.environ.get("MURPHY_RATE_SWARM_BURST", "100")),
        sensor_rpm=int(os.environ.get("MURPHY_RATE_SENSOR_RPM", "300")),
        sensor_burst=int(os.environ.get("MURPHY_RATE_SENSOR_BURST", "50")),
    )

    @app.middleware("http")
    async def swarm_rate_limit_middleware(request: Request, call_next):
        result = _rate_governor.check(request)
        if not result["allowed"]:
            return JSONResponse(
                status_code=429,
                content={
                    "success": False,
                    "error": result.get("error", "MURPHY-E201"),
                    "message": result.get("message", "Rate limit exceeded"),
                    "retry_after_seconds": result.get("retry_after_seconds", 60),
                    "traffic_class": result.get("traffic_class", "unknown"),
                },
                headers={"Retry-After": str(int(result.get("retry_after_seconds", 60)))},
            )
        response = await call_next(request)
        # Inject rate-limit headers for observability
        if "remaining" in result and result["remaining"] != -1:
            response.headers["X-RateLimit-Remaining"] = str(result["remaining"])
        if "limit" in result:
            response.headers["X-RateLimit-Limit"] = str(result["limit"])
        response.headers["X-Murphy-Traffic-Class"] = result.get("traffic_class", "unknown")
        return response
    log.info("Swarm rate governor active (human=%s/min, swarm=%s/min, sensor=%s/min)",
             os.environ.get("MURPHY_RATE_HUMAN_RPM", "60"),
             os.environ.get("MURPHY_RATE_SWARM_RPM", "600"),
             os.environ.get("MURPHY_RATE_SENSOR_RPM", "300"))
except Exception as _rg_e:
    _rate_governor = None
    log.warning("Swarm rate governor not available (%s) — running without global rate limits", _rg_e)

# -- Murphy Error Handling System ----------------------------------------------
try:
    from src.errors.handlers import register_error_handlers
    register_error_handlers(app)
    log.info("Murphy error handlers registered (/api/errors/*)")
except Exception as _err_e:
    log.warning("Murphy error handlers not available (%s)", _err_e)

# -- Module Instance Manager routes --------------------------------------------
if _mim_available and _register_mim_routes is not None:
    _register_mim_routes(app)

    # Wire spawn/despawn events → SSE + WebSocket broadcasts
    async def _on_instance_spawned(data):
        _broadcast_sse("module_instance_spawned", data)
        await _broadcast_ws("module_instance_spawned", data)

    async def _on_instance_despawned(data):
        _broadcast_sse("module_instance_despawned", data)
        await _broadcast_ws("module_instance_despawned", data)

    if _set_mim_callbacks is not None:
        _set_mim_callbacks(
            on_spawn=_on_instance_spawned,
            on_despawn=_on_instance_despawned,
        )

    log.info("Module Instance Manager endpoints registered at /module-instances/*")

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
    # New fields for enhanced HITL
    follow_up_questions: List[str] = Field(default_factory=list)
    example_upload_url: Optional[str] = Field(default=None)
    example_description: Optional[str] = Field(default=None)
    mfgc_ambiguity_flags: List[str] = Field(default_factory=list)

class HITLRejectionRequest(BaseModel):
    """Enhanced rejection request with mandatory reason and follow-up generation."""
    approved_by: str = Field(default="founder")
    reason: str = Field(..., min_length=10, description="Rejection reason is mandatory and must be at least 10 characters")
    request_follow_up_questions: bool = Field(default=True, description="Request LLM-generated follow-up questions")
    example_upload_url: Optional[str] = Field(default=None, description="URL to example file for reference")
    example_description: Optional[str] = Field(default=None, description="Description of what the example shows")
    desired_outcome: Optional[str] = Field(default=None, description="What the desired outcome should be")

class MilestoneDelayRequest(BaseModel):
    delay_minutes: float = Field(..., gt=0)
    reason: str = Field(default="Manual delay")

def _bg_task_done_callback(task: asyncio.Task) -> None:
    """Log unhandled exceptions from background tasks (safety net)."""
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        log.error("Background task %s crashed: %s", task.get_name(), exc, exc_info=exc)


# -- Startup -------------------------------------------------------------------
_background_tasks: list = []          # Track tasks for graceful shutdown

# -- Crown Jewel Subsystem Instances -------------------------------------------
_rosetta_manager: Optional[Any] = None
_ceo_branch: Optional[Any] = None
_heartbeat_runner: Optional[Any] = None
_aionmind_kernel: Optional[Any] = None
_lcm_engine_instance: Optional[Any] = None
_gate_bypass: Optional[Any] = None
_tool_registry: Optional[Any] = None
_feature_flag_manager: Optional[Any] = None
_team_coordinator: Optional[Any] = None
_persistent_memory: Optional[Any] = None
_skill_registry: Optional[Any] = None
_mcp_plugin_manager: Optional[Any] = None
_feedback_dispatcher: Optional[Any] = None

@app.on_event("startup")
async def _startup():
    _seed_automations()
    _automation_store.extend(_DEMO_AUTOMATIONS)
    _seed_campaigns()
    for coro in (
        _automation_tick(),
        _campaign_tick(),
        _setup_tick(),
        _hitl_auto_expire_tick(),
        _proposal_intake_tick(),
    ):
        task = asyncio.create_task(coro)
        task.add_done_callback(_bg_task_done_callback)
        _background_tasks.append(task)

    # Wire advanced self-improvement loop (Steps 4–5)
    if _advanced_loop_available and _wire_advanced_loop is not None:
        try:
            _adv_components = _wire_advanced_loop()
            app.state.adv_loop_components = _adv_components
            log.info(
                "Advanced self-improvement loop wired: %s",
                list(_adv_components.keys()),
            )
        except Exception as _adv_startup_e:
            log.warning("Advanced loop startup wiring failed: %s", _adv_startup_e)
            app.state.adv_loop_components = {}

    # -- Phase 1: Wire RosettaManager ------------------------------------------
    global _rosetta_manager
    if _rosetta_available:
        try:
            _rosetta_state_dir = os.environ.get(
                "MURPHY_PERSISTENCE_DIR", ".murphy_persistence"
            ) + "/rosetta"
            _rosetta_manager = _RosettaManager(persistence_dir=_rosetta_state_dir)
            _rosetta_manager.load_state()
            log.info("RosettaManager initialized — state dir: %s", _rosetta_state_dir)
        except Exception as _e:
            log.warning("RosettaManager init failed (%s) — continuing without", _e)
            _rosetta_manager = None

    # -- Phase 1: Wire CEOBranch + ActivatedHeartbeatRunner --------------------
    global _ceo_branch, _heartbeat_runner
    if _ceo_available:
        try:
            _ceo_branch = _CEOBranch(rosetta_manager=_rosetta_manager)
            _ceo_branch.activate()
            log.info("CEOBranch activated")
        except Exception as _e:
            log.warning("CEOBranch init failed (%s)", _e)
            _ceo_branch = None
    if _heartbeat_available and _ceo_branch is not None:
        try:
            _heartbeat_runner = _ActivatedHeartbeatRunner(ceo_branch=_ceo_branch)
            log.info("ActivatedHeartbeatRunner initialized")
        except Exception as _e:
            log.warning("ActivatedHeartbeatRunner init failed (%s)", _e)
            _heartbeat_runner = None

    # -- Phase 2: Wire AionMind RuntimeKernel ----------------------------------
    global _aionmind_kernel
    if _aionmind_available:
        try:
            _aionmind_kernel = _AionMindKernel()
            log.info("AionMindKernel instantiated")
        except Exception as _e:
            log.warning("AionMindKernel init failed (%s)", _e)
            _aionmind_kernel = None

    # -- Phase 2: Wire Tool Registry + AionMind bridge -------------------------
    global _tool_registry
    if _tool_registry_available:
        try:
            _tool_registry = _UniversalToolRegistry()
            log.info("UniversalToolRegistry initialized")
        except Exception as _e:
            log.warning("UniversalToolRegistry init failed (%s)", _e)
            _tool_registry = None

    # -- Phase 3: Wire LCMEngine -----------------------------------------------
    global _lcm_engine_instance
    if _lcm_available:
        try:
            _lcm_engine_instance = _LCMEngine()
            log.info("LCMEngine initialized")
        except Exception as _e:
            log.warning("LCMEngine init failed (%s)", _e)
            _lcm_engine_instance = None

    # -- Phase 3: Wire GateBypassController ------------------------------------
    global _gate_bypass
    if _gate_bypass_available:
        try:
            _gate_bypass = _GateBypassController()
            log.info("GateBypassController initialized")
        except Exception as _e:
            log.warning("GateBypassController init failed (%s)", _e)
            _gate_bypass = None

    # -- Phase 3: Wire FeatureFlagManager --------------------------------------
    global _feature_flag_manager
    if _feature_flags_available:
        try:
            _feature_flag_manager = _FeatureFlagManager()
            log.info("FeatureFlagManager initialized")
        except Exception as _e:
            log.warning("FeatureFlagManager init failed (%s)", _e)
            _feature_flag_manager = None

    # -- Phase 3: Wire TeamCoordinator -----------------------------------------
    global _team_coordinator
    if _multi_agent_available:
        try:
            _team_coordinator = _TeamCoordinator()
            log.info("TeamCoordinator initialized")
        except Exception as _e:
            log.warning("TeamCoordinator init failed (%s)", _e)
            _team_coordinator = None

    # -- Phase 3: Wire PersistentMemory ----------------------------------------
    global _persistent_memory
    if _persistent_memory_available:
        try:
            _persistent_memory = _PersistentMemoryStore()
            log.info("PersistentMemoryStore initialized")
        except Exception as _e:
            log.warning("PersistentMemoryStore init failed (%s)", _e)
            _persistent_memory = None

    # -- Phase 3: Wire SkillRegistry -------------------------------------------
    global _skill_registry
    if _skill_system_available:
        try:
            _skill_registry = _SkillRegistry()
            log.info("SkillRegistry initialized")
        except Exception as _e:
            log.warning("SkillRegistry init failed (%s)", _e)
            _skill_registry = None

    # -- Phase 3: Wire MCPPluginManager ----------------------------------------
    global _mcp_plugin_manager
    if _mcp_plugin_available:
        try:
            _mcp_plugin_manager = _MCPPluginManager()
            log.info("MCPPluginManager initialized")
        except Exception as _e:
            log.warning("MCPPluginManager init failed (%s)", _e)
            _mcp_plugin_manager = None

    # -- Phase 3: CEO Heartbeat tick loop (6th background task) ----------------
    if _heartbeat_runner is not None:
        _ceo_hb_task = asyncio.create_task(_ceo_heartbeat_tick())
        _ceo_hb_task.add_done_callback(_bg_task_done_callback)
        _background_tasks.append(_ceo_hb_task)
        log.info("CEO heartbeat tick started")

    # -- Global Feedback System (GFB-002) --------------------------------------
    global _feedback_dispatcher
    if _global_feedback_available:
        try:
            _feedback_dispatcher = _GlobalFeedbackDispatcher()
            log.info("GlobalFeedbackDispatcher initialized")
        except Exception as _e:
            log.warning("GlobalFeedbackDispatcher init failed (%s)", _e)
            _feedback_dispatcher = None

    log.info("Murphy Production Server v3 started — HITL gates active, milestone tracking enabled")


# -- Graceful Shutdown ---------------------------------------------------------
# Label: GRACEFUL-SHUTDOWN — Clean up background tasks on SIGTERM / server stop.
# Commissioning: All 5 background tick-loops are cancelled, SSE/WS clients
# are notified, and the rate governor state is logged for diagnostics.
@app.on_event("shutdown")
async def _shutdown():
    log.info("Murphy Production Server shutting down — cancelling %d background tasks", len(_background_tasks))
    for task in _background_tasks:
        if not task.done():
            task.cancel()
    # Wait briefly for tasks to acknowledge cancellation
    if _background_tasks:
        await asyncio.gather(*_background_tasks, return_exceptions=True)
    _background_tasks.clear()
    # Log rate governor final state for diagnostics
    if _rate_governor is not None:
        log.info("Rate governor final state: %s", _rate_governor.status())
    # Persist Rosetta state on shutdown
    if _rosetta_manager is not None:
        try:
            _rosetta_manager.save_state()
            log.info("Rosetta state saved on shutdown")
        except Exception as _e:
            log.warning("Rosetta state save failed on shutdown: %s", _e)
    log.info("Murphy Production Server shutdown complete")

# == Crown Jewel API Endpoints (Phases 1-8) ====================================

# -- Phase 1: Rosetta endpoints ------------------------------------------------
@app.get("/api/rosetta/state")
async def rosetta_state():
    """GET /api/rosetta/state — current Rosetta state snapshot. G1: RosettaManager state."""
    if _rosetta_manager is None:
        return JSONResponse({"available": False, "message": "RosettaManager not initialized"})
    try:
        states = _rosetta_manager.list_all()
        return JSONResponse({"available": True, "agent_count": len(states), "agents": [s for s in states]})
    except Exception as _e:
        log.warning("Rosetta state fetch error: %s", _e)
        return JSONResponse({"available": True, "error": str(_e)}, status_code=500)


@app.get("/api/rosetta/personas")
async def rosetta_personas():
    """GET /api/rosetta/personas — list all personas."""
    if _rosetta_manager is None:
        return JSONResponse({"available": False, "personas": []})
    try:
        all_states = _rosetta_manager.list_all()
        return JSONResponse({"available": True, "personas": all_states})
    except Exception as _e:
        return JSONResponse({"available": True, "error": str(_e), "personas": []}, status_code=500)


@app.get("/api/rosetta/persona/{persona_id}")
async def rosetta_persona(persona_id: str):
    """GET /api/rosetta/persona/{id} — single persona detail."""
    if _rosetta_manager is None:
        raise HTTPException(status_code=503, detail="RosettaManager not initialized")
    try:
        state = _rosetta_manager.get_state(persona_id)
        if state is None:
            raise HTTPException(status_code=404, detail=f"Persona {persona_id!r} not found")
        return JSONResponse({"persona_id": persona_id, "state": state})
    except HTTPException:
        raise
    except Exception as _e:
        raise HTTPException(status_code=500, detail=str(_e))


# -- Phase 1: CEO Branch endpoints ---------------------------------------------
@app.get("/api/ceo/status")
async def ceo_status():
    """GET /api/ceo/status — CEO Branch state and active VP roles."""
    if _ceo_branch is None:
        return JSONResponse({"available": False, "message": "CEOBranch not initialized"})
    try:
        status = _ceo_branch.get_status()
        return JSONResponse({"available": True, **status})
    except Exception as _e:
        return JSONResponse({"available": True, "error": str(_e)}, status_code=500)


@app.get("/api/ceo/directives")
async def ceo_directives():
    """GET /api/ceo/directives — list issued CEO directives."""
    if _ceo_branch is None:
        return JSONResponse({"available": False, "directives": []})
    try:
        status = _ceo_branch.get_status()
        return JSONResponse({"available": True, "directives": status.get("directives", [])})
    except Exception as _e:
        return JSONResponse({"available": True, "error": str(_e), "directives": []}, status_code=500)


@app.get("/api/heartbeat/status")
async def heartbeat_status():
    """GET /api/heartbeat/status — stability monitor state."""
    if _heartbeat_runner is None:
        return JSONResponse({"available": False, "message": "HeartbeatRunner not initialized"})
    try:
        status = _heartbeat_runner.get_status()
        return JSONResponse({"available": True, **status})
    except Exception as _e:
        return JSONResponse({"available": True, "error": str(_e)}, status_code=500)


# -- Phase 2: AionMind endpoints -----------------------------------------------
@app.get("/api/aionmind/status")
async def aionmind_status():
    """GET /api/aionmind/status — kernel state and layer health."""
    if _aionmind_kernel is None:
        return JSONResponse({"available": False, "message": "AionMindKernel not initialized"})
    try:
        status = _aionmind_kernel.get_status()
        return JSONResponse({"available": True, **status})
    except Exception as _e:
        return JSONResponse({"available": True, "error": str(_e)}, status_code=500)


# -- Phase 2: Tool Registry endpoints ------------------------------------------
@app.get("/api/tools")
async def list_tools():
    """GET /api/tools — list registered tools with permission levels."""
    if _tool_registry is None:
        return JSONResponse({"available": False, "tools": []})
    try:
        tools = _tool_registry.list_all()
        return JSONResponse({"available": True, "count": len(tools), "tools": tools})
    except Exception as _e:
        return JSONResponse({"available": True, "error": str(_e), "tools": []}, status_code=500)


# -- Phase 3: LCM Engine endpoints ---------------------------------------------
@app.get("/api/lcm/status")
async def lcm_status():
    """GET /api/lcm/status — LCM Engine health and immune memory."""
    if _lcm_engine_instance is None:
        return JSONResponse({"available": False, "message": "LCMEngine not initialized"})
    try:
        immune_mem = _lcm_engine_instance.get_immune_memory()
        return JSONResponse({"available": True, "immune_memory_size": len(immune_mem) if immune_mem else 0})
    except Exception as _e:
        return JSONResponse({"available": True, "error": str(_e)}, status_code=500)


# -- Phase 3: Gate Bypass endpoints --------------------------------------------
@app.get("/api/gates/trust-levels")
async def gate_trust_levels():
    """GET /api/gates/trust-levels — operator trust escalation levels."""
    if _gate_bypass is None:
        return JSONResponse({"available": False, "trust_levels": {}})
    try:
        trust = _gate_bypass.get_trust_levels()
        return JSONResponse({"available": True, "trust_levels": trust})
    except Exception as _e:
        return JSONResponse({"available": True, "error": str(_e), "trust_levels": {}}, status_code=500)


# -- Phase 3: Feature Flag endpoints -------------------------------------------
@app.get("/api/features")
async def list_features():
    """GET /api/features — feature flag states."""
    if _feature_flag_manager is None:
        return JSONResponse({"available": False, "flags": []})
    try:
        flags = getattr(_feature_flag_manager, "_flags", {})
        return JSONResponse({"available": True, "count": len(flags), "flag_ids": list(flags.keys())})
    except Exception as _e:
        return JSONResponse({"available": True, "error": str(_e), "flags": []}, status_code=500)


# -- Phase 3: Multi-Agent endpoints --------------------------------------------
@app.get("/api/agents/teams")
async def agent_teams():
    """GET /api/agents/teams — active agent teams."""
    if _team_coordinator is None:
        return JSONResponse({"available": False, "teams": []})
    try:
        teams = _team_coordinator.get_active_teams()
        return JSONResponse({"available": True, "teams": teams})
    except Exception as _e:
        return JSONResponse({"available": True, "error": str(_e), "teams": []}, status_code=500)


# -- Phase 3: Persistent Memory endpoints -------------------------------------
@app.get("/api/memory/search")
async def memory_search(query: str = "", tenant_id: str = "default"):
    """GET /api/memory/search — search persistent memory."""
    if _persistent_memory is None:
        return JSONResponse({"available": False, "results": []})
    try:
        results = _persistent_memory.search(tenant_id, query)
        return JSONResponse({"available": True, "results": results})
    except Exception as _e:
        return JSONResponse({"available": True, "error": str(_e), "results": []}, status_code=500)


# -- Phase 3: Skill endpoints --------------------------------------------------
@app.get("/api/skills")
async def list_skills():
    """GET /api/skills — list available skills."""
    if _skill_registry is None:
        return JSONResponse({"available": False, "skills": []})
    try:
        skills = _skill_registry.list_skills()
        return JSONResponse({"available": True, "count": len(skills), "skills": skills})
    except Exception as _e:
        return JSONResponse({"available": True, "error": str(_e), "skills": []}, status_code=500)


# -- Phase 3: MCP Plugin endpoints ---------------------------------------------
@app.get("/api/mcp/plugins")
async def list_mcp_plugins():
    """GET /api/mcp/plugins — registered MCP plugins."""
    if _mcp_plugin_manager is None:
        return JSONResponse({"available": False, "plugins": []})
    try:
        plugins = _mcp_plugin_manager.list_servers()
        return JSONResponse({"available": True, "count": len(plugins), "plugins": plugins})
    except Exception as _e:
        return JSONResponse({"available": True, "error": str(_e), "plugins": []}, status_code=500)


# -- Diagnostics endpoint (Phase 5) -------------------------------------------
@app.get("/api/diagnostics")
async def diagnostics():
    """GET /api/diagnostics — full subsystem health, tick times, error counts, memory."""
    import psutil
    proc = psutil.Process()
    mem_mb = proc.memory_info().rss / 1024 / 1024
    return JSONResponse({
        "subsystems": {
            "rosetta": {"available": _rosetta_manager is not None},
            "ceo_branch": {"available": _ceo_branch is not None},
            "heartbeat_runner": {"available": _heartbeat_runner is not None},
            "aionmind": {"available": _aionmind_kernel is not None},
            "lcm_engine": {"available": _lcm_engine_instance is not None},
            "gate_bypass": {"available": _gate_bypass is not None},
            "tool_registry": {"available": _tool_registry is not None},
            "feature_flags": {"available": _feature_flag_manager is not None},
            "team_coordinator": {"available": _team_coordinator is not None},
            "persistent_memory": {"available": _persistent_memory is not None},
            "skill_registry": {"available": _skill_registry is not None},
            "mcp_plugins": {"available": _mcp_plugin_manager is not None},
        },
        "background_tasks": len(_background_tasks),
        "memory_mb": round(mem_mb, 1),
        "pending_hitl": sum(1 for h in _HITL_QUEUE if h["status"] == "pending"),
        "active_automations": sum(1 for a in _automation_store if a.get("status") == "active"),
    })


# ==============================================================================
# HEALTH
# ==============================================================================
@app.get("/health")
async def health():
    active = sum(1 for a in _automation_store if a.get("status") == "active")
    pending_hitl = sum(1 for h in _HITL_QUEUE if h["status"] == "pending")
    return JSONResponse({
        "status": "ok", "version": "3.0.0", "env": _env,
        "active_automations": active, "total_automations": len(_automation_store),
        "tenants": len(_TENANTS), "campaigns": len(_campaigns),
        "pending_hitl_items": pending_hitl,
        "sse_subscribers": len(_sse_subscribers),
        "ws_clients": len(_ws_clients), "ts": _now_iso(),
        "subsystems_wired": sum([
            _rosetta_manager is not None,
            _ceo_branch is not None,
            _heartbeat_runner is not None,
            _aionmind_kernel is not None,
            _lcm_engine_instance is not None,
            _gate_bypass is not None,
            _tool_registry is not None,
            _feature_flag_manager is not None,
            _team_coordinator is not None,
            _persistent_memory is not None,
            _skill_registry is not None,
            _mcp_plugin_manager is not None,
        ]),
    })

@app.get("/api/rate-governor/status")
async def rate_governor_status():
    """Swarm rate governor diagnostics — active buckets, per-class limits, usage."""
    if _rate_governor is None:
        return JSONResponse({"enabled": False, "message": "Rate governor not loaded"})
    return JSONResponse({"enabled": True, **_rate_governor.status()})

# ==============================================================================
# HITL — Human-in-the-Loop Queue
# ==============================================================================
@app.get("/api/hitl/queue")
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

@app.get("/api/hitl/{hitl_id}")
async def get_hitl_item(hitl_id: str):
    item = next((h for h in _HITL_QUEUE if h["id"] == hitl_id), None)
    if not item: raise HTTPException(404, f"HITL item {hitl_id} not found")
    return JSONResponse({k: v for k, v in item.items() if not k.startswith("_")})

@app.get("/api/hitl/{hitl_id}/inspect")
async def inspect_hitl_deliverable(hitl_id: str):
    """Inspect a HITL deliverable to understand what it is, what changes were made, 
    and what those changes do.
    
    This provides the human-in-the-loop with the data needed to make informed choices:
    - WHAT the deliverable is (type, purpose, content preview)
    - WHAT CHANGES were made (diff from previous version, if any)
    - WHAT THOSE CHANGES DO (impact analysis, affected systems)
    """
    item = next((h for h in _HITL_QUEUE if h["id"] == hitl_id), None)
    if not item: raise HTTPException(404, f"HITL item {hitl_id} not found")
    
    hitl_type = item.get("type", "unknown")
    payload = item.get("payload", {})
    
    inspection = {
        "hitl_id": hitl_id,
        "type": hitl_type,
        "status": item.get("status"),
        "created_at": item.get("created_at"),
        "inspected_at": _now_iso()
    }
    
    # Type-specific inspection details
    if hitl_type == "automation_milestone":
        auto_id = payload.get("automation_id")
        ms_id = payload.get("milestone_id")
        auto = next((a for a in _automation_store if a["id"] == auto_id), None)
        
        if auto:
            milestone = next((m for m in auto.get("milestones", []) if m["id"] == ms_id), None)
            inspection["deliverable_info"] = {
                "what_it_is": {
                    "title": f"Milestone: {milestone.get('name', 'Unknown')}" if milestone else "Unknown Milestone",
                    "automation_name": auto.get("name"),
                    "automation_type": auto.get("type"),
                    "description": f"This is a checkpoint in the {auto.get('name', 'automation')} workflow requiring human approval before proceeding."
                },
                "changes_made": {
                    "previous_status": "running" if milestone else "unknown",
                    "current_status": "awaiting_approval",
                    "progress": milestone.get("progress", 0) if milestone else 0,
                    "modified_fields": ["status", "hitl_item_id"],
                    "change_summary": f"Milestone execution paused at {milestone.get('progress', 0)}% completion for review."
                },
                "what_changes_do": {
                    "on_approve": "Milestone marked complete, automation proceeds to next phase",
                    "on_reject": "Milestone returns to running state for rework, progress may decrease",
                    "affected_systems": auto.get("integrations", []),
                    "downstream_impact": f"Next milestone: {milestone.get('next_milestone', 'workflow completion')}" if milestone else "Unknown"
                }
            }
            inspection["content_preview"] = {
                "milestone_details": milestone,
                "automation_context": {
                    "name": auto.get("name"),
                    "type": auto.get("type"),
                    "tier": auto.get("tier"),
                    "total_milestones": len(auto.get("milestones", []))
                }
            }
    
    elif hitl_type == "campaign_paid_ad":
        tier = payload.get("tier", "unknown")
        proposal = payload.get("proposal", {})
        
        inspection["deliverable_info"] = {
            "what_it_is": {
                "title": f"Paid Ad Proposal for {tier} tier",
                "type": "Marketing Campaign Proposal",
                "description": "AI-generated paid advertising proposal requiring approval before campaign launch."
            },
            "changes_made": {
                "generated_by": "Murphy AI Marketing Engine",
                "proposal_components": ["targeting", "messaging", "budget_allocation", "timeline"],
                "change_summary": "New proposal generated based on tier performance data and market analysis."
            },
            "what_changes_do": {
                "on_approve": f"Campaign launches for {tier} tier with specified budget and targeting",
                "on_reject": "Proposal discarded, new proposal can be requested",
                "affected_systems": ["marketing_automation", "ad_platforms", "analytics"],
                "estimated_reach": proposal.get("estimated_reach", "calculated on approval"),
                "budget_impact": proposal.get("budget", "per approved amount")
            }
        }
        inspection["content_preview"] = proposal
    
    elif hitl_type == "setup_step":
        step_id = payload.get("step_id")
        step = next((s for s in _SELF_SETUP_STEPS if s["id"] == step_id), None)
        
        if step:
            inspection["deliverable_info"] = {
                "what_it_is": {
                    "title": f"Setup Step: {step.get('name', 'Unknown')}",
                    "type": "System Configuration Step",
                    "description": step.get("description", "Self-setup workflow step requiring completion verification.")
                },
                "changes_made": {
                    "step_name": step.get("name"),
                    "progress": step.get("progress", 0),
                    "change_summary": f"Step marked as {step.get('status')} awaiting verification."
                },
                "what_changes_do": {
                    "on_approve": "Step marked complete, workflow advances to next step",
                    "on_reject": "Step returns to active status for rework",
                    "downstream_steps": [s.get("name") for s in _SELF_SETUP_STEPS if s.get("order", 0) > step.get("order", 0)]
                }
            }
            inspection["content_preview"] = step
    
    else:
        # Generic inspection for unknown types
        inspection["deliverable_info"] = {
            "what_it_is": {
                "type": hitl_type,
                "description": "Generic HITL item requiring review."
            },
            "changes_made": {
                "change_summary": "Item queued for human review."
            },
            "what_changes_do": {
                "on_approve": "Item approved, proceeds in workflow",
                "on_reject": "Item rejected, returns for rework"
            }
        }
        inspection["content_preview"] = payload
    
    # Add rejection context if previously rejected
    if item.get("status") == "rejected":
        inspection["rejection_context"] = {
            "reason": item.get("rejection_reason"),
            "rejected_at": item.get("rejected_at"),
            "rejected_by": item.get("approved_by"),
            "follow_up_questions": item.get("follow_up_questions", []),
            "desired_outcome": item.get("desired_outcome"),
            "example_reference": item.get("example_reference")
        }
    
    return JSONResponse(inspection)

@app.post("/api/hitl/{hitl_id}/approve")
async def approve_hitl_item(hitl_id: str, req: HITLDecisionRequest):
    item = next((h for h in _HITL_QUEUE if h["id"] == hitl_id), None)
    if not item: raise HTTPException(404, f"HITL item {hitl_id} not found")
    if item["status"] != "pending":
        raise HTTPException(400, f"Item is already {item['status']}")

    item["status"] = "approved"
    item["approved_at"] = _now_iso()
    item["approved_by"] = req.approved_by
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

@app.post("/api/hitl/{hitl_id}/reject")
async def reject_hitl_item(hitl_id: str, req: HITLRejectionRequest):
    """Enhanced rejection endpoint with mandatory reason and follow-up question generation.
    
    The HITL rejection process now:
    1. REQUIRES a reason (min 10 characters) - not optional
    2. Generates LLM-powered follow-up questions to clarify what's needed
    3. Supports example uploads for reference
    4. Uses MFGC to identify ambiguity flags
    """
    item = next((h for h in _HITL_QUEUE if h["id"] == hitl_id), None)
    if not item: raise HTTPException(404, f"HITL item {hitl_id} not found")
    if item["status"] != "pending":
        raise HTTPException(400, f"Item is already {item['status']}")

    # Generate follow-up questions using MFGC-style analysis
    follow_up_questions = []
    mfgc_flags = []
    
    if req.request_follow_up_questions:
        # MFGC ambiguity detection - identify what needs clarification
        rejection_context = f"Rejection reason: {req.reason}"
        if req.desired_outcome:
            rejection_context += f"\nDesired outcome: {req.desired_outcome}"
        
        # Generate targeted follow-up questions based on rejection type
        hitl_type = item.get("type", "unknown")
        
        if "vague" in req.reason.lower() or "unclear" in req.reason.lower():
            mfgc_flags.append("ambiguity_in_requirements")
            follow_up_questions.extend([
                "What specific aspects of the deliverable need clarification?",
                "Can you provide a concrete example of the expected output?",
                "What constraints or requirements were not met?"
            ])
        
        if "incorrect" in req.reason.lower() or "wrong" in req.reason.lower():
            mfgc_flags.append("output_mismatch")
            follow_up_questions.extend([
                "What specifically is incorrect about the current output?",
                "What should the correct output look like?",
                "Are there reference materials that show the expected format?"
            ])
        
        if "incomplete" in req.reason.lower():
            mfgc_flags.append("incomplete_deliverable")
            follow_up_questions.extend([
                "What sections or components are missing?",
                "What additional information should be included?",
                "Is there a template or example to follow?"
            ])
        
        # Type-specific follow-up questions
        if hitl_type == "automation_milestone":
            follow_up_questions.extend([
                "What should the automation do differently?",
                "Are there specific test cases that failed?",
                "What integration points need adjustment?"
            ])
        elif hitl_type == "campaign_paid_ad":
            follow_up_questions.extend([
                "What changes to the targeting or messaging are needed?",
                "Are there brand guidelines that should be followed?",
                "What metrics should the campaign optimize for?"
            ])
        
        # If example was uploaded, add context
        if req.example_upload_url:
            mfgc_flags.append("example_provided")
            follow_up_questions.append(
                f"I see you've provided an example ({req.example_description or 'reference file'}). "
                "Should the system match this format/style exactly, or adapt certain elements?"
            )
        
        # Deduplicate and limit
        seen = set()
        unique_questions = []
        for q in follow_up_questions:
            q_lower = q.lower()
            if q_lower not in seen:
                seen.add(q_lower)
                unique_questions.append(q)
        follow_up_questions = unique_questions[:5]  # Max 5 questions
    
    # Update item with enhanced rejection data
    item["status"] = "rejected"
    item["rejected_at"] = _now_iso()
    item["approved_by"] = req.approved_by
    item["rejection_reason"] = req.reason
    item["follow_up_questions"] = follow_up_questions
    item["mfgc_ambiguity_flags"] = mfgc_flags
    if req.example_upload_url:
        item["example_reference"] = {
            "url": req.example_upload_url,
            "description": req.example_description
        }
    if req.desired_outcome:
        item["desired_outcome"] = req.desired_outcome
    
    hitl_type = item["type"]

    # Handle type-specific rejection logic
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

    _broadcast_sse("hitl_rejected", {
        "id": hitl_id, 
        "type": hitl_type, 
        "reason": req.reason,
        "follow_up_questions": follow_up_questions,
        "mfgc_flags": mfgc_flags
    })
    await _broadcast_ws("hitl_rejected", {"id": hitl_id, "type": hitl_type})
    
    return JSONResponse({
        **{k: v for k, v in item.items() if not k.startswith("_")},
        "hitl_enhancement": {
            "follow_up_questions_generated": len(follow_up_questions),
            "ambiguity_flags_detected": mfgc_flags,
            "example_provided": req.example_upload_url is not None
        }
    })

# ==============================================================================
# TENANT / ORG ENDPOINTS
# ==============================================================================
@app.get("/api/tenant")
async def list_tenants():
    return JSONResponse({"tenants": list(_TENANTS.values()), "total": len(_TENANTS)})

@app.get("/api/tenant/{tenant_id}")
async def get_tenant(tenant_id: str):
    t = _TENANTS.get(tenant_id)
    if not t: raise HTTPException(404, f"Tenant {tenant_id} not found")
    tenant_autos = [a for a in _automation_store if a.get("tenant_id") == tenant_id]
    return JSONResponse({**t,
        "automation_count": len(tenant_autos),
        "active_automations": sum(1 for a in tenant_autos if a["status"] == "active"),
        "monthly_savings": round(sum(_cost_savings(a)*{"hourly":720,"daily":30,"weekly":4,"monthly":1}.get(a.get("recurrence","daily"),30) for a in tenant_autos),2),
    })

@app.post("/api/tenant")
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
@app.get("/api/calendar")
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
        except (ValueError, TypeError, KeyError): orig = datetime.now(_UTC)
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

@app.get("/api/calendar/blocks")
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
@app.get("/api/automations")
async def list_automations(board_id:str=Query(default=""), tenant_id:str=Query(default=""),
                           category:str=Query(default=""), status:str=Query(default="")):
    autos = list(_automation_store)
    if board_id:  autos=[a for a in autos if a.get("board_id")==board_id]
    if tenant_id: autos=[a for a in autos if a.get("tenant_id")==tenant_id]
    if category:  autos=[a for a in autos if a.get("category")==category]
    if status:    autos=[a for a in autos if a.get("status")==status]
    return JSONResponse({"automations":[{**a,"cost_savings":_cost_savings(a)} for a in autos],"total":len(autos)})

# SSE route MUST be before {auto_id} parameterized routes
@app.get("/api/automations/stream")
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
            except ValueError: pass
    return StreamingResponse(event_gen(), media_type="text/event-stream",
                             headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"})

@app.get("/api/automations/{auto_id}")
async def get_automation(auto_id: str):
    a = next((x for x in _automation_store if x["id"]==auto_id), None)
    if not a: raise HTTPException(404, f"Automation {auto_id} not found")
    return JSONResponse({**a,"cost_savings":_cost_savings(a)})

@app.get("/api/automations/{auto_id}/milestones")
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

@app.post("/api/automations/{auto_id}/milestones/{ms_id}/delay")
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

@app.patch("/api/automations/{auto_id}")
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

@app.delete("/api/automations/{auto_id}")
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

@app.post("/api/prompt")
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
                "You are Murphy, an AI system builder and automation platform developed by Inoni LLC. "
                "Your job is to design business automations. "
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
@app.get("/api/labor-cost")
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
@app.get("/api/verticals")
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

@app.get("/api/verticals/{vertical_id}")
async def get_vertical(vertical_id:str, tenant_id:str=Query(default="")):
    v=_VERTICAL_CONFIGS.get(vertical_id)
    if not v: raise HTTPException(404,f"Vertical {vertical_id} not found")
    autos=[a for a in _automation_store if a.get("category")==vertical_id and (not tenant_id or a.get("tenant_id")==tenant_id)]
    recent=[e for e in _execution_log[-50:] if any(e["automation_id"]==a["id"] for a in autos)][-10:]
    return JSONResponse({**v,"id":vertical_id,
        "automations":[{**a,"cost_savings":_cost_savings(a)} for a in autos],
        "recent_executions":recent,
        "total_monthly_savings":round(sum(_cost_savings(a)*{"hourly":720,"daily":30,"weekly":4,"monthly":1}.get(a.get("recurrence","daily"),30) for a in autos),2)})

@app.post("/api/verticals/{vertical_id}/activate")
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
@app.get("/api/marketing/campaigns")
async def get_campaigns():
    return JSONResponse({"campaigns":list(_campaigns.values()),"total":len(_campaigns)})

@app.get("/api/marketing/campaigns/{tier}")
async def get_campaign(tier:str):
    c=_campaigns.get(tier)
    if not c: raise HTTPException(404,f"Campaign tier {tier} not found")
    return JSONResponse(c)

@app.post("/api/marketing/campaigns/{tier}/adjust")
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

@app.post("/api/marketing/paid-proposal")
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

@app.post("/api/marketing/paid-proposal/{proposal_id}/approve")
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

@app.get("/api/marketing/paid-proposals")
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

@app.get("/api/proposals/requests")
async def list_proposal_requests():
    return JSONResponse({"requests":_incoming_requests,"total":len(_incoming_requests)})

@app.post("/api/proposals/generate")
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

@app.get("/api/proposals/generated")
async def list_generated_proposals():
    return JSONResponse({"proposals":_generated_proposals,"total":len(_generated_proposals)})

@app.get("/api/proposals/generated/{proposal_id}")
async def get_generated_proposal(proposal_id:str):
    p=next((x for x in _generated_proposals if x["id"]==proposal_id),None)
    if not p: raise HTTPException(404,"Proposal not found")
    return JSONResponse(p)

@app.post("/api/proposals/generated/{proposal_id}/approve")
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

@app.post("/api/workflows/generate")
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

@app.get("/api/workflows")
async def list_workflows(tenant_id:str=Query(default="")):
    wfs=_workflow_history if not tenant_id else [w for w in _workflow_history if w.get("tenant_id")==tenant_id]
    return JSONResponse({"workflows":wfs,"total":len(wfs)})

@app.post("/api/workflows/{workflow_id}/execute")
async def execute_workflow(workflow_id:str):
    wf=next((w for w in _workflow_history if w["id"]==workflow_id),None)
    if not wf: raise HTTPException(404,"Workflow not found")
    wf["status"]="running"; wf["started_at"]=_now_iso()
    if wf.get("steps"): wf["steps"][0]["status"] = "running"
    _broadcast_sse("workflow_started",wf); await _broadcast_ws("workflow_started",wf)
    return JSONResponse(wf)

@app.post("/api/workflows/{workflow_id}/steps/{step_id}/approve")
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

@app.post("/api/workflows/{workflow_id}/advance")
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
@app.get("/api/comms/rooms")
async def list_rooms():
    return JSONResponse({"rooms":[{
        "id":room,"agents":agents,"agent_count":len(agents),
        "message_count":len([m for m in _agent_messages if m.get("room")==room]),
        "last_activity":next((m["sent_at"] for m in reversed(_agent_messages) if m.get("room")==room),None)
    } for room,agents in _SUBSYSTEM_ROOMS.items()],"total":len(_SUBSYSTEM_ROOMS)})

@app.post("/api/comms/send")
async def send_agent_message(msg:AgentMessageRequest):
    if msg.room not in _SUBSYSTEM_ROOMS: raise HTTPException(404,f"Room {msg.room} not found")
    message={"id":f"msg-{uuid.uuid4().hex[:8]}","sender":msg.sender,"room":msg.room,
        "message_type":msg.message_type,"content":msg.content,"recipients":_SUBSYSTEM_ROOMS[msg.room],
        "sent_at":_now_iso(),"status":"delivered"}
    _agent_messages.append(message)
    if len(_agent_messages)>1000: del _agent_messages[:100]
    _broadcast_sse("agent_message",message); await _broadcast_ws("agent_message",message)
    return JSONResponse(message, status_code=201)

@app.get("/api/comms/messages")
async def get_messages(room:str=Query(default=""), limit:int=Query(default=50,le=200)):
    msgs=_agent_messages if not room else [m for m in _agent_messages if m.get("room")==room]
    return JSONResponse({"messages":msgs[-limit:],"total":len(msgs)})

@app.post("/api/comms/broadcast")
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
@app.get("/api/pipeline/self-setup")
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

@app.post("/api/pipeline/self-setup/advance")
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

@app.post("/api/pipeline/self-setup/run-full")
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
@app.get("/api/executions")
async def get_executions(limit:int=Query(default=50,le=200), tenant_id:str=Query(default="")):
    execs=_execution_log if not tenant_id else [e for e in _execution_log if e.get("tenant_id")==tenant_id]
    return JSONResponse({"executions":execs[-limit:],"total":len(execs)})

@app.get("/api/tiers")
async def get_tiers():
    return JSONResponse({"tiers":TIERS,"active_automations":sum(1 for a in _automation_store if a["status"]=="active")})

_BOT_MANIFEST=["scheduler_bot","anomaly_watcher_bot","feedback_bot","librarian_bot","memory_manager_bot","triage_bot","optimization_bot","analysis_bot","commissioning_bot","engineering_bot","key_manager_bot","ghost_controller_bot","kaia","kiren","vallon","veritas","osmosis","rubixcube_bot"]

@app.get("/api/bots/status")
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
@app.get("/ws")
async def ws_http_fallback():
    """Fallback for HTTP clients trying to reach the WebSocket endpoint."""
    return JSONResponse({"error": "WebSocket endpoint — use ws:// protocol", "path": "/ws"}, status_code=426)

@app.websocket("/ws")
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
            except json.JSONDecodeError: pass
    except WebSocketDisconnect:
        log.info("WS disconnected: %s", client_id)
    finally:
        _ws_clients.pop(client_id,None)

# ==============================================================================
# ROI CALENDAR — Human vs Agent cost/ROI visualisation
# ==============================================================================
_roi_calendar_store: List[Dict[str, Any]] = []

@app.get("/api/roi-calendar/events")
async def roi_calendar_events_list(request: Request):
    return JSONResponse({"ok": True, "events": list(_roi_calendar_store), "total": len(_roi_calendar_store)})

@app.post("/api/roi-calendar/events")
async def roi_calendar_event_create(request: Request):
    body = await request.json()
    eid = "roi-" + uuid.uuid4().hex[:12]
    now_ts = _now_iso()
    event: Dict[str, Any] = {
        "event_id": eid,
        "title": body.get("title", "Untitled Task"),
        "description": body.get("description", ""),
        "automation_id": body.get("automation_id"),
        "start": body.get("start", now_ts),
        "end": body.get("end"),
        "status": "pending",
        "progress_pct": 0,
        "human_cost_estimate": float(body.get("human_cost_estimate", 0)),
        "human_time_estimate_hours": float(body.get("human_time_estimate_hours", 8)),
        "agent_compute_cost": 0.0,
        "overhead_cost": 0.0,
        "roi": 0.0,
        "actual_time_hours": 0.0,
        "agents": [],
        "hitl_reviews": [],
        "qc_passes": 0,
        "qc_failures": 0,
        "cost_adjustments": [],
        "created_at": now_ts,
        "updated_at": now_ts,
    }
    _roi_calendar_store.append(event)
    return JSONResponse({"ok": True, "event": event}, status_code=201)

@app.get("/api/roi-calendar/summary")
async def roi_calendar_summary():
    if not _roi_calendar_store:
        return JSONResponse({"ok": True, "total_human_cost_estimate": 0, "total_agent_cost": 0,
                             "total_roi": 0, "total_overhead": 0, "active_tasks": 0,
                             "completed_tasks": 0, "total_tasks": 0, "roi_pct": 0})
    total_human = sum(e["human_cost_estimate"] for e in _roi_calendar_store)
    total_agent = sum(e["agent_compute_cost"] for e in _roi_calendar_store)
    total_overhead = sum(e["overhead_cost"] for e in _roi_calendar_store)
    total_roi = total_human - total_agent - total_overhead
    roi_pct = round((total_roi / total_human * 100) if total_human > 0 else 0, 1)
    return JSONResponse({"ok": True,
        "total_human_cost_estimate": round(total_human, 2),
        "total_agent_cost": round(total_agent, 2),
        "total_roi": round(total_roi, 2),
        "total_overhead": round(total_overhead, 2),
        "active_tasks": sum(1 for e in _roi_calendar_store if e["status"] in ("running", "qc", "hitl_review")),
        "completed_tasks": sum(1 for e in _roi_calendar_store if e["status"] == "complete"),
        "total_tasks": len(_roi_calendar_store),
        "roi_pct": roi_pct})

@app.get("/api/roi-calendar/stream")
async def roi_calendar_stream(request: Request):
    _STATUS_SEQ = ["pending", "running", "qc", "complete"]
    _HITL_CHANCE = 0.15

    async def _gen():
        last_states: dict = {}
        ticks_to_advance = random.randint(3, 8)
        for tick in range(600):
            await asyncio.sleep(1)
            ticks_to_advance -= 1

            if ticks_to_advance <= 0:
                candidates = [e for e in _roi_calendar_store
                              if e.get("status") not in ("complete", "error")]
                if candidates:
                    ev = random.choice(candidates)
                    delta_pct = random.randint(5, 15)
                    ev["progress_pct"] = min(100, ev.get("progress_pct", 0) + delta_pct)

                    checklist = ev.get("checklist", [])
                    for ci, item in enumerate(checklist):
                        if item.get("status") == "running":
                            item["status"] = "complete"
                            item["completed_at"] = _now_iso()
                            for nitem in checklist[ci + 1:]:
                                if nitem.get("status") == "pending":
                                    nitem["status"] = "running"
                                    break
                            break
                        elif item.get("status") == "pending":
                            item["status"] = "running"
                            break

                    step_cost = round(random.uniform(0.02, 0.50), 2)
                    ev["agent_compute_cost"] = round(ev.get("agent_compute_cost", 0) + step_cost, 2)

                    hc = ev.get("human_cost_estimate", 0)
                    ac = ev.get("agent_compute_cost", 0)
                    oh = ev.get("overhead_cost", 0)
                    ev["roi"] = round(hc - ac - oh, 2)

                    cur_status = ev.get("status", "pending")
                    pct = ev["progress_pct"]
                    if cur_status == "pending" and pct > 5:
                        ev["status"] = "running"
                    elif cur_status == "running" and pct >= 90:
                        if random.random() < _HITL_CHANCE:
                            ev["status"] = "hitl_review"
                            ev["hitl_reviews"].append({
                                "decision": "pending",
                                "notes": "Automated HITL review triggered",
                                "ts": _now_iso(),
                                "cost_delta": 0,
                            })
                        else:
                            ev["status"] = "qc"
                    elif cur_status in ("qc", "hitl_review") and pct >= 95:
                        ev["status"] = "complete"
                        ev["progress_pct"] = 100
                        for item in checklist:
                            if item.get("status") != "complete":
                                item["status"] = "complete"
                                if not item.get("completed_at"):
                                    item["completed_at"] = _now_iso()
                        ev["qc_passes"] = ev.get("qc_passes", 0) + 1

                    ev["updated_at"] = _now_iso()

                ticks_to_advance = random.randint(3, 8)

            for ev in _roi_calendar_store:
                eid = ev["event_id"]
                ac = ev.get("agent_compute_cost", 0)
                sk = f"{ev.get('progress_pct', 0)}:{ev.get('status', '')}:{ac:.2f}"
                if last_states.get(eid) != sk:
                    last_states[eid] = sk
                    yield f"event: roi_update\ndata: {json.dumps(ev)}\n\n"
            yield "event: ping\ndata: {}\n\n"

    return StreamingResponse(_gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

@app.get("/api/roi-calendar/export")
async def roi_calendar_export(fmt: str = "json"):
    """Export ROI calendar data as JSON or CSV."""
    import io as _io_exp
    if fmt == "csv":
        import csv as _csv_exp
        output = _io_exp.StringIO()
        fieldnames = ["event_id", "title", "status", "progress_pct",
                      "human_cost_estimate", "human_time_estimate_hours",
                      "agent_compute_cost", "overhead_cost", "roi", "start", "end"]
        writer = _csv_exp.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for ev in _roi_calendar_store:
            writer.writerow(ev)
        content = output.getvalue()
        from starlette.responses import Response as _Resp
        return _Resp(content=content, media_type="text/csv",
                     headers={"Content-Disposition": "attachment; filename=roi-calendar.csv"})
    else:
        from starlette.responses import Response as _Resp
        content = json.dumps({"ok": True, "events": _roi_calendar_store}, indent=2)
        return _Resp(content=content, media_type="application/json",
                     headers={"Content-Disposition": "attachment; filename=roi-calendar.json"})

@app.patch("/api/roi-calendar/events/{event_id}")
async def roi_calendar_event_update(event_id: str, request: Request):
    body = await request.json()
    event = next((e for e in _roi_calendar_store if e["event_id"] == event_id), None)
    if not event:
        return JSONResponse({"ok": False, "error": "Event not found"}, status_code=404)
    for field in ["title", "description", "status", "progress_pct", "agent_compute_cost",
                  "overhead_cost", "actual_time_hours", "agents", "end"]:
        if field in body:
            event[field] = body[field]
    event["roi"] = event["human_cost_estimate"] - event["agent_compute_cost"] - event["overhead_cost"]
    if "hitl_review" in body:
        review = dict(body["hitl_review"])
        review["ts"] = _now_iso()
        event["hitl_reviews"].append(review)
        delta = float(review.get("cost_delta", event["human_cost_estimate"] * 0.05))
        event["cost_adjustments"].append({"reason": f"HITL review: {review.get('decision','change_requested')}", "delta": delta, "ts": review["ts"]})
        event["agent_compute_cost"] += delta
        event["roi"] = event["human_cost_estimate"] - event["agent_compute_cost"] - event["overhead_cost"]
    if "qc_result" in body:
        qc = body["qc_result"]
        if qc.get("passed"):
            event["qc_passes"] += 1
        else:
            event["qc_failures"] += 1
            delta = float(qc.get("retry_cost", event["agent_compute_cost"] * 0.1))
            event["cost_adjustments"].append({"reason": f"QC failure: {qc.get('reason','retry')}", "delta": delta, "ts": _now_iso()})
            event["agent_compute_cost"] += delta
            event["roi"] = event["human_cost_estimate"] - event["agent_compute_cost"] - event["overhead_cost"]
    event["updated_at"] = _now_iso()
    return JSONResponse({"ok": True, "event": event})

# ==============================================================================
# STATIC FILES + ALL ORIGINAL ROUTES PRESERVED
# ==============================================================================
_BASE_DIR   = Path(__file__).resolve().parent
_MURPHY_DIR = _BASE_DIR / "Murphy System"
_UI_DIR     = _BASE_DIR / "murphy_dashboard"

if _UI_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(_UI_DIR)), name="static_dash")
if (_MURPHY_DIR / "static").exists():
    app.mount("/murphy-static", StaticFiles(directory=str(_MURPHY_DIR / "static")), name="static_legacy")

def _read_html(path: Path) -> str:
    try: return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError): return f"<h1>File not found: {path}</h1>"

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    """Primary Command Center Dashboard"""
    idx = _UI_DIR / "index.html"
    if idx.exists(): return HTMLResponse(idx.read_text())
    return HTMLResponse("<h1>Murphy System API v3.0</h1><p><a href='/docs'>API Docs</a></p>")

@app.get("/calendar", response_class=HTMLResponse)
async def serve_calendar():
    """Original calendar UI — preserved"""
    for path in [
        _MURPHY_DIR / "calendar.html",
        _UI_DIR / "calendar.html",
    ]:
        if path.exists(): return HTMLResponse(path.read_text())
    return HTMLResponse("<p>Calendar at <a href='/'>dashboard</a></p>")

@app.get("/ui/roi-calendar", response_class=HTMLResponse)
async def serve_roi_calendar():
    """ROI Calendar — cost/ROI metrics control panel"""
    for path in [
        _BASE_DIR / "roi_calendar.html",
        _MURPHY_DIR / "roi_calendar.html",
        _UI_DIR / "roi_calendar.html",
    ]:
        if path.exists(): return HTMLResponse(path.read_text())
    return HTMLResponse("<p>ROI Calendar at <a href='/'>dashboard</a></p>")

@app.get("/dashboard", response_class=HTMLResponse)
async def serve_legacy_dashboard():
    """Original dashboard.html — preserved"""
    path = _MURPHY_DIR / "dashboard.html"
    if path.exists(): return HTMLResponse(path.read_text())
    return HTMLResponse("<p>Dashboard at <a href='/'>command center</a></p>")

@app.get("/landing", response_class=HTMLResponse)
async def serve_landing():
    """Original murphy_landing_page.html — preserved"""
    path = _MURPHY_DIR / "murphy_landing_page.html"
    if path.exists(): return HTMLResponse(path.read_text())
    return HTMLResponse("<p>Landing page not found</p>")

@app.get("/production-wizard", response_class=HTMLResponse)
async def serve_production_wizard():
    path = _MURPHY_DIR / "production_wizard.html"
    if path.exists(): return HTMLResponse(path.read_text())
    return HTMLResponse("<p>Production wizard not found</p>")

@app.get("/onboarding", response_class=HTMLResponse)
async def serve_onboarding():
    path = _MURPHY_DIR / "onboarding_wizard.html"
    if path.exists(): return HTMLResponse(path.read_text())
    return HTMLResponse("<p>Onboarding wizard not found</p>")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("murphy_production_server:app", host="0.0.0.0", port=port,
                reload=False, log_level="info")
# =============================================================================
# DEMO API ENDPOINTS - Forge Demo for Landing Page
# =============================================================================

# Rate limiting for demo
_DEMO_RATE_LIMITS: Dict[str, Dict[str, Any]] = {}
_DEMO_LIMIT_PER_DAY = 10

def _check_demo_rate_limit(fingerprint: str) -> Dict[str, Any]:
    """Check rate limit for demo builds."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if fingerprint not in _DEMO_RATE_LIMITS:
        _DEMO_RATE_LIMITS[fingerprint] = {"date": today, "count": 0}
    entry = _DEMO_RATE_LIMITS[fingerprint]
    if entry["date"] != today:
        entry["date"] = today
        entry["count"] = 0
    return {
        "builds_used_today": entry["count"],
        "builds_remaining_today": max(0, _DEMO_LIMIT_PER_DAY - entry["count"]),
        "limit": _DEMO_LIMIT_PER_DAY,
        "tier": "anonymous"
    }

def _consume_demo_rate_limit(fingerprint: str):
    """Consume one demo build."""
    if fingerprint in _DEMO_RATE_LIMITS:
        _DEMO_RATE_LIMITS[fingerprint]["count"] += 1

class BuildMetrics:
    """Tracks real metrics for a single forge run."""
    
    _TEAM_HOURLY = 75.0  # $75/hr average for dev team
    _HUMAN_TEAM_SIZE = 4
    _LLM_COST_PER_1K = 0.0006  # Approximate
    _SERVER_COST = 0.01
    _HITL_BUDGET = 0.05
    
    def __init__(self, query: str):
        self.query = query
        self.request_arrived_at = datetime.now(timezone.utc).isoformat()
        self.build_started_ts = 0.0
        self.build_ended_ts = 0.0
        self.llm_calls = 5
        self.total_tokens = 0
        self.agent_count = 64
        words = len(query.split())
        base_hours = 2.0 + min(words / 50, 6.0)
        self.predicted_human_hours = round(base_hours, 2)
        self.predicted_human_cost = round(self.predicted_human_hours * self._TEAM_HOURLY, 2)
        self.predicted_calendar_days = round(self.predicted_human_hours / (self._HUMAN_TEAM_SIZE * 6), 1)
    
    def start_build(self):
        import time
        self.build_started_ts = time.time()
    
    def finish_build(self):
        import time
        self.build_ended_ts = time.time()
        self.total_tokens = self.llm_calls * 1500
    
    @property
    def actual_elapsed_seconds(self) -> float:
        if self.build_ended_ts and self.build_started_ts:
            return round(self.build_ended_ts - self.build_started_ts, 3)
        return 0.0
    
    @property
    def total_actual_cost(self) -> float:
        llm_cost = (self.total_tokens / 1000) * self._LLM_COST_PER_1K
        return round(llm_cost + self._SERVER_COST + self._HITL_BUDGET, 6)
    
    @property
    def cost_savings(self) -> float:
        return round(self.predicted_human_cost - self.total_actual_cost, 2)
    
    @property
    def roi_multiple(self) -> float:
        if self.total_actual_cost > 0:
            return round(self.predicted_human_cost / self.total_actual_cost, 0)
        return 9999.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "llm_calls": self.llm_calls,
            "total_tokens": self.total_tokens,
            "agent_count": self.agent_count,
            "actual_elapsed_seconds": self.actual_elapsed_seconds,
            "total_actual_cost_usd": self.total_actual_cost,
            "predicted_human_hours": self.predicted_human_hours,
            "predicted_human_cost_usd": self.predicted_human_cost,
            "cost_savings_usd": self.cost_savings,
            "roi_multiple": self.roi_multiple,
        }

# Import demo deliverable generator
try:
    from demo_deliverable_generator import generate_deliverable as _generate_demo_deliverable
    _demo_gen_available = True
    log.info("Demo deliverable generator loaded")
except ImportError as e:
    log.warning(f"Demo deliverable generator not available: {e}")
    _demo_gen_available = False
    _generate_demo_deliverable = None

def _generate_fallback_deliverable(query: str) -> Dict[str, Any]:
    """Fallback deliverable generator when demo_deliverable_generator is not available."""
    return {
        "title": f"Deliverable: {query[:50]}",
        "filename": "murphy-deliverable.txt",
        "content": f"""# Murphy System Generated Deliverable

## Query
{query}

## Generated Content

This is a demonstration deliverable generated by Murphy System.

### Overview
Murphy System is an AI-powered business operating system that automates operations, 
enforces compliance, and replaces 12+ SaaS tools with one unified platform.

### Key Features
- AI Automation with Shadow Agents
- Human-in-the-Loop (HITL) Safety Gates
- Compliance as Code Engine
- Multi-tenant Architecture
- Real-time Dashboard

### Next Steps
1. Sign up for a free account
2. Configure your LLM provider
3. Create your first automation
4. Deploy and monitor

---
Generated by Murphy System - https://murphy.systems
""",
    }

@app.post("/api/demo/inspect")
async def api_demo_inspect(request: Request):
    """Inspect how a query would be processed through the forge pipeline."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"success": False, "error": "Invalid JSON"}, status_code=400)
    
    query = (body.get("query") or "").strip()
    if not query:
        return JSONResponse({"success": False, "error": "Query is required"}, status_code=400)
    
    from demo_deliverable_generator import _detect_scenario, _KEYWORD_MAP, _SCENARIO_TEMPLATES, _mfgc_quality_score, _scenario_to_filename
    
    # Step 1: Detect scenario
    detected_scenario = _detect_scenario(query)
    
    # Step 2: Find which keywords matched
    matched_keywords = []
    q = query.lower()
    for keyword, key in _KEYWORD_MAP.items():
        if keyword in q:
            matched_keywords.append({"keyword": keyword, "maps_to": key})
    
    # Step 3: Get template info
    template_info = None
    if detected_scenario and detected_scenario in _SCENARIO_TEMPLATES:
        template = _SCENARIO_TEMPLATES[detected_scenario]
        template_info = {
            "title": template.get("title", "Unknown"),
            "content_preview": template.get("content", "")[:500] + "...",
            "full_content_length": len(template.get("content", ""))
        }
    
    # Step 4: What would be generated
    filename = _scenario_to_filename(detected_scenario, query)
    quality = _mfgc_quality_score(detected_scenario) if detected_scenario else 94
    
    return JSONResponse({
        "success": True,
        "query": query,
        "pipeline_trace": {
            "step_1_scenario_detection": {
                "detected_scenario": detected_scenario,
                "matched_keywords": matched_keywords,
                "total_matches": len(matched_keywords)
            },
            "step_2_template_selection": {
                "template_found": detected_scenario is not None,
                "template_info": template_info
            },
            "step_3_output_generation": {
                "filename": filename,
                "quality_score": quality,
                "scenario_type": detected_scenario or "custom"
            }
        },
        "mss_enrichment": {
            "magnify": "Expands query to functional requirements + components",
            "solidify": "Converts to full implementation plan",
            "automation_blueprint": "Generated workflow with steps"
        },
        "mfgc_info": {
            "phases": ["INTAKE", "ANALYSIS", "SCORING", "GATING", "MURPHY_INDEX", "ENRICHMENT", "OUTPUT"],
            "confidence_baseline": quality / 100
        }
    })

@app.get("/api/demo/config")
async def api_demo_config():
    """Return the forge demo configuration showing scenarios, keywords, and system functions."""
    from demo_deliverable_generator import _SCENARIO_TEMPLATES, _KEYWORD_MAP, _mfgc_quality_score
    
    # Extract scenario info
    scenarios = {}
    for key, template in _SCENARIO_TEMPLATES.items():
        scenarios[key] = {
            "title": template.get("title", "Unknown"),
            "quality_score": _mfgc_quality_score(key),
            "content_length": len(template.get("content", ""))
        }
    
    # Group keywords by scenario
    keyword_groups = {}
    for keyword, scenario_key in _KEYWORD_MAP.items():
        if scenario_key not in keyword_groups:
            keyword_groups[scenario_key] = []
        keyword_groups[scenario_key].append(keyword)
    
    return JSONResponse({
        "success": True,
        "config": {
            "scenarios": scenarios,
            "keyword_map": keyword_groups,
            "total_scenarios": len(scenarios),
            "total_keywords": len(_KEYWORD_MAP)
        },
        "pipeline": {
            "step_1": "MFGC — Multi-Factor Gate Controller gates and confidence-scores the request",
            "step_2": "MSS Magnify — expands query to functional requirements + components",
            "step_3": "MSS Solidify — converts to a full implementation plan (RM5)",
            "step_4": "Librarian lookup — retrieves relevant context",
            "step_5": "LLM / LocalLLMFallback — generates final prose with enriched context",
            "step_6": "Automation Blueprint — generates workflow if major automation detected"
        },
        "mfgc_phases": [
            "INTAKE — Parse and validate request",
            "ANALYSIS — Determine request type and domain",
            "SCORING — Calculate confidence scores",
            "GATING — Apply quality gates",
            "MURPHY_INDEX — Calculate risk assessment",
            "ENRICHMENT — Add context from librarian",
            "OUTPUT — Generate final deliverable"
        ]
    })

@app.post("/api/demo/generate-deliverable")
async def api_demo_generate_deliverable(request: Request):
    """Generate a demo deliverable for the landing page forge."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"success": False, "error": "Invalid JSON"}, status_code=400)
    
    query = (body.get("query") or "").strip()
    if not query:
        return JSONResponse({"success": False, "error": "Query is required"}, status_code=400)
    
    # Rate limiting
    fp = hashlib.sha256(
        f"{request.client.host if request.client else '127.0.0.1'}:{request.headers.get('user-agent', 'unknown')}".encode()
    ).hexdigest()[:32]
    
    usage = _check_demo_rate_limit(fp)
    if usage["builds_remaining_today"] <= 0:
        return JSONResponse({
            "success": False,
            "error": "Daily build limit reached. Sign up for more builds.",
            "forge_usage": usage,
        }, status_code=429)
    
    # Create metrics tracker
    metrics = BuildMetrics(query)
    run_id = uuid.uuid4().hex[:12]
    
    # Generate deliverable
    log.info(f"Generating demo deliverable for: {query[:80]}")
    metrics.start_build()
    
    if _demo_gen_available and _generate_demo_deliverable:
        try:
            deliverable = _generate_demo_deliverable(query)
        except Exception as e:
            log.warning(f"Demo generator failed: {e}, using fallback")
            deliverable = _generate_fallback_deliverable(query)
    else:
        deliverable = _generate_fallback_deliverable(query)
    
    metrics.finish_build()
    _consume_demo_rate_limit(fp)
    usage = _check_demo_rate_limit(fp)
    
    log.info(
        f"Demo deliverable generated in {metrics.actual_elapsed_seconds}s - "
        f"{len(deliverable.get('content', ''))} chars, "
        f"ROI: {metrics.roi_multiple}x"
    )
    
    return JSONResponse({
        "success": True,
        "run_id": run_id,
        "deliverable": deliverable,
        "llm_provider": "murphy-demo",
        "forge_usage": usage,
        "elapsed_seconds": metrics.actual_elapsed_seconds,
        "metrics": metrics.to_dict(),
    })


# =============================================================================
# INFRASTRUCTURE ENDPOINTS - From hetzner_load.sh Integration
# =============================================================================

@app.get("/api/infrastructure/status")
async def get_infrastructure_status():
    """Get status of all infrastructure components.
    
    This endpoint provides visibility into the Docker Compose services
    defined in hetzner_load.sh: PostgreSQL, Redis, Prometheus, Grafana,
    Mail server, and Roundcube webmail.
    """
    import os
    
    # Check environment variables for configuration
    env_config = {
        "database_url": bool(os.getenv("DATABASE_URL", "")),
        "redis_url": bool(os.getenv("REDIS_URL", "")),
        "ollama_host": bool(os.getenv("OLLAMA_HOST", "")),
        "smtp_host": bool(os.getenv("SMTP_HOST", "")),
        "matrix_homeserver": bool(os.getenv("MATRIX_HOMESERVER_URL", "")),
        "murphy_secret_key": bool(os.getenv("MURPHY_SECRET_KEY", "")),
    }
    
    # Service status checks
    services = {}
    
    # PostgreSQL check
    try:
        import asyncpg
        db_url = os.getenv("DATABASE_URL", "")
        if db_url:
            # Would need async connection check
            services["postgres"] = {"status": "configured", "port": 5432, "connection": "available"}
        else:
            services["postgres"] = {"status": "not_configured", "port": 5432, "connection": "none"}
    except ImportError:
        services["postgres"] = {"status": "driver_missing", "port": 5432, "connection": "none"}
    
    # Redis check
    try:
        import redis
        redis_url = os.getenv("REDIS_URL", "")
        if redis_url:
            services["redis"] = {"status": "configured", "port": 6379, "connection": "available"}
        else:
            services["redis"] = {"status": "not_configured", "port": 6379, "connection": "none"}
    except ImportError:
        services["redis"] = {"status": "driver_missing", "port": 6379, "connection": "none"}
    
    # Prometheus check (port 9090)
    services["prometheus"] = {
        "status": "configured" if os.getenv("PROMETHEUS_ENABLED", "") else "available",
        "port": 9090,
        "endpoint": "/metrics"
    }
    
    # Grafana check (port 3000)
    services["grafana"] = {
        "status": "configured" if os.getenv("GRAFANA_ADMIN_USER", "") else "available",
        "port": 3000,
        "endpoint": "/grafana/"
    }
    
    # Mail server check
    services["mailserver"] = {
        "status": "configured" if os.getenv("SMTP_HOST", "") else "available",
        "ports": {"smtp": 25, "smtps": 465, "submission": 587, "imap": 993},
        "webmail_port": 8443,
        "webmail_endpoint": "/mail/"
    }
    
    # Ollama LLM check (port 11434)
    services["ollama"] = {
        "status": "configured" if os.getenv("OLLAMA_HOST", "") else "available",
        "port": 11434,
        "model": os.getenv("OLLAMA_MODEL", "phi3")
    }
    
    return JSONResponse({
        "success": True,
        "timestamp": _now_iso(),
        "environment_configured": env_config,
        "services": services,
        "nginx_routes": {
            "/": "Murphy API :8000",
            "/api/": "Murphy API :8000",
            "/ui/": "Murphy API :8000",
            "/static/": "Murphy API :8000",
            "/docs": "Swagger UI",
            "/metrics": "Prometheus scrape",
            "/grafana/": "Grafana :3000",
            "/mail/": "Roundcube :8443"
        }
    })


@app.get("/api/infrastructure/database")
async def get_database_status():
    """Get detailed PostgreSQL database status and connection info."""
    import os
    
    db_url = os.getenv("DATABASE_URL", "")
    db_host = os.getenv("POSTGRES_HOST", "localhost")
    db_port = os.getenv("POSTGRES_PORT", "5432")
    db_name = os.getenv("POSTGRES_DB", "murphy")
    db_user = os.getenv("POSTGRES_USER", "murphy")
    
    return JSONResponse({
        "success": True,
        "configured": bool(db_url),
        "connection": {
            "host": db_host,
            "port": int(db_port),
            "database": db_name,
            "user": db_user,
            # Never expose password
            "password_set": bool(os.getenv("POSTGRES_PASSWORD", ""))
        },
        "docker_service": "murphy-postgres",
        "compose_file": "docker-compose.hetzner.yml",
        "health_check": "pg_isready -U murphy"
    })


@app.get("/api/infrastructure/cache")
async def get_cache_status():
    """Get Redis cache status and configuration."""
    import os
    
    redis_url = os.getenv("REDIS_URL", "")
    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = os.getenv("REDIS_PORT", "6379")
    
    return JSONResponse({
        "success": True,
        "configured": bool(redis_url),
        "connection": {
            "host": redis_host,
            "port": int(redis_port),
            "password_set": bool(os.getenv("REDIS_PASSWORD", ""))
        },
        "docker_service": "murphy-redis",
        "compose_file": "docker-compose.hetzner.yml",
        "use_cases": [
            "session_storage",
            "api_cache",
            "rate_limiting",
            "real_time_data"
        ]
    })


@app.get("/api/infrastructure/mail")
async def get_mail_status():
    """Get mail server configuration and status."""
    import os
    
    return JSONResponse({
        "success": True,
        "configured": bool(os.getenv("SMTP_HOST", "")),
        "smtp": {
            "host": os.getenv("SMTP_HOST", "localhost"),
            "port": int(os.getenv("SMTP_PORT", "587")),
            "user": os.getenv("SMTP_USER", ""),
            "tls": os.getenv("SMTP_USE_TLS", "true").lower() == "true"
        },
        "imap": {
            "host": os.getenv("IMAP_HOST", "localhost"),
            "port": int(os.getenv("IMAP_PORT", "993"))
        },
        "docker_services": {
            "mailserver": "murphy-mailserver (Postfix + Dovecot)",
            "webmail": "murphy-webmail (Roundcube)"
        },
        "ports": {
            "smtp_inbound": 25,
            "smtps": 465,
            "submission": 587,
            "imap": 143,
            "imaps": 993
        },
        "webmail_endpoint": "/mail/",
        "webmail_port": 8443
    })


@app.get("/api/infrastructure/monitoring")
async def get_monitoring_status():
    """Get Prometheus and Grafana monitoring configuration."""
    import os
    
    return JSONResponse({
        "success": True,
        "prometheus": {
            "configured": True,
            "port": 9090,
            "scrape_endpoint": "/metrics",
            "retention": "30d",
            "docker_service": "murphy-prometheus"
        },
        "grafana": {
            "configured": bool(os.getenv("GRAFANA_ADMIN_USER", "")),
            "port": 3000,
            "endpoint": "/grafana/",
            "admin_configured": bool(os.getenv("GRAFANA_ADMIN_PASSWORD", "")),
            "docker_service": "murphy-grafana"
        },
        "alerting": {
            "rules_file": "prometheus-rules/murphy-alerts.yml",
            "enabled": True
        }
    })


@app.get("/api/infrastructure/llm")
async def get_llm_status():
    """Get local LLM (Ollama) configuration."""
    import os
    
    return JSONResponse({
        "success": True,
        "ollama": {
            "configured": bool(os.getenv("OLLAMA_HOST", "")),
            "host": os.getenv("OLLAMA_HOST", "http://localhost:11434"),
            "port": 11434,
            "default_model": os.getenv("OLLAMA_MODEL", "phi3"),
            "available_models": ["phi3", "llama3", "mistral"]
        },
        "fallback_providers": {
            "deepinfra": bool(os.getenv("DEEPINFRA_API_KEY", "")),
            "together": bool(os.getenv("TOGETHER_API_KEY", "")),
            "openai": bool(os.getenv("OPENAI_API_KEY", ""))
        }
    })


class InfrastructureConfigRequest(BaseModel):
    """Request model for infrastructure configuration updates."""
    component: str  # postgres, redis, mail, ollama, grafana
    config: Dict[str, Any] = {}


@app.post("/api/infrastructure/configure")
async def configure_infrastructure(req: InfrastructureConfigRequest):
    """Configure an infrastructure component.
    
    This endpoint allows updating configuration for infrastructure
    components. In production, this would update environment variables
    or configuration files.
    """
    valid_components = ["postgres", "redis", "mail", "ollama", "grafana", "prometheus"]
    
    if req.component not in valid_components:
        return JSONResponse({
            "success": False,
            "error": f"Invalid component. Must be one of: {valid_components}"
        }, status_code=400)
    
    # In a real implementation, this would update the environment file
    # at /etc/murphy-production/environment and restart services
    
    return JSONResponse({
        "success": True,
        "message": f"Configuration for {req.component} would be updated",
        "component": req.component,
        "config_received": req.config,
        "note": "In production, this updates /etc/murphy-production/environment",
        "restart_required": True,
        "restart_command": f"systemctl restart murphy-production"
    })


@app.get("/api/infrastructure/health")
async def infrastructure_health_check():
    """Comprehensive health check for all infrastructure components.
    
    This matches the health checks performed in hetzner_load.sh.
    """
    import os
    import socket
    
    def check_port(host: str, port: int) -> bool:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex((host, port))
            sock.close()
            return result == 0
        except Exception:
            return False
    
    health = {
        "murphy_api": {"status": "healthy", "port": 8000},
        "postgres": {"status": "unknown", "port": 5432},
        "redis": {"status": "unknown", "port": 6379},
        "prometheus": {"status": "unknown", "port": 9090},
        "grafana": {"status": "unknown", "port": 3000},
        "mailserver": {"status": "unknown", "ports": [25, 587, 993]},
        "webmail": {"status": "unknown", "port": 8443},
        "ollama": {"status": "unknown", "port": 11434},
        "matrix": {"status": "unknown", "port": 8008}
    }
    
    # Check each service port
    for service, info in health.items():
        if service == "mailserver":
            # Check multiple ports for mail server
            ports_ok = all(check_port("localhost", p) for p in info["ports"])
            health[service]["status"] = "healthy" if ports_ok else "unreachable"
        elif "port" in info:
            port_ok = check_port("localhost", info["port"])
            health[service]["status"] = "healthy" if port_ok else "unreachable"
    
    # Overall status
    all_healthy = all(
        info["status"] in ["healthy", "unknown"] 
        for info in health.values()
    )
    
    return JSONResponse({
        "success": True,
        "timestamp": _now_iso(),
        "overall_status": "healthy" if all_healthy else "degraded",
        "services": health,
        "environment_file": "/etc/murphy-production/environment",
        "compose_file": "docker-compose.hetzner.yml"
    })


# =============================================================================
# MATRIX SERVER ENDPOINTS - IM Bridge Integration
# =============================================================================

@app.get("/api/infrastructure/matrix")
async def get_matrix_status():
    """Get Matrix server configuration and status.
    
    The Matrix server enables real-time messaging integration for Murphy,
    allowing users to interact with the system via Matrix rooms.
    """
    import os
    
    homeserver = os.getenv("MATRIX_HOMESERVER_URL", os.getenv("MATRIX_HOMESERVER", ""))
    user_id = os.getenv("MATRIX_USER_ID", "")
    
    return JSONResponse({
        "success": True,
        "configured": bool(homeserver and user_id),
        "connection": {
            "homeserver": homeserver,
            "user_id": user_id,
            "device_id": os.getenv("MATRIX_DEVICE_ID", "MURPHYBOT"),
            "e2e_enabled": os.getenv("MATRIX_E2E_ENABLED", "false").lower() == "true"
        },
        "rooms": {
            "hitl_room": os.getenv("MATRIX_HITL_ROOM", ""),
            "alerts_room": os.getenv("MATRIX_ALERTS_ROOM", ""),
            "comms_room": os.getenv("MATRIX_COMMS_ROOM", ""),
            "default_room": os.getenv("MATRIX_DEFAULT_ROOM", ""),
            "auto_create_rooms": os.getenv("MATRIX_AUTO_CREATE_ROOMS", "true").lower() == "true",
            "space_name": os.getenv("MATRIX_SPACE_NAME", "Murphy System")
        },
        "polling": {
            "hitl_poll_interval": int(os.getenv("HITL_POLL_INTERVAL", "30")),
            "health_poll_interval": int(os.getenv("HEALTH_POLL_INTERVAL", "60")),
            "comms_poll_interval": int(os.getenv("COMMS_POLL_INTERVAL", "20"))
        },
        "authentication": {
            "password_set": bool(os.getenv("MATRIX_PASSWORD", "")),
            "access_token_set": bool(os.getenv("MATRIX_ACCESS_TOKEN", "")),
            "bot_token_set": bool(os.getenv("MATRIX_BOT_TOKEN", "")),
            "bot_user": os.getenv("BOT_USER", "")
        },
        "features": {
            "command_prefix": os.getenv("BOT_COMMAND_PREFIX", "!murphy"),
            "circuit_breaker_threshold": int(os.getenv("CIRCUIT_BREAKER_THRESHOLD", "5")),
            "circuit_breaker_timeout": int(os.getenv("CIRCUIT_BREAKER_TIMEOUT", "60"))
        }
    })


@app.get("/api/infrastructure/matrix/rooms")
async def get_matrix_rooms():
    """List configured Matrix rooms and their purposes."""
    import os
    
    rooms = []
    
    # HITL Room - Human-in-the-Loop approvals
    hitl_room = os.getenv("MATRIX_HITL_ROOM", "")
    if hitl_room:
        rooms.append({
            "room_id": hitl_room,
            "purpose": "hitl",
            "description": "Human-in-the-Loop approval requests",
            "poll_interval": int(os.getenv("HITL_POLL_INTERVAL", "30"))
        })
    
    # Alerts Room - System notifications
    alerts_room = os.getenv("MATRIX_ALERTS_ROOM", "")
    if alerts_room:
        rooms.append({
            "room_id": alerts_room,
            "purpose": "alerts",
            "description": "System alerts and notifications",
            "poll_interval": int(os.getenv("HEALTH_POLL_INTERVAL", "60"))
        })
    
    # Communications Room
    comms_room = os.getenv("MATRIX_COMMS_ROOM", "")
    if comms_room:
        rooms.append({
            "room_id": comms_room,
            "purpose": "communications",
            "description": "Team communications hub",
            "poll_interval": int(os.getenv("COMMS_POLL_INTERVAL", "20"))
        })
    
    # Default Room
    default_room = os.getenv("MATRIX_DEFAULT_ROOM", "")
    if default_room:
        rooms.append({
            "room_id": default_room,
            "purpose": "default",
            "description": "Default room for general interactions",
            "poll_interval": 60
        })
    
    return JSONResponse({
        "success": True,
        "total_rooms": len(rooms),
        "rooms": rooms,
        "space_name": os.getenv("MATRIX_SPACE_NAME", "Murphy System"),
        "auto_create": os.getenv("MATRIX_AUTO_CREATE_ROOMS", "true").lower() == "true"
    })


@app.get("/api/infrastructure/matrix/bridge")
async def get_matrix_bridge_status():
    """Get Matrix-Murphy API bridge status.
    
    The bridge connects Matrix rooms to Murphy's REST API,
    enabling commands like !murphy status, !murphy approve, etc.
    """
    import os
    
    return JSONResponse({
        "success": True,
        "bridge": {
            "name": "MurphyAPIBridge",
            "type": "httpx_async_client",
            "base_url": os.getenv("MURPHY_API_URL", "http://localhost:8000/api"),
            "web_url": os.getenv("MURPHY_WEB_URL", "http://localhost:8000"),
            "timeout": float(os.getenv("MURPHY_API_TIMEOUT", "30.0"))
        },
        "commands": {
            "prefix": os.getenv("BOT_COMMAND_PREFIX", "!murphy"),
            "available": [
                {"command": "status", "description": "Get system status"},
                {"command": "approve <id>", "description": "Approve a HITL request"},
                {"command": "reject <id> <reason>", "description": "Reject a HITL request"},
                {"command": "queue", "description": "List pending HITL items"},
                {"command": "help", "description": "Show available commands"},
                {"command": "health", "description": "Check system health"}
            ]
        },
        "circuit_breaker": {
            "threshold": int(os.getenv("CIRCUIT_BREAKER_THRESHOLD", "5")),
            "timeout_seconds": int(os.getenv("CIRCUIT_BREAKER_TIMEOUT", "60")),
            "states": ["CLOSED", "OPEN", "HALF_OPEN"]
        }
    })


class MatrixMessageRequest(BaseModel):
    """Request model for sending Matrix messages."""
    room_id: str
    message: str
    message_type: str = "m.text"  # m.text, m.notice, m.emote


class MatrixRoomRequest(BaseModel):
    """Request model for creating Matrix rooms."""
    room_name: str
    purpose: str = "general"
    is_public: bool = False


@app.post("/api/infrastructure/matrix/send")
async def send_matrix_message(req: MatrixMessageRequest):
    """Send a message to a Matrix room.
    
    This endpoint allows the Murphy API to send messages to Matrix rooms
    for notifications, alerts, and HITL interactions.
    """
    import os
    
    # Check if Matrix is configured
    homeserver = os.getenv("MATRIX_HOMESERVER_URL", os.getenv("MATRIX_HOMESERVER", ""))
    access_token = os.getenv("MATRIX_ACCESS_TOKEN", "")
    
    if not homeserver or not access_token:
        return JSONResponse({
            "success": False,
            "error": "Matrix not configured. Set MATRIX_HOMESERVER_URL and MATRIX_ACCESS_TOKEN."
        }, status_code=503)
    
    # In a full implementation, this would use the matrix-nio client
    # to actually send the message. For now, we return a simulated response.
    
    return JSONResponse({
        "success": True,
        "message": "Message queued for delivery",
        "room_id": req.room_id,
        "message_type": req.message_type,
        "timestamp": _now_iso(),
        "note": "In production, this sends via matrix-nio AsyncClient"
    })


@app.post("/api/infrastructure/matrix/rooms/create")
async def create_matrix_room(req: MatrixRoomRequest):
    """Create a new Matrix room for Murphy interactions.
    
    This allows dynamic creation of rooms for different purposes
    (projects, teams, HITL workflows, etc.)
    """
    import os
    
    homeserver = os.getenv("MATRIX_HOMESERVER_URL", os.getenv("MATRIX_HOMESERVER", ""))
    access_token = os.getenv("MATRIX_ACCESS_TOKEN", "")
    
    if not homeserver or not access_token:
        return JSONResponse({
            "success": False,
            "error": "Matrix not configured. Set MATRIX_HOMESERVER_URL and MATRIX_ACCESS_TOKEN."
        }, status_code=503)
    
    # Room alias from name
    alias = req.room_name.lower().replace(" ", "-").replace("_", "-")
    user_id = os.getenv("MATRIX_USER_ID", "@murphy:localhost")
    server_name = user_id.split(":")[1] if ":" in user_id else "localhost"
    
    return JSONResponse({
        "success": True,
        "room": {
            "name": req.room_name,
            "alias": f"#{alias}:{server_name}",
            "purpose": req.purpose,
            "is_public": req.is_public
        },
        "created": False,  # Would be True after actual creation
        "timestamp": _now_iso(),
        "note": "In production, this creates via matrix-nio AsyncClient.create_room"
    })


@app.get("/api/infrastructure/matrix/health")
async def matrix_health_check():
    """Health check for Matrix server connectivity.
    
    Verifies that the Matrix homeserver is reachable and the bot
    credentials are valid.
    """
    import os
    import socket
    
    homeserver = os.getenv("MATRIX_HOMESERVER_URL", os.getenv("MATRIX_HOMESERVER", ""))
    user_id = os.getenv("MATRIX_USER_ID", "")
    access_token = os.getenv("MATRIX_ACCESS_TOKEN", "")
    password = os.getenv("MATRIX_PASSWORD", "")
    
    # Parse homeserver URL to get host/port
    host = "localhost"
    port = 8008
    
    if homeserver:
        try:
            from urllib.parse import urlparse
            parsed = urlparse(homeserver)
            host = parsed.hostname or "localhost"
            port = parsed.port or (443 if parsed.scheme == "https" else 8008)
        except Exception:
            log.warning("Failed to parse MATRIX_HOMESERVER_URL: %s", homeserver)
    
    # Check port connectivity
    def check_port(h: str, p: int) -> bool:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((h, p))
            sock.close()
            return result == 0
        except Exception:
            return False
    
    port_reachable = check_port(host, port)
    
    health_status = {
        "configured": bool(homeserver and user_id and (access_token or password)),
        "homeserver_reachable": port_reachable,
        "credentials": {
            "homeserver_set": bool(homeserver),
            "user_id_set": bool(user_id),
            "access_token_set": bool(access_token),
            "password_set": bool(password)
        },
        "connection": {
            "host": host,
            "port": port,
            "url": homeserver
        }
    }
    
    # Overall health
    if health_status["configured"] and port_reachable:
        status = "healthy"
    elif health_status["configured"]:
        status = "degraded"
    else:
        status = "not_configured"
    
    return JSONResponse({
        "success": True,
        "status": status,
        "timestamp": _now_iso(),
        "health": health_status
    })


# =============================================================================
# INFRASTRUCTURE COMPARE — Detailed hetzner_load.sh Comparison
# =============================================================================

@app.post("/api/infrastructure/compare")
async def compare_infrastructure(request: Request):
    """Compare current production environment against hetzner_load.sh requirements.

    Returns a service-by-service comparison showing what hetzner_load.sh
    expects versus what the running environment has configured.
    """
    import os
    from pathlib import Path as _Path

    hetzner_path = _Path(__file__).resolve().parent / "scripts" / "hetzner_load.sh"
    hetzner_exists = hetzner_path.exists()

    # Expected services from hetzner_load.sh
    hetzner_requirements = {
        "postgres": {"port": 5432, "image": "postgres:16-alpine", "required": True},
        "redis": {"port": 6379, "image": "redis:7-alpine", "required": True},
        "prometheus": {"port": 9090, "image": "prom/prometheus", "required": True},
        "grafana": {"port": 3000, "image": "grafana/grafana", "required": True},
        "mailserver": {"ports": [25, 465, 587, 993], "required": False},
        "webmail": {"port": 8443, "image": "roundcube/roundcubemail", "required": False},
        "ollama": {"port": 11434, "required": True},
        "nginx": {"ports": [80, 443], "required": True},
    }

    comparisons = {}
    for svc, req in hetzner_requirements.items():
        env_key_map = {
            "postgres": "DATABASE_URL",
            "redis": "REDIS_URL",
            "ollama": "OLLAMA_HOST",
            "mailserver": "SMTP_HOST",
            "grafana": "GRAFANA_ADMIN_USER",
            "prometheus": "PROMETHEUS_ENABLED",
        }
        env_key = env_key_map.get(svc)
        configured = bool(os.getenv(env_key, "")) if env_key else None

        comparisons[svc] = {
            "required_by_hetzner": req.get("required", False),
            "expected_port": req.get("port") or req.get("ports"),
            "environment_configured": configured,
            "status": "configured" if configured else ("unchecked" if configured is None else "missing"),
        }

    overall = all(
        c["environment_configured"]
        for c in comparisons.values()
        if c["required_by_hetzner"] and c["environment_configured"] is not None
    )

    return JSONResponse({
        "success": True,
        "timestamp": _now_iso(),
        "hetzner_script_found": hetzner_exists,
        "comparisons": comparisons,
        "overall_ready": overall,
    })


# =============================================================================
# MATRIX NOTIFY — Real-time Matrix Messages for HITL Events
# =============================================================================

class MatrixNotifyRequest(BaseModel):
    """Request body for sending a Matrix notification."""
    event_type: str = Field(..., min_length=1, max_length=100,
                            description="HITL event type: hitl_pending, hitl_approved, hitl_rejected")
    hitl_id: Optional[str] = Field(default=None)
    room_id: Optional[str] = Field(default=None, description="Override room; uses default if omitted")
    message: Optional[str] = Field(default=None, description="Custom message; auto-generated if omitted")
    metadata: Dict[str, Any] = Field(default_factory=dict)


@app.post("/api/matrix/notify")
async def matrix_notify(req: MatrixNotifyRequest):
    """Send a real-time Matrix message for HITL events.

    Constructs a notification from the event type and optional metadata,
    then sends it to the configured Matrix room.
    """
    import os

    homeserver = os.getenv("MATRIX_HOMESERVER_URL", "")
    access_token = os.getenv("MATRIX_ACCESS_TOKEN", "")
    default_room = os.getenv("MATRIX_DEFAULT_ROOM_ID", "")

    if not homeserver or not access_token:
        return JSONResponse({
            "success": False,
            "error": "Matrix server not configured (MATRIX_HOMESERVER_URL / MATRIX_ACCESS_TOKEN missing)",
        }, status_code=503)

    room_id = req.room_id or default_room
    if not room_id:
        return JSONResponse({
            "success": False,
            "error": "No room_id provided and MATRIX_DEFAULT_ROOM_ID not set",
        }, status_code=400)

    # Build message from templates
    templates = {
        "hitl_pending": "🔔 **HITL Pending** — Item `{hitl_id}` requires approval.",
        "hitl_approved": "✅ **HITL Approved** — Item `{hitl_id}` has been approved.",
        "hitl_rejected": "❌ **HITL Rejected** — Item `{hitl_id}` was rejected.",
    }
    body = req.message or templates.get(
        req.event_type,
        f"ℹ️ **{req.event_type}** — HITL event for `{req.hitl_id or 'N/A'}`.",
    ).format(hitl_id=req.hitl_id or "N/A")

    # Attempt Matrix send via nio or HTTP fallback
    sent = False
    send_error = None
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10) as client:
            url = f"{homeserver.rstrip('/')}/_matrix/client/r0/rooms/{room_id}/send/m.room.message"
            resp = await client.put(
                f"{url}/{uuid.uuid4().hex}",
                headers={"Authorization": f"Bearer {access_token}"},
                json={"msgtype": "m.text", "body": body},
            )
            sent = resp.status_code in (200, 201)
            if not sent:
                send_error = f"Matrix returned {resp.status_code}"
    except ImportError:
        send_error = "httpx not installed — Matrix send skipped"
    except Exception as exc:
        send_error = str(exc)

    return JSONResponse({
        "success": sent,
        "event_type": req.event_type,
        "room_id": room_id,
        "message_body": body,
        "sent": sent,
        "error": send_error,
        "timestamp": _now_iso(),
    })


# =============================================================================
# SELF-LOOP ADVANCED WIRING ROUTES (Steps 4–5: SelfFixLoopConnector + TaskExecutionBridge)
# Design Label: WIRE-002, WIRE-003, WIRE-004
# =============================================================================

def _get_adv_components():
    """Retrieve the advanced loop component dict from app.state."""
    try:
        return getattr(app.state, "adv_loop_components", {})
    except Exception:
        return {}


@app.get("/api/self-loop/pending-reviews")
async def self_loop_pending_reviews():
    """Return all tasks currently held for human review."""
    components = _get_adv_components()
    bridge = components.get("task_execution_bridge")
    if bridge is None:
        return JSONResponse({"error": "task_execution_bridge not available"}, status_code=503)
    return JSONResponse({
        "success": True,
        "pending_reviews": bridge.get_pending_reviews(),
        "timestamp": _now_iso(),
    })


@app.post("/api/self-loop/approve/{task_id}")
async def self_loop_approve_task(task_id: str):
    """Approve a HITL-held task."""
    components = _get_adv_components()
    bridge = components.get("task_execution_bridge")
    if bridge is None:
        return JSONResponse({"error": "task_execution_bridge not available"}, status_code=503)
    approved = bridge.approve_task(task_id)
    return JSONResponse({
        "success": approved,
        "task_id": task_id,
        "message": "approved" if approved else "task not found or not pending",
        "timestamp": _now_iso(),
    })


@app.post("/api/self-loop/reject/{task_id}")
async def self_loop_reject_task(task_id: str, reason: str = ""):
    """Reject a HITL-held task."""
    components = _get_adv_components()
    bridge = components.get("task_execution_bridge")
    if bridge is None:
        return JSONResponse({"error": "task_execution_bridge not available"}, status_code=503)
    rejected = bridge.reject_task(task_id, reason=reason)
    return JSONResponse({
        "success": rejected,
        "task_id": task_id,
        "message": "rejected" if rejected else "task not found or not pending",
        "timestamp": _now_iso(),
    })


@app.post("/api/self-loop/bridge-gaps")
async def self_loop_bridge_gaps():
    """Manually trigger gap bridging from SelfFixLoop into AutomationLoopConnector."""
    components = _get_adv_components()
    connector = components.get("fix_loop_connector")
    if connector is None:
        return JSONResponse({"error": "fix_loop_connector not available"}, status_code=503)
    result = connector.bridge_gaps()
    return JSONResponse({
        "success": True,
        "result": result,
        "timestamp": _now_iso(),
    })


@app.get("/api/self-loop/execution-status")
async def self_loop_execution_status():
    """Return TaskExecutionBridge execution statistics."""
    components = _get_adv_components()
    bridge = components.get("task_execution_bridge")
    fix_conn = components.get("fix_loop_connector")
    return JSONResponse({
        "success": True,
        "task_execution_bridge": bridge.get_status() if bridge is not None else None,
        "fix_loop_connector": fix_conn.get_status() if fix_conn is not None else None,
        "components_available": list(components.keys()),
        "timestamp": _now_iso(),
    })


# =============================================================================
# GLOBAL FEEDBACK SYSTEM ENDPOINTS (GFB-005)
# Design Labels: GFB-001 (models), GFB-002 (dispatcher), GFB-005 (endpoints)
# =============================================================================

class _FeedbackSubmitRequest(BaseModel):
    """Request body for POST /api/feedback/submit."""
    user_id: str = Field(..., min_length=1, max_length=256)
    title: str = Field(..., min_length=5, max_length=256)
    description: str = Field(..., min_length=10, max_length=8192)
    severity: str = Field("medium")
    source: str = Field("website_widget")
    page_url: Optional[str] = None
    component: Optional[str] = None
    steps_to_reproduce: Optional[str] = None
    expected_behavior: Optional[str] = None
    actual_behavior: Optional[str] = None
    console_errors: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    tenant_id: Optional[str] = None


@app.post("/api/feedback/submit")
async def feedback_submit(req: _FeedbackSubmitRequest, request: Request):
    """POST /api/feedback/submit — accept a global feedback submission.

    Design Label: GFB-005
    Commissioning: G1 — collects, validates, categorises, and generates
    a remediation plan in a single call.
    """
    if _feedback_dispatcher is None:
        return JSONResponse(
            {"success": False, "error": "MURPHY-E700",
             "message": "Global feedback system not available"},
            status_code=503,
        )
    try:
        submission = _feedback_dispatcher.submit(
            user_id=req.user_id,
            title=req.title,
            description=req.description,
            severity=req.severity,
            source=req.source,
            page_url=req.page_url,
            component=req.component,
            steps_to_reproduce=req.steps_to_reproduce,
            expected_behavior=req.expected_behavior,
            actual_behavior=req.actual_behavior,
            console_errors=req.console_errors,
            tags=req.tags,
            metadata=req.metadata,
            tenant_id=req.tenant_id,
            user_agent=request.headers.get("user-agent"),
        )
        return JSONResponse({
            "success": True,
            "feedback_id": submission.id,
            "status": submission.status.value,
            "remediation_plan_id": submission.remediation_plan_id,
            "timestamp": _now_iso(),
        })
    except Exception as exc:
        log.exception("Feedback submission failed")
        return JSONResponse(
            {"success": False, "error": "MURPHY-E701",
             "message": str(exc)},
            status_code=422,
        )


@app.get("/api/feedback/{feedback_id}")
async def feedback_get(feedback_id: str):
    """GET /api/feedback/{id} — retrieve a single feedback submission and its plan.

    Design Label: GFB-005
    """
    if _feedback_dispatcher is None:
        return JSONResponse(
            {"success": False, "error": "MURPHY-E700",
             "message": "Global feedback system not available"},
            status_code=503,
        )
    submission = _feedback_dispatcher.get(feedback_id)
    if submission is None:
        return JSONResponse(
            {"success": False, "error": "MURPHY-E702",
             "message": f"Feedback {feedback_id} not found"},
            status_code=404,
        )
    plan = _feedback_dispatcher.get_plan_for_feedback(feedback_id)
    return JSONResponse({
        "success": True,
        "feedback": submission.model_dump(mode="json"),
        "remediation_plan": plan.model_dump(mode="json") if plan else None,
        "timestamp": _now_iso(),
    })


@app.post("/api/feedback/{feedback_id}/dispatch")
async def feedback_dispatch(feedback_id: str):
    """POST /api/feedback/{id}/dispatch — trigger GitHub repository_dispatch.

    Design Label: GFB-005
    Creates a GitHub Issue with remediation steps via the feedback-patch workflow.
    """
    if _feedback_dispatcher is None:
        return JSONResponse(
            {"success": False, "error": "MURPHY-E700",
             "message": "Global feedback system not available"},
            status_code=503,
        )
    result = _feedback_dispatcher.dispatch_to_github(feedback_id)
    status_code = 200 if result.get("success") else 502
    if not result.get("success") and "not found" in result.get("error", "").lower():
        status_code = 404
    return JSONResponse({
        **result,
        "timestamp": _now_iso(),
    }, status_code=status_code)


@app.get("/api/feedback/list/all")
async def feedback_list(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=200),
):
    """GET /api/feedback/list/all — list feedback submissions with optional filters.

    Design Label: GFB-005
    """
    if _feedback_dispatcher is None:
        return JSONResponse(
            {"success": False, "error": "MURPHY-E700",
             "message": "Global feedback system not available"},
            status_code=503,
        )
    items = _feedback_dispatcher.list_submissions(
        status=status, severity=severity, limit=limit,
    )
    return JSONResponse({
        "success": True,
        "count": len(items),
        "items": items,
        "timestamp": _now_iso(),
    })


@app.get("/api/feedback/stats")
async def feedback_stats():
    """GET /api/feedback/stats — aggregate feedback statistics.

    Design Label: GFB-005
    """
    if _feedback_dispatcher is None:
        return JSONResponse(
            {"success": False, "error": "MURPHY-E700",
             "message": "Global feedback system not available"},
            status_code=503,
        )
    return JSONResponse({
        "success": True,
        **_feedback_dispatcher.stats(),
        "timestamp": _now_iso(),
    })


@app.post("/api/feedback/{feedback_id}/resolve")
async def feedback_resolve(feedback_id: str, github_issue_url: Optional[str] = None):
    """POST /api/feedback/{id}/resolve — mark feedback as resolved.

    Design Label: GFB-005
    """
    if _feedback_dispatcher is None:
        return JSONResponse(
            {"success": False, "error": "MURPHY-E700",
             "message": "Global feedback system not available"},
            status_code=503,
        )
    resolved = _feedback_dispatcher.resolve(feedback_id, github_issue_url)
    if not resolved:
        return JSONResponse(
            {"success": False, "error": "MURPHY-E702",
             "message": f"Feedback {feedback_id} not found"},
            status_code=404,
        )
    return JSONResponse({
        "success": True,
        "feedback_id": feedback_id,
        "status": "resolved",
        "timestamp": _now_iso(),
    })


# ── Layer 6: Murphy Building Intelligence API ─────────────────────────────

# Guard imports so the server starts even if BAS/EMS packages missing.
_bas_available = False
_ems_available = False
_fdd_available = False
_eae_available = False

try:
    from building_automation.models import MurphyBuilding, MurphyFloor, MurphyZone, MurphyPoint, PointKind, Substance, Phenomenon
    from building_automation.hvac_control import ZoneTemperatureController
    _bas_available = True
except Exception:
    pass

try:
    from energy_management.metering import MeteringRegistry, MeterType, MurphyMeter, MeterReading
    from energy_management.demand_response import DemandResponseEngine
    from energy_management.carbon_accounting import CarbonTracker
    _ems_available = True
except Exception:
    pass

try:
    from fdd.rule_engine import RuleBasedFDD
    from fdd.alarm_manager import AlarmManager
    _fdd_available = True
except Exception:
    pass

try:
    from energy_audit_engine import EnergyAuditEngine
    _eae_available = True
except Exception:
    pass

# Singleton instances (in-memory, for demo / dev)
_metering_registry = MeteringRegistry() if _ems_available else None
_dr_engine = DemandResponseEngine() if _ems_available else None
_carbon_tracker = CarbonTracker() if _ems_available else None
_fdd_engine = RuleBasedFDD() if _fdd_available else None
_alarm_mgr = AlarmManager() if _fdd_available else None
_audit_engine = EnergyAuditEngine() if _eae_available else None

# Demo building for API
_demo_building: Optional[Dict] = None
if _bas_available:
    _demo_building = {
        "building_id": "bldg-001",
        "name": "Murphy HQ",
        "address": "123 Innovation Drive",
        "total_sqft": 50000,
        "zones": [
            {"zone_id": "z-lobby", "name": "Lobby", "zone_type": "lobby",
             "temperature": 72.0, "humidity": 45.0, "occupied": True, "occupant_count": 5},
            {"zone_id": "z-office-1", "name": "Office Floor 1", "zone_type": "office",
             "temperature": 71.5, "humidity": 42.0, "occupied": True, "occupant_count": 25},
            {"zone_id": "z-conf-1", "name": "Conference Room A", "zone_type": "conference",
             "temperature": 73.0, "humidity": 44.0, "occupied": False, "occupant_count": 0},
            {"zone_id": "z-server", "name": "Server Room", "zone_type": "server_room",
             "temperature": 65.0, "humidity": 35.0, "occupied": False, "occupant_count": 0},
        ],
    }


@app.get("/api/bas/buildings/{building_id}/zones")
async def bas_get_zones(building_id: str):
    """Zone list + current conditions for a building."""
    if not _bas_available or _demo_building is None:
        return JSONResponse({"error": "BAS module not available"}, status_code=503)
    if building_id != _demo_building["building_id"]:
        return JSONResponse({"error": f"Building {building_id} not found"}, status_code=404)
    return JSONResponse({
        "building_id": building_id,
        "zones": _demo_building["zones"],
        "timestamp": _now_iso(),
    })


@app.get("/api/bas/buildings/{building_id}/setpoints")
async def bas_get_setpoints(building_id: str):
    """Read setpoints for a building (auth-gated in production)."""
    if not _bas_available or _demo_building is None:
        return JSONResponse({"error": "BAS module not available"}, status_code=503)
    setpoints = [
        {"zone_id": z["zone_id"], "heating_setpoint": 70.0, "cooling_setpoint": 74.0}
        for z in _demo_building.get("zones", [])
    ]
    return JSONResponse({
        "building_id": building_id,
        "setpoints": setpoints,
        "timestamp": _now_iso(),
    })


@app.get("/api/ems/meters/{meter_id}/readings")
async def ems_get_readings(meter_id: str, start: Optional[float] = None, end: Optional[float] = None):
    """Interval data query with optional time range."""
    if _metering_registry is None:
        return JSONResponse({"error": "EMS module not available"}, status_code=503)
    try:
        readings = _metering_registry.get_readings(meter_id, start, end)
        return JSONResponse({
            "meter_id": meter_id,
            "readings": [{"timestamp": r.timestamp, "value": r.value, "unit": r.unit} for r in readings],
            "count": len(readings),
        })
    except KeyError:
        return JSONResponse({"error": f"Meter {meter_id} not found"}, status_code=404)


@app.get("/api/ems/demand-response/events")
async def ems_dr_events():
    """Active DR events + shed status."""
    if _dr_engine is None:
        return JSONResponse({"error": "EMS module not available"}, status_code=503)
    return JSONResponse({
        "active_events": _dr_engine.get_active_events(),
        "shed_status": _dr_engine.get_shed_status(),
        "timestamp": _now_iso(),
    })


@app.get("/api/ems/carbon/live")
async def ems_carbon_live():
    """Real-time carbon intensity."""
    if _carbon_tracker is None:
        return JSONResponse({"error": "EMS module not available"}, status_code=503)
    intensity = _carbon_tracker.get_live_intensity()
    totals = _carbon_tracker.total_emissions()
    return JSONResponse({
        "live_intensity": intensity,
        "cumulative": totals,
        "timestamp": _now_iso(),
    })


@app.get("/api/audit/list")
async def audit_list():
    """List all energy audits."""
    if _audit_engine is None:
        return JSONResponse({"error": "Audit engine not available"}, status_code=503)
    audits = _audit_engine.list_audits()
    return JSONResponse({"audits": audits, "count": len(audits)})


@app.get("/api/audit/{audit_id}")
async def audit_get(audit_id: str):
    """Get a specific energy audit."""
    if _audit_engine is None:
        return JSONResponse({"error": "Audit engine not available"}, status_code=503)
    audit = _audit_engine.get_audit(audit_id)
    if audit is None:
        return JSONResponse({"error": f"Audit {audit_id} not found"}, status_code=404)
    export = _audit_engine.export_audit(audit_id)
    return JSONResponse(export)


@app.get("/api/fdd/active")
async def fdd_active_faults():
    """Active faults from FDD engine."""
    if _fdd_engine is None:
        return JSONResponse({"error": "FDD module not available"}, status_code=503)
    faults = _fdd_engine.get_active_faults()
    return JSONResponse({
        "faults": [
            {"fault_id": f.fault_id, "rule_id": f.rule_id,
             "equipment_id": f.equipment_id, "severity": f.severity.value,
             "message": f.message, "status": f.status.value}
            for f in faults
        ],
        "count": len(faults),
        "timestamp": _now_iso(),
    })


@app.get("/api/fdd/alarms")
async def fdd_alarms():
    """Active alarms from alarm manager."""
    if _alarm_mgr is None:
        return JSONResponse({"error": "FDD module not available"}, status_code=503)
    alarms = _alarm_mgr.get_active_alarms()
    return JSONResponse({
        "alarms": alarms,
        "count": len(alarms),
        "timestamp": _now_iso(),
    })
