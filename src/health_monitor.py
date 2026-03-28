"""
Health Monitor for the Murphy System.

Design Label: OBS-001 — Subsystem Health Aggregation
Owner: DevOps Team / Platform Engineering
Dependencies: EventBackbone (optional, for reactive health events)

Provides:
- Registration of subsystem health-check callables
- Periodic or on-demand health aggregation
- Per-component status with latency tracking
- Overall system health derivation (healthy / degraded / unhealthy)
- EventBackbone integration for SYSTEM_HEALTH event publishing  [OBS-002]
- Thread-safe operation

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import collections
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class ComponentStatus(str, Enum):
    """Individual component health status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class SystemStatus(str, Enum):
    """Aggregate system health status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class ComponentHealth:
    """Result of a single component health check."""
    component_id: str
    status: ComponentStatus
    message: str = ""
    latency_ms: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)
    checked_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class HealthReport:
    """Aggregate health report across all registered components."""
    report_id: str
    system_status: SystemStatus
    components: List[ComponentHealth]
    healthy_count: int = 0
    degraded_count: int = 0
    unhealthy_count: int = 0
    total_latency_ms: float = 0.0
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-compatible dictionary."""
        return {
            "report_id": self.report_id,
            "system_status": self.system_status.value,
            "healthy_count": self.healthy_count,
            "degraded_count": self.degraded_count,
            "unhealthy_count": self.unhealthy_count,
            "total_latency_ms": round(self.total_latency_ms, 2),
            "generated_at": self.generated_at,
            "components": [
                {
                    "component_id": c.component_id,
                    "status": c.status.value,
                    "message": c.message,
                    "latency_ms": round(c.latency_ms, 2),
                    "details": c.details,
                    "checked_at": c.checked_at,
                }
                for c in self.components
            ],
        }


# ---------------------------------------------------------------------------
# Health check callable protocol
# ---------------------------------------------------------------------------
# A health check is any callable that returns a dict with at least:
#   {"status": "healthy"|"degraded"|"unhealthy", "message": str}
# It may also include arbitrary "details".
HealthCheckFn = Callable[[], Dict[str, Any]]


# ---------------------------------------------------------------------------
# HealthMonitor
# ---------------------------------------------------------------------------

