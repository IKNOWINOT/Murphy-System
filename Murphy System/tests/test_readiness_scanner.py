# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Tests for ReadinessScanner (Facet 4)
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.readiness_scanner import ReadinessScanner, run_readiness_scan


# ---------------------------------------------------------------------------
# Basic scan structure
# ---------------------------------------------------------------------------

class TestReadinessScannerStructure:
    def test_scan_returns_dict(self):
        scanner = ReadinessScanner()
        report = scanner.scan(base_url=None)
        assert isinstance(report, dict)

    def test_scan_has_required_keys(self):
        scanner = ReadinessScanner()
        report = scanner.scan(base_url=None)
        assert "ready" in report
        assert "score" in report
        assert "passed" in report
        assert "blockers" in report
        assert "warnings" in report
        assert "timestamp" in report

    def test_ready_is_bool(self):
        scanner = ReadinessScanner()
        report = scanner.scan(base_url=None)
        assert isinstance(report["ready"], bool)

    def test_score_format(self):
        scanner = ReadinessScanner()
        report = scanner.scan(base_url=None)
        score = report["score"]
        # e.g. "5/12 checks passed"
        assert "checks passed" in score
        assert "/" in score

    def test_passed_is_list(self):
        scanner = ReadinessScanner()
        report = scanner.scan(base_url=None)
        assert isinstance(report["passed"], list)

    def test_blockers_is_list(self):
        scanner = ReadinessScanner()
        report = scanner.scan(base_url=None)
        assert isinstance(report["blockers"], list)

    def test_warnings_is_list(self):
        scanner = ReadinessScanner()
        report = scanner.scan(base_url=None)
        assert isinstance(report["warnings"], list)

    def test_timestamp_is_string(self):
        scanner = ReadinessScanner()
        report = scanner.scan(base_url=None)
        assert isinstance(report["timestamp"], str)
        assert "T" in report["timestamp"]  # ISO 8601

    def test_api_key_strategy_present(self):
        scanner = ReadinessScanner()
        report = scanner.scan(base_url=None)
        strategy = report.get("api_key_strategy", {})
        assert isinstance(strategy, dict)
        providers = strategy.get("providers", [])
        assert len(providers) >= 1

    def test_deepinfra_is_first_provider(self):
        scanner = ReadinessScanner()
        report = scanner.scan(base_url=None)
        providers = report["api_key_strategy"]["providers"]
        first = providers[0]
        assert "DeepInfra" in first["name"]
        assert "deepinfra.com" in first["url"]
        assert first["rank"] == 1


# ---------------------------------------------------------------------------
# No LLM key → blocker present
# ---------------------------------------------------------------------------

