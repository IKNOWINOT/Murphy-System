"""
Automation Safeguard Engine — Murphy System

Design Label: AUTO-SAFE-001
Owner: Platform Engineering
Copyright © 2020 Inoni Limited Liability Company
License: BSL 1.1

Provides composable guard primitives that solve the 7 most common automation
failure modes documented across industrial and distributed-systems literature:

  1. RunawayLoopGuard         — hard iteration cap + wall-clock timeout kill switch
  2. EventStormSuppressor     — sliding-window rate + debounce (prevent event floods)
  3. FeedbackOscillationDetector — sign-change tracking to catch control oscillation
  4. CascadeBreaker           — dependency-aware circuit breaker with blast-radius cap
  5. IdempotencyGuard         — SHA-256 content-hash dedup with TTL eviction
  6. TrackingAccumulationWatcher — monitors collection growth, alerts when unbounded
  7. DeadlockDetector         — wait-for graph cycle detection + lock-hold timeout

All guards are:
  - Thread-safe (RLock)
  - Composable — any guard can wrap any Murphy automation primitive
  - Observable — each has a get_status() → Dict[str, Any] method
  - Memory-safe — use capped_append / bounded dicts (CWE-770)
  - Lazy-import friendly — no hard deps outside stdlib

AutomationSafeguardEngine is the top-level orchestrator that combines all guards
and is registered as a Murphy module.

Usage::

    safeguard = AutomationSafeguardEngine()

    # Wrap a loop
    with safeguard.loop_guard("my_loop"):
        for item in long_list:
            safeguard.loop_guard("my_loop").tick()

    # Check an event before processing
    if safeguard.event_storm.allow("email_webhook"):
        process(event)

    # Check idempotency before executing an action
    if safeguard.idempotency.is_new(action_payload):
        execute(action_payload)

    # Full health check
    health = safeguard.check_all()
"""

from __future__ import annotations

import hashlib
import logging
import math
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_AUDIT_LOG = 2_000
_MAX_DEDUP_CACHE = 10_000
_MAX_OSCILLATION_HISTORY = 500
_MAX_GRAPH_NODES = 1_000

# ---------------------------------------------------------------------------
# Optional bounded append (mirrors Murphy convention)
# ---------------------------------------------------------------------------

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(lst: list, item: Any, max_size: int = 10_000) -> None:  # type: ignore[misc]
        if len(lst) >= max_size:
            del lst[: max_size // 10]
        lst.append(item)


# ---------------------------------------------------------------------------
# Shared data models
# ---------------------------------------------------------------------------

@dataclass
class SafeguardEvent:
    """An audit record from any guard."""
    guard_name: str
    event_type: str          # "blocked", "allowed", "alert", "reset", "open", "closed"
    detail: str
    ts: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "guard_name": self.guard_name,
            "event_type": self.event_type,
            "detail": self.detail,
            "ts": self.ts,
        }


# ---------------------------------------------------------------------------
# 1. RunawayLoopGuard
# ---------------------------------------------------------------------------

class RunawayLoopError(RuntimeError):
    """Raised when a loop exceeds its hard cap or wall-clock timeout."""


class RunawayLoopGuard:
    """Prevents runaway loops and infinite regeneration.

    Attaches to any iterating process.  Call :meth:`tick` on every iteration;
    the guard raises :class:`RunawayLoopError` when the hard caps are exceeded.

    Supports Python context-manager usage::

        guard = RunawayLoopGuard("proposal_gen", max_iterations=500, max_seconds=30.0)
        with guard:
            while has_more():
                process_next()
                guard.tick()
    """

    def __init__(
        self,
        name: str,
        max_iterations: int = 1_000,
        max_seconds: float = 60.0,
        on_runaway: Optional[Callable[[str, str], None]] = None,
    ) -> None:
        self.name = name
        self.max_iterations = max_iterations
        self.max_seconds = max_seconds
        self._on_runaway = on_runaway
        self._lock = threading.RLock()
        self._iteration_count: int = 0
        self._start_ts: float = 0.0
        self._active: bool = False
        self._trips: int = 0
        self._audit: List[SafeguardEvent] = []

    # -- Context manager interface ------------------------------------------

    def __enter__(self) -> "RunawayLoopGuard":
        self.start()
        return self

    def __exit__(self, *_: Any) -> None:
        self.stop()

    def start(self) -> None:
        """Mark the start of a new loop execution."""
        with self._lock:
            self._iteration_count = 0
            self._start_ts = time.monotonic()
            self._active = True

    def stop(self) -> None:
        """Mark the end of a loop execution."""
        with self._lock:
            self._active = False

    def tick(self) -> None:
        """Record one iteration.  Raises RunawayLoopError if caps are exceeded."""
        with self._lock:
            if not self._active:
                return
            self._iteration_count += 1

            if self._iteration_count > self.max_iterations:
                self._trip(
                    f"iteration cap exceeded: {self._iteration_count} > {self.max_iterations}"
                )

            elapsed = time.monotonic() - self._start_ts
            if elapsed > self.max_seconds:
                self._trip(
                    f"wall-clock timeout: {elapsed:.1f}s > {self.max_seconds}s"
                )

    def _trip(self, reason: str) -> None:
        """Internal: record trip and raise."""
        self._trips += 1
        self._active = False
        ev = SafeguardEvent(self.name, "blocked", f"RunawayLoop tripped: {reason}")
        capped_append(self._audit, ev, _MAX_AUDIT_LOG)
        logger.warning("RunawayLoopGuard[%s] tripped: %s", self.name, reason)
        if self._on_runaway:
            try:
                self._on_runaway(self.name, reason)
            except Exception:  # noqa: BLE001
                pass
        raise RunawayLoopError(f"[{self.name}] {reason}")

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "name": self.name,
                "active": self._active,
                "iteration_count": self._iteration_count,
                "max_iterations": self.max_iterations,
                "max_seconds": self.max_seconds,
                "trips": self._trips,
            }


