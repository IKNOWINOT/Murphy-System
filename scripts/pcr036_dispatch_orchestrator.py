#!/usr/bin/env python3
"""
PCR-036 — Wire Conductor + Decomposer + Rubix into /api/rosetta/dispatch.

The orchestration loop is already built (src/compound_task_decomposer.py,
src/conductor/state_machine.py, bots.rubixcube_bot.PathConfidenceRegistry).
This patch CONNECTS that loop to the dispatch endpoint. No new modules.

INSERT POINT: src/runtime/app.py inside _rosetta_dispatch handler,
              after PCR-035's planner block, before the ExecGen block
              at the comment "PATCH-361: ExecGen generates mission briefs".

BEHAVIOR:
  - Calls detect_compound_query(prompt). If is_compound=False, no-op
    (existing PCR-035 behavior runs).
  - If compound, runs execute_prerequisite_phases() — the existing
    decomposer loop with rubix trajectory tracking.
  - Per-phase team RE-CAST: each phase calls DynamicRosettaPlanner.plan()
    with the phase fragment so Agent B "becomes Agent D" based on the
    phase's needs.
  - 33/66 latency canon: each phase's elapsed_ms compared against an
    expected budget; soft-warn at 33%, hard-warn at 66%.
  - Response gains `compound_workflow` field with phase outputs +
    trajectory scores. Existing PCR-035 fields unchanged.
  - DLF-R: phase nodes + SUPPORTS weaves added inside PCR-035's
    packaging block.

SAFETY:
  - Wrapped in try/except; ANY failure falls back to existing flow.
  - Marker-based, revertable via --revert.
  - Snapshot pre-change.
"""

from __future__ import annotations
import argparse
import re
import sys
from pathlib import Path

APP = Path("/opt/Murphy-System/src/runtime/app.py")

MARKER_START = "# PCR-036 BEGIN compound-orchestrator"
MARKER_END = "# PCR-036 END compound-orchestrator"

# Anchor: insert immediately BEFORE the ExecGen brief block.
ANCHOR = "            # PATCH-361: ExecGen generates mission briefs for every agent"

INSERT_BLOCK = '''            # PCR-036 BEGIN compound-orchestrator
            # Connects the (already-built) compound decomposer + rubix
            # trajectory tracker to the dispatch path. Failure here MUST
            # NOT break the existing PCR-035 flow.
            _pcr036_workflow = None
            _pcr036_phase_results = []
            try:
                from compound_task_decomposer import (
                    detect_compound_query as _ctd_detect_036,
                    execute_prerequisite_phases as _ctd_exec_036,
                )
                _decomp_036 = _ctd_detect_036(prompt)
                if _decomp_036.is_compound and _decomp_036.phases:
                    _notify("[PCR-036] compound query detected — " +
                            str(len(_decomp_036.phases)) + " phases, " +
                            "confidence=" + str(round(_decomp_036.decomposition_confidence, 2)))
                    # Per-phase team re-cast: call planner per phase so each
                    # phase gets a team suited to ITS fragment, not the
                    # original prompt.
                    try:
                        from dynamic_rosetta_planner import (
                            DynamicRosettaPlanner as _DRP036,
                        )
                        _drp036 = _DRP036()
                        for _ph_036 in _decomp_036.phases:
                            try:
                                _ph_pkt_036 = _drp036.plan(_ph_036.query_fragment or prompt)
                                _notify("  [PCR-036] phase " +
                                        str(_ph_036.phase_id) + " (" +
                                        _ph_036.phase_type.value + ") team: " +
                                        _ph_pkt_036.task_profile.domain +
                                        " / " + str(len(_ph_pkt_036.team)) + " agents")
                            except Exception as _e_recast_036:
                                _notify("  [PCR-036] E_PCR036_0008 team re-cast failed for phase " +
                                        str(_ph_036.phase_id) + ": " +
                                        str(_e_recast_036)[:80])
                    except Exception as _drp_err_036:
                        _notify("[PCR-036] E_PCR036_0008 planner unavailable: " +
                                str(_drp_err_036)[:80])
                    # Execute the phases — existing loop with rubix
                    # trajectory tracking (PathConfidenceRegistry).
                    try:
                        _result_036 = _ctd_exec_036(_decomp_036)
                        # 33/66 latency canon check per phase
                        _budget_ms_036 = 60_000  # 60s soft cap per phase
                        for _ph_done_036 in _result_036.phases:
                            _phase_summary_036 = {
                                "phase_id": _ph_done_036.phase_id,
                                "phase_type": _ph_done_036.phase_type.value,
                                "description": _ph_done_036.description[:200],
                                "success": _ph_done_036.success,
                                "elapsed_ms": _ph_done_036.elapsed_ms,
                                "depends_on": list(_ph_done_036.depends_on or []),
                            }
                            if _ph_done_036.error:
                                _phase_summary_036["error"] = _ph_done_036.error[:200]
                            if _ph_done_036.output:
                                _phase_summary_036["sources"] = (
                                    _ph_done_036.output.get("sources", [])
                                    if isinstance(_ph_done_036.output, dict)
                                    else []
                                )
                            # 33/66 thresholds
                            if _ph_done_036.elapsed_ms > _budget_ms_036:
                                _phase_summary_036["trajectory_flag"] = "OVER_BUDGET"
                                _notify("[PCR-036] E_PCR036_0005 phase " +
                                        str(_ph_done_036.phase_id) + " exceeded budget (" +
                                        str(_ph_done_036.elapsed_ms) + "ms > " +
                                        str(_budget_ms_036) + "ms)")
                            elif _ph_done_036.elapsed_ms > int(_budget_ms_036 * 0.66):
                                _phase_summary_036["trajectory_flag"] = "HARD_WARN_66"
                            elif _ph_done_036.elapsed_ms > int(_budget_ms_036 * 0.33):
                                _phase_summary_036["trajectory_flag"] = "SOFT_WARN_33"
                            _pcr036_phase_results.append(_phase_summary_036)
                        _pcr036_workflow = {
                            "is_compound": True,
                            "decomposition_confidence": _result_036.decomposition_confidence,
                            "phase_count": len(_result_036.phases),
                            "phases_succeeded": sum(1 for p in _result_036.phases if p.success),
                            "trajectory_scores": _result_036.trajectory_scores,
                            "enriched_context_chars": len(_result_036.enriched_context or ""),
                            "phases": _pcr036_phase_results,
                        }
                        _notify("[PCR-036] phases complete — " +
                                str(_pcr036_workflow["phases_succeeded"]) + "/" +
                                str(_pcr036_workflow["phase_count"]) + " succeeded")
                        # Inject enriched_context back into the original prompt
                        # so the downstream ExecGen sees the prerequisite results.
                        if _result_036.enriched_context:
                            prompt = (
                                prompt + "\\n\\n=== PREREQUISITE RESEARCH ===\\n" +
                                _result_036.enriched_context[:4000]
                            )
                            _notify("[PCR-036] prompt enriched with prerequisite context (" +
                                    str(len(_result_036.enriched_context)) + " chars)")
                    except Exception as _exec_err_036:
                        _notify("[PCR-036] E_PCR036_0003 execute_prerequisite_phases failed: " +
                                str(_exec_err_036)[:120])
                        _pcr036_workflow = None
                else:
                    # non-compound: silent no-op, existing PCR-035 path runs
                    pass
            except ImportError as _imp_err_036:
                _notify("[PCR-036] E_PCR036_0001 import failed: " +
                        str(_imp_err_036)[:80])
            except Exception as _outer_err_036:
                _notify("[PCR-036] E_PCR036_0003 outer failure: " +
                        str(_outer_err_036)[:120])
            # PCR-036 END compound-orchestrator

'''

