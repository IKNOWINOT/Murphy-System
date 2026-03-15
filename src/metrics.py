"""
Prometheus-compatible Metrics for Murphy System.

Exposes system health, module status, and operational counters in
Prometheus text exposition format.  The /metrics endpoint can be scraped
by Prometheus or any compatible monitoring tool.

No external dependencies — generates the text format directly.
"""

import logging
import threading
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_start_time = time.monotonic()

# ── In-process counters ────────────────────────────────────────────
_lock = threading.Lock()
_counters: Dict[str, float] = {}
_gauges: Dict[str, float] = {}
_histograms: Dict[str, List[float]] = {}


def inc_counter(name: str, amount: float = 1.0, labels: Optional[Dict[str, str]] = None) -> None:
    """Increment a counter metric."""
    key = _metric_key(name, labels)
    with _lock:
        _counters[key] = _counters.get(key, 0.0) + amount


def set_gauge(name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
    """Set a gauge metric to a specific value."""
    key = _metric_key(name, labels)
    with _lock:
        _gauges[key] = value


def observe_histogram(name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
    """Record an observation in a histogram metric."""
    key = _metric_key(name, labels)
    with _lock:
        _histograms.setdefault(key, []).append(value)


def _metric_key(name: str, labels: Optional[Dict[str, str]] = None) -> str:
    if not labels:
        return name
    label_str = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
    return f"{name}{{{label_str}}}"


# ── Prometheus text format renderer ────────────────────────────────

def render_metrics() -> str:
    """Render all metrics in Prometheus text exposition format."""
    lines: List[str] = []

    # Uptime gauge
    uptime = time.monotonic() - _start_time
    lines.append("# HELP murphy_uptime_seconds System uptime in seconds")
    lines.append("# TYPE murphy_uptime_seconds gauge")
    lines.append(f"murphy_uptime_seconds {uptime:.2f}")
    lines.append("")

    with _lock:
        # Counters
        rendered_names: set = set()
        for key, value in sorted(_counters.items()):
            base = key.split("{")[0]
            if base not in rendered_names:
                lines.append(f"# HELP {base} Counter metric")
                lines.append(f"# TYPE {base} counter")
                rendered_names.add(base)
            lines.append(f"{key} {value}")
        if _counters:
            lines.append("")

        # Gauges
        rendered_names = set()
        for key, value in sorted(_gauges.items()):
            base = key.split("{")[0]
            if base not in rendered_names:
                lines.append(f"# HELP {base} Gauge metric")
                lines.append(f"# TYPE {base} gauge")
                rendered_names.add(base)
            lines.append(f"{key} {value}")
        if _gauges:
            lines.append("")

        # Histograms (simplified — sum and count only)
        rendered_names = set()
        for key, observations in sorted(_histograms.items()):
            base = key.split("{")[0]
            if base not in rendered_names:
                lines.append(f"# HELP {base} Histogram metric")
                lines.append(f"# TYPE {base} histogram")
                rendered_names.add(base)
            lines.append(f"{key}_count {len(observations)}")
            lines.append(f"{key}_sum {sum(observations):.4f}")
        if _histograms:
            lines.append("")

    return "\n".join(lines) + "\n"


# ── Health aggregator ──────────────────────────────────────────────

_module_health: Dict[str, Dict[str, Any]] = {}
_health_lock = threading.Lock()


def register_module_health(module_name: str, status_fn) -> None:
    """Register a module's get_status function for health aggregation."""
    with _health_lock:
        _module_health[module_name] = {"status_fn": status_fn}


def get_system_health() -> Dict[str, Any]:
    """Aggregate health from all registered modules."""
    uptime = time.monotonic() - _start_time
    modules: Dict[str, Any] = {}

    with _health_lock:
        for name, info in _module_health.items():
            try:
                modules[name] = info["status_fn"]()
            except Exception as exc:
                logger.debug("Caught exception: %s", exc)
                modules[name] = {"status": "error", "error": str(exc)}

    all_healthy = all(
        m.get("status") != "error" for m in modules.values()
    )

    return {
        "status": "healthy" if all_healthy else "degraded",
        "uptime_seconds": round(uptime, 2),
        "modules": modules,
        "module_count": len(modules),
    }
