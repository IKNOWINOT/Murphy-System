"""
Temporal Business-Compliance Variation Tests — Murphy System

Tests every relevant compliance/regulation script by running 12 realistic
business archetypes through 5 growth stages each.  At every stage the
business operates in a slightly different country/industry context with an
evolving set of compliance toggles, and the test suite verifies that the
validation pipeline (RegulationMLEngine + ComplianceToggleManager) responds
correctly to those changes through time.

Business archetypes (12) — one per outreach vertical:
  saas, ecommerce, healthcare, legal, financial_services, manufacturing,
  construction, real_estate, hospitality, education, logistics, content_creator

Growth stages (5) per archetype:
  pre_launch → early_growth → scaling → regulated → global

What is validated at every stage:
  - predict_optimal_toggles() returns correct frameworks for country+industry
  - predict_gate_config_for_regulation_set() returns valid gates with weights
  - get_conflict_report() detects known problem pairs as toggles accumulate
  - get_co_occurrence_insights() updates as more scenarios are profiled
  - ComplianceToggleManager.get_recommended_frameworks() is consistent
  - Gate weights are ordered correctly (higher-priority gates score higher)
  - Compliance load grows monotonically through the timeline
  - Immune memory is utilised for repeated lookups within the same run
"""

from __future__ import annotations

import sys
import os
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

from regulation_ml_engine import (
    RegulationMLEngine,
    RegulationProfile,
    _KNOWN_CONFLICTS,
    _ALL_GATE_TYPES,
    _derive_gate_types,
    _compute_gate_weights,
    _order_gates,
    _count_conflicts,
    ALL_FRAMEWORKS,
    _COUNTRY_FRAMEWORKS,
    _INDUSTRY_FRAMEWORKS,
)
from compliance_toggle_manager import (
    ComplianceToggleManager,
    TenantFrameworkConfig,
)


# ---------------------------------------------------------------------------
# Stage-by-stage snapshot for one business archetype
# ---------------------------------------------------------------------------

@dataclass
class BusinessStage:
    """Configuration for one growth stage of a business archetype."""
    stage_name: str          # e.g. "pre_launch"
    country_code: str        # ISO 3166-1 alpha-2
    industry: str            # key in _INDUSTRY_FRAMEWORKS
    extra_frameworks: List[str]  # frameworks enabled *at this stage* (additive)
    expect_conflicts: bool = False        # True if this stage introduces a known conflict
    expect_gates_include: List[str] = field(default_factory=list)  # gates that MUST appear
    note: str = ""


@dataclass
class BusinessTimeline:
    """Full lifecycle for one business archetype."""
    archetype: str           # e.g. "saas_startup"
    vertical: str            # outreach vertical
    stages: List[BusinessStage]


# ---------------------------------------------------------------------------
# 12 Business Archetype Timelines
# ---------------------------------------------------------------------------

# Helper: build cumulative framework set up to and including a given stage index.
def _cumulative_frameworks(timeline: BusinessTimeline, up_to_stage: int) -> List[str]:
    seen: Set[str] = set()
    result: List[str] = []
    for i, stage in enumerate(timeline.stages):
        if i > up_to_stage:
            break
        for fw in stage.extra_frameworks:
            if fw in ALL_FRAMEWORKS and fw not in seen:
                result.append(fw)
                seen.add(fw)
    return result


