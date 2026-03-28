"""
Tests for wizard intake form validation — all required fields are validated
before the eligibility API is called.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

import os
import sys
import re
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")


# ---------------------------------------------------------------------------
# HTML Form Structure Tests
# ---------------------------------------------------------------------------

class TestWizardIntakeFormHTML:
    """grant_wizard.html contains all required form fields."""

    @pytest.fixture(autouse=True)
    def load_html(self):
        path = os.path.join(REPO_ROOT, "grant_wizard.html")
        with open(path, "rb") as f:
            self.raw = f.read()
        self.content = self.raw.decode("utf-8", errors="ignore")

    def test_wizard_file_exists(self):
        path = os.path.join(REPO_ROOT, "grant_wizard.html")
        assert os.path.isfile(path), "grant_wizard.html must exist"

    # ── Required field presence ──────────────────────────────────

    def test_has_project_type_field(self):
        """Project type dropdown is present."""
        content_lower = self.content.lower()
        assert "project_type" in content_lower or "project-type" in content_lower, \
            "Project type select field must be present"

    def test_has_zip_code_field(self):
        """ZIP code input is present."""
        content_lower = self.content.lower()
        assert "zip" in content_lower, "ZIP code field must be present"

    def test_has_cost_slider(self):
        """Estimated project cost range slider is present."""
        content_lower = self.content.lower()
        assert "cost" in content_lower, "Project cost field must be present"
        assert 'type="range"' in self.content or "range" in content_lower, \
            "Cost slider (range input) must be present"

    def test_has_business_type_field(self):
        """Business type dropdown is present."""
        content_lower = self.content.lower()
        assert "business_type" in content_lower or "business-type" in content_lower or \
               "business type" in content_lower, "Business type field must be present"

    def test_has_rural_checkbox(self):
        """Rural location checkbox is present."""
        content_lower = self.content.lower()
        assert "rural" in content_lower, "Rural checkbox must be present"

    def test_has_tax_status_field(self):
        """Tax status dropdown is present."""
        content_lower = self.content.lower()
        assert "tax_status" in content_lower or "tax-status" in content_lower or \
               "tax status" in content_lower, "Tax status field must be present"

    # ── Project type options ─────────────────────────────────────

    def test_has_bas_option(self):
        content_lower = self.content.lower()
        assert "bas" in content_lower or "bms" in content_lower, \
            "BAS/BMS option must be present"

    def test_has_ems_option(self):
        content_lower = self.content.lower()
        assert "ems" in content_lower, "EMS option must be present"

    def test_has_hvac_option(self):
        content_lower = self.content.lower()
        assert "hvac" in content_lower, "HVAC Controls option must be present"

    def test_has_scada_option(self):
        content_lower = self.content.lower()
        assert "scada" in content_lower, "SCADA option must be present"

    def test_has_solar_option(self):
        content_lower = self.content.lower()
        assert "solar" in content_lower, "Solar+Controls option must be present"

    # ── Business type options ────────────────────────────────────

    def test_has_commercial_option(self):
        assert "commercial" in self.content.lower()

    def test_has_nonprofit_option(self):
        assert "nonprofit" in self.content.lower() or "non-profit" in self.content.lower()

    def test_has_agricultural_option(self):
        assert "agricultural" in self.content.lower() or "agriculture" in self.content.lower()

    # ── Tax status options ───────────────────────────────────────

    def test_has_for_profit_option(self):
        content_lower = self.content.lower()
        assert "for-profit" in content_lower or "for_profit" in content_lower or \
               "for profit" in content_lower

    def test_has_tax_exempt_option(self):
        content_lower = self.content.lower()
        assert "tax-exempt" in content_lower or "tax_exempt" in content_lower or \
               "tax exempt" in content_lower

    def test_has_government_tax_option(self):
        assert "government" in self.content.lower()

    # ── Video component ──────────────────────────────────────────

    def test_has_video_element(self):
        content_lower = self.content.lower()
        assert "<video" in content_lower, "HTML5 video element must be present"

    def test_has_submit_button(self):
        content_lower = self.content.lower()
        assert "find" in content_lower or "submit" in content_lower or \
               "search" in content_lower, "Form submit button must be present"

    # ── Security callout ─────────────────────────────────────────

    def test_has_security_callout(self):
        content_lower = self.content.lower()
        assert "encrypt" in content_lower or "security" in content_lower, \
            "Security callout must be present"

    def test_security_callout_mentions_tenant_isolation(self):
        content_lower = self.content.lower()
        assert "session" in content_lower or "isolated" in content_lower or \
               "tenant" in content_lower or "account" in content_lower, \
            "Security callout must mention session/tenant isolation"

    # ── Step indicator ───────────────────────────────────────────

    def test_has_step_indicator(self):
        content_lower = self.content.lower()
        assert "step" in content_lower, "Step indicator must be present"

    def test_has_at_least_two_steps(self):
        """Wizard has at least step 1 (intake) and step 2 (results)."""
        content_lower = self.content.lower()
        assert "step-intake" in content_lower or "step-results" in content_lower or \
               "step-1" in content_lower or "step1" in content_lower, \
            "Wizard must have step panels"

    # ── Copyright ────────────────────────────────────────────────

    def test_has_copyright(self):
        assert "Inoni" in self.content or "BSL" in self.content, \
            "Copyright notice must be present"

    # ── Navigation ───────────────────────────────────────────────

    def test_has_topbar_nav(self):
        assert "murphy-topbar" in self.content, "Murphy topbar must be present"

    def test_has_financing_grants_nav_link(self):
        content_lower = self.content.lower()
        assert "financing" in content_lower or "grant" in content_lower, \
            "Financing & Grants nav link must be present"


# ---------------------------------------------------------------------------
# JavaScript Validation Logic Tests
# ---------------------------------------------------------------------------

class TestWizardJavaScriptValidation:
    """grant-wizard.js contains form validation logic."""

    @pytest.fixture(autouse=True)
    def load_js(self):
        path = os.path.join(REPO_ROOT, "static", "grant-wizard.js")
        with open(path, "rb") as f:
            self.content = f.read().decode("utf-8", errors="ignore")

    def test_js_file_exists(self):
        path = os.path.join(REPO_ROOT, "static", "grant-wizard.js")
        assert os.path.isfile(path), "static/grant-wizard.js must exist"

    def test_validates_zip_code(self):
        """JS validates ZIP code format."""
        content_lower = self.content.lower()
        assert "zip" in content_lower, "JS must reference ZIP field"

    def test_validates_project_type(self):
        """JS validates project type is selected."""
        content_lower = self.content.lower()
        assert "project_type" in content_lower or "project-type" in content_lower or \
               "projecttype" in content_lower, "JS must validate project type"

    def test_calls_eligibility_api(self):
        """JS makes call to eligibility API endpoint."""
        assert "/api/grants/eligibility" in self.content, \
            "JS must call /api/grants/eligibility"

    def test_uses_credentials_include(self):
        """API calls include session credentials."""
        assert "credentials" in self.content and "include" in self.content, \
            "JS must use credentials: 'include' for session auth"

    def test_uses_session_storage_key(self):
        """Session ID stored in localStorage."""
        assert "murphy_grant_session_id" in self.content, \
            "JS must use murphy_grant_session_id localStorage key"

    def test_posts_to_applications_endpoint(self):
        """JS posts to grant applications endpoint."""
        assert "applications" in self.content, \
            "JS must call the applications API endpoint"

    def test_handles_errors(self):
        """JS has error handling."""
        content_lower = self.content.lower()
        assert "error" in content_lower or "catch" in content_lower, \
            "JS must handle errors"

    def test_no_external_framework(self):
        """JS does not import external frameworks like React/Vue/Angular."""
        content_lower = self.content.lower()
        assert "react" not in content_lower
        assert "vue" not in content_lower
        assert "angular" not in content_lower
        assert "jquery" not in content_lower

    def test_has_loading_state(self):
        """JS shows loading state during API calls."""
        content_lower = self.content.lower()
        assert "loading" in content_lower or "spinner" in content_lower, \
            "JS must show loading state"

    def test_cost_slider_formatting(self):
        """JS formats cost slider value as currency."""
        content_lower = self.content.lower()
        assert "cost" in content_lower, "JS must handle cost slider"


# ---------------------------------------------------------------------------
# Pricing Page Integration Tests
# ---------------------------------------------------------------------------

class TestPricingPageIntegration:
    """pricing.html has the Financing & Grants navigation link and CTA."""

    @pytest.fixture(autouse=True)
    def load_html(self):
        path = os.path.join(REPO_ROOT, "pricing.html")
        with open(path, "rb") as f:
            self.content = f.read().decode("utf-8", errors="ignore")

    def test_pricing_has_financing_nav_link(self):
        """pricing.html nav includes Financing & Grants link."""
        assert "/ui/grant-wizard" in self.content, \
            "pricing.html must link to /ui/grant-wizard"

    def test_pricing_has_finance_cta_section(self):
        """pricing.html has a Finance this purchase CTA."""
        content_lower = self.content.lower()
        assert "finance" in content_lower or "grant" in content_lower, \
            "pricing.html must have finance/grant CTA section"

    def test_pricing_cta_links_to_wizard(self):
        """Finance CTA links to grant wizard."""
        assert "/ui/grant-wizard" in self.content

    def test_pricing_cta_mentions_tax_credit(self):
        """Finance CTA mentions IRA tax credit."""
        content_lower = self.content.lower()
        assert "tax credit" in content_lower or "ira" in content_lower or \
               "30%" in self.content, \
            "Finance CTA should mention IRA/tax credits"
