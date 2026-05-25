# Copyright © 2020 Inoni LLC — Creator: Corey Post — License: BSL 1.1
"""
ExecGenerativeAgent — PATCH-361
"The executive writes the brief before any agent acts."

ExecGen is the coordinator that generates a soul-aware, task-specific
directive for every agent BEFORE they run their LLM call.

Without ExecGen: every agent gets "You are an execution agent. Execute this step."
With ExecGen: every agent gets their SOUL.md as system= + a precise directive
              written specifically for them, naming their role, their team,
              the world state, and exactly what success looks like.

This is the equivalent of me (Murphy/the agent running dispatch) being injected
between the coordinator and every subagent — I write their brief, they execute it.
That's the Rosetta injection: not just rendering a soul doc, but actively writing
the agent into existence for this specific task.
"""
from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("murphy.exec_gen")


@dataclass
class GeneratedBrief:
    brief_id: str
    target_agent_id: str
    target_role: str
    directive: str          # becomes the user= prompt
    system_prompt: str      # becomes the system= prompt (the soul)
    expected_output: str
    success_criteria: List[str]
    constraints: List[str]
    org_context: str
    world_state: str
    generated_at: str
    generating_agent: str


@dataclass
class ExecBriefPacket:
    dispatch_id: str
    task: str
    briefs: Dict[str, GeneratedBrief]   # agent_id -> brief
    generated_at: str
    coordinator_id: str


class ExecGenerativeAgent:
    """
    Generates a mission brief for every agent in the swarm.
    Called after DynamicRosettaPlanner.plan() — before any LLM executes.
    The brief.system_prompt goes into system= on every LLM call.
    The brief.directive goes into the user= prompt.
    """

    def __init__(self, llm_provider=None):
        self._llm = llm_provider
        logger.info("[PATCH-361] ExecGenerativeAgent initialized")

    def generate_all_briefs(
        self,
        task: str,
        dispatch_packet,
        multicursor_snapshot: Optional[Dict] = None,
    ) -> ExecBriefPacket:
        t0 = time.time()
        dispatch_id = "dispatch_" + uuid.uuid4().hex[:8]
        briefs: Dict[str, GeneratedBrief] = {}

        team             = dispatch_packet.team
        soul_contexts    = dispatch_packet.soul_contexts
        profile          = dispatch_packet.task_profile
        coordinator_id   = dispatch_packet.coordinator_id

        # Build org context
        org_lines = []
        for agent in team:
            tag = " [COORDINATOR]" if agent.agent_id == coordinator_id else ""
            org_lines.append(f"  {agent.emoji} {agent.role_class} ({agent.department}){tag}")
        org_context = "Team:\n" + "\n".join(org_lines)

        world_state = self._summarize_world_state(multicursor_snapshot)

        for agent in team:
            soul_md = soul_contexts.get(agent.agent_id, "")
            brief = self._build_brief(
                task=task,
                agent=agent,
                soul_md=soul_md,
                org_context=org_context,
                world_state=world_state,
                profile=profile,
                is_coordinator=(agent.agent_id == coordinator_id),
                coordinator_id=coordinator_id,
            )
            briefs[agent.agent_id] = brief

        elapsed = (time.time() - t0) * 1000
        logger.info("[PATCH-361] %d briefs generated in %.0fms (dispatch=%s)",
                    len(briefs), elapsed, dispatch_id)

        return ExecBriefPacket(
            dispatch_id=dispatch_id,
            task=task,
            briefs=briefs,
            generated_at=datetime.now(timezone.utc).isoformat(),
            coordinator_id=coordinator_id,
        )

    def _build_brief(self, task, agent, soul_md, org_context, world_state,
                     profile, is_coordinator, coordinator_id) -> GeneratedBrief:
        caps_str = ", ".join(agent.capabilities)
        bounds_str = "; ".join(agent.boundaries)

        if is_coordinator:
            directive = (
                "You are the team coordinator for this task.\n\n"
                "TASK: " + task + "\n\n"
                "Your job:\n"
                "1. Direct each team member on their specific contribution\n"
                "2. Synthesize all outputs into a final result\n"
                "3. Flag HITL items before any external actions execute\n\n"
                + org_context + "\n\n"
                "Domain: " + profile.domain + " | Complexity: " + profile.complexity + " | Stake: " + profile.stake + "\n\n"
                "World state:\n" + world_state + "\n\n"
                "Your capabilities: " + caps_str + "\n"
                "Return JSON: {directive_per_agent: {}, synthesis_plan: str, hitl_items: [], success_criteria: []}"
            )
            expected = "Coordination plan with per-agent directives and synthesis approach"
            criteria = ["All agents have directives", "HITL items identified", "Synthesis plan defined"]
        else:
            manager_line = ("Report to: " + str(agent.reports_to)) if agent.reports_to else "Operating autonomously under coordinator."
            directive = (
                "You are the " + agent.role_class + " on a " + profile.domain + " task.\n\n"
                "YOUR ASSIGNMENT: " + agent.task_brief + "\n\n"
                "FULL TASK: " + task + "\n\n"
                "CHAIN OF COMMAND: " + manager_line + "\n"
                + org_context + "\n\n"
                "PRODUCE: JSON with keys: output (string), confidence (float 0-1), "
                "artifacts (list), next_action (string or null), hitl_required (bool)\n\n"
                "CAPABILITIES: " + caps_str + "\n"
                "CONSTRAINTS: " + bounds_str + "\n\n"
                "WORLD STATE:\n" + world_state
            )
            expected = agent.role_class + " work product as structured JSON"
            criteria = [
                "Output addresses: " + agent.task_brief,
                "Confidence score provided",
                "hitl_required=true if action is external or stake=high",
            ]

        return GeneratedBrief(
            brief_id="brief_" + uuid.uuid4().hex[:8],
            target_agent_id=agent.agent_id,
            target_role=agent.role_class,
            directive=directive,
            system_prompt=soul_md,
            expected_output=expected,
            success_criteria=criteria,
            constraints=agent.boundaries,
            org_context=org_context,
            world_state=world_state,
            generated_at=datetime.now(timezone.utc).isoformat(),
            generating_agent=coordinator_id,
        )

    def _summarize_world_state(self, snapshot: Optional[Dict]) -> str:
        if not snapshot:
            return "(MultiCursor not connected)"
        domains = snapshot.get("domains", {})
        lines = []
        for domain, data in domains.items():
            if isinstance(data, dict) and "error" not in data:
                parts = [str(k) + "=" + str(v) for k, v in data.items() if v]
                if parts:
                    lines.append("  [" + domain + "] " + ", ".join(parts))
        return "\n".join(lines) if lines else "(all domains empty)"