# ---------------------------------------------------------------------------
# 2. EventStormSuppressor
# ---------------------------------------------------------------------------

class EventStormSuppressor:
    """Prevents event storms and event floods.

    Combines:
    - **Sliding-window rate limit** — max *max_per_window* events per *window_sec*
    - **Debounce** — identical event keys are suppressed within *debounce_sec*

    Usage::

        suppressor = EventStormSuppressor(max_per_window=100, window_sec=1.0)
        if suppressor.allow("email_webhook"):
            handle(event)
    """

    def __init__(
        self,
        name: str = "default",
        max_per_window: int = 100,
        window_sec: float = 1.0,
        debounce_sec: float = 0.1,
        on_storm: Optional[Callable[[str, str], None]] = None,
    ) -> None:
        self.name = name
        self.max_per_window = max_per_window
        self.window_sec = window_sec
        self.debounce_sec = debounce_sec
        self._on_storm = on_storm
        self._lock = threading.RLock()
        # Sliding window: deque of event timestamps
        self._timestamps: deque = deque()
        # Debounce: key → last_allowed_ts
        self._last_seen: Dict[str, float] = {}
        self._blocked_count: int = 0
        self._allowed_count: int = 0
        self._audit: List[SafeguardEvent] = []

    def allow(self, event_key: str = "") -> bool:
        """Return True if the event should be processed; False if suppressed."""
        now = time.monotonic()
        with self._lock:
            # Evict timestamps outside the sliding window
            cutoff = now - self.window_sec
            while self._timestamps and self._timestamps[0] < cutoff:
                self._timestamps.popleft()

            # Rate check
            if len(self._timestamps) >= self.max_per_window:
                self._blocked_count += 1
                detail = (
                    f"rate limit: {len(self._timestamps)}/{self.max_per_window} "
                    f"in {self.window_sec}s window"
                )
                ev = SafeguardEvent(self.name, "blocked", detail)
                capped_append(self._audit, ev, _MAX_AUDIT_LOG)
                if self._on_storm:
                    try:
                        self._on_storm(self.name, detail)
                    except Exception:  # noqa: BLE001
                        pass
                logger.debug("EventStormSuppressor[%s] blocked: %s", self.name, detail)
                return False

            # Debounce check (only when event_key is provided)
            if event_key:
                last = self._last_seen.get(event_key, 0.0)
                if now - last < self.debounce_sec:
                    self._blocked_count += 1
                    detail = f"debounce: key={event_key!r} within {self.debounce_sec}s"
                    capped_append(self._audit, SafeguardEvent(self.name, "blocked", detail), _MAX_AUDIT_LOG)
                    return False
                self._last_seen[event_key] = now
                # Bounded debounce dict
                if len(self._last_seen) > _MAX_DEDUP_CACHE:
                    # Remove oldest 10%
                    to_remove = sorted(self._last_seen, key=self._last_seen.__getitem__)
                    for k in to_remove[: _MAX_DEDUP_CACHE // 10]:
                        del self._last_seen[k]

            self._timestamps.append(now)
            self._allowed_count += 1
            return True

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "name": self.name,
                "max_per_window": self.max_per_window,
                "window_sec": self.window_sec,
                "debounce_sec": self.debounce_sec,
                "current_window_count": len(self._timestamps),
                "blocked_count": self._blocked_count,
                "allowed_count": self._allowed_count,
            }


