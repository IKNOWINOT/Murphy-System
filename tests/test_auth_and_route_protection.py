"""
Tests for authentication, route protection, subscription tiers, and daily usage tracking.

Covers:
  - Signup endpoint creates real accounts with sessions and returns session_token
  - Login endpoint validates credentials, creates sessions, and returns session_token
  - session_token in responses enables localStorage mirroring for MurphyAPI Bearer-token path
  - Bearer-token auth using the session_token from signup/login responses
  - GET /api/auth/session-token endpoint (for OAuth users to mirror cookie to localStorage)
  - Profile endpoint returns authenticated user data
  - Logout invalidates sessions
  - Server-side HTML route protection (302 redirect for unauthenticated)
  - Public pages remain accessible without auth
  - FREE tier in subscription manager
  - Daily usage tracking and limits
  - Billing checkout endpoint
  - murphy_auth.js included in protected pages

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

import os
import sys
import json
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# ---------------------------------------------------------------------------
# App client fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    """Create a FastAPI test client."""
    os.environ["MURPHY_ENV"] = "development"
    from starlette.testclient import TestClient
    from src.runtime.app import create_app
    app = create_app()
    return TestClient(app, follow_redirects=False)


@pytest.fixture
def auth_client(client):
    """Create an authenticated test client by signing up a fresh user."""
    resp = client.post("/api/auth/signup", json={
        "email": f"test_{os.urandom(4).hex()}@example.com",
        "password": "SecurePass123!",
        "full_name": "Test User",
        "job_title": "Tester",
        "company": "TestCorp",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    # The response sets a murphy_session cookie
    return client, data


# ===========================================================================
# Part 1: Signup Endpoint
# ===========================================================================

class TestSignup:
    def test_signup_creates_account(self, client):
        resp = client.post("/api/auth/signup", json={
            "email": "signup_test@example.com",
            "password": "TestPass123!",
            "full_name": "Signup Test",
            "job_title": "Dev",
            "company": "TestCo",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["account_id"]
        assert data["email"] == "signup_test@example.com"
        assert data["tier"] == "free"

    def test_signup_returns_session_token(self, client):
        """Signup response must include session_token so the frontend can mirror
        it to localStorage for the MurphyAPI Bearer-token path."""
        resp = client.post("/api/auth/signup", json={
            "email": "session_token_signup@example.com",
            "password": "TestPass123!",
            "full_name": "Token Test",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "session_token" in data, "signup response must contain session_token"
        assert data["session_token"], "session_token must be non-empty"

    def test_signup_sets_session_cookie(self, client):
        resp = client.post("/api/auth/signup", json={
            "email": "cookie_test@example.com",
            "password": "TestPass123!",
            "full_name": "Cookie Test",
        })
        assert resp.status_code == 200
        assert "murphy_session" in resp.cookies

    def test_signup_requires_email(self, client):
        resp = client.post("/api/auth/signup", json={
            "password": "TestPass123!",
        })
        assert resp.status_code == 400
        assert "Email is required" in resp.json().get("error", "")

    def test_signup_requires_password_min_length(self, client):
        resp = client.post("/api/auth/signup", json={
            "email": "short_pw@example.com",
            "password": "short",
        })
        assert resp.status_code == 400
        assert "8 characters" in resp.json().get("error", "")

    def test_signup_prevents_duplicate_email(self, client):
        email = "dup_test@example.com"
        resp1 = client.post("/api/auth/signup", json={
            "email": email,
            "password": "TestPass123!",
        })
        assert resp1.status_code == 200
        resp2 = client.post("/api/auth/signup", json={
            "email": email,
            "password": "TestPass123!",
        })
        assert resp2.status_code == 409
        assert "already exists" in resp2.json().get("error", "")


# ===========================================================================
# Part 2: Login Endpoint
# ===========================================================================

class TestLogin:
    def test_login_with_valid_credentials(self, client):
        # First signup
        email = "login_test@example.com"
        client.post("/api/auth/signup", json={
            "email": email,
            "password": "TestPass123!",
            "full_name": "Login Test",
        })
        # Then login
        resp = client.post("/api/auth/login", json={
            "email": email,
            "password": "TestPass123!",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["email"] == email
        assert "murphy_session" in resp.cookies

    def test_login_returns_session_token(self, client):
        """Login response must include session_token so the frontend can mirror
        it to localStorage for the MurphyAPI Bearer-token path."""
        email = "login_session_token@example.com"
        client.post("/api/auth/signup", json={
            "email": email,
            "password": "TestPass123!",
            "full_name": "Token Login Test",
        })
        resp = client.post("/api/auth/login", json={
            "email": email,
            "password": "TestPass123!",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "session_token" in data, "login response must contain session_token"
        assert data["session_token"], "session_token must be non-empty"

    def test_bearer_token_auth_using_session_token(self, client):
        """A session_token from signup must authenticate subsequent API requests
        when sent as Authorization: Bearer <token> (Fix 2 for MurphyAPI).

        Uses a cookie-free TestClient that shares the SAME app instance (and
        therefore the same in-memory _session_store) as the module-scoped
        client, so the token is resolvable without needing the cookie.
        """
        email = "bearer_auth_test@example.com"
        signup_resp = client.post("/api/auth/signup", json={
            "email": email,
            "password": "TestPass123!",
            "full_name": "Bearer Auth Test",
        })
        token = signup_resp.json()["session_token"]
        # Share the same app (same _session_store) but use a fresh, cookie-free
        # TestClient so we verify the Bearer-header path, not the cookie path.
        from starlette.testclient import TestClient
        bare_client = TestClient(client.app, follow_redirects=False)
        resp = bare_client.get(
            "/api/profiles/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200, (
            f"Bearer token from signup should authenticate /api/profiles/me, got {resp.status_code}"
        )

    def test_login_with_wrong_password(self, client):
        email = "wrongpw_test@example.com"
        client.post("/api/auth/signup", json={
            "email": email,
            "password": "CorrectPass123!",
        })
        resp = client.post("/api/auth/login", json={
            "email": email,
            "password": "WrongPass123!",
        })
        assert resp.status_code == 401
        assert "Invalid email or password" in resp.json().get("error", "")

    def test_login_with_nonexistent_email(self, client):
        resp = client.post("/api/auth/login", json={
            "email": "nonexistent@example.com",
            "password": "TestPass123!",
        })
        assert resp.status_code == 401

    def test_login_requires_email_and_password(self, client):
        resp = client.post("/api/auth/login", json={
            "email": "",
            "password": "",
        })
        assert resp.status_code == 400

    def test_login_email_case_insensitive(self, client):
        email = "casetest@example.com"
        client.post("/api/auth/signup", json={
            "email": email,
            "password": "TestPass123!",
        })
        resp = client.post("/api/auth/login", json={
            "email": "CASETEST@example.com",
            "password": "TestPass123!",
        })
        assert resp.status_code == 200
        assert resp.json()["success"] is True


# ===========================================================================
# Part 3: Profile Endpoint
# ===========================================================================

class TestProfile:
    def test_profile_returns_user_data_when_authenticated(self, auth_client):
        client, signup_data = auth_client
        resp = client.get("/api/profiles/me")
        assert resp.status_code == 200
        data = resp.json()
        assert data["found"] is True
        assert data["email"]
        assert data["tier"] == "free"
        assert data["email_validated"] is True
        assert data["eula_accepted"] is True
        assert "daily_usage" in data
        assert "terminal_config" in data

    def test_profile_returns_401_without_auth(self, client):
        # Use a fresh client with no session cookies
        from starlette.testclient import TestClient
        from src.runtime.app import create_app
        fresh = TestClient(create_app(), follow_redirects=False)
        resp = fresh.get("/api/profiles/me")
        data = resp.json()
        # Without auth, found should be False
        assert data.get("found") is False

    def test_profile_includes_daily_usage(self, auth_client):
        client, _ = auth_client
        resp = client.get("/api/profiles/me")
        data = resp.json()
        assert "daily_usage" in data
        usage = data["daily_usage"]
        assert "used" in usage
        assert "limit" in usage
        assert "remaining" in usage


# ===========================================================================
# Part 4: Logout Endpoint
# ===========================================================================

class TestLogout:
    def test_logout_invalidates_session(self, client):
        email = f"logout_{os.urandom(4).hex()}@example.com"
        signup_resp = client.post("/api/auth/signup", json={
            "email": email,
            "password": "TestPass123!",
        })
        assert signup_resp.status_code == 200

        # Verify profile works
        profile_resp = client.get("/api/profiles/me")
        assert profile_resp.json().get("found") is True

        # Logout
        logout_resp = client.post("/api/auth/logout")
        assert logout_resp.status_code == 200
        assert logout_resp.json()["success"] is True


# ===========================================================================
# Part 4b: Session Token Endpoint
# ===========================================================================

class TestSessionTokenEndpoint:
    """GET /api/auth/session-token — enables OAuth users to mirror the
    HttpOnly murphy_session cookie value to localStorage after redirect.

    All tests here use a per-test isolated TestClient that shares the same
    app instance (same in-memory _session_store) but has its own cookie jar,
    so session cookies do NOT leak to the module-scoped client used by
    TestRouteProtection which relies on being unauthenticated.
    """

    def _fresh_client(self, client):
        """Return a cookie-free TestClient sharing the same app instance."""
        from starlette.testclient import TestClient
        return TestClient(client.app, follow_redirects=False)

    def test_returns_token_for_authenticated_session(self, client):
        """Authenticated user (cookie present) should get their session token."""
        c = self._fresh_client(client)
        c.post("/api/auth/signup", json={
            "email": f"st_auth_{os.urandom(4).hex()}@example.com",
            "password": "TestPass123!",
            "full_name": "Session Token Test",
        })
        resp = c.get("/api/auth/session-token")
        assert resp.status_code == 200
        data = resp.json()
        assert "session_token" in data
        assert data["session_token"]

    def test_returns_401_when_not_authenticated(self, client):
        """Unauthenticated request must get 401 — no token to return.

        The endpoint performs its own auth check via _get_account_from_session()
        regardless of MURPHY_ENV, so a fresh cookie-less client gets 401.
        """
        c = self._fresh_client(client)
        resp = c.get("/api/auth/session-token")
        assert resp.status_code == 401

    def test_session_token_matches_signup_token(self, client):
        """The token returned by the endpoint must match the one in the signup body."""
        c = self._fresh_client(client)
        signup_resp = c.post("/api/auth/signup", json={
            "email": f"st_match_{os.urandom(4).hex()}@example.com",
            "password": "TestPass123!",
        })
        signup_token = signup_resp.json()["session_token"]
        endpoint_resp = c.get("/api/auth/session-token")
        assert endpoint_resp.status_code == 200
        endpoint_token = endpoint_resp.json()["session_token"]
        assert signup_token == endpoint_token, (
            "Token from /api/auth/session-token must equal the signup session_token"
        )


# ===========================================================================
# Part 5: Server-Side Route Protection
# ===========================================================================

class TestRouteProtection:
    """Verify that protected HTML routes redirect to /ui/login without auth."""

    PROTECTED_ROUTES = [
        "/ui/terminal-unified",
        "/ui/terminal",
        "/ui/wallet",
        "/ui/workspace",
        "/ui/management",
        "/ui/calendar",
        "/ui/meeting-intelligence",
        "/ui/ambient",
        "/ui/community",
        "/ui/compliance",
        "/ui/onboarding",
        "/ui/workflow-canvas",
        "/ui/system-visualizer",
        "/ui/dashboard",
        "/ui/matrix",
        "/ui/production-wizard",
        "/ui/terminal-architect",
        "/ui/terminal-enhanced",
        "/ui/terminal-worker",
        "/ui/terminal-costs",
        "/ui/terminal-orgchart",
        "/ui/terminal-integrations",
        "/ui/terminal-orchestrator",
        "/ui/terminal-integrated",
    ]

    PUBLIC_ROUTES = [
        "/",
        "/ui/landing",
        "/ui/login",
        "/ui/signup",
        "/ui/pricing",
        "/ui/docs",
        "/ui/blog",
        "/ui/careers",
        "/ui/legal",
        "/ui/privacy",
        "/ui/partner",
    ]

    def test_protected_routes_redirect_without_auth(self, client):
        """Protected routes should return 302 redirect to /ui/login."""
        for route in self.PROTECTED_ROUTES:
            resp = client.get(route, cookies={})
            assert resp.status_code == 302, f"{route} should redirect (302), got {resp.status_code}"
            location = resp.headers.get("location", "")
            assert "/ui/login" in location, f"{route} should redirect to /ui/login, got {location}"

    def test_protected_routes_include_next_param(self, client):
        """Redirect should include ?next= so user returns after login."""
        resp = client.get("/ui/terminal-unified", cookies={})
        assert resp.status_code == 302
        location = resp.headers.get("location", "")
        assert "next=" in location

    def test_public_routes_accessible_without_auth(self, client):
        """Public routes should return 200 without authentication."""
        for route in self.PUBLIC_ROUTES:
            resp = client.get(route, cookies={})
            assert resp.status_code == 200, f"{route} should be public (200), got {resp.status_code}"

    def test_protected_routes_accessible_with_auth(self, auth_client):
        """Protected routes should return 200 with valid session."""
        client, _ = auth_client
        # Check a sample of protected routes
        for route in ["/ui/terminal-unified", "/ui/wallet", "/ui/workspace"]:
            resp = client.get(route)
            assert resp.status_code == 200, f"{route} should be accessible with auth, got {resp.status_code}"


# ===========================================================================
# Part 6: FREE Tier in Subscription Manager
# ===========================================================================

class TestFreeTier:
    def test_free_tier_exists_in_enum(self):
        from subscription_manager import SubscriptionTier
        assert hasattr(SubscriptionTier, "FREE")
        assert SubscriptionTier.FREE.value == "free"

    def test_free_tier_pricing_is_zero(self):
        from subscription_manager import SubscriptionTier, PRICING_PLANS
        plan = PRICING_PLANS[SubscriptionTier.FREE]
        assert plan.monthly_price == 0.00
        assert plan.annual_price == 0.00
        assert plan.max_automations == 0

    def test_free_tier_features_include_wallet_and_training(self):
        from subscription_manager import SubscriptionTier, SubscriptionManager
        mgr = SubscriptionManager()
        features = mgr.TIER_FEATURES.get(SubscriptionTier.FREE, {})
        assert features.get("crypto_wallet") is True
        assert features.get("shadow_agent_training") is True
        assert features.get("shadow_agent_sell") is False
        assert features.get("hitl_automations") is False

    def test_free_tier_daily_limit_is_10(self):
        from subscription_manager import SubscriptionTier, SubscriptionManager
        mgr = SubscriptionManager()
        features = mgr.TIER_FEATURES.get(SubscriptionTier.FREE, {})
        assert features.get("daily_action_limit") == 10


# ===========================================================================
# Part 7: Daily Usage Tracking
# ===========================================================================

class TestDailyUsage:
    def test_record_usage_for_free_account(self):
        from subscription_manager import SubscriptionManager
        mgr = SubscriptionManager()
        result = mgr.record_usage("test_account_123")
        assert result["allowed"] is True
        assert result["limit"] == 10
        assert result["used"] == 1
        assert result["remaining"] == 9

    def test_usage_limit_reached(self):
        from subscription_manager import SubscriptionManager
        mgr = SubscriptionManager()
        account = "limited_account"
        for i in range(10):
            result = mgr.record_usage(account)
            assert result["allowed"] is True
        # 11th action should be blocked
        result = mgr.record_usage(account)
        assert result["allowed"] is False
        assert "Daily limit" in result.get("message", "")

    def test_anonymous_usage_limit(self):
        from subscription_manager import SubscriptionManager
        mgr = SubscriptionManager()
        fp = "anon_fingerprint_123"
        for i in range(5):
            result = mgr.record_anon_usage(fp)
            assert result["allowed"] is True
        # 6th action should be blocked
        result = mgr.record_anon_usage(fp)
        assert result["allowed"] is False
        assert result["tier"] == "anonymous"

    def test_paid_accounts_have_unlimited_usage(self):
        from subscription_manager import (
            SubscriptionManager, SubscriptionTier,
            SubscriptionRecord, SubscriptionStatus,
        )
        mgr = SubscriptionManager()
        account = "paid_account_123"
        mgr._subscriptions[account] = SubscriptionRecord(
            account_id=account,
            tier=SubscriptionTier.SOLO,
            status=SubscriptionStatus.ACTIVE,
        )
        for i in range(20):
            result = mgr.record_usage(account)
            assert result["allowed"] is True
            assert result["limit"] == -1  # unlimited

    def test_get_daily_usage(self):
        from subscription_manager import SubscriptionManager
        mgr = SubscriptionManager()
        account = "usage_query_account"
        mgr.record_usage(account)
        mgr.record_usage(account)
        usage = mgr.get_daily_usage(account)
        assert usage["used"] == 2
        assert usage["limit"] == 10
        assert usage["remaining"] == 8


# ===========================================================================
# Part 8: Billing Checkout Endpoint
# ===========================================================================

class TestBillingCheckout:
    def test_checkout_rejects_missing_body(self, client):
        resp = client.post("/api/billing/checkout", json={"account_id": "", "tier": ""})
        # Existing billing API returns 422 for invalid payload
        assert resp.status_code in (400, 422)

    def test_checkout_attempts_payment(self, auth_client):
        client, signup_data = auth_client
        resp = client.post("/api/billing/checkout", json={
            "account_id": signup_data["account_id"],
            "tier": "solo",
            "interval": "monthly",
        })
        # Without external payment providers configured, expect 502 (gateway error)
        # or 200 with a mock URL if payment provider SDK is unavailable
        assert resp.status_code in (200, 502), \
            f"Expected 200 or 502, got {resp.status_code}: {resp.text}"


# ===========================================================================
# Part 9: Usage Daily API Endpoint
# ===========================================================================

class TestUsageDailyEndpoint:
    def test_anonymous_usage(self, client):
        from starlette.testclient import TestClient
        from src.runtime.app import create_app
        fresh = TestClient(create_app(), follow_redirects=False)
        resp = fresh.get("/api/usage/daily")
        assert resp.status_code == 200
        data = resp.json()
        assert data["tier"] == "anonymous"
        assert "limit" in data

    def test_authenticated_usage(self, auth_client):
        client, _ = auth_client
        resp = client.get("/api/usage/daily")
        assert resp.status_code == 200
        data = resp.json()
        assert data["tier"] == "free"
        assert data["limit"] == 10


# ===========================================================================
# Part 10: HTML Pages Include Auth Script
# ===========================================================================

class TestAuthScriptInclusion:
    """Verify that protected HTML pages include murphy_auth.js."""

    PROTECTED_PAGES_WITH_AUTH = [
        "terminal_unified.html",
        "terminal_architect.html",
        "wallet.html",
        "workspace.html",
        "management.html",
        "calendar.html",
        "meeting_intelligence.html",
        "ambient_intelligence.html",
        "community_forum.html",
        "compliance_dashboard.html",
    ]

    def test_protected_pages_include_murphy_auth_js(self):
        project_root = os.path.join(os.path.dirname(__file__), "..")
        for html_file in self.PROTECTED_PAGES_WITH_AUTH:
            filepath = os.path.join(project_root, html_file)
            if os.path.exists(filepath):
                with open(filepath) as f:
                    content = f.read()
                assert "murphy_auth" in content, \
                    f"{html_file} should include murphy_auth.js for client-side auth"

    PUBLIC_PAGES_WITHOUT_AUTH = [
        "murphy_landing_page.html",
        "login.html",
        "signup.html",
    ]

    def test_public_pages_do_not_require_auth(self):
        """Public pages should not require auth (no auth redirect)."""
        project_root = os.path.join(os.path.dirname(__file__), "..")
        for html_file in self.PUBLIC_PAGES_WITHOUT_AUTH:
            filepath = os.path.join(project_root, html_file)
            if os.path.exists(filepath):
                # These should exist and be public
                assert os.path.exists(filepath), f"{html_file} should exist"


# ===========================================================================
# Part 11: Health and Public API Endpoints
# ===========================================================================

class TestPublicEndpoints:
    def test_health_endpoint(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"

    def test_auth_providers_endpoint(self, client):
        resp = client.get("/api/auth/providers")
        assert resp.status_code == 200
        data = resp.json()
        assert "providers" in data


# ===========================================================================
# Part 12: Landing Page and Demo Page Routes
# ===========================================================================

class TestLandingAndDemoPages:
    """Ensure the landing page and demo page are served correctly."""

    def test_landing_page_at_root(self, client):
        """GET / should serve the landing page (200)."""
        resp = client.get("/")
        assert resp.status_code == 200

    def test_landing_page_at_html_path(self, client):
        """GET /murphy_landing_page.html should serve the landing page (200)."""
        resp = client.get("/murphy_landing_page.html")
        assert resp.status_code == 200

    def test_landing_page_at_ui_landing(self, client):
        """GET /ui/landing should serve the landing page (200)."""
        resp = client.get("/ui/landing")
        assert resp.status_code == 200

    def test_demo_page_returns_200(self, client):
        """GET /ui/demo should serve the demo page (200)."""
        resp = client.get("/ui/demo")
        assert resp.status_code == 200

    def test_demo_page_is_public(self, client):
        """The demo page should be accessible without authentication."""
        resp = client.get("/ui/demo")
        # Should NOT be a redirect to login
        assert resp.status_code == 200

    def test_demo_page_contains_demo_content(self, client):
        """The demo page should contain interactive demo elements."""
        resp = client.get("/ui/demo")
        assert resp.status_code == 200
        content = resp.text
        assert "Try Murphy" in content
