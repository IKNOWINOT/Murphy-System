# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Rosetta Soul Renderer — Murphy System (ROSETTA-SOUL-001)

Owner: Agent Identity / Rosetta Subsystem
Dep: rosetta_models, agent_persona_library

Renders a RosettaDocument into a compact SOUL.md-style markdown identity
document.  This is the Murphy equivalent of OpenClaw's SOUL.md — a single,
human-readable document that defines WHO the agent is, what it VALUES,
what its BOUNDARIES are, and how it COMMUNICATES.

Design rationale (from plan analysis):
  - OpenClaw SOUL.md is effective but token-crushing (loads everything).
  - Murphy's RosettaDocument already has all the identity data (contract,
    terminology, state feed, business plan, task pipeline, HITL models).
  - This renderer produces compact markdown (~170-300 tokens for L0+L1)
    that can be injected into context without waste.

Layered output matches MemPalace's L0-L3 stack:
  - L0 (identity):      ~50 tokens — who I am, what role, what type
  - L1 (critical facts): ~120 tokens — key business metrics, top priorities
  - L2 (on-demand):     full role details, terminology, task queue
  - L3 (deep search):   observation history, HITL throughput models

Error Handling:
  All public methods log and raise on invalid input.  No silent failures.
  Error codes: ROSETTA-SOUL-ERR-001 through ROSETTA-SOUL-ERR-004.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Import Rosetta models — graceful fallback if not available
try:
    from rosetta.rosetta_models import (  # type: ignore[import-untyped]
        AgentType,
        RosettaDocument,
    )
    _HAS_ROSETTA = True
except ImportError:
    _HAS_ROSETTA = False
    logger.debug("ROSETTA-SOUL-001: Rosetta models not available, using dict fallback")


# ---------------------------------------------------------------------------
# Soul Layer enum — matches MemPalace L0-L3
# ---------------------------------------------------------------------------

class SoulLayer:
    """Memory layer identifiers matching MemPalace's L0-L3 stack."""
    L0_IDENTITY = "L0"       # ~50 tokens: who am I
    L1_CRITICAL = "L1"       # ~120 tokens: key facts + priorities
    L2_DETAILED = "L2"       # On-demand: full role + terminology
    L3_DEEP = "L3"           # Deep search: observations + HITL models


# ---------------------------------------------------------------------------
# RosettaSoulRenderer — the SOUL.md generator
# ---------------------------------------------------------------------------

