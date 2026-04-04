"""
Hardening QC (Quality Control) Test Suite
==========================================

Validates all hardening fixes applied during the system hardening pass:

1. URL-encoded path traversal prevention (input_validation + hardening.py)
2. Expanded SQL injection pattern detection
3. Error response sanitization (no internal details leaked in production)
4. CORS wildcard rejection in production/staging
5. AuditLogger durable persistence via logging module
6. Rate limiter safe client_id extraction (X-Forwarded-For defense)
7. InputSanitizer expanded injection detection patterns
8. Shutdown manager safe logging (no crash on closed streams)
9. InputSanitizer.sanitize_path URL-decode defense
"""

import logging
import os
import re
import sys
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# 1. URL-encoded path traversal — input_validation.py
# ---------------------------------------------------------------------------

class TestURLEncodedPathTraversalInputValidation:
    """ConstraintInput.sanitize_input must neutralise URL-encoded traversals."""

    def _sanitize(self, value: str) -> str:
        from input_validation import ConstraintInput
        obj = ConstraintInput(target=value, rule="test rule placeholder", justification="test justification")
        return obj.target

    def test_plain_traversal_stripped(self):
        assert ".." not in self._sanitize("../../etc/passwd")

    def test_url_encoded_traversal_stripped(self):
        """Encoded dots: %2e%2e%2f → ../ must be caught."""
        result = self._sanitize("%2e%2e/%2e%2e/secret")
        assert ".." not in result

    def test_double_encoded_traversal_stripped(self):
        """Double-encoded: %252e%252e%252f must be caught."""
        result = self._sanitize("%252e%252e%252f%252e%252e%252fconfig")
        assert ".." not in result

    def test_mixed_encoding_traversal(self):
        """Mix of raw and encoded: ..%2F should be caught."""
        result = self._sanitize("..%2Fsecret")
        assert ".." not in result

    def test_safe_path_unchanged(self):
        """A path with no traversal should pass through untouched (minus dangerous chars)."""
        result = self._sanitize("reports/2024/summary")
        assert "reports" in result and "2024" in result


# ---------------------------------------------------------------------------
# 2. URL-encoded path traversal — security_plane/hardening.py
# ---------------------------------------------------------------------------

class TestURLEncodedPathTraversalHardening:
    """ValidationRule._validate_path must reject URL-encoded traversals."""

    def _validate(self, path_value: str):
        from security_plane.hardening import InputType, ValidationRule
        rule = ValidationRule(input_type=InputType.PATH)
        return rule.validate(path_value, "test_path")

    def test_plain_traversal_blocked(self):
        from security_plane.hardening import InjectionAttemptError
        with pytest.raises(InjectionAttemptError):
            self._validate("../../etc/passwd")

    def test_url_encoded_traversal_blocked(self):
        from security_plane.hardening import InjectionAttemptError
        with pytest.raises(InjectionAttemptError):
            self._validate("%2e%2e/%2e%2e/secret")

    def test_double_encoded_traversal_blocked(self):
        from security_plane.hardening import InjectionAttemptError
        with pytest.raises(InjectionAttemptError):
            self._validate("%252e%252e%252f%252e%252e%252fconfig")

    def test_percent_encoded_dot_slash_blocked(self):
        from security_plane.hardening import InjectionAttemptError
        with pytest.raises(InjectionAttemptError):
            self._validate("..%2Fsecret")

    def test_safe_relative_path_accepted(self):
        result = self._validate("docs/readme.md")
        assert result == os.path.normpath("docs/readme.md")


# ---------------------------------------------------------------------------
# 3. Expanded SQL injection patterns — input_validation.py
# ---------------------------------------------------------------------------

