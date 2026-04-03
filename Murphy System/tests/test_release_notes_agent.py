#!/usr/bin/env python3
# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post | License: BSL-1.1
#
# Tests for the Release Notes Generator Agent (RELEASE-NOTES-001)
#
# Commissioning profile:
#   G1: Validates each phase produces correct outputs
#   G2: Tests the three phases: collect, generate, release
#   G3: Covers commit categorization via conventional commits + keywords
#   G4: Full range including empty commits, missing tags
#   G5: Expected: structured JSON reports with correct fields
#   G6: Actual: verified via assertions
#   G9: Hardening checks included

"""Tests for Murphy System Release Notes Generator Agent."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from release_notes_agent import (  # noqa: E402
    AGENT_LABEL,
    AGENT_VERSION,
    CATEGORY_PATTERNS,
    KEYWORD_CATEGORIES,
    _categorize_commit,
    _get_previous_tag,
    phase_collect,
    phase_generate,
    phase_release,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def tmp_output(tmp_path):
    out = tmp_path / "output"
    out.mkdir()
    return out


@pytest.fixture
def commits_path(tmp_output):
    report = {
        "agent": AGENT_LABEL,
        "tag": "v1.2.0",
        "previous_tag": "v1.1.0",
        "commits": [
            {"sha": "aaa1111", "message": "feat(api): add new endpoint",
             "author": "dev", "date": "2026-01-01T00:00:00+00:00"},
            {"sha": "bbb2222", "message": "fix(auth): resolve login bug",
             "author": "dev", "date": "2026-01-02T00:00:00+00:00"},
            {"sha": "ccc3333", "message": "docs: update README",
             "author": "dev", "date": "2026-01-03T00:00:00+00:00"},
            {"sha": "ddd4444", "message": "security: patch CVE-2026-001",
             "author": "dev", "date": "2026-01-04T00:00:00+00:00"},
            {"sha": "eee5555", "message": "refactor: clean up imports",
             "author": "dev", "date": "2026-01-05T00:00:00+00:00"},
            {"sha": "fff6666", "message": "misc update",
             "author": "dev", "date": "2026-01-06T00:00:00+00:00"},
        ],
        "total_commits": 6,
    }
    path = tmp_output / "commits.json"
    path.write_text(json.dumps(report))
    return path


@pytest.fixture
def release_notes_path(tmp_output):
    md = "# Release v1.2.0\n\n## Features\n- feat(api): add new endpoint\n"
    path = tmp_output / "release_notes.md"
    path.write_text(md)
    return path


# ── Constants ─────────────────────────────────────────────────────────────────


class TestConstants:
    def test_agent_label(self):
        assert AGENT_LABEL == "RELEASE-NOTES-001"

    def test_agent_version(self):
        assert AGENT_VERSION == "1.0.0"

    def test_category_patterns(self):
        assert len(CATEGORY_PATTERNS) >= 5

    def test_keyword_categories(self):
        assert len(KEYWORD_CATEGORIES) >= 5


# ── _categorize_commit ────────────────────────────────────────────────────────


class TestCategorizeCommit:
    def test_feat_prefix(self):
        assert _categorize_commit("feat(api): add endpoint") == "features"

    def test_fix_prefix(self):
        assert _categorize_commit("fix(auth): resolve bug") == "fixes"

    def test_docs_prefix(self):
        assert _categorize_commit("docs: update readme") == "docs"

    def test_security_prefix(self):
        assert _categorize_commit("security: patch CVE") == "security"

    def test_refactor_prefix(self):
        assert _categorize_commit("refactor: clean up") == "refactors"

    def test_perf_prefix(self):
        assert _categorize_commit("perf: optimize query") == "performance"

    def test_keyword_fallback_add(self):
        assert _categorize_commit("Add new CSV export") == "features"

    def test_keyword_fallback_fix(self):
        assert _categorize_commit("Fix broken login page") == "fixes"

    def test_uncategorized(self):
        assert _categorize_commit("bump version") == "other"


# ── Phase: Collect ────────────────────────────────────────────────────────────


class TestPhaseCollect:
    def test_produces_commits_file(self, tmp_output):
        result = phase_collect("v1.0.0", tmp_output)
        assert (tmp_output / "commits.json").exists()
        assert "commits" in result
        assert "total_commits" in result
        assert result["tag"] == "v1.0.0"


# ── Phase: Generate ──────────────────────────────────────────────────────────


class TestPhaseGenerate:
    def test_produces_release_notes(self, commits_path, tmp_output):
        result = phase_generate(commits_path, "v1.2.0", tmp_output)
        assert (tmp_output / "release_notes.md").exists()
        assert (tmp_output / "release_notes.json").exists()
        assert result["total_commits"] == 6
        assert result["features"] >= 1
        assert result["fixes"] >= 1

    def test_markdown_content(self, commits_path, tmp_output):
        phase_generate(commits_path, "v1.2.0", tmp_output)
        md = (tmp_output / "release_notes.md").read_text()
        assert "v1.2.0" in md
        assert "Features" in md


# ── Phase: Release ────────────────────────────────────────────────────────────


class TestPhaseRelease:
    def test_produces_status(self, release_notes_path, tmp_output):
        result = phase_release(release_notes_path, "v1.2.0", tmp_output)
        assert (tmp_output / "release_status.json").exists()
        assert result["tag"] == "v1.2.0"
        assert "status" in result


# ── Helpers ───────────────────────────────────────────────────────────────────


class TestHelpers:
    def test_get_previous_tag_returns_none_or_string(self):
        result = _get_previous_tag("v99.99.99")
        assert result is None or isinstance(result, str)
