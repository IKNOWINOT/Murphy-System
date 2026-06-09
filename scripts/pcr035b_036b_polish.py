#!/usr/bin/env python3
"""
PCR-035b + PCR-036b — Combined polish patch.

PCR-035b: Bump estimated_agents for business_strategy domain.
  Strategy tasks classified as 'medium' currently get only 3 of the 6
  declared role-template agents. Adjust so business_strategy domain
  always uses at least 5 agents (Strategy Lead + Researcher + Finance
  + Architect + Risk), independent of word-count-based complexity.

PCR-036b: Switch elapsed_ms from millisecond floor to perf_counter_ns
  precision. Cached engine returns finish in microseconds and round to
  0 with the current int() cast. Add elapsed_us alongside elapsed_ms
  (preserves backward-compat — both fields populated).

SAFETY:
  Marker-based, revertable. Snapshot first. Two anchor files only:
    - src/dynamic_rosetta_planner.py (PCR-035b: one method touched)
    - src/compound_task_decomposer.py (PCR-036b: timer block + dataclass)
"""

from __future__ import annotations
import argparse
import sys
from pathlib import Path

DRP = Path("/opt/Murphy-System/src/dynamic_rosetta_planner.py")
CTD = Path("/opt/Murphy-System/src/compound_task_decomposer.py")

# ─── PCR-035b: planner — bump team size for business_strategy ────────────
DRP_ANCHOR_OLD = '''            estimated_agents=COMPLEXITY_TO_TEAM_SIZE.get(complexity, 3),
        )'''

DRP_ANCHOR_NEW = '''            estimated_agents=COMPLEXITY_TO_TEAM_SIZE.get(complexity, 3),
        )

    # PCR-035b BEGIN strategy team cap bump

    def _pcr035b_adjust_team_size(self, profile):
        """Bump team size for business_strategy so the full 5-agent
        team (Strategy Lead + Researcher + Finance + Architect + Risk)
        is selected even on 'medium'-complexity prompts."""
        if profile.domain == "business_strategy" and profile.estimated_agents < 5:
            profile.estimated_agents = 5
        return profile
    # PCR-035b END strategy team cap bump'''

# Wire the adjustment into plan() — inject between analyze_task and select_team.
DRP_PLAN_OLD = '''    def plan(self, prompt: str) -> DispatchPacket:
        t0 = time.time()
        team_id = "team_" + uuid.uuid4().hex[:8]
        profile = self.analyze_task(prompt)
        team    = self.select_team(profile, team_id)'''

DRP_PLAN_NEW = '''    def plan(self, prompt: str) -> DispatchPacket:
        t0 = time.time()
        team_id = "team_" + uuid.uuid4().hex[:8]
        profile = self.analyze_task(prompt)
        profile = self._pcr035b_adjust_team_size(profile)  # PCR-035b
        team    = self.select_team(profile, team_id)'''

# ─── PCR-036b: decomposer — ns precision ─────────────────────────────────
# Add elapsed_us field to dataclass
CTD_DATACLASS_OLD = '''    output: Optional[Dict[str, Any]] = None
    success: bool = False
    error: Optional[str] = None
    elapsed_ms: int = 0'''

CTD_DATACLASS_NEW = '''    output: Optional[Dict[str, Any]] = None
    success: bool = False
    error: Optional[str] = None
    elapsed_ms: int = 0
    elapsed_us: int = 0  # PCR-036b: microsecond precision'''

# Update the timer block — success branch
CTD_TIMER_SUCCESS_OLD = '''        start = time.monotonic()
        try:
            phase.output = _run_phase(phase, completed)
            phase.success = True
            phase.elapsed_ms = int((time.monotonic() - start) * 1000)'''

CTD_TIMER_SUCCESS_NEW = '''        start_ns = time.perf_counter_ns()  # PCR-036b
        try:
            phase.output = _run_phase(phase, completed)
            phase.success = True
            _elapsed_ns = time.perf_counter_ns() - start_ns  # PCR-036b
            phase.elapsed_us = _elapsed_ns // 1000
            phase.elapsed_ms = _elapsed_ns // 1_000_000'''

# Update the timer block — failure branch
CTD_TIMER_FAIL_OLD = '''        except Exception as exc:
            phase.elapsed_ms = int((time.monotonic() - start) * 1000)
            phase.error = f"CTD-EXEC-ERR-001: {type(exc).__name__}: {exc}"
            phase.success = False'''

