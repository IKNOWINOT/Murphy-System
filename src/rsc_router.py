"""
RSC FastAPI Router — PATCH-077b
Mounts the Unified Sink at /api/rsc/*.

Endpoints:
  GET  /api/rsc/status   — current S(t), mode, all variables
  GET  /api/rsc/stream   — SSE: live S(t) push on every update
  POST /api/rsc/signal   — any module pushes a signal directly
  GET  /api/rsc/history  — last N stability readings
  GET  /api/rsc/gate     — check if current mode allows an operation
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from src.rsc_unified_sink import get_sink, push, enforce, RSCMode

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/rsc", tags=["rsc"])


@router.get("/status")
async def rsc_status():
    """Current stability reading."""
    sink = get_sink()
    current = sink.get()
    if current is None:
        return JSONResponse({"ok": True, "data": None, "note": "no readings yet"})
    return JSONResponse({"ok": True, "data": current.to_dict()})


@router.get("/stream")
async def rsc_stream(request: Request):
    """
    SSE stream — pushes every S(t) update as a data: event.
    Clients connect once and receive live stability updates.
    """
    sink = get_sink()
    q: asyncio.Queue = asyncio.Queue(maxsize=100)
    sink.subscribe(q)

    # Send current state immediately on connect
    current = sink.get()
    if current:
        initial = f"data: {json.dumps(current.to_dict())}\n\n"
    else:
        initial = "data: {}\n\n"

    async def generator():
        try:
            yield initial
            while True:
                if await request.is_disconnected():
                    break
                try:
                    reading = await asyncio.wait_for(q.get(), timeout=30.0)
                    yield f"data: {json.dumps(reading)}\n\n"
                except asyncio.TimeoutError:
                    # Keepalive ping
                    yield ": keepalive\n\n"
        except Exception as e:
            logger.debug("RSC SSE client disconnected: %s", e)
        finally:
            sink.unsubscribe(q)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


class SignalPayload(BaseModel):
    source: str
    agents: Optional[float] = None
    tasks: Optional[float] = None
    gates: Optional[float] = None
    violations: Optional[float] = None
    contradictions: Optional[float] = None
    circular_deps: Optional[float] = None
    confidence: Optional[float] = None
    gaps: Optional[float] = None
    proposals: Optional[float] = None
    errors: Optional[float] = None
    parse_errors: Optional[float] = None


@router.post("/signal")
async def rsc_signal(payload: SignalPayload):
    """Push a signal from any module into the RSC sink."""
    kwargs = {k: v for k, v in payload.dict().items()
              if k != "source" and v is not None}
    reading = push(payload.source, **kwargs)
    return JSONResponse({"ok": True, "data": reading.to_dict()})


@router.get("/history")
async def rsc_history(limit: int = Query(default=50, le=500)):
    """Last N stability readings."""
    sink = get_sink()
    return JSONResponse({"ok": True, "data": sink.get_history(limit)})


@router.get("/gate")
async def rsc_gate(op: str = Query(default=""), mode: str = Query(default="nominal")):
    """
    Check if current S(t) allows an operation.
    Returns allowed=True/False and the current mode.
    """
    required = RSCMode.EXPAND if mode == "expand" else RSCMode.NOMINAL
    blocked = enforce(op or "check", required)
    current = get_sink().get()
    return JSONResponse({
        "ok": True,
        "allowed": blocked is None,
        "blocked_reason": blocked,
        "current_mode": current.mode if current else "unknown",
        "s_t": current.s_t if current else None,
    })
