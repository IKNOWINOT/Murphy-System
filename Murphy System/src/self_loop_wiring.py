# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Self-Loop Wiring for Murphy System.

Design Label: WIRE-001 — Self-Improvement Loop Startup Wiring
Owner: Platform Engineering
Dependencies:
  - EventBackbone          (event_backbone)
  - SelfImprovementEngine  (self_improvement_engine, ARCH-001)
  - SelfAutomationOrchestrator (self_automation_orchestrator, ARCH-002)
  - AutomationLoopConnector (automation_loop_connector, DEV-001)
  - HealthMonitor          (health_monitor, OBS-001)
  - SelfHealingCoordinator (self_healing_coordinator, OBS-004)
  - BugPatternDetector     (bug_pattern_detector, DEV-004)
  - event_backbone_client  (global backbone registration)

Implements Steps 1–3 of the "Murphy working on itself" activation plan:

  Step 1 — Startup wiring:
    Instantiates the core self-improvement subsystems with proper
    dependency injection and registers health checks.

  Step 2 — Periodic scheduler:
    ``SelfLoopScheduler`` daemon thread calls ``connector.run_cycle()``
    and ``health_monitor.check_all()`` on a configurable interval.

  Step 3 — Production integration:
    ``register_self_loop_routes(app)`` mounts two FastAPI endpoints:
      GET  /api/self-loop/status       — subsystem status snapshot
      POST /api/self-loop/trigger-cycle — manual cycle trigger

Public API::

    from self_loop_wiring import (
        wire_self_improvement_loop,
        shutdown_self_improvement_loop,
        register_self_loop_routes,
        SelfLoopScheduler,
    )

    # At startup:
    components = wire_self_improvement_loop()

    # In FastAPI app setup:
    register_self_loop_routes(app)

    # At shutdown:
    shutdown_self_improvement_loop()
