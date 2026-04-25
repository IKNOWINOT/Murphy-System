"""
LCM Router — PATCH-073
Mounts the LargeControlModel at /api/lcm/*.

Endpoints:
  POST /api/lcm/process       — Run NL input through the full LCM pipeline
  GET  /api/lcm/status        — Pilot status + subsystem wiring report
  POST /api/lcm/signal        — Feed an ambient signal directly into LCM
  GET  /api/lcm/history       — Last N run traces
  POST /api/lcm/threshold     — Adjust confidence/stability thresholds

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""
from __future__ import annotations

import logging
import threading
from collections import deque
from typing import Any, Deque, Dict, Optional

logger = logging.getLogger(__name__)

try:
    from fastapi import APIRouter, Request
    from fastapi.responses import JSONResponse
    _FASTAPI = True
except ImportError:
    _FASTAPI = False

# ── Singleton LCM instance ───────────────────────────────────────────────────
_lcm = None
_lcm_lock = threading.Lock()
_run_history: Deque[Dict[str, Any]] = deque(maxlen=100)


def _get_lcm():
    global _lcm
    with _lcm_lock:
        if _lcm is None:
            try:
                from src.large_control_model import LargeControlModel
                _lcm = LargeControlModel()
                logger.info("PATCH-073: LargeControlModel initialised")
            except Exception as exc:
                logger.error("PATCH-073: LCM init failed: %s", exc)
                return None
    return _lcm


def _ok(data: Any = None) -> "JSONResponse":
    return JSONResponse({"ok": True, "data": data})


def _err(msg: str, status: int = 500) -> "JSONResponse":
    logger.warning("LCM API error: %s", msg)
    return JSONResponse({"ok": False, "error": msg}, status_code=status)


def build_router() -> "APIRouter":
    if not _FASTAPI:
        raise RuntimeError("FastAPI not available")

    router = APIRouter(prefix="/api/lcm", tags=["lcm"])

    @router.post("/process")
    async def lcm_process(request: Request) -> JSONResponse:
        """Run a natural-language command through the full LCM pipeline."""
        try:
            body = await request.json()
        except Exception:
            return _err("Invalid JSON body", 400)

        text = (body.get("input") or body.get("text") or "").strip()
        account = body.get("account", "")
        if not text:
            return _err("'input' field required", 400)

        lcm = _get_lcm()
        if lcm is None:
            return _err("LCM unavailable — check logs")

        try:
            result = lcm.process(text, account=account or None)
            _run_history.appendleft(result)
            return _ok(result)
        except Exception as exc:
            logger.exception("PATCH-073: lcm.process() raised")
            return _err(str(exc))

    @router.get("/status")
    async def lcm_status() -> JSONResponse:
        """Return pilot status and subsystem wiring report."""
        lcm = _get_lcm()
        if lcm is None:
            return _err("LCM unavailable")
        try:
            status = lcm.get_pilot_status()
            return _ok(status)
        except Exception as exc:
            return _err(str(exc))

    @router.post("/signal")
    async def lcm_signal(request: Request) -> JSONResponse:
        """Feed an ambient signal into LCM as a natural-language command.

        Accepts: {"source": str, "type": str, "value": str, "confidence": float}
        Converts the signal to NL and runs it through LCM.process().
        """
        try:
            body = await request.json()
        except Exception:
            return _err("Invalid JSON body", 400)

        source = body.get("source", "ambient")
        sig_type = body.get("type", "signal")
        value = body.get("value", "")
        confidence = float(body.get("confidence", 0.8))

        # Convert signal → NL command
        nl_text = (
            f"Ambient signal from {source} [{sig_type}]: {value}. "
            f"Confidence: {confidence:.0%}. "
            "Assess and recommend action."
        )

        lcm = _get_lcm()
        if lcm is None:
            return _err("LCM unavailable")

        try:
            result = lcm.process(nl_text)
            result["_signal_source"] = source
            result["_signal_type"] = sig_type
            _run_history.appendleft(result)
            return _ok(result)
        except Exception as exc:
            logger.exception("PATCH-073: lcm.signal() raised")
            return _err(str(exc))

    @router.get("/history")
    async def lcm_history(limit: int = 20) -> JSONResponse:
        """Return the last N LCM run traces."""
        limit = min(max(1, limit), 100)
        return _ok({
            "runs": list(_run_history)[:limit],
            "total": len(_run_history),
        })

    @router.post("/threshold")
    async def lcm_threshold(request: Request) -> JSONResponse:
        """Adjust confidence/stability thresholds for auto-dispatch."""
        try:
            body = await request.json()
        except Exception:
            return _err("Invalid JSON body", 400)

        lcm = _get_lcm()
        if lcm is None:
            return _err("LCM unavailable")

        updated = {}
        if "confidence" in body:
            lcm.confidence_threshold = float(body["confidence"])
            updated["confidence_threshold"] = lcm.confidence_threshold
        if "stability" in body:
            lcm.stability_threshold = float(body["stability"])
            updated["stability_threshold"] = lcm.stability_threshold

        return _ok({"updated": updated})

    return router