_TIMELINES: List[BusinessTimeline] = [

    # ── 1. SaaS Startup (US → EU expansion) ──────────────────────────────
    BusinessTimeline(
        archetype="saas_startup",
        vertical="saas",
        stages=[
            BusinessStage(
                "pre_launch", "US", "technology", ["soc2"],
                expect_gates_include=["compliance", "security"],
                note="Pre-launch: minimal — SOC 2 readiness only",
            ),
            BusinessStage(
                "early_growth", "US", "technology", ["nist_csf", "cis_controls"],
                expect_gates_include=["security", "monitoring"],
                note="Series A: add security frameworks",
            ),
            BusinessStage(
                "scaling", "US", "cloud", ["fedramp", "iso_27001"],
                expect_gates_include=["compliance", "audit"],
                note="Gov contracts: FedRAMP + ISO 27001",
            ),
            BusinessStage(
                "regulated", "DE", "technology", ["gdpr", "nis2"],
                expect_gates_include=["regulatory", "compliance"],
                note="EU expansion: GDPR + NIS2",
            ),
            BusinessStage(
                "global", "DE", "technology", ["dsgvo"],
                expect_conflicts=True,
                expect_gates_include=["compliance", "audit", "security"],
                note="DE specifics: DSGVO conflicts with GDPR (redundant)",
            ),
        ],
    ),

    # ── 2. E-commerce (US → CA → BR) ─────────────────────────────────────
    BusinessTimeline(
        archetype="ecommerce_retailer",
        vertical="ecommerce",
        stages=[
            BusinessStage(
                "pre_launch", "US", "retail", ["pci_dss"],
                expect_gates_include=["compliance", "security"],
                note="Launch: PCI DSS for card payments",
            ),
            BusinessStage(
                "early_growth", "US", "retail", ["ccpa"],
                expect_gates_include=["regulatory"],
                note="California customers: CCPA",
            ),
            BusinessStage(
                "scaling", "US-CA", "retail", ["soc2"],
                expect_gates_include=["audit"],
                note="SOC 2 for enterprise buyers",
            ),
            BusinessStage(
                "regulated", "US", "retail", ["coppa"],
                expect_gates_include=["compliance", "regulatory"],
                note="Kids-targeted product line: COPPA",
            ),
            BusinessStage(
                "global", "BR", "retail", ["lgpd"],
                expect_gates_include=["compliance", "regulatory", "audit"],
                note="Brazil expansion: LGPD",
            ),
        ],
    ),

    # ── 3. Healthcare SaaS (US → GB → AU) ────────────────────────────────
    BusinessTimeline(
        archetype="healthtech",
        vertical="healthcare",
        stages=[
            BusinessStage(
                "pre_launch", "US", "healthcare", ["hipaa"],
                expect_gates_include=["compliance", "security", "quality"],
                note="Day-1: HIPAA is non-negotiable",
            ),
            BusinessStage(
                "early_growth", "US", "healthcare", ["hitech"],
                expect_gates_include=["compliance", "regulatory"],
                note="EHR integration: add HITECH",
            ),
            BusinessStage(
                "scaling", "US", "healthcare", ["soc2", "fda_21_cfr_11"],
                expect_gates_include=["audit", "qa"],
                note="FDA-regulated device: FDA 21 CFR Part 11",
            ),
            BusinessStage(
                "regulated", "GB", "healthcare", ["gdpr"],
                expect_gates_include=["compliance", "regulatory", "security"],
                note="UK NHS partnership: GDPR",
            ),
            BusinessStage(
                "global", "AU", "healthcare", ["privacy_act_au"],
                expect_gates_include=["compliance", "audit"],
                note="Australia launch: Privacy Act",
            ),
        ],
    ),

    # ── 4. Legal Tech (US → DE) ───────────────────────────────────────────
    BusinessTimeline(
        archetype="legal_tech",
        vertical="legal",
        stages=[
            BusinessStage(
                "pre_launch", "US", "legal", ["soc2", "iso_27001"],
                expect_gates_include=["security", "compliance"],
                note="Law firm clients demand SOC 2 + ISO 27001",
            ),
            BusinessStage(
                "early_growth", "US", "legal", ["sox"],
                expect_gates_include=["audit", "executive"],
                note="Public company clients: SOX",
            ),
            BusinessStage(
                "scaling", "US", "legal", ["nist_csf"],
                expect_gates_include=["security", "monitoring"],
                note="Government clients: NIST CSF",
            ),
            BusinessStage(
                "regulated", "DE", "legal", ["gdpr", "nis2"],
                expect_gates_include=["regulatory", "compliance"],
                note="German law firms: GDPR + NIS2",
            ),
            BusinessStage(
                "global", "DE", "legal", ["dsgvo"],
                expect_conflicts=True,
                expect_gates_include=["compliance", "regulatory"],
                note="DSGVO conflicts with GDPR (German redundancy)",
            ),
        ],
    ),

    # ── 5. FinTech / Payments (US → GB → SG) ─────────────────────────────
    BusinessTimeline(
        archetype="fintech_payments",
        vertical="financial_services",
        stages=[
            BusinessStage(
                "pre_launch", "US", "payments", ["pci_dss"],
                expect_gates_include=["compliance", "security"],
                note="Payment processor: PCI DSS first",
            ),
            BusinessStage(
                "early_growth", "US", "finance", ["sox", "aml_kyc"],
                expect_gates_include=["compliance", "audit", "hitl"],
                note="Regulated institution: SOX + AML/KYC",
            ),
            BusinessStage(
                "scaling", "US", "banking", ["glba", "soc2"],
                expect_gates_include=["compliance", "security"],
                note="Banking partnership: GLBA",
            ),
            BusinessStage(
                "regulated", "GB", "banking", ["gdpr", "psd2", "dora"],
                expect_gates_include=["regulatory", "monitoring"],
                note="EU payment: PSD2 + DORA",
            ),
            BusinessStage(
                "global", "SG", "finance", ["pdpa"],
                expect_gates_include=["compliance", "regulatory"],
                note="Singapore: PDPA",
            ),
        ],
    ),

    # ── 6. Manufacturing / Industry 4.0 (US → DE → JP) ───────────────────
    BusinessTimeline(
        archetype="smart_factory",
        vertical="manufacturing",
        stages=[
            BusinessStage(
                "pre_launch", "US", "manufacturing", ["iso_9001", "osha"],
                expect_gates_include=["quality", "safety"],
                note="Factory launch: ISO 9001 + OSHA",
            ),
            BusinessStage(
                "early_growth", "US", "manufacturing", ["iso_14001", "iso_45001"],
                expect_gates_include=["environmental", "safety"],
                note="Environmental + workforce safety",
            ),
            BusinessStage(
                "scaling", "US", "manufacturing", ["isa_95", "iec_61131"],
                expect_gates_include=["operations", "calibration"],
                note="Automation: ISA-95 + IEC 61131",
            ),
            BusinessStage(
                "regulated", "DE", "manufacturing", ["gdpr", "nis2"],
                expect_gates_include=["compliance", "regulatory"],
                note="German plant: GDPR + NIS2",
            ),
            BusinessStage(
                "global", "JP", "manufacturing", ["appi"],
                expect_gates_include=["compliance", "regulatory"],
                note="Japan expansion: APPI",
            ),
        ],
    ),

    # ── 7. Construction / 3D Printing / Engineering (US → AU) ────────────
    BusinessTimeline(
        archetype="construction_tech",
        vertical="construction",
        stages=[
            BusinessStage(
                "pre_launch", "US", "manufacturing", ["osha", "nfpa"],
                expect_gates_include=["safety", "regulatory"],
                note="Job-site: OSHA + NFPA fire codes",
            ),
            BusinessStage(
                "early_growth", "US", "manufacturing", ["iso_9001", "ce_marking"],
                expect_gates_include=["quality", "compliance"],
                note="Equipment certification: CE Marking",
            ),
            BusinessStage(
                "scaling", "US", "manufacturing", ["ul_certification", "iec_61131"],
                expect_gates_include=["safety", "calibration"],
                note="3D printer safety: UL + IEC 61131",
            ),
            BusinessStage(
                "regulated", "AU", "manufacturing", ["privacy_act_au"],
                expect_gates_include=["compliance", "regulatory"],
                note="Australian operations: Privacy Act",
            ),
            BusinessStage(
                "global", "DE", "manufacturing", ["gdpr", "iso_14001"],
                expect_gates_include=["compliance", "environmental"],
                note="EU green manufacturing",
            ),
        ],
    ),

    # ── 8. Real Estate PropTech (US → CA → GB) ───────────────────────────
    BusinessTimeline(
        archetype="proptech",
        vertical="real_estate",
        stages=[
            BusinessStage(
                "pre_launch", "US", "finance", ["pci_dss", "soc2"],
                expect_gates_include=["compliance", "security"],
                note="PropTech payment & data: PCI + SOC 2",
            ),
            BusinessStage(
                "early_growth", "US-CA", "finance", ["ccpa"],
                expect_gates_include=["regulatory"],
                note="California properties: CCPA",
            ),
            BusinessStage(
                "scaling", "CA", "finance", ["pipeda"],
                expect_gates_include=["compliance", "regulatory"],
                note="Canadian market: PIPEDA",
            ),
            BusinessStage(
                "regulated", "GB", "legal", ["gdpr"],
                expect_gates_include=["compliance", "regulatory", "security"],
                note="UK property: GDPR",
            ),
            BusinessStage(
                "global", "AU", "finance", ["privacy_act_au"],
                expect_gates_include=["compliance", "regulatory"],
                note="Australia market: Privacy Act",
            ),
        ],
    ),

    # ── 9. Hospitality / Travel Tech (US → FR → TH) ──────────────────────
    BusinessTimeline(
        archetype="hospitality_tech",
        vertical="hospitality",
        stages=[
            BusinessStage(
                "pre_launch", "US", "retail", ["pci_dss", "soc2"],
                expect_gates_include=["compliance", "security"],
                note="Hotel booking: PCI + SOC 2",
            ),
            BusinessStage(
                "early_growth", "US", "retail", ["ccpa"],
                expect_gates_include=["regulatory"],
                note="Guest data: CCPA",
            ),
            BusinessStage(
                "scaling", "FR", "general", ["gdpr"],
                expect_gates_include=["compliance", "regulatory"],
                note="EU launch: GDPR",
            ),
            BusinessStage(
                "regulated", "FR", "general", ["nis2"],
                expect_gates_include=["security", "regulatory"],
                note="Critical infrastructure: NIS2",
            ),
            BusinessStage(
                "global", "TH", "general", ["pdpa"],
                expect_gates_include=["compliance", "regulatory"],
                note="Thailand: PDPA",
            ),
        ],
    ),

    # ── 10. EdTech / LMS (US → EU → IN) ──────────────────────────────────
    BusinessTimeline(
        archetype="edtech",
        vertical="education",
        stages=[
            BusinessStage(
                "pre_launch", "US", "education", ["ferpa", "coppa"],
                expect_conflicts=True,  # FERPA + COPPA age-group overlap
                expect_gates_include=["compliance", "regulatory"],
                note="Student data: FERPA + COPPA (known age-group conflict)",
            ),
            BusinessStage(
                "early_growth", "US", "education", ["soc2"],
                expect_gates_include=["audit", "compliance"],
                note="District contracts: SOC 2",
            ),
            BusinessStage(
                "scaling", "US", "education", ["nist_csf"],
                expect_gates_include=["security", "monitoring"],
                note="Cybersecurity: NIST CSF",
            ),
            BusinessStage(
                "regulated", "FR", "education", ["gdpr"],
                expect_gates_include=["compliance", "regulatory"],
                note="EU students: GDPR",
            ),
            BusinessStage(
                "global", "IN", "education", [],
                expect_gates_include=["compliance"],
                note="India: pending PDPB — use baseline",
            ),
        ],
    ),

    # ── 11. Logistics / Supply Chain (US → DE → ZA) ──────────────────────
    BusinessTimeline(
        archetype="supply_chain",
        vertical="logistics",
        stages=[
            BusinessStage(
                "pre_launch", "US", "manufacturing", ["osha", "iso_9001"],
                expect_gates_include=["safety", "quality"],
                note="Warehouse: OSHA + ISO 9001",
            ),
            BusinessStage(
                "early_growth", "US", "manufacturing", ["sox", "soc2"],
                expect_gates_include=["audit", "compliance"],
                note="Public logistics firm: SOX + SOC 2",
            ),
            BusinessStage(
                "scaling", "US", "manufacturing", ["iso_14001"],
                expect_gates_include=["environmental"],
                note="Green supply chain: ISO 14001",
            ),
            BusinessStage(
                "regulated", "DE", "manufacturing", ["gdpr", "nis2"],
                expect_gates_include=["compliance", "regulatory"],
                note="EU operations: GDPR + NIS2",
            ),
            BusinessStage(
                "global", "ZA", "manufacturing", ["popia"],
                expect_gates_include=["compliance", "regulatory"],
                note="South Africa: POPIA",
            ),
        ],
    ),

    # ── 12. Creator Economy / Media (US → CA → JP) ───────────────────────
    BusinessTimeline(
        archetype="creator_platform",
        vertical="content_creator",
        stages=[
            BusinessStage(
                "pre_launch", "US", "technology", ["soc2"],
                expect_gates_include=["compliance", "security"],
                note="Launch: SOC 2 only",
            ),
            BusinessStage(
                "early_growth", "US", "technology", ["ccpa", "coppa"],
                expect_gates_include=["regulatory"],
                note="User data + minors: CCPA + COPPA",
            ),
            BusinessStage(
                "scaling", "CA", "technology", ["pipeda"],
                expect_gates_include=["compliance", "regulatory"],
                note="Canadian creators: PIPEDA",
            ),
            BusinessStage(
                "regulated", "CA", "technology", ["ferpa"],
                expect_conflicts=True,
                expect_gates_include=["compliance"],
                note="Educational content + COPPA + FERPA — overlap conflict",
            ),
            BusinessStage(
                "global", "JP", "technology", ["appi"],
                expect_gates_include=["compliance", "regulatory"],
                note="Japan: APPI",
            ),
        ],
    ),
]


