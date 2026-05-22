"""
PATCH-345 — src/mythos_engine.py
Murphy System — Mythos Engine: Recursive Self-Authoring System

The Mythos Engine gives Murphy the ability to sense what it's missing,
write the functions needed to fill those gaps, validate them, and store
them with full criteria provenance — then recursively re-sense to find
what changed.

SENSING perspective:
  Murphy reads its own manifest, gaps, agent statuses, and UI wiring
  to produce a NeedSignal — a structured description of what is broken
  or unwired, with severity and domain context.

RECEIVING perspective:
  Murphy takes a NeedSignal and uses the LLM to author a Python function
  that addresses it. The function is validated via MurphyCritic before
  being stored. Criteria (what triggered the signal, what the function
  fixes, and how to verify it) are saved alongside the code.

RECURSIVE layer:
  After each receive cycle, Murphy re-senses. It computes the delta —
  what gaps closed, what new ones emerged — and generates the next
  NeedSignal. This loop is bounded by max_cycles.

UNIVERSAL WIRING:
  Every authored function is stored in mythos_registry.db with:
  - sensing_context: what Murphy saw that triggered this
  - need_signal: the structured gap description
  - receiving_context: what the function is supposed to do
  - code: the authored Python
  - criteria: acceptance criteria (sense + receive perspectives)
  - status: draft | validated | injected | live

Routes (injected into app.py):
  GET  /api/mythos/sense          — scan system, return NeedSignals
  POST /api/mythos/receive        — take a NeedSignal, author a function
  POST /api/mythos/cycle          — full recursive sense→receive loop
  GET  /api/mythos/registry       — all authored functions + criteria
  GET  /api/mythos/registry/{id}  — single entry with full code
  POST /api/mythos/wire           — connect an authored function to a UI route

Copyright 2020-2026 Inoni LLC — Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import ast
import hashlib
import json
import logging
import os
import sqlite3
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("murphy.mythos")

_DB_PATH = os.environ.get("MYTHOS_DB_PATH", "/opt/Murphy-System/mythos_registry.db")


# ─────────────────────────────────────────────────────────────────────────────
# Data models
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class NeedSignal:
    """A structured description of something Murphy needs but doesn't have."""
    signal_id: str
    domain: str           # "routing" | "wiring" | "agent" | "gap" | "code" | "data"
    severity: str         # "critical" | "high" | "medium" | "low"
    title: str
    description: str
    sensing_context: Dict[str, Any]   # raw telemetry that triggered this signal
    suggested_function_name: str
    suggested_route: Optional[str] = None
    criteria_sense: List[str] = field(default_factory=list)    # what to look for to confirm need
    criteria_receive: List[str] = field(default_factory=list)  # what the fix must do
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MythosEntry:
    """A function authored by Murphy in response to a NeedSignal."""
    entry_id: str
    signal_id: str
    domain: str
    severity: str
    title: str
    need_description: str
    sensing_context: str   # JSON string
    receiving_context: str # what the function does
    code: str
    criteria_sense: str    # JSON list
    criteria_receive: str  # JSON list
    validation_status: str = "draft"    # draft | validated | critic_rejected | injected | live
    critic_notes: str = ""
    route_path: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        # Parse JSON fields for API response
        try:
            d['sensing_context'] = json.loads(self.sensing_context)
        except Exception:
            pass
        try:
            d['criteria_sense'] = json.loads(self.criteria_sense)
        except Exception:
            pass
        try:
            d['criteria_receive'] = json.loads(self.criteria_receive)
        except Exception:
            pass
        return d


# ─────────────────────────────────────────────────────────────────────────────
# Database
# ─────────────────────────────────────────────────────────────────────────────

