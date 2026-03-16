"""
Task Router — Librarian-driven dynamic task routing.

Replaces hardcoded ``IntegrationBus`` chains with a Librarian-first routing
pipeline:

    TaskRouter.route(task_dict)
        → SystemLibrarian.find_capabilities(task)
        → SolutionPath list (ranked)
        → GovernanceKernel gate validation
        → RoutingResult

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Route status
# ---------------------------------------------------------------------------


class RouteStatus(Enum):
    APPROVED = "approved"
    HITL = "hitl_required"
    BLOCKED = "blocked"
    NO_PATH = "no_viable_path"


# ---------------------------------------------------------------------------
# CapabilityMatch
# ---------------------------------------------------------------------------


@dataclass
class CapabilityMatch:
    """A single capability candidate returned by ``SystemLibrarian.find_capabilities()``.

    Attributes:
        capability_id: Unique identifier for the capability (e.g. ``"llm_routing"``).
        module_path: Dotted import path of the module providing this capability.
        score: Combined relevance score in [0.0, 1.0].
        match_reasons: Human-readable explanations of why this capability matched.
        cost_estimate: One of ``"low"``, ``"medium"``, ``"high"``.
        determinism: One of ``"deterministic"``, ``"stochastic"``.
        gate_compatibility: Mapping of gate name to compatibility status string.
        filtered: ``True`` if this match was excluded by the gate pre-filter.
        filter_reason: Explanation when *filtered* is ``True``.
    """

    capability_id: str
    module_path: str
    score: float
    match_reasons: List[str] = field(default_factory=list)
    cost_estimate: str = "medium"
    determinism: str = "deterministic"
    gate_compatibility: Dict[str, str] = field(default_factory=dict)
    filtered: bool = False
    filter_reason: Optional[str] = None


# ---------------------------------------------------------------------------
# SolutionPath
# ---------------------------------------------------------------------------


@dataclass
class SolutionPath:
    """A single ranked execution option for a task.

    Attributes:
        path_id: UUID string for this path.
        task_id: Parent task UUID.
        capability_id: e.g. ``"invoice_processing_pipeline"``.
        module_path: e.g. ``"src.invoice_processing.pipeline"``.
        score: Combined rank score in [0.0, 1.0].
        librarian_score: Raw Librarian match score.
        feedback_weight: Historical success weight (default 1.0 = neutral).
        cost_estimate: ``"low"`` | ``"medium"`` | ``"high"``.
        determinism: ``"deterministic"`` | ``"stochastic"``.
        requires_hitl: Whether a HITL gate is expected for this path.
        parameters: Extracted task parameters for this path.
        wingman: Assigned wingman validator module name, if any.
    """

    path_id: str
    task_id: str
    capability_id: str
    module_path: str
    score: float
    librarian_score: float
    feedback_weight: float = 1.0
    cost_estimate: str = "medium"
    determinism: str = "deterministic"
    requires_hitl: bool = False
    parameters: Dict[str, Any] = field(default_factory=dict)
    wingman: Optional[str] = None

    @property
    def combined_score(self) -> float:
        """Librarian score multiplied by historical feedback weight."""
        return self.librarian_score * self.feedback_weight


# ---------------------------------------------------------------------------
# RoutingResult
# ---------------------------------------------------------------------------


@dataclass
class RoutingResult:
    """Outcome of a single ``TaskRouter.route()`` call.

    Attributes:
        task_id: The task's unique identifier.
        status: Final routing disposition (:class:`RouteStatus`).
        solution_path: The approved path, or ``None`` if blocked/no_path.
        alternatives: All other paths that were evaluated.
        gate_results: Mapping of gate name → ``"pass"`` | ``"fail"`` | ``"hitl"``.
        confidence: Aggregate confidence in [0.0, 1.0].
    """

    task_id: str
    status: RouteStatus
    solution_path: Optional[SolutionPath]
    alternatives: List[SolutionPath]
    gate_results: Dict[str, str]
    confidence: float


# ---------------------------------------------------------------------------
# TaskRouter
# ---------------------------------------------------------------------------


class TaskRouter:
    """Librarian-first task router.

    Routes any incoming task dict through the Librarian capability-discovery
    pipeline, validates each candidate path through the GovernanceKernel, and
    returns the best viable :class:`RoutingResult`.

    Usage::

        router = TaskRouter(librarian, registry, governance_kernel, feedback)
        result = await router.route({"task": "generate invoice", "amount": 5000})
        if result.status == RouteStatus.APPROVED:
            executor.execute(result.solution_path)

    If the GovernanceKernel is unavailable (``None``), all paths are treated as
    approved (graceful degradation — preserves the old IntegrationBus behaviour).

    If the FeedbackIntegrator is unavailable (``None``), historical weights
    default to 1.0 (neutral — no learning penalty or bonus).
    """

    def __init__(
        self,
        librarian: Any,
        solution_registry: Any,
        governance: Optional[Any] = None,
        feedback: Optional[Any] = None,
    ) -> None:
        self._librarian = librarian
        self._registry = solution_registry
        self._governance = governance
        self._feedback = feedback

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def route(self, task: Dict[str, Any]) -> RoutingResult:
        """Route *task* through the Librarian pipeline and return a result.

        Pipeline:
            1. Ask Librarian for capability matches.
            2. Build :class:`SolutionPath` objects from the matches.
            3. Rank by Librarian score × FeedbackIntegrator historical weight.
            4. Register alternatives in :class:`SolutionPathRegistry`.
            5. Run gate validation on each path (best-first).
            6. Return first approved path, or HITL/BLOCKED if none pass.
        """
        task_id = task.get("task_id") or str(uuid.uuid4())
        task_text = str(task.get("task", task.get("description", "")))

        logger.info("TaskRouter: routing task_id=%s text=%r", task_id, task_text[:80])

        # Step 1 — capability discovery
        matches: List[CapabilityMatch] = self._librarian.find_capabilities(task)

        if not matches:
            logger.warning("TaskRouter: no capabilities found for task_id=%s", task_id)
            return RoutingResult(
                task_id=task_id,
                status=RouteStatus.NO_PATH,
                solution_path=None,
                alternatives=[],
                gate_results={},
                confidence=0.0,
            )

        # Step 2+3 — build and rank SolutionPaths
        paths = self._rank_paths(matches, self._feedback)
        for p in paths:
            p.task_id = task_id

        # Step 4 — persist alternatives in registry
        self._registry.register(task_id, paths)

        # Step 5 — gate validation (best-first)
        gate_results: Dict[str, str] = {}
        approved_path: Optional[SolutionPath] = None
        hitl_path: Optional[SolutionPath] = None

        for path in paths:
            verdict = self._validate_path(path, task, gate_results)
            if verdict == "pass":
                approved_path = path
                break
            elif verdict == "hitl" and hitl_path is None:
                hitl_path = path
                # continue — a fully-approved path is preferred over HITL

        # Step 6 — return result
        if approved_path is not None:
            logger.info(
                "TaskRouter: APPROVED path=%s capability=%s score=%.3f",
                approved_path.path_id,
                approved_path.capability_id,
                approved_path.combined_score,
            )
            return RoutingResult(
                task_id=task_id,
                status=RouteStatus.APPROVED,
                solution_path=approved_path,
                alternatives=[p for p in paths if p is not approved_path],
                gate_results=gate_results,
                confidence=approved_path.combined_score,
            )

        if hitl_path is not None:
            logger.info(
                "TaskRouter: HITL path=%s capability=%s",
                hitl_path.path_id,
                hitl_path.capability_id,
            )
            return RoutingResult(
                task_id=task_id,
                status=RouteStatus.HITL,
                solution_path=hitl_path,
                alternatives=[p for p in paths if p is not hitl_path],
                gate_results=gate_results,
                confidence=hitl_path.combined_score,
            )

        logger.warning("TaskRouter: all paths BLOCKED for task_id=%s", task_id)
        return RoutingResult(
            task_id=task_id,
            status=RouteStatus.BLOCKED,
            solution_path=None,
            alternatives=paths,
            gate_results=gate_results,
            confidence=0.0,
        )

    def route_sync(self, task: Dict[str, Any]) -> RoutingResult:
        """Synchronous wrapper around :meth:`route` for callers without an event loop."""
        import asyncio

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Running inside an existing event loop — create a new thread
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                    future = ex.submit(asyncio.run, self.route(task))
                    return future.result()
            return loop.run_until_complete(self.route(task))
        except RuntimeError:
            return asyncio.run(self.route(task))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _rank_paths(
        self,
        matches: List[CapabilityMatch],
        feedback: Optional[Any],
    ) -> List[SolutionPath]:
        """Build and rank :class:`SolutionPath` objects from *matches*.

        Multiply the Librarian match score by the historical success weight from
        *feedback*.  Paths with no historical data use a neutral weight of 1.0.
        """
        paths: List[SolutionPath] = []
        for match in matches:
            if match.filtered:
                continue
            weight = self._get_feedback_weight(match.capability_id, feedback)
            path = SolutionPath(
                path_id=str(uuid.uuid4()),
                task_id="",  # filled in after task_id is known
                capability_id=match.capability_id,
                module_path=match.module_path,
                score=match.score * weight,
                librarian_score=match.score,
                feedback_weight=weight,
                cost_estimate=match.cost_estimate,
                determinism=match.determinism,
                requires_hitl=False,
                parameters={},
            )
            paths.append(path)

        paths.sort(key=lambda p: p.combined_score, reverse=True)
        return paths

    @staticmethod
    def _get_feedback_weight(capability_id: str, feedback: Optional[Any]) -> float:
        """Return the historical success weight for *capability_id*.

        Queries :meth:`FeedbackIntegrator.get_weight` if available.  Falls back
        to a neutral weight of ``1.0`` so that capabilities with no history are
        neither penalised nor boosted.
        """
        if feedback is None:
            return 1.0
        get_weight = getattr(feedback, "get_weight", None)
        if callable(get_weight):
            try:
                w = get_weight(capability_id)
                return float(w) if w is not None else 1.0
            except Exception as exc:
                logger.debug("TaskRouter: feedback.get_weight failed: %s", exc)
        return 1.0

    def _validate_path(
        self,
        path: SolutionPath,
        task: Dict[str, Any],
        gate_results: Dict[str, str],
    ) -> str:
        """Run gate validation for *path* and return ``"pass"``, ``"hitl"``, or ``"fail"``.

        When no GovernanceKernel is configured, every path is treated as approved
        (graceful degradation — mirrors the old IntegrationBus behaviour).
        """
        if path.requires_hitl:
            gate_results[f"hitl_gate:{path.capability_id}"] = "hitl"
            return "hitl"

        if self._governance is None:
            gate_results[f"governance:{path.capability_id}"] = "pass"
            return "pass"

        # Try the lightweight enforce() API if available
        enforce = getattr(self._governance, "enforce", None)
        if callable(enforce):
            try:
                result = enforce(
                    caller_id="task_router",
                    department_id=task.get("department_id", "default"),
                    tool_name=path.capability_id,
                    estimated_cost=0.0,
                    context={"task": task, "path_id": path.path_id},
                )
                action = getattr(result, "action", None)
                if action is not None:
                    action_val = action.value if hasattr(action, "value") else str(action)
                    gate_results[f"governance:{path.capability_id}"] = (
                        "pass" if action_val in ("allow", "approved") else action_val
                    )
                    if action_val in ("allow", "approved"):
                        return "pass"
                    if action_val == "hitl_required":
                        return "hitl"
                    return "fail"
            except Exception as exc:
                logger.debug("TaskRouter: governance.enforce failed: %s", exc)

        # Fallback — assume pass
        gate_results[f"governance:{path.capability_id}"] = "pass"
        return "pass"


__all__ = [
    "RouteStatus",
    "RoutingResult",
    "CapabilityMatch",
    "SolutionPath",
    "TaskRouter",
]
