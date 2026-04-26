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


    @router.get("/contract", summary="Murphy Ethical Contract")
    async def ethical_contract():
        """
        The machine-level code of conduct that imprints on every AI
        interacting with the Murphy system.
        """
        try:
            from src.criminal_investigation_protocol import ETHICAL_CONTRACT, ETHICAL_CONTRACT_VERSION
            return JSONResponse(content={
                "version": ETHICAL_CONTRACT_VERSION,
                "terms": ETHICAL_CONTRACT["terms"],
                "north_star": ETHICAL_CONTRACT["north_star"],
            })
        except Exception as exc:
            return JSONResponse(content={"error": str(exc)}, status_code=500)

    @router.post("/investigate", summary="Run Criminal Investigation Protocol")
    async def run_investigation(request: dict):
        """
        Run the full 6-stage criminal investigation protocol on a decision.
        Stage 0 of the LCM pipeline — facts, motive, ethics, harm, free will, verdict.
        """
        try:
            from src.criminal_investigation_protocol import investigate
            report = investigate(
                intent=request.get("intent", ""),
                context=request.get("context", {}),
                domain=request.get("domain", "general"),
            )
            return JSONResponse(content=report.to_dict())
        except Exception as exc:
            return JSONResponse(content={"error": str(exc)}, status_code=500)


    # ── PATCH-095: Model Team ────────────────────────────────────────────────
    @router.get("/team/roe", summary="Rules of Engagement")
    async def team_roe():
        """The rules of engagement governing the Murphy Model Team."""
        try:
            from src.model_team import RULES_OF_ENGAGEMENT, ROLE_CONFIG, TeamRole
            return JSONResponse(content={
                "rules_of_engagement": RULES_OF_ENGAGEMENT,
                "team": {
                    role.value: {
                        "authority": cfg["authority"],
                        "constraint": cfg["constraint"],
                        "model_hint": cfg["model_hint"],
                        "provider": cfg["provider"],
                    }
                    for role, cfg in ROLE_CONFIG.items()
                },
            })
        except Exception as exc:
            return JSONResponse(content={"error": str(exc)}, status_code=500)

    @router.post("/team/deliberate", summary="Run Model Team Deliberation")
    async def team_deliberate(request: dict):
        """
        Run a full team deliberation under rules of engagement.
        Four models. Murphy referees. CIDP investigates the output.
        """
        try:
            from src.model_team import deliberate
            session = deliberate(
                task=request.get("task", ""),
                domain=request.get("domain", "general"),
                account=request.get("account", "unknown"),
            )
            return JSONResponse(content=session.to_dict())
        except Exception as exc:
            logger.warning("Team deliberate error: %s", exc)
            return JSONResponse(content={"error": str(exc)}, status_code=500)

    logger.info("PATCH-093c: Shield Wall router mounted — /api/shield/*")
    return router
