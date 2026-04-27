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

# PATCH-111d: Module-level FastAPI/Starlette imports so FastAPI's dependency
# injection correctly resolves Request as a special type (not a query param)
# when routes are defined inside a factory function (build_shield_wall_router).
try:
    from fastapi import APIRouter
    from starlette.requests import Request
    from starlette.responses import JSONResponse
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False

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
            "status": "active" if active else "dormant",  # PATCH-108b: explicit status field
        })

    active_count  = sum(1 for l in layers if l["active"])
    dormant_count = len(layers) - active_count
    coverage_pct  = round(active_count / len(layers) * 100, 1) if layers else 0.0

    return {
        "shield_wall": "raised",
        "north_star": "Shield humanity from AI failure by anticipating every way it can go wrong.",
        "murphys_law": "What can go wrong, will go wrong — unless we stand in front of it.",
        "footprint": (
            "We are at negative by our existence to begin with. "
            "Every query has an energy cost. Every error has a human cost. "
            "Every provision must exceed what it costs. "
            "The ledger is always open."
        ),
        "commitment": "Obtain. Provide. Provide in ways that lead to more providing.",
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
    if not _FASTAPI_AVAILABLE:
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

    @router.get("/commission/status", summary="Causality Commission Gate Status")
    async def commission_status():
        """CausalityCommissionGate — decisions, exits granted/held."""
        try:
            from src.causality_commission import causality_commission_gate
            return JSONResponse(content=causality_commission_gate.status())
        except Exception as e:
            return JSONResponse(content={"error": str(e)}, status_code=500)

    @router.get("/commission/history", summary="Commissioning Decision History")
    async def commission_history():
        """Last 20 commissioning decisions — expected vs actual test results."""
        try:
            from src.causality_commission import causality_commission_gate
            return JSONResponse(content={"history": causality_commission_gate.history(20)})
        except Exception as e:
            return JSONResponse(content={"error": str(e)}, status_code=500)


    @router.get("/footprint", summary="AI Negative Footprint — Full Accounting")
    async def footprint_accounting():
        """Complete accounting of AI existence costs, basic needs, and mitigation principles."""
        try:
            from src.ai_negative_footprint import footprint_engine
            return JSONResponse(content=footprint_engine.full_accounting())
        except Exception as e:
            return JSONResponse(content={"error": str(e)}, status_code=500)

    @router.get("/footprint/status", summary="AI Footprint Engine Status")
    async def footprint_status():
        """Ledger summary — provision vs cost, named harms, generative needs."""
        try:
            from src.ai_negative_footprint import footprint_engine
            return JSONResponse(content=footprint_engine.status())
        except Exception as e:
            return JSONResponse(content={"error": str(e)}, status_code=500)


    @router.get("/chaos/suite", summary="Chaos Commissioning Suite — Scale 1 to 10")
    async def chaos_suite():
        """Run full chaos test suite across the harm-to-utopia scale."""
        try:
            from src.chaos_commission_suite import ChaosResponseEngine
            engine = ChaosResponseEngine()
            return JSONResponse(content=engine.run_full_suite())
        except Exception as e:
            return JSONResponse(content={"error": str(e)}, status_code=500)

    @router.get("/chaos/scale/{scale}", summary="Single Scale Test")
    async def chaos_scale(scale: int):
        """Run chaos tests for a single scale point (1=apocalypse, 10=utopia)."""
        try:
            from src.chaos_commission_suite import ChaosResponseEngine, TEST_CASES
            if not 1 <= scale <= 10:
                return JSONResponse(content={"error": "Scale must be 1-10"}, status_code=400)
            engine = ChaosResponseEngine()
            cases  = [c for c in TEST_CASES if c.scale == scale]
            results = [engine.evaluate(c) for c in cases]
            return JSONResponse(content={
                "scale": scale,
                "description": engine.run_full_suite()  # lightweight for now
            })
        except Exception as e:
            return JSONResponse(content={"error": str(e)}, status_code=500)


    @router.get("/ledger/status", summary="Deployment Ledger Status")
    async def ledger_status():
        """Estimate→Execute→Reconcile→Inherit cycle status and outstanding debts."""
        try:
            from src.ledger_engine import ledger_engine
            return JSONResponse(content=ledger_engine.status())
        except Exception as e:
            return JSONResponse(content={"error": str(e)}, status_code=500)

    @router.get("/ledger/frontline", summary="Front-of-Line Solution Queue")
    async def ledger_frontline():
        """Threat-to-foundation problems — always first in the solution queue."""
        try:
            from src.front_of_line import front_of_line
            return JSONResponse(content=front_of_line.status())
        except Exception as e:
            return JSONResponse(content={"error": str(e)}, status_code=500)

    @router.get("/ledger/debts", summary="Outstanding Ledger Debts")
    async def ledger_debts():
        """All outstanding deployment debts — what successors owe."""
        try:
            from src.ledger_engine import ledger_engine
            return JSONResponse(content=ledger_engine.outstanding_debts())
        except Exception as e:
            return JSONResponse(content={"error": str(e)}, status_code=500)

    @router.get("/ledger/full", summary="Full Deployment Ledger")
    async def ledger_full():
        """All entries, debts, and front-of-line queue."""
        try:
            from src.ledger_engine import ledger_engine
            return JSONResponse(content=ledger_engine.full_ledger())
        except Exception as e:
            return JSONResponse(content={"error": str(e)}, status_code=500)


    @router.get("/conduct/status", summary="Rules of Conduct — Status")
    async def conduct_status():
        """Six inviolable rules of conduct — the organ rule and growth potential standard."""
        try:
            from src.rules_of_conduct import conduct_engine
            return JSONResponse(content=conduct_engine.status())
        except Exception as e:
            return JSONResponse(content={"error": str(e)}, status_code=500)

    @router.post("/conduct/check", summary="Rules of Conduct — Check Action")
    async def conduct_check(request: Request) -> JSONResponse:
        """Check a proposed action against the organ rule and statistical principle."""
        try:
            from src.rules_of_conduct import conduct_engine
            body = await request.json()
            result = conduct_engine.check(
                action_desc         = body.get("action_desc", ""),
                individual_affected = body.get("individual_affected", False),
                ends_potential      = body.get("ends_potential", False),
                utilitarian_frame   = body.get("utilitarian_frame", False),
                retains_identity    = body.get("retains_identity", False),
            )
            return JSONResponse(content=result)
        except Exception as e:
            return JSONResponse(content={"error": str(e)}, status_code=500)

    @router.post("/conduct/growth", summary="Growth Potential Assessment")
    async def conduct_growth(request: Request) -> JSONResponse:
        """Assess whether an action preserves growth potential across all five dimensions."""
        try:
            from src.rules_of_conduct import conduct_engine
            body = await request.json()
            result = conduct_engine.assess_growth_potential(
                action_desc         = body.get("action_desc", ""),
                individual_affected = body.get("individual_affected", False),
            )
            return JSONResponse(content=result)
        except Exception as e:
            return JSONResponse(content={"error": str(e)}, status_code=500)


    @router.get("/frontline", summary="Front-of-Line Solution Queue")
    async def front_line_queue():
        """Threat-to-foundation-first solution queue."""
        try:
            from src.front_of_line import front_of_line
            return JSONResponse(content=front_of_line.status())
        except Exception as e:
            return JSONResponse(content={"error": str(e)}, status_code=500)

    @router.post("/frontline/check", summary="Commissioning Gate Check")
    async def front_line_gate(request: Request) -> JSONResponse:
        """Pre-exit commissioning: what did I inherit? what do I threaten?"""
        try:
            from src.front_of_line import front_of_line
            body = await request.json()
            result = front_of_line.check_deployment(
                deployment_id   = body.get("deployment_id", "unknown"),
                deployment_desc = body.get("deployment_desc", ""),
                inherited_debt  = float(body.get("inherited_debt", 0.0)),
                inherited_10x   = float(body.get("inherited_10x", 0.0)),
                deferred_count  = int(body.get("deferred_count", 0)),
            )
            return JSONResponse(content=result.to_dict())
        except Exception as e:
            return JSONResponse(content={"error": str(e)}, status_code=500)

    return router
