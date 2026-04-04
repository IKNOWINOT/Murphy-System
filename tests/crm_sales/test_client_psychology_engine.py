"""
Tests for client_psychology_engine.py — Round 58

Covers:
  Part 1  — Enum completeness and values
  Part 2  — DemographicProfile construction and defaults
  Part 3  — PainIntensity urgency scores
  Part 4  — LanguagePack completeness for all generations
  Part 5  — Modern lingo is present in every language pack
  Part 6  — PainPointDetector — signal detection and ranking
  Part 7  — PainPointDetector — probe retrieval
  Part 8  — DemographicAdapter — get_language_pack
  Part 9  — DemographicAdapter — infer_profile_from_signals
  Part 10 — IncomeScalingPlaybook completeness and validity
  Part 11 — IncomeScalingEngine — get_playbook and recommend_multiplier
  Part 12 — FrameworkGuide completeness
  Part 13 — FrameworkSelector — correct framework selection
  Part 14 — ClientPsychologyEngine.read_client — full report
  Part 15 — ClientPsychologyEngine — language packs and framework guides
  Part 16 — ClientReadingReport serialisation
  Part 17 — Thread safety / recent_readings
"""

import sys
import os
import threading

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from client_psychology_engine import (
    GenerationCohort, IndustryVertical, DecisionMakerRole,
    CommunicationStyle, PainCategory, PainIntensity, SalesFramework,
    IncomeMultiplier,
    DemographicProfile, PainSignal, LanguagePack,
    IncomeScalingPlaybook, FrameworkGuide, ClientReadingReport,
    LANGUAGE_PACKS, PAIN_SIGNAL_LIBRARY, INCOME_SCALING_PLAYBOOKS,
    FRAMEWORK_GUIDES,
    PainPointDetector, DemographicAdapter, IncomeScalingEngine,
    FrameworkSelector, ClientPsychologyEngine,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def engine():
    return ClientPsychologyEngine()


@pytest.fixture
def gen_x_profile():
    return DemographicProfile(
        generation=GenerationCohort.GEN_X,
        industry=IndustryVertical.TECHNOLOGY,
        role=DecisionMakerRole.ECONOMIC_BUYER,
        formality_preference=0.55,
    )


@pytest.fixture
def gen_z_profile():
    return DemographicProfile(
        generation=GenerationCohort.GEN_Z,
        industry=IndustryVertical.TECHNOLOGY,
        role=DecisionMakerRole.CHAMPION,
    )


@pytest.fixture
def boomer_profile():
    return DemographicProfile(
        generation=GenerationCohort.BOOMER,
        industry=IndustryVertical.FINANCE,
        role=DecisionMakerRole.ECONOMIC_BUYER,
        formality_preference=0.80,
        relationship_dependency=0.85,
    )


@pytest.fixture
def detector():
    return PainPointDetector()


@pytest.fixture
def adapter():
    return DemographicAdapter()


@pytest.fixture
def scaler():
    return IncomeScalingEngine()


@pytest.fixture
def selector():
    return FrameworkSelector()


# ---------------------------------------------------------------------------
# Part 1 — Enum completeness and values
# ---------------------------------------------------------------------------

class TestEnums:
    def test_generation_cohort_count(self):
        assert len(GenerationCohort) == 5

    def test_generation_cohort_values(self):
        values = {g.value for g in GenerationCohort}
        assert "gen_z" in values
        assert "millennial" in values
        assert "gen_x" in values
        assert "boomer" in values
        assert "silent" in values

    def test_industry_vertical_count(self):
        assert len(IndustryVertical) == 12

    def test_decision_maker_roles(self):
        roles = {r.value for r in DecisionMakerRole}
        assert "economic_buyer" in roles
        assert "technical_buyer" in roles
        assert "champion" in roles
        assert "blocker" in roles

    def test_pain_categories_count(self):
        assert len(PainCategory) == 9

    def test_pain_intensity_count(self):
        assert len(PainIntensity) == 4

    def test_sales_framework_count(self):
        assert len(SalesFramework) == 8

    def test_income_multiplier_count(self):
        assert len(IncomeMultiplier) == 4

    def test_income_multiplier_numeric(self):
        assert IncomeMultiplier.TWO_X.numeric == 2
        assert IncomeMultiplier.THREE_X.numeric == 3
        assert IncomeMultiplier.FOUR_X.numeric == 4
        assert IncomeMultiplier.FIVE_X.numeric == 5


# ---------------------------------------------------------------------------
# Part 2 — DemographicProfile construction
# ---------------------------------------------------------------------------

class TestDemographicProfile:
    def test_basic_construction(self, gen_x_profile):
        assert gen_x_profile.generation == GenerationCohort.GEN_X
        assert gen_x_profile.industry == IndustryVertical.TECHNOLOGY
        assert gen_x_profile.role == DecisionMakerRole.ECONOMIC_BUYER

    def test_default_values(self):
        p = DemographicProfile(
            generation=GenerationCohort.MILLENNIAL,
            industry=IndustryVertical.HEALTHCARE,
            role=DecisionMakerRole.CHAMPION,
        )
        assert 0.0 <= p.tech_savviness <= 1.0
        assert 0.0 <= p.formality_preference <= 1.0
        assert 0.0 <= p.relationship_dependency <= 1.0
        assert 0.0 <= p.decision_speed <= 1.0

    def test_to_dict_keys(self, gen_x_profile):
        d = gen_x_profile.to_dict()
        assert "generation" in d
        assert "industry" in d
        assert "role" in d
        assert "tech_savviness" in d
        assert "formality_preference" in d

    def test_to_dict_values_are_strings(self, gen_x_profile):
        d = gen_x_profile.to_dict()
        assert d["generation"] == "gen_x"
        assert d["industry"] == "technology"


# ---------------------------------------------------------------------------
# Part 3 — PainIntensity urgency scores
# ---------------------------------------------------------------------------

class TestPainIntensity:
    def test_urgency_ordering(self):
        assert PainIntensity.LATENT.urgency_score < PainIntensity.ACKNOWLEDGED.urgency_score
        assert PainIntensity.ACKNOWLEDGED.urgency_score < PainIntensity.ACTIVE.urgency_score
        assert PainIntensity.ACTIVE.urgency_score < PainIntensity.CRITICAL.urgency_score

    def test_critical_is_max(self):
        assert PainIntensity.CRITICAL.urgency_score == 1.0

    def test_latent_is_min(self):
        assert PainIntensity.LATENT.urgency_score == 0.25


# ---------------------------------------------------------------------------
# Part 4 — LanguagePack completeness
# ---------------------------------------------------------------------------

class TestLanguagePacks:
    def test_all_generations_have_packs(self):
        for gen in GenerationCohort:
            assert gen in LANGUAGE_PACKS, f"Missing language pack for {gen}"

    def test_pack_has_required_fields(self):
        for gen, pack in LANGUAGE_PACKS.items():
            assert pack.generation == gen
            assert len(pack.power_words) >= 5
            assert len(pack.avoid_words) >= 3
            assert len(pack.trust_signals) >= 3
            assert len(pack.value_anchors) >= 3
            assert len(pack.opening_hooks) >= 1
            assert pack.preferred_format

    def test_pack_to_dict(self):
        pack = LANGUAGE_PACKS[GenerationCohort.GEN_X]
        d = pack.to_dict()
        assert d["generation"] == "gen_x"
        assert isinstance(d["power_words"], list)
        assert isinstance(d["avoid_words"], list)


# ---------------------------------------------------------------------------
# Part 5 — Modern lingo in every language pack
# ---------------------------------------------------------------------------

class TestModernLingo:
    def test_all_packs_have_modern_lingo(self):
        for gen, pack in LANGUAGE_PACKS.items():
            assert len(pack.modern_lingo) >= 3, f"{gen} missing modern lingo"

    def test_gen_z_has_icp_or_north_star(self):
        pack = LANGUAGE_PACKS[GenerationCohort.GEN_Z]
        all_lingo = " ".join(pack.modern_lingo).lower()
        assert "icp" in all_lingo or "north star" in all_lingo or "value" in all_lingo

    def test_millennial_has_gtm_or_nrr(self):
        pack = LANGUAGE_PACKS[GenerationCohort.MILLENNIAL]
        all_lingo = " ".join(pack.modern_lingo).lower()
        assert any(kw in all_lingo for kw in ("gtm", "nrr", "land", "expand", "retention"))

    def test_gen_x_has_ebitda_or_tco(self):
        pack = LANGUAGE_PACKS[GenerationCohort.GEN_X]
        all_lingo = " ".join(pack.modern_lingo).lower()
        assert any(kw in all_lingo for kw in ("ebitda", "tco", "efficiency", "operating"))

    def test_boomer_has_enterprise_terms(self):
        pack = LANGUAGE_PACKS[GenerationCohort.BOOMER]
        all_lingo = " ".join(pack.modern_lingo).lower()
        assert any(kw in all_lingo for kw in ("enterprise", "strategic", "executive", "board"))


# ---------------------------------------------------------------------------
# Part 6 — PainPointDetector
# ---------------------------------------------------------------------------

class TestPainPointDetector:
    def test_detects_revenue_pain(self, detector):
        signals = ["We are leaving money on the table every quarter"]
        results = detector.detect(signals)
        assert len(results) >= 1
        cats = {r.category for r in results}
        assert PainCategory.REVENUE_GROWTH in cats

    def test_detects_competitive_threat(self, detector):
        signals = ["Our competitors are moving faster and we are losing market share"]
        results = detector.detect(signals)
        assert len(results) >= 1
        cats = {r.category for r in results}
        assert PainCategory.COMPETITIVE_THREAT in cats

    def test_detects_talent_pain(self, detector):
        signals = ["We keep losing our best people to better offers elsewhere"]
        results = detector.detect(signals)
        assert len(results) >= 1
        cats = {r.category for r in results}
        assert PainCategory.TALENT_RETENTION in cats

    def test_results_sorted_by_urgency(self, detector):
        signals = [
            "competitors moving faster",
            "doing this manually still",
        ]
        results = detector.detect(signals)
        if len(results) >= 2:
            assert results[0].urgency_score >= results[1].urgency_score

    def test_primary_pain_returns_highest_urgency(self, detector):
        signals = ["We keep losing our best people", "doing this manually"]
        results = detector.detect(signals)
        primary = detector.primary_pain(results)
        if results:
            assert primary == results[0]

    def test_primary_pain_none_on_empty(self, detector):
        assert detector.primary_pain([]) is None

    def test_no_false_positives_on_empty_text(self, detector):
        results = detector.detect([""])
        assert isinstance(results, list)

    def test_get_probes_returns_list(self, detector):
        probes = detector.get_probes(PainCategory.REVENUE_GROWTH)
        assert isinstance(probes, list)
        assert len(probes) >= 1


# ---------------------------------------------------------------------------
# Part 7 — PAIN_SIGNAL_LIBRARY integrity
# ---------------------------------------------------------------------------

class TestPainSignalLibrary:
    def test_library_has_entries(self):
        assert len(PAIN_SIGNAL_LIBRARY) >= 15

    def test_all_categories_represented(self):
        cats = {s.category for s in PAIN_SIGNAL_LIBRARY}
        for cat in PainCategory:
            assert cat in cats, f"Missing pain category: {cat}"

    def test_signal_to_dict(self):
        signal = PAIN_SIGNAL_LIBRARY[0]
        d = signal.to_dict()
        assert "category" in d
        assert "intensity" in d
        assert "urgency_score" in d
        assert "trigger_phrase" in d
        assert "recommended_probe" in d

    def test_urgency_scores_valid(self):
        for sig in PAIN_SIGNAL_LIBRARY:
            assert 0.0 < sig.urgency_score <= 1.0


# ---------------------------------------------------------------------------
# Part 8 — DemographicAdapter
# ---------------------------------------------------------------------------

class TestDemographicAdapter:
    def test_get_language_pack_returns_correct_gen(self, adapter, gen_x_profile):
        pack = adapter.get_language_pack(gen_x_profile)
        assert pack.generation == GenerationCohort.GEN_X

    def test_adapt_message_returns_string(self, adapter, gen_x_profile):
        result = adapter.adapt_message("Here is our solution.", gen_x_profile)
        assert isinstance(result, str)
        assert len(result) > 10

    def test_adapt_message_includes_hook(self, adapter, gen_x_profile):
        pack = adapter.get_language_pack(gen_x_profile)
        hook_fragment = pack.opening_hooks[0][:20]
        result = adapter.adapt_message("Test message", gen_x_profile)
        assert hook_fragment in result

    def test_adapt_for_all_generations(self, adapter):
        for gen in GenerationCohort:
            profile = DemographicProfile(
                generation=gen,
                industry=IndustryVertical.TECHNOLOGY,
                role=DecisionMakerRole.ECONOMIC_BUYER,
            )
            result = adapter.adapt_message("Our solution helps you.", profile)
            assert isinstance(result, str)


# ---------------------------------------------------------------------------
# Part 9 — DemographicAdapter.infer_profile_from_signals
# ---------------------------------------------------------------------------

class TestDemographicAdapterInference:
    def test_infers_gen_x_from_roi_language(self, adapter):
        signals = ["What is the ROI?", "Show me the bottom line"]
        profile = adapter.infer_profile_from_signals(signals)
        assert profile.generation == GenerationCohort.GEN_X

    def test_infers_gen_z_from_values_language(self, adapter):
        signals = ["We want authentic impact", "transparency matters to us", "values-driven culture"]
        profile = adapter.infer_profile_from_signals(signals)
        assert profile.generation == GenerationCohort.GEN_Z

    def test_infers_boomer_from_trusted_partner(self, adapter):
        signals = ["We need a trusted partner", "long-term relationship is important"]
        profile = adapter.infer_profile_from_signals(signals)
        assert profile.generation == GenerationCohort.BOOMER

    def test_infers_technical_buyer_from_cto(self, adapter):
        signals = ["I am the CTO", "our engineer and architect need to approve"]
        profile = adapter.infer_profile_from_signals(signals)
        assert profile.role == DecisionMakerRole.TECHNICAL_BUYER

    def test_infers_economic_buyer_from_ceo(self, adapter):
        signals = ["I am the CEO and the board will review"]
        profile = adapter.infer_profile_from_signals(signals)
        assert profile.role == DecisionMakerRole.ECONOMIC_BUYER

    def test_returns_profile_object(self, adapter):
        profile = adapter.infer_profile_from_signals(["some signal"])
        assert isinstance(profile, DemographicProfile)


# ---------------------------------------------------------------------------
# Part 10 — IncomeScalingPlaybook completeness
# ---------------------------------------------------------------------------

class TestIncomeScalingPlaybooks:
    def test_all_multipliers_have_playbooks(self):
        for m in IncomeMultiplier:
            assert m in INCOME_SCALING_PLAYBOOKS

    def test_playbooks_have_required_fields(self):
        for m, pb in INCOME_SCALING_PLAYBOOKS.items():
            assert pb.multiplier == m
            assert pb.strategy_name
            assert pb.thesis
            assert len(pb.preconditions) >= 3
            assert len(pb.primary_tactics) >= 3
            assert len(pb.agent_behaviors) >= 2
            assert len(pb.risk_factors) >= 2
            assert len(pb.success_metrics) >= 3
            assert pb.timeline_weeks > 0

    def test_timeline_increases_with_multiplier(self):
        pb2 = INCOME_SCALING_PLAYBOOKS[IncomeMultiplier.TWO_X]
        pb3 = INCOME_SCALING_PLAYBOOKS[IncomeMultiplier.THREE_X]
        pb4 = INCOME_SCALING_PLAYBOOKS[IncomeMultiplier.FOUR_X]
        pb5 = INCOME_SCALING_PLAYBOOKS[IncomeMultiplier.FIVE_X]
        assert pb2.timeline_weeks < pb3.timeline_weeks < pb4.timeline_weeks < pb5.timeline_weeks

    def test_to_dict_structure(self):
        pb = INCOME_SCALING_PLAYBOOKS[IncomeMultiplier.TWO_X]
        d = pb.to_dict()
        assert d["multiplier"] == "2x"
        assert isinstance(d["primary_tactics"], list)
        assert isinstance(d["success_metrics"], list)


# ---------------------------------------------------------------------------
# Part 11 — IncomeScalingEngine
# ---------------------------------------------------------------------------

class TestIncomeScalingEngine:
    def test_get_playbook_for_all_multipliers(self, scaler):
        for m in IncomeMultiplier:
            pb = scaler.get_playbook(m)
            assert pb.multiplier == m

    def test_all_playbooks_returns_four(self, scaler):
        assert len(scaler.all_playbooks()) == 4

    def test_recommend_returns_valid_multiplier(self, scaler, gen_x_profile):
        pain = [PAIN_SIGNAL_LIBRARY[0]]
        result = scaler.recommend_multiplier(gen_x_profile, pain)
        assert isinstance(result, IncomeMultiplier)

    def test_digital_plus_innovation_recommends_5x(self, scaler):
        profile = DemographicProfile(
            generation=GenerationCohort.MILLENNIAL,
            industry=IndustryVertical.TECHNOLOGY,
            role=DecisionMakerRole.ECONOMIC_BUYER,
        )
        digital_pain = next(s for s in PAIN_SIGNAL_LIBRARY if s.category == PainCategory.DIGITAL_TRANSFORMATION)
        innov_pain   = next(s for s in PAIN_SIGNAL_LIBRARY if s.category == PainCategory.INNOVATION_PRESSURE)
        result = scaler.recommend_multiplier(profile, [digital_pain, innov_pain])
        assert result == IncomeMultiplier.FIVE_X

    def test_two_growth_pains_recommends_3x(self, scaler):
        profile = DemographicProfile(
            generation=GenerationCohort.GEN_X,
            industry=IndustryVertical.TECHNOLOGY,
            role=DecisionMakerRole.ECONOMIC_BUYER,
        )
        rev_pain  = next(s for s in PAIN_SIGNAL_LIBRARY if s.category == PainCategory.REVENUE_GROWTH)
        eff_pain  = next(s for s in PAIN_SIGNAL_LIBRARY if s.category == PainCategory.EFFICIENCY)
        result = scaler.recommend_multiplier(profile, [rev_pain, eff_pain])
        assert result == IncomeMultiplier.THREE_X


# ---------------------------------------------------------------------------
# Part 12 — FrameworkGuide completeness
# ---------------------------------------------------------------------------

class TestFrameworkGuides:
    def test_all_frameworks_have_guides(self):
        for fw in SalesFramework:
            assert fw in FRAMEWORK_GUIDES

    def test_guides_have_required_fields(self):
        for fw, guide in FRAMEWORK_GUIDES.items():
            assert guide.framework == fw
            assert guide.full_name
            assert len(guide.best_for) >= 2
            assert guide.opening_move
            assert len(guide.key_questions) >= 3
            assert guide.closing_technique
            assert guide.objection_handler
            assert guide.modern_twist

    def test_to_dict_structure(self):
        guide = FRAMEWORK_GUIDES[SalesFramework.MEDDIC]
        d = guide.to_dict()
        assert d["framework"] == "meddic"
        assert isinstance(d["key_questions"], list)
        assert isinstance(d["best_for"], list)


# ---------------------------------------------------------------------------
# Part 13 — FrameworkSelector
# ---------------------------------------------------------------------------

class TestFrameworkSelector:
    def test_busy_csuite_gets_snap(self, selector):
        profile = DemographicProfile(
            generation=GenerationCohort.MILLENNIAL,
            industry=IndustryVertical.TECHNOLOGY,
            role=DecisionMakerRole.ECONOMIC_BUYER,
            decision_speed=0.90,
            formality_preference=0.20,
        )
        fw = selector.select(profile, [])
        assert fw == SalesFramework.SNAP_SELLING

    def test_enterprise_economic_buyer_gets_meddic(self, selector):
        profile = DemographicProfile(
            generation=GenerationCohort.BOOMER,
            industry=IndustryVertical.FINANCE,
            role=DecisionMakerRole.ECONOMIC_BUYER,
            formality_preference=0.85,
        )
        fw = selector.select(profile, [])
        assert fw == SalesFramework.MEDDIC

    def test_competitive_threat_gets_challenger(self, selector):
        profile = DemographicProfile(
            generation=GenerationCohort.GEN_X,
            industry=IndustryVertical.TECHNOLOGY,
            role=DecisionMakerRole.CHAMPION,
        )
        comp_pain = next(s for s in PAIN_SIGNAL_LIBRARY if s.category == PainCategory.COMPETITIVE_THREAT)
        fw = selector.select(profile, [comp_pain])
        assert fw == SalesFramework.CHALLENGER

    def test_boomer_gets_consultative(self, selector, boomer_profile):
        fw = selector.select(boomer_profile, [])
        assert fw == SalesFramework.CONSULTATIVE

    def test_technical_buyer_gets_spin(self, selector):
        profile = DemographicProfile(
            generation=GenerationCohort.MILLENNIAL,
            industry=IndustryVertical.TECHNOLOGY,
            role=DecisionMakerRole.TECHNICAL_BUYER,
        )
        fw = selector.select(profile, [])
        assert fw == SalesFramework.SPIN_MODERN

    def test_get_guide_returns_correct(self, selector):
        guide = selector.get_guide(SalesFramework.GAP_SELLING)
        assert guide.framework == SalesFramework.GAP_SELLING

    def test_all_guides_returns_eight(self, selector):
        assert len(selector.all_guides()) == 8


# ---------------------------------------------------------------------------
# Part 14 — ClientPsychologyEngine.read_client
# ---------------------------------------------------------------------------

class TestClientPsychologyEngineReadClient:
    def test_returns_report_object(self, engine, gen_x_profile):
        r = engine.read_client(
            "test_001",
            ["leaving money on the table"],
            {"generation": GenerationCohort.GEN_X,
             "industry": IndustryVertical.TECHNOLOGY,
             "role": DecisionMakerRole.ECONOMIC_BUYER},
        )
        assert isinstance(r, ClientReadingReport)

    def test_report_has_all_required_fields(self, engine):
        r = engine.read_client(
            "test_002",
            ["competitors moving faster", "board wants more growth"],
        )
        assert r.client_id == "test_002"
        assert isinstance(r.demographic_profile, DemographicProfile)
        assert isinstance(r.detected_pain_signals, list)
        assert isinstance(r.recommended_framework, SalesFramework)
        assert isinstance(r.income_scaling_lever, IncomeMultiplier)
        assert isinstance(r.language_pack, LanguagePack)
        assert r.opening_gambit
        assert isinstance(r.key_discovery_questions, list)
        assert isinstance(r.objection_preemptions, list)
        assert r.closing_approach
        assert r.urgency_narrative

    def test_report_detects_pain_from_signals(self, engine):
        r = engine.read_client(
            "test_003",
            ["we keep losing our best people", "burn rate too high", "competitors moving faster"],
            {"generation": GenerationCohort.MILLENNIAL,
             "industry": IndustryVertical.TECHNOLOGY,
             "role": DecisionMakerRole.ECONOMIC_BUYER},
        )
        assert len(r.detected_pain_signals) >= 2

    def test_infers_profile_when_no_hints(self, engine):
        r = engine.read_client(
            "test_004",
            ["ROI is critical", "bottom line matters most to us"],
        )
        assert isinstance(r.demographic_profile, DemographicProfile)

    def test_primary_pain_is_highest_urgency(self, engine):
        r = engine.read_client(
            "test_005",
            ["burn rate too high", "doing this manually"],
            {"generation": GenerationCohort.GEN_X,
             "industry": IndustryVertical.TECHNOLOGY,
             "role": DecisionMakerRole.ECONOMIC_BUYER},
        )
        if r.primary_pain and len(r.detected_pain_signals) > 1:
            assert r.primary_pain.urgency_score >= r.detected_pain_signals[1].urgency_score

    def test_objection_preemptions_are_non_empty(self, engine):
        r = engine.read_client("test_006", ["audit findings piling up"])
        assert len(r.objection_preemptions) >= 1

    def test_discovery_questions_non_empty(self, engine):
        r = engine.read_client("test_007", ["legacy systems", "tech stack holding us back"])
        assert len(r.key_discovery_questions) >= 1


# ---------------------------------------------------------------------------
# Part 15 — ClientPsychologyEngine convenience methods
# ---------------------------------------------------------------------------

class TestClientPsychologyEngineConvenience:
    def test_get_language_pack(self, engine):
        pack = engine.get_language_pack(GenerationCohort.MILLENNIAL)
        assert pack.generation == GenerationCohort.MILLENNIAL

    def test_get_scaling_playbook(self, engine):
        pb = engine.get_scaling_playbook(IncomeMultiplier.THREE_X)
        assert pb.multiplier == IncomeMultiplier.THREE_X

    def test_describe_framework(self, engine):
        guide = engine.describe_framework(SalesFramework.CHALLENGER)
        assert guide.framework == SalesFramework.CHALLENGER

    def test_all_language_packs_count(self, engine):
        assert len(engine.all_language_packs()) == 5

    def test_recent_readings_empty_initially(self):
        e = ClientPsychologyEngine()
        assert e.recent_readings() == []

    def test_recent_readings_after_calls(self, engine):
        for i in range(3):
            engine.read_client(f"rec_test_{i}", ["leaving money on the table"])
        recent = engine.recent_readings(3)
        assert len(recent) == 3

    def test_recent_readings_respects_limit(self, engine):
        for i in range(5):
            engine.read_client(f"limit_test_{i}", ["burn rate too high"])
        recent = engine.recent_readings(2)
        assert len(recent) == 2


# ---------------------------------------------------------------------------
# Part 16 — ClientReadingReport serialisation
# ---------------------------------------------------------------------------

class TestClientReadingReportSerialisation:
    def test_to_dict_returns_dict(self, engine):
        r = engine.read_client(
            "serial_test",
            ["we are not hitting targets"],
            {"generation": GenerationCohort.GEN_X,
             "industry": IndustryVertical.TECHNOLOGY,
             "role": DecisionMakerRole.ECONOMIC_BUYER},
        )
        d = r.to_dict()
        assert isinstance(d, dict)

    def test_to_dict_keys(self, engine):
        r = engine.read_client("serial_test_2", ["competitors moving faster"])
        d = r.to_dict()
        for key in ("client_id", "demographic_profile", "detected_pain_signals",
                    "recommended_framework", "income_scaling_lever",
                    "opening_gambit", "closing_approach", "urgency_narrative"):
            assert key in d

    def test_to_dict_pains_are_list(self, engine):
        r = engine.read_client(
            "serial_test_3",
            ["losing deals to competitor", "board wants more"],
        )
        d = r.to_dict()
        assert isinstance(d["detected_pain_signals"], list)


# ---------------------------------------------------------------------------
# Part 17 — Thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_read_client(self):
        engine = ClientPsychologyEngine()
        results = []
        errors  = []

        def run(i):
            try:
                r = engine.read_client(
                    f"thread_{i}",
                    ["leaving money on the table", "competitors moving faster"],
                )
                results.append(r)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=run, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"Thread errors: {errors}"
        assert len(results) == 10
