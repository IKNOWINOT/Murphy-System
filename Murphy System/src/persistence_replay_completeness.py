"""
PERSISTENCE + REPLAY COMPLETENESS MODULE FOR MURPHY SYSTEM

Drives persistence and replay capability to 100% by providing:
1. Full replay orchestration with configurable speed/pause/step-through
2. State snapshots — create, restore, and compare full system state
3. Point-in-time recovery — restore to any previous timestamp
4. Write-ahead log (WAL) — crash recovery via pre-execution logging
5. Snapshot diffing — compare any two snapshots for changes

Complements persistence_manager.py (durable JSON storage) and
golden_path_bridge.py (path capture/replay).

Owner: INONI LLC / Corey Post
Contact: corey.gfc@gmail.com
Repository: https://github.com/IKNOWINOT/Murphy-System
"""

import copy
import json
import logging
import os
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)

# ================================================================
# Constants
# ================================================================

DEFAULT_WAL_DIR = ".murphy_persistence/wal"
DEFAULT_SNAPSHOT_DIR = ".murphy_persistence/snapshots"

WAL_STATUS_PENDING = "pending"
WAL_STATUS_COMMITTED = "committed"
WAL_STATUS_ROLLED_BACK = "rolled_back"


# ================================================================
# Enums
# ================================================================

class ReplayMode(str, Enum):
    """Execution mode for replay orchestration."""
    CONTINUOUS = "continuous"
    STEP = "step"
    TIMED = "timed"


class ReplayState(str, Enum):
    """Current state of a replay session."""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


# ================================================================
# Data classes
# ================================================================

@dataclass
class WALEntry:
    """A single write-ahead log entry."""
    entry_id: str
    operation: str
    timestamp: float
    data: Dict[str, Any] = field(default_factory=dict)
    status: str = WAL_STATUS_PENDING
    result: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "WALEntry":
        """Create from dictionary."""
        return cls(
            entry_id=d.get("entry_id", ""),
            operation=d.get("operation", ""),
            timestamp=d.get("timestamp", 0.0),
            data=d.get("data", {}),
            status=d.get("status", WAL_STATUS_PENDING),
            result=d.get("result"),
        )


@dataclass
class StateSnapshot:
    """A full system state snapshot at a point in time."""
    snapshot_id: str
    timestamp: float
    label: str
    state: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "StateSnapshot":
        """Create from dictionary."""
        return cls(
            snapshot_id=d.get("snapshot_id", ""),
            timestamp=d.get("timestamp", 0.0),
            label=d.get("label", ""),
            state=d.get("state", {}),
            metadata=d.get("metadata", {}),
        )


@dataclass
class ReplayStep:
    """One step in a replay sequence."""
    step_index: int
    event: Dict[str, Any]
    executed: bool = False
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


# ================================================================
# Write-Ahead Log
# ================================================================

