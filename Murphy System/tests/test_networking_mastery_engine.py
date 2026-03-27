"""
Tests for networking_mastery_engine.py — Round 58

Covers:
  Part 1  — Enum completeness
  Part 2  — NetworkingGreat dataclass integrity
  Part 3  — Networking greats corpus completeness
  Part 4  — All networking styles represented in corpus
  Part 5  — Networking IQ scores
  Part 6  — BuzzCampaign completeness
  Part 7  — BuzzEngine campaign retrieval
  Part 8  — CapabilityMapper — three-layer signal generation
  Part 9  — CapabilityMapper — archetype signal enrichment
  Part 10 — NetworkingGreatLibrary access methods
  Part 11 — NetworkIntelligenceEngine report generation
  Part 12 — NetworkIntelligenceReport structure and properties
  Part 13 — NetworkingMasteryEngine façade
  Part 14 — Capability layer content validation (face/between/outside)
  Part 15 — Thread safety and history tracking
"""

import sys
import os
import threading

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from networking_mastery_engine import (
    NetworkingStyle, BuzzType, CapabilityLayer, NetworkHealthStatus,
    NetworkingGreat, BuzzCampaign, CapabilitySignalSet, NetworkIntelligenceReport,
    NETWORKING_GREATS, BUZZ_CAMPAIGN_TEMPLATES,
    BuzzEngine, CapabilityMapper, NetworkingGreatLibrary,
    NetworkIntelligenceEngine, NetworkingMasteryEngine,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def engine():
    return NetworkingMasteryEngine()


@pytest.fixture
def buzz_engine():
    return BuzzEngine()


@pytest.fixture
def mapper():
    return CapabilityMapper()


@pytest.fixture
def library():
    return NetworkingGreatLibrary()


@pytest.fixture
def intel_engine():
    return NetworkIntelligenceEngine()


@pytest.fixture
def commercial_report(engine):
    return engine.analyse(
        agent_id="test_commercial",
        networking_style=NetworkingStyle.COMMERCIAL,
        current_network_iq=0.65,
        primary_strength="enterprise sales",
    )


@pytest.fixture
def digital_report(engine):
    return engine.analyse(
        agent_id="test_digital",
        networking_style=NetworkingStyle.DIGITAL,
        current_network_iq=0.72,
        primary_strength="platform strategy",
    )


# ---------------------------------------------------------------------------
# Part 1 — Enum completeness
# ---------------------------------------------------------------------------

class TestEnums:
    def test_networking_style_count(self):
        assert len(NetworkingStyle) == 6

    def test_networking_style_values(self):
        values = {s.value for s in NetworkingStyle}
        expected = {"political", "intellectual", "commercial", "community", "digital", "cultural"}
        assert expected == values

    def test_buzz_type_count(self):
        assert len(BuzzType) == 5

    def test_buzz_type_values(self):
        values = {b.value for b in BuzzType}
        assert "word_of_mouth" in values
        assert "thought_leadership" in values
        assert "social_proof" in values
        assert "demonstration_effect" in values
        assert "viral_loop" in values

    def test_capability_layer_count(self):
        assert len(CapabilityLayer) == 3

    def test_capability_layer_values(self):
        values = {c.value for c in CapabilityLayer}
        assert "face_value" in values
        assert "between_lines" in values
        assert "outside_box" in values

    def test_network_health_status_count(self):
        assert len(NetworkHealthStatus) == 4


# ---------------------------------------------------------------------------
# Part 2 — NetworkingGreat dataclass integrity
# ---------------------------------------------------------------------------

class TestNetworkingGreatDataclass:
    def test_caesar_exists(self):
        assert "julius_caesar" in NETWORKING_GREATS

    def test_franklin_exists(self):
        assert "benjamin_franklin" in NETWORKING_GREATS

    def test_required_fields(self):
        for gid, great in NETWORKING_GREATS.items():
            assert great.name, f"{gid} missing name"
            assert great.era, f"{gid} missing era"
            assert great.primary_style, f"{gid} missing primary_style"
            assert great.signature_method, f"{gid} missing signature_method"
            assert great.buzz_mechanism, f"{gid} missing buzz_mechanism"
            assert great.face_value_signal, f"{gid} missing face_value_signal"
            assert great.between_lines_signal, f"{gid} missing between_lines_signal"
            assert great.outside_box_move, f"{gid} missing outside_box_move"
            assert great.modern_translation, f"{gid} missing modern_translation"
            assert great.core_principle, f"{gid} missing core_principle"
            assert great.network_quote, f"{gid} missing network_quote"

    def test_to_dict_structure(self):
        great = NETWORKING_GREATS["julius_caesar"]
        d = great.to_dict()
        for key in ("great_id", "name", "era", "primary_style",
                    "signature_method", "buzz_mechanism",
                    "face_value_signal", "between_lines_signal",
                    "outside_box_move", "modern_translation",
                    "core_principle", "network_quote",
                    "networking_iq_score"):
            assert key in d

    def test_networking_iq_in_range(self):
        for great in NETWORKING_GREATS.values():
            assert 0.0 < great.networking_iq_score <= 1.0


# ---------------------------------------------------------------------------
# Part 3 — Networking greats corpus completeness
# ---------------------------------------------------------------------------

class TestNetworkingGreatsCorpus:
    def test_minimum_corpus_size(self):
        assert len(NETWORKING_GREATS) >= 15

    def test_all_ids_unique(self):
        ids = list(NETWORKING_GREATS.keys())
        assert len(ids) == len(set(ids))

    def test_all_names_unique(self):
        names = [g.name for g in NETWORKING_GREATS.values()]
        assert len(names) == len(set(names))


# ---------------------------------------------------------------------------
# Part 4 — All networking styles represented
# ---------------------------------------------------------------------------

class TestNetworkingStyleCoverage:
    def test_all_primary_styles_represented(self):
        primary_styles = {g.primary_style for g in NETWORKING_GREATS.values()}
        for style in NetworkingStyle:
            assert style in primary_styles, f"No primary great for style {style}"

    def test_secondary_styles_are_valid(self):
        for great in NETWORKING_GREATS.values():
            for ss in great.secondary_styles:
                assert isinstance(ss, NetworkingStyle)


# ---------------------------------------------------------------------------
# Part 5 — Networking IQ scores
# ---------------------------------------------------------------------------

class TestNetworkingIQ:
    def test_multi_style_greats_have_higher_iq(self):
        for great in NETWORKING_GREATS.values():
            style_count = 1 + len(great.secondary_styles)
            expected_min = min(1.0, 0.70 + style_count * 0.05)
            assert great.networking_iq_score >= expected_min - 0.01

    def test_assess_networking_iq_returns_float(self, intel_engine):
        score = intel_engine.assess_networking_iq(
            ["introduced two colleagues", "followed up after meeting",
             "wrote a weekly newsletter", "hosted a dinner"]
        )
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    def test_more_indicators_increases_iq(self, intel_engine):
        low_signals  = ["attended a meeting"]
        high_signals = ["introduced", "referred", "connected", "followed up",
                        "sent a note", "wrote", "published", "presented",
                        "hosted", "invited", "thanked", "credited"]
        low  = intel_engine.assess_networking_iq(low_signals)
        high = intel_engine.assess_networking_iq(high_signals)
        assert high > low


# ---------------------------------------------------------------------------
# Part 6 — BuzzCampaign completeness
# ---------------------------------------------------------------------------

class TestBuzzCampaignTemplates:
    def test_minimum_templates(self):
        assert len(BUZZ_CAMPAIGN_TEMPLATES) >= 5

    def test_all_buzz_types_represented(self):
        buzz_types = {c.buzz_type for c in BUZZ_CAMPAIGN_TEMPLATES}
        for bt in BuzzType:
            assert bt in buzz_types, f"No buzz campaign for type {bt}"

    def test_campaign_fields_complete(self):
        for c in BUZZ_CAMPAIGN_TEMPLATES:
            assert c.campaign_id
            assert c.strategy_name
            assert c.primary_vehicle
            assert c.trigger_event
            assert c.propagation_mechanism
            assert len(c.amplification_tactics) >= 2
            assert c.measurement_metric
            assert c.timeline_days > 0
            assert c.reach_multiplier > 0
            assert c.great_exemplar

    def test_to_dict_structure(self):
        c = BUZZ_CAMPAIGN_TEMPLATES[0]
        d = c.to_dict()
        assert "buzz_type" in d
        assert "strategy_name" in d
        assert "reach_multiplier" in d
        assert isinstance(d["amplification_tactics"], list)


# ---------------------------------------------------------------------------
# Part 7 — BuzzEngine
# ---------------------------------------------------------------------------

class TestBuzzEngine:
    def test_get_campaigns_returns_list(self, buzz_engine):
        campaigns = buzz_engine.get_campaigns()
        assert isinstance(campaigns, list)
        assert len(campaigns) >= 1

    def test_get_campaigns_max_respected(self, buzz_engine):
        campaigns = buzz_engine.get_campaigns(max_campaigns=2)
        assert len(campaigns) <= 2

    def test_get_campaigns_filtered_by_type(self, buzz_engine):
        campaigns = buzz_engine.get_campaigns(buzz_types=[BuzzType.THOUGHT_LEADERSHIP])
        for c in campaigns:
            assert c.buzz_type == BuzzType.THOUGHT_LEADERSHIP

    def test_campaigns_sorted_by_reach_multiplier(self, buzz_engine):
        campaigns = buzz_engine.get_campaigns(max_campaigns=5)
        multipliers = [c.reach_multiplier for c in campaigns]
        assert multipliers == sorted(multipliers, reverse=True)

    def test_recommend_for_low_iq(self, buzz_engine):
        campaigns = buzz_engine.recommend_for_stage(0.50)
        assert len(campaigns) >= 1
        types = {c.buzz_type for c in campaigns}
        assert BuzzType.DEMONSTRATION in types or BuzzType.WORD_OF_MOUTH in types

    def test_recommend_for_high_iq(self, buzz_engine):
        campaigns = buzz_engine.recommend_for_stage(0.90)
        assert len(campaigns) >= 1
        types = {c.buzz_type for c in campaigns}
        assert BuzzType.VIRAL_LOOP in types or BuzzType.THOUGHT_LEADERSHIP in types

    def test_all_campaigns_returns_full_list(self, buzz_engine):
        assert len(buzz_engine.all_campaigns()) == len(BUZZ_CAMPAIGN_TEMPLATES)


# ---------------------------------------------------------------------------
# Part 8 — CapabilityMapper
# ---------------------------------------------------------------------------

class TestCapabilityMapper:
    def test_generate_returns_signal_set(self, mapper):
        signals = mapper.generate_capability_signals("test_sub", "sales", "revenue growth")
        assert isinstance(signals, CapabilitySignalSet)

    def test_face_value_non_empty(self, mapper):
        signals = mapper.generate_capability_signals("test", "consulting", "strategy")
        assert len(signals.face_value) >= 2

    def test_between_lines_non_empty(self, mapper):
        signals = mapper.generate_capability_signals("test", "consulting", "strategy")
        assert len(signals.between_lines) >= 2

    def test_outside_box_non_empty(self, mapper):
        signals = mapper.generate_capability_signals("test", "consulting", "strategy")
        assert len(signals.outside_box) >= 2

    def test_all_are_strings(self, mapper):
        signals = mapper.generate_capability_signals("test", "sales", "deals")
        for s in signals.face_value + signals.between_lines + signals.outside_box:
            assert isinstance(s, str)


# ---------------------------------------------------------------------------
# Part 9 — CapabilityMapper archetype enrichment
# ---------------------------------------------------------------------------

class TestCapabilityMapperEnrichment:
    def test_add_archetype_signals_enriches(self, mapper):
        base    = mapper.generate_capability_signals("test", "sales", "revenue")
        archetype = NETWORKING_GREATS["julius_caesar"]
        enriched = mapper.add_archetype_signals(base, archetype)
        assert len(enriched.face_value)    > len(base.face_value)
        assert len(enriched.between_lines) > len(base.between_lines)
        assert len(enriched.outside_box)   > len(base.outside_box)

    def test_enriched_has_archetype_match(self, mapper):
        base      = mapper.generate_capability_signals("test", "sales", "revenue")
        archetype = NETWORKING_GREATS["benjamin_franklin"]
        enriched  = mapper.add_archetype_signals(base, archetype)
        assert enriched.archetype_match is not None
        assert enriched.archetype_match.name == "Benjamin Franklin"

    def test_to_dict_after_enrichment(self, mapper):
        base      = mapper.generate_capability_signals("test", "sales", "revenue")
        archetype = NETWORKING_GREATS["warren_buffett_network"]
        enriched  = mapper.add_archetype_signals(base, archetype)
        d = enriched.to_dict()
        assert d["archetype_match"] == "Warren Buffett"
        assert isinstance(d["face_value"], list)
        assert isinstance(d["between_lines"], list)
        assert isinstance(d["outside_box"], list)


# ---------------------------------------------------------------------------
# Part 10 — NetworkingGreatLibrary
# ---------------------------------------------------------------------------

class TestNetworkingGreatLibrary:
    def test_get_all_returns_full_corpus(self, library):
        assert len(library.get_all()) >= 15

    def test_get_by_style_commercial(self, library):
        greats = library.get_by_style(NetworkingStyle.COMMERCIAL)
        assert len(greats) >= 3
        for g in greats:
            assert (g.primary_style == NetworkingStyle.COMMERCIAL
                    or NetworkingStyle.COMMERCIAL in g.secondary_styles)

    def test_find_archetype_for_style(self, library):
        for style in NetworkingStyle:
            archetype = library.find_archetype_for_style(style)
            assert archetype is not None
            assert archetype.primary_style == style

    def test_top_n_returns_n(self, library):
        assert len(library.top_n(3)) == 3

    def test_top_n_sorted_descending(self, library):
        top = library.top_n(5)
        scores = [g.networking_iq_score for g in top]
        assert scores == sorted(scores, reverse=True)

    def test_find_by_principle_keyword(self, library):
        results = library.find_by_principle("reputation")
        assert len(results) >= 1
        for g in results:
            assert "reputation" in g.core_principle.lower()


# ---------------------------------------------------------------------------
# Part 11 — NetworkIntelligenceEngine
# ---------------------------------------------------------------------------

class TestNetworkIntelligenceEngine:
    def test_build_report_returns_report(self, intel_engine):
        report = intel_engine.build_report(
            agent_id="test_agent",
            networking_style=NetworkingStyle.INTELLECTUAL,
            current_network_iq=0.68,
        )
        assert isinstance(report, NetworkIntelligenceReport)

    def test_report_has_archetype(self, intel_engine):
        report = intel_engine.build_report("test", NetworkingStyle.POLITICAL)
        assert isinstance(report.archetype_match, NetworkingGreat)

    def test_report_has_buzz_campaigns(self, intel_engine):
        report = intel_engine.build_report("test", NetworkingStyle.COMMUNITY)
        assert len(report.buzz_campaigns) >= 1

    def test_report_has_quick_wins(self, intel_engine):
        report = intel_engine.build_report("test", NetworkingStyle.CULTURAL)
        assert len(report.quick_wins) >= 1

    def test_report_has_90_day_plan(self, intel_engine):
        report = intel_engine.build_report("test", NetworkingStyle.DIGITAL)
        assert len(report.ninety_day_plan) == 3
        for step in report.ninety_day_plan:
            assert "month" in step
            assert "theme" in step
            assert "actions" in step

    def test_report_has_gaps(self, intel_engine):
        report = intel_engine.build_report("test", NetworkingStyle.COMMERCIAL, 0.50)
        assert isinstance(report.network_gaps, list)


# ---------------------------------------------------------------------------
# Part 12 — NetworkIntelligenceReport structure
# ---------------------------------------------------------------------------

class TestNetworkIntelligenceReport:
    def test_health_status_elite(self, commercial_report):
        # Force elite by setting high IQ directly
        from dataclasses import replace
        import networking_mastery_engine as nme_mod
        report = nme_mod.NetworkIntelligenceReport(
            agent_id="test",
            networking_style=NetworkingStyle.COMMERCIAL,
            archetype_match=commercial_report.archetype_match,
            capability_signals=commercial_report.capability_signals,
            buzz_campaigns=commercial_report.buzz_campaigns,
            network_gaps=[],
            quick_wins=[],
            ninety_day_plan=[],
            network_iq=0.90,
        )
        assert report.health_status == NetworkHealthStatus.ELITE

    def test_health_status_developing(self, commercial_report):
        import networking_mastery_engine as nme_mod
        report = nme_mod.NetworkIntelligenceReport(
            agent_id="test",
            networking_style=NetworkingStyle.COMMERCIAL,
            archetype_match=commercial_report.archetype_match,
            capability_signals=commercial_report.capability_signals,
            buzz_campaigns=[],
            network_gaps=[],
            quick_wins=[],
            ninety_day_plan=[],
            network_iq=0.60,
        )
        assert report.health_status == NetworkHealthStatus.DEVELOPING

    def test_to_dict_structure(self, commercial_report):
        d = commercial_report.to_dict()
        for key in ("agent_id", "networking_style", "archetype_match",
                    "network_iq", "health_status", "capability_signals",
                    "buzz_campaigns", "network_gaps", "quick_wins",
                    "ninety_day_plan"):
            assert key in d

    def test_to_dict_capability_signals(self, commercial_report):
        d = commercial_report.to_dict()
        sigs = d["capability_signals"]
        assert "face_value" in sigs
        assert "between_lines" in sigs
        assert "outside_box" in sigs


# ---------------------------------------------------------------------------
# Part 13 — NetworkingMasteryEngine façade
# ---------------------------------------------------------------------------

class TestNetworkingMasteryEngine:
    def test_analyse_returns_report(self, engine):
        report = engine.analyse("test_001", NetworkingStyle.COMMERCIAL)
        assert isinstance(report, NetworkIntelligenceReport)

    def test_describe_great_known(self, engine):
        d = engine.describe_great("julius_caesar")
        assert d is not None
        assert d["name"] == "Julius Caesar"

    def test_describe_great_unknown(self, engine):
        result = engine.describe_great("nonexistent_person")
        assert result is None

    def test_get_buzz_campaigns(self, engine):
        campaigns = engine.get_buzz_campaigns()
        assert len(campaigns) >= 2

    def test_get_capability_signals(self, engine):
        signals = engine.get_capability_signals("test", "consulting", "strategy")
        assert isinstance(signals, CapabilitySignalSet)
        assert len(signals.face_value) >= 1

    def test_all_greats(self, engine):
        assert len(engine.all_greats()) >= 15

    def test_all_buzz_campaigns(self, engine):
        assert len(engine.all_buzz_campaigns()) >= 5

    def test_assess_networking_iq(self, engine):
        score = engine.assess_networking_iq(["introduced two people", "followed up consistently"])
        assert 0.0 <= score <= 1.0

    def test_recent_analyses_initially_empty(self):
        e = NetworkingMasteryEngine()
        assert e.recent_analyses() == []

    def test_recent_analyses_populated(self, engine):
        for i in range(3):
            engine.analyse(f"hist_{i}", NetworkingStyle.INTELLECTUAL)
        recent = engine.recent_analyses(3)
        assert len(recent) == 3


# ---------------------------------------------------------------------------
# Part 14 — Capability layer content validation
# ---------------------------------------------------------------------------

class TestCapabilityLayerContent:
    def test_face_value_contains_explicit_claim(self, commercial_report):
        for signal in commercial_report.capability_signals.face_value:
            assert isinstance(signal, str)
            assert len(signal) > 10

    def test_between_lines_contains_implicit_signals(self, commercial_report):
        combined = " ".join(commercial_report.capability_signals.between_lines).lower()
        # Between lines should reference quality, network, or trust signals
        assert any(kw in combined for kw in
                   ("network", "question", "trust", "relationship", "quality",
                    "follow", "client", "referenc", "preparation", "reliability"))

    def test_outside_box_contains_cross_domain_ideas(self, commercial_report):
        combined = " ".join(commercial_report.capability_signals.outside_box).lower()
        # Outside box should reference applying something unexpected
        assert any(kw in combined for kw in
                   ("applied", "strategy", "framework", "theory", "method",
                    "principles", "discipline", "system", "cross"))

    def test_all_three_layers_have_content(self, digital_report):
        sigs = digital_report.capability_signals
        assert len(sigs.face_value)    >= 2
        assert len(sigs.between_lines) >= 2
        assert len(sigs.outside_box)   >= 2


# ---------------------------------------------------------------------------
# Part 15 — Thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_analyse(self):
        engine  = NetworkingMasteryEngine()
        results = []
        errors  = []

        def run(i):
            try:
                r = engine.analyse(
                    f"thread_{i}",
                    NetworkingStyle.COMMERCIAL,
                    0.65 + (i % 3) * 0.05,
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