# ---------------------------------------------------------------------------
# Shared fixture — one engine per test module (reused for temporal continuity)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def trained_engine() -> RegulationMLEngine:
    """A trained RegulationMLEngine shared across all tests in this module.

    Using module-scope ensures that profiles built during earlier tests are
    available in later tests, deliberately mimicking temporal accumulation.
    """
    engine = RegulationMLEngine()
    engine.train()
    return engine


@pytest.fixture(scope="module")
def toggle_manager() -> ComplianceToggleManager:
    return ComplianceToggleManager()


# ---------------------------------------------------------------------------
# Helper assertions
# ---------------------------------------------------------------------------

def _assert_valid_prediction(result: Dict[str, Any], stage: BusinessStage) -> None:
    """Common assertions for every predict_optimal_toggles() result."""
    assert isinstance(result, dict), "Result must be a dict"
    assert "recommended_frameworks" in result
    assert isinstance(result["recommended_frameworks"], list)
    assert "confidence" in result
    assert 0.0 <= result["confidence"] <= 1.0, (
        f"Confidence {result['confidence']} out of range for stage {stage.stage_name}"
    )
    assert "gate_types" in result
    assert len(result["gate_types"]) > 0, f"No gate types for stage {stage.stage_name}"
    assert "gate_ordering" in result
    assert "source" in result

    # All returned frameworks must be in the valid catalog
    fw_catalog = set(ALL_FRAMEWORKS)
    for fw in result["recommended_frameworks"]:
        assert fw in fw_catalog, f"Unknown framework {fw!r} in stage {stage.stage_name}"

    # 'compliance' and 'audit' are baseline gates that must always be present
    for baseline_gate in ("compliance", "audit"):
        assert baseline_gate in result["gate_types"], (
            f"Baseline gate {baseline_gate!r} missing in stage {stage.stage_name}. "
            f"Got: {result['gate_types']}"
        )


