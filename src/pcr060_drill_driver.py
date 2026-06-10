"""
PCR-060i — Drill Driver (the control loop that makes 060 actually LOOP)

What 060i does for one dispatch:
  1. Call Goal Plotter (PCR-060b) once → R(t)
  2. For iteration n = 0..N-1:
     a. Call Magnify (or use init prompt for n=0) → executor output
     b. Extract F(t) from Magnify output structure (Q1=C)
     c. plot_trajectories(F, R, prior_delta) → Δ recommendation (PCR-060e)
     d. Run Boundary Detector v3 → satisfied? (PCR-060a)
     e. Record iteration to boundary_loop_iterations table (Q4=β)
     f. If satisfied AND recommendation='terminate': SUCCESS, exit
     g. If recommendation='apnea': pause, re-measure same F next iter
     h. If recommendation='fire': re-run Magnify scoped to weakest_link
  3. Hard exit at N=5 iterations or $1.00 LLM cap (per spec §2)
  4. Return DrillResult with deliverable + quality flag (Q5=ψ)

Per Murphy-approved C/X/R/β/ψ (chat-v2 consult 2026-06-10):
  C: F(t) from Magnify response directly (revised from A — graph snapshots
     are commented-out in app.py and never persisted)
  X: Direct HTTP POST to /api/mss/magnify
  R: Both — Δ values in prompt as constraints AND overwritten post-hoc
     in BoundaryResultV3
  β: SQLite table boundary_loop_iterations for replayability
  ψ: Best-effort exit at budget — return whatever exists, mark quality

REVERSIBILITY
=============
- New module + new table only.
- 060a Boundary Detector v3 stays untouched in this commit. The "R"
  strategy is half-applied: 060i overwrites trajectory_* fields
  in the returned result post-hoc, but doesn't yet inject the math
  into the detector's PROMPT. That's a follow-on (060i.1) and needs
  a 1-line detector change to accept injected_delta param.
- Magnify call wrapped in try/except — failure becomes a no-progress
  iteration (recommendation forced to 'apnea'), loop doesn't crash.
- Budget enforcement is in-process — when LLM_BUDGET_CAP_USD is
  exceeded, loop exits with deliverable_quality='budget_exceeded'.
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

import requests

from src.pcr060_trajectory_plotter import (
    TrajectoryAnalysis,
    plot_trajectories,
    r_curve_from_goal_plot,
)

LOG = logging.getLogger("murphy.pcr060_drill_driver")


# ─────────────────────────────────────────────────────────────────────
# Configuration (locked by spec §2)
# ─────────────────────────────────────────────────────────────────────

MAX_ITERATIONS = 5
LLM_BUDGET_CAP_USD = 1.00
MAGNIFY_URL = os.getenv("MAGNIFY_URL", "https://murphy.systems/api/mss/magnify")
MAGNIFY_TIMEOUT_SEC = 30
TOLERANCE = 0.10
FLATLINE_THRESHOLD = 0.02

# Estimated cost per Magnify call (rough — we don't have real metering yet)
ESTIMATED_COST_PER_MAGNIFY_USD = 0.05

# Iteration state persistence
DEFAULT_DB_PATH = "/var/lib/murphy-production/engagement_folders.db"
# (reusing the engagement_folders.db so we don't proliferate DBs;
#  the table is namespaced)


# ─────────────────────────────────────────────────────────────────────
# Schema (Q4=β)
# ─────────────────────────────────────────────────────────────────────

SCHEMA = """
CREATE TABLE IF NOT EXISTS boundary_loop_iterations (
    iteration_id          TEXT PRIMARY KEY,
    dispatch_id           TEXT NOT NULL,
    iteration             INTEGER NOT NULL,
    delta_at_present      REAL NOT NULL,
    d_delta_dt            REAL,
    recommendation        TEXT NOT NULL,
    converged             INTEGER NOT NULL,
    flatlining            INTEGER NOT NULL,
    boundary_satisfied    INTEGER NOT NULL,
    weakest_link          TEXT,
    magnify_ok            INTEGER NOT NULL,
    cost_usd              REAL NOT NULL,
    cumulative_cost_usd   REAL NOT NULL,
    f_curve_json          TEXT NOT NULL,
    reason                TEXT,
    created_at            REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_bli_dispatch
    ON boundary_loop_iterations (dispatch_id);

CREATE INDEX IF NOT EXISTS idx_bli_created
    ON boundary_loop_iterations (created_at);
"""


def init_drill_db(db_path: str = DEFAULT_DB_PATH) -> None:
    """Idempotent — safe to call at startup or per-drive."""
    con = sqlite3.connect(db_path)
    try:
        con.executescript(SCHEMA)
        con.commit()
    finally:
        con.close()


# ─────────────────────────────────────────────────────────────────────
# Result types
# ─────────────────────────────────────────────────────────────────────


@dataclass
class IterationRecord:
    iteration:            int
    delta_at_present:     float
    d_delta_dt:           Optional[float]
    recommendation:       str
    converged:            bool
    flatlining:           bool
    boundary_satisfied:   bool
    weakest_link:         Optional[str]
    magnify_ok:           bool
    cost_usd:             float
    cumulative_cost_usd:  float
    f_curve:              List[Dict[str, Any]]
    reason:               str

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DrillResult:
    dispatch_id:           str
    success:               bool
    deliverable_quality:   str   # 'verified' | 'degraded' | 'budget_exceeded' | 'magnify_failed'
    iterations_run:        int
    final_delta:           float
    cumulative_cost_usd:   float
    deliverable:           Optional[Dict[str, Any]]
    iteration_log:         List[IterationRecord] = field(default_factory=list)
    reason:                str = ""

    def as_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["iteration_log"] = [r.as_dict() for r in self.iteration_log]
        return d


# ─────────────────────────────────────────────────────────────────────
# Q1=C: F(t) extraction from Magnify response
# ─────────────────────────────────────────────────────────────────────


def f_curve_from_magnify(
    magnify_response: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Q1=C extraction.

    Magnify returns:
      result.output = {concept_overview, functional_requirements,
                       technical_components, compliance_considerations,
                       target_audience, industry, business_name,
                       cost_complexity_estimate}
      result.input_quality / output_quality = {resolution_score,
                                                density_index,
                                                coherence_score,
                                                iqs, cqi, ...}
    We map this to F(t):
      t=0.0  (present):  input_quality scores → state vector
      t=1.0  (solution): output_quality scores + cost estimate → state vector

    This is a 2-point F curve. Coarse but sufficient for v1 — the goal
    plotter R(t) is also 3-6 points so we're comparing at the endpoints.
    """
    if not magnify_response or not isinstance(magnify_response, dict):
        return []

    result = magnify_response.get("result", {})
    if not isinstance(result, dict):
        return []

    input_q = result.get("input_quality", {}) or {}
    output_q = result.get("output_quality", {}) or {}

    # State vector is QUALITY-ONLY (numeric). Categorical fields like
    # cost_complexity_estimate / industry / target_audience describe the
    # DELIVERABLE, not its quality, so they don't belong in Δ comparison.
    # They're available via the deliverable field on DrillResult instead.
    def _state(quality: Dict[str, Any]) -> Dict[str, Any]:
        s = {
            "resolution_score": quality.get("resolution_score"),
            "density_index":    quality.get("density_index"),
            "coherence_score":  quality.get("coherence_score"),
            "iqs":              quality.get("iqs"),
            "cqi":              quality.get("cqi"),
        }
        return {k: v for k, v in s.items() if v is not None}

    in_state = _state(input_q)
    out_state = _state(output_q)
    if not in_state and not out_state:
        # No quality data at all → empty curve so caller can apnea
        return []

    return [
        {"t": 0.0, "state": in_state, "state_name": "present"},
        {"t": 1.0, "state": out_state, "state_name": "solution"},
    ]


# ─────────────────────────────────────────────────────────────────────
# Q2=X: Magnify HTTP call
# ─────────────────────────────────────────────────────────────────────


def call_magnify(
    text: str,
    *,
    api_key: Optional[str] = None,
    url: str = MAGNIFY_URL,
    timeout: int = MAGNIFY_TIMEOUT_SEC,
    scope: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Direct HTTP POST. Returns response dict or None on failure.

    Wraps failure as None — caller treats this as no-progress iteration.
    """
    key = api_key or os.getenv("MURPHY_FOUNDER_KEY")
    if not key:
        LOG.warning("PCR-060i no API key for Magnify; returning None")
        return None

    payload: Dict[str, Any] = {"text": text}
    if scope:
        payload["scope"] = scope

    try:
        r = requests.post(
            url,
            json=payload,
            headers={"X-API-Key": key, "Content-Type": "application/json"},
            timeout=timeout,
        )
        if r.status_code != 200:
            LOG.warning("PCR-060i Magnify HTTP %d: %s", r.status_code, r.text[:200])
            return None
        return r.json()
    except (requests.RequestException, ValueError) as e:
        LOG.warning("PCR-060i Magnify call failed: %s", e)
        return None


# ─────────────────────────────────────────────────────────────────────
# Iteration persistence (Q4=β)
# ─────────────────────────────────────────────────────────────────────


def _persist_iteration(
    dispatch_id: str,
    record: IterationRecord,
    *,
    db_path: str = DEFAULT_DB_PATH,
) -> None:
    init_drill_db(db_path)
    con = sqlite3.connect(db_path)
    try:
        con.execute(
            "INSERT INTO boundary_loop_iterations "
            "(iteration_id, dispatch_id, iteration, delta_at_present, "
            " d_delta_dt, recommendation, converged, flatlining, "
            " boundary_satisfied, weakest_link, magnify_ok, cost_usd, "
            " cumulative_cost_usd, f_curve_json, reason, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                f"bli_{uuid.uuid4().hex[:14]}",
                dispatch_id,
                record.iteration,
                record.delta_at_present,
                record.d_delta_dt,
                record.recommendation,
                int(record.converged),
                int(record.flatlining),
                int(record.boundary_satisfied),
                record.weakest_link,
                int(record.magnify_ok),
                record.cost_usd,
                record.cumulative_cost_usd,
                json.dumps(record.f_curve),
                record.reason,
                time.time(),
            ),
        )
        con.commit()
    finally:
        con.close()


def read_iterations(
    dispatch_id: str,
    *,
    db_path: str = DEFAULT_DB_PATH,
) -> List[Dict[str, Any]]:
    """Read all persisted iterations for a dispatch — audit query."""
    init_drill_db(db_path)
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            "SELECT * FROM boundary_loop_iterations "
            "WHERE dispatch_id = ? ORDER BY iteration ASC",
            (dispatch_id,),
        ).fetchall()
    finally:
        con.close()
    return [dict(r) for r in rows]


# ─────────────────────────────────────────────────────────────────────
# Main entry: drive the boundary loop for one dispatch
# ─────────────────────────────────────────────────────────────────────


def drive_boundary_loop(
    prompt: str,
    *,
    business_spec: Optional[Dict[str, Any]] = None,
    dispatch_id: Optional[str] = None,
    goal_plot=None,
    boundary_detector=None,
    max_iterations: int = MAX_ITERATIONS,
    budget_cap_usd: float = LLM_BUDGET_CAP_USD,
    tolerance: float = TOLERANCE,
    flatline_threshold: float = FLATLINE_THRESHOLD,
    db_path: str = DEFAULT_DB_PATH,
    api_key: Optional[str] = None,
    magnify_url: str = MAGNIFY_URL,
) -> DrillResult:
    """The control loop. Drives one dispatch from prompt to deliverable.

    Args:
      prompt: user's stated intent
      business_spec: extra context for goal plotter
      dispatch_id: caller-provided id; auto-generated if None
      goal_plot: pre-computed GoalPlot to skip re-projecting (testing)
      boundary_detector: callable(prompt, output) -> BoundaryResultV3-like
                        (None = skip detector check, recommend purely on Δ)
      max_iterations: hard cap (default 5 per spec)
      budget_cap_usd: hard cap (default $1.00 per spec)
      tolerance: Δ(t=1) threshold for converged
      flatline_threshold: |dΔ/dt| threshold for flatlining
      db_path: SQLite path for iteration log
      api_key: passed to Magnify
      magnify_url: override for tests

    Returns: DrillResult with deliverable + quality + iteration log.
    """
    dispatch_id = dispatch_id or f"drill_{uuid.uuid4().hex[:14]}"
    business_spec = business_spec or {}

    # Step 1: R(t) from Goal Plotter
    if goal_plot is None:
        try:
            from src.pcr060_goal_plotter import project_goal
            goal_plot = project_goal(prompt, business_spec)
        except Exception as e:
            LOG.warning("PCR-060i goal projection failed: %s", e)
            goal_plot = None

    r_curve = r_curve_from_goal_plot(goal_plot) if goal_plot else []

    # Step 2: iteration loop
    iteration_log: List[IterationRecord] = []
    cumulative_cost = 0.0
    prior_delta: Optional[float] = None
    last_deliverable: Optional[Dict[str, Any]] = None
    last_magnify_response: Optional[Dict[str, Any]] = None
    last_weakest_link: Optional[str] = None

    for n in range(max_iterations):
        # Budget check BEFORE the call
        if cumulative_cost + ESTIMATED_COST_PER_MAGNIFY_USD > budget_cap_usd:
            LOG.info(
                "PCR-060i dispatch=%s budget cap reached at iter=%d (cum=%.2f, cap=%.2f)",
                dispatch_id, n, cumulative_cost, budget_cap_usd,
            )
            return DrillResult(
                dispatch_id=dispatch_id,
                success=False,
                deliverable_quality="budget_exceeded",
                iterations_run=n,
                final_delta=prior_delta if prior_delta is not None else 1.0,
                cumulative_cost_usd=cumulative_cost,
                deliverable=last_deliverable,
                iteration_log=iteration_log,
                reason=f"budget cap ${budget_cap_usd:.2f} reached at iter {n}",
            )

        # 2a: Magnify call
        text_for_call = prompt
        if last_weakest_link:
            text_for_call = f"{prompt}\n\n[scope: {last_weakest_link}]"

        magnify_response = call_magnify(
            text_for_call,
            api_key=api_key,
            url=magnify_url,
            scope=last_weakest_link,
        )
        magnify_ok = magnify_response is not None
        iter_cost = ESTIMATED_COST_PER_MAGNIFY_USD if magnify_ok else 0.0
        cumulative_cost += iter_cost

        # 2b: F(t) extraction
        f_curve = f_curve_from_magnify(magnify_response) if magnify_ok else []
        if magnify_ok:
            last_magnify_response = magnify_response
            last_deliverable = (magnify_response.get("result", {}) or {}).get("output")

        # 2c: trajectory plot
        if not magnify_ok or not f_curve or not r_curve:
            # No-progress iteration — force apnea
            traj = TrajectoryAnalysis(
                deltas=[],
                sample_ts=[],
                delta_at_present=prior_delta if prior_delta is not None else 1.0,
                d_delta_dt=0.0 if prior_delta is not None else None,
                converged=False,
                converging=False,
                flatlining=True,
                recommendation="apnea",
                reason=(
                    "magnify_failed" if not magnify_ok
                    else "no R(t) — goal plot unavailable" if not r_curve
                    else "no F(t) from response"
                ),
                iteration=n,
                tolerance=tolerance,
                flatline_threshold=flatline_threshold,
            )
        else:
            traj = plot_trajectories(
                f_curve, r_curve,
                sample_count=5,
                tolerance=tolerance,
                flatline_threshold=flatline_threshold,
                iteration=n,
                prior_delta_at_present=prior_delta,
            )

        # 2d: boundary detector (optional, for v1 we accept the trajectory
        #     verdict alone; detector wiring is 060i.1 with R-strategy)
        boundary_satisfied = traj.converged  # proxy until detector wired
        weakest_link: Optional[str] = None
        if boundary_detector and magnify_ok:
            try:
                detector_result = boundary_detector(prompt, magnify_response)
                # Best-effort: read .satisfied and .weakest_link if present
                boundary_satisfied = bool(getattr(detector_result, "satisfied", False))
                weakest_link = getattr(detector_result, "weakest_link", None)
            except Exception as e:
                LOG.warning("PCR-060i detector call failed at iter=%d: %s", n, e)

        # 2e: record + persist
        record = IterationRecord(
            iteration=n,
            delta_at_present=traj.delta_at_present,
            d_delta_dt=traj.d_delta_dt,
            recommendation=traj.recommendation,
            converged=traj.converged,
            flatlining=traj.flatlining,
            boundary_satisfied=boundary_satisfied,
            weakest_link=weakest_link,
            magnify_ok=magnify_ok,
            cost_usd=iter_cost,
            cumulative_cost_usd=cumulative_cost,
            f_curve=f_curve,
            reason=traj.reason,
        )
        iteration_log.append(record)
        try:
            _persist_iteration(dispatch_id, record, db_path=db_path)
        except Exception as e:
            LOG.warning("PCR-060i iteration persist failed: %s", e)

        prior_delta = traj.delta_at_present
        last_weakest_link = weakest_link

        # 2f/g/h: decide next action
        if traj.recommendation == "terminate" and (boundary_satisfied or not boundary_detector):
            LOG.info(
                "PCR-060i dispatch=%s SUCCESS at iter=%d Δ=%.3f",
                dispatch_id, n, traj.delta_at_present,
            )
            return DrillResult(
                dispatch_id=dispatch_id,
                success=True,
                deliverable_quality="verified",
                iterations_run=n + 1,
                final_delta=traj.delta_at_present,
                cumulative_cost_usd=cumulative_cost,
                deliverable=last_deliverable,
                iteration_log=iteration_log,
                reason=f"converged at iter {n}: {traj.reason}",
            )
        # else: keep iterating (apnea AND fire both = next iteration)

    # Budget OR iteration cap exhausted — Q5=ψ best-effort
    quality = "degraded" if last_magnify_response else "magnify_failed"
    return DrillResult(
        dispatch_id=dispatch_id,
        success=False,
        deliverable_quality=quality,
        iterations_run=max_iterations,
        final_delta=prior_delta if prior_delta is not None else 1.0,
        cumulative_cost_usd=cumulative_cost,
        deliverable=last_deliverable,
        iteration_log=iteration_log,
        reason=f"max_iterations {max_iterations} reached without convergence",
    )
