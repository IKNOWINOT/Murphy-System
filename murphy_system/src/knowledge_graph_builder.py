# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Knowledge Graph Builder — KGB-001

Owner: Intelligence · Dep: threading, uuid, dataclasses, collections

Extract entities and relationships from system data to build a queryable
in-memory knowledge graph.  Supports typed nodes, weighted directed edges,
sub-graph extraction, BFS/DFS traversal, shortest-path, and live analytics.

Classes: NodeKind, EdgeKind, GraphStatus, TraversalMode, NodeProperties,
         EdgeProperties, GraphNode, GraphEdge, TraversalResult, GraphStats,
         SubgraphResult, QueryResult, KnowledgeGraphEngine
``create_knowledge_graph_api(engine)`` returns a Flask Blueprint (JSON
error envelope).

Safety: every mutation runs under ``threading.Lock``; bounded lists via
capped_append; no external graph libs — engine ships with stubs so all
logic is testable without third-party dependencies.
"""
from __future__ import annotations

import logging
import threading
import uuid
from collections import defaultdict, deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

try:
    from flask import Blueprint, jsonify, request
    _HAS_FLASK = True
except ImportError:
    _HAS_FLASK = False
    Blueprint = type("Blueprint", (), {"route": lambda *a, **k: lambda f: f})  # type: ignore[assignment,misc]

    def jsonify(*_a: Any, **_k: Any) -> dict:  # type: ignore[misc]
        return {}

    class _FakeReq:  # type: ignore[no-redef]
        args: dict = {}
        @staticmethod
        def get_json(silent: bool = True) -> dict:
            return {}

    request = _FakeReq()  # type: ignore[assignment]

try:
    from .blueprint_auth import require_blueprint_auth
except ImportError:
    from blueprint_auth import require_blueprint_auth
try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max(1, max_size // 10)]
        target_list.append(item)

logger = logging.getLogger(__name__)

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _enum_val(v: Any) -> str:
    """Return the string value whether *v* is an Enum or already a str."""
    return v.value if hasattr(v, "value") else str(v)

class NodeKind(str, Enum):
    """Kind of graph node."""
    entity = "entity"; concept = "concept"; event = "event"
    metric = "metric"; resource = "resource"; action = "action"
    system = "system"; user = "user"; document = "document"; tag = "tag"

class EdgeKind(str, Enum):
    """Kind of graph edge."""
    relates_to = "relates_to"; depends_on = "depends_on"; causes = "causes"
    contains = "contains"; inherits = "inherits"; produces = "produces"
    consumes = "consumes"; triggers = "triggers"; monitors = "monitors"
    describes = "describes"

class GraphStatus(str, Enum):
    """Lifecycle status of the knowledge graph."""
    active = "active"; archived = "archived"
    snapshot = "snapshot"; merging = "merging"

class TraversalMode(str, Enum):
    """Graph traversal strategy."""
    bfs = "bfs"; dfs = "dfs"; shortest_path = "shortest_path"

@dataclass
class NodeProperties:
    """Key-value typed metadata store for a node."""
    label: str = ""
    kind: str = "entity"
    properties: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    def to_dict(self) -> Dict[str, Any]:
        """Serialise to JSON-safe dictionary."""
        return asdict(self)

@dataclass
class EdgeProperties:
    """Metadata descriptor for an edge."""
    source_id: str = ""
    target_id: str = ""
    label: str = ""
    kind: str = "relates_to"
    weight: float = 1.0
    properties: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_now)
    def to_dict(self) -> Dict[str, Any]:
        """Serialise to JSON-safe dictionary."""
        return asdict(self)

@dataclass
class GraphNode:
    """A single node in the knowledge graph."""
    node_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    label: str = ""
    kind: str = "entity"
    properties: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    def to_dict(self) -> Dict[str, Any]:
        """Serialise to JSON-safe dictionary."""
        return asdict(self)

@dataclass
class GraphEdge:
    """A directed edge between two nodes."""
    edge_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    source_id: str = ""
    target_id: str = ""
    label: str = ""
    kind: str = "relates_to"
    weight: float = 1.0
    properties: Dict[str, Any] = field(default_factory=dict)
    bidirectional: bool = False
    created_at: str = field(default_factory=_now)
    def to_dict(self) -> Dict[str, Any]:
        """Serialise to JSON-safe dictionary."""
        return asdict(self)

@dataclass
class TraversalResult:
    """Result of a graph traversal operation."""
    start_node_id: str = ""
    mode: str = ""
    visited_ids: List[str] = field(default_factory=list)
    paths: List[List[str]] = field(default_factory=list)
    depth: int = 0
    duration_ms: float = 0.0
    def to_dict(self) -> Dict[str, Any]:
        """Serialise to JSON-safe dictionary."""
        return asdict(self)

@dataclass
class GraphStats:
    """Aggregate statistics for the knowledge graph."""
    total_nodes: int = 0
    total_edges: int = 0
    node_kinds: Dict[str, int] = field(default_factory=dict)
    edge_kinds: Dict[str, int] = field(default_factory=dict)
    avg_degree: float = 0.0
    connected_components: int = 0
    density: float = 0.0
    def to_dict(self) -> Dict[str, Any]:
        """Serialise to JSON-safe dictionary."""
        return asdict(self)

@dataclass
class SubgraphResult:
    """A named subgraph extracted from the main graph."""
    name: str = ""
    node_ids: List[str] = field(default_factory=list)
    edge_ids: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=_now)
    def to_dict(self) -> Dict[str, Any]:
        """Serialise to JSON-safe dictionary."""
        return asdict(self)

@dataclass
class QueryResult:
    """Result of a text search across the graph."""
    query: str = ""
    matched_nodes: List[str] = field(default_factory=list)
    matched_edges: List[str] = field(default_factory=list)
    count: int = 0
    duration_ms: float = 0.0
    def to_dict(self) -> Dict[str, Any]:
        """Serialise to JSON-safe dictionary."""
        return asdict(self)

def _compute_connected_components(
    nodes: Dict[str, GraphNode], edges: Dict[str, GraphEdge],
) -> int:
    """Return the number of connected components via union-find."""
    parent: Dict[str, str] = {nid: nid for nid in nodes}

    def _find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def _union(a: str, b: str) -> None:
        ra, rb = _find(a), _find(b)
        if ra != rb:
            parent[ra] = rb

    for e in edges.values():
        if e.source_id in parent and e.target_id in parent:
            _union(e.source_id, e.target_id)
    return len({_find(n) for n in parent})

class KnowledgeGraphEngine:
    """Thread-safe in-memory knowledge graph engine."""

    def __init__(self, max_history: int = 10_000) -> None:
        self._lock = threading.Lock()
        self._nodes: Dict[str, GraphNode] = {}
        self._edges: Dict[str, GraphEdge] = {}
        self._adjacency: Dict[str, List[str]] = defaultdict(list)
        self._reverse_adjacency: Dict[str, List[str]] = defaultdict(list)
        self._history: List[dict] = []
        self._max_history = max_history
        self._status: str = "active"

    def add_node(self, label: str, kind: str = "entity",
                 properties: Optional[Dict[str, Any]] = None,
                 tags: Optional[List[str]] = None) -> GraphNode:
        """Create and index a new graph node."""
        node = GraphNode(label=label, kind=_enum_val(kind),
                         properties=properties or {}, tags=tags or [])
        with self._lock:
            self._nodes[node.node_id] = node
            capped_append(self._history, {"action": "add_node",
                          "id": node.node_id, "ts": _now()}, self._max_history)
        logger.debug("Node added: %s", node.node_id)
        return node

    def get_node(self, node_id: str) -> Optional[GraphNode]:
        """Look up a node by its ID."""
        with self._lock:
            return self._nodes.get(node_id)

    def update_node(self, node_id: str, label: Optional[str] = None,
                    kind: Optional[str] = None,
                    properties: Optional[Dict[str, Any]] = None,
                    tags: Optional[List[str]] = None) -> Optional[GraphNode]:
        """Update mutable fields on an existing node."""
        with self._lock:
            node = self._nodes.get(node_id)
            if node is None:
                return None
            if label is not None:
                node.label = label
            if kind is not None:
                node.kind = _enum_val(kind)
            if properties is not None:
                node.properties = properties
            if tags is not None:
                node.tags = tags
            node.updated_at = _now()
            capped_append(self._history, {"action": "update_node",
                          "id": node_id, "ts": _now()}, self._max_history)
        return node

    def delete_node(self, node_id: str) -> bool:
        """Remove a node and all connected edges."""
        with self._lock:
            if node_id not in self._nodes:
                return False
            edge_ids = list(self._adjacency.get(node_id, []))
            edge_ids += [eid for eid in self._reverse_adjacency.get(node_id, [])
                         if eid not in edge_ids]
            for eid in edge_ids:
                self._remove_edge_unlocked(eid)
            del self._nodes[node_id]
            self._adjacency.pop(node_id, None)
            self._reverse_adjacency.pop(node_id, None)
            capped_append(self._history, {"action": "delete_node",
                          "id": node_id, "ts": _now()}, self._max_history)
        return True

    def add_edge(self, source_id: str, target_id: str, label: str = "",
                 kind: str = "relates_to", weight: float = 1.0,
                 properties: Optional[Dict[str, Any]] = None,
                 bidirectional: bool = False) -> Optional[GraphEdge]:
        """Create a directed edge between two existing nodes."""
        with self._lock:
            if source_id not in self._nodes or target_id not in self._nodes:
                return None
            edge = GraphEdge(source_id=source_id, target_id=target_id,
                             label=label, kind=_enum_val(kind), weight=weight,
                             properties=properties or {},
                             bidirectional=bidirectional)
            self._edges[edge.edge_id] = edge
            self._adjacency[source_id].append(edge.edge_id)
            self._reverse_adjacency[target_id].append(edge.edge_id)
            if bidirectional:
                self._adjacency[target_id].append(edge.edge_id)
                self._reverse_adjacency[source_id].append(edge.edge_id)
            capped_append(self._history, {"action": "add_edge",
                          "id": edge.edge_id, "ts": _now()}, self._max_history)
        return edge

    def get_edge(self, edge_id: str) -> Optional[GraphEdge]:
        """Look up an edge by its ID."""
        with self._lock:
            return self._edges.get(edge_id)

    def delete_edge(self, edge_id: str) -> bool:
        """Remove an edge and its adjacency entries."""
        with self._lock:
            return self._remove_edge_unlocked(edge_id)

    def _remove_edge_unlocked(self, edge_id: str) -> bool:
        """Remove an edge (caller must hold ``_lock``)."""
        edge = self._edges.pop(edge_id, None)
        if edge is None:
            return False
        adj = self._adjacency.get(edge.source_id, [])
        adj[:] = [e for e in adj if e != edge_id]
        rev = self._reverse_adjacency.get(edge.target_id, [])
        rev[:] = [e for e in rev if e != edge_id]
        if edge.bidirectional:
            adj2 = self._adjacency.get(edge.target_id, [])
            adj2[:] = [e for e in adj2 if e != edge_id]
            rev2 = self._reverse_adjacency.get(edge.source_id, [])
            rev2[:] = [e for e in rev2 if e != edge_id]
        return True

    def list_nodes(self, kind: Optional[str] = None, tag: Optional[str] = None,
                   label_contains: Optional[str] = None,
                   limit: int = 100) -> List[GraphNode]:
        """Return nodes matching optional filters."""
        with self._lock:
            nodes = list(self._nodes.values())
        if kind:
            kv = _enum_val(kind)
            nodes = [n for n in nodes if n.kind == kv]
        if tag:
            nodes = [n for n in nodes if tag in n.tags]
        if label_contains:
            lc = label_contains.lower()
            nodes = [n for n in nodes if lc in n.label.lower()]
        return nodes[:limit]

    def list_edges(self, kind: Optional[str] = None,
                   source_id: Optional[str] = None,
                   target_id: Optional[str] = None,
                   limit: int = 100) -> List[GraphEdge]:
        """Return edges matching optional filters."""
        with self._lock:
            edges = list(self._edges.values())
        if kind:
            kv = _enum_val(kind)
            edges = [e for e in edges if e.kind == kv]
        if source_id:
            edges = [e for e in edges if e.source_id == source_id]
        if target_id:
            edges = [e for e in edges if e.target_id == target_id]
        return edges[:limit]

    def get_neighbors(self, node_id: str, direction: str = "outgoing",
                      kind: Optional[str] = None) -> List[GraphNode]:
        """Return adjacent nodes in the given direction."""
        with self._lock:
            if node_id not in self._nodes:
                return []
            edge_ids: List[str] = []
            if direction in ("outgoing", "both"):
                edge_ids += self._adjacency.get(node_id, [])
            if direction in ("incoming", "both"):
                edge_ids += self._reverse_adjacency.get(node_id, [])
            neighbor_ids: List[str] = []
            for eid in edge_ids:
                edge = self._edges.get(eid)
                if edge is None:
                    continue
                nid = (edge.target_id if edge.source_id == node_id
                       else edge.source_id)
                if nid not in neighbor_ids:
                    neighbor_ids.append(nid)
            nodes = [self._nodes[n] for n in neighbor_ids if n in self._nodes]
        if kind:
            kv = _enum_val(kind)
            nodes = [n for n in nodes if n.kind == kv]
        return nodes

    def traverse(self, start_node_id: str, mode: str = "bfs",
                 max_depth: int = 10) -> TraversalResult:
        """BFS or DFS graph traversal from *start_node_id*."""
        t0 = datetime.now(timezone.utc)
        with self._lock:
            if start_node_id not in self._nodes:
                return TraversalResult(start_node_id=start_node_id, mode=mode)
            visited, paths, depth = self._traverse_unlocked(
                start_node_id, mode, max_depth)
        dur = (datetime.now(timezone.utc) - t0).total_seconds() * 1000
        return TraversalResult(start_node_id=start_node_id, mode=mode,
                               visited_ids=visited, paths=paths,
                               depth=depth, duration_ms=round(dur, 3))

    def _traverse_unlocked(self, start: str, mode: str,
                           max_depth: int) -> tuple:
        """Core traversal logic (caller must hold ``_lock``)."""
        visited: List[str] = []
        paths: List[List[str]] = []
        if mode == "dfs":
            stack: List[tuple] = [(start, [start], 0)]
            seen: set = set()
            max_d = 0
            while stack:
                nid, path, d = stack.pop()
                if nid in seen:
                    continue
                seen.add(nid)
                visited.append(nid)
                paths.append(list(path))
                max_d = max(max_d, d)
                if d < max_depth:
                    for eid in self._adjacency.get(nid, []):
                        edge = self._edges.get(eid)
                        if edge and edge.target_id not in seen:
                            stack.append((edge.target_id,
                                          path + [edge.target_id], d + 1))
            return visited, paths, max_d
        queue: deque = deque([(start, [start], 0)])
        seen_b: set = set()
        max_d_b = 0
        while queue:
            nid, path, d = queue.popleft()
            if nid in seen_b:
                continue
            seen_b.add(nid)
            visited.append(nid)
            paths.append(list(path))
            max_d_b = max(max_d_b, d)
            if d < max_depth:
                for eid in self._adjacency.get(nid, []):
                    edge = self._edges.get(eid)
                    if edge and edge.target_id not in seen_b:
                        queue.append((edge.target_id,
                                      path + [edge.target_id], d + 1))
        return visited, paths, max_d_b

    def find_shortest_path(self, source_id: str,
                           target_id: str) -> Optional[List[str]]:
        """BFS shortest path returning a list of node IDs."""
        with self._lock:
            if source_id not in self._nodes or target_id not in self._nodes:
                return None
            queue: deque = deque([(source_id, [source_id])])
            seen: set = set()
            while queue:
                nid, path = queue.popleft()
                if nid == target_id:
                    return path
                if nid in seen:
                    continue
                seen.add(nid)
                for eid in self._adjacency.get(nid, []):
                    edge = self._edges.get(eid)
                    if edge and edge.target_id not in seen:
                        queue.append((edge.target_id,
                                      path + [edge.target_id]))
        return None

    def extract_subgraph(self, node_ids: List[str],
                         include_internal_edges: bool = True) -> SubgraphResult:
        """Extract a subgraph from the given node IDs."""
        with self._lock:
            valid = [n for n in node_ids if n in self._nodes]
            edge_ids: List[str] = []
            if include_internal_edges:
                nset = set(valid)
                for e in self._edges.values():
                    if e.source_id in nset and e.target_id in nset:
                        edge_ids.append(e.edge_id)
        return SubgraphResult(name=f"subgraph-{uuid.uuid4().hex[:8]}",
                              node_ids=valid, edge_ids=edge_ids)

    def search_nodes(self, query: str, limit: int = 50) -> QueryResult:
        """Text search across labels, tags, and property values."""
        t0 = datetime.now(timezone.utc)
        q = query.lower()
        matched_n: List[str] = []
        matched_e: List[str] = []
        with self._lock:
            for n in self._nodes.values():
                if self._node_matches(n, q):
                    matched_n.append(n.node_id)
            for e in self._edges.values():
                if q in e.label.lower():
                    matched_e.append(e.edge_id)
        dur = (datetime.now(timezone.utc) - t0).total_seconds() * 1000
        return QueryResult(query=query, matched_nodes=matched_n[:limit],
                           matched_edges=matched_e[:limit],
                           count=len(matched_n) + len(matched_e),
                           duration_ms=round(dur, 3))

    @staticmethod
    def _node_matches(node: GraphNode, q: str) -> bool:
        """Return True if *q* appears in the node's searchable fields."""
        if q in node.label.lower():
            return True
        if any(q in t.lower() for t in node.tags):
            return True
        return any(q in str(v).lower() for v in node.properties.values())

    def get_stats(self) -> GraphStats:
        """Compute aggregate graph statistics."""
        with self._lock:
            n_count = len(self._nodes)
            e_count = len(self._edges)
            nk: Dict[str, int] = defaultdict(int)
            for n in self._nodes.values():
                nk[n.kind] += 1
            ek: Dict[str, int] = defaultdict(int)
            for e in self._edges.values():
                ek[e.kind] += 1
            avg_deg = (2 * e_count / n_count) if n_count else 0.0
            density = (2 * e_count / (n_count * (n_count - 1))
                       ) if n_count > 1 else 0.0
            cc = _compute_connected_components(self._nodes, self._edges)
        return GraphStats(total_nodes=n_count, total_edges=e_count,
                          node_kinds=dict(nk), edge_kinds=dict(ek),
                          avg_degree=round(avg_deg, 4),
                          connected_components=cc, density=round(density, 6))

    def merge_graph(self, other_engine: "KnowledgeGraphEngine") -> int:
        """Merge another graph's nodes and edges, return count added."""
        added = 0
        with other_engine._lock:
            o_nodes = list(other_engine._nodes.values())
            o_edges = list(other_engine._edges.values())
        with self._lock:
            for n in o_nodes:
                if n.node_id not in self._nodes:
                    self._nodes[n.node_id] = n
                    added += 1
            for e in o_edges:
                if e.edge_id not in self._edges:
                    self._edges[e.edge_id] = e
                    self._adjacency[e.source_id].append(e.edge_id)
                    self._reverse_adjacency[e.target_id].append(e.edge_id)
                    if e.bidirectional:
                        self._adjacency[e.target_id].append(e.edge_id)
                        self._reverse_adjacency[e.source_id].append(e.edge_id)
                    added += 1
        return added

    def export_graph(self) -> dict:
        """Serialise the entire graph to a plain dict."""
        with self._lock:
            return {"nodes": [n.to_dict() for n in self._nodes.values()],
                    "edges": [e.to_dict() for e in self._edges.values()],
                    "status": self._status, "exported_at": _now()}

    def import_graph(self, data: dict) -> int:
        """Deserialise from export format, return count of items imported."""
        count = 0
        fields_n = set(GraphNode.__dataclass_fields__)
        fields_e = set(GraphEdge.__dataclass_fields__)
        with self._lock:
            for nd in data.get("nodes", []):
                node = GraphNode(**{k: nd[k] for k in fields_n if k in nd})
                self._nodes[node.node_id] = node
                count += 1
            for ed in data.get("edges", []):
                edge = GraphEdge(**{k: ed[k] for k in fields_e if k in ed})
                self._edges[edge.edge_id] = edge
                self._adjacency[edge.source_id].append(edge.edge_id)
                self._reverse_adjacency[edge.target_id].append(edge.edge_id)
                count += 1
        return count

    def clear(self) -> None:
        """Remove all nodes and edges."""
        with self._lock:
            self._nodes.clear()
            self._edges.clear()
            self._adjacency.clear()
            self._reverse_adjacency.clear()
            capped_append(self._history, {"action": "clear", "ts": _now()},
                          self._max_history)

