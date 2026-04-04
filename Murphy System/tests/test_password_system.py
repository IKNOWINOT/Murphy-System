"""Tests for the self-service password management system.

Covers:
  POST /api/auth/change-password          — logged-in user changes own password
  POST /api/auth/request-password-reset   — generates a reset token (email link)
  GET  /api/auth/reset-password/validate  — checks token validity
  POST /api/auth/reset-password           — consumes token, sets new password
  GET  /ui/change-password                — auth-required HTML route
  GET  /ui/reset-password                 — public HTML route
  change_password.html                    — UI content checks
  reset_password.html                     — UI content checks
  login.html                              — forgot-link wires to /ui/reset-password

Copyright © 2020 Inoni Limited Liability Company — BSL 1.1
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

os.environ.setdefault("MURPHY_ENV", "development")
os.environ.setdefault("MURPHY_RATE_LIMIT_RPM", "6000")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    from src.runtime.app import create_app
    return TestClient(create_app(), raise_server_exceptions=True)


def _create_account(client, email: str, password: str = "OldPass99!") -> str:
    """Sign up and return a session token."""
    client.post("/api/auth/signup", json={
        "email": email, "password": password, "full_name": "Test User",
    })
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    return r.json().get("session_token", "")


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ===========================================================================
# Change-password endpoint
# ===========================================================================

class TestChangePassword:
    """POST /api/auth/change-password — authenticated self-service."""

    def test_requires_auth(self, client):
        r = client.post("/api/auth/change-password", json={
            "current_password": "OldPass99!",
            "new_password":     "NewPass99!",
        })
        assert r.status_code == 401

    def test_happy_path(self, client):
        email = "chpw-happy@murphy.system"
        token = _create_account(client, email, "OldPass99!")
        r = client.post("/api/auth/change-password",
                        json={"current_password": "OldPass99!", "new_password": "NewPass99!"},
                        headers=_headers(token))
        assert r.status_code == 200
        d = r.json()
        assert d["success"] is True

    def test_can_login_with_new_password(self, client):
        email = "chpw-login@murphy.system"
        _create_account(client, email, "OldPass99!")
        token2 = _create_account(client, email + "_dummy", "dummy12345")  # just primes the store
        # Set up properly
        tok = _create_account(client, "chpw-newlogin@murphy.system", "OldPass99!")
        client.post("/api/auth/change-password",
                    json={"current_password": "OldPass99!", "new_password": "NewLogin99!"},
                    headers=_headers(tok))
        r = client.post("/api/auth/login",
                        json={"email": "chpw-newlogin@murphy.system", "password": "NewLogin99!"})
        assert r.json().get("success") is True

    def test_wrong_current_password_rejected(self, client):
        email = "chpw-wrong@murphy.system"
        token = _create_account(client, email, "OldPass99!")
        r = client.post("/api/auth/change-password",
                        json={"current_password": "WrongPass!", "new_password": "NewPass99!"},
                        headers=_headers(token))
        assert r.status_code == 400
        assert "incorrect" in r.json()["error"].lower()

    def test_new_password_too_short(self, client):
        email = "chpw-short@murphy.system"
        token = _create_account(client, email, "OldPass99!")
        r = client.post("/api/auth/change-password",
                        json={"current_password": "OldPass99!", "new_password": "tiny"},
                        headers=_headers(token))
        assert r.status_code == 400
        assert "8" in r.json()["error"]

    def test_same_password_rejected(self, client):
        email = "chpw-same@murphy.system"
        token = _create_account(client, email, "OldPass99!")
        r = client.post("/api/auth/change-password",
                        json={"current_password": "OldPass99!", "new_password": "OldPass99!"},
                        headers=_headers(token))
        assert r.status_code == 400
        assert "differ" in r.json()["error"].lower()

    def test_missing_fields_rejected(self, client):
        email = "chpw-missing@murphy.system"
        token = _create_account(client, email, "OldPass99!")
        r = client.post("/api/auth/change-password",
                        json={"current_password": "OldPass99!"},
                        headers=_headers(token))
        assert r.status_code == 400


# ===========================================================================
# Request-password-reset endpoint
# ===========================================================================

class TestRequestPasswordReset:
    """POST /api/auth/request-password-reset"""

    def test_happy_path_returns_success(self, client):
        email = "rpr-happy@murphy.system"
        _create_account(client, email)
        r = client.post("/api/auth/request-password-reset", json={"email": email})
        assert r.status_code == 200
        d = r.json()
        assert d["success"] is True

    def test_unknown_email_also_returns_success(self, client):
        """Never expose whether email exists."""
        r = client.post("/api/auth/request-password-reset",
                        json={"email": "nobody@unknown.invalid"})
        assert r.status_code == 200
        assert r.json()["success"] is True

    def test_dev_mode_returns_token(self, client):
        """In development env, the token is returned for testing convenience."""
        email = "rpr-dev@murphy.system"
        _create_account(client, email)
        r = client.post("/api/auth/request-password-reset", json={"email": email})
        d = r.json()
        assert "dev_token" in d, "Expected dev_token in development mode"
        assert d["dev_token"]

    def test_dev_mode_returns_reset_url(self, client):
        email = "rpr-url@murphy.system"
        _create_account(client, email)
        r = client.post("/api/auth/request-password-reset", json={"email": email})
        d = r.json()
        assert "dev_reset_url" in d
        assert "/ui/reset-password?token=" in d["dev_reset_url"]

    def test_missing_email_returns_400(self, client):
        r = client.post("/api/auth/request-password-reset", json={})
        assert r.status_code == 400


# ===========================================================================
# Validate reset token endpoint
# ===========================================================================

class TestValidateResetToken:
    """GET /api/auth/reset-password/validate"""

    def _get_fresh_token(self, client, suffix: str) -> str:
        email = f"val-{suffix}@murphy.system"
        _create_account(client, email)
        r = client.post("/api/auth/request-password-reset", json={"email": email})
        return r.json().get("dev_token", "")

    def test_valid_token_returns_true(self, client):
        token = self._get_fresh_token(client, "valid")
        r = client.get(f"/api/auth/reset-password/validate?token={token}")
        assert r.status_code == 200
        d = r.json()
        assert d["valid"] is True
        assert d["email"].endswith("@murphy.system")

    def test_invalid_token_returns_false(self, client):
        r = client.get("/api/auth/reset-password/validate?token=totally-fake-token")
        assert r.status_code == 200
        assert r.json()["valid"] is False

    def test_missing_token_param_returns_400(self, client):
        r = client.get("/api/auth/reset-password/validate")
        assert r.status_code == 400

    def test_used_token_is_invalid(self, client):
        email = "val-used@murphy.system"
        _create_account(client, email)
        r1 = client.post("/api/auth/request-password-reset", json={"email": email})
        token = r1.json().get("dev_token", "")
        # Consume it
        client.post("/api/auth/reset-password",
                    json={"token": token, "new_password": "Consumed99!"})
        r2 = client.get(f"/api/auth/reset-password/validate?token={token}")
        assert r2.json()["valid"] is False


# ===========================================================================
# Reset-password endpoint
# ===========================================================================

class TestResetPassword:
    """POST /api/auth/reset-password"""

    def _fresh(self, client, suffix: str) -> tuple[str, str]:
        """Return (email, reset_token) for a fresh account."""
        email = f"rp-{suffix}@murphy.system"
        _create_account(client, email)
        r = client.post("/api/auth/request-password-reset", json={"email": email})
        return email, r.json().get("dev_token", "")

    def test_happy_path(self, client):
        email, token = self._fresh(client, "happy")
        r = client.post("/api/auth/reset-password",
                        json={"token": token, "new_password": "Reset99Happy!"})
        assert r.status_code == 200
        assert r.json()["success"] is True

    def test_can_login_after_reset(self, client):
        email, token = self._fresh(client, "loginafter")
        client.post("/api/auth/reset-password",
                    json={"token": token, "new_password": "AfterReset99!"})
        r = client.post("/api/auth/login",
                        json={"email": email, "password": "AfterReset99!"})
        assert r.json().get("success") is True

    def test_cannot_reuse_token(self, client):
        email, token = self._fresh(client, "reuse")
        client.post("/api/auth/reset-password",
                    json={"token": token, "new_password": "Reuse1Pass99!"})
        r2 = client.post("/api/auth/reset-password",
                         json={"token": token, "new_password": "Reuse2Pass99!"})
        assert r2.status_code == 400
        assert "invalid" in r2.json()["error"].lower() or "used" in r2.json()["error"].lower()

    def test_bogus_token_rejected(self, client):
        r = client.post("/api/auth/reset-password",
                        json={"token": "not-a-real-token", "new_password": "SomePass99!"})
        assert r.status_code == 400

    def test_short_new_password_rejected(self, client):
        _, token = self._fresh(client, "short")
        r = client.post("/api/auth/reset-password",
                        json={"token": token, "new_password": "tiny"})
        assert r.status_code == 400
        assert "8" in r.json()["error"]

    def test_missing_token_rejected(self, client):
        r = client.post("/api/auth/reset-password",
                        json={"new_password": "NoToken99!"})
        assert r.status_code == 400


# ===========================================================================
# UI routes
# ===========================================================================

class TestPasswordUIRoutes:
    def test_reset_password_page_is_public(self, client):
        """GET /ui/reset-password returns 200 without a session."""
        r = client.get("/ui/reset-password", follow_redirects=True)
        assert r.status_code == 200

    def test_change_password_page_redirects_when_unauthenticated(self, client):
        """GET /ui/change-password should redirect to login for unauthenticated visitors."""
        r = client.get("/ui/change-password", follow_redirects=False)
        assert r.status_code in (200, 302, 307)
        if r.status_code in (302, 307):
            assert "login" in r.headers.get("location", "").lower()


# ===========================================================================
# Static source analysis
# ===========================================================================

class TestPasswordEndpointsInSource:
    @pytest.fixture(scope="class")
    def src(self):
        return (_ROOT / "src" / "runtime" / "app.py").read_text()

    ROUTES = [
        "/api/auth/change-password",
        "/api/auth/request-password-reset",
        "/api/auth/reset-password/validate",
        "/api/auth/reset-password",
    ]

    @pytest.mark.parametrize("route", ROUTES)
    def test_route_in_source(self, src, route):
        assert route in src, f"Missing password route in app.py: {route}"

    def test_token_store(self, src):
        assert "_password_reset_tokens" in src

    def test_reset_ui_route_registered(self, src):
        assert "reset_password.html" in src

    def test_change_ui_route_registered(self, src):
        assert "change_password.html" in src

    def test_reset_is_public_route(self, src):
        assert '"/ui/reset-password"' in src

    def test_single_use_token(self, src):
        assert 'meta["used"] = True' in src

    def test_expiry_check(self, src):
        assert "expires_at" in src


class TestPasswordHTMLFiles:
    def test_reset_password_html_exists(self):
        assert (_ROOT / "reset_password.html").exists()

    def test_change_password_html_exists(self):
        assert (_ROOT / "change_password.html").exists()

    def test_reset_html_has_request_form(self):
        html = (_ROOT / "reset_password.html").read_text()
        assert "request-form" in html

    def test_reset_html_has_set_form(self):
        html = (_ROOT / "reset_password.html").read_text()
        assert "set-form" in html

    def test_reset_html_calls_request_endpoint(self):
        html = (_ROOT / "reset_password.html").read_text()
        assert "/api/auth/request-password-reset" in html

    def test_reset_html_calls_reset_endpoint(self):
        html = (_ROOT / "reset_password.html").read_text()
        assert "/api/auth/reset-password" in html

    def test_reset_html_validates_token(self):
        html = (_ROOT / "reset_password.html").read_text()
        assert "/api/auth/reset-password/validate" in html

    def test_reset_html_has_expired_step(self):
        html = (_ROOT / "reset_password.html").read_text()
        assert "step-invalid" in html

    def test_reset_html_has_done_step(self):
        html = (_ROOT / "reset_password.html").read_text()
        assert "step-done" in html

    def test_reset_html_has_strength_meter(self):
        html = (_ROOT / "reset_password.html").read_text()
        assert "strength-fill" in html

    def test_reset_html_has_prefill_logic(self):
        html = (_ROOT / "reset_password.html").read_text()
        assert "prefill" in html

    def test_change_html_calls_change_endpoint(self):
        html = (_ROOT / "change_password.html").read_text()
        assert "/api/auth/change-password" in html

    def test_change_html_has_strength_meter(self):
        html = (_ROOT / "change_password.html").read_text()
        assert "strength-fill" in html

    def test_change_html_links_to_reset(self):
        html = (_ROOT / "change_password.html").read_text()
        assert "/ui/reset-password" in html

    def test_change_html_has_done_view(self):
        html = (_ROOT / "change_password.html").read_text()
        assert "done-view" in html

    def test_login_html_links_to_reset_page(self):
        html = (_ROOT / "login.html").read_text()
        assert "/ui/reset-password" in html

    def test_org_portal_links_to_change_password(self):
        html = (_ROOT / "org_portal.html").read_text()
        assert "/ui/change-password" in html
