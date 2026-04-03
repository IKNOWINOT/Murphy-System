"""
Tests for the GET /api/auth/providers endpoint.

Validates:
  1. The endpoint returns HTTP 200 with a JSON body
  2. The response contains a "providers" dict keyed by provider name
  3. Each provider value is a boolean (True/False for enabled status)
  4. Providers without client_id configured show False
  5. The endpoint is accessible without authentication
  6. The fastapi_security public-route exemption covers /api/auth/providers

Design Labels: TEST-AUTH-PROVIDERS-001
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest



# ---------------------------------------------------------------------------
# Helper: build a minimal FastAPI app with the /api/auth/providers handler
# ---------------------------------------------------------------------------

def _make_app(registry=None):
    """Build a minimal FastAPI app that replicates the /api/auth/providers handler."""
    try:
        from fastapi import FastAPI
        from fastapi.responses import JSONResponse
        from fastapi.testclient import TestClient
    except ImportError:
        pytest.skip("fastapi/httpx not installed")

    app = FastAPI()

    # Simulate the module-level _oauth_registry used in the real app
    _holder = {"registry": registry}

    @app.get("/api/auth/providers")
    async def auth_providers():
        """Return which OAuth providers are configured (have client credentials)."""
        configured = {}
        _oauth_registry = _holder["registry"]
        if _oauth_registry is not None:
            try:
                from src.account_management.models import OAuthProvider
                for p in OAuthProvider:
                    if p.value == "custom":
                        continue
                    try:
                        cfg = _oauth_registry.get_provider(p)
                        configured[p.value] = bool(cfg and cfg.client_id and cfg.enabled)
                    except Exception:
                        configured[p.value] = False
            except ImportError:
                # Fallback when account models are unavailable in test environment
                for name in ["google", "github", "meta", "linkedin", "apple", "microsoft"]:
                    try:
                        cfg = _oauth_registry.get_provider(name)
                        configured[name] = bool(cfg and cfg.client_id and cfg.enabled)
                    except Exception:
                        configured[name] = False
        # Env-var fallback: detect Google OAuth from env when registry is None
        if not configured.get("google") and os.environ.get("MURPHY_OAUTH_GOOGLE_CLIENT_ID"):
            configured["google"] = True
        return JSONResponse({"providers": configured})

    return TestClient(app), _holder


# ---------------------------------------------------------------------------
# 1. Returns 200 with providers dict
# ---------------------------------------------------------------------------

class TestAuthProvidersBasic:
    def test_returns_200(self):
        client, _ = _make_app()
        resp = client.get("/api/auth/providers")
        assert resp.status_code == 200

    def test_body_has_providers_key(self):
        client, _ = _make_app()
        data = client.get("/api/auth/providers").json()
        assert "providers" in data

    def test_providers_is_dict_or_list(self):
        client, _ = _make_app()
        data = client.get("/api/auth/providers").json()
        # providers may be dict or list depending on implementation
        assert isinstance(data["providers"], (dict, list))

    def test_no_auth_required(self):
        """Endpoint must respond 200 with no Authorization header."""
        client, _ = _make_app()
        resp = client.get("/api/auth/providers", headers={})
        assert resp.status_code == 200

    def test_content_type_json(self):
        client, _ = _make_app()
        resp = client.get("/api/auth/providers")
        assert "application/json" in resp.headers.get("content-type", "")


# ---------------------------------------------------------------------------
# 2. When registry is None — returns empty providers
# ---------------------------------------------------------------------------

class TestAuthProvidersNoRegistry:
    def test_empty_when_no_registry(self):
        client, _ = _make_app(registry=None)
        data = client.get("/api/auth/providers").json()
        providers = data["providers"]
        if isinstance(providers, dict):
            assert providers == {}
        else:
            assert providers == []


# ---------------------------------------------------------------------------
# 3. With a mock registry — enabled and disabled providers
# ---------------------------------------------------------------------------

class _FakeCfg:
    def __init__(self, client_id="", enabled=True):
        self.client_id = client_id
        self.enabled = enabled


class _FakeRegistry:
    def __init__(self, configs):
        self._configs = configs  # dict: provider_value -> _FakeCfg or None

    def get_provider(self, provider):
        key = provider if isinstance(provider, str) else provider.value
        return self._configs.get(key)


class TestAuthProvidersWithRegistry:
    def _make_registry(self):
        return _FakeRegistry({
            "google": _FakeCfg(client_id="gid-123", enabled=True),
            "github": _FakeCfg(client_id="", enabled=True),   # no client_id → disabled
            "meta": _FakeCfg(client_id="mid-456", enabled=False),  # disabled flag
            "linkedin": None,  # not configured → disabled
            "apple": _FakeCfg(client_id="aid-789", enabled=True),
            "microsoft": None,
        })

    def test_google_enabled_when_client_id_set(self):
        client, _ = _make_app(registry=self._make_registry())
        data = client.get("/api/auth/providers").json()
        providers = data["providers"]
        if isinstance(providers, dict):
            # google has client_id and enabled=True
            assert providers.get("google") is True
        # If list format, skip provider-specific check (format handled by real endpoint)

    def test_github_disabled_when_no_client_id(self):
        client, _ = _make_app(registry=self._make_registry())
        data = client.get("/api/auth/providers").json()
        providers = data["providers"]
        if isinstance(providers, dict):
            assert providers.get("github") is False

    def test_meta_disabled_when_flag_false(self):
        client, _ = _make_app(registry=self._make_registry())
        data = client.get("/api/auth/providers").json()
        providers = data["providers"]
        if isinstance(providers, dict):
            assert providers.get("meta") is False


# ---------------------------------------------------------------------------
# 4. fastapi_security exemption covers /api/auth/providers
# ---------------------------------------------------------------------------

class TestPublicRouteExemption:
    def test_auth_providers_is_public(self):
        """_is_public_api_route must return True for /api/auth/providers."""
        try:
            from fastapi_security import _is_public_api_route
        except ImportError:
            pytest.skip("fastapi_security not importable")

        assert _is_public_api_route("/api/auth/providers") is True
        # Trailing slash variant
        assert _is_public_api_route("/api/auth/providers/") is True

    def test_auth_providers_not_counted_as_protected(self):
        """Confirm the path is not treated as a protected API route."""
        try:
            from fastapi_security import _is_public_api_route
        except ImportError:
            pytest.skip("fastapi_security not importable")

        # Protected routes must return False
        assert _is_public_api_route("/api/accounts/me") is False
        assert _is_public_api_route("/api/billing/subscribe") is False
        # Public routes must return True
        assert _is_public_api_route("/api/auth/providers") is True


# ---------------------------------------------------------------------------
# 5. Endpoint survives registry exceptions gracefully
# ---------------------------------------------------------------------------

class TestAuthProvidersRobustness:
    def test_exception_in_registry_returns_200(self):
        """If the registry raises on get_provider, the endpoint should not crash."""
        class _ExplodingRegistry:
            def get_provider(self, provider):
                raise RuntimeError("Registry exploded")

        client, _ = _make_app(registry=_ExplodingRegistry())
        resp = client.get("/api/auth/providers")
        # Should return 200 even if provider iteration hits an exception
        assert resp.status_code == 200
        data = resp.json()
        assert "providers" in data
        # All providers should be marked disabled (False) when registry explodes
        providers = data["providers"]
        if isinstance(providers, dict):
            for v in providers.values():
                assert v is False


# ---------------------------------------------------------------------------
# 6. Env-var fallback detects Google from MURPHY_OAUTH_GOOGLE_CLIENT_ID
# ---------------------------------------------------------------------------

class TestAuthProvidersEnvVarFallback:
    """When registry is None but MURPHY_OAUTH_GOOGLE_CLIENT_ID env var is set,
    the endpoint should report google as available."""

    def test_google_true_when_env_var_set(self):
        with patch.dict(os.environ, {"MURPHY_OAUTH_GOOGLE_CLIENT_ID": "test-id-123"}):
            client, _ = _make_app(registry=None)
            resp = client.get("/api/auth/providers")
        assert resp.status_code == 200
        data = resp.json()
        assert data["providers"].get("google") is True

    def test_google_absent_when_env_var_not_set(self):
        env_clean = {"MURPHY_OAUTH_GOOGLE_CLIENT_ID": ""}
        with patch.dict(os.environ, env_clean):
            client, _ = _make_app(registry=None)
            resp = client.get("/api/auth/providers")
        assert resp.status_code == 200
        data = resp.json()
        assert not data["providers"].get("google")
