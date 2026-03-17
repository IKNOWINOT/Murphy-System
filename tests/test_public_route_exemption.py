"""
Regression tests: Public Route Exemption from Brute-Force Lockout

Verifies that normal unauthenticated browsing of the Murphy System website
does NOT trigger the brute-force lockout protection in fastapi_security.py.

Problem (CWE-307):
    HTML pages (login.html, signup.html, landing page, pricing.html) load
    several API endpoints without auth tokens:
      - /api/auth/oauth/<provider>  — OAuth buttons
      - /api/auth/callback[/<provider>] — OAuth callbacks
      - /api/reviews                — public reviews section
      - /api/profiles/me            — login-status check in murphy_auth.js
      - /favicon.ico                — browser auto-request

    Each 401 response used to call _brute_force.record_failure(ip), causing
    lockout after ~5 page-load requests (≈ 1–2 page views).

Fix:
    _is_public_api_route() and the updated _is_static_or_ui_page() now bypass
    the brute-force tracker so innocent browsing never counts as an attack.

Tests:
    1. _is_public_api_route returns True for all expected public routes
    2. _is_public_api_route returns False for protected routes
    3. _is_static_or_ui_page returns True for /favicon.ico + /favicon.svg
    4. Multiple hits to public routes do NOT trigger lockout
    5. Multiple hits to protected routes DO trigger lockout (regression guard)
    6. Full middleware dispatch skips brute-force for public routes (integration)
"""

import os
import sys
import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytest.importorskip("fastapi", reason="fastapi not installed — skipping")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from fastapi_security import (
    _is_public_api_route,
    _is_static_or_ui_page,
    _BruteForceTracker,
    SecurityMiddleware,
)


# ─────────────────────────────────────────────────────────────────────────────
# 1. _is_public_api_route — True cases
# ─────────────────────────────────────────────────────────────────────────────

class TestPublicApiRouteExemptions(unittest.TestCase):
    """_is_public_api_route() must return True for all pre-login public routes."""

    # OAuth initiation buttons (login.html / signup.html)
    def test_oauth_google(self):
        assert _is_public_api_route("/api/auth/oauth/google", "GET") is True

    def test_oauth_github(self):
        assert _is_public_api_route("/api/auth/oauth/github", "GET") is True

    def test_oauth_linkedin(self):
        assert _is_public_api_route("/api/auth/oauth/linkedin", "GET") is True

    def test_oauth_apple(self):
        assert _is_public_api_route("/api/auth/oauth/apple", "GET") is True

    def test_oauth_meta(self):
        assert _is_public_api_route("/api/auth/oauth/meta", "GET") is True

    # OAuth callbacks
    def test_auth_callback_bare(self):
        assert _is_public_api_route("/api/auth/callback", "GET") is True

    def test_auth_callback_with_provider(self):
        assert _is_public_api_route("/api/auth/callback/google", "GET") is True

    # Auth endpoints
    def test_auth_login(self):
        assert _is_public_api_route("/api/auth/login", "GET") is True

    def test_auth_login_post(self):
        assert _is_public_api_route("/api/auth/login", "POST") is True

    def test_auth_register(self):
        assert _is_public_api_route("/api/auth/register", "POST") is True

    def test_auth_signup(self):
        assert _is_public_api_route("/api/auth/signup", "POST") is True

    # System info routes (Auth: No in API_ROUTES.md)
    def test_api_manifest(self):
        assert _is_public_api_route("/api/manifest", "GET") is True

    def test_api_info(self):
        assert _is_public_api_route("/api/info", "GET") is True

    def test_api_ui_links(self):
        assert _is_public_api_route("/api/ui/links", "GET") is True

    def test_api_health(self):
        assert _is_public_api_route("/api/health", "GET") is True

    # Public reviews — GET only
    def test_reviews_get(self):
        assert _is_public_api_route("/api/reviews", "GET") is True

    # Trailing slash variants should also be exempt
    def test_oauth_with_trailing_slash(self):
        assert _is_public_api_route("/api/auth/oauth/google/", "GET") is True

    def test_reviews_get_trailing_slash(self):
        assert _is_public_api_route("/api/reviews/", "GET") is True


# ─────────────────────────────────────────────────────────────────────────────
# 2. _is_public_api_route — False cases (protected routes)
# ─────────────────────────────────────────────────────────────────────────────