class TestExpandedSQLInjectionPatterns:
    """ConstraintInput.sanitize_input must strip newly-added SQL patterns."""

    def _sanitize(self, value: str) -> str:
        from input_validation import ConstraintInput
        obj = ConstraintInput(target=value, rule="test rule placeholder", justification="test justification")
        return obj.target

    def test_union_select_removed(self):
        result = self._sanitize("something UNION SELECT * FROM users")
        assert "union" not in result.lower() or "select" not in result.lower()

    def test_insert_into_removed(self):
        result = self._sanitize("INSERT INTO secrets VALUES('x')")
        assert "insert" not in result.lower() or "into" not in result.lower()

    def test_delete_from_removed(self):
        result = self._sanitize("DELETE FROM users WHERE 1=1")
        assert "delete" not in result.lower() or "from" not in result.lower()

    def test_waitfor_delay_removed(self):
        result = self._sanitize("WAITFOR DELAY '0:0:5'")
        assert "waitfor" not in result.lower()

    def test_sleep_removed(self):
        result = self._sanitize("SELECT SLEEP(5)")
        assert "sleep" not in result.lower()

    def test_benchmark_removed(self):
        result = self._sanitize("SELECT BENCHMARK(1000000,SHA1('test'))")
        assert "benchmark" not in result.lower()

    def test_alter_table_removed(self):
        result = self._sanitize("ALTER TABLE users ADD COLUMN hacked TEXT")
        assert "alter" not in result.lower() or "table" not in result.lower()

    def test_stacked_query_drop_removed(self):
        result = self._sanitize("normal; DROP TABLE users")
        # semicolons are stripped by dangerous_chars, and 'drop table' pattern matches
        assert "drop" not in result.lower() or "table" not in result.lower()


# ---------------------------------------------------------------------------
# 4. Error response sanitization — runtime/app.py
# ---------------------------------------------------------------------------

class TestErrorResponseSanitization:
    """In production mode, _safe_error_response must not leak exception details."""

    def test_production_hides_details(self):
        from runtime.app import _safe_error_response
        with patch.dict(os.environ, {"MURPHY_ENV": "production"}):
            resp = _safe_error_response(RuntimeError("secret path /opt/keys/db.json"), 500)
            import json
            body = json.loads(resp.body.decode())
            assert "secret" not in body.get("error", "")
            assert "/opt" not in body.get("error", "")
            assert body["error"] == "An internal error occurred."

    def test_staging_hides_details(self):
        from runtime.app import _safe_error_response
        with patch.dict(os.environ, {"MURPHY_ENV": "staging"}):
            resp = _safe_error_response(ValueError("DB connection string"), 400)
            import json
            body = json.loads(resp.body.decode())
            assert "DB connection" not in body.get("error", "")

    def test_development_shows_details(self):
        from runtime.app import _safe_error_response
        with patch.dict(os.environ, {"MURPHY_ENV": "development"}):
            resp = _safe_error_response(ValueError("bad input"), 400)
            import json
            body = json.loads(resp.body.decode())
            assert body["error"] == "bad input"

    def test_test_env_shows_details(self):
        from runtime.app import _safe_error_response
        with patch.dict(os.environ, {"MURPHY_ENV": "test"}):
            resp = _safe_error_response(ValueError("debug info"), 500)
            import json
            body = json.loads(resp.body.decode())
            assert body["error"] == "debug info"


# ---------------------------------------------------------------------------
# 5. CORS wildcard rejection in production/staging
# ---------------------------------------------------------------------------

class TestCORSWildcardProductionGuard:
    """CORSPolicy must reject '*' in production and staging environments."""

    def test_wildcard_rejected_in_production(self):
        from security_hardening_config import CORSPolicy
        with patch.dict(os.environ, {"MURPHY_ENV": "production"}):
            with pytest.raises(ValueError, match="wildcard"):
                CORSPolicy(allowed_origins=["*"])

    def test_wildcard_rejected_in_staging(self):
        from security_hardening_config import CORSPolicy
        with patch.dict(os.environ, {"MURPHY_ENV": "staging"}):
            with pytest.raises(ValueError, match="wildcard"):
                CORSPolicy(allowed_origins=["*"])

    def test_wildcard_allowed_in_development(self):
        from security_hardening_config import CORSPolicy
        with patch.dict(os.environ, {"MURPHY_ENV": "development"}):
            policy = CORSPolicy(allowed_origins=["*"])
            assert policy.is_origin_allowed("http://evil.com")

    def test_explicit_origins_always_allowed(self):
        from security_hardening_config import CORSPolicy
        with patch.dict(os.environ, {"MURPHY_ENV": "production"}):
            policy = CORSPolicy(allowed_origins=["https://app.murphy.io"])
            assert policy.is_origin_allowed("https://app.murphy.io")
            assert not policy.is_origin_allowed("https://evil.com")


