"""
Tests for character_network_engine.py — Round 58

Covers:
  Part 1  — CharacterPillar enum completeness
  Part 2  — VictorianCharacterClass and NetworkTier enums
  Part 3  — VictorianLeader dataclass integrity
  Part 4  — Victorian leaders corpus completeness
  Part 5  — VictorianLeader pillar score validity
  Part 6  — VictorianLeader dominant_pillar and distance_to
  Part 7  — SecondNatureBehavior completeness
  Part 8  — MoralFiberScore properties
  Part 9  — CharacterAssessor scoring
  Part 10 — VictorianLeaderLibrary access methods
  Part 11 — SecondNatureBehaviorEngine habit building
  Part 12 — CharacterNetworkBuilder profile creation
  Part 13 — CharacterNetworkEngine façade
  Part 14 — NetworkAudit output
  Part 15 — Thread safety and caching
"""

import sys
import os
import threading

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from character_network_engine import (
    CharacterPillar, VictorianCharacterClass, NetworkTier,
    ALL_PILLARS,
    VictorianLeader, SecondNatureBehavior, MoralFiberScore,
    NetworkCandidate, CharacterNetworkProfile,
    VICTORIAN_LEADERS, SECOND_NATURE_BEHAVIORS,
    CharacterAssessor, VictorianLeaderLibrary,
    SecondNatureBehaviorEngine, CharacterNetworkBuilder,
    CharacterNetworkEngine,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def engine():
    return CharacterNetworkEngine()


@pytest.fixture
def assessor():
    return CharacterAssessor()


@pytest.fixture
def library():
    return VictorianLeaderLibrary()


@pytest.fixture
def behavior_engine():
    return SecondNatureBehaviorEngine()


@pytest.fixture
def builder():
    return CharacterNetworkBuilder()


@pytest.fixture
def sample_signals():
    return [
        "helped a colleague without being asked",
        "admitted an error to the team immediately",
        "stood up for a junior colleague in a difficult meeting",
        "persisted despite repeated setbacks",
        "credited someone else's idea publicly",
        "paused before reacting to criticism",
        "considered consequences before deciding",
        "listened before advising",
    ]


@pytest.fixture
def sample_score(assessor, sample_signals):
    return assessor.assess(sample_signals, subject_id="test_subject")


# ---------------------------------------------------------------------------
# Part 1 — CharacterPillar enum completeness
# ---------------------------------------------------------------------------

class TestCharacterPillarEnum:
    def test_count(self):
        assert len(CharacterPillar) == 8

    def test_all_pillars_present(self):
        values = {p.value for p in CharacterPillar}
        expected = {
            "integrity", "moral_courage", "service_above_self", "wisdom",
            "justice", "fortitude", "temperance", "prudence",
        }
        assert expected == values

    def test_all_pillars_list_matches_enum(self):
        assert set(ALL_PILLARS) == set(CharacterPillar)


# ---------------------------------------------------------------------------
# Part 2 — VictorianCharacterClass and NetworkTier
# ---------------------------------------------------------------------------

class TestOtherEnums:
    def test_character_class_count(self):
        assert len(VictorianCharacterClass) == 8

    def test_network_tier_count(self):
        assert len(NetworkTier) == 4

    def test_network_tier_values(self):
        tiers = {t.value for t in NetworkTier}
        assert "inner_circle" in tiers
        assert "trusted_advisors" in tiers
        assert "extended_network" in tiers
        assert "community_impact" in tiers


# ---------------------------------------------------------------------------
# Part 3 — VictorianLeader dataclass integrity
# ---------------------------------------------------------------------------

class TestVictorianLeaderDataclass:
    def test_nightingale_exists(self):
        assert "florence_nightingale" in VICTORIAN_LEADERS

    def test_leader_has_all_fields(self):
        leader = VICTORIAN_LEADERS["florence_nightingale"]
        assert leader.name
        assert leader.era
        assert leader.character_class
        assert leader.signature_act
        assert leader.network_approach
        assert leader.modern_parallel
        assert leader.character_lesson
        assert leader.second_nature_habit

    def test_to_dict_keys(self):
        leader = VICTORIAN_LEADERS["william_wilberforce"]
        d = leader.to_dict()
        for key in ("leader_id", "name", "era", "character_class",
                    "pillar_scores", "overall_score", "dominant_pillar",
                    "signature_act", "modern_parallel", "second_nature_habit"):
            assert key in d

    def test_overall_score_in_range(self):
        for leader in VICTORIAN_LEADERS.values():
            assert 0.0 < leader.overall_score <= 1.0

    def test_pillar_scores_values_are_serialised(self):
        leader = VICTORIAN_LEADERS["harriet_tubman"]
        d = leader.to_dict()
        assert isinstance(d["pillar_scores"], dict)
        for key in d["pillar_scores"]:
            assert isinstance(key, str)


# ---------------------------------------------------------------------------
# Part 4 — Victorian leaders corpus completeness
# ---------------------------------------------------------------------------

class TestVictorianLeadersCorpus:
    def test_minimum_leaders(self):
        assert len(VICTORIAN_LEADERS) >= 15

    def test_all_leaders_have_unique_ids(self):
        ids = list(VICTORIAN_LEADERS.keys())
        assert len(ids) == len(set(ids))

    def test_all_character_classes_represented(self):
        classes = {l.character_class for l in VICTORIAN_LEADERS.values()}
        for cc in VictorianCharacterClass:
            assert cc in classes, f"Character class {cc} not in corpus"

    def test_all_leaders_have_all_pillars(self):
        for lid, leader in VICTORIAN_LEADERS.items():
            for pillar in CharacterPillar:
                assert pillar in leader.pillar_scores, f"{lid} missing pillar {pillar}"


# ---------------------------------------------------------------------------
# Part 5 — Pillar score validity
# ---------------------------------------------------------------------------

class TestPillarScoreValidity:
    def test_all_scores_between_0_and_1(self):
        for leader in VICTORIAN_LEADERS.values():
            for pillar, score in leader.pillar_scores.items():
                assert 0.0 <= score <= 1.0, f"{leader.name}.{pillar.value} = {score}"

    def test_high_character_leaders_score_above_0_85(self):
        # Nightingale, Wilberforce, Tubman are known to be highest scorers
        for lid in ("florence_nightingale", "william_wilberforce", "harriet_tubman"):
            leader = VICTORIAN_LEADERS[lid]
            assert leader.overall_score >= 0.85


# ---------------------------------------------------------------------------
# Part 6 — VictorianLeader methods
# ---------------------------------------------------------------------------

class TestVictorianLeaderMethods:
    def test_dominant_pillar_returns_max(self):
        for leader in VICTORIAN_LEADERS.values():
            dom_pillar, dom_score = leader.dominant_pillar
            for score in leader.pillar_scores.values():
                assert dom_score >= score

    def test_distance_to_self_is_zero(self):
        leader = VICTORIAN_LEADERS["florence_nightingale"]
        dist = leader.distance_to(leader.pillar_scores)
        assert dist == pytest.approx(0.0, abs=1e-5)

    def test_distance_to_different_leader_is_positive(self):
        l1 = VICTORIAN_LEADERS["florence_nightingale"]
        l2 = VICTORIAN_LEADERS["benjamin_disraeli"]
        dist = l1.distance_to(l2.pillar_scores)
        assert dist > 0.0


# ---------------------------------------------------------------------------
# Part 7 — SecondNatureBehavior completeness
# ---------------------------------------------------------------------------

class TestSecondNatureBehaviors:
    def test_minimum_behaviors(self):
        assert len(SECOND_NATURE_BEHAVIORS) >= 10

    def test_all_pillars_have_at_least_one_behavior(self):
        behavior_pillars = {b.pillar for b in SECOND_NATURE_BEHAVIORS}
        for pillar in CharacterPillar:
            assert pillar in behavior_pillars, f"No behavior for {pillar}"

    def test_behavior_fields_complete(self):
        for b in SECOND_NATURE_BEHAVIORS:
            assert b.behavior_id
            assert b.description
            assert b.trigger
            assert b.micro_action
            assert b.compounding_effect
            assert b.victorian_exemplar

    def test_behavior_to_dict(self):
        b = SECOND_NATURE_BEHAVIORS[0]
        d = b.to_dict()
        assert "behavior_id" in d
        assert "pillar" in d
        assert "micro_action" in d
        assert "compounding_effect" in d


# ---------------------------------------------------------------------------
# Part 8 — MoralFiberScore properties
# ---------------------------------------------------------------------------

class TestMoralFiberScore:
    def test_overall_score_is_mean(self, sample_score):
        expected = sum(sample_score.pillar_scores.values()) / len(sample_score.pillar_scores)
        assert sample_score.overall_score == pytest.approx(expected, abs=1e-4)

    def test_dominant_pillar_is_max(self, sample_score):
        dom_pillar, dom_score = sample_score.dominant_pillar
        for score in sample_score.pillar_scores.values():
            assert dom_score >= score

    def test_development_areas_are_below_average(self, sample_score):
        avg = sample_score.overall_score
        for pillar, score in sample_score.development_areas:
            assert score < avg

    def test_development_areas_sorted_ascending(self, sample_score):
        areas = sample_score.development_areas
        for i in range(len(areas) - 1):
            assert areas[i][1] <= areas[i + 1][1]

    def test_character_archetype_is_string(self, sample_score):
        assert isinstance(sample_score.character_archetype, str)
        assert len(sample_score.character_archetype) > 5

    def test_to_dict_structure(self, sample_score):
        d = sample_score.to_dict()
        assert "subject_id" in d
        assert "overall_score" in d
        assert "dominant_pillar" in d
        assert "character_archetype" in d
        assert "development_areas" in d


# ---------------------------------------------------------------------------
# Part 9 — CharacterAssessor
# ---------------------------------------------------------------------------

class TestCharacterAssessor:
    def test_assess_returns_moral_fiber_score(self, assessor, sample_signals):
        score = assessor.assess(sample_signals, "test_subject")
        assert isinstance(score, MoralFiberScore)

    def test_assess_all_pillars_present(self, assessor, sample_signals):
        score = assessor.assess(sample_signals)
        for pillar in CharacterPillar:
            assert pillar in score.pillar_scores

    def test_scores_in_valid_range(self, assessor, sample_signals):
        score = assessor.assess(sample_signals)
        for pillar, s in score.pillar_scores.items():
            assert 0.0 <= s <= 1.0

    def test_base_score_is_0_70(self, assessor):
        score = assessor.assess([])
        for s in score.pillar_scores.values():
            assert s == pytest.approx(0.70, abs=0.01)

    def test_service_keyword_increases_service_score(self, assessor):
        weak_score = assessor.assess([])
        strong_score = assessor.assess(["helped", "served", "contributed", "gave", "volunteered"])
        assert (strong_score.pillar_scores[CharacterPillar.SERVICE_ABOVE_SELF] >
                weak_score.pillar_scores[CharacterPillar.SERVICE_ABOVE_SELF])

    def test_score_pillar_single(self, assessor):
        score = assessor.score_pillar(CharacterPillar.INTEGRITY, ["honest", "transparent", "consistent"])
        assert 0.70 <= score <= 1.0


# ---------------------------------------------------------------------------
# Part 10 — VictorianLeaderLibrary
# ---------------------------------------------------------------------------

class TestVictorianLeaderLibrary:
    def test_get_all_returns_dict(self, library):
        leaders = library.get_all()
        assert isinstance(leaders, dict)
        assert len(leaders) >= 15

    def test_get_by_class_reformers(self, library):
        reformers = library.get_by_class(VictorianCharacterClass.REFORMER)
        assert len(reformers) >= 3
        for r in reformers:
            assert r.character_class == VictorianCharacterClass.REFORMER

    def test_find_archetype_returns_closest(self, library, sample_score):
        archetype = library.find_archetype(sample_score)
        assert isinstance(archetype, VictorianLeader)

    def test_top_n_returns_n_leaders(self, library):
        top5 = library.top_n_by_score(5)
        assert len(top5) == 5

    def test_top_n_sorted_descending(self, library):
        top5 = library.top_n_by_score(5)
        scores = [l.overall_score for l in top5]
        assert scores == sorted(scores, reverse=True)

    def test_pillar_champions_returns_all_pillars(self, library):
        champions = library.pillar_champions()
        for pillar in CharacterPillar:
            assert pillar in champions
            assert isinstance(champions[pillar], VictorianLeader)


# ---------------------------------------------------------------------------
# Part 11 — SecondNatureBehaviorEngine
# ---------------------------------------------------------------------------

class TestSecondNatureBehaviorEngine:
    def test_get_behaviors_for_pillar(self, behavior_engine):
        behaviors = behavior_engine.get_behaviors_for_pillar(CharacterPillar.INTEGRITY)
        assert len(behaviors) >= 1
        for b in behaviors:
            assert b.pillar == CharacterPillar.INTEGRITY

    def test_build_habit_stack_returns_list(self, behavior_engine, sample_score):
        habits = behavior_engine.build_habit_stack(sample_score)
        assert isinstance(habits, list)
        assert len(habits) >= 3

    def test_habit_stack_prioritises_development_areas(self, behavior_engine, sample_score):
        dev_pillars = [p for p, _ in sample_score.development_areas[:3]]
        habits = behavior_engine.build_habit_stack(sample_score)
        habit_pillars = [h.pillar for h in habits]
        for dp in dev_pillars:
            assert dp in habit_pillars

    def test_embed_into_agent_adds_overlay(self, behavior_engine):
        genome = {"communication": 0.85, "technical": 0.90}
        enriched = behavior_engine.embed_into_agent(genome)
        assert "character_overlay" in enriched
        overlay = enriched["character_overlay"]
        assert "integrity_signal" in overlay
        assert "service_reflex" in overlay
        assert all(0.0 <= v <= 1.0 for v in overlay.values())


# ---------------------------------------------------------------------------
# Part 12 — CharacterNetworkBuilder
# ---------------------------------------------------------------------------

class TestCharacterNetworkBuilder:
    def test_build_profile_returns_profile(self, builder, sample_signals):
        profile = builder.build_profile("test_agent", sample_signals)
        assert isinstance(profile, CharacterNetworkProfile)

    def test_profile_has_archetype(self, builder, sample_signals):
        profile = builder.build_profile("test_agent", sample_signals)
        assert isinstance(profile.archetype_match, VictorianLeader)

    def test_profile_has_network(self, builder, sample_signals):
        profile = builder.build_profile("test_agent", sample_signals)
        assert isinstance(profile.network_by_tier, dict)
        assert len(profile.network_by_tier) == 4

    def test_profile_network_health_in_range(self, builder, sample_signals):
        profile = builder.build_profile("test_agent", sample_signals)
        assert 0.0 <= profile.network_health_score <= 1.0

    def test_profile_development_plan(self, builder, sample_signals):
        profile = builder.build_profile("test_agent", sample_signals)
        assert isinstance(profile.development_plan, list)
        assert len(profile.development_plan) >= 1
        for item in profile.development_plan:
            assert "priority" in item
            assert "pillar" in item
            assert "weekly_practice" in item

    def test_recommend_connections(self, builder, sample_score):
        recs = builder.recommend_connections(sample_score, count=3)
        assert len(recs) <= 3
        for r in recs:
            assert isinstance(r, NetworkCandidate)
            assert isinstance(r.moral_fiber, MoralFiberScore)


# ---------------------------------------------------------------------------
# Part 13 — CharacterNetworkEngine façade
# ---------------------------------------------------------------------------

class TestCharacterNetworkEngine:
    def test_profile_agent_returns_profile(self, engine, sample_signals):
        profile = engine.profile_agent("test_agent", sample_signals)
        assert isinstance(profile, CharacterNetworkProfile)
        assert profile.agent_id == "test_agent"

    def test_get_second_nature_habits(self, engine, sample_score):
        habits = engine.get_second_nature_habits(sample_score)
        assert isinstance(habits, list)
        assert len(habits) >= 3

    def test_describe_victorian_leader_known(self, engine):
        d = engine.describe_victorian_leader("florence_nightingale")
        assert d is not None
        assert d["name"] == "Florence Nightingale"

    def test_describe_victorian_leader_unknown(self, engine):
        result = engine.describe_victorian_leader("nonexistent_person")
        assert result is None

    def test_all_behaviors_count(self, engine):
        behaviors = engine.all_behaviors()
        assert len(behaviors) >= 10

    def test_all_leaders_count(self, engine):
        leaders = engine.all_leaders()
        assert len(leaders) >= 15


# ---------------------------------------------------------------------------
# Part 14 — Network audit
# ---------------------------------------------------------------------------

class TestNetworkAudit:
    def test_audit_returns_dict(self, engine, sample_signals):
        profile = engine.profile_agent("audit_test", sample_signals)
        audit = engine.network_audit(profile)
        assert isinstance(audit, dict)

    def test_audit_has_required_keys(self, engine, sample_signals):
        profile = engine.profile_agent("audit_test_2", sample_signals)
        audit = engine.network_audit(profile)
        for key in ("agent_id", "network_size", "health_score",
                    "pillar_distribution", "gaps", "archetype",
                    "second_nature_habits"):
            assert key in audit

    def test_audit_network_size_positive(self, engine, sample_signals):
        profile = engine.profile_agent("audit_test_3", sample_signals)
        audit = engine.network_audit(profile)
        assert audit["network_size"] > 0

    def test_to_dict(self, engine, sample_signals):
        profile = engine.profile_agent("serial_test", sample_signals)
        d = profile.to_dict()
        assert "agent_id" in d
        assert "own_moral_fiber" in d
        assert "archetype_match" in d
        assert "network_health_score" in d
        assert "total_network_size" in d


# ---------------------------------------------------------------------------
# Part 15 — Thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_profile_agent(self):
        engine = CharacterNetworkEngine()
        results = []
        errors  = []

        signals = [
            "helped a colleague", "admitted an error",
            "persisted despite setbacks", "credited someone else",
        ]

        def run(i):
            try:
                p = engine.profile_agent(f"thread_{i}", signals)
                results.append(p)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=run, args=(i,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"Thread errors: {errors}"
        assert len(results) == 8
