"""Selling prompt composer for influence-trained agents.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations
import logging

from typing import Any, Dict, List, Optional

from agent_persona_library._frameworks import INFLUENCE_FRAMEWORKS, InfluenceFramework
from agent_persona_library._roster import AGENT_ROSTER, AgentPersonaDefinition

# ---------------------------------------------------------------------------
# Selling Prompt Composer
# ---------------------------------------------------------------------------


class SellingPromptComposer:
    """Assembles influence-trained prompts for self-selling agents.

    Wires together:
    - AgentPersonaDefinition (who is speaking)
    - InfluenceFramework rules (how they speak)
    - ProspectProfile (who they're speaking to)
    - Live system data (what proof is available)
    - RosettaDocument fields (domain vocabulary, business math)
    """

    def __init__(
        self,
        frameworks: Optional[Dict[str, InfluenceFramework]] = None,
        agents: Optional[Dict[str, AgentPersonaDefinition]] = None,
    ) -> None:
        self._frameworks = frameworks or INFLUENCE_FRAMEWORKS
        self._agents = agents or AGENT_ROSTER

    # ------------------------------------------------------------------
    # Public composition methods
    # ------------------------------------------------------------------

    def compose_outreach_prompt(
        self,
        agent: AgentPersonaDefinition,
        prospect_context: Dict[str, Any],
        live_stats: Dict[str, Any],
    ) -> str:
        """Build the complete system prompt for an outreach message."""
        active_fw = self.select_active_frameworks(agent, "outreach", "first_contact")
        fw_block = self.format_framework_rules(active_fw)

        prospect_block = self._format_prospect_context(prospect_context)
        stats_block = self._format_live_stats(live_stats)

        return (
            f"{agent.system_prompt}\n\n"
            f"=== ACTIVE INFLUENCE RULES FOR THIS OUTREACH ===\n{fw_block}\n\n"
            f"=== PROSPECT CONTEXT ===\n{prospect_block}\n\n"
            f"=== LIVE MURPHY STATS ===\n{stats_block}\n\n"
            f"=== AVAILABLE ACTIONS ===\n"
            + "\n".join(f"- {a}" for a in agent.action_capabilities)
        )

    def compose_trial_interaction_prompt(
        self,
        agent: AgentPersonaDefinition,
        trial_context: Dict[str, Any],
        shadow_observations: List[Dict[str, Any]],
    ) -> str:
        """Build the prompt for a trial interaction."""
        active_fw = self.select_active_frameworks(agent, "trial", "trial_day_milestone")
        fw_block = self.format_framework_rules(active_fw)

        trial_block = self._format_trial_context(trial_context)
        obs_block = self._format_shadow_observations(shadow_observations)

        return (
            f"{agent.system_prompt}\n\n"
            f"=== ACTIVE INFLUENCE RULES FOR THIS TRIAL INTERACTION ===\n{fw_block}\n\n"
            f"=== TRIAL CONTEXT ===\n{trial_block}\n\n"
            f"=== SHADOW AGENT OBSERVATIONS ===\n{obs_block}\n\n"
            f"=== AVAILABLE ACTIONS ===\n"
            + "\n".join(f"- {a}" for a in agent.action_capabilities)
        )

    def compose_conversion_prompt(
        self,
        agent: AgentPersonaDefinition,
        trial_report: Dict[str, Any],
        shadow_patterns: List[Dict[str, Any]],
    ) -> str:
        """Build the prompt for the conversion message at trial end."""
        active_fw = self.select_active_frameworks(agent, "conversion", "trial_ending")
        fw_block = self.format_framework_rules(active_fw)

        report_block = self._format_trial_report(trial_report)
        patterns_block = self._format_shadow_patterns(shadow_patterns)

        return (
            f"{agent.system_prompt}\n\n"
            f"=== ACTIVE INFLUENCE RULES FOR CONVERSION ===\n{fw_block}\n\n"
            f"=== TRIAL REPORT SUMMARY ===\n{report_block}\n\n"
            f"=== SHADOW AGENT PATTERNS (SCARCITY ASSETS) ===\n{patterns_block}\n\n"
            f"=== AVAILABLE ACTIONS ===\n"
            + "\n".join(f"- {a}" for a in agent.action_capabilities)
        )

    def select_active_frameworks(
        self,
        agent: AgentPersonaDefinition,
        phase: str,
        trigger: str,
    ) -> List[InfluenceFramework]:
        """Select which influence frameworks are active for this situation."""
        active: List[InfluenceFramework] = []
        for fw_id in agent.influence_frameworks:
            fw = self._frameworks.get(fw_id)
            if fw is None:
                continue
            if phase in fw.applicable_phases or not fw.applicable_phases:
                active.append(fw)
        return active

    def format_framework_rules(self, frameworks: List[InfluenceFramework]) -> str:
        """Format influence rules as LLM system prompt instructions."""
        if not frameworks:
            return "(no active influence rules for this phase)"
        lines = []
        for fw in frameworks:
            lines.append(
                f"[{fw.source.upper()} — {fw.principle_name}]\n"
                f"Rule: {fw.rule}\n"
                f"When: {fw.trigger_condition}\n"
                f"Do: {fw.action_template}"
            )
        return "\n\n".join(lines)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _format_prospect_context(self, context: Dict[str, Any]) -> str:
        if not context:
            return "(no prospect context provided)"
        parts = []
        for key, val in context.items():
            parts.append(f"{key}: {val}")
        return "\n".join(parts)

    def _format_live_stats(self, stats: Dict[str, Any]) -> str:
        if not stats:
            return "(no live stats available)"
        parts = []
        for key, val in stats.items():
            parts.append(f"{key}: {val}")
        return "\n".join(parts)

    def _format_trial_context(self, context: Dict[str, Any]) -> str:
        if not context:
            return "(no trial context provided)"
        parts = []
        for key, val in context.items():
            parts.append(f"{key}: {val}")
        return "\n".join(parts)

    def _format_shadow_observations(self, observations: List[Dict[str, Any]]) -> str:
        if not observations:
            return "(no shadow agent observations yet)"
        lines = []
        for obs in observations:
            desc = obs.get("description", str(obs))
            confidence = obs.get("confidence", "unknown")
            lines.append(f"- {desc} (confidence: {confidence})")
        return "\n".join(lines)

    def _format_trial_report(self, report: Dict[str, Any]) -> str:
        if not report:
            return "(no trial report available)"
        parts = []
        for key, val in report.items():
            parts.append(f"{key}: {val}")
        return "\n".join(parts)

    def _format_shadow_patterns(self, patterns: List[Dict[str, Any]]) -> str:
        if not patterns:
            return "(no shadow patterns learned yet)"
        lines = []
        for p in patterns:
            name = p.get("pattern_name", str(p))
            time_saved = p.get("time_saved_hours_per_month", "unknown")
            confidence = p.get("confidence", "unknown")
            lines.append(
                f"- Pattern: {name} | Time saved/month: {time_saved}h | Confidence: {confidence}"
            )
        return "\n".join(lines)
