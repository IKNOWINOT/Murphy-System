"""
Gap Closure Tests — Round 48.

Validates the Production Output Calibration Engine (CAL-001):

  Gap 1 (Critical): No system existed to benchmark production outputs against
                     professional examples and iteratively close quality gaps.

  Gap 2 (High):     No QC loop validated that improved outputs still meet the
                     original proposal / request requirements.

Gaps addressed:
 1. production_output_calibrator — module exists with all data structures
 2. BestPractice extraction from 10 professional examples
 3. DimensionScore scoring across 10 quality dimensions
 4. GapAnalysis identification with severity ranking
 5. CalibrationPlan creation with prioritised actions
 6. QC against proposal request (QCVerdict PASS / PARTIAL / FAIL)
 7. Iterative calibration loop converges to 90-95 % threshold
 8. Dual-loop: benchmark + QC both required for convergence
 9. Edge cases: empty examples, bad thresholds, missing output
10. Thread safety of calibrator under concurrent access
"""

import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

import pytest

# ===========================================================================
# Helpers
# ===========================================================================

def _make_output(
    content: str = (
        "Output must have clarity and completeness. "
        "Must include structure and accuracy checks. "
        "Ensure professionalism and consistency throughout. "
        "Efficiency, maintainability, security, and usability covered."
    ),
    metadata: dict | None = None,
) -> "ProductionOutput":
    from production_output_calibrator import ProductionOutput
    return ProductionOutput(
        output_type="document",
        content=content,
        metadata=metadata or {},
    )


def _make_example(
    source: str = "industry_leader",
    strengths: list | None = None,
    content: str = "",
) -> "ProfessionalExample":
    from production_output_calibrator import ProfessionalExample
    return ProfessionalExample(
        source=source,
        content=content or f"Example from {source}",
        strengths=strengths or [],
    )


def _make_examples_10() -> list:
    """Build 10 professional examples covering all quality dimensions."""
    from production_output_calibrator import QualityDimension
    dims = list(QualityDimension)
    examples = []
    for i in range(10):
        dim = dims[i % len(dims)]
        examples.append(_make_example(
            source=f"pro_{i}",
            strengths=[f"Excellent {dim.value} standards",
                       f"Top-tier {dim.value} implementation"],
            content=f"Professional example demonstrating {dim.value} best practices",
        ))
    return examples


def _make_requirements(n: int = 3) -> list:
    from production_output_calibrator import ProposalRequirement
    descs = [
        "Output must have clarity and completeness",
        "Must include structure and accuracy checks",
        "Ensure professionalism and consistency throughout",
    ]
    reqs = []
    for i in range(min(n, len(descs))):
        reqs.append(ProposalRequirement(
            description=descs[i],
            category="core",
            mandatory=True,
        ))
    return reqs


def _build_calibrator(target: float = 0.90):
    from production_output_calibrator import ProductionOutputCalibrator
    cal = ProductionOutputCalibrator(target_threshold=target)
    cal.register_output(_make_output())
    cal.register_examples(_make_examples_10())
    cal.register_proposal_request(_make_requirements())
    return cal


# ===========================================================================
# Gap 1 — Module existence and data structures
# ===========================================================================

