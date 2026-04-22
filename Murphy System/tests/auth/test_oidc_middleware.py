"""Tests for ``OIDCAuthMiddleware`` (ADR-0012 Release N).

Covers the authentication ordering described in the ADR:

  1. ``Authorization: Bearer <jwt>``  → OIDC verifier
  2. ``Cookie: murphy_sid=<sid>``     → server-side session
  3. ``X-API-Key`` (deprecated)       → only when allowed AND on
                                        the legacy m2m route allowlist

Plus the deprecation-counter increment, the route-allowlist enforcement,
the ``MURPHY_ALLOW_API_KEY=false`` flip (Release N+1 preview), the
``OIDC_DISCOVERY_FAILED`` 503 ("no silent fallback"), and the
back-compat default that `MURPHY_API_KEY` set ⇒ auth enforced.
"""

from __future__ import annotations

import os

import pytest

pytest.importorskip("starlette")
pytest.importorskip("fastapi")

from fastapi import FastAPI, Request  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from auth_middleware import (  # noqa: E402
    OIDCAuthMiddleware,
    api_key_deprecation_counter,
    default_session_store,
)


# ── Helpers ────────────────────────────────────────────────────────────────


class _StubVerifier:
    """Minimal OIDCVerifier substitute for middleware tests."""

    def __init__(self, *, ok_token: str, claims, raises=None):
        self.ok_token = ok_token
        self.claims = claims
        self.raises = raises  # exception instance or None

    def verify(self, token, *, now=None):
        if self.raises is not None:
            raise self.raises
        if token != self.ok_token:
            from oidc_verifier import OIDCTokenError
            raise OIDCTokenError("bad_signature", "token mismatch")
        return self.claims


class _Claims:
    def __init__(self, sub, tenant=""):
        self.sub = sub
        self.tenant = tenant


def _build_app(*, verifier=None, sessions=None, counter=None):
    app = FastAPI()
    app.add_middleware(
        OIDCAuthMiddleware,
        verifier=verifier,
        session_store=sessions,
        counter=counter,
    )

    @app.get("/api/v1/internal/echo")
    def internal_echo(request: Request):  # type: ignore[no-untyped-def]
        return {
            "actor_user_sub": getattr(request.state, "actor_user_sub", None),
            "actor_kind": getattr(request.state, "actor_kind", None),
            "actor_tenant": getattr(request.state, "actor_tenant", None),
        }

    @app.get("/api/some/protected")
    def protected(request: Request):  # type: ignore[no-untyped-def]
        return {
            "actor_user_sub": getattr(request.state, "actor_user_sub", None),
            "actor_kind": getattr(request.state, "actor_kind", None),
        }

    @app.get("/api/auth/login")
    def login():
        return {"public": True}

    @app.get("/api/health")
    def health():
        return {"ok": True}

    return app


@pytest.fixture(autouse=True)
def _reset_state(monkeypatch):
    """Reset the module-global counter / session store + clear env between tests."""
    api_key_deprecation_counter.reset()
    # session_store is in-memory so just clear it.
    default_session_store._sessions.clear()  # type: ignore[attr-defined]
    for var in (
        "MURPHY_OIDC_ISSUER", "MURPHY_OIDC_CLIENT_ID",
        "MURPHY_OIDC_TENANT_CLAIM",
        "MURPHY_API_KEY", "MURPHY_API_KEYS",
        "MURPHY_ALLOW_API_KEY", "MURPHY_API_KEY_ROUTES",
        "MURPHY_AUTH_ENFORCED",
    ):
        monkeypatch.delenv(var, raising=False)


_LONG_JWT = "aaaaaaaaaa.bbbbbbbbbb.cccccccccc"  # 32 chars, 3 segments


# ── Path 1: Bearer JWT ─────────────────────────────────────────────────────


class TestBearerPath:
    def test_valid_jwt_attributes_actor(self):
        v = _StubVerifier(ok_token=_LONG_JWT, claims=_Claims("user-1", "acme"))
        app = _build_app(verifier=v)
        with TestClient(app) as c:
            r = c.get(
                "/api/some/protected",
                headers={"Authorization": f"Bearer {_LONG_JWT}"},
            )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["actor_user_sub"] == "user-1"
        assert body["actor_kind"] == "oidc"

    def test_invalid_jwt_returns_401_not_503(self):
        from oidc_verifier import OIDCTokenError
        v = _StubVerifier(
            ok_token="x", claims=_Claims("u"),
            raises=OIDCTokenError("expired", "expired"),
        )
        app = _build_app(verifier=v)
        with TestClient(app) as c:
            r = c.get(
                "/api/some/protected",
                headers={"Authorization": f"Bearer {_LONG_JWT}"},
            )
        assert r.status_code == 401
        assert r.json()["code"] == "OIDC_TOKEN_INVALID"
        assert r.json()["reason"] == "expired"

    def test_discovery_error_returns_503_no_silent_fallback(self, monkeypatch):
        """Per ADR: JWKS-refresh failure is 503, not silent API-key fallback."""
        from oidc_verifier import OIDCDiscoveryError
        v = _StubVerifier(
            ok_token="x", claims=_Claims("u"),
            raises=OIDCDiscoveryError("upstream down"),
        )
        # Configure an API-key fallback that WOULD pass — the discovery
        # error must still beat it to a 503 response.
        monkeypatch.setenv("MURPHY_API_KEY", "secret")
        monkeypatch.setenv("MURPHY_ALLOW_API_KEY", "true")
        app = _build_app(verifier=v)
        with TestClient(app) as c:
            r = c.get(
                "/api/v1/internal/echo",
                headers={
                    "Authorization": f"Bearer {_LONG_JWT}",
                    "X-API-Key": "secret",
                },
            )
        assert r.status_code == 503
        assert r.json()["code"] == "OIDC_DISCOVERY_FAILED"


