"""
Tests for src/pilot_config.py — Pilot Account Configuration

Verifies:
- Pilot account is cpost@murphy.systems
- All required fields are present
- PILOT_AUTOMATION_ROUTING covers all expected categories
- Helper functions work correctly

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from pilot_config import (
    PILOT_ACCOUNT,
    PILOT_AUTOMATION_ROUTING,
    get_pilot_email,
    is_pilot,
    get_routing_for_category,
)


class TestPilotAccount:
    def test_pilot_email_is_cpost(self):
        assert PILOT_ACCOUNT["email"] == "cpost@murphy.systems"

    def test_pilot_name_is_corey_post(self):
        assert PILOT_ACCOUNT["name"] == "Corey Post"

    def test_pilot_role_is_founder_admin(self):
        assert PILOT_ACCOUNT["role"] == "founder_admin"

    def test_pilot_org_is_inoni(self):
        assert "Inoni" in PILOT_ACCOUNT["org"]

    def test_automations_enabled(self):
        assert PILOT_ACCOUNT["automations_enabled"] is True

    def test_lcm_enabled(self):
        assert PILOT_ACCOUNT["lcm_enabled"] is True

    def test_all_modules_visible(self):
        assert PILOT_ACCOUNT["all_modules_visible"] is True

    def test_hitl_level_graduated(self):
        assert PILOT_ACCOUNT["hitl_level"] == "graduated"


class TestGetPilotEmail:
    def test_returns_correct_email(self):
        assert get_pilot_email() == "cpost@murphy.systems"

    def test_return_type_is_str(self):
        assert isinstance(get_pilot_email(), str)


class TestIsPilot:
    def test_cpost_is_pilot(self):
        assert is_pilot("cpost@murphy.systems") is True

    def test_case_insensitive(self):
        assert is_pilot("CPOST@MURPHY.SYSTEMS") is True

    def test_other_account_not_pilot(self):
        assert is_pilot("other@murphy.systems") is False

    def test_empty_string_not_pilot(self):
        assert is_pilot("") is False

    def test_old_email_not_pilot(self):
        assert is_pilot("cpost@inoni3dp.com") is False


class TestPilotAutomationRouting:
    EXPECTED_CATEGORIES = ["sales", "marketing", "engineering", "research",
                           "communications", "finance", "compliance", "onboarding"]

    def test_all_categories_present(self):
        for cat in self.EXPECTED_CATEGORIES:
            assert cat in PILOT_AUTOMATION_ROUTING, f"Missing category: {cat}"

    def test_finance_has_grant_modules(self):
        finance = PILOT_AUTOMATION_ROUTING["finance"]
        modules = finance.get("modules", [])
        assert "grant_wizard" in modules
        assert "grant_dashboard" in modules
        assert "financing_options" in modules

    def test_sales_has_shadow_agents(self):
        assert len(PILOT_AUTOMATION_ROUTING["sales"]["shadow_agents"]) >= 1

    def test_compliance_has_modules(self):
        assert "compliance_dashboard" in PILOT_AUTOMATION_ROUTING["compliance"]["modules"]


class TestGetRoutingForCategory:
    def test_known_category_returns_dict(self):
        result = get_routing_for_category("finance")
        assert isinstance(result, dict)
        assert "modules" in result

    def test_unknown_category_returns_empty(self):
        result = get_routing_for_category("nonexistent_category_xyz")
        assert result == {}

    def test_sales_routing(self):
        result = get_routing_for_category("sales")
        assert "shadow_agents" in result
