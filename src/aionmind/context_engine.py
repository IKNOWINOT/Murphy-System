"""
Layer 1 — Context Awareness Engine.

Converts raw inputs (user query, bot outputs, memory, telemetry, workflow
state) into a :class:`ContextObject` and an accompanying :class:`ContextGraph`.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional

from aionmind.models.context_graph import (
    ContextEdge,
    ContextGraph,
    ContextNode,
    EdgeType,
    NodeType,
)
from aionmind.models.context_object import ContextObject, Priority, RiskLevel

logger = logging.getLogger(__name__)


class ContextEngine:
    """Builds canonical :class:`ContextObject` + :class:`ContextGraph` pairs.

    This engine is **stateless** — it receives raw data and returns structured
    context.  It never triggers execution.
    """

    def build_context(
        self,
        *,
        source: str,
        raw_input: str = "",
        intent: str = "",
        priority: Priority = Priority.MEDIUM,
        risk_level: RiskLevel = RiskLevel.LOW,
        related_tasks: Optional[List[str]] = None,
        workflow_refs: Optional[List[str]] = None,
        memory_refs: Optional[List[str]] = None,
        constraints: Optional[List[str]] = None,
        evidence_refs: Optional[List[str]] = None,
        assumptions: Optional[List[str]] = None,
        risks: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ContextObject:
        """Create a validated :class:`ContextObject`."""
        ctx = ContextObject(
            source=source,
            raw_input=raw_input,
            intent=intent,
            priority=priority,
            risk_level=risk_level,
            related_tasks=related_tasks or [],
            workflow_refs=workflow_refs or [],
            memory_refs=memory_refs or [],
            constraints=constraints or [],
            evidence_refs=evidence_refs or [],
            assumptions=assumptions or [],
            risks=risks or [],
            metadata=metadata or {},
        )
        logger.info("Built ContextObject %s from source=%s", ctx.context_id, source)
        return ctx

    def build_graph(self, context: ContextObject) -> ContextGraph:
        """Derive a :class:`ContextGraph` from *context*.

        Creates nodes for every referenced task, workflow, memory entry, and
        evidence source, with edges linking them to a central context node.
        """
        graph = ContextGraph(context_id=context.context_id)

        # Central node representing the context itself
        root = ContextNode(
            node_id=context.context_id,
            node_type=NodeType.TASK,
            label=f"context:{context.intent or context.source}",
            data={"source": context.source, "intent": context.intent},
        )
        graph.add_node(root)

        # Task nodes
        for tid in context.related_tasks:
            node = ContextNode(node_id=tid, node_type=NodeType.TASK, label=f"task:{tid}")
            graph.add_node(node)
            graph.add_edge(
                ContextEdge(
                    source_id=root.node_id,
                    target_id=tid,
                    edge_type=EdgeType.RELATED_TO,
                )
            )

        # Workflow nodes
        for wid in context.workflow_refs:
            node = ContextNode(node_id=wid, node_type=NodeType.WORKFLOW, label=f"wf:{wid}")
            graph.add_node(node)
            graph.add_edge(
                ContextEdge(
                    source_id=root.node_id,
                    target_id=wid,
                    edge_type=EdgeType.RELATED_TO,
                )
            )

        # Memory nodes
        for mid in context.memory_refs:
            node = ContextNode(node_id=mid, node_type=NodeType.MEMORY, label=f"mem:{mid}")
            graph.add_node(node)
            graph.add_edge(
                ContextEdge(
                    source_id=mid,
                    target_id=root.node_id,
                    edge_type=EdgeType.INFORMS,
                )
            )

        # Evidence nodes
        for eid in context.evidence_refs:
            node = ContextNode(
                node_id=eid, node_type=NodeType.EVIDENCE, label=f"evidence:{eid}"
            )
            graph.add_node(node)
            graph.add_edge(
                ContextEdge(
                    source_id=eid,
                    target_id=root.node_id,
                    edge_type=EdgeType.INFORMS,
                )
            )

        # Constraint nodes
        for i, c in enumerate(context.constraints):
            cid = f"constraint-{context.context_id}-{i}"
            node = ContextNode(
                node_id=cid,
                node_type=NodeType.CONSTRAINT,
                label=c,
            )
            graph.add_node(node)
            graph.add_edge(
                ContextEdge(
                    source_id=cid,
                    target_id=root.node_id,
                    edge_type=EdgeType.INFORMS,
                )
            )

        logger.info(
            "Built ContextGraph %s with %d nodes, %d edges",
            graph.graph_id,
            len(graph.nodes),
            len(graph.edges),
        )
        return graph
