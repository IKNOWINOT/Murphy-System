"""
Web Tool Router — PATCH-079c
Exposes Murphy's internet tool use as REST endpoints.

  POST /api/web/search    — web search
  POST /api/web/fetch     — fetch + extract page text
  POST /api/web/screenshot — headless screenshot (returns base64 PNG)
  POST /api/web/fill      — form fill + submit automation

PATCH-079c | Label: WEB-ROUTER-001
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, HttpUrl

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/web", tags=["web"])


class SearchRequest(BaseModel):
    query: str
    max_results: int = 8

class FetchRequest(BaseModel):
    url: str
    timeout: int = 12

class ScreenshotRequest(BaseModel):
    url: str
    timeout: int = 20

class FillRequest(BaseModel):
    url: str
    fields: Dict[str, str]
    submit_selector: str = ""
    wait_after_ms: int = 2000


@router.post("/search")
async def web_search(req: SearchRequest):
    """DuckDuckGo web search — no API key required."""
    try:
        from src.web_tool import search
        results = search(req.query, max_results=req.max_results)
        return JSONResponse({"ok": True, "query": req.query, "results": results,
                             "count": len(results)})
    except Exception as exc:
        logger.error("WEB-ROUTER: /search failed: %s", exc)
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)


@router.post("/fetch")
async def web_fetch(req: FetchRequest):
    """Fetch a URL and extract text content."""
    try:
        from src.web_tool import fetch
        result = fetch(req.url, timeout=req.timeout)
        return JSONResponse({"ok": result.get("ok"), "data": result})
    except Exception as exc:
        logger.error("WEB-ROUTER: /fetch failed: %s", exc)
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)


@router.post("/screenshot")
async def web_screenshot(req: ScreenshotRequest):
    """Headless Playwright screenshot — returns base64 PNG."""
    try:
        from src.web_tool import screenshot
        result = screenshot(req.url, timeout=req.timeout)
        return JSONResponse({"ok": result.get("ok"), "data": result})
    except Exception as exc:
        logger.error("WEB-ROUTER: /screenshot failed: %s", exc)
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)


@router.post("/fill")
async def web_fill(req: FillRequest):
    """Playwright form fill + submit — acts as a user on a web page."""
    try:
        from src.web_tool import fill_and_submit
        result = fill_and_submit(
            req.url, req.fields,
            submit_selector=req.submit_selector,
            wait_after_ms=req.wait_after_ms,
        )
        return JSONResponse({"ok": result.get("ok"), "data": result})
    except Exception as exc:
        logger.error("WEB-ROUTER: /fill failed: %s", exc)
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)
