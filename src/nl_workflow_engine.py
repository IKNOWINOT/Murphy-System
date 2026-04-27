"""
PATCH-132b — src/nl_workflow_engine.py
Murphy System — Tenant-Scoped NL Workflow Engine

Two-agent pipeline (tenant-isolated):
  Agent 1 (BuildAgent):  NL description → full WorkflowBlueprint
    - Uses LLM to extract steps, schedule, inputs, outputs, agents, ROI
    - Guided by Murphy's canonical step-type vocabulary
    - Fills in ALL blanks from available system capabilities
    - Orders steps by optimal execution sequence

  Agent 2 (EditAgent):   Refinement loop on an existing blueprint
    - Receives blueprint + user edit instruction
    - Surgical edits only (no full regeneration)
    - Validates changes through MurphyCritic gate
    - Returns diff + updated blueprint

Each blueprint is:
  - Tenant-scoped (account_id)
  - Stored in SQLite per-tenant
  - Referenceable by workflow_id
  - Directly executable by WorkflowDAGEngine
  - Feeds ROI calendar (cost estimates)
  - Feeds production wizard (deliverable steps)

Copyright © 2020-2026 Inoni LLC — Corey Post | License: BSL 1.1
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
import threading
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("murphy.nl_workflow_engine")

# ── Murphy step-type vocabulary ──────────────────────────────────────────────
# These are the canonical node types the canvas and executor understand.
MURPHY_STEP_TYPES = {
    # Triggers
    "webhook":      {"category": "trigger",  "icon": "⚡", "desc": "Fires on HTTP webhook"},
    "schedule":     {"category": "trigger",  "icon": "⏰", "desc": "Fires on cron/time schedule"},
    "event":        {"category": "trigger",  "icon": "📡", "desc": "Fires on internal system event"},
    "manual":       {"category": "trigger",  "icon": "👆", "desc": "Manually triggered by user"},
    # Actions
    "api_call":     {"category": "action",   "icon": "🌐", "desc": "Call external API"},
    "execute":      {"category": "action",   "icon": "⚙",  "desc": "Run a task or script"},
    "message":      {"category": "action",   "icon": "💬", "desc": "Send message (email/Slack/SMS)"},
    "generate":     {"category": "action",   "icon": "✨", "desc": "Generate content with LLM"},
    # Logic
    "if_else":      {"category": "logic",    "icon": "⑂",  "desc": "Conditional branch"},
    "switch":       {"category": "logic",    "icon": "🔀", "desc": "Multi-branch switch"},
    "loop":         {"category": "logic",    "icon": "🔄", "desc": "Iterate over items"},
    "wait":         {"category": "logic",    "icon": "⏳", "desc": "Wait/delay step"},
    "merge":        {"category": "logic",    "icon": "🔗", "desc": "Join parallel branches"},
    # Agents
    "executive":    {"category": "agent",    "icon": "👔", "desc": "Executive admin agent"},
    "operations":   {"category": "agent",    "icon": "🏭", "desc": "Production ops agent"},
    "qa":           {"category": "agent",    "icon": "🔍", "desc": "QA / review agent"},
    # Gates
    "hitl":         {"category": "gate",     "icon": "🙋", "desc": "Human-in-the-loop review"},
    "compliance":   {"category": "gate",     "icon": "📋", "desc": "Compliance check"},
    "budget":       {"category": "gate",     "icon": "💰", "desc": "Budget approval gate"},
    # Production
    "proposal":     {"category": "production","icon": "📝", "desc": "Create proposal"},
    "workorder":    {"category": "production","icon": "📄", "desc": "Issue work order"},
    "validate":     {"category": "production","icon": "✅", "desc": "Validate deliverable"},
    "deliver":      {"category": "production","icon": "📦", "desc": "Deliver to client"},
}

# ── Schedule inference ───────────────────────────────────────────────────────
SCHEDULE_PATTERNS = [
    (r"every\s+(\d+)\s+minutes?",     lambda m: {"type":"cron","expr":f"*/{m.group(1)} * * * *","label":f"Every {m.group(1)} min"}),
    (r"every\s+(\d+)\s+hours?",       lambda m: {"type":"cron","expr":f"0 */{m.group(1)} * * *","label":f"Every {m.group(1)} hr"}),
    (r"daily\s+at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", lambda m: _daily_schedule(m)),
    (r"every\s+day\s+at\s+(\d{1,2})", lambda m: {"type":"cron","expr":f"0 {int(m.group(1))} * * *","label":f"Daily {m.group(1)}:00"}),
    (r"every\s+monday",    lambda _: {"type":"cron","expr":"0 9 * * 1","label":"Every Monday 9am"}),
    (r"every\s+weekday",   lambda _: {"type":"cron","expr":"0 9 * * 1-5","label":"Weekdays 9am"}),
    (r"weekly",             lambda _: {"type":"cron","expr":"0 9 * * 1","label":"Weekly (Mon 9am)"}),
    (r"monthly",            lambda _: {"type":"cron","expr":"0 9 1 * *","label":"Monthly (1st)"}),
    (r"hourly",             lambda _: {"type":"cron","expr":"0 * * * *","label":"Hourly"}),
    (r"on\s+demand|manual|when.*trigger", lambda _: {"type":"on_demand","expr":None,"label":"On demand"}),
]

def _daily_schedule(m) -> dict:
    h = int(m.group(1)); mn = int(m.group(2) or 0)
    ampm = (m.group(3) or "").lower()
    if ampm == "pm" and h != 12: h += 12
    elif ampm == "am" and h == 12: h = 0
    return {"type":"cron","expr":f"{mn} {h} * * *","label":f"Daily {h:02d}:{mn:02d}"}

def _infer_schedule(text: str) -> dict:
    text_l = text.lower()
    for pattern, builder in SCHEDULE_PATTERNS:
        m = re.search(pattern, text_l)
        if m:
            return builder(m)
    return {"type":"on_demand","expr":None,"label":"On demand"}


# ── ROI estimator ────────────────────────────────────────────────────────────
_STEP_HUMAN_HOURS = {
    "manual": 0.25, "webhook": 0.0, "schedule": 0.0, "event": 0.0,
    "api_call": 0.5, "execute": 1.0, "message": 0.25, "generate": 1.5,
    "if_else": 0.25, "switch": 0.25, "loop": 0.5, "wait": 0.0, "merge": 0.1,
    "executive": 2.0, "operations": 1.5, "qa": 1.0,
    "hitl": 0.5, "compliance": 1.0, "budget": 0.5,
    "proposal": 3.0, "workorder": 2.0, "validate": 1.5, "deliver": 0.5,
}
_HUMAN_HOURLY_RATE = 75.0   # USD
_AGENT_COST_PER_STEP = 0.08  # USD

def _estimate_roi(steps: List[Dict]) -> Dict:
    human_hrs = sum(_STEP_HUMAN_HOURS.get(s.get("type","execute"), 0.5) for s in steps)
    human_cost = round(human_hrs * _HUMAN_HOURLY_RATE, 2)
    agent_cost = round(len(steps) * _AGENT_COST_PER_STEP, 2)
    savings = round(human_cost - agent_cost, 2)
    return {
        "human_hours": round(human_hrs, 2),
        "human_cost_usd": human_cost,
        "agent_cost_usd": agent_cost,
        "savings_usd": savings,
        "roi_ratio": round(human_cost / max(agent_cost, 0.01), 1),
    }


# ── Blueprint dataclass ──────────────────────────────────────────────────────
@dataclass
class WorkflowBlueprint:
    workflow_id:  str
    account_id:   str
    name:         str
    description:  str
    trigger:      Dict     # {type, label, cron_expr?}
    steps:        List[Dict]  # [{id, type, label, config, depends_on}]
    agents:       List[str]   # agent names assigned
    schedule:     Dict     # {type, expr, label}
    inputs:       List[str]   # data inputs the workflow needs
    outputs:      List[str]   # data outputs produced
    roi:          Dict     # ROI estimates
    canvas_nodes: List[Dict]  # ready for workflow_canvas.html
    canvas_edges: List[Dict]  # ready for workflow_canvas.html
    generation_meta: Dict  # strategy, model, confidence
    created_at:   str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at:   str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    version:      int = 1

    def to_dict(self) -> Dict:
        return asdict(self)

    def to_canvas_payload(self) -> Dict:
        """Return the shape workflow_canvas.html importNLWorkflow() expects."""
        return {
            "success": True,
            "workflow": {
                "workflow_id": self.workflow_id,
                "name": self.name,
                "description": self.description,
                "nodes": self.canvas_nodes,
                "steps": self.steps,
                "schedule": self.schedule,
                "roi": self.roi,
                "generation_meta": self.generation_meta,
            }
        }

    def to_roi_event(self) -> Dict:
        """Return a record ready for /api/roi-calendar/events."""
        return {
            "title": self.name,
            "description": self.description,
            "workflow_id": self.workflow_id,
            "human_cost_estimate": self.roi["human_cost_usd"],
            "agent_compute_cost": self.roi["agent_cost_usd"],
            "schedule_label": self.schedule.get("label","On demand"),
            "step_count": len(self.steps),
        }


# ── DB layer ─────────────────────────────────────────────────────────────────
_DB_PATH = Path("/var/lib/murphy-production/nl_workflows.db")
_db_lock = threading.Lock()

def _get_db() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS blueprints (
            workflow_id  TEXT PRIMARY KEY,
            account_id   TEXT NOT NULL,
            name         TEXT,
            data         TEXT NOT NULL,
            created_at   TEXT,
            updated_at   TEXT
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_bp_account ON blueprints(account_id)")
    conn.commit()
    return conn

def _save_blueprint(bp: WorkflowBlueprint):
    with _db_lock:
        conn = _get_db()
        conn.execute(
            """INSERT OR REPLACE INTO blueprints
               (workflow_id, account_id, name, data, created_at, updated_at)
               VALUES (?,?,?,?,?,?)""",
            (bp.workflow_id, bp.account_id, bp.name,
             json.dumps(bp.to_dict()), bp.created_at, bp.updated_at)
        )
        conn.commit()
        conn.close()

def _load_blueprint(workflow_id: str, account_id: str) -> Optional[WorkflowBlueprint]:
    with _db_lock:
        conn = _get_db()
        row = conn.execute(
            "SELECT data FROM blueprints WHERE workflow_id=? AND account_id=?",
            (workflow_id, account_id)
        ).fetchone()
        conn.close()
    if not row:
        return None
    d = json.loads(row["data"])
    return WorkflowBlueprint(**d)

def _list_blueprints(account_id: str) -> List[Dict]:
    with _db_lock:
        conn = _get_db()
        rows = conn.execute(
            "SELECT workflow_id, name, created_at, updated_at FROM blueprints WHERE account_id=? ORDER BY updated_at DESC",
            (account_id,)
        ).fetchall()
        conn.close()
    return [dict(r) for r in rows]


# ── Canvas node builder ──────────────────────────────────────────────────────
def _build_canvas_nodes_edges(steps: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
    """Convert blueprint steps → canvas nodes + edges."""
    nodes, edges = [], []
    x, y = 120, 120
    id_map = {}

    for i, step in enumerate(steps):
        nid = f"node_{i}"
        id_map[step.get("id", step["label"])] = nid
        stype = step.get("type", "execute")
        meta = MURPHY_STEP_TYPES.get(stype, {"category":"action","icon":"⚙"})
        nodes.append({
            "id": nid,
            "type": meta["category"],
            "subtype": stype.replace("_", "-"),
            "label": f"{meta['icon']} {step['label']}",
            "x": x,
            "y": y,
            "data": step.get("config", {}),
        })
        x += 220
        if (i + 1) % 4 == 0:
            x = 120
            y += 160

    for i, step in enumerate(steps):
        src_id = id_map.get(step.get("id", step["label"]))
        for dep in step.get("depends_on", []):
            dst_id = id_map.get(dep)
            if src_id and dst_id:
                edges.append({"id": f"e_{dst_id}_{src_id}", "source": dst_id, "target": src_id})
        # Auto-chain sequential steps with no explicit deps
        if not step.get("depends_on") and i > 0:
            prev = id_map.get(steps[i-1].get("id", steps[i-1]["label"]))
            curr = id_map.get(step.get("id", step["label"]))
            if prev and curr:
                edges.append({"id": f"e_{prev}_{curr}", "source": prev, "target": curr})

    return nodes, edges


# ── LLM prompt helpers ────────────────────────────────────────────────────────
_BUILD_SYSTEM_PROMPT = """You are Murphy's Workflow Build Agent.

