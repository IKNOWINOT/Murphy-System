"""
Layer 2 — Collaborative Reasoning Engine (Orchestrator-of-Orchestrators).

Determines *how* orchestration should occur:
  1. Evaluate available capabilities from the registry.
  2. Generate candidate orchestration graphs (DAGs).
  3. Score and select the best graph using a deterministic policy.
  4. Inject mandatory HITL checkpoints and RSC check nodes.

Output is an :class:`ExecutionGraphObject` ready for the Orchestration Engine.

Hard invariants
---------------
* Selection is **deterministic and verifiable** — no opaque LLM magic.
* Every generated graph includes HITL checkpoints for high-risk nodes.
* Graphs are proposals until approved.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Callable, Dict, List, Optional

from aionmind.capability_registry import Capability, CapabilityRegistry
from aionmind.models.context_object import ContextObject, RiskLevel
from aionmind.models.execution_graph import (
    ExecutionEdge,
    ExecutionGraphObject,
    ExecutionNode,
    ExecutionNodeType,
)

logger = logging.getLogger(__name__)


def _default_score_fn(
    graph: ExecutionGraphObject, context: ContextObject
) -> float:
    """Deterministic scoring: prefer fewer nodes, penalise high-risk nodes."""
    base = 100.0
    base -= len(graph.nodes) * 2  # brevity bonus
    for n in graph.nodes:
        if n.requires_approval:
            base -= 1  # small cost for each approval gate
    return max(base, 0.0)


class ReasoningEngine:
    """Generates, scores and selects execution graphs.

    Parameters
    ----------
    registry : CapabilityRegistry
        Source of available capabilities.
    score_fn : callable, optional
        Custom deterministic scoring function.
    """

    def __init__(
        self,
        registry: CapabilityRegistry,
        *,
        score_fn: Optional[
            Callable[[ExecutionGraphObject, ContextObject], float]
        ] = None,
    ) -> None:
        self._registry = registry
        self._score_fn = score_fn or _default_score_fn

    # ── public API ────────────────────────────────────────────────

    def generate_candidates(
        self,
        context: ContextObject,
        *,
        max_candidates: int = 3,
    ) -> List[ExecutionGraphObject]:
        """Produce up to *max_candidates* orchestration graphs.

        Strategy
        --------
        1. Match capabilities to the context via tags / intent.
        2. For each matched set, build a linear chain, a fan-out/fan-in,
           and a sequential-with-gate variant.
        3. Inject HITL and RSC nodes automatically.
        """
        matched = self._match_capabilities(context)
        if not matched:
            logger.warning("No capabilities matched context %s", context.context_id)
            return []

        candidates: List[ExecutionGraphObject] = []

        # Strategy A — linear chain
        if max_candidates >= 1:
            candidates.append(
                self._build_linear_chain(context, matched)
            )

        # Strategy B — fan-out / fan-in
        if max_candidates >= 2 and len(matched) >= 2:
            candidates.append(
                self._build_fanout(context, matched)
            )

        # Strategy C — sequential with extra gate checks
        if max_candidates >= 3:
            candidates.append(
                self._build_gated_sequential(context, matched)
            )

        return candidates[:max_candidates]

    def select_best(
        self,
        candidates: List[ExecutionGraphObject],
        context: ContextObject,
    ) -> Optional[ExecutionGraphObject]:
        """Pick the highest-scoring graph.  Deterministic and auditable."""
        if not candidates:
            return None
        for g in candidates:
            g.score = self._score_fn(g, context)
        best = max(candidates, key=lambda g: g.score)
        best.rationale = (
            f"Selected graph {best.graph_id} with score {best.score:.2f} "
            f"over {len(candidates)} candidate(s)."
        )
        logger.info(
            "Selected graph %s (score=%.2f) for context %s",
            best.graph_id,
            best.score,
            context.context_id,
        )
        return best

    # ── internals ─────────────────────────────────────────────────

    def _match_capabilities(self, context: ContextObject) -> List[Capability]:
        """Find capabilities relevant to *context*."""
        # Simple heuristic: match on intent keywords as tags
        tags = [t.strip().lower() for t in context.intent.split() if t.strip()]
        if tags:
            results = self._registry.search(tags=tags)
            if results:
                return results
        # Fallback: return all registered capabilities
        return self._registry.list_all()

    def _inject_hitl_and_rsc(
        self,
        graph: ExecutionGraphObject,
        context: ContextObject,
    ) -> None:
        """Add mandatory HITL checkpoints for high-risk nodes and RSC checks."""
        is_high_risk = context.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)

        new_nodes: List[ExecutionNode] = []
        new_edges: List[ExecutionEdge] = []

        for node in list(graph.nodes):
            # Force approval on high-risk or capability-flagged nodes
            if is_high_risk or node.requires_approval:
                node.requires_approval = True

            # Insert RSC check before every capability call
            if node.node_type == ExecutionNodeType.CAPABILITY_CALL:
                rsc_node = ExecutionNode(
                    node_id=f"rsc-{node.node_id}",
                    node_type=ExecutionNodeType.RSC_CHECK,
                    label=f"RSC stability check before {node.label}",
                    depends_on=list(node.depends_on),  # same predecessors
                )
                # Re-wire: capability now depends on its RSC check
                node.depends_on = [rsc_node.node_id]
                new_nodes.append(rsc_node)
                new_edges.append(
                    ExecutionEdge(
                        source_id=rsc_node.node_id,
                        target_id=node.node_id,
                    )
                )

        graph.nodes.extend(new_nodes)
        graph.edges.extend(new_edges)

    def _build_linear_chain(
        self, context: ContextObject, caps: List[Capability]
    ) -> ExecutionGraphObject:
        graph = ExecutionGraphObject(context_id=context.context_id)
        prev_id: Optional[str] = None
        for cap in caps:
            node = ExecutionNode(
                node_type=ExecutionNodeType.CAPABILITY_CALL,
                capability_id=cap.capability_id,
                label=cap.name,
                requires_approval=cap.requires_approval,
                timeout_seconds=cap.timeout_seconds,
                depends_on=[prev_id] if prev_id else [],
            )
            graph.nodes.append(node)
            if prev_id:
                graph.edges.append(
                    ExecutionEdge(source_id=prev_id, target_id=node.node_id)
                )
            prev_id = node.node_id
        self._inject_hitl_and_rsc(graph, context)
        return graph

    def _build_fanout(
        self, context: ContextObject, caps: List[Capability]
    ) -> ExecutionGraphObject:
        graph = ExecutionGraphObject(context_id=context.context_id)
        # Fan-out: all caps run in parallel, then aggregate
        cap_ids: List[str] = []
        for cap in caps:
            node = ExecutionNode(
                node_type=ExecutionNodeType.CAPABILITY_CALL,
                capability_id=cap.capability_id,
                label=cap.name,
                requires_approval=cap.requires_approval,
                timeout_seconds=cap.timeout_seconds,
            )
            graph.nodes.append(node)
            cap_ids.append(node.node_id)
        # Aggregation node
        agg = ExecutionNode(
            node_type=ExecutionNodeType.AGGREGATION,
            label="aggregate_results",
            depends_on=cap_ids,
        )
        graph.nodes.append(agg)
        for cid in cap_ids:
            graph.edges.append(ExecutionEdge(source_id=cid, target_id=agg.node_id))
        self._inject_hitl_and_rsc(graph, context)
        return graph

    def _build_gated_sequential(
        self, context: ContextObject, caps: List[Capability]
    ) -> ExecutionGraphObject:
        graph = ExecutionGraphObject(context_id=context.context_id)
        prev_id: Optional[str] = None
        for cap in caps:
            # Gate check before each capability
            gate = ExecutionNode(
                node_type=ExecutionNodeType.GATE_CHECK,
                label=f"gate_before_{cap.name}",
                depends_on=[prev_id] if prev_id else [],
            )
            graph.nodes.append(gate)
            if prev_id:
                graph.edges.append(
                    ExecutionEdge(source_id=prev_id, target_id=gate.node_id)
                )

            node = ExecutionNode(
                node_type=ExecutionNodeType.CAPABILITY_CALL,
                capability_id=cap.capability_id,
                label=cap.name,
                requires_approval=cap.requires_approval,
                timeout_seconds=cap.timeout_seconds,
                depends_on=[gate.node_id],
            )
            graph.nodes.append(node)
            graph.edges.append(
                ExecutionEdge(source_id=gate.node_id, target_id=node.node_id)
            )
            prev_id = node.node_id

        self._inject_hitl_and_rsc(graph, context)
        return graph
