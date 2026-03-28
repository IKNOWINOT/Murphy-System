"""
tests/test_skill_catalogue_engine.py — Round 58
================================================
Test suite for src/skill_catalogue_engine.py.

Structure
---------
Part 1  — SkillCategory enum completeness
Part 2  — SkillInput dataclass
Part 3  — SkillDefinition dataclass + summary()
Part 4  — SkillResult dataclass + to_dict()
Part 5  — SkillCatalogue CRUD
Part 6  — SkillCatalogue query helpers
Part 7  — SkillRegistry aggregation
Part 8  — SkillRegistry.run() — success / failure / not-found / no-invoke
Part 9  — SkillRegistry.search()
Part 10 — SkillRegistry.help_text()
Part 11 — SkillCatalogueEngine — invoke + session_log
Part 12 — SkillCatalogueEngine cyclic_context injection
Part 13 — SkillCatalogueEngine.parse_command() — list / search / run / help / log
Part 14 — build_default_registry() completeness
Part 15 — build_default_engine() factory
Part 16 — CPE catalogue skills
Part 17 — CNE catalogue skills
Part 18 — NME catalogue skills
Part 19 — CTE catalogue skills
Part 20 — Meta catalogue skills
"""

from __future__ import annotations

import pytest

from skill_catalogue_engine import (
    SkillCategory,
    SkillStatus,
    SkillInput,
    SkillDefinition,
    SkillResult,
    SkillCatalogue,
    SkillRegistry,
    SkillCatalogueEngine,
    build_default_registry,
    build_default_engine,
    _coerce,
    _parse_kwargs,
)


# ===========================================================================
# Fixtures
# ===========================================================================

@pytest.fixture
def simple_skill() -> SkillDefinition:
    return SkillDefinition(
        skill_id="test.add",
        name="Add Numbers",
        description="Returns the sum of a and b.",
        category=SkillCategory.SKILL_MANAGEMENT,
        source_engine="TestEngine",
        inputs=[
            SkillInput("a", "first number", input_type="float"),
            SkillInput("b", "second number", input_type="float"),
        ],
        tags=["math", "test"],
        invoke=lambda a=0, b=0: a + b,
    )


@pytest.fixture
def cyclic_skill() -> SkillDefinition:
    return SkillDefinition(
        skill_id="test.cyclic",
        name="Cyclic Skill",
        description="Echoes cyclic context.",
        category=SkillCategory.CYCLIC_TRENDS,
        source_engine="TestEngine",
        inputs=[SkillInput("season", "Season string", required=False, default=None)],
        tags=["cyclic"],
        cyclic_aware=True,
        invoke=lambda season=None: {"season": season},
    )


@pytest.fixture
def catalogue(simple_skill) -> SkillCatalogue:
    cat = SkillCatalogue("test_cat", SkillCategory.SKILL_MANAGEMENT)
    cat.register(simple_skill)
    return cat


@pytest.fixture
def registry(catalogue) -> SkillRegistry:
    reg = SkillRegistry()
    reg.add_catalogue(catalogue)
    return reg


@pytest.fixture
def engine(registry) -> SkillCatalogueEngine:
    return SkillCatalogueEngine(registry=registry)


@pytest.fixture
def default_registry() -> SkillRegistry:
    return build_default_registry()


@pytest.fixture
def default_engine() -> SkillCatalogueEngine:
    return build_default_engine()


# ===========================================================================
# Part 1 — SkillCategory enum completeness
# ===========================================================================

