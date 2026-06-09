#!/usr/bin/env python3
"""
PCR-045b — wire agent_accomplishment_writer into the two dispatch
success paths (pass-1 fire + refinement fire).

PRE-FLIGHT:
  - The writer module (src/agent_accomplishment_writer.py) is fail-soft:
    any DB error is logged, never raised. So even if PCR-045a is missing
    or the table corrupts, the dispatch loop continues.
  - Both call sites are added INSIDE existing try blocks, so any unusual
    error path also can't break the dispatch.

ANCHORS (both unique strings in app.py):
  1. Pass-1 success — right after `_fired_040b.append(_aid_040b)` and
     the PCR-040b notify line.
  2. Refinement success — right after `_pass_refined_040c.append(_aid_040c)`
     and the PCR-040c notify line.

REVERSIBILITY:
  Marker-based. --verify and --revert supported.
"""

from __future__ import annotations
import argparse
import sys
from pathlib import Path

APP = Path("/opt/Murphy-System/src/runtime/app.py")

# ─── Call site 1: pass-1 success ──────────────────────────────────────
PASS1_OLD = '''                                    _fired_040b.append(_aid_040b)
                                    _notify("  [PCR-040b] " + _role_040b + " produced " + str(_outs_040b))'''

PASS1_NEW = '''                                    _fired_040b.append(_aid_040b)
                                    _notify("  [PCR-040b] " + _role_040b + " produced " + str(_outs_040b))
                                    # PCR-045b — record accomplishment per output (fail-soft)
                                    try:
                                        from agent_accomplishment_writer import record_accomplishment as _record_acc_045b
                                        for _ot_045b in _outs_040b:
                                            _node_045b = _graph_040b.get(_ot_045b)
                                            _record_acc_045b(
                                                profile_id=getattr(_agent_040b, "agent_id", _aid_040b),
                                                role_class=_role_040b,
                                                domain=getattr(_packet_040b.task_profile, "domain", "general") if "_packet_040b" in dir() else "general",
                                                task_prompt=_prompt_040b if "_prompt_040b" in dir() else "",
                                                output_type=_ot_045b,
                                                output_content=(_node_045b.content if _node_045b else None),
                                                success=True,
                                                pass_number=1,
                                                elapsed_us=0,
                                            )
                                    except Exception as _e_acc_045b:
                                        _notify("  [PCR-045b] acc write skipped: " + str(_e_acc_045b)[:80])'''

# ─── Call site 2: refinement success ──────────────────────────────────
REFINE_OLD = '''                                    _pass_refined_040c.append(_aid_040c)
                                    _notify("  [PCR-040c] pass " + str(_current_pass_040c) +
                                            ": " + _role_040c + " revised " + str(_outs_040c))'''

REFINE_NEW = '''                                    _pass_refined_040c.append(_aid_040c)
                                    _notify("  [PCR-040c] pass " + str(_current_pass_040c) +
                                            ": " + _role_040c + " revised " + str(_outs_040c))
                                    # PCR-045b — record refinement accomplishment (fail-soft)
                                    try:
                                        from agent_accomplishment_writer import record_accomplishment as _record_acc_045b_r
                                        for _ot_045b_r in _outs_040c:
                                            _node_045b_r = _graph_040b.get(_ot_045b_r)
                                            _record_acc_045b_r(
                                                profile_id=getattr(_agent_040c, "agent_id", _aid_040c),
                                                role_class=_role_040c,
                                                domain=getattr(_packet_040b.task_profile, "domain", "general") if "_packet_040b" in dir() else "general",
                                                task_prompt=_prompt_040b if "_prompt_040b" in dir() else "",
                                                output_type=_ot_045b_r,
                                                output_content=(_node_045b_r.content if _node_045b_r else None),
                                                success=True,
                                                pass_number=_current_pass_040c,
                                                elapsed_us=0,
                                            )
                                    except Exception as _e_acc_045b_r:
                                        _notify("  [PCR-045b] refine acc write skipped: " + str(_e_acc_045b_r)[:80])'''


def _patch(old: str, new: str, marker: str, name: str, verify: bool, revert: bool) -> int:
    src = APP.read_text(encoding="utf-8")
    if revert:
        if marker not in src:
            print(f"  · {name}: already absent"); return 0
        if new not in src:
            print(f"  ✗ {name}: new anchor not found"); return 1
        src = src.replace(new, old, 1)
        if verify: print(f"  ✓ {name}: would revert"); return 0
        APP.write_text(src, encoding="utf-8"); print(f"  ✓ {name}: reverted"); return 0
    if marker in src:
        print(f"  · {name}: already present"); return 0
    if old not in src:
        print(f"  ✗ {name}: old anchor not found"); return 1
    if src.count(old) > 1:
        print(f"  ✗ {name}: anchor matches {src.count(old)} places — refusing"); return 1
    src = src.replace(old, new, 1)
    if verify: print(f"  ✓ {name}: would apply"); return 0
    APP.write_text(src, encoding="utf-8"); print(f"  ✓ {name}: applied"); return 0


def apply(verify, revert):
    print(f"PCR-045b wire writer  verify={verify}  revert={revert}")
    steps = [
        (PASS1_OLD,  PASS1_NEW,  "PCR-045b — record accomplishment per output",  "pass-1 success"),
        (REFINE_OLD, REFINE_NEW, "PCR-045b — record refinement accomplishment",   "refinement success"),
    ]
    if revert:
        steps = list(reversed(steps))
    rc = 0
    for old, new, marker, name in steps:
        r = _patch(old, new, marker, name, verify, revert)
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