# ---------------------------------------------------------------------------
# 3. FeedbackOscillationDetector
# ---------------------------------------------------------------------------

class FeedbackOscillationDetector:
    """Detects feedback oscillation in control/automation loops.

    Records a time series of numeric measurements and fires a callback when
    the signal oscillates more than *max_sign_changes* times in the last
    *window* samples — indicating the system is over-correcting.

    Usage::

        detector = FeedbackOscillationDetector("temperature_pid", window=20)
        detector.record(current_temp)
        if detector.is_oscillating():
            apply_damping()
    """

    def __init__(
        self,
        name: str = "default",
        window: int = 20,
        max_sign_changes: int = 6,
        on_oscillation: Optional[Callable[[str, float], None]] = None,
    ) -> None:
        self.name = name
        self.window = window
        self.max_sign_changes = max_sign_changes
        self._on_oscillation = on_oscillation
        self._lock = threading.RLock()
        self._history: deque = deque(maxlen=_MAX_OSCILLATION_HISTORY)
        self._oscillation_count: int = 0
        self._audit: List[SafeguardEvent] = []

    def record(self, value: float) -> None:
        """Record a new measurement."""
        with self._lock:
            self._history.append(float(value))
            if self.is_oscillating(locked=True):
                self._oscillation_count += 1
                osc_rate = self._sign_changes(locked=True)
                detail = f"oscillation detected: {osc_rate} sign changes in last {self.window} samples"
                capped_append(self._audit, SafeguardEvent(self.name, "alert", detail), _MAX_AUDIT_LOG)
                logger.warning("FeedbackOscillationDetector[%s]: %s", self.name, detail)
                if self._on_oscillation:
                    try:
                        self._on_oscillation(self.name, osc_rate)
                    except Exception:  # noqa: BLE001
                        pass

    def _sign_changes(self, locked: bool = False) -> float:
        """Return number of sign changes in the delta series over the window."""
        samples = list(self._history)[-self.window:]
        if len(samples) < 3:
            return 0.0
        deltas = [samples[i + 1] - samples[i] for i in range(len(samples) - 1)]
        changes = sum(
            1 for i in range(len(deltas) - 1)
            if deltas[i] * deltas[i + 1] < 0  # sign change
        )
        return float(changes)

    def is_oscillating(self, locked: bool = False) -> bool:
        """Return True if the current window exceeds the oscillation threshold."""
        if locked:
            return self._sign_changes(locked=True) > self.max_sign_changes
        with self._lock:
            return self._sign_changes(locked=True) > self.max_sign_changes

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "name": self.name,
                "window": self.window,
                "max_sign_changes": self.max_sign_changes,
                "history_length": len(self._history),
                "oscillating": self.is_oscillating(locked=True),
                "oscillation_trips": self._oscillation_count,
                "recent_sign_changes": self._sign_changes(locked=True),
            }


# ---------------------------------------------------------------------------
# 4. CascadeBreaker
# ---------------------------------------------------------------------------

