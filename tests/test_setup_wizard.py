"""Tests for the Murphy System Setup Wizard."""

import json
import os
import pytest

from setup_wizard import (
    SetupProfile,
    SetupWizard,
    CORE_MODULES,
    VALID_AUTOMATION_TYPES,
    VALID_INDUSTRIES,
    VALID_SECURITY_LEVELS,
    VALID_LLM_PROVIDERS,
    VALID_DEPLOYMENT_MODES,
    VALID_ROBOTICS_PROTOCOLS,
    VALID_COMPLIANCE_FRAMEWORKS,
    PRESET_PROFILES,
    get_preset_profiles,
    apply_preset,
    _parse_bool,
    _fuzzy_match_choice,
    _fuzzy_match_multi_choice,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_full_profile(**overrides) -> SetupProfile:
    """Return a fully-populated profile with sensible defaults."""
    defaults = dict(
        organization_name="Acme Corp",
        industry="manufacturing",
        company_size="medium",
        automation_types=["factory_iot", "data"],
        security_level="standard",
        robotics_enabled=True,
        robotics_protocols=["ros2", "modbus"],
        avatar_enabled=False,
        avatar_connectors=[],
        llm_provider="deepinfra",
        monitoring_enabled=True,
        compliance_frameworks=["SOC2"],
        deployment_mode="docker",
        sales_automation_enabled=False,
    )
    defaults.update(overrides)
    return SetupProfile(**defaults)


# ---------------------------------------------------------------------------
# Tests — Profile
# ---------------------------------------------------------------------------

class TestSetupProfile:
    def test_default_profile(self):
        """Default profile has expected empty/default values."""
        p = SetupProfile()
        assert p.organization_name == ""
        assert p.industry == "other"
        assert p.company_size == "small"
        assert p.automation_types == []
        assert p.security_level == "standard"
        assert p.robotics_enabled is False
        assert p.robotics_protocols == []
        assert p.avatar_enabled is False
        assert p.llm_provider == "local"
        assert p.monitoring_enabled is True
        assert p.compliance_frameworks == []
        assert p.deployment_mode == "local"
        assert p.sales_automation_enabled is False

    def test_full_profile_creation(self):
        """Profile can be created with all fields set."""
        p = _make_full_profile()
        assert p.organization_name == "Acme Corp"
        assert p.industry == "manufacturing"
        assert p.robotics_enabled is True
        assert "ros2" in p.robotics_protocols


# ---------------------------------------------------------------------------
# Tests — Questions
# ---------------------------------------------------------------------------

class TestQuestions:
    def test_question_count(self):
        """Wizard provides at least 10 questions."""
        wiz = SetupWizard()
        qs = wiz.get_questions()
        assert len(qs) >= 10

    def test_question_has_required_keys(self):
        """Every question dict has the expected keys."""
        wiz = SetupWizard()
        required_keys = {"id", "text", "field", "question_type", "options", "default"}
        for q in wiz.get_questions():
            assert required_keys.issubset(q.keys()), f"Missing keys in {q['id']}"

    def test_question_ids_unique(self):
        """All question ids are unique."""
        wiz = SetupWizard()
        ids = [q["id"] for q in wiz.get_questions()]
        assert len(ids) == len(set(ids))

    def test_questions_immutable(self):
        """get_questions returns a deep copy."""
        wiz = SetupWizard()
        qs = wiz.get_questions()
        qs[0]["text"] = "MODIFIED"
        assert wiz.get_questions()[0]["text"] != "MODIFIED"


# ---------------------------------------------------------------------------
# Tests — Answer application
# ---------------------------------------------------------------------------

class TestApplyAnswer:
    def test_apply_text_answer(self):
        wiz = SetupWizard()
        result = wiz.apply_answer("q1", "My Company")
        assert result["ok"] is True
        assert wiz.get_profile().organization_name == "My Company"

    def test_apply_choice_answer(self):
        wiz = SetupWizard()
        result = wiz.apply_answer("q2", "finance")
        assert result["ok"] is True
        assert wiz.get_profile().industry == "finance"

    def test_apply_multi_choice_answer(self):
        wiz = SetupWizard()
        result = wiz.apply_answer("q4", ["data", "content"])
        assert result["ok"] is True
        assert wiz.get_profile().automation_types == ["data", "content"]

    def test_apply_boolean_answer(self):
        wiz = SetupWizard()
        result = wiz.apply_answer("q6", True)
        assert result["ok"] is True
        assert wiz.get_profile().robotics_enabled is True

    def test_invalid_choice_rejected(self):
        wiz = SetupWizard()
        result = wiz.apply_answer("q2", "not_an_industry")
        assert result["ok"] is False
        assert "Invalid choice" in result["error"]

    def test_invalid_multi_choice_rejected(self):
        wiz = SetupWizard()
        result = wiz.apply_answer("q4", ["data", "invalid_type"])
        assert result["ok"] is False
        assert "invalid_type" in result["error"]

    def test_wrong_type_text_rejected(self):
        wiz = SetupWizard()
        result = wiz.apply_answer("q1", 12345)
        assert result["ok"] is False

    def test_wrong_type_boolean_rejected(self):
        wiz = SetupWizard()
        result = wiz.apply_answer("q6", "yes")
        assert result["ok"] is False

    def test_unknown_question_rejected(self):
        wiz = SetupWizard()
        result = wiz.apply_answer("q999", "anything")
        assert result["ok"] is False
        assert "Unknown" in result["error"]


# ---------------------------------------------------------------------------
# Tests — Config generation
# ---------------------------------------------------------------------------

class TestGenerateConfig:
    def test_config_structure(self):
        wiz = SetupWizard()
        profile = _make_full_profile()
        config = wiz.generate_config(profile)
        assert "organization" in config
        assert "modules" in config
        assert "bots" in config
        assert config["organization"]["name"] == "Acme Corp"

    def test_config_modules_include_core(self):
        wiz = SetupWizard()
        profile = _make_full_profile()
        config = wiz.generate_config(profile)
        for core_mod in CORE_MODULES:
            assert core_mod in config["modules"]


# ---------------------------------------------------------------------------
# Tests — Module recommendation
# ---------------------------------------------------------------------------

class TestModules:
    def test_factory_iot_modules(self):
        wiz = SetupWizard()
        profile = _make_full_profile(automation_types=["factory_iot"])
        modules = wiz.get_enabled_modules(profile)
        assert "building_automation_connectors" in modules
        assert "manufacturing_automation_standards" in modules

    def test_content_modules(self):
        wiz = SetupWizard()
        profile = _make_full_profile(automation_types=["content"])
        modules = wiz.get_enabled_modules(profile)
        assert "content_creator_platform_modulator" in modules
        assert "social_media_moderation" in modules

    def test_robotics_module_added(self):
        wiz = SetupWizard()
        profile = _make_full_profile(robotics_enabled=True)
        modules = wiz.get_enabled_modules(profile)
        assert "robotics" in modules

    def test_avatar_module_added(self):
        wiz = SetupWizard()
        profile = _make_full_profile(avatar_enabled=True)
        modules = wiz.get_enabled_modules(profile)
        assert "avatar" in modules

    def test_sales_modules_added(self):
        wiz = SetupWizard()
        profile = _make_full_profile(sales_automation_enabled=True)
        modules = wiz.get_enabled_modules(profile)
        assert "workflow_template_marketplace" in modules

    def test_monitoring_modules_added(self):
        wiz = SetupWizard()
        profile = _make_full_profile(monitoring_enabled=True)
        modules = wiz.get_enabled_modules(profile)
        assert "compliance_monitoring_completeness" in modules

    def test_compliance_modules_added(self):
        wiz = SetupWizard()
        profile = _make_full_profile(compliance_frameworks=["HIPAA", "GDPR"])
        modules = wiz.get_enabled_modules(profile)
        assert "compliance_region_validator" in modules
        assert "contractual_audit" in modules

    def test_compliance_none_no_extra_modules(self):
        wiz = SetupWizard()
        profile = _make_full_profile(compliance_frameworks=["none"])
        modules = wiz.get_enabled_modules(profile)
        assert "compliance_region_validator" not in modules


# ---------------------------------------------------------------------------
# Tests — Bot recommendation
# ---------------------------------------------------------------------------

class TestBots:
    def test_industry_bots(self):
        wiz = SetupWizard()
        profile = _make_full_profile(industry="finance")
        bots = wiz.get_recommended_bots(profile)
        assert "trading_bot" in bots

    def test_sales_bots(self):
        wiz = SetupWizard()
        profile = _make_full_profile(sales_automation_enabled=True)
        bots = wiz.get_recommended_bots(profile)
        assert "sales_outreach_bot" in bots

    def test_automation_bots(self):
        wiz = SetupWizard()
        profile = _make_full_profile(automation_types=["agent"])
        bots = wiz.get_recommended_bots(profile)
        assert "swarm_coordinator_bot" in bots


# ---------------------------------------------------------------------------
# Tests — Validation
# ---------------------------------------------------------------------------

class TestValidation:
    def test_valid_profile(self):
        wiz = SetupWizard()
        result = wiz.validate_profile(_make_full_profile())
        assert result["valid"] is True
        assert result["issues"] == []

    def test_missing_org_name(self):
        wiz = SetupWizard()
        result = wiz.validate_profile(_make_full_profile(organization_name=""))
        assert result["valid"] is False
        assert any("Organization" in i for i in result["issues"])

    def test_robotics_without_protocols(self):
        wiz = SetupWizard()
        profile = _make_full_profile(robotics_enabled=True, robotics_protocols=[])
        result = wiz.validate_profile(profile)
        assert result["valid"] is False
        assert any("protocol" in i.lower() for i in result["issues"])


# ---------------------------------------------------------------------------
# Tests — Export
# ---------------------------------------------------------------------------

class TestExport:
    def test_export_creates_file(self, tmp_path):
        wiz = SetupWizard()
        config = wiz.generate_config(_make_full_profile())
        out = tmp_path / "config.json"
        wiz.export_config(config, str(out))
        assert out.exists()
        loaded = json.loads(out.read_text())
        assert loaded["organization"]["name"] == "Acme Corp"


# ---------------------------------------------------------------------------
# Tests — Summary
# ---------------------------------------------------------------------------

class TestSummary:
    def test_summary_contains_key_info(self):
        wiz = SetupWizard()
        profile = _make_full_profile()
        summary = wiz.summarize(profile)
        assert "Acme Corp" in summary
        assert "manufacturing" in summary
        assert "medium" in summary
        assert "deepinfra" in summary

    def test_summary_shows_protocols_when_robotics_enabled(self):
        wiz = SetupWizard()
        profile = _make_full_profile(robotics_enabled=True,
                                     robotics_protocols=["ros2"])
        summary = wiz.summarize(profile)
        assert "ros2" in summary


# ---------------------------------------------------------------------------
# Tests — Fuzzy input helpers (CLI layer)
# ---------------------------------------------------------------------------

class TestParseBool:
    def test_standard_yes(self):
        assert _parse_bool("yes") is True
        assert _parse_bool("y") is True
        assert _parse_bool("true") is True
        assert _parse_bool("1") is True

    def test_standard_no(self):
        assert _parse_bool("no") is False
        assert _parse_bool("n") is False
        assert _parse_bool("false") is False
        assert _parse_bool("0") is False

    def test_natural_language_yes(self):
        assert _parse_bool("sure") is True
        assert _parse_bool("yep") is True
        assert _parse_bool("absolutely") is True
        assert _parse_bool("definitely") is True

    def test_natural_language_no(self):
        assert _parse_bool("not yet") is False
        assert _parse_bool("nah") is False
        assert _parse_bool("nope") is False
        assert _parse_bool("maybe later") is False
        assert _parse_bool("skip") is False

    def test_unrecognised_returns_none(self):
        assert _parse_bool("banana") is None
        assert _parse_bool("42") is None


class TestFuzzyMatchChoice:
    def test_exact_match(self):
        assert _fuzzy_match_choice("local", VALID_LLM_PROVIDERS) == "local"

    def test_option_with_trailing_text(self):
        assert _fuzzy_match_choice("local for now.", VALID_LLM_PROVIDERS) == "local"

    def test_option_as_standalone_word(self):
        assert _fuzzy_match_choice("I'd pick deepinfra please", VALID_LLM_PROVIDERS) == "deepinfra"

    def test_no_match_returns_none(self):
        assert _fuzzy_match_choice("something random", VALID_LLM_PROVIDERS) is None

    def test_case_insensitive(self):
        assert _fuzzy_match_choice("LOCAL", VALID_LLM_PROVIDERS) == "local"

    def test_industry_embedded(self):
        assert _fuzzy_match_choice(
            "all of those. i'm the creator of the murphy system.",
            VALID_INDUSTRIES,
        ) is None  # no single valid option dominates


class TestFuzzyMatchMultiChoice:
    def test_all_keyword(self):
        result = _fuzzy_match_multi_choice("all", VALID_AUTOMATION_TYPES)
        assert result == list(VALID_AUTOMATION_TYPES)

    def test_all_of_them(self):
        result = _fuzzy_match_multi_choice("all of them", VALID_AUTOMATION_TYPES)
        assert result == list(VALID_AUTOMATION_TYPES)

    def test_all_of_those(self):
        result = _fuzzy_match_multi_choice("all of those", VALID_AUTOMATION_TYPES)
        assert result == list(VALID_AUTOMATION_TYPES)

    def test_everything(self):
        result = _fuzzy_match_multi_choice("everything", VALID_AUTOMATION_TYPES)
        assert result == list(VALID_AUTOMATION_TYPES)

    def test_comma_separated(self):
        result = _fuzzy_match_multi_choice("data, content", VALID_AUTOMATION_TYPES)
        assert result == ["data", "content"]

    def test_skip_phrase_returns_empty(self):
        result = _fuzzy_match_multi_choice("I dont know yet", VALID_COMPLIANCE_FRAMEWORKS)
        assert result == []

    def test_skip_none_keyword(self):
        result = _fuzzy_match_multi_choice("skip", VALID_AUTOMATION_TYPES)
        assert result == []

    def test_skip_not_sure(self):
        result = _fuzzy_match_multi_choice("not sure", VALID_AUTOMATION_TYPES)
        assert result == []

    def test_single_word_match(self):
        result = _fuzzy_match_multi_choice("just data", VALID_AUTOMATION_TYPES)
        assert result == ["data"]


# ---------------------------------------------------------------------------
# Tests — Deployment preset profiles
# ---------------------------------------------------------------------------

_EXPECTED_PRESETS = [
    "solo_operator",
    "personal_assistant",
    "org_onboarding",
    "startup_growth",
    "enterprise_compliance",
    "agency_automation",
]


class TestPresetRegistry:
    """Verify the preset catalogue itself is well-formed."""

    def test_all_six_presets_exist(self):
        for pid in _EXPECTED_PRESETS:
            assert pid in PRESET_PROFILES, f"Missing preset: {pid}"

    def test_preset_count(self):
        assert len(PRESET_PROFILES) == 6

    def test_each_preset_has_required_keys(self):
        for pid, preset in PRESET_PROFILES.items():
            assert "id" in preset, f"{pid} missing 'id'"
            assert "name" in preset, f"{pid} missing 'name'"
            assert "description" in preset, f"{pid} missing 'description'"
            assert "profile" in preset, f"{pid} missing 'profile'"

    def test_preset_ids_match_keys(self):
        for pid, preset in PRESET_PROFILES.items():
            assert preset["id"] == pid

    def test_get_preset_profiles_returns_deep_copy(self):
        presets = get_preset_profiles()
        presets["solo_operator"]["name"] = "MUTATED"
        assert PRESET_PROFILES["solo_operator"]["name"] != "MUTATED"


class TestApplyPreset:
    """Verify apply_preset produces valid SetupProfile instances."""

    @pytest.mark.parametrize("preset_id", _EXPECTED_PRESETS)
    def test_apply_preset_returns_profile(self, preset_id):
        profile = apply_preset(preset_id)
        assert isinstance(profile, SetupProfile)

    @pytest.mark.parametrize("preset_id", _EXPECTED_PRESETS)
    def test_preset_org_name_override(self, preset_id):
        profile = apply_preset(preset_id, organization_name="Test Org")
        assert profile.organization_name == "Test Org"

    def test_unknown_preset_raises(self):
        with pytest.raises(ValueError, match="Unknown preset"):
            apply_preset("does_not_exist")

    @pytest.mark.parametrize("preset_id", _EXPECTED_PRESETS)
    def test_preset_industry_valid(self, preset_id):
        profile = apply_preset(preset_id)
        assert profile.industry in VALID_INDUSTRIES

    @pytest.mark.parametrize("preset_id", _EXPECTED_PRESETS)
    def test_preset_security_level_valid(self, preset_id):
        profile = apply_preset(preset_id)
        assert profile.security_level in VALID_SECURITY_LEVELS

    @pytest.mark.parametrize("preset_id", _EXPECTED_PRESETS)
    def test_preset_llm_provider_valid(self, preset_id):
        profile = apply_preset(preset_id)
        assert profile.llm_provider in VALID_LLM_PROVIDERS

    @pytest.mark.parametrize("preset_id", _EXPECTED_PRESETS)
    def test_preset_deployment_mode_valid(self, preset_id):
        profile = apply_preset(preset_id)
        assert profile.deployment_mode in VALID_DEPLOYMENT_MODES

    @pytest.mark.parametrize("preset_id", _EXPECTED_PRESETS)
    def test_preset_automation_types_valid(self, preset_id):
        profile = apply_preset(preset_id)
        for atype in profile.automation_types:
            assert atype in VALID_AUTOMATION_TYPES, (
                f"Preset {preset_id} has invalid automation type: {atype}"
            )

    @pytest.mark.parametrize("preset_id", _EXPECTED_PRESETS)
    def test_preset_compliance_frameworks_valid(self, preset_id):
        profile = apply_preset(preset_id)
        for fw in profile.compliance_frameworks:
            assert fw in VALID_COMPLIANCE_FRAMEWORKS, (
                f"Preset {preset_id} has invalid compliance framework: {fw}"
            )


class TestPresetValidation:
    """Every preset must pass the wizard's own validation (with org name)."""

    @pytest.mark.parametrize("preset_id", _EXPECTED_PRESETS)
    def test_preset_validates_with_org_name(self, preset_id):
        wiz = SetupWizard()
        profile = apply_preset(preset_id, organization_name="Validation Corp")
        result = wiz.validate_profile(profile)
        assert result["valid"] is True, (
            f"Preset {preset_id} failed validation: {result['issues']}"
        )


class TestPresetConfigGeneration:
    """Preset profiles must generate valid configs with core modules."""

    @pytest.mark.parametrize("preset_id", _EXPECTED_PRESETS)
    def test_preset_generates_config(self, preset_id):
        wiz = SetupWizard()
        profile = apply_preset(preset_id, organization_name="Config Corp")
        config = wiz.generate_config(profile)
        assert "organization" in config
        assert "modules" in config
        assert "bots" in config
        assert config["organization"]["name"] == "Config Corp"

    @pytest.mark.parametrize("preset_id", _EXPECTED_PRESETS)
    def test_preset_config_includes_core_modules(self, preset_id):
        wiz = SetupWizard()
        profile = apply_preset(preset_id, organization_name="Core Corp")
        config = wiz.generate_config(profile)
        for core_mod in CORE_MODULES:
            assert core_mod in config["modules"], (
                f"Preset {preset_id} missing core module: {core_mod}"
            )

    @pytest.mark.parametrize("preset_id", _EXPECTED_PRESETS)
    def test_preset_config_exports_to_json(self, preset_id, tmp_path):
        wiz = SetupWizard()
        profile = apply_preset(preset_id, organization_name="Export Corp")
        config = wiz.generate_config(profile)
        out = tmp_path / f"{preset_id}.json"
        wiz.export_config(config, str(out))
        assert out.exists()
        loaded = json.loads(out.read_text())
        assert loaded["organization"]["name"] == "Export Corp"


class TestPresetSpecificBehavior:
    """Verify each preset enables its expected modules and bots."""

    def test_solo_operator_has_sales(self):
        wiz = SetupWizard()
        profile = apply_preset("solo_operator")
        modules = wiz.get_enabled_modules(profile)
        assert "workflow_template_marketplace" in modules
        bots = wiz.get_recommended_bots(profile)
        assert "sales_outreach_bot" in bots

    def test_personal_assistant_minimal(self):
        wiz = SetupWizard()
        profile = apply_preset("personal_assistant")
        modules = wiz.get_enabled_modules(profile)
        assert "cross_platform_data_sync" in modules
        # No sales modules
        assert "workflow_template_marketplace" not in modules

    def test_org_onboarding_has_agent_modules(self):
        wiz = SetupWizard()
        profile = apply_preset("org_onboarding")
        modules = wiz.get_enabled_modules(profile)
        assert "shadow_agent_integration" in modules
        assert "compliance_region_validator" in modules

    def test_startup_growth_has_sales_and_agents(self):
        wiz = SetupWizard()
        profile = apply_preset("startup_growth")
        modules = wiz.get_enabled_modules(profile)
        bots = wiz.get_recommended_bots(profile)
        assert "shadow_agent_integration" in modules
        assert "sales_outreach_bot" in bots

    def test_enterprise_compliance_has_all_frameworks(self):
        profile = apply_preset("enterprise_compliance")
        assert "SOC2" in profile.compliance_frameworks
        assert "HIPAA" in profile.compliance_frameworks
        assert "GDPR" in profile.compliance_frameworks
        assert "ISO27001" in profile.compliance_frameworks
        assert profile.security_level == "hardened"
        assert profile.deployment_mode == "kubernetes"

    def test_enterprise_compliance_modules(self):
        wiz = SetupWizard()
        profile = apply_preset("enterprise_compliance")
        modules = wiz.get_enabled_modules(profile)
        assert "compliance_region_validator" in modules
        assert "contractual_audit" in modules

    def test_agency_automation_content_focus(self):
        wiz = SetupWizard()
        profile = apply_preset("agency_automation")
        modules = wiz.get_enabled_modules(profile)
        assert "content_creator_platform_modulator" in modules
        assert "social_media_moderation" in modules
        bots = wiz.get_recommended_bots(profile)
        assert "content_generation_bot" in bots

    def test_all_presets_have_monitoring_where_expected(self):
        """Presets with monitoring_enabled=True must get monitoring modules."""
        wiz = SetupWizard()
        for pid in _EXPECTED_PRESETS:
            profile = apply_preset(pid)
            modules = wiz.get_enabled_modules(profile)
            if profile.monitoring_enabled:
                assert "compliance_monitoring_completeness" in modules, (
                    f"Preset {pid} has monitoring enabled but missing module"
                )
            else:
                assert "compliance_monitoring_completeness" not in modules, (
                    f"Preset {pid} has monitoring disabled but got module"
                )

    def test_no_preset_enables_robotics(self):
        """None of the six presets enable robotics by default."""
        for pid in _EXPECTED_PRESETS:
            profile = apply_preset(pid)
            assert profile.robotics_enabled is False

    def test_all_presets_enable_avatar(self):
        """Every preset enables avatar for HITL identity."""
        for pid in _EXPECTED_PRESETS:
            profile = apply_preset(pid)
            assert profile.avatar_enabled is True


class TestPresetGapClosure:
    """Prove that preset profiles close identified responsibility gaps.

    Each test explicitly validates a gap that would exist without the
    preset system.
    """

    def test_gap_solo_operator_can_run_entire_business(self):
        """GAP-1: A solo operator needs sales + content + data in one config."""
        profile = apply_preset("solo_operator", organization_name="Solo LLC")
        assert "business" in profile.automation_types
        assert "data" in profile.automation_types
        assert "content" in profile.automation_types
        assert profile.sales_automation_enabled is True

    def test_gap_personal_assistant_low_overhead(self):
        """GAP-2: Personal assistant must have minimal overhead."""
        profile = apply_preset("personal_assistant")
        assert profile.security_level == "basic"
        assert profile.monitoring_enabled is False
        assert profile.sales_automation_enabled is False
        assert profile.deployment_mode == "local"

    def test_gap_org_onboarding_has_agent_and_compliance(self):
        """GAP-3: Org onboarding needs agent swarms and compliance."""
        profile = apply_preset("org_onboarding")
        assert "agent" in profile.automation_types
        assert "SOC2" in profile.compliance_frameworks

    def test_gap_enterprise_hardened_security(self):
        """GAP-4: Enterprise preset must use hardened security."""
        profile = apply_preset("enterprise_compliance")
        assert profile.security_level == "hardened"

    def test_gap_every_preset_passes_full_validation(self):
        """GAP-5: No preset should produce an invalid profile."""
        wiz = SetupWizard()
        for pid in _EXPECTED_PRESETS:
            profile = apply_preset(pid, organization_name="Gap Test Inc")
            result = wiz.validate_profile(profile)
            assert result["valid"] is True, (
                f"Preset {pid} fails validation: {result['issues']}"
            )