CTD_TIMER_FAIL_NEW = '''        except Exception as exc:
            _elapsed_ns = time.perf_counter_ns() - start_ns  # PCR-036b
            phase.elapsed_us = _elapsed_ns // 1000
            phase.elapsed_ms = _elapsed_ns // 1_000_000
            phase.error = f"CTD-EXEC-ERR-001: {type(exc).__name__}: {exc}"
            phase.success = False'''


def apply(verify: bool, revert: bool) -> int:
    print(f"PCR-035b + PCR-036b patcher  verify={verify}  revert={revert}")
    print("=" * 60)
    drp_src = DRP.read_text(encoding="utf-8")
    ctd_src = CTD.read_text(encoding="utf-8")

    if revert:
        changed = False
        if "PCR-035b BEGIN" in drp_src:
            drp_src = drp_src.replace(DRP_ANCHOR_NEW, DRP_ANCHOR_OLD, 1)
            drp_src = drp_src.replace(DRP_PLAN_NEW, DRP_PLAN_OLD, 1)
            changed = True
        if "PCR-036b" in ctd_src:
            ctd_src = ctd_src.replace(CTD_DATACLASS_NEW, CTD_DATACLASS_OLD, 1)
            ctd_src = ctd_src.replace(CTD_TIMER_SUCCESS_NEW, CTD_TIMER_SUCCESS_OLD, 1)
            ctd_src = ctd_src.replace(CTD_TIMER_FAIL_NEW, CTD_TIMER_FAIL_OLD, 1)
            changed = True
        if not changed:
            print("  · already absent")
            return 0
        if verify:
            print("  ✓ (verify) would revert")
            return 0
        DRP.write_text(drp_src, encoding="utf-8")
        CTD.write_text(ctd_src, encoding="utf-8")
        print("  ✓ reverted")
        return 0

    # Apply
    already_drp = "PCR-035b BEGIN" in drp_src
    already_ctd = "PCR-036b" in ctd_src
    if already_drp and already_ctd:
        print("  · already present")
        return 0

    if not already_drp:
        if DRP_ANCHOR_OLD not in drp_src:
            print("  ✗ PCR-035b anchor (estimated_agents return) not found")
            return 1
        if DRP_PLAN_OLD not in drp_src:
            print("  ✗ PCR-035b anchor (plan method) not found")
            return 1
        drp_src = drp_src.replace(DRP_ANCHOR_OLD, DRP_ANCHOR_NEW, 1)
        drp_src = drp_src.replace(DRP_PLAN_OLD, DRP_PLAN_NEW, 1)

    if not already_ctd:
        if CTD_DATACLASS_OLD not in ctd_src:
            print("  ✗ PCR-036b anchor (dataclass) not found")
            return 1
        if CTD_TIMER_SUCCESS_OLD not in ctd_src:
            print("  ✗ PCR-036b anchor (timer success) not found")
            return 1
        if CTD_TIMER_FAIL_OLD not in ctd_src:
            print("  ✗ PCR-036b anchor (timer fail) not found")
            return 1
        ctd_src = ctd_src.replace(CTD_DATACLASS_OLD, CTD_DATACLASS_NEW, 1)
        ctd_src = ctd_src.replace(CTD_TIMER_SUCCESS_OLD, CTD_TIMER_SUCCESS_NEW, 1)
        ctd_src = ctd_src.replace(CTD_TIMER_FAIL_OLD, CTD_TIMER_FAIL_NEW, 1)

    if verify:
        print("  ✓ (verify) would insert PCR-035b + PCR-036b")
        return 0

    DRP.write_text(drp_src, encoding="utf-8")
    CTD.write_text(ctd_src, encoding="utf-8")
    print("  ✓ inserted PCR-035b + PCR-036b")
    print("    - dynamic_rosetta_planner.py: business_strategy team cap bumped to 5")
    print("    - compound_task_decomposer.py: ns timer + elapsed_us field")
    print("=" * 60)
    print("  ✓ done")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--revert", action="store_true")
    args = ap.parse_args()
    return apply(verify=args.verify, revert=args.revert)


if __name__ == "__main__":
    sys.exit(main())
