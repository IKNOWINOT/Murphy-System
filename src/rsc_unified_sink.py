"""
RSC Unified Sink — PATCH-077a
Fan-in aggregator: every wired module streams its state into one RSC sink.
The RSC computes S(t) in real-time on every signal arrival.

Architecture:
  Sources → (daemon threads, each on own interval) → RSCSink._state dict
  RSCSink → recomputes S(t) on every update → notifies SSE subscribers
  SSE subscribers → /api/rsc/stream (live S(t) feed)
  S(t) < 0.70 → CONSTRAIN mode (blocks effectors)
  S(t) > 0.85 → EXPAND mode (enables expansion)

State variable mapping (all normalized to [0,1]):
  A_t: active agents + tasks   (max_norm=100)
  G_t: active gates + violations (max_norm=1000)
  E_t: entropy: LCM contradictions + code circular_deps (max_norm=10)
  C_t: mean confidence from CE + LCM (already [0,1])
  M_t: failure pressure: gaps + proposals + errors (tanh-normalized)

RSC formula (from stability_score.py):
  R_t = α·A_t + β·G_t + γ·E_t + ε·M_t − δ·C_t
  S_t = 1 / (1 + R_t)   (S_MIN=0.70, S_EXPAND=0.85)
"""
from __future__ import annotations

import asyncio
import logging
import math
import threading
import time
import urllib.request as _ur
import json
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Deque, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

# ── RSC coefficients (from RecursionEnergyCoefficients defaults) ──────────────
_ALPHA   = 0.3   # agent weight
_BETA    = 0.2   # gate weight
_GAMMA   = 0.25  # entropy weight
_EPSILON = 0.15  # failure pressure weight
_DELTA   = 0.10  # confidence damping (negative: higher conf → lower R_t)

_S_MIN    = 0.70   # stability floor
_S_EXPAND = 0.85   # expansion threshold

_BASE = "http://127.0.0.1:8000"


# ── Mode ──────────────────────────────────────────────────────────────────────
class RSCMode:
    CONSTRAIN = "constrain"   # S_t < 0.70
    NOMINAL   = "nominal"     # 0.70 ≤ S_t < 0.85
    EXPAND    = "expand"      # S_t ≥ 0.85


@dataclass
class RSCReading:
    s_t: float
    r_t: float
    mode: str
    a_t: float
    g_t: float
    e_t: float
    c_t: float
    m_t: float
    ts: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "s_t": round(self.s_t, 4),
            "r_t": round(self.r_t, 4),
            "mode": self.mode,
            "variables": {
                "A_t": round(self.a_t, 4),
                "G_t": round(self.g_t, 4),
                "E_t": round(self.e_t, 4),
                "C_t": round(self.c_t, 4),
                "M_t": round(self.m_t, 4),
            },
            "ts": self.ts,
            "stable": self.s_t >= _S_MIN,
            "expand_ready": self.s_t >= _S_EXPAND,
        }


