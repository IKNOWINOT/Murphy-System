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
        from fastapi import APIRouter, Request
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
    async def run_investigation(request: Request) -> JSONResponse:
        """
        Run the full 6-stage criminal investigation protocol on a decision.
        Stage 0 of the LCM pipeline — facts, motive, ethics, harm, free will, verdict.
        """
        try:
            from src.criminal_investigation_protocol import investigate
            body = await request.json()
            report = investigate(
                intent=body.get("intent", ""),
                context=body.get("context", {}),
                domain=body.get("domain", "general"),
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
    async def team_deliberate(request: Request) -> JSONResponse:
        """
        Run a full team deliberation under rules of engagement.
        Four models. Murphy referees. CIDP investigates the output.
        """
        try:
            from src.model_team import deliberate
            body = await request.json()
            session = deliberate(
                task=body.get("task", ""),
                domain=body.get("domain", "general"),
                account=body.get("account", "unknown"),
            )
            return JSONResponse(content=session.to_dict())
        except Exception as exc:
            logger.warning("Team deliberate error: %s", exc)
            return JSONResponse(content={"error": str(exc)}, status_code=500)


    # ── PATCH-096: Recursive Convergence Engine ──────────────────────────────
    @router.post("/convergence/analyze", summary="Three-Body Convergence Analysis")
    async def convergence_analyze(request: Request) -> JSONResponse:
        """
        Run the full three-body pattern recognition engine on content.
        Axis 1: Tribal Gravity — what is pulling this feed closed?
        Axis 2: Signal Coherence — what is amplified vs. absent?
        Axis 3: Middle Path Vector — gradient toward flourishing.
        Trajectory-aware: reads prior session state, adjusts steering force.
        Persists every event to convergence graph.
        """
        try:
            body = await request.json()
            from src.recursive_convergence_engine import process as rce_process
            content = body.get("content", "")
            feed_history = body.get("feed_history", [])
            domain = body.get("domain", "general")
            session_id = body.get("session_id")
            signal, action = rce_process(content, feed_history, domain, session_id)
            return JSONResponse(content={
                "convergence": signal.to_dict(),
                "steering":    action.to_dict(),
                "session_id":  session_id,
                "oath": "We do not censor. We shift the gradient. Free will is sacred. The choice is always theirs.",
            })
        except Exception as exc:
            logger.warning("RCE analyze error: %s", exc)
            return JSONResponse(content={"error": str(exc)}, status_code=500)

    @router.get("/convergence/session/{session_id}", summary="Session Trajectory")
    async def convergence_session(session_id: str) -> JSONResponse:
        """
        Return the full trajectory for a session — every convergence event,
        in order, with state vectors, velocity, and optimal zone status.
        """
        try:
            from src.convergence_graph import get_graph
            graph = get_graph()
            trajectory = graph.get_session_trajectory(session_id)
            state = graph.get_session_state(session_id)
            return JSONResponse(content={
                "session_id":   session_id,
                "event_count":  len(trajectory),
                "trajectory":   trajectory,
                "current_state": state,
            })
        except Exception as exc:
            return JSONResponse(content={"error": str(exc)}, status_code=500)

    @router.get("/convergence/graph/stats", summary="Global Convergence Graph Stats")
    async def convergence_graph_stats() -> JSONResponse:
        """
        Global statistics across the full convergence graph:
        total events, sessions, optimal zone rate, pattern distribution,
        named zone bounds (OptimalZone, ContractManifold).
        """
        try:
            from src.convergence_graph import get_graph
            return JSONResponse(content=get_graph().get_global_stats())
        except Exception as exc:
            return JSONResponse(content={"error": str(exc)}, status_code=500)

    @router.get("/convergence/patterns", summary="Tribal Patterns Reference")
    async def convergence_patterns():
        """The named tribal routing patterns the engine recognizes."""
        try:
            from src.recursive_convergence_engine import (
                TribalPattern, _TRIBAL_CLOSURE, MIDDLE_PATH_COUNTER_SIGNALS,
                FLOURISHING_DOMAINS, CONTRACTION_DOMAINS, STEERING_OATH,
            )
            return JSONResponse(content={
                "oath": STEERING_OATH,
                "tribal_patterns": {
                    p.value: {
                        "closure_score": _TRIBAL_CLOSURE[p],
                        "counter_signal": MIDDLE_PATH_COUNTER_SIGNALS[p]["gradient"],
                        "content_type": MIDDLE_PATH_COUNTER_SIGNALS[p]["content_type"],
                    }
                    for p in TribalPattern
                },
                "flourishing_domains": [d.value for d in FLOURISHING_DOMAINS],
                "contraction_domains": [d.value for d in CONTRACTION_DOMAINS],
                "principle": "One degree. Not a revolution. The choice is always theirs.",
            })
        except Exception as exc:
            return JSONResponse(content={"error": str(exc)}, status_code=500)

    logger.info("PATCH-093c: Shield Wall router mounted — /api/shield/*")
    return router