# ── Path 2: Session cookie ─────────────────────────────────────────────────


class TestSessionPath:
    def test_valid_session_cookie_attributes_actor(self):
        default_session_store.put("sid-123", {"sub": "user-9", "tenant": "ten-2"})
        app = _build_app()
        with TestClient(app) as c:
            r = c.get(
                "/api/some/protected",
                cookies={"murphy_sid": "sid-123"},
            )
        assert r.status_code == 200
        body = r.json()
        assert body["actor_user_sub"] == "user-9"
        assert body["actor_kind"] == "session"


# ── Path 3: API-key fallback ───────────────────────────────────────────────


class TestApiKeyFallback:
    def test_accepted_on_allowlisted_route_and_counter_increments(self, monkeypatch):
        monkeypatch.setenv("MURPHY_API_KEY", "secret")
        monkeypatch.setenv("MURPHY_ALLOW_API_KEY", "true")
        app = _build_app()
        with TestClient(app) as c:
            r = c.get(
                "/api/v1/internal/echo",
                headers={"X-API-Key": "secret"},
            )
        assert r.status_code == 200
        assert r.json()["actor_kind"] == "api_key"
        # ADR: "murphy_api_key_requests_total{route=...}" increments.
        snap = api_key_deprecation_counter.snapshot()
        assert snap.get("/api/v1/internal/echo", 0) == 1

    def test_rejected_on_non_allowlisted_route(self, monkeypatch):
        monkeypatch.setenv("MURPHY_API_KEY", "secret")
        monkeypatch.setenv("MURPHY_ALLOW_API_KEY", "true")
        app = _build_app()
        with TestClient(app) as c:
            r = c.get(
                "/api/some/protected",
                headers={"X-API-Key": "secret"},
            )
        assert r.status_code == 401
        assert r.json()["code"] == "API_KEY_ROUTE_DENIED"

    def test_release_n1_preview_disables_api_key_path(self, monkeypatch):
        """When MURPHY_ALLOW_API_KEY=false, the legacy header is rejected
        even on the allowlisted route — Release N+1 default."""
        monkeypatch.setenv("MURPHY_API_KEY", "secret")
        monkeypatch.setenv("MURPHY_ALLOW_API_KEY", "false")
        app = _build_app()
        with TestClient(app) as c:
            r = c.get(
                "/api/v1/internal/echo",
                headers={"X-API-Key": "secret"},
            )
        assert r.status_code == 401
        assert r.json()["code"] == "API_KEY_DEPRECATED"

    def test_wrong_api_key_rejected_constant_time(self, monkeypatch):
        monkeypatch.setenv("MURPHY_API_KEY", "secret")
        monkeypatch.setenv("MURPHY_ALLOW_API_KEY", "true")
        app = _build_app()
        with TestClient(app) as c:
            r = c.get(
                "/api/v1/internal/echo",
                headers={"X-API-Key": "wrong"},
            )
        assert r.status_code == 401
        assert r.json()["code"] == "AUTH_REQUIRED"

    def test_custom_allowlist_via_env(self, monkeypatch):
        monkeypatch.setenv("MURPHY_API_KEY", "secret")
        monkeypatch.setenv("MURPHY_ALLOW_API_KEY", "true")
        monkeypatch.setenv("MURPHY_API_KEY_ROUTES", "/api/some/*")
        app = _build_app()
        with TestClient(app) as c:
            r = c.get(
                "/api/some/protected",
                headers={"X-API-Key": "secret"},
            )
        assert r.status_code == 200
        assert r.json()["actor_kind"] == "api_key"


# ── Public exemptions & permissive defaults ────────────────────────────────


class TestExemptions:
    def test_auth_endpoints_always_public(self):
        app = _build_app()
        with TestClient(app) as c:
            assert c.get("/api/auth/login").status_code == 200
            assert c.get("/api/health").status_code == 200

    def test_permissive_when_no_credentials_configured(self):
        # No MURPHY_API_KEY, no MURPHY_OIDC_*, no MURPHY_AUTH_ENFORCED.
        # The middleware must remain permissive (matches the legacy
        # inline middleware's "auth disabled when no key set" behaviour).
        app = _build_app()
        with TestClient(app) as c:
            r = c.get("/api/some/protected")
        assert r.status_code == 200
        assert r.json()["actor_kind"] == "anonymous"

    def test_back_compat_setting_api_key_implicitly_enforces_auth(self, monkeypatch):
        """Pre-Release-N behaviour: setting MURPHY_API_KEY makes /api/*
        require credentials.  Must be preserved so upgrades don't open
        a deployment up."""
        monkeypatch.setenv("MURPHY_API_KEY", "secret")
        # MURPHY_ALLOW_API_KEY defaults to 'true' so the key path is
        # available, but on a non-allowlisted route the key is denied.
        # No bearer + no session ⇒ 401.
        app = _build_app()
        with TestClient(app) as c:
            r = c.get("/api/some/protected")
        assert r.status_code == 401
        assert r.json()["code"] == "AUTH_REQUIRED"