"""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional dependency imports — each wrapped so missing modules degrade
# gracefully (log warning, continue without that subsystem).
# ---------------------------------------------------------------------------

try:
    from event_backbone import EventBackbone
    _BACKBONE_AVAILABLE = True
except Exception:  # pragma: no cover
    EventBackbone = None  # type: ignore[assignment,misc]
    _BACKBONE_AVAILABLE = False

try:
    from event_backbone_client import set_backbone as _set_backbone_client
    _CLIENT_AVAILABLE = True
except Exception:  # pragma: no cover
    _set_backbone_client = None  # type: ignore[assignment]
    _CLIENT_AVAILABLE = False

try:
    from persistence_manager import PersistenceManager
    _PM_AVAILABLE = True
except Exception:  # pragma: no cover
    PersistenceManager = None  # type: ignore[assignment,misc]
    _PM_AVAILABLE = False

try:
    from self_improvement_engine import SelfImprovementEngine
    _ENGINE_AVAILABLE = True
except Exception:  # pragma: no cover
    SelfImprovementEngine = None  # type: ignore[assignment,misc]
    _ENGINE_AVAILABLE = False

try:
    from self_automation_orchestrator import SelfAutomationOrchestrator
    _ORCHESTRATOR_AVAILABLE = True
except Exception:  # pragma: no cover
    SelfAutomationOrchestrator = None  # type: ignore[assignment,misc]
    _ORCHESTRATOR_AVAILABLE = False

try:
    from automation_loop_connector import AutomationLoopConnector
    _CONNECTOR_AVAILABLE = True
except Exception:  # pragma: no cover
    AutomationLoopConnector = None  # type: ignore[assignment,misc]
    _CONNECTOR_AVAILABLE = False

try:
    from health_monitor import HealthMonitor
    _MONITOR_AVAILABLE = True
except Exception:  # pragma: no cover
    HealthMonitor = None  # type: ignore[assignment,misc]
    _MONITOR_AVAILABLE = False

try:
    from self_healing_coordinator import SelfHealingCoordinator
    _COORDINATOR_AVAILABLE = True
except Exception:  # pragma: no cover
    SelfHealingCoordinator = None  # type: ignore[assignment,misc]
    _COORDINATOR_AVAILABLE = False

try:
    from bug_pattern_detector import BugPatternDetector
    _BUG_DETECTOR_AVAILABLE = True
except Exception:  # pragma: no cover
    BugPatternDetector = None  # type: ignore[assignment,misc]
    _BUG_DETECTOR_AVAILABLE = False

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_INTERVAL_SECONDS = 300  # 5 minutes
_ENV_INTERVAL_VAR = "MURPHY_SELF_LOOP_INTERVAL_SECONDS"

# ---------------------------------------------------------------------------
# Module-level state (protected by _state_lock)
# ---------------------------------------------------------------------------

_state_lock = threading.Lock()
_components: Dict[str, Any] = {}
_scheduler: Optional["SelfLoopScheduler"] = None


# ---------------------------------------------------------------------------
# SelfLoopScheduler
# ---------------------------------------------------------------------------

class SelfLoopScheduler:
    """Daemon thread that periodically runs the self-improvement cycle.

    Design Label: WIRE-001
    Owner: Platform Engineering

    Calls ``connector.run_cycle()`` every *interval_seconds* seconds and
    ``health_monitor.check_all()`` offset by half the interval so the two
    operations do not overlap.

    Usage::

        scheduler = SelfLoopScheduler(
            connector=connector,
            health_monitor=monitor,
            interval_seconds=300,
        )
        scheduler.start()
        # …
        scheduler.stop()
    """

    def __init__(
        self,
        connector: Any = None,
        health_monitor: Any = None,
        interval_seconds: Optional[float] = None,
    ) -> None:
        self._connector = connector
        self._health_monitor = health_monitor
        self._interval = float(
            interval_seconds
            if interval_seconds is not None
            else int(os.environ.get(_ENV_INTERVAL_VAR, _DEFAULT_INTERVAL_SECONDS))
        )
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._cycle_count = 0
        self._health_count = 0

    # ------------------------------------------------------------------
    # Public control
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the background scheduler daemon thread."""
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                logger.warning("SelfLoopScheduler already running — ignoring start()")
                return
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run,
                name="SelfLoopScheduler",
                daemon=True,
            )
            self._thread.start()
            logger.info(
                "SelfLoopScheduler started (interval=%.0fs)",
                self._interval,
            )

    def stop(self) -> None:
        """Signal the scheduler to stop and wait for the thread to exit."""
        self._stop_event.set()
        with self._lock:
            thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=max(self._interval / 10, 5.0))
        logger.info("SelfLoopScheduler stopped")

    @property
    def is_running(self) -> bool:
        """Return True if the scheduler thread is alive."""
        with self._lock:
            return self._thread is not None and self._thread.is_alive()

    def get_status(self) -> Dict[str, Any]:
        """Return scheduler status summary."""
        return {
            "running": self.is_running,
            "interval_seconds": self._interval,
            "cycle_count": self._cycle_count,
            "health_count": self._health_count,
            "connector_attached": self._connector is not None,
            "health_monitor_attached": self._health_monitor is not None,
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run(self) -> None:
        """Main scheduler loop."""
        half = self._interval / 2.0
        next_cycle = time.monotonic()
        next_health = time.monotonic() + half

        while not self._stop_event.is_set():
            now = time.monotonic()

            if now >= next_cycle:
                self._run_cycle()
                next_cycle = now + self._interval

            if now >= next_health:
                self._run_health_check()
                next_health = now + self._interval

            # Sleep in small increments so stop_event is checked promptly
            remaining = min(next_cycle, next_health) - time.monotonic()
            sleep_time = max(0.1, min(remaining, 1.0))
            self._stop_event.wait(timeout=sleep_time)

    def _run_cycle(self) -> None:
        """Call connector.run_cycle() and log the result."""
        if self._connector is None:
            return
        try:
            result = self._connector.run_cycle()
            self._cycle_count += 1
            logger.info(
                "SelfLoopScheduler cycle #%d complete: %s",
                self._cycle_count,
                result,
            )
        except Exception:
            logger.exception("SelfLoopScheduler: run_cycle() raised an exception")

    def _run_health_check(self) -> None:
        """Call health_monitor.check_all() and log the result."""
        if self._health_monitor is None:
            return
        try:
            report = self._health_monitor.check_all()
            self._health_count += 1
            logger.info(
                "SelfLoopScheduler health check #%d: system_status=%s",
                self._health_count,
                getattr(report, "system_status", report),
            )
        except Exception:
            logger.exception("SelfLoopScheduler: check_all() raised an exception")


# ---------------------------------------------------------------------------
# wire_self_improvement_loop
# ---------------------------------------------------------------------------

def wire_self_improvement_loop(
    persistence_manager: Any = None,
) -> Dict[str, Any]:
    """Instantiate and wire all self-improvement subsystems.

    Returns a dict with keys for each instantiated component.  Any subsystem
    whose module is missing is silently omitted and logged as a warning so
    the rest of the system continues to operate in a degraded mode.

    Components returned (when available):
      - ``backbone``     — EventBackbone singleton
      - ``engine``       — SelfImprovementEngine
      - ``orchestrator`` — SelfAutomationOrchestrator
      - ``connector``    — AutomationLoopConnector
      - ``health_monitor`` — HealthMonitor
      - ``coordinator``  — SelfHealingCoordinator
      - ``bug_detector`` — BugPatternDetector
      - ``scheduler``    — SelfLoopScheduler (already started)
    """
    global _components, _scheduler

    components: Dict[str, Any] = {}

    # 1. EventBackbone -------------------------------------------------------
    backbone = None
    if _BACKBONE_AVAILABLE:
        try:
            backbone = EventBackbone()
            components["backbone"] = backbone
            logger.info("WIRE-001: EventBackbone instantiated")
        except Exception:
            logger.warning("WIRE-001: Failed to instantiate EventBackbone", exc_info=True)
    else:
        logger.warning("WIRE-001: event_backbone module unavailable — skipping")

    # Register backbone singleton via event_backbone_client ----------------
    if backbone is not None and _CLIENT_AVAILABLE and _set_backbone_client is not None:
        try:
            _set_backbone_client(backbone)
            logger.info("WIRE-001: EventBackbone registered as global singleton")
        except Exception:
            logger.warning("WIRE-001: Failed to register EventBackbone singleton", exc_info=True)

    # 2. SelfImprovementEngine -----------------------------------------------
    engine = None
    if _ENGINE_AVAILABLE:
        try:
            engine = SelfImprovementEngine(persistence_manager=persistence_manager)
            components["engine"] = engine
            logger.info("WIRE-001: SelfImprovementEngine instantiated")
        except Exception:
            logger.warning("WIRE-001: Failed to instantiate SelfImprovementEngine", exc_info=True)
    else:
        logger.warning("WIRE-001: self_improvement_engine module unavailable — skipping")

    # 3. SelfAutomationOrchestrator ------------------------------------------
    orchestrator = None
    if _ORCHESTRATOR_AVAILABLE:
        try:
            orchestrator = SelfAutomationOrchestrator(
                persistence_manager=persistence_manager
            )
            components["orchestrator"] = orchestrator
            logger.info("WIRE-001: SelfAutomationOrchestrator instantiated")
        except Exception:
            logger.warning(
                "WIRE-001: Failed to instantiate SelfAutomationOrchestrator", exc_info=True
            )
    else:
        logger.warning("WIRE-001: self_automation_orchestrator module unavailable — skipping")

    # 4. AutomationLoopConnector ---------------------------------------------
    connector = None
    if _CONNECTOR_AVAILABLE:
        try:
            connector = AutomationLoopConnector(
                improvement_engine=engine,
                orchestrator=orchestrator,
                event_backbone=backbone,
            )
            components["connector"] = connector
            logger.info("WIRE-001: AutomationLoopConnector instantiated and wired")
        except Exception:
            logger.warning(
                "WIRE-001: Failed to instantiate AutomationLoopConnector", exc_info=True
            )
    else:
        logger.warning("WIRE-001: automation_loop_connector module unavailable — skipping")

    # 5. HealthMonitor -------------------------------------------------------
    health_monitor = None
    if _MONITOR_AVAILABLE:
        try:
            health_monitor = HealthMonitor(event_backbone=backbone)
            components["health_monitor"] = health_monitor
            logger.info("WIRE-001: HealthMonitor instantiated")
        except Exception:
            logger.warning("WIRE-001: Failed to instantiate HealthMonitor", exc_info=True)
    else:
        logger.warning("WIRE-001: health_monitor module unavailable — skipping")

    # 6. SelfHealingCoordinator ----------------------------------------------
    coordinator = None
    if _COORDINATOR_AVAILABLE:
        try:
            coordinator = SelfHealingCoordinator(event_backbone=backbone)
            components["coordinator"] = coordinator
            logger.info("WIRE-001: SelfHealingCoordinator instantiated")
        except Exception:
            logger.warning(
                "WIRE-001: Failed to instantiate SelfHealingCoordinator", exc_info=True
            )
    else:
        logger.warning("WIRE-001: self_healing_coordinator module unavailable — skipping")

    # 7. BugPatternDetector --------------------------------------------------
    if _BUG_DETECTOR_AVAILABLE:
        try:
            bug_detector = BugPatternDetector(
                improvement_engine=engine,
                event_backbone=backbone,
            )
            components["bug_detector"] = bug_detector
            logger.info("WIRE-001: BugPatternDetector instantiated")
        except Exception:
            logger.warning("WIRE-001: Failed to instantiate BugPatternDetector", exc_info=True)
    else:
        logger.warning("WIRE-001: bug_pattern_detector module unavailable — skipping")

    # 8. Register health checks with HealthMonitor ---------------------------
    if health_monitor is not None:
        _register_health_checks(
            health_monitor=health_monitor,
            engine=engine,
            orchestrator=orchestrator,
            connector=connector,
            coordinator=coordinator,
        )

    # 9. Start the scheduler -------------------------------------------------
    scheduler = SelfLoopScheduler(
        connector=connector,
        health_monitor=health_monitor,
    )
    scheduler.start()
    components["scheduler"] = scheduler

    # 10. Persist to module-level state for route handlers -------------------
    with _state_lock:
        _components = components
        _scheduler = scheduler

    logger.info(
        "WIRE-001: self-improvement loop wired (%d subsystems active)",
        len(components),
    )
    return components


def _register_health_checks(
    health_monitor: Any,
    engine: Any,
    orchestrator: Any,
    connector: Any,
    coordinator: Any,
) -> None:
    """Register a get_status() health check for each wired subsystem."""
    checks = {
        "self_improvement_engine": engine,
        "self_automation_orchestrator": orchestrator,
        "automation_loop_connector": connector,
        "self_healing_coordinator": coordinator,
    }
    for name, component in checks.items():
        if component is None:
            continue
        get_status = getattr(component, "get_status", None)
        if get_status is None:
            logger.warning("WIRE-001: %s has no get_status() — skipping health check", name)
            continue
        try:
            health_monitor.register(name, get_status)
            logger.info("WIRE-001: Registered health check for %s", name)
        except Exception:
            logger.warning(
                "WIRE-001: Failed to register health check for %s", name, exc_info=True
            )


# ---------------------------------------------------------------------------
# shutdown_self_improvement_loop
# ---------------------------------------------------------------------------

def shutdown_self_improvement_loop() -> None:
    """Stop the scheduler and clean up module-level state."""
    global _components, _scheduler

    with _state_lock:
        scheduler = _scheduler
        _scheduler = None
        _components = {}

    if scheduler is not None:
        try:
            scheduler.stop()
            logger.info("WIRE-001: SelfLoopScheduler stopped cleanly")
        except Exception:
            logger.warning("WIRE-001: Error stopping SelfLoopScheduler", exc_info=True)


# ---------------------------------------------------------------------------
# register_self_loop_routes  (FastAPI integration)
# ---------------------------------------------------------------------------

def register_self_loop_routes(app: Any) -> None:
    """Mount self-loop status and trigger endpoints on a FastAPI *app*.

    Routes added:
      GET  /api/self-loop/status        — status snapshot of all subsystems
      POST /api/self-loop/trigger-cycle — manually triggers one run_cycle()
    """
    try:
        from fastapi.responses import JSONResponse
    except ImportError:  # pragma: no cover
        logger.warning("WIRE-001: FastAPI not available — cannot register self-loop routes")
        return

    @app.get("/api/self-loop/status")
    async def self_loop_status() -> JSONResponse:  # type: ignore[return]
        """Return the status of all self-improvement subsystems."""
        with _state_lock:
            comps = dict(_components)

        status: Dict[str, Any] = {}
        for name, component in comps.items():
            get_status = getattr(component, "get_status", None)
            if get_status is not None:
                try:
                    status[name] = get_status()
                except Exception as exc:
                    status[name] = {"error": str(exc)}
            else:
                status[name] = {"present": True}

        return JSONResponse(
            content={
                "success": True,
                "subsystems_active": len(comps),
                "status": status,
            }
        )

    @app.post("/api/self-loop/trigger-cycle")
    async def self_loop_trigger_cycle() -> JSONResponse:  # type: ignore[return]
        """Manually trigger one connector.run_cycle() run."""
        with _state_lock:
            connector = _components.get("connector")

        if connector is None:
            return JSONResponse(
                status_code=503,
                content={
                    "success": False,
                    "error": "AutomationLoopConnector not available",
                },
            )

        try:
            result = connector.run_cycle()
            return JSONResponse(
                content={
                    "success": True,
                    "result": str(result),
                }
            )
        except Exception as exc:
            logger.exception("WIRE-001: trigger-cycle failed")
            return JSONResponse(
                status_code=500,
                content={"success": False, "error": str(exc)},
            )

    logger.info("WIRE-001: self-loop routes registered on app")
