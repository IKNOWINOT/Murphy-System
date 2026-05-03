"""
Murphy Visual Inspector — PATCH-161
Playwright-based screenshot + page audit engine.
Murphy can photograph any of its own pages and analyze them.
"""
import asyncio, base64, io, json, time, os, re
from pathlib import Path
from typing import Optional

_SNAP_DIR = Path("/var/lib/murphy-production/snapshots")
_SNAP_DIR.mkdir(parents=True, exist_ok=True)

PLAYWRIGHT_ARGS = [
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--disable-extensions",
    "--disable-background-networking",
]

BASE_URL = os.environ.get("MURPHY_BASE_URL", "https://murphy.systems")
INTERNAL_URL = "http://127.0.0.1:8000"


async def _screenshot_url(url: str, full_page: bool = False, width: int = 1280,
                           height: int = 900, session_token: str = "") -> dict:
    """Take a screenshot of a URL, optionally injecting a session cookie."""
    from playwright.async_api import async_playwright
    start = time.time()
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=PLAYWRIGHT_ARGS)
        ctx_kwargs = {"viewport": {"width": width, "height": height}}
        if session_token:
            ctx_kwargs["storage_state"] = {
                "cookies": [{
                    "name": "murphy_session",
                    "value": session_token,
                    "domain": url.split("/")[2].split(":")[0],
                    "path": "/",
                    "httpOnly": True,
                    "secure": url.startswith("https"),
                }]
            }
        ctx = await browser.new_context(**ctx_kwargs)
        page = await ctx.new_page()
        # Capture JS console errors
        errors = []
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(str(e)))
        try:
            resp = await page.goto(url, wait_until="networkidle", timeout=30000)
            status = resp.status if resp else 0
            title = await page.title()
            # Check for broken elements
            broken_imgs = await page.eval_on_selector_all(
                "img", "els => els.filter(e=>!e.complete||e.naturalWidth===0).map(e=>e.src)"
            )
            png = await page.screenshot(full_page=full_page)
            b64 = base64.b64encode(png).decode()
            # Save to disk
            slug = re.sub(r"[^a-z0-9]", "_", url.lower())[-40:]
            ts = int(time.time())
            snap_path = _SNAP_DIR / f"{ts}_{slug}.png"
            snap_path.write_bytes(png)
        finally:
            await browser.close()
        return {
            "url": url,
            "status": status,
            "title": title,
            "duration_s": round(time.time() - start, 2),
            "full_page": full_page,
            "png_b64": b64,
            "snap_path": str(snap_path),
            "js_errors": errors[:10],
            "broken_images": broken_imgs[:10],
            "size_kb": round(len(png) / 1024, 1),
        }


def screenshot_url(url: str, full_page: bool = False, session_token: str = "") -> dict:
    """Sync wrapper."""
    return asyncio.run(_screenshot_url(url, full_page=full_page, session_token=session_token))


async def _audit_pages(pages: list, session_token: str = "") -> list:
    """Screenshot multiple pages concurrently (max 3 at a time)."""
    import asyncio
    sem = asyncio.Semaphore(3)
    async def bounded(url):
        async with sem:
            try:
                return await _screenshot_url(url, session_token=session_token)
            except Exception as e:
                return {"url": url, "error": str(e)}
    return await asyncio.gather(*[bounded(u) for u in pages])


def audit_pages(pages: list, session_token: str = "") -> list:
    return asyncio.run(_audit_pages(pages, session_token=session_token))


# All Murphy UI pages
MURPHY_PAGES = [
    "/",
    "/login",
    "/ui/terminal-unified",
    "/ui/game-studio",
    "/ui/matrix-chat",
    "/ui/org-chart",
    "/ui/compliance",
    "/ui/roi-calendar",
    "/ui/forge",
    "/ui/ambient",
    "/ui/trading",
    "/ui/robotics",
    "/ui/onboarding",
    "/ui/workflow-builder",
    "/ui/swarm-status",
]


def audit_all_murphy_pages(session_token: str = "") -> dict:
    """Screenshot all Murphy UI pages and return a summary audit."""
    urls = [f"{BASE_URL}{p}" for p in MURPHY_PAGES]
    results = audit_pages(urls, session_token=session_token)
    summary = {
        "total": len(results),
        "ok": sum(1 for r in results if r.get("status") == 200 and not r.get("error")),
        "errors": sum(1 for r in results if r.get("error") or r.get("status", 0) >= 400),
        "js_error_pages": [r["url"] for r in results if r.get("js_errors")],
        "broken_image_pages": [r["url"] for r in results if r.get("broken_images")],
        "pages": results,
    }
    return summary