def validate_wingman_pair(storyline: List[str], actuals: List[str]) -> dict:
    """KGB-001 Wingman gate."""
    if not storyline:
        return {"passed": False, "message": "Storyline list is empty"}
    if not actuals:
        return {"passed": False, "message": "Actuals list is empty"}
    if len(storyline) != len(actuals):
        return {"passed": False,
                "message": f"Length mismatch: storyline={len(storyline)} "
                           f"actuals={len(actuals)}"}
    mismatches: List[int] = [i for i, (s, a) in enumerate(zip(storyline, actuals)) if s != a]
    if mismatches:
        return {"passed": False, "message": f"Pair mismatches at indices {mismatches}"}
    return {"passed": True, "message": "Wingman pair validated",
            "pair_count": len(storyline)}

def gate_kgb_in_sandbox(context: dict) -> dict:
    """KGB-001 Causality Sandbox gate."""
    required_keys = {"graph_id"}
    missing = required_keys - set(context.keys())
    if missing:
        return {"passed": False,
                "message": f"Missing context keys: {sorted(missing)}"}
    if not context.get("graph_id"):
        return {"passed": False, "message": "graph_id must be non-empty"}
    return {"passed": True, "message": "Sandbox gate passed",
            "graph_id": context["graph_id"]}

def _api_body() -> Dict[str, Any]:
    """Extract JSON body from the current request."""
    return request.get_json(silent=True) or {}

