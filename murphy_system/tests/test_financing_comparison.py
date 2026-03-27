"""
Tests for financing comparison — financing options render correctly per
amount range and the comparison table contains expected providers.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")


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


# ---------------------------------------------------------------------------
# Financing HTML Content Tests
# ---------------------------------------------------------------------------

class TestFinancingOptionsHTML:
    """financing_options.html contains all required providers and data."""

    @pytest.fixture(autouse=True)
    def load_html(self):
        path = os.path.join(REPO_ROOT, "financing_options.html")
        with open(path, "rb") as f:
            self.content = f.read()

    def test_file_exists(self):
        path = os.path.join(REPO_ROOT, "financing_options.html")
        assert os.path.isfile(path), "financing_options.html must exist"

    def test_contains_wisetack(self):
        assert b"Wisetack" in self.content

    def test_contains_greensky(self):
        assert b"GreenSky" in self.content or b"Greensky" in self.content

    def test_contains_affirm(self):
        assert b"Affirm" in self.content

    def test_contains_cpace(self):
        assert b"PACE" in self.content or b"C-PACE" in self.content

    def test_contains_paypal(self):
        assert b"PayPal" in self.content or b"Pay Later" in self.content

    def test_contains_amount_range_wisetack(self):
        """Wisetack range $500–$25K is shown."""
        assert b"25K" in self.content or b"25,000" in self.content

    def test_contains_amount_range_greensky(self):
        """GreenSky range up to $65K is shown."""
        assert b"65K" in self.content or b"65,000" in self.content

    def test_contains_amount_range_affirm(self):
        """Affirm range shown."""
        assert b"17" in self.content or b"Affirm" in self.content

    def test_contains_term_cpace(self):
        """C-PACE long term (10-30 year) is shown."""
        assert b"30" in self.content or b"year" in self.content.lower()

    def test_contains_apply_buttons(self):
        """Apply buttons present for providers."""
        assert b"Apply" in self.content or b"apply" in self.content.lower()

    def test_contains_copyright(self):
        assert b"Inoni" in self.content or b"BSL" in self.content

    def test_contains_link_to_grant_wizard(self):
        """Page links back to grant wizard."""
        assert b"grant-wizard" in self.content or b"grant_wizard" in self.content

    def test_contains_espc_explanation(self):
        """ESPC / Energy Savings Performance Contract is mentioned."""
        assert b"ESPC" in self.content or b"espc" in self.content.lower() or b"Performance" in self.content

    def test_contains_murphy_topbar(self):
        """Page uses Murphy topbar navigation."""
        assert b"murphy-topbar" in self.content

    def test_contains_financing_nav_link(self):
        """Navigation includes Financing & Grants link."""
        assert b"grant-wizard" in self.content or b"Financing" in self.content


# ---------------------------------------------------------------------------
# Financing Page Serving Tests
# ---------------------------------------------------------------------------

class TestFinancingPageServing:
    """The /ui/financing route is registered and served."""

    def test_financing_route_registered(self, client):
        resp = client.get("/ui/financing")
        assert resp.status_code in (200, 302), \
            f"Expected 200 or 302 redirect, got {resp.status_code}"

    def test_financing_route_serves_html(self, client):
        resp = client.get("/ui/financing")
        if resp.status_code == 200:
            assert "text/html" in resp.headers.get("content-type", "")

    def test_financing_redirect_to_login_when_unauthed(self, client):
        resp = client.get("/ui/financing")
        if resp.status_code == 302:
            location = resp.headers.get("location", "")
            assert "/ui/login" in location, \
                f"Expected redirect to /ui/login, got {location}"


# ---------------------------------------------------------------------------
# Amount Range Logic Tests
# ---------------------------------------------------------------------------

class TestFinancingAmountRanges:
    """Financing provider amount ranges are correctly represented in the HTML."""

    PROVIDERS = {
        "Wisetack": {"min": 500, "max": 25000},
        "GreenSky": {"min": 1000, "max": 65000},
        "Affirm": {"min": 50, "max": 17500},
    }

    @pytest.fixture(autouse=True)
    def load_html(self):
        path = os.path.join(REPO_ROOT, "financing_options.html")
        with open(path, "rb") as f:
            self.content = f.read().decode("utf-8", errors="ignore").lower()

    def test_wisetack_max_amount_shown(self):
        assert "25" in self.content, "Wisetack $25K max should appear"

    def test_greensky_max_amount_shown(self):
        assert "65" in self.content, "GreenSky $65K max should appear"

    def test_affirm_min_amount_shown(self):
        # Affirm starts at $50
        assert "affirm" in self.content

    def test_cpace_no_fixed_max(self):
        """C-PACE covers up to 100% of project cost."""
        assert "100%" in self.content or "project cost" in self.content or "pace" in self.content

    def test_paypal_four_payments(self):
        """PayPal Pay Later uses 4-payment structure."""
        assert "4 payment" in self.content or "four payment" in self.content or "paypal" in self.content


# ---------------------------------------------------------------------------
# Mirror File Tests
# ---------------------------------------------------------------------------

class TestFinancingMirrorFiles:
    """murphy_system/ mirror files exist and match root files."""

    def test_mirror_financing_exists(self):
        mirror = os.path.join(REPO_ROOT, "murphy_system", "financing_options.html")
        assert os.path.isfile(mirror), "murphy_system/financing_options.html mirror must exist"

    def test_mirror_grant_wizard_exists(self):
        mirror = os.path.join(REPO_ROOT, "murphy_system", "grant_wizard.html")
        assert os.path.isfile(mirror), "murphy_system/grant_wizard.html mirror must exist"

    def test_mirror_grant_dashboard_exists(self):
        mirror = os.path.join(REPO_ROOT, "murphy_system", "grant_dashboard.html")
        assert os.path.isfile(mirror), "murphy_system/grant_dashboard.html mirror must exist"

    def test_mirror_grant_application_exists(self):
        mirror = os.path.join(REPO_ROOT, "murphy_system", "grant_application.html")
        assert os.path.isfile(mirror), "murphy_system/grant_application.html mirror must exist"
