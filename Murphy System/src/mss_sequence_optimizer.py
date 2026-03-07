"""
MSS Sequence Optimizer — Chains MSSController through arbitrary M/S sequences,
scores results, and ranks them to find the optimal transformation pipeline.
Design Label: MSS-OPT-001
Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from mss_controls import MSSController, TransformationResult, _describe_output

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants — discovered optimal sequence
# ---------------------------------------------------------------------------

OPTIMAL_SEQUENCE = "MMSMM"
OPTIMAL_RATIO = 4.0
OPTIMAL_SIMPLIFY_POSITION = 0.4  # simplify at 40% (position 3 of 5, ~1/e from end)

# ---------------------------------------------------------------------------
# Test battery sequences organised by mathematical family
# ---------------------------------------------------------------------------

_TEST_BATTERY_SEQUENCES: List[str] = [
    # Pure magnify
    "M", "MM", "MMM", "MMMM", "MMMMM",
    # Pure simplify
    "S", "SS", "SSS",
    # Fibonacci ratios
    "MS", "MMS", "MMMSS", "MMMMMSSS", "MMMMMMMMSSSSS",
    # Golden ratio approximations
    "MMMSS", "MMMMMSSS", "MMMMMMMMSSSSS",
    # Alternating (user's pattern)
    "MS", "MMSMMS", "MMSMS", "MSMSMS", "MMSMMSMMS",
    # Front-loaded
    "MMMMS", "MMMMSS", "MMMMMSS", "MMMMMS",
    # Back-loaded
    "SMMMM", "SMMMMM", "SSMMM",
    # Sandwich
    "MSMM", "MSMMM", "SMMS", "SMMMS",
    # Harmonic
    "M", "MS", "MMS", "MMMS", "MMMMS",
    # Power of 2
    "MM", "MMSS", "MMMMSSSS",
    # Prime ratios
    "MMS", "MMMS", "MMMMMSS", "MMMMMMMSSS",
    # The winner
    "MMSMM",
    # Breathing
    "MSMS", "MMSMMSMMS", "MMMSMMMSMMMS",
]

# Deduplicate while preserving order
_seen_seqs: set = set()
TEST_BATTERY_SEQUENCES: List[str] = []
for _seq in _TEST_BATTERY_SEQUENCES:
    if _seq not in _seen_seqs:
        _seen_seqs.add(_seq)
        TEST_BATTERY_SEQUENCES.append(_seq)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class SequenceResult:
    """Full trace of a single sequence run through the MSS pipeline."""

    sequence: str
    steps: List[TransformationResult] = field(default_factory=list)
    final_result: Optional[TransformationResult] = None
    rm_trace: List[str] = field(default_factory=list)
    magnify_count: int = 0
    simplify_count: int = 0
    ratio: float = 0.0         # M/S ratio (inf if no simplifies)
    composite_score: float = 0.0
    component_count: int = 0
    data_flow_count: int = 0
    has_simulation: bool = False
    governance_status: str = "approved"


# ---------------------------------------------------------------------------
# Optimizer class
# ---------------------------------------------------------------------------

class MSSSequenceOptimizer:
    """Chains MSSController through arbitrary M/S sequences and ranks results.

    Args:
        controller: A fully-initialised :class:`MSSController` instance.
    """

    def __init__(self, controller: MSSController) -> None:
        self._controller = controller

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_sequence(
        self,
        text: str,
        sequence: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> SequenceResult:
        """Run *sequence* against *text* through the MSS controller.

        Each uppercase letter is a transformation step:
          ``M`` → :meth:`MSSController.magnify`
          ``S`` → :meth:`MSSController.simplify`

        The chain always ends with a :meth:`MSSController.solidify` call.
        The output of each step is converted to text via :func:`_describe_output`
        and fed as input to the next step.

        Args:
            text: The initial input text.
            sequence: A string of ``'M'`` / ``'S'`` characters (e.g. ``"MMSMM"``).
            context: Optional context dictionary passed to every step.

        Returns:
            A populated :class:`SequenceResult`.

        Raises:
            ValueError: If *sequence* is empty or contains invalid characters.
        """
        if not sequence:
            raise ValueError("sequence must not be empty")
        invalid = set(sequence) - {"M", "S"}
        if invalid:
            raise ValueError(f"Invalid sequence characters: {invalid!r}")

        steps: List[TransformationResult] = []
        rm_trace: List[str] = []
        magnify_count = 0
        simplify_count = 0

        current_text = text
        for op in sequence:
            if op == "M":
                result = self._controller.magnify(current_text, context)
                magnify_count += 1
            else:
                result = self._controller.simplify(current_text, context)
                simplify_count += 1
            steps.append(result)
            rm_trace.append(result.target_rm)
            current_text = _describe_output(result.output)

        # Always finish with solidify
        final_result = self._controller.solidify(current_text, context)
        rm_trace.append(final_result.target_rm)

        # Build counts from final output
        final_output = final_result.output
        component_count = len(final_output.get("technical_components", []))
        data_flow_count = len(
            final_output.get("architecture_mapping", {}).get("data_flows", [])
        )
        has_simulation = final_result.simulation is not None
        governance_status = final_result.governance_status

        ratio = (
            float(magnify_count) / simplify_count
            if simplify_count > 0
            else float("inf")
        )

        seq_result = SequenceResult(
            sequence=sequence,
            steps=steps,
            final_result=final_result,
            rm_trace=rm_trace,
            magnify_count=magnify_count,
            simplify_count=simplify_count,
            ratio=ratio,
            component_count=component_count,
            data_flow_count=data_flow_count,
            has_simulation=has_simulation,
            governance_status=governance_status,
        )
        seq_result.composite_score = self.score_result(seq_result)
        return seq_result

    def score_result(self, result: SequenceResult) -> float:
        """Compute the composite score for a :class:`SequenceResult`.

        Weighted scoring formula::

            resolution_score   × 0.25
            + density_score    × 0.20
            + coherence_score  × 0.15
            + risk_score       × 0.15
            + governance_score × 0.10
            + efficiency_score × 0.15

        Returns:
            A float in the range 0.0–1.0.
        """
        if result.final_result is None:
            return 0.0

        out_quality = result.final_result.output_quality

        # resolution_score is in 0–6; normalise to 0–1
        resolution_score = min(out_quality.resolution_score / 6.0, 1.0)

        # density_score is in 0–1 already
        density_score = min(out_quality.density_index, 1.0)

        # coherence delta: improvement between input and output quality
        in_quality = result.final_result.input_quality
        raw_delta = out_quality.coherence_score - in_quality.coherence_score
        max_range = 6.0
        coherence_score = min(max((raw_delta + max_range) / (2 * max_range), 0.0), 1.0)

        # risk_score: lower simulation score is better risk profile
        if result.final_result.simulation is not None:
            sim_overall = result.final_result.simulation.overall_score
            # overall_score in 0–6; invert so lower risk = higher score
            risk_score = max(0.0, 1.0 - (sim_overall / 6.0))
        else:
            risk_score = 0.5  # neutral when no simulation data

        # governance_score
        gov = result.governance_status.lower()
        if gov == "approved":
            governance_score = 1.0
        elif gov == "conditional":
            governance_score = 0.5
        else:
            governance_score = 0.0

        # efficiency_score: composite quality per total operations
        total_operations = result.magnify_count + result.simplify_count + 1  # +1 for solidify
        raw_composite = out_quality.cqi  # in 0–6
        efficiency_score = min((raw_composite / 6.0) / (total_operations or 1), 1.0)

        composite = (
            resolution_score * 0.25
            + density_score * 0.20
            + coherence_score * 0.15
            + risk_score * 0.15
            + governance_score * 0.10
            + efficiency_score * 0.15
        )
        return round(min(max(composite, 0.0), 1.0), 6)

    def run_test_battery(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[SequenceResult]:
        """Run all test battery sequences, score and return them.

        Args:
            text: Input text for every sequence run.
            context: Optional context dictionary.

        Returns:
            List of :class:`SequenceResult` instances, sorted by
            composite_score descending.
        """
        results: List[SequenceResult] = []
        for seq in TEST_BATTERY_SEQUENCES:
            try:
                result = self.run_sequence(text, seq, context)
                results.append(result)
            except Exception as exc:
                logger.warning("Sequence %r failed: %s", seq, exc)
        return self.get_rankings(results)

    def get_rankings(self, results: List[SequenceResult]) -> List[SequenceResult]:
        """Sort *results* by composite_score descending.

        Args:
            results: List of :class:`SequenceResult` to rank.

        Returns:
            A new list sorted best-first.
        """
        return sorted(results, key=lambda r: r.composite_score, reverse=True)

    def get_optimal_sequence(self, results: List[SequenceResult]) -> str:
        """Return the winning sequence string from a ranked list.

        Args:
            results: List of :class:`SequenceResult`, already ranked or not.

        Returns:
            The sequence string of the highest-scoring result, or
            :data:`OPTIMAL_SEQUENCE` if *results* is empty.
        """
        if not results:
            return OPTIMAL_SEQUENCE
        ranked = self.get_rankings(results)
        return ranked[0].sequence

    def generate_report(self, results: List[SequenceResult]) -> Dict[str, Any]:
        """Generate a full analysis report from a list of results.

        Args:
            results: List of :class:`SequenceResult` to analyse.

        Returns:
            A dictionary with keys: ``winner``, ``top_5``, ``best_ratio``,
            ``best_family``, ``efficiency_winner``, ``diminishing_returns``.
        """
        if not results:
            return {
                "winner": OPTIMAL_SEQUENCE,
                "top_5": [],
                "best_ratio": None,
                "best_family": None,
                "efficiency_winner": None,
                "diminishing_returns": {},
            }

        ranked = self.get_rankings(results)
        winner = ranked[0]
        top_5 = ranked[:5]

        # Best ratio band: group by M:S ratio (rounded to 1 dp)
        ratio_groups: Dict[str, List[SequenceResult]] = {}
        for r in results:
            key = f"{r.ratio:.1f}" if r.ratio != float("inf") else "inf"
            ratio_groups.setdefault(key, []).append(r)
        best_ratio = max(
            ratio_groups,
            key=lambda k: max(r.composite_score for r in ratio_groups[k]),
        )

        # Best family: group by first character pattern
        family_groups: Dict[str, List[SequenceResult]] = {}
        for r in results:
            if r.magnify_count > 0 and r.simplify_count > 0:
                first_s = r.sequence.index("S") if "S" in r.sequence else len(r.sequence)
                first_s_pct = first_s / (len(r.sequence) or 1)
                if first_s_pct < 0.4:
                    family = "back_loaded"
                elif first_s_pct < 0.7:
                    family = "balanced"
                else:
                    family = "front_loaded"
            elif r.magnify_count > 0:
                family = "pure_magnify"
            else:
                family = "pure_simplify"
            family_groups.setdefault(family, []).append(r)

        best_family = max(
            family_groups,
            key=lambda k: max(r.composite_score for r in family_groups[k]),
        )

        # Efficiency winner: highest score per operation count
        def _efficiency(r: SequenceResult) -> float:
            ops = r.magnify_count + r.simplify_count + 1
            return r.composite_score / (ops or 1)

        efficiency_winner_result = max(results, key=_efficiency)

        # Diminishing returns analysis: score per added operation
        by_length: Dict[int, List[SequenceResult]] = {}
        for r in results:
            length = len(r.sequence)
            by_length.setdefault(length, []).append(r)

        diminishing_returns: Dict[str, Any] = {}
        for length in sorted(by_length):
            best_at_length = max(by_length[length], key=lambda r: r.composite_score)
            diminishing_returns[str(length)] = {
                "best_score": best_at_length.composite_score,
                "best_sequence": best_at_length.sequence,
            }

        return {
            "winner": winner.sequence,
            "winner_score": winner.composite_score,
            "top_5": [
                {
                    "sequence": r.sequence,
                    "score": r.composite_score,
                    "ratio": r.ratio,
                    "magnify_count": r.magnify_count,
                    "simplify_count": r.simplify_count,
                }
                for r in top_5
            ],
            "best_ratio": best_ratio,
            "best_family": best_family,
            "efficiency_winner": efficiency_winner_result.sequence,
            "diminishing_returns": diminishing_returns,
        }
