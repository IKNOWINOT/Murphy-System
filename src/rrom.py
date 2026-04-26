"""
PATCH-098: RROM Phase 1 — Ratio Resource Orchestration Model (Measurement)
============================================================================
Phase 1 is measurement only. No throttling. No lifecycle changes.
We are learning R_observed for each module cluster before we steer anything.

The seven Rubik faces (PATCH-102: +hardware_health):
  M1 shield_util       — Shield Wall + Honeypot + Conduct checks per minute
  M2 auth_util         — OIDC + session validation per minute
  M3 llm_demand        — LLM completions in-flight (semaphore)
  M4 convergence_demand — Convergence analyze + steer per minute
  M5 model_team_util   — Model Team deliberations in-flight
  M6 ambient_util      — Ambient synthesis loop cycles per minute

Ethical floors (Phase 2 will enforce):
  Shield:    ≥ 15% of available compute
  Auth:      ≥ 10% of available compute
  LLM:       ≤ 40% of available compute (cap, not floor)
  Ambient:   first to shed under pressure

PCC applies: R_fair(module) = demand_observed / demand_infinity
             where demand_infinity = sustainable baseline for that face

Creator: Corey Post / Murphy System  |  PATCH-098  |  License: BSL 1.1
"""

import asyncio
import logging
import os
import threading
import time
from collections import deque
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────
WINDOW_SECONDS   = 60          # rolling window for rate measurement
SAMPLE_INTERVAL  = 5           # seconds between snapshots
MAX_HISTORY      = 720         # 1 hour of 5s samples

# Ethical floors (Phase 2 will enforce — Phase 1 just measures)
FLOOR_SHIELD     = 0.15
FLOOR_AUTH       = 0.10
CAP_LLM          = 0.40
FIRST_TO_SHED    = "ambient_util"

# ── Data structures ────────────────────────────────────────────────────────────

@dataclass
class ModuleMetric:
    """One measurement snapshot for one module face."""
    face:            str
    timestamp:       float
    rate_per_min:    float   # calls / second * 60
    in_flight:       int     # concurrent requests right now
    util_ratio:      float   # 0.0–1.0 against its R_infinity baseline
    r_fair:          float   # PCC ratio: observed / infinity


@dataclass
class RROMSnapshot:
    """Full six-face snapshot."""
    captured_at:   str
    faces:         Dict[str, ModuleMetric] = field(default_factory=dict)
    overall_load:  float = 0.0    # weighted average across all faces
    pressure:      str   = "NORMAL"  # NORMAL | ELEVATED | HIGH | CRITICAL
    shed_candidate: str  = ""     # which face to shed first

    def to_dict(self):
        return {
            "captured_at":   self.captured_at,
            "overall_load":  round(self.overall_load, 3),
            "pressure":      self.pressure,
            "shed_candidate":self.shed_candidate,
            "faces":         {k: asdict(v) for k, v in self.faces.items()},
        }


# ── Counters (thread-safe) ─────────────────────────────────────────────────────

class RateCounter:
    """Rolling window rate counter."""
    def __init__(self, window: float = WINDOW_SECONDS):
        self._window  = window
        self._events: deque = deque()
        self._lock    = threading.Lock()

    def hit(self):
        now = time.monotonic()
        with self._lock:
            self._events.append(now)
            cutoff = now - self._window
            while self._events and self._events[0] < cutoff:
                self._events.popleft()

    @property
    def rate_per_min(self) -> float:
        now = time.monotonic()
        with self._lock:
            cutoff = now - self._window
            while self._events and self._events[0] < cutoff:
                self._events.popleft()
            return len(self._events) * (60.0 / self._window)


class InFlightCounter:
    """Thread-safe in-flight request counter."""
    def __init__(self):
        self._count = 0
        self._lock  = threading.Lock()

    def inc(self):
        with self._lock:
            self._count += 1

    def dec(self):
        with self._lock:
            self._count = max(0, self._count - 1)

    @property
    def value(self) -> int:
        return self._count


# ── R_infinity baselines (sustainable capacity per face) ────────────────────────
# These are the "demand_infinity" values — calibrated from server specs.
# CX31: 4vCPU / 8GB RAM / single Uvicorn worker / 31 threads
# Tuned conservatively — Phase 2 will refine from actual measurement.

R_INFINITY: Dict[str, float] = {
    "shield_util":        120.0,  # shield checks/min at full load
    "auth_util":           80.0,  # auth validations/min
    "llm_demand":           4.0,  # concurrent LLM calls (in-flight)
    "convergence_demand":  30.0,  # convergence analyze/min
    "model_team_util":      2.0,  # concurrent deliberations
    "ambient_util":        10.0,  # ambient cycles/min
}

# ── RROM Engine ────────────────────────────────────────────────────────────────