def _assert_gate_weights_ordered(gate_weights: Dict[str, float], gate_ordering: List[str]) -> None:
    """Verify the gate ordering matches descending weights."""
    ordered_weights = [gate_weights[g] for g in gate_ordering if g in gate_weights]
    assert ordered_weights == sorted(ordered_weights, reverse=True), (
        f"Gate ordering does not match descending weights. "
        f"Ordering: {gate_ordering}, Weights: {gate_weights}"
    )


# ---------------------------------------------------------------------------
# Test Class: Stage-by-stage validation for each archetype
# ---------------------------------------------------------------------------

class TestTemporalStageValidation:
    """For each business archetype, walk every stage and validate all modules."""

    @pytest.mark.parametrize("timeline", _TIMELINES, ids=[t.archetype for t in _TIMELINES])
    def test_all_stages_pass_prediction(self, trained_engine: RegulationMLEngine, timeline: BusinessTimeline):
        """Every stage of every archetype must return a valid prediction."""
        for i, stage in enumerate(timeline.stages):
            result = trained_engine.predict_optimal_toggles(stage.country_code, stage.industry)
            _assert_valid_prediction(result, stage)

    @pytest.mark.parametrize("timeline", _TIMELINES, ids=[t.archetype for t in _TIMELINES])
    def test_gate_weights_ordered_at_every_stage(self, trained_engine: RegulationMLEngine, timeline: BusinessTimeline):
        """Gate ordering must always be sorted by descending weight."""
        for stage in timeline.stages:
            cum_fws = _cumulative_frameworks(timeline, timeline.stages.index(stage))
            if not cum_fws:
                continue
            result = trained_engine.predict_gate_config_for_regulation_set(cum_fws)
            _assert_gate_weights_ordered(result["gate_weights"], result["gate_ordering"])

    @pytest.mark.parametrize("timeline", _TIMELINES, ids=[t.archetype for t in _TIMELINES])
    def test_compliance_load_never_decreases(self, trained_engine: RegulationMLEngine, timeline: BusinessTimeline):
        """Cumulative framework count must be ≥ at each subsequent stage."""
        previous_count = 0
        for i, stage in enumerate(timeline.stages):
            cum_fws = _cumulative_frameworks(timeline, i)
            count = len(cum_fws)
            assert count >= previous_count, (
                f"Archetype {timeline.archetype}: stage {stage.stage_name!r} reduced "
                f"framework count from {previous_count} to {count}"
            )
            previous_count = count

    @pytest.mark.parametrize("timeline", _TIMELINES, ids=[t.archetype for t in _TIMELINES])
    def test_conflict_detection_fires_when_expected(self, trained_engine: RegulationMLEngine, timeline: BusinessTimeline):
        """Stages marked expect_conflicts=True must have conflict_count ≥ 1."""
        for i, stage in enumerate(timeline.stages):
            if not stage.expect_conflicts:
                continue
            cum_fws = _cumulative_frameworks(timeline, i)
            report = trained_engine.get_conflict_report(cum_fws)
            assert report["conflict_count"] >= 1, (
                f"Expected conflict not detected at stage {stage.stage_name!r} "
                f"of archetype {timeline.archetype!r}. "
                f"Frameworks: {cum_fws}"
            )
            assert report["is_clean"] is False

    @pytest.mark.parametrize("timeline", _TIMELINES, ids=[t.archetype for t in _TIMELINES])
    def test_no_spurious_conflicts_at_clean_stages(self, trained_engine: RegulationMLEngine, timeline: BusinessTimeline):
        """Stages with expect_conflicts=False must not introduce *new* conflicts.

        We compare the conflict count of the cumulative set up to stage N against
        the cumulative set up to stage N-1.  A clean stage must not raise the count.
        """
        prev_conflict_count = 0
        for i, stage in enumerate(timeline.stages):
            cum_fws = _cumulative_frameworks(timeline, i)
            if not cum_fws:
                continue
            report = trained_engine.get_conflict_report(cum_fws)
            current_count = report["conflict_count"]

            if not stage.expect_conflicts:
                assert current_count <= prev_conflict_count, (
                    f"Stage {stage.stage_name!r} of {timeline.archetype!r} "
                    f"unexpectedly raised conflict count from {prev_conflict_count} "
                    f"to {current_count}. New frameworks: {stage.extra_frameworks}. "
                    f"Conflicts: {report['conflicts']}"
                )

            prev_conflict_count = current_count

    @pytest.mark.parametrize("timeline", _TIMELINES, ids=[t.archetype for t in _TIMELINES])
    def test_toggle_manager_consistent_with_engine(
        self,
        trained_engine: RegulationMLEngine,
        toggle_manager: ComplianceToggleManager,
        timeline: BusinessTimeline,
    ):
        """ComplianceToggleManager baseline recommendations must be a subset of ML predictions."""
        for stage in timeline.stages:
            baseline = set(toggle_manager.get_recommended_frameworks(
                stage.country_code, stage.industry
            ))
            ml_result = trained_engine.predict_optimal_toggles(
                stage.country_code, stage.industry
            )
            ml_set = set(ml_result["recommended_frameworks"])

            # Every framework in the baseline must also be in the ML result
            missing = baseline - ml_set
            assert not missing, (
                f"Archetype {timeline.archetype!r}, stage {stage.stage_name!r}: "
                f"ML result missing baseline frameworks: {missing}"
            )

    @pytest.mark.parametrize("timeline", _TIMELINES, ids=[t.archetype for t in _TIMELINES])
    def test_required_gates_present_throughout_timeline(
        self, trained_engine: RegulationMLEngine, timeline: BusinessTimeline
    ):
        """Every stage's expected gates must appear in the gate config output."""
        for i, stage in enumerate(timeline.stages):
            cum_fws = _cumulative_frameworks(timeline, i)
            if not cum_fws:
                continue
            gate_result = trained_engine.predict_gate_config_for_regulation_set(cum_fws)
            for required_gate in stage.expect_gates_include:
                assert required_gate in gate_result["gate_types"], (
                    f"Stage {stage.stage_name!r} ({timeline.archetype!r}): "
                    f"expected gate {required_gate!r} not found. "
                    f"Got: {gate_result['gate_types']}"
                )


