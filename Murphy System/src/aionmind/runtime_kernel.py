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


# Risk tiers ordered from least to most risky.  Used by
# ``cognitive_execute`` to compare a context's risk against the
# caller-supplied ``max_auto_approve_risk`` ceiling.
_RISK_ORDER: Dict[RiskLevel, int] = {
    RiskLevel.LOW: 0,
    RiskLevel.MEDIUM: 1,
    RiskLevel.HIGH: 2,
    RiskLevel.CRITICAL: 3,
}


def _risk_le(actual: RiskLevel, ceiling: RiskLevel) -> bool:
    """Return True iff ``actual`` is at or below ``ceiling`` in risk."""
    return _RISK_ORDER.get(actual, 99) <= _RISK_ORDER.get(ceiling, -1)


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
        auto_bridge_bots: bool = True,
        auto_discover_rsc: bool = True,
    ) -> None:
        # Layer 1
        self._context_engine = ContextEngine()
        # Layer 2
        self._registry = CapabilityRegistry()
        self._reasoning = ReasoningEngine(self._registry)
        # Layer 3 — RSC wiring (Gap 2)
        effective_rsc = rsc_client
        if effective_rsc is None and auto_discover_rsc:
            effective_rsc = self._try_discover_rsc()
        self._stability = StabilityIntegration(
            stability_threshold=stability_threshold,
            rsc_client=effective_rsc,
        )
        # Layer 4
        self._orchestration = OrchestrationEngine(self._stability)
        # Layer 5
        self._memory = MemoryLayer()
        # Layer 6
        self._optimization = OptimizationEngine()

        # Gap 1 — bot inventory → capability bridge
        if auto_bridge_bots:
            self._bridge_bot_capabilities()

    # ── private bootstrap helpers ─────────────────────────────────

    def _bridge_bot_capabilities(self) -> None:
        """Auto-load bot_inventory_library capabilities into the registry."""
        try:
            from aionmind.bot_capability_bridge import (
                load_bot_capabilities_into_registry,
            )
            count = load_bot_capabilities_into_registry(self._registry)
            if count:
                logger.info("Auto-bridged %d bot capabilities.", count)
        except Exception as exc:
            logger.debug("Bot capability bridge unavailable — skipped: %s", exc, exc_info=True)

    @staticmethod
    def _try_discover_rsc() -> Optional[Any]:
        """Attempt to create an RSC adapter at startup."""
        try:
            from aionmind.rsc_client_adapter import create_rsc_adapter
            adapter = create_rsc_adapter(auto_discover=True)
            return adapter
        except Exception as exc:
            logger.debug("RSC auto-discovery unavailable: %s", exc, exc_info=True)
            return None

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

    def execute(
        self,
        graph: ExecutionGraphObject,
        *,
        actor: Optional[str] = None,
    ) -> OrchestrationState:
        """Execute an approved graph (Layer 4).

        Parameters
        ----------
        graph : ExecutionGraphObject
            The approved graph to execute.
        actor : str, optional
            Identity label of the human / service initiating execution.
            Recorded on :class:`OrchestrationState` and on every audit
            entry so the audit trail is attributable.

        Raises ``ValueError`` if the graph has not been approved.
        """
        state = self._orchestration.execute(graph, actor=actor)
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

    # ── Gap 3: WorkflowDAGEngine bridge ───────────────────────────

    def compile_to_dag(
        self,
        graph: ExecutionGraphObject,
        *,
        dag_engine: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Optionally compile an ExecutionGraphObject into a legacy
        WorkflowDAGEngine workflow for backward compatibility.

        Returns a dict with ``workflow_id`` and ``engine`` on success,
        or ``{"error": ...}`` on failure.
        """
        try:
            from aionmind.dag_bridge import compile_to_workflow_dag
            return compile_to_workflow_dag(graph, dag_engine=dag_engine)
        except Exception as exc:
            logger.debug("DAG bridge unavailable: %s", exc)
            return {"error": str(exc)}

    # ── Gap 5: Cognitive pipeline entry-point ─────────────────────

    def cognitive_execute(
        self,
        *,
        source: str = "api",
        raw_input: str = "",
        intent: str = "",
        task_type: str = "general",
        parameters: Optional[Dict[str, Any]] = None,
        auto_approve: bool = False,
        approver: str = "system",
        metadata: Optional[Dict[str, Any]] = None,
        actor: Optional[str] = None,
        max_auto_approve_risk: RiskLevel = RiskLevel.LOW,
    ) -> Dict[str, Any]:
        """High-level convenience that runs the full cognitive pipeline:
        ``build_context → plan → select → (approve) → execute``.

        This is the method existing endpoints (``/api/execute``,
        ``/api/forms/*``) call to route through AionMind.

        Parameters
        ----------
        source : str
            Origin label (e.g. ``"api"``, ``"form"``, ``"user"``).
        raw_input : str
            The user's natural-language request.
        intent : str
            Detected or declared intent.
        task_type : str
            Task classification (``"general"``, ``"automation"``, etc.).
        parameters : dict, optional
            Extra parameters forwarded as metadata.
        auto_approve : bool
            When ``True`` the selected graph is auto-approved (for low-risk
            tasks only; high-risk tasks still require human approval).
        approver : str
            Label for the approver when auto_approve is enabled.
        metadata : dict, optional
            Free-form metadata merged into the :class:`ContextObject`'s
            ``metadata`` field.  Used by Phase 1 to thread the
            ``founder``/``user_email`` flags down to capability handlers
            without overloading ``parameters``.
        actor : str, optional
            Identity label of the human / service that initiated the
            request.  Stored on :class:`OrchestrationState` and emitted
            on every audit entry so audit trails are attributable.
        max_auto_approve_risk : RiskLevel
            Maximum risk level eligible for auto-approval when
            ``auto_approve`` is set.  Defaults to ``LOW`` to preserve
            the kernel's no-autonomy contract; callers (e.g. the
            ``_auto_approve_for`` policy in ``app.py``) may raise this
            for owners who can self-approve MEDIUM-risk work.

        Returns
        -------
        dict
            Unified result with ``context``, ``graph``, ``execution``, and
            ``pipeline`` keys.
        """
        meta: Dict[str, Any] = dict(parameters or {})
        if metadata:
            # Caller-supplied metadata takes precedence over the
            # parameters-derived defaults so identity flags survive.
            meta.update(metadata)
        # ``task_type`` is the kernel's contract — always set it from
        # the dedicated argument so caller metadata cannot accidentally
        # override the routing label.
        meta["task_type"] = task_type
        if actor and "actor" not in meta:
            meta["actor"] = actor

        # Step 1 — build context
        risk = RiskLevel.LOW
        if task_type in ("integration", "deployment", "security"):
            risk = RiskLevel.MEDIUM
        ctx = self.build_context(
            source=source,
            raw_input=raw_input,
            intent=intent or raw_input,
            risk_level=risk,
            metadata=meta,
        )

        # Step 2 — plan
        candidates = self.plan(ctx, max_candidates=3)
        if not candidates:
            return {
                "pipeline": "aionmind",
                "context_id": ctx.context_id,
                "status": "no_candidates",
                "detail": "Reasoning engine produced no candidate graphs — "
                          "check registered capabilities.",
            }

        # Step 3 — select best
        graph = self.select(candidates, ctx)
        if graph is None:
            graph = candidates[0]

        # Step 4 — approval gate
        if auto_approve and _risk_le(ctx.risk_level, max_auto_approve_risk):
            graph.approved = True
            graph.approved_by = approver
        elif not graph.approved:
            return {
                "pipeline": "aionmind",
                "context_id": ctx.context_id,
                "graph_id": graph.graph_id,
                "status": "pending_approval",
                "graph": graph.model_dump(),
                "note": "Graph requires human approval before execution.",
            }

        # Step 5 — execute
        state = self.execute(graph, actor=actor)

        # Step 6 — memory archival
        self._memory.store_intermediate_state(
            f"pipeline:{state.execution_id}",
            {
                "context_id": ctx.context_id,
                "graph_id": graph.graph_id,
                "execution_id": state.execution_id,
                "status": state.status.value,
                "task_type": task_type,
                "raw_input": raw_input,
            },
        )

        return {
            "pipeline": "aionmind",
            "context_id": ctx.context_id,
            "graph_id": graph.graph_id,
            "execution_id": state.execution_id,
            "status": state.status.value,
            "audit_trail": [
                {
                    "timestamp": a.timestamp,
                    "node_id": a.node_id,
                    "event": a.event,
                    "details": a.details,
                }
                for a in state.audit_trail
            ],
        }

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