class _CBState:
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CascadeBreaker:
    """Dependency-aware circuit breaker with blast-radius cap.

    Tracks failure rates per named *component*.  When a component's failure
    ratio exceeds *trip_ratio* within *window_sec*, its breaker opens and
    *all dependents* listed in the dependency graph are also opened (blast
    radius).  A hard cap (*max_open*) prevents the entire system from being
    tripped by a single cascading event.

    Usage::

        breaker = CascadeBreaker()
        breaker.register("stripe_api", depends_on=["billing_service"])
        breaker.record_failure("stripe_api")
        if breaker.is_open("billing_service"):
            use_fallback()
    """

    def __init__(
        self,
        name: str = "default",
        trip_ratio: float = 0.5,
        window_sec: float = 60.0,
        reset_sec: float = 30.0,
        max_open: int = 10,
        on_trip: Optional[Callable[[str, List[str]], None]] = None,
    ) -> None:
        self.name = name
        self.trip_ratio = trip_ratio
        self.window_sec = window_sec
        self.reset_sec = reset_sec
        self.max_open = max_open
        self._on_trip = on_trip
        self._lock = threading.RLock()
        # component → deque of (ts, success:bool)
        self._calls: Dict[str, deque] = {}
        # component → state
        self._states: Dict[str, str] = {}
        # component → ts when opened
        self._opened_at: Dict[str, float] = {}
        # dependency graph: component → set of dependents
        self._dependents: Dict[str, Set[str]] = {}
        self._audit: List[SafeguardEvent] = []

    def register(self, component: str, depends_on: Optional[List[str]] = None) -> None:
        """Register a component and its upstream dependencies."""
        with self._lock:
            if component not in self._calls:
                self._calls[component] = deque()
                self._states[component] = _CBState.CLOSED
            if depends_on:
                for dep in depends_on:
                    if dep not in self._calls:
                        self._calls[dep] = deque()
                        self._states[dep] = _CBState.CLOSED
                    # component depends on dep → dep has a downstream dependent = component
                    self._dependents.setdefault(dep, set()).add(component)

    def record_success(self, component: str) -> None:
        """Record a successful call for *component*."""
        self.register(component)
        with self._lock:
            now = time.monotonic()
            self._calls[component].append((now, True))
            self._evict(component, now)
            if self._states[component] == _CBState.HALF_OPEN:
                self._states[component] = _CBState.CLOSED
                capped_append(
                    self._audit,
                    SafeguardEvent(self.name, "closed", f"{component} recovered"),
                    _MAX_AUDIT_LOG,
                )

    def record_failure(self, component: str) -> None:
        """Record a failed call for *component*, possibly tripping the breaker."""
        self.register(component)
        with self._lock:
            now = time.monotonic()
            self._calls[component].append((now, False))
            self._evict(component, now)
            calls = list(self._calls[component])
            total = len(calls)
            failures = sum(1 for _, ok in calls if not ok)
            ratio = failures / max(total, 1)
            if ratio >= self.trip_ratio and self._states[component] != _CBState.OPEN:
                self._open(component, ratio)

    def _evict(self, component: str, now: float) -> None:
        dq = self._calls[component]
        cutoff = now - self.window_sec
        while dq and dq[0][0] < cutoff:
            dq.popleft()

    def _open(self, component: str, ratio: float) -> None:
        """Open the breaker for *component* and propagate to dependents."""
        opened: List[str] = []
        currently_open = sum(1 for s in self._states.values() if s == _CBState.OPEN)
        if currently_open >= self.max_open:
            logger.warning(
                "CascadeBreaker[%s]: max_open=%d reached, not opening more",
                self.name, self.max_open,
            )
            return

        self._states[component] = _CBState.OPEN
        self._opened_at[component] = time.monotonic()
        opened.append(component)
        detail = f"{component} opened (failure ratio={ratio:.2f})"
        capped_append(self._audit, SafeguardEvent(self.name, "open", detail), _MAX_AUDIT_LOG)
        logger.warning("CascadeBreaker[%s]: %s", self.name, detail)

        # Propagate to dependents (blast radius, respects max_open)
        for dep in self._dependents.get(component, set()):
            currently_open = sum(1 for s in self._states.values() if s == _CBState.OPEN)
            if currently_open >= self.max_open:
                break
            if self._states.get(dep, _CBState.CLOSED) != _CBState.OPEN:
                self._states[dep] = _CBState.OPEN
                self._opened_at[dep] = time.monotonic()
                opened.append(dep)
                capped_append(
                    self._audit,
                    SafeguardEvent(self.name, "open", f"{dep} cascade-opened from {component}"),
                    _MAX_AUDIT_LOG,
                )
                logger.warning("CascadeBreaker[%s]: %s cascade-opened", self.name, dep)

        if self._on_trip:
            try:
                self._on_trip(component, opened)
            except Exception:  # noqa: BLE001
                pass

    def is_open(self, component: str) -> bool:
        """Return True if the breaker for *component* is open."""
        with self._lock:
            now = time.monotonic()
            state = self._states.get(component, _CBState.CLOSED)
            if state == _CBState.OPEN:
                opened_at = self._opened_at.get(component, 0.0)
                if now - opened_at >= self.reset_sec:
                    self._states[component] = _CBState.HALF_OPEN
                    capped_append(
                        self._audit,
                        SafeguardEvent(self.name, "half_open", f"{component} entered half-open"),
                        _MAX_AUDIT_LOG,
                    )
                    return False  # Allow one probe
            return state == _CBState.OPEN

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "name": self.name,
                "trip_ratio": self.trip_ratio,
                "max_open": self.max_open,
                "components": {c: s for c, s in self._states.items()},
                "open_count": sum(1 for s in self._states.values() if s == _CBState.OPEN),
            }


# ---------------------------------------------------------------------------
# 5. IdempotencyGuard
# ---------------------------------------------------------------------------

