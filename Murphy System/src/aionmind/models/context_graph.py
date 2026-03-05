"""
Layer 1 — ContextGraph: a lightweight graph of nodes and edges representing
world-state and workflow-state that accompanies a ContextObject.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class NodeType(str, Enum):
    """Type of a node in the context graph."""

    TASK = "task"
    WORKFLOW = "workflow"
    MEMORY = "memory"
    AGENT = "agent"
    EVIDENCE = "evidence"
    CONSTRAINT = "constraint"
    APPROVAL = "approval"


class EdgeType(str, Enum):
    """Type of a directed edge between context-graph nodes."""

    DEPENDS_ON = "depends_on"
    RELATED_TO = "related_to"
    PRODUCES = "produces"
    CONSUMES = "consumes"
    REQUIRES_APPROVAL = "requires_approval"
    INFORMS = "informs"


class ContextNode(BaseModel):
    """A single node in the context graph."""

    node_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
    )
    node_type: NodeType
    label: str = ""
    data: Dict[str, Any] = Field(default_factory=dict)


class ContextEdge(BaseModel):
    """A directed edge in the context graph."""

    edge_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
    )
    source_id: str
    target_id: str
    edge_type: EdgeType
    weight: float = 1.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ContextGraph(BaseModel):
    """Graph overlay representing world-state & workflow-state.

    Invariant: the graph is informational only — it never triggers execution.
    """

    graph_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
    )
    context_id: str = Field(
        ...,
        description="The ContextObject this graph belongs to.",
    )
    nodes: List[ContextNode] = Field(default_factory=list)
    edges: List[ContextEdge] = Field(default_factory=list)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    # ── query helpers ─────────────────────────────────────────────

    def get_node(self, node_id: str) -> Optional[ContextNode]:
        """Return the node with the given ID, or ``None``."""
        for n in self.nodes:
            if n.node_id == node_id:
                return n
        return None

    def get_edges_from(self, node_id: str) -> List[ContextEdge]:
        """Return all edges originating from *node_id*."""
        return [e for e in self.edges if e.source_id == node_id]

    def get_edges_to(self, node_id: str) -> List[ContextEdge]:
        """Return all edges pointing to *node_id*."""
        return [e for e in self.edges if e.target_id == node_id]

    def add_node(self, node: ContextNode) -> None:
        self.nodes.append(node)

    def add_edge(self, edge: ContextEdge) -> None:
        self.edges.append(edge)
