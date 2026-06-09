#!/usr/bin/env python3
"""
PCR-034 patcher — wire mind_cycle → auto_fix_matrix → HITL queue.

What this does:
  After every mind cycle, take the entry's proposed_action and pass it
  through auto_fix_matrix.classify(). If the classifier returns a
  classification of HITL_REQUIRED with a proposed_action other than
  'do_nothing', enqueue a HITL item so the founder can review.

Key safety properties verified before this patch was written:
  - auto_fix_matrix.classify() has NO path that returns
    {classification: AUTO_FIX_SAFE, proposed_action: patch_code}.
    "All code changes are HITL by policy" is hardcoded.
  - The only AUTO_FIX_SAFE action returned is 'restart_unit' (reversible).
  - This wiring CANNOT autonomously change code. It can only feed the
    existing HITL queue with mind_cycle proposals.

Dry-run mode (default ON for first 24h):
  Set env var PCR034_DRY_RUN=0 to actually insert into hitl_queue.
  When PCR034_DRY_RUN=1 (default), only logs would-insert intent.

Idempotent, marker-based, --revert capable.
"""

from __future__ import annotations
import argparse
import re
import sys
from pathlib import Path

MIND = Path("/opt/Murphy-System/src/murphy_mind.py")

# Insertion anchor — we add the new function right after _emit_cycle_dlfr's
# def line and add a single call line in _run_cycle after _emit_cycle_dlfr's
# existing call.
ANCHOR_FN_DEF = "def _emit_cycle_dlfr(cycle: int, entry: 'SelfModelEntry', duration_s: float, llm_model: str) -> str:"
ANCHOR_CALL = "_emit_cycle_dlfr(cycle, entry, duration, llm_model)"

MARKER_FN_START = "# PCR-034 BEGIN _emit_cycle_hitl_if_actionable"
MARKER_FN_END = "# PCR-034 END _emit_cycle_hitl_if_actionable"
MARKER_CALL_START = "        # PCR-034 BEGIN HITL-emit"
MARKER_CALL_END = "        # PCR-034 END HITL-emit"

NEW_FN_CODE = '''

# PCR-034 BEGIN _emit_cycle_hitl_if_actionable
def _emit_cycle_hitl_if_actionable(cycle: int, entry: 'SelfModelEntry') -> str:
    """PCR-034: route mind_cycle.proposed_action through auto_fix_matrix
    and enqueue a HITL item if the classifier says action is needed.

    SAFETY: auto_fix_matrix.classify() structurally returns HITL_REQUIRED
    for every patch_code action. This function CANNOT autonomously change
    code. It can only feed the HITL queue.

    Dry-run mode is controlled by PCR034_DRY_RUN env var (default "1" = on).
    Set PCR034_DRY_RUN=0 to actually insert into hitl_queue.

    Best-effort. Failure here MUST NOT break the cycle loop.
    Returns "would_insert:<hitl_id>" / "inserted:<hitl_id>" / "skipped:<reason>"
    """
    import os as _os
    import json as _json
    import sqlite3 as _sqlite3
    import hashlib as _hashlib
    import datetime as _dt

    try:
        proposed = (entry.proposed_action or "").strip()
        if not proposed or proposed.lower() in ("seek_new_gap", "none", ""):
            return "skipped:no_action"

        # Build a flag dict that auto_fix_matrix understands.
        # mind_cycle proposed_actions tend to look like
        # "patch the function partial_status_update in src/dynamic_manifold.py"
        # so we model them as ROUTE_500-style code-change flags.
        proposed_lower = proposed.lower()
        if "patch" in proposed_lower or "fix" in proposed_lower or "modify" in proposed_lower:
            flag_kind = "error_rate"
            flag_id = f"MIND_CYCLE_{cycle}"
        elif "restart" in proposed_lower:
            flag_kind = "error_rate"
            flag_id = f"MIND_CYCLE_RESTART_{cycle}"
        else:
            return "skipped:non_actionable"

        flag = {
            "flag_id": flag_id,
            "kind": flag_kind,
            "severity": "medium",
            "target": (entry.priority_gap or "")[:120],
            "rationale": proposed[:500],
        }

        # Run through auto_fix_matrix
        try:
            from src.auto_fix_matrix import classify
        except Exception as e:
            return f"skipped:matrix_unavailable:{e}"

        verdict = classify(flag)
        action = verdict.get("proposed_action", "do_nothing")
        classification = verdict.get("classification", "HITL_REQUIRED")

        if action == "do_nothing":
            return f"skipped:matrix_do_nothing:{classification}"

        # We have an actionable verdict. Build the HITL item.
        ts = entry.timestamp or _dt.datetime.now(_dt.UTC).isoformat()
        hitl_id_seed = f"mind_cycle_{cycle}_{action}_{flag['target']}"
        hitl_id = "mc_" + _hashlib.sha1(hitl_id_seed.encode()).hexdigest()[:14]

        dry_run = _os.environ.get("PCR034_DRY_RUN", "1") == "1"

        if dry_run:
            # Log only — do not write to hitl_queue
            logger.info(
                "[PCR-034 DRY-RUN] would enqueue HITL: id=%s action=%s "
                "classification=%s target=%s",
                hitl_id, action, classification, flag["target"][:60]
            )
            return f"would_insert:{hitl_id}"

        # Real path — insert into hitl_queue
        DB = "/var/lib/murphy-production/hitl_queue.db"
        try:
            with _sqlite3.connect(DB, timeout=2.0) as conn:
                cur = conn.cursor()
                cur.execute("SELECT 1 FROM hitl_queue WHERE hitl_id = ?", (hitl_id,))
                if cur.fetchone():
                    return f"skipped:exists:{hitl_id}"

                dag_state = {
                    "source": "mind_cycle",
                    "pcr": "PCR-034",
                    "cycle": cycle,
                    "proposed_action": proposed[:500],
                    "priority_gap": (entry.priority_gap or "")[:200],
                    "classification": classification,
                    "matrix_action": action,
                    "reasoning": verdict.get("reasoning", "")[:400],
                }

                intent = f"mind_cycle_{cycle}: {proposed[:160]}"

                cur.execute("""
                    INSERT INTO hitl_queue
                      (hitl_id, dag_id, dag_name, blocked_node_id,
                       blocked_node_name, intent, domain, stake, account,
                       created_at, expires_at, status, dag_state_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    hitl_id,
                    f"mind_cycle_{cycle}",
                    f"MindCycle: {flag['flag_id']}",
                    flag["target"][:60],
                    flag_kind,
                    intent,
                    "mind_cycle",  # NEW LANE
                    "medium",
                    "system",
                    ts,
                    (_dt.datetime.now(_dt.UTC) + _dt.timedelta(hours=48)).isoformat(),
                    "pending",
                    _json.dumps(dag_state),
                ))
                conn.commit()
                logger.info("[PCR-034] enqueued HITL item: %s action=%s",
                            hitl_id, action)
                return f"inserted:{hitl_id}"
        except Exception as e:
            logger.warning("[PCR-034] hitl_queue insert failed: %s", e)
            return f"error:insert_failed:{e}"

    except Exception as e:
        logger.warning("[PCR-034] _emit_cycle_hitl_if_actionable error: %s", e)
        return f"error:{e}"
# PCR-034 END _emit_cycle_hitl_if_actionable

'''

