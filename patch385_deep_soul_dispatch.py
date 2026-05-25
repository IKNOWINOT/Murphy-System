"""
PATCH-385 — Wire Deep Soul Engine (L0-L4) into DynamicRosettaPlanner dispatch

Replaces the legacy 95-word stub _render_soul with full layered soul loading
from the entity_graph.db. No token limits — Rosetta has no ceiling.
Layer selection is by role/domain relevance, not budget truncation.

Three changes:
  1. dynamic_rosetta_planner.py — _render_soul calls build_deep_soul + ships full stack
  2. deep_soul_engine.py — get_soul_for_dispatch no longer truncates to token budget
  3. app.py — add /api/soul/dispatch-preview to inspect what soul any agent gets

Applied: 2026-05-23
"""

# ════════════════════════════════════════════════════════════════════════
# CHANGE 1 — Replace DynamicRosettaPlanner._render_soul
# ════════════════════════════════════════════════════════════════════════

NEW_RENDER_SOUL = '''    def _render_soul(self, agent: AgentBlueprint, profile: TaskProfile) -> str:
        """
        PATCH-385 — Load full layered Deep Soul (L0-L4) from entity_graph.db.

        Rosetta has NO token limit. Layer selection is by relevance to the
        agent's role and the task domain. Full soul stack is returned —
        every layer that exists for this agent is included, no truncation.
        """
        try:
            from src.deep_soul_engine import build_deep_soul

            # Build the full layered soul — no budget cap
            soul_layers = build_deep_soul(
                agent_id=agent.agent_id,
                role_title=agent.role_class,
                domain=getattr(profile, "domain", "operations"),
                person_id=getattr(agent, "shadows_person_id", None),
                project_ids=getattr(profile, "project_ids", None) or [],
                include_gmail_context=False,  # PATCH-385: gmail injection happens at task time, not render
            )

            # full_soul key already concatenates L0+L1+L2+L3+L4
            # If missing (older deep_soul_engine), build it ourselves
            if "full_soul" in soul_layers and soul_layers["full_soul"]:
                return soul_layers["full_soul"]

            return "\\n\\n".join(
                soul_layers.get(layer, "")
                for layer in ("L0", "L1", "L2", "L3", "L4")
                if soul_layers.get(layer)
            )
        except Exception as e:
            logger.warning(
                "[PATCH-385] Deep soul load failed for %s — falling back to stub: %s",
                agent.agent_id, e,
            )
            # Fallback to a minimal soul (NOT the old 95-word version — just identity)
            return (
                f"# AGENT — {agent.agent_id}\\n"
                f"**Role:** {agent.role_class}\\n"
                f"**Reports to:** {agent.reports_to or 'CEO'}\\n"
                f"**Task domain:** {getattr(profile, 'domain', 'operations')}\\n"
            )
'''


# ════════════════════════════════════════════════════════════════════════
# CHANGE 2 — Replace deep_soul_engine.get_soul_for_dispatch (remove budget gating)
# ════════════════════════════════════════════════════════════════════════

NEW_GET_SOUL_FOR_DISPATCH = '''def get_soul_for_dispatch(
    agent_id: str,
    task_prompt: str,
    domain: str = "operations",
    token_budget: int = 0,  # PATCH-385: kept for backwards compat, ignored
    gmail_token: Optional[str] = None,
    person_id: Optional[str] = None,
    project_ids: Optional[List[str]] = None,
) -> str:
    """
    PATCH-385 — Get the full layered soul for a task. NO TOKEN LIMIT.
    
    Rosetta is not bounded by token counts. L0-L4 are organizational
    granularity (depth-of-loading), not size ceilings. Every layer that
    has content for this agent is returned. Token budget arg is preserved
    for API compat but ignored.
    """
    try:
        soul = build_deep_soul(
            agent_id=agent_id,
            role_title=agent_id,
            domain=domain,
            person_id=person_id,
            project_ids=project_ids,
            include_gmail_context=gmail_token is not None,
            gmail_token=gmail_token,
        )
        # Return the full stack — no truncation
        if "full_soul" in soul and soul["full_soul"]:
            return soul["full_soul"]
        return "\\n\\n".join(
            soul.get(layer, "")
            for layer in ("L0","L1","L2","L3","L4")
            if soul.get(layer)
        )
    except Exception as e:
        logger.warning("Deep soul build failed for %s: %s — using minimal soul", agent_id, e)
        return f"# SOUL — {agent_id}\\n**Domain:** {domain}\\n**Task:** {task_prompt[:100]}"
'''


# ════════════════════════════════════════════════════════════════════════
# CHANGE 3 — Add /api/soul/dispatch-preview route
# ════════════════════════════════════════════════════════════════════════

DISPATCH_PREVIEW_ROUTE = '''
    # ═══ PATCH-385: Deep Soul Dispatch Preview ═══
    @app.get("/api/soul/dispatch-preview")
    async def soul_dispatch_preview(
        agent_id: str = "ceo",
        task: str = "review Q4 strategy",
        domain: str = "operations",
        request: Request = None,
    ):
        """
        Preview the FULL layered soul (L0-L4) that an agent would receive
        for a given task. No token limit — every layer that has content
        for this agent is returned.
        """
        try:
            from src.deep_soul_engine import build_deep_soul

            soul = build_deep_soul(
                agent_id=agent_id,
                role_title=agent_id,
                domain=domain,
                include_gmail_context=False,
            )

            layers_info = {}
            for layer_key in ("L0","L1","L2","L3","L4"):
                text = soul.get(layer_key, "")
                layers_info[layer_key] = {
                    "chars": len(text),
                    "words": len(text.split()) if text else 0,
                    "tokens_est": int(len(text) / 4),
                    "preview": text[:300] + ("..." if len(text) > 300 else ""),
                    "loaded": bool(text),
                }

            full_text = soul.get("full_soul", "") or "\\n\\n".join(
                soul.get(k, "") for k in ("L0","L1","L2","L3","L4") if soul.get(k)
            )

            return {
                "gate": "PATCH-385-SOUL-DISPATCH",
                "status": "OK",
                "agent_id": agent_id,
                "task": task,
                "domain": domain,
                "layers": layers_info,
                "total": {
                    "chars": len(full_text),
                    "words": len(full_text.split()),
                    "tokens_est": int(len(full_text) / 4),
                    "layers_loaded": sum(1 for v in layers_info.values() if v["loaded"]),
                },
                "full_soul": full_text,
                "note": "No token limit — Rosetta layer selection is by relevance, not budget",
            }
        except Exception as e:
            return {
                "gate": "PATCH-385-SOUL-DISPATCH",
                "status": "ERROR",
                "error": str(e),
                "agent_id": agent_id,
            }
'''
