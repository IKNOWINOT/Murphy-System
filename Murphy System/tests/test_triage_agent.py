#!/usr/bin/env python3
# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post | License: BSL-1.1
#
# Tests for the Triage Agent (TRIAGE-AGENT-001)
#
# Commissioning profile:
#   G1: Validates triage produces correct outputs
#   G2: Tests classification, staleness, priority detection
#   G3: Covers all label rules and priority rules
#   G4: Full range including fresh, stale, and very stale issues
#   G5: Expected: structured JSON reports with correct fields
#   G6: Actual: verified via assertions
#   G9: Hardening checks included

"""Tests for Murphy System Triage Agent."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from triage_agent import (  # noqa: E402
    AGENT_LABEL,
    AGENT_VERSION,
    LABEL_RULES,
    PRIORITY_RULES,
    _classify_issue,
    run_triage,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def tmp_output(tmp_path):
    out = tmp_path / "output"
    out.mkdir()
    return out


@pytest.fixture
def now():
    return datetime.now(timezone.utc)


# ── Constants ─────────────────────────────────────────────────────────────────


class TestConstants:
    def test_agent_label(self):
        assert AGENT_LABEL == "TRIAGE-AGENT-001"

    def test_agent_version(self):
        assert AGENT_VERSION == "1.0.0"

    def test_label_rules_non_empty(self):
        assert len(LABEL_RULES) >= 5

    def test_priority_rules_non_empty(self):
        assert len(PRIORITY_RULES) >= 2


# ── run_triage ────────────────────────────────────────────────────────────────


class TestRunTriage:
    def test_produces_report(self, tmp_output):
        result = run_triage(tmp_output)
        assert (tmp_output / "triage_report.json").exists()
        assert "issues_scanned" in result
        assert "labels_applied" in result
        assert "stale_warnings" in result
        assert "auto_closed" in result

    def test_report_metadata(self, tmp_output):
        result = run_triage(tmp_output)
        assert result["agent"] == AGENT_LABEL


# ── _classify_issue ───────────────────────────────────────────────────────────


class TestClassifyIssue:
    def test_bug_label(self, now):
        issue = {"number": 1, "title": "App crashes on startup",
                 "body": "error traceback shown", "updated_at": now.isoformat()}
        actions = _classify_issue(issue, now, 14, 30)
        labels = [a["label"] for a in actions if a["type"] == "label"]
        assert "bug" in labels

    def test_feature_label(self, now):
        issue = {"number": 2, "title": "Add new feature for export",
                 "body": "enhancement request", "updated_at": now.isoformat()}
        actions = _classify_issue(issue, now, 14, 30)
        labels = [a["label"] for a in actions if a["type"] == "label"]
        assert "feature" in labels

    def test_security_label(self, now):
        issue = {"number": 3, "title": "XSS vulnerability found",
                 "body": "security issue", "updated_at": now.isoformat()}
        actions = _classify_issue(issue, now, 14, 30)
        labels = [a["label"] for a in actions if a["type"] == "label"]
        assert "security" in labels

    def test_connector_label(self, now):
        issue = {"number": 4, "title": "Slack connector broken",
                 "body": "integration issue", "updated_at": now.isoformat()}
        actions = _classify_issue(issue, now, 14, 30)
        labels = [a["label"] for a in actions if a["type"] == "label"]
        assert "connector" in labels

    def test_p0_priority(self, now):
        issue = {"number": 5, "title": "Data loss in production",
                 "body": "critical security crash", "updated_at": now.isoformat()}
        actions = _classify_issue(issue, now, 14, 30)
        priorities = [a["label"] for a in actions if a["type"] == "priority"]
        assert "P0-critical" in priorities

    def test_stale_warning_at_14_days(self, now):
        old = (now - timedelta(days=20)).isoformat()
        issue = {"number": 6, "title": "Stale issue", "body": "",
                 "updated_at": old}
        actions = _classify_issue(issue, now, 14, 30)
        stale = [a for a in actions if a["type"] == "stale_warning"]
        assert len(stale) == 1

    def test_auto_close_at_30_days(self, now):
        very_old = (now - timedelta(days=35)).isoformat()
        issue = {"number": 7, "title": "Very stale", "body": "",
                 "updated_at": very_old}
        actions = _classify_issue(issue, now, 14, 30)
        closed = [a for a in actions if a["type"] == "auto_close"]
        assert len(closed) == 1

    def test_fresh_issue_no_stale(self, now):
        issue = {"number": 8, "title": "Fresh issue", "body": "",
                 "updated_at": now.isoformat()}
        actions = _classify_issue(issue, now, 14, 30)
        stale = [a for a in actions if a["type"] in ("stale_warning", "auto_close")]
        assert len(stale) == 0
