# Copyright © 2020-2026 Inoni Limited Liability Company. All rights reserved.
# Created by: Corey Post

"""
agent_coordinator.py — Murphy System Multi-Agent Orchestration
Thread-safe coordinator supporting broadcast, point-to-point, and priority routing.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class AgentRole(Enum):
    ORCHESTRATOR = "orchestrator"
    PLANNER = "planner"
    EXECUTOR = "executor"
    VALIDATOR = "validator"
    MONITOR = "monitor"
    SPECIALIST = "specialist"


class MessageType(Enum):
    TASK = "task"
    RESULT = "result"
    BROADCAST = "broadcast"
    HEARTBEAT = "heartbeat"
    ERROR = "error"
    QUERY = "query"
    RESPONSE = "response"


class Priority(Enum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


class AgentStatus(Enum):
    IDLE = "idle"
    BUSY = "busy"
    ERROR = "error"
    OFFLINE = "offline"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class AgentMessage:
    from_agent: str
    to_agent: str               # agent id OR "broadcast"
    msg_type: MessageType
    payload: Dict[str, Any]
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    priority: Priority = Priority.NORMAL
    correlation_id: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "message_id": self.message_id,
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "msg_type": self.msg_type.value,
            "payload": self.payload,
            "timestamp": self.timestamp,
            "priority": self.priority.value,
            "correlation_id": self.correlation_id,
        }


@dataclass
class TaskResult:
    task_id: str
    agent_id: str
    success: bool
    result: Any
    error: Optional[str] = None
    duration_ms: float = 0.0


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class Agent:
    """
    A single agent in the Murphy System swarm.
    Register a processor via register_processor() to handle incoming messages.
    """

    def __init__(
        self,
        agent_id: str,
        role: AgentRole,
        capabilities: Optional[List[str]] = None,
    ) -> None:
        self.agent_id = agent_id
        self.role = role
        self.capabilities: List[str] = capabilities or []
        self.status = AgentStatus.IDLE
        self._inbox: List[AgentMessage] = []
        self._outbox: List[AgentMessage] = []
        self._lock = threading.Lock()
        self._processors: Dict[MessageType, Callable[[AgentMessage], Optional[AgentMessage]]] = {}
        self._coordinator: Optional["AgentCoordinator"] = None

    def register_processor(
        self,
        msg_type: MessageType,
        handler: Callable[[AgentMessage], Optional[AgentMessage]],
    ) -> None:
        self._processors[msg_type] = handler

    def send(self, message: AgentMessage) -> None:
        with self._lock:
            self._outbox.append(message)
        if self._coordinator:
            self._coordinator.dispatch(message)

    def receive(self, message: AgentMessage) -> None:
        with self._lock:
            self._inbox.append(message)

    def process(self) -> List[AgentMessage]:
        with self._lock:
            messages = list(sorted(self._inbox, key=lambda m: -m.priority.value))
            self._inbox.clear()

        responses: List[AgentMessage] = []
        for msg in messages:
            handler = self._processors.get(msg.msg_type)
            if handler:
                try:
                    self.status = AgentStatus.BUSY
                    resp = handler(msg)
                    if resp:
                        responses.append(resp)
                except Exception as exc:
                    error_msg = AgentMessage(
                        from_agent=self.agent_id,
                        to_agent=msg.from_agent,
                        msg_type=MessageType.ERROR,
                        payload={"error": str(exc), "original_msg_id": msg.message_id},
                        correlation_id=msg.message_id,
                    )
                    responses.append(error_msg)
                finally:
                    self.status = AgentStatus.IDLE
        return responses

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "role": self.role.value,
            "capabilities": self.capabilities,
            "status": self.status.value,
            "inbox_size": len(self._inbox),
            "outbox_size": len(self._outbox),
        }

    def __repr__(self) -> str:
        return f"<Agent id={self.agent_id!r} role={self.role.value} status={self.status.value}>"


# ---------------------------------------------------------------------------
# AgentCoordinator
# ---------------------------------------------------------------------------

class AgentCoordinator:
    """
    Central coordinator for the Murphy System agent swarm.
    Supports broadcast, point-to-point, and priority-based routing.
    """

    def __init__(self) -> None:
        self._agents: Dict[str, Agent] = {}
        self._lock = threading.Lock()
        self._message_log: List[AgentMessage] = []

    # ── Registration ─────────────────────────────────────────────────────────

    def register_agent(self, agent: Agent) -> None:
        agent._coordinator = self
        with self._lock:
            self._agents[agent.agent_id] = agent

    def unregister_agent(self, agent_id: str) -> bool:
        with self._lock:
            if agent_id in self._agents:
                del self._agents[agent_id]
                return True
        return False

    def get_agent(self, agent_id: str) -> Optional[Agent]:
        return self._agents.get(agent_id)

    # ── Dispatch ─────────────────────────────────────────────────────────────

    def dispatch(self, message: AgentMessage) -> int:
        """Route a message. Returns number of agents that received it."""
        with self._lock:
            self._message_log.append(message)
            targets: List[Agent] = []

            if message.to_agent == "broadcast":
                targets = [a for a in self._agents.values()
                           if a.agent_id != message.from_agent]
            else:
                agent = self._agents.get(message.to_agent)
                if agent:
                    targets = [agent]

        for agent in targets:
            agent.receive(message)
        return len(targets)

    def broadcast(self, from_agent_id: str, msg_type: MessageType,
                  payload: Dict[str, Any],
                  priority: Priority = Priority.NORMAL) -> int:
        msg = AgentMessage(
            from_agent=from_agent_id,
            to_agent="broadcast",
            msg_type=msg_type,
            payload=payload,
            priority=priority,
        )
        return self.dispatch(msg)

    # ── Orchestration ────────────────────────────────────────────────────────

    def orchestrate_task(
        self,
        task: Dict[str, Any],
        orchestrator_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        High-level task orchestration:
        1. Find the orchestrator agent
        2. Dispatch the task as a TASK message
        3. Collect results from all EXECUTOR agents
        4. Return aggregated results
        """
        orch = (
            self._agents.get(orchestrator_id)
            if orchestrator_id
            else self._find_by_role(AgentRole.ORCHESTRATOR)
        )
        if not orch:
            return {"success": False, "error": "No ORCHESTRATOR agent registered"}

        task_id = task.get("task_id", str(uuid.uuid4()))
        task_msg = AgentMessage(
            from_agent="coordinator",
            to_agent=orch.agent_id,
            msg_type=MessageType.TASK,
            payload={"task_id": task_id, **task},
            priority=Priority.HIGH,
        )

        orch.receive(task_msg)
        responses = orch.process()

        return {
            "task_id": task_id,
            "success": True,
            "orchestrator": orch.agent_id,
            "responses": [r.to_dict() for r in responses],
            "agents_active": len([a for a in self._agents.values()
                                  if a.status != AgentStatus.OFFLINE]),
        }

    # ── Status ───────────────────────────────────────────────────────────────

    def get_swarm_status(self) -> Dict[str, Any]:
        with self._lock:
            agents_info = [a.to_dict() for a in self._agents.values()]
        return {
            "total_agents": len(agents_info),
            "by_role": {
                role.value: [a["agent_id"] for a in agents_info if a["role"] == role.value]
                for role in AgentRole
            },
            "by_status": {
                status.value: [a["agent_id"] for a in agents_info if a["status"] == status.value]
                for status in AgentStatus
            },
            "messages_routed": len(self._message_log),
            "agents": agents_info,
        }

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _find_by_role(self, role: AgentRole) -> Optional[Agent]:
        for agent in self._agents.values():
            if agent.role == role and agent.status != AgentStatus.OFFLINE:
                return agent
        return None

    def list_agents(self) -> List[Agent]:
        return list(self._agents.values())


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

