#!/usr/bin/env python3
"""
pcr027_patch_latency_v2.py — PCR-027 / Phase 9 patcher v2.

Promotes scan_provenance_latency() from "count volume only" (Phase 6a
stub) to "compute p95/p50 + emit HIGH_LATENCY flags."

The orchestrator (compute_flags) already calls this function — no
invocation change needed. We just replace the function body.

Strategy (L35-safe):
  - Replace whole function in place, anchored on def signature.
  - Idempotent via marker (PCR-027 BEGIN).
  - --revert removes the new block; restore from snapshot for the
    original behavior.
"""

from __future__ import annotations
import argparse
import re
import sys
from pathlib import Path

TARGET = Path("/opt/Murphy-System/src/bottleneck_monitor.py")

MARKER_BEGIN = "# === PCR-027 BEGIN scan_provenance_latency p95 ==="
MARKER_END   = "# === PCR-027 END scan_provenance_latency p95 ==="

NEW_FUNCTION = f'''
{MARKER_BEGIN}
def _parse_latency_ms(output_summary: str) -> int:
    """Parse latency_ms from PCR-025 output_summary format:
       'HTTP 200 · 14ms · 8046b'. Returns -1 on parse failure."""
    if not output_summary:
        return -1
    try:
        import re as _re
        m = _re.search(r"\\b(\\d+)ms\\b", output_summary)
        return int(m.group(1)) if m else -1
    except Exception:
        return -1


def scan_provenance_latency(window_minutes: int) -> tuple[list[dict], dict]:
    """Read result_provenance for action-level p95 vs p50 latency.
       PCR-027: now parses latency_ms from PCR-025's output_summary
       and emits HIGH_LATENCY_<action> flags when p95 > 2x p50."""
    stats = {{"provenance_scanned": 0, "producers_seen": 0,
             "actions_with_samples": 0}}
    flags: list[dict] = []
    if not ENTITY_DB.exists():
        return flags, stats
    cutoff = _iso_minutes_ago(window_minutes)
    try:
        conn = sqlite3.connect(str(ENTITY_DB))
        cur = conn.cursor()
        # Volume per producer (preserves Phase 6a stats shape)
        cur.execute("""SELECT produced_by, COUNT(*)
                         FROM result_provenance
                        WHERE produced_at >= ?
                     GROUP BY produced_by""", (cutoff,))
        producer_rows = cur.fetchall()
        stats["provenance_scanned"] = sum(r[1] for r in producer_rows)
        stats["producers_seen"] = len(producer_rows)

        # Latency per action_name (the new PCR-027 logic)
        cur.execute("""SELECT action_name, output_summary
                         FROM result_provenance
                        WHERE produced_at >= ?""", (cutoff,))
        rows = cur.fetchall()
        conn.close()
    except Exception as e:
        return flags, {{"error": f"provenance scan failed: {{e}}"}}

    by_action: dict[str, list[int]] = {{}}
    for action_name, output_summary in rows:
        ms = _parse_latency_ms(output_summary)
        if ms < 0 or not action_name:
            continue
        by_action.setdefault(action_name, []).append(ms)

    for action_name, latencies in by_action.items():
        n = len(latencies)
        if n < MIN_SAMPLES:
            continue
        stats["actions_with_samples"] += 1
        sorted_ms = sorted(latencies)
        p50 = sorted_ms[n // 2]
        p95 = sorted_ms[max(0, int(n * 0.95) - 1)]
        if p50 <= 0:
            continue
        ratio = p95 / p50
        if ratio > LATENCY_RATIO_THRESHOLD:
            flags.append({{
                "flag_id": f"HIGH_LATENCY_{{action_name}}",
                "kind": "high_latency",
                "target": action_name,
                "severity": "high" if ratio > 4.0 else "medium",
                "evidence": {{
                    "p50_ms": p50,
                    "p95_ms": p95,
                    "ratio": round(ratio, 2),
                    "sample_size": n,
                    "source": "result_provenance",
                }},
            }})
    return flags, stats
{MARKER_END}
'''


def apply_patch(verify=False, revert=False):
    text = TARGET.read_text(encoding="utf-8")
    has = MARKER_BEGIN in text
    if verify:
        return has, ("  ✓ scan_provenance_latency promoted to p95/p50" if has
                     else "  ✗ scan_provenance_latency NOT promoted")
    if revert:
        if not has:
            return True, "  · nothing to revert"
        pat = re.compile(re.escape(MARKER_BEGIN) + r".*?" +
                         re.escape(MARKER_END) + r"\n?", re.DOTALL)
        text = pat.sub("", text)
        TARGET.write_text(text, encoding="utf-8")
        return True, ("  ✓ removed PCR-027 block (restore original from "
                      "snapshot if needed)")
    if has:
        return True, "  · already patched (idempotent)"

    # Anchor: replace the whole existing scan_provenance_latency function.
    # Match from "def scan_provenance_latency" until the next top-level
    # def (line starting with "def " at column 0, no indent).
    pattern = re.compile(
        r"def scan_provenance_latency\(window_minutes: int\) -> tuple\[list\[dict\], dict\]:.*?(?=\n\ndef |\Z)",
        re.DOTALL
    )
    m = pattern.search(text)
    if not m:
        return False, "  ✗ scan_provenance_latency function not found"
    text = text[:m.start()] + NEW_FUNCTION.strip() + "\n" + text[m.end():]
    TARGET.write_text(text, encoding="utf-8")
    return True, "  ✓ replaced scan_provenance_latency with p95/p50 logic"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--revert", action="store_true")
    args = ap.parse_args()
    print(f"PCR-027 patcher v2 verify={args.verify} revert={args.revert}")
    print("=" * 60)
    ok, msg = apply_patch(verify=args.verify, revert=args.revert)
    print(msg)
    print("=" * 60)
    print("  ✓ done" if ok else "  ✗ failed")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