class TestSkillCategory:
    def test_twelve_categories(self):
        assert len(SkillCategory) == 12

    def test_demographic_intelligence_exists(self):
        assert SkillCategory.DEMOGRAPHIC_INTELLIGENCE == "demographic_intelligence"

    def test_pain_point_detection_exists(self):
        assert SkillCategory.PAIN_POINT_DETECTION == "pain_point_detection"

    def test_sales_framework_exists(self):
        assert SkillCategory.SALES_FRAMEWORK == "sales_framework"

    def test_income_scaling_exists(self):
        assert SkillCategory.INCOME_SCALING == "income_scaling"

    def test_character_network_exists(self):
        assert SkillCategory.CHARACTER_NETWORK == "character_network"

    def test_victorian_virtue_exists(self):
        assert SkillCategory.VICTORIAN_VIRTUE == "victorian_virtue"

    def test_networking_mastery_exists(self):
        assert SkillCategory.NETWORKING_MASTERY == "networking_mastery"

    def test_buzz_creation_exists(self):
        assert SkillCategory.BUZZ_CREATION == "buzz_creation"

    def test_capability_signalling_exists(self):
        assert SkillCategory.CAPABILITY_SIGNALLING == "capability_signalling"

    def test_cyclic_trends_exists(self):
        assert SkillCategory.CYCLIC_TRENDS == "cyclic_trends"

    def test_weather_adaptation_exists(self):
        assert SkillCategory.WEATHER_ADAPTATION == "weather_adaptation"

    def test_skill_management_exists(self):
        assert SkillCategory.SKILL_MANAGEMENT == "skill_management"


# ===========================================================================
# Part 2 — SkillInput dataclass
# ===========================================================================

class TestSkillInput:
    def test_required_by_default(self):
        si = SkillInput("x", "x value")
        assert si.required is True

    def test_default_none(self):
        si = SkillInput("x", "x value")
        assert si.default is None

    def test_input_type_str_by_default(self):
        si = SkillInput("x", "x value")
        assert si.input_type == "str"

    def test_optional_with_default(self):
        si = SkillInput("limit", "max results", required=False, default=10, input_type="int")
        assert si.required is False
        assert si.default == 10
        assert si.input_type == "int"


# ===========================================================================
# Part 3 — SkillDefinition
# ===========================================================================

class TestSkillDefinition:
    def test_summary_contains_skill_id(self, simple_skill):
        assert "test.add" in simple_skill.summary()

    def test_summary_contains_name(self, simple_skill):
        assert "Add Numbers" in simple_skill.summary()

    def test_summary_contains_description(self, simple_skill):
        assert "sum" in simple_skill.summary()

    def test_not_cyclic_aware_by_default(self, simple_skill):
        assert simple_skill.cyclic_aware is False

    def test_cyclic_aware_flag(self, cyclic_skill):
        assert cyclic_skill.cyclic_aware is True

    def test_tags_stored(self, simple_skill):
        assert "math" in simple_skill.tags


# ===========================================================================
# Part 4 — SkillResult + to_dict()
# ===========================================================================

class TestSkillResult:
    def test_success_result(self):
        r = SkillResult(skill_id="x", status=SkillStatus.SUCCESS, output=42)
        assert r.status == SkillStatus.SUCCESS
        assert r.output == 42

    def test_failure_result_has_error(self):
        r = SkillResult(skill_id="x", status=SkillStatus.FAILURE, output=None, error="boom")
        assert r.error == "boom"

    def test_to_dict_keys(self):
        r = SkillResult(skill_id="x", status=SkillStatus.SUCCESS, output="hello")
        d = r.to_dict()
        for key in ("log_id", "skill_id", "status", "output", "timestamp", "error", "metadata"):
            assert key in d

    def test_log_id_auto_generated(self):
        r1 = SkillResult(skill_id="x", status=SkillStatus.SUCCESS, output=None)
        r2 = SkillResult(skill_id="x", status=SkillStatus.SUCCESS, output=None)
        assert r1.log_id != r2.log_id

    def test_timestamp_format(self):
        r = SkillResult(skill_id="x", status=SkillStatus.SUCCESS, output=None)
        assert r.timestamp.endswith("Z")


# ===========================================================================
# Part 5 — SkillCatalogue CRUD
# ===========================================================================

