#!/usr/bin/env python3
"""
PCR-044 — fix engineering domain circular dependency

DIAGNOSIS (PCR-043c smoke test):
  All 11 domains audited for executable order via topological walk.
  10 clean, 1 deadlocked: engineering.

  Lead Engineer    inputs:  [prompt, test_plan, security_audit]
                   outputs: [architecture_decision, deliverable]
  Code Executor    inputs:  [prompt, architecture_decision]
                   outputs: [patch_set]
  QA Auditor       inputs:  [patch_set]
                   outputs: [test_plan, regression_report]
  Security Reviewer inputs: [patch_set]
                   outputs: [security_audit]

  Lead waits for test_plan + security_audit → QA + Security wait for
  patch_set → Code Executor waits for architecture_decision → Lead.
  Perfect deadlock. Nothing ever fires.

FIX (per founder direction — utilize Rosetta's full role-writing power):
  Lead Engineer is the architect — the KICKOFF role. It should fire on
  the prompt alone. test_plan and security_audit are downstream feedback
  signals, not prerequisites for the initial architecture.

  Change Lead Engineer inputs:
    [prompt, test_plan, security_audit]   →   [prompt]

  After Lead emits architecture_decision, Code Executor fires, then QA
  + Security run in parallel. If multi-pass refinement is enabled (PCR-040c
  PCR040C_MAX_PASSES > 1), Lead can fire again in pass 2 with test_plan
  and security_audit available — the feedback loop becomes a refinement
  loop, not a deadlock.

  Same model as exec_admin Coordinator (PCR-043c smoke test showed Coord
  fires LAST after Analyst + Scheduler — exactly the right kickoff vs
  finalize pattern).

VERIFICATION:
  After patch, topological walk for engineering must fire all 4 roles in
  order: Lead Engineer → Code Executor → QA Auditor + Security Reviewer.

REVERSIBILITY:
  Marker-based on the single line containing Lead Engineer's input list.
"""

from __future__ import annotations
import argparse
import sys
from pathlib import Path

PLANNER = Path("/opt/Murphy-System/src/dynamic_rosetta_planner.py")

ANCHOR_OLD = '''    "Lead Engineer": (
        ["prompt", "test_plan", "security_audit"],
        ["architecture_decision", "deliverable"],
    ),'''

ANCHOR_NEW = '''    "Lead Engineer": (
        # PCR-044 — Lead is the kickoff architect, fires on prompt alone.
        # test_plan and security_audit are downstream feedback consumed in
        # refinement passes (PCR-040c), not first-pass prerequisites.
        ["prompt"],
        ["architecture_decision", "deliverable"],
    ),'''


def apply(verify, revert):
    print(f"PCR-044 engineering DAG  verify={verify}  revert={revert}")
    src = PLANNER.read_text(encoding="utf-8")
    if revert:
        if "PCR-044" not in src:
            print("  · already absent"); return 0
        src = src.replace(ANCHOR_NEW, ANCHOR_OLD, 1)
        if verify: print("  ✓ would revert"); return 0
        PLANNER.write_text(src, encoding="utf-8")
        print("  ✓ reverted"); return 0
    if "PCR-044" in src:
        print("  · already present"); return 0
    if ANCHOR_OLD not in src:
        print("  ✗ ANCHOR_OLD not found"); return 1
    src = src.replace(ANCHOR_OLD, ANCHOR_NEW, 1)
    if verify: print("  ✓ would apply"); return 0
    PLANNER.write_text(src, encoding="utf-8")
    print("  ✓ Lead Engineer now fires on prompt alone")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--revert", action="store_true")
    a = ap.parse_args()
    return apply(a.verify, a.revert)


if __name__ == "__main__":
    sys.exit(main())
