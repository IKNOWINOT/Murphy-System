#!/usr/bin/env python3
"""
PCR-045c — persistent-agent reuse layer

THE PAYOFF PCR. Closes the loop:
  fire → record accomplishment (045b) → consult on next dispatch (045c)

FOUNDER DIRECTION (2026-06-09 00:10 PT):
  "All of these agents become a saved on what they accomplished and
   re utilized when they are useable for other tasks."

ASK-MURPHY-FIRST FINDINGS:
  - employ_team() in agent_employment_bridge.py is only called by R603
    pilot + module __main__. The dispatch path uses select_team()
    directly.
  - AgentBlueprint.agent_id is ephemeral: slug + random uid per dispatch.
    Different runs of "Lead Engineer" get different ids.
  - 045b records profile_id = agent.agent_id, so the table currently
    has each dispatch's instance as a "new" agent.

ARCHITECTURE:
  Two-layer identity (option C, as memory.md notes):
    agent_id        — ephemeral per-dispatch (existing, unchanged)
    persistent_id   — stable per (role_class, domain) — NEW

  AgentBlueprint gains:
    persistent_id: str
    prior_accomplishments_count: int = 0
    prior_keyword_overlap: int = 0

  select_team() does:
    For each role about to be built:
      1. Compute persistent_id from (role_class, domain) hash
      2. Call find_reusable_agents(role_class, prompt) — cross-domain
      3. If best candidate has success_count >= 1, attach its
         persistent_id and accomplishment stats to the blueprint
      4. Otherwise use the freshly-computed persistent_id (first time
         this (role, domain) combo runs — establishes the identity)

  045b writes will now go to a STABLE persistent_id for repeated
  invocations of the same (role, domain). Accomplishments accumulate.

  Dispatch logic is UNCHANGED for now. Reuse signal is captured in
  the blueprint but doesn't yet inject prior soul content. That's a
  cleaner separate PCR (045d) once we have receipts.

NEW CALL SITE in app.py:
  After select_team() returns, before agents fire, the 045b writer
  needs to record under blueprint.persistent_id (not agent_id).
  Done via marker-patch on the existing 045b call sites — swap the
  profile_id source from agent_id to persistent_id, with fallback.
"""

from __future__ import annotations
import argparse
import sys
from pathlib import Path

PLANNER = Path("/opt/Murphy-System/src/dynamic_rosetta_planner.py")
APP     = Path("/opt/Murphy-System/src/runtime/app.py")

# ─── Patch 1: AgentBlueprint gains 3 new fields ────────────────────────
BP_OLD = '''    # PCR-044 — kickoff vs refinement input separation. When kickoff_inputs
    # is set, ready_agents() uses it for pass 1; refinement_inputs are
    # consumed via ready_for_refinement() in pass 2+. Backward compatible:
    # leaving kickoff_inputs empty falls back to input_types.
    kickoff_inputs: List[str] = field(default_factory=list)
    refinement_inputs: List[str] = field(default_factory=list)'''

BP_NEW = '''    # PCR-044 — kickoff vs refinement input separation. When kickoff_inputs
    # is set, ready_agents() uses it for pass 1; refinement_inputs are
    # consumed via ready_for_refinement() in pass 2+. Backward compatible:
    # leaving kickoff_inputs empty falls back to input_types.
    kickoff_inputs: List[str] = field(default_factory=list)
    refinement_inputs: List[str] = field(default_factory=list)
    # PCR-045c — persistent identity layer. persistent_id is stable
    # across dispatches for a (role_class, domain) combination; agent_id
    # stays ephemeral for per-run tracing. Accomplishments accumulate
    # under persistent_id so reuse signal grows over time.
    persistent_id: str = ""
    prior_accomplishments_count: int = 0
    prior_keyword_overlap: int = 0'''

