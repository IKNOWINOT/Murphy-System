"""
Murphy System — Module Loading Framework

Provides :class:`ModuleLoadReport` and :class:`ModuleLoader` to replace the
ad-hoc try/except pattern in ``app.py``.  Modules are classified as
``critical`` (system must abort if they fail) or ``optional`` (graceful
degradation is acceptable).  A structured report is produced and stored for
consumption by ``/api/health`` and ``/api/modules``.

Design Labels: ML-001
Owner: INONI LLC / Corey Post
"""

from __future__ import annotations

import importlib
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class LoadStatus(str, Enum):
    """Possible outcomes for a module load attempt."""

    LOADED = "loaded"
    FAILED = "failed"
    SKIPPED = "skipped"


class ModulePriority(str, Enum):
    """Classification that drives fail-fast vs graceful-degradation behaviour."""

    CRITICAL = "critical"
    OPTIONAL = "optional"


@dataclass
class ModuleLoadReport:
    """Record of a single module load attempt."""

    name: str
    priority: ModulePriority
    status: LoadStatus = LoadStatus.SKIPPED
    error: Optional[str] = None
    load_time_ms: float = 0.0
    router_registered: bool = False


@dataclass
class ModuleLoaderResult:
    """Aggregate outcome produced by :class:`ModuleLoader`."""

    reports: List[ModuleLoadReport] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Convenience accessors
    # ------------------------------------------------------------------

    @property
    def loaded(self) -> List[ModuleLoadReport]:
        return [r for r in self.reports if r.status == LoadStatus.LOADED]

    @property
    def failed(self) -> List[ModuleLoadReport]:
        return [r for r in self.reports if r.status == LoadStatus.FAILED]

    @property
    def skipped(self) -> List[ModuleLoadReport]:
        return [r for r in self.reports if r.status == LoadStatus.SKIPPED]

    @property
    def critical_failures(self) -> List[ModuleLoadReport]:
        return [r for r in self.failed if r.priority == ModulePriority.CRITICAL]

    @property
    def optional_failures(self) -> List[ModuleLoadReport]:
        return [r for r in self.failed if r.priority == ModulePriority.OPTIONAL]

    def as_dict(self) -> Dict[str, Any]:
        """Serialise for JSON API responses."""
        return {
            "summary": {
                "total": len(self.reports),
                "loaded": len(self.loaded),
                "failed": len(self.failed),
                "skipped": len(self.skipped),
                "critical_failures": len(self.critical_failures),
                "optional_failures": len(self.optional_failures),
            },
            "modules": [
                {
                    "name": r.name,
                    "priority": r.priority.value,
                    "status": r.status.value,
                    "error": r.error,
                    "load_time_ms": round(r.load_time_ms, 3),
                    "router_registered": r.router_registered,
                }
                for r in self.reports
            ],
        }

    def banner_lines(self) -> List[str]:
        """Return lines suitable for the startup banner."""
        total = len(self.reports)
        n_loaded = len(self.loaded)
        n_fail = len(self.failed)

        if n_fail == 0:
            summary = f"✅ {n_loaded}/{total} modules loaded"
        else:
            _truncate = 3

            def _names(failures: List["ModuleLoadReport"]) -> str:
                shown = failures[:_truncate]
                rest = len(failures) - _truncate
                result = ", ".join(f"{r.name} ({r.error})" for r in shown)
                if rest > 0:
                    result += f", …and {rest} more"
                return result

            parts = [f"✅ {n_loaded}/{total} modules loaded"]
            if self.optional_failures:
                parts.append(
                    f"  ⚠️  {len(self.optional_failures)} optional unavailable: "
                    f"{_names(self.optional_failures)}"
                )
            if self.critical_failures:
                parts.append(
                    f"  ❌ {len(self.critical_failures)} CRITICAL failures: "
                    f"{_names(self.critical_failures)}"
                )
            summary = "\n".join(parts)

        return summary.splitlines()


# ---------------------------------------------------------------------------
# ModuleEntry — configuration record for a single loadable module
# ---------------------------------------------------------------------------

@dataclass
class _ModuleEntry:
    name: str
    priority: ModulePriority
    # Callable that receives the FastAPI app and performs the load action.
    # Returns True when an APIRouter was registered via app.include_router().
    # Returns False for middleware-only or infrastructure modules (no router).
    loader: Callable[..., bool]


# ---------------------------------------------------------------------------
# ModuleLoader
# ---------------------------------------------------------------------------

class ModuleLoader:
    """Framework for loading optional and critical FastAPI sub-routers.

    Each registered loader callable receives the FastAPI ``app`` instance and
    performs its load action (typically ``app.include_router(...)`` or middleware
    registration).  It should return:

    - ``True``  — an ``APIRouter`` was registered via ``app.include_router()``.
    - ``False`` — the module loaded successfully but added no router (e.g. it
                  applied middleware, initialised an infrastructure subsystem, or
                  performed a validation check).

    Usage::

        loader = ModuleLoader()
        loader.register(
            name="billing",
            priority=ModulePriority.OPTIONAL,
            loader=lambda app: _load_billing(app),
        )
        result = loader.load_all(app)
        # raises SystemError if any CRITICAL module failed

    The :class:`ModuleLoaderResult` is stored on ``loader.result`` for
    subsequent inspection by health / modules endpoints.
    """

    def __init__(self) -> None:
        self._entries: List[_ModuleEntry] = []
        self.result: ModuleLoaderResult = ModuleLoaderResult()

    def register(
        self,
        name: str,
        priority: ModulePriority,
        loader: Callable[..., bool],
    ) -> None:
        """Register a module for deferred loading."""
        self._entries.append(_ModuleEntry(name=name, priority=priority, loader=loader))

    def load_all(self, app: Any) -> ModuleLoaderResult:
        """Attempt to load all registered modules.

        Raises
        ------
        SystemError
            If one or more *critical* modules fail to load.
        """
        reports: List[ModuleLoadReport] = []

        for entry in self._entries:
            report = ModuleLoadReport(
                name=entry.name,
                priority=entry.priority,
            )
            t0 = time.monotonic()
            try:
                registered = entry.loader(app)
                report.status = LoadStatus.LOADED
                report.router_registered = bool(registered)
            except Exception as exc:
                report.status = LoadStatus.FAILED
                report.error = str(exc)
                if entry.priority == ModulePriority.CRITICAL:
                    logger.error(
                        "CRITICAL module '%s' failed to load: %s", entry.name, exc
                    )
                else:
                    logger.warning(
                        "Optional module '%s' not available: %s", entry.name, exc
                    )
            finally:
                report.load_time_ms = (time.monotonic() - t0) * 1000
            reports.append(report)

        result = ModuleLoaderResult(reports=reports)
        self.result = result

        if result.critical_failures:
            names = ", ".join(r.name for r in result.critical_failures)
            raise SystemError(
                f"Murphy System cannot start: critical module(s) failed to load: {names}"
            )

        return result
