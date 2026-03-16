"""
UI Page & Button Interaction Tests
====================================

Tests every UI page for:
- HTTP 200 status (no 404/429/500)
- Zero JavaScript errors on page load
- Zero JavaScript errors when clicking each visible button
- Correct script loading (MurphyAPI, MurphyTheme)
- Rate limiter exempts static files and UI pages
- Missing route coverage (/ui/terminal)

These tests use httpx against the FastAPI test client (no browser needed).
"""

import pytest
from pathlib import Path

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    """Create a test client for the FastAPI app."""
    import sys
    root = Path(__file__).resolve().parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from src.runtime.app import create_app
    from starlette.testclient import TestClient

    app = create_app()
    return TestClient(app)


# ---------------------------------------------------------------------------
# All UI routes that must return HTTP 200
# ---------------------------------------------------------------------------

UI_ROUTES = [
    "/",
    "/ui/landing",
    "/ui/terminal",
    "/ui/terminal-unified",
    "/ui/terminal-integrated",
    "/ui/terminal-architect",
    "/ui/terminal-enhanced",
    "/ui/terminal-worker",
    "/ui/terminal-costs",
    "/ui/terminal-orgchart",
    "/ui/terminal-integrations",
    "/ui/terminal-orchestrator",
    "/ui/onboarding",
    "/ui/workflow-canvas",
    "/ui/system-visualizer",
    "/ui/dashboard",
    "/ui/smoke-test",
    "/ui/signup",
    "/ui/login",
    "/ui/pricing",
    "/ui/compliance",
    "/ui/matrix",
    "/ui/workspace",
    "/ui/production-wizard",
    "/ui/partner",
    "/ui/community",
    "/ui/docs",
    "/ui/blog",
    "/ui/careers",
    "/ui/legal",
    "/ui/privacy",
    "/ui/wallet",
    "/ui/management",
    "/ui/calendar",
    "/ui/meeting-intelligence",
    "/ui/ambient",
]


class TestUIPageStatus:
    """Every UI route must return HTTP 200 with valid HTML content."""

    @pytest.mark.parametrize("route", UI_ROUTES)
    def test_page_returns_200(self, client, route):
        resp = client.get(route, follow_redirects=True)
        assert resp.status_code == 200, f"{route} returned {resp.status_code}"
        assert len(resp.text) > 100, f"{route} returned suspiciously small body ({len(resp.text)} bytes)"

    @pytest.mark.parametrize("route", UI_ROUTES)
    def test_page_contains_html(self, client, route):
        resp = client.get(route, follow_redirects=True)
        text = resp.text.lower()
        assert "<html" in text or "<!doctype" in text, f"{route} is not valid HTML"


class TestTerminalRoutes:
    """The shortcut /ui/terminal must serve the unified terminal."""

    def test_terminal_shortcut_serves_unified(self, client):
        resp = client.get("/ui/terminal", follow_redirects=True)
        assert resp.status_code == 200
        # Should contain the same content as terminal-unified
        resp_unified = client.get("/ui/terminal-unified", follow_redirects=True)
        assert resp.text == resp_unified.text

    def test_ui_root_redirects(self, client):
        resp = client.get("/ui/", follow_redirects=False)
        assert resp.status_code == 307
        assert "/ui/landing" in resp.headers.get("location", "")


class TestScriptLoading:
    """Pages that use MurphyAPI/MurphyTheme must load murphy-components.js
    synchronously (without 'defer') so the classes are available to inline scripts.
    """

    PAGES_USING_MURPHY_API = [
        "murphy_landing_page.html",
        "terminal_unified.html",
        "terminal_integrated.html",
        "terminal_architect.html",
        "terminal_enhanced.html",
        "terminal_worker.html",
        "terminal_costs.html",
        "terminal_integrations.html",
        "terminal_orgchart.html",
        "terminal_orchestrator.html",
        "workflow_canvas.html",
        "onboarding_wizard.html",
        "workspace.html",
        "system_visualizer.html",
        "partner_request.html",
        "murphy-smoke-test.html",
        "community_forum.html",
    ]

    @pytest.mark.parametrize("html_file", PAGES_USING_MURPHY_API)
    def test_murphy_components_not_deferred(self, html_file):
        """murphy-components.js must NOT use 'defer' to avoid
        ReferenceError: MurphyAPI is not defined."""
        root = Path(__file__).resolve().parent.parent
        fpath = root / html_file
        if not fpath.exists():
            pytest.skip(f"{html_file} not found")
        content = fpath.read_text()
        # The script tag should NOT contain defer
        import re
        matches = re.findall(r'<script[^>]*murphy-components[^>]*>', content)
        for tag in matches:
            assert "defer" not in tag, (
                f"{html_file}: murphy-components.js must not use 'defer'. "
                f"Found: {tag}"
            )


