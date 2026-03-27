"""Unified Execution Bus for graph-driven task execution."""
from __future__ import annotations

from typing import Callable, Dict, List, Any, Coroutine, Optional
from dataclasses import dataclass, field
import asyncio
import uuid
import networkx as nx


@dataclass
class TaskNode:
    """Node representing an async task in the execution graph."""

    id: str
    label: str
    func: Callable[[], Coroutine[Any, Any, Any]]
    signature: Dict[str, float] = field(default_factory=dict)
    result: Any = None
    status: str = "pending"


class TaskGraphExecutor:
    """Execute a DAG of async tasks respecting dependencies."""

    def __init__(self) -> None:
        self.graph = nx.DiGraph()
        self.nodes: Dict[str, TaskNode] = {}

    def add_task(
        self,
        label: str,
        func: Callable[[], Coroutine[Any, Any, Any]],
        depends_on: Optional[List[str]] = None,
        signature: Optional[Dict[str, float]] = None,
    ) -> str:
        task_id = uuid.uuid4().hex[:8]
        node = TaskNode(id=task_id, label=label, func=func, signature=signature or {})
        self.nodes[task_id] = node
        self.graph.add_node(task_id)
        if depends_on:
            for dep in depends_on:
                if dep not in self.graph:
                    raise ValueError(f"Unknown dependency: {dep}")
                self.graph.add_edge(dep, task_id)
        return task_id

    async def execute(self) -> None:
        ordered = list(nx.topological_sort(self.graph))
        for node_id in ordered:
            node = self.nodes[node_id]
            node.status = "running"
            try:
                node.result = await node.func()
                node.status = "completed"
            except Exception as exc:  # pragma: no cover - minimal error handling
                node.status = f"error: {exc}"  # keep error message
                raise

    def get_results(self) -> Dict[str, Any]:
        return {nid: node.result for nid, node in self.nodes.items()}

    def describe_graph(self) -> List[Dict[str, Any]]:
        return [
            {"id": nid, "label": node.label, "status": node.status}
            for nid, node in self.nodes.items()
        ]


if __name__ == "__main__":  # pragma: no cover - manual demo
    async def demo() -> None:
        bus = TaskGraphExecutor()

        async def task_a():
            await asyncio.sleep(0.2)
            return "step1"

        async def task_b():
            await asyncio.sleep(0.1)
            return "step2"

        async def task_c():
            return "done"

        a = bus.add_task("load", task_a)
        b = bus.add_task("process", task_b, depends_on=[a])
        bus.add_task("output", task_c, depends_on=[b])

        await bus.execute()
        print(bus.get_results())

    asyncio.run(demo())
