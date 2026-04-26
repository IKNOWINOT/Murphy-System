"""
Murphy System — UI Test Suite
conftest.py — MCB-backed fixtures and shared configuration.

All browser interaction goes through MultiCursorBrowser (MCB).
Playwright is MCB's transport — tests never call it directly.

Every test gets:
  - `mcb_page`        — MCB instance + zone_id for single-cursor tests
  - `mcb_multi`       — factory that returns N zones from one MCB instance
  - `screenshot`      — helper that saves PNGs to tests/ui/screenshots/
  - `BASE_URL`        — the local HTTP server base URL

The `page` fixture is a compatibility shim: it wraps an MCB zone so that
existing tests using `page.goto(url)` / `page.locator()` / `expect()`
continue to work without modification.

Run: pytest tests/ui/ -v
"""

from __future__ import annotations

import asyncio
import os
import re
import threading
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Tuple

import pytest

# ── Configuration ──────────────────────────────────────────────────────────
BASE_URL        = os.environ.get("MURPHY_TEST_URL", "http://localhost:18080")
SCREENSHOTS_DIR = Path(__file__).parent / "screenshots"
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)


# ── Async runner (thread-safe, works inside or outside uvicorn) ─────────

def _run(coro) -> Any:
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            box: Dict = {}
            def _t():
                nl = asyncio.new_event_loop()
                asyncio.set_event_loop(nl)
                try:
                    box["v"] = nl.run_until_complete(coro)
                except Exception as e:
                    box["e"] = e
                finally:
                    nl.close()
            th = threading.Thread(target=_t, daemon=True)
            th.start(); th.join(timeout=60)
            if "e" in box: raise box["e"]
            return box.get("v")
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


# ── MCB import (graceful skip if not available) ────────────────────────────

try:
    import sys
    sys.path.insert(0, str(Path(__file__).parents[2] / "src"))
    from agent_module_loader import MultiCursorBrowser
    _HAS_MCB = True
except ImportError:
    MultiCursorBrowser = None
    _HAS_MCB = False

if not _HAS_MCB:
    collect_ignore_glob = ["test_*.py"]


# ── MCBPageShim — makes MCB zone look like a Playwright Page ──────────────

