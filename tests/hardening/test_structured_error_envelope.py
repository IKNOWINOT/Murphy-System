"""
Module: tests/hardening/test_structured_error_envelope.py
Subsystem: Error Envelope — Structured API Error Responses
Label: TEST-ENVELOPE-001 — Commission tests for error_envelope.py

Commissioning Answers (G1–G9)
-----------------------------
G1  What does the module do?
    Provides production-grade structured error envelopes (RFC 9457-inspired)
    for all Murphy API responses, including success/error wrappers,
    StructuredError dataclass, paginated responses, error categories, and
    backward-compatible legacy helpers.

G2  What specification / design-label does it fulfil?
    ENVELOPE-001 as documented in Murphy System 1.0 Production Spec.

G3  Under what conditions should it succeed / fail?
    Succeed: response shapes match the documented schema; 5xx messages are
    scrubbed; auto-generated fields (correlation_id, timestamp) are valid;
    pagination math is correct; all 8 categories exist.
    Fail: schema drift; sensitive details leak in 5xx responses; missing
    fields in StructuredError.

G4  What is the test-profile?
    Pure unit tests — no network, no disk, no external services.

G5  Any external dependencies?
    FastAPI (JSONResponse).

G6  Can the tests run in CI without credentials?
    Yes.

G7  Expected run-time?
    < 1 s.

G8  Owner / maintainer?
    Platform Engineering.

G9  Review date?
    On every PR that modifies src/error_envelope.py.
"""
from __future__ import annotations

import json
import math
import uuid

import pytest

from src.error_envelope import (
    ErrorCategory,
    StructuredError,
    _STATUS_TO_CATEGORY,
    error_response,
    paginated_response,
    structured_error_response,
    success_response,
)


# ── Helper to extract JSON body from JSONResponse ─────────────────────────


def _body(resp) -> dict:
    """Decode a JSONResponse body to a Python dict."""
    return json.loads(resp.body.decode())


# ── Legacy Helpers ─────────────────────────────────────────────────────────


class TestLegacyHelpers:
    """TEST-ENVELOPE-001 — Backward-compatible success/error helpers."""

    def test_success_response(self) -> None:
        """success_response returns {"success": true, "data": payload}."""
        resp = success_response(data={"key": "value"})
        body = _body(resp)
        assert body["success"] is True
        assert body["data"] == {"key": "value"}
        assert resp.status_code == 200

    def test_error_response(self) -> None:
        """error_response returns {"success": false, "error": {"code": ..., "message": ...}}."""
        resp = error_response("INVALID", "bad request", status_code=422)
        body = _body(resp)
        assert body["success"] is False
        assert body["error"]["code"] == "INVALID"
        assert body["error"]["message"] == "bad request"
        assert resp.status_code == 422

    def test_backward_compatibility_success(self) -> None:
        """Old success_response signature still works (data kwarg)."""
        resp = success_response(data=None)
        body = _body(resp)
        assert body["success"] is True
        assert body["data"] is None

    def test_backward_compatibility_error(self) -> None:
        """Old error_response positional signature still works."""
        resp = error_response("CODE", "msg")
        body = _body(resp)
        assert body["success"] is False
        assert resp.status_code == 400  # default


# ── StructuredError Dataclass ──────────────────────────────────────────────


class TestStructuredError:
    """TEST-ENVELOPE-001 — StructuredError dataclass validation."""

    def test_structured_error_fields(self) -> None:
        """StructuredError has all required fields."""
        err = StructuredError(
            code="TEST_ERR",
            message="something broke",
            category=ErrorCategory.INTERNAL,
            retryable=False,
        )
        d = err.to_dict()
        required_keys = {
            "code", "message", "category", "retryable",
            "retry_after_seconds", "correlation_id", "timestamp",
        }
        assert required_keys.issubset(d.keys())

    def test_structured_error_auto_correlation_id(self) -> None:
        """UUID auto-generated for correlation_id."""
        err = StructuredError(
            code="X", message="x", category=ErrorCategory.VALIDATION,
        )
        # Should be a valid UUID-4 string
        parsed = uuid.UUID(err.correlation_id, version=4)
        assert str(parsed) == err.correlation_id

    def test_structured_error_auto_timestamp(self) -> None:
        """ISO 8601 timestamp auto-generated."""
        err = StructuredError(
            code="X", message="x", category=ErrorCategory.VALIDATION,
        )
        # Must contain 'T' separator and timezone info ('+' or 'Z')
        assert "T" in err.timestamp
        assert "+" in err.timestamp or "Z" in err.timestamp


# ── Structured Error Responses ─────────────────────────────────────────────


class TestStructuredErrorResponse:
    """TEST-ENVELOPE-001 — structured_error_response behaviour."""

    def test_structured_error_response_4xx(self) -> None:
        """Detail message preserved for client errors (4xx)."""
        resp = structured_error_response(
            "BAD_INPUT", "Field 'email' is required", status_code=400,
        )
        body = _body(resp)
        assert body["success"] is False
        assert body["error"]["message"] == "Field 'email' is required"
        assert resp.status_code == 400

    def test_structured_error_response_5xx(self) -> None:
        """Message scrubbed to 'Internal server error' for 5xx."""
        resp = structured_error_response(
            "DB_CRASH", "PostgreSQL connection pool exhausted", status_code=500,
        )
        body = _body(resp)
        assert body["error"]["message"] == "Internal server error"
        assert resp.status_code == 500


# ── Paginated Response ─────────────────────────────────────────────────────


class TestPaginatedResponse:
    """TEST-ENVELOPE-001 — paginated_response."""

    def test_paginated_response(self) -> None:
        """Includes pagination metadata."""
        resp = paginated_response(
            data=["a", "b"], page=1, per_page=2, total=10,
        )
        body = _body(resp)
        assert body["success"] is True
        assert body["data"] == ["a", "b"]
        pag = body["pagination"]
        assert pag["page"] == 1
        assert pag["per_page"] == 2
        assert pag["total"] == 10
        assert "total_pages" in pag

    def test_paginated_response_total_pages(self) -> None:
        """total_pages = math.ceil(total / per_page)."""
        resp = paginated_response(
            data=[], page=1, per_page=3, total=10,
        )
        body = _body(resp)
        assert body["pagination"]["total_pages"] == math.ceil(10 / 3)


# ── Error Categories ───────────────────────────────────────────────────────


class TestErrorCategories:
    """TEST-ENVELOPE-001 — ErrorCategory enum and status mapping."""

    def test_error_category_values(self) -> None:
        """All 8 categories exist."""
        expected = {
            "VALIDATION", "AUTH", "NOT_FOUND", "CONFLICT",
            "RATE_LIMIT", "INTERNAL", "TIMEOUT", "DEPENDENCY",
        }
        actual = {cat.value for cat in ErrorCategory}
        assert actual == expected

    def test_status_to_category_mapping(self) -> None:
        """429 → RATE_LIMIT (retryable), 404 → NOT_FOUND (not retryable)."""
        cat_429, retry_429 = _STATUS_TO_CATEGORY[429]
        assert cat_429 == ErrorCategory.RATE_LIMIT
        assert retry_429 is True

        cat_404, retry_404 = _STATUS_TO_CATEGORY[404]
        assert cat_404 == ErrorCategory.NOT_FOUND
        assert retry_404 is False
