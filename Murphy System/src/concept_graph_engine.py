"""
Concept Graph Engine — Structural Knowledge Graph for the Murphy System

Design Label: CGE-001 — Concept Dependency and Regulatory Graph
Owner: Core Platform
Contact: corey.gfc@gmail.com
Repository: https://github.com/IKNOWINOT/Murphy-System
Dependencies:
  - thread_safe_operations (capped_append for bounded collections)

Purpose:
  Maintains a directed graph of concepts, modules, regulations, actors,
  processes, data sources, and metrics.  Edges encode structural
  relationships such as dependency, production, consumption, regulation,
  operation, improvement, and conflict.  Query helpers surface missing
  dependencies, regulatory gaps, redundant modules, and cross-domain
  opportunities.  A Graph Connectivity Score (GCS) and composite
  graph-health metric provide at-a-glance quality indicators.

Safety invariants:
  - Thread-safe: all shared state guarded by Lock
  - Deterministic: no randomness, no LLM calls
  - Bounded: nodes capped at 10 000, edges at 50 000
  - Idempotent: identical inputs always yield identical outputs

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""
from __future__ import annotations

import hashlib
import json
import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Optional, Set, Tuple

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Node types
# ---------------------------------------------------------------------------
NODE_TYPE_CONCEPT: str = "Concept"
NODE_TYPE_MODULE: str = "Module"
NODE_TYPE_REGULATION: str = "Regulation"
NODE_TYPE_ACTOR: str = "Actor"
NODE_TYPE_PROCESS: str = "Process"
NODE_TYPE_DATA: str = "Data"
NODE_TYPE_METRIC: str = "Metric"

VALID_NODE_TYPES: FrozenSet[str] = frozenset({
    NODE_TYPE_CONCEPT,
    NODE_TYPE_MODULE,
    NODE_TYPE_REGULATION,
    NODE_TYPE_ACTOR,
    NODE_TYPE_PROCESS,
    NODE_TYPE_DATA,
    NODE_TYPE_METRIC,
})

# ---------------------------------------------------------------------------
# Edge types
# ---------------------------------------------------------------------------
EDGE_DEPENDS_ON: str = "depends_on"
EDGE_PRODUCES: str = "produces"
EDGE_CONSUMES: str = "consumes"
EDGE_REGULATED_BY: str = "regulated_by"
EDGE_OPERATES_IN: str = "operates_in"
EDGE_IMPROVES: str = "improves"
EDGE_CONFLICTS_WITH: str = "conflicts_with"

VALID_EDGE_TYPES: FrozenSet[str] = frozenset({
    EDGE_DEPENDS_ON,
    EDGE_PRODUCES,
    EDGE_CONSUMES,
    EDGE_REGULATED_BY,
    EDGE_OPERATES_IN,
    EDGE_IMPROVES,
    EDGE_CONFLICTS_WITH,
})

# ---------------------------------------------------------------------------
# Capacity limits
# ---------------------------------------------------------------------------
MAX_NODES: int = 10_000
MAX_EDGES: int = 50_000


# ---------------------------------------------------------------------------
# Frozen result dataclasses
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class GraphHealthResult:
    """Immutable snapshot of graph-health metrics."""

    node_coverage: float
    dependency_completeness: float
    regulatory_coverage: float
    redundancy_score: float
    cache_key: str


@dataclass(frozen=True)
class CrossDomainOpportunity:
    """Immutable record of a cross-domain structural similarity."""

    concept_a: str
    concept_b: str
    shared_targets: Tuple[str, ...]


# ---------------------------------------------------------------------------
# ConceptGraphEngine
# ---------------------------------------------------------------------------
class ConceptGraphEngine:
    """Directed knowledge graph with bounded storage and thread-safe access."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # {node_id: {"id": str, "type": str, "attributes": dict}}
        self._nodes: Dict[str, Dict[str, Any]] = {}
        # List of (source_id, target_id, edge_type) tuples
        self._edges: List[Tuple[str, str, str]] = []
        # Ordered list of node ids for capped_append bookkeeping
        self._node_id_order: List[str] = []

    # ==================== CRUD — Nodes ====================

    def add_node(
        self,
        node_id: str,
        node_type: str,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Add a node to the graph.  Returns status dict."""
        if node_type not in VALID_NODE_TYPES:
            logger.warning("Rejected node '%s': invalid type '%s'", node_id, node_type)
            return {"status": "error", "message": f"Invalid node type '{node_type}'"}

        with self._lock:
            if node_id in self._nodes:
                logger.debug("Node '%s' already exists; updating attributes", node_id)
                self._nodes[node_id]["attributes"].update(attributes or {})
                return {"status": "ok", "node_id": node_id, "updated": True}

            node: Dict[str, Any] = {
                "id": node_id,
                "type": node_type,
                "attributes": dict(attributes) if attributes else {},
            }
            self._nodes[node_id] = node
            capped_append(self._node_id_order, node_id, max_size=MAX_NODES)
            # If capped_append trimmed old ids, remove them from _nodes too
            self._sync_nodes_after_cap()
            logger.info("Added node '%s' (type=%s)", node_id, node_type)
            return {"status": "ok", "node_id": node_id, "updated": False}

    def remove_node(self, node_id: str) -> Dict[str, Any]:
        """Remove a node and all its incident edges."""
        with self._lock:
            if node_id not in self._nodes:
                return {"status": "error", "message": f"Node '{node_id}' not found"}
            del self._nodes[node_id]
            if node_id in self._node_id_order:
                self._node_id_order.remove(node_id)
            before = len(self._edges)
            self._edges = [
                e for e in self._edges
                if e[0] != node_id and e[1] != node_id
            ]
            removed_edges = before - len(self._edges)
            logger.info(
                "Removed node '%s' and %d incident edge(s)",
                node_id, removed_edges,
            )
            return {"status": "ok", "node_id": node_id, "edges_removed": removed_edges}

    # ==================== CRUD — Edges ====================

    def add_edge(
        self, source_id: str, target_id: str, edge_type: str,
    ) -> Dict[str, Any]:
        """Add a directed edge.  Returns status dict."""
        if edge_type not in VALID_EDGE_TYPES:
            logger.warning(
                "Rejected edge %s->%s: invalid type '%s'",
                source_id, target_id, edge_type,
            )
            return {"status": "error", "message": f"Invalid edge type '{edge_type}'"}

        edge: Tuple[str, str, str] = (source_id, target_id, edge_type)
        with self._lock:
            if edge in self._edges:
                return {"status": "ok", "duplicate": True}
            capped_append(self._edges, edge, max_size=MAX_EDGES)
            logger.info("Added edge %s -[%s]-> %s", source_id, edge_type, target_id)
            return {"status": "ok", "duplicate": False}

    def remove_edge(
        self, source_id: str, target_id: str, edge_type: str,
    ) -> Dict[str, Any]:
        """Remove a specific directed edge."""
        edge: Tuple[str, str, str] = (source_id, target_id, edge_type)
        with self._lock:
            if edge not in self._edges:
                return {
                    "status": "error",
                    "message": f"Edge ({source_id}, {target_id}, {edge_type}) not found",
                }
            self._edges.remove(edge)
            logger.info("Removed edge %s -[%s]-> %s", source_id, edge_type, target_id)
            return {"status": "ok"}

    # ==================== Query — Structural Analysis ====================

    def find_missing_dependencies(self) -> List[str]:
        """Return node ids referenced as edge targets but not present as nodes."""
        with self._lock:
            referenced: Set[str] = set()
            for _, target_id, _ in self._edges:
                referenced.add(target_id)
            for source_id, _, _ in self._edges:
                referenced.add(source_id)
            existing = set(self._nodes.keys())
        return sorted(referenced - existing)

    def find_regulatory_gaps(self) -> List[str]:
        """Return Module-type node ids that have no 'regulated_by' edge."""
        with self._lock:
            regulated: Set[str] = {
                src for src, _, etype in self._edges
                if etype == EDGE_REGULATED_BY
            }
            modules = [
                nid for nid, node in self._nodes.items()
                if node["type"] == NODE_TYPE_MODULE
            ]
        return sorted(nid for nid in modules if nid not in regulated)

    def find_redundant_modules(self) -> List[Tuple[str, str]]:
        """Return pairs of Module-type nodes with identical depends_on target sets."""
        with self._lock:
            dep_map: Dict[str, Set[str]] = {}
            for nid, node in self._nodes.items():
                if node["type"] == NODE_TYPE_MODULE:
                    dep_map[nid] = set()

            for src, tgt, etype in self._edges:
                if etype == EDGE_DEPENDS_ON and src in dep_map:
                    dep_map[src].add(tgt)

        # Only modules with at least one dependency are considered
        ids = sorted(nid for nid, deps in dep_map.items() if deps)
        pairs: List[Tuple[str, str]] = []
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                if dep_map[ids[i]] == dep_map[ids[j]]:
                    pairs.append((ids[i], ids[j]))
        return pairs

    def detect_cross_domain_opportunities(self) -> List[CrossDomainOpportunity]:
        """Find Concept-type nodes sharing edges to the same downstream targets."""
        with self._lock:
            target_map: Dict[str, Set[str]] = {}
            concept_ids = {
                nid for nid, node in self._nodes.items()
                if node["type"] == NODE_TYPE_CONCEPT
            }
            for src, tgt, _ in self._edges:
                if src in concept_ids:
                    target_map.setdefault(src, set()).add(tgt)

        ids = sorted(target_map.keys())
        results: List[CrossDomainOpportunity] = []
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                shared = target_map[ids[i]] & target_map[ids[j]]
                if shared:
                    results.append(CrossDomainOpportunity(
                        concept_a=ids[i],
                        concept_b=ids[j],
                        shared_targets=tuple(sorted(shared)),
                    ))
        return results

    # ==================== Metrics ====================

    def compute_graph_health(self) -> GraphHealthResult:
        """Return a frozen snapshot of composite graph-health metrics."""
        with self._lock:
            nodes_snapshot = dict(self._nodes)
            edges_snapshot = list(self._edges)

        # --- node_coverage ---
        referenced: Set[str] = set()
        for src, tgt, _ in edges_snapshot:
            referenced.add(src)
            referenced.add(tgt)
        existing = set(nodes_snapshot.keys())
        all_referenced = referenced | existing
        node_coverage = (
            len(existing & all_referenced) / (len(all_referenced) or 1)
            if all_referenced else 1.0
        )

        # --- dependency_completeness ---
        modules = [
            nid for nid, n in nodes_snapshot.items()
            if n["type"] == NODE_TYPE_MODULE
        ]
        if modules:
            has_dep = {
                src for src, _, etype in edges_snapshot
                if etype == EDGE_DEPENDS_ON
            }
            dependency_completeness = (
                len([m for m in modules if m in has_dep]) / (len(modules) or 1)
            )
        else:
            dependency_completeness = 1.0

        # --- regulatory_coverage ---
        if modules:
            has_reg = {
                src for src, _, etype in edges_snapshot
                if etype == EDGE_REGULATED_BY
            }
            regulatory_coverage = (
                len([m for m in modules if m in has_reg]) / (len(modules) or 1)
            )
        else:
            regulatory_coverage = 1.0

        # --- redundancy_score ---
        if len(modules) >= 2:
            dep_map: Dict[str, Set[str]] = {m: set() for m in modules}
            for src, tgt, etype in edges_snapshot:
                if etype == EDGE_DEPENDS_ON and src in dep_map:
                    dep_map[src].add(tgt)
            total_pairs = len(modules) * (len(modules) - 1) // 2
            identical = 0
            mod_ids = sorted(modules)
            for i in range(len(mod_ids)):
                for j in range(i + 1, len(mod_ids)):
                    if dep_map[mod_ids[i]] == dep_map[mod_ids[j]]:
                        identical += 1
            redundancy_score = identical / total_pairs
        else:
            redundancy_score = 0.0

        cache_key = hashlib.sha256(
            json.dumps(
                {
                    "node_coverage": node_coverage,
                    "dependency_completeness": dependency_completeness,
                    "regulatory_coverage": regulatory_coverage,
                    "redundancy_score": redundancy_score,
                },
                sort_keys=True,
                default=str,
            ).encode("utf-8"),
        ).hexdigest()

        result = GraphHealthResult(
            node_coverage=round(node_coverage, 6),
            dependency_completeness=round(dependency_completeness, 6),
            regulatory_coverage=round(regulatory_coverage, 6),
            redundancy_score=round(redundancy_score, 6),
            cache_key=cache_key,
        )
        logger.debug("Graph health computed: %s", cache_key[:12])
        return result

    def compute_gcs(self) -> float:
        """Graph Connectivity Score: edge density normalised to 0-1.

        GCS = E / (N * (N - 1)) for a directed graph, where E is the
        number of edges and N the number of nodes.  Returns 0.0 for
        trivial graphs (N < 2).
        """
        with self._lock:
            n = len(self._nodes)
            e = len(self._edges)
        if n < 2:
            return 0.0
        max_edges = n * (n - 1)
        gcs = min(e / max_edges, 1.0)
        logger.debug("GCS computed: %.4f (nodes=%d, edges=%d)", gcs, n, exc)
        return round(gcs, 6)

    # ==================== Serialization ====================

    def to_json(self) -> Dict[str, Any]:
        """Serialize the entire graph to a JSON-compatible dict with a cache key."""
        with self._lock:
            nodes = [dict(n) for n in self._nodes.values()]
            edges = [
                {"source": s, "target": t, "type": et}
                for s, t, et in self._edges
            ]

        payload = {"nodes": nodes, "edges": edges}
        raw = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        cache_key = hashlib.sha256(raw).hexdigest()
        payload["cache_key"] = cache_key
        return payload

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> "ConceptGraphEngine":
        """Deserialize a graph from a dict produced by ``to_json``."""
        engine = cls()
        for node in data.get("nodes", []):
            engine.add_node(
                node_id=node["id"],
                node_type=node["type"],
                attributes=node.get("attributes", {}),
            )
        for edge in data.get("edges", []):
            engine.add_edge(
                source_id=edge["source"],
                target_id=edge["target"],
                edge_type=edge["type"],
            )
        logger.info(
            "Loaded graph from JSON (%d nodes, %d edges)",
            len(data.get("nodes", [])),
            len(data.get("edges", [])),
        )
        return engine

    # ==================== Internal Helpers ====================

    def _sync_nodes_after_cap(self) -> None:
        """Remove node entries whose ids were evicted by capped_append."""
        valid_ids = set(self._node_id_order)
        evicted = [nid for nid in self._nodes if nid not in valid_ids]
        for nid in evicted:
            del self._nodes[nid]
            logger.debug("Evicted capped node '%s'", nid)
