#!/usr/bin/env python3
"""
bottleneck_monitor.py — PCR-022 / Phase 6a of Final Shape of Complete.

READ-ONLY monitor. Reads three production data sources, computes
bottleneck flags, writes flags to a single output JSON.

This phase does NOT:
  - write to hitl_queue (that's 6b, under HITL approval)
  - attempt any auto-fix (that's 6b)
  - fix /api/auth/verify-email 500 (that's 6b under HITL)

Data sources (canonical, verified before code was written):
  economic_pulse.db / cost_events
    Columns: id, action_type, cost_usd, agent_id, description, ts
    1,436 rows in prod as of 2026-06-08
  entity_graph.db / events
    Columns: id, occurred_at, actor_type, actor_id, action_verb,
             action_object, pipeline, outcome, hitl_decision_id,
             severity, ...
    Hash-chained outcome log
  entity_graph.db / result_provenance
    Columns: result_id, produced_at, produced_by, action_name,
             cost_usd, job_id, tenant_id, ...
    Shipped in PCR-020 / Phase 4a

Flags emitted (each is one finding):
  HIGH_LATENCY_<pipeline>   p95 > 2× p50 for that pipeline in window
  HIGH_ERROR_<pipeline>     >10% outcome != 'ok' in window
  COST_SPIKE_<action_type>  action's avg cost in window > 2× lifetime avg
  ROUTE_500_<path>          (placeholder for 6b; not implemented in 6a)

Output:
  /var/lib/murphy-production/bottleneck_flags.json
  Structure: {
    "generated_at": "ISO timestamp",
    "window_minutes": 60,
    "flags": [ {flag_id, kind, target, severity, evidence, ...}, ... ],
    "stats": { "events_scanned": N, "costs_scanned": N, ... }
  }

Usage:
  python3 -m src.bottleneck_monitor           # run once, write JSON
  python3 -m src.bottleneck_monitor --verify  # just print, don't write
  python3 -m src.bottleneck_monitor --window-minutes 120
"""

from __future__ import annotations
import argparse
import json
import sqlite3
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

# Canonical paths — verified to exist in prod before this module was written
DATA_ROOT = Path("/var/lib/murphy-production")
ECONOMIC_DB = DATA_ROOT / "economic_pulse.db"
ENTITY_DB = DATA_ROOT / "entity_graph.db"
OUTPUT_PATH = DATA_ROOT / "bottleneck_flags.json"

