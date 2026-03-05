"""
AionMind Runtime Kernel — Murphy System 2.0a (Embedded).

The kernel is the **façade** that ties all six cognitive layers together into a
single entry-point.  In Murphy 2.0b this façade will become a dedicated service
with a stable API; for 2.0a it lives in-process.

Non-negotiable constraint: NO AUTONOMY.
  - High-risk / low-confidence / irreversible operations require human approval.
  - Telemetry and learning loops never trigger execution actions directly.
  - Optimization outputs are proposals / recommendations only.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

from aionmind.capability_registry import Capability, CapabilityRegistry
from aionmind.context_engine import ContextEngine
from aionmind.memory_layer import MemoryLayer
from aionmind.models.context_graph import ContextGraph
from aionmind.models.context_object import ContextObject, Priority, RiskLevel
from aionmind.models.execution_graph import ExecutionGraphObject
from aionmind.models.proposals import OptimizationProposal, ProposalStatus
from aionmind.optimization_engine import OptimizationEngine
from aionmind.orchestration_engine import OrchestrationEngine, OrchestrationState
from aionmind.reasoning_engine import ReasoningEngine
from aionmind.stability_integration import StabilityIntegration

logger = logging.getLogger(__name__)


class AionMindKernel:
    """Murphy 2.0a runtime kernel — Collaborative Orchestrator of Orchestrators.

    Usage
    -----
    >>> kernel = AionMindKernel()
    >>> kernel.register_capability(Capability(...))
    >>> ctx = kernel.build_context(source="user", raw_input="Deploy v2")
    >>> candidates = kernel.plan(ctx)
    >>> graph = kernel.select(candidates, ctx)
    >>> # Human approves the graph …
    >>> graph.approved = True; graph.approved_by = "operator"
    >>> state = kernel.execute(graph)
    """

    def __init__(
        self,
        *,
        stability_threshold: float = 0.5,
        rsc_client: Optional[Any] = None,
    ) -> None:
        # Layer 1
        self._context_engine = ContextEngine()
        # Layer 2
        self._registry = CapabilityRegistry()
        self._reasoning = ReasoningEngine(self._registry)
        # Layer 3
        self._stability = StabilityIntegration(
            stability_threshold=stability_threshold,
            rsc_client=rsc_client,
        )
        # Layer 4
        self._orchestration = OrchestrationEngine(self._stability)
        # Layer 5
        self._memory = MemoryLayer()
        # Layer 6
        self._optimization = OptimizationEngine()

    # ── accessors ─────────────────────────────────────────────────

    @property
    def registry(self) -> CapabilityRegistry:
        return self._registry

    @property
    def memory(self) -> MemoryLayer:
        return self._memory

    @property
    def optimization(self) -> OptimizationEngine:
        return self._optimization

    @property
    def orchestration(self) -> OrchestrationEngine:
        return self._orchestration

    @property
    def stability(self) -> StabilityIntegration:
        return self._stability

    # ── Layer 1: Context ──────────────────────────────────────────

    def build_context(self, **kwargs: Any) -> ContextObject:
        """Build a :class:`ContextObject` (delegates to :class:`ContextEngine`)."""
        ctx = self._context_engine.build_context(**kwargs)
        # Persist in STM
        self._memory.store_intermediate_state(
            f"ctx:{ctx.context_id}", ctx.model_dump()
        )
        return ctx

    def build_graph(self, context: ContextObject) -> ContextGraph:
        """Build a :class:`ContextGraph` for an existing context."""
        return self._context_engine.build_graph(context)

    # ── Layer 2: Planning ─────────────────────────────────────────

    def register_capability(self, capability: Capability) -> None:
        self._registry.register(capability)

    def register_handler(
        self, capability_id: str, handler: Callable[..., Any]
    ) -> None:
        self._orchestration.register_handler(capability_id, handler)

    def plan(
        self,
        context: ContextObject,
        *,
        max_candidates: int = 3,
    ) -> List[ExecutionGraphObject]:
        """Generate candidate execution graphs (Layer 2)."""
        candidates = self._reasoning.generate_candidates(
            context, max_candidates=max_candidates
        )
        # Store candidates in STM
        for g in candidates:
            self._memory.store_intermediate_state(
                f"candidate:{g.graph_id}",
                {"graph_id": g.graph_id, "context_id": context.context_id},
            )
        return candidates

    def select(
        self,
        candidates: List[ExecutionGraphObject],
        context: ContextObject,
    ) -> Optional[ExecutionGraphObject]:
        """Select the best execution graph (Layer 2)."""
        return self._reasoning.select_best(candidates, context)

    # ── Layer 4: Execution ────────────────────────────────────────

    def execute(self, graph: ExecutionGraphObject) -> OrchestrationState:
        """Execute an approved graph (Layer 4).

        Raises ``ValueError`` if the graph has not been approved.
        """
        state = self._orchestration.execute(graph)
        # Store result in STM for immediate access
        self._memory.store_intermediate_state(
            f"exec:{state.execution_id}",
            {
                "execution_id": state.execution_id,
                "graph_id": state.graph_id,
                "status": state.status.value,
            },
        )
        return state

    # ── Layer 5: Memory convenience ───────────────────────────────

    def archive_execution(self, execution_id: str) -> None:
        """Move an execution result from STM to LTM."""
        key = f"exec:{execution_id}"
        data = self._memory.retrieve_context(key)
        if data:
            self._memory.archive_workflow(key, data)
            self._memory.delete_stm(key)

    # ── Layer 6: Proposals (convenience delegates) ────────────────

    def list_proposals(
        self, *, status: Optional[ProposalStatus] = None
    ) -> List[OptimizationProposal]:
        return self._optimization.list_proposals(status=status)

    def approve_proposal(self, proposal_id: str, approver: str) -> bool:
        return self._optimization.approve_proposal(proposal_id, approver)

    # ── Observability ─────────────────────────────────────────────

    def status(self) -> Dict[str, Any]:
        """Return a summary of the kernel's current state."""
        return {
            "capabilities_registered": self._registry.count(),
            "memory": self._memory.stats(),
            "pending_proposals": len(
                self._optimization.list_proposals(
                    status=ProposalStatus.PENDING_REVIEW
                )
            ),
        }
