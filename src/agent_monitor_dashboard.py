"""
Agent Monitor Dashboard
========================
Real-time monitoring dashboard for all agents in the system.
Shows what each agent is doing, how they're monitoring, with
drill-down capability to inspect any agent's activity at any time.
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class AgentState(Enum):
    """Possible states of a monitored agent."""
    IDLE = "idle"
    MONITORING = "monitoring"
    EXECUTING = "executing"
    ALERTING = "alerting"
    PAUSED = "paused"
    ERROR = "error"
    TERMINATED = "terminated"


class MonitoringMode(Enum):
    """How an agent monitors its target."""
    PASSIVE = "passive"
    ACTIVE = "active"
    REACTIVE = "reactive"
    PREDICTIVE = "predictive"


@dataclass
class AgentActivity:
    """A single activity record for an agent."""
    activity_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    action: str = ""
    target: str = ""
    result: str = ""
    metrics: dict = field(default_factory=dict)
    duration_ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            "activity_id": self.activity_id,
            "timestamp": self.timestamp,
            "action": self.action,
            "target": self.target,
            "result": self.result,
            "metrics": self.metrics,
            "duration_ms": self.duration_ms,
        }


@dataclass
class MonitoredAgent:
    """Representation of an agent being tracked by the dashboard."""
    agent_id: str = field(default_factory=lambda: f"agent-{str(uuid.uuid4())[:8]}")
    name: str = ""
    role: str = "monitor"
    state: AgentState = AgentState.IDLE
    monitoring_mode: MonitoringMode = MonitoringMode.PASSIVE
    assigned_targets: list = field(default_factory=list)
    metrics_tracked: list = field(default_factory=list)
    activity_log: list = field(default_factory=list)
    alert_count: int = 0
    last_heartbeat: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    config: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "role": self.role,
            "state": self.state.value,
            "monitoring_mode": self.monitoring_mode.value,
            "assigned_targets": self.assigned_targets,
            "metrics_tracked": self.metrics_tracked,
            "activity_log": [a.to_dict() if hasattr(a, 'to_dict') else a for a in self.activity_log[-20:]],
            "alert_count": self.alert_count,
            "last_heartbeat": self.last_heartbeat,
            "created_at": self.created_at,
            "config": self.config,
        }

    def to_summary(self) -> dict:
        """Minimal summary for dashboard listing."""
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "role": self.role,
            "state": self.state.value,
            "monitoring_mode": self.monitoring_mode.value,
            "target_count": len(self.assigned_targets),
            "alert_count": self.alert_count,
            "last_heartbeat": self.last_heartbeat,
        }


@dataclass
class DashboardSnapshot:
    """A point-in-time snapshot of the entire dashboard."""
    snapshot_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    total_agents: int = 0
    agents_by_state: dict = field(default_factory=dict)
    agents_by_role: dict = field(default_factory=dict)
    total_alerts: int = 0
    agent_summaries: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "snapshot_id": self.snapshot_id,
            "timestamp": self.timestamp,
            "total_agents": self.total_agents,
            "agents_by_state": self.agents_by_state,
            "agents_by_role": self.agents_by_role,
            "total_alerts": self.total_alerts,
            "agent_summaries": self.agent_summaries,
        }


class AgentMonitorDashboard:
    """
    Real-time dashboard for monitoring all agents in the system.
    Provides overview, drill-down, and activity tracking.
    """

    def __init__(self):
        self.agents: dict[str, MonitoredAgent] = {}
        self.max_agents = 500
        self.max_activity_per_agent = 1000

    def register_agent(
        self,
        name: str,
        role: str = "monitor",
        monitoring_mode: str = "passive",
        targets: Optional[list] = None,
        metrics: Optional[list] = None,
        config: Optional[dict] = None,
    ) -> MonitoredAgent:
        """Register a new agent for monitoring."""
        if len(self.agents) >= self.max_agents:
            # Evict terminated agents first
            terminated = [k for k, v in self.agents.items() if v.state == AgentState.TERMINATED]
            for t in terminated[:10]:
                del self.agents[t]

        mode = MonitoringMode.PASSIVE
        for m in MonitoringMode:
            if m.value == monitoring_mode:
                mode = m
                break

        agent = MonitoredAgent(
            name=name,
            role=role,
            monitoring_mode=mode,
            assigned_targets=targets or [],
            metrics_tracked=metrics or [],
            config=config or {},
        )
        self.agents[agent.agent_id] = agent

        self._record_activity(agent.agent_id, "registered", "system", "Agent registered on dashboard")
        return agent

    def update_state(self, agent_id: str, new_state: str) -> Optional[MonitoredAgent]:
        """Update an agent's state."""
        agent = self.agents.get(agent_id)
        if not agent:
            return None

        old_state = agent.state.value
        for s in AgentState:
            if s.value == new_state:
                agent.state = s
                break

        agent.last_heartbeat = datetime.now(timezone.utc).isoformat()
        self._record_activity(agent_id, "state_change", "system", f"{old_state} -> {new_state}")
        return agent

    def record_heartbeat(self, agent_id: str, metrics: Optional[dict] = None) -> bool:
        """Record a heartbeat from an agent."""
        agent = self.agents.get(agent_id)
        if not agent:
            return False

        agent.last_heartbeat = datetime.now(timezone.utc).isoformat()
        if metrics:
            self._record_activity(agent_id, "heartbeat", "self", "ok", metrics=metrics)
        return True

    def record_alert(self, agent_id: str, alert_target: str, alert_details: str) -> bool:
        """Record an alert from an agent."""
        agent = self.agents.get(agent_id)
        if not agent:
            return False

        agent.alert_count += 1
        agent.state = AgentState.ALERTING
        self._record_activity(agent_id, "alert", alert_target, alert_details)
        return True

    def get_agent_detail(self, agent_id: str) -> Optional[dict]:
        """Get full detail for a specific agent (drill-down)."""
        agent = self.agents.get(agent_id)
        if not agent:
            return None
        return agent.to_dict()

    def get_agent_activity(self, agent_id: str, limit: int = 50) -> Optional[list]:
        """Get activity log for a specific agent."""
        agent = self.agents.get(agent_id)
        if not agent:
            return None
        activities = agent.activity_log[-limit:]
        return [a.to_dict() if hasattr(a, 'to_dict') else a for a in activities]

    def get_dashboard_snapshot(self) -> DashboardSnapshot:
        """Get a point-in-time snapshot of all agents."""
        by_state = {}
        by_role = {}
        total_alerts = 0

        for agent in self.agents.values():
            state = agent.state.value
            by_state[state] = by_state.get(state, 0) + 1
            by_role[agent.role] = by_role.get(agent.role, 0) + 1
            total_alerts += agent.alert_count

        snapshot = DashboardSnapshot(
            total_agents=len(self.agents),
            agents_by_state=by_state,
            agents_by_role=by_role,
            total_alerts=total_alerts,
            agent_summaries=[a.to_summary() for a in self.agents.values()],
        )
        return snapshot

    def list_agents(self, state_filter: Optional[str] = None, role_filter: Optional[str] = None) -> list[dict]:
        """List agents with optional filtering."""
        results = []
        for agent in self.agents.values():
            if state_filter and agent.state.value != state_filter:
                continue
            if role_filter and agent.role != role_filter:
                continue
            results.append(agent.to_summary())
        return results

    def deregister_agent(self, agent_id: str) -> bool:
        """Deregister an agent from the dashboard."""
        agent = self.agents.get(agent_id)
        if not agent:
            return False

        agent.state = AgentState.TERMINATED
        self._record_activity(agent_id, "deregistered", "system", "Agent removed from dashboard")
        return True

    def _record_activity(
        self,
        agent_id: str,
        action: str,
        target: str,
        result: str,
        metrics: Optional[dict] = None,
        duration_ms: float = 0.0,
    ):
        """Record an activity entry for an agent."""
        agent = self.agents.get(agent_id)
        if not agent:
            return

        activity = AgentActivity(
            action=action,
            target=target,
            result=result,
            metrics=metrics or {},
            duration_ms=duration_ms,
        )
        agent.activity_log.append(activity)

        # Trim activity log if needed
        if len(agent.activity_log) > self.max_activity_per_agent:
            agent.activity_log = agent.activity_log[-self.max_activity_per_agent:]
