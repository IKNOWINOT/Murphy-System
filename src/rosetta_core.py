"""
PATCH-115 — src/rosetta_core.py
Murphy System — Swarm Rosetta Core Coordinator

The Rosetta is the translation hub of the agent swarm.
It receives signals from the SignalCollector, routes them to the correct
domain agent (ExecAdmin, ProdOps), and orchestrates the full
NL→DAG→Execute→Learn pipeline.

Translation layers (Urantia principle):
  PAST   — pattern library lookup (what has worked before?)
  PRESENT — current signal + PCC context (what is needed now?)
  LEGACY  — record outcome to pattern library (what should be remembered?)

The Rosetta maintains swarm state: all agents, their last activity,
active workflows, and the signal queue.

Copyright © 2020-2026 Inoni LLC — Created by Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("murphy.rosetta_core")


@dataclass
class AgentState:
    agent_id: str
    name: str
    emoji: str
    role: str
    domain: str
    status: str = "idle"          # idle | running | error | offline
    last_trigger: Optional[str] = None
    last_outcome: Optional[str] = None
    runs_total: int = 0
    runs_success: int = 0
    handler: Optional[Callable] = None


class RosettraCore:
    """
    PATCH-115: Swarm Rosetta Coordinator.

    Wires: SignalCollector → route → Agent → DAGExecutor → PatternLibrary
    """

    AGENT_REGISTRY: Dict[str, Dict] = {
        "collector":   {"name": "Collector",   "emoji": "📡", "domain": "system",     "role": "Ingests all ambient signals"},
        "translator":  {"name": "Translator",  "emoji": "🧠", "domain": "system",     "role": "NL→DAG via LCM + pattern lib"},
        "scheduler":   {"name": "Scheduler",   "emoji": "🗓️", "domain": "system",     "role": "Cron + event trigger backbone"},
        "executor":    {"name": "Executor",    "emoji": "⚡", "domain": "system",     "role": "Runs DAG nodes via execution_router"},
        "auditor":     {"name": "Auditor",     "emoji": "📋", "domain": "system",     "role": "Logs every step, feeds pattern lib"},
        "exec_admin":  {"name": "ExecAdmin",   "emoji": "👔", "domain": "exec_admin", "role": "Calendar, email, approvals, reports"},
        "prod_ops":    {"name": "ProdOps",     "emoji": "🔧", "domain": "prod_ops",   "role": "Deploy, health, incident, self-patch"},
        "hitl":        {"name": "HITL Gate",   "emoji": "🔴", "domain": "system",     "role": "Human approval for high/critical stake"},
        "rosetta":     {"name": "Rosetta",     "emoji": "🌐", "domain": "system",     "role": "Coordinator: routes signals→agents"},
    }

    def __init__(self):
        self._agents: Dict[str, AgentState] = {}
        self._active_workflows: Dict[str, Dict] = {}
        self._signal_queue: List[Dict] = []
        self._lock = threading.Lock()
        self._running = False
        self._loop_thread: Optional[threading.Thread] = None
        self._init_agents()
        logger.info("PATCH-115: RosettraCore initialized — %d agents registered", len(self._agents))

    def _init_agents(self):
        for agent_id, cfg in self.AGENT_REGISTRY.items():
            self._agents[agent_id] = AgentState(
                agent_id=agent_id,
                name=cfg["name"],
                emoji=cfg["emoji"],
                role=cfg["role"],
                domain=cfg["domain"],
            )

    def register_handler(self, agent_id: str, handler: Callable):
        """Wire a handler function to an agent."""
        if agent_id in self._agents:
            self._agents[agent_id].handler = handler
            logger.info("Rosetta: handler registered for agent '%s'", agent_id)

    def route_signal(self, signal: Dict) -> Optional[str]:
        """
        Route a normalized signal to the correct domain agent.
        Returns dag_id if a workflow was triggered, else None.
        """
        domain = signal.get("domain", "system")
        signal_type = signal.get("signal_type", "")
        intent_hint = signal.get("intent_hint", "")

        # Determine target agent
        if domain == "exec_admin":
            target = "exec_admin"
        elif domain == "prod_ops":
            target = "prod_ops"
        elif signal_type in ("lcm_intent",):
            target = "translator"
        else:
            logger.debug("Rosetta: signal domain=%s → no specific agent, queuing", domain)
            return None

        agent = self._agents.get(target)
        if not agent:
            return None

        logger.info("Rosetta: routing %s → %s agent [%s]",
                    signal.get("signal_id","?"), target, intent_hint[:60])

        if agent.handler:
            try:
                agent.status = "running"
                agent.last_trigger = datetime.now(timezone.utc).isoformat()
                result = agent.handler(signal)
                agent.status = "idle"
                agent.runs_total += 1
                agent.runs_success += 1
                agent.last_outcome = "ok"
                return result
            except Exception as exc:
                agent.status = "error"
                agent.runs_total += 1
                agent.last_outcome = f"error: {exc}"
                logger.error("Rosetta: agent %s failed: %s", target, exc)
                return None
        else:
            logger.debug("Rosetta: agent %s has no handler yet (PATCH pending)", target)
            return None

    def translate(self, nl_text: str, account: str = "unknown",
                  execute: bool = False) -> Dict:
        """
        Full Rosetta translation: NL → WorkflowSpec → DAGGraph → [Execute].
        This is the PRESENT layer: what does this text mean right now?
        """
        from src.nl_workflow_parser import get_parser
        from src.workflow_dag import get_executor, get_workflow_db

        # PAST: check pattern library (stub for PATCH-119)
        pattern_match = None

        # PRESENT: parse
        parser = get_parser()
        spec, dag = parser.parse_and_build_dag(nl_text, account=account)

        dag_dict = dag.to_dict()

        result = {
            "spec": {
                "intent": spec.intent,
                "domain": spec.domain,
                "urgency": spec.urgency,
                "stake": spec.stake,
                "constraints": spec.constraints,
                "entities": spec.entities,
                "confidence": spec.confidence,
            },
            "dag": {
                "dag_id": dag.dag_id,
                "name": dag.name,
                "nodes": len(dag.nodes),
                "status": dag.status,
            },
            "pattern_match": pattern_match,
            "executed": False,
        }

        if execute and dag.stake not in ("critical",):
            executor = get_executor()
            executed_dag = executor.execute(dag)
            result["dag"]["status"] = executed_dag.status
            result["executed"] = True

            # LEGACY: record to pattern library (stub for PATCH-119)
            logger.info("Rosetta: LEGACY — outcome recorded for pattern learning (dag=%s)", dag.dag_id)

        with self._lock:
            self._active_workflows[dag.dag_id] = {
                "dag_id": dag.dag_id,
                "name": dag.name,
                "domain": spec.domain,
                "stake": spec.stake,
                "status": dag.status,
                "account": account,
                "started_at": datetime.now(timezone.utc).isoformat(),
            }

        return result

    def swarm_status(self) -> Dict:
        """Return full swarm state for dashboard."""
        with self._lock:
            return {
                "agents": {
                    aid: {
                        "name": a.name,
                        "emoji": a.emoji,
                        "role": a.role,
                        "domain": a.domain,
                        "status": a.status,
                        "last_trigger": a.last_trigger,
                        "last_outcome": a.last_outcome,
                        "runs_total": a.runs_total,
                        "runs_success": a.runs_success,
                        "has_handler": a.handler is not None,
                    }
                    for aid, a in self._agents.items()
                },
                "active_workflows": len(self._active_workflows),
                "signal_queue_depth": len(self._signal_queue),
                "rosetta": "operational",
            }

    def start_signal_loop(self, interval_seconds: float = 30.0):
        """Start background thread that processes signal queue."""
        if self._running:
            return
        self._running = True

        def _loop():
            while self._running:
                try:
                    from src.signal_collector import get_collector
                    collector = get_collector()
                    signals = collector.latest(limit=10)
                    unprocessed = [s for s in signals if not s.get("processed")]
                    for signal in unprocessed[:5]:
                        self.route_signal(signal)
                except Exception as exc:
                    logger.warning("Rosetta signal loop error: %s", exc)
                time.sleep(interval_seconds)

        self._loop_thread = threading.Thread(target=_loop, daemon=True, name="rosetta-signal-loop")
        self._loop_thread.start()
        logger.info("Rosetta: signal processing loop started (interval=%ss)", interval_seconds)

    def stop(self):
        self._running = False


# ── Singleton ─────────────────────────────────────────────────────────────────
_rosetta: Optional[RosettraCore] = None
_rosetta_lock = threading.Lock()

def get_rosetta() -> RosettraCore:
    global _rosetta
    if _rosetta is None:
        with _rosetta_lock:
            if _rosetta is None:
                _rosetta = RosettraCore()
    return _rosetta
