#!/usr/bin/env python3
"""
PCR-040c — Refinement loop (multi-pass convergence).

After PCR-040b's single-pass execution completes the graph, give each
agent whose outputs were consumed downstream a chance to revise its
work given what was built on top of it. Repeat until either
  - no agent wants to revise (natural convergence)
  - max_passes hit (budget bound)

DESIGN CHOICE: self-review, not critic-driven.
  Each agent re-reads its own output + the downstream consumer's
  output, decides "do I want to revise based on what others built on
  me?" — yes produces v2, no leaves it. No new role added. No
  separate critic. The work IS the state on the graph going toward
  complete (founder's words).

VERSIONING:
  ArtifactGraph nodes get a `version` field. add() now produces v1,
  v2, v3... when called multiple times for the same output_type.
  Latest version is always returned by get().

ACTIVATION:
  PCR040C_MAX_PASSES env var. Default 1 = current PCR-040b behavior.
  Set 2 or 3 to enable refinement. Each pass costs ~5 LLM calls.

SAFETY:
  - Default off (max_passes=1 = single-pass, unchanged)
  - Fail-soft on refinement errors (graph keeps the original)
  - Marker-based revert
"""

from __future__ import annotations
import argparse
import sys
from pathlib import Path

ARTIFACT_GRAPH = Path("/opt/Murphy-System/src/artifact_graph.py")
APP = Path("/opt/Murphy-System/src/runtime/app.py")

# ─── 1. Extend ArtifactGraph for versioning + refinement readiness ───────

AG_OLD = '''    def add(self, node: ArtifactNode) -> None:
        self.nodes[node.output_type] = node

    def get(self, output_type: str) -> Optional[ArtifactNode]:
        return self.nodes.get(output_type)'''

AG_NEW = '''    def add(self, node: ArtifactNode) -> None:
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
        return eligible'''

# Add `version` field to ArtifactNode
NODE_OLD = '''    success: bool = True
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:'''

NODE_NEW = '''    success: bool = True
    error: Optional[str] = None
    version: int = 1  # PCR-040c — bumps on each refinement

    def to_dict(self) -> Dict[str, Any]:'''

NODE_DICT_OLD = '''            "success":           self.success,
            "error":             self.error,
        }'''

NODE_DICT_NEW = '''            "success":           self.success,
            "error":             self.error,
            "version":           self.version,
        }'''

# ─── 2. Wrap the dispatch execution in a passes loop ─────────────────────

# Anchor: the start of the existing PCR-040b execution block.
# We're inserting BEFORE the `while _round_040b` loop and AFTER it.

WRAP_OLD = '''                    if "_pkt360" in locals() and _pkt360 is not None:
                        from artifact_graph import new_graph as _new_graph_040b
                        from artifact_graph import ArtifactNode as _ArtifactNode_040b
                        _graph_040b = _new_graph_040b(prompt)
                        _team_040b = _pkt360.team
                        _souls_040b = _pkt360.soul_contexts or {}
                        _max_rounds_040b = 8
                        _round_040b = 0
                        _fired_040b = []
                        _failed_040b = []

                        while _round_040b < _max_rounds_040b:'''

WRAP_NEW = '''                    if "_pkt360" in locals() and _pkt360 is not None:
                        from artifact_graph import new_graph as _new_graph_040b
                        from artifact_graph import ArtifactNode as _ArtifactNode_040b
                        _graph_040b = _new_graph_040b(prompt)
                        _team_040b = _pkt360.team
                        _souls_040b = _pkt360.soul_contexts or {}
                        _max_rounds_040b = 8
                        _round_040b = 0
                        _fired_040b = []
                        _failed_040b = []

                        # PCR-040c — multi-pass refinement loop
                        _max_passes_040c = int(_os_040b.environ.get("PCR040C_MAX_PASSES", "1"))
                        _passes_040c = []  # per-pass summaries

                        while _round_040b < _max_rounds_040b:'''

# After the main while loop closes, before _unfilled_040b is computed,
# add the refinement passes. Anchor: the line that computes _unfilled_040b.

REFINE_OLD = '''                        _unfilled_040b = _graph_040b.unfilled(_team_040b)'''

