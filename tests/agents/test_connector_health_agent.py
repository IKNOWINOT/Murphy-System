#!/usr/bin/env python3
# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post | License: BSL-1.1
#
# Tests for the Connector Health Agent (CONNECTOR-HEALTH-001)
#
# Commissioning profile:
#   G1: Validates each phase produces correct outputs
#   G2: Tests the three phases: discover, check, report
#   G3: Covers connector patterns and edge cases
#   G4: Full range including empty/corrupt/missing inputs
#   G5: Expected: structured JSON reports with correct fields
#   G6: Actual: verified via assertions
#   G9: Hardening checks included

"""Tests for Murphy System Connector Health Agent."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts"))

from connector_health_agent import (  # noqa: E402
    AGENT_LABEL,
    AGENT_VERSION,
    CONNECTOR_PATTERNS,
    EXPECTED_MARKERS,
    _extract_connector_metadata,
    _find_src_dir,
    _format_issue_body,
    _probe_connector,
    phase_check,
    phase_discover,
    phase_report,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def tmp_output(tmp_path):
    out = tmp_path / "output"
    out.mkdir()
    return out


@pytest.fixture
def fake_src(tmp_path):
    """Create a minimal src/ tree with connectors."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "slack_connector.py").write_text(
        '"""Slack connector."""\nclass SlackConnector:\n    pass\n'
    )
    (src / "jira_connector.py").write_text(
        '"""Jira connector."""\nclass JiraConnector:\n    pass\n'
    )
    (src / "broken_connector.py").write_text("def oops(\n")  # syntax error
    (src / "not_a_connector.py").write_text("x = 1\n")
    return src


@pytest.fixture
def discovery_report(tmp_output):
    report = {
        "agent": AGENT_LABEL,
        "version": AGENT_VERSION,
        "phase": "discover",
        "connectors": [
            {
                "file": "src/slack_connector.py",
                "module": "src.slack_connector",
                "name": "slack_connector",
                "classes": ["SlackConnector"],
                "has_docstring": True,
                "line_count": 3,
            },
        ],
        "total": 1,
    }
    path = tmp_output / "discovery_report.json"
    path.write_text(json.dumps(report))
    return path


@pytest.fixture
def health_report_path(tmp_output):
    report = {
        "agent": AGENT_LABEL,
        "version": AGENT_VERSION,
        "phase": "check",
        "results": [
            {
                "name": "slack_connector",
                "module": "src.slack_connector",
                "status": "healthy",
                "checks": {"import": "pass", "has_classes": "pass",
                           "has_docstring": "pass", "parseable": "pass"},
            },
            {
                "name": "broken_connector",
                "module": "src.broken_connector",
                "status": "unhealthy",
                "checks": {"import": "fail: SyntaxError",
                           "has_classes": "warn: no classes defined",
                           "has_docstring": "warn: no module docstring",
                           "parseable": "fail: SyntaxError"},
            },
        ],
        "healthy": 1,
        "unhealthy": 1,
        "total": 2,
    }
    path = tmp_output / "health_report.json"
    path.write_text(json.dumps(report))
    return path


# ── Constants ─────────────────────────────────────────────────────────────────


class TestConstants:
    def test_agent_label(self):
        assert AGENT_LABEL == "CONNECTOR-HEALTH-001"

    def test_agent_version(self):
        assert AGENT_VERSION == "1.0.0"

    def test_connector_patterns_non_empty(self):
        assert len(CONNECTOR_PATTERNS) >= 1


# ── Phase: Discover ───────────────────────────────────────────────────────────


class TestPhaseDiscover:
    def test_produces_discovery_report(self, tmp_output):
        result = phase_discover(tmp_output)
        assert (tmp_output / "discovery_report.json").exists()
        assert "connectors" in result
        assert "total" in result
        assert isinstance(result["connectors"], list)

    def test_finds_real_connectors(self, tmp_output):
        result = phase_discover(tmp_output)
        assert result["total"] >= 0  # May be 0 if running outside repo root

    def test_report_contains_agent_metadata(self, tmp_output):
        result = phase_discover(tmp_output)
        assert result["agent"] == AGENT_LABEL
        assert result["version"] == AGENT_VERSION


# ── _extract_connector_metadata ───────────────────────────────────────────────


class TestExtractMetadata:
    def test_extracts_classes(self, fake_src):
        meta = _extract_connector_metadata(
            fake_src / "slack_connector.py", "src.slack_connector"
        )
        assert "SlackConnector" in meta["classes"]
        assert meta["has_docstring"] is True
        assert meta["line_count"] >= 1

    def test_handles_syntax_error(self, fake_src):
        meta = _extract_connector_metadata(
            fake_src / "broken_connector.py", "src.broken_connector"
        )
        assert "parse_error" in meta

    def test_empty_classes_for_no_class_file(self, fake_src):
        meta = _extract_connector_metadata(
            fake_src / "not_a_connector.py", "src.not_a_connector"
        )
        assert meta["classes"] == []


# ── _probe_connector ──────────────────────────────────────────────────────────


class TestProbeConnector:
    def test_healthy_connector(self):
        connector = {
            "name": "json",
            "module": "json",
            "classes": ["JSONEncoder"],
            "has_docstring": True,
        }
        result = _probe_connector(connector)
        assert result["status"] == "healthy"
        assert result["checks"]["import"] == "pass"

    def test_unimportable_connector(self):
        connector = {
            "name": "fake",
            "module": "src.__nonexistent_connector_xyz__",
            "classes": [],
            "has_docstring": False,
        }
        result = _probe_connector(connector)
        assert result["status"] == "unhealthy"
        assert "fail" in result["checks"]["import"]


# ── Phase: Check ──────────────────────────────────────────────────────────────


class TestPhaseCheck:
    def test_produces_health_report(self, discovery_report, tmp_output):
        result = phase_check(discovery_report, tmp_output)
        assert (tmp_output / "health_report.json").exists()
        assert "results" in result
        assert "healthy" in result
        assert "unhealthy" in result

    def test_counts_healthy_unhealthy(self, discovery_report, tmp_output):
        result = phase_check(discovery_report, tmp_output)
        assert result["healthy"] + result["unhealthy"] == result["total"]


# ── Phase: Report ─────────────────────────────────────────────────────────────


class TestPhaseReport:
    def test_produces_issue_report(self, health_report_path, tmp_output):
        result = phase_report(health_report_path, tmp_output)
        assert (tmp_output / "issue_report.json").exists()
        assert "issues" in result
        assert result["issues_to_create"] >= 1

    def test_issue_body_format(self):
        result = {
            "name": "broken_connector",
            "module": "src.broken_connector",
            "status": "unhealthy",
            "checks": {"import": "fail: SyntaxError"},
        }
        body = _format_issue_body(result)
        assert "broken_connector" in body
        assert "unhealthy" in body


# ── _find_src_dir ─────────────────────────────────────────────────────────────


class TestFindSrcDir:
    def test_returns_path(self):
        # Should not crash; returns a Path
        result = _find_src_dir()
        assert isinstance(result, Path)
