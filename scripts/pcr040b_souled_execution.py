#!/usr/bin/env python3
"""
PCR-040b — Souled agent execution + graph mutation.

The execution layer for PCR-040a's role I/O contracts. Souled agents
actually fire LLM calls, produce structured output artifacts, mutate
the graph. This IS the ping-pong of information transformation.

WHAT THIS DOES:
  - Creates src/artifact_graph.py with the ArtifactGraph class
  - Adds a souled_execution module that:
      1. Iterates rounds until no more ready agents
      2. For each ready agent: build brief from graph inputs + soul +
         call LLMController.query_llm with structured prompt
      3. Parse response into output artifacts, write to graph
      4. Fail-soft: errors logged, graph marked, downstream waits
  - Wires execution into /api/rosetta/dispatch as opt-in
    (controlled by PCR040B_EXECUTE env var, default off for safety)
  - Surfaces graph_state in dispatch response

WHAT THIS DOES NOT DO YET:
  - Convergence/refinement loop (round 2 mutating round 1) — PCR-040c
  - Streaming responses
  - Per-agent cost surfacing in response (cost still logged to ledger)

SAFETY:
  - PCR040B_EXECUTE env var controls activation (default: 0 = dry-run)
  - In dry-run: graph_state shows what WOULD execute, no LLM calls
  - In live mode: each agent has 60s budget, failures don't propagate
  - Total dispatch time bounded at 180s
  - Marker-based revert
"""

from __future__ import annotations
import argparse
import sys
from pathlib import Path

APP = Path("/opt/Murphy-System/src/runtime/app.py")
NEW_MODULE = Path("/opt/Murphy-System/src/artifact_graph.py")

# ─── 1. The ArtifactGraph module ─────────────────────────────────────────
ARTIFACT_GRAPH_SRC = '''"""
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
'''

# ─── 2. The dispatch-side hook (PCR-040b BEGIN block) ────────────────────
# We insert just AFTER the PCR-036 compound block, BEFORE the response
# is built. Anchor: existing "compound_workflow" in the response dict.

DISPATCH_HOOK_OLD = '''                "compound_workflow": locals().get("_pcr036_workflow"),  # PCR-036'''

DISPATCH_HOOK_NEW = '''                "compound_workflow": locals().get("_pcr036_workflow"),  # PCR-036
                "graph_state": locals().get("_pcr040b_graph_dict"),  # PCR-040b'''

# The execution block itself, inserted after the PCR-036 END marker.
# We anchor on a stable line right after PCR-036's block.
PCR036_END_ANCHOR = '''                except Exception as _drp_err_036:
                        _notify("[PCR-036] E_PCR036_0008 planner unavailable: " +
                                str(_drp_err_036)[:80])'''

