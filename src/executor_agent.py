"""
PATCH-130 + R195 — src/executor_agent.py
Murphy System — Executor Agent (position 4 / RosettaSoul)

Decides HOW to execute an action. Currently routes to LLM for question
answering; future versions add ICP scoring, side-effects, and tool calls.

REBUILD-2026-06-10: prior file was corrupted (contained only the string
"Swarm heartbeat confirmed"). Rebuilt as minimal LLM passthrough mirroring
scheduler_agent.py shape. Consulted Murphy before rebuild (SD-56).
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

try:
    from src.rosetta_core import AgentBase
except Exception:
    AgentBase = object

logger = logging.getLogger("murphy.executor_agent")


class ExecutorAgent(AgentBase):
    """Position 4 — Executor. Decisive, bias: action_orientation."""

    def __init__(self):
        try:
            super().__init__("executor")
        except Exception:
            # AgentBase may not accept name kwarg in fallback mode
            pass

    def act(self, signal: Dict) -> Dict:
        """Execute on a signal. PATCH-R195: route question → LLM."""
        question     = signal.get("question") or ""
        intent_hint  = signal.get("intent_hint", "execute")
        source       = signal.get("source", "unknown")
        payload      = signal.get("raw_payload", {})
        workflow_run = signal.get("workflow_run_id", "")

        if not question:
            return {
                "status": "ok",
                "response": f"Executor acknowledged intent '{intent_hint}' from {source} (no question)",
                "intent": intent_hint,
                "source": source,
                "workflow_run_id": workflow_run,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        try:
            from src.llm_provider import complete
            system = (
                "You are Murphy's Executor agent. You receive a question or "
                "intent and you give a direct, actionable answer. Be concise. "
                "Be specific. No hedging."
            )
            response_text = complete(
                prompt=question,
                system=system,
                max_tokens=1200,
                temperature=0.2,
            )
            return {
                "status": "ok",
                "response": response_text or "",
                "intent": intent_hint,
                "source": source,
                "workflow_run_id": workflow_run,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as exc:
            logger.warning("ExecutorAgent.act: LLM call failed: %s", exc)
            return {
                "status": "error",
                "response": f"[LLM_ERROR] {exc}",
                "intent": intent_hint,
                "source": source,
                "workflow_run_id": workflow_run,
                "error": str(exc),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }


_executor_agent: Optional[ExecutorAgent] = None

def get_executor_agent() -> ExecutorAgent:
    """Singleton accessor. Mirrors scheduler_agent / collector_agent shape."""
    global _executor_agent
    if _executor_agent is None:
        _executor_agent = ExecutorAgent()
    return _executor_agent