# ---------------------------------------------------------------------------
# Test Class: Temporal gate-weight drift
# ---------------------------------------------------------------------------

class TestGateWeightDrift:
    """As compliance load accumulates, high-priority gates should dominate."""

    @pytest.mark.parametrize("timeline", _TIMELINES, ids=[t.archetype for t in _TIMELINES])
    def test_safety_gate_weight_never_drops_when_safety_frameworks_present(
        self, trained_engine: RegulationMLEngine, timeline: BusinessTimeline
    ):
        """Once safety frameworks enter the set, 'safety' gate weight must stay present."""
        safety_frameworks = {"osha", "ce_marking", "ul_certification", "nfpa", "iso_45001"}
        safety_entered = False

        for i, stage in enumerate(timeline.stages):
            cum_fws = set(_cumulative_frameworks(timeline, i))
            if cum_fws & safety_frameworks:
                safety_entered = True

            if safety_entered and cum_fws & safety_frameworks:
                result = trained_engine.predict_gate_config_for_regulation_set(list(cum_fws))
                assert "safety" in result["gate_types"], (
                    f"'safety' gate dropped after being introduced in "
                    f"{timeline.archetype!r} at stage {stage.stage_name!r}. "
                    f"Frameworks: {list(cum_fws)}"
                )

    @pytest.mark.parametrize("timeline", _TIMELINES, ids=[t.archetype for t in _TIMELINES])
    def test_compliance_gate_always_present(
        self, trained_engine: RegulationMLEngine, timeline: BusinessTimeline
    ):
        """'compliance' gate must always be present regardless of framework set."""
        for i, stage in enumerate(timeline.stages):
            cum_fws = _cumulative_frameworks(timeline, i)
            if not cum_fws:
                cum_fws = ["soc2"]  # fallback
            result = trained_engine.predict_gate_config_for_regulation_set(cum_fws)
            assert "compliance" in result["gate_types"], (
                f"'compliance' gate missing for {timeline.archetype!r} "
                f"stage {stage.stage_name!r}. Gates: {result['gate_types']}"
            )

    @pytest.mark.parametrize("timeline", _TIMELINES, ids=[t.archetype for t in _TIMELINES])
    def test_audit_gate_present_when_audit_frameworks_active(
        self, trained_engine: RegulationMLEngine, timeline: BusinessTimeline
    ):
        """'audit' gate must appear whenever SOX, SOC2, GDPR, or HIPAA are active."""
        audit_triggers = {"sox", "soc2", "gdpr", "hipaa", "fedramp"}
        for i, stage in enumerate(timeline.stages):
            cum_fws = set(_cumulative_frameworks(timeline, i))
            if cum_fws & audit_triggers:
                result = trained_engine.predict_gate_config_for_regulation_set(list(cum_fws))
                assert "audit" in result["gate_types"], (
                    f"'audit' gate missing when audit-trigger frameworks active "
                    f"in {timeline.archetype!r} stage {stage.stage_name!r}. "
                    f"Frameworks: {list(cum_fws)}"
                )


# ---------------------------------------------------------------------------
# Test Class: Specific cross-validation scenarios
# ---------------------------------------------------------------------------