class TestSkillCatalogue:
    def test_register_and_get(self, simple_skill):
        cat = SkillCatalogue("c", SkillCategory.SKILL_MANAGEMENT)
        cat.register(simple_skill)
        assert cat.get("test.add") is simple_skill

    def test_len(self, catalogue):
        assert len(catalogue) == 1

    def test_all_skills_returns_list(self, catalogue):
        skills = catalogue.all_skills()
        assert isinstance(skills, list)
        assert len(skills) == 1

    def test_get_missing_returns_none(self, catalogue):
        assert catalogue.get("no.such.skill") is None

    def test_register_chaining(self, simple_skill):
        cat = SkillCatalogue("c", SkillCategory.SKILL_MANAGEMENT)
        returned = cat.register(simple_skill)
        assert returned is cat

    def test_repr_contains_name(self, catalogue):
        assert "test_cat" in repr(catalogue)


# ===========================================================================
# Part 6 — SkillCatalogue query helpers
# ===========================================================================

class TestSkillCatalogueQueries:
    def test_by_tag_found(self, catalogue):
        assert len(catalogue.by_tag("math")) == 1

    def test_by_tag_miss(self, catalogue):
        assert catalogue.by_tag("nonexistent") == []

    def test_cyclic_skills_empty_for_non_cyclic(self, catalogue):
        assert catalogue.cyclic_skills() == []

    def test_cyclic_skills_found(self, cyclic_skill):
        cat = SkillCatalogue("c", SkillCategory.CYCLIC_TRENDS)
        cat.register(cyclic_skill)
        assert len(cat.cyclic_skills()) == 1


# ===========================================================================
# Part 7 — SkillRegistry aggregation
# ===========================================================================

class TestSkillRegistry:
    def test_add_catalogue(self, catalogue):
        reg = SkillRegistry()
        reg.add_catalogue(catalogue)
        assert len(reg) == 1

    def test_chaining(self, catalogue):
        reg = SkillRegistry()
        returned = reg.add_catalogue(catalogue)
        assert returned is reg

    def test_find_existing(self, registry):
        assert registry.find("test.add") is not None

    def test_find_missing_returns_none(self, registry):
        assert registry.find("x.y.z") is None

    def test_all_skills(self, registry):
        assert len(registry.all_skills()) == 1

    def test_skills_by_category(self, registry):
        skills = registry.skills_by_category(SkillCategory.SKILL_MANAGEMENT)
        assert len(skills) == 1

    def test_skills_by_category_wrong_returns_empty(self, registry):
        assert registry.skills_by_category(SkillCategory.BUZZ_CREATION) == []

    def test_len(self, registry):
        assert len(registry) == 1

    def test_repr(self, registry):
        assert "SkillRegistry" in repr(registry)


# ===========================================================================
# Part 8 — SkillRegistry.run()
# ===========================================================================

class TestSkillRegistryRun:
    def test_successful_run(self, registry):
        result = registry.run("test.add", a=3, b=4)
        assert result.status == SkillStatus.SUCCESS
        assert result.output == 7

    def test_skill_not_found(self, registry):
        result = registry.run("missing.skill")
        assert result.status == SkillStatus.FAILURE
        assert "not found" in result.error.lower()

    def test_skill_with_no_invoke(self):
        cat = SkillCatalogue("c", SkillCategory.SKILL_MANAGEMENT)
        cat.register(SkillDefinition(
            skill_id="no.invoke",
            name="No Invoke",
            description="desc",
            category=SkillCategory.SKILL_MANAGEMENT,
            source_engine="Test",
        ))
        reg = SkillRegistry()
        reg.add_catalogue(cat)
        result = reg.run("no.invoke")
        assert result.status == SkillStatus.SKIPPED

    def test_invoke_exception_returns_failure(self):
        cat = SkillCatalogue("c", SkillCategory.SKILL_MANAGEMENT)
        cat.register(SkillDefinition(
            skill_id="err.skill",
            name="Err",
            description="raises",
            category=SkillCategory.SKILL_MANAGEMENT,
            source_engine="Test",
            invoke=lambda: 1 / 0,
        ))
        reg = SkillRegistry()
        reg.add_catalogue(cat)
        result = reg.run("err.skill")
        assert result.status == SkillStatus.FAILURE
        assert result.error is not None


