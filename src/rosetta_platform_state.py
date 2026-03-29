# © 2020 Inoni Limited Liability Company by Corey Post — License: BSL 1.1
"""
Rosetta Platform State — Murphy System
========================================

Three-layer Rosetta state system providing a consistent, copyable view of the
entire Murphy System's cognitive state:

  Layer 1 — PlatformRosettaState  (singleton)
    The single global state of the whole Murphy platform.
    Tracks: platform health, global goals, system-wide calibrations,
    active room brains, routing statistics.

  Layer 2 — AgentRosettaState  (per agent, in src/rosetta/rosetta_manager.py)
    Per-agent state documents: identity, goals, tasks, automation progress.
    Already implemented — this module provides a read adapter only.

  Layer 3 — CombinedRosettaView  (computed)
    Aggregates Layer 1 + all Layer 2 agents into a unified snapshot.
    Used by founder-update reports, HITL dashboards, and calibration sync.

Copy system
-----------
Each layer supports:
  ``snapshot()`` — capture a point-in-time immutable copy
  ``restore(snapshot)`` — revert the layer to a previous snapshot
  ``sync_up()`` — push agent state deltas up to platform state
  ``sync_down()`` — push platform calibrations down to agents

Design:  RPS-001
Owner:   Platform AI / State Management
License: BSL 1.1
Copyright © 2020 Inoni Limited Liability Company — Created by Corey Post
"""

from __future__ import annotations

import copy
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Platform-level state model
# ---------------------------------------------------------------------------

@dataclass
class PlatformCalibration:
    """A single world-knowledge calibration anchor at platform level."""

    sensor_id: str
    value: float
    confidence: float = 1.0
    unit: str = ""
    domain: str = ""
    last_updated: float = field(default_factory=time.time)


@dataclass
class PlatformGoal:
    """A platform-wide goal (above individual agent goals)."""

    goal_id: str
    title: str
    description: str = ""
    progress_percent: float = 0.0
    owner_agent: str = "murphy-system"
    created_at: float = field(default_factory=time.time)


@dataclass
class PlatformRosettaState:
    """
    Singleton platform-level state document.

    This is the Layer 1 of the Rosetta system — it holds state that
    spans all agents, all rooms, and all subsystems.
    """

    platform_id: str = "murphy-system"
    version: str = "1.0.0"
    status: str = "idle"                           # idle | active | degraded | error
    uptime_seconds: float = 0.0
    active_rooms: List[str] = field(default_factory=list)
    active_agents: List[str] = field(default_factory=list)
    calibrations: List[PlatformCalibration] = field(default_factory=list)
    global_goals: List[PlatformGoal] = field(default_factory=list)
    room_brain_count: int = 0
    routing_stats: Dict[str, Any] = field(default_factory=dict)
    mfgc_threshold: float = 0.85
    last_heartbeat: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "platform_id":      self.platform_id,
            "version":          self.version,
            "status":           self.status,
            "uptime_seconds":   self.uptime_seconds,
            "active_rooms":     self.active_rooms,
            "active_agents":    self.active_agents,
            "calibration_count":len(self.calibrations),
            "goal_count":       len(self.global_goals),
            "room_brain_count": self.room_brain_count,
            "routing_stats":    self.routing_stats,
            "mfgc_threshold":   self.mfgc_threshold,
            "last_heartbeat":   self.last_heartbeat,
        }


# ---------------------------------------------------------------------------
# Snapshot — immutable point-in-time copy
# ---------------------------------------------------------------------------

@dataclass
class RosettaSnapshot:
    """Immutable point-in-time copy of any Rosetta layer."""

    snapshot_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    layer: str = ""                        # "platform" | "agent:<id>" | "combined"
    captured_at: float = field(default_factory=time.time)
    data: Dict[str, Any] = field(default_factory=dict)

    @property
    def age_seconds(self) -> float:
        return time.time() - self.captured_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id":  self.snapshot_id,
            "layer":        self.layer,
            "captured_at":  datetime.fromtimestamp(self.captured_at, tz=timezone.utc).isoformat(),
            "age_seconds":  self.age_seconds,
            "data":         self.data,
        }


# ---------------------------------------------------------------------------
# Combined view — Layer 3
# ---------------------------------------------------------------------------

