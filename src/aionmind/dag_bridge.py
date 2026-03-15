"""
WorkflowDAGEngine Bridge — compiles :class:`ExecutionGraphObject` into
:class:`WorkflowDAGEngine` workflows for backward compatibility with 1.0
execution paths.

The bridge is **optional** — callers can choose to use the native AionMind
orchestration engine or compile graphs into the legacy DAG engine.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from aionmind.models.execution_graph import (
    ExecutionGraphObject,
    ExecutionNode,
    ExecutionNodeType,
)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from workflow_dag_engine import (
        StepDefinition,
        WorkflowDAGEngine,
        WorkflowDefinition,
    )


def compile_to_workflow_dag(
    graph: ExecutionGraphObject,
    *,
    dag_engine: Optional[Any] = None,
) -> Dict[str, Any]:
    """Compile an :class:`ExecutionGraphObject` into a legacy WorkflowDAGEngine workflow.

    Parameters
    ----------
    graph : ExecutionGraphObject
        The AionMind execution graph to compile.
    dag_engine : WorkflowDAGEngine, optional
        An existing engine instance.  When ``None`` a fresh one is created.

    Returns
    -------
    dict
        ``{"workflow_id": ..., "step_count": ..., "engine": ...}`` on success,
        or ``{"error": ...}`` on failure.
    """
    try:
        from workflow_dag_engine import (
            StepDefinition,
            WorkflowDefinition,
        )
        from workflow_dag_engine import (
            WorkflowDAGEngine as WDE,
        )
    except ImportError:
        logger.warning("workflow_dag_engine not available — bridge skipped.")
        return {"error": "workflow_dag_engine not importable"}

    if dag_engine is None:
        dag_engine = WDE()

    # Build dependency map from edges: target_id → list of source_ids
    dep_map: Dict[str, List[str]] = {}
    for edge in graph.edges:
        dep_map.setdefault(edge.target_id, []).append(edge.source_id)

    # Convert each ExecutionNode to a StepDefinition
    steps: List[StepDefinition] = []
    for node in graph.nodes:
        action = _node_type_to_action(node)
        step = StepDefinition(
            step_id=node.node_id,
            name=node.label or f"{node.node_type.value}:{node.node_id[:8]}",
            action=action,
            depends_on=dep_map.get(node.node_id, []),
            timeout_seconds=node.timeout_seconds,
            max_retries=node.max_retries,
            metadata={
                "origin": "aionmind_bridge",
                "capability_id": node.capability_id or "",
                "node_type": node.node_type.value,
                "requires_approval": node.requires_approval,
            },
        )
        steps.append(step)

    workflow = WorkflowDefinition(
        workflow_id=f"am:{graph.graph_id}",
        name=f"AionMind graph {graph.graph_id[:8]}",
        description=f"Compiled from ExecutionGraphObject {graph.graph_id}",
        steps=steps,
        metadata={
            "source_graph_id": graph.graph_id,
            "context_id": graph.context_id,
            "approved": graph.approved,
            "approved_by": graph.approved_by,
        },
    )

    ok = dag_engine.register_workflow(workflow)
    if not ok:
        return {"error": "DAG validation failed (possible cycle or invalid deps)"}

    logger.info(
        "Compiled ExecutionGraphObject %s → WorkflowDAGEngine workflow %s (%d steps).",
        graph.graph_id,
        workflow.workflow_id,
        len(steps),
    )
    return {
        "workflow_id": workflow.workflow_id,
        "step_count": len(steps),
        "engine": dag_engine,
    }


def _node_type_to_action(node: ExecutionNode) -> str:
    """Map an ExecutionNode to a WorkflowDAGEngine action string."""
    if node.node_type == ExecutionNodeType.CAPABILITY_CALL:
        return node.capability_id or "capability_call"
    if node.node_type == ExecutionNodeType.GATE_CHECK:
        return "gate_check"
    if node.node_type == ExecutionNodeType.HITL_CHECKPOINT:
        return "hitl_checkpoint"
    if node.node_type == ExecutionNodeType.RSC_CHECK:
        return "rsc_check"
    if node.node_type == ExecutionNodeType.AGGREGATION:
        return "aggregation"
    if node.node_type == ExecutionNodeType.CONDITIONAL:
        return "conditional"
    return node.node_type.value
