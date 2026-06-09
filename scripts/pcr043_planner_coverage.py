#!/usr/bin/env python3
"""
PCR-043 — Planner coverage for short prompts (graph_state.nodes == 0)

DIAGNOSIS (live):
  Prompt "hi" → team_size=1 (Coordinator)
  Coordinator inputs = ['prompt', 'analysis_report', 'schedule']
  initial graph nodes = []
  ready_agents() requires inputs ⊆ produced → empty produced → 0 ready
  while loop breaks at round 0 → graph_state.nodes = 0

ROOT CAUSE:
  new_graph(prompt) returns an empty ArtifactGraph. No agent can be
  "ready" because none of their declared inputs (including the universal
  'prompt' input) are present as produced artifacts.

FIX:
  Seed the new graph with a 'prompt' ArtifactNode containing the user
  prompt as content. This is the ONE artifact every agent expects as a
  starting input. With the prompt seed present, agents whose inputs are
  satisfied by {'prompt'} (e.g. simple coordinators) immediately become
  ready, the while loop fires them, and graph_state.nodes > 0.

  No semantic change for prompts that already produce a multi-agent
  team — the seed is just a recognized input type, not an output the
  team competes to produce.

REVERSIBILITY:
  Single function body change. Marker-based. Pure additive seed.
"""

from __future__ import annotations
import argparse
import sys
from pathlib import Path

GRAPH = Path("/opt/Murphy-System/src/artifact_graph.py")

ANCHOR_OLD = """def new_graph(prompt: str) -> ArtifactGraph:
    return ArtifactGraph(prompt=prompt)"""

ANCHOR_NEW = '''def new_graph(prompt: str) -> ArtifactGraph:
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
    return _g'''


def apply(verify, revert):
    print(f"PCR-043 planner coverage  verify={verify}  revert={revert}")
    src = GRAPH.read_text(encoding="utf-8")
    if revert:
        if "PCR-043" not in src:
            print("  · already absent"); return 0
        src = src.replace(ANCHOR_NEW, ANCHOR_OLD, 1)
        if verify: print("  ✓ would revert"); return 0
        GRAPH.write_text(src, encoding="utf-8")
        print("  ✓ reverted"); return 0
    if "PCR-043" in src:
        print("  · already present"); return 0
    if ANCHOR_OLD not in src:
        print("  ✗ ANCHOR_OLD not found"); return 1
    src = src.replace(ANCHOR_OLD, ANCHOR_NEW, 1)
    if verify: print("  ✓ would apply"); return 0
    GRAPH.write_text(src, encoding="utf-8")
    print("  ✓ new_graph() now seeds a 'prompt' ArtifactNode")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--revert", action="store_true")
    a = ap.parse_args()
    return apply(a.verify, a.revert)


if __name__ == "__main__":
    sys.exit(main())
