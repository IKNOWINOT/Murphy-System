"""
PCR-060e — Trajectory Plotter (deterministic)

THE WIRING PIECE between PCR-060b (Goal Plotter) and PCR-060a (Boundary
Detector). Before this patch, BoundaryResultV3.trajectory_converging
and .trajectory_delta_last were populated by the LLM judge eyeballing
its own reasoning — not by math.

This module computes Δ(t), dΔ/dt, and convergence status as PURE
FUNCTIONS of two trajectory curves. No LLM. Deterministic. Testable.
Replayable.

DOMAIN CLARIFICATION (per audit 2026-06-10)
===========================================
Naming clash: trajectory_engine.py is a FINANCIAL trading module
(skyrocketing assets). app.py's trajectory_scores are PCR-036 phase-
summary path confidence. THIS module is the BOUNDARY-LOOP trajectory
plotter and lives in the pcr060_* namespace.

DEFINITIONS (from spec §2 Part B)
=================================
F(t): forward curve — trajectory walked from prompt's stated problem
      toward proposed solution. Updated each Magnify pass.
R(t): reverse curve — trajectory reverse-engineered from goal back
      toward present. Re-computed each pass as deliverable evolves.

Both curves parametrize on t ∈ [0.0, 1.0]:
  - For R(t):  t=0 = goal state, t=1 = present (per GoalPlot spec)
  - For F(t):  t=0 = present, t=1 = projected solution end-state

Each point has a STATE VECTOR (operational + money-ratio targets).
Δ(t) is computed as the distance between F(1-t) and R(t) — they
should meet in the middle: F's projected end matches R's stated
goal, F's present matches R's projected present.

CONVERGENCE CHECK
=================
The spec requires:
  - Δ(N) < tolerance (curves meet by iteration N)
  - dΔ/dt < 0 for last 2 iterations (still converging)

This module computes both. The iteration N gating happens in the
DRILL DRIVER (PCR-060i) which calls this every iteration and decides
whether to fire another Magnify pass or terminate.

REVERSIBILITY
=============
- Pure functions, no I/O except a single LOG.info per call.
- No state mutation. Returns a dataclass with all numbers.
- BoundaryDetector v3 continues to work without this module — when
  this is wired (in 060i), the v3 detector receives PLOTTED values
  instead of LLM-eyeballed ones.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

LOG = logging.getLogger("murphy.pcr060_trajectory_plotter")


# ─────────────────────────────────────────────────────────────────────
# Result type
# ─────────────────────────────────────────────────────────────────────


@dataclass
class TrajectoryAnalysis:
    """The output of plot_trajectories."""

    # Δ(t) at each sampled t
    deltas: List[float] = field(default_factory=list)

    # Sampled t values matching deltas
    sample_ts: List[float] = field(default_factory=list)

    # Δ at t=1 (the present), i.e. how far apart F and R are NOW
    delta_at_present: float = 0.0

    # dΔ/dt from last iteration to this one (if available)
    d_delta_dt: Optional[float] = None

    # True if Δ(t=1) < tolerance — curves have met
    converged: bool = False

    # True if dΔ/dt < 0 over the last few iterations — still narrowing
    converging: bool = False

    # True if Δ stalled (|dΔ/dt| < flatline_threshold) — neither
    # converging nor diverging
    flatlining: bool = False

    # What this iteration recommends to the drill driver:
    # 'fire' = run another Magnify pass
    # 'apnea' = pause and re-measure (don't fire, don't terminate)
    # 'terminate' = converged, exit loop
    recommendation: str = "fire"

    # Human-readable explanation
    reason: str = ""

    # Audit
    iteration: int = 0
    tolerance: float = 0.1
    flatline_threshold: float = 0.02

    def as_dict(self) -> Dict[str, Any]:
        return {
            "deltas":             self.deltas,
            "sample_ts":          self.sample_ts,
            "delta_at_present":   self.delta_at_present,
            "d_delta_dt":         self.d_delta_dt,
            "converged":          self.converged,
            "converging":         self.converging,
            "flatlining":         self.flatlining,
            "recommendation":     self.recommendation,
            "reason":             self.reason,
            "iteration":          self.iteration,
            "tolerance":          self.tolerance,
            "flatline_threshold": self.flatline_threshold,
        }


# ─────────────────────────────────────────────────────────────────────
# State-vector distance
# ─────────────────────────────────────────────────────────────────────


def _normalize_numeric(value: Any) -> Optional[float]:
    """Extract a float from a target value. Numbers as-is, strings parsed."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        # strip $ , % etc
        cleaned = value.replace("$", "").replace(",", "").replace("%", "").strip()
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def state_vector_distance(a: Dict[str, Any], b: Dict[str, Any]) -> float:
    """L1 normalized distance between two target dicts.

    For each key in either dict:
      - if both values are numeric: relative diff |a-b| / max(|a|,|b|,1)
      - if one is missing: distance 1.0 (max for that key)
      - if non-numeric (string labels, etc): 0 if equal, 1 if different

    Returns sum across all keys / num_keys (normalized 0..1).
    """
    keys = set(a.keys()) | set(b.keys())
    if not keys:
        return 0.0

    total = 0.0
    for k in keys:
        va, vb = a.get(k), b.get(k)
        if va is None or vb is None:
            total += 1.0
            continue
        na, nb = _normalize_numeric(va), _normalize_numeric(vb)
        if na is not None and nb is not None:
            denom = max(abs(na), abs(nb), 1.0)
            total += abs(na - nb) / denom
        else:
            total += 0.0 if str(va) == str(vb) else 1.0

    return total / len(keys)


# ─────────────────────────────────────────────────────────────────────
# Curve interpolation
# ─────────────────────────────────────────────────────────────────────


