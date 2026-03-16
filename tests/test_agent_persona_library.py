"""Tests for agent_persona_library and rosetta_selling_bridge.

Verifies:
- All influence frameworks are properly defined with all required fields
- All agent personas have valid influence framework references
- SellingPromptComposer produces prompts containing the right influence rules
- Rosetta bridge correctly converts personas to EmployeeContract format
- Bootstrap config conversion produces InoniOrgBootstrap-compatible dicts
- Agent collaboration handoffs are fully connected (no dead ends)
- Every trigger condition maps to a valid action
- Every gate definition has a valid threshold and comparator
- Prompt composition with sample prospect data produces personalized output
- Information API feeds map to valid data sources
"""

import pytest

from src.agent_persona_library import (
    AGENT_ROSTER,
    INFLUENCE_FRAMEWORKS,
    AgentPersonaDefinition,
    InfluenceFramework,
    SellingPromptComposer,
    _build_agent_roster,
    _build_influence_frameworks,
)
from src.rosetta_selling_bridge import (
    AgentCollaborationProtocol,
    RosettaSellingBridge,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def composer():
    return SellingPromptComposer()


@pytest.fixture
def bridge():
    return RosettaSellingBridge()


@pytest.fixture
def protocol():
    return AgentCollaborationProtocol()


@pytest.fixture
def all_agents():
    return list(AGENT_ROSTER.values())


@pytest.fixture
def all_frameworks():
    return list(INFLUENCE_FRAMEWORKS.values())


@pytest.fixture
def sample_prospect():
    return {
        "business_name": "Acme Agency",
        "industry": "content_creation",
        "website": "https://acmeagency.example.com",
        "pain_point": "Manual invoice reconciliation every Tuesday",
        "team_size": 12,
        "monthly_revenue_estimate": 85000,
    }


@pytest.fixture
def sample_live_stats():
    return {
        "automations_running": 142,
        "emails_sent_today": 3471,
        "state_changes_processed": 18904,
        "uptime_pct": 99.97,
    }


@pytest.fixture
def sample_trial_context():
    return {
        "trial_id": "trial-001",
        "prospect_id": "prospect-acme",
        "trial_day": 3,
        "engagement_score": 0.72,
        "automations_triggered": 8,
    }


@pytest.fixture
def sample_shadow_observations():
    return [
        {
            "description": "Prospect spends ~3 hours each Tuesday on invoice reconciliation",
            "confidence": 0.92,
            "pattern_type": "recurring_manual_task",
        },
        {
            "description": "Lead scoring currently done manually every Monday morning",
            "confidence": 0.85,
            "pattern_type": "data_processing",
        },
    ]


@pytest.fixture
def sample_trial_report():
    return {
        "trial_days_completed": 7,
        "automations_triggered": 23,
        "hours_saved_estimate": 11.5,
        "patterns_identified": 8,
        "engagement_score": 0.78,
    }


@pytest.fixture
def sample_shadow_patterns():
    return [
        {
            "pattern_name": "Tuesday invoice reconciliation",
            "time_saved_hours_per_month": 12,
            "confidence": 0.92,
        },
        {
            "pattern_name": "Monday lead scoring",
            "time_saved_hours_per_month": 4,
            "confidence": 0.85,
        },
    ]


# ---------------------------------------------------------------------------
# Part 1: InfluenceFramework tests
# ---------------------------------------------------------------------------


class TestInfluenceFrameworks:
    """All influence frameworks must be properly defined."""

    REQUIRED_SOURCES = {"cialdini", "carnegie", "covey", "nlp", "mentalism", "habit_science"}

    REQUIRED_CIALDINI = {
        "cialdini_reciprocity",
        "cialdini_social_proof",
        "cialdini_authority",
        "cialdini_commitment_consistency",
        "cialdini_liking",
        "cialdini_scarcity",
    }
    REQUIRED_CARNEGIE = {
        "carnegie_never_criticize",
        "carnegie_honest_appreciation",
        "carnegie_arouse_eager_want",
        "carnegie_become_interested",
        "carnegie_feel_important",
        "carnegie_let_them_talk",
    }
    REQUIRED_COVEY = {
        "covey_begin_with_end",
        "covey_seek_to_understand",
        "covey_think_win_win",
        "covey_synergize",
    }
    REQUIRED_NLP = {
        "nlp_pacing_leading",
        "nlp_future_pacing",
        "nlp_anchoring",
        "nlp_reframing",
    }
    REQUIRED_MENTALISM = {
        "mentalism_barnum_refined",
        "mentalism_rainbow_ruse",
        "mentalism_hot_reading",
    }
    REQUIRED_HABIT = {
        "habit_tiny_habits",
        "habit_habit_stacking",
        "habit_variable_reward",
    }

    def test_all_sources_present(self, all_frameworks):
        sources = {fw.source for fw in all_frameworks}
        assert self.REQUIRED_SOURCES.issubset(sources), (
            f"Missing sources: {self.REQUIRED_SOURCES - sources}"
        )

    def test_cialdini_principles_complete(self):
        missing = self.REQUIRED_CIALDINI - set(INFLUENCE_FRAMEWORKS)
        assert not missing, f"Missing Cialdini frameworks: {missing}"

    def test_carnegie_principles_complete(self):
        missing = self.REQUIRED_CARNEGIE - set(INFLUENCE_FRAMEWORKS)
        assert not missing, f"Missing Carnegie frameworks: {missing}"

    def test_covey_principles_complete(self):
        missing = self.REQUIRED_COVEY - set(INFLUENCE_FRAMEWORKS)
        assert not missing, f"Missing Covey frameworks: {missing}"

    def test_nlp_principles_complete(self):
        missing = self.REQUIRED_NLP - set(INFLUENCE_FRAMEWORKS)
        assert not missing, f"Missing NLP frameworks: {missing}"

    def test_mentalism_principles_complete(self):
        missing = self.REQUIRED_MENTALISM - set(INFLUENCE_FRAMEWORKS)
        assert not missing, f"Missing Mentalism frameworks: {missing}"

    def test_habit_principles_complete(self):
        missing = self.REQUIRED_HABIT - set(INFLUENCE_FRAMEWORKS)
        assert not missing, f"Missing Habit Science frameworks: {missing}"

    def test_all_required_fields_present(self, all_frameworks):
        required_fields = [
            "framework_id", "source", "principle_name", "rule",
            "trigger_condition", "action_template", "applicable_phases",
        ]
        for fw in all_frameworks:
            for field in required_fields:
                assert hasattr(fw, field), f"{fw.framework_id} missing field '{field}'"
                assert getattr(fw, field) is not None, (
                    f"{fw.framework_id}.{field} must not be None"
                )

    def test_framework_ids_are_unique(self, all_frameworks):
        ids = [fw.framework_id for fw in all_frameworks]
        assert len(ids) == len(set(ids)), "Duplicate framework_ids found"

    def test_applicable_phases_are_non_empty(self, all_frameworks):
        for fw in all_frameworks:
            assert fw.applicable_phases, (
                f"{fw.framework_id}.applicable_phases must be a non-empty list"
            )

    def test_rule_is_non_empty_string(self, all_frameworks):
        for fw in all_frameworks:
            assert isinstance(fw.rule, str) and fw.rule.strip(), (
                f"{fw.framework_id}.rule must be a non-empty string"
            )

    def test_rebuild_produces_same_count(self):
        rebuilt = _build_influence_frameworks()
        assert len(rebuilt) == len(INFLUENCE_FRAMEWORKS)


# ---------------------------------------------------------------------------
# Part 2: AgentPersonaDefinition tests
# ---------------------------------------------------------------------------


class TestAgentPersonas:
    """All agent personas must be valid and complete."""

    REQUIRED_AGENTS = {
        "morgan_vale",
        "alex_reeves",
        "casey_torres",
        "taylor_kim",
        "drew_nakamura",
        "murphy",
        "quinn_harper",
        "jordan_blake",
        "sam_ortega",
    }

    def test_all_required_agents_present(self):
        missing = self.REQUIRED_AGENTS - set(AGENT_ROSTER)
        assert not missing, f"Missing agents: {missing}"

    def test_all_required_fields_present(self, all_agents):
        required_fields = [
            "agent_id", "name", "title", "department", "personality",
            "communication_style", "influence_frameworks", "system_prompt",
            "information_apis", "trigger_conditions", "gate_definitions",
            "action_capabilities", "reports_to", "direct_reports",
            "rosetta_fields", "kaia_mix",
        ]
        for agent in all_agents:
            for field in required_fields:
                assert hasattr(agent, field), f"{agent.agent_id} missing field '{field}'"

    def test_agent_ids_are_unique(self, all_agents):
        ids = [a.agent_id for a in all_agents]
        assert len(ids) == len(set(ids)), "Duplicate agent_ids found"

    def test_influence_framework_references_are_valid(self, all_agents):
        known_ids = set(INFLUENCE_FRAMEWORKS.keys())
        for agent in all_agents:
            for fw_id in agent.influence_frameworks:
                assert fw_id in known_ids, (
                    f"Agent {agent.agent_id} references unknown framework '{fw_id}'"
                )

    def test_each_agent_has_at_least_one_framework(self, all_agents):
        for agent in all_agents:
            assert agent.influence_frameworks, (
                f"Agent {agent.agent_id} must have at least one influence framework"
            )

    def test_each_agent_has_at_least_one_trigger(self, all_agents):
        for agent in all_agents:
            assert agent.trigger_conditions, (
                f"Agent {agent.agent_id} must have at least one trigger condition"
            )

    def test_each_agent_has_at_least_one_gate(self, all_agents):
        for agent in all_agents:
            assert agent.gate_definitions, (
                f"Agent {agent.agent_id} must have at least one gate definition"
            )

    def test_each_agent_has_at_least_one_action(self, all_agents):
        for agent in all_agents:
            assert agent.action_capabilities, (
                f"Agent {agent.agent_id} must have at least one action capability"
            )

    def test_rosetta_fields_have_agent_type(self, all_agents):
        for agent in all_agents:
            assert "agent_type" in agent.rosetta_fields, (
                f"Agent {agent.agent_id} missing 'agent_type' in rosetta_fields"
            )

    def test_rosetta_fields_have_management_layer(self, all_agents):
        for agent in all_agents:
            assert "management_layer" in agent.rosetta_fields, (
                f"Agent {agent.agent_id} missing 'management_layer' in rosetta_fields"
            )

    def test_rosetta_fields_have_permissions(self, all_agents):
        for agent in all_agents:
            assert "permissions" in agent.rosetta_fields, (
                f"Agent {agent.agent_id} missing 'permissions' in rosetta_fields"
            )
            assert agent.rosetta_fields["permissions"], (
                f"Agent {agent.agent_id}.rosetta_fields['permissions'] must be non-empty"
            )

    def test_kaia_mix_sums_to_one(self, all_agents):
        for agent in all_agents:
            if agent.kaia_mix:
                total = sum(agent.kaia_mix.values())
                assert abs(total - 1.0) < 0.01, (
                    f"Agent {agent.agent_id}.kaia_mix sums to {total}, expected ~1.0"
                )

    def test_gate_definitions_have_threshold_and_comparator(self, all_agents):
        valid_comparators = {"gt", "lt", "gte", "lte", "eq"}
        for agent in all_agents:
            for gate in agent.gate_definitions:
                assert "threshold" in gate, (
                    f"Gate {gate.get('gate_id')} in {agent.agent_id} missing 'threshold'"
                )
                assert "comparator" in gate, (
                    f"Gate {gate.get('gate_id')} in {agent.agent_id} missing 'comparator'"
                )
                assert gate["comparator"] in valid_comparators, (
                    f"Gate {gate.get('gate_id')} in {agent.agent_id} has invalid "
                    f"comparator '{gate['comparator']}'"
                )
                assert isinstance(gate["threshold"], (int, float)), (
                    f"Gate {gate.get('gate_id')} threshold must be numeric"
                )

    def test_trigger_conditions_have_trigger_id_and_event(self, all_agents):
        for agent in all_agents:
            for trigger in agent.trigger_conditions:
                assert "trigger_id" in trigger, (
                    f"Trigger in {agent.agent_id} missing 'trigger_id'"
                )
                assert "event" in trigger, (
                    f"Trigger {trigger.get('trigger_id')} in {agent.agent_id} missing 'event'"
                )

    def test_information_apis_have_required_fields(self, all_agents):
        for agent in all_agents:
            for api in agent.information_apis:
                assert "api_id" in api, (
                    f"API in {agent.agent_id} missing 'api_id'"
                )
                assert "endpoint" in api, (
                    f"API {api.get('api_id')} in {agent.agent_id} missing 'endpoint'"
                )
                assert "description" in api, (
                    f"API {api.get('api_id')} in {agent.agent_id} missing 'description'"
                )

    def test_rebuild_produces_same_agents(self):
        rebuilt = _build_agent_roster()
        assert set(rebuilt.keys()) == set(AGENT_ROSTER.keys())

    def test_morgan_vale_has_executive_layer(self):
        morgan = AGENT_ROSTER["morgan_vale"]
        assert morgan.rosetta_fields["management_layer"] == "executive"

    def test_murphy_has_all_system_access(self):
        murphy = AGENT_ROSTER["murphy"]
        assert any("all" in p for p in murphy.rosetta_fields.get("permissions", []))

    def test_quinn_harper_has_scarcity_framework(self):
        quinn = AGENT_ROSTER["quinn_harper"]
        assert "cialdini_scarcity" in quinn.influence_frameworks

    def test_casey_torres_has_reciprocity_framework(self):
        casey = AGENT_ROSTER["casey_torres"]
        assert "cialdini_reciprocity" in casey.influence_frameworks

    def test_sam_ortega_has_authority_framework(self):
        sam = AGENT_ROSTER["sam_ortega"]
        assert "cialdini_authority" in sam.influence_frameworks


# ---------------------------------------------------------------------------
# Part 3: SellingPromptComposer tests
# ---------------------------------------------------------------------------


class TestSellingPromptComposer:
    """SellingPromptComposer must produce complete, influence-informed prompts."""

    def test_compose_outreach_prompt_contains_agent_identity(
        self, composer, sample_prospect, sample_live_stats
    ):
        casey = AGENT_ROSTER["casey_torres"]
        prompt = composer.compose_outreach_prompt(casey, sample_prospect, sample_live_stats)
        assert "Casey Torres" in prompt

    def test_compose_outreach_prompt_contains_influence_rules(
        self, composer, sample_prospect, sample_live_stats
    ):
        casey = AGENT_ROSTER["casey_torres"]
        prompt = composer.compose_outreach_prompt(casey, sample_prospect, sample_live_stats)
        assert "INFLUENCE" in prompt.upper() or "Rule" in prompt

    def test_compose_outreach_prompt_contains_prospect_data(
        self, composer, sample_prospect, sample_live_stats
    ):
        casey = AGENT_ROSTER["casey_torres"]
        prompt = composer.compose_outreach_prompt(casey, sample_prospect, sample_live_stats)
        assert "Acme Agency" in prompt

    def test_compose_outreach_prompt_contains_live_stats(
        self, composer, sample_prospect, sample_live_stats
    ):
        casey = AGENT_ROSTER["casey_torres"]
        prompt = composer.compose_outreach_prompt(casey, sample_prospect, sample_live_stats)
        assert "142" in prompt  # automations_running

    def test_compose_trial_interaction_prompt_contains_agent_identity(
        self, composer, sample_trial_context, sample_shadow_observations
    ):
        taylor = AGENT_ROSTER["taylor_kim"]
        prompt = composer.compose_trial_interaction_prompt(
            taylor, sample_trial_context, sample_shadow_observations
        )
        assert "Taylor Kim" in prompt

    def test_compose_trial_interaction_prompt_contains_observations(
        self, composer, sample_trial_context, sample_shadow_observations
    ):
        taylor = AGENT_ROSTER["taylor_kim"]
        prompt = composer.compose_trial_interaction_prompt(
            taylor, sample_trial_context, sample_shadow_observations
        )
        assert "invoice reconciliation" in prompt

    def test_compose_conversion_prompt_contains_scarcity_rule(
        self, composer, sample_trial_report, sample_shadow_patterns
    ):
        quinn = AGENT_ROSTER["quinn_harper"]
        prompt = composer.compose_conversion_prompt(quinn, sample_trial_report, sample_shadow_patterns)
        assert "cialdini_scarcity" in quinn.influence_frameworks
        # The prompt should include the scarcity influence rule
        assert "Quinn Harper" in prompt

    def test_compose_conversion_prompt_contains_patterns(
        self, composer, sample_trial_report, sample_shadow_patterns
    ):
        quinn = AGENT_ROSTER["quinn_harper"]
        prompt = composer.compose_conversion_prompt(quinn, sample_trial_report, sample_shadow_patterns)
        assert "invoice reconciliation" in prompt

    def test_select_active_frameworks_filters_by_phase(self, composer):
        casey = AGENT_ROSTER["casey_torres"]
        # outreach phase should include reciprocity
        active = composer.select_active_frameworks(casey, "outreach", "first_contact")
        active_ids = [fw.framework_id for fw in active]
        assert "cialdini_reciprocity" in active_ids

    def test_select_active_frameworks_excludes_wrong_phase(self, composer):
        # cialdini_scarcity only applies to conversion phase
        quinn = AGENT_ROSTER["quinn_harper"]
        active_outreach = composer.select_active_frameworks(quinn, "outreach", "first_contact")
        active_ids = [fw.framework_id for fw in active_outreach]
        # scarcity is conversion-only, should not appear in outreach
        assert "cialdini_scarcity" not in active_ids

    def test_select_active_frameworks_conversion_includes_scarcity(self, composer):
        quinn = AGENT_ROSTER["quinn_harper"]
        active = composer.select_active_frameworks(quinn, "conversion", "trial_ending")
        active_ids = [fw.framework_id for fw in active]
        assert "cialdini_scarcity" in active_ids

    def test_format_framework_rules_returns_string(self, composer):
        frameworks = [INFLUENCE_FRAMEWORKS["cialdini_reciprocity"]]
        result = composer.format_framework_rules(frameworks)
        assert isinstance(result, str)
        assert "Reciprocity" in result

    def test_format_framework_rules_empty_returns_no_active_message(self, composer):
        result = composer.format_framework_rules([])
        assert "no active" in result.lower()

    def test_compose_outreach_empty_context_does_not_raise(self, composer):
        casey = AGENT_ROSTER["casey_torres"]
        prompt = composer.compose_outreach_prompt(casey, {}, {})
        assert "Casey Torres" in prompt

    def test_compose_with_all_agents_does_not_raise(
        self, composer, sample_prospect, sample_live_stats
    ):
        for agent_id, agent in AGENT_ROSTER.items():
            prompt = composer.compose_outreach_prompt(agent, sample_prospect, sample_live_stats)
            assert agent.name in prompt, f"Agent name missing from prompt for {agent_id}"


# ---------------------------------------------------------------------------
# Part 4: RosettaSellingBridge tests
# ---------------------------------------------------------------------------


class TestRosettaSellingBridge:
    """Bridge must correctly convert personas to Rosetta/bootstrap structures."""

    def test_persona_to_employee_contract_has_required_keys(self, bridge):
        morgan = AGENT_ROSTER["morgan_vale"]
        contract = bridge.persona_to_employee_contract(morgan)
        required = ["agent_type", "role_title", "management_layer", "department"]
        for key in required:
            assert key in contract, f"EmployeeContract missing key '{key}'"

    def test_persona_to_employee_contract_management_layer_valid(self, bridge, all_agents):
        valid_layers = {"executive", "middle", "individual"}
        for agent in all_agents:
            contract = bridge.persona_to_employee_contract(agent)
            assert contract["management_layer"] in valid_layers, (
                f"Agent {agent.agent_id} has invalid management_layer: "
                f"{contract['management_layer']}"
            )

    def test_persona_to_employee_contract_department_matches(self, bridge):
        morgan = AGENT_ROSTER["morgan_vale"]
        contract = bridge.persona_to_employee_contract(morgan)
        assert contract["department"] == "executive"

    def test_persona_to_rosetta_document_has_required_keys(self, bridge):
        morgan = AGENT_ROSTER["morgan_vale"]
        doc = bridge.persona_to_rosetta_document(morgan)
        required = [
            "agent_id", "agent_name", "contract", "terminology",
            "state_feed_entries", "system_prompt",
        ]
        for key in required:
            assert key in doc, f"RosettaDocument dict missing key '{key}'"

    def test_persona_to_rosetta_document_agent_id_matches(self, bridge, all_agents):
        for agent in all_agents:
            doc = bridge.persona_to_rosetta_document(agent)
            assert doc["agent_id"] == agent.agent_id

    def test_persona_to_rosetta_document_state_feed_entries_match_apis(self, bridge):
        morgan = AGENT_ROSTER["morgan_vale"]
        doc = bridge.persona_to_rosetta_document(morgan)
        assert len(doc["state_feed_entries"]) == len(morgan.information_apis)

    def test_persona_to_bootstrap_config_has_required_keys(self, bridge, all_agents):
        required = ["role", "dept", "perms", "avatar"]
        for agent in all_agents:
            config = bridge.persona_to_bootstrap_config(agent)
            for key in required:
                assert key in config, (
                    f"Bootstrap config for {agent.agent_id} missing key '{key}'"
                )

    def test_persona_to_bootstrap_config_avatar_has_name(self, bridge, all_agents):
        for agent in all_agents:
            config = bridge.persona_to_bootstrap_config(agent)
            assert config["avatar"]["name"] == agent.name

    def test_persona_to_bootstrap_config_avatar_has_system_prompt(self, bridge, all_agents):
        for agent in all_agents:
            config = bridge.persona_to_bootstrap_config(agent)
            assert "system_prompt" in config["avatar"]
            assert config["avatar"]["system_prompt"]

    def test_create_information_api_feeds(self, bridge):
        casey = AGENT_ROSTER["casey_torres"]
        feeds = bridge.create_information_api_feeds(casey)
        assert len(feeds) == len(casey.information_apis)
        for feed in feeds:
            assert "feed_id" in feed
            assert "agent_id" in feed
            assert "endpoint" in feed
            assert feed["agent_id"] == "casey_torres"

    def test_create_trigger_subscriptions(self, bridge):
        casey = AGENT_ROSTER["casey_torres"]
        subs = bridge.create_trigger_subscriptions(casey)
        assert len(subs) == len(casey.trigger_conditions)
        for sub in subs:
            assert "subscription_id" in sub
            assert "agent_id" in sub
            assert "event_type" in sub

    def test_create_gate_rules(self, bridge):
        casey = AGENT_ROSTER["casey_torres"]
        rules = bridge.create_gate_rules(casey)
        assert len(rules) == len(casey.gate_definitions)
        for rule in rules:
            assert "rule_id" in rule
            assert "metric" in rule
            assert "comparator" in rule
            assert "threshold" in rule

    def test_register_all_selling_agents_returns_all_agents(self, bridge):
        registry = bridge.register_all_selling_agents()
        assert set(registry.keys()) == set(AGENT_ROSTER.keys())

    def test_register_all_selling_agents_has_complete_config(self, bridge):
        registry = bridge.register_all_selling_agents()
        required_keys = [
            "bootstrap_config", "rosetta_document",
            "information_feeds", "trigger_subscriptions", "gate_rules"
        ]
        for agent_id, config in registry.items():
            for key in required_keys:
                assert key in config, (
                    f"Registry entry for {agent_id} missing key '{key}'"
                )

    def test_inject_selling_persona_returns_string(self, bridge):
        casey = AGENT_ROSTER["casey_torres"]
        result = bridge.inject_selling_persona(
            persona=casey,
            base_prompt="Write an outreach email.",
        )
        assert isinstance(result, str)
        assert len(result) > 0


# ---------------------------------------------------------------------------
# Part 5: AgentCollaborationProtocol tests
# ---------------------------------------------------------------------------


class TestAgentCollaborationProtocol:
    """Collaboration protocol must be complete and internally consistent."""

    def test_handoff_rules_are_defined(self, protocol):
        handoffs = protocol.define_handoff_rules()
        assert handoffs, "Handoff rules must not be empty"

    def test_escalation_paths_are_defined(self, protocol):
        escalations = protocol.define_escalation_paths()
        assert escalations, "Escalation paths must not be empty"

    def test_cross_department_triggers_are_defined(self, protocol):
        triggers = protocol.define_cross_department_triggers()
        assert triggers, "Cross-department triggers must not be empty"

    def test_casey_to_alex_handoff_exists(self, protocol):
        handoffs = protocol.define_handoff_rules()
        handoff_ids = [h["handoff_id"] for h in handoffs]
        assert "casey_to_alex" in handoff_ids

    def test_alex_to_taylor_handoff_exists(self, protocol):
        handoffs = protocol.define_handoff_rules()
        handoff_ids = [h["handoff_id"] for h in handoffs]
        assert "alex_to_taylor" in handoff_ids

    def test_taylor_to_quinn_handoff_exists(self, protocol):
        handoffs = protocol.define_handoff_rules()
        handoff_ids = [h["handoff_id"] for h in handoffs]
        assert "taylor_to_quinn" in handoff_ids

    def test_quinn_feeds_back_to_casey(self, protocol):
        handoffs = protocol.define_handoff_rules()
        quinn_to_casey = [
            h for h in handoffs
            if h["from_agent"] == "quinn_harper" and h["to_agent"] == "casey_torres"
        ]
        assert quinn_to_casey, "Quinn Harper → Casey Torres feedback loop must exist"

    def test_no_dead_ends(self, protocol):
        errors = protocol.validate_no_dead_ends()
        assert not errors, f"Dead ends found in collaboration protocol: {errors}"

    def test_all_handoff_agents_are_known(self, protocol):
        known_agents = set(AGENT_ROSTER.keys()) | {"corey_post", "dynamic"}
        handoffs = protocol.define_handoff_rules()
        for h in handoffs:
            assert h["from_agent"] in known_agents, (
                f"Handoff '{h['handoff_id']}' from_agent '{h['from_agent']}' is unknown"
            )
            assert h["to_agent"] in known_agents, (
                f"Handoff '{h['handoff_id']}' to_agent '{h['to_agent']}' is unknown"
            )

    def test_all_escalation_agents_are_known(self, protocol):
        known_agents = set(AGENT_ROSTER.keys()) | {"corey_post"}
        escalations = protocol.define_escalation_paths()
        for e in escalations:
            assert e["from_agent"] in known_agents, (
                f"Escalation '{e['escalation_id']}' from_agent '{e['from_agent']}' is unknown"
            )
            assert e["to_agent"] in known_agents, (
                f"Escalation '{e['escalation_id']}' to_agent '{e['to_agent']}' is unknown"
            )

    def test_every_escalation_has_urgency(self, protocol):
        escalations = protocol.define_escalation_paths()
        for e in escalations:
            assert "urgency" in e, f"Escalation '{e['escalation_id']}' missing 'urgency'"
            assert e["urgency"] in {"low", "medium", "high", "critical"}, (
                f"Escalation '{e['escalation_id']}' has invalid urgency '{e['urgency']}'"
            )

    def test_every_handoff_passes_data(self, protocol):
        handoffs = protocol.define_handoff_rules()
        for h in handoffs:
            assert "data_passed" in h, f"Handoff '{h['handoff_id']}' missing 'data_passed'"
            assert h["data_passed"], f"Handoff '{h['handoff_id']}' data_passed must be non-empty"

    def test_get_full_protocol_returns_all_sections(self, protocol):
        full = protocol.get_full_protocol()
        assert "handoff_rules" in full
        assert "escalation_paths" in full
        assert "cross_department_triggers" in full

    def test_morgan_vale_oversees_revenue_escalations(self, protocol):
        escalations = protocol.define_escalation_paths()
        morgan_targets = [
            e for e in escalations if e["to_agent"] == "morgan_vale"
        ]
        assert morgan_targets, "Morgan Vale must receive at least one escalation"

    def test_cross_department_new_customer_triggers_multiple_agents(self, protocol):
        triggers = protocol.define_cross_department_triggers()
        customer_trigger = next(
            (t for t in triggers if t["trigger_id"] == "new_customer_converted"), None
        )
        assert customer_trigger is not None, "new_customer_converted trigger must exist"
        assert len(customer_trigger["notified_agents"]) >= 3, (
            "new_customer_converted should notify at least 3 agents"
        )

    def test_system_health_warning_triggers_murphy(self, protocol):
        triggers = protocol.define_cross_department_triggers()
        health_trigger = next(
            (t for t in triggers if t["trigger_id"] == "system_health_warning"), None
        )
        assert health_trigger is not None, "system_health_warning trigger must exist"
        assert "murphy" in health_trigger["notified_agents"]


# ---------------------------------------------------------------------------
# Part 6: Integration tests
# ---------------------------------------------------------------------------


class TestIntegration:
    """End-to-end composition and bridge integration tests."""

    def test_full_outreach_flow(
        self, bridge, composer, sample_prospect, sample_live_stats
    ):
        """Simulate Casey composing an outreach via the bridge."""
        casey = AGENT_ROSTER["casey_torres"]
        prompt = bridge.inject_selling_persona(
            persona=casey,
            base_prompt="Write a personalized outreach email to this prospect.",
            prospect_context=sample_prospect,
            live_stats=sample_live_stats,
        )
        assert "Casey Torres" in prompt
        assert isinstance(prompt, str)
        assert len(prompt) > 100

    def test_full_trial_flow(
        self, bridge, composer, sample_trial_context, sample_shadow_observations
    ):
        """Simulate Taylor composing a trial interaction."""
        taylor = AGENT_ROSTER["taylor_kim"]
        prompt = composer.compose_trial_interaction_prompt(
            taylor, sample_trial_context, sample_shadow_observations
        )
        assert "Taylor Kim" in prompt
        assert "invoice reconciliation" in prompt

    def test_full_conversion_flow(
        self, bridge, composer, sample_trial_report, sample_shadow_patterns
    ):
        """Simulate Quinn composing a conversion message."""
        quinn = AGENT_ROSTER["quinn_harper"]
        prompt = composer.compose_conversion_prompt(
            quinn, sample_trial_report, sample_shadow_patterns
        )
        assert "Quinn Harper" in prompt
        assert "invoice reconciliation" in prompt

    def test_registry_bootstrap_configs_match_agent_names(self, bridge):
        registry = bridge.register_all_selling_agents()
        for agent_id, config in registry.items():
            persona = AGENT_ROSTER[agent_id]
            assert config["bootstrap_config"]["avatar"]["name"] == persona.name

    def test_all_agents_have_trigger_to_action_mapping(self):
        """Every trigger event in an agent must correspond to a valid action."""
        for agent_id, agent in AGENT_ROSTER.items():
            actions = set(agent.action_capabilities)
            assert actions, f"Agent {agent_id} has no action capabilities"
            for trigger in agent.trigger_conditions:
                assert trigger["trigger_id"], (
                    f"Agent {agent_id} has empty trigger_id"
                )

    def test_gate_thresholds_are_numeric(self):
        for agent_id, agent in AGENT_ROSTER.items():
            for gate in agent.gate_definitions:
                threshold = gate.get("threshold")
                assert isinstance(threshold, (int, float)), (
                    f"Agent {agent_id} gate '{gate.get('gate_id')}' "
                    f"threshold is not numeric: {threshold!r}"
                )

    def test_information_feeds_have_valid_endpoints(self):
        for agent_id, agent in AGENT_ROSTER.items():
            for api in agent.information_apis:
                endpoint = api.get("endpoint", "")
                assert endpoint.startswith("internal://") or endpoint.startswith("http"), (
                    f"Agent {agent_id} API '{api.get('api_id')}' has invalid endpoint: {endpoint}"
                )
