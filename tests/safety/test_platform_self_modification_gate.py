"""Tests for PSM-001 — RSC pre-launch gate.

Test profile (one case per condition enumerated in rsc_gate.py docstring):

  1. Constructor refuses None and bad threshold.
  2. Cold-start (no history) → allowed, reason="cold_start".
  3. Stable history → allowed, reason="stable".
  4. Single unstable sample → veto, reason="lyapunov_unstable".
  5. Consecutive violations at threshold → veto, reason="consecutive_violations".
  6. Streak overrides a stable blip.
  7. Monitor raises in get_history → veto, reason="monitor_error".
  8. Monitor raises in check_stability → veto, reason="monitor_error".
  9. Object exposing .lyapunov_monitor is unwrapped.
 10. Snapshot is JSON-serialisable.
 11. Real LyapunovMonitor wired end-to-end (allow → veto → recover).
"""

from __future__ import annotations

import json

import pytest

from src.platform_self_modification.rsc_gate import (
    DEFAULT_MAX_CONSECUTIVE_VIOLATIONS,
    GateDecision,
    RSCSelfModificationGate,
)
from src.recursive_stability_controller.lyapunov_monitor import LyapunovMonitor


class _FakeMonitor:
    """Minimal duck-typed stand-in for LyapunovMonitor."""

    def __init__(
        self,
        history=None,
        consecutive=0,
        stable=True,
        raise_on=None,
    ):
        self._history = history or []
        self._consecutive = consecutive
        self._stable = stable
        self._raise_on = raise_on or set()

    def get_history(self, n=None):
        if "get_history" in self._raise_on:
            raise RuntimeError("synthetic history failure")
        return list(self._history)

    def get_consecutive_violations(self):
        if "get_consecutive_violations" in self._raise_on:
            raise RuntimeError("synthetic counter failure")
        return self._consecutive

    def check_stability(self):
        if "check_stability" in self._raise_on:
            raise RuntimeError("synthetic stability failure")
        return self._stable


# ---------------------------------------------------------------------------
# 1. Construction
# ---------------------------------------------------------------------------

def test_gate_rejects_none_source():
    with pytest.raises(ValueError, match="must not be None"):
        RSCSelfModificationGate(None)


def test_gate_rejects_zero_threshold():
    with pytest.raises(ValueError, match="max_consecutive_violations"):
        RSCSelfModificationGate(_FakeMonitor(), max_consecutive_violations=0)


# ---------------------------------------------------------------------------
# 2-6. Decision conditions
# ---------------------------------------------------------------------------

def test_cold_start_allows_with_warning():
    gate = RSCSelfModificationGate(_FakeMonitor(history=[]))
    d = gate.check_pre_launch()
    assert d.allowed is True
    assert d.reason == "cold_start"
    assert d.snapshot["latest"] is None


def test_stable_history_allows():
    gate = RSCSelfModificationGate(
        _FakeMonitor(history=[{"is_stable": True, "delta_V": -0.1}], stable=True)
    )
    d = gate.check_pre_launch()
    assert d.allowed is True
    assert d.reason == "stable"
    assert d.snapshot["latest_check_stable"] is True


def test_single_unstable_sample_vetoes():
    gate = RSCSelfModificationGate(
        _FakeMonitor(history=[{"is_stable": False, "delta_V": 0.5}], stable=False)
    )
    d = gate.check_pre_launch()
    assert d.allowed is False
    assert d.reason == "lyapunov_unstable"


def test_consecutive_violations_at_threshold_vetoes():
    gate = RSCSelfModificationGate(
        _FakeMonitor(
            history=[{"is_stable": True}],
            consecutive=DEFAULT_MAX_CONSECUTIVE_VIOLATIONS,
            stable=True,
        )
    )
    d = gate.check_pre_launch()
    assert d.allowed is False
    assert d.reason == "consecutive_violations"
    assert d.snapshot["consecutive_violations"] == DEFAULT_MAX_CONSECUTIVE_VIOLATIONS


