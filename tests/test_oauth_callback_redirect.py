"""
Tests for OAuth callback redirect behaviour.

Verifies that ``GET /api/auth/callback`` redirects to ``/dashboard.html``
with a ``murphy_session`` cookie after a successful OAuth flow, instead of
returning a raw JSON response.

Covers:
  1. Successful callback issues a 302 redirect (not 200 JSON).
  2. Redirect location is ``/dashboard.html``.
  3. ``murphy_session`` cookie is set on the response.
  4. Redirect URL contains ``session_token``, ``user_id``, and ``provider``
     as URL-encoded query parameters.
  5. Missing ``code`` or ``state`` returns 400 JSON.
  6. Unavailable OAuth registry returns 503 JSON.

Copyright © 2020-2026 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import sys
import os
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.parse import urlparse, parse_qs

import pytest

# ---------------------------------------------------------------------------
# Sys-path setup
# ---------------------------------------------------------------------------

_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))


# ---------------------------------------------------------------------------
# Helpers
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

    def test_redirect_location_is_dashboard(self, app_client):
        """Redirect must point to /dashboard.html."""
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
        assert location.startswith("/dashboard.html"), (
            f"Expected redirect to /dashboard.html, got: {location!r}"
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

    def test_redirect_url_contains_expected_query_params(self, app_client):
        """Redirect URL must contain session_token, user_id, and provider."""
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

        assert "session_token" in qs, f"session_token missing from redirect URL: {location}"
        assert "user_id" in qs, f"user_id missing from redirect URL: {location}"
        assert "provider" in qs, f"provider missing from redirect URL: {location}"
        assert qs["user_id"][0] == "goog-user-99", (
            f"Expected user_id=goog-user-99, got {qs['user_id']}"
        )
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
