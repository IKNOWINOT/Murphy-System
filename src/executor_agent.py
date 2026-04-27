"""
PATCH-130 — src/executor_agent.py
Murphy System — Executor Agent (position 4 / RosettaSoul)
Carries out approved actions via DAG execution.
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

try:
    from src.rosetta_core import AgentBase
except Exception:
    AgentBase = object

logger = logging.getLogger("murphy.executor")


class ExecutorAgent(AgentBase):
    """Position 4 — Executor. Direct, bias: completion."""

    def __init__(self):
        super().__init__("executor")

    def act(self, signal: Dict) -> Dict:
        """Execute a pre-approved action via the DAG executor."""
        action = signal.get("action", "")
        domain = signal.get("domain", "general")
        payload = signal.get("raw_payload", {})

        try:
            from src.workflow_dag import build_dag, task_node, get_executor
            dag = build_dag(
                f"exec_{domain}",
                f"Executor: {action[:60]}",
                domain=domain,
                stake=signal.get("stake", "medium"),
                account=signal.get("source", "system"),
            )
            dag.add_node(task_node("execute", action, depends_on=[]))
            result = get_executor().execute(dag)
            return {
                "status": "executed",
                "dag_id": dag.dag_id,
                "dag_status": result.status,
                "action": action,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as exc:
            logger.warning("ExecutorAgent.act error: %s", exc)
            return {"status": "error", "action": action, "error": str(exc)}


_executor_agent: Optional[ExecutorAgent] = None

def get_executor_agent() -> ExecutorAgent:
    global _executor_agent
    if _executor_agent is None:
        _executor_agent = ExecutorAgent()
    return _executor_agent