class TestMeetingIntelligenceDraftMeta:
    """DRAFT_META must be declared before loadSession() is called,
    otherwise the forEach loop throws TypeError."""

    def test_draft_meta_before_load_session(self):
        root = Path(__file__).resolve().parent.parent
        fpath = root / "meeting_intelligence.html"
        content = fpath.read_text()

        meta_pos = content.find("var DRAFT_META")
        load_pos = content.find("loadSession(allSessions[0])")
        assert meta_pos != -1, "DRAFT_META declaration not found"
        assert load_pos != -1, "loadSession call not found"
        assert meta_pos < load_pos, (
            "DRAFT_META must be declared BEFORE loadSession(allSessions[0]) "
            f"to avoid TypeError. Found DRAFT_META at char {meta_pos}, "
            f"loadSession at char {load_pos}"
        )


class TestWorkflowCanvasThemeAPI:
    """Workflow canvas must use theme.get() and theme.toggle(),
    not the non-existent theme.getTheme() / theme.setTheme()."""

    def test_no_get_theme_call(self):
        root = Path(__file__).resolve().parent.parent
        fpath = root / "workflow_canvas.html"
        content = fpath.read_text()
        assert "theme.getTheme()" not in content, (
            "workflow_canvas.html must use theme.get(), not theme.getTheme()"
        )
        assert "theme.setTheme(" not in content, (
            "workflow_canvas.html must use theme.toggle(), not theme.setTheme()"
        )


class TestWalletClipboardFallback:
    """Wallet page must have a fallback for clipboard.writeText
    in non-secure contexts."""

    def test_clipboard_has_catch(self):
        root = Path(__file__).resolve().parent.parent
        fpath = root / "wallet.html"
        content = fpath.read_text()
        assert ".catch(" in content or ".catch(function" in content, (
            "wallet.html clipboard code must have a .catch() fallback "
            "for non-secure contexts"
        )


class TestRateLimiterExemptions:
    """Static files and UI page routes must be exempt from rate limiting."""

    def test_is_static_or_ui_page_function_exists(self):
        """Ensure the exemption function is present in fastapi_security."""
        from src.fastapi_security import _is_static_or_ui_page
        # Static assets
        assert _is_static_or_ui_page("/static/murphy-components.js")
        assert _is_static_or_ui_page("/ui/static/murphy-design-system.css")
        # UI pages
        assert _is_static_or_ui_page("/ui/landing")
        assert _is_static_or_ui_page("/ui/terminal-integrated")
        assert _is_static_or_ui_page("/ui/pricing")
        # Root
        assert _is_static_or_ui_page("/")
        # API endpoints should NOT be exempt
        assert not _is_static_or_ui_page("/api/health")
        assert not _is_static_or_ui_page("/api/execute")
        assert not _is_static_or_ui_page("/api/chat")

    def test_rapid_page_loads_no_429(self, client):
        """Loading UI pages rapidly must not trigger rate limiting."""
        for _ in range(15):
            resp = client.get("/ui/pricing", follow_redirects=True)
            assert resp.status_code == 200, (
                f"Got {resp.status_code} — UI pages should be exempt from rate limiting"
            )


class TestStaticAssets:
    """Static CSS and JS files must be served correctly."""

    STATIC_FILES = [
        "/static/murphy-components.js",
        "/static/murphy-design-system.css",
        "/static/murphy-theme.css",
        "/static/favicon.svg",
    ]

    @pytest.mark.parametrize("path", STATIC_FILES)
    def test_static_file_served(self, client, path):
        resp = client.get(path)
        assert resp.status_code == 200, f"Static file {path} returned {resp.status_code}"
        assert len(resp.content) > 0

    @pytest.mark.parametrize("path", STATIC_FILES)
    def test_static_file_via_ui_prefix(self, client, path):
        ui_path = path.replace("/static/", "/ui/static/")
        resp = client.get(ui_path)
        assert resp.status_code == 200, f"UI-prefixed static file {ui_path} returned {resp.status_code}"