class IdempotencyGuard:
    """Prevents duplicate/double-trigger execution via SHA-256 content hashing.

    Maintains a bounded cache of seen payload hashes with TTL expiry.
    Safe for concurrent use.

    Usage::

        guard = IdempotencyGuard(ttl_sec=300.0)
        if guard.is_new(event_payload):
            execute(event_payload)
        else:
            logger.info("Duplicate event suppressed")
    """

    def __init__(
        self,
        name: str = "default",
        ttl_sec: float = 300.0,
        max_cache: int = _MAX_DEDUP_CACHE,
    ) -> None:
        self.name = name
        self.ttl_sec = ttl_sec
        self.max_cache = max_cache
        self._lock = threading.RLock()
        # hash → expiry_ts
        self._seen: Dict[str, float] = {}
        self._blocked_count: int = 0
        self._allowed_count: int = 0
        self._audit: List[SafeguardEvent] = []

    @staticmethod
    def _hash(payload: Any) -> str:
        """Compute a stable SHA-256 hex digest of *payload*."""
        import json as _json
        try:
            raw = _json.dumps(payload, sort_keys=True, default=str)
        except Exception:  # noqa: BLE001
            raw = str(payload)
        return hashlib.sha256(raw.encode()).hexdigest()

    def is_new(self, payload: Any) -> bool:
        """Return True if this payload has NOT been seen within the TTL window."""
        digest = self._hash(payload)
        now = time.monotonic()
        with self._lock:
            self._evict(now)
            if digest in self._seen:
                self._blocked_count += 1
                detail = f"duplicate suppressed: hash={digest[:16]}…"
                capped_append(self._audit, SafeguardEvent(self.name, "blocked", detail), _MAX_AUDIT_LOG)
                return False
            # New payload
            self._seen[digest] = now + self.ttl_sec
            self._allowed_count += 1
            return True

    def mark_seen(self, payload: Any) -> None:
        """Explicitly mark a payload as seen (without is_new check)."""
        digest = self._hash(payload)
        with self._lock:
            self._seen[digest] = time.monotonic() + self.ttl_sec

    def _evict(self, now: float) -> None:
        """Remove expired entries; also trim if over max_cache."""
        expired = [k for k, exp in self._seen.items() if exp <= now]
        for k in expired:
            del self._seen[k]
        if len(self._seen) >= self.max_cache:
            # Remove oldest 10% by earliest expiry
            sorted_keys = sorted(self._seen, key=self._seen.__getitem__)
            for k in sorted_keys[: self.max_cache // 10]:
                del self._seen[k]

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "name": self.name,
                "ttl_sec": self.ttl_sec,
                "cache_size": len(self._seen),
                "max_cache": self.max_cache,
                "blocked_count": self._blocked_count,
                "allowed_count": self._allowed_count,
            }


# ---------------------------------------------------------------------------
# 6. TrackingAccumulationWatcher
# ---------------------------------------------------------------------------

