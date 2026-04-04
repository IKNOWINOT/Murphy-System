"""
Tests for the OAuth callback handler redirect behaviour introduced in the
fix-oauth-callback-redirect PR.

Validates:
  - Successful OAuth flow returns 302 to /ui/terminal-unified
  - Redirect URL contains ?oauth_success=1&provider=<name>
  - murphy_session cookie is set with correct attributes
  - Missing code/state returns 400
  - Unavailable OAuth registry returns 503

Design Labels: TEST-AUTH-CALLBACK-001
"""

import secrets
import sys
import os
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.parse import urlparse, parse_qs

import pytest

_root = Path(__file__).resolve().parent.parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_app():
    """Build a minimal FastAPI test app that replicates the callback handler."""
    try:
        from fastapi import FastAPI, Request
        from fastapi.responses import JSONResponse, RedirectResponse
        from fastapi.testclient import TestClient
    except ImportError:
        pytest.skip("fastapi/httpx not installed")

    app = FastAPI()

    # Simulated OAuth registry (mirrors the real complete_auth_flow contract)
    class _FakeToken:
        def __init__(self, provider_value="google", profile=None):
            self.provider = MagicMock()
            self.provider.value = provider_value
            self.token_type = "Bearer"
            self.refresh_token = "rt-abc"
            self.expires_at = None
            self.raw_profile = profile or {"email": "user@example.com", "name": "Test User"}

    class _FakeRegistry:
        def __init__(self, token=None, raises=None):
            self._token = token or _FakeToken()
            self._raises = raises

        def complete_auth_flow(self, state, code):
            if self._raises:
                raise self._raises
            return self._token

    # Module-level reference to allow test injection
    _registry_holder = {"registry": _FakeRegistry()}

    @app.get("/api/auth/callback")
    async def oauth_callback(request: Request):
        """Replica of the production callback handler."""
        params = dict(request.query_params)
        code = params.get("code", "")
        state = params.get("state", "")
        if not code or not state:
            return JSONResponse(
                {"error": "Missing code or state parameter"},
                status_code=400,
            )
        _oauth_registry = _registry_holder["registry"]
        if _oauth_registry is None:
            return JSONResponse({"error": "OAuth registry unavailable"}, status_code=503)
        try:
            import secrets as _secrets
            token = _oauth_registry.complete_auth_flow(state, code)
            session_token = _secrets.token_urlsafe(32)
            provider_name = token.provider.value
            redirect_url = (
                "/ui/terminal-unified"
                "?oauth_success=1"
                f"&provider={provider_name}"
            )
            response = RedirectResponse(redirect_url, status_code=302)
            response.set_cookie(
                key="murphy_session",
                value=session_token,
                httponly=True,
                secure=True,
                samesite="lax",
                max_age=86400,
            )
            return response
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        except Exception as exc:
            return JSONResponse({"error": "internal error"}, status_code=500)

    return TestClient(app, raise_server_exceptions=False), _registry_holder


# ---------------------------------------------------------------------------
# Test classes
# ---------------------------------------------------------------------------


class TestOAuthCallbackMissingParams:
    """Missing query-string parameters must return 400."""

    def test_no_code_no_state(self):
        client, _ = _make_app()
        resp = client.get("/api/auth/callback")
        assert resp.status_code == 400
        assert "error" in resp.json()

    def test_code_only(self):
        client, _ = _make_app()
        resp = client.get("/api/auth/callback?code=abc")
        assert resp.status_code == 400

    def test_state_only(self):
        client, _ = _make_app()
        resp = client.get("/api/auth/callback?state=xyz")
        assert resp.status_code == 400


class TestOAuthCallbackNoRegistry:
    """503 when the OAuth registry is unavailable."""

    def test_registry_unavailable(self):
        client, holder = _make_app()
        holder["registry"] = None
        resp = client.get(
            "/api/auth/callback?code=abc&state=xyz",
            follow_redirects=False,
        )
        assert resp.status_code == 503


class TestOAuthCallbackSuccess:
    """Successful flow must redirect with cookie and correct URL."""

    def test_returns_302(self):
        client, _ = _make_app()
        resp = client.get(
            "/api/auth/callback?code=auth-code-123&state=state-abc",
            follow_redirects=False,
        )
        assert resp.status_code == 302

    def test_redirect_location_contains_oauth_success(self):
        client, _ = _make_app()
        resp = client.get(
            "/api/auth/callback?code=auth-code-123&state=state-abc",
            follow_redirects=False,
        )
        location = resp.headers.get("location", "")
        assert "oauth_success=1" in location

    def test_redirect_location_contains_provider(self):
        client, _ = _make_app()
        resp = client.get(
            "/api/auth/callback?code=auth-code-123&state=state-abc",
            follow_redirects=False,
        )
        location = resp.headers.get("location", "")
        assert "provider=google" in location

    def test_redirect_location_points_to_dashboard(self):
        client, _ = _make_app()
        resp = client.get(
            "/api/auth/callback?code=auth-code-123&state=state-abc",
            follow_redirects=False,
        )
        location = resp.headers.get("location", "")
        assert location.startswith("/ui/terminal-unified")

    def test_murphy_session_cookie_set(self):
        client, _ = _make_app()
        resp = client.get(
            "/api/auth/callback?code=auth-code-123&state=state-abc",
            follow_redirects=False,
        )
        assert "murphy_session" in resp.cookies

    def test_murphy_session_cookie_not_empty(self):
        client, _ = _make_app()
        resp = client.get(
            "/api/auth/callback?code=auth-code-123&state=state-abc",
            follow_redirects=False,
        )
        cookie_val = resp.cookies.get("murphy_session", "")
        assert len(cookie_val) > 0

    def test_each_request_gets_unique_session_token(self):
        client, _ = _make_app()

        def _get_token():
            r = client.get(
                "/api/auth/callback?code=auth-code-123&state=state-abc",
                follow_redirects=False,
            )
            return r.cookies.get("murphy_session", "")

        t1 = _get_token()
        t2 = _get_token()
        assert t1 and t2
        assert t1 != t2


