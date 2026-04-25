"""
Murphy Web Tool — PATCH-079b
Real internet tool use: web search, page fetch, screenshot, form fill.

Provides a unified interface for Murphy to act as a user on the internet:
  search(query)          → DuckDuckGo results (no API key needed)
  fetch(url)             → page text via requests + bs4
  screenshot(url)        → PNG bytes via Playwright headless
  fill_and_submit(url, selectors, values) → form automation via Playwright

All functions are sync-safe and import-guarded — degrade gracefully
if a dep is missing. All exceptions are logged, never silently swallowed.

PATCH-079b | Label: WEB-TOOL-001
Copyright © 2020-2026 Inoni LLC
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Search ────────────────────────────────────────────────────────────────────

def search(query: str, max_results: int = 8) -> List[Dict[str, str]]:
    """
    Run a DuckDuckGo web search. Returns list of {title, url, snippet}.
    No API key required. Uses duckduckgo_search package.
    """
    try:
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "snippet": r.get("body", "")[:300],
                })
        logger.info("WEB-TOOL: search(%r) → %d results", query, len(results))
        return results
    except Exception as exc:
        logger.error("WEB-TOOL: search failed: %s", exc)
        return [{"title": "search_error", "url": "", "snippet": str(exc)}]


# ── Fetch page text ───────────────────────────────────────────────────────────

def fetch(url: str, timeout: int = 20) -> Dict[str, Any]:
    """
    Fetch a URL and return extracted text + metadata.
    Uses requests + BeautifulSoup. Returns:
      {ok, url, title, text, links, status_code}
    """
    try:
        import requests
        from bs4 import BeautifulSoup

        headers = {
            "User-Agent": "Mozilla/5.0 (Murphy/1.0; +https://murphy.systems) AppleWebKit/537.36"
        }
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        # Remove noise
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        title = soup.title.string.strip() if soup.title else ""
        text = " ".join(soup.get_text(separator=" ").split())[:8000]
        links = [a.get("href") for a in soup.find_all("a", href=True)][:20]

        logger.info("WEB-TOOL: fetch(%s) → %d chars title=%r", url, len(text), title[:40])
        return {
            "ok": True, "url": url, "title": title,
            "text": text, "links": links, "status_code": resp.status_code,
        }
    except Exception as exc:
        logger.error("WEB-TOOL: fetch(%s) failed: %s", url, exc)
        return {"ok": False, "url": url, "error": str(exc), "text": "", "links": []}


# ── Screenshot ────────────────────────────────────────────────────────────────

def screenshot(url: str, timeout: int = 20) -> Dict[str, Any]:
    """
    Take a full-page screenshot of a URL via Playwright headless Chromium.
    Returns {ok, url, png_bytes (base64), width, height}.
    """
    try:
        import base64
        import threading

        result_box = {}

        def _capture_sync():
            from playwright.sync_api import sync_playwright
            with sync_playwright() as pw:
                browser = pw.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-setuid-sandbox"],
                )
                page = browser.new_page(viewport={"width": 1280, "height": 900})
                page.goto(url, wait_until="networkidle", timeout=timeout * 1000)
                png = page.screenshot(full_page=True)
                browser.close()
                result_box["png"] = png

        # Run in dedicated thread to avoid event-loop conflicts with uvicorn
        t = threading.Thread(target=_capture_sync, daemon=True)
        t.start()
        t.join(timeout=timeout + 5)
        if "png" not in result_box:
            raise TimeoutError(f"screenshot timed out after {timeout}s")

        png_bytes = result_box["png"]
        encoded = base64.b64encode(png_bytes).decode()
        logger.info("WEB-TOOL: screenshot(%s) → %d bytes", url, len(png_bytes))
        return {"ok": True, "url": url, "png_b64": encoded,
                "size_bytes": len(png_bytes)}
    except Exception as exc:
        logger.error("WEB-TOOL: screenshot(%s) failed: %s", url, exc)
        return {"ok": False, "url": url, "error": str(exc)}


# ── Form automation ───────────────────────────────────────────────────────────

def fill_and_submit(
    url: str,
    fields: Dict[str, str],      # {css_selector: value}
    submit_selector: str = "",
    wait_after_ms: int = 2000,
    timeout: int = 30,
) -> Dict[str, Any]:
    """
    Navigate to url, fill form fields, optionally click submit, return result page text.
    fields = {"#email": "user@example.com", "#password": "secret"}
    submit_selector = "button[type=submit]"
    """
    try:
        result_box = {}

        def _fill_sync():
            from playwright.sync_api import sync_playwright
            with sync_playwright() as pw:
                browser = pw.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-setuid-sandbox"],
                )
                page = browser.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)
                for selector, value in fields.items():
                    try:
                        page.fill(selector, value)
                        logger.debug("WEB-TOOL: filled %s", selector)
                    except Exception as fe:
                        logger.warning("WEB-TOOL: fill(%s) failed: %s", selector, fe)
                if submit_selector:
                    page.click(submit_selector)
                    page.wait_for_timeout(wait_after_ms)
                result_box["text"] = page.inner_text("body")[:4000]
                result_box["png"] = page.screenshot()
                browser.close()

        t = threading.Thread(target=_fill_sync, daemon=True)
        t.start()
        t.join(timeout=timeout + 5)
        text = result_box.get("text", "")
        png = result_box.get("png", b"")
        import base64
        logger.info("WEB-TOOL: fill_and_submit(%s) → result %d chars", url, len(text))
        return {"ok": True, "url": url, "result_text": text,
                "screenshot_b64": base64.b64encode(png).decode()}
    except Exception as exc:
        logger.error("WEB-TOOL: fill_and_submit(%s) failed: %s", url, exc)
        return {"ok": False, "url": url, "error": str(exc)}
