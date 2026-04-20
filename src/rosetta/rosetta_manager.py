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

from .rosetta_models import (
    AutomationProgress,
    Identity,
    ImprovementProposal,
    RosettaAgentState,
    SystemState,
    WorkflowPattern,
)

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

    # ---- P3 wiring helpers ----

    def update_after_task(
        self,
        agent_id: str,
        patterns: List[Dict[str, Any]],
    ) -> Optional[RosettaAgentState]:
        """P3-001: Merge improvement patterns from SelfImprovementEngine into agent state.

        Converts raw pattern dicts (from ``SelfImprovementEngine.extract_patterns()``)
        into ``WorkflowPattern`` entries and upserts them on the agent's state document.
        Creates a minimal state for the agent if one does not yet exist.

        Args:
            agent_id: The agent whose state should be updated.
            patterns: List of pattern dicts as returned by
                ``SelfImprovementEngine.extract_patterns()``.

        Returns:
            The updated ``RosettaAgentState``, or ``None`` on error.
        """
        if not patterns:
            return self.load_state(agent_id)

        try:
            agent_id = self._sanitize_id(agent_id)
        except ValueError as exc:
            logger.warning("update_after_task: invalid agent_id %r — %s", agent_id, exc)
            return None

        with self._lock:
            state = self._states.get(agent_id)
            if state is None:
                filepath = self._filepath(agent_id)
                if filepath.exists():
                    try:
                        state = RosettaAgentState.model_validate(self._read_json(filepath))
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("update_after_task: failed to load %s — %s", agent_id, exc)
                        state = None
                if state is None:
                    state = RosettaAgentState(
                        identity=Identity(agent_id=agent_id, name=agent_id)
                    )

            existing_ids = {wp.pattern_id for wp in state.workflow_patterns}
            for p in patterns:
                pid = p.get("pattern_id", "")
                if not pid or pid in existing_ids:
                    continue
                try:
                    wp = WorkflowPattern(
                        pattern_id=pid,
                        name=p.get("type", "unknown"),
                        steps=p.get("sample_task_ids", []),
                        success_rate=1.0 if p.get("type") == "success_pattern" else 0.0,
                        avg_duration_seconds=float(p.get("avg_duration", 0.0)),
                        usage_count=int(p.get("occurrences", 0)),
                    )
                    state.workflow_patterns.append(wp)
                    existing_ids.add(pid)
                except Exception as exc:  # noqa: BLE001
                    logger.debug("update_after_task: skipping malformed pattern %r — %s", pid, exc)

            state.metadata.updated_at = datetime.now(timezone.utc)
            self._states[agent_id] = state
            try:
                self._write_json(self._filepath(agent_id), state.model_dump(mode="json"))
            except Exception as exc:  # noqa: BLE001
                logger.warning("update_after_task: persistence write failed — %s", exc)

        logger.debug("update_after_task: merged %d patterns for agent %s", len(patterns), agent_id)
        return state

    def save_agent_doc(
        self,
        agent_id: str,
        rag: Any,
        content: Optional[str] = None,
    ) -> Dict[str, Any]:
        """P3-003: Ingest the agent state document into the RAG vector store.

        Serialises the current ``RosettaAgentState`` to JSON (or uses the supplied
        *content* string) and calls ``rag.ingest_document()`` so that downstream
        retrieval-augmented generation can query agent knowledge.

        Args:
            agent_id: The agent whose document should be ingested.
            rag: A ``RAGVectorIntegration`` instance (or compatible duck-type).
            content: Optional pre-serialised content string. If omitted, the
                current state is serialised automatically.

        Returns:
            The dict returned by ``rag.ingest_document()``, or an error dict.
        """
        try:
            agent_id = self._sanitize_id(agent_id)
        except ValueError as exc:
            logger.warning("save_agent_doc: invalid agent_id %r — %s", agent_id, exc)
            return {"status": "error", "message": str(exc)}

        if content is None:
            state = self.load_state(agent_id)
            if state is None:
                return {"status": "error", "message": f"agent {agent_id!r} not found"}
            try:
                content = json.dumps(state.model_dump(mode="json"), indent=2, default=str)
            except Exception as exc:  # noqa: BLE001
                logger.warning("save_agent_doc: serialisation failed — %s", exc)
                return {"status": "error", "message": str(exc)}

        try:
            result = rag.ingest_document(
                text=content,
                title=f"rosetta:{agent_id}",
                source="rosetta_state_manager",
                metadata={"agent_id": agent_id, "type": "rosetta_agent_state"},
            )
            logger.info("save_agent_doc: ingested doc for agent %s → %s", agent_id, result.get("status"))
            return result
        except Exception as exc:  # noqa: BLE001
            logger.warning("save_agent_doc: rag.ingest_document failed — %s", exc)
            return {"status": "error", "message": str(exc)}

    def sync_system_state(
        self,
        agent_id: str,
        system_state: "SystemState",
    ) -> Optional[RosettaAgentState]:
        """P3-005: Push a ``SystemState`` delta into the Rosetta document.

        Replaces the ``system_state`` field of the agent's document with the
        provided snapshot and persists the change.

        Args:
            agent_id: The agent whose system state should be updated.
            system_state: A ``SystemState`` model instance with the new values.

        Returns:
            The updated ``RosettaAgentState``, or ``None`` on error.
        """
        try:
            agent_id = self._sanitize_id(agent_id)
        except ValueError as exc:
            logger.warning("sync_system_state: invalid agent_id %r — %s", agent_id, exc)
            return None

        updates = {"system_state": system_state.model_dump(mode="json")}
        return self.update_state(agent_id, updates)

    def sync_automation_progress(
        self,
        agent_id: str,
        category: str,
        completed: int,
        total: int,
    ) -> Optional[RosettaAgentState]:
        """P3-002: Upsert an ``AutomationProgress`` entry for an orchestrator cycle.

        Finds an existing entry for *category* in the agent's
        ``automation_progress`` list (or appends a new one) and updates the
        completed/total counts and coverage percentage.

        Args:
            agent_id: Target agent identifier.
            category: Automation category label (e.g. ``"self_improvement"``).
            completed: Number of completed workflow items.
            total: Total workflow items in the category.

        Returns:
            Updated ``RosettaAgentState`` or ``None`` on error.
        """
        try:
            agent_id = self._sanitize_id(agent_id)
        except ValueError as exc:
            logger.warning("sync_automation_progress: invalid agent_id %r — %s", agent_id, exc)
            return None

        with self._lock:
            state = self._states.get(agent_id)
            if state is None:
                filepath = self._filepath(agent_id)
                if filepath.exists():
                    try:
                        state = RosettaAgentState.model_validate(self._read_json(filepath))
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("sync_automation_progress: load failed — %s", exc)
                        state = None
                if state is None:
                    state = RosettaAgentState(
                        identity=Identity(agent_id=agent_id, name=agent_id)
                    )

            coverage = (completed / total * 100.0) if total > 0 else 0.0
            matched = next((ap for ap in state.automation_progress if ap.category == category), None)
            if matched is not None:
                matched.completed_items = completed
                matched.total_items = total
                matched.coverage_percent = coverage
                matched.last_updated = datetime.now(timezone.utc)
            else:
                state.automation_progress.append(
                    AutomationProgress(
                        category=category,
                        total_items=total,
                        completed_items=completed,
                        coverage_percent=coverage,
                    )
                )

            state.metadata.updated_at = datetime.now(timezone.utc)
            self._states[agent_id] = state
            try:
                self._write_json(self._filepath(agent_id), state.model_dump(mode="json"))
            except Exception as exc:  # noqa: BLE001
                logger.warning("sync_automation_progress: write failed — %s", exc)

        return state

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
