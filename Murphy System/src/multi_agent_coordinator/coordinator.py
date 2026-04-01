"""
Team Coordinator — parallel dispatch, merge, and validate.

Design Label: MAC-003

Coordinates multiple bots/engines for a complex task:
  1. Decompose into subtasks
  2. Dispatch subtasks (respecting dependency DAG)
  3. Collect results
  4. Merge with conflict resolution
  5. Apply Murphy Validation

Thread-safe, bounded queues, no bare except.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from typing import Any, Callable, Deque, Dict, List, Optional

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

logger = logging.getLogger(__name__)

_MAX_COORDINATION_LOG = 200
_MURPHY_VALIDATION_THRESHOLD = 0.7


class TeamCoordinator:
    """Coordinates a team of tools for parallel subtask execution.

    Designed to plug into the Two-Phase Orchestrator's Phase 1.
    """

    def __init__(
        self,
        *,
        murphy_threshold: float = _MURPHY_VALIDATION_THRESHOLD,
        max_parallel: int = 10,
    ) -> None:
        self._murphy_threshold = murphy_threshold
        self._max_parallel = max_parallel
        self._coordination_log: Deque[CoordinationResult] = deque(
            maxlen=_MAX_COORDINATION_LOG,
        )
        self._tool_executors: Dict[str, Callable[..., SubTaskResult]] = {}

    # ------------------------------------------------------------------
    # Tool executor registration
    # ------------------------------------------------------------------

    def register_executor(
        self,
        tool_id: str,
        executor: Callable[..., SubTaskResult],
    ) -> None:
        """Register an async or sync callable that executes a tool."""
        self._tool_executors[tool_id] = executor
        logger.info("Executor registered for tool: %s", tool_id)

    # ------------------------------------------------------------------
    # Decomposition helper
    # ------------------------------------------------------------------

    @staticmethod
    def decompose(
        request: str,
        subtask_specs: List[Dict[str, Any]],
        merge_strategy: MergeStrategy = MergeStrategy.VOTE,
    ) -> TaskDecomposition:
        """Build a TaskDecomposition from a list of subtask specs.

        Each spec dict should have at minimum ``assigned_tool_id``.
        """
        subtasks = [SubTask(**spec) for spec in subtask_specs]
        decomp = TaskDecomposition(
            original_request=request,
            subtasks=subtasks,
            merge_strategy=merge_strategy,
        )
        for st in decomp.subtasks:
            st.parent_task_id = decomp.task_id
        return decomp

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def execute(
        self,
        decomposition: TaskDecomposition,
        *,
        custom_merge: Optional[Callable[[List[SubTaskResult]], Dict[str, Any]]] = None,
    ) -> CoordinationResult:
        """Run all subtasks, merge results, validate."""
        t0 = time.monotonic()
        results: List[SubTaskResult] = []
        pending = list(decomposition.subtasks)
        completed_ids: set[str] = set()

        # Dispatch waves respecting dependencies
        while pending:
            ready = [
                st for st in pending
                if all(dep in completed_ids for dep in st.depends_on)
            ]
            if not ready:
                # Deadlock or unresolvable deps
                logger.error("Deadlock detected: remaining subtasks have unsatisfied deps")
                for st in pending:
                    results.append(SubTaskResult(
                        subtask_id=st.subtask_id,
                        tool_id=st.assigned_tool_id,
                        status=SubTaskStatus.FAILED,
                        error="Unresolvable dependency",
                    ))
                break

            # Execute ready batch (bounded parallelism)
            batch = ready[: self._max_parallel]
            batch_results = await self._execute_batch(batch)
            results.extend(batch_results)

            for r in batch_results:
                completed_ids.add(r.subtask_id)
            for st in batch:
                pending.remove(st)

        # Merge
        merge_strategy = decomposition.merge_strategy
        conflicts: List[ConflictResolution] = []

        if custom_merge and merge_strategy == MergeStrategy.CUSTOM:
            merged = custom_merge(results)
        else:
            merged, conflicts = self._merge_results(results, merge_strategy)

        # Murphy Validation
        score = self._murphy_validate(results, merged)
        passed = score >= self._murphy_threshold

        elapsed_ms = (time.monotonic() - t0) * 1000
        coord_result = CoordinationResult(
            task_id=decomposition.task_id,
            status=CoordinationStatus.COMPLETED if passed else CoordinationStatus.FAILED,
            subtask_results=results,
            merged_output=merged,
            conflicts_resolved=conflicts,
            murphy_validation_score=score,
            murphy_validation_passed=passed,
            total_execution_time_ms=elapsed_ms,
        )
        self._coordination_log.append(coord_result)
        return coord_result

    async def _execute_batch(
        self,
        batch: List[SubTask],
    ) -> List[SubTaskResult]:
        """Execute a batch of subtasks concurrently."""
        tasks = [self._execute_one(st) for st in batch]
        return list(await asyncio.gather(*tasks, return_exceptions=False))

    async def _execute_one(self, subtask: SubTask) -> SubTaskResult:
        """Execute a single subtask via its registered executor."""
        executor = self._tool_executors.get(subtask.assigned_tool_id)
        if executor is None:
            return SubTaskResult(
                subtask_id=subtask.subtask_id,
                tool_id=subtask.assigned_tool_id,
                status=SubTaskStatus.FAILED,
                error=f"No executor registered for {subtask.assigned_tool_id}",
            )

        t0 = time.monotonic()
        try:
            if asyncio.iscoroutinefunction(executor):
                result = await asyncio.wait_for(
                    executor(subtask.input_data),
                    timeout=subtask.timeout_seconds,
                )
            else:
                result = executor(subtask.input_data)

            elapsed_ms = (time.monotonic() - t0) * 1000

            if isinstance(result, SubTaskResult):
                result.subtask_id = subtask.subtask_id
                result.execution_time_ms = elapsed_ms
                return result

            # Executor returned a plain dict
            return SubTaskResult(
                subtask_id=subtask.subtask_id,
                tool_id=subtask.assigned_tool_id,
                status=SubTaskStatus.COMPLETED,
                output=result if isinstance(result, dict) else {"value": result},
                confidence=0.8,
                execution_time_ms=elapsed_ms,
            )
        except asyncio.TimeoutError:
            return SubTaskResult(
                subtask_id=subtask.subtask_id,
                tool_id=subtask.assigned_tool_id,
                status=SubTaskStatus.TIMEOUT,
                error=f"Timed out after {subtask.timeout_seconds}s",
                execution_time_ms=(time.monotonic() - t0) * 1000,
            )
        except Exception as exc:
            logger.exception("Subtask %s failed: %s", subtask.subtask_id, exc)
            return SubTaskResult(
                subtask_id=subtask.subtask_id,
                tool_id=subtask.assigned_tool_id,
                status=SubTaskStatus.FAILED,
                error=str(exc),
                execution_time_ms=(time.monotonic() - t0) * 1000,
            )

    # ------------------------------------------------------------------
    # Merge strategies
    # ------------------------------------------------------------------

    def _merge_results(
        self,
        results: List[SubTaskResult],
        strategy: MergeStrategy,
    ) -> tuple[Dict[str, Any], List[ConflictResolution]]:
        """Merge subtask results according to the chosen strategy."""
        successful = [r for r in results if r.status == SubTaskStatus.COMPLETED]
        conflicts: List[ConflictResolution] = []

        if not successful:
            return {"error": "All subtasks failed"}, conflicts

        if strategy == MergeStrategy.FIRST_SUCCESS:
            return successful[0].output, conflicts

        if strategy == MergeStrategy.PRIORITY:
            # Assume ordering reflects priority
            return successful[0].output, conflicts

        if strategy == MergeStrategy.CONCAT:
            merged: Dict[str, Any] = {}
            for r in successful:
                for key, val in r.output.items():
                    if key in merged:
                        existing = merged[key]
                        if isinstance(existing, list):
                            existing.append(val)
                        else:
                            merged[key] = [existing, val]
                    else:
                        merged[key] = val
            return merged, conflicts

        # Default: VOTE (confidence-weighted)
        return self._confidence_vote(successful, conflicts)

    @staticmethod
    def _confidence_vote(
        results: List[SubTaskResult],
        conflicts: List[ConflictResolution],
    ) -> tuple[Dict[str, Any], List[ConflictResolution]]:
        """Merge by confidence-weighted voting."""
        all_keys: set[str] = set()
        for r in results:
            all_keys.update(r.output.keys())

        merged: Dict[str, Any] = {}
        for key in all_keys:
            values_with_conf: List[tuple[Any, float]] = []
            for r in results:
                if key in r.output:
                    values_with_conf.append((r.output[key], r.confidence))

            if len(values_with_conf) == 1:
                merged[key] = values_with_conf[0][0]
                continue

            # Check for conflict
            unique_vals = set()
            for v, _ in values_with_conf:
                try:
                    unique_vals.add(v)
                except TypeError:
                    unique_vals.add(str(v))

            if len(unique_vals) <= 1:
                merged[key] = values_with_conf[0][0]
                continue

            # Conflict: pick highest confidence
            best = max(values_with_conf, key=lambda x: x[1])
            merged[key] = best[0]
            conflicts.append(ConflictResolution(
                field=key,
                conflicting_values=[v for v, _ in values_with_conf],
                resolved_value=best[0],
                resolution_method="confidence_weighted_vote",
                confidence=best[1],
            ))

        return merged, conflicts

    # ------------------------------------------------------------------
    # Murphy Validation
    # ------------------------------------------------------------------

    def _murphy_validate(
        self,
        results: List[SubTaskResult],
        merged: Dict[str, Any],
    ) -> float:
        """Apply Murphy Validation formula to merged result.

        Score = (success_ratio * 0.4) + (avg_confidence * 0.4) + (completeness * 0.2)
        """
        if not results:
            return 0.0

        total = len(results)
        successes = sum(1 for r in results if r.status == SubTaskStatus.COMPLETED)
        success_ratio = successes / total

        confidences = [r.confidence for r in results if r.status == SubTaskStatus.COMPLETED]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        # Completeness: did we get non-empty output?
        completeness = 1.0 if merged and "error" not in merged else 0.0

        return (success_ratio * 0.4) + (avg_confidence * 0.4) + (completeness * 0.2)

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def get_coordination_log(self) -> List[CoordinationResult]:
        """Return recent coordination results (bounded)."""
        return list(self._coordination_log)
