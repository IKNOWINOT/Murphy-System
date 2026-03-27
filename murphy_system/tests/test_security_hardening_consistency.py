"""
Murphy System — Security Hardening + Consistency Integration Tests

Tests the security hardening config module and validates system-wide consistency.
"""
import unittest
from datetime import datetime, timedelta, timezone


from src.security_hardening_config import (
    InputSanitizer,
    CORSPolicy,
    RateLimiter,
    ContentSecurityPolicy,
    APIKeyRotationPolicy,
    AuditLogger,
    SessionSecurity,
    SecurityHardeningConfig,
)


# ── Input Sanitization Tests ────────────────────────────────────────

class TestInputSanitizer(unittest.TestCase):
    def test_sanitize_html_entities(self):
        result = InputSanitizer.sanitize_string("<script>alert('xss')</script>")
        self.assertNotIn("<script>", result)
        self.assertIn("&lt;", result)

    def test_sanitize_max_length(self):
        result = InputSanitizer.sanitize_string("a" * 20000, max_length=100)
        self.assertEqual(len(result), 100)

    def test_detect_script_injection(self):
        threats = InputSanitizer.detect_injection("<script>alert(1)</script>")
        self.assertTrue(len(threats) > 0)

    def test_detect_sql_injection(self):
        threats = InputSanitizer.detect_injection("'; DROP TABLE users; --")
        self.assertTrue(len(threats) > 0)

    def test_clean_input_no_threats(self):
        threats = InputSanitizer.detect_injection("Hello, this is normal text.")
        self.assertEqual(len(threats), 0)

    def test_sanitize_path_traversal(self):
        result = InputSanitizer.sanitize_path("../../etc/passwd")
        self.assertNotIn("..", result)

    def test_sanitize_dict_recursive(self):
        data = {"name": "<b>bold</b>", "nested": {"value": "<script>x</script>"}}
        result = InputSanitizer.sanitize_dict(data)
        self.assertNotIn("<b>", result["name"])
        self.assertNotIn("<script>", result["nested"]["value"])

    def test_sanitize_dict_depth_limit(self):
        data = {"a": {"b": {"c": "deep"}}}
        result = InputSanitizer.sanitize_dict(data, max_depth=1)
        self.assertIn("a", result)


# ── CORS Tests ───────────────────────────────────────────────────────

class TestCORSPolicy(unittest.TestCase):
    def test_no_origins_blocks_all(self):
        cors = CORSPolicy()
        self.assertFalse(cors.is_origin_allowed("http://evil.com"))

    def test_allowed_origin(self):
        cors = CORSPolicy(allowed_origins=["http://localhost:3000"])
        self.assertTrue(cors.is_origin_allowed("http://localhost:3000"))
        self.assertFalse(cors.is_origin_allowed("http://evil.com"))

    def test_wildcard_origin(self):
        cors = CORSPolicy(allowed_origins=["*"])
        self.assertTrue(cors.is_origin_allowed("http://anything.com"))

    def test_headers_generated(self):
        cors = CORSPolicy(allowed_origins=["http://localhost:3000"])
        headers = cors.get_headers("http://localhost:3000")
        self.assertIn("Access-Control-Allow-Origin", headers)

    def test_blocked_origin_no_headers(self):
        cors = CORSPolicy(allowed_origins=["http://localhost:3000"])
        headers = cors.get_headers("http://evil.com")
        self.assertNotIn("Access-Control-Allow-Origin", headers)

    def test_status(self):
        cors = CORSPolicy(allowed_origins=["http://localhost:3000"])
        s = cors.status()
        self.assertEqual(s["allowed_origins_count"], 1)


# ── Rate Limiter Tests ───────────────────────────────────────────────

class TestRateLimiter(unittest.TestCase):
    def test_allows_within_limit(self):
        rl = RateLimiter(requests_per_minute=60, burst_size=10)
        result = rl.check("client_1")
        self.assertTrue(result["allowed"])

    def test_blocks_after_burst(self):
        rl = RateLimiter(requests_per_minute=60, burst_size=3)
        for _ in range(3):
            rl.check("client_1")
        result = rl.check("client_1")
        self.assertFalse(result["allowed"])

    def test_different_clients_independent(self):
        rl = RateLimiter(requests_per_minute=60, burst_size=1)
        rl.check("client_1")
        result = rl.check("client_2")
        self.assertTrue(result["allowed"])

    def test_status(self):
        rl = RateLimiter()
        rl.check("c1")
        s = rl.status()
        self.assertEqual(s["active_clients"], 1)


# ── CSP Tests ────────────────────────────────────────────────────────

class TestContentSecurityPolicy(unittest.TestCase):
    def test_default_policy_header(self):
        csp = ContentSecurityPolicy()
        header = csp.to_header()
        self.assertIn("default-src", header)
        self.assertIn("'self'", header)

    def test_add_source(self):
        csp = ContentSecurityPolicy()
        csp.add_source("script-src", "https://cdn.example.com")
        header = csp.to_header()
        self.assertIn("https://cdn.example.com", header)

    def test_security_headers_complete(self):
        csp = ContentSecurityPolicy()
        headers = csp.get_headers()
        self.assertIn("X-Content-Type-Options", headers)
        self.assertIn("X-Frame-Options", headers)
        self.assertIn("X-XSS-Protection", headers)
        self.assertIn("Strict-Transport-Security", headers)
        self.assertIn("Referrer-Policy", headers)
        self.assertIn("Permissions-Policy", headers)

    def test_x_frame_deny(self):
        csp = ContentSecurityPolicy()
        headers = csp.get_headers()
        self.assertEqual(headers["X-Frame-Options"], "DENY")