def _state_at(
    curve: List[Dict[str, Any]],
    t_target: float,
    state_key: str = "state",
) -> Dict[str, Any]:
    """Get the state vector at t=t_target on the curve.

    Curve is a list of {"t": float, state_key: dict, ...} points.
    Picks the nearest point by t — no interpolation between dicts
    because state-vector targets are often categorical (role names,
    business class labels). Nearest-neighbor is the right primitive.
    """
    if not curve:
        return {}
    best = min(curve, key=lambda p: abs(p.get("t", 0.0) - t_target))
    return best.get(state_key, {})


# ─────────────────────────────────────────────────────────────────────
# Core: plot_trajectories
# ─────────────────────────────────────────────────────────────────────


def plot_trajectories(
    f_curve: List[Dict[str, Any]],
    r_curve: List[Dict[str, Any]],
    *,
    sample_count: int = 5,
    tolerance: float = 0.1,
    flatline_threshold: float = 0.02,
    iteration: int = 0,
    prior_delta_at_present: Optional[float] = None,
) -> TrajectoryAnalysis:
    """Compute Δ(t), dΔ/dt, and convergence verdict.

    Args:
        f_curve: forward trajectory points, each a dict with at least
                 't' and a state-vector dict. Typically derived from
                 the executor's graph (what the system has DECIDED
                 so far in this dispatch). t=0 = present, t=1 = solution.
        r_curve: reverse trajectory points (from GoalPlot.r_curve
                 serialized as dicts). t=0 = goal, t=1 = present.
        sample_count: how many t values to sample for Δ(t).
        tolerance: convergence threshold for Δ(t=1).
        flatline_threshold: |dΔ/dt| below this counts as flatline.
        iteration: which Magnify iteration this is (0-indexed).
        prior_delta_at_present: Δ(t=1) from the PREVIOUS iteration.
                                Needed to compute dΔ/dt. None on
                                iteration 0.

    Returns:
        TrajectoryAnalysis with all the math + a recommendation
        for the drill driver.
    """
    # Sample at evenly-spaced t in [0, 1]
    if sample_count < 2:
        sample_count = 2
    sample_ts = [i / (sample_count - 1) for i in range(sample_count)]

    deltas = []
    for t in sample_ts:
        # F maps t=0 (present) → t=1 (solution).
        # R maps t=0 (goal) → t=1 (present).
        # To compare: at any t, F(t) is at fraction t of journey
        # AWAY from present; R(1-t) is at fraction t of journey
        # AWAY from present (because R goes goal→present).
        # So compare F(t) vs R(1-t).
        f_state = _state_at(f_curve, t)
        r_state = _state_at(r_curve, 1.0 - t)
        deltas.append(state_vector_distance(f_state, r_state))

    delta_at_present = deltas[-1] if deltas else 0.0

    # dΔ/dt: relative to the previous iteration
    d_delta_dt: Optional[float] = None
    if prior_delta_at_present is not None:
        d_delta_dt = delta_at_present - prior_delta_at_present

    # Verdict logic
    converged = delta_at_present < tolerance
    converging = (d_delta_dt is not None) and (d_delta_dt < -flatline_threshold)
    flatlining = (d_delta_dt is not None) and (abs(d_delta_dt) < flatline_threshold) and not converged

    # Recommend
    if converged:
        recommendation = "terminate"
        reason = f"Δ(t=1)={delta_at_present:.3f} < tolerance={tolerance}"
    elif flatlining:
        recommendation = "apnea"
        reason = (
            f"Δ stalled at {delta_at_present:.3f} "
            f"(|dΔ/dt|={abs(d_delta_dt or 0):.3f} < flatline={flatline_threshold})"
        )
    else:
        recommendation = "fire"
        if d_delta_dt is None:
            reason = f"iteration 0, Δ(t=1)={delta_at_present:.3f}, no prior to compare"
        elif converging:
            reason = f"Δ narrowing: dΔ/dt={d_delta_dt:.3f} < 0"
        else:
            reason = f"Δ widening: dΔ/dt={d_delta_dt:.3f} >= 0"

    result = TrajectoryAnalysis(
        deltas=deltas,
        sample_ts=sample_ts,
        delta_at_present=delta_at_present,
        d_delta_dt=d_delta_dt,
        converged=converged,
        converging=converging,
        flatlining=flatlining,
        recommendation=recommendation,
        reason=reason,
        iteration=iteration,
        tolerance=tolerance,
        flatline_threshold=flatline_threshold,
    )
    LOG.info(
        "PCR-060e plot iter=%d Δ(1)=%.3f dΔ/dt=%s rec=%s",
        iteration, delta_at_present,
        f"{d_delta_dt:.3f}" if d_delta_dt is not None else "n/a",
        recommendation,
    )
    return result


# ─────────────────────────────────────────────────────────────────────
# Adapter: serialize GoalPlot.r_curve into the dict shape we accept
# ─────────────────────────────────────────────────────────────────────


def r_curve_from_goal_plot(goal_plot: Any) -> List[Dict[str, Any]]:
    """Take a GoalPlot (from pcr060_goal_plotter) and serialize r_curve.

    Each TrajectoryPoint becomes a dict with 't' and 'state' where
    state is the combined operational + money_ratio targets.
    """
    if not hasattr(goal_plot, "r_curve"):
        return []
    out = []
    for tp in goal_plot.r_curve:
        state = {}
        state.update(getattr(tp, "operational_targets", {}) or {})
        state.update(getattr(tp, "money_ratio_targets", {}) or {})
        out.append({
            "t":     getattr(tp, "t", 0.0),
            "state": state,
            "state_name": getattr(tp, "state_name", ""),
        })
    return out