class WriteAheadLog:
    """Write-ahead log ensuring crash recovery.

    Every operation is logged *before* execution. On crash, pending
    entries can be inspected and either replayed or rolled back.
    Thread-safe via a dedicated lock.
    """

    def __init__(self, wal_dir: Optional[str] = None) -> None:
        self._wal_dir = Path(wal_dir or DEFAULT_WAL_DIR)
        self._wal_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._entries: List[WALEntry] = []
        self._load_existing()
        logger.info("WriteAheadLog initialized at %s", self._wal_dir)

    # -------------------- internal helpers --------------------

    def _wal_file(self) -> Path:
        return self._wal_dir / "wal.json"

    def _flush(self) -> None:
        """Atomically write the full WAL to disk."""
        data = [e.to_dict() for e in self._entries]
        tmp = self._wal_file().with_suffix(".tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)
            tmp.replace(self._wal_file())
        except Exception as exc:
            logger.debug("Suppressed exception: %s", exc)
            if tmp.exists():
                tmp.unlink()
            raise

    def _load_existing(self) -> None:
        """Load WAL from disk if present."""
        wal_file = self._wal_file()
        if wal_file.exists():
            try:
                with open(wal_file, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                self._entries = [WALEntry.from_dict(e) for e in raw]
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("WAL load failed, starting fresh: %s", exc)
                self._entries = []

    # -------------------- public API --------------------

    def log_operation(self, operation: str, data: Dict[str, Any]) -> str:
        """Log an operation before executing it.

        Args:
            operation: Name of the operation (e.g. ``"save_document"``).
            data: Serializable payload describing the operation.

        Returns:
            The unique ``entry_id`` for this WAL record.
        """
        entry = WALEntry(
            entry_id=str(uuid.uuid4()),
            operation=operation,
            timestamp=time.time(),
            data=data,
            status=WAL_STATUS_PENDING,
        )
        with self._lock:
            capped_append(self._entries, entry)
            self._flush()
        logger.debug("WAL logged operation %s (%s)", entry.entry_id, operation)
        return entry.entry_id

    def commit(self, entry_id: str, result: Optional[Dict[str, Any]] = None) -> bool:
        """Mark a WAL entry as committed after successful execution.

        Args:
            entry_id: ID returned by :meth:`log_operation`.
            result: Optional result data to attach.

        Returns:
            ``True`` if committed, ``False`` if entry not found.
        """
        with self._lock:
            for entry in self._entries:
                if entry.entry_id == entry_id:
                    entry.status = WAL_STATUS_COMMITTED
                    entry.result = result
                    self._flush()
                    logger.debug("WAL committed %s", entry_id)
                    return True
        return False

    def rollback(self, entry_id: str) -> bool:
        """Mark a WAL entry as rolled back.

        Args:
            entry_id: ID returned by :meth:`log_operation`.

        Returns:
            ``True`` if rolled back, ``False`` if entry not found.
        """
        with self._lock:
            for entry in self._entries:
                if entry.entry_id == entry_id:
                    entry.status = WAL_STATUS_ROLLED_BACK
                    self._flush()
                    logger.debug("WAL rolled back %s", entry_id)
                    return True
        return False

    def get_pending(self) -> List[Dict[str, Any]]:
        """Return all entries still in ``pending`` state.

        These represent operations that were logged but never
        committed or rolled back — i.e. potential crash survivors.
        """
        with self._lock:
            return [e.to_dict() for e in self._entries if e.status == WAL_STATUS_PENDING]

    def get_all_entries(self) -> List[Dict[str, Any]]:
        """Return every WAL entry as a list of dicts."""
        with self._lock:
            return [e.to_dict() for e in self._entries]

    def clear_committed(self) -> int:
        """Remove all committed entries from the WAL.

        Returns:
            Number of entries removed.
        """
        with self._lock:
            before = len(self._entries)
            self._entries = [e for e in self._entries if e.status != WAL_STATUS_COMMITTED]
            removed = before - len(self._entries)
            self._flush()
        logger.info("WAL cleared %d committed entries", removed)
        return removed

    def get_status(self) -> Dict[str, Any]:
        """Return WAL status summary."""
        with self._lock:
            total = len(self._entries)
            pending = sum(1 for e in self._entries if e.status == WAL_STATUS_PENDING)
            committed = sum(1 for e in self._entries if e.status == WAL_STATUS_COMMITTED)
            rolled_back = sum(1 for e in self._entries if e.status == WAL_STATUS_ROLLED_BACK)
        return {
            "wal_dir": str(self._wal_dir),
            "total_entries": total,
            "pending": pending,
            "committed": committed,
            "rolled_back": rolled_back,
        }


# ================================================================
# Snapshot Manager
# ================================================================

class SnapshotManager:
    """Create, restore, compare, and diff state snapshots.

    Snapshots are stored as JSON files on disk and kept in an
    in-memory index for fast access.  Thread-safe.
    """

    def __init__(self, snapshot_dir: Optional[str] = None) -> None:
        self._snapshot_dir = Path(snapshot_dir or DEFAULT_SNAPSHOT_DIR)
        self._snapshot_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._snapshots: Dict[str, StateSnapshot] = {}
        self._load_existing()
        logger.info("SnapshotManager initialized at %s", self._snapshot_dir)

    # -------------------- internal helpers --------------------

    def _snapshot_file(self, snapshot_id: str) -> Path:
        return self._snapshot_dir / f"{snapshot_id}.json"

    def _write_snapshot(self, snapshot: StateSnapshot) -> None:
        """Atomically persist a snapshot to disk."""
        filepath = self._snapshot_file(snapshot.snapshot_id)
        tmp = filepath.with_suffix(".tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(snapshot.to_dict(), f, indent=2, default=str)
            tmp.replace(filepath)
        except Exception as exc:
            logger.debug("Suppressed exception: %s", exc)
            if tmp.exists():
                tmp.unlink()
            raise

    def _load_existing(self) -> None:
        """Load all snapshots from disk into the in-memory index."""
        for path in self._snapshot_dir.glob("*.json"):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                snap = StateSnapshot.from_dict(raw)
                self._snapshots[snap.snapshot_id] = snap
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Skipping corrupt snapshot %s: %s", path.name, exc)

    # -------------------- public API --------------------

    def create_snapshot(
        self,
        state: Dict[str, Any],
        label: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a snapshot of the given system state.

        Args:
            state: Full system state dictionary to capture.
            label: Human-readable label for the snapshot.
            metadata: Optional extra metadata.

        Returns:
            Dict with ``snapshot_id``, ``timestamp``, and ``label``.
        """
        snapshot = StateSnapshot(
            snapshot_id=str(uuid.uuid4()),
            timestamp=time.time(),
            label=label,
            state=copy.deepcopy(state),
            metadata=metadata or {},
        )
        with self._lock:
            self._snapshots[snapshot.snapshot_id] = snapshot
            self._write_snapshot(snapshot)
        logger.info("Created snapshot %s (%s)", snapshot.snapshot_id, label)
        return {
            "snapshot_id": snapshot.snapshot_id,
            "timestamp": snapshot.timestamp,
            "label": snapshot.label,
        }

    def restore_snapshot(self, snapshot_id: str) -> Optional[Dict[str, Any]]:
        """Restore a previously captured snapshot.

        Args:
            snapshot_id: ID of the snapshot to restore.

        Returns:
            Deep copy of the captured state, or ``None`` if not found.
        """
        with self._lock:
            snap = self._snapshots.get(snapshot_id)
            if snap is None:
                logger.warning("Snapshot %s not found", snapshot_id)
                return None
            return copy.deepcopy(snap.state)

    def get_snapshot_info(self, snapshot_id: str) -> Optional[Dict[str, Any]]:
        """Return metadata for a snapshot without the full state payload.

        Returns:
            Dict with id, timestamp, label, metadata, and state_keys.
        """
        with self._lock:
            snap = self._snapshots.get(snapshot_id)
            if snap is None:
                return None
            return {
                "snapshot_id": snap.snapshot_id,
                "timestamp": snap.timestamp,
                "label": snap.label,
                "metadata": snap.metadata,
                "state_keys": sorted(snap.state.keys()),
            }

    def list_snapshots(self) -> List[Dict[str, Any]]:
        """List all snapshots ordered by timestamp ascending.

        Returns:
            List of snapshot info dicts (id, timestamp, label).
        """
        with self._lock:
            snaps = sorted(self._snapshots.values(), key=lambda s: s.timestamp)
        return [
            {
                "snapshot_id": s.snapshot_id,
                "timestamp": s.timestamp,
                "label": s.label,
            }
            for s in snaps
        ]

    def delete_snapshot(self, snapshot_id: str) -> bool:
        """Delete a snapshot from memory and disk.

        Returns:
            ``True`` if deleted, ``False`` if not found.
        """
        with self._lock:
            snap = self._snapshots.pop(snapshot_id, None)
            if snap is None:
                return False
            filepath = self._snapshot_file(snapshot_id)
            if filepath.exists():
                filepath.unlink()
        logger.info("Deleted snapshot %s", snapshot_id)
        return True

    def compare_snapshots(
        self, snapshot_id_a: str, snapshot_id_b: str
    ) -> Optional[Dict[str, Any]]:
        """Check whether two snapshots are identical.

        Returns:
            Dict with ``identical`` (bool) and ``snapshot_a``/``snapshot_b`` labels,
            or ``None`` if either snapshot is missing.
        """
        with self._lock:
            snap_a = self._snapshots.get(snapshot_id_a)
            snap_b = self._snapshots.get(snapshot_id_b)
            if snap_a is None or snap_b is None:
                return None
            identical = snap_a.state == snap_b.state
        return {
            "snapshot_a": snapshot_id_a,
            "snapshot_b": snapshot_id_b,
            "identical": identical,
            "label_a": snap_a.label,
            "label_b": snap_b.label,
        }

    def diff_snapshots(
        self, snapshot_id_a: str, snapshot_id_b: str
    ) -> Optional[Dict[str, Any]]:
        """Compute a detailed diff between two snapshots.

        Returns a dict with ``added``, ``removed``, and ``modified`` keys
        describing changes from snapshot A → snapshot B.  Each category
        is a dict mapping key names to their values.  ``modified`` entries
        include ``{"old": …, "new": …}`` pairs.

        Returns ``None`` if either snapshot is missing.
        """
        with self._lock:
            snap_a = self._snapshots.get(snapshot_id_a)
            snap_b = self._snapshots.get(snapshot_id_b)
            if snap_a is None or snap_b is None:
                return None
            state_a = snap_a.state
            state_b = snap_b.state

        keys_a = set(state_a.keys())
        keys_b = set(state_b.keys())

        added = {k: state_b[k] for k in sorted(keys_b - keys_a)}
        removed = {k: state_a[k] for k in sorted(keys_a - keys_b)}
        modified: Dict[str, Any] = {}
        for k in sorted(keys_a & keys_b):
            if state_a[k] != state_b[k]:
                modified[k] = {"old": state_a[k], "new": state_b[k]}

        return {
            "snapshot_a": snapshot_id_a,
            "snapshot_b": snapshot_id_b,
            "added": added,
            "removed": removed,
            "modified": modified,
            "total_changes": len(added) + len(removed) + len(modified),
        }

    def get_status(self) -> Dict[str, Any]:
        """Return snapshot manager status summary."""
        with self._lock:
            count = len(self._snapshots)
        return {
            "snapshot_dir": str(self._snapshot_dir),
            "total_snapshots": count,
        }


# ================================================================
# Point-in-Time Recovery
# ================================================================

class PointInTimeRecovery:
    """Recover system state to any previous point in time.

    Maintains a time-ordered history of state changes so the system
    can be rolled back incrementally to any recorded timestamp.
    Thread-safe.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._history: List[Dict[str, Any]] = []  # [{timestamp, state, label}]

    def record_state(
        self,
        state: Dict[str, Any],
        label: str = "",
        timestamp: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Record a state checkpoint for future recovery.

        Args:
            state: Full system state to save.
            label: Optional descriptive label.
            timestamp: Explicit timestamp; defaults to ``time.time()``.

        Returns:
            Dict with ``index``, ``timestamp``, and ``label``.
        """
        ts = timestamp if timestamp is not None else time.time()
        entry = {
            "timestamp": ts,
            "state": copy.deepcopy(state),
            "label": label,
        }
        with self._lock:
            capped_append(self._history, entry)
            self._history.sort(key=lambda e: e["timestamp"])
            idx = self._history.index(entry)
        return {"index": idx, "timestamp": ts, "label": label}

    def recover_to_timestamp(self, target_ts: float) -> Optional[Dict[str, Any]]:
        """Recover the state as of *target_ts*.

        Returns the latest recorded state whose timestamp is ≤ *target_ts*,
        or ``None`` if no such record exists.
        """
        with self._lock:
            candidate = None
            for entry in self._history:
                if entry["timestamp"] <= target_ts:
                    candidate = entry
                else:
                    break
            if candidate is None:
                return None
            return {
                "timestamp": candidate["timestamp"],
                "label": candidate["label"],
                "state": copy.deepcopy(candidate["state"]),
            }

    def recover_to_index(self, index: int) -> Optional[Dict[str, Any]]:
        """Recover state at the given history index.

        Args:
            index: Zero-based position in the time-sorted history.

        Returns:
            Dict with ``timestamp``, ``label``, ``state``, or ``None``
            if the index is out of range.
        """
        with self._lock:
            if index < 0 or index >= len(self._history):
                return None
            entry = self._history[index]
            return {
                "timestamp": entry["timestamp"],
                "label": entry["label"],
                "state": copy.deepcopy(entry["state"]),
            }

    def list_checkpoints(self) -> List[Dict[str, Any]]:
        """List all recorded checkpoints (without state payloads)."""
        with self._lock:
            return [
                {"index": i, "timestamp": e["timestamp"], "label": e["label"]}
                for i, e in enumerate(self._history)
            ]

    def rollback_to_timestamp(self, target_ts: float) -> Dict[str, Any]:
        """Roll back history by removing all entries after *target_ts*.

        Returns:
            Dict with ``rolled_back_count`` and ``remaining_count``.
        """
        with self._lock:
            before = len(self._history)
            self._history = [e for e in self._history if e["timestamp"] <= target_ts]
            after = len(self._history)
        return {
            "rolled_back_count": before - after,
            "remaining_count": after,
        }

    def get_status(self) -> Dict[str, Any]:
        """Return recovery subsystem status."""
        with self._lock:
            count = len(self._history)
            ts_range = {}
            if count > 0:
                ts_range = {
                    "earliest": self._history[0]["timestamp"],
                    "latest": self._history[-1]["timestamp"],
                }
        return {
            "total_checkpoints": count,
            "timestamp_range": ts_range,
        }


# ================================================================
# Replay Orchestrator
# ================================================================

class ReplayOrchestrator:
    """Replay complete execution sequences from persisted state.

    Supports continuous, timed, and step-through replay modes with
    configurable speed.  Each step can optionally invoke a user-
    supplied callback.  Thread-safe.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state = ReplayState.IDLE
        self._mode = ReplayMode.CONTINUOUS
        self._speed: float = 1.0  # multiplier; >1 = faster
        self._steps: List[ReplayStep] = []
        self._current_index: int = 0
        self._session_id: str = ""
        self._callback: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None
        self._results: List[Dict[str, Any]] = []

    # -------------------- configuration --------------------

    def load_sequence(
        self,
        events: List[Dict[str, Any]],
        session_id: str = "",
        mode: str = "continuous",
        speed: float = 1.0,
        callback: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Load a sequence of events for replay.

        Args:
            events: Ordered list of event dicts.
            session_id: Identifier for this replay session.
            mode: ``"continuous"``, ``"step"``, or ``"timed"``.
            speed: Replay speed multiplier (default 1.0).
            callback: Optional function called for each event;
                      receives the event dict and returns a result dict.

        Returns:
            Dict confirming load with step count.
        """
        with self._lock:
            self._steps = [
                ReplayStep(step_index=i, event=e) for i, e in enumerate(events)
            ]
            self._current_index = 0
            self._session_id = session_id or str(uuid.uuid4())
            self._mode = ReplayMode(mode)
            self._speed = max(0.01, speed)
            self._callback = callback
            self._state = ReplayState.IDLE
            self._results = []
        return {
            "session_id": self._session_id,
            "total_steps": len(events),
            "mode": self._mode.value,
            "speed": self._speed,
        }

    # -------------------- execution --------------------

    def _execute_step(self, step: ReplayStep) -> Dict[str, Any]:
        """Execute a single replay step."""
        result: Dict[str, Any] = {"step_index": step.step_index, "event": step.event}
        try:
            if self._callback:
                step.result = self._callback(step.event)
            else:
                step.result = {"echo": step.event}
            step.executed = True
            result["status"] = "ok"
            result["result"] = step.result
        except Exception as exc:
            logger.debug("Caught exception: %s", exc)
            step.error = str(exc)
            step.executed = True
            result["status"] = "error"
            result["error"] = step.error
        return result

    def run(self) -> Dict[str, Any]:
        """Run the full replay sequence in continuous mode.

        Returns:
            Dict with ``session_id``, ``total_steps``, ``executed``,
            ``errors``, and ``results``.
        """
        with self._lock:
            if not self._steps:
                return {"session_id": self._session_id, "total_steps": 0,
                        "executed": 0, "errors": 0, "results": []}
            self._state = ReplayState.RUNNING

        errors = 0
        results: List[Dict[str, Any]] = []
        while True:
            with self._lock:
                if self._state == ReplayState.PAUSED:
                    break
                if self._current_index >= len(self._steps):
                    self._state = ReplayState.COMPLETED
                    break
                step = self._steps[self._current_index]
                self._current_index += 1

            r = self._execute_step(step)
            results.append(r)
            if r["status"] == "error":
                errors += 1

            # In timed mode, sleep between steps
            if self._mode == ReplayMode.TIMED and self._speed > 0:
                delay = 1.0 / self._speed
                time.sleep(delay)

        with self._lock:
            self._results = results
            if errors > 0 and self._state != ReplayState.PAUSED:
                self._state = ReplayState.COMPLETED

        return {
            "session_id": self._session_id,
            "total_steps": len(self._steps),
            "executed": len(results),
            "errors": errors,
            "results": results,
        }

    def step_forward(self) -> Optional[Dict[str, Any]]:
        """Execute exactly one step (step-through mode).

        Returns:
            Step result dict, or ``None`` if no more steps.
        """
        with self._lock:
            if self._current_index >= len(self._steps):
                self._state = ReplayState.COMPLETED
                return None
            step = self._steps[self._current_index]
            self._current_index += 1
            self._state = ReplayState.RUNNING

        result = self._execute_step(step)

        with self._lock:
            capped_append(self._results, result)
            if self._current_index >= len(self._steps):
                self._state = ReplayState.COMPLETED
            else:
                self._state = ReplayState.PAUSED
        return result

    def pause(self) -> Dict[str, Any]:
        """Pause a running replay."""
        with self._lock:
            self._state = ReplayState.PAUSED
        return {"state": ReplayState.PAUSED.value, "current_index": self._current_index}

    def resume(self) -> Dict[str, Any]:
        """Resume a paused replay (runs remaining steps)."""
        with self._lock:
            if self._state != ReplayState.PAUSED:
                return {"error": "not paused", "state": self._state.value}
            self._state = ReplayState.RUNNING
        return self.run()

    def reset(self) -> Dict[str, Any]:
        """Reset the orchestrator to idle."""
        with self._lock:
            self._current_index = 0
            self._state = ReplayState.IDLE
            self._results = []
            for step in self._steps:
                step.executed = False
                step.result = None
                step.error = None
        return {"state": ReplayState.IDLE.value, "steps_reset": len(self._steps)}

    # -------------------- status --------------------

    def get_progress(self) -> Dict[str, Any]:
        """Return current replay progress."""
        with self._lock:
            total = len(self._steps)
            executed = sum(1 for s in self._steps if s.executed)
            errored = sum(1 for s in self._steps if s.error is not None)
        return {
            "session_id": self._session_id,
            "state": self._state.value,
            "mode": self._mode.value,
            "speed": self._speed,
            "total_steps": total,
            "executed_steps": executed,
            "errored_steps": errored,
            "current_index": self._current_index,
        }

    def get_results(self) -> List[Dict[str, Any]]:
        """Return collected results from executed steps."""
        with self._lock:
            return list(self._results)

    def get_status(self) -> Dict[str, Any]:
        """Return orchestrator status summary."""
        return self.get_progress()


# ================================================================
# Unified Facade
# ================================================================

class PersistenceReplayCompleteness:
    """Unified facade combining all persistence+replay completeness features.

    Provides a single entry point to the WAL, snapshot, point-in-time
    recovery, and replay orchestration subsystems.
    """

    def __init__(
        self,
        wal_dir: Optional[str] = None,
        snapshot_dir: Optional[str] = None,
    ) -> None:
        self.wal = WriteAheadLog(wal_dir=wal_dir)
        self.snapshots = SnapshotManager(snapshot_dir=snapshot_dir)
        self.recovery = PointInTimeRecovery()
        self.orchestrator = ReplayOrchestrator()
        logger.info("PersistenceReplayCompleteness initialized")

    # ---------- convenience wrappers ----------

    def protected_operation(
        self,
        operation: str,
        data: Dict[str, Any],
        executor: Callable[[Dict[str, Any]], Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Execute an operation under WAL protection.

        1. Logs the operation to the WAL.
        2. Executes *executor(data)*.
        3. On success, commits the WAL entry.
        4. On failure, rolls back the WAL entry and re-raises.

        Returns:
            The executor's result dict.
        """
        entry_id = self.wal.log_operation(operation, data)
        try:
            result = executor(data)
            self.wal.commit(entry_id, result)
            return result
        except Exception as exc:
            logger.debug("Suppressed exception: %s", exc)
            self.wal.rollback(entry_id)
            raise

    def snapshot_and_record(
        self,
        state: Dict[str, Any],
        label: str = "",
    ) -> Dict[str, Any]:
        """Create a snapshot *and* record the state for point-in-time recovery.

        Returns:
            Combined dict with snapshot info and checkpoint index.
        """
        snap_info = self.snapshots.create_snapshot(state, label=label)
        checkpoint = self.recovery.record_state(state, label=label)
        return {**snap_info, "checkpoint_index": checkpoint["index"]}

    def get_status(self) -> Dict[str, Any]:
        """Return combined status of all subsystems."""
        return {
            "wal": self.wal.get_status(),
            "snapshots": self.snapshots.get_status(),
            "recovery": self.recovery.get_status(),
            "orchestrator": self.orchestrator.get_status(),
        }
