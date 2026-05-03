"""
Murphy Visual Inspector — PATCH-161b
Playwright-based screenshot + page audit engine.
All functions are async-native — call with await from FastAPI handlers.
"""
import asyncio, base64, io, json, time, os, re
from pathlib import Path
from typing import Optional, List

_SNAP_DIR = Path("/var/lib/murphy-production/snapshots")
_SNAP_DIR.mkdir(parents=True, exist_ok=True)

PLAYWRIGHT_ARGS = [
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--disable-extensions",
]

BASE_URL = os.environ.get("MURPHY_BASE_URL", "https://murphy.systems")


async def screenshot_url(url: str, full_page: bool = False, width: int = 1280,
                          height: int = 900, session_token: str = "") -> dict:
    """Take a screenshot of a URL. Async — await this from FastAPI handlers."""
    from playwright.async_api import async_playwright
    start = time.time()
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=PLAYWRIGHT_ARGS)
        ctx_kwargs = {"viewport": {"width": width, "height": height}}
        if session_token:
            domain = url.split("/")[2].split(":")[0]
            ctx_kwargs["storage_state"] = {
                "cookies": [{
                    "name": "murphy_session",
                    "value": session_token,
                    "domain": domain,
                    "path": "/",
                    "httpOnly": True,
                    "secure": url.startswith("https"),
                }]
            }
        ctx = await browser.new_context(**ctx_kwargs)
        page = await ctx.new_page()
        js_errors = []
        page.on("console", lambda m: js_errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: js_errors.append(str(e)))
        try:
            resp = await page.goto(url, wait_until="networkidle", timeout=30000)
            http_status = resp.status if resp else 0
            title = await page.title()
            broken_imgs = await page.eval_on_selector_all(
                "img",
                "els => els.filter(e => !e.complete || e.naturalWidth === 0).map(e => e.src)"
            )
            png = await page.screenshot(full_page=full_page)
            b64 = base64.b64encode(png).decode()
            slug = re.sub(r"[^a-z0-9]", "_", url.lower())[-40:]
            ts = int(time.time())
            snap_path = _SNAP_DIR / f"{ts}_{slug}.png"
            snap_path.write_bytes(png)
        finally:
            await browser.close()
    return {
        "url": url,
        "status": http_status,
        "title": title,
        "duration_s": round(time.time() - start, 2),
        "full_page": full_page,
        "png_b64": b64,
        "snap_path": str(snap_path),
        "snap_filename": snap_path.name,
        "js_errors": js_errors[:10],
        "broken_images": broken_imgs[:10],
        "size_kb": round(len(png) / 1024, 1),
    }


async def audit_pages(pages: List[str], session_token: str = "") -> List[dict]:
    """Screenshot multiple pages concurrently (max 3 at a time)."""
    sem = asyncio.Semaphore(3)
    async def bounded(url: str) -> dict:
        async with sem:
            try:
                return await screenshot_url(url, session_token=session_token)
            except Exception as e:
                return {"url": url, "error": str(e), "status": 0}
    return list(await asyncio.gather(*[bounded(u) for u in pages]))


MURPHY_PAGES = [
    "/",
    "/login",
    "/ui/terminal-unified",
    "/ui/game-studio",
    "/ui/matrix-chat",
    "/ui/compliance",
    "/ui/roi-calendar",
    "/ui/ambient",
    "/ui/trading",
    "/ui/robotics",
    "/ui/onboarding",
    "/ui/workflow-builder",
]
