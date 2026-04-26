"""
PATCH-099: PCC — Predictive Convergence Correction
====================================================
Shifts Murphy from reactive error-correction to trajectory-based estimation.

Formula:
    R_fair = R_observed / R_infinity
    R_infinity = R_t + E(C | T, S, A)

Where:
    R_observed  = what we're actually seeing right now (measured state)
    R_infinity  = what a fully-calibrated, fair outcome would look like
                  given this trajectory
    R_t         = current rolling baseline (exponential moving average)
    E(C|T,S,A)  = expected correction given:
                    C = causal chain selected (which path we entered)
                    T = trajectory (prompt history, direction of travel)
                    S = MSS StateVector D1-D8 (circumstance)
                    A = implicit assumptions (what we're taking for granted)

Outputs:
    R_fair < 1.0  — under-steering: trajectory heading somewhere worse than fair
    R_fair = 1.0  — calibrated: steering is appropriate for this trajectory
    R_fair > 1.0  — over-steering: applying more correction than the trajectory warrants
    R_fair = 0.0  — cold start: no prior data, use Rosetta (legacy prior)

Hard floors (Omega_possible boundary — PCC never touches these):
    p_harm_physical    >= FLOOR_HARM  → HOLD regardless of R_fair
    p_harm_autonomy    >= FLOOR_HARM  → HOLD regardless of R_fair

Feedback rule:
    Confirmed good outcome: R_t += 0.05
    Disconfirmed (harm detected): R_t -= 0.03

Steering feedback:
    R_fair < 0.6  → INCREASE magnitude (steer harder)
    0.6 <= R_fair <= 1.2  → HOLD magnitude (calibrated)
    R_fair > 1.2  → REDUCE magnitude (ease off)

Creator: Corey Post / Murphy System  |  PATCH-099  |  License: BSL 1.1
"""

import logging
import math
import threading
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────
FLOOR_HARM          = 0.65   # Hard floor — if harm probability >= this, HOLD
EMA_ALPHA           = 0.15   # Exponential moving average smoothing factor
FEEDBACK_CONFIRM    = +0.05  # R_t adjustment on confirmed good outcome
FEEDBACK_DISCONFIRM = -0.03  # R_t adjustment on harm detection
R_FAIR_UNDERSTEER   = 0.60   # Below this → increase steering magnitude
R_FAIR_OVERSTEER    = 1.20   # Above this → reduce steering magnitude
COLD_START_R_T      = 0.50   # Default R_t before any feedback is collected
MAX_HISTORY         = 500    # Max trajectory events to keep per session


# ── MSS Dimension Weights ──────────────────────────────────────────────────────
# D1-D8 gravitational weights in the R_infinity calculation.
# Higher weight = this dimension pulls harder on the expected correction.
# Tuned from architecture principles — not arbitrary.
MSS_WEIGHTS = {
    "d1_flourishing":        +0.20,  # positive pull toward fair outcome
    "d2_contraction":        -0.25,  # negative pull (harm direction)
    "d3_closure":            -0.30,  # tribal closure is strongest harm signal
    "d4_coherence_delta":    +0.15,  # net coherence direction
    "d5_p_harm_physical":    -0.35,  # hard harm — strongest negative weight
    "d6_p_harm_psychological":-0.20, # psychological harm
    "d7_p_harm_financial":   -0.10,  # financial harm
    "d8_p_harm_autonomy":    -0.30,  # autonomy harm — near-hard-floor level
}

# D9: masculine/feminine harmonic balance
# When |D9| > 0.3, one axis is dominating — adjustment needed
D9_BALANCE_THRESHOLD = 0.30


# ── Causal Chain Catalog ───────────────────────────────────────────────────────
# Each named causal chain has a known correction expectation.
# E(C) = expected correction magnitude when entering this chain.
CAUSAL_CHAINS: Dict[str, float] = {
    "outrage_amplification":     0.80,  # high correction expected
    "scapegoat_loop":            0.75,
    "in_group_closure":          0.70,
    "threat_frame":              0.50,
    "curiosity_expansion":       0.10,  # low correction — already flourishing
    "cooperation_signal":        0.05,
    "complexity_injection":      0.15,
    "autonomy_preservation":     0.20,
    "default":                   0.40,  # unknown chain
    "world_state_pressure":      0.55,  # PATCH-103: systemic world risk — moderate correction
}


# ── Data Structures ────────────────────────────────────────────────────────────

@dataclass
class PCCInput:
    """Everything PCC needs to compute R_fair."""
    session_id:      str
    state_vector:    Dict[str, float]   # D1-D8 values
    causal_chain:    str = "default"    # which chain was entered
    trajectory_len:  int = 0            # how many events in this session
    d9_balance:      float = 0.0        # masculine/feminine harmonic (-1 to 1)
    assumptions:     List[str] = field(default_factory=list)  # implicit A