class TrackingAccumulationWatcher:
    """Detects unbounded collection growth (tracking accumulation / memory leaks).

    Registers named collections by a callable that returns their current size.
    On each :meth:`check` call it compares size to the previous sample;
    if a collection grows continuously for *alert_after_n_checks* consecutive
    checks beyond *growth_threshold* percent, it fires the alert callback.

    Usage::

        watcher = TrackingAccumulationWatcher()
        watcher.register("event_queue", lambda: len(event_queue))
        watcher.register("audit_log", lambda: len(self._audit_log), max_size=5000)
        watcher.check()   # Call periodically
    """

    def __init__(
        self,
        name: str = "default",
        growth_threshold_pct: float = 10.0,
        alert_after_n_checks: int = 3,
        on_accumulation: Optional[Callable[[str, str], None]] = None,
    ) -> None:
        self.name = name
        self.growth_threshold_pct = growth_threshold_pct
        self.alert_after_n_checks = alert_after_n_checks
        self._on_accumulation = on_accumulation
        self._lock = threading.RLock()
        # collection_name → (size_fn, max_size_or_None)
        self._collections: Dict[str, Tuple[Callable[[], int], Optional[int]]] = {}
        # collection_name → previous_size
        self._prev_sizes: Dict[str, int] = {}
        # collection_name → consecutive_growth_count
        self._growth_streak: Dict[str, int] = {}
        self._alerts: int = 0
        self._audit: List[SafeguardEvent] = []

    def register(
        self,
        collection_name: str,
        size_fn: Callable[[], int],
        max_size: Optional[int] = None,
    ) -> None:
        """Register a collection to monitor."""
        with self._lock:
            self._collections[collection_name] = (size_fn, max_size)
            self._prev_sizes[collection_name] = 0
            self._growth_streak[collection_name] = 0

    def check(self) -> List[str]:
        """Run one check pass.  Returns list of alert messages."""
        alerts: List[str] = []
        with self._lock:
            for cname, (size_fn, max_size) in list(self._collections.items()):
                try:
                    current = size_fn()
                except Exception as exc:  # noqa: BLE001
                    logger.debug("TrackingAccumulationWatcher size_fn error for %s: %s", cname, exc)
                    continue

                prev = self._prev_sizes.get(cname, 0)
                # Hard max check
                if max_size and current > max_size:
                    msg = (
                        f"{cname} exceeded max_size: {current} > {max_size}"
                    )
                    self._fire_alert(cname, msg)
                    alerts.append(msg)
                    self._prev_sizes[cname] = current
                    continue

                # Unbounded growth streak check
                if prev > 0:
                    growth_pct = (current - prev) / prev * 100.0
                    if growth_pct >= self.growth_threshold_pct:
                        self._growth_streak[cname] = self._growth_streak.get(cname, 0) + 1
                    else:
                        self._growth_streak[cname] = 0

                    if self._growth_streak[cname] >= self.alert_after_n_checks:
                        msg = (
                            f"{cname} unbounded growth: "
                            f"{prev} → {current} ({growth_pct:.1f}% over "
                            f"{self._growth_streak[cname]} consecutive checks)"
                        )
                        self._fire_alert(cname, msg)
                        alerts.append(msg)
                else:
                    self._growth_streak[cname] = 0

                self._prev_sizes[cname] = current
        return alerts

    def _fire_alert(self, cname: str, msg: str) -> None:
        self._alerts += 1
        capped_append(self._audit, SafeguardEvent(self.name, "alert", msg), _MAX_AUDIT_LOG)
        logger.warning("TrackingAccumulationWatcher[%s]: %s", self.name, msg)
        if self._on_accumulation:
            try:
                self._on_accumulation(cname, msg)
            except Exception:  # noqa: BLE001
                pass

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "name": self.name,
                "monitored_collections": list(self._collections.keys()),
                "current_sizes": {
                    n: self._prev_sizes.get(n, 0)
                    for n in self._collections
                },
                "growth_streaks": dict(self._growth_streak),
                "alerts_fired": self._alerts,
            }


# ---------------------------------------------------------------------------
# 7. DeadlockDetector
# ---------------------------------------------------------------------------

