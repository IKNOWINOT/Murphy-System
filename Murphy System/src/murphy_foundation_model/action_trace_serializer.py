# Copyright © 2020-2026 Inoni LLC — Created by Corey Post
# License: BSL 1.1
"""
Action Trace Serializer
=======================

Captures structured SENSE → THINK → ACT → LEARN traces produced by the
Murphy System and persists them as append-only JSONL files.  Traces are
the raw material from which the Murphy Foundation Model learns.

Usage::

    collector = ActionTraceCollector.get_instance(trace_dir="./data/action_traces")
    collector.record_trace(trace)
    collector.flush()
"""

from __future__ import annotations

import gzip
import json
import logging
import os
import sys
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ActionTrace:
    """A single SENSE → THINK → ACT → LEARN trace."""

    trace_id: str
    timestamp: datetime

    # SENSE
    world_state: Dict[str, Any]

    # THINK
    intent: str
    constraints: List[Dict[str, Any]]
    confidence_at_decision: float
    murphy_index_at_decision: float
    alternatives_considered: List[Dict[str, Any]]
    reasoning_chain: List[str]

    # ACT
    actions_taken: List[Dict[str, Any]]
    action_types: List[str]  # API_CALL, ACTUATOR, CONTENT, DATA, COMMAND, AGENT

    # LEARN
    outcome_success: bool
    outcome_utility: float  # -1.0 to 1.0
    outcome_details: Dict[str, Any]
    human_correction: Optional[str] = None

    # META
    phase: str = ""
    engine_used: str = ""
    authority_level: str = ""
    execution_time_ms: float = 0.0

    # Labeling (populated by OutcomeLabeler)
    labels: Optional[Dict[str, float]] = None


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------

def trace_to_dict(trace: ActionTrace) -> Dict[str, Any]:
    """Serialize an *ActionTrace* to a plain dict safe for JSON encoding."""
    data = asdict(trace)
    # datetime → ISO-8601 string
    if isinstance(data.get("timestamp"), datetime):
        data["timestamp"] = data["timestamp"].isoformat()
    return data


def dict_to_trace(data: Dict[str, Any]) -> ActionTrace:
    """Deserialize a dict (from JSON) back into an *ActionTrace*."""
    data = dict(data)  # shallow copy so we don't mutate the caller's dict
    ts = data.get("timestamp")
    if isinstance(ts, str):
        data["timestamp"] = datetime.fromisoformat(ts)
    # Normalise naive timestamps to UTC so comparisons with aware cutoffs work.
    if isinstance(data.get("timestamp"), datetime) and data["timestamp"].tzinfo is None:
        data["timestamp"] = data["timestamp"].replace(tzinfo=timezone.utc)
    return ActionTrace(**data)


# ---------------------------------------------------------------------------
# Collector
# ---------------------------------------------------------------------------