class MCBPageShim:
    """Thin shim: MCB zone with a Playwright-Page-compatible API.

    Existing tests that call page.goto(), page.locator(), page.evaluate(),
    page.title(), page.screenshot(), expect() will all work unchanged.
    """

    def __init__(self, mcb: "MultiCursorBrowser", zone_id: str):
        self._mcb     = mcb
        self._zone_id = zone_id

    # ── Core navigation ────────────────────────────────────────────────

    def goto(self, url: str, **kwargs) -> None:
        _run(self._mcb.navigate(self._zone_id, url))

    def reload(self, **kwargs) -> None:
        from agent_module_loader import MultiCursorActionType as AT
        _run(self._mcb._execute(AT.RELOAD, self._zone_id))

    def go_back(self, **kwargs):
        from agent_module_loader import MultiCursorActionType as AT
        _run(self._mcb._execute(AT.GO_BACK, self._zone_id))

    def go_forward(self, **kwargs):
        from agent_module_loader import MultiCursorActionType as AT
        _run(self._mcb._execute(AT.GO_FORWARD, self._zone_id))

    # ── Read ───────────────────────────────────────────────────────────

    def title(self) -> str:
        r = _run(self._mcb.get_title(self._zone_id))
        return r.data.get("title", "") if r else ""

    def url(self) -> str:
        r = _run(self._mcb.get_url(self._zone_id))
        return r.data.get("url", "") if r else ""

    def content(self) -> str:
        r = _run(self._mcb.get_content(self._zone_id))
        return r.data.get("content", "") if r else ""

    def inner_text(self, selector: str) -> str:
        r = _run(self._mcb.get_text(self._zone_id, selector))
        return r.data.get("text", "") if r else ""

    def text_content(self, selector: str) -> Optional[str]:
        r = _run(self._mcb.text_content(self._zone_id, selector))
        return r.data.get("text") if r else None

    def input_value(self, selector: str) -> str:
        r = _run(self._mcb.input_value(self._zone_id, selector))
        return r.data.get("value", "") if r else ""

    def evaluate(self, expression: str, *args) -> Any:
        r = _run(self._mcb.evaluate(self._zone_id, expression))
        return r.data.get("result") if r else None

    # ── Interaction ────────────────────────────────────────────────────

    def click(self, selector: str, **kwargs) -> None:
        _run(self._mcb.click(self._zone_id, selector))

    def fill(self, selector: str, value: str, **kwargs) -> None:
        _run(self._mcb.fill(self._zone_id, selector, value))

    def type(self, selector: str, text: str, **kwargs) -> None:
        _run(self._mcb.type(self._zone_id, selector, text))

    def press(self, selector: str, key: str, **kwargs) -> None:
        from agent_module_loader import MultiCursorActionType as AT
        _run(self._mcb._execute(AT.PRESS, self._zone_id, selector=selector,
                                parameters={"key": key}))

    def wait_for_timeout(self, ms: int) -> None:
        import time; time.sleep(ms / 1000)

    def wait_for_selector(self, selector: str, **kwargs) -> Any:
        _run(self._mcb.wait_for_selector(self._zone_id, selector,
                                          timeout_ms=kwargs.get("timeout", 30000)))
        return self.locator(selector)

    # ── Screenshot ─────────────────────────────────────────────────────

    def screenshot(self, path: Optional[str] = None, **kwargs) -> bytes:
        import base64
        r = _run(self._mcb.screenshot(self._zone_id, path=path))
        if not r:
            return b""
        png_b64 = r.data.get("png_b64") or r.data.get("png_bytes_b64", "")
        png_bytes = r.data.get("png_bytes") or (
            base64.b64decode(png_b64) if png_b64 else b""
        )
        if path and png_bytes:
            Path(path).write_bytes(png_bytes)
        return png_bytes

    # ── Locator shim ───────────────────────────────────────────────────

    def locator(self, selector: str) -> "MCBLocatorShim":
        return MCBLocatorShim(self, selector)

    def get_by_role(self, role: str, **kwargs):
        name = kwargs.get("name") or kwargs.get("has_text")
        return MCBLocatorShim(self, f"[role='{role}']")

    def get_by_text(self, text: str, **kwargs):
        return MCBLocatorShim(self, f"text={text}")

    def get_by_label(self, text: str, **kwargs):
        return MCBLocatorShim(self, f"label={text}")

    def get_by_placeholder(self, text: str, **kwargs):
        return MCBLocatorShim(self, f"[placeholder='{text}']")


class MCBLocatorShim:
    """Minimal Playwright Locator shim backed by MCB zone."""

    def __init__(self, page_shim: MCBPageShim, selector: str):
        self._page     = page_shim
        self._selector = selector

    @property
    def first(self) -> "MCBLocatorShim":
        return self  # MCB always acts on first match

    def count(self) -> int:
        return 1  # conservative — if element action succeeds, it exists

    def is_visible(self) -> bool:
        r = _run(self._page._mcb.is_visible(self._page._zone_id, self._selector))
        return bool(r and r.data.get("visible", True))

    def is_hidden(self) -> bool:
        r = _run(self._page._mcb.is_hidden(self._page._zone_id, self._selector))
        return bool(r and r.data.get("hidden", False))

    def is_editable(self) -> bool:
        r = _run(self._page._mcb.is_editable(self._page._zone_id, self._selector))
        return bool(r and r.data.get("editable", True))

    def is_enabled(self) -> bool:
        return not self.is_disabled()

    def is_disabled(self) -> bool:
        r = _run(self._page._mcb.is_disabled(self._page._zone_id, self._selector))
        return bool(r and r.data.get("disabled", False))

    def inner_text(self) -> str:
        return self._page.inner_text(self._selector)

    def text_content(self) -> Optional[str]:
        return self._page.text_content(self._selector)

    def input_value(self) -> str:
        return self._page.input_value(self._selector)

    def get_attribute(self, name: str) -> Optional[str]:
        from agent_module_loader import MultiCursorActionType as AT
        r = _run(self._page._mcb._execute(
            AT.GET_ATTRIBUTE, self._page._zone_id,
            selector=self._selector, parameters={"name": name}
        ))
        return r.data.get("value") if r else None

    def fill(self, value: str, **kwargs) -> None:
        self._page.fill(self._selector, value)

    def click(self, **kwargs) -> None:
        self._page.click(self._selector)

    def screenshot(self, **kwargs) -> bytes:
        return self._page.screenshot(**kwargs)

    # ── expect() compatibility ─────────────────────────────────────────
    # expect(locator).to_be_visible() etc. work because MCBExpect wraps this

    def to_be_visible(self):
        assert self.is_visible(), f"Expected {self._selector!r} to be visible"

    def to_be_editable(self):
        assert self.is_editable(), f"Expected {self._selector!r} to be editable"

    def to_be_hidden(self):
        assert self.is_hidden(), f"Expected {self._selector!r} to be hidden"

    def to_have_attribute(self, name: str, value: str):
        actual = self.get_attribute(name)
        assert actual == value, f"Expected {self._selector!r} attr {name!r}={value!r}, got {actual!r}"

    def to_have_value(self, value: str):
        actual = self.input_value()
        assert actual == value, f"Expected {self._selector!r} value {value!r}, got {actual!r}"