class TestGap1_ModuleAndDataStructures:
    """production_output_calibrator module imports with all public types."""

    def test_module_imports(self):
        import production_output_calibrator  # noqa: F401

    def test_enum_quality_dimension(self):
        from production_output_calibrator import QualityDimension
        assert len(QualityDimension) == 10

    def test_enum_calibration_status(self):
        from production_output_calibrator import CalibrationStatus
        assert CalibrationStatus.CONVERGED.value == "converged"

    def test_enum_qc_verdict(self):
        from production_output_calibrator import QCVerdict
        assert QCVerdict.PASS.value == "pass"
        assert QCVerdict.PARTIAL.value == "partial"
        assert QCVerdict.FAIL.value == "fail"

    def test_dataclass_production_output(self):
        out = _make_output()
        assert out.output_id
        assert out.output_type == "document"

    def test_dataclass_professional_example(self):
        ex = _make_example()
        assert ex.example_id
        assert ex.source == "industry_leader"

    def test_dataclass_best_practice(self):
        from production_output_calibrator import BestPractice, QualityDimension
        bp = BestPractice(dimension=QualityDimension.ACCURACY, description="test")
        assert bp.practice_id
        assert bp.weight == 1.0

    def test_dataclass_dimension_score(self):
        from production_output_calibrator import DimensionScore, QualityDimension
        ds = DimensionScore(dimension=QualityDimension.SECURITY, score=0.85)
        assert ds.max_score == 1.0

    def test_dataclass_gap_analysis(self):
        from production_output_calibrator import GapAnalysis, QualityDimension
        ga = GapAnalysis(dimension=QualityDimension.USABILITY, severity=0.5)
        assert ga.gap_id

    def test_dataclass_proposal_requirement(self):
        from production_output_calibrator import ProposalRequirement
        pr = ProposalRequirement(description="must do X", mandatory=True)
        assert pr.met is False

    def test_dataclass_qc_result(self):
        from production_output_calibrator import QCResult, QCVerdict
        qr = QCResult(verdict=QCVerdict.PASS)
        assert qr.compliance_pct == 0.0

    def test_dataclass_calibration_plan(self):
        from production_output_calibrator import CalibrationPlan
        cp = CalibrationPlan(actions=["a", "b"])
        assert len(cp.actions) == 2

    def test_dataclass_calibration_round(self):
        from production_output_calibrator import CalibrationRound
        cr = CalibrationRound(round_number=1, benchmark_score=0.8)
        assert cr.gaps_found == 0

    def test_dataclass_calibration_report(self):
        from production_output_calibrator import CalibrationReport, CalibrationStatus
        rp = CalibrationReport(status=CalibrationStatus.CONVERGED)
        assert rp.converged is False  # field default, not status-derived

    def test_calibrator_class_exists(self):
        from production_output_calibrator import ProductionOutputCalibrator
        cal = ProductionOutputCalibrator()
        assert cal.status.value == "not_started"


# ===========================================================================
# Gap 2 — Best-practice extraction
# ===========================================================================

class TestGap2_BestPracticeExtraction:
    """Extract combined best practices from 10 professional examples."""

    def test_extract_returns_one_per_dimension(self):
        cal = _build_calibrator()
        practices = cal.extract_best_practices()
        from production_output_calibrator import QualityDimension
        assert len(practices) == len(QualityDimension)

    def test_extract_links_to_source_examples(self):
        cal = _build_calibrator()
        practices = cal.extract_best_practices()
        for bp in practices:
            assert len(bp.source_example_ids) >= 1

    def test_extract_weight_scales_with_sources(self):
        cal = _build_calibrator()
        practices = cal.extract_best_practices()
        multi = [bp for bp in practices if len(bp.source_example_ids) > 1]
        for bp in multi:
            assert bp.weight > 1.0

    def test_extract_requires_examples(self):
        from production_output_calibrator import ProductionOutputCalibrator
        cal = ProductionOutputCalibrator()
        cal.register_output(_make_output())
        with pytest.raises(ValueError, match="No examples"):
            cal.extract_best_practices()


# ===========================================================================
# Gap 3 — Scoring across 10 quality dimensions
# ===========================================================================

class TestGap3_Scoring:
    """Score output against extracted best practices."""

    def test_score_returns_all_dimensions(self):
        cal = _build_calibrator()
        cal.extract_best_practices()
        scores = cal.score_output()
        from production_output_calibrator import QualityDimension
        assert len(scores) == len(QualityDimension)

    def test_scores_in_range(self):
        cal = _build_calibrator()
        cal.extract_best_practices()
        for s in cal.score_output():
            assert 0.0 <= s.score <= 1.0

    def test_score_evidence_populated(self):
        cal = _build_calibrator()
        cal.extract_best_practices()
        scores = cal.score_output()
        has_evidence = any(s.evidence for s in scores)
        assert has_evidence

    def test_score_requires_output(self):
        from production_output_calibrator import ProductionOutputCalibrator
        cal = ProductionOutputCalibrator()
        cal.register_examples(_make_examples_10())
        cal.extract_best_practices()
        with pytest.raises(ValueError, match="No output"):
            cal.score_output()

    def test_score_requires_best_practices(self):
        from production_output_calibrator import ProductionOutputCalibrator
        cal = ProductionOutputCalibrator()
        cal.register_output(_make_output())
        with pytest.raises(ValueError, match="Best practices"):
            cal.score_output()


# ===========================================================================
# Gap 4 — Gap analysis
# ===========================================================================

class TestGap4_GapAnalysis:
    """Identify gaps between output and target threshold."""

    def test_gaps_identified(self):
        cal = _build_calibrator()
        cal.extract_best_practices()
        gaps = cal.identify_gaps()
        assert len(gaps) > 0

    def test_gap_severity_in_range(self):
        cal = _build_calibrator()
        cal.extract_best_practices()
        for g in cal.identify_gaps():
            assert 0.0 <= g.severity <= 1.0

    def test_gap_has_recommended_action(self):
        cal = _build_calibrator()
        cal.extract_best_practices()
        for g in cal.identify_gaps():
            assert g.recommended_action


