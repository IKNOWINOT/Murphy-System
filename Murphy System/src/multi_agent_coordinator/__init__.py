"""
Multi-Agent Coordinator — team-based parallel execution.

Design Label: MAC-001
Module ID:    src.multi_agent_coordinator

Implements team-based parallel execution for the Two-Phase Orchestrator
where Phase 1 can decompose complex tasks into subtasks and spawn
multiple engines/bots in parallel with a coordination layer that:
  • Merges results
  • Resolves conflicts between bot outputs
  • Applies Murphy Validation to the merged result

Commissioning answers
─────────────────────
Q: Does the module do what it was designed to do?
A: Provides task decomposition, parallel subtask dispatch, result
   merging, conflict resolution, and Murphy-validated final output.

Q: What conditions are possible?
A: Decompose → dispatch → collect → merge → validate.  Subtasks may
   succeed, fail, or time out independently.  Conflicts resolved by
   confidence-weighted voting.

Q: Has hardening been applied?
A: Thread-safe coordination, bounded subtask queues, timeout enforcement,
   structured error propagation, no bare except.
"""

from __future__ import annotations

from src.multi_agent_coordinator.models import (
    ConflictResolution,
    CoordinationResult,
    CoordinationStatus,
    MergeStrategy,
    SubTask,
    SubTaskResult,
    SubTaskStatus,
    TaskDecomposition,
)
from src.multi_agent_coordinator.coordinator import TeamCoordinator

__all__ = [
    "ConflictResolution",
    "CoordinationResult",
    "CoordinationStatus",
    "MergeStrategy",
    "SubTask",
    "SubTaskResult",
    "SubTaskStatus",
    "TaskDecomposition",
    "TeamCoordinator",
]