CALL_INSERT = '''        # PCR-034 BEGIN HITL-emit
        try:
            _emit_cycle_hitl_if_actionable(cycle, entry)
        except Exception as _e:
            logger.debug("PCR-034 emit_hitl error (non-fatal): %s", _e)
        # PCR-034 END HITL-emit
'''


def apply(verify: bool, revert: bool):
    print(f"PCR-034 patcher verify={verify} revert={revert}")
    print("=" * 60)

    src = MIND.read_text(encoding="utf-8")

    if revert:
        if MARKER_FN_START not in src and MARKER_CALL_START not in src:
            print("  · already absent")
            return 0
        # Remove the function block
        src = re.sub(
            r"\n*" + re.escape(MARKER_FN_START) + r".*?" + re.escape(MARKER_FN_END) + r"\n*",
            "\n\n", src, flags=re.DOTALL
        )
        # Remove the call block
        src = re.sub(
            re.escape(MARKER_CALL_START) + r".*?" + re.escape(MARKER_CALL_END) + r"\n",
            "", src, flags=re.DOTALL
        )
        if verify:
            print("  ✓ (verify) would remove PCR-034 patches")
            return 0
        MIND.write_text(src, encoding="utf-8")
        print("  ✓ removed PCR-034 patches")
        return 0

    # Apply
    if MARKER_FN_START in src and MARKER_CALL_START in src:
        print("  · already present — no-op")
        return 0

    if ANCHOR_FN_DEF not in src:
        print(f"  ✗ anchor (function def) not found")
        return 1
    if ANCHOR_CALL not in src:
        print(f"  ✗ anchor (call site) not found")
        return 1

    # Insert the new function BEFORE the existing _emit_cycle_dlfr def line
    new_src = src.replace(ANCHOR_FN_DEF, NEW_FN_CODE.lstrip() + "\n" + ANCHOR_FN_DEF, 1)

    # Insert the call line AFTER the existing _emit_cycle_dlfr call
    new_src = new_src.replace(
        "        " + ANCHOR_CALL,
        "        " + ANCHOR_CALL + "\n" + CALL_INSERT.rstrip(),
        1
    )

    if verify:
        print("  ✓ (verify) would insert PCR-034 patches")
        return 0

    MIND.write_text(new_src, encoding="utf-8")
    print("  ✓ inserted PCR-034 patches")
    print(f"  · dry-run default: PCR034_DRY_RUN=1 (set =0 to actually enqueue)")
    print("=" * 60)
    print("  ✓ done")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--revert", action="store_true")
    args = ap.parse_args()
    return apply(verify=args.verify, revert=args.revert)


if __name__ == "__main__":
    sys.exit(main())