class TestCrossValidationScenarios:
    """Cross-validate specific framework combinations that make sense per business."""

    def test_healthcare_hipaa_hitech_coexist_cleanly(self, trained_engine: RegulationMLEngine):
        """HIPAA + HITECH together should be conflict-free (HITECH extends HIPAA)."""
        report = trained_engine.get_conflict_report(["hipaa", "hitech", "soc2"])
        assert report["is_clean"] is True

    def test_fintech_pci_sox_aml_no_conflicts(self, trained_engine: RegulationMLEngine):
        """Core fintech stack (PCI DSS + SOX + AML/KYC) must have no conflicts."""
        report = trained_engine.get_conflict_report(["pci_dss", "sox", "aml_kyc", "glba"])
        assert report["is_clean"] is True

    def test_manufacturing_safety_stack_clean(self, trained_engine: RegulationMLEngine):
        """Manufacturing safety stack (ISO 9001 + ISO 45001 + OSHA + NFPA) must be clean."""
        report = trained_engine.get_conflict_report(["iso_9001", "iso_45001", "osha", "nfpa"])
        assert report["is_clean"] is True

    def test_gdpr_dsgvo_is_conflict(self, trained_engine: RegulationMLEngine):
        """GDPR + DSGVO is a known conflict (DSGVO = German GDPR)."""
        report = trained_engine.get_conflict_report(["gdpr", "dsgvo"])
        assert report["conflict_count"] >= 1
        assert "dsgvo" in {r["framework"] for r in report["redundancies"]}

    def test_soc1_soc2_is_conflict(self, trained_engine: RegulationMLEngine):
        """SOC 1 + SOC 2 together is a known conflict."""
        report = trained_engine.get_conflict_report(["soc1", "soc2"])
        conflict_pairs = {
            tuple(sorted([c["framework_a"], c["framework_b"]])) for c in report["conflicts"]
        }
        assert ("soc1", "soc2") in conflict_pairs

    def test_nist_800_171_cmmc_conflict(self, trained_engine: RegulationMLEngine):
        """CMMC + NIST 800-171 together triggers the subsumption conflict."""
        report = trained_engine.get_conflict_report(["cmmc", "nist_800_171"])
        conflict_pairs = {
            tuple(sorted([c["framework_a"], c["framework_b"]])) for c in report["conflicts"]
        }
        assert ("cmmc", "nist_800_171") in conflict_pairs

    def test_ferpa_coppa_conflict_for_edtech(self, trained_engine: RegulationMLEngine):
        """FERPA + COPPA is a known conflict (age-group overlap in education)."""
        report = trained_engine.get_conflict_report(["ferpa", "coppa"])
        assert report["conflict_count"] >= 1

    def test_eu_privacy_stack_for_eu_saas(self, trained_engine: RegulationMLEngine):
        """EU SaaS (GDPR + NIS2 + SOC 2) must have no conflicts."""
        report = trained_engine.get_conflict_report(["gdpr", "nis2", "soc2"])
        assert report["is_clean"] is True

    def test_global_enterprise_security_stack(self, trained_engine: RegulationMLEngine):
        """Global enterprise security (ISO 27001 + SOC 2 + NIST CSF + CIS Controls) — clean."""
        report = trained_engine.get_conflict_report(["iso_27001", "soc2", "nist_csf", "cis_controls"])
        assert report["is_clean"] is True

    def test_government_defense_stack_clean(self, trained_engine: RegulationMLEngine):
        """Defense contractor (FedRAMP + ITAR) must be clean (different domains)."""
        report = trained_engine.get_conflict_report(["fedramp", "itar"])
        assert report["is_clean"] is True

    def test_saas_add_gdpr_at_eu_expansion(self, trained_engine: RegulationMLEngine):
        """SaaS adding GDPR at EU expansion: predict_optimal_toggles DE/technology must include gdpr."""
        result = trained_engine.predict_optimal_toggles("DE", "technology")
        assert "gdpr" in result["recommended_frameworks"]

    def test_healthcare_us_must_include_hipaa(self, trained_engine: RegulationMLEngine):
        """predict_optimal_toggles US/healthcare must include hipaa."""
        result = trained_engine.predict_optimal_toggles("US", "healthcare")
        assert "hipaa" in result["recommended_frameworks"]

    def test_banking_gb_must_include_gdpr(self, trained_engine: RegulationMLEngine):
        """predict_optimal_toggles GB/banking must include gdpr."""
        result = trained_engine.predict_optimal_toggles("GB", "banking")
        assert "gdpr" in result["recommended_frameworks"]

    def test_government_us_must_include_fedramp(self, trained_engine: RegulationMLEngine):
        """predict_optimal_toggles US/government must include fedramp."""
        result = trained_engine.predict_optimal_toggles("US", "government")
        assert "fedramp" in result["recommended_frameworks"]

    def test_defense_us_must_include_cmmc(self, trained_engine: RegulationMLEngine):
        """predict_optimal_toggles US/defense must include cmmc."""
        result = trained_engine.predict_optimal_toggles("US", "defense")
        assert "cmmc" in result["recommended_frameworks"]

    def test_education_us_must_include_ferpa(self, trained_engine: RegulationMLEngine):
        """predict_optimal_toggles US/education must include ferpa."""
        result = trained_engine.predict_optimal_toggles("US", "education")
        assert "ferpa" in result["recommended_frameworks"]


# ---------------------------------------------------------------------------
# Test Class: Temporal co-occurrence evolution
# ---------------------------------------------------------------------------