class RSCSink:
    """Thread-safe fan-in aggregator. Any source can update any variable."""

    def __init__(self):
        self._lock = threading.Lock()
        self._state: Dict[str, float] = {
            "agents": 0.0,      # raw active agent count
            "tasks": 0.0,       # raw active task count
            "gates": 0.0,       # raw active gate count
            "violations": 0.0,  # compliance violations
            "contradictions": 0.0,  # ambient signal contradictions
            "circular_deps": 0.0,   # code circular dependencies
            "confidence": 0.85,     # mean confidence score (default healthy)
            "gaps": 0.0,            # self-fix gap count
            "proposals": 0.0,       # repair proposals
            "errors": 0.0,          # recent error count
            "parse_errors": 0.0,    # code parse errors from introspection
        }
        self._history: Deque[RSCReading] = deque(maxlen=500)
        self._current: Optional[RSCReading] = None
        self._subscribers: List[asyncio.Queue] = []
        self._sub_lock = threading.Lock()
        self._update_event = threading.Event()

    def update(self, **kwargs: float) -> RSCReading:
        """Update one or more state variables. Recomputes S(t) immediately."""
        with self._lock:
            for k, v in kwargs.items():
                if k in self._state:
                    self._state[k] = float(v)
            reading = self._compute()
            self._history.appendleft(reading)
            self._current = reading
        # Notify SSE subscribers (non-blocking)
        self._notify(reading)
        self._update_event.set()
        return reading

    def get(self) -> Optional[RSCReading]:
        with self._lock:
            return self._current

    def get_history(self, n: int = 50) -> List[Dict]:
        with self._lock:
            return [r.to_dict() for r in list(self._history)[:n]]

    def subscribe(self, q: asyncio.Queue) -> None:
        with self._sub_lock:
            self._subscribers.append(q)

    def unsubscribe(self, q: asyncio.Queue) -> None:
        with self._sub_lock:
            self._subscribers = [s for s in self._subscribers if s is not q]

    def _notify(self, reading: RSCReading) -> None:
        with self._sub_lock:
            dead = []
            for q in self._subscribers:
                try:
                    q.put_nowait(reading.to_dict())
                except Exception:
                    dead.append(q)
            for d in dead:
                self._subscribers.remove(d)

    def _compute(self) -> RSCReading:
        s = self._state
        # Normalize
        A_t = min((s["agents"] + s["tasks"]) / 100.0, 1.0)
        G_t = min((s["gates"] + s["violations"]) / 1000.0, 1.0)
        E_t = min((s["contradictions"] + s["circular_deps"] + s["parse_errors"]) / 10.0, 1.0)
        C_t = max(0.0, min(s["confidence"], 1.0))
        # M_t: tanh normalization — unbounded input, bounded output
        raw_m = s["gaps"] + s["proposals"] + s["errors"]
        M_t = math.tanh(raw_m / 5.0)  # tanh(1)=0.76, tanh(2)=0.96

        R_t = _ALPHA*A_t + _BETA*G_t + _GAMMA*E_t + _EPSILON*M_t - _DELTA*C_t
        R_t = max(0.0, R_t)
        S_t = 1.0 / (1.0 + R_t)

        if S_t >= _S_EXPAND:
            mode = RSCMode.EXPAND
        elif S_t >= _S_MIN:
            mode = RSCMode.NOMINAL
        else:
            mode = RSCMode.CONSTRAIN

        return RSCReading(s_t=S_t, r_t=R_t, mode=mode,
                          a_t=A_t, g_t=G_t, e_t=E_t, c_t=C_t, m_t=M_t)


# ── Global singleton ──────────────────────────────────────────────────────────
_sink: Optional[RSCSink] = None
_sink_lock = threading.Lock()


def get_sink() -> RSCSink:
    global _sink
    with _sink_lock:
        if _sink is None:
            _sink = RSCSink()
            _sink.update()  # compute initial baseline
    return _sink


def push(source: str, **kwargs: float) -> RSCReading:
    """Push signal from any module. Thread-safe."""
    reading = get_sink().update(**kwargs)
    logger.debug("RSC signal from %s: S_t=%.3f mode=%s", source, reading.s_t, reading.mode)
    return reading


def check_gate(required_mode: str = RSCMode.NOMINAL) -> bool:
    """
    Check if current stability allows an operation.
    Use in recursive/effector modules to gate execution:
      if not rsc_unified_sink.check_gate(): return  # constrained
    """
    current = get_sink().get()
    if current is None:
        return True  # no data yet — allow by default
    if required_mode == RSCMode.EXPAND:
        return current.mode == RSCMode.EXPAND
    elif required_mode == RSCMode.NOMINAL:
        return current.mode in (RSCMode.NOMINAL, RSCMode.EXPAND)
    return True  # CONSTRAIN mode always passes check_gate(CONSTRAIN)