# ── API Key Rotation Tests ───────────────────────────────────────────

class TestAPIKeyRotation(unittest.TestCase):
    def test_new_key_valid(self):
        policy = APIKeyRotationPolicy(rotation_days=90)
        policy.register_key("key_1")
        result = policy.check_rotation("key_1")
        self.assertEqual(result["status"], "valid")

    def test_expired_key(self):
        policy = APIKeyRotationPolicy(rotation_days=90)
        old_date = datetime.now(timezone.utc) - timedelta(days=100)
        policy.register_key("key_1", created_at=old_date)
        result = policy.check_rotation("key_1")
        self.assertEqual(result["status"], "expired")

    def test_warning_key(self):
        policy = APIKeyRotationPolicy(rotation_days=90, warning_days=14)
        near_date = datetime.now(timezone.utc) - timedelta(days=80)
        policy.register_key("key_1", created_at=near_date)
        result = policy.check_rotation("key_1")
        self.assertEqual(result["status"], "warning")

    def test_generate_key_format(self):
        policy = APIKeyRotationPolicy()
        key = policy.generate_key()
        self.assertTrue(key.startswith("murphy_"))
        self.assertGreater(len(key), 20)

    def test_unknown_key(self):
        policy = APIKeyRotationPolicy()
        result = policy.check_rotation("nonexistent")
        self.assertEqual(result["status"], "unknown")


# ── Audit Logger Tests ───────────────────────────────────────────────

class TestAuditLogger(unittest.TestCase):
    def test_log_and_query(self):
        logger = AuditLogger()
        logger.log("auth", "user1", "api", "login", "success")
        results = logger.query(event_type="auth")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["actor"], "user1")

    def test_max_entries_enforced(self):
        logger = AuditLogger(max_entries=5)
        for i in range(10):
            logger.log("event", f"user_{i}", "res", "act")
        self.assertLessEqual(len(logger._log), 5)

    def test_query_filters(self):
        logger = AuditLogger()
        logger.log("auth", "user1", "api", "login", "success")
        logger.log("auth", "user2", "api", "login", "denied")
        results = logger.query(outcome="denied")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["actor"], "user2")

    def test_status(self):
        logger = AuditLogger()
        logger.log("test", "u", "r", "a")
        s = logger.status()
        self.assertEqual(s["total_entries"], 1)


# ── Session Security Tests ───────────────────────────────────────────

class TestSessionSecurity(unittest.TestCase):
    def test_create_session(self):
        ss = SessionSecurity()
        result = ss.create_session("user1")
        self.assertTrue(result["created"])
        self.assertIn("session_id", result)

    def test_validate_session(self):
        ss = SessionSecurity()
        created = ss.create_session("user1")
        result = ss.validate_session(created["session_id"])
        self.assertTrue(result["valid"])

    def test_invalid_session(self):
        ss = SessionSecurity()
        result = ss.validate_session("fake_session")
        self.assertFalse(result["valid"])

    def test_concurrent_session_limit(self):
        ss = SessionSecurity(max_concurrent_sessions=2)
        ss.create_session("user1")
        ss.create_session("user1")
        result = ss.create_session("user1")
        self.assertFalse(result["created"])

    def test_mfa_required(self):
        ss = SessionSecurity(require_mfa=True)
        created = ss.create_session("user1")
        result = ss.validate_session(created["session_id"])
        self.assertFalse(result["valid"])
        self.assertEqual(result["reason"], "mfa_required")


# ── Full Pipeline Tests ─────────────────────────────────────────────

class TestSecurityHardeningConfig(unittest.TestCase):
    def test_initialization(self):
        config = SecurityHardeningConfig()
        self.assertTrue(config._initialized)

    def test_clean_request_allowed(self):
        config = SecurityHardeningConfig()
        config.cors = CORSPolicy(allowed_origins=["*"])
        result = config.apply_request_security(
            "client_1", "http://localhost", {"query": "Hello world"}
        )
        self.assertTrue(result["allowed"])

    def test_injection_blocked(self):
        config = SecurityHardeningConfig()
        result = config.apply_request_security(
            "client_1", "", {"query": "<script>alert(1)</script>"}
        )
        self.assertFalse(result["allowed"])
        self.assertEqual(result["reason"], "injection_detected")

    def test_rate_limit_enforced(self):
        config = SecurityHardeningConfig()
        config.rate_limiter = RateLimiter(requests_per_minute=60, burst_size=2)
        config.apply_request_security("c1", "", {"a": "b"})
        config.apply_request_security("c1", "", {"a": "b"})
        result = config.apply_request_security("c1", "", {"a": "b"})
        self.assertFalse(result["allowed"])

    def test_response_headers(self):
        config = SecurityHardeningConfig()
        headers = config.get_response_headers()
        self.assertIn("Content-Security-Policy", headers)
        self.assertIn("X-Frame-Options", headers)

    def test_full_status(self):
        config = SecurityHardeningConfig()
        s = config.status()
        self.assertEqual(s["module"], "security_hardening_config")
        self.assertTrue(s["initialized"])
        self.assertIn("components", s)
        self.assertIn("input_sanitizer", s["components"])

    def test_audit_trail_on_blocked(self):
        config = SecurityHardeningConfig()
        config.apply_request_security(
            "attacker", "", {"payload": "<script>steal()</script>"}
        )
        entries = config.audit.query(event_type="injection_attempt")
        self.assertGreater(len(entries), 0)


if __name__ == "__main__":
    unittest.main()
