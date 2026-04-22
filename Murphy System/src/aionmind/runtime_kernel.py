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

        # Per-subsystem capability counts populated by the bridge
        # loaders.  Surfaced via ``status()`` so callers can see what
        # got registered without inspecting the whole registry.
        self._bridge_counts: Dict[str, int] = {}

        # Phase 2 (E25) — in-process outcome counter for
        # ``cognitive_execute``.  Exposed via ``metrics()`` /
        # ``GET /api/aionmind/metrics``.  Pre-seeded with every
        # outcome key so consumers get a stable schema even before
        # any traffic.
        self._aionmind_metrics: Dict[str, int] = {
            "calls_total": 0,
            "auto_approved": 0,
            "pending_approval": 0,
            "no_candidates": 0,
            "executed": 0,
            "failed": 0,
            # P1b (FORGE-KERNEL-001): out-of-band pipelines (currently
            # the Demo Forge ``/api/demo/generate-deliverable`` route)
            # record their executions through ``record_external_execution``
            # so the operator audit log + outcome KPI strip reflect
            # Forge usage too.  ``executed_external`` covers successes
            # and ``failed_external`` covers failures; we keep the
            # counters separate from ``executed``/``failed`` so an
            # operator can tell kernel-driven work from Forge demo
            # work at a glance.
            "executed_external": 0,
            "failed_external": 0,
        }

        # Phase 2 (E26) — append-only JSONL audit log path.  When
        # set, every ``cognitive_execute`` call appends one line.
        # ``None`` disables persistence (default for tests / dev).
        self._audit_log_path: Optional[str] = None

        # Gap 1 — bot inventory → capability bridge
        if auto_bridge_bots:
            self._bridge_bot_capabilities()
            # Phase 2 (C9–C16) — subsystem capability bridges.  Each
            # bridge is best-effort: if the underlying subsystem cannot
            # be imported, the bridge still registers its capabilities
            # with stub handlers so plans surface them and a clear
            # ``unavailable`` payload is returned at execute time.
            self._bridge_subsystem_capabilities()

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
                self._bridge_counts["bot_inventory"] = count
        except Exception as exc:
            logger.debug("Bot capability bridge unavailable — skipped: %s", exc, exc_info=True)

    def _bridge_subsystem_capabilities(self) -> None:
        """Auto-load every Phase-2 subsystem bridge.

        Each bridge is wrapped in its own try/except so a single
        broken subsystem cannot block the others.  After all bridges
        run a single startup-summary line is emitted (E24 — per
        subsystem totals) so operators can see what made it into the
        registry without trawling per-bridge log lines.
        """
        # Each entry: (logical_name, import_path, loader_attr).
        bridges = [
            ("automations", "aionmind.automations_capability_bridge",
             "load_automations_capabilities_into_kernel"),
            ("hitl", "aionmind.hitl_capability_bridge",
             "load_hitl_capabilities_into_kernel"),
            ("boards", "aionmind.boards_capability_bridge",
             "load_boards_capabilities_into_kernel"),
            ("founder", "aionmind.founder_capability_bridge",
             "load_founder_capabilities_into_kernel"),
            ("production", "aionmind.production_capability_bridge",
             "load_production_capabilities_into_kernel"),
            ("integration_bus", "aionmind.integration_bus_capability_bridge",
             "load_integration_bus_capabilities_into_kernel"),
            ("document", "aionmind.document_capability_bridge",
             "load_document_capabilities_into_kernel"),
        ]
        for name, module_path, loader_name in bridges:
            try:
                module = __import__(module_path, fromlist=[loader_name])
                loader = getattr(module, loader_name)
                count = loader(self)
                if count:
                    self._bridge_counts[name] = count
            except Exception as exc:  # pragma: no cover - defensive
                logger.debug(
                    "Subsystem bridge %s unavailable — skipped: %s",
                    name,
                    exc,
                    exc_info=True,
                )
        # E24 — single per-subsystem summary line.
        if self._bridge_counts:
            summary = ", ".join(
                f"{n}={c}" for n, c in sorted(self._bridge_counts.items())
            )
            logger.info(
                "AionMind capability bridges loaded (%d total): %s",
                self._registry.count(),
                summary,
            )

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

        self._aionmind_metrics["calls_total"] += 1

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
            self._aionmind_metrics["no_candidates"] += 1
            result = {
                "pipeline": "aionmind",
                "context_id": ctx.context_id,
                "status": "no_candidates",
                "detail": "Reasoning engine produced no candidate graphs — "
                          "check registered capabilities.",
            }
            self._append_audit_log(result, actor=actor, task_type=task_type)
            return result

        # Step 3 — select best
        graph = self.select(candidates, ctx)
        if graph is None:
            graph = candidates[0]

        # Step 4 — approval gate
        auto_approved_now = False
        if auto_approve and _risk_le(ctx.risk_level, max_auto_approve_risk):
            graph.approved = True
            graph.approved_by = approver
            auto_approved_now = True
            self._aionmind_metrics["auto_approved"] += 1
        elif not graph.approved:
            self._aionmind_metrics["pending_approval"] += 1
            result = {
                "pipeline": "aionmind",
                "context_id": ctx.context_id,
                "graph_id": graph.graph_id,
                "status": "pending_approval",
                "auto_approved": False,
                "graph": graph.model_dump(),
                "note": "Graph requires human approval before execution.",
            }
            self._append_audit_log(result, actor=actor, task_type=task_type)
            return result

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

        status_val = state.status.value
        if status_val == "completed":
            self._aionmind_metrics["executed"] += 1
        elif status_val == "failed":
            self._aionmind_metrics["failed"] += 1

        result = {
            "pipeline": "aionmind",
            "context_id": ctx.context_id,
            "graph_id": graph.graph_id,
            "execution_id": state.execution_id,
            "status": status_val,
            "auto_approved": auto_approved_now,
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
        self._append_audit_log(result, actor=actor, task_type=task_type)
        return result

    # ── Observability ─────────────────────────────────────────────

    def metrics(self) -> Dict[str, int]:
        """Return a snapshot of the cognitive_execute outcome counters.

        Phase 2 / E25.  Counters are monotonic for the life of the
        kernel process; callers wanting deltas should diff successive
        snapshots.

        P1b: includes ``executed_external`` and ``failed_external``
        counters that out-of-band pipelines bump via
        :meth:`record_external_execution`.
        """
        return dict(self._aionmind_metrics)

    def record_external_execution(
        self,
        *,
        actor: Optional[str],
        task_type: str,
        status: str,
        summary: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Record an out-of-band pipeline execution against the kernel
        audit log + outcome metrics.

        Phase 2 / P1b (FORGE-KERNEL-001).  This is the audit-only
        complement to :meth:`cognitive_execute`: pipelines that run
        outside the AionMind reasoning/execution loop (today, the
        Demo Forge ``/api/demo/generate-deliverable`` route) call
        this on completion so the operator surfaces (D20 metrics,
        D23 audit tab) reflect their activity.

        Unlike ``cognitive_execute`` this method:

        * does **not** build a context, plan, select, or execute;
        * does **not** consult the risk policy or approval gate;
        * does **not** mutate the capability registry or memory;
        * is safe to call from any thread (the underlying file write
          uses one append-syscall per entry, matching ``_append_audit_log``).

        Parameters
        ----------
        actor : str, optional
            Identity label of the human / service that initiated the
            external execution.  Recorded on the audit entry.  When
            falsy, the audit entry stores ``"anonymous"``.
        task_type : str
            Routing label for the external pipeline (e.g.
            ``"demo_forge"``).  Recorded on the audit entry and on
            the metrics counter so an operator can tell external
            work apart from kernel-driven work.
        status : str
            Free-form outcome label.  Anything other than ``"completed"``
            is treated as a failure for metrics purposes.  Recorded
            verbatim on the audit entry.
        summary : str, optional
            Short human-readable summary (e.g. the Forge query) — kept
            short so the audit log stays operator-readable.  The first
            240 characters are stored.
        details : dict, optional
            Free-form structured details (provider, scenario, latency,
            etc.) merged into the audit entry under ``external``.

        Returns
        -------
        dict
            The audit entry that was appended (or would have been, if
            no audit log path is configured).  Useful for tests and
            for callers that want to echo the audit row back to the
            client.
        """
        # ── Counters first (cheap and always available) ────────────────
        if status == "completed":
            self._aionmind_metrics["executed_external"] += 1
        else:
            self._aionmind_metrics["failed_external"] += 1

        # ── Build the audit entry ──────────────────────────────────────
        import time as _time

        entry: Dict[str, Any] = {
            "ts": _time.time(),
            "actor": actor or "anonymous",
            "task_type": task_type,
            "status": status,
            # Mark the entry as external so a UI / audit reader can
            # filter or label it differently from kernel-driven rows.
            "source": "external",
            "auto_approved": False,
        }
        if summary:
            entry["summary"] = str(summary)[:240]
        if details:
            # Defensive copy so callers can't mutate after recording.
            try:
                entry["external"] = dict(details)
            except Exception:
                entry["external"] = {"_repr": repr(details)[:240]}

        # ── Append to JSONL audit log (best-effort, mirrors _append_audit_log) ──
        path = self._audit_log_path
        if path:
            try:
                import json as _json
                import os as _os

                parent = _os.path.dirname(path)
                if parent:
                    _os.makedirs(parent, exist_ok=True)
                with open(path, "a", encoding="utf-8") as fh:
                    fh.write(_json.dumps(entry, separators=(",", ":")) + "\n")
            except Exception as exc:  # pragma: no cover - defensive
                logger.debug("audit-log append (external) failed: %s", exc, exc_info=True)
        return entry

    def set_audit_log_path(self, path: Optional[str]) -> None:
        """Configure the append-only JSONL audit log destination.

        Phase 2 / E26.  When *path* is set, every ``cognitive_execute``
        outcome appends one JSON line.  Pass ``None`` to disable.
        Callers are responsible for log rotation.
        """
        self._audit_log_path = path

    def audit_log_path(self) -> Optional[str]:
        """Return the configured JSONL audit log path, or ``None``.

        Phase 2 / D21 — used by the read-only ``/api/aionmind/audit``
        endpoint to expose the *enabled* / *disabled* state cleanly
        without having to introspect private state.
        """
        return self._audit_log_path

    def tail_audit_log(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Return up to *limit* most-recent JSONL audit entries (newest-first).

        Phase 2 / D21.  Read-only accessor backing the
        ``/api/aionmind/audit`` endpoint.  The semantics:

        * If no path is configured, returns ``[]``.
        * If the file does not yet exist, returns ``[]`` (the kernel
          appends lazily on first ``cognitive_execute``).
        * Lines that fail JSON parsing are skipped, not raised — the
          audit log is best-effort by design (E26).
        * *limit* is clamped into ``[1, 500]`` to keep the response
          bounded.
        """
        path = self._audit_log_path
        if not path:
            return []
        try:
            limit = max(1, min(500, int(limit)))
        except (TypeError, ValueError):
            limit = 50
        try:
            import json as _json
            import os as _os

            if not _os.path.exists(path):
                return []
            # Read the whole file then keep the tail.  The audit log
            # is bounded by operator-managed rotation so this is fine
            # for the intended scale; a true "tail" is a follow-up.
            with open(path, "r", encoding="utf-8") as fh:
                lines = fh.readlines()
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("audit-log read failed: %s", exc, exc_info=True)
            return []

        out: List[Dict[str, Any]] = []
        # Iterate the tail newest-first, stopping once we have *limit*
        # parseable entries.
        for raw in reversed(lines):
            line = raw.strip()
            if not line:
                continue
            try:
                entry = _json.loads(line)
            except Exception:
                continue
            if not isinstance(entry, dict):
                continue
            out.append(entry)
            if len(out) >= limit:
                break
        return out

    def _append_audit_log(
        self,
        result: Dict[str, Any],
        *,
        actor: Optional[str],
        task_type: str,
    ) -> None:
        """Best-effort append to the JSONL audit log.

        Failures are logged at DEBUG and swallowed — audit-log
        persistence MUST NOT break the request path.
        """
        path = self._audit_log_path
        if not path:
            return
        try:
            import json as _json
            import os as _os
            import time as _time

            entry = {
                "ts": _time.time(),
                "actor": actor or "anonymous",
                "task_type": task_type,
                "status": result.get("status"),
                "context_id": result.get("context_id"),
                "graph_id": result.get("graph_id"),
                "execution_id": result.get("execution_id"),
                "auto_approved": result.get("auto_approved", False),
            }
            parent = _os.path.dirname(path)
            if parent:
                _os.makedirs(parent, exist_ok=True)
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(_json.dumps(entry, separators=(",", ":")) + "\n")
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("audit-log append failed: %s", exc, exc_info=True)

    def status(self) -> Dict[str, Any]:
        """Return a summary of the kernel's current state."""
        return {
            "capabilities_registered": self._registry.count(),
            "bridge_counts": dict(self._bridge_counts),
            "memory": self._memory.stats(),
            "pending_proposals": len(
                self._optimization.list_proposals(
                    status=ProposalStatus.PENDING_REVIEW
                )
            ),
        }
