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
    version: int = 1  # PCR-040c — bumps on each refinement

    def to_dict(self) -> Dict[str, Any]:
        return {
            "output_type":       self.output_type,
            "producer_role":     self.producer_role,
            "producer_agent_id": self.producer_agent_id,
            "content":           self.content,
            "produced_at":       self.produced_at,
            "success":           self.success,
            "error":             self.error,
            "version":           self.version,
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
        # PCR-040c — versioning: if this output_type already has a node,
        # archive the old one under {output_type}@v{n} and increment.
        existing = self.nodes.get(node.output_type)
        if existing is not None:
            # Find current max version for this type
            v = 1
            for k in list(self.nodes.keys()):
                if k.startswith(node.output_type + "@v"):
                    try:
                        n = int(k.split("@v")[-1])
                        if n >= v: v = n + 1
                    except Exception:
                        pass
            # If first overwrite, archive original as v1
            if v == 1:
                self.nodes[node.output_type + "@v1"] = existing
                v = 2
            # Mark the new node with its version
            try:
                node.version = v
            except Exception:
                pass
            self.nodes[node.output_type + "@v" + str(v)] = node
        else:
            try:
                node.version = 1
            except Exception:
                pass
        # latest always lives at the unversioned key
        self.nodes[node.output_type] = node

    def get(self, output_type: str) -> Optional[ArtifactNode]:
        return self.nodes.get(output_type)

    def ready_for_refinement(self, team: List[Any]) -> List[Any]:
        """PCR-040c — agents whose outputs were consumed downstream.

        An agent A is refinement-ready when:
          - A has fired (its outputs are in the graph)
          - Some other agent B has fired with A's outputs as inputs
            (so A's work has been 'built on top of')
          - Therefore A has new context to potentially revise against

        Terminal agents (whose outputs nobody consumes) are not
        refinement-eligible — there's nothing new for them to react to.
        """
        produced_types = set()
        for k in self.nodes.keys():
            if "@v" not in k:
                produced_types.add(k)
        eligible = []
        for agent in team:
            outs = set(getattr(agent, "output_types", []) or [])
            if not outs: continue
            if not outs.issubset(produced_types): continue  # didn't fire
            # Is any downstream consumer producing now?
            consumed = False
            for other in team:
                if other is agent: continue
                other_ins = set(getattr(other, "input_types", []) or [])
                if other_ins & outs:
                    # other consumes some of agent's outputs
                    other_outs = set(getattr(other, "output_types", []) or [])
                    if other_outs and other_outs.issubset(produced_types):
                        consumed = True
                        break
            if consumed:
                eligible.append(agent)
        return eligible

    def ready_agents(self, team: List[Any]) -> List[Any]:
        """PCR-044 — Agents whose KICKOFF inputs are satisfied, and which
        haven't yet been fired. kickoff_inputs (if declared) lets a role
        fire on a subset of its full input list, with refinement inputs
        deferred to ready_for_refinement() in pass 2+.

        Backward compatible: agents without kickoff_inputs use input_types.
        """
        produced = self.produced()
        ready = []
        for agent in team:
            # PCR-044 — prefer kickoff_inputs (pass-1 requirements) when
            # the agent declares them. Fall back to input_types otherwise.
            _kickoff = getattr(agent, "kickoff_inputs", None)
            if _kickoff:
                inputs = set(_kickoff)
            else:
                inputs = set(getattr(agent, "input_types", []) or [])
            outputs = set(getattr(agent, "output_types", []) or [])
            # not ready if any kickoff input missing
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
    # PCR-043 — seed graph with a 'prompt' ArtifactNode so agents whose
    # declared inputs include 'prompt' can immediately be ready. Without
    # this seed, short prompts produce empty graphs because no agent's
    # input set is ever satisfied.
    from datetime import datetime as _dt043
    _g = ArtifactGraph(prompt=prompt)
    try:
        _seed = ArtifactNode(
            output_type="prompt",
            producer_role="user",
            producer_agent_id="user",
            content={"prompt": prompt},
            raw_response=str(prompt)[:5000],
            produced_at=_dt043.utcnow().isoformat() + "Z",
            success=True,
        )
        _g.add(_seed)
    except Exception:
        # If seeding fails for any reason, return the empty graph —
        # preserves prior behavior, just no PCR-043 benefit.
        pass
    return _g