class DeadlockDetector:
    """Detects deadlocks and lock starvation.

    Uses a wait-for graph: each :meth:`acquire` call registers "holder holds
    lock, waiter is waiting for lock".  The detector finds cycles (deadlock)
    using DFS.  It also detects starvation: a waiter that has been waiting
    longer than *starvation_timeout_sec* is reported.

    Usage::

        detector = DeadlockDetector()
        detector.acquire("task_A", "shared_db_lock")
        # ... later
        detector.release("task_A", "shared_db_lock")
        if detector.has_deadlock():
            emergency_release_all()
    """

    def __init__(
        self,
        name: str = "default",
        starvation_timeout_sec: float = 30.0,
        on_deadlock: Optional[Callable[[str, List[str]], None]] = None,
    ) -> None:
        self.name = name
        self.starvation_timeout_sec = starvation_timeout_sec
        self._on_deadlock = on_deadlock
        self._lock = threading.RLock()
        # lock_name → holder_id (or None if free)
        self._held_by: Dict[str, Optional[str]] = {}
        # waiter_id → (lock_name, wait_start_ts)
        self._waiting: Dict[str, Tuple[str, float]] = {}
        self._deadlock_count: int = 0
        self._starvation_count: int = 0
        self._audit: List[SafeguardEvent] = []

    def acquire(self, holder_id: str, lock_name: str) -> None:
        """Signal that *holder_id* is waiting on (or has acquired) *lock_name*."""
        with self._lock:
            if self._held_by.get(lock_name) is None:
                # Lock is free — holder acquires immediately
                self._held_by[lock_name] = holder_id
                # Remove from waiting if was waiting
                self._waiting.pop(holder_id, None)
            else:
                # Lock is held — register as waiter
                self._waiting[holder_id] = (lock_name, time.monotonic())
                cycle = self._find_cycle()
                if cycle:
                    self._deadlock_count += 1
                    detail = f"deadlock cycle: {' → '.join(cycle)}"
                    capped_append(self._audit, SafeguardEvent(self.name, "alert", detail), _MAX_AUDIT_LOG)
                    logger.error("DeadlockDetector[%s]: %s", self.name, detail)
                    if self._on_deadlock:
                        try:
                            self._on_deadlock(self.name, cycle)
                        except Exception:  # noqa: BLE001
                            pass

    def release(self, holder_id: str, lock_name: str) -> None:
        """Signal that *holder_id* has released *lock_name*."""
        with self._lock:
            if self._held_by.get(lock_name) == holder_id:
                self._held_by[lock_name] = None

    def check_starvation(self) -> List[str]:
        """Return list of waiter IDs that have been waiting too long."""
        now = time.monotonic()
        starved: List[str] = []
        with self._lock:
            for waiter, (lock_name, wait_start) in list(self._waiting.items()):
                if now - wait_start > self.starvation_timeout_sec:
                    self._starvation_count += 1
                    msg = (
                        f"starvation: {waiter!r} waiting on {lock_name!r} "
                        f"for {now - wait_start:.1f}s > {self.starvation_timeout_sec}s"
                    )
                    capped_append(self._audit, SafeguardEvent(self.name, "alert", msg), _MAX_AUDIT_LOG)
                    logger.warning("DeadlockDetector[%s]: %s", self.name, msg)
                    starved.append(waiter)
        return starved

    def has_deadlock(self) -> bool:
        """Return True if the current wait-for graph contains a cycle."""
        with self._lock:
            return bool(self._find_cycle())

    def _find_cycle(self) -> List[str]:
        """DFS cycle detection on the wait-for graph."""
        # Build adjacency: waiter → holder (via the lock they're waiting on)
        graph: Dict[str, str] = {}
        for waiter, (lock_name, _) in self._waiting.items():
            holder = self._held_by.get(lock_name)
            if holder and holder != waiter:
                graph[waiter] = holder

        visited: Set[str] = set()
        path: List[str] = []

        def dfs(node: str) -> Optional[List[str]]:
            if node in path:
                idx = path.index(node)
                return path[idx:] + [node]
            if node in visited:
                return None
            visited.add(node)
            path.append(node)
            nxt = graph.get(node)
            if nxt:
                result = dfs(nxt)
                if result:
                    return result
            path.pop()
            return None

        for start in list(graph.keys()):
            if start not in visited:
                cycle = dfs(start)
                if cycle:
                    return cycle
        return []

    def emergency_release_all(self) -> int:
        """Clear all held locks and waiters.  Returns count of locks released."""
        with self._lock:
            count = sum(1 for v in self._held_by.values() if v is not None)
            self._held_by.clear()
            self._waiting.clear()
            capped_append(
                self._audit,
                SafeguardEvent(self.name, "reset", f"emergency_release_all: {count} locks cleared"),
                _MAX_AUDIT_LOG,
            )
            logger.warning("DeadlockDetector[%s]: emergency_release_all — %d locks cleared", self.name, count)
            return count

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "name": self.name,
                "held_locks": sum(1 for v in self._held_by.values() if v is not None),
                "waiters": len(self._waiting),
                "deadlock_count": self._deadlock_count,
                "starvation_count": self._starvation_count,
                "has_deadlock": self._find_cycle() != [],
            }


# ---------------------------------------------------------------------------
# AutomationSafeguardEngine — top-level orchestrator
# ---------------------------------------------------------------------------

