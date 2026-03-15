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

    def test_groq_is_first_provider(self):
        scanner = ReadinessScanner()
        report = scanner.scan(base_url=None)
        providers = report["api_key_strategy"]["providers"]
        first = providers[0]
        assert "Groq" in first["name"]
        assert "groq.com" in first["url"]
        assert first["rank"] == 1


# ---------------------------------------------------------------------------
# No LLM key → blocker present
# ---------------------------------------------------------------------------

class TestBlockers:
    def test_missing_llm_key_creates_blocker(self, monkeypatch):
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        scanner = ReadinessScanner()
        report = scanner.scan(base_url=None)
        blocker_names = [b["check"] for b in report["blockers"]]
        assert "llm_api_key" in blocker_names

    def test_has_llm_key_no_blocker(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "gsk_test_key_12345")
        scanner = ReadinessScanner()
        report = scanner.scan(base_url=None)
        blocker_names = [b["check"] for b in report["blockers"]]
        assert "llm_api_key" not in blocker_names

    def test_ready_false_when_blockers_present(self, monkeypatch):
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        scanner = ReadinessScanner()
        report = scanner.scan(base_url=None)
        # blockers exist → ready must be False
        if report["blockers"]:
            assert report["ready"] is False

    def test_ready_true_when_no_blockers(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "gsk_test_key_12345")
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
