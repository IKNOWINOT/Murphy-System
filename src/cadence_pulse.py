"""
cadence_pulse.py — Pulse query layer (delegates to BLOCK-A.4.1 + A.2.5)
=======================================================================

WHAT THIS IS:
  The query/aggregation layer for Murphy's pulse system. Reads the
  REAL data sources that already exist:
  - cadence_registry in murphy_registry.db (source catalog, BLOCK-A.2.5)
  - pulse_ticks in cadence_pulse.db (tick log, BLOCK-A.4.1)

WHY IT EXISTS:
  /api/pulse/current and /api/pulse/health endpoints need a unified
  read shape across both DBs. Writes are handled by cadence_emit
  (BLOCK-A.4.1) — this module is read-only aggregation.

DO NOT TOUCH:
  emit_heartbeat lives in src.cadence_emit (BLOCK-A.4.1). DO NOT re-
  implement it here. This module is READ-ONLY by design.

LAST UPDATED: 2026-05-26 (consolidation pass — removed duplicate write path)
"""

from __future__ import annotations
import sqlite3
import logging
import statistics
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

logger = logging.getLogger("murphy.cadence_pulse")

REGISTRY_DB = "/var/lib/murphy-production/murphy_registry.db"
TICKS_DB    = "/var/lib/murphy-production/cadence_pulse.db"


# ── Re-export the canonical emit helper so callers don't get confused ────────
try:
    from src.cadence_emit import emit_heartbeat  # canonical writer
except ImportError:
    logger.warning("cadence_emit not importable — emit_heartbeat unavailable")
    def emit_heartbeat(*args, **kwargs):
        return False


def get_pulse_summary(since_minutes: int = 15) -> Dict[str, Any]:
    """
    Read every active cadence source from cadence_registry, join with
    last tick from pulse_ticks, return unified shape.

    Returns:
      {
        "color": "green|yellow|red",
        "reasons": [str],
        "sources": [{
            source, display_name, source_type, tier, interval_s,
            last_tick_at, drift_seconds, status (ok|stale|silent|never_seen),
            consecutive_failures, total_ticks,
        }],
        "total": int,
        "window_minutes": int,
      }
    """
    sources_info: List[Dict[str, Any]] = []
    try:
        rconn = sqlite3.connect(REGISTRY_DB, timeout=3)
        rconn.row_factory = sqlite3.Row
        rows = rconn.execute(
            """SELECT source_name, display_name, source_type, interval_s,
                      tier, health_status, consecutive_failures, total_ticks,
                      last_tick_at, last_success
               FROM cadence_registry
               WHERE enabled = 1 AND lifecycle = 'active'
               ORDER BY interval_s ASC"""
        ).fetchall()
        rconn.close()

        now = datetime.now(timezone.utc)

        for r in rows:
            src         = r["source_name"]
            interval_s  = r["interval_s"] or 0
            last_iso    = r["last_tick_at"]
            drift_s     = None
            if last_iso:
                try:
                    last_dt = datetime.fromisoformat(last_iso.replace("Z","+00:00"))
                    drift_s = (now - last_dt).total_seconds()
                except Exception:
                    drift_s = None
            # Derive status
            if drift_s is None:
                status = "never_seen"
            elif interval_s <= 0:
                status = "ok"  # event-driven, no expected interval
            elif drift_s < 1.5 * interval_s:
                status = "ok"
            elif drift_s < 3 * interval_s:
                status = "stale"
            else:
                status = "silent"
            sources_info.append({
                "source":               src,
                "display_name":         r["display_name"],
                "source_type":          r["source_type"],
                "tier":                 r["tier"],
                "interval_s":           interval_s,
                "last_tick_at":         last_iso,
                "drift_seconds":        round(drift_s, 1) if drift_s is not None else None,
                "status":               status,
                "consecutive_failures": r["consecutive_failures"] or 0,
                "total_ticks":          r["total_ticks"] or 0,
                "last_success":         bool(r["last_success"]) if r["last_success"] is not None else None,
            })
    except Exception as exc:
        logger.warning("get_pulse_summary registry read failed: %s", exc)
        return {"color":"red", "reasons":[f"registry_db_error: {exc}"],
                "sources":[], "total":0, "window_minutes":since_minutes}

    # Roll up overall color
    statuses = [s["status"] for s in sources_info]
    operational_sources = [s for s in sources_info if s["tier"] == "operational"]
    if any(s["status"] in ("silent","never_seen") for s in operational_sources):
        color = "red"
    elif any(s["status"] == "stale" for s in operational_sources):
        color = "yellow"
    elif "silent" in statuses or "never_seen" in statuses:
        color = "yellow"  # non-operational silent is just yellow
    elif "stale" in statuses:
        color = "yellow"
    else:
        color = "green"

    reasons = [
        f"{s['source']}: {s['status']} (drift {s['drift_seconds']}s / interval {s['interval_s']}s)"
        for s in sources_info if s["status"] != "ok"
    ]

    return {
        "color":          color,
        "reasons":        reasons,
        "sources":        sources_info,
        "total":          len(sources_info),
        "window_minutes": since_minutes,
    }


def score_alignment(source: str,
                     expected_interval_s: int,
                     recent_beats: List[float]) -> Dict[str, Any]:
    """Score how well a source's actual cadence matches expected interval."""
    if len(recent_beats) < 2:
        return {"source": source, "alignment": 0.0, "median_actual_s": None,
                "expected_s": expected_interval_s, "variance": None,
                "verdict": "insufficient_data"}
    intervals = [recent_beats[i] - recent_beats[i-1] for i in range(1, len(recent_beats))]
    median_actual = statistics.median(intervals)
    variance = statistics.stdev(intervals) if len(intervals) > 1 else 0.0
    if expected_interval_s > 0:
        alignment = max(0.0, 1.0 - abs(median_actual - expected_interval_s) / expected_interval_s)
    else:
        alignment = 0.0
    verdict = "aligned" if alignment > 0.85 else ("drifting" if alignment >= 0.5 else "broken")
    return {"source": source, "alignment": round(alignment, 3),
            "median_actual_s": round(median_actual, 1),
            "expected_s": expected_interval_s,
            "variance": round(variance, 1), "verdict": verdict}


def get_recent_beats(source: str, since_minutes: int = 60) -> List[float]:
    """Recent epoch timestamps for a source from pulse_ticks."""
    try:
        c = sqlite3.connect(TICKS_DB, timeout=3)
        c.row_factory = sqlite3.Row
        rows = c.execute(
            """SELECT ts FROM pulse_ticks
               WHERE source_name = ? AND ts >= datetime('now', ?)
               ORDER BY ts""",
            (source, f"-{since_minutes} minutes")
        ).fetchall()
        c.close()
        out = []
        for r in rows:
            try:
                dt = datetime.fromisoformat(r["ts"].replace("Z","+00:00"))
                out.append(dt.timestamp())
            except Exception:
                pass
        return out
    except Exception:
        return []
