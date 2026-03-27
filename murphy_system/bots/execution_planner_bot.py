"""Plan execution order from a dependency graph."""
from __future__ import annotations

from typing import List
import networkx as nx

class ExecutionPlannerBot:
    """Walk dependency graphs and produce execution schedules."""

    def plan_execution(self, graph: nx.DiGraph) -> List[str]:
        return list(nx.topological_sort(graph))