REFINE_NEW = '''                        # PCR-040c — refinement passes (default off, max_passes=1)
                        _passes_040c.append({"pass": 1, "fired": len(_fired_040b),
                                              "failed": len(_failed_040b)})
                        _current_pass_040c = 1
                        while _current_pass_040c < _max_passes_040c and _pcr040b_execute:
                            _current_pass_040c += 1
                            _refine_eligible_040c = _graph_040b.ready_for_refinement(_team_040b)
                            if not _refine_eligible_040c:
                                _notify("  [PCR-040c] pass " + str(_current_pass_040c) +
                                        ": no refinement-eligible agents, converged")
                                break
                            _pass_refined_040c = []
                            for _agent_040c in _refine_eligible_040c:
                                _aid_040c = _agent_040c.agent_id
                                _role_040c = _agent_040c.role_class
                                _outs_040c = list(getattr(_agent_040c, "output_types", []) or [])
                                try:
                                    # Build refinement brief: prev output + downstream consumers
                                    _prev_content_040c = {}
                                    for _ot_040c in _outs_040c:
                                        _prev_node_040c = _graph_040b.get(_ot_040c)
                                        if _prev_node_040c:
                                            _prev_content_040c[_ot_040c] = _prev_node_040c.content
                                    # Find downstream consumers' outputs
                                    _downstream_040c = []
                                    for _other_040c in _team_040b:
                                        if _other_040c is _agent_040c: continue
                                        _other_ins_040c = set(getattr(_other_040c, "input_types", []) or [])
                                        if _other_ins_040c & set(_outs_040c):
                                            for _other_ot_040c in (_other_040c.output_types or []):
                                                _dn_node_040c = _graph_040b.get(_other_ot_040c)
                                                if _dn_node_040c and _dn_node_040c.success:
                                                    _downstream_040c.append(
                                                        "[" + _other_ot_040c + "] by " +
                                                        _other_040c.role_class + ":\\n" +
                                                        str(_dn_node_040c.content)[:1500]
                                                    )
                                    _soul_040c = _souls_040b.get(_aid_040c, "")
                                    _refine_brief_040c = (
                                        "You are " + _role_040c + ". Your soul:\\n" +
                                        _soul_040c[:2000] +
                                        "\\n\\n=== YOUR PREVIOUS OUTPUT ===\\n" +
                                        str(_prev_content_040c)[:2000] +
                                        "\\n\\n=== WHAT DOWNSTREAM AGENTS BUILT ON TOP ===\\n" +
                                        "\\n\\n".join(_downstream_040c) +
                                        "\\n\\n=== REFINEMENT TASK ===\\n" +
                                        "Given how downstream agents built on your work, would you " +
                                        "revise your output to better support what they need or " +
                                        "correct anything they exposed? If NO revision needed, " +
                                        "return: {\\"_no_change\\": true}\\n" +
                                        "If YES, return JSON with keys " + str(_outs_040c) +
                                        " containing your REVISED outputs. ONLY valid JSON.\\n"
                                    )
                                    _llm_040c = _MLLM_040b()
                                    _resp_040c = _llm_040c.complete(
                                        prompt=_refine_brief_040c,
                                        system="You are a refinement agent. Return only valid JSON.",
                                        max_tokens=2000, temperature=0.5,
                                    )
                                    _raw_040c = getattr(_resp_040c, "content", "") or ""
                                    _parsed_040c = None
                                    try:
                                        _parsed_040c = _json_040b.loads(_raw_040c)
                                    except Exception:
                                        _m_040c = _re_040b.search(r"\\{.*\\}", _raw_040c, _re_040b.DOTALL)
                                        if _m_040c:
                                            try: _parsed_040c = _json_040b.loads(_m_040c.group(0))
                                            except Exception: pass
                                    if _parsed_040c is None:
                                        continue  # parse fail = no revision
                                    if _parsed_040c.get("_no_change"):
                                        continue  # agent declined to revise
                                    # Write revised outputs (versioned by graph.add)
                                    for _ot_040c in _outs_040c:
                                        _revised_040c = _parsed_040c.get(_ot_040c)
                                        if _revised_040c is None: continue
                                        _graph_040b.add(_ArtifactNode_040b(
                                            output_type=_ot_040c,
                                            producer_role=_role_040c,
                                            producer_agent_id=_aid_040c,
                                            content=_revised_040c,
                                            raw_response=_raw_040c[:5000],
                                            produced_at=datetime.utcnow().isoformat() + "Z",
                                            success=True,
                                        ))
                                    _pass_refined_040c.append(_aid_040c)
                                    _notify("  [PCR-040c] pass " + str(_current_pass_040c) +
                                            ": " + _role_040c + " revised " + str(_outs_040c))
                                except Exception as _e_refine_040c:
                                    _notify("  [PCR-040c] pass " + str(_current_pass_040c) +
                                            ": " + _role_040c + " refine failed: " +
                                            str(_e_refine_040c)[:80])
                            _passes_040c.append({
                                "pass": _current_pass_040c,
                                "refined": _pass_refined_040c,
                                "refined_count": len(_pass_refined_040c),
                            })
                            if not _pass_refined_040c:
                                _notify("  [PCR-040c] pass " + str(_current_pass_040c) +
                                        ": no agent revised, converged")
                                break
                        # PCR-040c — surface pass history
                        _unfilled_040b = _graph_040b.unfilled(_team_040b)'''