class AutomationSafeguardEngine:
    """Unified safeguard engine — orchestrates all 7 guard primitives.

    Murphy module pattern: thread-safe, lazy init, ``get_status()``.

    Usage::

        engine = AutomationSafeguardEngine()
        engine.event_storm.allow("webhook_trigger")
        engine.idempotency.is_new(payload)
        engine.cascade_breaker.record_failure("stripe_api")
        health = engine.check_all()
    """

    MODULE_NAME = "automation_safeguard_engine"
    MODULE_VERSION = "1.0.0"

    def __init__(
        self,
        # RunawayLoopGuard defaults
        loop_max_iterations: int = 1_000,
        loop_max_seconds: float = 60.0,
        # EventStormSuppressor defaults
        storm_max_per_window: int = 200,
        storm_window_sec: float = 1.0,
        storm_debounce_sec: float = 0.05,
        # FeedbackOscillationDetector defaults
        osc_window: int = 20,
        osc_max_sign_changes: int = 6,
        # CascadeBreaker defaults
        cb_trip_ratio: float = 0.5,
        cb_window_sec: float = 60.0,
        cb_reset_sec: float = 30.0,
        cb_max_open: int = 10,
        # IdempotencyGuard defaults
        idem_ttl_sec: float = 300.0,
        # TrackingAccumulationWatcher defaults
        accum_growth_threshold_pct: float = 10.0,
        accum_alert_after_n_checks: int = 3,
        # DeadlockDetector defaults
        deadlock_starvation_timeout_sec: float = 30.0,
    ) -> None:
        self._lock = threading.RLock()
        self._started_at = time.time()

        # Named default guards
        self.loop_guards: Dict[str, RunawayLoopGuard] = {}
        self._loop_max_iterations = loop_max_iterations
        self._loop_max_seconds = loop_max_seconds

        self.event_storm = EventStormSuppressor(
            name="event_storm",
            max_per_window=storm_max_per_window,
            window_sec=storm_window_sec,
            debounce_sec=storm_debounce_sec,
        )
        self.oscillation = FeedbackOscillationDetector(
            name="oscillation",
            window=osc_window,
            max_sign_changes=osc_max_sign_changes,
        )
        self.cascade_breaker = CascadeBreaker(
            name="cascade_breaker",
            trip_ratio=cb_trip_ratio,
            window_sec=cb_window_sec,
            reset_sec=cb_reset_sec,
            max_open=cb_max_open,
        )
        self.idempotency = IdempotencyGuard(
            name="idempotency",
            ttl_sec=idem_ttl_sec,
        )
        self.accumulation_watcher = TrackingAccumulationWatcher(
            name="accumulation_watcher",
            growth_threshold_pct=accum_growth_threshold_pct,
            alert_after_n_checks=accum_alert_after_n_checks,
        )
        self.deadlock_detector = DeadlockDetector(
            name="deadlock_detector",
            starvation_timeout_sec=deadlock_starvation_timeout_sec,
        )

    # ------------------------------------------------------------------
    # Loop guard factory
    # ------------------------------------------------------------------

    def loop_guard(
        self,
        name: str,
        max_iterations: Optional[int] = None,
        max_seconds: Optional[float] = None,
    ) -> RunawayLoopGuard:
        """Return (or create) a named RunawayLoopGuard."""
        with self._lock:
            if name not in self.loop_guards:
                self.loop_guards[name] = RunawayLoopGuard(
                    name=name,
                    max_iterations=max_iterations or self._loop_max_iterations,
                    max_seconds=max_seconds or self._loop_max_seconds,
                )
            return self.loop_guards[name]

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    def check_all(self) -> Dict[str, Any]:
        """Run all guards' status checks and return a unified health dict."""
        accumulation_alerts = self.accumulation_watcher.check()
        starvation_alerts = self.deadlock_detector.check_starvation()
        cascade_status = self.cascade_breaker.get_status()
        oscillating = self.oscillation.is_oscillating()

        healthy = (
            not accumulation_alerts
            and not starvation_alerts
            and cascade_status["open_count"] == 0
            and not oscillating
            and not self.deadlock_detector.has_deadlock()
        )

        return {
            "module": self.MODULE_NAME,
            "healthy": healthy,
            "guards": {
                "event_storm": self.event_storm.get_status(),
                "oscillation": self.oscillation.get_status(),
                "cascade_breaker": cascade_status,
                "idempotency": self.idempotency.get_status(),
                "accumulation_watcher": self.accumulation_watcher.get_status(),
                "deadlock_detector": self.deadlock_detector.get_status(),
                "loop_guards": {
                    n: g.get_status() for n, g in self.loop_guards.items()
                },
            },
            "accumulation_alerts": accumulation_alerts,
            "starvation_alerts": starvation_alerts,
        }

    def get_status(self) -> Dict[str, Any]:
        """Murphy module-pattern status dict."""
        with self._lock:
            return {
                "module": self.MODULE_NAME,
                "version": self.MODULE_VERSION,
                "uptime_sec": round(time.time() - self._started_at, 1),
                "event_storm_blocked": self.event_storm.get_status()["blocked_count"],
                "cascade_open": self.cascade_breaker.get_status()["open_count"],
                "idempotency_blocked": self.idempotency.get_status()["blocked_count"],
                "loop_guard_trips": sum(
                    g.get_status()["trips"] for g in self.loop_guards.values()
                ),
                "deadlock_count": self.deadlock_detector.get_status()["deadlock_count"],
                "accumulation_alerts": self.accumulation_watcher.get_status()["alerts_fired"],
                "oscillation_trips": self.oscillation.get_status()["oscillation_trips"],
            }


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_ENGINE_SINGLETON: Optional[AutomationSafeguardEngine] = None
_ENGINE_LOCK = threading.Lock()


def get_engine() -> AutomationSafeguardEngine:
    """Return the module-level singleton AutomationSafeguardEngine."""
    global _ENGINE_SINGLETON
    with _ENGINE_LOCK:
        if _ENGINE_SINGLETON is None:
            _ENGINE_SINGLETON = AutomationSafeguardEngine()
    return _ENGINE_SINGLETON


def get_status() -> Dict[str, Any]:
    """Module-level get_status() following Murphy module pattern."""
    return get_engine().get_status()