class TestBlockers:
    def test_missing_llm_key_creates_blocker(self, monkeypatch):
        monkeypatch.delenv("DEEPINFRA_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        scanner = ReadinessScanner()
        report = scanner.scan(base_url=None)
        blocker_names = [b["check"] for b in report["blockers"]]
        assert "llm_api_key" in blocker_names

    def test_has_llm_key_no_blocker(self, monkeypatch):
        monkeypatch.setenv("DEEPINFRA_API_KEY", "gsk_test_key_12345")
        scanner = ReadinessScanner()
        report = scanner.scan(base_url=None)
        blocker_names = [b["check"] for b in report["blockers"]]
        assert "llm_api_key" not in blocker_names

    def test_ready_false_when_blockers_present(self, monkeypatch):
        monkeypatch.delenv("DEEPINFRA_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        scanner = ReadinessScanner()
        report = scanner.scan(base_url=None)
        # blockers exist → ready must be False
        if report["blockers"]:
            assert report["ready"] is False

    def test_ready_true_when_no_blockers(self, monkeypatch):
        monkeypatch.setenv("DEEPINFRA_API_KEY", "gsk_test_key_12345")
        scanner = ReadinessScanner()
        report = scanner.scan(base_url=None)
        if not report["blockers"]:
            assert report["ready"] is True


# ---------------------------------------------------------------------------
# Config loads
# ---------------------------------------------------------------------------

class TestConfigCheck:
    def test_config_loads_passes(self):
        scanner = ReadinessScanner()
        report = scanner.scan(base_url=None)
        assert "config_loads" in report["passed"]


# ---------------------------------------------------------------------------
# HTTP check skipped when base_url=None
# ---------------------------------------------------------------------------

class TestHttpCheck:
    def test_no_http_check_when_base_url_none(self):
        scanner = ReadinessScanner()
        report = scanner.scan(base_url=None)
        # health_endpoint should not appear in passed or warnings when skipped
        assert "health_endpoint" not in report["passed"]


# ---------------------------------------------------------------------------
# Module-level convenience
# ---------------------------------------------------------------------------

class TestConvenienceFunction:
    def test_run_readiness_scan_returns_dict(self):
        report = run_readiness_scan(base_url=None)
        assert "ready" in report
        assert "score" in report


# ---------------------------------------------------------------------------
# DeploymentGateRunner tests
# ---------------------------------------------------------------------------

class TestDeploymentGateRunner:
    """Tests for the five production-blocking deployment gates."""

    def test_runner_has_five_default_gates(self):
        """DeploymentGateRunner has exactly 5 default gates."""
        from readiness_scanner import DeploymentGateRunner
        runner = DeploymentGateRunner()
        result = runner.run_all()
        assert len(result["gates"]) == 5

    def test_runner_result_has_expected_keys(self):
        """run_all() response contains all required keys."""
        from readiness_scanner import DeploymentGateRunner
        runner = DeploymentGateRunner()
        result = runner.run_all()
        for key in ("all_passed", "gates", "failed_gates", "passed_count",
                    "failed_count", "evaluated_at"):
            assert key in result

    def test_get_status_returns_compact_dict(self):
        """get_status() returns a compact summary dict."""
        from readiness_scanner import DeploymentGateRunner
        runner = DeploymentGateRunner()
        status = runner.get_status()
        for key in ("all_passed", "gates_total", "gates_passed",
                    "gates_failed", "blocked_by", "evaluated_at"):
            assert key in status

    def test_security_scan_gate_fails_without_murphy_env(self, monkeypatch):
        """security_scan gate fails when MURPHY_ENV is not set."""
        from readiness_scanner import DeploymentGateRunner
        monkeypatch.delenv("MURPHY_ENV", raising=False)
        runner = DeploymentGateRunner()
        result = runner.run_all()
        sec_gate = next(g for g in result["gates"] if g["gate"] == "security_scan")
        assert sec_gate["passed"] is False

    def test_security_scan_gate_passes_in_development(self, monkeypatch):
        """security_scan gate passes in development environment."""
        from readiness_scanner import DeploymentGateRunner
        monkeypatch.setenv("MURPHY_ENV", "development")
        runner = DeploymentGateRunner()
        result = runner.run_all()
        sec_gate = next(g for g in result["gates"] if g["gate"] == "security_scan")
        assert sec_gate["passed"] is True

    def test_test_pass_gate_skipped_in_development(self, monkeypatch):
        """test_pass gate passes (skipped) in development environment."""
        from readiness_scanner import DeploymentGateRunner
        monkeypatch.setenv("MURPHY_ENV", "development")
        runner = DeploymentGateRunner()
        result = runner.run_all()
        tp_gate = next(g for g in result["gates"] if g["gate"] == "test_pass")
        assert tp_gate["passed"] is True

    def test_test_pass_gate_fails_in_production_without_flag(self, monkeypatch):
        """test_pass gate fails in production when MURPHY_TESTS_PASSED != 1."""
        from readiness_scanner import DeploymentGateRunner
        monkeypatch.setenv("MURPHY_ENV", "production")
        monkeypatch.delenv("MURPHY_TESTS_PASSED", raising=False)
        runner = DeploymentGateRunner()
        result = runner.run_all()
        tp_gate = next(g for g in result["gates"] if g["gate"] == "test_pass")
        assert tp_gate["passed"] is False

    def test_test_pass_gate_passes_in_production_with_flag(self, monkeypatch):
        """test_pass gate passes in production when MURPHY_TESTS_PASSED=1."""
        from readiness_scanner import DeploymentGateRunner
        monkeypatch.setenv("MURPHY_ENV", "production")
        monkeypatch.setenv("MURPHY_TESTS_PASSED", "1")
        runner = DeploymentGateRunner()
        result = runner.run_all()
        tp_gate = next(g for g in result["gates"] if g["gate"] == "test_pass")
        assert tp_gate["passed"] is True

    def test_secret_availability_gate_skipped_in_development(self, monkeypatch):
        """secret_availability gate passes (skipped) in development."""
        from readiness_scanner import DeploymentGateRunner
        monkeypatch.setenv("MURPHY_ENV", "development")
        runner = DeploymentGateRunner()
        result = runner.run_all()
        sa_gate = next(g for g in result["gates"] if g["gate"] == "secret_availability")
        assert sa_gate["passed"] is True

    def test_secret_availability_gate_fails_in_production_without_secrets(self, monkeypatch):
        """secret_availability gate fails in production when secrets are missing."""
        from readiness_scanner import DeploymentGateRunner
        monkeypatch.setenv("MURPHY_ENV", "production")
        for k in ("MURPHY_API_KEYS", "MURPHY_CREDENTIAL_MASTER_KEY",
                  "MURPHY_JWT_SECRET", "POSTGRES_PASSWORD", "MURPHY_SECRET_KEY"):
            monkeypatch.delenv(k, raising=False)
        runner = DeploymentGateRunner()
        result = runner.run_all()
        sa_gate = next(g for g in result["gates"] if g["gate"] == "secret_availability")
        assert sa_gate["passed"] is False

    def test_add_custom_gate(self, monkeypatch):
        """Custom gate can be added and evaluated."""
        from readiness_scanner import DeploymentGateRunner
        runner = DeploymentGateRunner()
        runner.add_gate("custom_test", "custom", lambda: (True, "custom gate passed"))
        result = runner.run_all()
        custom = next((g for g in result["gates"] if g["gate"] == "custom_test"), None)
        assert custom is not None
        assert custom["passed"] is True

    def test_all_gates_pass_in_development_with_server_mocked(self, monkeypatch):
        """All non-infra gates pass in development env (health skipped via custom)."""
        from readiness_scanner import DeploymentGateRunner, DeploymentGate
        monkeypatch.setenv("MURPHY_ENV", "development")
        runner = DeploymentGateRunner()
        # Override health check gate to always pass (no server running)
        for gate in runner._gates:
            if gate.name == "health_check":
                gate._check_fn = lambda: (True, "health check bypassed for test")
        result = runner.run_all()
        assert result["all_passed"] is True
