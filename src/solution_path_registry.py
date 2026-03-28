"""
SolutionPathRegistry — Persists ranked solution-path alternatives for each task.

Backs the "I found N ways to do this" HITL presentation and feeds outcome data
back into the routing layer so future tasks benefit from historical success rates.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class SolutionPath:
    """A single ranked execution option for a task."""

    path_id: str
    task_id: str
    capability_id: str        # e.g. "invoice_processing_pipeline"
    module_path: str          # e.g. "src.invoice_processing.pipeline"
    score: float              # 0.0–1.0 combined rank
    librarian_score: float    # Raw Librarian match score
    feedback_weight: float    # Historical success weight (default 1.0)
    cost_estimate: str        # "low" | "medium" | "high"
    determinism: str          # "deterministic" | "stochastic"
    requires_hitl: bool       # Whether HITL gate is expected
    parameters: Dict[str, Any] = field(default_factory=dict)
    wingman: Optional[str] = None  # Assigned wingman validator module

    @property
    def combined_score(self) -> float:
        return self.librarian_score * self.feedback_weight

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SolutionPath":
        return cls(**data)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class SolutionPathRegistry:
    """
    Persists solution-path alternatives across process restarts.

    Storage layout (``data_dir``):
    - ``{task_id}.json``   — all paths for a task
    - ``outcomes.jsonl``   — append-only outcome log
    """

    def __init__(self, data_dir: str = "data/solution_paths") -> None:
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._outcomes_path = self._data_dir / "outcomes.jsonl"

    # ------------------------------------------------------------------
    # Core CRUD
    # ------------------------------------------------------------------

    def register(self, task_id: str, paths: List[SolutionPath]) -> None:
        """Persist the full set of alternatives for *task_id*."""
        if not paths:
            return
        sorted_paths = sorted(paths, key=lambda p: p.combined_score, reverse=True)
        dest = self._data_dir / f"{task_id}.json"
        dest.write_text(
            json.dumps([p.to_dict() for p in sorted_paths], indent=2),
            encoding="utf-8",
        )
        logger.debug("Registered %d solution paths for task %s", len(paths), task_id)

    def get_alternatives(self, task_id: str) -> List[SolutionPath]:
        """Return all registered alternatives for HITL presentation."""
        dest = self._data_dir / f"{task_id}.json"
        if not dest.exists():
            return []
        raw = json.loads(dest.read_text(encoding="utf-8"))
        return [SolutionPath.from_dict(d) for d in raw]

    def get_primary(self, task_id: str) -> Optional[SolutionPath]:
        """Return the highest-scored path (first in sorted list)."""
        alts = self.get_alternatives(task_id)
        return alts[0] if alts else None

    def get_fallback(
        self, task_id: str, failed_path_id: str
    ) -> Optional[SolutionPath]:
        """Return the next-best alternative after *failed_path_id* fails."""
        alts = self.get_alternatives(task_id)
        for i, path in enumerate(alts):
            if path.path_id == failed_path_id and i + 1 < len(alts):
                return alts[i + 1]
        return None

    # ------------------------------------------------------------------
    # Outcome recording
    # ------------------------------------------------------------------

    def record_outcome(
        self,
        task_id: str,
        path_id: str,
        success: bool,
        latency_ms: int = 0,
    ) -> None:
        """
        Append an outcome record.  The feedback_weight for this capability
        can be derived later by aggregating outcome records.
        """
        record = {
            "task_id": task_id,
            "path_id": path_id,
            "success": success,
            "latency_ms": latency_ms,
        }
        with self._outcomes_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
        logger.debug("Outcome recorded: task=%s path=%s success=%s", task_id, path_id, success)

    def get_success_rate(self, capability_id: str) -> float:
        """
        Return the historical success rate (0.0–1.0) for *capability_id*
        based on the outcomes log.  Returns 1.0 (neutral) if no history.
        """
        if not self._outcomes_path.exists():
            return 1.0

        all_paths: Dict[str, str] = {}
        # Build path_id → capability_id mapping from task files
        for task_file in self._data_dir.glob("*.json"):
            if task_file.name == "outcomes.jsonl":
                continue
            try:
                raw = json.loads(task_file.read_text(encoding="utf-8"))
                for p in raw:
                    all_paths[p["path_id"]] = p.get("capability_id", "")
            except (json.JSONDecodeError, KeyError):
                pass

        successes = 0
        total = 0
        with self._outcomes_path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                cap = all_paths.get(rec.get("path_id", ""), "")
                if cap == capability_id:
                    total += 1
                    if rec.get("success"):
                        successes += 1

        return (successes / total) if total > 0 else 1.0
