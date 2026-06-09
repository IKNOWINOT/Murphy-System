#!/usr/bin/env python3
"""
pcr026_patch_monitor.py — PCR-026 / Phase 8 patcher.

Rewires bottleneck_monitor.scan_cost_spikes() to read the canonical
llm_cost_ledger.calls table (alive, 44k+ rows, currently writing)
instead of economic_pulse.cost_events (dead since 2026-05-12).

Strategy (L35-safe):
  - Replace scan_cost_spikes() function body in-place, anchored on
    the unique docstring + signature.
  - Idempotent via marker.
  - Field map:
      cost_events.action_type → calls.caller
      cost_events.cost_usd    → calls.cost_usd  (same)
      cost_events.ts          → calls.ts        (same)
  - Schema honors canon: llm_cost_ledger.calls is the canonical
    cost ledger per vault_and_accounting_canon.md.
"""

from __future__ import annotations
import argparse
import re
import sys
from pathlib import Path

TARGET = Path("/opt/Murphy-System/src/bottleneck_monitor.py")

MARKER_BEGIN = "# === PCR-026 BEGIN rewired scan_cost_spikes ==="
MARKER_END   = "# === PCR-026 END rewired scan_cost_spikes ==="

NEW_FUNCTION = f'''
{MARKER_BEGIN}
LLM_COST_DB = Path("/var/lib/murphy-production/llm_cost_ledger.db")


def scan_cost_spikes(window_minutes: int) -> tuple[list[dict], dict]:
    """Read llm_cost_ledger.calls (canonical cost ledger per
       vault_and_accounting_canon.md); flag callers whose window
       avg cost > 2x lifetime avg.

       PCR-026: rewired from economic_pulse.cost_events (dead since
       2026-05-12) to llm_cost_ledger.calls (alive, 44k+ rows).
       Field map: caller→action_type, cost_usd→cost_usd, ts→ts."""
    flags: list[dict] = []
    stats = {{"costs_scanned": 0, "action_types_seen": 0}}
    if not LLM_COST_DB.exists():
        return flags, stats

    cutoff = _iso_minutes_ago(window_minutes)
    try:
        conn = sqlite3.connect(str(LLM_COST_DB))
        cur = conn.cursor()

        # Lifetime average per caller (excluding the recent window
        # to avoid contamination)
        cur.execute("""SELECT caller, AVG(cost_usd), COUNT(*)
                         FROM calls
                        WHERE ts < ?
                          AND cost_usd > 0
                          AND caller IS NOT NULL
                     GROUP BY caller""", (cutoff,))
        lifetime = {{row[0]: (row[1], row[2]) for row in cur.fetchall()
                    if row[0] and row[1] is not None}}

        # Window average per caller
        cur.execute("""SELECT caller, AVG(cost_usd), COUNT(*)
                         FROM calls
                        WHERE ts >= ?
                          AND cost_usd > 0
                          AND caller IS NOT NULL
                     GROUP BY caller""", (cutoff,))
        window_rows = cur.fetchall()
        stats["costs_scanned"] = sum(r[2] for r in window_rows)
        stats["action_types_seen"] = len(window_rows)
        conn.close()
    except Exception as e:
        return flags, {{"error": f"cost scan failed: {{e}}"}}

    for action_type, win_avg, win_count in window_rows:
        if not action_type or win_count < MIN_SAMPLES // 2:
            continue
        life = lifetime.get(action_type)
        if not life or life[0] <= 0:
            continue
        life_avg, life_count = life
        if life_count < MIN_SAMPLES:
            continue
        ratio = win_avg / life_avg
        if ratio > COST_SPIKE_RATIO:
            flags.append({{
                "flag_id": f"COST_SPIKE_{{action_type}}",
                "kind": "cost_spike",
                "target": action_type,
                "severity": "high" if ratio > 3.0 else "medium",
                "evidence": {{
                    "window_avg_usd": round(win_avg, 6),
                    "lifetime_avg_usd": round(life_avg, 6),
                    "ratio": round(ratio, 2),
                    "window_sample_size": win_count,
                    "lifetime_sample_size": life_count,
                    "source": "llm_cost_ledger.calls",
                }},
            }})
    return flags, stats
{MARKER_END}
'''


def apply_patch(verify=False, revert=False):
    text = TARGET.read_text(encoding="utf-8")
    has = MARKER_BEGIN in text
    if verify:
        return has, ("  ✓ scan_cost_spikes rewired to llm_cost_ledger" if has
                     else "  ✗ scan_cost_spikes NOT rewired")
    if revert:
        if not has:
            return True, "  · nothing to revert"
        # Remove our block (everything between markers)
        pat = re.compile(re.escape(MARKER_BEGIN) + r".*?" +
                         re.escape(MARKER_END) + r"\n?", re.DOTALL)
        text = pat.sub("", text)
        # Note: revert doesn't restore the original function — use snapshot
        TARGET.write_text(text, encoding="utf-8")
        return True, "  ✓ removed PCR-026 block (restore from snapshot)"
    if has:
        return True, "  · already patched (idempotent)"

    # Anchor on the existing scan_cost_spikes definition. Replace the
    # whole function with our marker block.
    pattern = re.compile(
        r"def scan_cost_spikes\(window_minutes: int\) -> tuple\[list\[dict\], dict\]:.*?(?=\n\ndef |\nif __name__|\Z)",
        re.DOTALL
    )
    m = pattern.search(text)
    if not m:
        return False, "  ✗ scan_cost_spikes function not found"
    # Replace the matched function with our new block
    text = text[:m.start()] + NEW_FUNCTION.strip() + "\n" + text[m.end():]
    TARGET.write_text(text, encoding="utf-8")
    return True, "  ✓ replaced scan_cost_spikes (now reads llm_cost_ledger)"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--revert", action="store_true")
    args = ap.parse_args()
    print(f"PCR-026 patcher verify={args.verify} revert={args.revert}")
    print("=" * 60)
    ok, msg = apply_patch(verify=args.verify, revert=args.revert)
    print(msg)
    print("=" * 60)
    print("  ✓ done" if ok else "  ✗ failed")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
