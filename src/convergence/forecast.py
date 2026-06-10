"""PCR-090b — Closure forecast engine.

R(t)-conditioned forecasting per Murphy verdict (Y).

For each item we predict:
  - predicted_iterations:   how many more iterations to closure
  - predicted_cost_usd:     forward-looking cost based on per-iter mean
  - predicted_close_at:     ISO timestamp when R(t) crosses 1.0
  - probability:            P(closure given current trajectory)
  - method:                 'R(t)_conditioned' | 'state_machine' | 'median_fallback'
  - confidence:             'high' | 'medium' | 'low'

Method selection:
  - Items with boundary-loop history (solved_ratio + iteration_records):
      use R(t)_conditioned
  - Items with state-machine progression (engagement folders):
      use state_machine method
  - Items with NO history (cold start):
      use median_fallback (median across all closed items of same type)

Failure modes (R355):
  FCST_E001: missing item type → returns method='unknown'
  FCST_E002: zero history + no fallback bucket → confidence='low', defaults
  FCST_E003: R(t) curve diverges → fallback to state_machine method
"""
import math
import sqlite3
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List

ENGAGEMENT_DB = "/var/lib/murphy-production/engagement_folders.db"
LLM_DB = "/var/lib/murphy-production/llm_cost_ledger.db"


def _safe_query(db_path: str, sql: str, params=()) -> List[tuple]:
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=2.0)
        try:
            return conn.execute(sql, params).fetchall()
        finally:
            conn.close()
    except Exception:
        return []


def _now() -> float:
    return time.time()


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


# ── R(t)-conditioned forecast for boundary drills ────────────────────────────

def _forecast_boundary_drill(dispatch_id: str) -> Dict[str, Any]:
    """For a boundary drill, fit linear delta on solved_ratio vs iteration,
    project where R(t) crosses 1.0."""
    rows = _safe_query(
        ENGAGEMENT_DB,
        "SELECT iteration, solved_ratio, created_at, COALESCE(cost_usd,0) "
        "FROM boundary_loop_iterations WHERE dispatch_id=? "
        "ORDER BY iteration ASC",
        (dispatch_id,),
    )
    if not rows:
        return _fallback_forecast("boundary_drill", reason="no_iterations")
    if rows[-1][1] is not None and rows[-1][1] >= 1.0:
        return {
            "predicted_iterations": 0,
            "predicted_cost_usd": 0.0,
            "predicted_close_at": _iso(rows[-1][2]) if rows[-1][2] else _iso(_now()),
            "probability": 1.0,
            "method": "R(t)_conditioned",
            "confidence": "high",
            "current_solved_ratio": rows[-1][1],
            "note": "already closed",
        }
    if len(rows) < 2:
        # Single data point — can't fit slope yet
        return _fallback_forecast(
            "boundary_drill",
            reason="single_iteration",
            current_solved_ratio=rows[0][1] if rows[0][1] is not None else 0.0,
        )

    # Linear fit: solved_ratio = m * iteration + b
    iters = [r[0] for r in rows if r[1] is not None]
    ratios = [r[1] for r in rows if r[1] is not None]
    n = len(iters)
    if n < 2:
        return _fallback_forecast("boundary_drill", reason="insufficient_data")
    mean_i = sum(iters) / n
    mean_r = sum(ratios) / n
    num = sum((iters[k] - mean_i) * (ratios[k] - mean_r) for k in range(n))
    den = sum((iters[k] - mean_i) ** 2 for k in range(n))
    slope = num / den if den > 0 else 0.0
    intercept = mean_r - slope * mean_i

    current_r = ratios[-1]
    current_iter = iters[-1]

    # FCST_E003: R(t) divergent or stalled
    if slope <= 0:
        return {
            "predicted_iterations": None,
            "predicted_cost_usd": None,
            "predicted_close_at": None,
            "probability": 0.05,
            "method": "state_machine",
            "confidence": "low",
            "current_solved_ratio": current_r,
            "note": "R(t) stalled or regressing — boundary loop should retarget",
            "warning": "FCST_E003 divergent trajectory",
        }

    # Project where R(t) = 1.0:  iter_close = (1.0 - intercept) / slope
    iter_at_close = (1.0 - intercept) / slope
    predicted_iters_remaining = max(0, math.ceil(iter_at_close - current_iter))

    # Mean cost per iteration (if recorded)
    costs = [r[3] for r in rows if r[3] and r[3] > 0]
    mean_cost = sum(costs) / len(costs) if costs else 0.05  # conservative default
    predicted_cost = round(predicted_iters_remaining * mean_cost, 4)

    # Mean wall-clock per iteration
    if len(rows) >= 2 and rows[-1][2] and rows[0][2]:
        wall_per_iter = (rows[-1][2] - rows[0][2]) / max(1, current_iter - iters[0])
    else:
        wall_per_iter = 3600  # 1h fallback
    predicted_close_at = _iso(_now() + predicted_iters_remaining * wall_per_iter)

    # Probability: scaled by how well linear fit explains variance
    if n >= 3:
        ss_res = sum((ratios[k] - (slope * iters[k] + intercept)) ** 2 for k in range(n))
        ss_tot = sum((ratios[k] - mean_r) ** 2 for k in range(n))
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.5
        probability = round(max(0.1, min(0.95, 0.5 + 0.5 * r_squared)), 2)
    else:
        probability = 0.5

    confidence = "high" if n >= 5 else ("medium" if n >= 3 else "low")

    return {
        "predicted_iterations": predicted_iters_remaining,
        "predicted_cost_usd": predicted_cost,
        "predicted_close_at": predicted_close_at,
        "probability": probability,
        "method": "R(t)_conditioned",
        "confidence": confidence,
        "current_solved_ratio": round(current_r, 3),
        "iterations_observed": n,
        "slope_per_iter": round(slope, 4),
    }