# ===========================================================================
# Part 9 — SkillRegistry.search()
# ===========================================================================

class TestSkillRegistrySearch:
    def test_search_by_name(self, registry):
        results = registry.search("Add")
        assert any(s.skill_id == "test.add" for s in results)

    def test_search_by_tag(self, registry):
        results = registry.search("math")
        assert len(results) >= 1

    def test_search_no_results(self, registry):
        assert registry.search("zzz_no_match_zzz") == []

    def test_search_case_insensitive(self, registry):
        results = registry.search("ADD NUMBERS")
        assert len(results) >= 1


# ===========================================================================
# Part 10 — SkillRegistry.help_text()
# ===========================================================================

class TestSkillRegistryHelpText:
    def test_help_text_contains_skill_id(self, registry):
        text = registry.help_text()
        assert "test.add" in text

    def test_help_text_contains_catalogue_name(self, registry):
        text = registry.help_text()
        assert "test_cat" in text.lower()


# ===========================================================================
# Part 11 — SkillCatalogueEngine invoke + session_log
# ===========================================================================

class TestSkillCatalogueEngineInvoke:
    def test_invoke_returns_result(self, engine):
        result = engine.invoke("test.add", a=1, b=2)
        assert result.output == 3

    def test_invoke_logs_to_session(self, engine):
        engine.invoke("test.add", a=10, b=5)
        assert len(engine.session_log) == 1

    def test_session_log_records_skill_id(self, engine):
        engine.invoke("test.add", a=0, b=0)
        assert engine.session_log[0].skill_id == "test.add"

    def test_session_log_records_inputs(self, engine):
        engine.invoke("test.add", a=7, b=3)
        assert engine.session_log[0].inputs.get("a") == 7

    def test_multiple_invocations_all_logged(self, engine):
        for i in range(5):
            engine.invoke("test.add", a=i, b=i)
        assert len(engine.session_log) == 5

    def test_invoke_missing_skill_still_logs(self, engine):
        engine.invoke("missing.skill")
        assert len(engine.session_log) == 1
        assert engine.session_log[0].result.status == SkillStatus.FAILURE

    def test_total_skills(self, engine):
        assert engine.total_skills() == 1


# ===========================================================================
# Part 12 — Cyclic context injection
# ===========================================================================

class TestCyclicContextInjection:
    def test_set_cyclic_context_stored(self, engine, cyclic_skill):
        engine.registry.find("test.add")  # sanity
        engine.add_catalogue(
            SkillCatalogue("cc", SkillCategory.CYCLIC_TRENDS).register(cyclic_skill)
        )
        engine.set_cyclic_context(season="SUMMER")
        result = engine.invoke("test.cyclic")
        assert result.output["season"] == "SUMMER"

    def test_caller_kwargs_override_cyclic(self, engine, cyclic_skill):
        engine.add_catalogue(
            SkillCatalogue("cc2", SkillCategory.CYCLIC_TRENDS).register(cyclic_skill)
        )
        engine.set_cyclic_context(season="SUMMER")
        result = engine.invoke("test.cyclic", season="WINTER")
        assert result.output["season"] == "WINTER"

    def test_clear_cyclic_context(self, engine, cyclic_skill):
        engine.add_catalogue(
            SkillCatalogue("cc3", SkillCategory.CYCLIC_TRENDS).register(cyclic_skill)
        )
        engine.set_cyclic_context(season="AUTUMN")
        engine.clear_cyclic_context()
        result = engine.invoke("test.cyclic")
        assert result.output["season"] is None

    def test_non_cyclic_skill_ignores_context(self, engine):
        engine.set_cyclic_context(season="SPRING")
        result = engine.invoke("test.add", a=1, b=1)
        assert result.status == SkillStatus.SUCCESS

    def test_cyclic_context_not_injected_into_non_cyclic_skill(self, engine):
        engine.set_cyclic_context(season="SPRING")
        result = engine.invoke("test.add", a=2, b=2)
        assert result.output == 4


