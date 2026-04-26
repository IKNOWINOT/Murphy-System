"""
Murphy Ghost Vision — murphy_ghost_vision.py
PATCH-091

Pattern recognition layer for GhostController web automation.
Converts CSS selectors, text, roles, and labels into screen coordinates
so Ghost can click/type/interact like a real user — no browser library needed.

Three-stage locator pipeline (fast → reliable → visual):
  Stage 1 — HTML DOM locator  : fetch HTML, parse with cssselect/bs4,
                                extract element text/label/placeholder,
                                estimate screen position from DOM layout
  Stage 2 — OCR locator       : screenshot → pytesseract → find text on screen
  Stage 3 — Visual pattern    : transformers zero-shot image classification
                                identifies UI element regions by type

Also provides:
  - GhostBrowser   : launches Chromium (no Playwright) + Xvfb, manages sessions
  - GhostPage      : per-tab state, screenshot, navigate, cookies
  - WebPatternDB   : learned patterns for common website UI (login forms,
                     nav bars, search boxes, modals, CTAs, cookie banners)

Copyright © 2020-2026 Inoni LLC — Created by Corey Post
PATCH-091 | Label: MCB-VISION-001
License: BSL 1.1
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import logging
import os
import re
import subprocess
import tempfile
import threading
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

CHROMIUM_BIN = (
    os.environ.get("MURPHY_CHROMIUM_BIN")
    or "/root/.cache/ms-playwright/chromium-1208/chrome-linux64/chrome"
)
CHROMIUM_FLAGS = [
    "--headless=new",
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--remote-debugging-port=0",   # OS picks a free port
    "--window-size=1280,900",
    "--disable-extensions",
    "--disable-background-networking",
    "--disable-default-apps",
    "--mute-audio",
]

# Common website UI patterns — text hints that identify element types
WEB_PATTERN_DB: Dict[str, List[str]] = {
    "login_form":      ["sign in", "log in", "login", "signin", "email", "password", "username"],
    "signup_form":     ["sign up", "create account", "register", "join", "get started"],
    "search_box":      ["search", "find", "q", "query", "lookup"],
    "submit_button":   ["submit", "send", "go", "continue", "next", "sign in", "log in",
                        "create", "register", "subscribe", "buy", "checkout"],
    "nav_menu":        ["home", "about", "pricing", "features", "contact", "blog", "docs"],
    "cookie_banner":   ["accept", "allow", "agree", "cookies", "gdpr", "privacy", "consent"],
    "modal_close":     ["close", "dismiss", "×", "✕", "cancel", "no thanks"],
    "pagination":      ["next", "previous", "prev", "page", "load more", "show more"],
    "dropdown":        ["select", "choose", "pick", "filter", "sort by"],
    "social_login":    ["google", "facebook", "github", "twitter", "apple", "microsoft"],
}

# ── Data classes ───────────────────────────────────────────────────────────────

@dataclass
class LocatedElement:
    """Result of locating an element on screen."""
    x: int
    y: int
    width: int = 0
    height: int = 0
    confidence: float = 1.0
    method: str = "unknown"        # html | ocr | visual | pattern
    text: str = ""
    selector: str = ""
    element_type: str = ""         # input | button | a | select | ...

    @property
    def center(self) -> Tuple[int, int]:
        return (self.x + self.width // 2, self.y + self.height // 2)


@dataclass
class PageState:
    """Current state of a browser tab/page."""
    url: str = ""
    title: str = ""
    html: str = ""
    screenshot_png: bytes = b""
    cookies: Dict[str, str] = field(default_factory=dict)
    viewport: Tuple[int, int] = (1280, 900)
    debug_port: int = 0


# ── Xvfb manager ──────────────────────────────────────────────────────────────

class XvfbDisplay:
    """Start and manage a virtual X display for headless operation."""

    def __init__(self, display_num: int = 99, size: str = "1280x900x24"):
        self.display_num = display_num
        self.display     = f":{display_num}"
        self.size        = size
        self._proc: Optional[subprocess.Popen] = None

    def start(self) -> str:
        if os.environ.get("DISPLAY"):
            logger.info("[Xvfb] Real display detected: %s", os.environ["DISPLAY"])
            return os.environ["DISPLAY"]
        try:
            self._proc = subprocess.Popen(
                ["Xvfb", self.display, "-screen", "0", self.size, "-ac"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            time.sleep(0.8)
            os.environ["DISPLAY"] = self.display
            logger.info("[Xvfb] Started virtual display %s", self.display)
            return self.display
        except FileNotFoundError:
            logger.warning("[Xvfb] Xvfb not found — running fully headless via Chromium --headless")
            return ""

    def stop(self):
        if self._proc:
            self._proc.terminate()
            self._proc = None
            logger.info("[Xvfb] Stopped")


# ── GhostBrowser — launches Chromium directly, no library ─────────────────────

class GhostBrowser:
    """
    Launches Chromium as a subprocess and drives it via its DevTools HTTP API.
    No Playwright. No CDP library. Pure HTTP + JSON to Chromium's debug port.

    This is Murphy's browser engine — Ghost is the user, Chromium is the screen.
    """

    def __init__(self, headless: bool = True, viewport: Tuple[int, int] = (1280, 900)):
        self.headless    = headless
        self.viewport    = viewport
        self._proc:   Optional[subprocess.Popen] = None
        self._port:   int = 0
        self._xvfb:   Optional[XvfbDisplay] = None
        self._tabs:   Dict[str, PageState] = {}   # tab_id → PageState
        self._lock    = threading.Lock()

    # ── Lifecycle ──────────────────────────────────────────────────────────

    def launch(self) -> "GhostBrowser":
        """Start Chromium. Returns self for chaining."""
        if not self.headless:
            self._xvfb = XvfbDisplay()
            self._xvfb.start()

        # Pick a random free port
        import socket
        s = socket.socket(); s.bind(("", 0)); self._port = s.getsockname()[1]; s.close()

        flags = list(CHROMIUM_FLAGS)
        # Replace port placeholder
        flags = [f.replace("--remote-debugging-port=0", f"--remote-debugging-port={self._port}")
                 for f in flags]
        if not self.headless:
            flags = [f for f in flags if "--headless" not in f]

        flags.append(f"--window-size={self.viewport[0]},{self.viewport[1]}")

        cmd = [CHROMIUM_BIN] + flags + ["about:blank"]
        self._proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        # Wait for debug port
        self._wait_for_port()
        logger.info("[GhostBrowser] Launched Chromium pid=%d port=%d", self._proc.pid, self._port)
        return self

    def _wait_for_port(self, timeout: float = 10.0):
        import socket
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                s = socket.create_connection(("127.0.0.1", self._port), timeout=0.5)
                s.close(); return
            except OSError:
                time.sleep(0.2)
        raise TimeoutError(f"Chromium debug port {self._port} never opened")

    def close(self):
        if self._proc:
            self._proc.terminate()
            try: self._proc.wait(timeout=5)
            except Exception: self._proc.kill()
            self._proc = None
        if self._xvfb:
            self._xvfb.stop()
        logger.info("[GhostBrowser] Closed")

    # ── DevTools HTTP API (no library — pure urllib) ───────────────────────

    def _dt_get(self, path: str) -> Any:
        url = f"http://127.0.0.1:{self._port}{path}"
        with urllib.request.urlopen(url, timeout=10) as r:
            return json.loads(r.read())

    def _dt_post(self, path: str, data: Dict = None) -> Any:
        url = f"http://127.0.0.1:{self._port}{path}"
        body = json.dumps(data or {}).encode()
        req  = urllib.request.Request(url, data=body,
                                       headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read()) if r.length else {}

    def _ws_command(self, tab_id: str, method: str, params: Dict = None) -> Dict:
        """Send a single CDP command via WebSocket and return the result."""
        import websocket  # websocket-client — already in requirements
        ws_url = f"ws://127.0.0.1:{self._port}/devtools/page/{tab_id}"
        ws = websocket.create_connection(ws_url, timeout=15)
        try:
            msg = json.dumps({"id": 1, "method": method, "params": params or {}})
            ws.send(msg)
            # Drain until we get our response (id=1)
            deadline = time.time() + 15
            while time.time() < deadline:
                raw = ws.recv()
                resp = json.loads(raw)
                if resp.get("id") == 1:
                    return resp.get("result", {})
        finally:
            ws.close()
        return {}

    # ── Tab management ─────────────────────────────────────────────────────

    def new_tab(self) -> str:
        tab = self._dt_post("/json/new")
        tab_id = tab.get("id", "")
        self._tabs[tab_id] = PageState(debug_port=self._port)
        return tab_id

    def list_tabs(self) -> List[Dict]:
        return self._dt_get("/json/list")

    def close_tab(self, tab_id: str):
        self._dt_get(f"/json/close/{tab_id}")
        self._tabs.pop(tab_id, None)

    # ── Navigation ─────────────────────────────────────────────────────────

    def navigate(self, tab_id: str, url: str, timeout: float = 20.0) -> PageState:
        self._ws_command(tab_id, "Page.navigate", {"url": url})
        # Wait for load
        deadline = time.time() + timeout
        while time.time() < deadline:
            state = self.get_page_state(tab_id)
            if state.url and url.split("//")[-1].split("/")[0] in state.url:
                break
            time.sleep(0.5)
        return self.get_page_state(tab_id)

    def get_page_state(self, tab_id: str) -> PageState:
        # Get URL + title
        result = self._ws_command(tab_id, "Runtime.evaluate", {
            "expression": "JSON.stringify({url: location.href, title: document.title, html: document.documentElement.outerHTML.substring(0,200000)})",
            "returnByValue": True,
        })
        try:
            val = json.loads(result.get("result", {}).get("value", "{}"))
        except Exception:
            val = {}
        ps = self._tabs.get(tab_id, PageState())
        ps.url   = val.get("url", "")
        ps.title = val.get("title", "")
        ps.html  = val.get("html", "")
        self._tabs[tab_id] = ps
        return ps

    def screenshot(self, tab_id: str) -> bytes:
        result = self._ws_command(tab_id, "Page.captureScreenshot", {
            "format": "png", "captureBeyondViewport": False
        })
        data = result.get("data", "")
        return base64.b64decode(data) if data else b""

    def evaluate(self, tab_id: str, expression: str) -> Any:
        result = self._ws_command(tab_id, "Runtime.evaluate", {
            "expression": expression,
            "returnByValue": True,
            "awaitPromise": True,
        })
        return result.get("result", {}).get("value")

    def get_element_coords(self, tab_id: str, selector: str) -> Optional[Tuple[int,int,int,int]]:
        """Get (x, y, width, height) of a CSS selector via JS."""
        expr = f"""
        (function() {{
            var el = document.querySelector({json.dumps(selector)});
            if (!el) return null;
            var r = el.getBoundingClientRect();
            return {{x: Math.round(r.left), y: Math.round(r.top),
                     w: Math.round(r.width), h: Math.round(r.height)}};
        }})()
        """
        result = self._ws_command(tab_id, "Runtime.evaluate", {
            "expression": expr, "returnByValue": True
        })
        val = result.get("result", {}).get("value")
        if val:
            return (val["x"], val["y"], val["w"], val["h"])
        return None

    def click_selector(self, tab_id: str, selector: str) -> bool:
        coords = self.get_element_coords(tab_id, selector)
        if coords:
            x, y, w, h = coords
            cx, cy = x + w // 2, y + h // 2
            self._ws_command(tab_id, "Input.dispatchMouseEvent", {
                "type": "mousePressed", "x": cx, "y": cy,
                "button": "left", "clickCount": 1
            })
            self._ws_command(tab_id, "Input.dispatchMouseEvent", {
                "type": "mouseReleased", "x": cx, "y": cy,
                "button": "left", "clickCount": 1
            })
            return True
        return False

    def fill_selector(self, tab_id: str, selector: str, value: str) -> bool:
        coords = self.get_element_coords(tab_id, selector)
        if coords:
            x, y, w, h = coords
            cx, cy = x + w // 2, y + h // 2
            # Focus the element first
            self._ws_command(tab_id, "Input.dispatchMouseEvent", {
                "type": "mousePressed", "x": cx, "y": cy, "button": "left", "clickCount": 1
            })
            self._ws_command(tab_id, "Input.dispatchMouseEvent", {
                "type": "mouseReleased", "x": cx, "y": cy, "button": "left", "clickCount": 1
            })
            # Clear and type
            self.evaluate(tab_id, f"document.querySelector({json.dumps(selector)}).value = ''")
            for ch in value:
                self._ws_command(tab_id, "Input.dispatchKeyEvent", {
                    "type": "keyDown", "text": ch
                })
                self._ws_command(tab_id, "Input.dispatchKeyEvent", {
                    "type": "keyUp", "text": ch
                })
            return True
        return False


# ── OCR locator ───────────────────────────────────────────────────────────────

class OCRLocator:
    """Find elements on screen by text using pytesseract."""

    def __init__(self):
        self._available = False
        try:
            import pytesseract
            self._available = True
        except ImportError:
            logger.warning("[OCR] pytesseract not available")

    def find_text(self, png_bytes: bytes, text: str,
                  confidence_threshold: int = 60) -> Optional[LocatedElement]:
        """Find text in a screenshot. Returns LocatedElement with screen coords."""
        if not self._available or not png_bytes:
            return None
        try:
            import pytesseract
            from PIL import Image
            img = Image.open(io.BytesIO(png_bytes))
            data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
            text_lower = text.lower().strip()
            for i, word in enumerate(data["text"]):
                if not word: continue
                conf = int(data["conf"][i])
                if conf < confidence_threshold: continue
                if text_lower in word.lower():
                    x = data["left"][i]
                    y = data["top"][i]
                    w = data["width"][i]
                    h = data["height"][i]
                    return LocatedElement(
                        x=x, y=y, width=w, height=h,
                        confidence=conf/100.0,
                        method="ocr",
                        text=word,
                    )
        except Exception as e:
            logger.warning("[OCR] find_text failed: %s", e)
        return None

    def extract_all_text(self, png_bytes: bytes) -> str:
        """Extract all visible text from screenshot."""
        if not self._available or not png_bytes:
            return ""
        try:
            import pytesseract
            from PIL import Image
            img = Image.open(io.BytesIO(png_bytes))
            return pytesseract.image_to_string(img)
        except Exception as e:
            logger.warning("[OCR] extract_all_text failed: %s", e)
            return ""


# ── Visual pattern recognizer ─────────────────────────────────────────────────

class VisualPatternRecognizer:
    """
    Identifies UI element types in screenshots using a lightweight
    transformers zero-shot image classifier.

    Uses CLIP (openai/clip-vit-base-patch32) — 600MB, runs on CPU,
    no GPU required. Loaded lazily on first use.
    """

    # UI element types we can recognize
    ELEMENT_LABELS = [
        "a login form with email and password fields",
        "a search input box",
        "a navigation menu bar",
        "a submit or call-to-action button",
        "a cookie consent banner",
        "a modal dialog popup",
        "a dropdown select menu",
        "a text input field",
        "a checkbox or radio button",
        "a sign up registration form",
        "a pricing table",
        "a product card",
        "an error message or alert",
        "a loading spinner",
        "a social login button (Google, Facebook, GitHub)",
    ]

    def __init__(self):
        self._pipe = None
        self._lock = threading.Lock()
        self._loaded = False

    def _load(self):
        with self._lock:
            if self._loaded:
                return
            try:
                from transformers import pipeline
                logger.info("[Vision] Loading CLIP model (first use, may take ~10s)...")
                self._pipe = pipeline(
                    "zero-shot-image-classification",
                    model="openai/clip-vit-base-patch32",
                    device=-1,  # CPU
                )
                self._loaded = True
                logger.info("[Vision] CLIP model loaded")
            except Exception as e:
                logger.warning("[Vision] Could not load CLIP: %s", e)
                self._loaded = True  # don't retry

    def classify_screenshot(self, png_bytes: bytes,
                             candidate_labels: Optional[List[str]] = None) -> List[Dict]:
        """Classify what UI elements are visible in a screenshot.
        Returns list of {label, score} sorted by score desc."""
        self._load()
        if not self._pipe or not png_bytes:
            return []
        try:
            from PIL import Image
            img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
            labels = candidate_labels or self.ELEMENT_LABELS
            result = self._pipe(img, candidate_labels=labels)
            return sorted(result, key=lambda x: x["score"], reverse=True)
        except Exception as e:
            logger.warning("[Vision] classify failed: %s", e)
            return []

    def identify_page_type(self, png_bytes: bytes) -> str:
        """High-level: what kind of page is this?"""
        results = self.classify_screenshot(png_bytes, [
            "a login page", "a sign up page", "a home page",
            "a product page", "a dashboard", "a search results page",
            "a checkout page", "an article or blog post",
            "a settings page", "an error page",
        ])
        return results[0]["label"] if results else "unknown"


# ── GhostVision — the unified locator ────────────────────────────────────────

class GhostVision:
    """
    Unified element locator for GhostController web automation.

    Locator pipeline (tries each stage in order, returns first hit):
      1. CSS/DOM    — get_element_coords() via JS in Chromium (exact, fast)
      2. Text/role  — find by visible text, placeholder, label, ARIA role
      3. OCR        — screenshot + pytesseract text search
      4. Pattern DB — match against known website UI patterns
      5. Visual     — CLIP zero-shot image classification (slowest, most general)

    Usage:
        vision = GhostVision(browser, tab_id)
        el = vision.locate("#submit-btn")
        el = vision.locate("Sign In")          # text search
        el = vision.locate("role:button:Submit")
        el = vision.locate("placeholder:Email")
        el = vision.locate("label:Password")
    """

    def __init__(self, browser: GhostBrowser, tab_id: str):
        self._browser = browser
        self._tab_id  = tab_id
        self._ocr     = OCRLocator()
        self._vision  = VisualPatternRecognizer()
        self._page_cache: Optional[PageState] = None
        self._shot_cache: Optional[bytes]     = None

    def _get_page(self) -> PageState:
        if not self._page_cache:
            self._page_cache = self._browser.get_page_state(self._tab_id)
        return self._page_cache

    def _get_screenshot(self) -> bytes:
        if not self._shot_cache:
            self._shot_cache = self._browser.screenshot(self._tab_id)
        return self._shot_cache

    def invalidate_cache(self):
        self._page_cache = None
        self._shot_cache = None

    def locate(self, query: str, timeout_ms: int = 10000) -> Optional[LocatedElement]:
        """
        Locate an element on the current page.

        Query formats:
          #id                   CSS id selector
          .class                CSS class selector
          tag[attr=val]         Any CSS selector
          text:Sign In          Find by visible text
          placeholder:Email     Find by input placeholder
          label:Password        Find by associated label
          role:button:Submit    Find by ARIA role + name
          pattern:submit_button Find by web pattern DB
          ocr:Accept Cookies    Force OCR search
        """
        query = query.strip()

        # ── Stage 1: CSS selector via JS ──────────────────────────────────
        if query.startswith(("#", ".", "[")) or re.match(r"^[a-z]+[\[#\.\s>+~]", query):
            coords = self._browser.get_element_coords(self._tab_id, query)
            if coords:
                x, y, w, h = coords
                return LocatedElement(x=x, y=y, width=w, height=h,
                                       method="css", selector=query,
                                       confidence=1.0)

        # ── Stage 2a: text: prefix ────────────────────────────────────────
        if query.startswith("text:"):
            text = query[5:]
            return self._find_by_text(text)

        # ── Stage 2b: placeholder: prefix ────────────────────────────────
        if query.startswith("placeholder:"):
            ph = query[12:]
            sel = f"[placeholder*='{ph}']"
            coords = self._browser.get_element_coords(self._tab_id, sel)
            if coords:
                x, y, w, h = coords
                return LocatedElement(x=x, y=y, width=w, height=h,
                                       method="html", selector=sel, confidence=0.95)

        # ── Stage 2c: label: prefix ───────────────────────────────────────
        if query.startswith("label:"):
            lbl = query[6:]
            el = self._find_by_label(lbl)
            if el: return el

        # ── Stage 2d: role: prefix ────────────────────────────────────────
        if query.startswith("role:"):
            parts = query[5:].split(":", 1)
            role = parts[0]
            name = parts[1] if len(parts) > 1 else ""
            el = self._find_by_role(role, name)
            if el: return el

        # ── Stage 2e: pattern: prefix ─────────────────────────────────────
        if query.startswith("pattern:"):
            pattern = query[8:]
            el = self._find_by_pattern(pattern)
            if el: return el

        # ── Stage 3: OCR ──────────────────────────────────────────────────
        if query.startswith("ocr:"):
            text = query[4:]
            shot = self._get_screenshot()
            return self._ocr.find_text(shot, text)

        # ── Fallback: try as plain text search ────────────────────────────
        el = self._find_by_text(query)
        if el: return el

        # ── Stage 4: OCR fallback ─────────────────────────────────────────
        shot = self._get_screenshot()
        if shot:
            el = self._ocr.find_text(shot, query)
            if el: return el

        # ── Stage 5: Visual pattern (CLIP) ────────────────────────────────
        if shot:
            classifications = self._vision.classify_screenshot(shot)
            logger.debug("[GhostVision] Visual classify: %s", classifications[:3])
            # Can't pinpoint coordinates from whole-page classification alone
            # — return None, caller should try a more specific query
        return None

    def _find_by_text(self, text: str) -> Optional[LocatedElement]:
        """Find element by its visible text content via JS."""
        expr = f"""
        (function() {{
            var needle = {json.dumps(text.lower())};
            var all = document.querySelectorAll('button,a,input,label,span,div,h1,h2,h3,p,li');
            for (var i=0; i<all.length; i++) {{
                var el = all[i];
                var t = (el.textContent || el.value || el.placeholder || el.innerText || '').toLowerCase().trim();
                if (t.includes(needle) || needle.includes(t) && t.length > 2) {{
                    var r = el.getBoundingClientRect();
                    if (r.width > 0 && r.height > 0) {{
                        return {{x: Math.round(r.left), y: Math.round(r.top),
                                 w: Math.round(r.width), h: Math.round(r.height),
                                 tag: el.tagName.toLowerCase(),
                                 text: el.textContent.trim().substring(0,80)}};
                    }}
                }}
            }}
            return null;
        }})()
        """
        result = self._browser._ws_command(self._tab_id, "Runtime.evaluate", {
            "expression": expr, "returnByValue": True
        })
        val = result.get("result", {}).get("value")
        if val:
            return LocatedElement(
                x=val["x"], y=val["y"], width=val["w"], height=val["h"],
                method="text", text=val.get("text", ""),
                element_type=val.get("tag", ""),
                confidence=0.9,
            )
        return None

    def _find_by_label(self, label_text: str) -> Optional[LocatedElement]:
        """Find input associated with a label."""
        expr = f"""
        (function() {{
            var needle = {json.dumps(label_text.lower())};
            var labels = document.querySelectorAll('label');
            for (var i=0; i<labels.length; i++) {{
                var lbl = labels[i];
                if (lbl.textContent.toLowerCase().includes(needle)) {{
                    var target = lbl.control || document.getElementById(lbl.htmlFor);
                    var el = target || lbl;
                    var r = el.getBoundingClientRect();
                    if (r.width > 0) return {{x: Math.round(r.left), y: Math.round(r.top),
                                              w: Math.round(r.width), h: Math.round(r.height)}};
                }}
            }}
            return null;
        }})()
        """
        result = self._browser._ws_command(self._tab_id, "Runtime.evaluate", {
            "expression": expr, "returnByValue": True
        })
        val = result.get("result", {}).get("value")
        if val:
            return LocatedElement(
                x=val["x"], y=val["y"], width=val["w"], height=val["h"],
                method="label", text=label_text, confidence=0.92,
            )
        return None

    def _find_by_role(self, role: str, name: str = "") -> Optional[LocatedElement]:
        """Find element by ARIA role and optional accessible name."""
        name_filter = f"&& (el.textContent.toLowerCase().includes({json.dumps(name.lower())}) || (el.getAttribute('aria-label')||'').toLowerCase().includes({json.dumps(name.lower())}))" if name else ""
        expr = f"""
        (function() {{
            var all = document.querySelectorAll('[role="{role}"],{role}');
            for (var i=0; i<all.length; i++) {{
                var el = all[i];
                {name_filter and f'if (!({name_filter.strip("&& ")})) continue;'}
                var r = el.getBoundingClientRect();
                if (r.width > 0) return {{x: Math.round(r.left), y: Math.round(r.top),
                                          w: Math.round(r.width), h: Math.round(r.height),
                                          text: el.textContent.trim().substring(0,80)}};
            }}
            return null;
        }})()
        """
        result = self._browser._ws_command(self._tab_id, "Runtime.evaluate", {
            "expression": expr, "returnByValue": True
        })
        val = result.get("result", {}).get("value")
        if val:
            return LocatedElement(
                x=val["x"], y=val["y"], width=val["w"], height=val["h"],
                method="role", text=val.get("text",""), confidence=0.88,
            )
        return None

    def _find_by_pattern(self, pattern_name: str) -> Optional[LocatedElement]:
        """Find element using WebPatternDB hints."""
        hints = WEB_PATTERN_DB.get(pattern_name, [])
        for hint in hints:
            el = self._find_by_text(hint)
            if el:
                el.method = "pattern"
                return el
        return None

    def identify_page(self) -> Dict[str, Any]:
        """Full page analysis — what type of page, what elements are present."""
        shot = self._get_screenshot()
        page = self._get_page()
        page_type = self._vision.identify_page_type(shot) if shot else "unknown"
        ocr_text  = self._ocr.extract_all_text(shot) if shot else ""
        patterns_found = []
        for pattern, hints in WEB_PATTERN_DB.items():
            for hint in hints:
                if hint in ocr_text.lower() or hint in page.html.lower():
                    patterns_found.append(pattern)
                    break
        return {
            "url":           page.url,
            "title":         page.title,
            "page_type":     page_type,
            "patterns":      list(set(patterns_found)),
            "ocr_text":      ocr_text[:2000],
        }
    def get_captcha_engine(self, capsolver_key: str = None,
                            two_captcha_key: str = None) -> "CaptchaEngine":
        """Get or create a CaptchaEngine for this page.

        Lazily initialised — only created when a CAPTCHA is detected.
        Pass capsolver_key or two_captcha_key to enable token API solving.
        Also reads CAPSOLVER_API_KEY / TWO_CAPTCHA_KEY env vars automatically.
        """
        if not hasattr(self, '_captcha_engine') or self._captcha_engine is None:
            try:
                from src.murphy_captcha import CaptchaEngine
            except ImportError:
                from murphy_captcha import CaptchaEngine
            self._captcha_engine = CaptchaEngine(
                browser=self._browser,
                tab_id=self._tab_id,
                capsolver_key=capsolver_key,
                two_captcha_key=two_captcha_key,
            )
        return self._captcha_engine

    async def handle_captcha(self, page: Any = None,
                              capsolver_key: str = None,
                              two_captcha_key: str = None) -> "CaptchaResult":
        """Detect and handle any CAPTCHA on the current page.

        Called automatically by GhostPageHandle before every navigation.
        Also callable manually from MCB actions.

        Returns CaptchaResult with .resolved, .type, .strategy, .notes.
        """
        try:
            from src.murphy_captcha import CaptchaDetector
        except ImportError:
            from murphy_captcha import CaptchaDetector
        ps = self._get_page()
        html = ps.html or ""
        if not html:
            ps = self._browser.get_page_state(self._tab_id)
            html = ps.html
        detector = CaptchaDetector()
        ctype = detector.detect(html, ps.url)
        if ctype.value == "none":
            try:
                from src.murphy_captcha import CaptchaResult, CaptchaType
            except ImportError:
                from murphy_captcha import CaptchaResult, CaptchaType
            return CaptchaResult(detected=False)
        logger.info("[GhostVision] CAPTCHA detected: %s — invoking engine", ctype.value)
        engine = self.get_captcha_engine(capsolver_key, two_captcha_key)
        return await engine.handle(html, ps.url, page)