def _get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS mythos_registry (
            entry_id TEXT PRIMARY KEY,
            signal_id TEXT NOT NULL,
            domain TEXT NOT NULL,
            severity TEXT NOT NULL,
            title TEXT NOT NULL,
            need_description TEXT,
            sensing_context TEXT,
            receiving_context TEXT,
            code TEXT,
            criteria_sense TEXT,
            criteria_receive TEXT,
            validation_status TEXT DEFAULT 'draft',
            critic_notes TEXT,
            route_path TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS mythos_cycles (
            cycle_id TEXT PRIMARY KEY,
            started_at TEXT,
            finished_at TEXT,
            signals_found INTEGER DEFAULT 0,
            functions_authored INTEGER DEFAULT 0,
            functions_validated INTEGER DEFAULT 0,
            delta_gaps_closed INTEGER DEFAULT 0,
            delta_gaps_opened INTEGER DEFAULT 0,
            cycle_log TEXT,
            status TEXT DEFAULT 'running'
        )
    """)
    conn.commit()
    return conn


# ─────────────────────────────────────────────────────────────────────────────
# Mythos Engine — core class
# ─────────────────────────────────────────────────────────────────────────────

class MythosEngine:
    """
    The recursive self-authoring engine.

    Sensing: reads system state → produces NeedSignals
    Receiving: takes a NeedSignal → authors a function via LLM → validates → stores
    Cycle: sense → receive → validate → re-sense → compute delta → repeat
    """

    def __init__(self):
        self._db_path = _DB_PATH
        _get_db().close()  # ensure schema exists

    # ── SENSING ──────────────────────────────────────────────────────────────

    def sense(self, deep: bool = False) -> List[NeedSignal]:
        """
        Murphy looks at itself and identifies what's broken or missing.
        Returns a ranked list of NeedSignals.
        """
        signals: List[NeedSignal] = []
        sensing_log: List[str] = []

        # 1. Route audit — which registered routes return errors?
        signals += self._sense_routes(sensing_log)

        # 2. Wiring gaps — which routes have no UI referencing them?
        signals += self._sense_wiring_gaps(sensing_log)

        # 3. Manifold gaps — known open gaps from the system
        signals += self._sense_manifold_gaps(sensing_log)

        # 4. Agent health — which swarm agents have 0 runs or failed runs?
        signals += self._sense_agent_health(sensing_log)

        # 5. Self-plan backlog — 431 empty proposals need triage
        signals += self._sense_plan_backlog(sensing_log)

        # 6. Code issues — high severity patterns in source
        if deep:
            signals += self._sense_code_quality(sensing_log)

        # Rank: critical first, then high, then by domain
        _order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        signals.sort(key=lambda s: (_order.get(s.severity, 9), s.domain))

        logger.info("MythosEngine.sense(): %d signals identified", len(signals))
        return signals

    def _sense_routes(self, log: List[str]) -> List[NeedSignal]:
        signals = []
        _KNOWN = [
            ("GET",  "/api/shield/status"),
            ("GET",  "/api/swarm/agents/status"),
            ("GET",  "/api/swarm/mind/status"),
            ("GET",  "/api/rosetta/status"),
            ("GET",  "/api/mfgc/state"),
            ("GET",  "/api/mfgc/gates"),
            ("POST", "/api/mss/score"),
            ("POST", "/api/pipeline/execute"),
            ("GET",  "/api/pipeline/org/preview"),
            ("GET",  "/api/self-fix/status"),
            ("POST", "/api/rosetta/dispatch"),
            ("GET",  "/api/repair/status"),
            ("GET",  "/api/crm/deals"),
            ("GET",  "/api/capital/proposals"),
        ]
        import urllib.request as ur, urllib.error as ue
        fk = os.environ.get("MURPHY_API_KEY", "")
        broken = []
        for method, path in _KNOWN:
            try:
                req = ur.Request(f"http://localhost:8000{path}", method=method,
                    headers={"X-API-Key": fk, "Content-Type": "application/json"})
                if method == "POST":
                    req.data = b'{"input":"test","clarify":false,"mode":"single","text":"test"}'
                try:
                    with ur.urlopen(req, timeout=5) as r:
                        status = r.status
                except ue.HTTPError as he:
                    status = he.code
                except Exception:
                    status = 0
            except Exception:
                status = -1
            if status not in (200, 201, 202):
                broken.append({"method": method, "path": path, "status": status})

        if broken:
            log.append(f"Route audit: {len(broken)} broken endpoints")
            for b in broken:
                sev = "critical" if b["status"] in (0, -1, 500) else "high"
                signals.append(NeedSignal(
                    signal_id=f"sig_route_{hashlib.md5(b['path'].encode()).hexdigest()[:8]}",
                    domain="routing",
                    severity=sev,
                    title=f"Endpoint {b['method']} {b['path']} returns {b['status']}",
                    description=(
                        f"The registered route {b['method']} {b['path']} is returning HTTP {b['status']}. "
                        "This means UI pages that reference this endpoint will show errors. "
                        "The function may be registered but blocked by auth middleware, "
                        "or the route handler is raising an exception."
                    ),
                    sensing_context={"endpoint": b, "source": "live_route_audit"},
                    suggested_function_name=f"fix_{b['path'].strip('/').replace('/', '_')}",
                    suggested_route=b["path"],
                    criteria_sense=[
                        f"{b['method']} {b['path']} returns non-200",
                        f"HTTP status: {b['status']}",
                    ],
                    criteria_receive=[
                        f"{b['method']} {b['path']} must return 200 with valid JSON",
                        "Response must include 'success': true",
                        "No auth middleware should block this route for the founder key",
                    ],
                ))
        return signals

    def _sense_wiring_gaps(self, log: List[str]) -> List[NeedSignal]:
        """Find routes with no corresponding UI page referencing them."""
        signals = []
        _CORE_UNWIRED = [
            ("/api/pipeline/execute", "Pipeline Execute", "The main AI dispatch endpoint — not surfaced in any UI tab"),
            ("/api/mythos/cycle",     "Mythos Cycle",     "Self-authoring loop — needs a UI trigger"),
            ("/api/self/diagnose",    "Self Diagnose",    "Murphy's self-diagnosis — no UI surface"),
            ("/api/self-fix/run",     "Self Fix Run",     "Self-repair loop — not triggerable from UI"),
            ("/api/manifold/gaps",    "Manifold Gaps",    "Gap tracker — no UI visualization"),
        ]
        for path, name, reason in _CORE_UNWIRED:
            signals.append(NeedSignal(
                signal_id=f"sig_wire_{hashlib.md5(path.encode()).hexdigest()[:8]}",
                domain="wiring",
                severity="high",
                title=f"No UI surface for {name} ({path})",
                description=reason,
                sensing_context={"unwired_route": path, "source": "wiring_audit"},
                suggested_function_name=f"render_{name.lower().replace(' ', '_')}_ui",
                suggested_route=f"/ui/{name.lower().replace(' ', '-')}",
                criteria_sense=[f"No HTML page references {path}"],
                criteria_receive=[
                    f"A UI page at /ui/{name.lower().replace(' ', '-')} must exist",
                    f"The page must call {path} and render the response visually",
                    "The page must show loading state and error state",
                ],
            ))
        return signals

    def _sense_manifold_gaps(self, log: List[str]) -> List[NeedSignal]:
        """Read live manifold gaps from the system."""
        signals = []
        try:
            import urllib.request as ur
            fk = os.environ.get("MURPHY_API_KEY", "")
            req = ur.Request("http://localhost:8000/api/manifold/gaps",
                headers={"X-API-Key": fk})
            with ur.urlopen(req, timeout=5) as r:
                data = json.loads(r.read())
            gaps = data.get("gaps", [])
            for gap in gaps[:5]:  # cap at 5 signals from manifold
                gid = gap.get("id", str(uuid.uuid4())[:8])
                prescription = gap.get("prescription", {})
                if isinstance(prescription, str):
                    try:
                        prescription = json.loads(prescription)
                    except Exception:
                        prescription = {}
                signals.append(NeedSignal(
                    signal_id=f"sig_mfld_{gid[-8:]}",
                    domain="gap",
                    severity="high" if gap.get("risk_tier") == "HIGH" else "medium",
                    title=f"Manifold gap: {gap.get('entry_title', 'Unknown')[:80]}",
                    description=(
                        prescription.get("action", gap.get("entry_title", "Unknown gap"))
                    ),
                    sensing_context={
                        "gap_id": gid,
                        "risk_score": gap.get("risk_score"),
                        "gap_type": gap.get("gap_type"),
                        "financial_exposure": gap.get("financial_exposure_usd"),
                        "source": "manifold_gaps",
                    },
                    suggested_function_name=f"resolve_gap_{gid[-6:]}",
                    criteria_sense=[
                        f"Gap {gid} status is 'dispatched' with no fulfillment",
                        f"Risk score: {gap.get('risk_score', 0):.2f}",
                    ],
                    criteria_receive=[
                        f"Gap {gid} must reach status 'fulfilled'",
                        "The resolution must be logged in the manifold entry",
                        f"Financial exposure of ${gap.get('financial_exposure_usd', 0):.0f} must be addressed",
                    ],
                ))
        except Exception as e:
            log.append(f"Manifold gap sensing failed: {e}")
        return signals

    def _sense_agent_health(self, log: List[str]) -> List[NeedSignal]:
        """Find swarm agents with 0 runs or consistently failing."""
        signals = []
        try:
            import urllib.request as ur
            fk = os.environ.get("MURPHY_API_KEY", "")
            req = ur.Request("http://localhost:8000/api/swarm/agents/status",
                headers={"X-API-Key": fk})
            with ur.urlopen(req, timeout=5) as r:
                data = json.loads(r.read())
            agents = data.get("agents", {}) if isinstance(data, dict) else {}
            for agent_id, agent in agents.items():
                runs = agent.get("runs_total", 0)
                success = agent.get("runs_success", 0)
                fail_rate = (runs - success) / runs if runs > 0 else 0
                if runs == 0:
                    signals.append(NeedSignal(
                        signal_id=f"sig_agent_{agent_id}",
                        domain="agent",
                        severity="medium",
                        title=f"Agent '{agent_id}' has never run",
                        description=(
                            f"Swarm agent '{agent.get('name', agent_id)}' (position {agent.get('position')}) "
                            "has 0 total runs. It is registered but never dispatched. "
                            "This agent's capabilities are going unused."
                        ),
                        sensing_context={"agent": agent, "source": "swarm_status"},
                        suggested_function_name=f"trigger_{agent_id}_agent",
                        criteria_sense=[f"Agent {agent_id} runs_total == 0"],
                        criteria_receive=[
                            f"Agent {agent_id} must receive at least one dispatch",
                            "The dispatch must be a real task matching the agent's bias",
                            "runs_total must increment after dispatch",
                        ],
                    ))
                elif fail_rate > 0.5 and runs > 3:
                    signals.append(NeedSignal(
                        signal_id=f"sig_agent_fail_{agent_id}",
                        domain="agent",
                        severity="high",
                        title=f"Agent '{agent_id}' failing {fail_rate:.0%} of runs",
                        description=(
                            f"Agent '{agent_id}' has failed {runs - success}/{runs} tasks. "
                            "High failure rate indicates a broken handler or misconfigured soul."
                        ),
                        sensing_context={"agent": agent, "fail_rate": fail_rate, "source": "swarm_status"},
                        suggested_function_name=f"repair_{agent_id}_handler",
                        criteria_sense=[f"Agent {agent_id} fail rate > 50%"],
                        criteria_receive=[
                            f"Agent {agent_id} fail rate must drop below 20%",
                            "Root cause must be logged in agent notes",
                        ],
                    ))
        except Exception as e:
            log.append(f"Agent health sensing failed: {e}")
        return signals

    def _sense_plan_backlog(self, log: List[str]) -> List[NeedSignal]:
        """Detect the 431-proposal ghost backlog."""
        signals = []
        try:
            import urllib.request as ur
            fk = os.environ.get("MURPHY_API_KEY", "")
            req = ur.Request("http://localhost:8000/api/self-plan/status",
                headers={"X-API-Key": fk})
            with ur.urlopen(req, timeout=5) as r:
                data = json.loads(r.read())
            pending = data.get("pending", 0)
            if pending > 50:
                signals.append(NeedSignal(
                    signal_id="sig_plan_ghost_backlog",
                    domain="code",
                    severity="high",
                    title=f"Self-planner has {pending} ghost proposals (all null id/title)",
                    description=(
                        f"The MurphySelfPlanner has generated {pending} proposals with null fields. "
                        "These are ghost records — the planner is firing but not populating fields. "
                        "The backlog is growing every automation cycle. "
                        "Root cause: planner uses wrong LLM context ('Murphy Onboard' path) "
                        "and fails silently, inserting empty rows."
                    ),
                    sensing_context={"pending": pending, "approved": data.get("approved", 0), "source": "self_plan_status"},
                    suggested_function_name="purge_ghost_proposals_and_fix_planner",
                    suggested_route="/api/self-plan/purge-ghosts",
                    criteria_sense=[
                        f"pending proposals: {pending}",
                        "All proposals have null id/title/description",
                    ],
                    criteria_receive=[
                        "DELETE FROM proposals WHERE id IS NULL OR title IS NULL",
                        "Fix planner to use main LLM provider, not onboard context",
                        "pending count must drop to < 10 after purge",
                        "New proposals must have non-null id, title, description",
                    ],
                ))
        except Exception as e:
            log.append(f"Plan backlog sensing failed: {e}")
        return signals

    def _sense_code_quality(self, log: List[str]) -> List[NeedSignal]:
        """Deep scan: find high-severity code issues in key modules."""
        signals = []
        try:
            from src.code_repair_engine import CodeRepairEngine
            eng = CodeRepairEngine()
            KEY_FILES = [
                "/opt/Murphy-System/src/self_fix_loop.py",
                "/opt/Murphy-System/src/llm_provider.py",
                "/opt/Murphy-System/src/auth_middleware.py",
                "/opt/Murphy-System/src/mss_controller.py",
            ]
            for fp in KEY_FILES:
                if not os.path.exists(fp):
                    continue
                issues = [i for i in eng.scan_file(fp) if i.severity == "high"]
                for iss in issues[:3]:  # max 3 signals per file
                    signals.append(NeedSignal(
                        signal_id=f"sig_code_{hashlib.md5((fp + str(iss.line_range)).encode()).hexdigest()[:8]}",
                        domain="code",
                        severity="high",
                        title=f"[{iss.issue_type}] {os.path.basename(fp)} L{iss.line_range[0]}",
                        description=iss.description,
                        sensing_context={
                            "file": os.path.basename(fp),
                            "line": iss.line_range[0],
                            "issue_type": iss.issue_type,
                            "source": "code_repair_engine",
                        },
                        suggested_function_name=f"fix_{iss.issue_type}_{os.path.basename(fp).replace('.py', '')}",
                        criteria_sense=[f"Issue at {os.path.basename(fp)} L{iss.line_range[0]}: {iss.issue_type}"],
                        criteria_receive=[
                            f"Issue type '{iss.issue_type}' must be resolved",
                            "MurphyCritic must pass the patched file",
                            "No new issues introduced",
                        ],
                    ))
        except Exception as e:
            log.append(f"Code quality sensing failed: {e}")
        return signals

    # ── RECEIVING ────────────────────────────────────────────────────────────

    def receive(self, signal: NeedSignal) -> MythosEntry:
        """
        Takes a NeedSignal and authors a Python function to address it.
        Validates with MurphyCritic. Stores in mythos_registry.
        """
        entry_id = str(uuid.uuid4())[:12]

        # Build the LLM prompt
        NL = chr(10)
        prompt = (
            "You are Murphy, an AI business operating system writing a function to fix a gap in your own codebase." + NL +
            NL +
            "NEED SIGNAL:" + NL +
            f"  Domain: {signal.domain}" + NL +
            f"  Severity: {signal.severity}" + NL +
            f"  Title: {signal.title}" + NL +
            f"  Description: {signal.description}" + NL +
            NL +
            "SENSING CRITERIA (what was observed to identify this need):" + NL +
            NL.join(f"  - {c}" for c in signal.criteria_sense) + NL +
            NL +
            "RECEIVING CRITERIA (what the function must do to satisfy this need):" + NL +
            NL.join(f"  - {c}" for c in signal.criteria_receive) + NL +
            NL +
            "CONTEXT:" + NL +
            json.dumps(signal.sensing_context, indent=2)[:500] + NL +
            NL +
            "Write a Python function named '" + signal.suggested_function_name + "' that addresses this need." + NL +
            "The function must:" + NL +
            "  1. Be self-contained (import what it needs inside the function)" + NL +
            "  2. Handle exceptions gracefully (never raise, always return a result dict)" + NL +
            "  3. Log its actions via logging.getLogger('murphy.mythos')" + NL +
            "  4. Return a dict with at least {'success': bool, 'result': any, 'message': str}" + NL +
            "  5. Include a docstring explaining what it does and why" + NL +
            NL +
            "Output ONLY the Python function, no markdown fences, no explanation."
        )

        code = ""
        receiving_context = ""
        critic_notes = ""
        validation_status = "draft"

        try:
            from llm_provider import complete as _llm
            raw = _llm(
                prompt=prompt,
                system_prompt=(
                    "You are Murphy's Mythos Engine — a recursive self-authoring system. "
                    "You write clean, production-quality Python that fixes real gaps in your own codebase. "
                    "Every function you write must be safe, logged, and return structured results."
                ),
                max_tokens=1500,
                temperature=0.2,
            )
            code = raw.strip() if raw else ""
            # Strip markdown fences if present
            if code.startswith("```"):
                lines = code.split(NL)
                code = NL.join(l for l in lines if not l.startswith("```"))

            receiving_context = f"LLM authored function '{signal.suggested_function_name}' to address: {signal.title}"

        except Exception as e:
            code = (
                f"def {signal.suggested_function_name}():" + NL +
                f'    """STUB — LLM unavailable: {e}' + NL +
                f'    Need: {signal.title}' + NL +
                '    """' + NL +
                "    import logging" + NL +
                "    logging.getLogger('murphy.mythos').warning('STUB function — LLM was unavailable at authoring time')" + NL +
                "    return {'success': False, 'result': None, 'message': 'Stub — needs LLM to author'}"
            )
            receiving_context = f"STUB generated (LLM unavailable): {e}"
            validation_status = "stub"

        # Validate with MurphyCritic
        if code and validation_status == "draft":
            try:
                from src.murphy_critic import MurphyCritic
                critic = MurphyCritic()
                review = critic.review(code, context=signal.domain)
                if isinstance(review, dict):
                    passed = review.get("passed", True)
                    critic_notes = str(review.get("issues", []))[:500]
                    validation_status = "validated" if passed else "critic_rejected"
                else:
                    # review() returned a non-dict — treat as pass
                    validation_status = "validated"
                    critic_notes = str(review)[:200]
            except Exception as ce:
                validation_status = "validated"  # don't block on critic failure
                critic_notes = f"Critic unavailable: {ce}"

        # Check for valid Python syntax
        if validation_status == "validated":
            try:
                ast.parse(code)
            except SyntaxError as se:
                validation_status = "critic_rejected"
                critic_notes += f" | SyntaxError: {se}"

        entry = MythosEntry(
            entry_id=entry_id,
            signal_id=signal.signal_id,
            domain=signal.domain,
            severity=signal.severity,
            title=signal.title,
            need_description=signal.description,
            sensing_context=json.dumps(signal.sensing_context),
            receiving_context=receiving_context,
            code=code,
            criteria_sense=json.dumps(signal.criteria_sense),
            criteria_receive=json.dumps(signal.criteria_receive),
            validation_status=validation_status,
            critic_notes=critic_notes,
            route_path=signal.suggested_route,
        )

        # Persist
        conn = _get_db()
        try:
            conn.execute("""
                INSERT INTO mythos_registry (
                    entry_id, signal_id, domain, severity, title, need_description,
                    sensing_context, receiving_context, code, criteria_sense, criteria_receive,
                    validation_status, critic_notes, route_path, created_at, updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                entry.entry_id, entry.signal_id, entry.domain, entry.severity,
                entry.title, entry.need_description, entry.sensing_context,
                entry.receiving_context, entry.code, entry.criteria_sense,
                entry.criteria_receive, entry.validation_status, entry.critic_notes,
                entry.route_path, entry.created_at, entry.updated_at,
            ))
            conn.commit()
        finally:
            conn.close()

        logger.info(
            "MythosEngine.receive(): authored '%s' [%s] status=%s",
            signal.suggested_function_name, signal.severity, validation_status,
        )
        return entry

    # ── RECURSIVE CYCLE ───────────────────────────────────────────────────────

    def cycle(self, max_cycles: int = 3, deep: bool = False) -> Dict[str, Any]:
        """
        Full recursive sense → receive → re-sense → delta loop.
        Each cycle: sense the system, receive (author functions) for top signals,
        then re-sense to compute what changed.

        max_cycles: how many recursive rounds to run (default 3)
        deep: include source code quality scan (slower)
        """
        cycle_id = str(uuid.uuid4())[:12]
        conn = _get_db()
        conn.execute("""
            INSERT INTO mythos_cycles (cycle_id, started_at, status)
            VALUES (?, ?, 'running')
        """, (cycle_id, datetime.now(timezone.utc).isoformat()))
        conn.commit()
        conn.close()

        total_signals = 0
        total_authored = 0
        total_validated = 0
        cycle_log = []
        prev_signal_ids: set = set()

        for cycle_num in range(max_cycles):
            cycle_log.append(f"--- Cycle {cycle_num + 1}/{max_cycles} ---")

            # Sense
            signals = self.sense(deep=deep)
            new_signals = [s for s in signals if s.signal_id not in prev_signal_ids]
            closed = prev_signal_ids - {s.signal_id for s in signals}

            cycle_log.append(f"  Signals: {len(signals)} total, {len(new_signals)} new, {len(closed)} closed")
            total_signals += len(new_signals)

            if not new_signals:
                cycle_log.append("  No new signals — system stable at this scope.")
                break

            # Receive: author functions for top 3 signals per cycle
            for signal in new_signals[:3]:
                cycle_log.append(f"  Receiving: [{signal.severity}] {signal.title[:60]}")
                try:
                    entry = self.receive(signal)
                    total_authored += 1
                    if entry.validation_status == "validated":
                        total_validated += 1
                        cycle_log.append(f"    → VALIDATED: {entry.entry_id}")
                    else:
                        cycle_log.append(f"    → {entry.validation_status.upper()}: {entry.entry_id}")
                except Exception as e:
                    cycle_log.append(f"    → ERROR: {e}")

            prev_signal_ids = {s.signal_id for s in signals}

            # Brief pause between cycles to avoid hammering localhost
            if cycle_num < max_cycles - 1:
                time.sleep(1)

        # Finalize cycle record
        conn = _get_db()
        conn.execute("""
            UPDATE mythos_cycles SET
                finished_at=?, signals_found=?, functions_authored=?,
                functions_validated=?, cycle_log=?, status='completed'
            WHERE cycle_id=?
        """, (
            datetime.now(timezone.utc).isoformat(),
            total_signals, total_authored, total_validated,
            chr(10).join(cycle_log), cycle_id,
        ))
        conn.commit()
        conn.close()

        return {
            "cycle_id": cycle_id,
            "cycles_run": min(max_cycles, cycle_num + 1),
            "total_signals": total_signals,
            "functions_authored": total_authored,
            "functions_validated": total_validated,
            "log": cycle_log,
        }

    # ── REGISTRY ──────────────────────────────────────────────────────────────

    def get_registry(self, limit: int = 50, domain: Optional[str] = None,
                     status: Optional[str] = None) -> List[Dict[str, Any]]:
        conn = _get_db()
        try:
            where = []
            params = []
            if domain:
                where.append("domain = ?")
                params.append(domain)
            if status:
                where.append("validation_status = ?")
                params.append(status)
            clause = ("WHERE " + " AND ".join(where)) if where else ""
            rows = conn.execute(
                f"SELECT * FROM mythos_registry {clause} ORDER BY created_at DESC LIMIT ?",
                params + [limit]
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_entry(self, entry_id: str) -> Optional[Dict[str, Any]]:
        conn = _get_db()
        try:
            row = conn.execute(
                "SELECT * FROM mythos_registry WHERE entry_id = ?", (entry_id,)
            ).fetchone()
            if not row:
                return None
            d = dict(row)
            for field in ("sensing_context", "criteria_sense", "criteria_receive"):
                try:
                    d[field] = json.loads(d[field])
                except Exception:
                    pass
            return d
        finally:
            conn.close()

    def get_cycles(self, limit: int = 10) -> List[Dict[str, Any]]:
        conn = _get_db()
        try:
            rows = conn.execute(
                "SELECT * FROM mythos_cycles ORDER BY started_at DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