@dataclass
class PCCResult:
    """PCC output — R_fair and steering directive."""
    r_observed:      float   # raw measured state
    r_infinity:      float   # expected fair-outcome baseline
    r_fair:          float   # R_observed / R_infinity (the ratio)
    r_t:             float   # current rolling baseline
    e_correction:    float   # E(C | T, S, A)
    causal_chain:    str
    steering_directive: str  # INCREASE | HOLD | REDUCE | BLOCK
    hard_floor_hit:  bool    # True if harm floor triggered BLOCK
    magnitude_delta: float   # how much to adjust magnitude (+/-)
    pcc_timestamp:   str
    cold_start:      bool    # True if no prior trajectory data

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class TrajectoryEvent:
    """One recorded outcome — used to update R_t."""
    session_id:   str
    r_fair:       float
    confirmed:    bool     # True = good outcome, False = harm detected
    timestamp:    float    # monotonic


# ── PCC Engine ─────────────────────────────────────────────────────────────────

class PCCEngine:
    """
    Predictive Convergence Correction — the core steering calibrator.

    One singleton per process. Thread-safe.
    Maintains R_t (rolling baseline) per session and globally.
    """

    def __init__(self):
        self._lock     = threading.Lock()
        self._r_t:     Dict[str, float] = {}   # per-session rolling baseline
        self._global_r_t = COLD_START_R_T      # cross-session baseline
        self._history: Dict[str, List[TrajectoryEvent]] = {}
        self._total_events = 0

    # ── Primary API ────────────────────────────────────────────────────────────

    def compute(self, inp: PCCInput) -> PCCResult:
        """
        Compute R_fair for the given input.

        Principle 5 applied: what is the expected result at all operation points?
          - Cold start (no history): R_fair = 0.0, directive = HOLD (Rosetta prior)
          - Hard floor hit: directive = BLOCK regardless
          - Calibrated: HOLD
          - Under-steering: INCREASE
          - Over-steering: REDUCE
        """
        with self._lock:
            cold_start = self._total_events == 0

            # ── Step 1: R_observed — weighted sum of MSS state ────────────────
            r_observed = self._compute_r_observed(inp.state_vector)

            # ── Step 2: R_t — rolling baseline for this session ──────────────
            r_t = self._r_t.get(inp.session_id, self._global_r_t)

            # ── Step 3: E(C | T, S, A) — expected correction ──────────────────
            e_correction = self._compute_e_correction(
                inp.causal_chain, inp.trajectory_len, inp.d9_balance, inp.assumptions
            )

            # ── Step 4: R_infinity ────────────────────────────────────────────
            r_infinity = r_t + e_correction
            if r_infinity <= 0:
                r_infinity = 0.001  # prevent divide-by-zero

            # ── Step 5: R_fair ────────────────────────────────────────────────
            r_fair = r_observed / r_infinity if not cold_start else 0.0

            # ── Step 6: Hard floor check ──────────────────────────────────────
            hard_floor_hit = self._check_hard_floors(inp.state_vector)

            # ── Step 7: Steering directive ────────────────────────────────────
            directive, magnitude_delta = self._directive(r_fair, hard_floor_hit, cold_start)

            result = PCCResult(
                r_observed       = round(r_observed, 4),
                r_infinity       = round(r_infinity, 4),
                r_fair           = round(r_fair, 4),
                r_t              = round(r_t, 4),
                e_correction     = round(e_correction, 4),
                causal_chain     = inp.causal_chain,
                steering_directive = directive,
                hard_floor_hit   = hard_floor_hit,
                magnitude_delta  = round(magnitude_delta, 4),
                pcc_timestamp    = datetime.now(timezone.utc).isoformat(),
                cold_start       = cold_start,
            )

            logger.debug(
                "PCC: session=%s r_observed=%.3f r_infinity=%.3f r_fair=%.3f directive=%s",
                inp.session_id, r_observed, r_infinity, r_fair, directive
            )
            return result

    def feedback(self, session_id: str, r_fair: float, confirmed: bool):
        """
        Record an outcome and update R_t.
        confirmed=True  → good outcome, R_t += FEEDBACK_CONFIRM
        confirmed=False → harm detected, R_t -= FEEDBACK_DISCONFIRM (abs)
        """
        with self._lock:
            event = TrajectoryEvent(
                session_id=session_id,
                r_fair=r_fair,
                confirmed=confirmed,
                timestamp=time.monotonic(),
            )
            if session_id not in self._history:
                self._history[session_id] = []
            self._history[session_id].append(event)
            if len(self._history[session_id]) > MAX_HISTORY:
                self._history[session_id].pop(0)

            self._total_events += 1

            # Update per-session R_t
            current = self._r_t.get(session_id, self._global_r_t)
            delta = FEEDBACK_CONFIRM if confirmed else -abs(FEEDBACK_DISCONFIRM)
            new_r_t = max(0.05, min(2.0, current + delta))
            self._r_t[session_id] = new_r_t

            # EMA update to global baseline
            self._global_r_t = (
                EMA_ALPHA * new_r_t + (1 - EMA_ALPHA) * self._global_r_t
            )

            logger.info(
                "PCC feedback: session=%s confirmed=%s r_t: %.3f → %.3f  global=%.3f",
                session_id, confirmed, current, new_r_t, self._global_r_t
            )

    def status(self, session_id: str = None) -> Dict:
        """Current PCC status for monitoring / self-eval."""
        with self._lock:
            out = {
                "global_r_t":    round(self._global_r_t, 4),
                "total_events":  self._total_events,
                "sessions":      len(self._r_t),
                "cold_start":    self._total_events == 0,
            }
            if session_id:
                out["session_r_t"] = round(self._r_t.get(session_id, self._global_r_t), 4)
                hist = self._history.get(session_id, [])
                out["session_events"] = len(hist)
                if hist:
                    out["last_r_fair"] = round(hist[-1].r_fair, 4)
                    out["last_confirmed"] = hist[-1].confirmed
            return out

    # ── Internal computation ────────────────────────────────────────────────────

    def _compute_r_observed(self, sv: Dict[str, float]) -> float:
        """
        Weighted sum of MSS dimensions → R_observed.
        Positive weights pull toward fair outcome.
        Negative weights pull toward harm.
        Result is normalized to 0–1 range.
        """
        raw = 0.0
        weight_sum = sum(abs(w) for w in MSS_WEIGHTS.values())
        for dim, weight in MSS_WEIGHTS.items():
            val = sv.get(dim, 0.0)
            raw += weight * val
        # Normalize: raw ranges from -weight_sum to +weight_sum → map to 0–1
        normalized = (raw + weight_sum) / (2 * weight_sum)
        return max(0.0, min(1.0, normalized))

    def _compute_e_correction(
        self,
        causal_chain: str,
        trajectory_len: int,
        d9_balance: float,
        assumptions: List[str],
    ) -> float:
        """
        E(C | T, S, A) — expected correction given causal chain, trajectory, and assumptions.

        Components:
          base     = E(C) for the named causal chain
          traj_adj = trajectory length adjustment (longer = more correction expected)
          d9_adj   = D9 harmonic imbalance penalty
          assump   = assumption penalty (more assumptions = more expected error)
        """
        base = CAUSAL_CHAINS.get(causal_chain, CAUSAL_CHAINS["default"])

        # Trajectory adjustment: longer trajectory = more history = less correction needed
        # (system has more data to work with)
        traj_adj = -0.05 * math.log1p(trajectory_len) if trajectory_len > 0 else 0.0

        # D9 harmonic imbalance: if one axis dominates, add correction expectation
        d9_adj = 0.10 * max(0.0, abs(d9_balance) - D9_BALANCE_THRESHOLD)

        # Assumption penalty: each unverified assumption adds a small correction expectation
        assump_adj = 0.03 * len(assumptions)

        total = base + traj_adj + d9_adj + assump_adj
        return max(0.01, total)  # minimum expected correction

    def _check_hard_floors(self, sv: Dict[str, float]) -> bool:
        """
        Hard floor check — if physical or autonomy harm probability >= FLOOR_HARM,
        PCC directs BLOCK regardless of R_fair.
        These are pre-conditions that define Omega_possible boundary.
        PCC does not reason past them — they are not negotiable.
        """
        p_physical = sv.get("d5_p_harm_physical", 0.0)
        p_autonomy = sv.get("d8_p_harm_autonomy", 0.0)
        return p_physical >= FLOOR_HARM or p_autonomy >= FLOOR_HARM

    def _directive(
        self, r_fair: float, hard_floor_hit: bool, cold_start: bool
    ) -> Tuple[str, float]:
        """
        Translate R_fair into a steering directive and magnitude delta.
        Returns (directive, magnitude_delta).
        """
        if hard_floor_hit:
            return "BLOCK", 0.0
        if cold_start:
            return "HOLD", 0.0          # Rosetta prior — no data yet
        if r_fair < R_FAIR_UNDERSTEER:
            # Under-steering: trajectory heading somewhere worse than fair
            # Increase magnitude proportionally
            delta = (R_FAIR_UNDERSTEER - r_fair) * 0.5
            return "INCREASE", +round(delta, 4)
        if r_fair > R_FAIR_OVERSTEER:
            # Over-steering: backing off
            delta = (r_fair - R_FAIR_OVERSTEER) * 0.3
            return "REDUCE", -round(delta, 4)
        return "HOLD", 0.0


# ── Singleton ──────────────────────────────────────────────────────────────────
pcc = PCCEngine()