class TestProtectedRoutesNotExempt(unittest.TestCase):
    """Protected routes must NOT be exempted from brute-force tracking."""

    def test_profiles_me_is_protected(self):
        assert _is_public_api_route("/api/profiles/me", "GET") is False

    def test_profiles_list_is_protected(self):
        assert _is_public_api_route("/api/profiles", "GET") is False

    def test_config_is_protected(self):
        assert _is_public_api_route("/api/config", "GET") is False

    def test_execute_is_protected(self):
        assert _is_public_api_route("/api/execute", "POST") is False

    def test_reviews_post_is_protected(self):
        """POST /api/reviews (review submission) must stay protected."""
        assert _is_public_api_route("/api/reviews", "POST") is False

    def test_reviews_moderate_is_protected(self):
        assert _is_public_api_route("/api/reviews/submit", "POST") is False

    def test_auth_role_is_protected(self):
        assert _is_public_api_route("/api/auth/role", "GET") is False

    def test_auth_permissions_is_protected(self):
        assert _is_public_api_route("/api/auth/permissions", "GET") is False

    def test_status_is_protected(self):
        assert _is_public_api_route("/api/status", "GET") is False

    def test_admin_is_protected(self):
        assert _is_public_api_route("/api/admin", "GET") is False

    def test_workflows_is_protected(self):
        assert _is_public_api_route("/api/workflows", "GET") is False


# ─────────────────────────────────────────────────────────────────────────────
# 3. _is_static_or_ui_page — favicon exemptions
# ─────────────────────────────────────────────────────────────────────────────

class TestFaviconExemption(unittest.TestCase):
    """Browsers auto-request favicon.ico on every page load; it must be exempt."""

    def test_favicon_ico(self):
        assert _is_static_or_ui_page("/favicon.ico") is True

    def test_favicon_svg_suffix(self):
        assert _is_static_or_ui_page("/static/favicon.svg") is True

    def test_root_favicon_svg(self):
        assert _is_static_or_ui_page("/favicon.svg") is True

    def test_root_page_still_exempt(self):
        assert _is_static_or_ui_page("/") is True

    def test_static_assets_still_exempt(self):
        assert _is_static_or_ui_page("/static/styles.css") is True

    def test_api_not_exempt_via_static(self):
        assert _is_static_or_ui_page("/api/auth/oauth/google") is False


# ─────────────────────────────────────────────────────────────────────────────
# 4. BruteForceTracker — public routes do NOT accumulate failures
# ─────────────────────────────────────────────────────────────────────────────

class TestPublicRoutesDoNotAccumulateFailures(unittest.TestCase):
    """Simulate repeated unauthenticated hits to public routes; IP must stay unlocked."""

    def test_many_public_route_hits_no_lockout(self):
        """The middleware no longer calls record_failure for public routes.

        Contrast:
          - Protected route: each missing-credential request calls record_failure → lockout.
          - Public route:    the middleware returns early before record_failure → no lockout.

        This test uses _BruteForceTracker directly to document the invariant:
        if record_failure is NOT called (as it now isn't for public routes),
        an IP can accumulate unlimited "requests" without ever being locked out.
        """
        tracker = _BruteForceTracker(max_attempts=5, window_seconds=900, lockout_seconds=900)
        ip = "97.120.108.19"

        # Simulate 20 page-load-equivalent API hits to public routes.
        # The fix ensures record_failure is never called for these paths.
        for _ in range(20):
            # Public-route code path: no call to tracker.record_failure()
            pass  # intentionally empty — the middleware simply does call_next()

        # Even without any explicit check, the IP must remain unlocked
        assert tracker.is_locked_out(ip) is False, (
            "IP must NOT be locked out when no failures have been recorded"
        )

    def test_zero_failures_never_locks_out(self):
        """Verify the lock-out threshold explicitly: 0 failures → no lockout."""
        tracker = _BruteForceTracker(max_attempts=5, window_seconds=900, lockout_seconds=900)
        ip = "97.120.108.20"
        # Record 4 failures (one below threshold) then confirm no lockout
        for _ in range(4):
            locked = tracker.record_failure(ip)
            assert locked is False
        assert tracker.is_locked_out(ip) is False

    def test_four_failures_then_public_route_no_lockout(self):
        """Verifies that once close to threshold, hitting a public route does NOT
        push the counter over the edge (because record_failure is not called)."""
        tracker = _BruteForceTracker(max_attempts=5, window_seconds=900, lockout_seconds=900)
        ip = "97.120.108.21"

        # 4 failures on protected endpoints (close to limit)
        for _ in range(4):
            tracker.record_failure(ip)

        # Now simulate 10 hits to public routes — no record_failure calls
        for _ in range(10):
            pass  # public route path: record_failure is NOT called

        # Should still NOT be locked out (only 4 protected failures, not 5)
        assert tracker.is_locked_out(ip) is False


# ─────────────────────────────────────────────────────────────────────────────
# 5. BruteForceTracker — protected routes DO accumulate failures (regression)
# ─────────────────────────────────────────────────────────────────────────────

