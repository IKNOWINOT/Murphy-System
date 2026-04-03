#!/usr/bin/env python3
# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post | License: BSL-1.1
#
# Tests for the Security Posture Agent (SEC-POSTURE-001)
#
# Commissioning profile:
#   G1: Validates each phase produces correct outputs
#   G2: Tests six phases: bandit, secrets, ssrf, hitl, authority, score
#   G3: Covers scoring formula and threshold logic
#   G4: Full range including clean and dirty codebases
#   G5: Expected: structured JSON reports with correct fields
#   G6: Actual: verified via assertions
#   G9: Hardening checks included

"""Tests for Murphy System Security Posture Agent."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest


from security_posture_agent import (  # noqa: E402
    AGENT_LABEL,
    AGENT_VERSION,
    SECRET_PATTERNS,
    SSRF_PATTERNS,
    phase_authority,
    phase_bandit,
    phase_hitl,
    phase_score,
    phase_secrets,
    phase_ssrf,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def tmp_output(tmp_path):
    out = tmp_path / "output"
    out.mkdir()
    return out


@pytest.fixture
def clean_phase_results(tmp_output):
    """Simulate all phases returning zero findings."""
    for name, key in [
        ("bandit_results", "findings"),
        ("secret_scan", "detections"),
        ("ssrf_scan", "risks"),
        ("hitl_check", "gaps"),
        ("authority_check", "issues"),
    ]:
        (tmp_output / f"{name}.json").write_text(json.dumps({key: 0}))
    return tmp_output


@pytest.fixture
def dirty_phase_results(tmp_output):
    """Simulate phases with findings."""
    (tmp_output / "bandit_results.json").write_text(json.dumps({"findings": 10}))
    (tmp_output / "secret_scan.json").write_text(json.dumps({"detections": 3}))
    (tmp_output / "ssrf_scan.json").write_text(json.dumps({"risks": 2}))
    (tmp_output / "hitl_check.json").write_text(json.dumps({"gaps": 1}))
    (tmp_output / "authority_check.json").write_text(json.dumps({"issues": 1}))
    return tmp_output


# ── Constants ─────────────────────────────────────────────────────────────────


class TestConstants:
    def test_agent_label(self):
        assert AGENT_LABEL == "SEC-POSTURE-001"

    def test_agent_version(self):
        assert AGENT_VERSION == "1.0.0"

    def test_ssrf_patterns_non_empty(self):
        assert len(SSRF_PATTERNS) >= 3

    def test_secret_patterns_non_empty(self):
        assert len(SECRET_PATTERNS) >= 3


# ── Individual Phases ─────────────────────────────────────────────────────────


class TestPhaseBandit:
    def test_produces_report(self, tmp_output):
        result = phase_bandit(tmp_output)
        assert (tmp_output / "bandit_results.json").exists()
        assert "findings" in result


class TestPhaseSecrets:
    def test_produces_report(self, tmp_output):
        result = phase_secrets(tmp_output)
        assert (tmp_output / "secret_scan.json").exists()
        assert "detections" in result


class TestPhaseSsrf:
    def test_produces_report(self, tmp_output):
        result = phase_ssrf(tmp_output)
        assert (tmp_output / "ssrf_scan.json").exists()
        assert "risks" in result


class TestPhaseHitl:
    def test_produces_report(self, tmp_output):
        result = phase_hitl(tmp_output)
        assert (tmp_output / "hitl_check.json").exists()
        assert "gaps" in result


class TestPhaseAuthority:
    def test_produces_report(self, tmp_output):
        result = phase_authority(tmp_output)
        assert (tmp_output / "authority_check.json").exists()
        assert "issues" in result


# ── Phase: Score ──────────────────────────────────────────────────────────────


class TestPhaseScore:
    def test_perfect_score(self, clean_phase_results):
        result = phase_score(clean_phase_results, 60)
        assert result["score"] == 100
        assert result["passed"] is True

    def test_reduced_score(self, dirty_phase_results):
        # threshold=0 to avoid SystemExit
        result = phase_score(dirty_phase_results, 0)
        assert result["score"] < 100
        assert result["score"] >= 0

    def test_blocks_below_threshold(self, dirty_phase_results):
        with pytest.raises(SystemExit) as exc_info:
            phase_score(dirty_phase_results, 99)
        assert exc_info.value.code == 1

    def test_creates_markdown(self, clean_phase_results):
        phase_score(clean_phase_results, 60)
        assert (clean_phase_results / "posture_report.md").exists()
        md = (clean_phase_results / "posture_report.md").read_text()
        assert "Security Posture" in md