# ===========================================================================
# Part 13 — parse_command()
# ===========================================================================

class TestParseCommand:
    def test_list_all(self, engine):
        response = engine.parse_command("/skill list")
        assert "test.add" in response

    def test_list_unknown_category(self, engine):
        response = engine.parse_command("/skill list unknown_cat_xyz")
        assert "Unknown category" in response

    def test_search_found(self, engine):
        response = engine.parse_command("/skill search math")
        assert "test.add" in response

    def test_search_not_found(self, engine):
        response = engine.parse_command("/skill search zzz_no_match_zzz")
        assert "No skills matched" in response

    def test_search_missing_query(self, engine):
        response = engine.parse_command("/skill search")
        assert "Usage" in response

    def test_run_known_skill(self, engine):
        response = engine.parse_command("/skill run test.add a=3 b=4")
        assert "success" in response.lower()

    def test_run_missing_skill_id(self, engine):
        response = engine.parse_command("/skill run")
        assert "Usage" in response

    def test_help_specific_skill(self, engine):
        response = engine.parse_command("/skill help test.add")
        assert "Add Numbers" in response

    def test_help_unknown_skill(self, engine):
        response = engine.parse_command("/skill help no.such.skill")
        assert "not found" in response.lower()

    def test_help_no_arg_returns_all(self, engine):
        response = engine.parse_command("/skill help")
        assert "Available Skills" in response

    def test_log_empty(self, engine):
        response = engine.parse_command("/skill log")
        assert "empty" in response.lower()

    def test_log_after_invocation(self, engine):
        engine.invoke("test.add", a=1, b=1)
        response = engine.parse_command("/skill log")
        assert "test.add" in response

    def test_unknown_subcommand(self, engine):
        response = engine.parse_command("/skill xyzzy")
        assert "Unknown sub-command" in response


# ===========================================================================
# Part 14 — build_default_registry() completeness
# ===========================================================================

class TestDefaultRegistry:
    def test_has_five_catalogues(self, default_registry):
        assert len(default_registry.all_catalogues()) == 5

    def test_has_at_least_twenty_skills(self, default_registry):
        assert len(default_registry) >= 20

    def test_cpe_skills_present(self, default_registry):
        assert default_registry.find("cpe.read_client") is not None

    def test_cne_skills_present(self, default_registry):
        assert default_registry.find("cne.score_moral_fiber") is not None

    def test_nme_skills_present(self, default_registry):
        assert default_registry.find("nme.create_buzz") is not None

    def test_cte_skills_present(self, default_registry):
        assert default_registry.find("cte.get_month_context") is not None

    def test_meta_skills_present(self, default_registry):
        assert default_registry.find("sce.list_all") is not None

    def test_all_skills_have_descriptions(self, default_registry):
        for skill in default_registry.all_skills():
            assert skill.description, f"{skill.skill_id} has empty description"

    def test_all_skills_have_category(self, default_registry):
        for skill in default_registry.all_skills():
            assert isinstance(skill.category, SkillCategory)

    def test_all_skills_have_source_engine(self, default_registry):
        for skill in default_registry.all_skills():
            assert skill.source_engine


# ===========================================================================
# Part 15 — build_default_engine() factory
# ===========================================================================

class TestBuildDefaultEngine:
    def test_returns_engine_instance(self, default_engine):
        assert isinstance(default_engine, SkillCatalogueEngine)

    def test_engine_has_skills(self, default_engine):
        assert default_engine.total_skills() >= 20

    def test_engine_with_cyclic_context(self):
        engine = build_default_engine(cyclic_context={"season": "SPRING", "weather_pattern": "WARM_SUNNY"})
        assert engine._cyclic_context.get("season") == "SPRING"

    def test_session_log_empty_on_creation(self, default_engine):
        assert len(default_engine.session_log) == 0


# ===========================================================================
# Part 16 — CPE catalogue skills
# ===========================================================================

