"""
PATCH-096b — Convergence Router
src/convergence_router.py

Mounts the Recursive Convergence Engine, convergence graph,
and probabilistic CIDP investigation at /api/convergence/*.

Uses the same router pattern as lcm_router.py which correctly
handles POST request bodies without platform middleware interference.

MSS RM3 (Technical Specification):
  All POST endpoints use `request: Request` + `await request.json()`
  per the platform's established pattern (lcm_router.py reference).
  Return type annotations -> JSONResponse are explicit on all handlers.

Copyright © 2020-2026 Inoni LLC — Created by Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


def _ok(data: Any, status: int = 200):
    from fastapi.responses import JSONResponse
    return JSONResponse(content={"success": True, "data": data}, status_code=status)


def _err(msg: str, status: int = 500):
    from fastapi.responses import JSONResponse
    return JSONResponse(
        content={"success": False, "error": {"code": "RCE_ERROR", "message": msg}},
        status_code=status,
    )


def build_convergence_router():
    """Build and return the convergence APIRouter. Called from runtime/app.py."""
    from fastapi import APIRouter, Request
    from fastapi.responses import JSONResponse

    router = APIRouter(prefix="/api/convergence", tags=["convergence"])

    # ── POST /api/convergence/analyze ─────────────────────────────────────
    @router.post("/analyze")
    async def analyze(request: Request) -> JSONResponse:
        """
        Three-body convergence analysis + trajectory-aware steering.

        Body:
          content      — text content to analyze (required)
          session_id   — groups events into a trajectory (optional, auto-generated)
          feed_history — prior content strings for tribal velocity (optional)
          domain       — content domain: media, political, personal, general (optional)

        Returns convergence signal, steering action, session_id.
        Every call persists a node to the convergence graph.
        """
        try:
            body = await request.json()
        except Exception:
            return _err("Invalid JSON body", 400)

        content = (body.get("content") or "").strip()
        if not content:
            return _err("'content' field required", 400)

        session_id   = body.get("session_id")
        feed_history = body.get("feed_history", [])
        domain       = body.get("domain", "general")

        try:
            from src.recursive_convergence_engine import process as rce_process
            signal, action = rce_process(content, feed_history, domain, session_id)
            return _ok({
                "convergence": signal.to_dict(),
                "steering":    action.to_dict(),
                "session_id":  session_id,
                "oath": (
                    "We do not censor. We shift the gradient. "
                    "Free will is sacred. The choice is always theirs."
                ),
            })
        except Exception as exc:
            logger.exception("convergence/analyze error")
            return _err(str(exc))

    # ── GET /api/convergence/session/{session_id} ──────────────────────────
    @router.get("/session/{session_id}")
    async def session_trajectory(session_id: str) -> JSONResponse:
        """
        Full trajectory for a session — every convergence event in order.
        State vectors, velocity, optimal zone status, sustain mode.
        """
        try:
            from src.convergence_graph import get_graph
            graph = get_graph()
            traj  = graph.get_session_trajectory(session_id)
            state = graph.get_session_state(session_id)
            return _ok({
                "session_id":    session_id,
                "event_count":   len(traj),
                "trajectory":    traj,
                "current_state": state,
            })
        except Exception as exc:
            return _err(str(exc))

    # ── GET /api/convergence/graph/stats ──────────────────────────────────
    @router.get("/graph/stats")
    async def graph_stats() -> JSONResponse:
        """
        Global convergence graph statistics:
        total events, sessions, optimal zone rate, pattern distribution,
        named zone bounds (OptimalZone, ContractManifold).
        """
        try:
            from src.convergence_graph import get_graph
            return _ok(get_graph().get_global_stats())
        except Exception as exc:
            return _err(str(exc))

    # ── GET /api/convergence/patterns ─────────────────────────────────────
    @router.get("/patterns")
    async def patterns() -> JSONResponse:
        """
        All named tribal patterns, their closure scores, and counter-signal gradients.
        Includes OptimalZone and ContractManifold named bounds.
        """
        try:
            from src.recursive_convergence_engine import (
                TribalPattern, _TRIBAL_CLOSURE, MIDDLE_PATH_COUNTER_SIGNALS,
                FLOURISHING_DOMAINS, CONTRACTION_DOMAINS, STEERING_OATH,
            )
            from src.convergence_graph import (
                OPTIMAL_FLOURISHING_MIN, OPTIMAL_CLOSURE_MAX, OPTIMAL_HARM_MAX,
                CONTRACT_CLOSURE_MIN, CONTRACT_FLOURISHING_MAX, CONTRACT_HARM_MIN,
                SUSTAIN_MAGNITUDE,
            )
            return _ok({
                "oath": STEERING_OATH,
                "tribal_patterns": {
                    p.value: {
                        "closure_score": _TRIBAL_CLOSURE[p],
                        "counter_gradient": MIDDLE_PATH_COUNTER_SIGNALS[p]["gradient"],
                        "content_type":    MIDDLE_PATH_COUNTER_SIGNALS[p]["content_type"],
                    }
                    for p in TribalPattern
                },
                "flourishing_domains": [d.value for d in FLOURISHING_DOMAINS],
                "contraction_domains": [d.value for d in CONTRACTION_DOMAINS],
                "optimal_zone_bounds": {
                    "flourishing_min": OPTIMAL_FLOURISHING_MIN,
                    "closure_max":     OPTIMAL_CLOSURE_MAX,
                    "harm_max":        OPTIMAL_HARM_MAX,
                },
                "contraction_manifold_bounds": {
                    "closure_min":     CONTRACT_CLOSURE_MIN,
                    "flourishing_max": CONTRACT_FLOURISHING_MAX,
                    "harm_min":        CONTRACT_HARM_MIN,
                },
                "sustain_magnitude": SUSTAIN_MAGNITUDE,
                "mss_principle": (
                    "Ambiguity is the path to P=NP. "
                    "Every undefined term is resolved by MSS to its highest-precision definition. "
                    "Named bounds are not magic numbers — they are engineering decisions, "
                    "MSS-resolved at RM4 (Architecture Design), revisable as the graph learns."
                ),
            })
        except Exception as exc:
            return _err(str(exc))

    # ── POST /api/convergence/investigate ─────────────────────────────────
    @router.post("/investigate")
    async def investigate(request: Request) -> JSONResponse:
        """
        Run the full 6-stage CIDP criminal investigation on a decision.
        Stage 4 now uses probabilistic harm (Bayesian) not binary thresholds.
        Hard stop only at P(catastrophic) > 0.95.
        Free will no-go list remains structural (Stage 5) — not probabilistic.
        """
        try:
            body = await request.json()
        except Exception:
            return _err("Invalid JSON body", 400)

        intent = (body.get("intent") or "").strip()
        if not intent:
            return _err("'intent' field required", 400)

        try:
            from src.criminal_investigation_protocol import investigate as cidp_investigate
            report = cidp_investigate(
                intent=intent,
                context=body.get("context", {}),
                domain=body.get("domain", "general"),
            )
            return _ok(report.to_dict())
        except Exception as exc:
            logger.exception("convergence/investigate error")
            return _err(str(exc))

    logger.info("PATCH-096b: Convergence router mounted — /api/convergence/* live")
    return router
