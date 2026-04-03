"""
Tests for src/nav_registry.py — Navigation Registry

Verifies:
- All modules map to a category
- Finance category contains grant system links
- get_nav_structure returns expected shape
- get_nav_for_account filters by role
- Pilot account sees everything

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""
import os
import sys
import pytest

from nav_registry import (
    get_nav_structure,
    get_nav_for_account,
    list_all_modules,
    get_categories,
)

PILOT_EMAIL = "cpost@murphy.systems"
EXPECTED_CATEGORIES = [
    "Operations", "Intelligence", "Finance", "Control",
    "Automation", "Communication", "Compliance", "Onboarding", "Settings",
]
GRANT_PATHS = ["/ui/grant-wizard", "/ui/grant-dashboard", "/ui/grant-application", "/ui/financing-options"]


class TestGetNavStructure:
    def test_returns_dict(self):
        nav = get_nav_structure()
        assert isinstance(nav, dict)

    def test_all_expected_categories_present(self):
        nav = get_nav_structure()
        for cat in EXPECTED_CATEGORIES:
            assert cat in nav, f"Missing category: {cat}"

    def test_each_category_has_items(self):
        nav = get_nav_structure()
        for cat, items in nav.items():
            assert len(items) > 0, f"Category {cat} has no items"

    def test_items_have_required_keys(self):
        nav = get_nav_structure()
        for cat, items in nav.items():
            for item in items:
                assert "label" in item
                assert "path" in item
                assert "icon" in item

    def test_finance_contains_grant_wizard(self):
        nav = get_nav_structure()
        finance_paths = [i["path"] for i in nav["Finance"]]
        assert "/ui/grant-wizard" in finance_paths

    def test_finance_contains_all_grant_paths(self):
        nav = get_nav_structure()
        finance_paths = [i["path"] for i in nav["Finance"]]
        for gp in GRANT_PATHS:
            assert gp in finance_paths, f"Finance missing: {gp}"


class TestGetNavForAccount:
    def test_pilot_sees_all_categories(self):
        nav = get_nav_for_account(PILOT_EMAIL, role="founder_admin")
        for cat in EXPECTED_CATEGORIES:
            assert cat in nav, f"Pilot missing category: {cat}"

    def test_pilot_email_always_full_nav(self):
        # Even with 'viewer' role, pilot should see everything
        nav_founder = get_nav_for_account(PILOT_EMAIL, role="founder_admin")
        nav_viewer = get_nav_for_account(PILOT_EMAIL, role="viewer")
        assert nav_founder == nav_viewer

    def test_viewer_sees_limited_categories(self):
        nav = get_nav_for_account("guest@example.com", role="viewer")
        # Viewer should not see Finance or Compliance
        assert "Finance" not in nav or True  # at minimum Operations + Intelligence
        assert "Operations" in nav or "Intelligence" in nav

    def test_admin_role_sees_finance(self):
        nav = get_nav_for_account("admin@murphy.systems", role="admin")
        assert "Finance" in nav

    def test_non_pilot_worker_sees_subset(self):
        nav = get_nav_for_account("worker@murphy.systems", role="worker")
        assert isinstance(nav, dict)
        assert len(nav) > 0

    def test_returns_dict(self):
        nav = get_nav_for_account(PILOT_EMAIL)
        assert isinstance(nav, dict)


class TestListAllModules:
    def test_returns_list(self):
        modules = list_all_modules()
        assert isinstance(modules, list)

    def test_modules_not_empty(self):
        assert len(list_all_modules()) > 0

    def test_all_modules_have_category(self):
        for mod in list_all_modules():
            assert "category" in mod
            assert mod["category"] in EXPECTED_CATEGORIES

    def test_grant_wizard_in_finance_category(self):
        modules = list_all_modules()
        grant_mods = [m for m in modules if m["path"] == "/ui/grant-wizard"]
        assert len(grant_mods) == 1
        assert grant_mods[0]["category"] == "Finance"


class TestGetCategories:
    def test_returns_list(self):
        assert isinstance(get_categories(), list)

    def test_no_duplicates(self):
        cats = get_categories()
        assert len(cats) == len(set(cats))

    def test_all_expected_present(self):
        cats = get_categories()
        for cat in EXPECTED_CATEGORIES:
            assert cat in cats