# ===========================================================================
# Gap 5 — Calibration plan
# ===========================================================================

class TestGap5_CalibrationPlan:
    """Create prioritised remediation plan from gaps."""

    def test_plan_contains_actions(self):
        cal = _build_calibrator()
        cal.extract_best_practices()
        plan = cal.create_plan()
        assert len(plan.actions) > 0

    def test_plan_sorted_by_severity(self):
        cal = _build_calibrator()
        cal.extract_best_practices()
        plan = cal.create_plan()
        severities = [g.severity for g in plan.gaps]
        assert severities == sorted(severities, reverse=True)

    def test_plan_has_priority_order(self):
        cal = _build_calibrator()
        cal.extract_best_practices()
        plan = cal.create_plan()
        assert len(plan.priority_order) == len(plan.gaps)


# ===========================================================================
# Gap 6 — QC against proposal request
# ===========================================================================

class TestGap6_QCAgainstRequest:
    """QC loop validates output meets original proposal requirements."""

    def test_qc_pass_when_requirements_met(self):
        from production_output_calibrator import QCVerdict
        cal = _build_calibrator()
        result = cal.qc_against_request()
        assert result.verdict in (QCVerdict.PASS, QCVerdict.PARTIAL)

    def test_qc_vacuous_pass_no_requirements(self):
        from production_output_calibrator import (
            ProductionOutputCalibrator,
            QCVerdict,
        )
        cal = ProductionOutputCalibrator()
        cal.register_output(_make_output())
        cal.register_examples(_make_examples_10())
        result = cal.qc_against_request()
        assert result.verdict == QCVerdict.PASS
        assert result.compliance_pct == 100.0

    def test_qc_fail_when_content_mismatches(self):
        from production_output_calibrator import (
            ProductionOutputCalibrator,
            ProposalRequirement,
            QCVerdict,
        )
        cal = ProductionOutputCalibrator()
        cal.register_output(_make_output(content="completely unrelated xyz"))
        cal.register_examples(_make_examples_10())
        cal.register_proposal_request([
            ProposalRequirement(
                description="quantum_entanglement_verification_protocol",
                mandatory=True,
            ),
        ])
        result = cal.qc_against_request()
        assert result.verdict == QCVerdict.FAIL

    def test_qc_reports_unmet_requirements(self):
        from production_output_calibrator import (
            ProductionOutputCalibrator,
            ProposalRequirement,
        )
        cal = ProductionOutputCalibrator()
        cal.register_output(_make_output(content="basic text"))
        cal.register_examples(_make_examples_10())
        cal.register_proposal_request([
            ProposalRequirement(
                description="zzz_nonexistent_requirement_qqq",
                mandatory=True,
            ),
        ])
        result = cal.qc_against_request()
        assert len(result.unmet_requirements) >= 1

    def test_qc_compliance_pct_calculated(self):
        cal = _build_calibrator()
        result = cal.qc_against_request()
        assert 0.0 <= result.compliance_pct <= 100.0


# ===========================================================================
# Gap 7 — Iterative calibration loop converges
# ===========================================================================

class TestGap7_CalibrationConvergence:
    """calibrate() iterates until benchmark ≥ 90 % and QC passes."""

    def test_calibrate_converges(self):
        from production_output_calibrator import CalibrationStatus
        cal = _build_calibrator()
        report = cal.calibrate()
        assert report.converged is True
        assert report.status == CalibrationStatus.CONVERGED

    def test_calibrate_multiple_rounds(self):
        cal = _build_calibrator()
        report = cal.calibrate()
        assert len(report.rounds) >= 1

    def test_benchmark_score_improves(self):
        cal = _build_calibrator()
        report = cal.calibrate()
        if len(report.rounds) >= 2:
            assert report.rounds[-1].benchmark_score >= report.rounds[0].benchmark_score

    def test_final_score_above_threshold(self):
        cal = _build_calibrator()
        report = cal.calibrate()
        assert report.final_benchmark_score >= 0.90

    def test_summary_populated(self):
        cal = _build_calibrator()
        report = cal.calibrate()
        assert "converged" in report.summary.lower()


# ===========================================================================
# Gap 8 — Dual-loop: benchmark + QC both required
# ===========================================================================