def _api_need(body: Dict[str, Any], *keys: str) -> Optional[Any]:
    """Return an error tuple if any *keys* are missing from *body*."""
    for k in keys:
        if not body.get(k):
            return jsonify({"error": f"Missing required field: {k}",
                            "code": "MISSING_FIELD"}), 400
    return None

def _not_found(msg: str) -> Any:
    return jsonify({"error": msg, "code": "NOT_FOUND"}), 404

def create_knowledge_graph_api(engine: KnowledgeGraphEngine) -> Any:
    """Create a Flask Blueprint with knowledge-graph REST endpoints."""
    bp = Blueprint("kg", __name__, url_prefix="/api")
    eng = engine

    @bp.route("/kg/nodes", methods=["POST"])
    def create_node() -> Any:
        body = _api_body()
        err = _api_need(body, "label")
        if err:
            return err
        node = eng.add_node(label=body["label"], kind=body.get("kind", "entity"),
                            properties=body.get("properties", {}),
                            tags=body.get("tags", []))
        return jsonify(node.to_dict()), 201

    @bp.route("/kg/nodes", methods=["GET"])
    def list_nodes() -> Any:
        a = request.args
        nodes = eng.list_nodes(kind=a.get("kind"), tag=a.get("tag"),
                               label_contains=a.get("q"),
                               limit=int(a.get("limit", 100)))
        return jsonify([n.to_dict() for n in nodes]), 200

    @bp.route("/kg/nodes/<node_id>", methods=["GET"])
    def get_node(node_id: str) -> Any:
        node = eng.get_node(node_id)
        if node is None:
            return _not_found("Node not found")
        return jsonify(node.to_dict()), 200

    @bp.route("/kg/nodes/<node_id>", methods=["PUT"])
    def update_node(node_id: str) -> Any:
        body = _api_body()
        node = eng.update_node(node_id, label=body.get("label"),
                               kind=body.get("kind"),
                               properties=body.get("properties"),
                               tags=body.get("tags"))
        if node is None:
            return _not_found("Node not found")
        return jsonify(node.to_dict()), 200

    @bp.route("/kg/nodes/<node_id>", methods=["DELETE"])
    def delete_node(node_id: str) -> Any:
        if not eng.delete_node(node_id):
            return _not_found("Node not found")
        return jsonify({"deleted": True}), 200

    @bp.route("/kg/edges", methods=["POST"])
    def create_edge() -> Any:
        body = _api_body()
        err = _api_need(body, "source_id", "target_id")
        if err:
            return err
        edge = eng.add_edge(source_id=body["source_id"],
                            target_id=body["target_id"],
                            label=body.get("label", ""),
                            kind=body.get("kind", "relates_to"),
                            weight=float(body.get("weight", 1.0)),
                            properties=body.get("properties", {}),
                            bidirectional=bool(body.get("bidirectional", False)))
        if edge is None:
            return _not_found("Source or target node not found")
        return jsonify(edge.to_dict()), 201

    @bp.route("/kg/edges", methods=["GET"])
    def list_edges() -> Any:
        a = request.args
        edges = eng.list_edges(kind=a.get("kind"), source_id=a.get("source_id"),
                               target_id=a.get("target_id"),
                               limit=int(a.get("limit", 100)))
        return jsonify([e.to_dict() for e in edges]), 200

    @bp.route("/kg/edges/<edge_id>", methods=["GET"])
    def get_edge(edge_id: str) -> Any:
        edge = eng.get_edge(edge_id)
        if edge is None:
            return _not_found("Edge not found")
        return jsonify(edge.to_dict()), 200

    @bp.route("/kg/edges/<edge_id>", methods=["DELETE"])
    def delete_edge(edge_id: str) -> Any:
        if not eng.delete_edge(edge_id):
            return _not_found("Edge not found")
        return jsonify({"deleted": True}), 200

    @bp.route("/kg/nodes/<node_id>/neighbors", methods=["GET"])
    def get_neighbors(node_id: str) -> Any:
        a = request.args
        nodes = eng.get_neighbors(node_id, direction=a.get("direction", "outgoing"),
                                  kind=a.get("kind"))
        return jsonify([n.to_dict() for n in nodes]), 200

    @bp.route("/kg/traverse", methods=["POST"])
    def traverse() -> Any:
        body = _api_body()
        err = _api_need(body, "start_node_id")
        if err:
            return err
        result = eng.traverse(start_node_id=body["start_node_id"],
                              mode=body.get("mode", "bfs"),
                              max_depth=int(body.get("max_depth", 10)))
        return jsonify(result.to_dict()), 200

    @bp.route("/kg/shortest-path", methods=["POST"])
    def shortest_path() -> Any:
        body = _api_body()
        err = _api_need(body, "source_id", "target_id")
        if err:
            return err
        path = eng.find_shortest_path(body["source_id"], body["target_id"])
        if path is None:
            return _not_found("No path found")
        return jsonify({"path": path, "length": len(path)}), 200

    @bp.route("/kg/subgraph", methods=["POST"])
    def subgraph() -> Any:
        body = _api_body()
        err = _api_need(body, "node_ids")
        if err:
            return err
        result = eng.extract_subgraph(
            node_ids=body["node_ids"],
            include_internal_edges=body.get("include_internal_edges", True))
        return jsonify(result.to_dict()), 200

    @bp.route("/kg/search", methods=["GET"])
    def search() -> Any:
        a = request.args
        result = eng.search_nodes(query=a.get("q", ""),
                                  limit=int(a.get("limit", 50)))
        return jsonify(result.to_dict()), 200

    @bp.route("/kg/stats", methods=["GET"])
    def stats() -> Any:
        return jsonify(eng.get_stats().to_dict()), 200

    @bp.route("/kg/export", methods=["POST"])
    def export_graph() -> Any:
        return jsonify(eng.export_graph()), 200

    @bp.route("/kg/import", methods=["POST"])
    def import_graph() -> Any:
        return jsonify({"imported": eng.import_graph(_api_body())}), 200

    @bp.route("/kg/health", methods=["GET"])
    def health() -> Any:
        st = eng.get_stats()
        return jsonify({"status": "healthy", "module": "KGB-001",
                        "nodes": st.total_nodes, "edges": st.total_edges}), 200

    require_blueprint_auth(bp)
    return bp