class RosettaSoulRenderer:
    """Renders RosettaDocument into compact SOUL.md-style identity markdown.

    Design Label: ROSETTA-SOUL-001

    The output is a layered markdown document:
      - L0 (~50 tokens):  Agent name, type, role, management layer
      - L1 (~120 tokens): Top business metrics, current priorities, authority
      - L2 (full):        Complete role description, terminology, tasks
      - L3 (deep):        Shadow observations, HITL throughput models

    Wake-up context = L0 + L1 (~170 tokens).
    Full context = all layers (still compact vs loading raw JSON).

    Usage::

        renderer = RosettaSoulRenderer()
        soul_md = renderer.render(rosetta_doc)
        wakeup = renderer.render_wakeup(rosetta_doc)  # L0+L1 only

    Integration with agent persona library::

        soul_md = renderer.render_from_persona(persona_dict)
    """

    def render(
        self,
        doc: Any,
        layers: Optional[List[str]] = None,
    ) -> str:
        """Render a RosettaDocument into SOUL.md-format markdown.

        Args:
            doc:    RosettaDocument (Pydantic model) or dict with equivalent keys.
            layers: Which layers to include. Default: all (L0-L3).

        Returns:
            Markdown string.

        Raises:
            ValueError: If doc is empty or missing required fields.
        """
        if doc is None:
            raise ValueError("ROSETTA-SOUL-ERR-001: doc must not be None")

        if layers is None:
            layers = [SoulLayer.L0_IDENTITY, SoulLayer.L1_CRITICAL,
                      SoulLayer.L2_DETAILED, SoulLayer.L3_DEEP]

        # Normalise to dict
        data = self._to_dict(doc)

        sections: List[str] = []

        if SoulLayer.L0_IDENTITY in layers:
            sections.append(self._render_l0(data))

        if SoulLayer.L1_CRITICAL in layers:
            sections.append(self._render_l1(data))

        if SoulLayer.L2_DETAILED in layers:
            sections.append(self._render_l2(data))

        if SoulLayer.L3_DEEP in layers:
            sections.append(self._render_l3(data))

        return "\n\n".join(s for s in sections if s.strip())

    def render_wakeup(self, doc: Any) -> str:
        """Render only L0 + L1 (~170 tokens) for agent wake-up context.

        This is what the agent reads first before any action.
        Equivalent to MemPalace's wake-up context generation.
        """
        return self.render(doc, layers=[SoulLayer.L0_IDENTITY, SoulLayer.L1_CRITICAL])

    def render_from_persona(self, persona: Dict[str, Any]) -> str:
        """Render a SOUL.md from an agent persona library dict.

        This bridges the existing 9 agent personas into the Rosetta soul format.

        Args:
            persona: Dict with keys like 'name', 'role', 'description',
                     'personality', 'capabilities', 'boundaries'.

        Returns:
            Markdown string.
        """
        if not persona:
            raise ValueError("ROSETTA-SOUL-ERR-002: persona dict must not be empty")

        name = persona.get("name", "Unknown Agent")
        role = persona.get("role", persona.get("role_title", "Agent"))
        desc = persona.get("description", persona.get("role_description", ""))
        personality = persona.get("personality", "")
        capabilities = persona.get("capabilities", [])
        boundaries = persona.get("boundaries", persona.get("off_limits_topics", []))

        lines = [
            f"# SOUL — {name}",
            "",
            f"**Role:** {role}",
        ]

        if desc:
            lines.append(f"**Identity:** {desc}")

        if personality:
            lines.append(f"**Personality:** {personality}")

        if capabilities:
            lines.append("")
            lines.append("## Capabilities")
            for cap in capabilities:
                lines.append(f"- {cap}")

        if boundaries:
            lines.append("")
            lines.append("## Boundaries")
            for b in boundaries:
                lines.append(f"- ❌ {b}")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Layer renderers
    # ------------------------------------------------------------------

    def _render_l0(self, data: Dict[str, Any]) -> str:
        """L0 Identity — ~50 tokens. WHO I AM."""
        name = data.get("agent_name", "Unknown")
        agent_id = data.get("agent_id", "?")

        contract = data.get("contract", {})
        agent_type = contract.get("agent_type", "automation")
        role_title = contract.get("role_title", "Agent")
        layer = contract.get("management_layer", "individual")
        department = contract.get("department", "")

        type_label = "Shadow Agent" if agent_type == "shadow" else "Automation Agent"
        shadow_info = ""
        if agent_type == "shadow":
            user = contract.get("shadowed_user_name", contract.get("shadowed_user_id", ""))
            if user:
                shadow_info = f" (shadows: {user})"

        lines = [
            f"# SOUL — {name}",
            "",
            f"**ID:** `{agent_id}`  ",
            f"**Type:** {type_label}{shadow_info}  ",
            f"**Role:** {role_title}  ",
            f"**Layer:** {layer.replace('_', ' ').title()}  ",
        ]
        if department:
            lines.append(f"**Department:** {department}  ")

        return "\n".join(lines)

    def _render_l1(self, data: Dict[str, Any]) -> str:
        """L1 Critical Facts — ~120 tokens. KEY METRICS + PRIORITIES."""
        lines = ["## Critical Facts"]

        # Business metrics from state feed
        state_feed = data.get("state_feed", {})
        entries = state_feed.get("entries", [])
        if entries:
            lines.append("")
            lines.append("### Live Metrics")
            for entry in entries[:5]:  # top 5 metrics only
                name = entry.get("name", "?")
                value = entry.get("value", "?")
                lines.append(f"- **{name}:** {value}")

        # Business plan summary
        bplan = data.get("business_plan")
        if bplan and isinstance(bplan, dict):
            ue = bplan.get("unit_economics", {})
            if ue:
                lines.append("")
                lines.append("### Business Target")
                goal = ue.get("monthly_revenue_goal")
                if goal:
                    lines.append(f"- Revenue goal: ${goal:,.0f}/mo" if isinstance(goal, (int, float)) else f"- Revenue goal: {goal}")
                volume = ue.get("required_monthly_volume")
                if volume:
                    lines.append(f"- Required volume: {volume} units/mo")

        # Top priority tasks
        pipeline = data.get("task_pipeline", {})
        tasks = pipeline.get("tasks", [])
        actionable = [t for t in tasks if t.get("status") in ("queued", "running")]
        if actionable:
            lines.append("")
            lines.append("### Current Priorities")
            for task in actionable[:3]:  # top 3
                lines.append(f"- [{task.get('status', '?')}] {task.get('title', task.get('description', '?'))}")

        # Authority summary
        contract = data.get("contract", {})
        actions = contract.get("authorised_actions", [])
        if actions:
            lines.append("")
            lines.append("### Authorised Actions")
            for action in actions[:5]:
                lines.append(f"- {action}")

        return "\n".join(lines)

    def _render_l2(self, data: Dict[str, Any]) -> str:
        """L2 Detailed — full role description, terminology, task queue."""
        lines = ["## Detailed Context"]

        # Full role description
        contract = data.get("contract", {})
        role_desc = contract.get("role_description", "")
        if role_desc:
            lines.append("")
            lines.append("### Role Description")
            lines.append(role_desc)

        # Reporting structure
        reports_to = contract.get("reports_to")
        direct_reports = contract.get("direct_reports", [])
        if reports_to or direct_reports:
            lines.append("")
            lines.append("### Org Structure")
            if reports_to:
                lines.append(f"- Reports to: {reports_to}")
            if direct_reports:
                lines.append(f"- Direct reports: {', '.join(direct_reports)}")

        # Industry terminology
        terminology = data.get("terminology", {})
        industry = terminology.get("industry", "")
        if industry and industry != "general":
            lines.append("")
            lines.append(f"### Domain — {industry}")
            keywords = terminology.get("domain_keywords", [])
            if keywords:
                lines.append(f"Keywords: {', '.join(keywords[:15])}")
            off_limits = terminology.get("off_limits_topics", [])
            if off_limits:
                lines.append(f"Off-limits: {', '.join(off_limits[:10])}")

        # Full task pipeline
        pipeline = data.get("task_pipeline", {})
        tasks = pipeline.get("tasks", [])
        if tasks:
            lines.append("")
            lines.append("### Task Pipeline")
            for task in tasks[:10]:
                status = task.get("status", "?")
                title = task.get("title", task.get("description", "?"))
                priority = task.get("priority", "?")
                lines.append(f"- [{status}] P{priority}: {title}")

        return "\n".join(lines)

    def _render_l3(self, data: Dict[str, Any]) -> str:
        """L3 Deep — shadow observations, HITL throughput models."""
        lines = ["## Deep Context"]

        # Shadow observations
        observations = data.get("shadow_observations", [])
        if observations:
            lines.append("")
            lines.append("### Shadow Observations")
            for obs in observations[-10:]:  # last 10
                if isinstance(obs, dict):
                    lines.append(f"- {obs.get('summary', obs.get('observation', str(obs)[:100]))}")
                else:
                    lines.append(f"- {str(obs)[:100]}")

        # HITL throughput models
        hitl = data.get("hitl_models", [])
        if hitl:
            lines.append("")
            lines.append("### HITL Throughput")
            for model in hitl:
                if isinstance(model, dict):
                    task_type = model.get("task_type", "?")
                    daily = model.get("daily_capacity", "?")
                    lines.append(f"- {task_type}: {daily} tasks/day")

        # Base state goals
        base = data.get("base_state")
        if base and isinstance(base, dict):
            goals = base.get("goals", [])
            if goals:
                lines.append("")
                lines.append("### Goals")
                for goal in goals[:5]:
                    if isinstance(goal, dict):
                        lines.append(f"- [{goal.get('status', '?')}] {goal.get('description', '?')}")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_dict(doc: Any) -> Dict[str, Any]:
        """Normalise RosettaDocument or dict to plain dict."""
        if isinstance(doc, dict):
            return doc

        # Pydantic model
        if hasattr(doc, "model_dump"):
            try:
                return doc.model_dump()  # type: ignore[union-attr]
            except Exception:  # ROSETTA-SOUL-ERR-003
                logger.warning("ROSETTA-SOUL-ERR-003: model_dump() failed, falling back to __dict__")

        if hasattr(doc, "__dict__"):
            return doc.__dict__

        raise ValueError(
            "ROSETTA-SOUL-ERR-004: doc must be a RosettaDocument, dict, or Pydantic model"
        )