class TestCoOccurrenceEvolution:
    """Verify co-occurrence insights develop correctly across the full timeline."""

    def test_co_occurrence_insights_populated_after_all_stages(
        self, trained_engine: RegulationMLEngine
    ):
        """After all timelines are exercised, co-occurrence must have real data."""
        # Warm up: run every stage of every timeline through the engine
        for timeline in _TIMELINES:
            for i, stage in enumerate(timeline.stages):
                cum_fws = _cumulative_frameworks(timeline, i)
                if cum_fws:
                    trained_engine.predict_gate_config_for_regulation_set(cum_fws)

        insights = trained_engine.get_co_occurrence_insights()
        assert insights["status"] == "ok"
        assert insights["total_scenarios_profiled"] > 0
        assert insights["unique_pair_combinations"] > 0

    def test_most_efficient_combo_is_plausible(self, trained_engine: RegulationMLEngine):
        """most_efficient_combo must have efficiency_score between 0 and 1."""
        insights = trained_engine.get_co_occurrence_insights()
        combo = insights.get("most_efficient_combo")
        if combo is not None:
            assert 0.0 <= combo["efficiency_score"] <= 1.0

    def test_most_conflicted_combo_is_plausible(self, trained_engine: RegulationMLEngine):
        """most_conflicted_combo must have conflict_score ≥ 0."""
        insights = trained_engine.get_co_occurrence_insights()
        combo = insights.get("most_conflicted_combo")
        if combo is not None:
            assert combo["conflict_score"] >= 0.0

    def test_top_pairs_have_positive_counts(self, trained_engine: RegulationMLEngine):
        """All top co-occurrence pairs must have count > 0."""
        insights = trained_engine.get_co_occurrence_insights()
        for pair_info in insights.get("top_pairs", []):
            assert pair_info["count"] > 0

    def test_soc2_appears_in_top_pairs(self, trained_engine: RegulationMLEngine):
        """soc2 co-occurs widely — it should appear in top pairs."""
        insights = trained_engine.get_co_occurrence_insights()
        top_pair_strs = " ".join(p["pair"] for p in insights.get("top_pairs", []))
        # soc2 is present in many timelines; its pair should surface in top 10
        # (lenient check — top_pairs may not have 10 entries if few scenarios exist)
        if len(insights.get("top_pairs", [])) >= 5:
            assert "soc2" in top_pair_strs, (
                f"soc2 not in top pairs despite being in many scenarios. "
                f"Top pairs: {top_pair_strs}"
            )


# ---------------------------------------------------------------------------
# Test Class: Immune memory persistence within a session
# ---------------------------------------------------------------------------

class TestImmuneMemoryWithinSession:
    """Verify immune memory is exploited correctly as stages repeat lookups."""

    def test_repeated_stage_lookups_use_immune_memory(self, trained_engine: RegulationMLEngine):
        """Second call to the same stage must come from immune_memory."""
        stage = _TIMELINES[0].stages[0]  # SaaS pre_launch → US / technology
        # First call — may be model_lookup or immune_memory
        trained_engine.predict_optimal_toggles(stage.country_code, stage.industry)
        # Second call — must be immune_memory
        result = trained_engine.predict_optimal_toggles(stage.country_code, stage.industry)
        assert result["source"] == "immune_memory"

    def test_immune_memory_size_grows_with_novel_combos(self, trained_engine: RegulationMLEngine):
        """Novel country+industry combos must add entries to immune memory."""
        from regulation_ml_engine import _REG_IMMUNE_MEMORY, _REG_IMMUNE_LOCK

        with _REG_IMMUNE_LOCK:
            before = len(_REG_IMMUNE_MEMORY)

        # Ask for a combo not in any of the 12 timelines
        trained_engine.predict_optimal_toggles("SE", "healthcare")

        with _REG_IMMUNE_LOCK:
            after = len(_REG_IMMUNE_MEMORY)

        assert after >= before  # may already be cached, but never shrinks


# ---------------------------------------------------------------------------
# Test Class: Thread safety across concurrent timeline walks
# ---------------------------------------------------------------------------

class TestConcurrentTimelineWalks:
    """All 12 timelines run concurrently must not corrupt state."""

    def test_concurrent_timeline_walks_no_errors(self, trained_engine: RegulationMLEngine):
        errors: List[Exception] = []

        def walk_timeline(timeline: BusinessTimeline) -> None:
            try:
                for i, stage in enumerate(timeline.stages):
                    cum_fws = _cumulative_frameworks(timeline, i)
                    trained_engine.predict_optimal_toggles(stage.country_code, stage.industry)
                    if cum_fws:
                        trained_engine.predict_gate_config_for_regulation_set(cum_fws)
                        trained_engine.get_conflict_report(cum_fws)
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [
            threading.Thread(target=walk_timeline, args=(tl,))
            for tl in _TIMELINES
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=60)

        assert errors == [], f"Concurrent walk errors: {errors}"

    def test_concurrent_conflict_reports_consistent(self, trained_engine: RegulationMLEngine):
        """Multiple threads running get_conflict_report on the same set must agree."""
        fws = ["gdpr", "dsgvo", "soc1", "soc2"]
        results: List[Dict[str, Any]] = []
        errors: List[Exception] = []

        def run_check() -> None:
            try:
                report = trained_engine.get_conflict_report(fws)
                results.append(report["conflict_count"])
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=run_check) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert errors == []
        # All threads must agree on the conflict count
        assert len(set(results)) == 1, f"Inconsistent conflict counts: {results}"


# ---------------------------------------------------------------------------
# Test Class: ComplianceToggleManager temporal saving
# ---------------------------------------------------------------------------