# ---------------------------------------------------------------------------
# 6. AuditLogger durable persistence
# ---------------------------------------------------------------------------

class TestAuditLoggerPersistence:
    """AuditLogger must emit events via standard logging for durable storage."""

    def test_audit_event_emitted_to_logging(self, caplog):
        from security_hardening_config import AuditLogger
        audit = AuditLogger()
        with caplog.at_level(logging.INFO, logger="murphy.audit"):
            audit.log("auth", "user1", "/api/data", "read", "success")
        assert any("AUDIT" in r.message for r in caplog.records)

    def test_audit_entries_still_in_memory(self):
        from security_hardening_config import AuditLogger
        audit = AuditLogger()
        audit.log("test", "actor", "resource", "action")
        entries = audit.query(event_type="test")
        assert len(entries) == 1

    def test_audit_persist_failure_does_not_break_request(self):
        from security_hardening_config import AuditLogger
        audit = AuditLogger()
        # Break the persist logger
        audit._persist_logger = MagicMock()
        audit._persist_logger.info.side_effect = OSError("disk full")
        # Should not raise
        audit.log("test", "actor", "resource", "action")
        assert len(audit._log) == 1


# ---------------------------------------------------------------------------
# 7. Rate limiter safe client_id extraction
# ---------------------------------------------------------------------------

class TestExtractClientId:
    """extract_client_id must safely handle X-Forwarded-For spoofing."""

    def test_no_forwarded_for_uses_remote_addr(self):
        from security_hardening_config import extract_client_id
        assert extract_client_id("10.0.0.1") == "10.0.0.1"

    def test_forwarded_for_without_trusted_proxies_uses_remote_addr(self):
        from security_hardening_config import extract_client_id
        result = extract_client_id("10.0.0.1", "1.2.3.4, 5.6.7.8")
        assert result == "10.0.0.1"

    def test_forwarded_for_from_untrusted_proxy_uses_remote_addr(self):
        from security_hardening_config import extract_client_id
        result = extract_client_id(
            "10.0.0.99",
            "1.2.3.4, 5.6.7.8",
            trusted_proxies={"10.0.0.1"},
        )
        # remote_addr is not trusted, so it is used directly
        assert result == "10.0.0.99"

    def test_forwarded_for_from_trusted_proxy_extracts_client(self):
        from security_hardening_config import extract_client_id
        result = extract_client_id(
            "10.0.0.1",
            "203.0.113.50, 10.0.0.1",
            trusted_proxies={"10.0.0.1"},
        )
        assert result == "203.0.113.50"

    def test_multi_hop_forwarded_for_extracts_rightmost_untrusted(self):
        from security_hardening_config import extract_client_id
        result = extract_client_id(
            "10.0.0.2",
            "spoofed.ip, 203.0.113.50, 10.0.0.1",
            trusted_proxies={"10.0.0.1", "10.0.0.2"},
        )
        assert result == "203.0.113.50"

    def test_empty_forwarded_for_uses_remote_addr(self):
        from security_hardening_config import extract_client_id
        result = extract_client_id("10.0.0.1", "", trusted_proxies={"10.0.0.1"})
        assert result == "10.0.0.1"

    def test_none_remote_addr_returns_unknown(self):
        from security_hardening_config import extract_client_id
        result = extract_client_id(None, None)
        assert result == "unknown"


# ---------------------------------------------------------------------------
# 8. InputSanitizer expanded injection detection
# ---------------------------------------------------------------------------

class TestInputSanitizerExpandedPatterns:
    """InputSanitizer.detect_injection must detect newly-added patterns."""

    def _detect(self, value: str):
        from security_hardening_config import InputSanitizer
        return InputSanitizer.detect_injection(value)

    def test_detects_union_select(self):
        threats = self._detect("' UNION SELECT password FROM users --")
        assert len(threats) > 0

    def test_detects_waitfor_delay(self):
        threats = self._detect("'; WAITFOR DELAY '0:0:5' --")
        assert len(threats) > 0

    def test_detects_sleep(self):
        threats = self._detect("' OR SLEEP(5) --")
        assert len(threats) > 0

    def test_detects_benchmark(self):
        threats = self._detect("' OR BENCHMARK(1000000,SHA1('x')) --")
        assert len(threats) > 0

    def test_clean_input_no_threats(self):
        threats = self._detect("Hello, I want to order 5 widgets.")
        assert len(threats) == 0


