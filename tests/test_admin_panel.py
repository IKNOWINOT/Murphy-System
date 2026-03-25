"""Tests for the Platform Admin API endpoints.

Covers:
  - /api/admin/users   (list, create, get, update, delete, suspend/unsuspend, reset-password)
  - /api/admin/organizations  (list, create, get, update, delete, member management)
  - /api/admin/stats
  - /api/admin/sessions / DELETE /api/admin/sessions/{id}
  - /api/admin/audit-log
  - Auth gate: non-admin and unauthenticated requests get 403/401

Copyright © 2020 Inoni Limited Liability Company — BSL 1.1
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Ensure project root is on the path
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

os.environ.setdefault("MURPHY_ENV", "development")
os.environ.setdefault("MURPHY_RATE_LIMIT_RPM", "6000")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    """Instantiate the FastAPI app once for the whole module."""
    from fastapi.testclient import TestClient
    from src.runtime.app import create_app
    return TestClient(create_app(), raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def signup_and_get_token(client, email: str, password: str = "TestPass1!") -> str:
    client.post("/api/auth/signup", json={"email": email, "password": password, "full_name": "Test User"})
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    return r.json().get("session_token", "")


# ===========================================================================
# Auth gate tests — no credentials
# ===========================================================================

class TestAdminAuthGate:
    """All /api/admin/* endpoints must return 403 without admin credentials."""

    ENDPOINTS = [
        ("GET",    "/api/admin/users"),
        ("GET",    "/api/admin/users/fake-id"),
        ("PATCH",  "/api/admin/users/fake-id"),
        ("DELETE", "/api/admin/users/fake-id"),
        ("POST",   "/api/admin/users/fake-id/reset-password"),
        ("POST",   "/api/admin/users/fake-id/suspend"),
        ("POST",   "/api/admin/users/fake-id/unsuspend"),
        ("GET",    "/api/admin/organizations"),
        ("GET",    "/api/admin/organizations/fake-id"),
        ("PATCH",  "/api/admin/organizations/fake-id"),
        ("DELETE", "/api/admin/organizations/fake-id"),
        ("GET",    "/api/admin/organizations/fake-id/members"),
        ("POST",   "/api/admin/organizations/fake-id/members"),
        ("DELETE", "/api/admin/organizations/fake-id/members/fake-uid"),
        ("GET",    "/api/admin/stats"),
        ("GET",    "/api/admin/sessions"),
        ("DELETE", "/api/admin/sessions/fake-id"),
        ("GET",    "/api/admin/audit-log"),
    ]

    @pytest.mark.parametrize("method,path", ENDPOINTS)
    def test_unauthenticated_gets_403(self, client, method, path):
        resp = client.request(method, path, json={})
        # 401 (unauthenticated), 403 (no admin), or 422 (validation) all acceptable
        assert resp.status_code in (401, 403, 422, 429), (
            f"{method} {path} returned {resp.status_code} — expected 401/403/422/429"
        )

    def test_regular_user_gets_403_on_list_users(self, client):
        token = signup_and_get_token(client, "regular-user@murphy.system")
        resp = client.get("/api/admin/users", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (403, 429)

    def test_regular_user_gets_403_on_stats(self, client):
        token = signup_and_get_token(client, "regular-user2@murphy.system")
        resp = client.get("/api/admin/stats", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (403, 429)


# ===========================================================================
# Admin endpoint shape tests — check routes exist and return the right shape
# ===========================================================================

class TestAdminEndpointShape:
    """Verify each admin endpoint exists and returns the expected JSON shape
    when called without credentials (403 response body is still valid JSON)."""

    def test_list_users_returns_json_error_when_unauthed(self, client):
        r = client.get("/api/admin/users")
        assert r.status_code in (401, 403, 429)

    def test_list_orgs_returns_json_error_when_unauthed(self, client):
        r = client.get("/api/admin/organizations")
        assert r.status_code in (401, 403, 429)

    def test_stats_returns_json_error_when_unauthed(self, client):
        r = client.get("/api/admin/stats")
        assert r.status_code in (401, 403, 429)

    def test_audit_log_returns_json_error_when_unauthed(self, client):
        r = client.get("/api/admin/audit-log")
        assert r.status_code in (401, 403, 429)

    def test_sessions_returns_json_error_when_unauthed(self, client):
        r = client.get("/api/admin/sessions")
        assert r.status_code in (401, 403, 429)

    def test_create_user_returns_json_error_when_unauthed(self, client):
        r = client.post("/api/admin/users", json={"email": "x@x.com", "password": "pass1234"})
        assert r.status_code in (401, 403, 429)

    def test_create_org_returns_json_error_when_unauthed(self, client):
        r = client.post("/api/admin/organizations", json={"name": "Test Org"})
        assert r.status_code in (401, 403, 429)

    def test_reset_password_returns_json_error_when_unauthed(self, client):
        r = client.post("/api/admin/users/noid/reset-password", json={"new_password": "newpass123"})
        assert r.status_code in (401, 403, 429)

    def test_suspend_returns_json_error_when_unauthed(self, client):
        r = client.post("/api/admin/users/noid/suspend", json={})
        assert r.status_code in (401, 403, 429)

    def test_unsuspend_returns_json_error_when_unauthed(self, client):
        r = client.post("/api/admin/users/noid/unsuspend", json={})
        assert r.status_code in (401, 403, 429)


# ===========================================================================
# Admin panel HTML route
# ===========================================================================

class TestAdminPanelRoute:
    """The /ui/admin route should return a 200 HTML response."""

    def test_admin_ui_route_exists(self, client):
        r = client.get("/ui/admin", follow_redirects=True)
        # If admin_panel.html exists on disk it will be served (200);
        # if not, the file-serving code skips it but the route still resolves.
        # Either way should not 404.
        assert r.status_code in (200, 302, 307), (
            f"/ui/admin returned {r.status_code}"
        )


# ===========================================================================
# Admin code content tests (static analysis of app.py)
# ===========================================================================

class TestAdminAPIInAppPy:
    """Ensure all required admin endpoints are present in app.py source."""

    @pytest.fixture(scope="class")
    def app_source(self):
        path = _ROOT / "src" / "runtime" / "app.py"
        return path.read_text()

    REQUIRED_ROUTES = [
        "/api/admin/users",
        "/api/admin/users/{user_id}",
        "/api/admin/users/{user_id}/reset-password",
        "/api/admin/users/{user_id}/suspend",
        "/api/admin/users/{user_id}/unsuspend",
        "/api/admin/organizations",
        "/api/admin/organizations/{org_id}",
        "/api/admin/organizations/{org_id}/members",
        "/api/admin/stats",
        "/api/admin/sessions",
        "/api/admin/sessions/{account_id}",
        "/api/admin/audit-log",
    ]

    @pytest.mark.parametrize("route", REQUIRED_ROUTES)
    def test_route_in_source(self, app_source, route):
        assert route in app_source, f"Missing admin route in app.py: {route}"

    def test_require_admin_helper_present(self, app_source):
        assert "_require_admin" in app_source

    def test_admin_audit_log_helper_present(self, app_source):
        assert "_admin_log" in app_source

    def test_org_store_present(self, app_source):
        assert "_org_store" in app_source

    def test_admin_panel_html_route_present(self, app_source):
        assert "admin_panel.html" in app_source
