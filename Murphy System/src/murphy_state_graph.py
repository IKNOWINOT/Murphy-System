"""
Murphy System - Murphy State Graph
Copyright 2024-2026 Corey Post, Inoni LLC
License: BSL 1.1

Persistent state-machine orchestration engine for Murphy's workflow execution.
Provides graph-based workflow execution with checkpointing and human-in-the-loop support.
Integrates with: persistence_manager.py, hitl_autonomy_controller.py, workflow_dag_engine.py
"""

import json
import logging
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

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
# GraphState
# ---------------------------------------------------------------------------

class GraphState:
    """
    Persistent graph state container backed by a plain dictionary.

    Wraps a ``data`` dict and exposes typed accessors so that node handlers
    can read and write state without mutating the raw dict directly.
    """

    def __init__(self, data: Optional[Dict[str, Any]] = None) -> None:
        self.data: Dict[str, Any] = dict(data) if data else {}

    def get(self, key: str, default: Any = None) -> Any:
        """Return the value for *key*, or *default* if absent."""
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set *key* to *value* in the state."""
        self.data[key] = value

    def to_dict(self) -> Dict[str, Any]:
        """Return a shallow copy of the underlying data dict."""
        return dict(self.data)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "GraphState":
        """Construct a :class:`GraphState` from a plain dictionary."""
        return cls(data=d)


# ---------------------------------------------------------------------------
# NodeType
# ---------------------------------------------------------------------------

class NodeType(Enum):
    """Supported node types within a :class:`StateGraph`."""
    ACTION = "action"
    CONDITION = "condition"
    HUMAN_APPROVAL = "human_approval"
    PARALLEL_FORK = "parallel_fork"
    PARALLEL_JOIN = "parallel_join"
    START = "start"
    END = "end"


# ---------------------------------------------------------------------------
# GraphNode / GraphEdge
# ---------------------------------------------------------------------------

@dataclass
class GraphNode:
    """A single node in the state graph."""
    node_id: str
    name: str
    node_type: NodeType
    handler: Optional[Callable] = field(default=None)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphEdge:
    """A directed edge connecting two nodes with an optional guard condition."""
    edge_id: str
    from_node: str
    to_node: str
    condition: Optional[Callable[["GraphState"], bool]] = field(default=None)
    label: str = ""


# ---------------------------------------------------------------------------
# Checkpoint / CheckpointStore
# ---------------------------------------------------------------------------

@dataclass
class Checkpoint:
    """Snapshot of graph execution state at a particular node."""
    checkpoint_id: str
    graph_id: str
    current_node: str
    state: Dict[str, Any]
    timestamp: str
    status: str  # "running" | "paused" | "completed" | "failed"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "graph_id": self.graph_id,
            "current_node": self.current_node,
            "state": self.state,
            "timestamp": self.timestamp,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Checkpoint":
        return cls(
            checkpoint_id=d["checkpoint_id"],
            graph_id=d["graph_id"],
            current_node=d["current_node"],
            state=d.get("state", {}),
            timestamp=d.get("timestamp", ""),
            status=d.get("status", "running"),
        )


class CheckpointStore:
    """
    Persists :class:`Checkpoint` objects either to JSON files on disk (when
    *persistence_dir* is provided) or to an in-memory dictionary.

    Thread-safe via a single :class:`threading.Lock`.
    """

    def __init__(self, persistence_dir: Optional[str] = None) -> None:
        self._lock = threading.Lock()
        self._memory: Dict[str, Checkpoint] = {}
        self._dir: Optional[Path] = None
        if persistence_dir:
            self._dir = Path(persistence_dir)
            try:
                self._dir.mkdir(parents=True, exist_ok=True)
                logger.info("CheckpointStore using directory: %s", self._dir)
            except OSError as exc:
                logger.error("Failed to create checkpoint directory %s: %s", persistence_dir, exc)
                self._dir = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def save(self, cp: Checkpoint) -> None:
        """Persist *cp* (overwrites any existing checkpoint with the same ID)."""
        with self._lock:
            self._memory[cp.checkpoint_id] = cp
            if self._dir:
                path = self._dir / f"{cp.checkpoint_id}.json"
                try:
                    path.write_text(json.dumps(cp.to_dict(), indent=2), encoding="utf-8")
                    logger.debug("Checkpoint saved to disk: %s", path)
                except OSError as exc:
                    logger.error("Failed to write checkpoint %s: %s", cp.checkpoint_id, exc)

    def load(self, checkpoint_id: str) -> Optional[Checkpoint]:
        """Return the :class:`Checkpoint` for *checkpoint_id*, or ``None``."""
        with self._lock:
            if checkpoint_id in self._memory:
                return self._memory[checkpoint_id]
            if self._dir:
                path = self._dir / f"{checkpoint_id}.json"
                try:
                    raw = path.read_text(encoding="utf-8")
                    cp = Checkpoint.from_dict(json.loads(raw))
                    self._memory[checkpoint_id] = cp
                    return cp
                except (FileNotFoundError, json.JSONDecodeError, KeyError) as exc:
                    logger.debug("Could not load checkpoint %s: %s", checkpoint_id, exc)
            return None

    def list_checkpoints(self, graph_id: str) -> List[Checkpoint]:
        """Return all checkpoints belonging to *graph_id*."""
        with self._lock:
            self._reload_from_disk()
            return [cp for cp in self._memory.values() if cp.graph_id == graph_id]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _reload_from_disk(self) -> None:
        """Load any on-disk checkpoints not yet in memory (caller holds lock)."""
        if not self._dir:
            return
        try:
            for path in self._dir.glob("*.json"):
                cid = path.stem
                if cid in self._memory:
                    continue
                try:
                    raw = path.read_text(encoding="utf-8")
                    cp = Checkpoint.from_dict(json.loads(raw))
                    self._memory[cid] = cp
                except (json.JSONDecodeError, KeyError) as exc:
                    logger.warning("Skipping corrupt checkpoint file %s: %s", path, exc)
        except OSError as exc:
            logger.error("Failed to scan checkpoint directory: %s", exc)


# ---------------------------------------------------------------------------
# HumanInTheLoop
# ---------------------------------------------------------------------------

class HumanInTheLoop:
    """
    Manages human approval requests within graph execution.

    Approval IDs are UUIDs; callers can check, approve, or reject them
    concurrently from any thread.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # Stores Optional[bool]: None = pending, True = approved, False = rejected
        self._approvals: Dict[str, Optional[bool]] = {}

    def request_approval(self, node_id: str, state: GraphState, context: Dict[str, Any]) -> str:
        """
        Register a new pending approval for *node_id* and return its ID.

        The returned *approval_id* can be passed to :meth:`check_approval`,
        :meth:`approve`, or :meth:`reject`.
        """
        approval_id = str(uuid.uuid4())
        with self._lock:
            self._approvals[approval_id] = None
        logger.info(
            "HITL approval requested: approval_id=%s node_id=%s context_keys=%s",
            approval_id,
            node_id,
            list(context.keys()),
        )
        return approval_id

    def check_approval(self, approval_id: str) -> Optional[bool]:
        """Return ``True`` (approved), ``False`` (rejected), or ``None`` (pending)."""
        with self._lock:
            return self._approvals.get(approval_id)

    def approve(self, approval_id: str) -> None:
        """Mark *approval_id* as approved."""
        with self._lock:
            if approval_id in self._approvals:
                self._approvals[approval_id] = True
                logger.info("HITL approval granted: %s", approval_id)

    def reject(self, approval_id: str) -> None:
        """Mark *approval_id* as rejected."""
        with self._lock:
            if approval_id in self._approvals:
                self._approvals[approval_id] = False
                logger.info("HITL approval rejected: %s", approval_id)