class ActionTraceCollector:
    """Singleton that collects action traces via EventBackbone pub/sub.

    Stores traces in append-only JSONL files under *trace_dir*.
    Rotates files daily; ``compress_old_files`` compresses after N days.
    """

    _instance: Optional["ActionTraceCollector"] = None

    # -- singleton access ---------------------------------------------------

    @classmethod
    def get_instance(
        cls,
        trace_dir: Optional[str] = None,
        event_backbone: Any = None,
    ) -> "ActionTraceCollector":
        """Return (or create) the singleton collector."""
        if cls._instance is None:
            cls._instance = cls(trace_dir=trace_dir, event_backbone=event_backbone)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton — primarily for testing."""
        cls._instance = None

    # -- init ---------------------------------------------------------------

    def __init__(
        self,
        trace_dir: Optional[str] = None,
        event_backbone: Any = None,
    ) -> None:
        self.trace_dir = Path(
            trace_dir or os.environ.get("MFM_TRACE_DIR", "./data/action_traces")
        )
        self.trace_dir.mkdir(parents=True, exist_ok=True)
        self.event_backbone = event_backbone

        self.traces_buffer: List[ActionTrace] = []
        self.buffer_lock = threading.Lock()
        self.flush_interval = 30  # seconds

        self._current_file: Optional[Path] = None
        self._current_date: Optional[str] = None
        self._trace_count: int = 0
        self._stats: Dict[str, Any] = {
            "total": 0,
            "by_action_type": {},
            "success_count": 0,
            "fail_count": 0,
        }

        if self.event_backbone:
            self._register_hooks()

        logger.info("ActionTraceCollector initialised — trace_dir=%s", self.trace_dir)

    # -- public API ---------------------------------------------------------

    def record_trace(self, trace: ActionTrace) -> None:
        """Buffer a trace and auto-flush when the buffer reaches 100."""
        with self.buffer_lock:
            self.traces_buffer.append(trace)
            self._update_stats(trace)
            if len(self.traces_buffer) >= 100:
                self._flush_buffer()

    def flush(self) -> None:
        """Flush the in-memory buffer to disk."""
        with self.buffer_lock:
            self._flush_buffer()

    def get_stats(self) -> Dict[str, Any]:
        """Return collection statistics."""
        total = self._stats["total"]
        return {
            "total_traces": total,
            "action_type_distribution": dict(self._stats["by_action_type"]),
            "success_rate": (
                self._stats["success_count"] / total if total > 0 else 0.0
            ),
            "failure_rate": (
                self._stats["fail_count"] / total if total > 0 else 0.0
            ),
            "trace_dir": str(self.trace_dir),
            "current_file": str(self._current_file) if self._current_file else None,
        }

    def load_traces(self, since_days: Optional[int] = None) -> List[ActionTrace]:
        """Load traces from JSONL files on disk.

        Parameters
        ----------
        since_days:
            If given, only return traces from files written within the
            last *since_days* days.
        """
        self.flush()
        traces: List[ActionTrace] = []
        for filepath in sorted(self.trace_dir.glob("traces_*.jsonl")):
            if since_days is not None:
                file_date_str = filepath.stem.replace("traces_", "")
                try:
                    file_date = datetime.strptime(file_date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                    if (datetime.now(timezone.utc) - file_date).days > since_days:
                        continue
                except ValueError:
                    continue
            with open(filepath, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        traces.append(dict_to_trace(json.loads(line)))
        return traces

    def compress_old_files(self, older_than_days: int = 7) -> int:
        """Gzip JSONL files older than *older_than_days*.

        Returns the number of files compressed.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
        compressed = 0
        for filepath in list(self.trace_dir.glob("traces_*.jsonl")):
            file_date_str = filepath.stem.replace("traces_", "")
            try:
                file_date = datetime.strptime(file_date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                if file_date < cutoff:
                    gz_path = filepath.with_suffix(".jsonl.gz")
                    if not gz_path.exists():
                        with open(filepath, "rb") as f_in:
                            with gzip.open(gz_path, "wb") as f_out:
                                f_out.write(f_in.read())
                        filepath.unlink()
                        compressed += 1
            except ValueError:
                continue
        if compressed:
            logger.info("Compressed %d old trace file(s)", compressed)
        return compressed

    # -- internal -----------------------------------------------------------

    def _get_current_file(self) -> Path:
        """Return the JSONL file path for today, rotating daily."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if today != self._current_date:
            self._current_date = today
            self._current_file = self.trace_dir / f"traces_{today}.jsonl"
        return self._current_file  # type: ignore[return-value]

    def _flush_buffer(self) -> None:
        """Write buffered traces to the current JSONL file."""
        if not self.traces_buffer:
            return
        filepath = self._get_current_file()
        with open(filepath, "a", encoding="utf-8") as fh:
            for trace in self.traces_buffer:
                fh.write(json.dumps(trace_to_dict(trace), default=str) + "\n")
        self._trace_count += len(self.traces_buffer)
        self.traces_buffer.clear()

    def _register_hooks(self) -> None:
        """Register with EventBackbone to capture events as traces."""
        # Subscribes to key EventType values — concrete wiring depends on
        # the EventBackbone.subscribe() signature discovered at runtime.
        try:
            from event_backbone import EventType  # noqa: F811

            for etype in (EventType.TASK_COMPLETED, EventType.TASK_FAILED):
                self.event_backbone.subscribe(etype, self._on_event)
            logger.info("Registered EventBackbone hooks for trace collection")
        except Exception:
            logger.warning(
                "Could not register EventBackbone hooks — "
                "traces must be recorded manually via record_trace()"
            )

    def _on_event(self, event: Any) -> None:
        """EventBackbone handler — wraps an Event into an ActionTrace."""
        try:
            payload = event.payload if hasattr(event, "payload") else {}
            trace = ActionTrace(
                trace_id=getattr(event, "event_id", ""),
                timestamp=getattr(event, "timestamp", datetime.now(timezone.utc)),
                world_state=payload.get("world_state", {}),
                intent=payload.get("intent", ""),
                constraints=payload.get("constraints", []),
                confidence_at_decision=float(
                    payload.get("confidence", 0.5)
                ),
                murphy_index_at_decision=float(
                    payload.get("murphy_index", 0.5)
                ),
                alternatives_considered=payload.get("alternatives", []),
                reasoning_chain=payload.get("reasoning_chain", []),
                actions_taken=payload.get("actions_taken", []),
                action_types=payload.get("action_types", []),
                outcome_success=payload.get("outcome_success", False),
                outcome_utility=float(payload.get("outcome_utility", 0.0)),
                outcome_details=payload.get("outcome_details", {}),
                human_correction=payload.get("human_correction"),
                phase=payload.get("phase", ""),
                engine_used=payload.get("engine_used", ""),
                authority_level=payload.get("authority_level", ""),
                execution_time_ms=float(
                    payload.get("execution_time_ms", 0.0)
                ),
            )
            self.record_trace(trace)
        except Exception:
            logger.exception("Failed to convert event to ActionTrace")

    def _update_stats(self, trace: ActionTrace) -> None:
        self._stats["total"] += 1
        for at in trace.action_types:
            self._stats["by_action_type"][at] = (
                self._stats["by_action_type"].get(at, 0) + 1
            )
        if trace.outcome_success:
            self._stats["success_count"] += 1
        else:
            self._stats["fail_count"] += 1


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

def _cli() -> None:
    """Minimal CLI for inspecting trace data."""
    if len(sys.argv) < 2:
        print("Usage: python -m murphy_foundation_model.action_trace_serializer <command>")
        print("Commands: stats, count")
        sys.exit(1)

    command = sys.argv[1]
    collector = ActionTraceCollector.get_instance()

    if command == "stats":
        import pprint

        traces = collector.load_traces()
        # Rebuild stats from loaded traces
        for t in traces:
            collector._update_stats(t)
        pprint.pprint(collector.get_stats())
    elif command == "count":
        traces = collector.load_traces()
        print(f"Total traces on disk: {len(traces)}")
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    _cli()
