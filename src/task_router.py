"""
TaskRouter — Librarian-first task routing with gate validation.

Receives a raw task dict, consults :class:`SystemLibrarian` for capability
matches, builds :class:`SolutionPath` alternatives, ranks them by combined
Librarian score × historical feedback weight, then validates each path through
:class:`GovernanceKernel` gates (best-first).

Returns a :class:`RoutingResult` whose *status* is one of:

- ``APPROVED``  — a path passed all gates; ``solution_path`` is populated.
- ``HITL``      — all paths need human review; ``solution_path`` is the best
  candidate.
- ``BLOCKED``   — no path could be approved or safely escalated.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.system_librarian import SystemLibrarian
    from src.module_registry import ModuleRegistry
    from src.solution_path_registry import SolutionPathRegistry, SolutionPath

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class RouteStatus(Enum):
    APPROVED = "approved"
    HITL = "hitl"
    BLOCKED = "blocked"


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------

@dataclass
class RoutingResult:
    """Outcome of a :meth:`TaskRouter.route` call."""

    status: RouteStatus
    task_id: str
    solution_path: Optional["SolutionPath"] = None
    alternatives: List["SolutionPath"] = field(default_factory=list)
    rejection_reason: Optional[str] = None
    gate_results: Dict[str, Any] = field(default_factory=dict)

    def is_approved(self) -> bool:
        return self.status == RouteStatus.APPROVED

    def needs_hitl(self) -> bool:
        return self.status == RouteStatus.HITL

    def is_blocked(self) -> bool:
        return self.status == RouteStatus.BLOCKED


# ---------------------------------------------------------------------------
# CapabilityMatch — lightweight score holder returned by the Librarian
# ---------------------------------------------------------------------------

@dataclass
class CapabilityMatch:
    """A capability that the Librarian matched against the incoming task."""

    capability_id: str
    module_path: str
    score: float               # 0.0–1.0 relevance score
    cost_estimate: str = "low"
    determinism: str = "deterministic"
    requires_hitl: bool = False
    parameters: Dict[str, Any] = field(default_factory=dict)
    wingman: Optional[str] = None


# ---------------------------------------------------------------------------
# TaskRouter
# ---------------------------------------------------------------------------

class TaskRouter:
    """
    Librarian-first task router.

    Usage::

        router = TaskRouter(librarian, module_registry, solution_registry)
        result = router.route({"task": "generate invoice", "amount": 5000})
        if result.is_approved():
            executor.execute(result.solution_path)
    """

    def __init__(
        self,
        librarian: "SystemLibrarian",
        module_registry: "ModuleRegistry",
        solution_registry: "SolutionPathRegistry",
        governance: Optional[Any] = None,
    ) -> None:
        self._librarian = librarian
        self._registry = module_registry
        self._solution_registry = solution_registry
        self._governance = governance

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def route(self, task: Dict[str, Any]) -> RoutingResult:
        """
        Full routing pipeline:

        1. Ask Librarian for capability matches via ``search_knowledge``.
        2. Build :class:`SolutionPath` alternatives weighted by historical
           success rate from :class:`SolutionPathRegistry`.
        3. Rank paths by combined score (librarian × feedback).
        4. Register alternatives in the registry.
        5. Run gate validation on each path (best-first).
        6. Return first approved path, or HITL/BLOCKED.
        """
        task_id = str(uuid.uuid4())
        task_text = self._extract_task_text(task)
        logger.info("Routing task %s: %r", task_id, task_text[:80])

        # Step 1 – match capabilities via Librarian
        matches = self._match_capabilities(task_text, task)
        if not matches:
            logger.warning("No capabilities matched for task %s", task_id)
            return RoutingResult(
                status=RouteStatus.BLOCKED,
                task_id=task_id,
                rejection_reason="No registered capability matched the task.",
            )

        # Step 2 – build SolutionPath objects
        from src.solution_path_registry import SolutionPath  # local import to avoid circulars
        paths = self._build_paths(task_id, matches)

        # Step 3 – rank by combined score
        ranked = sorted(paths, key=lambda p: p.combined_score, reverse=True)

        # Step 4 – register alternatives
        self._solution_registry.register(task_id, ranked)

        # Step 5 – gate validation (best-first)
        approved_path, gate_results = self._validate_paths(ranked)

        # Step 6 – return result
        if approved_path is not None:
            return RoutingResult(
                status=RouteStatus.APPROVED,
                task_id=task_id,
                solution_path=approved_path,
                alternatives=ranked,
                gate_results=gate_results,
            )

        # Check whether any path needs HITL vs full block
        hitl_path = next((p for p in ranked if p.requires_hitl), None)
        if hitl_path is not None:
            return RoutingResult(
                status=RouteStatus.HITL,
                task_id=task_id,
                solution_path=hitl_path,
                alternatives=ranked,
                gate_results=gate_results,
            )

        return RoutingResult(
            status=RouteStatus.BLOCKED,
            task_id=task_id,
            alternatives=ranked,
            rejection_reason="All candidate paths failed gate validation.",
            gate_results=gate_results,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _extract_task_text(self, task: Dict[str, Any]) -> str:
        """Extract a single search string from the task dict."""
        if "task" in task:
            return str(task["task"])
        if "description" in task:
            return str(task["description"])
        if "intent" in task:
            return str(task["intent"])
        # Fallback: join all string values
        return " ".join(str(v) for v in task.values() if isinstance(v, str))

    def _match_capabilities(
        self, task_text: str, task: Dict[str, Any]
    ) -> List[CapabilityMatch]:
        """
        Ask the Librarian to search its knowledge base, then cross-reference
        with the ModuleRegistry to build :class:`CapabilityMatch` objects.
        """
        matches: List[CapabilityMatch] = []

        # Librarian knowledge search
        knowledge_hits = self._librarian.search_knowledge(task_text)
        for hit in knowledge_hits:
            score = self._relevance_score(task_text, hit)
            matches.append(
                CapabilityMatch(
                    capability_id=hit.topic,
                    module_path=f"src.{hit.category}",
                    score=score,
                    parameters=dict(task),
                )
            )

        # Module registry capability search (fallback / supplement)
        registry_caps = self._registry.get_capabilities()
        for cap_name, module_names in registry_caps.items():
            if task_text.lower() in cap_name.lower() or any(
                word in cap_name.lower()
                for word in task_text.lower().split()
                if len(word) > 3
            ):
                for mod_name in module_names[:1]:  # take best module per capability
                    # Avoid duplicating Librarian hits
                    existing_ids = {m.capability_id for m in matches}
                    if cap_name not in existing_ids:
                        matches.append(
                            CapabilityMatch(
                                capability_id=cap_name,
                                module_path=f"src.{mod_name}",
                                score=0.5,
                                parameters=dict(task),
                            )
                        )

        return matches

    def _relevance_score(self, query: str, knowledge: Any) -> float:
        """Compute a 0.0–1.0 relevance score for a knowledge hit."""
        query_words = set(query.lower().split())
        topic_words = set(knowledge.topic.lower().split())
        desc_words = set(knowledge.description.lower().split())
        all_words = topic_words | desc_words
        overlap = len(query_words & all_words)
        if not query_words:
            return 0.0
        return min(1.0, overlap / len(query_words))

    def _build_paths(
        self, task_id: str, matches: List[CapabilityMatch]
    ) -> List["SolutionPath"]:
        """Build SolutionPath dataclasses, weighting by historical success rate."""
        from src.solution_path_registry import SolutionPath

        paths = []
        for match in matches:
            feedback_weight = self._solution_registry.get_success_rate(
                match.capability_id
            )
            paths.append(
                SolutionPath(
                    path_id=str(uuid.uuid4()),
                    task_id=task_id,
                    capability_id=match.capability_id,
                    module_path=match.module_path,
                    score=match.score * feedback_weight,
                    librarian_score=match.score,
                    feedback_weight=feedback_weight,
                    cost_estimate=match.cost_estimate,
                    determinism=match.determinism,
                    requires_hitl=match.requires_hitl,
                    parameters=match.parameters,
                    wingman=match.wingman,
                )
            )
        return paths

    def _validate_paths(
        self, ranked_paths: List["SolutionPath"]
    ) -> tuple[Optional["SolutionPath"], Dict[str, Any]]:
        """
        Run gate validation best-first.

        If no GovernanceKernel is configured, every path is approved
        (permissive default — suitable for development).
        """
        gate_results: Dict[str, Any] = {}

        if self._governance is None:
            # No governance — approve best path unconditionally
            if ranked_paths:
                best = ranked_paths[0]
                gate_results[best.path_id] = {"status": "approved", "gates": []}
                return best, gate_results
            return None, gate_results

        for path in ranked_paths:
            try:
                result = self._governance.validate_path(path)
                gate_results[path.path_id] = result
                if result.get("approved", False):
                    return path, gate_results
            except Exception as exc:
                logger.warning(
                    "Gate validation error for path %s: %s", path.path_id, exc
                )
                gate_results[path.path_id] = {"error": str(exc)}

        return None, gate_results
