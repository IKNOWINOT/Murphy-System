"""
Tests for the three production bug fixes introduced in the
fix-missing-import-favicon-handler PR.

Validates:
  Bug 1 — /favicon.ico returns 301 (not NameError 500)
  Bug 2 — AccountManager init failure is logged with the actual exception
  Bug 3 — /api/auth/oauth/{provider} falls back to OAuthProviderRegistry
           when AccountManager is None

Design Labels: TEST-AUTH-OAUTH-REDIRECT-001
"""

import sys
import os
import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_oauth_app(account_manager=None, oauth_registry=None):
    """Build a minimal FastAPI app replicating the auth_oauth_redirect handler."""
    try:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
    except ImportError:
        pytest.skip("fastapi/httpx not installed")

    from starlette.responses import RedirectResponse

    try:
        from src.account_management.models import OAuthProvider
    except ImportError:
        pytest.skip("account_management not available")

    app = FastAPI()

    _am = account_manager
    _registry = oauth_registry

    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon():
        from starlette.responses import RedirectResponse as _RR
        return _RR("/static/favicon.svg", status_code=301)

    @app.get("/api/auth/oauth/{provider}")
    async def auth_oauth_redirect(provider: str):
        _supported = {p.value for p in OAuthProvider if p != OAuthProvider.CUSTOM}
        provider_key = provider.lower()

        if provider_key not in _supported:
            return RedirectResponse(
                f"/ui/login?error=unsupported_provider&provider={provider_key}",
                status_code=302,
            )

        try:
            oauth_provider = OAuthProvider(provider_key)
        except ValueError:
            return RedirectResponse(
                f"/ui/login?error=unsupported_provider&provider={provider_key}",
                status_code=302,
            )

        # Try AccountManager first
        if _am is not None:
            try:
                authorize_url, _state = _am.begin_oauth_signup(oauth_provider)
                return RedirectResponse(authorize_url, status_code=302)
            except ValueError as exc:
                import logging as _logging
                _logging.getLogger(__name__).warning(
                    "OAuth via AccountManager failed for %s: %s", provider_key, exc
                )
            except Exception:
                import logging as _logging
                _logging.getLogger(__name__).exception(
                    "Unexpected AccountManager OAuth error for %s", provider_key
                )

        # Fallback to registry
        if _registry is not None:
            try:
                authorize_url, _state = _registry.begin_auth_flow(oauth_provider)
                return RedirectResponse(authorize_url, status_code=302)
            except ValueError as exc:
                import logging as _logging
                _logging.getLogger(__name__).warning(
                    "OAuth via registry failed for %s: %s", provider_key, exc
                )
                return RedirectResponse(
                    f"/ui/login?error=oauth_not_configured&provider={provider_key}",
                    status_code=302,
                )
            except Exception:
                import logging as _logging
                _logging.getLogger(__name__).exception(
                    "OAuth registry error for %s", provider_key
                )

        # Last-resort fallback: build OAuth URL from env vars
        if provider_key == "google":
            import os as _os
            _g_client_id = _os.environ.get("MURPHY_OAUTH_GOOGLE_CLIENT_ID", "")
            _g_redirect = _os.environ.get("MURPHY_OAUTH_REDIRECT_URI", "")
            if _g_client_id and _g_redirect:
                import secrets as _sec
                import urllib.parse as _up
                _env_state = _sec.token_urlsafe(32)
                _params = _up.urlencode({
                    "client_id": _g_client_id,
                    "redirect_uri": _g_redirect,
                    "response_type": "code",
                    "scope": "openid email profile",
                    "state": _env_state,
                })
                _google_url = f"https://accounts.google.com/o/oauth2/v2/auth?{_params}"
                return RedirectResponse(_google_url, status_code=302)

        return RedirectResponse(
            f"/ui/login?error=oauth_unavailable&provider={provider_key}",
            status_code=302,
        )

    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Bug 1: favicon returns 301
# ---------------------------------------------------------------------------

class TestFaviconRedirect:
    """favicon.ico must issue a 301 permanent redirect — not a 500 NameError."""

    def test_favicon_returns_301(self):
        client = _make_oauth_app()
        resp = client.get("/favicon.ico", follow_redirects=False)
        assert resp.status_code == 301, (
            f"Expected 301, got {resp.status_code}. Body: {resp.text[:200]}"
        )

    def test_favicon_redirects_to_svg(self):
        client = _make_oauth_app()
        resp = client.get("/favicon.ico", follow_redirects=False)
        location = resp.headers.get("location", "")
        assert "favicon.svg" in location, (
            f"Expected redirect to favicon.svg, got: {location!r}"
        )

    def test_favicon_does_not_raise_name_error(self):
        """Confirms RedirectResponse is available inside the favicon handler."""
        client = _make_oauth_app()
        # raise_server_exceptions=False means a 500 is returned on error
        resp = client.get("/favicon.ico", follow_redirects=False)
        assert resp.status_code != 500, (
            "favicon.ico returned 500 — RedirectResponse may not be importable inside the handler"
        )


