"""
Agent Run Recorder — Captures full telemetry for successful Murphy System runs.

Design Label: YT-001 — Agent Run Recording & Publishability Gate
Owner: Platform Engineering / Content Team
Dependencies:
  - thread_safe_operations (capped_append)
  - TelemetryStreamer (execution_orchestrator/telemetry.py)

Purpose:
  Subscribes to execution events, captures complete run telemetry as
  AgentRunRecording objects, and exposes list/get/delete operations.
  Only recordings with SUCCESS_COMPLETED status are retained.

Safety invariants:
  - Thread-safe: all shared state guarded by Lock
  - Bounded: max 1000 recordings, evict oldest 10% on overflow
  - No secrets stored: raw terminal output is accepted as-is (caller redacts)

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)

_MAX_RECORDINGS = 1_000

# Run status constants
STATUS_SUCCESS = "SUCCESS_COMPLETED"
STATUS_FAILED = "FAILED"
STATUS_PARTIAL = "PARTIAL"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class AgentRunRecording:
    """Complete telemetry snapshot of a single Murphy System agent run."""

    run_id: str
    task_description: str
    task_type: str
    status: str
    confidence_score: float
    confidence_progression: List[Dict[str, float]]
    steps: List[Dict[str, Any]]
    hitl_decisions: List[Dict[str, Any]]
    modules_used: List[str]
    gates_passed: List[str]
    duration_seconds: float
    system_version: str
    started_at: str
    completed_at: str
    terminal_output: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_publishable(self, min_confidence: float = 0.70) -> bool:
        """Return True when the run meets minimum quality bar for publishing."""
        return (
            self.status == STATUS_SUCCESS
            and self.confidence_score >= min_confidence
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to plain dict for storage or API responses."""
        return {
            "run_id": self.run_id,
            "task_description": self.task_description,
            "task_type": self.task_type,
            "status": self.status,
            "confidence_score": self.confidence_score,
            "confidence_progression": list(self.confidence_progression),
            "steps": list(self.steps),
            "hitl_decisions": list(self.hitl_decisions),
            "modules_used": list(self.modules_used),
            "gates_passed": list(self.gates_passed),
            "duration_seconds": self.duration_seconds,
            "system_version": self.system_version,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "terminal_output": list(self.terminal_output),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentRunRecording":
        """Deserialise from plain dict."""
        return cls(
            run_id=data["run_id"],
            task_description=data.get("task_description", ""),
            task_type=data.get("task_type", "unknown"),
            status=data.get("status", STATUS_FAILED),
            confidence_score=float(data.get("confidence_score", 0.0)),
            confidence_progression=list(data.get("confidence_progression", [])),
            steps=list(data.get("steps", [])),
            hitl_decisions=list(data.get("hitl_decisions", [])),
            modules_used=list(data.get("modules_used", [])),
            gates_passed=list(data.get("gates_passed", [])),
            duration_seconds=float(data.get("duration_seconds", 0.0)),
            system_version=data.get("system_version", "1.0"),
            started_at=data.get("started_at", ""),
            completed_at=data.get("completed_at", ""),
            terminal_output=list(data.get("terminal_output", [])),
            metadata=dict(data.get("metadata", {})),
        )


# ---------------------------------------------------------------------------
# Recorder
# ---------------------------------------------------------------------------

class AgentRunRecorder:
    """
    Records successful agent run telemetry for downstream publishing.

    Thread-safe, bounded collection (max 1000 recordings).
    Only retains runs with SUCCESS_COMPLETED status.

    Usage::

        recorder = AgentRunRecorder(system_version="1.0")
        recording = recorder.record_run(
            task_description="Deploy payment gateway",
            task_type="infrastructure",
            status=STATUS_SUCCESS,
            confidence_score=0.92,
            ...
        )
        publishable = recorder.list_recordings(publishable_only=True)
    """

    def __init__(
        self,
        system_version: str = "1.0",
        max_recordings: int = _MAX_RECORDINGS,
    ) -> None:
        self._lock = threading.Lock()
        self._recordings: List[AgentRunRecording] = []
        self._system_version = system_version
        self._max_recordings = max_recordings

    # ------------------------------------------------------------------
    # Recording creation
    # ------------------------------------------------------------------

    def record_run(
        self,
        task_description: str,
        task_type: str,
        status: str,
        confidence_score: float,
        confidence_progression: Optional[List[Dict[str, float]]] = None,
        steps: Optional[List[Dict[str, Any]]] = None,
        hitl_decisions: Optional[List[Dict[str, Any]]] = None,
        modules_used: Optional[List[str]] = None,
        gates_passed: Optional[List[str]] = None,
        duration_seconds: float = 0.0,
        started_at: Optional[str] = None,
        completed_at: Optional[str] = None,
        terminal_output: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        run_id: Optional[str] = None,
    ) -> Optional[AgentRunRecording]:
        """
        Create and store a recording for a completed run.

        Only recordings with STATUS_SUCCESS_COMPLETED are retained.
        Returns the recording if stored, None if filtered out.
        """
        if status != STATUS_SUCCESS:
            logger.debug(
                "Skipping recording for run with status=%s (only SUCCESS_COMPLETED stored)",
                status,
            )
            return None

        now = datetime.now(timezone.utc).isoformat()
        recording = AgentRunRecording(
            run_id=run_id or str(uuid.uuid4()),
            task_description=task_description,
            task_type=task_type,
            status=status,
            confidence_score=confidence_score,
            confidence_progression=list(confidence_progression or []),
            steps=list(steps or []),
            hitl_decisions=list(hitl_decisions or []),
            modules_used=list(modules_used or []),
            gates_passed=list(gates_passed or []),
            duration_seconds=duration_seconds,
            system_version=self._system_version,
            started_at=started_at or now,
            completed_at=completed_at or now,
            terminal_output=list(terminal_output or []),
            metadata=dict(metadata or {}),
        )

        with self._lock:
            capped_append(self._recordings, recording, max_size=self._max_recordings)

        logger.info(
            "Recorded agent run run_id=%s task_type=%s confidence=%.2f",
            recording.run_id,
            recording.task_type,
            recording.confidence_score,
        )
        return recording

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def list_recordings(
        self,
        publishable_only: bool = False,
        min_confidence: float = 0.70,
        status_filter: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Return recordings as dicts, with optional filters."""
        with self._lock:
            recordings = list(self._recordings)

        if status_filter:
            recordings = [r for r in recordings if r.status == status_filter]

        if publishable_only:
            recordings = [r for r in recordings if r.is_publishable(min_confidence)]

        recordings = recordings[-limit:]
        return [r.to_dict() for r in recordings]

    def get_recording(self, run_id: str) -> Optional[AgentRunRecording]:
        """Return a recording by run_id, or None if not found."""
        with self._lock:
            for rec in self._recordings:
                if rec.run_id == run_id:
                    return rec
        return None

    def delete_recording(self, run_id: str) -> bool:
        """Delete a recording by run_id. Returns True if found and deleted."""
        with self._lock:
            before = len(self._recordings)
            self._recordings = [r for r in self._recordings if r.run_id != run_id]
            deleted = len(self._recordings) < before

        if deleted:
            logger.info("Deleted recording run_id=%s", run_id)
        return deleted

    def count(self) -> int:
        """Return total number of stored recordings."""
        with self._lock:
            return len(self._recordings)

    def get_stats(self) -> Dict[str, Any]:
        """Return recorder statistics."""
        with self._lock:
            recordings = list(self._recordings)

        total = len(recordings)
        publishable = sum(1 for r in recordings if r.is_publishable())
        avg_conf = (
            sum(r.confidence_score for r in recordings) / (len(recordings) or 1)
        )
        return {
            "total_recordings": total,
            "publishable_recordings": publishable,
            "average_confidence": round(avg_conf, 3),
            "system_version": self._system_version,
            "max_recordings": self._max_recordings,
        }
