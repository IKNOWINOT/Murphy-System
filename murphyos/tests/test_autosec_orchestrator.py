"""Tests for murphy_autosec_orchestrator — security orchestrator."""

from unittest import mock

import pytest

from murphy_autosec_orchestrator import AutoSecOrchestrator


# ── initialize ────────────────────────────────────────────────────────────
class TestInitialize:
    def test_initialize_starts_all_engines(self):
        orch = AutoSecOrchestrator(config={"dry_run": True})
        report = orch.initialize()
        assert isinstance(report, dict)
        assert len(report) > 0

    def test_initialize_reports_component_status(self):
        orch = AutoSecOrchestrator(config={"dry_run": True})
        report = orch.initialize()
        for key, val in report.items():
            assert isinstance(val, bool), f"{key} should be bool"

    def test_double_initialize_safe(self):
        orch = AutoSecOrchestrator(config={"dry_run": True})
        orch.initialize()
        report2 = orch.initialize()
        assert isinstance(report2, dict)


# ── health_check ──────────────────────────────────────────────────────────
class TestHealthCheck:
    def test_health_check_returns_dict(self):
        orch = AutoSecOrchestrator(config={"dry_run": True})
        orch.initialize()
        health = orch.health_check()
        assert isinstance(health, dict)

    def test_health_check_before_init(self):
        orch = AutoSecOrchestrator(config={"dry_run": True})
        health = orch.health_check()
        assert isinstance(health, dict)


# ── get_security_posture ──────────────────────────────────────────────────
class TestSecurityPosture:
    def test_posture_in_range(self):
        orch = AutoSecOrchestrator(config={"dry_run": True})
        orch.initialize()
        score = orch.get_security_posture()
        assert 0 <= score <= 100

    def test_posture_is_integer(self):
        orch = AutoSecOrchestrator(config={"dry_run": True})
        score = orch.get_security_posture()
        assert isinstance(score, int)


# ── threat summary ────────────────────────────────────────────────────────
class TestThreatSummary:
    def test_threat_summary_returns_dict(self):
        orch = AutoSecOrchestrator(config={"dry_run": True})
        orch.initialize()
        summary = orch.get_threat_summary()
        assert isinstance(summary, dict)


# ── shutdown ──────────────────────────────────────────────────────────────
class TestShutdown:
    def test_shutdown_succeeds(self):
        orch = AutoSecOrchestrator(config={"dry_run": True})
        orch.initialize()
        orch.shutdown()  # should not raise