# ---------------------------------------------------------------------------
# BranchRouter
# ---------------------------------------------------------------------------

class BranchRouter:
    """Evaluates edge conditions and returns the next node to visit."""

    def route(self, state: GraphState, edges: List[GraphEdge]) -> Optional[str]:
        """
        Iterate *edges* in order and return the ``to_node`` of the first edge
        whose condition evaluates to ``True`` (or whose condition is ``None``).

        Returns ``None`` when no edge matches.
        """
        for edge in edges:
            if edge.condition is None:
                logger.debug("BranchRouter: unconditional edge %s -> %s", edge.from_node, edge.to_node)
                return edge.to_node
            try:
                result = edge.condition(state)
            except Exception as exc:
                logger.error(
                    "BranchRouter: condition on edge %s raised %s; skipping",
                    edge.edge_id,
                    exc,
                )
                continue
            if result:
                logger.debug(
                    "BranchRouter: condition matched edge %s -> %s (label=%r)",
                    edge.from_node,
                    edge.to_node,
                    edge.label,
                )
                return edge.to_node
        logger.debug("BranchRouter: no matching edge found")
        return None


# ---------------------------------------------------------------------------
# ParallelFork / ParallelJoin
# ---------------------------------------------------------------------------

@dataclass
class ParallelFork:
    """Describes a set of branches to launch from a fork node."""
    fork_id: str
    branch_node_ids: List[str] = field(default_factory=list)


