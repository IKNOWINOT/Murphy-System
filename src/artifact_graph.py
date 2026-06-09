"""
PCR-040b — ArtifactGraph: the state of the work as a graph.

The output of one agent is the input data for another.
The graph holds all produced artifacts, indexed by output_type.
When ALL of an agent's input_types are present in the graph, the
agent is "ready" to fire.

This is the projection model. The graph IS the projection. Complete
means: all terminal-deliverable inputs are satisfied.

Designed to compose with DLF-R packages (each artifact node maps to
a DLF-R weave).
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set
from datetime import datetime, timezone


@dataclass
class ArtifactNode:
    """One artifact produced by one agent."""
    output_type: str
    producer_role: str
    producer_agent_id: str
    content: Any                  # structured data from LLM parse
    raw_response: str = ""        # full LLM response for forensics
    produced_at: str = ""
    success: bool = True
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "output_type":       self.output_type,
            "producer_role":     self.producer_role,
            "producer_agent_id": self.producer_agent_id,
            "content":           self.content,
            "produced_at":       self.produced_at,
            "success":           self.success,
            "error":             self.error,
        }


@dataclass
class ArtifactGraph:
    """All produced artifacts for one dispatch run."""
    prompt: str
    nodes: Dict[str, ArtifactNode] = field(default_factory=dict)
    # output_type -> ArtifactNode  (one producer per type per run)

    def produced(self) -> Set[str]:
        """Set of output_types currently present in the graph."""
        # 'prompt' is always available as a virtual input
        return {"prompt"} | set(self.nodes.keys())

    def add(self, node: ArtifactNode) -> None:
        self.nodes[node.output_type] = node

    def get(self, output_type: str) -> Optional[ArtifactNode]:
        return self.nodes.get(output_type)

    def ready_agents(self, team: List[Any]) -> List[Any]:
        """Agents whose all input_types are satisfied, and which
        haven't yet been fired (no outputs produced)."""
        produced = self.produced()
        ready = []
        for agent in team:
            inputs = set(getattr(agent, "input_types", []) or [])
            outputs = set(getattr(agent, "output_types", []) or [])
            # not ready if any input missing
            if not inputs.issubset(produced):
                continue
            # already-fired if any of its outputs already in graph
            if outputs and outputs.issubset(set(self.nodes.keys())):
                continue
            ready.append(agent)
        return ready

    def unfilled(self, team: List[Any]) -> List[str]:
        """Output types still expected but not yet produced."""
        all_outputs: Set[str] = set()
        for agent in team:
            for o in getattr(agent, "output_types", []) or []:
                all_outputs.add(o)
        return sorted(all_outputs - set(self.nodes.keys()))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "prompt": self.prompt[:200],
            "nodes":  {k: v.to_dict() for k, v in self.nodes.items()},
            "produced_types": sorted(self.nodes.keys()),
        }


def new_graph(prompt: str) -> ArtifactGraph:
    return ArtifactGraph(prompt=prompt)
