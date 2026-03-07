"""
Rosetta Manager — thread-safe CRUD for agent state documents.

Persists each agent's RosettaAgentState as a JSON file under the
configured persistence directory.
"""

from __future__ import annotations

import json
import logging
import re
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional

from .rosetta_models import RosettaAgentState

logger = logging.getLogger(__name__)


class RosettaManager:
    """Thread-safe manager for Rosetta agent state documents."""

    def __init__(self, persistence_dir: str = ".murphy_persistence/rosetta") -> None:
        self._states: Dict[str, RosettaAgentState] = {}
        self._lock = Lock()
        self._persistence_dir = Path(persistence_dir)
        self._persistence_dir.mkdir(parents=True, exist_ok=True)

    # ---- helpers ----

    @staticmethod
    @contextmanager
    def _file_lock(filepath: Path):
        """Acquire an OS-level file lock for cross-process safety."""
        lock_path = filepath.with_suffix(filepath.suffix + ".lock")
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with open(lock_path, "w", encoding="utf-8") as lock_file:
            try:
                if sys.platform == "win32":
                    import msvcrt
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
                else:
                    import fcntl
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
                yield
            finally:
                if sys.platform == "win32":
                    import msvcrt
                    try:
                        msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
                    except OSError:
                        logger.debug("File unlock failed (non-critical)")
                else:
                    import fcntl
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    @staticmethod
    def _sanitize_id(id_str: str) -> str:
        """Sanitize an agent ID to prevent path traversal attacks."""
        if not id_str or not isinstance(id_str, str):
            raise ValueError("ID must be a non-empty string")
        sanitized = re.sub(r'[/\\]', '', id_str)
        while '..' in sanitized:
            sanitized = sanitized.replace('..', '')
        if not re.match(r'^[a-zA-Z0-9_\-][a-zA-Z0-9_\-\.]*$', sanitized):
            raise ValueError(f"Invalid ID format: {id_str!r}")
        return sanitized

    def _filepath(self, agent_id: str) -> Path:
        return self._persistence_dir / f"{agent_id}.json"

    def _write_json(self, filepath: Path, data: Any) -> None:
        """Atomically write JSON data to a file with OS-level file locking."""
        tmp_path = filepath.with_suffix(".tmp")
        with self._file_lock(filepath):
            try:
                with open(tmp_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, default=str)
                tmp_path.replace(filepath)
            except Exception as exc:
                logger.debug("Suppressed exception: %s", exc)
                if tmp_path.exists():
                    tmp_path.unlink()
                raise

    def _read_json(self, filepath: Path) -> Any:
        with self._file_lock(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)

    # ---- public API ----

    def save_state(self, state: RosettaAgentState) -> str:
        """Save agent state to disk and in-memory cache. Returns agent_id."""
        agent_id = self._sanitize_id(state.identity.agent_id)
        state.metadata.updated_at = datetime.now(timezone.utc)
        with self._lock:
            self._states[agent_id] = state
            self._write_json(self._filepath(agent_id), state.model_dump(mode="json"))
        logger.info("Saved Rosetta state for agent %s", agent_id)
        return agent_id

    def load_state(self, agent_id: str) -> Optional[RosettaAgentState]:
        """Load agent state, preferring in-memory cache, falling back to disk."""
        agent_id = self._sanitize_id(agent_id)
        with self._lock:
            if agent_id in self._states:
                return self._states[agent_id]
            filepath = self._filepath(agent_id)
            if not filepath.exists():
                return None
            try:
                data = self._read_json(filepath)
                state = RosettaAgentState.model_validate(data)
                self._states[agent_id] = state
                return state
            except (json.JSONDecodeError, OSError, Exception) as exc:
                logger.error("Failed to load Rosetta state for %s: %s", agent_id, exc)
                return None

    def update_state(
        self, agent_id: str, updates: Dict[str, Any]
    ) -> Optional[RosettaAgentState]:
        """Partial update of an existing agent state. Returns updated state or None."""
        agent_id = self._sanitize_id(agent_id)
        with self._lock:
            state = self._states.get(agent_id)
            if state is None:
                filepath = self._filepath(agent_id)
                if not filepath.exists():
                    return None
                try:
                    data = self._read_json(filepath)
                    state = RosettaAgentState.model_validate(data)
                except Exception as exc:
                    logger.debug("Suppressed exception: %s", exc)
                    return None

            current = state.model_dump(mode="json")
            self._deep_merge(current, updates)
            state = RosettaAgentState.model_validate(current)
            state.metadata.updated_at = datetime.now(timezone.utc)
            self._states[agent_id] = state
            self._write_json(self._filepath(agent_id), state.model_dump(mode="json"))
        return state

    def list_agents(self) -> List[str]:
        """List all agent IDs with saved states."""
        with self._lock:
            on_disk = {p.stem for p in self._persistence_dir.glob("*.json")}
            in_memory = set(self._states.keys())
            return sorted(on_disk | in_memory)

    def delete_state(self, agent_id: str) -> bool:
        """Delete agent state from memory and disk."""
        agent_id = self._sanitize_id(agent_id)
        with self._lock:
            self._states.pop(agent_id, None)
            filepath = self._filepath(agent_id)
            if filepath.exists():
                filepath.unlink()
                logger.info("Deleted Rosetta state for agent %s", agent_id)
                return True
            return False

    def aggregate(self) -> Dict[str, Any]:
        """Aggregate state across all agents."""
        agents = self.list_agents()
        total_goals = 0
        total_tasks = 0
        statuses: Dict[str, int] = {}
        for aid in agents:
            state = self.load_state(aid)
            if state is None:
                continue
            total_goals += len(state.agent_state.active_goals)
            total_tasks += len(state.agent_state.task_queue)
            sys_status = state.system_state.status
            statuses[sys_status] = statuses.get(sys_status, 0) + 1
        return {
            "total_agents": len(agents),
            "total_goals": total_goals,
            "total_tasks": total_tasks,
            "system_statuses": statuses,
        }

    def get_status(self) -> Dict[str, Any]:
        """Get manager status."""
        with self._lock:
            return {
                "persistence_dir": str(self._persistence_dir),
                "agents_in_memory": len(self._states),
                "agents_on_disk": len(list(self._persistence_dir.glob("*.json"))),
            }

    # ---- internal ----

    @staticmethod
    def _deep_merge(base: Dict[str, Any], overrides: Dict[str, Any]) -> None:
        """Recursively merge *overrides* into *base* (mutates base)."""
        for key, value in overrides.items():
            if (
                key in base
                and isinstance(base[key], dict)
                and isinstance(value, dict)
            ):
                RosettaManager._deep_merge(base[key], value)
            else:
                base[key] = value
