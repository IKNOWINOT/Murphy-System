"""PSM-001 — RSC pre-launch gate for platform self-modification cycles.

Design label: ``PSM-001``
Owner: Platform Engineering
Depends on: ``src.recursive_stability_controller.lyapunov_monitor``

Commissioning answers (CLAUDE.md / problem-statement checklist):

* **What is this module supposed to do?**
  Decide whether a self-modification cycle is safe to launch *right now*
  by querying the Lyapunov monitor. The Lyapunov function is
  ``Vₜ = Rₜ²`` where Rₜ is recursion energy; the system is stable when
  ``ΔVₜ ≤ 0``. A cycle that grows energy (ΔVₜ > 0) violates the hard
  constraint, so launching another self-edit on top of an unstable
  trajectory would compound the instability.

* **What conditions are possible?**
  1. Cold start (no history) → allow with a "no-baseline" warning.
  2. Latest sample stable AND consecutive_violations < threshold → allow.
  3. Latest sample unstable → veto.
  4. consecutive_violations ≥ threshold → veto (the system is *trending*
     unstable even if the latest single sample is stable).
  5. Monitor raises → veto with ``reason="monitor_error"``.
     **Never** silently allow.

* **Expected vs actual at every operating point** is captured by
  ``tests/safety/test_platform_self_modification_gate.py`` (one test per
  condition above). Restart-from-symptom: if the endpoint returns 409
  with ``reason="lyapunov_unstable"``, operators inspect
  ``snapshot["latest"]`` and the Lyapunov monitor history to confirm,
  then re-run after the system relaxes.

* **Hardening:** exceptions inside the monitor never leak; the gate
  fails *closed* (vetoes). All decisions are explicit dataclass values,
  no truthy-coercion of None, and the snapshot is JSON-serialisable so
  it can be persisted in the immutable ledger.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Optional


# Default thresholds. Tuned to match the existing LyapunovMonitor unit
# tests, which treat 2+ consecutive violations as a sustained trend.
DEFAULT_MAX_CONSECUTIVE_VIOLATIONS = 2


@dataclass(frozen=True)
class GateDecision:
    """Outcome of a pre-launch gate evaluation.

    Attributes:
        allowed: True iff the cycle is permitted to launch.
        reason:  Stable machine-readable token. One of
                 ``"stable"``, ``"cold_start"``, ``"lyapunov_unstable"``,
                 ``"consecutive_violations"``, ``"monitor_error"``,
                 ``"monitor_unavailable"``.
        message: Human-readable explanation suitable for an operator UI.
        snapshot: JSON-serialisable Lyapunov state at decision time.
                  Always populated (may be empty dict on monitor error).
    """

    allowed: bool
    reason: str
    message: str
    snapshot: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """JSON-safe representation for the immutable ledger."""
        return asdict(self)


class RSCSelfModificationGate:
    """Gate self-modification cycles on the Lyapunov stability signal.

    The gate accepts either a bare ``LyapunovMonitor`` or a full
    ``RecursiveStabilityController``; it auto-detects which by attribute
    presence so the production wiring code can pass whichever object
    it has on hand.
    """

    def __init__(
        self,
        monitor_or_controller: Any,
        *,
        max_consecutive_violations: int = DEFAULT_MAX_CONSECUTIVE_VIOLATIONS,
    ) -> None:
        if monitor_or_controller is None:
            raise ValueError(
                "PSM-001: monitor_or_controller must not be None — "
                "the gate must fail closed, never silently allow."
            )
        if max_consecutive_violations < 1:
            raise ValueError(
                "PSM-001: max_consecutive_violations must be >= 1; "
                f"got {max_consecutive_violations}."
            )
        self._source = monitor_or_controller
        self._max_consecutive = max_consecutive_violations

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check_pre_launch(self) -> GateDecision:
        """Evaluate whether a self-modification cycle may launch *now*.

        Never raises. On any internal error the gate vetoes with
        ``reason="monitor_error"`` so automation cannot proceed silently.
        """
        try:
            monitor = self._resolve_monitor()
        except Exception as exc:  # noqa: BLE001 — fail-closed contract
            return GateDecision(
                allowed=False,
                reason="monitor_unavailable",
                message=f"PSM-001: Lyapunov monitor unavailable: {exc}",
                snapshot={},
            )

        try:
            history = monitor.get_history(n=1) or []
            consecutive = int(monitor.get_consecutive_violations() or 0)
            latest_stable = bool(monitor.check_stability())
        except Exception as exc:  # noqa: BLE001 — fail-closed contract
            return GateDecision(
                allowed=False,
                reason="monitor_error",
                message=f"PSM-001: Lyapunov monitor raised: {exc}",
                snapshot={},
            )

        latest = history[-1] if history else None
        snapshot: Dict[str, Any] = {
            "latest": latest,
            "consecutive_violations": consecutive,
            "max_consecutive_violations": self._max_consecutive,
            "latest_check_stable": latest_stable,
        }

        # Cold start: no samples at all. Allow but tell the operator.
        if latest is None:
            return GateDecision(
                allowed=True,
                reason="cold_start",
                message=(
                    "PSM-001: No Lyapunov samples yet — allowing cold-start "
                    "cycle. Operator should monitor first cycle closely."
                ),
                snapshot=snapshot,
            )

        # Hard veto: consecutive-violation streak. Trend dominates the
        # single-sample check because a stable blip inside an unstable
        # streak does not clear the trajectory.
        if consecutive >= self._max_consecutive:
            return GateDecision(
                allowed=False,
                reason="consecutive_violations",
                message=(
                    f"PSM-001: VETO — {consecutive} consecutive Lyapunov "
                    f"violations (threshold {self._max_consecutive}). "
                    "System energy is trending up; cycle refused."
                ),
                snapshot=snapshot,
            )

        # Single-sample veto: ΔVₜ > 0 right now.
        if not latest_stable:
            return GateDecision(
                allowed=False,
                reason="lyapunov_unstable",
                message=(
                    "PSM-001: VETO — latest Lyapunov sample is unstable "
                    "(ΔVₜ > 0). Self-modification refused until Rₜ relaxes."
                ),
                snapshot=snapshot,
            )

        return GateDecision(
            allowed=True,
            reason="stable",
            message="PSM-001: Lyapunov stable — cycle permitted.",
            snapshot=snapshot,
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _resolve_monitor(self) -> Any:
        """Return the underlying LyapunovMonitor.

        Accepts either a bare monitor (duck-typed by attribute presence)
        or a ``RecursiveStabilityController`` whose monitor is at
        ``.lyapunov_monitor``.
        """
        src = self._source
        if hasattr(src, "lyapunov_monitor") and src.lyapunov_monitor is not None:
            src = src.lyapunov_monitor
        # Duck-type check — must expose the three methods we call.
        for name in ("get_history", "get_consecutive_violations", "check_stability"):
            if not hasattr(src, name):
                raise AttributeError(
                    f"object {type(src).__name__!r} is missing method {name!r}"
                )
        return src
