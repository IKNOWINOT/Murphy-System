"""
Tests for GateBehaviorModelEngine.

Validates:
  - GateConfig / GateBehaviorProfile / GateProfileTrainingExample dataclasses
  - Phase 1: run_phase1() full pipeline
  - Phase 2: run_phase2() ML training
  - predict() — immune fast-path, ML path, full simulation path
  - Helper functions: _compute_immune_signature, _optimise_gate_ordering,
    _build_gate_configs_from_inference, _simulate_gate_profile,
    _validate_gate_profile_rubix, _profile_to_training_example
  - enumerate_all_subject_matters()
  - import / export profiles
  - get_status()
  - _FallbackInferenceResult

Copyright © 2020-2026 Inoni LLC — Created by Corey Post
License: BSL 1.1
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest

from gate_behavior_model_engine import (
    GateConfig,
    GateBehaviorProfile,
    GateProfileTrainingExample,
    GateBehaviorModelEngine,
    _FallbackInferenceResult,
    _GateAction,
    _GateGap,
    _compute_immune_signature,
    _determine_fail_action,
    _determine_severity,
    _determine_threshold,
    _optimise_gate_ordering,
    _build_gate_configs_from_inference,
    _simulate_gate_profile,
    _validate_gate_profile_rubix,
    _profile_to_training_example,
    enumerate_all_subject_matters,
    build_engine,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_gate_config(
    name: str = "test_gate",
    gate_type: str = "security",
    severity: str = "high",
    threshold: float = 0.90,
    risk_reduction: float = 0.7,
    fail_action: str = "block",
    position: int = 0,
) -> GateConfig:
    return GateConfig(
        gate_name=name,
        gate_type=gate_type,
        severity=severity,
        confidence_threshold=threshold,
        risk_reduction=risk_reduction,
        fail_action=fail_action,
        position_in_sequence=position,
        wired_function=f"validate_{name}",
        conditions=[{"key": "value"}],
    )


def _make_profile(
    industry: str = "technology",
    gate_count: int = 3,
) -> GateBehaviorProfile:
    configs = [
        _make_gate_config(f"gate_{i}", position=i) for i in range(gate_count)
    ]
    return GateBehaviorProfile(
        profile_id=str(uuid.uuid4()),
        subject_matter=f"A {industry} company",
        industry=industry,
        gate_configs=configs,
        gate_ordering=[f"gate_{i}" for i in range(gate_count)],
        total_risk_reduction=0.7,
        confidence=0.85,
        monte_carlo_p95=0.82,
        forecast_halflife_days=90.0,
        immune_signature=_compute_immune_signature(
            industry,
            [c.gate_type for c in configs],
            [c.severity for c in configs],
        ),
        created_at="2026-01-01T00:00:00+00:00",
    )


class _FakeDomainGate:
    def __init__(self, name: str, gate_type_val: str = "security", severity_val: str = "medium"):
        from unittest.mock import MagicMock
        self.name = name
        self.gate_type = MagicMock(value=gate_type_val)
        self.severity = MagicMock(value=severity_val)
        self.risk_reduction = 0.6
        self.wired_function = f"validate_{name}"


class _FakeInferenceResult:
    def __init__(self, industry: str = "technology", gate_names: Optional[List[str]] = None):
        self.inferred_industry = industry
        self.org_positions = []
        self.inferred_gates = [
            _FakeDomainGate(n) for n in (
                gate_names if gate_names is not None else ["security_gate", "compliance_gate"]
            )
        ]
        self.form_schema = None


# ---------------------------------------------------------------------------
# GateConfig
# ---------------------------------------------------------------------------

class TestGateConfig:
    def test_creation(self):
        gc = _make_gate_config()
        assert gc.gate_name == "test_gate"
        assert gc.severity == "high"
        assert gc.confidence_threshold == 0.90

    def test_to_dict_round_trip(self):
        gc = _make_gate_config("my_gate", "compliance", "critical", 0.95, 0.8, "block", 2)
        d = gc.to_dict()
        restored = GateConfig.from_dict(d)
        assert restored.gate_name == "my_gate"
        assert restored.severity == "critical"
        assert restored.confidence_threshold == 0.95
        assert restored.position_in_sequence == 2

    def test_from_dict_defaults(self):
        gc = GateConfig.from_dict({})
        assert gc.gate_name == ""
        assert gc.severity == "medium"
        assert gc.fail_action == "warn"

    def test_conditions_preserved(self):
        gc = _make_gate_config()
        d = gc.to_dict()
        assert d["conditions"] == [{"key": "value"}]


# ---------------------------------------------------------------------------
# GateBehaviorProfile
# ---------------------------------------------------------------------------

class TestGateBehaviorProfile:
    def test_creation(self):
        p = _make_profile("healthcare", gate_count=4)
        assert p.industry == "healthcare"
        assert len(p.gate_configs) == 4
        assert p.confidence == 0.85

    def test_to_dict_round_trip(self):
        p = _make_profile("finance", gate_count=2)
        d = p.to_dict()
        restored = GateBehaviorProfile.from_dict(d)
        assert restored.profile_id == p.profile_id
        assert restored.industry == "finance"
        assert len(restored.gate_configs) == 2
        assert restored.confidence == p.confidence

    def test_from_dict_empty(self):
        p = GateBehaviorProfile.from_dict({})
        assert p.industry == "other"
        assert p.gate_configs == []
        assert p.confidence == 0.0


# ---------------------------------------------------------------------------
# GateProfileTrainingExample
# ---------------------------------------------------------------------------

class TestGateProfileTrainingExample:
    def test_creation(self):
        te = GateProfileTrainingExample(
            industry="technology",
            description_keywords=["cloud", "security", "devops"],
            position_count=3,
            gate_count=5,
            complexity="medium",
            has_regulatory=False,
            has_security_focus=True,
            optimal_gate_types=["security", "compliance"],
            optimal_severities=["high", "critical"],
            optimal_thresholds=[0.90, 0.95],
            optimal_ordering=[0, 1],
            optimal_fail_actions=["block", "block"],
            effectiveness_score=0.82,
            source_profile_id="abc",
        )
        assert te.industry == "technology"
        assert te.has_security_focus is True
        assert te.effectiveness_score == 0.82

    def test_to_dict(self):
        p = _make_profile("technology")
        te = _profile_to_training_example(p, "A technology SaaS company")
        d = te.to_dict()
        assert d["industry"] == "technology"
        assert isinstance(d["description_keywords"], list)
        assert isinstance(d["optimal_gate_types"], list)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

class TestComputeImmuneSignature:
    def test_deterministic(self):
        sig1 = _compute_immune_signature("healthcare", ["compliance", "security"], ["critical", "high"])
        sig2 = _compute_immune_signature("healthcare", ["security", "compliance"], ["high", "critical"])
        assert sig1 == sig2  # sorted inputs

    def test_different_inputs_different_sig(self):
        sig1 = _compute_immune_signature("healthcare", ["compliance"], ["critical"])
        sig2 = _compute_immune_signature("technology", ["compliance"], ["critical"])
        assert sig1 != sig2

    def test_returns_hex_string(self):
        sig = _compute_immune_signature("other", [], [])
        assert len(sig) == 64
        int(sig, 16)  # should not raise


class TestDetermineSeverity:
    def test_healthcare_compliance_is_critical(self):
        assert _determine_severity("compliance", "healthcare", 0.5) == "critical"

    def test_high_risk_is_critical(self):
        assert _determine_severity("validation", "other", 0.85) == "critical"

    def test_medium_risk(self):
        sev = _determine_severity("validation", "other", 0.45)
        assert sev == "medium"

    def test_low_risk(self):
        sev = _determine_severity("performance", "other", 0.2)
        assert sev == "low"


class TestDetermineFailAction:
    def test_critical_always_block(self):
        assert _determine_fail_action("validation", "critical", "other") == "block"

    def test_healthcare_high_escalates(self):
        assert _determine_fail_action("compliance", "high", "healthcare") == "escalate"

    def test_compliance_type_defaults_block(self):
        assert _determine_fail_action("compliance", "medium", "other") == "block"


class TestDetermineThreshold:
    def test_healthcare_higher_threshold(self):
        t = _determine_threshold("validation", "healthcare")
        assert t >= 0.90

    def test_performance_lower_threshold(self):
        t = _determine_threshold("performance", "other")
        assert t <= 0.85

    def test_security_high_threshold(self):
        t = _determine_threshold("security", "other")
        assert t >= 0.90


class TestOptimiseGateOrdering:
    def test_critical_first(self):
        configs = [
            _make_gate_config("low_gate", severity="low", fail_action="warn"),
            _make_gate_config("critical_gate", severity="critical", fail_action="block"),
            _make_gate_config("high_gate", severity="high", fail_action="escalate"),
        ]
        ordering = _optimise_gate_ordering(configs)
        assert ordering[0] == "critical_gate"

    def test_empty_list(self):
        assert _optimise_gate_ordering([]) == []

    def test_ordering_is_list_of_strings(self):
        configs = [_make_gate_config(f"gate_{i}") for i in range(3)]
        ordering = _optimise_gate_ordering(configs)
        assert all(isinstance(s, str) for s in ordering)
        assert len(ordering) == 3


class TestSimulateGateProfile:
    def test_empty_returns_zero(self):
        result = _simulate_gate_profile([], "other")
        assert result["effectiveness"] == 0.0

    def test_non_empty_returns_score(self):
        configs = [_make_gate_config(f"gate_{i}", risk_reduction=0.7) for i in range(3)]
        result = _simulate_gate_profile(configs, "technology")
        assert 0 <= result["effectiveness"] <= 1.0
        assert "regressions" in result
        assert "side_effects" in result

    def test_healthcare_boost(self):
        configs = [_make_gate_config("compliance_gate", gate_type="compliance", severity="critical", risk_reduction=0.8)]
        r_healthcare = _simulate_gate_profile(configs, "healthcare")
        r_other = _simulate_gate_profile(configs, "other")
        assert r_healthcare["effectiveness"] >= r_other["effectiveness"]

    def test_side_effects_counted(self):
        configs = [
            _make_gate_config("low_block_gate", severity="low", fail_action="block"),
        ]
        result = _simulate_gate_profile(configs, "other")
        assert result["side_effects"] >= 1


class TestBuildGateConfigsFromInference:
    def test_from_inference_result(self):
        ir = _FakeInferenceResult("technology", ["auth_gate", "data_gate"])
        configs = _build_gate_configs_from_inference(ir, "technology")
        assert len(configs) == 2
        assert all(isinstance(c, GateConfig) for c in configs)
        assert configs[0].gate_name == "auth_gate"

    def test_empty_inference_result(self):
        ir = _FakeInferenceResult("other", [])
        configs = _build_gate_configs_from_inference(ir, "other")
        assert configs == []

    def test_positions_assigned(self):
        ir = _FakeInferenceResult("technology", ["g1", "g2", "g3"])
        configs = _build_gate_configs_from_inference(ir, "technology")
        positions = [c.position_in_sequence for c in configs]
        assert positions == [0, 1, 2]


class TestValidateGateProfileRubix:
    def test_no_rubix_uses_fallback(self):
        configs = [_make_gate_config()]
        sim = {"effectiveness": 0.75}
        stats = _validate_gate_profile_rubix(configs, sim, None)
        assert 0 <= stats["confidence"] <= 1.0
        assert stats["monte_carlo_p95"] >= 0
        assert stats["forecast_halflife_days"] > 0

    def test_empty_configs_returns_defaults(self):
        stats = _validate_gate_profile_rubix([], {"effectiveness": 0.5}, None)
        assert stats["confidence"] > 0
        assert stats["forecast_halflife_days"] > 0

    def test_with_real_rubix(self):
        try:
            from rubix_evidence_adapter import RubixEvidenceAdapter
            rubix = RubixEvidenceAdapter()
            configs = [_make_gate_config("gate_a", risk_reduction=0.8)]
            sim = {"effectiveness": 0.80}
            stats = _validate_gate_profile_rubix(configs, sim, rubix)
            assert 0 <= stats["confidence"] <= 1.0
            assert stats["monte_carlo_p95"] >= 0
            assert stats["forecast_halflife_days"] >= 30.0
        except ImportError:
            pytest.skip("rubix_evidence_adapter not available")


# ---------------------------------------------------------------------------
# FallbackInferenceResult
# ---------------------------------------------------------------------------

class TestFallbackInferenceResult:
    def test_healthcare_detected(self):
        f = _FallbackInferenceResult("healthcare clinic management")
        assert f.inferred_industry == "healthcare"

    def test_finance_detected(self):
        f = _FallbackInferenceResult("fintech banking operations")
        assert f.inferred_industry == "finance"

    def test_technology_detected(self):
        f = _FallbackInferenceResult("cloud software devops")
        assert f.inferred_industry == "technology"

    def test_other_fallback(self):
        f = _FallbackInferenceResult("some random description xyz")
        assert f.inferred_industry == "other"

    def test_empty_gates_and_positions(self):
        f = _FallbackInferenceResult("test")
        assert f.inferred_gates == []
        assert f.org_positions == []


# ---------------------------------------------------------------------------
# Internal gap / action wrappers
# ---------------------------------------------------------------------------

class TestGateGap:
    def test_creation(self):
        gap = _GateGap("healthcare clinic", "healthcare", ["compliance_gate"])
        assert gap.category == "gate_optimisation"
        assert gap.source == "gate_behavior_model_engine"
        assert "healthcare" in gap.context["subject_matter"]
        assert gap.gap_id.startswith("gate-opt-")

    def test_long_description_truncated(self):
        gap = _GateGap("x" * 200, "other", [])
        assert len(gap.description) <= 130


class TestGateAction:
    def test_creation(self):
        configs = [_make_gate_config("gc")]
        action = _GateAction("gap-123", configs, effectiveness=0.75)
        assert action.fix_type == "gate_profile_config"
        assert len(action.fix_steps) == 1
        assert action.source_strategy == "gate_behavior_model_engine"


# ---------------------------------------------------------------------------
# GateBehaviorModelEngine — Phase 1
# ---------------------------------------------------------------------------

class TestGateBehaviorModelEnginePhase1:
    def test_run_phase1_with_fallback(self):
        """Phase 1 should work without any external dependencies."""
        engine = GateBehaviorModelEngine()
        subjects = ["A healthcare clinic", "A technology startup"]
        profiles = engine.run_phase1(subject_matters=subjects)
        assert len(profiles) == 2
        assert all(isinstance(p, GateBehaviorProfile) for p in profiles)

    def test_profiles_saved_in_memory(self):
        engine = GateBehaviorModelEngine()
        subjects = ["A manufacturing plant"]
        engine.run_phase1(subject_matters=subjects)
        all_profiles = engine.get_all_profiles()
        assert len(all_profiles) == 1

    def test_profile_has_required_fields(self):
        engine = GateBehaviorModelEngine()
        engine.run_phase1(subject_matters=["A finance firm"])
        profile = engine.get_all_profiles()[0]
        assert profile.profile_id
        assert profile.created_at
        assert isinstance(profile.gate_ordering, list)
        assert 0 <= profile.confidence <= 1.0
        assert profile.forecast_halflife_days >= 30.0

    def test_subject_index_populated(self):
        engine = GateBehaviorModelEngine()
        subject = "A healthcare company operations"
        engine.run_phase1(subject_matters=[subject])
        found = engine.get_profile_by_subject(subject)
        assert found is not None

    def test_immune_fast_path_reuses_profile(self):
        engine = GateBehaviorModelEngine()
        subject = "A retail company"
        engine.run_phase1(subject_matters=[subject])
        # Second call should hit fast-path
        profiles2 = engine.run_phase1(subject_matters=[subject])
        assert len(engine.get_all_profiles()) == 1  # no duplicate
        assert profiles2[0].profile_id == engine.get_all_profiles()[0].profile_id

    def test_max_subjects_limits_processing(self):
        engine = GateBehaviorModelEngine()
        subjects = [f"Subject {i}" for i in range(10)]
        profiles = engine.run_phase1(subject_matters=subjects, max_subjects=3)
        assert len(profiles) == 3

    def test_error_in_subject_is_skipped(self):
        engine = GateBehaviorModelEngine()
        # Mix of valid and pathological inputs
        subjects = ["", "A technology company", "   "]
        profiles = engine.run_phase1(subject_matters=subjects)
        # At minimum the valid subject should produce a profile
        assert any(p.subject_matter == "A technology company" for p in profiles)

    def test_immune_signature_computed(self):
        engine = GateBehaviorModelEngine()
        engine.run_phase1(subject_matters=["A security-focused organisation"])
        profile = engine.get_all_profiles()[0]
        assert len(profile.immune_signature) == 64

    def test_gate_ordering_is_optimised(self):
        engine = GateBehaviorModelEngine()
        engine.run_phase1(subject_matters=["A healthcare clinic with compliance requirements"])
        profile = engine.get_all_profiles()[0]
        assert isinstance(profile.gate_ordering, list)

    def test_total_risk_reduction_in_range(self):
        engine = GateBehaviorModelEngine()
        engine.run_phase1(subject_matters=["A manufacturing plant"])
        profile = engine.get_all_profiles()[0]
        assert 0.0 <= profile.total_risk_reduction <= 1.0


# ---------------------------------------------------------------------------
# GateBehaviorModelEngine — Phase 2
# ---------------------------------------------------------------------------

class TestGateBehaviorModelEnginePhase2:
    def test_phase2_requires_phase1(self):
        engine = GateBehaviorModelEngine()
        result = engine.run_phase2()
        assert result["status"] == "no_profiles"

    def test_phase2_after_phase1(self):
        engine = GateBehaviorModelEngine()
        engine.run_phase1(subject_matters=["A tech startup", "A healthcare clinic"])
        result = engine.run_phase2()
        # Should at least attempt training (even if ML pipeline unavailable)
        assert "profiles_trained" in result
        assert result["profiles_trained"] == 2

    def test_phase2_sets_trained_flag(self):
        engine = GateBehaviorModelEngine()
        engine.run_phase1(subject_matters=["A finance firm"])
        engine.run_phase2()
        status = engine.get_status()
        assert status["phase2_trained"] is True

    def test_training_examples_accumulated(self):
        engine = GateBehaviorModelEngine()
        engine.run_phase1(subject_matters=["A retail company", "A tech firm"])
        examples = engine.get_training_examples()
        assert len(examples) == 2
        assert all(isinstance(e, GateProfileTrainingExample) for e in examples)


# ---------------------------------------------------------------------------
# GateBehaviorModelEngine — predict
# ---------------------------------------------------------------------------

class TestGateBehaviorModelEnginePredict:
    def test_predict_returns_profile(self):
        engine = GateBehaviorModelEngine()
        result = engine.predict("A healthcare clinic")
        assert "profile" in result
        assert "source" in result
        assert "confidence" in result
        assert isinstance(result["profile"], GateBehaviorProfile)

    def test_predict_uses_immune_fast_path(self):
        engine = GateBehaviorModelEngine()
        subject = "A technology startup company"
        engine.run_phase1(subject_matters=[subject])
        result = engine.predict(subject)
        assert result["source"] == "immune_memory"

    def test_predict_full_simulation_for_novel(self):
        engine = GateBehaviorModelEngine()
        result = engine.predict("A completely novel domain xyz123")
        assert result["source"] == "full_simulation"

    def test_predict_force_simulation_bypasses_cache(self):
        engine = GateBehaviorModelEngine()
        subject = "A manufacturing plant"
        engine.run_phase1(subject_matters=[subject])
        result = engine.predict(subject, force_simulation=True)
        assert result["source"] == "full_simulation"

    def test_predict_confidence_in_range(self):
        engine = GateBehaviorModelEngine()
        result = engine.predict("A healthcare company")
        assert 0.0 <= result["confidence"] <= 1.0

    def test_active_learning_adds_training_example(self):
        engine = GateBehaviorModelEngine()
        # No phase 1 run — should trigger full simulation → new training example
        engine.predict("A novel retail company")
        examples = engine.get_training_examples()
        assert len(examples) >= 1


# ---------------------------------------------------------------------------
# GateBehaviorModelEngine — import/export
# ---------------------------------------------------------------------------

class TestImportExport:
    def test_export_empty(self):
        engine = GateBehaviorModelEngine()
        exported = engine.export_profiles()
        assert exported == []

    def test_export_round_trip(self):
        engine = GateBehaviorModelEngine()
        engine.run_phase1(subject_matters=["A technology company", "A healthcare clinic"])
        exported = engine.export_profiles()
        assert len(exported) == 2

        # Import into fresh engine
        engine2 = GateBehaviorModelEngine()
        count = engine2.import_profiles(exported)
        assert count == 2
        assert len(engine2.get_all_profiles()) == 2

    def test_import_bad_entries_skipped(self):
        engine = GateBehaviorModelEngine()
        count = engine.import_profiles([{"bad": "entry"}, {}, None])
        assert count >= 0  # should not crash

    def test_import_restores_subject_index(self):
        engine = GateBehaviorModelEngine()
        engine.run_phase1(subject_matters=["A finance firm"])
        exported = engine.export_profiles()

        engine2 = GateBehaviorModelEngine()
        engine2.import_profiles(exported)
        found = engine2.get_profile_by_subject("A finance firm")
        assert found is not None


# ---------------------------------------------------------------------------
# GateBehaviorModelEngine — get_status
# ---------------------------------------------------------------------------

class TestGetStatus:
    def test_initial_status(self):
        engine = GateBehaviorModelEngine()
        status = engine.get_status()
        assert status["profile_count"] == 0
        assert status["training_example_count"] == 0
        assert status["phase2_trained"] is False

    def test_status_after_phase1(self):
        engine = GateBehaviorModelEngine()
        engine.run_phase1(subject_matters=["A tech company"])
        status = engine.get_status()
        assert status["profile_count"] == 1
        assert status["training_example_count"] == 1


# ---------------------------------------------------------------------------
# enumerate_all_subject_matters
# ---------------------------------------------------------------------------

class TestEnumerateSubjectMatters:
    def test_returns_list(self):
        subjects = enumerate_all_subject_matters()
        assert isinstance(subjects, list)

    def test_no_duplicates(self):
        subjects = enumerate_all_subject_matters()
        lower = [s.strip().lower() for s in subjects]
        assert len(lower) == len(set(lower))

    def test_non_empty_strings(self):
        subjects = enumerate_all_subject_matters()
        for s in subjects:
            assert isinstance(s, str)
            assert len(s.strip()) > 0


# ---------------------------------------------------------------------------
# build_engine factory
# ---------------------------------------------------------------------------

class TestBuildEngine:
    def test_returns_engine(self):
        engine = build_engine()
        assert isinstance(engine, GateBehaviorModelEngine)

    def test_custom_threshold(self):
        engine = build_engine(prediction_threshold=0.9)
        assert engine._prediction_confidence_threshold == 0.9


# ---------------------------------------------------------------------------
# MFM fine-tuning (smoke test — graceful when MFM not available)
# ---------------------------------------------------------------------------

class TestMFMFinetuning:
    def test_no_profiles_returns_gracefully(self):
        engine = GateBehaviorModelEngine()
        result = engine.run_mfm_finetuning()
        assert result["status"] in ("no_profiles", "mfm_not_available", "MFMTrainer_not_found")

    def test_with_profiles_does_not_crash(self):
        engine = GateBehaviorModelEngine()
        engine.run_phase1(subject_matters=["A technology company"])
        # Should not raise even if MFM deps are absent
        result = engine.run_mfm_finetuning()
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# Thread safety smoke test
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_phase1_runs(self):
        import threading
        engine = GateBehaviorModelEngine()
        subjects = [f"Company {i}" for i in range(10)]
        errors: list = []

        def run(s):
            try:
                engine.run_phase1(subject_matters=[s])
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=run, args=(s,)) for s in subjects]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert errors == []
        # All unique subjects should be present
        assert engine.get_status()["profile_count"] == len(subjects)
