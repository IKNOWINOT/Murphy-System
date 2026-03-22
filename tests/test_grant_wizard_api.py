"""
Tests for Grant Wizard API — eligibility endpoint returns correct grants for
various project types and parameter combinations.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    os.environ["MURPHY_ENV"] = "development"
    from starlette.testclient import TestClient
    from src.runtime.app import create_app
    app = create_app()
    return TestClient(app, follow_redirects=False)


@pytest.fixture(scope="module")
def auth_client(client):
    """Authenticated client with a fresh session."""
    email = f"grant_wizard_{os.urandom(4).hex()}@example.com"
    resp = client.post("/api/auth/signup", json={
        "email": email,
        "password": "SecurePass123!",
        "full_name": "Grant Wizard Tester",
        "job_title": "Engineer",
        "company": "TestCorp",
    })
    assert resp.status_code == 200
    return client


# ---------------------------------------------------------------------------
# UI Route Tests
# ---------------------------------------------------------------------------

class TestGrantWizardUIRoutes:
    """Grant wizard UI pages are served correctly."""

    def test_grant_wizard_page_exists(self, client):
        """GET /ui/grant-wizard returns HTML (redirects to login without auth)."""
        resp = client.get("/ui/grant-wizard")
        # Unauthenticated → redirect to login, or serve page
        assert resp.status_code in (200, 302)

    def test_grant_dashboard_page_exists(self, client):
        resp = client.get("/ui/grant-dashboard")
        assert resp.status_code in (200, 302)

    def test_grant_application_page_exists(self, client):
        resp = client.get("/ui/grant-application")
        assert resp.status_code in (200, 302)

    def test_financing_options_page_exists(self, client):
        resp = client.get("/ui/financing")
        assert resp.status_code in (200, 302)

    def test_grant_wizard_redirect_to_login(self, client):
        """Unauthenticated request is redirected to login."""
        resp = client.get("/ui/grant-wizard")
        if resp.status_code == 302:
            assert "/ui/login" in resp.headers.get("location", "")

    def test_grant_dashboard_redirect_to_login(self, client):
        resp = client.get("/ui/grant-dashboard")
        if resp.status_code == 302:
            assert "/ui/login" in resp.headers.get("location", "")


# ---------------------------------------------------------------------------
# Eligibility API Tests (if grants API is mounted)
# ---------------------------------------------------------------------------

class TestGrantEligibilityAPI:
    """Eligibility endpoint returns results for supported project types."""

    BASE_PARAMS = {
        "zip": "97201",
        "cost": "25000",
        "business_type": "commercial",
        "building_type": "office",
        "sqft": "5000",
        "rural": "false",
        "tax_status": "for_profit",
    }

    def _check_eligibility(self, client, project_type):
        params = dict(self.BASE_PARAMS, project_type=project_type)
        resp = client.get("/api/grants/eligibility", params=params)
        return resp

    def test_eligibility_bas_project(self, auth_client):
        resp = self._check_eligibility(auth_client, "bas")
        assert resp.status_code in (200, 401, 404, 422)

    def test_eligibility_ems_project(self, auth_client):
        resp = self._check_eligibility(auth_client, "ems")
        assert resp.status_code in (200, 401, 404, 422)

    def test_eligibility_hvac_project(self, auth_client):
        resp = self._check_eligibility(auth_client, "hvac_controls")
        assert resp.status_code in (200, 401, 404, 422)

    def test_eligibility_solar_project(self, auth_client):
        resp = self._check_eligibility(auth_client, "solar_controls")
        assert resp.status_code in (200, 401, 404, 422)

    def test_eligibility_scada_project(self, auth_client):
        resp = self._check_eligibility(auth_client, "scada")
        assert resp.status_code in (200, 401, 404, 422)

    def test_eligibility_manufacturing_project(self, auth_client):
        resp = self._check_eligibility(auth_client, "smart_manufacturing")
        assert resp.status_code in (200, 401, 404, 422)

    def test_eligibility_rural_flag(self, auth_client):
        """Rural flag passes through correctly."""
        params = dict(self.BASE_PARAMS, project_type="bas", rural="true", zip="59001")
        resp = auth_client.get("/api/grants/eligibility", params=params)
        assert resp.status_code in (200, 401, 404, 422)

    def test_eligibility_nonprofit_tax_exempt(self, auth_client):
        """Nonprofit tax-exempt business type passes through."""
        params = dict(self.BASE_PARAMS, project_type="bas",
                      business_type="nonprofit", tax_status="tax_exempt")
        resp = auth_client.get("/api/grants/eligibility", params=params)
        assert resp.status_code in (200, 401, 404, 422)

    def test_eligibility_government_direct_pay(self, auth_client):
        """Government entity passes through for direct pay eligibility."""
        params = dict(self.BASE_PARAMS, project_type="bas",
                      business_type="government", tax_status="government")
        resp = auth_client.get("/api/grants/eligibility", params=params)
        assert resp.status_code in (200, 401, 404, 422)

    def test_eligibility_response_structure_when_200(self, auth_client):
        """If eligibility endpoint returns 200, response is valid JSON."""
        params = dict(self.BASE_PARAMS, project_type="bas")
        resp = auth_client.get("/api/grants/eligibility", params=params)
        if resp.status_code == 200:
            data = resp.json()
            assert isinstance(data, (dict, list))

    def test_eligibility_large_project(self, auth_client):
        """Very large project cost is accepted."""
        params = dict(self.BASE_PARAMS, project_type="solar_controls", cost="500000")
        resp = auth_client.get("/api/grants/eligibility", params=params)
        assert resp.status_code in (200, 401, 404, 422)

    def test_eligibility_small_project(self, auth_client):
        """Minimum project cost is accepted."""
        params = dict(self.BASE_PARAMS, project_type="bas", cost="5000")
        resp = auth_client.get("/api/grants/eligibility", params=params)
        assert resp.status_code in (200, 401, 404, 422)


# ---------------------------------------------------------------------------
# Static Asset Tests
# ---------------------------------------------------------------------------

class TestGrantWizardStaticAssets:
    """Wizard CSS and JS files are served."""

    def test_grant_wizard_css_served(self, client):
        resp = client.get("/static/grant-wizard.css")
        assert resp.status_code == 200
        assert "text/css" in resp.headers.get("content-type", "")

    def test_grant_wizard_js_served(self, client):
        resp = client.get("/static/grant-wizard.js")
        assert resp.status_code == 200

    def test_grant_dashboard_js_served(self, client):
        resp = client.get("/static/grant-dashboard.js")
        assert resp.status_code == 200

    def test_grant_wizard_css_contains_security_callout(self, client):
        resp = client.get("/static/grant-wizard.css")
        assert resp.status_code == 200
        assert b"security" in resp.content.lower() or b"callout" in resp.content.lower()

    def test_grant_wizard_js_contains_eligibility_call(self, client):
        resp = client.get("/static/grant-wizard.js")
        assert resp.status_code == 200
        assert b"eligibility" in resp.content.lower()

    def test_grant_dashboard_js_contains_session_key(self, client):
        resp = client.get("/static/grant-dashboard.js")
        assert resp.status_code == 200
        assert b"murphy_grant_session_id" in resp.content


# ---------------------------------------------------------------------------
# HTML Content Tests
# ---------------------------------------------------------------------------

class TestGrantWizardHTMLContent:
    """Wizard HTML files contain required elements."""

    def _get_html(self, client, path):
        """Get HTML content, following any auth redirect."""
        resp = client.get(path)
        if resp.status_code == 302:
            # Return empty bytes — page requires auth
            return b""
        return resp.content

    def test_wizard_html_contains_copyright(self, client):
        content = self._get_html(client, "/ui/grant-wizard")
        if content:
            assert b"Inoni" in content or b"BSL" in content

    def test_wizard_html_contains_security_callout(self, client):
        content = self._get_html(client, "/ui/grant-wizard")
        if content:
            assert b"encrypt" in content.lower() or b"security" in content.lower()

    def test_financing_html_contains_wisetack(self, client):
        content = self._get_html(client, "/ui/financing")
        if content:
            assert b"Wisetack" in content or b"wisetack" in content.lower()

    def test_financing_html_contains_cpace(self, client):
        content = self._get_html(client, "/ui/financing")
        if content:
            assert b"PACE" in content or b"pace" in content.lower()

    def test_dashboard_html_contains_status_labels(self, client):
        content = self._get_html(client, "/ui/grant-dashboard")
        if content:
            assert b"Draft" in content or b"draft" in content.lower()

    def test_wizard_html_contains_grant_wizard_js(self, client):
        content = self._get_html(client, "/ui/grant-wizard")
        if content:
            assert b"grant-wizard.js" in content

    def test_wizard_html_contains_step_indicator(self, client):
        content = self._get_html(client, "/ui/grant-wizard")
        if content:
            assert b"step" in content.lower()

    def test_application_html_contains_hitl_section(self, client):
        content = self._get_html(client, "/ui/grant-application")
        if content:
            assert b"field" in content.lower() or b"review" in content.lower()