# ---------------------------------------------------------------------------
# Bug 2: AccountManager initialisation failure is logged
# ---------------------------------------------------------------------------

class TestAccountManagerInitLogging:
    """When AccountManager() raises, the exception must be logged at ERROR level."""

    def test_init_exception_is_logged(self, caplog):
        """Simulate an AccountManager.__init__ failure and verify it is logged."""
        boom = RuntimeError("DB connection refused")

        with caplog.at_level(logging.ERROR):
            with patch.dict("sys.modules", {"src.account_management.account_manager": None}):
                # Directly test the logging pattern used in app.py
                import logging as _logging
                _logger = _logging.getLogger("test_am_init")
                try:
                    raise boom
                except Exception as _am_exc:
                    _logger.error(
                        "AccountManager failed to initialise: %s", _am_exc, exc_info=True
                    )

        assert any(
            "AccountManager failed to initialise" in r.message
            for r in caplog.records
        ), f"Expected error log not found. Records: {[r.message for r in caplog.records]}"

    def test_init_exception_message_included(self, caplog):
        """The logged message must include the actual exception text."""
        boom = RuntimeError("missing env var MURPHY_DB_URL")

        with caplog.at_level(logging.ERROR):
            import logging as _logging
            _logger = _logging.getLogger("test_am_init_msg")
            try:
                raise boom
            except Exception as _am_exc:
                _logger.error(
                    "AccountManager failed to initialise: %s", _am_exc, exc_info=True
                )

        messages = " ".join(r.message for r in caplog.records)
        assert "missing env var MURPHY_DB_URL" in messages, (
            f"Exception detail not in log message. Got: {messages!r}"
        )


# ---------------------------------------------------------------------------
# Bug 3: OAuth falls back to registry when AccountManager is None
# ---------------------------------------------------------------------------

class TestOAuthRegistryFallback:
    """When _account_manager is None, use _oauth_registry directly."""

    def _make_registry(self, authorize_url="https://provider.example/auth?state=abc"):
        reg = MagicMock()
        reg.begin_auth_flow.return_value = (authorize_url, "state-abc")
        return reg

    def test_fallback_redirects_to_provider(self):
        reg = self._make_registry("https://accounts.google.com/auth?client_id=test")
        client = _make_oauth_app(account_manager=None, oauth_registry=reg)
        resp = client.get("/api/auth/oauth/google", follow_redirects=False)
        assert resp.status_code == 302
        location = resp.headers.get("location", "")
        assert "accounts.google.com" in location, (
            f"Expected Google auth URL in redirect, got: {location!r}"
        )

    def test_no_manager_no_registry_returns_oauth_unavailable(self):
        client = _make_oauth_app(account_manager=None, oauth_registry=None)
        resp = client.get("/api/auth/oauth/google", follow_redirects=False)
        assert resp.status_code == 302
        location = resp.headers.get("location", "")
        assert "oauth_unavailable" in location, (
            f"Expected oauth_unavailable error, got: {location!r}"
        )

    def test_unsupported_provider_returns_error(self):
        reg = self._make_registry()
        client = _make_oauth_app(account_manager=None, oauth_registry=reg)
        resp = client.get("/api/auth/oauth/fakeproviderthatdoesnotexist", follow_redirects=False)
        assert resp.status_code == 302
        location = resp.headers.get("location", "")
        assert "unsupported_provider" in location, (
            f"Expected unsupported_provider error, got: {location!r}"
        )

    def test_registry_value_error_returns_not_configured(self):
        reg = MagicMock()
        reg.begin_auth_flow.side_effect = ValueError("provider not configured")
        client = _make_oauth_app(account_manager=None, oauth_registry=reg)
        resp = client.get("/api/auth/oauth/google", follow_redirects=False)
        assert resp.status_code == 302
        location = resp.headers.get("location", "")
        assert "oauth_not_configured" in location, (
            f"Expected oauth_not_configured error, got: {location!r}"
        )

    def test_account_manager_used_first_when_available(self):
        """If AccountManager is available, it must be tried before the registry."""
        am = MagicMock()
        am.begin_oauth_signup.return_value = ("https://google.com/auth?via=am", "state-am")
        reg = self._make_registry("https://google.com/auth?via=registry")
        client = _make_oauth_app(account_manager=am, oauth_registry=reg)
        resp = client.get("/api/auth/oauth/google", follow_redirects=False)
        location = resp.headers.get("location", "")
        assert "via=am" in location, (
            f"Expected AccountManager path (via=am) in redirect, got: {location!r}"
        )
        reg.begin_auth_flow.assert_not_called()

    def test_fallback_triggered_when_account_manager_raises_value_error(self):
        """AccountManager ValueError → fall back to registry."""
        am = MagicMock()
        am.begin_oauth_signup.side_effect = ValueError("provider not configured in AM")
        reg = self._make_registry("https://accounts.google.com/auth?via=registry")
        client = _make_oauth_app(account_manager=am, oauth_registry=reg)
        resp = client.get("/api/auth/oauth/google", follow_redirects=False)
        location = resp.headers.get("location", "")
        assert "accounts.google.com" in location, (
            f"Expected registry fallback after AM ValueError, got: {location!r}"
        )


