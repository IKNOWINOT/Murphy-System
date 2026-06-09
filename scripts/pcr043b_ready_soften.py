#!/usr/bin/env python3
"""
PCR-043b — soften ready_agents() to fire when in-team deps satisfied

DIAGNOSIS (deeper than 043a):
  After PCR-043 seeded a 'prompt' node, Coordinator was still not ready
  because its declared inputs are ['prompt','analysis_report','schedule']
  but the trivial-complexity team has NO Analyst or Scheduler.
  The 'analysis_report' and 'schedule' inputs are unfulfillable for this
  team. ready_agents() correctly says "deps not met" and the loop dies.

FIX:
  An agent is ready when ALL inputs it can possibly receive from its
  CURRENT TEAM are present. If an input has no producer in the team
  (no team member declares it in output_types), it is unfulfillable and
  should not block.

  Replace the input.issubset(produced) check with a "satisfiable subset"
  check: only require the subset of inputs that some teammate CAN
  produce. If a required input is in nobody's output_types, treat it
  as not required for readiness.

  This is the right model: a 1-agent team with a Coordinator that needs
  data from Analysts won't have an Analyst — fire the Coordinator on
  what's available.

REVERSIBILITY:
  Single function body change. Marker-based.
"""

from __future__ import annotations
import argparse
import sys
from pathlib import Path

GRAPH = Path("/opt/Murphy-System/src/artifact_graph.py")

ANCHOR_OLD = '''    def ready_agents(self, team: List[Any]) -> List[Any]:
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
        return ready'''

ANCHOR_NEW = '''    def ready_agents(self, team: List[Any]) -> List[Any]:
        """PCR-043b — Agents are ready when all *in-team-satisfiable*
        inputs are present, and they haven't yet been fired.

        Inputs that no teammate can produce are 'unfulfillable' and
        treated as not blocking. Without this, small teams whose
        coordinator declares inputs from missing roles (e.g. Analyst)
        never fire and graph_state stays empty."""
        produced = self.produced()
        # Build the set of output_types ANY team member can produce.
        team_outputs: Set[str] = set()
        for agent in team:
            for o in (getattr(agent, "output_types", []) or []):
                team_outputs.add(o)
        ready = []
        for agent in team:
            inputs = set(getattr(agent, "input_types", []) or [])
            outputs = set(getattr(agent, "output_types", []) or [])
            # PCR-043b — only require inputs that SOMEONE in the team
            # can actually produce. Unfulfillable inputs are dropped
            # from the readiness check.
            required = inputs & team_outputs
            if required and not required.issubset(produced):
                continue
            # If after dropping unfulfillable inputs the agent has
            # zero required inputs, it can fire on initial seed.
            # already-fired if any of its outputs already in graph
            if outputs and outputs.issubset(set(self.nodes.keys())):
                continue
            ready.append(agent)
        return ready'''


def apply(verify, revert):
    print(f"PCR-043b ready_agents soften  verify={verify}  revert={revert}")
    src = GRAPH.read_text(encoding="utf-8")
    if revert:
        if "PCR-043b" not in src:
            print("  · already absent"); return 0
        src = src.replace(ANCHOR_NEW, ANCHOR_OLD, 1)
        if verify: print("  ✓ would revert"); return 0
        GRAPH.write_text(src, encoding="utf-8")
        print("  ✓ reverted"); return 0
    if "PCR-043b" in src:
        print("  · already present"); return 0
    if ANCHOR_OLD not in src:
        print("  ✗ ANCHOR_OLD not found"); return 1
    src = src.replace(ANCHOR_OLD, ANCHOR_NEW, 1)
    if verify: print("  ✓ would apply"); return 0
    GRAPH.write_text(src, encoding="utf-8")
    print("  ✓ ready_agents() now drops unfulfillable inputs")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--revert", action="store_true")
    a = ap.parse_args()
    return apply(a.verify, a.revert)


if __name__ == "__main__":
    sys.exit(main())