# Thresholds — tuned to be quiet, not noisy
LATENCY_RATIO_THRESHOLD = 2.0   # p95 > 2× p50 → flag
ERROR_RATE_THRESHOLD = 0.10     # >10% non-ok outcomes → flag
COST_SPIKE_RATIO = 2.0          # window avg > 2× lifetime → flag
MIN_SAMPLES = 10                 # don't flag on tiny populations


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _iso_minutes_ago(n: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(minutes=n)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _quantile(sorted_vals: list[float], q: float) -> float:
    """Simple percentile. q in [0,1]."""
    if not sorted_vals:
        return 0.0
    idx = max(0, min(len(sorted_vals) - 1, int(round(q * (len(sorted_vals) - 1)))))
    return float(sorted_vals[idx])


def scan_event_outcomes(window_minutes: int) -> tuple[list[dict], dict]:
    """Read entity_graph.events grouped by pipeline; flag latency + error rate."""
    flags: list[dict] = []
    stats = {"events_scanned": 0, "pipelines_seen": 0}
    if not ENTITY_DB.exists():
        return flags, stats

    cutoff = _iso_minutes_ago(window_minutes)
    try:
        conn = sqlite3.connect(str(ENTITY_DB))
        cur = conn.cursor()
        cur.execute("""SELECT pipeline, outcome, occurred_at
                         FROM events
                        WHERE occurred_at >= ?""", (cutoff,))
        rows = cur.fetchall()
        stats["events_scanned"] = len(rows)
        conn.close()
    except Exception as e:
        return flags, {"error": f"events scan failed: {e}"}

    # Group by pipeline
    by_pipeline: dict[str, list[tuple[str, str]]] = {}
    for pipeline, outcome, occurred_at in rows:
        if not pipeline:
            continue
        by_pipeline.setdefault(pipeline, []).append((outcome or "unknown", occurred_at))

    stats["pipelines_seen"] = len(by_pipeline)

    # Flag error rate
    for pipeline, items in by_pipeline.items():
        if len(items) < MIN_SAMPLES:
            continue
        non_ok = sum(1 for o, _ in items if o not in ("ok", "success", "completed"))
        rate = non_ok / len(items)
        if rate > ERROR_RATE_THRESHOLD:
            flags.append({
                "flag_id": f"HIGH_ERROR_{pipeline}",
                "kind": "error_rate",
                "target": pipeline,
                "severity": "high" if rate > 0.25 else "medium",
                "evidence": {
                    "error_rate": round(rate, 4),
                    "sample_size": len(items),
                    "window_minutes": window_minutes,
                },
                "hitl_required": True,
                "auto_fix_eligible": False,
                "rationale": (f"Pipeline {pipeline} produced {non_ok}/{len(items)} "
                              f"non-ok outcomes in last {window_minutes} min "
                              f"({rate:.1%}). Threshold is {ERROR_RATE_THRESHOLD:.0%}."),
            })

    return flags, stats


# === PCR-026 BEGIN rewired scan_cost_spikes ===
LLM_COST_DB = Path("/var/lib/murphy-production/llm_cost_ledger.db")


def scan_cost_spikes(window_minutes: int) -> tuple[list[dict], dict]:
    """Read llm_cost_ledger.calls (canonical cost ledger per
       vault_and_accounting_canon.md); flag callers whose window
       avg cost > 2x lifetime avg.

       PCR-026: rewired from economic_pulse.cost_events (dead since
       2026-05-12) to llm_cost_ledger.calls (alive, 44k+ rows).
       Field map: caller→action_type, cost_usd→cost_usd, ts→ts."""
    flags: list[dict] = []
    stats = {"costs_scanned": 0, "action_types_seen": 0}
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
        lifetime = {row[0]: (row[1], row[2]) for row in cur.fetchall()
                    if row[0] and row[1] is not None}

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
        return flags, {"error": f"cost scan failed: {e}"}

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
            flags.append({
                "flag_id": f"COST_SPIKE_{action_type}",
                "kind": "cost_spike",
                "target": action_type,
                "severity": "high" if ratio > 3.0 else "medium",
                "evidence": {
                    "window_avg_usd": round(win_avg, 6),
                    "lifetime_avg_usd": round(life_avg, 6),
                    "ratio": round(ratio, 2),
                    "window_sample_size": win_count,
                    "lifetime_sample_size": life_count,
                    "source": "llm_cost_ledger.calls",
                },
            })
    return flags, stats
# === PCR-026 END rewired scan_cost_spikes ===


def scan_provenance_latency(window_minutes: int) -> tuple[list[dict], dict]:
    """Read result_provenance for time-grouped latency.
       Since we don't have explicit duration in the schema yet, this
       phase only counts volume per producer. p95-vs-p50 latency will
       come once produced_at + finished_at are both recorded.
       In 6a we just report volume; we don't flag yet."""
    stats = {"provenance_scanned": 0, "producers_seen": 0}
    if not ENTITY_DB.exists():
        return [], stats
    cutoff = _iso_minutes_ago(window_minutes)
    try:
        conn = sqlite3.connect(str(ENTITY_DB))
        cur = conn.cursor()
        cur.execute("""SELECT produced_by, COUNT(*)
                         FROM result_provenance
                        WHERE produced_at >= ?
                     GROUP BY produced_by""", (cutoff,))
        rows = cur.fetchall()
        stats["provenance_scanned"] = sum(r[1] for r in rows)
        stats["producers_seen"] = len(rows)
        conn.close()
    except Exception as e:
        return [], {"error": f"provenance scan failed: {e}"}
    return [], stats  # 6a: no latency flags emitted yet


def compute_flags(window_minutes: int) -> dict[str, Any]:
    t0 = time.time()
    err_flags, err_stats = scan_event_outcomes(window_minutes)
    cost_flags, cost_stats = scan_cost_spikes(window_minutes)
    prov_flags, prov_stats = scan_provenance_latency(window_minutes)

    all_flags = err_flags + cost_flags + prov_flags
    return {
        "generated_at": _iso_now(),
        "window_minutes": window_minutes,
        "flags": all_flags,
        "flag_count": len(all_flags),
        "stats": {
            "events": err_stats,
            "costs": cost_stats,
            "provenance": prov_stats,
            "scan_duration_ms": int((time.time() - t0) * 1000),
        },
        "phase": "6a (read-only)",
        "schema_version": 1,
    }


def write_output(payload: dict[str, Any]) -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUTPUT_PATH.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    tmp.replace(OUTPUT_PATH)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--window-minutes", type=int, default=60)
    ap.add_argument("--verify", action="store_true",
                    help="print flags but don't write the output file")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    payload = compute_flags(args.window_minutes)

    if not args.quiet:
        print(f"Bottleneck monitor — {payload['generated_at']}")
        print(f"  window: {payload['window_minutes']} min")
        print(f"  flags: {payload['flag_count']}")
        print(f"  stats: {json.dumps(payload['stats'], default=str)}")
        for f in payload["flags"]:
            print(f"  • [{f['severity'].upper()}] {f['flag_id']}: {f['rationale']}")

    if not args.verify:
        write_output(payload)
        if not args.quiet:
            print(f"  → wrote {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
