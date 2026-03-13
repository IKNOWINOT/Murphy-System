"""Rosetta Selling Bridge — wires self-selling agent personas into the Rosetta system.

This module converts ``AgentPersonaDefinition`` objects from ``agent_persona_library``
into Rosetta-compatible structures and registers them with the existing
``InoniOrgBootstrap`` agent framework.

Bridges:
  - ``AgentPersonaDefinition`` → ``EmployeeContract`` + ``RosettaDocument`` fields
  - Persona information APIs → ``StateFeed`` entries
  - Persona trigger conditions → ``EventBackbone`` subscriptions
  - Persona gate definitions → ``AlertRule`` instances
  - All personas → ``InoniOrgBootstrap`` agent config format

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

# REMEDIATION: R48-relimport — convert relative to absolute imports for standalone module
from agent_persona_library import (
    AGENT_ROSTER,
    INFLUENCE_FRAMEWORKS,
    AgentPersonaDefinition,
    InfluenceFramework,
    SellingPromptComposer,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional soft imports — the bridge degrades gracefully if upstream modules
# are not installed in the test environment.
# ---------------------------------------------------------------------------

try:
    from rosetta.rosetta_models import (
        AgentType,
        EmployeeContract,
        IndustryTerminology,
        ManagementLayer,
        MetricDirection,
        RosettaDocument,
        StateFeed,
        StateFeedEntry,
        TermDefinition,
    )
    _ROSETTA_AVAILABLE = True
except ImportError:  # pragma: no cover
    _ROSETTA_AVAILABLE = False
    AgentType = None
    EmployeeContract = None
    IndustryTerminology = None
    ManagementLayer = None
    RosettaDocument = None
    StateFeed = None
    StateFeedEntry = None
    MetricDirection = None
    TermDefinition = None

try:
    from rosetta.rosetta_document_builder import RosettaDocumentBuilder
    _BUILDER_AVAILABLE = True
except ImportError:  # pragma: no cover
    _BUILDER_AVAILABLE = False
    RosettaDocumentBuilder = None

try:
    from avatar.avatar_models import AvatarProfile, AvatarStyle, AvatarVoice
    from avatar.persona_injector import PersonaInjector
    _PERSONA_AVAILABLE = True
except ImportError:  # pragma: no cover
    _PERSONA_AVAILABLE = False
    PersonaInjector = None
    AvatarProfile = None
    AvatarVoice = None
    AvatarStyle = None

try:
    from alert_rules_engine import AlertRule, AlertSeverity, Comparator
    _ALERTS_AVAILABLE = True
except ImportError:  # pragma: no cover
    _ALERTS_AVAILABLE = False
    AlertRule = None
    AlertSeverity = None
    Comparator = None


# ---------------------------------------------------------------------------
# Management layer mapping helpers
# ---------------------------------------------------------------------------

_MGMT_LAYER_MAP: Dict[str, str] = {
    "executive": "executive",
    "middle": "middle",
    "individual": "individual",
    "individual_contributor": "individual",
}


def _resolve_management_layer(layer_str: str) -> str:
    """Resolve a freeform management layer string to a valid ManagementLayer value."""
    return _MGMT_LAYER_MAP.get(layer_str.lower(), "individual")


# ---------------------------------------------------------------------------
# RosettaSellingBridge
# ---------------------------------------------------------------------------


class RosettaSellingBridge:
    """Bridges the self-selling agent personas into the Rosetta document system.

    Converts AgentPersonaDefinition → EmployeeContract + RosettaDocument fields.
    Wires into InoniOrgBootstrap agent registration.
    Connects PersonaInjector for LLM prompt enrichment.
    Maps information_apis to StateFeed entries.
    Maps trigger_conditions to EventBackbone subscriptions.
    Maps gate_definitions to AlertRule instances.
    """

    def __init__(
        self,
        agent_roster: Optional[Dict[str, AgentPersonaDefinition]] = None,
        composer: Optional[SellingPromptComposer] = None,
    ) -> None:
        self._roster = agent_roster or AGENT_ROSTER
        self._composer = composer or SellingPromptComposer()
        self._injector = PersonaInjector() if _PERSONA_AVAILABLE else None

    # ------------------------------------------------------------------
    # Core conversion methods
    # ------------------------------------------------------------------

    def persona_to_employee_contract(self, persona: AgentPersonaDefinition) -> Dict[str, Any]:
        """Convert persona to EmployeeContract-compatible fields."""
        rf = persona.rosetta_fields
        layer = _resolve_management_layer(rf.get("management_layer", "individual"))
        return {
            "agent_type": rf.get("agent_type", "automation"),
            "role_title": rf.get("role_title", persona.title),
            "role_description": rf.get("role_description", ""),
            "management_layer": layer,
            "department": persona.department,
            "organisation_id": "inoni_llc",
            "authorised_permissions": rf.get("permissions", []),
        }

    def persona_to_rosetta_document(
        self,
        persona: AgentPersonaDefinition,
        business_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Build a full RosettaDocument dict for this selling agent.

        Returns a plain dict that can be consumed by RosettaDocumentBuilder
        or used directly for testing without the full Rosetta stack.
        """
        business_context = business_context or {}
        contract_fields = self.persona_to_employee_contract(persona)
        rf = persona.rosetta_fields

        state_entries = []
        for api in persona.information_apis:
            state_entries.append(
                {
                    "metric_name": api["api_id"],
                    "value": 0.0,
                    "unit": "raw",
                    "target": None,
                    "source": api.get("endpoint", ""),
                    "description": api.get("description", ""),
                }
            )

        terminology = {
            "industry": rf.get("industry", "automation_saas"),
            "domain_keywords": rf.get("domain_keywords", []),
        }

        return {
            "agent_id": persona.agent_id,
            "agent_name": persona.name,
            "contract": contract_fields,
            "terminology": terminology,
            "state_feed_entries": state_entries,
            "business_context": business_context,
            "influence_frameworks": persona.influence_frameworks,
            "system_prompt": persona.system_prompt,
            "communication_style": persona.communication_style,
            "kaia_mix": persona.kaia_mix,
        }

    def persona_to_bootstrap_config(self, persona: AgentPersonaDefinition) -> Dict[str, Any]:
        """Convert persona to InoniOrgBootstrap agent config format.

        The returned dict is compatible with the ``agent_configs`` list structure
        used inside ``InoniOrgBootstrap.bootstrap()``.
        """
        rf = persona.rosetta_fields
        return {
            "role": persona.agent_id,
            "dept": persona.department,
            "perms": rf.get("permissions", []),
            "avatar": {
                "name": persona.name,
                "title": persona.title,
                "personality": persona.personality,
                "style": persona.communication_style,
                "system_prompt": persona.system_prompt,
            },
        }

    def create_information_api_feeds(
        self, persona: AgentPersonaDefinition
    ) -> List[Dict[str, Any]]:
        """Map agent's information_apis to live data feed configurations.

        Each returned dict represents a StateFeed-compatible configuration
        that can be used to provision live metric polling.
        """
        feeds = []
        for api in persona.information_apis:
            feeds.append(
                {
                    "feed_id": f"{persona.agent_id}__{api['api_id']}",
                    "agent_id": persona.agent_id,
                    "api_id": api["api_id"],
                    "description": api.get("description", ""),
                    "endpoint": api.get("endpoint", ""),
                    "refresh_seconds": api.get("refresh_seconds", 300),
                    "metric_name": api["api_id"],
                }
            )
        return feeds

    def create_trigger_subscriptions(
        self, persona: AgentPersonaDefinition
    ) -> List[Dict[str, Any]]:
        """Map agent's trigger_conditions to EventBackbone event subscriptions."""
        subscriptions = []
        for trigger in persona.trigger_conditions:
            subscriptions.append(
                {
                    "subscription_id": f"{persona.agent_id}__{trigger['trigger_id']}",
                    "agent_id": persona.agent_id,
                    "trigger_id": trigger["trigger_id"],
                    "event_type": trigger.get("event", trigger["trigger_id"]),
                    "description": trigger.get("description", ""),
                    "threshold": trigger.get("threshold"),
                    "schedule": trigger.get("schedule"),
                    "handler": persona.agent_id,
                }
            )
        return subscriptions

    def create_gate_rules(
        self, persona: AgentPersonaDefinition
    ) -> List[Dict[str, Any]]:
        """Map agent's gate_definitions to AlertRule-compatible dicts.

        If the AlertRulesEngine is available, the dicts can be passed directly
        to ``AlertRulesEngine.add_rule(AlertRule(**dict))``.
        """
        rules = []
        for gate in persona.gate_definitions:
            comparator_raw = gate.get("comparator", "gte")
            rules.append(
                {
                    "rule_id": f"{persona.agent_id}__{gate['gate_id']}",
                    "name": gate.get("name", gate["gate_id"]),
                    "severity": "warning",
                    "metric": gate.get("metric", ""),
                    "comparator": comparator_raw,
                    "threshold": gate.get("threshold", 0.0),
                    "description": gate.get("description", ""),
                    "agent_id": persona.agent_id,
                    "action": gate.get("action", ""),
                }
            )
        return rules

    def register_all_selling_agents(self) -> Dict[str, Any]:
        """Register all self-selling agent personas into the org chart.

        Returns a dict keyed by agent_id with the bootstrap config, Rosetta
        document dict, feed configs, trigger subscriptions, and gate rules
        for each agent.
        """
        registry: Dict[str, Any] = {}
        for agent_id, persona in self._roster.items():
            registry[agent_id] = {
                "bootstrap_config": self.persona_to_bootstrap_config(persona),
                "rosetta_document": self.persona_to_rosetta_document(persona),
                "information_feeds": self.create_information_api_feeds(persona),
                "trigger_subscriptions": self.create_trigger_subscriptions(persona),
                "gate_rules": self.create_gate_rules(persona),
            }
            logger.info("Registered selling agent: %s (%s)", persona.name, agent_id)
        return registry

    # ------------------------------------------------------------------
    # PersonaInjector integration
    # ------------------------------------------------------------------

    def inject_selling_persona(
        self,
        persona: AgentPersonaDefinition,
        base_prompt: str,
        prospect_context: Optional[Dict[str, Any]] = None,
        live_stats: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Enrich a base prompt with the agent's selling persona.

        Falls back to simple string composition if PersonaInjector is not available.
        """
        prospect_context = prospect_context or {}
        live_stats = live_stats or {}

        enriched_base = self._composer.compose_outreach_prompt(
            agent=persona,
            prospect_context=prospect_context,
            live_stats=live_stats,
        )

        if self._injector is not None and _PERSONA_AVAILABLE:
            voice_map = {
                "executive": AvatarVoice.AUTHORITATIVE,
                "sales": AvatarVoice.FRIENDLY,
                "customer_success": AvatarVoice.EMPATHETIC,
                "marketing": AvatarVoice.ENERGETIC,
                "technical_operations": AvatarVoice.PROFESSIONAL,
                "trial_intelligence": AvatarVoice.PROFESSIONAL,
                "communications": AvatarVoice.NEUTRAL,
                "partnerships": AvatarVoice.PROFESSIONAL,
            }
            style_map = {
                "executive": AvatarStyle.EXECUTIVE,
                "sales": AvatarStyle.CASUAL,
                "customer_success": AvatarStyle.SUPPORTIVE,
                "marketing": AvatarStyle.CREATIVE,
                "technical_operations": AvatarStyle.TECHNICAL,
                "trial_intelligence": AvatarStyle.TECHNICAL,
                "communications": AvatarStyle.FORMAL,
                "partnerships": AvatarStyle.FORMAL,
            }
            avatar = AvatarProfile(
                avatar_id=persona.agent_id,
                name=persona.name,
                voice=voice_map.get(persona.department, AvatarVoice.PROFESSIONAL),
                style=style_map.get(persona.department, AvatarStyle.FORMAL),
                personality_traits=persona.kaia_mix,
                knowledge_domains=persona.rosetta_fields.get("domain_keywords", []),
                greeting_template=f"Hi, I'm {persona.name}. How can I help?",
            )
            return self._injector.inject(base_prompt=enriched_base, avatar=avatar)

        return f"[{persona.name} — {persona.title}]\n\n{enriched_base}\n\n{base_prompt}"


# ---------------------------------------------------------------------------
# AgentCollaborationProtocol
# ---------------------------------------------------------------------------


class AgentCollaborationProtocol:
    """Defines how selling agents hand off, escalate, and collaborate.

    The collaboration follows the org chart:
    - Casey Torres discovers and contacts → hands qualified leads to Alex Reeves
    - Alex Reeves qualifies and demos → hands closed deals to Taylor Kim
    - Taylor Kim shepherds trial → works with Quinn Harper on shadow agent
    - Quinn Harper translates shadow observations → feeds back to Casey for
      outreach refinement
    - Morgan Vale oversees all revenue decisions → approves pricing, major deals
    - Jordan Blake generates content that all agents reference
    - Sam Ortega provides the system proof that all agents cite
    - Murphy (AI Comms) handles routing and public face
    - Drew Nakamura manages partnerships and referrals

    Any agent can trigger any other agent's action through the EventBackbone.
    The Librarian routes tasks to the right agent based on message content
    (route_to_agent pattern from InoniOrgBootstrap).
    """

    def define_handoff_rules(self) -> List[Dict[str, Any]]:
        """Define agent-to-agent handoff conditions."""
        return [
            {
                "handoff_id": "casey_to_alex",
                "from_agent": "casey_torres",
                "to_agent": "alex_reeves",
                "condition": "prospect_replied_to_outreach",
                "description": (
                    "Casey Torres hands off any prospect who has replied to outreach to "
                    "Alex Reeves for qualification."
                ),
                "data_passed": [
                    "prospect_profile",
                    "outreach_history",
                    "prospect_website_data",
                    "initial_lead_score",
                ],
            },
            {
                "handoff_id": "alex_to_taylor",
                "from_agent": "alex_reeves",
                "to_agent": "taylor_kim",
                "condition": "lead_score_gte_0.7_and_demo_completed",
                "description": (
                    "Alex Reeves hands qualified, demo-completed leads to Taylor Kim "
                    "for trial shepherding."
                ),
                "data_passed": [
                    "prospect_profile",
                    "qualification_notes",
                    "demo_recording",
                    "confirmed_pain_points",
                    "lead_score",
                ],
            },
            {
                "handoff_id": "taylor_to_quinn",
                "from_agent": "taylor_kim",
                "to_agent": "quinn_harper",
                "condition": "trial_day_1_completed",
                "description": (
                    "Taylor Kim initiates Quinn Harper involvement once the trial starts "
                    "and shadow observations begin accumulating."
                ),
                "data_passed": [
                    "trial_id",
                    "prospect_id",
                    "shadow_agent_id",
                    "trial_start_date",
                ],
            },
            {
                "handoff_id": "quinn_to_casey",
                "from_agent": "quinn_harper",
                "to_agent": "casey_torres",
                "condition": "high_confidence_patterns_identified",
                "description": (
                    "Quinn Harper feeds pattern intelligence back to Casey Torres "
                    "to refine outreach for similar prospects."
                ),
                "data_passed": [
                    "industry_patterns",
                    "common_pain_points",
                    "effective_outreach_hooks",
                ],
            },
            {
                "handoff_id": "taylor_to_alex_conversion",
                "from_agent": "taylor_kim",
                "to_agent": "alex_reeves",
                "condition": "trial_conversion_readiness_met",
                "description": (
                    "Taylor Kim hands off to Alex Reeves when trial shows conversion "
                    "readiness — Alex closes the deal."
                ),
                "data_passed": [
                    "trial_report",
                    "shadow_patterns",
                    "demonstrated_value",
                    "recommended_plan",
                ],
            },
            {
                "handoff_id": "murphy_routing",
                "from_agent": "murphy",
                "to_agent": "dynamic",
                "condition": "inbound_message_requires_specialist",
                "description": (
                    "Murphy routes any inbound message to the appropriate specialist agent "
                    "based on message content and current pipeline stage."
                ),
                "data_passed": [
                    "message_content",
                    "prospect_context",
                    "conversation_history",
                ],
            },
            {
                "handoff_id": "drew_to_casey",
                "from_agent": "drew_nakamura",
                "to_agent": "casey_torres",
                "condition": "partner_referral_received",
                "description": (
                    "Drew Nakamura passes warm referrals from partners directly to "
                    "Casey Torres for personalized outreach."
                ),
                "data_passed": [
                    "referral_profile",
                    "partner_context",
                    "referral_warmth_score",
                ],
            },
        ]

    def define_escalation_paths(self) -> List[Dict[str, Any]]:
        """Define when and how agents escalate to higher authority."""
        return [
            {
                "escalation_id": "deal_above_threshold",
                "from_agent": "alex_reeves",
                "to_agent": "morgan_vale",
                "condition": "deal_value_gt_5000_usd",
                "description": (
                    "Alex Reeves escalates deals above $5,000 to Morgan Vale for approval."
                ),
                "urgency": "high",
            },
            {
                "escalation_id": "custom_pricing_request",
                "from_agent": "alex_reeves",
                "to_agent": "morgan_vale",
                "condition": "prospect_requests_custom_pricing",
                "description": (
                    "Any custom pricing request is escalated to Morgan Vale."
                ),
                "urgency": "medium",
            },
            {
                "escalation_id": "trial_dropout",
                "from_agent": "taylor_kim",
                "to_agent": "alex_reeves",
                "condition": "trial_engagement_critical_low",
                "description": (
                    "Taylor Kim escalates to Alex Reeves when trial engagement drops "
                    "to critical levels."
                ),
                "urgency": "high",
            },
            {
                "escalation_id": "system_outage_during_trial",
                "from_agent": "sam_ortega",
                "to_agent": "corey_post",
                "condition": "system_outage_during_active_trial",
                "description": (
                    "Sam Ortega escalates to Corey Post if a system outage occurs "
                    "while an active trial is running."
                ),
                "urgency": "critical",
            },
            {
                "escalation_id": "compliance_violation",
                "from_agent": "casey_torres",
                "to_agent": "corey_post",
                "condition": "can_spam_violation_detected",
                "description": (
                    "Casey Torres escalates any CAN-SPAM compliance issue immediately "
                    "to Corey Post."
                ),
                "urgency": "critical",
            },
            {
                "escalation_id": "revenue_miss",
                "from_agent": "morgan_vale",
                "to_agent": "corey_post",
                "condition": "monthly_revenue_below_90pct_target",
                "description": (
                    "Morgan Vale escalates to Corey Post when monthly revenue is "
                    "below 90% of target."
                ),
                "urgency": "high",
            },
            {
                "escalation_id": "brand_violation",
                "from_agent": "jordan_blake",
                "to_agent": "morgan_vale",
                "condition": "content_fails_brand_gate",
                "description": (
                    "Jordan Blake escalates content that fails the brand consistency gate "
                    "to Morgan Vale for manual review."
                ),
                "urgency": "medium",
            },
        ]

    def define_cross_department_triggers(self) -> List[Dict[str, Any]]:
        """Define triggers that cross department boundaries."""
        return [
            {
                "trigger_id": "new_customer_converted",
                "originating_agent": "alex_reeves",
                "notified_agents": ["taylor_kim", "morgan_vale", "sam_ortega", "drew_nakamura"],
                "event": "prospect_converted_to_customer",
                "description": (
                    "When Alex closes a deal, it triggers: Taylor Kim to start onboarding, "
                    "Morgan Vale to update revenue metrics, Sam Ortega to provision access, "
                    "Drew Nakamura to record referral attribution."
                ),
            },
            {
                "trigger_id": "system_health_warning",
                "originating_agent": "sam_ortega",
                "notified_agents": ["murphy", "taylor_kim", "alex_reeves"],
                "event": "system_health_degraded",
                "description": (
                    "When Sam detects system degradation, Murphy is notified to pause "
                    "outgoing communications, Taylor Kim to pause trial interactions, "
                    "Alex Reeves to hold demos."
                ),
            },
            {
                "trigger_id": "competitor_pricing_change",
                "originating_agent": "jordan_blake",
                "notified_agents": ["morgan_vale", "alex_reeves", "casey_torres"],
                "event": "competitor_pricing_change_detected",
                "description": (
                    "Jordan Blake's competitive intelligence notifies Morgan Vale "
                    "(pricing review), Alex Reeves (objection handling update), "
                    "and Casey Torres (outreach angle update)."
                ),
            },
            {
                "trigger_id": "shadow_pattern_ready",
                "originating_agent": "quinn_harper",
                "notified_agents": ["taylor_kim", "casey_torres"],
                "event": "high_confidence_pattern_identified",
                "description": (
                    "Quinn Harper notifies Taylor Kim (include in trial report) and "
                    "Casey Torres (use as outreach hook for similar prospects)."
                ),
            },
            {
                "trigger_id": "partner_milestone",
                "originating_agent": "drew_nakamura",
                "notified_agents": ["morgan_vale", "jordan_blake"],
                "event": "partner_revenue_milestone",
                "description": (
                    "Drew Nakamura notifies Morgan Vale (revenue update) and "
                    "Jordan Blake (partner success story for content)."
                ),
            },
            {
                "trigger_id": "content_published",
                "originating_agent": "jordan_blake",
                "notified_agents": ["casey_torres", "alex_reeves", "murphy"],
                "event": "new_content_published",
                "description": (
                    "Jordan Blake notifies Casey Torres (new hook for outreach), "
                    "Alex Reeves (new proof point for demos), "
                    "Murphy (updated reference material for inbound responses)."
                ),
            },
        ]

    def get_full_protocol(self) -> Dict[str, Any]:
        """Return the complete collaboration protocol as a single dict."""
        return {
            "handoff_rules": self.define_handoff_rules(),
            "escalation_paths": self.define_escalation_paths(),
            "cross_department_triggers": self.define_cross_department_triggers(),
        }

    def validate_no_dead_ends(self) -> List[str]:
        """Validate that no agent has triggers with no reachable action.

        Returns a list of validation error strings (empty = all valid).
        """
        errors: List[str] = []
        handoffs = self.define_handoff_rules()
        escalations = self.define_escalation_paths()
        known_agents = set(AGENT_ROSTER.keys()) | {"corey_post"}

        for h in handoffs:
            if h["from_agent"] not in known_agents:
                errors.append(f"Handoff {h['handoff_id']}: unknown from_agent '{h['from_agent']}'")
            if h["to_agent"] not in known_agents and h["to_agent"] != "dynamic":
                errors.append(f"Handoff {h['handoff_id']}: unknown to_agent '{h['to_agent']}'")

        for e in escalations:
            if e["from_agent"] not in known_agents:
                errors.append(
                    f"Escalation {e['escalation_id']}: unknown from_agent '{e['from_agent']}'"
                )
            if e["to_agent"] not in known_agents:
                errors.append(
                    f"Escalation {e['escalation_id']}: unknown to_agent '{e['to_agent']}'"
                )

        return errors
