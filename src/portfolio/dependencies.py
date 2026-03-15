"""
Portfolio – Dependency Manager
================================

Manages item-to-item dependencies with cycle detection.

Copyright 2024 Inoni LLC – BSL-1.1
"""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Dict, List, Optional, Set

from .models import Dependency, DependencyType


class DependencyManager:
    """Stores and validates dependencies between items."""

    def __init__(self) -> None:
        self._deps: Dict[str, Dependency] = {}
        # Adjacency list: predecessor → [successors]
        self._successors: Dict[str, List[str]] = defaultdict(list)
        self._predecessors: Dict[str, List[str]] = defaultdict(list)

    def add_dependency(
        self,
        predecessor_id: str,
        successor_id: str,
        dependency_type: DependencyType = DependencyType.FINISH_TO_START,
        lag_days: int = 0,
    ) -> Dependency:
        """Add a dependency. Raises ``ValueError`` if it would create a cycle."""
        if predecessor_id == successor_id:
            raise ValueError("An item cannot depend on itself")

        # Check for duplicate
        for dep in self._deps.values():
            if dep.predecessor_id == predecessor_id and dep.successor_id == successor_id:
                raise ValueError("Dependency already exists")

        # Cycle detection: would adding successor → predecessor create a path?
        if self._would_create_cycle(predecessor_id, successor_id):
            raise ValueError(
                f"Adding dependency {predecessor_id} → {successor_id} would create a cycle"
            )

        dep = Dependency(
            predecessor_id=predecessor_id,
            successor_id=successor_id,
            dependency_type=dependency_type,
            lag_days=lag_days,
        )
        self._deps[dep.id] = dep
        self._successors[predecessor_id].append(successor_id)
        self._predecessors[successor_id].append(predecessor_id)
        return dep

    def remove_dependency(self, dependency_id: str) -> bool:
        dep = self._deps.get(dependency_id)
        if dep is None:
            return False
        del self._deps[dependency_id]
        if dep.successor_id in self._successors.get(dep.predecessor_id, []):
            self._successors[dep.predecessor_id].remove(dep.successor_id)
        if dep.predecessor_id in self._predecessors.get(dep.successor_id, []):
            self._predecessors[dep.successor_id].remove(dep.predecessor_id)
        return True

    def get_dependencies(self, item_id: str) -> List[Dependency]:
        """Return all dependencies where *item_id* is predecessor or successor."""
        return [
            d for d in self._deps.values()
            if d.predecessor_id == item_id or d.successor_id == item_id
        ]

    def get_predecessors(self, item_id: str) -> List[str]:
        return list(self._predecessors.get(item_id, []))

    def get_successors(self, item_id: str) -> List[str]:
        return list(self._successors.get(item_id, []))

    def _would_create_cycle(self, predecessor_id: str, successor_id: str) -> bool:
        """BFS from successor to see if we can reach predecessor."""
        visited: Set[str] = set()
        queue: deque[str] = deque([successor_id])
        while queue:
            current = queue.popleft()
            if current == predecessor_id:
                return True
            if current in visited:
                continue
            visited.add(current)
            for succ in self._successors.get(current, []):
                queue.append(succ)
        return False

    def topological_sort(self, item_ids: Optional[List[str]] = None) -> List[str]:
        """Return items in topological order (for scheduling).

        Uses Kahn's algorithm.  If *item_ids* is ``None``, sorts all known items.
        """
        if item_ids is None:
            item_ids = list(set(
                list(self._successors.keys()) +
                [s for lst in self._successors.values() for s in lst]
            ))

        in_degree: Dict[str, int] = {iid: 0 for iid in item_ids}
        for iid in item_ids:
            for pred in self._predecessors.get(iid, []):
                if pred in in_degree:
                    in_degree[iid] = in_degree.get(iid, 0) + 1

        queue: deque[str] = deque(iid for iid, d in in_degree.items() if d == 0)
        result: List[str] = []

        while queue:
            current = queue.popleft()
            result.append(current)
            for succ in self._successors.get(current, []):
                if succ in in_degree:
                    in_degree[succ] -= 1
                    if in_degree[succ] == 0:
                        queue.append(succ)

        return result
