"""Build dependency graphs between bot tasks."""
from __future__ import annotations

from typing import List, Dict
import networkx as nx

class GraphArchitectBot:
    """Construct a DAG based on declared dependencies."""

    def build_graph(self, tasks: List[Dict]) -> nx.DiGraph:
        graph = nx.DiGraph()
        for task in tasks:
            tid = task["id"]
            graph.add_node(tid)
            for dep in task.get("depends_on", []):
                graph.add_edge(dep, tid)
        if not nx.is_directed_acyclic_graph(graph):
            raise ValueError("Circular dependency detected")
        return graph