@dataclass
class ParallelJoin:
    """Describes how many branch results a join node must collect."""
    join_id: str
    expects: int


# ---------------------------------------------------------------------------
# StateGraph
# ---------------------------------------------------------------------------

class StateGraph:
    """
    Directed graph of :class:`GraphNode` objects connected by :class:`GraphEdge`
    objects.  Provides the structural description executed by :class:`GraphRunner`.
    """

    def __init__(self, graph_id: str) -> None:
        self.graph_id = graph_id
        self._nodes: Dict[str, GraphNode] = {}
        self._edges: Dict[str, GraphEdge] = {}
        self._edges_from: Dict[str, List[str]] = {}
        self._entry_point: Optional[str] = None

    # ------------------------------------------------------------------
    # Mutation API
    # ------------------------------------------------------------------

    def add_node(self, node: GraphNode) -> None:
        """Register *node* in the graph."""
        self._nodes[node.node_id] = node
        self._edges_from.setdefault(node.node_id, [])
        logger.debug("StateGraph %s: added node %s (%s)", self.graph_id, node.node_id, node.node_type)

    def add_edge(self, edge: GraphEdge) -> None:
        """Register *edge* in the graph."""
        self._edges[edge.edge_id] = edge
        self._edges_from.setdefault(edge.from_node, [])
        self._edges_from[edge.from_node].append(edge.edge_id)
        logger.debug(
            "StateGraph %s: added edge %s (%s -> %s)",
            self.graph_id,
            edge.edge_id,
            edge.from_node,
            edge.to_node,
        )

    def set_entry_point(self, node_id: str) -> None:
        """Designate *node_id* as the starting node for execution."""
        self._entry_point = node_id
        logger.debug("StateGraph %s: entry point set to %s", self.graph_id, node_id)

    # ------------------------------------------------------------------
    # Query API
    # ------------------------------------------------------------------

    def get_node(self, node_id: str) -> Optional[GraphNode]:
        """Return the :class:`GraphNode` for *node_id*, or ``None``."""
        return self._nodes.get(node_id)

    def get_edges_from(self, node_id: str) -> List[GraphEdge]:
        """Return all edges that originate from *node_id*."""
        edge_ids = self._edges_from.get(node_id, [])
        return [self._edges[eid] for eid in edge_ids if eid in self._edges]

    def validate(self) -> List[str]:
        """
        Check graph structural integrity and return a list of error strings.
        An empty list means the graph is valid.
        """
        errors: List[str] = []
        if not self._entry_point:
            errors.append("No entry point defined (call set_entry_point).")
        elif self._entry_point not in self._nodes:
            errors.append(f"Entry point '{self._entry_point}' not found in nodes.")

        for edge_id, edge in self._edges.items():
            if edge.from_node not in self._nodes:
                errors.append(f"Edge '{edge_id}': from_node '{edge.from_node}' not in nodes.")
            if edge.to_node not in self._nodes:
                errors.append(f"Edge '{edge_id}': to_node '{edge.to_node}' not in nodes.")

        end_nodes = [n for n in self._nodes.values() if n.node_type == NodeType.END]
        if not end_nodes:
            errors.append("Graph has no END node.")

        return errors

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @property
    def entry_point(self) -> Optional[str]:
        return self._entry_point


# ---------------------------------------------------------------------------
# GraphRunner
# ---------------------------------------------------------------------------