# ── Source adapters (daemon threads) ─────────────────────────────────────────

def _safe_get(endpoint: str, cookie: str = "", timeout: int = 8) -> Any:
    try:
        req = _ur.Request(f"{_BASE}{endpoint}")
        if cookie:
            req.add_header("Cookie", cookie)
        with _ur.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception as e:
        logger.debug("RSC adapter GET %s failed: %s", endpoint, e)
        return {}


def _founder_cookie() -> str:
    try:
        body = json.dumps({"email": "cpost@murphy.systems", "password": "Password1"}).encode()
        req = _ur.Request(f"{_BASE}/api/auth/login", data=body,
                          headers={"Content-Type": "application/json"}, method="POST")
        with _ur.urlopen(req, timeout=8) as r:
            d = json.loads(r.read())
        return f"murphy_session={d.get('session_token','')}"
    except Exception as e:
        logger.debug("RSC adapter login failed: %s", e)
        return ""


def _adapter_loop(name: str, interval: int, fn: Callable[[str], None]) -> None:
    """Generic adapter loop."""
    logger.info("RSC adapter started: %s (every %ds)", name, interval)
    cookie = ""
    cookie_ts = 0.0
    while True:
        try:
            # Refresh cookie every 15 minutes
            if time.time() - cookie_ts > 900:
                cookie = _founder_cookie()
                cookie_ts = time.time()
            fn(cookie)
        except Exception as e:
            logger.warning("RSC adapter %s error: %s", name, e)
        time.sleep(interval)


# Individual adapter functions

def _adapt_self_fix(cookie: str) -> None:
    d = _safe_get("/api/self-fix/status", cookie)
    gaps = float(d.get("gaps_found", d.get("open_gaps", 0)) or 0)
    push("self_fix", gaps=gaps)


def _adapt_confidence(cookie: str) -> None:
    d = _safe_get("/api/confidence/status", cookie)
    score = float(d.get("data", {}).get("mean_score", 0.85) or 0.85)
    push("confidence_engine", confidence=score)


def _adapt_swarm(cookie: str) -> None:
    d = _safe_get("/api/swarm/status", cookie)
    agents = float(d.get("active_agents", d.get("total_agents", 0)) or 0)
    push("swarm", agents=agents)


def _adapt_repair(cookie: str) -> None:
    d = _safe_get("/api/repair/proposals", cookie)
    proposals_list = d.get("proposals", [])
    push("repair", proposals=float(len(proposals_list)))


def _adapt_gate_synthesis(cookie: str) -> None:
    d = _safe_get("/api/gate-synthesis/health", cookie)
    gates = float(d.get("active_gates", d.get("gate_count", 0)) or 0)
    push("gate_synthesis", gates=gates)


def _adapt_lcm(cookie: str) -> None:
    d = _safe_get("/api/lcm/status", cookie)
    data = d.get("data", {})
    # LCM confidence from last run, queue depth as entropy proxy
    conf = float(data.get("last_confidence", 0.85) or 0.85)
    queue = float(data.get("queue_depth", data.get("pending", 0)) or 0)
    push("lcm", confidence=max(0.1, conf), contradictions=min(queue, 10.0))


def _adapt_ambient(cookie: str) -> None:
    d = _safe_get("/api/ambient/stats", cookie)
    total = float(d.get("total_signals", 0) or 0)
    # Use synthesis_count as proxy for contradiction detection
    synth = float(d.get("synthesis_count", 0) or 0)
    push("ambient", contradictions=max(0.0, total - synth * 5) / 10.0)


