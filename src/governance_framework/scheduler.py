"""
Governance Scheduler Implementation

Implements scheduler semantics that prioritize stability over throughput:
- Authority precedence enforcement
- Bounded iteration control
- Refusal as valid terminal state
- Resource containment
- Dependency resolution
"""

import heapq
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Set, Union

from .agent_descriptor_complete import ActionType, AgentDescriptor, AuthorityBand, PriorityLevel
from .stability_controller import ExecutionOutcome

logger = logging.getLogger(__name__)


class SchedulingDecision(Enum):
    """Scheduler decision types"""
    SCHEDULE = "SCHEDULE"
    BLOCK = "BLOCK"
    TERMINATE = "TERMINATE"
    ESCALATE = "ESCALATE"
    REFUSE = "REFUSE"


@dataclass
class ScheduledAgent:
    """Agent scheduled for execution"""

    agent_id: str
    descriptor: AgentDescriptor
    priority: PriorityLevel
    scheduled_time: datetime
    dependencies: List[str]
    resource_requirements: Dict[str, int]

    def __lt__(self, other):
        """For priority queue ordering"""
        if self.priority.value != other.priority.value:
            return self.priority.value < other.priority.value
        return self.scheduled_time < other.scheduled_time


class GovernanceScheduler:
    """Scheduler that enforces governance rules"""

    def __init__(self):
        self.scheduled_agents = []
        self.running_agents = {}
        self.completed_agents = {}

        # System resources
        self.total_resources = {
            "max_cpu": 16,
            "max_memory": 32768,
            "max_api_calls": 1000
        }

        self.used_resources = {
            "cpu": 0,
            "memory": 0,
            "api_calls": 0
        }

        self.lock = threading.RLock()

    def schedule_agent(self, agent: ScheduledAgent) -> SchedulingDecision:
        """Schedule agent with governance enforcement"""

        with self.lock:
            # Rule 1: Authority Precedence
            if not self._check_authority_precedence(agent):
                return SchedulingDecision.BLOCK

            # Rule 2: Resource Containment
            if not self._check_resource_containment(agent):
                return SchedulingDecision.BLOCK

            # Rule 3: Dependency Resolution
            if not self._check_dependencies(agent):
                return SchedulingDecision.BLOCK

            # Schedule the agent
            heapq.heappush(self.scheduled_agents, agent)

            return SchedulingDecision.SCHEDULE

    def _check_authority_precedence(self, agent: ScheduledAgent) -> bool:
        """Rule 1: Authority Precedence"""
        return agent.descriptor.authority_band != AuthorityBand.NONE or \
               agent.descriptor.can_execute_action(ActionType.PROPOSE_ACTION)

    def _check_resource_containment(self, agent: ScheduledAgent) -> bool:
        """Rule 2: Resource Containment"""

        required_cpu = agent.resource_requirements.get("cpu", 0)
        required_memory = agent.resource_requirements.get("memory", 0)

        available_cpu = self.total_resources["max_cpu"] - self.used_resources["cpu"]
        available_memory = self.total_resources["max_memory"] - self.used_resources["memory"]

        return required_cpu <= available_cpu and required_memory <= available_memory

    def _check_dependencies(self, agent: ScheduledAgent) -> bool:
        """Rule 3: Dependency Resolution"""

        for dep_id in agent.dependencies:
            if dep_id not in self.completed_agents:
                return False

        return True

    def get_system_status(self) -> Dict:
        """Get current system status"""

        with self.lock:
            return {
                "scheduled_count": len(self.scheduled_agents),
                "running_count": len(self.running_agents),
                "completed_count": len(self.completed_agents),
                "resource_utilization": {
                    "cpu_percent": (self.used_resources["cpu"] / self.total_resources["max_cpu"]) * 100,
                    "memory_percent": (self.used_resources["memory"] / self.total_resources["max_memory"]) * 100
                },
                "total_authority": sum(
                    agent.descriptor.authority_band.value
                    for agent in self.running_agents.values()
                    if "descriptor" in agent
                )
            }

    def enforce_invariants(self) -> List[str]:
        """Enforce system invariants"""

        violations = []

        # Check total authority doesn't exceed system limits
        total_authority = sum(
            agent.descriptor.authority_band.value
            for agent in self.running_agents.values()
            if "descriptor" in agent
        )

        if total_authority > 10:
            violations.append("Total authority exceeds system limit")

        # Check resource boundary (90% rule)
        if self.used_resources["cpu"] > self.total_resources["max_cpu"] * 0.9:
            violations.append("CPU usage exceeds 90% threshold")

        if self.used_resources["memory"] > self.total_resources["max_memory"] * 0.9:
            violations.append("Memory usage exceeds 90% threshold")

        return violations