class GraphRunner:
    """
    Synchronous executor for a :class:`StateGraph`.

    Walks the graph node-by-node, invoking handlers, checkpointing after each
    step, and pausing for human-in-the-loop approvals when required.
    """

    def __init__(
        self,
        graph: StateGraph,
        checkpoint_store: Optional[CheckpointStore] = None,
        hitl: Optional[HumanInTheLoop] = None,
        max_steps: int = 100,
        timeout_s: float = 300.0,
    ) -> None:
        self._graph = graph
        self._checkpoint_store = checkpoint_store
        self._hitl = hitl
        self._max_steps = max_steps
        self._timeout_s = timeout_s
        self._router = BranchRouter()
        self._history: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, initial_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the graph from its entry point with *initial_state*.

        Returns the final state dict (or the current state if execution is
        paused waiting for a human approval).
        """
        errors = self._graph.validate()
        if errors:
            raise ValueError("Graph validation failed: " + "; ".join(errors))

        state = GraphState.from_dict(initial_state)
        current_node_id = self._graph.entry_point
        start_time = time.monotonic()
        steps = 0

        logger.info("GraphRunner: starting graph %s at node %s", self._graph.graph_id, current_node_id)

        while current_node_id is not None:
            if steps >= self._max_steps:
                logger.warning("GraphRunner: max_steps (%d) reached", self._max_steps)
                state.set("_status", "max_steps_exceeded")
                break

            elapsed = time.monotonic() - start_time
            if elapsed > self._timeout_s:
                logger.warning("GraphRunner: timeout after %.1f s", elapsed)
                state.set("_status", "timeout")
                break

            node = self._graph.get_node(current_node_id)
            if node is None:
                logger.error("GraphRunner: node '%s' not found; aborting", current_node_id)
                state.set("_status", "node_not_found")
                break

            logger.info(
                "GraphRunner: executing node %s (%s) step=%d",
                node.node_id,
                node.node_type.value,
                steps,
            )

            next_node_id = self._execute_node(node, state)

            self._record_history(node, state)
            self._save_checkpoint(node, state, next_node_id)

            if state.get("_status") == "waiting_approval":
                logger.info("GraphRunner: paused at node %s waiting for approval", node.node_id)
                break

            if node.node_type == NodeType.END:
                state.set("_status", "completed")
                logger.info("GraphRunner: reached END node %s", node.node_id)
                break

            if next_node_id is None:
                logger.info("GraphRunner: no outgoing edge from %s; stopping", node.node_id)
                state.set("_status", "completed")
                break

            current_node_id = next_node_id
            steps += 1

        return state.to_dict()

    def run_from_checkpoint(self, checkpoint_id: str) -> Dict[str, Any]:
        """Resume execution from the checkpoint identified by *checkpoint_id*."""
        if self._checkpoint_store is None:
            raise RuntimeError("No CheckpointStore configured; cannot resume from checkpoint.")

        cp = self._checkpoint_store.load(checkpoint_id)
        if cp is None:
            raise KeyError(f"Checkpoint '{checkpoint_id}' not found.")

        logger.info(
            "GraphRunner: resuming from checkpoint %s at node %s (status=%s)",
            checkpoint_id,
            cp.current_node,
            cp.status,
        )

        state = GraphState.from_dict(cp.state)
        state.set("_status", "running")

        current_node_id = cp.current_node
        start_time = time.monotonic()
        steps = 0

        while current_node_id is not None:
            if steps >= self._max_steps:
                logger.warning("GraphRunner: max_steps (%d) reached during resume", self._max_steps)
                state.set("_status", "max_steps_exceeded")
                break

            elapsed = time.monotonic() - start_time
            if elapsed > self._timeout_s:
                logger.warning("GraphRunner: timeout after %.1f s during resume", elapsed)
                state.set("_status", "timeout")
                break

            node = self._graph.get_node(current_node_id)
            if node is None:
                logger.error("GraphRunner: node '%s' not found during resume; aborting", current_node_id)
                state.set("_status", "node_not_found")
                break

            logger.info(
                "GraphRunner: (resume) executing node %s (%s) step=%d",
                node.node_id,
                node.node_type.value,
                steps,
            )

            next_node_id = self._execute_node(node, state)
            self._record_history(node, state)
            self._save_checkpoint(node, state, next_node_id)

            if state.get("_status") == "waiting_approval":
                logger.info("GraphRunner: paused at node %s waiting for approval", node.node_id)
                break

            if node.node_type == NodeType.END:
                state.set("_status", "completed")
                logger.info("GraphRunner: reached END node %s", node.node_id)
                break

            if next_node_id is None:
                state.set("_status", "completed")
                break

            current_node_id = next_node_id
            steps += 1

        return state.to_dict()

    def get_execution_history(self) -> List[Dict[str, Any]]:
        """Return a copy of the recorded node execution history."""
        with self._lock:
            return list(self._history)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _execute_node(self, node: GraphNode, state: GraphState) -> Optional[str]:
        """
        Dispatch execution for *node* and return the next node ID (or ``None``).

        Mutates *state* in place via the node handler or built-in logic.
        """
        if node.node_type == NodeType.HUMAN_APPROVAL:
            return self._handle_human_approval(node, state)

        if node.node_type == NodeType.PARALLEL_FORK:
            return self._handle_parallel_fork(node, state)

        if node.node_type == NodeType.PARALLEL_JOIN:
            return self._handle_parallel_join(node, state)

        # ACTION, CONDITION, START, END, or unknown — call handler if present
        if node.handler is not None:
            try:
                result = node.handler(state)
                if isinstance(result, str):
                    return result
            except Exception as exc:
                logger.error("GraphRunner: handler on node %s raised: %s", node.node_id, exc)
                state.set("_error", str(exc))
                state.set("_status", "failed")
                return None

        edges = self._graph.get_edges_from(node.node_id)
        return self._router.route(state, edges)

    def _handle_human_approval(self, node: GraphNode, state: GraphState) -> Optional[str]:
        """Pause execution and register an approval request."""
        if self._hitl is None:
            logger.warning(
                "GraphRunner: HUMAN_APPROVAL node %s reached but no HumanInTheLoop configured; skipping",
                node.node_id,
            )
            edges = self._graph.get_edges_from(node.node_id)
            return self._router.route(state, edges)

        context = dict(node.metadata)
        approval_id = self._hitl.request_approval(node.node_id, state, context)
        state.set("_approval_id", approval_id)
        state.set("_approval_node", node.node_id)
        state.set("_status", "waiting_approval")
        return None

    def _handle_parallel_fork(self, node: GraphNode, state: GraphState) -> Optional[str]:
        """Execute parallel branches sequentially and accumulate results."""
        edges = self._graph.get_edges_from(node.node_id)
        branch_results: List[Dict[str, Any]] = []

        for edge in edges:
            branch_start = self._graph.get_node(edge.to_node)
            if branch_start is None:
                logger.warning("GraphRunner: fork branch node '%s' not found; skipping", edge.to_node)
                continue

            branch_state = GraphState.from_dict(state.to_dict())
            branch_steps = 0
            current = branch_start.node_id

            while current is not None and branch_steps < self._max_steps:
                bnode = self._graph.get_node(current)
                if bnode is None or bnode.node_type in (NodeType.PARALLEL_JOIN, NodeType.END):
                    break
                next_id = self._execute_node(bnode, branch_state)
                self._record_history(bnode, branch_state)
                if branch_state.get("_status") in ("failed", "waiting_approval"):
                    break
                current = next_id
                branch_steps += 1

            branch_results.append(branch_state.to_dict())

        state.set("_fork_results", branch_results)
        logger.info(
            "GraphRunner: fork %s completed %d branches", node.node_id, len(branch_results)
        )

        join_edges = self._graph.get_edges_from(node.node_id)
        return self._router.route(state, join_edges)

    def _handle_parallel_join(self, node: GraphNode, state: GraphState) -> Optional[str]:
        """Merge fork results stored in state and route to the next node."""
        fork_results: List[Dict[str, Any]] = state.get("_fork_results", [])
        merged: Dict[str, Any] = {}
        for result in fork_results:
            merged.update(result)
        state.set("_joined_state", merged)
        logger.info(
            "GraphRunner: join %s merged %d branch result(s)",
            node.node_id,
            len(fork_results),
        )

        if node.handler is not None:
            try:
                node.handler(state)
            except Exception as exc:
                logger.error("GraphRunner: join handler on node %s raised: %s", node.node_id, exc)
                state.set("_error", str(exc))
                state.set("_status", "failed")
                return None

        edges = self._graph.get_edges_from(node.node_id)
        return self._router.route(state, edges)

    def _record_history(self, node: GraphNode, state: GraphState) -> None:
        """Append a history entry for the completed node step."""
        entry = {
            "node_id": node.node_id,
            "node_type": node.node_type.value,
            "timestamp": time.time(),
            "status": state.get("_status", "running"),
        }
        with self._lock:
            capped_append(self._history, entry)

    def _save_checkpoint(
        self,
        node: GraphNode,
        state: GraphState,
        next_node_id: Optional[str],
    ) -> None:
        """Persist a checkpoint if a store is available."""
        if self._checkpoint_store is None:
            return

        raw_status = state.get("_status", "running")
        cp_status = raw_status if raw_status in ("running", "paused", "completed", "failed") else "running"

        cp = Checkpoint(
            checkpoint_id=str(uuid.uuid4()),
            graph_id=self._graph.graph_id,
            current_node=next_node_id or node.node_id,
            state=state.to_dict(),
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            status=cp_status,
        )
        self._checkpoint_store.save(cp)
        logger.debug("GraphRunner: checkpoint saved %s", cp.checkpoint_id)
