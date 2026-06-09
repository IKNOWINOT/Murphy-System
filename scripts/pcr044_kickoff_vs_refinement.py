#!/usr/bin/env python3
"""
PCR-044 (REPLACEMENT) — kickoff inputs vs refinement inputs

PRIOR (mistaken) PCR-044 was reverted. That fix stripped Lead Engineer's
test_plan and security_audit inputs entirely, which destroyed the
refinement loop (the whole point of having a cycle is so Lead can
collapse downstream feedback into a better second-pass deliverable —
potentially pivoting to a different job, e.g. a CAD redesign).

PROPER FIX (per founder direction 2026-06-09 00:05 PT):
  'If it collapsed to better information the lead engineer can conduct
   after the cycle from and possibly lead to different jobs next.
   Or what if it draws something in cad?'

  Distinguish KICKOFF inputs (required for pass 1) from REFINEMENT
  inputs (consumed in pass 2+ via ready_for_refinement, which already
  exists in artifact_graph.py).

MODEL:
  ROLE_IO_CONTRACTS becomes a 3-tuple (was 2-tuple):
    (kickoff_inputs, refinement_inputs, outputs)

  ready_agents() — first-pass — checks only kickoff_inputs.
  ready_for_refinement() — already exists, no change needed; the
    refinement brief already pulls downstream consumers' outputs.

  Backward compatibility:
    Roles still declared as 2-tuple → refinement_inputs = []
    Roles upgraded to 3-tuple → refinement loop has new info to feed.

  Lead Engineer becomes:
    kickoff:    ["prompt"]
    refinement: ["test_plan", "security_audit"]
    outputs:    ["architecture_decision", "deliverable"]

  All OTHER roles remain unchanged (2-tuple → refinement=[] default).

WHY THIS IS THE RIGHT MODEL:
  - The cycle is the feature, not the bug.
  - 'Drawing in CAD' fits perfectly: Lead emits arch_decision (geometry),
    Code Executor renders the CAD file, QA validates dimensions, Security
    checks IP/licensing → Lead reviews their findings in pass 2 and either
    ships, iterates geometry, OR pivots the deliverable ('scrap the bracket,
    design a 3D-printed jig').
  - This composes cleanly with the persistent-agent direction: an agent's
    accomplishment record IS the set of refinement loops they've closed.

REVERSIBILITY:
  Two patches:
    A) artifact_graph.py — ready_agents() reads kickoff_inputs if the
       agent's input_types is a dict/3-tuple, else falls back to original.
    B) dynamic_rosetta_planner.py — Lead Engineer contract becomes the
       new 3-tuple shape; AgentBlueprint carries kickoff_inputs and
       refinement_inputs as separate fields.

  Both marker-based, both with --verify and --revert.
"""

from __future__ import annotations
import argparse
import sys
from pathlib import Path

GRAPH = Path("/opt/Murphy-System/src/artifact_graph.py")
PLANNER = Path("/opt/Murphy-System/src/dynamic_rosetta_planner.py")

# === PATCH A: ready_agents reads kickoff_inputs if present ===
GRAPH_OLD = '''    def ready_agents(self, team: List[Any]) -> List[Any]:
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

GRAPH_NEW = '''    def ready_agents(self, team: List[Any]) -> List[Any]:
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
        return ready'''

# === PATCH B-1: AgentBlueprint gains kickoff_inputs + refinement_inputs ===
# Find current AgentBlueprint declaration
PLANNER_BLUEPRINT_OLD = '''    input_types: List[str] = field(default_factory=list)
    output_types: List[str] = field(default_factory=list)'''

PLANNER_BLUEPRINT_NEW = '''    input_types: List[str] = field(default_factory=list)
    output_types: List[str] = field(default_factory=list)
    # PCR-044 — kickoff vs refinement input separation. When kickoff_inputs
    # is set, ready_agents() uses it for pass 1; refinement_inputs are
    # consumed via ready_for_refinement() in pass 2+. Backward compatible:
    # leaving kickoff_inputs empty falls back to input_types.
    kickoff_inputs: List[str] = field(default_factory=list)
    refinement_inputs: List[str] = field(default_factory=list)'''

# === PATCH B-2: Lead Engineer contract becomes 3-tuple-aware ===
# Currently it's:
#   "Lead Engineer": (["prompt", "test_plan", "security_audit"],
#                     ["architecture_decision", "deliverable"]),
# We keep ROLE_IO_CONTRACTS as 2-tuple (kickoff, outputs) and add a
# new ROLE_REFINEMENT_INPUTS dict for the pass-2 inputs. This is the
# least-invasive change.
LEAD_OLD = '''    "Lead Engineer": (
        ["prompt", "test_plan", "security_audit"],
        ["architecture_decision", "deliverable"],
    ),'''

LEAD_NEW = '''    "Lead Engineer": (
        # PCR-044 — kickoff inputs: pass 1 architecture from the prompt alone.
        # Refinement inputs (test_plan, security_audit) consumed in pass 2+
        # via ready_for_refinement(), letting Lead collapse downstream
        # feedback into a revised architecture OR pivot to a different
        # deliverable (e.g. CAD redesign).
        ["prompt"],
        ["architecture_decision", "deliverable"],
    ),'''

# === PATCH B-3: introduce ROLE_REFINEMENT_INPUTS dict next to ROLE_IO_CONTRACTS ===
# We'll insert it right after the closing brace of ROLE_IO_CONTRACTS by
# anchoring on a known-following line. The simplest is to anchor on the
# DOMAIN_ROLE_TEMPLATES["general"] line which is unique.
REFINEMENT_DICT_OLD = '''DOMAIN_ROLE_TEMPLATES["general"] = DOMAIN_ROLE_TEMPLATES["exec_admin"]'''

REFINEMENT_DICT_NEW = '''# PCR-044 — refinement inputs (consumed in pass 2+ via ready_for_refinement).
# These are NOT prerequisites for the agent to fire pass 1. They let an
# agent collapse downstream feedback into a revised output OR a pivot.
# Keyed by role_class; missing roles default to no refinement inputs.
ROLE_REFINEMENT_INPUTS: Dict[str, List[str]] = {
    "Lead Engineer": ["test_plan", "security_audit"],
    # Future: other roles can opt in to refinement here as the loop
    # proves itself in engineering domain.
}

