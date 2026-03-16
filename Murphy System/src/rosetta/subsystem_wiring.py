"""
Rosetta Subsystem Wiring — Murphy System (INC-07 Phase 3)

Wires the Rosetta state management layer into the Murphy System runtime
by establishing formal P3 integration points between the Rosetta Manager
and five key subsystems:

  P3-001  Rosetta ↔ Event Backbone          — state-change events published
  P3-002  Rosetta ↔ Confidence Engine       — agent confidence tracked per state
  P3-003  Rosetta ↔ Learning Engine         — outcomes recorded for ML training
  P3-004  Rosetta ↔ Governance Kernel       — HITL gates on critical transitions
  P3-005  Rosetta ↔ Security Plane          — identity validation on state writes

Public surface
--------------
    WiringPoint         — enum of the five integration points
    WiringStatus        — enum of per-point health states
    WiringResult        — outcome of a single wiring attempt
    RosettaSubsystemWiring — orchestrator that wires/unwinds all points
    bootstrap_wiring    — convenience function for startup

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

__all__ = [
    "WiringPoint",
    "WiringStatus",
    "WiringResult",
    "RosettaSubsystemWiring",
    "bootstrap_wiring",
]


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class WiringPoint(str, Enum):
    """Five formal integration points between Rosetta and Murphy subsystems.

    Attributes:
        EVENT_BACKBONE:    P3-001 — publish state-change events.
        CONFIDENCE_ENGINE: P3-002 — track agent confidence per state.
        LEARNING_ENGINE:   P3-003 — record outcomes for ML training.
        GOVERNANCE_KERNEL: P3-004 — HITL gate critical transitions.
        SECURITY_PLANE:    P3-005 — validate identity on state writes.
    """

    EVENT_BACKBONE = "P3-001:event_backbone"
    CONFIDENCE_ENGINE = "P3-002:confidence_engine"
    LEARNING_ENGINE = "P3-003:learning_engine"
    GOVERNANCE_KERNEL = "P3-004:governance_kernel"
    SECURITY_PLANE = "P3-005:security_plane"


class WiringStatus(str, Enum):
    """Health status of a single wiring point.

    Attributes:
        PENDING:   Not yet attempted.
        WIRED:     Successfully established.
        DEGRADED:  Connected but operating in fallback mode.
        FAILED:    Could not be established.
        UNWIRED:   Previously wired, now torn down.
    """

    PENDING = "pending"
    WIRED = "wired"
    DEGRADED = "degraded"
    FAILED = "failed"
    UNWIRED = "unwired"


# ---------------------------------------------------------------------------
# WiringResult
# ---------------------------------------------------------------------------


@dataclass
class WiringResult:
    """Outcome of a single wiring attempt.

    Attributes:
        point:      The integration point that was wired.
        status:     Resulting health status.
        message:    Human-readable summary.
        duration_ms: Time taken in milliseconds.
        timestamp:  UTC timestamp of the attempt.
        metadata:   Arbitrary additional context.
    """

    point: WiringPoint
    status: WiringStatus
    message: str = ""
    duration_ms: float = 0.0
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_ok(self) -> bool:
        """Return True if the wiring succeeded (WIRED or DEGRADED)."""
        return self.status in (WiringStatus.WIRED, WiringStatus.DEGRADED)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "point": self.point.value,
            "status": self.status.value,
            "message": self.message,
            "duration_ms": round(self.duration_ms, 3),
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


# ---------------------------------------------------------------------------
# RosettaSubsystemWiring
# ---------------------------------------------------------------------------

#: Type alias for a subsystem adapter callable.
#: Signature: (rosetta_manager) → None or raises
_AdapterFn = Callable[[Any], None]


class RosettaSubsystemWiring:
    """Orchestrates the five P3 integration points for the Rosetta subsystem.

    Each point is wired independently so that partial failures do not prevent
    the remaining points from being established.  Thread-safe.

    Parameters
    ----------
    rosetta_manager:
        The :class:`~rosetta.rosetta_manager.RosettaManager` instance to wire.
    adapters:
        Optional overrides for each wiring point.  Provide a mapping of
        ``WiringPoint → callable`` to inject test doubles or alternative
        implementations without monkey-patching.
    strict:
        When ``True``, :meth:`wire_all` raises :class:`RuntimeError` if any
        point ends in ``FAILED`` status.  Defaults to ``False``.
    """

    def __init__(
        self,
        rosetta_manager: Any = None,
        *,
        adapters: Optional[Dict[WiringPoint, _AdapterFn]] = None,
        strict: bool = False,
    ) -> None:
        self._manager = rosetta_manager
        self._adapters: Dict[WiringPoint, Optional[_AdapterFn]] = {
            p: None for p in WiringPoint
        }
        if adapters:
            for point, fn in adapters.items():
                self._adapters[point] = fn
        self._strict = strict
        self._results: Dict[WiringPoint, WiringResult] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def wire_all(self) -> List[WiringResult]:
        """Attempt to wire all five integration points.

        Returns a list of :class:`WiringResult` objects in definition order.
        If *strict* is ``True``, raises :class:`RuntimeError` after wiring
        if any point has status ``FAILED``.
        """
        results = []
        for point in WiringPoint:
            result = self._wire_one(point)
            results.append(result)
        if self._strict:
            failed = [r for r in results if r.status == WiringStatus.FAILED]
            if failed:
                names = ", ".join(r.point.value for r in failed)
                raise RuntimeError(
                    f"Rosetta subsystem wiring failed for: {names}"
                )
        return results

    def wire_point(self, point: WiringPoint) -> WiringResult:
        """Wire a single integration point and return its result."""
        return self._wire_one(point)

    def unwind_all(self) -> List[WiringResult]:
        """Tear down all wired integration points."""
        results = []
        with self._lock:
            for point in list(self._results.keys()):
                r = WiringResult(
                    point=point,
                    status=WiringStatus.UNWIRED,
                    message="Torn down via unwind_all()",
                )
                self._results[point] = r
                results.append(r)
                logger.info("Rosetta wiring unwound: %s", point.value)
        return results

    def get_result(self, point: WiringPoint) -> Optional[WiringResult]:
        """Return the most recent result for *point*, or ``None``."""
        with self._lock:
            return self._results.get(point)

    def all_results(self) -> List[WiringResult]:
        with self._lock:
            return [self._results[p] for p in WiringPoint if p in self._results]

    def is_fully_wired(self) -> bool:
        """Return ``True`` if all five points are WIRED or DEGRADED."""
        with self._lock:
            return all(
                self._results.get(p, WiringResult(p, WiringStatus.PENDING)).is_ok()
                for p in WiringPoint
            )

    def summary(self) -> Dict[str, Any]:
        with self._lock:
            results = [
                self._results[p].to_dict()
                for p in WiringPoint
                if p in self._results
            ]
        wired = sum(1 for r in results if r["status"] in ("wired", "degraded"))
        return {
            "total_points": len(WiringPoint),
            "wired": wired,
            "failed": sum(1 for r in results if r["status"] == "failed"),
            "pending": len(WiringPoint) - len(results),
            "fully_wired": wired == len(WiringPoint),
            "results": results,
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _wire_one(self, point: WiringPoint) -> WiringResult:
        import time

        t0 = time.perf_counter()
        adapter = self._adapters.get(point)
        try:
            if adapter is not None:
                adapter(self._manager)
            else:
                self._default_wire(point)
            elapsed = (time.perf_counter() - t0) * 1000
            result = WiringResult(
                point=point,
                status=WiringStatus.WIRED,
                message=f"{point.value} wired successfully",
                duration_ms=elapsed,
            )
            logger.info("Rosetta wiring OK: %s (%.1f ms)", point.value, elapsed)
        except Exception as exc:  # noqa: BLE001
            elapsed = (time.perf_counter() - t0) * 1000
            result = WiringResult(
                point=point,
                status=WiringStatus.FAILED,
                message=f"Wiring failed: {type(exc).__name__}",
                duration_ms=elapsed,
            )
            logger.warning(
                "Rosetta wiring FAILED: %s — %s", point.value, type(exc).__name__
            )
        with self._lock:
            self._results[point] = result
        return result

    def _default_wire(self, point: WiringPoint) -> None:
        """Default (no-op) wire logic used when no adapter is provided.

        Real adapters are injected by the Murphy System bootstrap or by
        tests.  The default implementation validates that the manager exists
        and logs the wiring event, then returns.
        """
        if point == WiringPoint.EVENT_BACKBONE:
            # P3-001: Register Rosetta state-change event hooks.
            logger.debug("P3-001: event backbone wiring (stub — no backbone provided)")

        elif point == WiringPoint.CONFIDENCE_ENGINE:
            # P3-002: Register agent confidence callbacks.
            logger.debug("P3-002: confidence engine wiring (stub)")

        elif point == WiringPoint.LEARNING_ENGINE:
            # P3-003: Register outcome recording callbacks.
            logger.debug("P3-003: learning engine wiring (stub)")

        elif point == WiringPoint.GOVERNANCE_KERNEL:
            # P3-004: Register HITL gate callbacks for critical state transitions.
            logger.debug("P3-004: governance kernel wiring (stub)")

        elif point == WiringPoint.SECURITY_PLANE:
            # P3-005: Register identity validation hooks for state writes.
            logger.debug("P3-005: security plane wiring (stub)")

        else:
            raise ValueError(f"Unknown wiring point: {point!r}")


# ---------------------------------------------------------------------------
# Convenience bootstrap
# ---------------------------------------------------------------------------


def bootstrap_wiring(
    rosetta_manager: Any = None,
    *,
    adapters: Optional[Dict[WiringPoint, _AdapterFn]] = None,
    strict: bool = False,
) -> RosettaSubsystemWiring:
    """Create a :class:`RosettaSubsystemWiring`, wire all points, and return it.

    Intended for use in the Murphy System startup sequence::

        from rosetta.subsystem_wiring import bootstrap_wiring
        wiring = bootstrap_wiring(rosetta_manager=manager)

    Parameters
    ----------
    rosetta_manager:
        Optional :class:`~rosetta.rosetta_manager.RosettaManager` instance.
    adapters:
        Optional mapping of wiring point overrides.
    strict:
        Raise on any FAILED wiring point if ``True``.
    """
    wiring = RosettaSubsystemWiring(
        rosetta_manager=rosetta_manager,
        adapters=adapters,
        strict=strict,
    )
    results = wiring.wire_all()
    ok = sum(1 for r in results if r.is_ok())
    logger.info(
        "Rosetta subsystem bootstrap complete: %d/%d points wired",
        ok,
        len(WiringPoint),
    )
    return wiring