# Surface passes in response payload
DICT_OLD = '''                        _pcr040b_graph_dict["unfilled"] = _unfilled_040b'''

DICT_NEW = '''                        _pcr040b_graph_dict["unfilled"] = _unfilled_040b
                        _pcr040b_graph_dict["passes"] = _passes_040c  # PCR-040c'''


def apply(verify: bool, revert: bool) -> int:
    print(f"PCR-040c patcher  verify={verify}  revert={revert}")
    print("=" * 60)
    ag_src = ARTIFACT_GRAPH.read_text(encoding="utf-8")
    app_src = APP.read_text(encoding="utf-8")

    if revert:
        if "PCR-040c" not in ag_src and "PCR-040c" not in app_src:
            print("  · already absent"); return 0
        ag_src = ag_src.replace(AG_NEW, AG_OLD, 1)
        ag_src = ag_src.replace(NODE_NEW, NODE_OLD, 1)
        ag_src = ag_src.replace(NODE_DICT_NEW, NODE_DICT_OLD, 1)
        app_src = app_src.replace(WRAP_NEW, WRAP_OLD, 1)
        app_src = app_src.replace(REFINE_NEW, REFINE_OLD, 1)
        app_src = app_src.replace(DICT_NEW, DICT_OLD, 1)
        if verify: print("  ✓ would revert"); return 0
        ARTIFACT_GRAPH.write_text(ag_src, encoding="utf-8")
        APP.write_text(app_src, encoding="utf-8")
        print("  ✓ reverted"); return 0

    if "PCR-040c" in ag_src or "PCR-040c" in app_src:
        print("  · already present"); return 0

    # Anchor checks
    misses = []
    if AG_OLD not in ag_src: misses.append("AG_OLD")
    if NODE_OLD not in ag_src: misses.append("NODE_OLD")
    if NODE_DICT_OLD not in ag_src: misses.append("NODE_DICT_OLD")
    if WRAP_OLD not in app_src: misses.append("WRAP_OLD")
    if REFINE_OLD not in app_src: misses.append("REFINE_OLD")
    if DICT_OLD not in app_src: misses.append("DICT_OLD")
    if misses:
        print(f"  ✗ anchors missing: {misses}")
        return 1

    ag_src = ag_src.replace(AG_OLD, AG_NEW, 1)
    ag_src = ag_src.replace(NODE_OLD, NODE_NEW, 1)
    ag_src = ag_src.replace(NODE_DICT_OLD, NODE_DICT_NEW, 1)
    app_src = app_src.replace(WRAP_OLD, WRAP_NEW, 1)
    app_src = app_src.replace(REFINE_OLD, REFINE_NEW, 1)
    app_src = app_src.replace(DICT_OLD, DICT_NEW, 1)

    if verify: print("  ✓ would apply"); return 0

    ARTIFACT_GRAPH.write_text(ag_src, encoding="utf-8")
    APP.write_text(app_src, encoding="utf-8")
    print("  ✓ ArtifactGraph: versioning + ready_for_refinement()")
    print("  ✓ dispatch: refinement pass loop (default 1 pass = unchanged)")
    print("  ✓ response: graph_state.passes added")
    print("=" * 60)
    print("  ACTIVATION:")
    print("    Default: PCR040C_MAX_PASSES=1 = single-pass (current behavior)")
    print("    Refine:  PCR040C_MAX_PASSES=2 or 3 (+~30-60s per pass)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--revert", action="store_true")
    a = ap.parse_args()
    return apply(a.verify, a.revert)


if __name__ == "__main__":
    sys.exit(main())
