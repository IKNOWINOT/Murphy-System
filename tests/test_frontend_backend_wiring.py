# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Frontend-Backend Wiring Commissioning Tests — Murphy System

Validates that every UI page's API calls are backed by real FastAPI route
handlers.  Uses static analysis of HTML files plus the app route registry
to detect wiring gaps without requiring a live server.

Business Source License 1.1 (BSL 1.1)
Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
"""

from __future__ import annotations

import os
import re
import pathlib
import pytest
from typing import Dict, List, Set, Tuple

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _extract_api_calls_from_html(filepath: pathlib.Path) -> Set[str]:
    """Parse an HTML file and extract all /api/* endpoint paths called via fetch/API."""
    text = filepath.read_text(encoding="utf-8", errors="replace")
    # Match patterns like:  fetch('/api/...'), API('/api/...'), apiFetch('/api/...')
    # Also match:  '/api/...'  and  "/api/..."  in JS strings
    patterns = [
        r"""(?:fetch|API|apiFetch|api\.(?:get|post|put|delete|patch))\s*\(\s*['"`]([^'"`]+)['"`]""",
        r"""(?:fetch|API|apiFetch|api\.(?:get|post|put|delete|patch))\s*\(\s*(?:API_BASE\s*\+\s*)?['"`]([^'"`]+)['"`]""",
        # Match: api('GET', '/api/...')  or  api("POST", "/api/...")
        r"""api\s*\(\s*['"][A-Z]+['"]\s*,\s*['"`]([^'"`]+)['"`]""",
        # Match: API_BASE = '/api/compliance'  (captures the base path)
        r"""API_BASE\s*=\s*['"`]([^'"`]+)['"`]""",
        # Match: apiFetch('/api/...')  with various helper names
        r"""(?:apiFetch|apiPost|apiGet)\s*\(\s*['"`]([^'"`]+)['"`]""",
    ]
    endpoints: Set[str] = set()
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            path = match.group(1)
            # Normalise: strip query strings, resolve variables
            path = path.split("?")[0].split("#")[0]
            # Skip non-API paths
            if not path.startswith("/api/") and not path.startswith("/"):
                # Could be a relative path appended to API_BASE
                if not path.startswith("http"):
                    path = "/api/" + path.lstrip("/")
            if "/api/" in path:
                # Normalise path parameters to {param}
                path = re.sub(r"/[0-9a-f-]{8,}(?:/|$)", "/{id}/", path)
                # Remove trailing slashes
                path = path.rstrip("/") or path
                endpoints.add(path)
    return endpoints


def _get_html_routes() -> Dict[str, str]:
    """Replicate the _html_routes mapping from app.py."""
    return {
        "/": "murphy_landing_page.html",
        "/ui/landing": "murphy_landing_page.html",
        "/ui/demo": "demo.html",
        "/ui/terminal-unified": "terminal_unified.html",
        "/ui/terminal-integrated": "terminal_integrated.html",
        "/ui/terminal-architect": "terminal_architect.html",
        "/ui/terminal-enhanced": "terminal_enhanced.html",
        "/ui/terminal-worker": "terminal_worker.html",
        "/ui/terminal-costs": "terminal_costs.html",
        "/ui/terminal-orgchart": "terminal_orgchart.html",
        "/ui/terminal-integrations": "terminal_integrations.html",
        "/ui/terminal-orchestrator": "terminal_orchestrator.html",
        "/ui/onboarding": "onboarding_wizard.html",
        "/ui/workflow-canvas": "workflow_canvas.html",
        "/ui/system-visualizer": "system_visualizer.html",
        "/ui/signup": "signup.html",
        "/ui/login": "login.html",
        "/ui/pricing": "pricing.html",
        "/ui/compliance": "compliance_dashboard.html",
        "/ui/workspace": "workspace.html",
        "/ui/production-wizard": "production_wizard.html",
        "/ui/partner": "partner_request.html",
        "/ui/community": "community_forum.html",
        "/ui/wallet": "wallet.html",
        "/ui/management": "management.html",
        "/ui/calendar": "calendar.html",
        "/ui/meeting-intelligence": "meeting_intelligence.html",
        "/ui/ambient": "ambient_intelligence.html",
        "/ui/trading": "trading_dashboard.html",
        "/ui/risk-dashboard": "risk_dashboard.html",
        "/ui/paper-trading": "paper_trading_dashboard.html",
        "/ui/grant-wizard": "grant_wizard.html",
        "/ui/grant-dashboard": "grant_dashboard.html",
        "/ui/grant-application": "grant_application.html",
        "/ui/financing": "financing_options.html",
        "/ui/roi-calendar": "roi_calendar.html",
        "/ui/comms-hub": "communication_hub.html",
        "/ui/admin": "admin_panel.html",
        "/ui/org-portal": "org_portal.html",
        "/ui/game-creation": "game_creation.html",
        "/ui/dispatch": "dispatch.html",
        "/ui/docs": "docs.html",
        "/ui/blog": "blog.html",
        "/ui/careers": "careers.html",
        "/ui/legal": "legal.html",
        "/ui/privacy": "privacy.html",
        "/ui/dashboard": "murphy_ui_integrated.html",
        "/ui/smoke-test": "murphy-smoke-test.html",
        "/ui/matrix": "matrix_integration.html",
        "/ui/trading-dashboard": "trading_dashboard.html",
        "/ui/change-password": "change_password.html",
        "/ui/terminal-integrated-legacy": "murphy_ui_integrated_terminal.html",
        "/ui/boards": "boards.html",
        "/ui/workdocs": "workdocs.html",
        "/ui/time-tracking": "time_tracking.html",
        "/ui/dashboards": "dashboards.html",
        "/ui/crm": "crm.html",
        "/ui/portfolio": "portfolio.html",
        "/ui/aionmind": "aionmind.html",
        "/ui/automations": "automations.html",
        "/ui/dev-module": "dev_module.html",
        "/ui/service-module": "service_module.html",
        "/ui/guest-portal": "guest_portal.html",
    }


def _collect_pages() -> List[Tuple[str, pathlib.Path]]:
    """Return (route, filepath) for every HTML page that exists on disk."""
    pages = []
    for route, filename in _get_html_routes().items():
        filepath = PROJECT_ROOT / filename
        if filepath.is_file():
            pages.append((route, filepath))
    return pages


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestHTMLPagesExist:
    """Verify every registered UI route has its HTML file on disk."""

    @pytest.mark.parametrize(
        "route,filename",
        list(_get_html_routes().items()),
        ids=list(_get_html_routes().keys()),
    )
    def test_html_file_exists(self, route: str, filename: str):
        filepath = PROJECT_ROOT / filename
        assert filepath.is_file(), (
            f"Route {route!r} maps to {filename!r} but file does not exist at {filepath}"
        )


class TestSidebarNavigation:
    """Verify sidebar navigation items match registered routes."""

    def test_sidebar_contains_new_pages(self):
        sidebar_js = (PROJECT_ROOT / "static" / "murphy-components.js").read_text()
        assert "/ui/boards" in sidebar_js, "Sidebar missing /ui/boards link"
        assert "/ui/workdocs" in sidebar_js, "Sidebar missing /ui/workdocs link"
        assert "/ui/time-tracking" in sidebar_js, "Sidebar missing /ui/time-tracking link"
        assert "/ui/dashboards" in sidebar_js, "Sidebar missing /ui/dashboards link"
        assert "/ui/crm" in sidebar_js, "Sidebar missing /ui/crm link"
        assert "/ui/portfolio" in sidebar_js, "Sidebar missing /ui/portfolio link"
        assert "/ui/aionmind" in sidebar_js, "Sidebar missing /ui/aionmind link"
        assert "/ui/automations" in sidebar_js, "Sidebar missing /ui/automations link"
        assert "/ui/dev-module" in sidebar_js, "Sidebar missing /ui/dev-module link"
        assert "/ui/service-module" in sidebar_js, "Sidebar missing /ui/service-module link"
        assert "/ui/guest-portal" in sidebar_js, "Sidebar missing /ui/guest-portal link"

    def test_sidebar_links_are_registered(self):
        sidebar_js = (PROJECT_ROOT / "static" / "murphy-components.js").read_text()
        html_routes = set(_get_html_routes().keys())
        # Extract all href values from sidebar
        hrefs = re.findall(r"href:\s*'([^']+)'", sidebar_js)
        for href in hrefs:
            assert href in html_routes, (
                f"Sidebar link {href!r} is not registered in _html_routes"
            )


class TestAPIWiring:
    """Verify that pages making API calls are wired to actual backend endpoints."""

    WIRED_PAGES = [
        ("trading_dashboard.html", {"/api/trading/status", "/api/trading/portfolio", "/api/trading/positions"}),
        ("paper_trading_dashboard.html", {"/api/trading/paper/status"}),
        ("risk_dashboard.html", {"/api/trading/emergency/status", "/api/trading/risk/assessment"}),
        ("wallet.html", {"/api/wallet/balances"}),
        ("admin_panel.html", {"/api/admin/stats", "/api/admin/users"}),
        ("compliance_dashboard.html", {"/api/compliance"}),
        ("boards.html", {"/api/boards"}),
        ("workdocs.html", {"/api/workdocs"}),
        ("time_tracking.html", {"/api/time-tracking/entries"}),
        ("dashboards.html", {"/api/dashboards"}),
        ("crm.html", {"/api/crm/contacts"}),
        ("portfolio.html", {"/api/portfolio/bars"}),
        ("aionmind.html", {"/api/aionmind/status"}),
        ("automations.html", {"/api/automations/rules"}),
        ("dev_module.html", {"/api/dev/sprints"}),
        ("service_module.html", {"/api/service/tickets"}),
        ("guest_portal.html", {"/api/guest/invites"}),
    ]

    @pytest.mark.parametrize(
        "filename,expected_endpoints",
        WIRED_PAGES,
        ids=[p[0] for p in WIRED_PAGES],
    )
    def test_page_calls_expected_endpoints(self, filename: str, expected_endpoints: Set[str]):
        filepath = PROJECT_ROOT / filename
        if not filepath.is_file():
            pytest.skip(f"{filename} not found")
        calls = _extract_api_calls_from_html(filepath)
        for endpoint in expected_endpoints:
            # Check if any extracted call starts with the expected endpoint
            matched = any(call.startswith(endpoint) for call in calls)
            assert matched, (
                f"{filename} should call {endpoint!r} but extracted calls are: {sorted(calls)}"
            )


class TestNewPageIntegration:
    """Verify the three new pages (boards, workdocs, time_tracking) are fully wired."""

    def test_boards_html_exists(self):
        assert (PROJECT_ROOT / "boards.html").is_file()

    def test_boards_html_has_api_calls(self):
        calls = _extract_api_calls_from_html(PROJECT_ROOT / "boards.html")
        assert any("/api/boards" in c for c in calls), f"boards.html missing /api/boards calls: {calls}"

    def test_boards_html_has_murphy_sidebar(self):
        text = (PROJECT_ROOT / "boards.html").read_text()
        assert "murphy-sidebar" in text, "boards.html missing murphy-sidebar component"

    def test_boards_html_has_design_system(self):
        text = (PROJECT_ROOT / "boards.html").read_text()
        assert "murphy-design-system.css" in text, "boards.html missing design system CSS"

    def test_workdocs_html_exists(self):
        assert (PROJECT_ROOT / "workdocs.html").is_file()

    def test_workdocs_html_has_api_calls(self):
        calls = _extract_api_calls_from_html(PROJECT_ROOT / "workdocs.html")
        assert any("/api/workdocs" in c for c in calls), f"workdocs.html missing /api/workdocs calls: {calls}"

    def test_workdocs_html_has_murphy_sidebar(self):
        text = (PROJECT_ROOT / "workdocs.html").read_text()
        assert "murphy-sidebar" in text, "workdocs.html missing murphy-sidebar component"

    def test_time_tracking_html_exists(self):
        assert (PROJECT_ROOT / "time_tracking.html").is_file()

    def test_time_tracking_html_has_api_calls(self):
        calls = _extract_api_calls_from_html(PROJECT_ROOT / "time_tracking.html")
        assert any("/api/time-tracking" in c for c in calls), (
            f"time_tracking.html missing /api/time-tracking calls: {calls}"
        )

    def test_time_tracking_html_has_murphy_sidebar(self):
        text = (PROJECT_ROOT / "time_tracking.html").read_text()
        assert "murphy-sidebar" in text, "time_tracking.html missing murphy-sidebar component"


class TestAppRouteRegistration:
    """Verify new routes are registered in app.py."""

    def test_boards_route_in_app(self):
        app_py = (PROJECT_ROOT / "src" / "runtime" / "app.py").read_text()
        assert '"/ui/boards"' in app_py, "app.py missing /ui/boards route"
        assert '"boards.html"' in app_py, "app.py missing boards.html mapping"

    def test_workdocs_route_in_app(self):
        app_py = (PROJECT_ROOT / "src" / "runtime" / "app.py").read_text()
        assert '"/ui/workdocs"' in app_py, "app.py missing /ui/workdocs route"
        assert '"workdocs.html"' in app_py, "app.py missing workdocs.html mapping"

    def test_time_tracking_route_in_app(self):
        app_py = (PROJECT_ROOT / "src" / "runtime" / "app.py").read_text()
        assert '"/ui/time-tracking"' in app_py, "app.py missing /ui/time-tracking route"
        assert '"time_tracking.html"' in app_py, "app.py missing time_tracking.html mapping"

    def test_dashboards_route_in_app(self):
        app_py = (PROJECT_ROOT / "src" / "runtime" / "app.py").read_text()
        assert '"/ui/dashboards"' in app_py, "app.py missing /ui/dashboards route"
        assert '"dashboards.html"' in app_py, "app.py missing dashboards.html mapping"

    def test_crm_route_in_app(self):
        app_py = (PROJECT_ROOT / "src" / "runtime" / "app.py").read_text()
        assert '"/ui/crm"' in app_py, "app.py missing /ui/crm route"
        assert '"crm.html"' in app_py, "app.py missing crm.html mapping"

    def test_portfolio_route_in_app(self):
        app_py = (PROJECT_ROOT / "src" / "runtime" / "app.py").read_text()
        assert '"/ui/portfolio"' in app_py, "app.py missing /ui/portfolio route"
        assert '"portfolio.html"' in app_py, "app.py missing portfolio.html mapping"

    def test_aionmind_route_in_app(self):
        app_py = (PROJECT_ROOT / "src" / "runtime" / "app.py").read_text()
        assert '"/ui/aionmind"' in app_py, "app.py missing /ui/aionmind route"
        assert '"aionmind.html"' in app_py, "app.py missing aionmind.html mapping"

    def test_automations_route_in_app(self):
        app_py = (PROJECT_ROOT / "src" / "runtime" / "app.py").read_text()
        assert '"/ui/automations"' in app_py, "app.py missing /ui/automations route"
        assert '"automations.html"' in app_py, "app.py missing automations.html mapping"

    def test_dev_module_route_in_app(self):
        app_py = (PROJECT_ROOT / "src" / "runtime" / "app.py").read_text()
        assert '"/ui/dev-module"' in app_py, "app.py missing /ui/dev-module route"
        assert '"dev_module.html"' in app_py, "app.py missing dev_module.html mapping"

    def test_service_module_route_in_app(self):
        app_py = (PROJECT_ROOT / "src" / "runtime" / "app.py").read_text()
        assert '"/ui/service-module"' in app_py, "app.py missing /ui/service-module route"
        assert '"service_module.html"' in app_py, "app.py missing service_module.html mapping"

    def test_guest_portal_route_in_app(self):
        app_py = (PROJECT_ROOT / "src" / "runtime" / "app.py").read_text()
        assert '"/ui/guest-portal"' in app_py, "app.py missing /ui/guest-portal route"
        assert '"guest_portal.html"' in app_py, "app.py missing guest_portal.html mapping"


class TestSprint2PageIntegration:
    """Verify Sprint 2 pages (dashboards, crm, portfolio, aionmind) are fully wired."""

    def test_dashboards_html_exists(self):
        assert (PROJECT_ROOT / "dashboards.html").is_file()

    def test_dashboards_html_has_api_calls(self):
        calls = _extract_api_calls_from_html(PROJECT_ROOT / "dashboards.html")
        assert any("/api/dashboards" in c for c in calls), f"dashboards.html missing /api/dashboards calls: {calls}"

    def test_dashboards_html_has_murphy_sidebar(self):
        text = (PROJECT_ROOT / "dashboards.html").read_text()
        assert "murphy-sidebar" in text

    def test_dashboards_html_has_design_system(self):
        text = (PROJECT_ROOT / "dashboards.html").read_text()
        assert "murphy-design-system.css" in text

    def test_crm_html_exists(self):
        assert (PROJECT_ROOT / "crm.html").is_file()

    def test_crm_html_has_api_calls(self):
        calls = _extract_api_calls_from_html(PROJECT_ROOT / "crm.html")
        assert any("/api/crm" in c for c in calls), f"crm.html missing /api/crm calls: {calls}"

    def test_crm_html_has_murphy_sidebar(self):
        text = (PROJECT_ROOT / "crm.html").read_text()
        assert "murphy-sidebar" in text

    def test_portfolio_html_exists(self):
        assert (PROJECT_ROOT / "portfolio.html").is_file()

    def test_portfolio_html_has_api_calls(self):
        calls = _extract_api_calls_from_html(PROJECT_ROOT / "portfolio.html")
        assert any("/api/portfolio" in c for c in calls), f"portfolio.html missing /api/portfolio calls: {calls}"

    def test_portfolio_html_has_murphy_sidebar(self):
        text = (PROJECT_ROOT / "portfolio.html").read_text()
        assert "murphy-sidebar" in text

    def test_aionmind_html_exists(self):
        assert (PROJECT_ROOT / "aionmind.html").is_file()

    def test_aionmind_html_has_api_calls(self):
        calls = _extract_api_calls_from_html(PROJECT_ROOT / "aionmind.html")
        assert any("/api/aionmind" in c for c in calls), f"aionmind.html missing /api/aionmind calls: {calls}"

    def test_aionmind_html_has_murphy_sidebar(self):
        text = (PROJECT_ROOT / "aionmind.html").read_text()
        assert "murphy-sidebar" in text


class TestSprint3PageIntegration:
    """Verify Sprint 3 pages (automations, dev_module, service_module, guest_portal) are fully wired."""

    def test_automations_html_exists(self):
        assert (PROJECT_ROOT / "automations.html").is_file()

    def test_automations_html_has_api_calls(self):
        calls = _extract_api_calls_from_html(PROJECT_ROOT / "automations.html")
        assert any("/api/automations" in c for c in calls), f"automations.html missing /api/automations calls: {calls}"

    def test_automations_html_has_murphy_sidebar(self):
        text = (PROJECT_ROOT / "automations.html").read_text()
        assert "murphy-sidebar" in text

    def test_automations_html_has_design_system(self):
        text = (PROJECT_ROOT / "automations.html").read_text()
        assert "murphy-design-system.css" in text

    def test_dev_module_html_exists(self):
        assert (PROJECT_ROOT / "dev_module.html").is_file()

    def test_dev_module_html_has_api_calls(self):
        calls = _extract_api_calls_from_html(PROJECT_ROOT / "dev_module.html")
        assert any("/api/dev" in c for c in calls), f"dev_module.html missing /api/dev calls: {calls}"

    def test_dev_module_html_has_murphy_sidebar(self):
        text = (PROJECT_ROOT / "dev_module.html").read_text()
        assert "murphy-sidebar" in text

    def test_service_module_html_exists(self):
        assert (PROJECT_ROOT / "service_module.html").is_file()

    def test_service_module_html_has_api_calls(self):
        calls = _extract_api_calls_from_html(PROJECT_ROOT / "service_module.html")
        assert any("/api/service" in c for c in calls), f"service_module.html missing /api/service calls: {calls}"

    def test_service_module_html_has_murphy_sidebar(self):
        text = (PROJECT_ROOT / "service_module.html").read_text()
        assert "murphy-sidebar" in text

    def test_guest_portal_html_exists(self):
        assert (PROJECT_ROOT / "guest_portal.html").is_file()

    def test_guest_portal_html_has_api_calls(self):
        calls = _extract_api_calls_from_html(PROJECT_ROOT / "guest_portal.html")
        assert any("/api/guest" in c for c in calls), f"guest_portal.html missing /api/guest calls: {calls}"

    def test_guest_portal_html_has_murphy_sidebar(self):
        text = (PROJECT_ROOT / "guest_portal.html").read_text()
        assert "murphy-sidebar" in text


class TestGapClosureMetrics:
    """Report on the overall wiring state."""

    def test_wiring_coverage(self):
        """At least 35 pages should have API calls (24 original + 3 sprint1 + 4 sprint2 + 4 sprint3)."""
        pages = _collect_pages()
        pages_with_api = 0
        for route, filepath in pages:
            calls = _extract_api_calls_from_html(filepath)
            if calls:
                pages_with_api += 1
        assert pages_with_api >= 35, (
            f"Expected at least 35 pages with API calls, got {pages_with_api}"
        )

    def test_no_orphan_sidebar_links(self):
        """Every sidebar link should resolve to a file on disk."""
        sidebar_js = (PROJECT_ROOT / "static" / "murphy-components.js").read_text()
        hrefs = re.findall(r"href:\s*'([^']+)'", sidebar_js)
        html_routes = _get_html_routes()
        for href in hrefs:
            assert href in html_routes, f"Sidebar link {href!r} not in route map"
            filename = html_routes[href]
            filepath = PROJECT_ROOT / filename
            assert filepath.is_file(), f"Sidebar link {href!r} → {filename!r} file missing"