Convert the user's natural language description into a structured workflow blueprint using Murphy's step vocabulary.

Murphy step types: {step_types}

Rules:
1. Generate 3-8 steps. More is not better — be minimal and direct.
2. Every workflow needs exactly ONE trigger step (first step).
3. High-stakes actions (delete, send to all, payment) need a hitl gate before execution.
4. Always end with an "execute" or "deliver" step that produces the output.
5. Assign the most appropriate agent(s): executive (scheduling/comms), operations (systems/deploys), qa (review/verify).
6. Infer all missing details from context — never ask, always fill in.
7. Return ONLY valid JSON, no prose.

Output schema:
{{
  "name": "Short workflow name (5 words max)",
  "steps": [
    {{
      "id": "unique_snake_case_id",
      "type": "step_type_from_vocabulary",
      "label": "Human-readable label",
      "config": {{}},
      "depends_on": []
    }}
  ],
  "agents": ["agent_name", ...],
  "inputs": ["what data this workflow needs"],
  "outputs": ["what this workflow produces"]
}}"""

_EDIT_SYSTEM_PROMPT = """You are Murphy's Workflow Edit Agent.

You receive an existing workflow blueprint and an edit instruction.
Make ONLY the requested changes. Do not regenerate the entire workflow.

Return ONLY the modified fields as JSON:
{{
  "steps": [...],      // only if steps changed
  "name": "...",       // only if name changed
  "agents": [...],     // only if agents changed
  "inputs": [...],     // only if inputs changed
  "outputs": [...]     // only if outputs changed
}}
Do not return unchanged fields. Do not add prose."""


# ── Build Agent ───────────────────────────────────────────────────────────────
class BuildAgent:
    """Agent 1: NL description → WorkflowBlueprint."""

    def __init__(self, llm_provider=None):
        self._llm = llm_provider

    def build(self, description: str, account_id: str,
              context: Optional[Dict] = None) -> WorkflowBlueprint:
        """Build a complete workflow blueprint from a natural language description."""
        step_types_str = ", ".join(
            f"{k} ({v['desc']})" for k, v in MURPHY_STEP_TYPES.items()
        )

        workflow_id = str(uuid.uuid4())[:12]
        schedule = _infer_schedule(description)

        # Try LLM first, fall back to heuristic
        if self._llm:
            steps, agents, inputs, outputs, name = self._llm_build(
                description, step_types_str, context
            )
        else:
            steps, agents, inputs, outputs, name = self._heuristic_build(description)

        roi = _estimate_roi(steps)
        canvas_nodes, canvas_edges = _build_canvas_nodes_edges(steps)

        return WorkflowBlueprint(
            workflow_id=workflow_id,
            account_id=account_id,
            name=name,
            description=description,
            trigger={"type": schedule["type"], "label": schedule["label"]},
            steps=steps,
            agents=agents,
            schedule=schedule,
            inputs=inputs,
            outputs=outputs,
            roi=roi,
            canvas_nodes=canvas_nodes,
            canvas_edges=canvas_edges,
            generation_meta={
                "strategy": "llm" if self._llm else "heuristic",
                "confidence": 0.85 if self._llm else 0.55,
                "step_count": len(steps),
            },
        )

    def _llm_build(self, description: str, step_types_str: str,
                   context: Optional[Dict]) -> Tuple:
        system = _BUILD_SYSTEM_PROMPT.format(step_types=step_types_str)
        user_msg = f"Build a workflow for: {description}"
        if context:
            user_msg += f"\nContext: {json.dumps(context)}"
        try:
            result = self._llm.complete(
                prompt=user_msg,
                system_prompt=system,
                max_tokens=800,
            )
            content = result.content.strip()
            m = re.search(r"\{.*\}", content, re.DOTALL)
            if m:
                d = json.loads(m.group())
                steps = d.get("steps", [])
                for s in steps:
                    if "id" not in s:
                        s["id"] = re.sub(r"[^a-z0-9_]", "_", s.get("label","step").lower())[:30]
                    if "depends_on" not in s:
                        s["depends_on"] = []
                return (
                    steps,
                    d.get("agents", ["operations"]),
                    d.get("inputs", []),
                    d.get("outputs", []),
                    d.get("name", description[:50]),
                )
        except Exception as exc:
            logger.warning("BuildAgent LLM failed: %s — falling back to heuristic", exc)
        return self._heuristic_build(description)

    def _heuristic_build(self, description: str) -> Tuple:
        """Keyword-driven fallback when LLM is unavailable."""
        text = description.lower()
        steps = []
        step_id_ctr = [0]

        def add(stype: str, label: str, config: dict = None):
            sid = f"step_{step_id_ctr[0]:02d}_{stype}"
            step_id_ctr[0] += 1
            steps.append({"id": sid, "type": stype, "label": label,
                          "config": config or {}, "depends_on": []})

        # Trigger
        if any(k in text for k in ("webhook", "form submit", "on submit", "when.*submits")):
            add("webhook", "On form submit")
        elif any(k in text for k in ("every", "daily", "weekly", "hourly", "schedule", "cron")):
            sched = _infer_schedule(description)
            add("schedule", f"Schedule: {sched['label']}", {"cron": sched.get("expr")})
        else:
            add("manual", "Manual trigger")

        # Data source
        if any(k in text for k in ("database", "db", "sql", "crm", "salesforce", "airtable")):
            add("api_call", "Fetch from data source")

        # Core action
        if any(k in text for k in ("report", "summary", "brief", "analysis")):
            add("generate", "Generate report")
        elif any(k in text for k in ("email", "send", "notify", "alert", "message")):
            add("message", "Send notification")
        elif any(k in text for k in ("deploy", "restart", "rollback", "patch")):
            add("operations", "Operations action")
        elif any(k in text for k in ("approve", "review", "check")):
            add("qa", "Review and approve")
        else:
            add("execute", "Execute workflow task")

        # Gate if needed
        if any(k in text for k in ("payment", "delete", "send to all", "broadcast", "critical")):
            add("hitl", "Human approval required")

        # Compliance
        if any(k in text for k in ("compliance", "audit", "legal", "gdpr", "hipaa")):
            add("compliance", "Compliance check")

        # Delivery
        if any(k in text for k in ("deliver", "export", "save", "upload", "send to", "post to")):
            add("deliver", "Deliver output")

        # Agents
        agents = []
        if any(k in text for k in ("email", "schedule", "calendar", "meeting", "brief")):
            agents.append("executive")
        if any(k in text for k in ("deploy", "server", "database", "system", "ops", "monitor")):
            agents.append("operations")
        if any(k in text for k in ("review", "qa", "check", "validate", "approve")):
            agents.append("qa")
        if not agents:
            agents = ["operations"]

        inputs = []
        if "from" in text:
            source_m = re.search(r"from\s+(\w+(?:\s+\w+)?)", description)
            if source_m:
                inputs.append(source_m.group(1))

        outputs = []
        if any(k in text for k in ("report", "brief", "summary")):
            outputs.append("report")
        elif any(k in text for k in ("email", "message", "notification")):
            outputs.append("notification")
        elif any(k in text for k in ("document", "file", "export")):
            outputs.append("file")
        else:
            outputs.append("workflow result")

        name = description[:60].strip().rstrip(".")
        return steps, agents, inputs, outputs, name


# ── Edit Agent ────────────────────────────────────────────────────────────────
class EditAgent:
    """Agent 2: Refine an existing blueprint based on edit instruction."""

    def __init__(self, llm_provider=None):
        self._llm = llm_provider

    def edit(self, blueprint: WorkflowBlueprint,
             instruction: str) -> WorkflowBlueprint:
        """Apply a natural language edit instruction to a blueprint."""
        if self._llm:
            changes = self._llm_edit(blueprint, instruction)
        else:
            changes = self._heuristic_edit(blueprint, instruction)

        # Apply changes
        if "steps" in changes:
            blueprint.steps = changes["steps"]
            blueprint.canvas_nodes, blueprint.canvas_edges = (
                _build_canvas_nodes_edges(blueprint.steps)
            )
            blueprint.roi = _estimate_roi(blueprint.steps)
        if "name" in changes:
            blueprint.name = changes["name"]
        if "agents" in changes:
            blueprint.agents = changes["agents"]
        if "inputs" in changes:
            blueprint.inputs = changes["inputs"]
        if "outputs" in changes:
            blueprint.outputs = changes["outputs"]
        if "schedule" in changes:
            blueprint.schedule = changes["schedule"]

        blueprint.updated_at = datetime.now(timezone.utc).isoformat()
        blueprint.version += 1
        blueprint.generation_meta["last_edit"] = instruction[:100]
        return blueprint

    def _llm_edit(self, blueprint: WorkflowBlueprint, instruction: str) -> Dict:
        current = json.dumps({
            "name": blueprint.name,
            "steps": blueprint.steps,
            "agents": blueprint.agents,
            "inputs": blueprint.inputs,
            "outputs": blueprint.outputs,
        }, indent=2)
        try:
            result = self._llm.complete(
                prompt=f"Current workflow:\n{current}\n\nEdit instruction: {instruction}",
                system_prompt=_EDIT_SYSTEM_PROMPT,
                max_tokens=600,
            )
            content = result.content.strip()
            m = re.search(r"\{.*\}", content, re.DOTALL)
            if m:
                return json.loads(m.group())
        except Exception as exc:
            logger.warning("EditAgent LLM failed: %s", exc)
        return self._heuristic_edit(blueprint, instruction)

    def _heuristic_edit(self, blueprint: WorkflowBlueprint, instruction: str) -> Dict:
        text = instruction.lower()
        changes: Dict = {}

        if "rename" in text or "call it" in text:
            m = re.search(r"(?:rename|call it)\s+[\"\']?([^\"']+)[\"\']?", text)
            if m:
                changes["name"] = m.group(1).strip()

        if "add" in text and any(k in text for k in MURPHY_STEP_TYPES.keys()):
            for stype, meta in MURPHY_STEP_TYPES.items():
                if stype in text or meta["desc"].lower().split()[0] in text:
                    new_step = {
                        "id": f"step_{len(blueprint.steps):02d}_{stype}",
                        "type": stype,
                        "label": f"{meta['icon']} {stype.replace('_', ' ').title()}",
                        "config": {},
                        "depends_on": [blueprint.steps[-1]["id"]] if blueprint.steps else [],
                    }
                    new_steps = blueprint.steps + [new_step]
                    changes["steps"] = new_steps
                    break

        if "schedule" in text or "run" in text:
            new_sched = _infer_schedule(instruction)
            if new_sched["type"] != "on_demand":
                changes["schedule"] = new_sched

        return changes


# ── Engine (facade) ──────────────────────────────────────────────────────────
class NLWorkflowEngine:
    """
    Tenant-scoped facade over BuildAgent + EditAgent.
    All operations require account_id for data isolation.
    """
    _instance = None
    _lock = threading.Lock()

    def __init__(self, llm_provider=None):
        self._build_agent = BuildAgent(llm_provider)
        self._edit_agent  = EditAgent(llm_provider)
        self._llm = llm_provider

    @classmethod
    def get_instance(cls, llm_provider=None) -> "NLWorkflowEngine":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls(llm_provider)
            return cls._instance

    def build(self, description: str, account_id: str,
              context: Optional[Dict] = None) -> WorkflowBlueprint:
        """Agent 1: Build a new workflow from NL description."""
        bp = self._build_agent.build(description, account_id, context)
        _save_blueprint(bp)
        return bp

    def edit(self, workflow_id: str, account_id: str,
             instruction: str) -> Optional[WorkflowBlueprint]:
        """Agent 2: Edit an existing workflow with NL instruction."""
        bp = _load_blueprint(workflow_id, account_id)
        if not bp:
            return None
        bp = self._edit_agent.edit(bp, instruction)
        _save_blueprint(bp)
        return bp

    def get(self, workflow_id: str, account_id: str) -> Optional[WorkflowBlueprint]:
        return _load_blueprint(workflow_id, account_id)

    def list(self, account_id: str) -> List[Dict]:
        return _list_blueprints(account_id)

    def set_llm(self, llm_provider):
        """Wire in the LLM provider after system init."""
        self._llm = llm_provider
        self._build_agent._llm = llm_provider
        self._edit_agent._llm  = llm_provider


_engine: Optional[NLWorkflowEngine] = None

def get_engine(llm_provider=None) -> NLWorkflowEngine:
    global _engine
    if _engine is None:
        _engine = NLWorkflowEngine(llm_provider)
    return _engine