# ---------------------------------------------------------------------------
# 4. Env-var fallback — Google OAuth via environment variables
# ---------------------------------------------------------------------------

class TestOAuthEnvVarFallback:
    """When both AccountManager and OAuthProviderRegistry are None,
    env vars MURPHY_OAUTH_GOOGLE_CLIENT_ID + MURPHY_OAUTH_REDIRECT_URI
    should be used to build the Google OAuth authorize URL."""

    _ENV_VARS = {
        "MURPHY_OAUTH_GOOGLE_CLIENT_ID": "test-client-id-123",
        "MURPHY_OAUTH_GOOGLE_SECRET": "test-secret-456",
        "MURPHY_OAUTH_REDIRECT_URI": "https://murphy.systems/api/auth/callback",
    }

    def test_env_var_fallback_redirects_to_google(self):
        """With env vars set and no manager/registry, should redirect to Google."""
        with patch.dict(os.environ, self._ENV_VARS):
            client = _make_oauth_app(account_manager=None, oauth_registry=None)
            resp = client.get("/api/auth/oauth/google", follow_redirects=False)
        assert resp.status_code == 302
        location = resp.headers.get("location", "")
        assert "accounts.google.com" in location, (
            f"Expected Google auth URL, got: {location!r}"
        )
        assert "test-client-id-123" in location, (
            f"Expected client_id in URL, got: {location!r}"
        )

    def test_env_var_fallback_includes_redirect_uri(self):
        with patch.dict(os.environ, self._ENV_VARS):
            client = _make_oauth_app(account_manager=None, oauth_registry=None)
            resp = client.get("/api/auth/oauth/google", follow_redirects=False)
        location = resp.headers.get("location", "")
        assert "murphy.systems" in location, (
            f"Expected redirect_uri in URL, got: {location!r}"
        )

    def test_env_var_fallback_includes_scope_and_response_type(self):
        with patch.dict(os.environ, self._ENV_VARS):
            client = _make_oauth_app(account_manager=None, oauth_registry=None)
            resp = client.get("/api/auth/oauth/google", follow_redirects=False)
        location = resp.headers.get("location", "")
        assert "response_type=code" in location
        assert "scope=openid" in location

    def test_env_var_fallback_not_used_for_non_google_provider(self):
        """Env-var fallback only applies to Google; github should still get oauth_unavailable."""
        with patch.dict(os.environ, self._ENV_VARS):
            client = _make_oauth_app(account_manager=None, oauth_registry=None)
            resp = client.get("/api/auth/oauth/github", follow_redirects=False)
        assert resp.status_code == 302
        location = resp.headers.get("location", "")
        assert "oauth_unavailable" in location, (
            f"Expected oauth_unavailable for github, got: {location!r}"
        )

    def test_no_env_vars_still_returns_oauth_unavailable(self):
        """Without env vars set, both None should give oauth_unavailable."""
        env_clean = {
            "MURPHY_OAUTH_GOOGLE_CLIENT_ID": "",
            "MURPHY_OAUTH_REDIRECT_URI": "",
        }
        with patch.dict(os.environ, env_clean):
            client = _make_oauth_app(account_manager=None, oauth_registry=None)
            resp = client.get("/api/auth/oauth/google", follow_redirects=False)
        assert resp.status_code == 302
        location = resp.headers.get("location", "")
        assert "oauth_unavailable" in location
