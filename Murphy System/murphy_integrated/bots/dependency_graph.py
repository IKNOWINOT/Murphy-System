"""Cross-bot dependency graph utilities."""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, List


class DependencyGraph:
    def __init__(self) -> None:
        self.edges: Dict[str, List[str]] = defaultdict(list)

    def add_dependency(self, bot: str, depends_on: str) -> None:
        self.edges[bot].append(depends_on)

    def get_dependencies(self, bot: str) -> List[str]:
        return self.edges.get(bot, [])
