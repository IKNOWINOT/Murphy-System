"""
Murphy Web Tool — PATCH-090a
Real internet tool use: web search, page fetch, screenshot, form fill.

ALL browser operations go through MultiCursorBrowser (MCB).
Playwright is the transport underneath MCB — never called directly here.

  search(query)                          → DuckDuckGo results (no browser needed)
  fetch(url)                             → page text via requests + bs4 (no browser needed)
  screenshot(url)                        → PNG via MCB single-zone session
  fill_and_submit(url, fields, submit)   → form automation via MCB

PATCH-090a | Label: WEB-TOOL-002
Copyright © 2020-2026 Inoni LLC
"""
from __future__ import annotations

import asyncio
import base64
import logging
import threading
import uuid
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Internal: run an async MCB coroutine from sync context ───────────────

def _run_mcb(coro) -> Any:
    """Run an async MCB coroutine safely from a sync caller.

    Handles the case where uvicorn already owns an event loop —
    spins a new loop in a dedicated daemon thread in that case.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # We're inside uvicorn — run in a fresh thread with its own loop
            result_box: Dict = {}
            exc_box: Dict = {}

            def _thread():
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    result_box["v"] = new_loop.run_until_complete(coro)
                except Exception as e:
                    exc_box["e"] = e
                finally:
                    new_loop.close()

            t = threading.Thread(target=_thread, daemon=True)
            t.start()
            t.join(timeout=60)
            if "e" in exc_box:
                raise exc_box["e"]
            return result_box.get("v")
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


# ── Search ────────────────────────────────────────────────────────────────

def search(query: str, max_results: int = 8) -> List[Dict[str, str]]:
    """DuckDuckGo search — no browser needed, uses ddgs HTTP API."""
    try:
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append({
                    "title":   r.get("title", ""),
                    "url":     r.get("href", ""),
                    "snippet": r.get("body", "")[:300],
                })
        logger.info("WEB-TOOL: search(%r) → %d results", query, len(results))
        return results
    except Exception as exc:
        logger.error("WEB-TOOL: search failed: %s", exc)
        return [{"title": "search_error", "url": "", "snippet": str(exc)}]


# ── Fetch page text ───────────────────────────────────────────────────────

def fetch(url: str, timeout: int = 20) -> Dict[str, Any]:
    """Fetch URL and return text via requests + BeautifulSoup (no browser needed)."""
    try:
        import requests
        from bs4 import BeautifulSoup

        headers = {
            "User-Agent": "Mozilla/5.0 (Murphy/1.0; +https://murphy.systems) "
                          "AppleWebKit/537.36"
        }
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        title = soup.title.string.strip() if soup.title else ""
        text  = " ".join(soup.get_text(separator=" ").split())[:8000]
        links = [a.get("href") for a in soup.find_all("a", href=True)][:20]
        logger.info("WEB-TOOL: fetch(%s) → %d chars", url, len(text))
        return {
            "ok": True, "url": url, "title": title,
            "text": text, "links": links, "status_code": resp.status_code,
        }
    except Exception as exc:
        logger.error("WEB-TOOL: fetch(%s) failed: %s", url, exc)
        return {"ok": False, "url": url, "error": str(exc), "text": "", "links": []}


# ── Screenshot via MCB ────────────────────────────────────────────────────

def screenshot(url: str, timeout: int = 20) -> Dict[str, Any]:
    """Screenshot a URL through a single-zone MCB session.

    MCB manages the Playwright browser — no direct Playwright calls here.
    """
    async def _do():
        from src.agent_module_loader import MultiCursorBrowser
        mcb = MultiCursorBrowser(headless=True)
        try:
            await mcb.launch()
            zones = mcb.auto_layout(1)
            zone_id = zones[0]["zone_id"]
            await mcb.navigate(zone_id, url)
            result = await mcb.screenshot(zone_id)
            png_bytes = result.data.get("png_bytes") or result.data.get("png") or b""
            encoded = base64.b64encode(png_bytes).decode() if png_bytes else ""
            logger.info("WEB-TOOL: screenshot(%s) via MCB → %d bytes", url, len(png_bytes))
            return {
                "ok":        True,
                "url":       url,
                "png_b64":   encoded,
                "size_bytes": len(png_bytes),
                "zone_id":   zone_id,
            }
        except Exception as exc:
            logger.error("WEB-TOOL: screenshot(%s) MCB failed: %s", url, exc)
            return {"ok": False, "url": url, "error": str(exc)}
        finally:
            try:
                await mcb.close()
            except Exception:
                pass

    return _run_mcb(_do())


# ── Form fill + submit via MCB ────────────────────────────────────────────

def fill_and_submit(
    url: str,
    fields: Dict[str, str],
    submit_selector: str = "",
    wait_after_ms: int = 2000,
    timeout: int = 30,
) -> Dict[str, Any]:
    """Navigate, fill fields, optionally submit — all through MCB.

    fields = {"#email": "user@example.com", "#password": "secret"}
    submit_selector = "button[type=submit]"
    """
    async def _do():
        from src.agent_module_loader import MultiCursorBrowser
        mcb = MultiCursorBrowser(headless=True)
        try:
            await mcb.launch()
            zones = mcb.auto_layout(1)
            zone_id = zones[0]["zone_id"]

            await mcb.navigate(zone_id, url)

            for selector, value in fields.items():
                try:
                    await mcb.fill(zone_id, selector, value)
                    logger.debug("WEB-TOOL: filled %s", selector)
                except Exception as fe:
                    logger.warning("WEB-TOOL: fill(%s) failed: %s", selector, fe)

            if submit_selector:
                await mcb.click(zone_id, submit_selector)
                await mcb._get_page(zone_id)  # ensure page reference is live
                # wait for navigation / reaction
                await asyncio.sleep(wait_after_ms / 1000)

            text_result = await mcb.get_text(zone_id, "body")
            text = text_result.data.get("text", "")[:4000]

            shot_result = await mcb.screenshot(zone_id)
            png_bytes   = shot_result.data.get("png_bytes") or shot_result.data.get("png") or b""
            encoded     = base64.b64encode(png_bytes).decode() if png_bytes else ""

            logger.info("WEB-TOOL: fill_and_submit(%s) → %d chars", url, len(text))
            return {
                "ok":             True,
                "url":            url,
                "result_text":    text,
                "screenshot_b64": encoded,
                "zone_id":        zone_id,
            }
        except Exception as exc:
            logger.error("WEB-TOOL: fill_and_submit(%s) failed: %s", url, exc)
            return {"ok": False, "url": url, "error": str(exc)}
        finally:
            try:
                await mcb.close()
            except Exception:
                pass

    return _run_mcb(_do())