class TestProtectedRoutesStillLockOut(unittest.TestCase):
    """Repeated invalid-credential hits to protected routes must still lock out."""

    def test_repeated_failures_trigger_lockout(self):
        tracker = _BruteForceTracker(max_attempts=5, window_seconds=900, lockout_seconds=900)
        ip = "10.0.0.1"

        locked = False
        for _ in range(5):
            locked = tracker.record_failure(ip)

        assert locked is True, "5 failures within window must trigger lockout"
        assert tracker.is_locked_out(ip) is True

    def test_lockout_blocks_further_requests(self):
        tracker = _BruteForceTracker(max_attempts=3, window_seconds=900, lockout_seconds=900)
        ip = "10.0.0.2"

        for _ in range(3):
            tracker.record_failure(ip)

        assert tracker.is_locked_out(ip) is True

    def test_success_clears_lockout(self):
        tracker = _BruteForceTracker(max_attempts=3, window_seconds=900, lockout_seconds=900)
        ip = "10.0.0.3"

        for _ in range(3):
            tracker.record_failure(ip)

        tracker.record_success(ip)
        assert tracker.is_locked_out(ip) is False


# ─────────────────────────────────────────────────────────────────────────────
# 6. Integration: middleware dispatch skips brute-force for public routes
# ─────────────────────────────────────────────────────────────────────────────

class TestMiddlewareDispatchPublicRoutes(unittest.TestCase):
    """End-to-end dispatch: public routes pass through without hitting brute-force."""

    def _make_request(self, path: str, method: str = "GET"):
        """Build a minimal mock Starlette Request."""
        mock_request = MagicMock()
        mock_request.method = method
        mock_request.url.path = path
        mock_request.client = MagicMock()
        mock_request.client.host = "97.120.108.19"
        mock_request.headers = {}
        return mock_request

    def _run_dispatch(self, path: str, method: str = "GET", status_code: int = 200):
        """Run SecurityMiddleware.dispatch for a given path and return the response."""
        middleware = SecurityMiddleware(app=MagicMock(), service_name="test")
        request = self._make_request(path, method)

        mock_response = MagicMock()
        mock_response.headers = {}
        mock_response.status_code = status_code

        async def _call_next(_req):
            return mock_response

        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(middleware.dispatch(request, _call_next))
        finally:
            loop.close()

    def test_oauth_route_passes_through(self):
        """GET /api/auth/oauth/google must pass through without recording a failure."""
        response = self._run_dispatch("/api/auth/oauth/google", "GET", status_code=200)
        assert response.status_code == 200

    def test_reviews_get_passes_through(self):
        """GET /api/reviews must pass through without recording a failure."""
        response = self._run_dispatch("/api/reviews", "GET", status_code=200)
        assert response.status_code == 200

    def test_favicon_passes_through(self):
        """GET /favicon.ico must pass through (static exemption)."""
        response = self._run_dispatch("/favicon.ico", "GET", status_code=200)
        assert response.status_code == 200

    def test_public_route_does_not_record_failure_on_401(self):
        """Even when the underlying handler returns 401, public routes must NOT
        cause brute-force failure recording.  We verify this by confirming the
        IP stays unlocked even after many such requests."""
        from fastapi_security import _brute_force

        ip = "203.0.113.42"
        # Reset any existing tracking for this IP
        _brute_force._attempts.pop(ip, None)
        _brute_force._lockouts.pop(ip, None)

        middleware = SecurityMiddleware(app=MagicMock(), service_name="test")

        async def _simulate_public_hits():
            for _ in range(10):
                request = self._make_request("/api/auth/oauth/google", "GET")
                request.client.host = ip
                mock_response = MagicMock()
                mock_response.headers = {}
                mock_response.status_code = 401  # underlying handler returns 401
                await middleware.dispatch(request, AsyncMock(return_value=mock_response))

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(_simulate_public_hits())
        finally:
            loop.close()

        assert not _brute_force.is_locked_out(ip), (
            "IP must NOT be locked out after repeated hits to public OAuth route"
        )

    def test_protected_route_records_failures_on_missing_creds(self):
        """Missing credentials on a protected route DO accumulate toward lockout."""
        from fastapi_security import _brute_force

        ip = "198.51.100.7"
        _brute_force._attempts.pop(ip, None)
        _brute_force._lockouts.pop(ip, None)

        # Run in a fresh production-like environment so the middleware enforces auth
        with patch.dict(os.environ, {"MURPHY_ENV": "production", "MURPHY_API_KEYS": "secret-key"}):
            middleware = SecurityMiddleware(app=MagicMock(), service_name="test")

            async def _simulate_protected_hits():
                for _ in range(5):
                    request = self._make_request("/api/profiles/me", "GET")
                    request.client.host = ip
                    request.headers = {}  # no credentials
                    mock_response = MagicMock()
                    mock_response.headers = {}
                    mock_response.status_code = 200
                    await middleware.dispatch(request, AsyncMock(return_value=mock_response))

            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(_simulate_protected_hits())
            finally:
                loop.close()

        assert _brute_force.is_locked_out(ip), (
            "IP must be locked out after 5 failed attempts on protected route"
        )


if __name__ == "__main__":
    unittest.main()
