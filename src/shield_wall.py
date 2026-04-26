"""
PATCH-093c — src/shield_wall.py
Murphy System — Shield Wall Module

The Shield Wall is the north star of murphy.systems.
Every protection layer is named, visible, and commissioned.

Murphy's Law: What can go wrong, will go wrong.
Our vow: stand in front of it.

Copyright © 2020-2026 Inoni LLC — Created by Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Re-export the boot protocol from startup_feature_summary
# (single source of truth for SHIELD_LAYERS definition)
# ---------------------------------------------------------------------------

from src.startup_feature_summary import (  # noqa: E402
    NORTH_STAR,
    SHIELD_LAYERS,
    raise_shield_wall,
    get_feature_status,
    print_feature_summary,
)

__all__ = [
    "NORTH_STAR",
    "SHIELD_LAYERS",
    "raise_shield_wall",
    "get_feature_status",
    "print_feature_summary",
    "get_shield_wall_status",
    "build_shield_wall_router",
]


# ---------------------------------------------------------------------------
# Shield Wall Status API
# ---------------------------------------------------------------------------

def get_shield_wall_status() -> Dict[str, Any]:
    """
    Return structured Shield Wall status for API and dashboard use.

    Used by /api/shield/status endpoint (PATCH-093c).
    """
    import os
    layers = []
    for layer_name, shield_fn, blocks, env_var in SHIELD_LAYERS:
        active = (env_var is None) or bool(os.getenv(env_var))
        layers.append({
            "layer": layer_name,
            "shield_function": shield_fn,
            "blocks": blocks,
            "requires_env": env_var,
            "active": active,
        })

    active_count  = sum(1 for l in layers if l["active"])
    dormant_count = len(layers) - active_count
    coverage_pct  = round(active_count / len(layers) * 100, 1) if layers else 0.0

    return {
        "shield_wall": "raised",
        "north_star": "Shield humanity from AI failure by anticipating every way it can go wrong.",
        "murphys_law": "What can go wrong, will go wrong — unless we stand in front of it.",
        "layers": layers,
        "summary": {
            "total": len(layers),
            "active": active_count,
            "dormant": dormant_count,
            "coverage_pct": coverage_pct,
        },
    }


# ---------------------------------------------------------------------------
# FastAPI router — /api/shield/*
# ---------------------------------------------------------------------------

def build_shield_wall_router():
    """
    PATCH-093c: Mount Shield Wall status at /api/shield/status.

    Returns a FastAPI APIRouter. Called from runtime/app.py.
    """
    try:
        from fastapi import APIRouter
        from fastapi.responses import JSONResponse
    except ImportError:
        logger.warning("FastAPI not available — Shield Wall router not mounted")
        return None

    router = APIRouter(prefix="/api/shield", tags=["shield_wall"])

    @router.get("/status", summary="Shield Wall Status")
    async def shield_status():
        """
        Returns all active and dormant protection layers with named functions.
        The north star of murphy.systems — always visible, always honest.
        """
        return JSONResponse(content=get_shield_wall_status())

    @router.get("/north-star", summary="Murphy North Star")
    async def north_star():
        """The vow behind murphy.systems."""
        return JSONResponse(content={
            "north_star": NORTH_STAR,
            "murphys_law": "What can go wrong, will go wrong.",
            "vow": "Shield humanity. Stand in front of every failure before it lands.",
        })

    logger.info("PATCH-093c: Shield Wall router mounted — /api/shield/*")
    return router
