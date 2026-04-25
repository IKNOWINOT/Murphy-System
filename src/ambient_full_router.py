"""
PATCH-072a: Ambient AI Full Activation Router

Rewires /api/ambient/* stubs to the real AmbientContextStore + AmbientSynthesis
+ AmbientEmailDelivery pipeline.

Endpoints:
  POST /api/ambient/context        — ingest context signals (stores + triggers synthesis)
  POST /api/ambient/insights       — receive pre-synthesised insights + optionally deliver
  POST /api/ambient/deliver        — deliver an insight via email
  GET  /api/ambient/settings       — get ambient settings
  POST /api/ambient/settings       — save ambient settings
  GET  /api/ambient/stats          — full stats (signals, insights, deliveries)
  POST /api/ambient/synthesize     — manually trigger LLM synthesis from stored signals
  GET  /api/ambient/signals        — list recent signals
  GET  /api/ambient/deliveries     — list recent deliveries

Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · BSL 1.1
PATCH-072a
"""
from __future__ import annotations
import json
import logging, os
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ambient", tags=["ambient-ai"])

# ── Singletons ──────────────────────────────────────────────────────────────
_store = None
_synth = None

def _get_store():
    """Return the shared AmbientContextStore — prefers the one on murphy app state."""
    global _store
    # Try to get the shared store set by app.py (murphy._ambient_store)
    try:
        import gc
        for obj in gc.get_objects():
            if hasattr(obj, "_ambient_store"):
                return obj._ambient_store
    except Exception:
        pass
    if _store is None:
        from src.ambient_context_store import AmbientContextStore
        _store = AmbientContextStore(max_signals=2000, ttl_seconds=86400)
        logger.info("PATCH-072a: AmbientContextStore initialised (standalone)")
    return _store

def _get_synth():
    global _synth
    if _synth is None:
        try:
            from src.ambient_synthesis import synthesize
            _synth = synthesize
            logger.info("PATCH-072a: AmbientSynthesis wired")
        except Exception as exc:
            logger.warning("PATCH-072a: AmbientSynthesis unavailable: %s", exc)
    return _synth

# ── Schemas ──────────────────────────────────────────────────────────────────
class SignalPayload(BaseModel):
    signals: List[Dict[str, Any]] = []
    auto_synthesize: bool = False

class InsightPayload(BaseModel):
    insights: List[Dict[str, Any]] = []
    deliver: bool = False
    to_emails: List[str] = []

class DeliverPayload(BaseModel):
    insight: Dict[str, Any]
    to_emails: List[str] = []

class SettingsPayload(BaseModel):
    contextEnabled: bool = True
    emailEnabled: bool = True
    frequency: str = "daily"
    confidenceMin: float = 0.65
    shadowMode: bool = False

class SynthesizePayload(BaseModel):
    limit: int = 50
    deliver: bool = False
    to_emails: List[str] = []

# ── Routes ───────────────────────────────────────────────────────────────────
@router.post("/context")
async def ingest_context(payload: SignalPayload):
    """Ingest ambient context signals. Optionally triggers LLM synthesis."""
    store = _get_store()
    stored = store.push(payload.signals)
    result = {"ok": True, "stored": stored}

    if payload.auto_synthesize and payload.signals:
        synth = _get_synth()
        if synth:
            try:
                insights = synth(payload.signals)
                for ins in (insights or []):
                    store.store_insight(ins)
                result["synthesized"] = len(insights or [])
            except Exception as exc:
                result["synthesis_error"] = str(exc)
    return JSONResponse(result)


@router.post("/insights")
async def receive_insights(payload: InsightPayload):
    """Receive pre-synthesised insights and optionally deliver via email."""
    store = _get_store()
    for ins in payload.insights:
        store.store_insight(ins)

    delivered = 0
    if payload.deliver and payload.insights:
        try:
            from src.ambient_email_delivery import deliver
            to = payload.to_emails or [os.getenv("MURPHY_FOUNDER_EMAIL", "cpost@murphy.systems")]
            for ins in payload.insights:
                r = deliver(ins, to_emails=to)
                if r.get("delivered"):
                    delivered += 1
        except Exception as exc:
            logger.warning("PATCH-072a: delivery failed: %s", exc)

    return JSONResponse({"ok": True, "queued": len(payload.insights), "delivered": delivered})


@router.post("/deliver")
async def deliver_insight(payload: DeliverPayload):
    """Deliver a single ambient insight via email."""
    try:
        from src.ambient_email_delivery import deliver
        to = payload.to_emails or [os.getenv("MURPHY_FOUNDER_EMAIL", "cpost@murphy.systems")]
        result = deliver(payload.insight, to_emails=to)
        return JSONResponse({"ok": True, "result": result})
    except Exception as exc:
        raise HTTPException(500, str(exc))


@router.post("/synthesize")
async def synthesize_now(payload: SynthesizePayload):
    """Manually trigger LLM synthesis from recent stored signals."""
    store = _get_store()
    signals = store.get_recent(limit=payload.limit)
    if not signals:
        return JSONResponse({"ok": True, "insights": [], "message": "No signals to synthesize"})

    synth = _get_synth()
    if synth is None:
        raise HTTPException(503, "Synthesis engine unavailable")

    try:
        insights = synth(signals) or []
        for ins in insights:
            store.store_insight(ins)

        delivered = 0
        if payload.deliver and insights:
            from src.ambient_email_delivery import deliver
            to = payload.to_emails or [os.getenv("MURPHY_FOUNDER_EMAIL", "cpost@murphy.systems")]
            for ins in insights:
                r = deliver(ins, to_emails=to)
                if r.get("delivered"):
                    delivered += 1

        return JSONResponse({"ok": True, "insights_generated": len(insights),
                             "delivered": delivered, "insights": insights[:5]})
    except Exception as exc:
        raise HTTPException(500, str(exc))


@router.get("/settings")
async def get_settings():
    """Return current ambient engine settings."""
    store = _get_store()
    return JSONResponse({"ok": True, "settings": store.get_settings()})


@router.post("/settings")
async def save_settings(payload: SettingsPayload):
    """Persist ambient engine settings."""
    store = _get_store()
    result = store.save_settings(payload.dict())
    return JSONResponse({"ok": True, "settings": result})


@router.get("/stats")
async def get_stats():
    """Full ambient intelligence stats."""
    store = _get_store()
    stats = store.get_stats()
    try:
        from src.ambient_email_delivery import email_backend_mode
        stats["email_backend"] = email_backend_mode()
    except Exception:
        stats["email_backend"] = "unknown"
    return JSONResponse({"ok": True, **stats})


@router.get("/signals")
async def list_signals(limit: int = 50, source: Optional[str] = None):
    """List recent ambient signals."""
    store = _get_store()
    return JSONResponse({"ok": True, "signals": store.get_recent(limit=limit, source=source)})


@router.get("/deliveries")
async def list_deliveries(limit: int = 20):
    """List recent ambient deliveries."""
    store = _get_store()
    return JSONResponse({"ok": True, "deliveries": store.get_deliveries(limit=limit)})