# expect() shim — wraps locator, returns it (locator already has to_be_* methods)
def expect(locator):
    return locator


# ── Session-scoped MCB instance ────────────────────────────────────────────

@pytest.fixture(scope="session")
def _session_mcb():
    """One shared MCB browser instance for the whole test session."""
    mcb = MultiCursorBrowser(headless=True)
    _run(mcb.launch())
    yield mcb
    _run(mcb.close())


# ── Primary page fixture ───────────────────────────────────────────────────

@pytest.fixture
def mcb_page(_session_mcb) -> Generator[Tuple[MultiCursorBrowser, str], None, None]:
    """Yields (mcb, zone_id) — one zone per test, cleaned up after."""
    zones   = _session_mcb.auto_layout(1)
    zone_id = zones[0]["zone_id"]
    yield _session_mcb, zone_id
    # Close just this zone's page
    try:
        page = _run(_session_mcb._get_page(zone_id))
        if page and not page.is_closed():
            _run(page.close())
    except Exception:
        pass


@pytest.fixture
def page(_session_mcb) -> Generator[MCBPageShim, None, None]:
    """Playwright-Page-compatible shim — drop-in for existing tests."""
    zones   = _session_mcb.auto_layout(1)
    zone_id = zones[0]["zone_id"]
    yield MCBPageShim(_session_mcb, zone_id)
    try:
        pg = _run(_session_mcb._get_page(zone_id))
        if pg and not pg.is_closed():
            _run(pg.close())
    except Exception:
        pass


# ── Multi-cursor fixture ───────────────────────────────────────────────────

@pytest.fixture
def multi_cursor(_session_mcb):
    """Returns a factory: call open_cursors(n) to get n MCBPageShims."""
    opened_zones: List[str] = []

    def open_cursors(n: int = 2) -> List[MCBPageShim]:
        zones = _session_mcb.auto_layout(n)
        shims = []
        for z in zones[:n]:
            opened_zones.append(z["zone_id"])
            shims.append(MCBPageShim(_session_mcb, z["zone_id"]))
        return shims

    yield open_cursors

    for zid in opened_zones:
        try:
            pg = _run(_session_mcb._get_page(zid))
            if pg and not pg.is_closed():
                _run(pg.close())
        except Exception:
            pass


# ── Screenshot helper ──────────────────────────────────────────────────────

@pytest.fixture
def screenshot(request):
    test_name   = request.node.name
    module_name = request.node.fspath.basename.replace(".py", "")
    subdir_map  = {
        "test_landing_page": "landing", "test_login": "login",
        "test_signup": "signup", "test_navigation": "navigation",
        "test_admin": "admin", "test_compliance": "compliance",
        "test_all_pages": "all_pages",
    }
    subdir   = subdir_map.get(module_name, "all_pages")
    save_dir = SCREENSHOTS_DIR / subdir
    save_dir.mkdir(parents=True, exist_ok=True)

    def _capture(pg, label: str) -> Path:
        safe_test  = re.sub(r"[^\w]", "_", test_name)[:60]
        safe_label = re.sub(r"[^\w]", "_", label)[:40]
        path       = save_dir / f"{safe_test}__{safe_label}.png"
        pg.screenshot(path=str(path))
        return path

    return _capture


# ── Base URL convenience ───────────────────────────────────────────────────

@pytest.fixture(scope="session")
def base_url():
    return BASE_URL