@dataclass
class CombinedRosettaView:
    """
    Aggregated view of platform state + all agent states.

    Produced by :meth:`RosettaPlatformManager.combined_view`.
    """

    platform: Dict[str, Any] = field(default_factory=dict)
    agents: Dict[str, Any] = field(default_factory=dict)
    coherence_score: float = 0.0    # 0–1: how aligned agents are with platform
    agent_count: int = 0
    total_active_tasks: int = 0
    avg_goal_progress: float = 0.0
    calibration_count: int = 0
    generated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "platform":           self.platform,
            "agent_count":        self.agent_count,
            "coherence_score":    round(self.coherence_score, 4),
            "total_active_tasks": self.total_active_tasks,
            "avg_goal_progress":  round(self.avg_goal_progress, 2),
            "calibration_count":  self.calibration_count,
            "generated_at":       datetime.fromtimestamp(self.generated_at, tz=timezone.utc).isoformat(),
        }


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------

class RosettaPlatformManager:
    """
    Manages the three-layer Rosetta state system.

    Thread-safe.  Provides snapshot, restore, sync_up, sync_down operations
    for each layer.

    Usage::

        mgr = RosettaPlatformManager()
        mgr.update_platform(status="active", active_agents=["agent-1", "agent-2"])

        snap = mgr.snapshot_platform()          # Layer 1 snapshot
        view = mgr.combined_view()              # Layer 3 combined
        mgr.restore_platform(snap)              # Restore Layer 1
    """

    def __init__(self, rosetta_manager: Optional[Any] = None) -> None:
        self._lock       = threading.Lock()
        self._platform   = PlatformRosettaState()
        self._snapshots: List[RosettaSnapshot] = []
        self._start_time = time.time()
        # Layer 2 adapter — optional RosettaManager from src/rosetta/
        self._agent_mgr  = rosetta_manager

    # ------------------------------------------------------------------
    # Platform state (Layer 1)
    # ------------------------------------------------------------------

    def update_platform(self, **kwargs: Any) -> None:
        """Update fields of the platform state."""
        with self._lock:
            for k, v in kwargs.items():
                if hasattr(self._platform, k):
                    setattr(self._platform, k, v)
            self._platform.uptime_seconds = time.time() - self._start_time
            self._platform.last_heartbeat = time.time()

    def get_platform(self) -> PlatformRosettaState:
        """Return a shallow copy of the current platform state."""
        with self._lock:
            return copy.copy(self._platform)

    def add_calibration(self, sensor_id: str, value: float, **kwargs: Any) -> None:
        """Add or update a platform-level calibration anchor."""
        with self._lock:
            for cal in self._platform.calibrations:
                if cal.sensor_id == sensor_id:
                    cal.value = value
                    cal.last_updated = time.time()
                    for k, v in kwargs.items():
                        if hasattr(cal, k):
                            setattr(cal, k, v)
                    return
            self._platform.calibrations.append(
                PlatformCalibration(sensor_id=sensor_id, value=value, **kwargs)
            )

    def add_goal(self, title: str, description: str = "", owner_agent: str = "murphy-system") -> str:
        """Add a platform-level goal. Returns goal_id."""
        goal = PlatformGoal(
            goal_id     = str(uuid.uuid4()),
            title       = title,
            description = description,
            owner_agent = owner_agent,
        )
        with self._lock:
            self._platform.global_goals.append(goal)
        return goal.goal_id

    # ------------------------------------------------------------------
    # Snapshot / restore
    # ------------------------------------------------------------------

    def snapshot_platform(self) -> RosettaSnapshot:
        """Capture an immutable snapshot of the platform state (Layer 1)."""
        with self._lock:
            snap = RosettaSnapshot(
                layer="platform",
                data=self._platform.to_dict(),
            )
            self._snapshots.append(snap)
            if len(self._snapshots) > 100:
                del self._snapshots[:10]
        return snap

    def restore_platform(self, snapshot: RosettaSnapshot) -> None:
        """Restore platform state from *snapshot*."""
        if snapshot.layer != "platform":
            raise ValueError(f"Snapshot layer is '{snapshot.layer}', expected 'platform'")
        with self._lock:
            data = snapshot.data
            for k, v in data.items():
                if hasattr(self._platform, k):
                    setattr(self._platform, k, v)
        logger.info("Platform state restored from snapshot %s", snapshot.snapshot_id)

    def list_snapshots(self) -> List[RosettaSnapshot]:
        """Return all stored snapshots, newest first."""
        with self._lock:
            return list(reversed(self._snapshots))

    # ------------------------------------------------------------------
    # Agent state (Layer 2) — read adapter
    # ------------------------------------------------------------------

    def list_agents(self) -> List[str]:
        """Return all known agent IDs from Layer 2."""
        if self._agent_mgr is None:
            return list(self._platform.active_agents)
        try:
            return self._agent_mgr.list_agents()
        except Exception:
            return []

    def get_agent_state(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Return the state dict for *agent_id* (Layer 2), or ``None``."""
        if self._agent_mgr is None:
            return None
        try:
            state = self._agent_mgr.load_state(agent_id)
            if state is None:
                return None
            return state.model_dump() if hasattr(state, "model_dump") else dict(state)
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Sync operations
    # ------------------------------------------------------------------

    def sync_up(self, agent_id: str) -> bool:
        """
        Push agent state deltas up to platform state.

        Updates:
          - active_agents list
          - total task count
          - calibration anchors (if the agent carries any)
        """
        state = self.get_agent_state(agent_id)
        if state is None:
            return False

        with self._lock:
            if agent_id not in self._platform.active_agents:
                self._platform.active_agents.append(agent_id)
            # Absorb any calibrations the agent knows about
            for cal in state.get("calibrations", []):
                sid = cal.get("sensor_id") or cal.get("id")
                val = cal.get("value")
                if sid and val is not None:
                    self.add_calibration(str(sid), float(val))
        logger.debug("sync_up: agent '%s' synced to platform state", agent_id)
        return True

    def sync_down(self, agent_id: str) -> bool:
        """
        Push platform calibrations down to an agent.

        Calls ``RosettaManager.save_state()`` with updated calibration fields.
        """
        if self._agent_mgr is None:
            return False
        try:
            state = self._agent_mgr.load_state(agent_id)
            if state is None:
                return False
            with self._lock:
                cals = [
                    {"sensor_id": c.sensor_id, "value": c.value,
                     "confidence": c.confidence, "domain": c.domain}
                    for c in self._platform.calibrations
                ]
            if hasattr(state, "metadata"):
                # Metadata is a Pydantic model — use the extras dict
                if hasattr(state.metadata, "extras"):
                    state.metadata.extras["platform_calibrations"] = cals
                elif isinstance(state.metadata, dict):
                    state.metadata["platform_calibrations"] = cals
            self._agent_mgr.save_state(state)
            logger.debug("sync_down: platform calibrations pushed to agent '%s'", agent_id)
            return True
        except Exception as exc:
            logger.warning("sync_down failed for '%s': %s", agent_id, exc)
            return False

    # ------------------------------------------------------------------
    # Combined view (Layer 3)
    # ------------------------------------------------------------------

    def combined_view(self) -> CombinedRosettaView:
        """
        Build the Layer 3 combined view: platform + all agents.

        Computes a coherence score: proportion of agents whose status
        matches the platform status.
        """
        agents = self.list_agents()
        agent_data: Dict[str, Any] = {}
        active_tasks = 0
        goal_progress_sum = 0.0
        goal_count = 0
        coherent = 0

        for aid in agents:
            state = self.get_agent_state(aid)
            if state is None:
                continue
            agent_data[aid] = state

            # Count active tasks
            sys_state = state.get("system_state", {})
            active_tasks += sys_state.get("active_tasks", 0)

            # Check coherence: agent's status matches platform
            if sys_state.get("status") == self._platform.status:
                coherent += 1

            # Average goal progress
            for goal in state.get("agent_state", {}).get("active_goals", []):
                goal_progress_sum += goal.get("progress_percent", 0)
                goal_count += 1

        coherence = coherent / len(agents) if agents else 1.0

        with self._lock:
            platform_dict = self._platform.to_dict()
            cal_count = len(self._platform.calibrations)

        return CombinedRosettaView(
            platform          = platform_dict,
            agents            = agent_data,
            coherence_score   = coherence,
            agent_count       = len(agents),
            total_active_tasks= active_tasks,
            avg_goal_progress = goal_progress_sum / goal_count if goal_count else 0.0,
            calibration_count = cal_count,
        )

    def snapshot_combined(self) -> RosettaSnapshot:
        """Capture an immutable snapshot of the combined view (Layer 3)."""
        view = self.combined_view()
        snap = RosettaSnapshot(layer="combined", data=view.to_dict())
        with self._lock:
            self._snapshots.append(snap)
        return snap


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_default_manager: Optional[RosettaPlatformManager] = None
_mgr_lock = threading.Lock()


def get_platform_manager(rosetta_manager: Optional[Any] = None) -> RosettaPlatformManager:
    """Return (and lazily create) the default :class:`RosettaPlatformManager`."""
    global _default_manager
    with _mgr_lock:
        if _default_manager is None:
            _default_manager = RosettaPlatformManager(rosetta_manager=rosetta_manager)
    return _default_manager


__all__ = [
    "PlatformCalibration",
    "PlatformGoal",
    "PlatformRosettaState",
    "RosettaSnapshot",
    "CombinedRosettaView",
    "RosettaPlatformManager",
    "get_platform_manager",
]