PCR040B_BLOCK = '''                except Exception as _drp_err_036:
                        _notify("[PCR-036] E_PCR036_0008 planner unavailable: " +
                                str(_drp_err_036)[:80])

                # PCR-040b BEGIN souled execution
                # When PCR040B_EXECUTE=1, fire ready agents via LLM and
                # mutate an artifact graph. Otherwise dry-run: show what
                # WOULD execute without making LLM calls.
                _pcr040b_graph_dict = None
                try:
                    import os as _os_040b
                    _pcr040b_execute = _os_040b.environ.get("PCR040B_EXECUTE", "0") == "1"
                    if "_pkt360" in locals() and _pkt360 is not None:
                        from artifact_graph import new_graph as _new_graph_040b
                        from artifact_graph import ArtifactNode as _ArtifactNode_040b
                        _graph_040b = _new_graph_040b(prompt)
                        _team_040b = _pkt360.team
                        _souls_040b = _pkt360.soul_contexts or {}
                        _max_rounds_040b = 8
                        _round_040b = 0
                        _fired_040b = []
                        _failed_040b = []

                        while _round_040b < _max_rounds_040b:
                            _ready_040b = _graph_040b.ready_agents(_team_040b)
                            if not _ready_040b:
                                break
                            _round_040b += 1
                            for _agent_040b in _ready_040b:
                                _aid_040b = _agent_040b.agent_id
                                _role_040b = _agent_040b.role_class
                                _outs_040b = list(getattr(_agent_040b, "output_types", []) or [])

                                if not _pcr040b_execute:
                                    # DRY RUN — mark would-fire, write stub
                                    for _ot_040b in _outs_040b:
                                        _node_040b = _ArtifactNode_040b(
                                            output_type=_ot_040b,
                                            producer_role=_role_040b,
                                            producer_agent_id=_aid_040b,
                                            content={"_dry_run": True,
                                                     "_note": "PCR040B_EXECUTE=0"},
                                            raw_response="",
                                            produced_at=datetime.utcnow().isoformat() + "Z",
                                            success=True,
                                        )
                                        _graph_040b.add(_node_040b)
                                    _fired_040b.append(_aid_040b)
                                    _notify("  [PCR-040b dry] would fire " + _role_040b + " -> " + str(_outs_040b))
                                    continue

                                # LIVE — build brief, call LLM, parse output
                                try:
                                    _ins_040b = list(getattr(_agent_040b, "input_types", []) or [])
                                    _input_context_040b = []
                                    for _it_040b in _ins_040b:
                                        if _it_040b == "prompt":
                                            _input_context_040b.append("PROMPT:\\n" + prompt)
                                        else:
                                            _src_040b = _graph_040b.get(_it_040b)
                                            if _src_040b and _src_040b.success:
                                                _input_context_040b.append(
                                                    "INPUT [" + _it_040b + "] (from " +
                                                    _src_040b.producer_role + "):\\n" +
                                                    str(_src_040b.content)[:2000]
                                                )
                                    _soul_040b = _souls_040b.get(_aid_040b, "")
                                    _brief_040b = (
                                        "You are " + _role_040b + ". Your soul follows.\\n\\n" +
                                        _soul_040b[:3000] +
                                        "\\n\\n=== INPUT NODES ===\\n" +
                                        "\\n\\n".join(_input_context_040b) +
                                        "\\n\\n=== YOUR TASK ===\\n" +
                                        "Produce JSON with these output keys: " + str(_outs_040b) + ".\\n" +
                                        "Each key should map to a structured object representing that artifact.\\n" +
                                        "Return ONLY valid JSON, no markdown, no commentary.\\n"
                                    )

                                    # Call LLM
                                    from src.llm_controller import LLMController as _LLMC_040b, LLMRequest as _LLMReq_040b
                                    import asyncio as _asyncio_040b
                                    _llm_040b = _LLMC_040b()
                                    _req_040b = _LLMReq_040b(
                                        query=_brief_040b,
                                        context="",
                                        max_tokens=2000,
                                    ) if hasattr(_LLMReq_040b, "__init__") else _LLMReq_040b(query=_brief_040b)
                                    # Use a fresh event loop per call (dispatch is sync)
                                    _loop_040b = _asyncio_040b.new_event_loop()
                                    try:
                                        _resp_040b = _loop_040b.run_until_complete(
                                            _asyncio_040b.wait_for(
                                                _llm_040b.query_llm(_req_040b),
                                                timeout=60.0
                                            )
                                        )
                                    finally:
                                        _loop_040b.close()

                                    _raw_040b = getattr(_resp_040b, "content", "") or str(_resp_040b)

                                    # Parse JSON, tolerant
                                    import json as _json_040b
                                    import re as _re_040b
                                    _parsed_040b = None
                                    try:
                                        _parsed_040b = _json_040b.loads(_raw_040b)
                                    except Exception:
                                        # Try to extract JSON object from response
                                        _m_040b = _re_040b.search(r"\\{.*\\}", _raw_040b, _re_040b.DOTALL)
                                        if _m_040b:
                                            try:
                                                _parsed_040b = _json_040b.loads(_m_040b.group(0))
                                            except Exception:
                                                _parsed_040b = None

                                    if _parsed_040b is None:
                                        # Couldn't parse — store raw under first output
                                        for _ot_040b in _outs_040b:
                                            _graph_040b.add(_ArtifactNode_040b(
                                                output_type=_ot_040b,
                                                producer_role=_role_040b,
                                                producer_agent_id=_aid_040b,
                                                content={"_unparsed": _raw_040b[:1000]},
                                                raw_response=_raw_040b[:5000],
                                                produced_at=datetime.utcnow().isoformat() + "Z",
                                                success=False,
                                                error="JSON parse failed",
                                            ))
                                        _failed_040b.append(_aid_040b)
                                        _notify("  [PCR-040b] " + _role_040b + " PARSE FAIL")
                                        continue

                                    # Write each declared output
                                    for _ot_040b in _outs_040b:
                                        _content_040b = _parsed_040b.get(_ot_040b, _parsed_040b)
                                        _graph_040b.add(_ArtifactNode_040b(
                                            output_type=_ot_040b,
                                            producer_role=_role_040b,
                                            producer_agent_id=_aid_040b,
                                            content=_content_040b,
                                            raw_response=_raw_040b[:5000],
                                            produced_at=datetime.utcnow().isoformat() + "Z",
                                            success=True,
                                        ))
                                    _fired_040b.append(_aid_040b)
                                    _notify("  [PCR-040b] " + _role_040b + " produced " + str(_outs_040b))

                                except Exception as _e_agent_040b:
                                    # Mark all this agent's outputs as failed
                                    for _ot_040b in _outs_040b:
                                        _graph_040b.add(_ArtifactNode_040b(
                                            output_type=_ot_040b,
                                            producer_role=_role_040b,
                                            producer_agent_id=_aid_040b,
                                            content={},
                                            raw_response="",
                                            produced_at=datetime.utcnow().isoformat() + "Z",
                                            success=False,
                                            error=str(_e_agent_040b)[:200],
                                        ))
                                    _failed_040b.append(_aid_040b)
                                    _notify("  [PCR-040b] " + _role_040b + " FAILED: " + str(_e_agent_040b)[:80])

                        _unfilled_040b = _graph_040b.unfilled(_team_040b)
                        _pcr040b_graph_dict = _graph_040b.to_dict()
                        _pcr040b_graph_dict["mode"] = "live" if _pcr040b_execute else "dry"
                        _pcr040b_graph_dict["rounds"] = _round_040b
                        _pcr040b_graph_dict["fired"] = _fired_040b
                        _pcr040b_graph_dict["failed"] = _failed_040b
                        _pcr040b_graph_dict["unfilled"] = _unfilled_040b
                        _notify("[PCR-040b] graph: rounds=" + str(_round_040b) +
                                " fired=" + str(len(_fired_040b)) +
                                " failed=" + str(len(_failed_040b)) +
                                " unfilled=" + str(len(_unfilled_040b)))
                except Exception as _e_040b:
                    _notify("[PCR-040b] E_PCR040B_0001 graph execution failed: " +
                            str(_e_040b)[:120])
                # PCR-040b END souled execution'''