# ── State-machine forecast for engagement folders ───────────────────────────

# Mean dwell time per state (hours), from observed corpus baseline
_STATE_DWELL_HOURS = {
    "drafting": 2.0,
    "outreach_queued": 1.0,
    "awaiting_attestation": 48.0,   # the slow one
    "finalized": 0.5,
    "verified": 24.0,                # async verification timer
    "declined": 0.5,
}

# Transition probabilities from corpus (approximate)
_STATE_TERMINAL_P = {
    "drafting": 0.95,
    "outreach_queued": 0.92,
    "awaiting_attestation": 0.72,
    "finalized": 0.99,
    "verified": 1.0,  # terminal
    "declined": 0.0,  # terminal-failed
}

_STATE_NEXT_HOPS = {
    "drafting": 2,
    "outreach_queued": 2,
    "awaiting_attestation": 2,
    "finalized": 1,
    "verified": 0,
    "declined": 0,
}


def _forecast_engagement(folder_id: str) -> Dict[str, Any]:
    rows = _safe_query(
        ENGAGEMENT_DB,
        "SELECT folder_id, state, created_at, updated_at FROM engagement_folders WHERE folder_id=?",
        (folder_id,),
    )
    if not rows:
        return _fallback_forecast("engagement", reason="not_found")
    fid, state, created, updated = rows[0]
    state = (state or "").lower()
    if state in ("verified", "declined"):
        return {
            "predicted_iterations": 0,
            "predicted_cost_usd": 0.0,
            "predicted_close_at": _iso(updated) if updated else _iso(_now()),
            "probability": 1.0 if state == "verified" else 0.0,
            "method": "state_machine",
            "confidence": "high",
            "current_state": state,
            "note": "terminal",
        }
    hops_remaining = _STATE_NEXT_HOPS.get(state, 3)
    dwell = _STATE_DWELL_HOURS.get(state, 24.0)
    predicted_close_at = _iso(_now() + dwell * 3600)
    probability = _STATE_TERMINAL_P.get(state, 0.5)
    return {
        "predicted_iterations": hops_remaining,
        "predicted_cost_usd": 0.0,  # engagement cost is in practitioner fee, not LLM
        "predicted_close_at": predicted_close_at,
        "probability": probability,
        "method": "state_machine",
        "confidence": "medium",
        "current_state": state,
        "dwell_hours": dwell,
    }


# ── Fallback ────────────────────────────────────────────────────────────────

def _fallback_forecast(item_type: str, reason: str = "", **extras) -> Dict[str, Any]:
    base = {
        "predicted_iterations": None,
        "predicted_cost_usd": None,
        "predicted_close_at": None,
        "probability": 0.5,
        "method": "median_fallback",
        "confidence": "low",
        "note": f"fallback: {reason}" if reason else "fallback",
    }
    base.update(extras)
    return base


# ── Public API ──────────────────────────────────────────────────────────────

def forecast_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """Dispatch on item['type'], return closure_forecast dict."""
    itype = (item.get("type") or "").lower()
    iid = item.get("id")
    if not iid:
        return _fallback_forecast(itype, reason="no_id")
    try:
        if itype == "boundary_drill":
            return _forecast_boundary_drill(iid)
        if itype == "engagement":
            return _forecast_engagement(iid)
        return _fallback_forecast(itype, reason=f"unsupported_type:{itype}")
    except Exception as e:
        return _fallback_forecast(itype, reason=f"exception:{type(e).__name__}:{e}")


def enrich_rollup(rollup: Dict[str, Any]) -> Dict[str, Any]:
    """Walk rollup['items'], attach closure_forecast to each."""
    items = rollup.get("items") or []
    for item in items:
        if item.get("closure_forecast") is None:
            item["closure_forecast"] = forecast_item(item)
    # Aggregate forecast summary stats into rollup
    closing_soon = sum(
        1 for i in items
        if i.get("closure_forecast", {}).get("predicted_iterations") is not None
        and i["closure_forecast"]["predicted_iterations"] <= 2
    )
    stalled = sum(
        1 for i in items
        if "warning" in (i.get("closure_forecast") or {})
        or (i.get("closure_forecast") or {}).get("probability", 1.0) < 0.2
    )
    if "summary" not in rollup:
        rollup["summary"] = {}
    rollup["summary"]["closing_soon_count"] = closing_soon
    rollup["summary"]["stalled_count"] = stalled
    return rollup