class TestOAuthCallbackRegistryError:
    """Registry errors must return 400 (ValueError) or 500."""

    def test_invalid_state_returns_400(self):
        client, holder = _make_app()
        holder["registry"].complete_auth_flow = MagicMock(
            side_effect=ValueError("Invalid or expired OAuth state")
        )
        resp = client.get(
            "/api/auth/callback?code=abc&state=expired",
            follow_redirects=False,
        )
        assert resp.status_code == 400

    def test_unexpected_error_returns_500(self):
        client, holder = _make_app()
        holder["registry"].complete_auth_flow = MagicMock(
            side_effect=RuntimeError("Network timeout")
        )
        resp = client.get(
            "/api/auth/callback?code=abc&state=xyz",
            follow_redirects=False,
        )
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# Helpers (for integration tests using the real app)
# ---------------------------------------------------------------------------

def _make_token(provider_value: str = "google", user_sub: str = "user-123") -> MagicMock:
    """Return a mock OAuthToken as returned by complete_auth_flow."""
    tok = MagicMock()
    tok.provider.value = provider_value
    tok.token_type = "Bearer"
    tok.refresh_token = "rt-xxx"
    tok.expires_at = "2026-03-18T00:00:00+00:00"
    tok.raw_profile = {"sub": user_sub, "email": "test@example.com", "name": "Test User"}
    return tok


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def app_client():
    """Create a TestClient for the FastAPI app."""
    from starlette.testclient import TestClient
    from src.runtime.app import create_app

    return TestClient(create_app(), raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestOAuthCallbackRedirect:
    """Verify /api/auth/callback now redirects instead of returning JSON."""

    def test_successful_callback_issues_redirect(self, app_client):
        """A valid callback must respond with 302 (not 200 JSON)."""
        mock_token = _make_token()
        _registry_path = (
            "src.account_management.oauth_provider_registry"
            ".OAuthProviderRegistry.complete_auth_flow"
        )
        with patch(_registry_path, return_value=mock_token):
            resp = app_client.get(
                "/api/auth/callback",
                params={"code": "auth-code-abc", "state": "state-xyz"},
                follow_redirects=False,
            )

        assert resp.status_code == 302, (
            f"Expected 302 redirect, got {resp.status_code}. "
            f"Body: {resp.text[:200]}"
        )

    def test_redirect_location_is_terminal_unified(self, app_client):
        """Redirect must point to /ui/terminal-unified."""
        mock_token = _make_token()
        _registry_path = (
            "src.account_management.oauth_provider_registry"
            ".OAuthProviderRegistry.complete_auth_flow"
        )
        with patch(_registry_path, return_value=mock_token):
            resp = app_client.get(
                "/api/auth/callback",
                params={"code": "auth-code-abc", "state": "state-xyz"},
                follow_redirects=False,
            )

        location = resp.headers.get("location", "")
        assert location.startswith("/ui/terminal-unified"), (
            f"Expected redirect to /ui/terminal-unified, got: {location!r}"
        )
        assert "oauth_success=1" in location, (
            f"Expected oauth_success=1 in redirect URL, got: {location!r}"
        )

    def test_murphy_session_cookie_is_set(self, app_client):
        """Response must set the murphy_session cookie."""
        mock_token = _make_token()
        _registry_path = (
            "src.account_management.oauth_provider_registry"
            ".OAuthProviderRegistry.complete_auth_flow"
        )
        with patch(_registry_path, return_value=mock_token):
            resp = app_client.get(
                "/api/auth/callback",
                params={"code": "auth-code-abc", "state": "state-xyz"},
                follow_redirects=False,
            )

        cookies = resp.cookies
        assert "murphy_session" in cookies, (
            f"murphy_session cookie not set. Cookies: {dict(cookies)}"
        )
        assert cookies["murphy_session"], "murphy_session cookie value must not be empty"

    def test_redirect_url_contains_provider_param(self, app_client):
        """Redirect URL must contain provider query parameter."""
        mock_token = _make_token(provider_value="google", user_sub="goog-user-99")
        _registry_path = (
            "src.account_management.oauth_provider_registry"
            ".OAuthProviderRegistry.complete_auth_flow"
        )
        with patch(_registry_path, return_value=mock_token):
            resp = app_client.get(
                "/api/auth/callback",
                params={"code": "auth-code-abc", "state": "state-xyz"},
                follow_redirects=False,
            )

        location = resp.headers.get("location", "")
        qs = parse_qs(urlparse(location).query)

        assert "provider" in qs, f"provider missing from redirect URL: {location}"
        assert qs["provider"][0] == "google", (
            f"Expected provider=google, got {qs['provider']}"
        )

    def test_missing_code_returns_400(self, app_client):
        """Callback without code param must return 400 JSON error."""
        resp = app_client.get(
            "/api/auth/callback",
            params={"state": "state-xyz"},
            follow_redirects=False,
        )
        assert resp.status_code == 400
        body = resp.json()
        assert "error" in body

    def test_missing_state_returns_400(self, app_client):
        """Callback without state param must return 400 JSON error."""
        resp = app_client.get(
            "/api/auth/callback",
            params={"code": "auth-code-abc"},
            follow_redirects=False,
        )
        assert resp.status_code == 400
        body = resp.json()
        assert "error" in body