DOMAIN_ROLE_TEMPLATES["general"] = DOMAIN_ROLE_TEMPLATES["exec_admin"]'''

# === PATCH B-4: select_team() populates kickoff_inputs + refinement_inputs ===
# Currently it does:
#   _io_in, _io_out = ROLE_IO_CONTRACTS.get(role_class, ([], []))
#   ... input_types=list(_io_in), output_types=list(_io_out),
# We add kickoff_inputs (same as _io_in for now, since ROLE_IO_CONTRACTS
# now MEANS kickoff inputs) and refinement_inputs from the new dict.

SELECT_TEAM_OLD = '''            # PCR-040a — pull I/O contract for this role (empty default)
            _io_in, _io_out = ROLE_IO_CONTRACTS.get(role_class, ([], []))
            team.append(AgentBlueprint(
                agent_id=agent_id, role_class=role_class, department=dept,
                reports_to=coordinator_id if not is_coord else None,
                tone=tone, bias=bias, hitl_threshold=hitl_thresh,
                capabilities=caps, boundaries=bounds,
                task_brief=brief, emoji=emoji,
                input_types=list(_io_in), output_types=list(_io_out),
            ))'''

SELECT_TEAM_NEW = '''            # PCR-040a — pull I/O contract for this role (empty default)
            _io_in, _io_out = ROLE_IO_CONTRACTS.get(role_class, ([], []))
            # PCR-044 — kickoff inputs = ROLE_IO_CONTRACTS (pass 1 prereqs).
            # refinement_inputs come from ROLE_REFINEMENT_INPUTS (pass 2+).
            # input_types stays = union for backward compat with any
            # consumer that reads it directly.
            _refine_in = ROLE_REFINEMENT_INPUTS.get(role_class, [])
            _all_inputs = list(_io_in) + [x for x in _refine_in if x not in _io_in]
            team.append(AgentBlueprint(
                agent_id=agent_id, role_class=role_class, department=dept,
                reports_to=coordinator_id if not is_coord else None,
                tone=tone, bias=bias, hitl_threshold=hitl_thresh,
                capabilities=caps, boundaries=bounds,
                task_brief=brief, emoji=emoji,
                input_types=_all_inputs, output_types=list(_io_out),
                kickoff_inputs=list(_io_in),
                refinement_inputs=list(_refine_in),
            ))'''


def _patch(path: Path, old: str, new: str, marker: str, name: str, verify: bool, revert: bool) -> int:
    src = path.read_text(encoding="utf-8")
    if revert:
        if marker not in src:
            print(f"  · {name}: already absent"); return 0
        if new not in src:
            print(f"  ✗ {name}: new anchor not found for revert"); return 1
        src = src.replace(new, old, 1)
        if verify: print(f"  ✓ {name}: would revert"); return 0
        path.write_text(src, encoding="utf-8"); print(f"  ✓ {name}: reverted"); return 0
    if marker in src:
        print(f"  · {name}: already present"); return 0
    if old not in src:
        print(f"  ✗ {name}: old anchor not found"); return 1
    src = src.replace(old, new, 1)
    if verify: print(f"  ✓ {name}: would apply"); return 0
    path.write_text(src, encoding="utf-8"); print(f"  ✓ {name}: applied"); return 0


def apply(verify, revert):
    print(f"PCR-044 kickoff/refinement  verify={verify}  revert={revert}")
    order = [
        (GRAPH,   GRAPH_OLD,             GRAPH_NEW,             "PCR-044",                  "ready_agents reads kickoff"),
        (PLANNER, PLANNER_BLUEPRINT_OLD, PLANNER_BLUEPRINT_NEW, "PCR-044 — kickoff vs refinement", "AgentBlueprint fields"),
        (PLANNER, REFINEMENT_DICT_OLD,   REFINEMENT_DICT_NEW,   "ROLE_REFINEMENT_INPUTS",   "refinement dict"),
        (PLANNER, LEAD_OLD,              LEAD_NEW,              "PCR-044 — kickoff inputs",  "Lead Engineer contract"),
        (PLANNER, SELECT_TEAM_OLD,       SELECT_TEAM_NEW,       "PCR-044 — kickoff inputs = ROLE_IO_CONTRACTS", "select_team populates"),
    ]
    if revert:
        order = list(reversed(order))
    rc = 0
    for path, old, new, marker, name in order:
        r = _patch(path, old, new, marker, name, verify, revert)
        if r != 0: rc = r
    return rc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--revert", action="store_true")
    a = ap.parse_args()
    return apply(a.verify, a.revert)


if __name__ == "__main__":
    sys.exit(main())