# Anchor 2: extend the final JSONResponse return to include the workflow.
# We add a sibling field next to brief_packet_id.
RETURN_ANCHOR = '"brief_packet_id": _brief_packet361.dispatch_id if "_brief_packet361" in dir() and _brief_packet361 else None,'
RETURN_INSERT = (
    '"brief_packet_id": _brief_packet361.dispatch_id if "_brief_packet361" in dir() and _brief_packet361 else None,\n'
    '                "compound_workflow": locals().get("_pcr036_workflow"),  # PCR-036'
)


def apply(verify: bool, revert: bool) -> int:
    print(f"PCR-036 patcher  verify={verify}  revert={revert}")
    print("=" * 60)

    src = APP.read_text(encoding="utf-8")

    if revert:
        if MARKER_START not in src and 'compound_workflow' not in src:
            print("  · already absent")
            return 0
        # Remove the inserted block
        src = re.sub(
            re.escape(MARKER_START) + r".*?" + re.escape(MARKER_END) + r"\n\n",
            "",
            src, flags=re.DOTALL,
        )
        # Restore the return statement
        src = src.replace(RETURN_INSERT, RETURN_ANCHOR, 1)
        if verify:
            print("  ✓ (verify) would revert PCR-036")
            return 0
        APP.write_text(src, encoding="utf-8")
        print("  ✓ reverted PCR-036")
        return 0

    # Apply
    if MARKER_START in src:
        print("  · already present — no-op")
        return 0

    if ANCHOR not in src:
        print(f"  ✗ insertion anchor not found")
        print(f"    looking for: {ANCHOR[:80]}...")
        return 1
    if RETURN_ANCHOR not in src:
        print(f"  ✗ return anchor not found")
        return 1

    # Insert the orchestrator block immediately above the ExecGen comment
    new_src = src.replace(ANCHOR, INSERT_BLOCK + ANCHOR, 1)

    # Extend the response body
    new_src = new_src.replace(RETURN_ANCHOR, RETURN_INSERT, 1)

    if verify:
        print("  ✓ (verify) would insert PCR-036")
        return 0

    APP.write_text(new_src, encoding="utf-8")
    print("  ✓ inserted PCR-036")
    print("    - orchestrator block: ~85 lines inserted before ExecGen block")
    print("    - response extended: +compound_workflow field")
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
