"""
Security-Focused Tests — PR 6 Gap Closure

Validates real security behaviour (no mocks) for:

  1. CSRF token validation — valid, expired, missing
  2. Rate limit enforcement — normal, burst, blocked
  3. RBAC authorization — permitted, denied, edge cases
  4. Input validation — XSS, SQL injection, oversized payloads
  5. Auth bypass attempts

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import time
import uuid

import pytest

from csrf_protection import CSRFTokenStore, generate_token, validate_token, revoke_token
from fastapi_security import _FastAPIRateLimiter
from rbac_governance import (
    Role, Permission, TenantPolicy, UserIdentity, RBACGovernance,
)
from input_validation import ChatMessageInput, validate_input


# ===========================================================================
# 1. CSRF token validation
# ===========================================================================

class TestCSRFTokenValidation:
    """Validate CSRF token generate / validate / expiry lifecycle."""

    def test_valid_token_accepted(self):
        store = CSRFTokenStore()
        token = store.generate("sess-valid")
        ok, reason = store.validate("sess-valid", token)
        assert ok is True
        assert reason == "ok"

    def test_missing_session_rejected(self):
        store = CSRFTokenStore()
        ok, reason = store.validate("nonexistent-session", "any-token")
        assert ok is False
        assert reason == "missing"

    def test_missing_token_string_rejected(self):
        store = CSRFTokenStore()
        store.generate("sess-x")
        ok, reason = store.validate("sess-x", "")
        assert ok is False
        assert reason == "missing"

    def test_expired_token_rejected(self):
        store = CSRFTokenStore(ttl_seconds=0)  # TTL = 0 → always expired
        token = store.generate("sess-exp")
        time.sleep(0.01)
        ok, reason = store.validate("sess-exp", token)
        assert ok is False
        assert reason == "expired"

    def test_wrong_token_mismatch(self):
        store = CSRFTokenStore()
        store.generate("sess-mismatch")
        ok, reason = store.validate("sess-mismatch", "wrong-token-value")
        assert ok is False
        assert reason == "mismatch"

    def test_token_revoked_then_missing(self):
        store = CSRFTokenStore()
        store.generate("sess-rev")
        store.revoke("sess-rev")
        ok, reason = store.validate("sess-rev", "anything")
        assert ok is False
        assert reason == "missing"

    def test_module_level_generate_validate(self):
        sid = f"sess-{uuid.uuid4().hex[:8]}"
        token = generate_token(sid)
        ok, reason = validate_token(sid, token)
        assert ok is True

    def test_purge_expired_removes_entries(self):
        store = CSRFTokenStore(ttl_seconds=0)
        for i in range(5):
            store.generate(f"session-{i}")
        time.sleep(0.01)
        removed = store.purge_expired()
        assert removed == 5
        assert len(store) == 0

    def test_independent_sessions_do_not_cross_validate(self):
        store = CSRFTokenStore()
        t1 = store.generate("s1")
        store.generate("s2")
        # Token from s1 must not validate against s2
        ok, _ = store.validate("s2", t1)
        assert ok is False

    def test_empty_session_id_raises(self):
        store = CSRFTokenStore()
        with pytest.raises(ValueError):
            store.generate("")


# ===========================================================================
# 2. Rate limit enforcement
# ===========================================================================

class TestRateLimitEnforcement:
    """Token-bucket rate limiter: normal flow, burst, blocked."""

    def _limiter(self, rpm: int = 60, burst: int = 3) -> _FastAPIRateLimiter:
        return _FastAPIRateLimiter(
            requests_per_minute=rpm,
            burst_size=burst,
            swarm_burst_size=0,
        )

    def test_first_request_allowed(self):
        lim = self._limiter(burst=5)
        result = lim.check("client-a")
        assert result["allowed"] is True

    def test_requests_within_burst_allowed(self):
        lim = self._limiter(burst=5)
        cid = "client-burst"
        for _ in range(5):
            r = lim.check(cid)
            assert r["allowed"] is True

    def test_exceeding_burst_blocked(self):
        lim = self._limiter(rpm=1, burst=2)
        cid = "client-blocked"
        # Exhaust burst
        lim.check(cid)
        lim.check(cid)
        # Next request should be blocked
        r = lim.check(cid)
        assert r["allowed"] is False
        assert r["remaining"] == 0

    def test_blocked_result_has_retry_after(self):
        lim = self._limiter(rpm=1, burst=1)
        cid = "client-retry"
        lim.check(cid)  # consume burst
        r = lim.check(cid)
        if not r["allowed"]:
            assert "retry_after_seconds" in r
            assert r["retry_after_seconds"] > 0

    def test_different_clients_independent(self):
        lim = self._limiter(burst=1)
        r1 = lim.check("client-x")
        r2 = lim.check("client-y")
        assert r1["allowed"] is True
        assert r2["allowed"] is True

    def test_remaining_decrements(self):
        lim = self._limiter(burst=5)
        cid = "client-decrement"
        r1 = lim.check(cid)
        r2 = lim.check(cid)
        assert r2["remaining"] <= r1["remaining"]

    def test_high_volume_same_client_eventually_blocked(self):
        lim = self._limiter(rpm=1, burst=3)
        cid = "client-hv"
        results = [lim.check(cid) for _ in range(20)]
        blocked = [r for r in results if not r["allowed"]]
        assert len(blocked) > 0, "Expected some requests to be blocked"


# ===========================================================================
# 3. RBAC authorization
# ===========================================================================

class TestRBACAuthorization:
    """RBAC: permitted, denied, edge cases."""

    @pytest.fixture
    def gov(self):
        g = RBACGovernance()
        policy = TenantPolicy(
            tenant_id="t1", name="TestOrg",
            max_concurrent_tasks=10, budget_limit=10000.0,
            allowed_domains=["test.com"],
            compliance_frameworks=[],
        )
        g.create_tenant(policy)
        g.register_user(UserIdentity(
            user_id="owner1", tenant_id="t1",
            roles=[Role.OWNER], display_name="Owner",
        ))
        g.register_user(UserIdentity(
            user_id="viewer1", tenant_id="t1",
            roles=[Role.VIEWER], display_name="Viewer",
        ))
        g.register_user(UserIdentity(
            user_id="op1", tenant_id="t1",
            roles=[Role.OPERATOR], display_name="Operator",
        ))
        return g

    def test_owner_can_execute_task(self, gov):
        allowed, reason = gov.check_permission("owner1", Permission.EXECUTE_TASK)
        assert allowed is True

    def test_viewer_cannot_execute_task(self, gov):
        allowed, _ = gov.check_permission("viewer1", Permission.EXECUTE_TASK)
        assert allowed is False

    def test_owner_can_configure_system(self, gov):
        allowed, _ = gov.check_permission("owner1", Permission.CONFIGURE_SYSTEM)
        assert allowed is True

    def test_viewer_cannot_configure_system(self, gov):
        allowed, _ = gov.check_permission("viewer1", Permission.CONFIGURE_SYSTEM)
        assert allowed is False

    def test_unknown_user_denied(self, gov):
        allowed, reason = gov.check_permission("ghost-user", Permission.VIEW_STATUS)
        assert allowed is False
        assert "unknown" in reason

    def test_operator_can_view_status(self, gov):
        allowed, _ = gov.check_permission("op1", Permission.VIEW_STATUS)
        assert allowed is True

    def test_assign_role_elevates_permissions(self, gov):
        gov.register_user(UserIdentity(
            user_id="promoted1", tenant_id="t1",
            roles=[Role.VIEWER], display_name="Soon Admin",
        ))
        gov.assign_role("promoted1", Role.ADMIN, assigner_id="owner1")
        allowed, _ = gov.check_permission("promoted1", Permission.CONFIGURE_SYSTEM)
        assert allowed is True

    def test_remove_role_reduces_permissions(self, gov):
        gov.register_user(UserIdentity(
            user_id="demoted1", tenant_id="t1",
            roles=[Role.OPERATOR], display_name="Soon Viewer",
        ))
        gov.remove_role("demoted1", Role.OPERATOR, remover_id="owner1")
        allowed, _ = gov.check_permission("demoted1", Permission.EXECUTE_TASK)
        assert allowed is False

    def test_tenant_isolation_same_tenant(self, gov):
        result = gov.enforce_tenant_isolation("owner1", "t1")
        assert result is True

    def test_tenant_isolation_different_tenant(self, gov):
        result = gov.enforce_tenant_isolation("owner1", "other-tenant")
        assert result is False


# ===========================================================================
# 4. Input validation — XSS, SQL injection, oversized payloads
# ===========================================================================

class TestInputValidation:
    """Input validation blocks injections and oversized inputs."""

    def test_valid_message_accepted(self):
        ok, data, err = validate_input(
            {"message": "Hello, show me the dashboard"},
            ChatMessageInput,
        )
        assert ok is True
        assert err is None

    def test_xss_script_tag_blocked(self):
        ok, _, err = validate_input(
            {"message": "<script>alert('xss')</script>"},
            ChatMessageInput,
        )
        assert ok is False

    def test_xss_img_onerror_blocked(self):
        ok, _, err = validate_input(
            {"message": "<img src=x onerror=alert(1)>"},
            ChatMessageInput,
        )
        assert ok is False

    def test_sql_injection_drop_blocked(self):
        ok, _, err = validate_input(
            {"message": "'; DROP TABLE users; --"},
            ChatMessageInput,
        )
        assert ok is False

    def test_javascript_uri_blocked(self):
        ok, _, err = validate_input(
            {"message": "javascript:alert(1)"},
            ChatMessageInput,
        )
        assert ok is False

    def test_path_traversal_blocked(self):
        ok, _, err = validate_input(
            {"message": "../../etc/passwd"},
            ChatMessageInput,
        )
        assert ok is False

    def test_oversized_message_blocked(self):
        ok, _, err = validate_input(
            {"message": "A" * 100_000},
            ChatMessageInput,
        )
        assert ok is False

    def test_empty_message_blocked(self):
        ok, _, err = validate_input({"message": ""}, ChatMessageInput)
        assert ok is False

    def test_normal_long_message_accepted(self):
        """A message under the size limit with no injection is accepted."""
        ok, data, err = validate_input(
            {"message": "Please summarize my project status " * 5},
            ChatMessageInput,
        )
        assert ok is True


# ===========================================================================
# 5. Auth bypass attempts
# ===========================================================================

class TestAuthBypassAttempts:
    """Ensure common auth bypass patterns are rejected."""

    def test_sql_injection_in_session_id_blocked(self):
        """A SQL-injection-style session_id must not produce a valid CSRF token."""
        store = CSRFTokenStore()
        malicious_sid = "' OR '1'='1"
        # generate() should accept any non-empty string, but validate with a
        # crafted token should fail
        token = store.generate(malicious_sid)
        ok, reason = store.validate(malicious_sid, "injected-token")
        assert ok is False

    def test_empty_session_yields_missing(self):
        store = CSRFTokenStore()
        ok, reason = store.validate("", "some-token")
        assert ok is False
        assert reason == "missing"

    def test_forged_token_rejected(self):
        """A token generated for session A cannot be used for session B."""
        store = CSRFTokenStore()
        token_a = store.generate("session-a")
        ok, _ = store.validate("session-b", token_a)
        assert ok is False

    def test_rbac_unknown_user_denied_all_permissions(self):
        """An unknown user is denied every permission without exception."""
        gov = RBACGovernance()
        policy = TenantPolicy(
            tenant_id="isolated", name="Isolated",
            max_concurrent_tasks=1, budget_limit=100.0,
            allowed_domains=[], compliance_frameworks=[],
        )
        gov.create_tenant(policy)
        for perm in Permission:
            allowed, _ = gov.check_permission("attacker", perm)
            assert allowed is False, f"Unexpected grant for permission {perm}"

    def test_rate_limiter_blocks_brute_force(self):
        """A client sending many rapid requests is eventually blocked."""
        lim = _FastAPIRateLimiter(requests_per_minute=6, burst_size=3,
                                  swarm_burst_size=0)
        cid = "brute-force-attacker"
        results = [lim.check(cid) for _ in range(50)]
        blocked = sum(1 for r in results if not r["allowed"])
        assert blocked > 0, "Brute-force attacker should be rate-limited"