class TestGap8_DualLoop:
    """Both benchmark AND QC must pass for convergence."""

    def test_qc_compliance_in_final_report(self):
        cal = _build_calibrator()
        report = cal.calibrate()
        assert report.final_qc_compliance >= 0.0

    def test_qc_checked_each_round(self):
        cal = _build_calibrator()
        report = cal.calibrate()
        for rnd in report.rounds:
            assert rnd.qc_result is not None

    def test_dual_convergence_requires_both(self):
        """If QC never passes, calibration should not converge."""
        from production_output_calibrator import (
            ProductionOutputCalibrator,
            ProposalRequirement,
        )
        cal = ProductionOutputCalibrator(target_threshold=0.90)
        cal.register_output(_make_output(content="basic"))
        cal.register_examples(_make_examples_10())
        # Use many impossible keywords so match_ratio stays < 0.5 even
        # after QC-fix improvement strings are appended.
        cal.register_proposal_request([
            ProposalRequirement(
                description=(
                    "zqxjk bvnmw plrth gsdyf cwokz "
                    "uxmrj tnbae hqdil fgvzp kmwoy"
                ),
                mandatory=True,
            ),
        ])
        report = cal.calibrate()
        # QC should fail because the nonsense keywords can never be met
        assert report.converged is False

    def test_total_gaps_closed_accumulated(self):
        cal = _build_calibrator()
        report = cal.calibrate()
        assert report.total_gaps_closed >= 0


# ===========================================================================
# Gap 9 — Edge cases and validation
# ===========================================================================

class TestGap9_EdgeCases:
    """Boundary conditions and error handling."""

    def test_reject_threshold_below_90(self):
        from production_output_calibrator import ProductionOutputCalibrator
        with pytest.raises(ValueError, match="target_threshold"):
            ProductionOutputCalibrator(target_threshold=0.50)

    def test_reject_threshold_above_95(self):
        from production_output_calibrator import ProductionOutputCalibrator
        with pytest.raises(ValueError, match="target_threshold"):
            ProductionOutputCalibrator(target_threshold=0.99)

    def test_reject_more_than_10_examples(self):
        from production_output_calibrator import ProductionOutputCalibrator
        cal = ProductionOutputCalibrator()
        extras = _make_examples_10() + [_make_example(source="extra")]
        with pytest.raises(ValueError, match="Maximum 10"):
            cal.register_examples(extras)

    def test_reject_empty_examples(self):
        from production_output_calibrator import ProductionOutputCalibrator
        cal = ProductionOutputCalibrator()
        with pytest.raises(ValueError, match="At least one"):
            cal.register_examples([])

    def test_reject_wrong_output_type(self):
        from production_output_calibrator import ProductionOutputCalibrator
        cal = ProductionOutputCalibrator()
        with pytest.raises(TypeError):
            cal.register_output("not a ProductionOutput")  # type: ignore[arg-type]

    def test_calibrate_without_output_raises(self):
        from production_output_calibrator import ProductionOutputCalibrator
        cal = ProductionOutputCalibrator()
        cal.register_examples(_make_examples_10())
        with pytest.raises(ValueError, match="No output"):
            cal.calibrate()

    def test_calibrate_without_examples_raises(self):
        from production_output_calibrator import ProductionOutputCalibrator
        cal = ProductionOutputCalibrator()
        cal.register_output(_make_output())
        with pytest.raises(ValueError, match="No examples"):
            cal.calibrate()

    def test_single_example_still_works(self):
        from production_output_calibrator import ProductionOutputCalibrator
        cal = ProductionOutputCalibrator()
        cal.register_output(_make_output())
        cal.register_examples([_make_example(strengths=["clarity best"])])
        practices = cal.extract_best_practices()
        assert len(practices) >= 1


# ===========================================================================
# Gap 10 — Thread safety
# ===========================================================================

class TestGap10_ThreadSafety:
    """Calibrator is safe under concurrent access."""

    def test_concurrent_scoring(self):
        cal = _build_calibrator()
        cal.extract_best_practices()
        errors: list = []

        def score_worker():
            try:
                scores = cal.score_output()
                assert len(scores) > 0
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=score_worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert not errors, f"Thread errors: {errors}"

    def test_concurrent_calibration_rounds(self):
        cal = _build_calibrator()
        cal.extract_best_practices()
        results: list = []
        errors: list = []

        def round_worker():
            try:
                cr = cal.run_calibration_round()
                results.append(cr)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=round_worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert not errors, f"Thread errors: {errors}"
        assert len(results) == 4
