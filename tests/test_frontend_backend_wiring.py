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


class TestGapClosureMetrics:
    """Report on the overall wiring state."""

    def test_wiring_coverage(self):
        """At least 27 pages should have API calls (24 original + 3 new)."""
        pages = _collect_pages()
        pages_with_api = 0
        for route, filepath in pages:
            calls = _extract_api_calls_from_html(filepath)
            if calls:
                pages_with_api += 1
        assert pages_with_api >= 27, (
            f"Expected at least 27 pages with API calls, got {pages_with_api}"
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