def _adapt_introspection(cookie: str) -> None:
    """Slow adapter — reads code health from self-introspection."""
    try:
        from src.self_introspection_module import IntrospectionEngine
        engine = IntrospectionEngine()
        snap = engine.get_health_snapshot() if engine._graph else {}
        if not snap:
            engine.scan_codebase("/opt/Murphy-System/src")
            snap = engine.get_health_snapshot()
        circular = float(len(snap.get("circular_dependencies", [])))
        parse_err = float(snap.get("parse_error_count", 0) or 0)
        push("introspection", circular_deps=circular, parse_errors=parse_err)
        logger.info("RSC introspection: circular_deps=%d parse_errors=%d", int(circular), int(parse_err))
    except Exception as e:
        logger.debug("RSC introspection adapter failed: %s", e)


def start_all_adapters() -> None:
    """Start all source adapter daemon threads."""
    adapters = [
        ("self_fix",       30,  _adapt_self_fix),
        ("confidence",     30,  _adapt_confidence),
        ("swarm",          30,  _adapt_swarm),
        ("repair",         60,  _adapt_repair),
        ("gate_synthesis", 60,  _adapt_gate_synthesis),
        ("lcm",            30,  _adapt_lcm),
        ("ambient",        60,  _adapt_ambient),
        ("introspection",  600, _adapt_introspection),  # full code scan every 10min
    ]
    for name, interval, fn in adapters:
        t = threading.Thread(
            target=_adapter_loop,
            args=(name, interval, fn),
            daemon=True,
            name=f"rsc-adapter-{name}",
        )
        t.start()
    logger.info("RSC: %d source adapters started", len(adapters))


# ── Effector enforcement (call from any recursive module) ─────────────────────

def enforce(op_name: str, required_mode: str = RSCMode.NOMINAL) -> Optional[str]:
    """
    Call at the top of any recursive/effector function.
    Returns None if allowed, or a reason string if blocked.

    Usage:
        blocked = rsc_unified_sink.enforce("self_modify")
        if blocked:
            return {"error": blocked}
    """
    current = get_sink().get()
    if current is None:
        return None  # no data — allow
    if current.mode == RSCMode.CONSTRAIN and required_mode != RSCMode.CONSTRAIN:
        msg = (f"RSC CONSTRAIN: S_t={current.s_t:.3f} < {_S_MIN} — "
               f"operation '{op_name}' blocked until system stabilises")
        logger.warning(msg)
        return msg
    if required_mode == RSCMode.EXPAND and current.mode != RSCMode.EXPAND:
        msg = (f"RSC EXPAND required: S_t={current.s_t:.3f} < {_S_EXPAND} — "
               f"operation '{op_name}' blocked")
        logger.warning(msg)
        return msg
    return None

# ── Resource budget helper ────────────────────────────────────────────────────

def resource_budget() -> Dict[str, Any]:
    """
    Return a resource envelope scaled to current S(t).
    Any module can call this to get its allowed resource limits.

    Returns dict with:
      max_tokens:   LLM token cap
      max_workers:  Thread pool worker cap
      loop_interval_multiplier: Scale factor for timed loops (1.0=normal, 2.0=half-rate)
      mode:         Current RSC mode string
      s_t:          Current stability score

    Usage:
        from src.rsc_unified_sink import resource_budget
        budget = resource_budget()
        pool_size = min(requested_size, budget["max_workers"])
    """
    current = get_sink().get()
    if current is None:
        # No data yet — full resources allowed
        return {"max_tokens": 131072, "max_workers": 8,
                "loop_interval_multiplier": 1.0, "mode": "unknown", "s_t": 1.0}

    if current.mode == RSCMode.CONSTRAIN:
        return {"max_tokens": 512,   "max_workers": 1, "loop_interval_multiplier": 2.0,
                "mode": current.mode, "s_t": current.s_t}
    elif current.mode == RSCMode.EXPAND:
        return {"max_tokens": 131072, "max_workers": 8, "loop_interval_multiplier": 1.0,
                "mode": current.mode, "s_t": current.s_t}
    else:  # NOMINAL
        return {"max_tokens": 2048,  "max_workers": 4, "loop_interval_multiplier": 1.0,
                "mode": current.mode, "s_t": current.s_t}