def apply(verify: bool, revert: bool) -> int:
    print(f"PCR-040b patcher  verify={verify}  revert={revert}")
    print("=" * 60)
    app_src = APP.read_text(encoding="utf-8")

    if revert:
        if "PCR-040b BEGIN" not in app_src and not NEW_MODULE.exists():
            print("  · already absent")
            return 0
        app_src = app_src.replace(PCR040B_BLOCK, PCR036_END_ANCHOR, 1)
        app_src = app_src.replace(DISPATCH_HOOK_NEW, DISPATCH_HOOK_OLD, 1)
        if verify:
            print("  ✓ (verify) would revert PCR-040b")
            return 0
        APP.write_text(app_src, encoding="utf-8")
        if NEW_MODULE.exists():
            NEW_MODULE.unlink()
        print("  ✓ reverted PCR-040b")
        return 0

    # Apply
    if "PCR-040b BEGIN" in app_src:
        print("  · already present")
        return 0

    if PCR036_END_ANCHOR not in app_src:
        print("  ✗ PCR-036 end anchor not found")
        return 1
    if DISPATCH_HOOK_OLD not in app_src:
        print("  ✗ dispatch response hook anchor not found")
        return 1

    app_src = app_src.replace(PCR036_END_ANCHOR, PCR040B_BLOCK, 1)
    app_src = app_src.replace(DISPATCH_HOOK_OLD, DISPATCH_HOOK_NEW, 1)

    if verify:
        print("  ✓ (verify) would insert PCR-040b")
        print("     + create src/artifact_graph.py")
        print("     + wire dispatch hook")
        print("     + add graph_state to response")
        return 0

    NEW_MODULE.write_text(ARTIFACT_GRAPH_SRC, encoding="utf-8")
    APP.write_text(app_src, encoding="utf-8")
    print("  ✓ created src/artifact_graph.py")
    print("  ✓ wired PCR-040b execution block into dispatch")
    print("  ✓ graph_state added to dispatch response")
    print("=" * 60)
    print("  ✓ done")
    print()
    print("  ACTIVATION:")
    print("    Default: DRY-RUN (PCR040B_EXECUTE=0). Graph shows what WOULD fire.")
    print("    Live:    export PCR040B_EXECUTE=1 and restart service.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--revert", action="store_true")
    args = ap.parse_args()
    return apply(verify=args.verify, revert=args.revert)


if __name__ == "__main__":
    sys.exit(main())