def test_streak_overrides_stable_blip():
    """A single stable sample inside a streak does not clear the veto."""
    gate = RSCSelfModificationGate(
        _FakeMonitor(history=[{"is_stable": True}], consecutive=5, stable=True),
        max_consecutive_violations=2,
    )
    assert gate.check_pre_launch().reason == "consecutive_violations"


def test_just_under_threshold_allowed():
    gate = RSCSelfModificationGate(
        _FakeMonitor(history=[{"is_stable": True}], consecutive=1, stable=True),
        max_consecutive_violations=2,
    )
    assert gate.check_pre_launch().allowed is True


# ---------------------------------------------------------------------------
# 7-8. Failure modes — must fail closed, never silently allow
# ---------------------------------------------------------------------------

def test_history_failure_vetoes_with_monitor_error():
    gate = RSCSelfModificationGate(_FakeMonitor(raise_on={"get_history"}))
    d = gate.check_pre_launch()
    assert d.allowed is False
    assert d.reason == "monitor_error"
    assert "synthetic history failure" in d.message


def test_check_stability_failure_vetoes_with_monitor_error():
    gate = RSCSelfModificationGate(_FakeMonitor(raise_on={"check_stability"}))
    d = gate.check_pre_launch()
    assert d.allowed is False
    assert d.reason == "monitor_error"


def test_consecutive_failure_vetoes_with_monitor_error():
    gate = RSCSelfModificationGate(
        _FakeMonitor(raise_on={"get_consecutive_violations"})
    )
    assert gate.check_pre_launch().reason == "monitor_error"


# ---------------------------------------------------------------------------
# 9. Controller-style source unwrapping
# ---------------------------------------------------------------------------

def test_controller_source_is_unwrapped():
    inner = _FakeMonitor(history=[{"is_stable": True}], stable=True)

    class FakeController:
        lyapunov_monitor = inner

    gate = RSCSelfModificationGate(FakeController())
    assert gate.check_pre_launch().reason == "stable"


def test_object_missing_required_methods_is_rejected_at_check_time():
    """Bad source should veto, not crash."""
    gate = RSCSelfModificationGate(object())
    d = gate.check_pre_launch()
    assert d.allowed is False
    assert d.reason == "monitor_unavailable"


# ---------------------------------------------------------------------------
# 10. Ledger-friendliness
# ---------------------------------------------------------------------------

def test_decision_is_json_serialisable():
    gate = RSCSelfModificationGate(_FakeMonitor(history=[{"is_stable": True}]))
    d = gate.check_pre_launch()
    payload = json.dumps(d.to_dict())
    assert json.loads(payload)["allowed"] is True


# ---------------------------------------------------------------------------
# 11. Real LyapunovMonitor end-to-end
# ---------------------------------------------------------------------------

def test_real_monitor_allow_then_veto_then_recover():
    monitor = LyapunovMonitor()
    gate = RSCSelfModificationGate(monitor, max_consecutive_violations=2)

    # Cold start → allowed.
    assert gate.check_pre_launch().reason == "cold_start"

    # Stable trajectory: energy decreasing.
    monitor.update(recursion_energy=1.0, timestamp=1.0, cycle_id=1)
    monitor.update(recursion_energy=0.8, timestamp=2.0, cycle_id=2)
    assert gate.check_pre_launch().reason == "stable"

    # Two consecutive violations → veto.
    monitor.update(recursion_energy=1.5, timestamp=3.0, cycle_id=3)
    monitor.update(recursion_energy=2.0, timestamp=4.0, cycle_id=4)
    decision = gate.check_pre_launch()
    assert decision.allowed is False
    assert decision.reason in {"consecutive_violations", "lyapunov_unstable"}

    # Recover with a sustained drop → counter resets, gate re-opens.
    monitor.update(recursion_energy=1.0, timestamp=5.0, cycle_id=5)
    assert gate.check_pre_launch().reason == "stable"


def test_decision_is_immutable():
    """Frozen dataclass — accidental mutation must be impossible."""
    d = GateDecision(allowed=True, reason="stable", message="ok")
    with pytest.raises(Exception):
        d.allowed = False  # type: ignore[misc]