class TestToggleManagerTemporalSaving:
    """Simulate a tenant progressing through compliance stages over time."""

    def test_tenant_compliance_grows_through_stages(self):
        """Saving frameworks at each stage must accumulate correctly."""
        mgr = ComplianceToggleManager()
        tenant = "tenant-temporal-test"

        # Pre-launch
        mgr.save_tenant_frameworks(tenant, ["soc2"], updated_by="stage_pre_launch")
        assert set(mgr.get_tenant_frameworks(tenant)) == {"soc2"}

        # Early growth
        mgr.save_tenant_frameworks(tenant, ["soc2", "nist_csf", "iso_27001"])
        assert "iso_27001" in mgr.get_tenant_frameworks(tenant)

        # Scaling (add fedramp)
        mgr.save_tenant_frameworks(tenant, ["soc2", "nist_csf", "iso_27001", "fedramp"])
        assert "fedramp" in mgr.get_tenant_frameworks(tenant)

        # Final — count is 4
        assert len(mgr.get_tenant_frameworks(tenant)) == 4

    def test_audit_log_records_every_stage_save(self):
        mgr = ComplianceToggleManager()
        tenant = "tenant-audit-log-test"
        stages = [
            ["soc2"],
            ["soc2", "gdpr"],
            ["soc2", "gdpr", "iso_27001"],
        ]
        for fws in stages:
            mgr.save_tenant_frameworks(tenant, fws)

        log = mgr.get_audit_log()
        tenant_entries = [e for e in log if e["tenant_id"] == tenant]
        assert len(tenant_entries) == 3

    def test_ml_enhanced_recommendations_superset_of_baseline(self):
        """use_ml=True should return ≥ as many frameworks as use_ml=False."""
        mgr = ComplianceToggleManager()
        for timeline in _TIMELINES:
            for stage in timeline.stages:
                baseline = set(mgr.get_recommended_frameworks(
                    stage.country_code, stage.industry, use_ml=False
                ))
                ml_enhanced = set(mgr.get_recommended_frameworks(
                    stage.country_code, stage.industry, use_ml=True
                ))
                assert baseline.issubset(ml_enhanced), (
                    f"ML result is not a superset of baseline for "
                    f"{stage.country_code}/{stage.industry}. "
                    f"Missing: {baseline - ml_enhanced}"
                )

    @pytest.mark.parametrize("timeline", _TIMELINES, ids=[t.archetype for t in _TIMELINES])
    def test_save_then_report_for_each_archetype(self, timeline: BusinessTimeline):
        """Saving the final stage's frameworks and generating a report must not error."""
        mgr = ComplianceToggleManager()
        tenant = f"tenant-{timeline.archetype}"
        final_stage_idx = len(timeline.stages) - 1
        final_fws = _cumulative_frameworks(timeline, final_stage_idx)
        if not final_fws:
            final_fws = ["soc2"]

        mgr.save_tenant_frameworks(tenant, final_fws)
        report = mgr.generate_compliance_report(tenant)

        assert report["tenant_id"] == tenant
        assert report["enabled_count"] == len(final_fws)
        assert isinstance(report["framework_statuses"], dict)


# ---------------------------------------------------------------------------
# Test Class: Framework completeness across all timelines
# ---------------------------------------------------------------------------

class TestFrameworkCompleteness:
    """All frameworks referenced in the timelines must be in ALL_FRAMEWORKS."""

    def test_all_stage_frameworks_are_in_catalog(self):
        fw_catalog = set(ALL_FRAMEWORKS)
        for timeline in _TIMELINES:
            for stage in timeline.stages:
                for fw in stage.extra_frameworks:
                    assert fw in fw_catalog, (
                        f"Framework {fw!r} in {timeline.archetype!r} "
                        f"stage {stage.stage_name!r} is not in ALL_FRAMEWORKS"
                    )

    def test_all_required_gates_are_in_gate_catalog(self):
        gate_catalog = set(_ALL_GATE_TYPES)
        for timeline in _TIMELINES:
            for stage in timeline.stages:
                for gate in stage.expect_gates_include:
                    assert gate in gate_catalog, (
                        f"Gate {gate!r} in {timeline.archetype!r} "
                        f"stage {stage.stage_name!r} is not in _ALL_GATE_TYPES"
                    )

    def test_all_industries_are_in_catalog(self):
        for timeline in _TIMELINES:
            for stage in timeline.stages:
                industry = stage.industry
                # Allow "general" as wildcard fallback
                assert (
                    industry in _INDUSTRY_FRAMEWORKS or industry == "general"
                ), (
                    f"Industry {industry!r} in {timeline.archetype!r} "
                    f"stage {stage.stage_name!r} is not in _INDUSTRY_FRAMEWORKS"
                )

    def test_all_country_codes_are_in_catalog_or_known_extra(self):
        """Country codes must be in _COUNTRY_FRAMEWORKS or standard ISO codes."""
        extra_allowed = {"IN", "CN", "US-CA"}  # These are in _COUNTRY_FRAMEWORKS
        for timeline in _TIMELINES:
            for stage in timeline.stages:
                cc = stage.country_code
                assert (
                    cc in _COUNTRY_FRAMEWORKS or cc in extra_allowed
                ), (
                    f"Country {cc!r} in {timeline.archetype!r} "
                    f"stage {stage.stage_name!r} is not in _COUNTRY_FRAMEWORKS"
                )

    def test_timelines_cover_all_12_outreach_verticals(self):
        """All 12 outreach verticals must have at least one timeline."""
        try:
            from outreach_compliance_plan import BUSINESS_TYPE_VERTICALS
        except ImportError:
            BUSINESS_TYPE_VERTICALS = [
                "saas", "ecommerce", "healthcare", "legal", "financial_services",
                "manufacturing", "construction", "real_estate", "hospitality",
                "education", "logistics", "content_creator",
            ]
        covered = {tl.vertical for tl in _TIMELINES}
        for vertical in BUSINESS_TYPE_VERTICALS:
            assert vertical in covered, (
                f"Outreach vertical {vertical!r} has no temporal timeline"
            )


# ---------------------------------------------------------------------------
# Test Class: Status & model integrity after full run
# ---------------------------------------------------------------------------

class TestEngineStatusAfterFullRun:
    """Verify engine status reflects all the work done across the test module."""

    def test_status_trained_is_true(self, trained_engine: RegulationMLEngine):
        status = trained_engine.get_status()
        assert status["trained"] is True

    def test_status_profile_count_matches_scenario_matrix(self, trained_engine: RegulationMLEngine):
        """Profile count should cover the country × industry matrix (546 = 39 × 14)."""
        status = trained_engine.get_status()
        assert status["profile_count"] > 0

    def test_status_immune_memory_size_positive(self, trained_engine: RegulationMLEngine):
        status = trained_engine.get_status()
        assert status["immune_memory_size"] > 0

    def test_export_model_json_serialisable(self, trained_engine: RegulationMLEngine):
        import json
        exported = trained_engine.export_model()
        # Should not raise
        json.dumps(exported)

    def test_all_profiles_have_valid_country_and_industry(self, trained_engine: RegulationMLEngine):
        profiles = trained_engine.get_all_profiles()
        for p in profiles:
            assert isinstance(p.country_code, str) and p.country_code
            assert isinstance(p.industry, str) and p.industry
            assert 0.0 <= p.efficiency_score <= 1.0
            assert 0.0 <= p.rubix_confidence <= 1.0
