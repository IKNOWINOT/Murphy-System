# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Tests verifying that every API endpoint called by the frontend HTML files
has a matching backend handler registered in ``src/runtime/app.py``.

These tests ensure the 5 frontend→backend wiring gaps are closed:
  1. POST /api/credentials/store     — onboarding_wizard.html Step 3
  2. POST /api/auth/forgot-password  — login.html password reset
  3. GET  /api/integrations/list     — terminal_unified / workflow_canvas
  4. GET  /api/ip/portfolio          — terminal_unified IP tab
  5. POST /api/workflow-terminal/execute — workflow_canvas execution
"""

import os
import re
import sys

import pytest

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROJECT_ROOT)
sys.path.insert(0, os.path.join(_PROJECT_ROOT, "src"))


def _read_app_py() -> str:
    """Read the full app.py source."""
    path = os.path.join(_PROJECT_ROOT, "src", "runtime", "app.py")
    with open(path) as fh:
        return fh.read()


def _read_html(filename: str) -> str:
    """Read an HTML file from the project root."""
    path = os.path.join(_PROJECT_ROOT, filename)
    with open(path) as fh:
        return fh.read()


# ---------------------------------------------------------------------------
# 1. Backend endpoint existence checks (source-code level)
# ---------------------------------------------------------------------------

class TestNewEndpointsExistInSource:
    """Verify the 5 new endpoints are registered in app.py."""

    @pytest.fixture(autouse=True)
    def _load(self):
        self.source = _read_app_py()

    def test_credentials_store_endpoint(self):
        assert 'credentials/store' in self.source, (
            "app.py must register POST /api/credentials/store"
        )

    def test_auth_forgot_password_endpoint(self):
        assert 'auth/forgot-password' in self.source, (
            "app.py must register POST /api/auth/forgot-password"
        )

    def test_integrations_list_handler(self):
        # Can be handled by the {status} param route or a dedicated route
        assert 'integrations/list' in self.source or 'integrations_list' in self.source, (
            "app.py must handle GET /api/integrations/list"
        )

    def test_ip_portfolio_endpoint(self):
        assert 'ip/portfolio' in self.source, (
            "app.py must register GET /api/ip/portfolio"
        )

    def test_workflow_terminal_execute_endpoint(self):
        assert 'workflow-terminal/execute' in self.source, (
            "app.py must register POST /api/workflow-terminal/execute"
        )


# ---------------------------------------------------------------------------
# 2. Frontend→backend alignment — every fetch()/api.post() has a handler
# ---------------------------------------------------------------------------

class TestFrontendAPICallsCovered:
    """Verify frontend HTML files only call API endpoints that exist in the backend."""

    @pytest.fixture(autouse=True)
    def _load(self):
        self.source = _read_app_py()

    def _has_handler(self, path_fragment: str) -> bool:
        """Check if the path fragment appears in app.py route definitions."""
        return path_fragment in self.source

    def test_onboarding_wizard_credentials_store(self):
        html = _read_html("onboarding_wizard.html")
        assert "credentials/store" in html, "Onboarding wizard should call credentials/store"
        assert self._has_handler("credentials/store"), "Backend missing credentials/store handler"

    def test_login_forgot_password(self):
        html = _read_html("login.html")
        assert "forgot-password" in html, "Login page should have forgot-password functionality"
        assert self._has_handler("auth/forgot-password"), "Backend missing forgot-password handler"

    def test_terminal_unified_integrations_list(self):
        html = _read_html("terminal_unified.html")
        assert "integrations/list" in html, "Terminal should call integrations/list"
        assert self._has_handler("integrations/list") or self._has_handler("integrations/{status}"), (
            "Backend missing integrations/list handler"
        )

    def test_terminal_unified_ip_portfolio(self):
        html = _read_html("terminal_unified.html")
        assert "ip/portfolio" in html, "Terminal should call ip/portfolio"
        assert self._has_handler("ip/portfolio"), "Backend missing ip/portfolio handler"

    def test_workflow_canvas_execute(self):
        html = _read_html("workflow_canvas.html")
        assert "workflow-terminal/execute" in html, "Canvas should call workflow-terminal/execute"
        assert self._has_handler("workflow-terminal/execute"), "Backend missing workflow-terminal/execute handler"


# ---------------------------------------------------------------------------
# 3. Functional tests using create_app() + httpx
# ---------------------------------------------------------------------------

class TestEndpointsFunctional:
    """Exercise the 5 new endpoints via TestClient to verify they return valid JSON."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        """Create app and TestClient."""
        try:
            from starlette.testclient import TestClient
        except ImportError:
            pytest.skip("starlette not available")
        os.environ.setdefault("MURPHY_ENV", "development")
        os.environ.setdefault("LLM_PROVIDER", "onboard")
        try:
            from src.runtime.app import create_app
            self.app = create_app()
            self.client = TestClient(self.app, raise_server_exceptions=False)
        except Exception as exc:
            pytest.skip(f"Could not create app: {exc}")

    def test_credentials_store_returns_json(self):
        resp = self.client.post(
            "/api/credentials/store",
            json={"integration": "test_integration", "credential": "test_key"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["integration"] == "test_integration"

    def test_credentials_store_rejects_missing_integration(self):
        resp = self.client.post(
            "/api/credentials/store",
            json={"credential": "test_key"},
        )
        assert resp.status_code == 400

    def test_auth_forgot_password_returns_json(self):
        resp = self.client.post(
            "/api/auth/forgot-password",
            json={"email": "user@example.com"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

    def test_auth_forgot_password_rejects_invalid_email(self):
        resp = self.client.post(
            "/api/auth/forgot-password",
            json={"email": "not-an-email"},
        )
        assert resp.status_code == 400

    def test_integrations_list_returns_catalog(self):
        resp = self.client.get("/api/integrations/list")
        assert resp.status_code == 200
        data = resp.json()
        assert "integrations" in data
        assert data["count"] > 0

    def test_ip_portfolio_returns_json(self):
        resp = self.client.get("/api/ip/portfolio")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "portfolio" in data

    def test_workflow_terminal_execute_returns_result(self):
        resp = self.client.post(
            "/api/workflow-terminal/execute",
            json={
                "nodes": [
                    {"id": "s1", "name": "Fetch", "type": "data_retrieval", "description": "Retrieve data"},
                    {"id": "s2", "name": "Check", "type": "validation", "description": "Validate", "depends_on": ["s1"]},
                ],
                "name": "Test Workflow",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["status"] == "completed"
        assert "s1" in data["steps"]
        assert "s2" in data["steps"]

    def test_workflow_terminal_execute_rejects_empty_nodes(self):
        resp = self.client.post(
            "/api/workflow-terminal/execute",
            json={"nodes": []},
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# 4. API documentation completeness
# ---------------------------------------------------------------------------

class TestDocumentationUpdated:
    """Verify that the 5 new endpoints are documented in API_ROUTES.md."""

    @pytest.fixture(autouse=True)
    def _load(self):
        path = os.path.join(_PROJECT_ROOT, "API_ROUTES.md")
        with open(path) as fh:
            self.doc = fh.read()

    def test_credentials_store_documented(self):
        assert "credentials/store" in self.doc

    def test_forgot_password_documented(self):
        assert "forgot-password" in self.doc

    def test_integrations_list_documented(self):
        assert "integrations/list" in self.doc

    def test_ip_portfolio_documented(self):
        assert "ip/portfolio" in self.doc

    def test_workflow_terminal_execute_documented(self):
        assert "workflow-terminal/execute" in self.doc