# ─── Patch 2: select_team consults find_reusable_agents ───────────────
ST_OLD = '''            # PCR-040a — pull I/O contract for this role (empty default)
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

ST_NEW = '''            # PCR-040a — pull I/O contract for this role (empty default)
            _io_in, _io_out = ROLE_IO_CONTRACTS.get(role_class, ([], []))
            # PCR-044 — kickoff inputs = ROLE_IO_CONTRACTS (pass 1 prereqs).
            # refinement_inputs come from ROLE_REFINEMENT_INPUTS (pass 2+).
            _refine_in = ROLE_REFINEMENT_INPUTS.get(role_class, [])
            _all_inputs = list(_io_in) + [x for x in _refine_in if x not in _io_in]
            # PCR-045c — persistent identity + reuse lookup. Stable id from
            # (role_class, domain); existing accomplishments rank candidates
            # cross-domain. Fail-soft: if the lookup or DB hiccups, use the
            # freshly-computed persistent_id with zero priors.
            _persistent_id_045c = (
                role_class.lower().replace(" ", "_") + "_" +
                (profile.domain or "general")
            )
            _prior_count_045c = 0
            _prior_overlap_045c = 0
            try:
                from agent_accomplishment_writer import find_reusable_agents as _fra_045c
                _candidates_045c = _fra_045c(
                    role_class=role_class,
                    task_prompt=brief or "",
                    limit=1,
                    min_success_count=1,
                )
                if _candidates_045c:
                    _best_045c = _candidates_045c[0]
                    _persistent_id_045c = _best_045c["profile_id"]
                    _prior_count_045c = _best_045c.get("success_count", 0)
                    _prior_overlap_045c = _best_045c.get("keyword_overlap", 0)
            except Exception:
                pass  # fail-soft: stay with freshly-computed persistent_id
            team.append(AgentBlueprint(
                agent_id=agent_id, role_class=role_class, department=dept,
                reports_to=coordinator_id if not is_coord else None,
                tone=tone, bias=bias, hitl_threshold=hitl_thresh,
                capabilities=caps, boundaries=bounds,
                task_brief=brief, emoji=emoji,
                input_types=_all_inputs, output_types=list(_io_out),
                kickoff_inputs=list(_io_in),
                refinement_inputs=list(_refine_in),
                persistent_id=_persistent_id_045c,
                prior_accomplishments_count=_prior_count_045c,
                prior_keyword_overlap=_prior_overlap_045c,
            ))'''

# ─── Patch 3: 045b call sites now record under persistent_id ──────────
ACC_PASS1_OLD = '''                                            _record_acc_045b(
                                                profile_id=getattr(_agent_040b, "agent_id", _aid_040b),
                                                role_class=_role_040b,'''

ACC_PASS1_NEW = '''                                            _record_acc_045b(
                                                # PCR-045c — record under persistent_id so accomplishments
                                                # accumulate across dispatches for same (role, domain).
                                                # Falls back to agent_id if blueprint is missing the field
                                                # (e.g. on a stale running team during deploy).
                                                profile_id=getattr(_agent_040b, "persistent_id", None) or getattr(_agent_040b, "agent_id", _aid_040b),
                                                role_class=_role_040b,'''

ACC_REFINE_OLD = '''                                            _record_acc_045b_r(
                                                profile_id=getattr(_agent_040c, "agent_id", _aid_040c),
                                                role_class=_role_040c,'''

ACC_REFINE_NEW = '''                                            _record_acc_045b_r(
                                                # PCR-045c — record under persistent_id (same as pass-1 path)
                                                profile_id=getattr(_agent_040c, "persistent_id", None) or getattr(_agent_040c, "agent_id", _aid_040c),
                                                role_class=_role_040c,'''


def _patch(path: Path, old: str, new: str, marker: str, name: str, verify, revert):
    src = path.read_text(encoding="utf-8")
    if revert:
        if marker not in src:
            print(f"  · {name}: already absent"); return 0
        if new not in src:
            print(f"  ✗ {name}: new anchor not found"); return 1
        src = src.replace(new, old, 1)
        if verify: print(f"  ✓ {name}: would revert"); return 0
        path.write_text(src, encoding="utf-8"); print(f"  ✓ {name}: reverted"); return 0
    if marker in src:
        print(f"  · {name}: already present"); return 0
    if old not in src:
        print(f"  ✗ {name}: old anchor not found"); return 1
    if src.count(old) > 1:
        print(f"  ✗ {name}: anchor matches {src.count(old)} places — refusing"); return 1
    src = src.replace(old, new, 1)
    if verify: print(f"  ✓ {name}: would apply"); return 0
    path.write_text(src, encoding="utf-8"); print(f"  ✓ {name}: applied"); return 0


def apply(verify, revert):
    print(f"PCR-045c reuse layer  verify={verify}  revert={revert}")
    steps = [
        (PLANNER, BP_OLD,         BP_NEW,         "PCR-045c — persistent identity layer", "AgentBlueprint fields"),
        (PLANNER, ST_OLD,         ST_NEW,         "PCR-045c — persistent identity + reuse lookup", "select_team reuse lookup"),
        (APP,     ACC_PASS1_OLD,  ACC_PASS1_NEW,  "PCR-045c — record under persistent_id so accomplishments", "045b pass-1 → persistent_id"),
        (APP,     ACC_REFINE_OLD, ACC_REFINE_NEW, "PCR-045c — record under persistent_id (same as pass-1 path)", "045b refine → persistent_id"),
    ]
    if revert:
        steps = list(reversed(steps))
    rc = 0
    for path, old, new, marker, name in steps:
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
