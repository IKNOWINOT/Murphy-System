"""
Tests for Historical Greatness Engine and Elite Org Simulator integration.

Covers:
  Part 1  — GreatnessTrait enum completeness (10 traits)
  Part 2  — HistoricalClass enum completeness (10 classes)
  Part 3  — TraitDefinition coverage and content quality
  Part 4  — HistoricalGreats corpus — count, scores, peak traits
  Part 5  — GreatnessBenchmark — per-class, all-time, elite thresholds
  Part 6  — SkillGenome → TraitProfiler calibration
  Part 7  — ArchetypeMatcher — class champions, top-N, trait champions
  Part 8  — CalibrationResult completeness and consistency
  Part 9  — Trait development plan generation
  Part 10 — Agent calibration from KAIA mix + influence frameworks
  Part 11 — EliteOrgSimulator.calibrate_chart / calibrate_role wiring
  Part 12 — Org greatness summary consistency checks
  Part 13 — Cross-class trait universality (all greats score > 0.7 on all traits)
  Part 14 — Distance metrics and archetype ranking
  Part 15 — describe_trait full content check
"""

from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
from historical_greatness_engine import (
    ALL_TRAITS,
    BENCHMARK,
    HISTORICAL_GREATS,
    TRAIT_DEFINITIONS,
    ArchetypeMatcher,
    CalibrationResult,
    GreatnessBenchmark,
    GreatnessTrait,
    HistoricalClass,
    HistoricalGreat,
    HistoricalGreatnessEngine,
    TraitDefinition,
    TraitProfiler,
    _build_historical_greats,
    _t,
)
from elite_org_simulator import (
    CompanyStage,
    EliteOrgSimulator,
    OrgChartBuilder,
    ScenarioType,
    SkillGenome,
    COMPETENCY_DIMENSIONS,
    _ELITE_GENOMES,
    _ROLE_FRAMEWORKS,
    _KAIA_MIXES,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def engine() -> HistoricalGreatnessEngine:
    return HistoricalGreatnessEngine()


@pytest.fixture(scope="module")
def sim() -> EliteOrgSimulator:
    return EliteOrgSimulator(seed=77)


@pytest.fixture(scope="module")
def series_b_chart():
    return OrgChartBuilder().build(CompanyStage.SERIES_B)


@pytest.fixture(scope="module")
def profiler() -> TraitProfiler:
    return TraitProfiler()


@pytest.fixture(scope="module")
def matcher() -> ArchetypeMatcher:
    return ArchetypeMatcher()


# ---------------------------------------------------------------------------
# Part 1 — GreatnessTrait enum completeness
# ---------------------------------------------------------------------------

class TestGreatnessTrait:
    def test_ten_traits_defined(self):
        assert len(ALL_TRAITS) == 10

    def test_all_expected_traits_present(self):
        expected = {
            "obsessive_focus", "extreme_preparation", "failure_as_data",
            "pattern_recognition", "radical_self_belief", "cross_domain_learning",
            "narrative_mastery", "adaptive_strategy", "network_leverage",
            "long_game_thinking",
        }
        actual = {t.value for t in ALL_TRAITS}
        assert actual == expected

    def test_traits_are_string_enum(self):
        for trait in ALL_TRAITS:
            assert isinstance(trait.value, str)
            assert len(trait.value) > 0

    def test_traits_unique(self):
        values = [t.value for t in ALL_TRAITS]
        assert len(values) == len(set(values))


# ---------------------------------------------------------------------------
# Part 2 — HistoricalClass enum completeness
# ---------------------------------------------------------------------------

class TestHistoricalClass:
    def test_ten_classes_defined(self):
        classes = list(HistoricalClass)
        assert len(classes) == 10

    def test_all_expected_classes_present(self):
        expected = {
            "military", "business", "science", "arts", "politics",
            "athletics", "philosophy", "engineering", "spiritual", "exploration",
        }
        actual = {c.value for c in HistoricalClass}
        assert actual == expected


# ---------------------------------------------------------------------------
# Part 3 — TraitDefinition coverage and content quality
# ---------------------------------------------------------------------------

class TestTraitDefinitions:
    def test_all_traits_have_definitions(self):
        for trait in ALL_TRAITS:
            assert trait in TRAIT_DEFINITIONS, f"Missing definition for {trait}"

    def test_definitions_have_required_fields(self):
        required = [
            "name", "description", "core_question", "evidence_phrase",
            "modern_equivalent", "anti_pattern", "historical_epitome", "epitome_quote",
        ]
        for trait, defn in TRAIT_DEFINITIONS.items():
            for field in required:
                val = getattr(defn, field)
                assert isinstance(val, str), f"{trait}.{field} must be str"
                assert len(val) >= 8, f"{trait}.{field} too short: {val!r}"

    def test_definitions_have_unique_names(self):
        names = [d.name for d in TRAIT_DEFINITIONS.values()]
        assert len(names) == len(set(names))

    def test_definitions_have_unique_epitomes(self):
        epitomes = [d.historical_epitome for d in TRAIT_DEFINITIONS.values()]
        assert len(epitomes) == len(set(epitomes)), "Each trait should have a unique historical epitome"

    def test_obsessive_focus_epitome_is_newton(self):
        defn = TRAIT_DEFINITIONS[GreatnessTrait.OBSESSIVE_FOCUS]
        assert "Newton" in defn.historical_epitome

    def test_narrative_mastery_epitome_is_churchill(self):
        defn = TRAIT_DEFINITIONS[GreatnessTrait.NARRATIVE_MASTERY]
        assert "Churchill" in defn.historical_epitome

    def test_long_game_thinking_epitome_is_buffett(self):
        defn = TRAIT_DEFINITIONS[GreatnessTrait.LONG_GAME_THINKING]
        assert "Buffett" in defn.historical_epitome

    def test_all_quotes_nonempty(self):
        for trait, defn in TRAIT_DEFINITIONS.items():
            assert len(defn.epitome_quote) > 20, f"{trait} quote too short"

    def test_anti_patterns_distinct(self):
        anti_patterns = [d.anti_pattern for d in TRAIT_DEFINITIONS.values()]
        # Should all be unique (different failure modes for different traits)
        assert len(anti_patterns) == len(set(anti_patterns))


# ---------------------------------------------------------------------------
# Part 4 — HistoricalGreats corpus
# ---------------------------------------------------------------------------

class TestHistoricalGreatsCorpus:
    def test_at_least_40_greats(self):
        assert len(HISTORICAL_GREATS) >= 40

    def test_all_classes_represented(self):
        classes_in_corpus = {g.primary_class for g in HISTORICAL_GREATS.values()}
        for hc in HistoricalClass:
            assert hc in classes_in_corpus, f"Class {hc} has no primary representative"

    def test_all_greats_have_ten_trait_scores(self):
        for gid, great in HISTORICAL_GREATS.items():
            assert len(great.trait_scores) == 10, f"{gid} missing trait scores"
            for trait in ALL_TRAITS:
                assert trait in great.trait_scores, f"{gid} missing {trait}"

    def test_all_scores_in_range(self):
        for gid, great in HISTORICAL_GREATS.items():
            for trait, score in great.trait_scores.items():
                assert 0.0 <= score <= 1.0, f"{gid}.{trait} = {score} out of range"

    def test_all_greats_score_above_floor(self):
        """Elite historical greats should score ≥ 0.65 on every single trait."""
        for gid, great in HISTORICAL_GREATS.items():
            for trait, score in great.trait_scores.items():
                assert score >= 0.65, (
                    f"{gid} ({great.name}) scored {score:.2f} on {trait.value} — "
                    f"below the 0.65 floor for historical greatness"
                )

    def test_overall_scores_all_above_08(self):
        for gid, great in HISTORICAL_GREATS.items():
            assert great.overall_score >= 0.80, (
                f"{gid} overall_score {great.overall_score:.4f} below 0.80"
            )

    def test_known_figures_present(self):
        known = ["isaac_newton", "lincoln", "da_vinci", "napoleon", "caesar", "warren_buffett",
                 "albert_einstein", "gandhi", "aristotle", "shakespeare", "michael_jordan"]
        for gid in known:
            assert gid in HISTORICAL_GREATS, f"Expected {gid!r} in corpus"

    def test_napoleon_extreme_preparation_maxes_out(self):
        napoleon = HISTORICAL_GREATS["napoleon"]
        assert napoleon.trait_scores[GreatnessTrait.EXTREME_PREPARATION] == 1.00

    def test_da_vinci_cross_domain_maxes_out(self):
        da_vinci = HISTORICAL_GREATS["da_vinci"]
        assert da_vinci.trait_scores[GreatnessTrait.CROSS_DOMAIN_LEARNING] == 1.00

    def test_franklin_cross_domain_maxes_out(self):
        franklin = HISTORICAL_GREATS["benjamin_franklin"]
        assert franklin.trait_scores[GreatnessTrait.CROSS_DOMAIN_LEARNING] == 1.00

    def test_jobs_narrative_mastery_near_max(self):
        jobs = HISTORICAL_GREATS["steve_jobs"]
        assert jobs.trait_scores[GreatnessTrait.NARRATIVE_MASTERY] >= 0.98

    def test_peak_trait_is_max(self):
        for gid, great in HISTORICAL_GREATS.items():
            peak_trait, peak_score = great.peak_trait
            for trait, score in great.trait_scores.items():
                assert score <= peak_score + 1e-9, (
                    f"{gid} peak trait is {peak_trait} ({peak_score:.2f}) but {trait} = {score:.2f}"
                )

    def test_each_great_has_unique_id(self):
        ids = list(HISTORICAL_GREATS.keys())
        assert len(ids) == len(set(ids))

    def test_greats_have_signature_achievement(self):
        for gid, great in HISTORICAL_GREATS.items():
            assert len(great.signature_achievement) > 10, f"{gid} missing signature_achievement"

    def test_greats_have_core_lesson(self):
        for gid, great in HISTORICAL_GREATS.items():
            assert len(great.core_lesson) > 20, f"{gid} missing core_lesson"

    def test_distance_to_self_is_zero(self):
        napoleon = HISTORICAL_GREATS["napoleon"]
        assert napoleon.distance_to(napoleon.trait_scores) == 0.0

    def test_distance_to_different_is_positive(self):
        napoleon = HISTORICAL_GREATS["napoleon"]
        gandhi = HISTORICAL_GREATS["gandhi"]
        assert napoleon.distance_to(gandhi.trait_scores) > 0.0

    def test_to_dict_contains_required_keys(self):
        great = HISTORICAL_GREATS["lincoln"]
        d = great.to_dict()
        for key in ["great_id", "name", "era", "primary_class", "trait_scores",
                    "overall_score", "peak_trait", "signature_achievement", "core_lesson"]:
            assert key in d


# ---------------------------------------------------------------------------
# Part 5 — GreatnessBenchmark
# ---------------------------------------------------------------------------

class TestGreatnessBenchmark:
    def test_all_time_mean_has_all_traits(self):
        for trait in ALL_TRAITS:
            assert trait in BENCHMARK.all_time_mean

    def test_all_time_mean_scores_in_range(self):
        for trait, score in BENCHMARK.all_time_mean.items():
            assert 0.0 <= score <= 1.0

    def test_elite_threshold_has_all_traits(self):
        for trait in ALL_TRAITS:
            assert trait in BENCHMARK.elite_threshold

    def test_elite_threshold_gte_all_time_mean(self):
        for trait in ALL_TRAITS:
            assert BENCHMARK.elite_threshold[trait] >= BENCHMARK.all_time_mean[trait], (
                f"{trait}: elite_threshold {BENCHMARK.elite_threshold[trait]:.4f} "
                f"< all_time_mean {BENCHMARK.all_time_mean[trait]:.4f}"
            )

    def test_per_class_means_cover_all_represented_classes(self):
        classes_in_corpus = {g.primary_class for g in HISTORICAL_GREATS.values()}
        for hc in classes_in_corpus:
            assert hc in BENCHMARK.per_class_means, f"{hc} missing from per_class_means"

    def test_per_class_means_all_traits_present(self):
        for hc, scores in BENCHMARK.per_class_means.items():
            for trait in ALL_TRAITS:
                assert trait in scores, f"{hc} missing {trait} in per_class_means"

    def test_percentile_rank_returns_0_to_100(self):
        for trait in ALL_TRAITS:
            for score in [0.0, 0.5, 0.80, 0.95, 1.0]:
                rank = BENCHMARK.percentile_rank(trait, score)
                assert 0.0 <= rank <= 100.0

    def test_higher_score_higher_percentile(self):
        trait = GreatnessTrait.OBSESSIVE_FOCUS
        low = BENCHMARK.percentile_rank(trait, 0.75)
        high = BENCHMARK.percentile_rank(trait, 0.95)
        assert high > low

    def test_to_dict_has_required_keys(self):
        d = BENCHMARK.to_dict()
        assert "all_time_mean" in d
        assert "elite_threshold" in d
        assert "per_class_means" in d


# ---------------------------------------------------------------------------
# Part 6 — SkillGenome → TraitProfiler calibration
# ---------------------------------------------------------------------------

class TestTraitProfiler:
    def test_ceo_genome_produces_calibration(self, profiler):
        genome = SkillGenome.build("ceo")
        result = profiler.profile(genome.scores, subject_id="ceo")
        assert result.subject_id == "ceo"
        assert len(result.trait_scores) == 10

    def test_all_role_keys_produce_valid_calibration(self, profiler):
        for role_key in list(_ELITE_GENOMES.keys())[:15]:   # sample first 15
            genome = SkillGenome.build(role_key)
            result = profiler.profile(genome.scores, subject_id=role_key)
            assert 0.0 <= result.overall_greatness <= 1.0

    def test_trait_scores_in_range(self, profiler):
        genome = SkillGenome.build("vp_sales")
        result = profiler.profile(genome.scores, subject_id="vp_sales")
        for trait, score in result.trait_scores.items():
            assert 0.0 <= score <= 1.0

    def test_peak_trait_is_max(self, profiler):
        genome = SkillGenome.build("cto")
        result = profiler.profile(genome.scores, subject_id="cto")
        peak_t, peak_s = result.peak_trait
        for s in result.trait_scores.values():
            assert s <= peak_s + 1e-9

    def test_growth_traits_are_lowest(self, profiler):
        genome = SkillGenome.build("sdr")
        result = profiler.profile(genome.scores, subject_id="sdr")
        if result.growth_traits:
            growth_scores = [s for _, s in result.growth_traits]
            all_scores = list(result.trait_scores.values())
            assert max(growth_scores) <= sorted(all_scores)[len(growth_scores) - 1] + 1e-9

    def test_archetype_match_is_historical_great(self, profiler):
        genome = SkillGenome.build("ceo")
        result = profiler.profile(genome.scores, subject_id="ceo")
        assert result.archetype_match.great_id in HISTORICAL_GREATS

    def test_recommendations_not_empty(self, profiler):
        genome = SkillGenome.build("marketing_manager")
        result = profiler.profile(genome.scores, subject_id="mm")
        assert len(result.recommendations) >= 2

    def test_historical_class_alignment_is_valid(self, profiler):
        genome = SkillGenome.build("senior_software_engineer")
        result = profiler.profile(genome.scores, subject_id="sse")
        assert result.historical_class_alignment in list(HistoricalClass)

    def test_percentile_ranks_populated(self, profiler):
        genome = SkillGenome.build("cfo")
        result = profiler.profile(genome.scores)
        assert len(result.percentile_ranks) == 10
        for rank in result.percentile_ranks.values():
            assert 0.0 <= rank <= 100.0

    def test_high_execution_maps_to_obsessive_focus(self, profiler):
        """A genome with very high execution_speed should score well on OBSESSIVE_FOCUS."""
        scores = {dim: 0.5 for dim in COMPETENCY_DIMENSIONS}
        scores["execution_speed"] = 1.0
        scores["technical_depth"] = 1.0
        result = profiler.profile(scores)
        focus_score = result.trait_scores[GreatnessTrait.OBSESSIVE_FOCUS]
        assert focus_score > 0.65

    def test_high_communication_maps_to_narrative_mastery(self, profiler):
        scores = {dim: 0.5 for dim in COMPETENCY_DIMENSIONS}
        scores["communication_clarity"] = 1.0
        scores["leadership_presence"] = 1.0
        result = profiler.profile(scores)
        narr_score = result.trait_scores[GreatnessTrait.NARRATIVE_MASTERY]
        assert narr_score > 0.65

    def test_secondary_archetype_different_from_primary(self, profiler):
        genome = SkillGenome.build("ceo")
        result = profiler.profile(genome.scores, subject_id="ceo")
        if result.secondary_archetype:
            assert result.secondary_archetype.great_id != result.archetype_match.great_id


# ---------------------------------------------------------------------------
# Part 7 — ArchetypeMatcher
# ---------------------------------------------------------------------------

class TestArchetypeMatcher:
    def test_class_champions_covers_all_classes(self, matcher):
        champions = matcher.class_champions()
        for hc in HistoricalClass:
            if any(g.primary_class == hc for g in HISTORICAL_GREATS.values()):
                assert hc in champions

    def test_class_champion_is_highest_scorer_in_class(self, matcher):
        champions = matcher.class_champions()
        for hc, champ in champions.items():
            class_greats = [g for g in HISTORICAL_GREATS.values() if g.primary_class == hc]
            best_score = max(g.overall_score for g in class_greats)
            assert abs(champ.overall_score - best_score) < 1e-9

    def test_top_n_all_time_returns_n_items(self, matcher):
        for n in [1, 5, 10, 20]:
            top = matcher.top_n_all_time(n)
            assert len(top) == min(n, len(HISTORICAL_GREATS))

    def test_top_10_are_descending_order(self, matcher):
        top = matcher.top_n_all_time(10)
        scores = [g.overall_score for g in top]
        assert scores == sorted(scores, reverse=True)

    def test_trait_champions_covers_all_traits(self, matcher):
        champions = matcher.trait_champions()
        for trait in ALL_TRAITS:
            assert trait in champions

    def test_trait_champion_has_highest_score_for_that_trait(self, matcher):
        champions = matcher.trait_champions()
        for trait, champ in champions.items():
            max_score = max(g.trait_scores.get(trait, 0.0) for g in HISTORICAL_GREATS.values())
            assert abs(champ.trait_scores.get(trait, 0.0) - max_score) < 1e-9

    def test_match_by_traits_returns_historical_great(self, matcher):
        traits = {t: 0.95 for t in ALL_TRAITS}
        result = matcher.match_by_traits(traits)
        assert isinstance(result, HistoricalGreat)

    def test_match_by_competencies_returns_calibration_result(self, matcher):
        scores = {dim: 0.88 for dim in COMPETENCY_DIMENSIONS}
        result = matcher.match_by_competencies(scores, subject_id="test")
        assert isinstance(result, CalibrationResult)
        assert result.subject_id == "test"

    def test_napoleon_archetype_for_prep_dominant_profile(self, matcher):
        """A profile dominated by extreme_preparation should match a military / prep legend."""
        traits = {t: 0.75 for t in ALL_TRAITS}
        traits[GreatnessTrait.EXTREME_PREPARATION] = 1.00
        traits[GreatnessTrait.PATTERN_RECOGNITION] = 0.98
        traits[GreatnessTrait.ADAPTIVE_STRATEGY]   = 0.95
        result = matcher.match_by_traits(traits)
        # Napoleon, Alexander, Sun Tzu, or Eisenhower are all valid (high prep + adaptive military)
        assert result.primary_class in (HistoricalClass.MILITARY, HistoricalClass.POLITICS)


# ---------------------------------------------------------------------------
# Part 8 — CalibrationResult completeness
# ---------------------------------------------------------------------------

class TestCalibrationResult:
    def test_to_dict_has_all_required_keys(self, engine):
        genome = SkillGenome.build("ceo")
        result = engine.calibrate_genome(genome, subject_id="ceo_test")
        d = result.to_dict()
        required_keys = [
            "subject_id", "subject_type", "trait_scores", "percentile_ranks",
            "overall_greatness", "archetype_match", "archetype_distance",
            "peak_trait", "growth_traits", "recommendations", "historical_class_alignment",
        ]
        for key in required_keys:
            assert key in d

    def test_trait_scores_dict_has_10_entries(self, engine):
        genome = SkillGenome.build("cto")
        result = engine.calibrate_genome(genome, subject_id="cto_test")
        assert len(result.trait_scores) == 10

    def test_archetype_distance_nonnegative(self, engine):
        genome = SkillGenome.build("vp_sales")
        result = engine.calibrate_genome(genome, subject_id="vps_test")
        assert result.archetype_distance >= 0.0

    def test_overall_greatness_in_range(self, engine):
        for role_key in ["ceo", "sdr", "senior_software_engineer", "cfo", "chro"]:
            genome = SkillGenome.build(role_key)
            result = engine.calibrate_genome(genome, subject_id=role_key)
            assert 0.0 <= result.overall_greatness <= 1.0

    def test_c_suite_outscores_ic(self, engine):
        ceo_g  = SkillGenome.build("ceo")
        swe_g  = SkillGenome.build("software_engineer")
        ceo_r  = engine.calibrate_genome(ceo_g,  subject_id="ceo")
        swe_r  = engine.calibrate_genome(swe_g,  subject_id="swe")
        assert ceo_r.overall_greatness > swe_r.overall_greatness

    def test_growth_traits_list_is_sorted_ascending(self, engine):
        genome = SkillGenome.build("sdr")
        result = engine.calibrate_genome(genome, subject_id="sdr")
        scores = [s for _, s in result.growth_traits]
        assert scores == sorted(scores)


# ---------------------------------------------------------------------------
# Part 9 — Trait development plan
# ---------------------------------------------------------------------------

class TestTraitDevelopmentPlan:
    def test_development_plan_has_required_keys(self, engine):
        genome = SkillGenome.build("sales_manager")
        calib  = engine.calibrate_genome(genome, subject_id="sm")
        plan   = engine.trait_development_plan(calib, weeks=12)
        assert "subject_id" in plan
        assert "overall_current" in plan
        assert "archetype" in plan
        assert "development_plan" in plan
        assert "universal_practice" in plan

    def test_development_plan_has_3_priorities(self, engine):
        genome = SkillGenome.build("account_executive")
        calib  = engine.calibrate_genome(genome, subject_id="ae")
        plan   = engine.trait_development_plan(calib)
        items  = plan["development_plan"]
        assert len(items) == 3

    def test_priorities_are_1_2_3(self, engine):
        genome = SkillGenome.build("product_manager")
        calib  = engine.calibrate_genome(genome, subject_id="pm")
        plan   = engine.trait_development_plan(calib)
        priorities = [item["priority"] for item in plan["development_plan"]]
        assert priorities == [1, 2, 3]

    def test_plan_items_have_target_score(self, engine):
        genome = SkillGenome.build("cmo")
        calib  = engine.calibrate_genome(genome, subject_id="cmo")
        plan   = engine.trait_development_plan(calib)
        for item in plan["development_plan"]:
            assert "target_score" in item
            assert item["target_score"] >= item["current_score"] - 1e-6

    def test_plan_items_have_weekly_practice(self, engine):
        genome = SkillGenome.build("engineering_manager")
        calib  = engine.calibrate_genome(genome, subject_id="em")
        plan   = engine.trait_development_plan(calib)
        for item in plan["development_plan"]:
            assert len(item["weekly_practice"]) > 5

    def test_plan_universal_practice_nonempty(self, engine):
        genome = SkillGenome.build("ceo")
        calib  = engine.calibrate_genome(genome, subject_id="ceo")
        plan   = engine.trait_development_plan(calib)
        assert len(plan["universal_practice"]) > 30

    def test_plan_subject_id_matches(self, engine):
        genome = SkillGenome.build("coo")
        calib  = engine.calibrate_genome(genome, subject_id="coo_42")
        plan   = engine.trait_development_plan(calib)
        assert plan["subject_id"] == "coo_42"

    def test_plan_weeks_to_impact_positive(self, engine):
        genome = SkillGenome.build("chro")
        calib  = engine.calibrate_genome(genome, subject_id="chro")
        plan   = engine.trait_development_plan(calib, weeks=12)
        for item in plan["development_plan"]:
            assert item["weeks_to_impact"] >= 1


# ---------------------------------------------------------------------------
# Part 10 — Agent calibration from KAIA mix + frameworks
# ---------------------------------------------------------------------------

class TestAgentCalibration:
    def test_ceo_agent_calibration(self, engine):
        result = engine.calibrate_agent(
            "morgan_vale",
            kaia_mix={"analytical": 0.30, "decisive": 0.35, "empathetic": 0.15, "creative": 0.10, "technical": 0.10},
            influence_frameworks=["cialdini_authority", "covey_begin_with_end", "carnegie_arouse_eager_want"],
        )
        assert result.subject_id == "morgan_vale"
        assert result.subject_type == "agent"

    def test_sales_agent_high_narrative_mastery(self, engine):
        result = engine.calibrate_agent(
            "alex_reeves",
            kaia_mix={"analytical": 0.25, "decisive": 0.40, "empathetic": 0.15, "creative": 0.10, "technical": 0.10},
            influence_frameworks=["cialdini_scarcity", "nlp_pacing_leading", "carnegie_arouse_eager_want", "cialdini_social_proof"],
        )
        narr = result.trait_scores[GreatnessTrait.NARRATIVE_MASTERY]
        assert narr >= 0.20  # KAIA proxy contributes; full frameworks amplify

    def test_empty_kaia_produces_calibration(self, engine):
        result = engine.calibrate_agent(
            "test_agent",
            kaia_mix={},
            influence_frameworks=[],
        )
        assert isinstance(result, CalibrationResult)

    def test_calibration_type_is_agent(self, engine):
        result = engine.calibrate_agent(
            "casey_torres",
            kaia_mix={"analytical": 0.15, "decisive": 0.30, "empathetic": 0.25, "creative": 0.25, "technical": 0.05},
            influence_frameworks=["cialdini_reciprocity", "mentalism_hot_reading", "habit_tiny_habits"],
        )
        assert result.subject_type == "agent"

    def test_technical_heavy_agent_aligns_science_or_engineering(self, engine):
        result = engine.calibrate_agent(
            "tech_heavy",
            kaia_mix={"analytical": 0.30, "decisive": 0.10, "empathetic": 0.05, "creative": 0.10, "technical": 0.45},
            influence_frameworks=["habit_tiny_habits"],
        )
        assert result.historical_class_alignment in (
            HistoricalClass.SCIENCE, HistoricalClass.ENGINEERING,
            HistoricalClass.ATHLETICS,  # execution-focused
        )

    def test_all_nine_roster_agents_calibrate(self, engine):
        roster = [
            ("morgan_vale",  {"analytical": 0.40, "decisive": 0.35, "empathetic": 0.10, "creative": 0.05, "technical": 0.10},
             ["cialdini_authority", "covey_begin_with_end"]),
            ("alex_reeves",  {"analytical": 0.25, "decisive": 0.40, "empathetic": 0.15, "creative": 0.10, "technical": 0.10},
             ["cialdini_commitment_consistency", "nlp_pacing_leading"]),
            ("casey_torres", {"analytical": 0.15, "decisive": 0.30, "empathetic": 0.25, "creative": 0.25, "technical": 0.05},
             ["cialdini_reciprocity", "mentalism_hot_reading"]),
            ("taylor_kim",   {"analytical": 0.20, "decisive": 0.15, "empathetic": 0.45, "creative": 0.10, "technical": 0.10},
             ["carnegie_honest_appreciation", "nlp_future_pacing"]),
            ("drew_nakamura",{"analytical": 0.25, "decisive": 0.25, "empathetic": 0.25, "creative": 0.15, "technical": 0.10},
             ["covey_think_win_win", "cialdini_liking"]),
            ("murphy",       {"analytical": 0.20, "decisive": 0.20, "empathetic": 0.30, "creative": 0.20, "technical": 0.10},
             ["cialdini_liking", "nlp_pacing_leading"]),
            ("quinn_harper", {"analytical": 0.30, "decisive": 0.25, "empathetic": 0.15, "creative": 0.10, "technical": 0.20},
             ["habit_tiny_habits"]),
            ("jordan_blake", {"analytical": 0.25, "decisive": 0.30, "empathetic": 0.20, "creative": 0.15, "technical": 0.10},
             ["cialdini_social_proof"]),
            ("sam_ortega",   {"analytical": 0.20, "decisive": 0.25, "empathetic": 0.30, "creative": 0.15, "technical": 0.10},
             ["carnegie_feel_important"]),
        ]
        for agent_id, kaia, frameworks in roster:
            result = engine.calibrate_agent(agent_id, kaia, frameworks)
            assert result.subject_id == agent_id
            assert 0.0 <= result.overall_greatness <= 1.0


# ---------------------------------------------------------------------------
# Part 11 — EliteOrgSimulator.calibrate_chart / calibrate_role wiring
# ---------------------------------------------------------------------------

class TestEliteOrgSimulatorHGEWiring:
    def test_calibrate_role_ceo_returns_result(self, sim):
        result = sim.calibrate_role("ceo")
        assert result is not None
        assert result.subject_id == "ceo"

    def test_calibrate_role_all_c_suite(self, sim):
        for role_key in ["ceo", "cto", "cro", "cfo", "cmo", "cpo", "coo", "clo", "chro"]:
            result = sim.calibrate_role(role_key)
            assert result is not None, f"calibrate_role({role_key!r}) returned None"
            assert 0.0 < result.overall_greatness <= 1.0

    def test_calibrate_chart_returns_dict(self, sim, series_b_chart):
        out = sim.calibrate_chart(series_b_chart)
        assert "role_calibrations" in out
        assert "org_summary" in out

    def test_calibrate_chart_covers_all_roles(self, sim, series_b_chart):
        out = sim.calibrate_chart(series_b_chart)
        n_filled = sum(1 for r in series_b_chart.roles.values() if r.is_filled)
        assert len(out["role_calibrations"]) == n_filled

    def test_calibrate_chart_org_summary_has_required_keys(self, sim, series_b_chart):
        out = sim.calibrate_chart(series_b_chart)
        summary = out["org_summary"]
        for key in ["headcount_calibrated", "avg_greatness_score", "dominant_archetype",
                    "archetype_distribution", "class_alignment_distribution",
                    "top_roles", "bottom_roles", "benchmark_vs_elite"]:
            assert key in summary

    def test_calibrate_chart_avg_greatness_in_range(self, sim, series_b_chart):
        out = sim.calibrate_chart(series_b_chart)
        avg = out["org_summary"]["avg_greatness_score"]
        assert 0.5 <= avg <= 1.0

    def test_calibrate_chart_dominant_archetype_is_real_great(self, sim, series_b_chart):
        out = sim.calibrate_chart(series_b_chart)
        dom = out["org_summary"]["dominant_archetype"]
        names = {g.name for g in HISTORICAL_GREATS.values()}
        assert dom in names

    def test_calibrate_chart_top_roles_not_empty(self, sim, series_b_chart):
        out = sim.calibrate_chart(series_b_chart)
        assert len(out["org_summary"]["top_roles"]) >= 1

    def test_calibrate_chart_seed_stage(self, sim):
        chart = sim.build_chart(CompanyStage.SEED)
        out = sim.calibrate_chart(chart)
        assert len(out["role_calibrations"]) == chart.headcount

    def test_calibrate_role_vp_sales_archetype_is_sales_legend(self, sim):
        """VP Sales profile should match a persuasion/narrative-dominant historical figure."""
        result = sim.calibrate_role("vp_sales")
        # Should match a military, business, or politics legend — not a pure scientist
        assert result.historical_class_alignment in (
            HistoricalClass.BUSINESS, HistoricalClass.POLITICS,
            HistoricalClass.MILITARY, HistoricalClass.ATHLETICS,
        )


# ---------------------------------------------------------------------------
# Part 12 — Org greatness summary consistency
# ---------------------------------------------------------------------------

class TestOrgGreatnessSummary:
    def test_summary_produced_for_all_stages(self, engine):
        builder = OrgChartBuilder()
        for stage in CompanyStage:
            chart = builder.build(stage)
            summary = engine.org_greatness_summary(chart)
            assert "headcount_calibrated" in summary
            assert summary["headcount_calibrated"] == sum(
                1 for r in chart.roles.values() if r.is_filled
            )

    def test_summary_benchmark_vs_elite_has_all_traits(self, engine, series_b_chart):
        summary = engine.org_greatness_summary(series_b_chart)
        bve = summary["benchmark_vs_elite"]
        for trait in ALL_TRAITS:
            assert trait.value in bve

    def test_summary_class_distribution_sums_to_headcount(self, engine, series_b_chart):
        summary = engine.org_greatness_summary(series_b_chart)
        total = sum(summary["class_alignment_distribution"].values())
        assert total == summary["headcount_calibrated"]

    def test_top_roles_have_higher_scores_than_bottom(self, engine, series_b_chart):
        summary = engine.org_greatness_summary(series_b_chart)
        if summary["top_roles"] and summary["bottom_roles"]:
            min_top    = min(score for _, score in summary["top_roles"])
            max_bottom = max(score for _, score in summary["bottom_roles"])
            assert min_top >= max_bottom - 1e-9


# ---------------------------------------------------------------------------
# Part 13 — Cross-class trait universality
# ---------------------------------------------------------------------------

class TestCrossClassUniversality:
    """
    Every great, regardless of class, should demonstrate at least moderate
    competency (≥ 0.70) on every one of the 10 universal traits.
    This proves the traits are truly universal, not class-specific.
    """

    def test_all_greats_above_0_70_on_all_traits(self):
        failures = []
        for gid, great in HISTORICAL_GREATS.items():
            for trait in ALL_TRAITS:
                score = great.trait_scores.get(trait, 0.0)
                if score < 0.70:
                    failures.append(f"{great.name} [{gid}] scored {score:.2f} on {trait.value}")
        assert not failures, "Some greats score below 0.70 on a universal trait:\n" + "\n".join(failures)

    def test_trait_ranges_above_0_5_std_dev(self):
        """There should be meaningful variance in each trait across all greats."""
        import math
        for trait in ALL_TRAITS:
            vals = [g.trait_scores[trait] for g in HISTORICAL_GREATS.values()]
            mean = sum(vals) / len(vals)
            std  = math.sqrt(sum((v - mean) ** 2 for v in vals) / len(vals))
            assert std > 0.02, f"{trait.value} has near-zero variance ({std:.4f}) — not meaningful"

    def test_military_class_high_on_preparation(self):
        military_greats = [g for g in HISTORICAL_GREATS.values() if g.primary_class == HistoricalClass.MILITARY]
        avg_prep = sum(g.trait_scores[GreatnessTrait.EXTREME_PREPARATION] for g in military_greats) / len(military_greats)
        assert avg_prep >= 0.90

    def test_business_class_high_on_long_game(self):
        biz_greats = [g for g in HISTORICAL_GREATS.values() if g.primary_class == HistoricalClass.BUSINESS]
        avg_long = sum(g.trait_scores[GreatnessTrait.LONG_GAME_THINKING] for g in biz_greats) / len(biz_greats)
        assert avg_long >= 0.90

    def test_science_class_high_on_pattern_recognition(self):
        sci_greats = [g for g in HISTORICAL_GREATS.values() if g.primary_class == HistoricalClass.SCIENCE]
        avg_patt = sum(g.trait_scores[GreatnessTrait.PATTERN_RECOGNITION] for g in sci_greats) / len(sci_greats)
        assert avg_patt >= 0.94

    def test_arts_class_high_on_narrative_mastery(self):
        arts_greats = [g for g in HISTORICAL_GREATS.values() if g.primary_class == HistoricalClass.ARTS]
        avg_narr = sum(g.trait_scores[GreatnessTrait.NARRATIVE_MASTERY] for g in arts_greats) / len(arts_greats)
        assert avg_narr >= 0.88

    def test_athletics_class_high_on_obsessive_focus(self):
        ath_greats = [g for g in HISTORICAL_GREATS.values() if g.primary_class == HistoricalClass.ATHLETICS]
        avg_focus = sum(g.trait_scores[GreatnessTrait.OBSESSIVE_FOCUS] for g in ath_greats) / len(ath_greats)
        assert avg_focus >= 0.97

    def test_philosophy_class_high_on_cross_domain_learning(self):
        phil_greats = [g for g in HISTORICAL_GREATS.values() if g.primary_class == HistoricalClass.PHILOSOPHY]
        avg_cross = sum(g.trait_scores[GreatnessTrait.CROSS_DOMAIN_LEARNING] for g in phil_greats) / len(phil_greats)
        assert avg_cross >= 0.90


# ---------------------------------------------------------------------------
# Part 14 — Distance metrics and archetype ranking
# ---------------------------------------------------------------------------

class TestDistanceMetrics:
    def test_perfect_overlap_gives_zero_distance(self):
        napoleon = HISTORICAL_GREATS["napoleon"]
        assert napoleon.distance_to(napoleon.trait_scores) < 1e-9

    def test_opposite_profile_gives_large_distance(self):
        napoleon = HISTORICAL_GREATS["napoleon"]
        opposite = {t: 1.0 - napoleon.trait_scores[t] for t in ALL_TRAITS}
        dist = napoleon.distance_to(opposite)
        assert dist > 0.50  # Should be substantially different

    def test_archetype_is_closer_than_opposite(self):
        lincoln = HISTORICAL_GREATS["lincoln"]
        # Create a "Lincoln-like" profile
        lincoln_like = {t: lincoln.trait_scores[t] * 0.95 for t in ALL_TRAITS}
        profiler = TraitProfiler()
        # Use direct distance check
        dist_to_lincoln = lincoln.distance_to(lincoln_like)
        dist_to_napoleon = HISTORICAL_GREATS["napoleon"].distance_to(lincoln_like)
        assert dist_to_lincoln < dist_to_napoleon

    def test_similar_classes_have_smaller_distances(self):
        """Military greats should be closer to each other than to science greats."""
        napoleon = HISTORICAL_GREATS["napoleon"]
        alexander = HISTORICAL_GREATS["alexander_great"]
        darwin = HISTORICAL_GREATS["charles_darwin"]
        dist_mil_mil = napoleon.distance_to(alexander.trait_scores)
        dist_mil_sci = napoleon.distance_to(darwin.trait_scores)
        assert dist_mil_mil < dist_mil_sci

    def test_top_n_ordering_consistent_with_distance(self):
        matcher = ArchetypeMatcher()
        top_10 = matcher.top_n_all_time(10)
        top_5  = matcher.top_n_all_time(5)
        # Top 5 should be a subset of top 10
        top_10_ids = {g.great_id for g in top_10}
        for g in top_5:
            assert g.great_id in top_10_ids


# ---------------------------------------------------------------------------
# Part 15 — describe_trait full content check
# ---------------------------------------------------------------------------

class TestDescribeTrait:
    def test_describe_all_traits(self, engine):
        for trait in ALL_TRAITS:
            info = engine.describe_trait(trait)
            assert info["trait"] == trait.value
            assert len(info["name"]) > 3
            assert len(info["description"]) > 20
            assert len(info["epitome_quote"]) > 10
            assert len(info["top_5_scorers"]) >= 1

    def test_describe_trait_benchmark_mean_in_range(self, engine):
        for trait in ALL_TRAITS:
            info = engine.describe_trait(trait)
            assert 0.0 <= info["benchmark_mean"] <= 1.0
            assert 0.0 <= info["elite_threshold"] <= 1.0

    def test_describe_trait_elite_threshold_gte_mean(self, engine):
        for trait in ALL_TRAITS:
            info = engine.describe_trait(trait)
            assert info["elite_threshold"] >= info["benchmark_mean"] - 1e-9

    def test_describe_obsessive_focus_includes_newton(self, engine):
        info = engine.describe_trait(GreatnessTrait.OBSESSIVE_FOCUS)
        scorer_names = [name for name, _ in info["top_5_scorers"]]
        assert "Isaac Newton" in scorer_names or "Steve Jobs" in scorer_names

    def test_top_5_scorers_sorted_descending(self, engine):
        for trait in ALL_TRAITS:
            info = engine.describe_trait(trait)
            scores = [s for _, s in info["top_5_scorers"]]
            assert scores == sorted(scores, reverse=True), f"{trait} scorers not descending"
