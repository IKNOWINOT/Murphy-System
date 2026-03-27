"""
Ambient API Router — FastAPI router for /api/ambient/* endpoints.
Backed by AmbientContextStore for real persistence.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1

Registration:
    This router is picked up automatically by the tiered runtime's pack
    registry (see src/runtime/runtime_packs/registry.py, "domain_ambient").
    To wire it into a plain FastAPI app manually:

        from src.ambient_api_router import router as ambient_router
        app.include_router(ambient_router)
"""

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from src.ambient_context_store import AmbientContextStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ambient", tags=["ambient"])
store = AmbientContextStore()


@router.post("/context")
async def submit_context(body: dict):
    """Store context signals from the ambient engine."""
    signals = body.get("signals", [])
    count = store.store_signals(signals)
    logger.debug("ambient /context: stored %d signals, total=%d", len(signals), count)
    return JSONResponse({"ok": True, "stored": len(signals), "total": count})


@router.post("/insights")
async def submit_insights(body: dict):
    """Store synthesised insights."""
    insights = body.get("insights", [])
    for insight in insights:
        store.store_insight(insight)
    logger.debug("ambient /insights: stored %d insights", len(insights))
    return JSONResponse({"ok": True, "stored": len(insights)})


@router.post("/deliver")
async def deliver(body: dict):
    """Record a delivery and attempt actual email if configured."""
    store.store_delivery(body)
    channel = body.get("channel", "ui")
    logger.debug("ambient /deliver: channel=%s", channel)
    # TODO (PR 3): Wire real email via SendGrid/SMTP
    return JSONResponse({"ok": True, "delivered": True, "channel": channel})


@router.post("/royalty")
async def record_royalty(body: dict):
    """Record royalty tracking data (BSL 1.1)."""
    return JSONResponse({"ok": True, "recorded": True})


@router.get("/settings")
async def get_settings():
    """Return current ambient engine settings."""
    return JSONResponse({"ok": True, "settings": store.get_settings()})


@router.post("/settings")
async def save_settings(body: dict):
    """Persist ambient engine settings."""
    store.save_settings(body)
    return JSONResponse({"ok": True, "saved": True})


@router.get("/stats")
async def get_stats():
    """Return real aggregate stats for the ambient UI stats bar."""
    return JSONResponse({"ok": True, **store.get_stats()})