class TestCPECatalogue:
    def test_profile_generation_skill(self, default_registry):
        skill = default_registry.find("cpe.profile_generation")
        assert skill is not None
        assert skill.category == SkillCategory.DEMOGRAPHIC_INTELLIGENCE

    def test_detect_pain_skill(self, default_registry):
        skill = default_registry.find("cpe.detect_pain")
        assert skill.category == SkillCategory.PAIN_POINT_DETECTION

    def test_select_framework_skill(self, default_registry):
        skill = default_registry.find("cpe.select_framework")
        assert skill.category == SkillCategory.SALES_FRAMEWORK

    def test_adapt_language_skill(self, default_registry):
        skill = default_registry.find("cpe.adapt_language")
        assert "language" in skill.tags

    def test_income_scaling_skill(self, default_registry):
        skill = default_registry.find("cpe.income_scaling")
        assert "2x" in skill.tags

    def test_read_client_skill(self, default_registry):
        skill = default_registry.find("cpe.read_client")
        assert "report" in skill.tags

    def test_read_client_invocable(self, default_registry):
        result = default_registry.run("cpe.read_client", statement="We need to grow revenue.")
        assert result.status == SkillStatus.SUCCESS
        assert result.output["action"] == "read_client"

    def test_detect_pain_invocable(self, default_registry):
        result = default_registry.run("cpe.detect_pain", statement="Our churn rate is killing us.")
        assert result.status == SkillStatus.SUCCESS


# ===========================================================================
# Part 17 — CNE catalogue skills
# ===========================================================================

class TestCNECatalogue:
    def test_score_moral_fiber_skill(self, default_registry):
        skill = default_registry.find("cne.score_moral_fiber")
        assert skill.category == SkillCategory.VICTORIAN_VIRTUE

    def test_match_archetype_skill(self, default_registry):
        skill = default_registry.find("cne.match_archetype")
        assert "victorian" in skill.tags

    def test_build_network_skill(self, default_registry):
        skill = default_registry.find("cne.build_network")
        assert "trust" in skill.tags

    def test_second_nature_skill(self, default_registry):
        skill = default_registry.find("cne.second_nature_prompt")
        assert "invisible-good" in skill.tags

    def test_virtue_development_plan_skill(self, default_registry):
        skill = default_registry.find("cne.virtue_development_plan")
        assert "growth" in skill.tags

    def test_score_moral_fiber_invocable(self, default_registry):
        result = default_registry.run(
            "cne.score_moral_fiber",
            contact_id="john_doe",
            trait_signals={"integrity": 0.9, "diligence": 0.85},
        )
        assert result.status == SkillStatus.SUCCESS
        assert result.output["contact_id"] == "john_doe"

    def test_second_nature_invocable(self, default_registry):
        result = default_registry.run(
            "cne.second_nature_prompt",
            context="board_meeting",
            relationship_stage="established",
        )
        assert result.status == SkillStatus.SUCCESS


# ===========================================================================
# Part 18 — NME catalogue skills
# ===========================================================================

class TestNMECatalogue:
    def test_profile_master_skill(self, default_registry):
        skill = default_registry.find("nme.profile_master")
        assert "mastery" in skill.tags

    def test_create_buzz_is_cyclic_aware(self, default_registry):
        skill = default_registry.find("nme.create_buzz")
        assert skill.cyclic_aware is True

    def test_signal_capability_skill(self, default_registry):
        skill = default_registry.find("nme.signal_capability")
        assert "three-layer" in skill.tags

    def test_network_intelligence_skill(self, default_registry):
        skill = default_registry.find("nme.network_intelligence")
        assert skill.cyclic_aware is True

    def test_event_timing_skill(self, default_registry):
        skill = default_registry.find("nme.event_timing")
        assert "calendar" in skill.tags

    def test_create_buzz_invocable(self, default_registry):
        result = default_registry.run(
            "nme.create_buzz",
            objective="launch new product line",
            audience="enterprise CTOs",
        )
        assert result.status == SkillStatus.SUCCESS

    def test_signal_capability_three_layers(self, default_registry):
        result = default_registry.run(
            "nme.signal_capability",
            capability="AI automation",
            audience_type="executive",
        )
        assert result.output["action"] == "signal_capability"