class RROMEngine:
    """
    Phase 1: measurement + PCC ratio computation.
    Exposes counters for each module to call hit()/inc()/dec().
    Snapshots every SAMPLE_INTERVAL seconds.
    """

    def __init__(self):
        # Rate counters (calls per minute)
        self._rates: Dict[str, RateCounter] = {
            face: RateCounter() for face in R_INFINITY
        }
        # In-flight counters (concurrent)
        self._inflight: Dict[str, InFlightCounter] = {
            face: InFlightCounter() for face in R_INFINITY
        }
        # History
        self._history: deque = deque(maxlen=MAX_HISTORY)
        self._current: Optional[RROMSnapshot] = None
        # Background sampler
        self._running = False
        self._thread:  Optional[threading.Thread] = None

    def start(self):
        """Start background measurement loop."""
        if self._running:
            return
        self._running = True
        self._thread  = threading.Thread(
            target=self._sample_loop, daemon=True, name="rrom-sampler"
        )
        self._thread.start()
        logger.info("PATCH-098: RROM Phase 1 sampler started (interval=%ds)", SAMPLE_INTERVAL)

    def stop(self):
        self._running = False

    # ── Public API for modules to call ──────────────────────────────────────

    def hit(self, face: str):
        """Record one request on a rate-based face."""
        if face in self._rates:
            self._rates[face].hit()

    def enter(self, face: str):
        """Record start of an in-flight operation."""
        if face in self._inflight:
            self._inflight[face].inc()
            if face in self._rates:
                self._rates[face].hit()

    def exit(self, face: str):
        """Record end of an in-flight operation."""
        if face in self._inflight:
            self._inflight[face].dec()

    # ── Snapshot logic ───────────────────────────────────────────────────────

    def _sample_loop(self):
        while self._running:
            try:
                snap = self._take_snapshot()
                self._history.append(snap)
                self._current = snap
            except Exception as exc:
                logger.warning("RROM sampler error: %s", exc)
            time.sleep(SAMPLE_INTERVAL)

    def _take_snapshot(self) -> RROMSnapshot:
        faces: Dict[str, ModuleMetric] = {}
        for face, r_inf in R_INFINITY.items():
            rate = self._rates[face].rate_per_min
            inf  = self._inflight[face].value
            # For in-flight faces (llm, model_team), util = inflight / R_infinity
            # For rate faces, util = rate / R_infinity
            if face in ("llm_demand", "model_team_util"):
                util  = min(1.0, inf / max(r_inf, 1))
                r_fair= round(util, 4)
            else:
                util  = min(1.0, rate / max(r_inf, 1))
                r_fair= round(util, 4)
            faces[face] = ModuleMetric(
                face         = face,
                timestamp    = time.monotonic(),
                rate_per_min = round(rate, 2),
                in_flight    = inf,
                util_ratio   = round(util, 4),
                r_fair       = r_fair,
            )
        # PATCH-102: inject hardware_health face from HardwareTelemetryEngine
        try:
            from src.hardware_telemetry import hardware_telemetry as _hw
            _hw_summary = _hw.summary()
            # util_ratio = 1 - health_score (0 = healthy, 1 = critical)
            _hw_util = round(1.0 - _hw_summary.get("health_score", 0.8), 4)
            faces["hardware_health"] = ModuleMetric(
                face         = "hardware_health",
                timestamp    = time.monotonic(),
                rate_per_min = 0.0,
                in_flight    = 0,
                util_ratio   = _hw_util,
                r_fair       = _hw_util,
            )
        except Exception as _hw_exc:
            logger.debug("RROM hardware face error (non-blocking): %s", _hw_exc)

        # PATCH-103: inject world_pressure face from WorldStateEngine
        try:
            from src.world_state_engine import world_state as _wse
            _wse_summary = _wse.summary()
            _world_util = round(_wse_summary.get("world_pressure", 0.5), 4)
            faces["world_pressure"] = ModuleMetric(
                face         = "world_pressure",
                timestamp    = time.monotonic(),
                rate_per_min = 0.0,
                in_flight    = 0,
                util_ratio   = _world_util,
                r_fair       = _world_util,
            )
        except Exception as _wse_exc:
            logger.debug("RROM world face error (non-blocking): %s", _wse_exc)

        overall = sum(m.util_ratio for m in faces.values()) / len(faces)
        # Pressure classification
        if overall < 0.3:
            pressure = "NORMAL"
        elif overall < 0.55:
            pressure = "ELEVATED"
        elif overall < 0.75:
            pressure = "HIGH"
        else:
            pressure = "CRITICAL"

        return RROMSnapshot(
            captured_at    = datetime.now(timezone.utc).isoformat(),
            faces          = faces,
            overall_load   = round(overall, 4),
            pressure       = pressure,
            shed_candidate = FIRST_TO_SHED,
        )

    # ── Query ────────────────────────────────────────────────────────────────

    def current_snapshot(self) -> Optional[Dict]:
        if self._current:
            return self._current.to_dict()
        return None

    def history(self, last_n: int = 12) -> List[Dict]:
        return [s.to_dict() for s in list(self._history)[-last_n:]]

    def face_status(self, face: str) -> Dict:
        if not self._current or face not in self._current.faces:
            return {"error": f"Face {face} not in snapshot"}
        m = self._current.faces[face]
        r_inf = R_INFINITY.get(face, 1.0)
        return {
            "face":         face,
            "rate_per_min": m.rate_per_min,
            "in_flight":    m.in_flight,
            "util_ratio":   m.util_ratio,
            "r_fair":       m.r_fair,
            "r_infinity":   r_inf,
            "pressure":     self._current.pressure,
            "floor_met":    self._check_floor(face, m),
        }

    def _check_floor(self, face: str, m: ModuleMetric) -> Optional[bool]:
        """Phase 1: report whether ethical floor would be met (no enforcement yet)."""
        if face == "shield_util":
            return m.util_ratio >= FLOOR_SHIELD
        if face == "auth_util":
            return m.util_ratio >= FLOOR_AUTH
        if face == "llm_demand":
            return m.util_ratio <= CAP_LLM
        return None  # no floor defined for this face


    def enforce(self) -> Dict[str, Any]:
        """
        PATCH-103e: RROM Phase 2 — Budget enforcement.

        Phase 1 (existing): measure and report.
        Phase 2 (this):     act on violations.

        Enforcement actions (in order of severity):
          1. WARN     — face approaching ceiling, log alert
          2. THROTTLE — face at ceiling, set shed_candidate flag
          3. BLOCK    — Shield Wall or Auth below ethical floor → raise alarm
          4. CASCADE  — overall_load > 0.85 → begin ambient task shedding

        Returns enforcement_report: what actions were taken this cycle.

        Engineering Principle 9: Hardening.
          - Never enforces Shield Wall or Auth downward (hard floors always protected)
          - Enforcement is advisory for most faces (logs + flags, no hard kills)
          - CASCADE only sheds faces listed in FIRST_TO_SHED
          - All enforcement events logged for audit

        PATCH: 103e
        """
        if not self._current:
            return {"status": "no_snapshot", "actions": []}

        snap = self._current
        actions: List[Dict[str, Any]] = []
        enforcement_status = "NOMINAL"

        for face, metric in snap.faces.items():
            util   = metric.util_ratio
            r_inf  = R_INFINITY.get(face, 1.0)
            r_fair = metric.r_fair

            # ── Shield Wall: floor check (must stay >= FLOOR_SHIELD) ─────
            if face == "shield_util":
                if util < FLOOR_SHIELD and util > 0.0:
                    actions.append({
                        "face": face, "action": "BLOCK",
                        "reason": f"Shield Wall below ethical floor ({util:.3f} < {FLOOR_SHIELD})",
                        "severity": "CRITICAL",
                    })
                    enforcement_status = "CRITICAL"
                    logger.critical("RROM ENFORCE: Shield Wall below floor — %s < %s", util, FLOOR_SHIELD)

            # ── Auth: floor check ────────────────────────────────────────
            elif face == "auth_util":
                if util < FLOOR_AUTH and util > 0.0:
                    actions.append({
                        "face": face, "action": "WARN",
                        "reason": f"Auth below ethical floor ({util:.3f} < {FLOOR_AUTH})",
                        "severity": "HIGH",
                    })
                    if enforcement_status == "NOMINAL":
                        enforcement_status = "DEGRADED"

            # ── LLM: cap check ───────────────────────────────────────────
            elif face == "llm_demand":
                if util > CAP_LLM:
                    actions.append({
                        "face": face, "action": "THROTTLE",
                        "reason": f"LLM demand above cap ({util:.3f} > {CAP_LLM})",
                        "severity": "MEDIUM",
                        "shed_candidate": FIRST_TO_SHED,
                    })
                    if enforcement_status == "NOMINAL":
                        enforcement_status = "THROTTLED"

            # ── Hardware/World: high pressure warning ────────────────────
            elif face in ("hardware_health", "world_pressure"):
                if util > 0.75:
                    actions.append({
                        "face": face, "action": "WARN",
                        "reason": f"{face} pressure high ({util:.3f}) — consider shedding ambient tasks",
                        "severity": "MEDIUM",
                    })

            # ── Generic: approaching ceiling ─────────────────────────────
            else:
                if util > 0.80 and face != FIRST_TO_SHED:
                    actions.append({
                        "face": face, "action": "WARN",
                        "reason": f"{face} at {util:.0%} utilization",
                        "severity": "LOW",
                    })

        # ── CASCADE: overall load critical ───────────────────────────────
        if snap.overall_load > 0.85:
            actions.append({
                "face": FIRST_TO_SHED, "action": "CASCADE",
                "reason": f"Overall RROM load critical ({snap.overall_load:.3f}) — shedding {FIRST_TO_SHED}",
                "severity": "HIGH",
            })
            enforcement_status = "CASCADE"
            logger.warning("RROM CASCADE: shedding %s (load=%.3f)", FIRST_TO_SHED, snap.overall_load)

        report = {
            "status":       enforcement_status,
            "enforced_at":  datetime.now(timezone.utc).isoformat(),
            "overall_load": snap.overall_load,
            "pressure":     snap.pressure,
            "actions":      actions,
            "action_count": len(actions),
        }
        if actions:
            logger.info("RROM enforce: %s — %d actions", enforcement_status, len(actions))
        return report


# Singleton — started at module import
rrom = RROMEngine()
rrom.start()
