"""
Layer 2 — ExecutionGraphObject: the DAG produced by the Reasoning Engine
and consumed by the Dynamic Orchestration Engine (Layer 4).

Each node in the graph represents one orchestration step (capability
invocation, gate check, HITL checkpoint, etc.).
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ExecutionNodeType(str, Enum):
    """Kind of work a node represents."""

    CAPABILITY_CALL = "capability_call"
    GATE_CHECK = "gate_check"
    HITL_CHECKPOINT = "hitl_checkpoint"
    RSC_CHECK = "rsc_check"
    AGGREGATION = "aggregation"
    CONDITIONAL = "conditional"


class ExecutionNodeStatus(str, Enum):
    """Runtime status of a node."""

    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    PAUSED = "paused"


class ExecutionNode(BaseModel):
    """Single step in an execution graph."""

    node_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    node_type: ExecutionNodeType
    capability_id: Optional[str] = None
    label: str = ""
    depends_on: List[str] = Field(default_factory=list)
    status: ExecutionNodeStatus = ExecutionNodeStatus.PENDING
    requires_approval: bool = False
    timeout_seconds: float = 300.0
    max_retries: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)
    result: Optional[Any] = None
    error: Optional[str] = None


class ExecutionEdge(BaseModel):
    """Dependency edge between execution nodes."""

    edge_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_id: str
    target_id: str
    condition: Optional[str] = None


class ExecutionGraphObject(BaseModel):
    """Complete execution graph (DAG) for an orchestration task.

    Invariants
    ----------
    * The graph is a **proposal** until approved.  It does not execute itself.
    * Every high-risk node MUST have ``requires_approval = True``.
    * RSC check nodes are injected automatically before recursion expansion.
    """

    graph_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    context_id: str = Field(
        ..., description="The ContextObject that originated this graph."
    )
    nodes: List[ExecutionNode] = Field(default_factory=list)
    edges: List[ExecutionEdge] = Field(default_factory=list)
    approved: bool = Field(
        default=False,
        description="Whether the graph has been approved for execution.",
    )
    approved_by: Optional[str] = None
    rationale: str = Field(
        default="",
        description="Structured rationale for why this graph was chosen.",
    )
    score: float = Field(
        default=0.0,
        description="Deterministic selection score used to choose this graph.",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    # ── helpers ───────────────────────────────────────────────────

    def get_node(self, node_id: str) -> Optional[ExecutionNode]:
        for n in self.nodes:
            if n.node_id == node_id:
                return n
        return None

    def get_root_nodes(self) -> List[ExecutionNode]:
        """Return nodes with no incoming edges (entry points)."""
        targets = {e.target_id for e in self.edges}
        return [n for n in self.nodes if n.node_id not in targets]

    def get_dependents(self, node_id: str) -> List[ExecutionNode]:
        """Return nodes that depend on *node_id*."""
        dep_ids = {e.target_id for e in self.edges if e.source_id == node_id}
        return [n for n in self.nodes if n.node_id in dep_ids]

    def topological_order(self) -> List[str]:
        """Return node IDs in topological (execution) order."""
        in_degree: Dict[str, int] = {n.node_id: 0 for n in self.nodes}
        adj: Dict[str, List[str]] = {n.node_id: [] for n in self.nodes}
        for e in self.edges:
            adj[e.source_id].append(e.target_id)
            in_degree[e.target_id] = in_degree.get(e.target_id, 0) + 1

        queue = [nid for nid, deg in in_degree.items() if deg == 0]
        order: List[str] = []
        while queue:
            nid = queue.pop(0)
            order.append(nid)
            for dep in adj.get(nid, []):
                in_degree[dep] -= 1
                if in_degree[dep] == 0:
                    queue.append(dep)
        return order