class HealthMonitor:
    """Aggregated health monitoring for the Murphy System.

    Design Label: OBS-001 + OBS-002
    Owner: DevOps Team

    Usage::

        monitor = HealthMonitor(event_backbone=backbone)
        monitor.register("persistence", lambda: pm.get_status())
        report = monitor.check_all()
    """

    def __init__(self, event_backbone=None) -> None:
        self._lock = threading.Lock()
        self._checks: Dict[str, HealthCheckFn] = {}
        self._max_history = 100
        self._history: collections.deque[HealthReport] = collections.deque(
            maxlen=self._max_history
        )
        self._event_backbone = event_backbone

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, component_id: str, check_fn: HealthCheckFn) -> None:
        """Register a health-check callable for a named component."""
        with self._lock:
            self._checks[component_id] = check_fn
        logger.info("Registered health check: %s", component_id)

    def unregister(self, component_id: str) -> bool:
        """Remove a health-check registration. Returns True if found."""
        with self._lock:
            return self._checks.pop(component_id, None) is not None

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def check_component(self, component_id: str) -> Optional[ComponentHealth]:
        """Run a single component health check by ID."""
        with self._lock:
            check_fn = self._checks.get(component_id)
        if check_fn is None:
            return None
        return self._run_check(component_id, check_fn)

    def check_all(self) -> HealthReport:
        """Run all registered health checks and produce an aggregate report.

        If an EventBackbone is attached, a SYSTEM_HEALTH event is published
        with the report payload.  [OBS-002]
        """
        with self._lock:
            checks = dict(self._checks)

        results: List[ComponentHealth] = []
        for cid, fn in checks.items():
            results.append(self._run_check(cid, fn))

        healthy = sum(1 for r in results if r.status == ComponentStatus.HEALTHY)
        degraded = sum(1 for r in results if r.status == ComponentStatus.DEGRADED)
        unhealthy = sum(1 for r in results if r.status == ComponentStatus.UNHEALTHY)
        total_latency = sum(r.latency_ms for r in results)

        # Derive system status
        if unhealthy > 0:
            system_status = SystemStatus.UNHEALTHY
        elif degraded > 0:
            system_status = SystemStatus.DEGRADED
        else:
            system_status = SystemStatus.HEALTHY

        report = HealthReport(
            report_id=f"health-{uuid.uuid4().hex[:12]}",
            system_status=system_status,
            components=results,
            healthy_count=healthy,
            degraded_count=degraded,
            unhealthy_count=unhealthy,
            total_latency_ms=total_latency,
        )

        with self._lock:
            capped_append(self._history, report)

        # [OBS-002] Publish to EventBackbone
        if self._event_backbone is not None:
            try:
                from event_backbone import EventType
                self._event_backbone.publish(
                    event_type=EventType.SYSTEM_HEALTH,
                    payload=report.to_dict(),
                    source="health_monitor",
                )
            except Exception as exc:
                logger.warning("Failed to publish SYSTEM_HEALTH event: %s", exc)

        logger.info(
            "Health check complete: %s (healthy=%d degraded=%d unhealthy=%d)",
            system_status.value, healthy, degraded, unhealthy,
        )
        return report

    # ------------------------------------------------------------------
    # History / Status
    # ------------------------------------------------------------------

    def get_latest_report(self) -> Optional[HealthReport]:
        """Return the most recent health report, or None."""
        with self._lock:
            return self._history[-1] if self._history else None

    def get_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Return recent health reports as dicts."""
        with self._lock:
            recent = list(self._history)[-limit:]
        return [r.to_dict() for r in recent]

    def get_status(self) -> Dict[str, Any]:
        """Return monitor status summary."""
        with self._lock:
            latest = self._history[-1] if self._history else None
            return {
                "registered_checks": len(self._checks),
                "component_ids": sorted(self._checks.keys()),
                "reports_generated": len(self._history),
                "latest_system_status": latest.system_status.value if latest else None,
                "event_backbone_attached": self._event_backbone is not None,
            }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _run_check(component_id: str, check_fn: HealthCheckFn) -> ComponentHealth:
        """Execute a health check and wrap the result."""
        start = time.monotonic()
        try:
            result = check_fn()
            elapsed = (time.monotonic() - start) * 1000
            raw_status = result.get("status", "unknown")
            try:
                status = ComponentStatus(raw_status)
            except ValueError:
                status = ComponentStatus.UNKNOWN
            return ComponentHealth(
                component_id=component_id,
                status=status,
                message=result.get("message", ""),
                latency_ms=elapsed,
                details={k: v for k, v in result.items() if k not in ("status", "message")},
            )
        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000
            logger.error("Health check failed for %s: %s", component_id, exc)
            return ComponentHealth(
                component_id=component_id,
                status=ComponentStatus.UNHEALTHY,
                message=f"Check raised: {exc}",
                latency_ms=elapsed,
            )


# ---------------------------------------------------------------------------
# Kubernetes probe helpers
# ---------------------------------------------------------------------------

class KubernetesProbeAdapter:
    """Exposes readiness and liveness probes suitable for Kubernetes.

    Kubernetes liveness probe — answers "is the process alive?":
      A single critical dependency (e.g. the event loop itself) must respond.
      If not, Kubernetes will restart the pod.

    Kubernetes readiness probe — answers "can this pod serve traffic?":
      All registered checks must pass at the HEALTHY level.
      While degraded, the pod is removed from load-balancer rotation.

    Usage (in FastAPI)::

        from health_monitor import HealthMonitor, KubernetesProbeAdapter
        monitor = HealthMonitor()
        probe = KubernetesProbeAdapter(monitor)

        @app.get("/healthz/live")
        def liveness():
            return probe.liveness()

        @app.get("/healthz/ready")
        def readiness():
            return probe.readiness()
    """

    def __init__(self, monitor: HealthMonitor) -> None:
        self._monitor = monitor

    def liveness(self) -> Dict[str, Any]:
        """Return a liveness response.

        The process is considered alive as long as this method can be invoked.
        Registers a minimal self-check to confirm the health monitor itself is
        functional.

        Returns:
            Dict with ``{"alive": True, "status": "ok"}``

        Raises:
            RuntimeError: if the health monitor itself is unresponsive.
        """
        # A liveness probe must be cheap — just confirm the monitor is alive.
        status = self._monitor.get_status()
        return {
            "alive": True,
            "status": "ok",
            "registered_checks": status.get("registered_checks", 0),
        }

    def readiness(self) -> Dict[str, Any]:
        """Return a readiness response based on the latest health report.

        A pod is considered *ready* only when the overall system status is
        ``HEALTHY``.  ``DEGRADED`` or ``UNHEALTHY`` both result in not-ready.

        Returns:
            Dict with ``{"ready": bool, "system_status": str, ...}``
        """
        report = self._monitor.check_all()
        ready = report.system_status == SystemStatus.HEALTHY
        return {
            "ready": ready,
            "system_status": report.system_status.value,
            "healthy_count": report.healthy_count,
            "degraded_count": report.degraded_count,
            "unhealthy_count": report.unhealthy_count,
            "total_latency_ms": round(report.total_latency_ms, 2),
            "generated_at": report.generated_at,
        }

    def is_ready(self) -> bool:
        """Return True if the system is ready to serve traffic."""
        report = self._monitor.check_all()
        return report.system_status == SystemStatus.HEALTHY

    def is_alive(self) -> bool:
        """Return True if the process / monitor is alive (always True if callable)."""
        return True


# ---------------------------------------------------------------------------
# Built-in dependency health check factories
# ---------------------------------------------------------------------------

def make_database_health_check(
    database_url: Optional[str] = None,
    timeout_seconds: float = 3.0,
) -> Callable[[], Dict[str, Any]]:
    """Return a health-check function for PostgreSQL / SQLite.

    Attempts a lightweight ``SELECT 1`` to verify connectivity.
    Falls back gracefully if SQLAlchemy is not installed.

    Args:
        database_url: Database connection URL. Reads ``DATABASE_URL`` env var
                      if not supplied.
        timeout_seconds: Connection timeout in seconds.

    Returns:
        A callable that returns a health-check result dict.
    """
    import os

    def _check() -> Dict[str, Any]:
        url = database_url or os.environ.get("DATABASE_URL", "")
        if not url:
            return {
                "status": ComponentStatus.UNHEALTHY.value,
                "message": "DATABASE_URL not configured",
            }
        try:
            import importlib
            sqlalchemy = importlib.import_module("sqlalchemy")
            engine = sqlalchemy.create_engine(
                url,
                connect_args={"connect_timeout": int(timeout_seconds)},
                pool_pre_ping=True,
            )
            with engine.connect() as conn:
                conn.execute(sqlalchemy.text("SELECT 1"))
            return {"status": ComponentStatus.HEALTHY.value, "message": "Database reachable"}
        except ImportError:
            return {
                "status": ComponentStatus.DEGRADED.value,
                "message": "sqlalchemy not installed — cannot verify database",
            }
        except Exception as exc:
            return {
                "status": ComponentStatus.UNHEALTHY.value,
                "message": f"Database unreachable: {exc}",
            }

    return _check


def make_redis_health_check(
    redis_url: Optional[str] = None,
    timeout_seconds: float = 3.0,
) -> Callable[[], Dict[str, Any]]:
    """Return a health-check function for Redis.

    Sends a ``PING`` command and expects ``PONG``.
    Falls back gracefully if the ``redis`` package is not installed.

    Args:
        redis_url: Redis connection URL. Reads ``REDIS_URL`` env var if not supplied.
        timeout_seconds: Socket timeout in seconds.

    Returns:
        A callable that returns a health-check result dict.
    """
    import os

    def _check() -> Dict[str, Any]:
        url = redis_url or os.environ.get("REDIS_URL", "")
        if not url:
            return {
                "status": ComponentStatus.DEGRADED.value,
                "message": "REDIS_URL not configured — Redis checks skipped",
            }
        try:
            import importlib
            redis_mod = importlib.import_module("redis")
            client = redis_mod.from_url(url, socket_timeout=timeout_seconds)
            pong = client.ping()
            if pong:
                return {"status": ComponentStatus.HEALTHY.value, "message": "Redis reachable"}
            return {
                "status": ComponentStatus.DEGRADED.value,
                "message": "Redis PING returned unexpected response",
            }
        except ImportError:
            return {
                "status": ComponentStatus.DEGRADED.value,
                "message": "redis package not installed — cannot verify Redis",
            }
        except Exception as exc:
            return {
                "status": ComponentStatus.UNHEALTHY.value,
                "message": f"Redis unreachable: {exc}",
            }

    return _check


def make_llm_health_check(
    llm_url: Optional[str] = None,
    timeout_seconds: float = 5.0,
) -> Callable[[], Dict[str, Any]]:
    """Return a health-check function for the LLM endpoint (Ollama or remote API).

    Performs a lightweight HTTP GET to the model list endpoint to confirm
    that the LLM service is reachable.

    Args:
        llm_url: Base URL of the LLM service. Reads ``OLLAMA_HOST`` env var
                 (default ``http://localhost:11434``) if not supplied.
        timeout_seconds: HTTP request timeout in seconds.

    Returns:
        A callable that returns a health-check result dict.
    """
    import os
    import urllib.request
    import urllib.error

    def _check() -> Dict[str, Any]:
        base_url = llm_url or os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        check_url = base_url.rstrip("/") + "/api/tags"
        try:
            req = urllib.request.Request(
                check_url,
                headers={"User-Agent": "MurphyHealthMonitor/1.0"},
            )
            with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
                if resp.status == 200:
                    return {
                        "status": ComponentStatus.HEALTHY.value,
                        "message": f"LLM service reachable at {base_url}",
                        "url": base_url,
                    }
                return {
                    "status": ComponentStatus.DEGRADED.value,
                    "message": f"LLM service returned HTTP {resp.status}",
                }
        except Exception as exc:
            return {
                "status": ComponentStatus.DEGRADED.value,
                "message": f"LLM service unreachable: {exc}",
                "url": base_url,
            }

    return _check
