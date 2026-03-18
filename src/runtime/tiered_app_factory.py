"""
Murphy System Tiered App Factory
Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1

Creates a lightweight FastAPI application for TIERED runtime mode.

The tiered app deliberately exposes only the routers that have been
loaded by the active RuntimePacks, plus a small set of management
endpoints for runtime introspection and dynamic pack control.

Endpoints provided here:
  GET  /api/health                      — liveness / readiness probe
  GET  /api/runtime/mode                — which runtime mode is active
  GET  /api/runtime/status              — full orchestrator status
  GET  /api/runtime/packs               — list packs + per-pack status
  POST /api/runtime/packs/{name}/load   — manually trigger a pack load
  POST /api/runtime/packs/{name}/unload — manually unload a pack
  POST /api/runtime/fallback            — trigger emergency monolith fallback
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger("murphy.tiered_app_factory")


def create_tiered_app(orchestrator: Any) -> Any:
    """
    Build and return a FastAPI application for tiered mode.

    Args:
        orchestrator: A booted :class:`~src.runtime.tiered_orchestrator.TieredOrchestrator`.

    Returns:
        A configured ``FastAPI`` instance.

    Raises:
        ImportError: If FastAPI is not installed.
    """
    try:
        from fastapi import FastAPI  # noqa: PLC0415
        from fastapi.middleware.cors import CORSMiddleware  # noqa: PLC0415
        from fastapi.responses import JSONResponse  # noqa: PLC0415
    except ImportError as exc:
        raise ImportError("FastAPI is required for tiered mode.") from exc

    app = FastAPI(
        title="Murphy System (Tiered Mode)",
        description=(
            "Murphy System running in tiered / on-demand mode. "
            "Only the packs required by this team are loaded."
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # ── CORS ────────────────────────────────────────────────────────────────
    _allowed_origins = [
        o.strip()
        for o in os.environ.get("MURPHY_CORS_ORIGINS", "*").split(",")
        if o.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Global exception handler ─────────────────────────────────────────────
    @app.exception_handler(Exception)
    async def _global_exception_handler(request: Any, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"error": "internal_server_error", "detail": str(exc)},
        )

    # ── Health ───────────────────────────────────────────────────────────────
    @app.get("/api/health", tags=["runtime"])
    async def health() -> dict:
        """Liveness / readiness probe. Always returns 200 in tiered mode."""
        return {"status": "ok", "mode": "tiered"}

    # ── Runtime mode ─────────────────────────────────────────────────────────
    @app.get("/api/runtime/mode", tags=["runtime"])
    async def runtime_mode() -> dict:
        """Returns the active runtime mode."""
        return {"mode": "tiered"}

    # ── Orchestrator status ───────────────────────────────────────────────────
    @app.get("/api/runtime/status", tags=["runtime"])
    async def runtime_status() -> dict:
        """Full orchestrator status including all pack states."""
        return orchestrator.get_status()

    # ── List packs ────────────────────────────────────────────────────────────
    @app.get("/api/runtime/packs", tags=["runtime"])
    async def list_packs() -> dict:
        """List all registered packs with their current status."""
        status = orchestrator.get_status()
        return {"packs": status.get("packs", {})}

    # ── Load a pack ───────────────────────────────────────────────────────────
    @app.post("/api/runtime/packs/{pack_name}/load", tags=["runtime"])
    async def load_pack(pack_name: str) -> dict:
        """
        Manually load a registered pack.

        Useful for activating optional capabilities after boot without
        restarting the server.
        """
        success = await orchestrator.load_pack(pack_name)
        if success:
            return {"status": "loaded", "pack": pack_name}
        return JSONResponse(
            status_code=500,
            content={"status": "failed", "pack": pack_name},
        )

    # ── Unload a pack ─────────────────────────────────────────────────────────
    @app.post("/api/runtime/packs/{pack_name}/unload", tags=["runtime"])
    async def unload_pack(pack_name: str) -> dict:
        """
        Manually unload a pack to free resources.

        Note: routes provided by this pack will be unavailable until the
        pack is loaded again.
        """
        success = await orchestrator.unload_pack(pack_name)
        if success:
            return {"status": "unloaded", "pack": pack_name}
        return JSONResponse(
            status_code=500,
            content={"status": "failed", "pack": pack_name},
        )

    # ── Emergency monolith fallback ───────────────────────────────────────────
    @app.post("/api/runtime/fallback", tags=["runtime"])
    async def trigger_fallback() -> dict:
        """
        Trigger an emergency fallback to monolith mode.

        This endpoint sets ``MURPHY_RUNTIME_MODE=monolith`` in the process
        environment.  A full process restart is required for the change to
        take effect.
        """
        os.environ["MURPHY_RUNTIME_MODE"] = "monolith"
        logger.warning(
            "Emergency monolith fallback triggered via API. "
            "Restart the server to complete the switch."
        )
        return {
            "status": "fallback_scheduled",
            "message": (
                "MURPHY_RUNTIME_MODE has been set to 'monolith'. "
                "Restart the server to complete the switch."
            ),
        }

    # ── Mount active pack routers ─────────────────────────────────────────────
    for router in orchestrator.get_active_routers():
        app.include_router(router)
        logger.debug("Mounted router from pack: %s", getattr(router, "prefix", "<unknown>"))

    logger.info(
        "Tiered FastAPI app created — %d pack router(s) mounted.",
        len(orchestrator.get_active_routers()),
    )
    return app
