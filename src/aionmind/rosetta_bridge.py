"""
AionMind ↔ Rosetta Persistence Bridge — PATCH-063
Copyright 2020 Inoni LLC | License: BSL 1.1

Every Murphy cognitive_execute session writes its context, decisions,
and outcomes into a RosettaAgentState that survives restarts.

On boot: loads all existing agent states from disk into AionMind memory.
On each call: updates the agent's state with the latest session.
Shadow agents accumulate workflow_patterns here as learned memory.

Label: ROSETTA-AION-001
"""

from __future__ import annotations

import json
import logging
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_PERSISTENCE_DIR = "/var/lib/murphy-production/rosetta_agents"
_BRIDGE_LOCK = threading.Lock()


def _get_rosetta_manager():
    try:
        from src.rosetta.rosetta_manager import RosettaManager
        return RosettaManager(persistence_dir=_PERSISTENCE_DIR)
    except Exception as exc:
        logger.warning("ROSETTA-AION-001: RosettaManager unavailable: %s", exc)
        return None


def _get_or_create_agent_state(agent_id: str, role: str = "aionmind", manager=None):
    """Load existing state from disk or create a fresh one."""
    try:
        from src.rosetta.rosetta_models import (
            RosettaAgentState, Identity, SystemState, Metadata,
        )
        from src.rosetta.rosetta_manager import RosettaManager

        mgr = manager or _get_rosetta_manager()
        if mgr is None:
            return None, None

        state = mgr.load_state(agent_id)
        if state is None:
            # Create fresh state
            state = RosettaAgentState(
                identity=Identity(agent_id=agent_id, name=agent_id, role=role),
                system_state=SystemState(status="active"),
                metadata=Metadata(),
            )
        return state, mgr
    except Exception as exc:
        logger.warning("ROSETTA-AION-001: _get_or_create_agent_state failed: %s", exc)
        return None, None


def record_session_to_rosetta(
    agent_id: str,
    session_id: str,
    raw_input: str,
    intent: str,
    task_type: str,
    status: str,
    result_summary: str,
    tokens_in: int = 0,
    tokens_out: int = 0,
    tool_calls: Optional[List[Dict]] = None,
    actor: Optional[str] = None,
) -> bool:
    """
    Write a completed AionMind session into the agent's RosettaAgentState.
    Returns True on success.
    Label: ROSETTA-AION-002
    """
    with _BRIDGE_LOCK:
        try:
            state, mgr = _get_or_create_agent_state(agent_id)
            if state is None:
                return False

            # Build a workflow pattern entry (reuses existing Rosetta schema)
            try:
                import json as _json
                from src.rosetta.rosetta_models import WorkflowPattern
                # Encode session into actual WorkflowPattern schema fields
                # name = "[task_type] intent" (searchable description)
                # steps = serialized session data (JSON strings)
                session_data = _json.dumps({
                    "raw_input": raw_input[:500],
                    "status": status,
                    "result_summary": result_summary[:500],
                    "tokens_in": tokens_in,
                    "tokens_out": tokens_out,
                    "tool_calls": tool_calls or [],
                    "actor": actor,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }, default=str)
                pattern = WorkflowPattern(
                    pattern_id=session_id,
                    name=f"[{task_type}] {(intent or raw_input)[:200]}",
                    steps=[session_data],
                    success_rate=0.9 if status == "completed" else 0.3,
                    avg_duration_seconds=0.0,
                    usage_count=1,
                )
                # Append to workflow_patterns (cap at 500 entries)
                state.workflow_patterns = (state.workflow_patterns or [])
                state.workflow_patterns.append(pattern)
                if len(state.workflow_patterns) > 500:
                    state.workflow_patterns = state.workflow_patterns[-500:]
            except Exception as exc:
                logger.warning("WorkflowPattern build failed: %s", exc)

            # Update system state
            try:
                state.system_state.status = "active"
                state.system_state.last_heartbeat = datetime.now(timezone.utc)
            except Exception:
                pass

            mgr.save_state(state)
            logger.debug("ROSETTA-AION-002: session %s saved for agent %s", session_id, agent_id)
            return True

        except Exception as exc:
            logger.warning("ROSETTA-AION-002: record_session_to_rosetta failed: %s", exc)
            return False


def load_agent_memory(agent_id: str, last_n: int = 20) -> List[Dict]:
    """
    Retrieve the last N workflow patterns (sessions) for an agent from Rosetta.
    Used to inject prior context into AionMind before a new session.
    Label: ROSETTA-AION-003
    """
    try:
        state, _ = _get_or_create_agent_state(agent_id)
        if state is None or not state.workflow_patterns:
            return []
        patterns = state.workflow_patterns[-last_n:]
        import json as _json
        out = []
        for p in patterns:
            try:
                session_data = _json.loads(p.steps[0]) if p.steps else {}
            except Exception:
                session_data = {}
            out.append({
                "session_id": p.pattern_id,
                "description": p.name,
                "status": session_data.get("status", "unknown"),
                "result": session_data.get("result_summary", ""),
                "tool_calls": session_data.get("tool_calls", []),
                "timestamp": session_data.get("timestamp", ""),
            })
        return out
    except Exception as exc:
        logger.warning("ROSETTA-AION-003: load_agent_memory failed: %s", exc)
        return []


def boot_load_all_agents() -> int:
    """
    On system boot: scan Rosetta persistence dir, load all agent states into memory.
    Returns count of agents restored.
    Label: ROSETTA-AION-004
    """
    try:
        mgr = _get_rosetta_manager()
        if mgr is None:
            return 0
        p = Path(_PERSISTENCE_DIR)
        if not p.exists():
            return 0
        count = 0
        for f in p.glob("*.json"):
            agent_id = f.stem
            try:
                state = mgr.load_state(agent_id)
                if state:
                    count += 1
            except Exception as exc:
                logger.debug("boot_load: skip %s: %s", agent_id, exc)
        logger.info("ROSETTA-AION-004: Restored %d agent states from disk", count)
        return count
    except Exception as exc:
        logger.warning("ROSETTA-AION-004: boot_load_all_agents failed: %s", exc)
        return 0


def list_all_agents() -> List[Dict]:
    """Return summary of all persisted agents."""
    try:
        mgr = _get_rosetta_manager()
        if mgr is None:
            return []
        p = Path(_PERSISTENCE_DIR)
        if not p.exists():
            return []
        results = []
        for f in p.glob("*.json"):
            try:
                state = mgr.load_state(f.stem)
                if state:
                    results.append({
                        "agent_id": state.identity.agent_id,
                        "name": state.identity.name,
                        "role": state.identity.role,
                        "sessions": len(state.workflow_patterns or []),
                        "status": state.system_state.status if state.system_state else "unknown",
                        "last_seen": str(state.system_state.last_heartbeat) if state.system_state else None,
                    })
            except Exception:
                pass
        return results
    except Exception as exc:
        logger.warning("list_all_agents failed: %s", exc)
        return []