# ===========================================================================
# Part 19 — CTE catalogue skills
# ===========================================================================

class TestCTECatalogue:
    def test_get_month_context_skill(self, default_registry):
        skill = default_registry.find("cte.get_month_context")
        assert "season" in skill.tags

    def test_automation_trend_input_is_cyclic_aware(self, default_registry):
        skill = default_registry.find("cte.automation_trend_input")
        assert skill.cyclic_aware is True

    def test_automation_trend_input_tags(self, default_registry):
        skill = default_registry.find("cte.automation_trend_input")
        assert "automation" in skill.tags
        assert "weather" in skill.tags

    def test_trend_snapshot_is_cyclic_aware(self, default_registry):
        assert default_registry.find("cte.trend_snapshot").cyclic_aware is True

    def test_weather_signal_bank_skill(self, default_registry):
        skill = default_registry.find("cte.weather_signal_bank")
        assert "signal" in skill.tags

    def test_get_month_context_invocable(self, default_registry):
        result = default_registry.run(
            "cte.get_month_context",
            month=7,
            temperature_deviation=3.0,
        )
        assert result.status == SkillStatus.SUCCESS
        assert result.output["month"] == 7

    def test_automation_trend_input_invocable(self, default_registry):
        result = default_registry.run(
            "cte.automation_trend_input",
            automation_type="energy",
            month=8,
            weather_pattern="hot_humid",
        )
        assert result.output["automation_type"] == "energy"

    def test_cyclic_context_auto_injected_into_automation_skill(self):
        engine = build_default_engine(cyclic_context={"season": "WINTER", "economic_phase": "CONTRACTION"})
        result = engine.invoke("cte.automation_trend_input", automation_type="scheduling")
        assert result.output["season"] == "WINTER"
        assert result.output["economic_phase"] == "CONTRACTION"


# ===========================================================================
# Part 20 — Meta catalogue skills
# ===========================================================================

class TestMetaCatalogue:
    def test_list_all_skill(self, default_registry):
        skill = default_registry.find("sce.list_all")
        assert "meta" in skill.tags

    def test_search_skill(self, default_registry):
        skill = default_registry.find("sce.search")
        assert skill is not None

    def test_session_log_skill(self, default_registry):
        skill = default_registry.find("sce.session_log")
        assert "log" in skill.tags

    def test_list_all_invocable(self, default_registry):
        result = default_registry.run("sce.list_all")
        assert result.status == SkillStatus.SUCCESS
        assert result.output["action"] == "list_all"

    def test_search_invocable(self, default_registry):
        result = default_registry.run("sce.search", query="pain")
        assert result.status == SkillStatus.SUCCESS


# ===========================================================================
# Utility helpers
# ===========================================================================

class TestUtilityHelpers:
    def test_coerce_true(self):
        assert _coerce("true") is True

    def test_coerce_yes(self):
        assert _coerce("yes") is True

    def test_coerce_false(self):
        assert _coerce("false") is False

    def test_coerce_int(self):
        assert _coerce("42") == 42

    def test_coerce_float(self):
        assert abs(_coerce("3.14") - 3.14) < 0.001

    def test_coerce_string(self):
        assert _coerce("hello") == "hello"

    def test_parse_kwargs_basic(self):
        kwargs = _parse_kwargs(["a=3", "b=4"])
        assert kwargs == {"a": 3, "b": 4}

    def test_parse_kwargs_mixed_types(self):
        kwargs = _parse_kwargs(["name=alice", "score=0.9", "active=true"])
        assert kwargs["name"] == "alice"
        assert abs(kwargs["score"] - 0.9) < 0.001
        assert kwargs["active"] is True

    def test_parse_kwargs_empty(self):
        assert _parse_kwargs([]) == {}

    def test_parse_kwargs_ignores_non_kv(self):
        kwargs = _parse_kwargs(["notakv", "a=1"])
        assert "notakv" not in kwargs
        assert kwargs["a"] == 1
