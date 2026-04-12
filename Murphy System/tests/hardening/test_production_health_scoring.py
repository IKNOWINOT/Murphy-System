"""
Module: tests/hardening/test_production_health_scoring.py
Subsystem: Health Monitor — Dependency Health Scoring & Startup Readiness Gate
Label: TEST-OBS-003 — Commission tests for DependencyHealthScorer and StartupReadinessGate

Commissioning Answers (G1–G9)
-----------------------------
G1  What does the module do?
    DependencyHealthScorer converts per-component health statuses into a
    single numeric score (0.0–1.0) with optional weighting.
    StartupReadinessGate blocks application startup until all health checks
    pass or a timeout elapses.

G2  What specification / design-label does it fulfil?
    OBS-003 (Dependency Health Scoring) and OBS-005 (Startup Readiness Gate)
    as documented in Murphy System 1.0 Production Spec.

G3  Under what conditions should it succeed / fail?
    Succeed: score computation matches the documented formula; gate opens
    when all checks pass; gate times out when checks remain unhealthy.
    Fail: score outside [0.0, 1.0]; gate opens with failing checks; gate
    hangs indefinitely.

G4  What is the test-profile?
    Pure unit tests with in-memory HealthMonitor stubs — no network, no
    disk, no external services.

G5  Any external dependencies?
    None beyond the standard library and pytest.

G6  Can the tests run in CI without credentials?
    Yes.

G7  Expected run-time?
    < 3 s.

G8  Owner / maintainer?
    Platform Engineering / DevOps Team.

G9  Review date?
    On every PR that modifies src/health_monitor.py.
"""
from __future__ import annotations

import pytest

from src.health_monitor import (
    ComponentStatus,
    DependencyHealthScorer,
    GateResult,
    HealthMonitor,
    StartupReadinessGate,
)


# ── Helpers ─────────────────────────────────────────────────────────────────


def _make_monitor(*statuses: str) -> HealthMonitor:
    """Build a HealthMonitor with stub checks returning the given statuses."""
    monitor = HealthMonitor()
    for idx, status in enumerate(statuses):
        _status = status  # capture for closure
        monitor.register(
            f"comp-{idx}",
            lambda s=_status: {"status": s, "message": f"stub-{s}"},
        )
    return monitor


# ── DependencyHealthScorer Tests ───────────────────────────────────────────


class TestDependencyHealthScorer:
    """TEST-OBS-003 — Dependency health scoring."""

    def test_scorer_all_healthy(self) -> None:
        """All healthy components → score = 1.0."""
        monitor = _make_monitor("healthy", "healthy", "healthy")
        scorer = DependencyHealthScorer(monitor)
        assert scorer.score() == pytest.approx(1.0)

    def test_scorer_all_unhealthy(self) -> None:
        """All unhealthy components → score = 0.0."""
        monitor = _make_monitor("unhealthy", "unhealthy")
        scorer = DependencyHealthScorer(monitor)
        assert scorer.score() == pytest.approx(0.0)

    def test_scorer_mixed(self) -> None:
        """Mixed statuses → correct average."""
        # healthy(1.0) + degraded(0.5) + unhealthy(0.0) = 1.5 / 3 = 0.5
        monitor = _make_monitor("healthy", "degraded", "unhealthy")
        scorer = DependencyHealthScorer(monitor)
        assert scorer.score() == pytest.approx(0.5)

    def test_scorer_with_weights(self) -> None:
        """Weighted scoring shifts result toward heavier component."""
        monitor = HealthMonitor()
        monitor.register("db", lambda: {"status": "healthy", "message": "ok"})
        monitor.register("cache", lambda: {"status": "unhealthy", "message": "down"})
        scorer = DependencyHealthScorer(monitor)
        # db weight=3 (score 1.0), cache weight=1 (score 0.0)
        # weighted = (3*1.0 + 1*0.0) / (3+1) = 0.75
        result = scorer.score_with_weights({"db": 3.0, "cache": 1.0})
        assert result == pytest.approx(0.75)

    def test_scorer_production_ready(self) -> None:
        """is_production_ready respects min_score threshold."""
        monitor = _make_monitor("healthy", "healthy", "degraded")
        scorer = DependencyHealthScorer(monitor)
        # score = (1.0 + 1.0 + 0.5) / 3 ≈ 0.833
        assert scorer.is_production_ready(min_score=0.8) is True
        assert scorer.is_production_ready(min_score=0.9) is False

    def test_scorer_degraded_components(self) -> None:
        """get_degraded_components lists non-healthy IDs."""
        monitor = _make_monitor("healthy", "degraded", "unhealthy")
        scorer = DependencyHealthScorer(monitor)
        degraded = scorer.get_degraded_components()
        assert "comp-0" not in degraded
        assert "comp-1" in degraded
        assert "comp-2" in degraded


# ── StartupReadinessGate Tests ─────────────────────────────────────────────


class TestStartupReadinessGate:
    """TEST-OBS-003 — Startup readiness gate."""

    def test_gate_opens_when_healthy(self) -> None:
        """Gate opens immediately when all checks pass."""
        monitor = _make_monitor("healthy", "healthy")
        gate = StartupReadinessGate(monitor)
        result = gate.wait_until_ready(timeout_seconds=2.0, poll_interval=0.05)
        assert isinstance(result, GateResult)
        assert result.opened is True
        assert result.failed_checks == []

    def test_gate_timeout_when_unhealthy(self) -> None:
        """Gate returns opened=False after timeout when checks fail."""
        monitor = _make_monitor("unhealthy")
        gate = StartupReadinessGate(monitor)
        result = gate.wait_until_ready(timeout_seconds=0.15, poll_interval=0.05)
        assert result.opened is False
        assert len(result.failed_checks) >= 1

    def test_gate_status_snapshot(self) -> None:
        """gate_status() returns dict with expected shape."""
        monitor = _make_monitor("healthy", "unhealthy")
        gate = StartupReadinessGate(monitor)
        status = gate.gate_status()
        assert "is_open" in status
        assert "checks_passed" in status
        assert "elapsed_seconds" in status
        assert "remaining_checks" in status
        assert isinstance(status["checks_passed"], list)
        assert isinstance(status["remaining_checks"], list)
        # With one healthy and one unhealthy, gate should not be open
        assert status["is_open"] is False
        assert len(status["remaining_checks"]) >= 1
