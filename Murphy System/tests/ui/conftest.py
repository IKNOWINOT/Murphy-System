"""
Murphy System — UI Test Suite
conftest.py — Multi-cursor fixtures and shared configuration.

Every test gets:
  - `page` — a Page-like object ready to use (requires playwright or multicursor)
  - `browser_context` — multi-tab context for multi-cursor tests
  - `screenshot` — helper that saves PNGs to tests/ui/screenshots/ (committed)
  - `BASE_URL` — the local HTTP server base URL

Run: pytest tests/ui/ -v --headed=false
"""

import os
import re
from pathlib import Path

import pytest

try:
    from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright
    _HAS_PLAYWRIGHT = True
except ImportError:
    _HAS_PLAYWRIGHT = False
    Browser = None
    BrowserContext = None
    Page = None
    sync_playwright = None

# Skip the entire tests/ui directory when playwright is not installed
if not _HAS_PLAYWRIGHT:
    collect_ignore_glob = ["test_*.py"]

# ── Configuration ──────────────────────────────────────────────────────────
BASE_URL = os.environ.get("MURPHY_TEST_URL", "http://localhost:18080")
SCREENSHOTS_DIR = Path(__file__).parent / "screenshots"
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)


# ── Playwright browser fixture (module-scoped for speed) ───────────────────
@pytest.fixture(scope="session")
def playwright_instance():
    with sync_playwright() as pw:
        yield pw


@pytest.fixture(scope="session")
def browser(playwright_instance):
    b = playwright_instance.chromium.launch(headless=True, args=["--no-sandbox"])
    yield b
    b.close()


@pytest.fixture
def context(browser: Browser):
    ctx = browser.new_context(
        viewport={"width": 1280, "height": 800},
        ignore_https_errors=True,
    )
    yield ctx
    ctx.close()


@pytest.fixture
def page(context: BrowserContext):
    p = context.new_page()
    yield p
    p.close()


# ── Multi-cursor fixture: opens N pages simultaneously ─────────────────────
@pytest.fixture
def multi_cursor(context: BrowserContext):
    """Return a factory that opens multiple pages (cursors) in the same context."""
    pages = []

    def open_cursors(n: int = 2) -> list:
        for _ in range(n):
            p = context.new_page()
            pages.append(p)
        return pages

    yield open_cursors
    for p in pages:
        try:
            p.close()
        except Exception:
            pass


# ── Screenshot helper ──────────────────────────────────────────────────────
@pytest.fixture
def screenshot(request):
    """
    Returns a callable: screenshot(page, label)
    Saves PNG to tests/ui/screenshots/{subdir}/{test_name}_{label}.png
    The subdir is derived from the test file name (e.g. test_landing_page → landing).
    """
    test_name = request.node.name
    module_name = request.node.fspath.basename.replace(".py", "")
    # Map module → screenshot subdir
    subdir_map = {
        "test_landing_page": "landing",
        "test_login": "login",
        "test_signup": "signup",
        "test_navigation": "navigation",
        "test_admin": "admin",
        "test_compliance": "compliance",
        "test_partner": "partner",
        "test_pricing": "pricing",
        "test_docs": "docs",
        "test_careers": "careers",
        "test_legal": "legal",
        "test_privacy": "privacy",
        "test_blog": "blog",
        "test_wallet": "wallet",
        "test_trading": "trading",
        "test_terminals": "terminal",
        "test_onboarding": "onboarding",
        "test_grants": "grants",
        "test_communications": "communications",
        "test_calendar": "calendar",
        "test_dispatch": "dispatch",
        "test_workspace": "workspace",
        "test_all_pages": "all_pages",
    }
    subdir = subdir_map.get(module_name, "all_pages")
    save_dir = SCREENSHOTS_DIR / subdir
    save_dir.mkdir(parents=True, exist_ok=True)

    def _capture(pg: Page, label: str) -> Path:
        safe_test = re.sub(r"[^\w]", "_", test_name)[:60]
        safe_label = re.sub(r"[^\w]", "_", label)[:40]
        path = save_dir / f"{safe_test}__{safe_label}.png"
        pg.screenshot(path=str(path), full_page=False)
        return path

    return _capture


# ── Base URL convenience ───────────────────────────────────────────────────
@pytest.fixture(scope="session")
def base_url():
    return BASE_URL
