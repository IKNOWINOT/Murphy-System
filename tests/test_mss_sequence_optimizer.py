"""Tests for the MSS Sequence Optimizer (mss_sequence_optimizer.py).

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from src.mss_controls import MSSController
from src.information_quality import InformationQualityEngine
from src.information_density import InformationDensityEngine
from src.resolution_scoring import ResolutionDetectionEngine
from src.structural_coherence import StructuralCoherenceEngine
from src.concept_translation import ConceptTranslationEngine
from src.simulation_engine import StrategicSimulationEngine
from src.mss_sequence_optimizer import (
    MSSSequenceOptimizer,
    SequenceResult,
    OPTIMAL_SEQUENCE,
    TEST_BATTERY_SEQUENCES,
)


SAMPLE_TEXT = (
    "Build an automated niche content site that publishes SEO articles, "
    "monitors keyword rankings, and manages a subscriber list for a B2B software niche."
)


@pytest.fixture
def controller():
    rde = ResolutionDetectionEngine()
    ide = InformationDensityEngine()
    sce = StructuralCoherenceEngine()
    iqe = InformationQualityEngine(rde, ide, sce)
    cte = ConceptTranslationEngine()
    sim = StrategicSimulationEngine()
    return MSSController(iqe, cte, sim)


@pytest.fixture
def optimizer(controller):
    return MSSSequenceOptimizer(controller)


# ---------------------------------------------------------------------------
# run_sequence
# ---------------------------------------------------------------------------

class TestRunSequence:
    def test_mmsmm_returns_sequence_result(self, optimizer):
        result = optimizer.run_sequence(SAMPLE_TEXT, "MMSMM")
        assert isinstance(result, SequenceResult)

    def test_mmsmm_sequence_field(self, optimizer):
        result = optimizer.run_sequence(SAMPLE_TEXT, "MMSMM")
        assert result.sequence == "MMSMM"

    def test_mmsmm_correct_step_count(self, optimizer):
        result = optimizer.run_sequence(SAMPLE_TEXT, "MMSMM")
        # 5 sequence steps (M M S M M)
        assert len(result.steps) == 5

    def test_single_m_returns_sequence_result(self, optimizer):
        result = optimizer.run_sequence(SAMPLE_TEXT, "M")
        assert isinstance(result, SequenceResult)
        assert result.magnify_count == 1
        assert result.simplify_count == 0

    def test_single_s_returns_sequence_result(self, optimizer):
        result = optimizer.run_sequence(SAMPLE_TEXT, "S")
        assert isinstance(result, SequenceResult)
        assert result.simplify_count == 1
        assert result.magnify_count == 0

    def test_empty_sequence_raises(self, optimizer):
        with pytest.raises(ValueError):
            optimizer.run_sequence(SAMPLE_TEXT, "")

    def test_invalid_characters_raise(self, optimizer):
        with pytest.raises(ValueError):
            optimizer.run_sequence(SAMPLE_TEXT, "MMXMM")

    def test_magnify_simplify_counts_correct(self, optimizer):
        result = optimizer.run_sequence(SAMPLE_TEXT, "MMSMM")
        assert result.magnify_count == 4
        assert result.simplify_count == 1

    def test_rm_trace_length(self, optimizer):
        # 5 sequence steps + 1 solidify = 6 entries in rm_trace
        result = optimizer.run_sequence(SAMPLE_TEXT, "MMSMM")
        assert len(result.rm_trace) == 6

    def test_rm_trace_pattern_for_mmsmm(self, optimizer):
        """RM goes up on M, down on S, then up again — solidify locks at RM5."""
        result = optimizer.run_sequence(SAMPLE_TEXT, "MMSMM")
        # Convert to integer indices: RM0=0, RM1=1, ... RM5=5
        rm_order = ["RM0", "RM1", "RM2", "RM3", "RM4", "RM5"]
        indices = [rm_order.index(rm) if rm in rm_order else 0 for rm in result.rm_trace]
        # First two steps are magnify → indices should not decrease
        assert indices[0] >= 0
        assert indices[1] >= indices[0]
        # Third step is simplify → index should drop relative to second
        assert indices[2] <= indices[1]
        # Fourth and fifth are magnify → should not decrease
        assert indices[3] >= indices[2]
        assert indices[4] >= indices[3]

    def test_mmsmm_final_result_not_none(self, optimizer):
        result = optimizer.run_sequence(SAMPLE_TEXT, "MMSMM")
        assert result.final_result is not None

    def test_mmsmm_has_simulation(self, optimizer):
        """solidify always runs a simulation."""
        result = optimizer.run_sequence(SAMPLE_TEXT, "MMSMM")
        assert result.has_simulation is True
        assert result.final_result.simulation is not None

    def test_mmsmm_governance_status_valid(self, optimizer):
        result = optimizer.run_sequence(SAMPLE_TEXT, "MMSMM")
        assert result.governance_status in ("approved", "conditional", "blocked")

    def test_ratio_no_simplify(self, optimizer):
        result = optimizer.run_sequence(SAMPLE_TEXT, "MM")
        assert result.ratio == float("inf")

    def test_ratio_mmsmm(self, optimizer):
        result = optimizer.run_sequence(SAMPLE_TEXT, "MMSMM")
        assert result.ratio == pytest.approx(4.0)


# ---------------------------------------------------------------------------
# score_result
# ---------------------------------------------------------------------------

class TestScoreResult:
    def test_returns_float(self, optimizer):
        result = optimizer.run_sequence(SAMPLE_TEXT, "MMSMM")
        score = optimizer.score_result(result)
        assert isinstance(score, float)

    def test_score_between_0_and_1(self, optimizer):
        result = optimizer.run_sequence(SAMPLE_TEXT, "MMSMM")
        score = optimizer.score_result(result)
        assert 0.0 <= score <= 1.0

    def test_score_stored_on_result(self, optimizer):
        result = optimizer.run_sequence(SAMPLE_TEXT, "MMSMM")
        assert isinstance(result.composite_score, float)
        assert 0.0 <= result.composite_score <= 1.0


# ---------------------------------------------------------------------------
# run_test_battery
# ---------------------------------------------------------------------------

class TestRunTestBattery:
    def test_returns_list(self, optimizer):
        results = optimizer.run_test_battery(SAMPLE_TEXT)
        assert isinstance(results, list)

    def test_non_empty_results(self, optimizer):
        results = optimizer.run_test_battery(SAMPLE_TEXT)
        assert len(results) > 0

    def test_all_results_are_sequence_results(self, optimizer):
        results = optimizer.run_test_battery(SAMPLE_TEXT)
        for r in results:
            assert isinstance(r, SequenceResult)


# ---------------------------------------------------------------------------
# get_rankings
# ---------------------------------------------------------------------------

class TestGetRankings:
    def test_sorted_descending(self, optimizer):
        results = optimizer.run_test_battery(SAMPLE_TEXT)
        ranked = optimizer.get_rankings(results)
        scores = [r.composite_score for r in ranked]
        assert scores == sorted(scores, reverse=True)

    def test_same_length_as_input(self, optimizer):
        results = optimizer.run_test_battery(SAMPLE_TEXT)
        ranked = optimizer.get_rankings(results)
        assert len(ranked) == len(results)


# ---------------------------------------------------------------------------
# get_optimal_sequence
# ---------------------------------------------------------------------------

class TestGetOptimalSequence:
    def test_returns_string(self, optimizer):
        results = optimizer.run_test_battery(SAMPLE_TEXT)
        optimal = optimizer.get_optimal_sequence(results)
        assert isinstance(optimal, str)

    def test_empty_list_returns_default(self, optimizer):
        optimal = optimizer.get_optimal_sequence([])
        assert optimal == OPTIMAL_SEQUENCE


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------

class TestGenerateReport:
    def test_report_has_winner_key(self, optimizer):
        results = optimizer.run_test_battery(SAMPLE_TEXT)
        report = optimizer.generate_report(results)
        assert "winner" in report

    def test_report_has_top_5_key(self, optimizer):
        results = optimizer.run_test_battery(SAMPLE_TEXT)
        report = optimizer.generate_report(results)
        assert "top_5" in report

    def test_report_has_best_ratio_key(self, optimizer):
        results = optimizer.run_test_battery(SAMPLE_TEXT)
        report = optimizer.generate_report(results)
        assert "best_ratio" in report

    def test_report_winner_is_string(self, optimizer):
        results = optimizer.run_test_battery(SAMPLE_TEXT)
        report = optimizer.generate_report(results)
        assert isinstance(report["winner"], str)

    def test_report_empty_input(self, optimizer):
        report = optimizer.generate_report([])
        assert report["winner"] == OPTIMAL_SEQUENCE
        assert report["top_5"] == []

    def test_all_sequence_results_have_correct_counts(self, optimizer):
        """Every result's magnify + simplify counts must match its sequence length."""
        results = optimizer.run_test_battery(SAMPLE_TEXT)
        for r in results:
            total = r.magnify_count + r.simplify_count
            assert total == len(r.sequence), (
                f"Sequence {r.sequence!r}: {total} != {len(r.sequence)}"
            )
