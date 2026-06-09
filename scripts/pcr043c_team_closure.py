#!/usr/bin/env python3
"""
PCR-043c — team selection by dependency closure, not by headcount

PROBLEM:
  select_team() uses profile.estimated_agents as a hard headcount. For
  trivial complexity that = 1, so only Coordinator is selected. Its inputs
  (analysis_report, schedule) have no producer on the team → graph empty.

FIX (per founder direction):
  Walk the input dependency closure: for every input declared by a
  selected role, if no teammate produces it AND a domain template does,
  add that role. Iterate until closed. Rosetta writes every role needed.
"""

from __future__ import annotations
import argparse
import sys
from pathlib import Path

PLANNER = Path("/opt/Murphy-System/src/dynamic_rosetta_planner.py")

ANCHOR_OLD = """        selected  = regular[:n]
        if profile.requires_hitl and hitl_tmpl:
            if len(selected) < 5:
                selected.append(hitl_tmpl)
            else:
                selected[-1] = hitl_tmpl

        team: List[AgentBlueprint] = []"""

ANCHOR_NEW = """        selected  = regular[:n]
        if profile.requires_hitl and hitl_tmpl:
            if len(selected) < 5:
                selected.append(hitl_tmpl)
            else:
                selected[-1] = hitl_tmpl

        # PCR-043c — dependency-closure team selection.
        # For every input declared by a selected role, if no teammate produces
        # it AND a domain template does, add that role. Iterate until closed.
        # 'prompt' is the user-seed (PCR-043) — skipped from closure pulls.
        # Rosetta writes any role; headcount is a floor, not a ceiling.
        try:
            _SEED_INPUTS_043c = {"prompt"}
            _MAX_PASSES_043c = 6
            _all_by_role_043c = {t[0]: t for t in regular}
            for _pass_043c in range(_MAX_PASSES_043c):
                _team_outputs_043c = set()
                for _tmpl_043c in selected:
                    _r043c = _tmpl_043c[0]
                    _, _outs_043c = ROLE_IO_CONTRACTS.get(_r043c, ([], []))
                    for _o043c in _outs_043c:
                        _team_outputs_043c.add(_o043c)
                _team_outputs_043c |= _SEED_INPUTS_043c
                _missing_043c = set()
                for _tmpl_043c in selected:
                    _r043c = _tmpl_043c[0]
                    _ins_043c, _ = ROLE_IO_CONTRACTS.get(_r043c, ([], []))
                    for _i043c in _ins_043c:
                        if _i043c not in _team_outputs_043c:
                            _missing_043c.add(_i043c)
                if not _missing_043c:
                    break
                _added_043c = False
                for _name_043c, _tup_043c in _all_by_role_043c.items():
                    if any(t[0] == _name_043c for t in selected):
                        continue
                    _, _outs_043c = ROLE_IO_CONTRACTS.get(_name_043c, ([], []))
                    if set(_outs_043c) & _missing_043c:
                        selected.append(_tup_043c)
                        _added_043c = True
                if not _added_043c:
                    break
        except Exception:
            # If closure fails for any reason, fall back to the original
            # headcount-based selection — preserves prior behavior.
            pass

        team: List[AgentBlueprint] = []"""


def apply(verify, revert):
    print(f"PCR-043c team closure  verify={verify}  revert={revert}")
    src = PLANNER.read_text(encoding="utf-8")
    if revert:
        if "PCR-043c" not in src:
            print("  · already absent"); return 0
        src = src.replace(ANCHOR_NEW, ANCHOR_OLD, 1)
        if verify: print("  ✓ would revert"); return 0
        PLANNER.write_text(src, encoding="utf-8")
        print("  ✓ reverted"); return 0
    if "PCR-043c" in src:
        print("  · already present"); return 0
    if ANCHOR_OLD not in src:
        print("  ✗ ANCHOR_OLD not found"); return 1
    src = src.replace(ANCHOR_OLD, ANCHOR_NEW, 1)
    if verify: print("  ✓ would apply"); return 0
    PLANNER.write_text(src, encoding="utf-8")
    print("  ✓ select_team() now walks dependency closure")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--revert", action="store_true")
    a = ap.parse_args()
    return apply(a.verify, a.revert)


if __name__ == "__main__":
    sys.exit(main())