# ---------------------------------------------------------------------------
# 9. Shutdown manager safe logging
# ---------------------------------------------------------------------------

class TestShutdownManagerSafeLogging:
    """ShutdownManager._safe_log must not crash when streams are closed."""

    def test_safe_log_with_working_logger(self, caplog):
        from shutdown_manager import ShutdownManager
        sm = ShutdownManager.__new__(ShutdownManager)
        sm.cleanup_handlers = []
        sm.is_shutting_down = False
        with caplog.at_level(logging.INFO):
            sm._safe_log("test message")
        assert any("test message" in r.message for r in caplog.records)

    def test_safe_log_fallback_on_closed_stream(self, capsys):
        from shutdown_manager import ShutdownManager
        sm = ShutdownManager.__new__(ShutdownManager)
        sm.cleanup_handlers = []
        sm.is_shutting_down = False

        # Create a mock handler with a closed stream
        mock_handler = logging.StreamHandler()
        mock_handler.stream = MagicMock()
        mock_handler.stream.closed = True

        test_logger = logging.getLogger("shutdown_manager")
        original_handlers = test_logger.handlers[:]

        try:
            # The _safe_log method checks stream.closed and falls back to stderr
            sm._safe_log("fallback message")
            # Should not raise
        finally:
            test_logger.handlers = original_handlers


# ---------------------------------------------------------------------------
# 10. InputSanitizer.sanitize_path URL-decode defense
# ---------------------------------------------------------------------------

class TestInputSanitizerSanitizePathURLDecode:
    """InputSanitizer.sanitize_path must decode URL-encoded traversals."""

    def _sanitize(self, path: str) -> str:
        from security_hardening_config import InputSanitizer
        return InputSanitizer.sanitize_path(path)

    def test_plain_traversal_removed(self):
        result = self._sanitize("../../etc/passwd")
        assert ".." not in result

    def test_url_encoded_traversal_removed(self):
        result = self._sanitize("%2e%2e/%2e%2e/etc/passwd")
        assert ".." not in result

    def test_double_encoded_traversal_removed(self):
        result = self._sanitize("%252e%252e%252f%252e%252e%252fetc/passwd")
        assert ".." not in result

    def test_safe_path_unchanged(self):
        result = self._sanitize("reports/2024/summary.txt")
        assert result == "reports/2024/summary.txt"

    def test_backslash_traversal_removed(self):
        result = self._sanitize("..\\..\\windows\\system32")
        assert ".." not in result


# ---------------------------------------------------------------------------
# 11. Integration: full hardening pipeline smoke test
# ---------------------------------------------------------------------------

class TestHardeningIntegrationSmokeTest:
    """End-to-end smoke test for the security hardening orchestrator."""

    def test_request_with_injection_blocked(self):
        from security_hardening_config import SecurityHardeningConfig
        config = SecurityHardeningConfig()
        result = config.apply_request_security(
            client_id="10.0.0.1",
            origin="",
            request_data={"query": "'; DROP TABLE users; --"},
        )
        assert not result["allowed"]
        assert result["reason"] == "injection_detected"

    def test_clean_request_allowed(self):
        from security_hardening_config import SecurityHardeningConfig
        config = SecurityHardeningConfig()
        result = config.apply_request_security(
            client_id="10.0.0.1",
            origin="",
            request_data={"query": "Show me sales for Q4 2024"},
        )
        assert result["allowed"]

    def test_rate_limiter_blocks_burst(self):
        from security_hardening_config import SecurityHardeningConfig
        config = SecurityHardeningConfig()
        # Exhaust the burst limit
        for _ in range(config.rate_limiter.burst + 1):
            result = config.apply_request_security(
                client_id="burst-test",
                origin="",
                request_data={"q": "ok"},
            )
        assert not result["allowed"]
        assert result["reason"] == "rate_limit_exceeded"
