#!/usr/bin/env python3
"""
PCR-045b.1 — fix domain field in accomplishment writes

PROBLEM:
  PCR-045b used a `dir()`-based scope check to grab _packet_040b which
  doesn't exist in that scope (PCR-040b uses _pkt360 instead). Result:
  every accomplishment recorded with domain='general' fallback even
  when planner correctly classified the prompt as 'engineering' or
  'business_strategy'. Cross-domain reuse ranking will misrank.

FIX:
  Reference _pkt360.task_profile.domain (the real planner output, in
  scope at both call sites) and `prompt` (the original input variable).
  No dir() check — just direct references inside the try/except so a
  NameError still falls through to the fail-soft except block.

Both call sites have identical structure differences; this patcher
handles both via two separate marker swaps.
"""

from __future__ import annotations
import argparse
import sys
from pathlib import Path

APP = Path("/opt/Murphy-System/src/runtime/app.py")

# ─── Call site 1 (pass-1) ──────────────────────────────────────────────
PASS1_OLD = '''                                            _record_acc_045b(
                                                profile_id=getattr(_agent_040b, "agent_id", _aid_040b),
                                                role_class=_role_040b,
                                                domain=getattr(_packet_040b.task_profile, "domain", "general") if "_packet_040b" in dir() else "general",
                                                task_prompt=_prompt_040b if "_prompt_040b" in dir() else "",
                                                output_type=_ot_045b,
                                                output_content=(_node_045b.content if _node_045b else None),
                                                success=True,
                                                pass_number=1,
                                                elapsed_us=0,
                                            )'''

PASS1_NEW = '''                                            # PCR-045b.1 — use _pkt360 (the real planner packet in scope)
                                            # and `prompt` (original input). NameError falls through to
                                            # the surrounding except — writer remains fail-soft.
                                            _record_acc_045b(
                                                profile_id=getattr(_agent_040b, "agent_id", _aid_040b),
                                                role_class=_role_040b,
                                                domain=getattr(_pkt360.task_profile, "domain", "general"),
                                                task_prompt=prompt,
                                                output_type=_ot_045b,
                                                output_content=(_node_045b.content if _node_045b else None),
                                                success=True,
                                                pass_number=1,
                                                elapsed_us=0,
                                            )'''

# ─── Call site 2 (refinement) ──────────────────────────────────────────
REFINE_OLD = '''                                            _record_acc_045b_r(
                                                profile_id=getattr(_agent_040c, "agent_id", _aid_040c),
                                                role_class=_role_040c,
                                                domain=getattr(_packet_040b.task_profile, "domain", "general") if "_packet_040b" in dir() else "general",
                                                task_prompt=_prompt_040b if "_prompt_040b" in dir() else "",
                                                output_type=_ot_045b_r,
                                                output_content=(_node_045b_r.content if _node_045b_r else None),
                                                success=True,
                                                pass_number=_current_pass_040c,
                                                elapsed_us=0,
                                            )'''

REFINE_NEW = '''                                            # PCR-045b.1 — same fix on refinement path
                                            _record_acc_045b_r(
                                                profile_id=getattr(_agent_040c, "agent_id", _aid_040c),
                                                role_class=_role_040c,
                                                domain=getattr(_pkt360.task_profile, "domain", "general"),
                                                task_prompt=prompt,
                                                output_type=_ot_045b_r,
                                                output_content=(_node_045b_r.content if _node_045b_r else None),
                                                success=True,
                                                pass_number=_current_pass_040c,
                                                elapsed_us=0,
                                            )'''


def _patch(old, new, marker, name, verify, revert):
    src = APP.read_text(encoding="utf-8")
    if revert:
        if marker not in src:
            print(f"  · {name}: already absent"); return 0
        src = src.replace(new, old, 1)
        if verify: print(f"  ✓ {name}: would revert"); return 0
        APP.write_text(src, encoding="utf-8"); print(f"  ✓ {name}: reverted"); return 0
    if marker in src:
        print(f"  · {name}: already present"); return 0
    if old not in src:
        print(f"  ✗ {name}: old anchor not found"); return 1
    if src.count(old) > 1:
        print(f"  ✗ {name}: {src.count(old)} matches — refusing"); return 1
    src = src.replace(old, new, 1)
    if verify: print(f"  ✓ {name}: would apply"); return 0
    APP.write_text(src, encoding="utf-8"); print(f"  ✓ {name}: applied"); return 0


def apply(verify, revert):
    print(f"PCR-045b.1 domain fix  verify={verify}  revert={revert}")
    steps = [
        (PASS1_OLD, PASS1_NEW, "PCR-045b.1 — use _pkt360",       "pass-1"),
        (REFINE_OLD, REFINE_NEW, "PCR-045b.1 — same fix on refinement", "refinement"),
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