def _make_demo_coordinator() -> AgentCoordinator:
    coord = AgentCoordinator()

    orch = Agent("orch-1", AgentRole.ORCHESTRATOR, ["plan", "delegate"])
    planner = Agent("plan-1", AgentRole.PLANNER, ["decompose", "prioritize"])
    executor = Agent("exec-1", AgentRole.EXECUTOR, ["run_action", "call_api"])
    validator = Agent("valid-1", AgentRole.VALIDATOR, ["hipaa_check", "confidence_gate"])
    monitor = Agent("mon-1", AgentRole.MONITOR, ["metrics", "alerting"])

    def orch_handler(msg: AgentMessage) -> Optional[AgentMessage]:
        return AgentMessage(
            from_agent=orch.agent_id,
            to_agent=msg.from_agent,
            msg_type=MessageType.RESULT,
            payload={"status": "orchestrated", "task_id": msg.payload.get("task_id")},
        )

    orch.register_processor(MessageType.TASK, orch_handler)

    for agent in [orch, planner, executor, validator, monitor]:
        coord.register_agent(agent)

    return coord


if __name__ == "__main__":
    import json as _json

    coord = _make_demo_coordinator()
    print("Murphy System Agent Coordinator")
    print("=" * 50)

    result = coord.orchestrate_task({"task_id": "demo-001", "description": "Process patient record"})
    print("Orchestration result:")
    print(_json.dumps(result, indent=2))
    print()

    status = coord.get_swarm_status()
    print("Swarm status:")
    print(_json.dumps(status, indent=2))
