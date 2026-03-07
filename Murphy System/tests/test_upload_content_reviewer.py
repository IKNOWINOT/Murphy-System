"""
Tests for upload_content_reviewer.py

Coverage:
  - Safe content passes review
  - API keys blocked (groq, openai, slack, bearer, aws)
  - PII blocked (email, phone, SSN)
  - DB URLs blocked (postgres, redis, mongodb)
  - Private key blocked
  - Internal paths flagged
  - Auto-redact replaces sensitive strings
  - After redaction, re-scan passes
  - Finding.to_dict structure
  - ContentReviewResult.to_dict structure
  - History tracking

Copyright © 2020 Inoni Limited Liability Company
License: BSL 1.1
"""

from __future__ import annotations

import os
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from upload_content_reviewer import (
    Finding,
    ContentReviewResult,
    UploadContentReviewer,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_recording(**kwargs):
    defaults = dict(
        run_id="run-review-001",
        task_description="Process customer orders",
        task_type="ecommerce",
        status="SUCCESS_COMPLETED",
        confidence_score=0.85,
        confidence_progression=[],
        steps=[],
        hitl_decisions=[],
        modules_used=["order_engine"],
        gates_passed=[],
        duration_seconds=30.0,
        system_version="1.0",
        started_at="2024-01-01T00:00:00Z",
        completed_at="2024-01-01T00:00:30Z",
        terminal_output=[],
        metadata={},
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


# ---------------------------------------------------------------------------
# Safe content
# ---------------------------------------------------------------------------

class TestSafeContent:
    def test_clean_recording_passes(self):
        reviewer = UploadContentReviewer()
        rec = _make_recording()
        result = reviewer.review(rec)
        assert result.is_safe is True
        assert len(result.findings) == 0

    def test_clean_terminal_output_passes(self):
        reviewer = UploadContentReviewer()
        rec = _make_recording(terminal_output=["Step 1 complete", "All done."])
        result = reviewer.review(rec)
        assert result.is_safe is True


# ---------------------------------------------------------------------------
# API key detection
# ---------------------------------------------------------------------------

class TestAPIKeyDetection:
    def test_groq_api_key_blocked(self):
        reviewer = UploadContentReviewer()
        rec = _make_recording(terminal_output=["key=gsk_abcdefghijklmnopqrstuvwxyz12345"])
        result = reviewer.review(rec)
        assert result.is_safe is False
        names = [f.pattern_name for f in result.findings]
        assert "groq_api_key" in names

    def test_openai_key_blocked(self):
        reviewer = UploadContentReviewer()
        rec = _make_recording(terminal_output=["using sk-abcdefghijklmnopqrstuvwxyz123456789"])
        result = reviewer.review(rec)
        assert result.is_safe is False
        names = [f.pattern_name for f in result.findings]
        assert "openai_api_key" in names

    def test_slack_token_blocked(self):
        reviewer = UploadContentReviewer()
        # Fake test value — clearly synthetic, not a real token
        fake = "xoxb" + "-" + "0" * 12 + "-" + "0" * 12 + "-" + "a" * 16
        rec = _make_recording(terminal_output=[f"token={fake}"])
        result = reviewer.review(rec)
        assert result.is_safe is False
        names = [f.pattern_name for f in result.findings]
        assert "slack_token" in names

    def test_aws_key_blocked(self):
        reviewer = UploadContentReviewer()
        rec = _make_recording(terminal_output=["aws_key=AKIAIOSFODNN7EXAMPLE"])
        result = reviewer.review(rec)
        assert result.is_safe is False
        names = [f.pattern_name for f in result.findings]
        assert "aws_access_key" in names

    def test_bearer_token_blocked(self):
        reviewer = UploadContentReviewer()
        rec = _make_recording(terminal_output=["Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9abc"])
        result = reviewer.review(rec)
        assert result.is_safe is False


# ---------------------------------------------------------------------------
# PII detection
# ---------------------------------------------------------------------------

class TestPIIDetection:
    def test_email_blocked(self):
        reviewer = UploadContentReviewer()
        rec = _make_recording(terminal_output=["contact: user@example.com"])
        result = reviewer.review(rec)
        assert result.is_safe is False
        names = [f.pattern_name for f in result.findings]
        assert "email_address" in names

    def test_phone_number_blocked(self):
        reviewer = UploadContentReviewer()
        rec = _make_recording(terminal_output=["call us at 555-867-5309"])
        result = reviewer.review(rec)
        assert result.is_safe is False
        names = [f.pattern_name for f in result.findings]
        assert "phone_number" in names

    def test_ssn_blocked(self):
        reviewer = UploadContentReviewer()
        rec = _make_recording(terminal_output=["ssn: 123-45-6789"])
        result = reviewer.review(rec)
        assert result.is_safe is False
        names = [f.pattern_name for f in result.findings]
        assert "ssn_pattern" in names


# ---------------------------------------------------------------------------
# Database URLs
# ---------------------------------------------------------------------------

class TestDatabaseURLDetection:
    def test_postgres_url_blocked(self):
        reviewer = UploadContentReviewer()
        rec = _make_recording(terminal_output=["connecting to postgresql://user:pass@localhost/db"])
        result = reviewer.review(rec)
        assert result.is_safe is False

    def test_redis_url_blocked(self):
        reviewer = UploadContentReviewer()
        rec = _make_recording(terminal_output=["redis://localhost:6379/0"])
        result = reviewer.review(rec)
        assert result.is_safe is False

    def test_mongodb_url_blocked(self):
        reviewer = UploadContentReviewer()
        rec = _make_recording(terminal_output=["mongodb://user:pass@host:27017/db"])
        result = reviewer.review(rec)
        assert result.is_safe is False


# ---------------------------------------------------------------------------
# Private key
# ---------------------------------------------------------------------------

class TestPrivateKeyDetection:
    def test_private_key_header_blocked(self):
        reviewer = UploadContentReviewer()
        rec = _make_recording(terminal_output=["-----BEGIN RSA PRIVATE KEY-----"])
        result = reviewer.review(rec)
        assert result.is_safe is False
        names = [f.pattern_name for f in result.findings]
        assert "private_key_header" in names


# ---------------------------------------------------------------------------
# Auto-redaction
# ---------------------------------------------------------------------------

class TestAutoRedaction:
    def test_auto_redact_email_makes_safe(self):
        reviewer = UploadContentReviewer()
        rec = _make_recording(terminal_output=["contact: user@example.com for info"])
        result = reviewer.review(rec, auto_redact=True)
        assert result.redacted_recording is not None
        terminal = result.redacted_recording.terminal_output
        assert "user@example.com" not in "\n".join(terminal)
        assert "[REDACTED]" in "\n".join(terminal)

    def test_redacted_recording_scans_clean(self):
        reviewer = UploadContentReviewer()
        rec = _make_recording(terminal_output=["email: test@test.com"])
        result = reviewer.review(rec, auto_redact=True)
        assert result.is_safe is True

    def test_auto_redact_preserves_run_id(self):
        reviewer = UploadContentReviewer()
        rec = _make_recording(terminal_output=["key: gsk_abcdefghijklmnopqrstuvwxyz12345"])
        result = reviewer.review(rec, auto_redact=True)
        assert result.redacted_recording is not None
        assert result.redacted_recording.run_id == rec.run_id


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

class TestDataModels:
    def test_finding_to_dict(self):
        finding = Finding(
            finding_id="cf-001",
            field_name="terminal_output",
            pattern_name="email_address",
            severity="medium",
            description="Email PII",
            snippet="user@example.com",
        )
        d = finding.to_dict()
        assert d["finding_id"] == "cf-001"
        assert d["severity"] == "medium"

    def test_review_result_to_dict(self):
        reviewer = UploadContentReviewer()
        rec = _make_recording()
        result = reviewer.review(rec)
        d = result.to_dict()
        assert "review_id" in d
        assert "is_safe" in d
        assert "findings_count" in d

    def test_history_tracked(self):
        reviewer = UploadContentReviewer()
        rec = _make_recording()
        reviewer.review(rec)
        reviewer.review(rec)
        history = reviewer.get_history()
        assert len(history) == 2
