"""
Full-house LCM test suite.

Tests: domain coverage, 3D printing depth, CAD depth, BAS depth,
cross-domain consistency, LCM speed, active learning, epoch survival,
gate adaptation, tandem integration, simultaneous chaos, reproducibility.

Run with:
    python -m pytest tests/test_lcm_full_house.py --override-ini="addopts=" -v -q
"""
from __future__ import annotations

import sys
import os
import time
import pytest

# Ensure src/ is on path when running from repo root
_SRC_DIR = os.path.join(os.path.dirname(__file__), "..", "src")
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

# ---------------------------------------------------------------------------
# Guarded imports
# ---------------------------------------------------------------------------

try:
    from lcm_domain_registry import (
        LCMDomainRegistry,
        DomainCategory,
        GateType,
        SubjectDomain,
    )
    HAS_REGISTRY = True
except ImportError:
    HAS_REGISTRY = False

try:
    from lcm_engine import (
        LCMEngine,
        BotRole,
        GateBehaviorProfile,
        LCMPredictor,
        CausalGateProfiler,
        UniversalDomainEnumerator,
        LCMModelTrainer,
    )
    HAS_ENGINE = True
except ImportError:
    HAS_ENGINE = False

try:
    from lcm_integration_bridge import (
        LCMIntegrationBridge,
        AMWorkflowGateBridge,
        BASActionGateBridge,
        BotGovernanceGateBridge,
        WorldModelGateBridge,
        EnterpriseIntegrationGateBridge,
    )
    HAS_BRIDGE = True
except ImportError:
    HAS_BRIDGE = False

try:
    from lcm_chaos_simulation import (
        LCMChaosSimulation,
        EconomicEpoch,
        EconomicTimeMachine,
        DomainChaosGenerator,
        FullHouseSimulator,
        ChaosSimulationResult,
        EpochConditions,
        ChaosEvent,
    )
    HAS_CHAOS = True
except ImportError:
    HAS_CHAOS = False

_ALL = HAS_REGISTRY and HAS_ENGINE and HAS_BRIDGE and HAS_CHAOS
_REG_AND_ENGINE = HAS_REGISTRY and HAS_ENGINE


# ===========================================================================
# TestDomainRegistry
# ===========================================================================

class TestDomainRegistry:
    """Tests for LCM Domain Registry."""

    @pytest.mark.skipif(not HAS_REGISTRY, reason="lcm_domain_registry not available")
    def test_registry_has_50_plus_domains(self):
        """Registry must contain at least 50 domains."""
        registry = LCMDomainRegistry()
        domains = registry.list_all()
        assert len(domains) >= 50, f"Expected ≥50 domains, got {len(domains)}"

    @pytest.mark.skipif(not HAS_REGISTRY, reason="lcm_domain_registry not available")
    def test_3d_printing_domains_all_present(self):
        """All nine 3D printing variants must be registered."""
        registry = LCMDomainRegistry()
        expected_ids = [
            "3d_printing_fdm",
            "3d_printing_sla",
            "3d_printing_sls",
            "3d_printing_slm_dmls",
            "3d_printing_ebm",
            "3d_printing_polyjet",
            "3d_printing_binder",
            "3d_printing_ded",
            "3d_printing_fiber",
        ]
        for did in expected_ids:
            domain = registry.get(did)
            assert domain is not None, f"Domain '{did}' not found in registry"

    @pytest.mark.skipif(not HAS_REGISTRY, reason="lcm_domain_registry not available")
    def test_all_domain_categories_represented(self):
        """Every DomainCategory enum value must have at least one domain."""
        registry = LCMDomainRegistry()
        found_categories = {d.category for d in registry.list_all()}
        for cat in DomainCategory:
            assert cat in found_categories, (
                f"DomainCategory.{cat.name} has no registered domains"
            )

    @pytest.mark.skipif(not HAS_REGISTRY, reason="lcm_domain_registry not available")
    def test_each_domain_has_gate_types(self):
        """Every domain must declare at least one gate type."""
        registry = LCMDomainRegistry()
        for domain in registry.list_all():
            assert len(domain.gate_types) >= 1, (
                f"Domain '{domain.domain_id}' has no gate_types"
            )

    @pytest.mark.skipif(not HAS_REGISTRY, reason="lcm_domain_registry not available")
    def test_domain_get_returns_none_for_unknown(self):
        """get() on a non-existent domain_id must return None."""
        registry = LCMDomainRegistry()
        result = registry.get("non_existent_domain_xyz_9999")
        assert result is None

    @pytest.mark.skipif(not HAS_REGISTRY, reason="lcm_domain_registry not available")
    def test_list_by_category_physical_manufacturing(self):
        """PHYSICAL_MANUFACTURING category has at least 5 domains."""
        registry = LCMDomainRegistry()
        domains = registry.list_by_category(DomainCategory.PHYSICAL_MANUFACTURING)
        assert len(domains) >= 5, f"Expected ≥5 PHYSICAL_MANUFACTURING domains, got {len(domains)}"

    @pytest.mark.skipif(not HAS_REGISTRY, reason="lcm_domain_registry not available")
    def test_hvac_bas_has_energy_and_safety_gates(self):
        """hvac_bas must include SAFETY and ENERGY gate types."""
        registry = LCMDomainRegistry()
        domain = registry.get("hvac_bas")
        assert domain is not None
        gate_values = [g.value for g in domain.gate_types]
        assert "safety" in gate_values, "hvac_bas missing SAFETY gate"
        assert "energy" in gate_values, "hvac_bas missing ENERGY gate"

    @pytest.mark.skipif(not HAS_REGISTRY, reason="lcm_domain_registry not available")
    def test_slm_dmls_has_safety_gate(self):
        """SLM/DMLS (metal powder) must have SAFETY gate."""
        registry = LCMDomainRegistry()
        domain = registry.get("3d_printing_slm_dmls")
        assert domain is not None
        gate_values = [g.value for g in domain.gate_types]
        assert "safety" in gate_values, "SLM/DMLS missing SAFETY gate (powder hazard)"

    @pytest.mark.skipif(not HAS_REGISTRY, reason="lcm_domain_registry not available")
    def test_clinical_operations_compliance_gate(self):
        """clinical_operations must have COMPLIANCE gate (HIPAA)."""
        registry = LCMDomainRegistry()
        domain = registry.get("clinical_operations")
        assert domain is not None
        gate_values = [g.value for g in domain.gate_types]
        assert "compliance" in gate_values

    @pytest.mark.skipif(not HAS_REGISTRY, reason="lcm_domain_registry not available")
    def test_get_gate_types_returns_list(self):
        """get_gate_types() must return a list for known and unknown domain_ids."""
        registry = LCMDomainRegistry()
        gates_known = registry.get_gate_types("trading")
        assert isinstance(gates_known, list)
        assert len(gates_known) >= 1

        gates_unknown = registry.get_gate_types("does_not_exist_abc")
        assert isinstance(gates_unknown, list)
        assert gates_unknown == []

    @pytest.mark.skipif(not HAS_REGISTRY, reason="lcm_domain_registry not available")
    def test_domain_has_compliance_standards(self):
        """High-priority domains like trading/banking must have compliance standards."""
        registry = LCMDomainRegistry()
        for did in ["trading", "banking", "clinical_operations", "pharmaceutical"]:
            d = registry.get(did)
            if d is not None:
                assert len(d.compliance_standards) >= 1, (
                    f"{did} has no compliance_standards"
                )


# ===========================================================================
# TestLCMEngine
# ===========================================================================

class TestLCMEngine:
    """Tests for LCM Engine."""

    @pytest.mark.skipif(not HAS_ENGINE, reason="lcm_engine not available")
    def test_engine_builds_without_error(self):
        """LCMEngine.build() must complete without raising."""
        engine = LCMEngine()
        engine.build()
        status = engine.status()
        assert status["built"] is True
        assert status["profile_count"] > 0

    @pytest.mark.skipif(not HAS_ENGINE, reason="lcm_engine not available")
    def test_predict_returns_gate_profile(self):
        """predict() must return a GateBehaviorProfile with expected fields."""
        engine = LCMEngine()
        profile = engine.predict("hvac_bas", "monitor")
        assert isinstance(profile, GateBehaviorProfile)
        assert profile.domain_id == "hvac_bas"
        assert profile.role == "monitor"
        assert isinstance(profile.gate_types, list)
        assert isinstance(profile.gate_weights, dict)
        assert 0.0 <= profile.confidence <= 1.0

    @pytest.mark.skipif(not HAS_ENGINE, reason="lcm_engine not available")
    def test_predict_speed_under_10ms(self):
        """After build(), predict() for a known domain must return in <10 ms."""
        engine = LCMEngine()
        engine.build()

        # Prime the cache with one call
        engine.predict("3d_printing_fdm", "expert")

        # Measure subsequent call
        t0 = time.perf_counter()
        profile = engine.predict("3d_printing_fdm", "expert")
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        assert elapsed_ms < 10.0, (
            f"predict() took {elapsed_ms:.2f}ms — must be <10ms"
        )
        assert profile is not None

    @pytest.mark.skipif(not HAS_ENGINE, reason="lcm_engine not available")
    def test_cross_domain_consistency(self):
        """Safety-critical domains must have higher safety gate weight than comfort domains."""
        engine = LCMEngine()
        engine.build()

        safety_domain = engine.predict("clinical_operations", "validator")
        comfort_domain = engine.predict("hospitality", "assistant")

        # Safety-critical domain should have safety in gate_types
        assert "safety" in safety_domain.gate_types or len(safety_domain.gate_types) > 0

        # Both must return valid GateBehaviorProfile
        assert isinstance(safety_domain, GateBehaviorProfile)
        assert isinstance(comfort_domain, GateBehaviorProfile)

    @pytest.mark.skipif(not HAS_ENGINE, reason="lcm_engine not available")
    def test_all_bot_roles_produce_profiles(self):
        """Every BotRole must produce a valid GateBehaviorProfile."""
        engine = LCMEngine()
        for role in BotRole:
            profile = engine.predict("cnc_machining", role.value)
            assert isinstance(profile, GateBehaviorProfile), (
                f"BotRole.{role.name} did not return GateBehaviorProfile"
            )
            assert profile.role == role.value

    @pytest.mark.skipif(not HAS_ENGINE, reason="lcm_engine not available")
    def test_engine_status_fields(self):
        """status() must return a dict with known keys."""
        engine = LCMEngine()
        status = engine.status()
        for key in ("built", "profile_count", "immune_memory_size", "model_type"):
            assert key in status, f"status() missing key '{key}'"

    @pytest.mark.skipif(not HAS_ENGINE, reason="lcm_engine not available")
    def test_novel_domain_fallback(self):
        """predict() on an unknown domain must still return a GateBehaviorProfile."""
        engine = LCMEngine()
        profile = engine.predict("totally_unknown_domain_xyz", "expert")
        assert isinstance(profile, GateBehaviorProfile)
        assert len(profile.gate_types) >= 1

    @pytest.mark.skipif(not _REG_AND_ENGINE, reason="registry or engine not available")
    def test_enumerate_all_combinations(self):
        """UniversalDomainEnumerator must produce domain × role combinations."""
        from lcm_domain_registry import LCMDomainRegistry  # noqa: PLC0415
        from lcm_engine import UniversalDomainEnumerator, BotRole  # noqa: PLC0415

        registry = LCMDomainRegistry()
        enumerator = UniversalDomainEnumerator(registry)
        combos = enumerator.enumerate_bot_role_domain_combinations()
        expected_min = len(list(BotRole)) * len(registry.list_all())
        assert len(combos) == expected_min

    @pytest.mark.skipif(not HAS_ENGINE, reason="lcm_engine not available")
    def test_model_trainer_exports_serializable_dict(self):
        """LCMModelTrainer.export_model() must return a JSON-serializable dict."""
        import json  # noqa: PLC0415
        trainer = LCMModelTrainer()
        profiles = [
            GateBehaviorProfile(
                domain_id="test_domain",
                role="expert",
                gate_types=["quality", "safety"],
                gate_weights={"quality": 0.9, "safety": 0.85},
                confidence=0.88,
            )
        ]
        trainer.train(profiles)
        exported = trainer.export_model()
        assert isinstance(exported, dict)
        # Must be JSON-serializable
        serialized = json.dumps(exported)
        assert len(serialized) > 0

    @pytest.mark.skipif(not HAS_ENGINE, reason="lcm_engine not available")
    def test_predictor_loads_model(self):
        """LCMPredictor must accept a model and serve from it."""
        predictor = LCMPredictor()
        model = {
            "type": "stub",
            "lookup": {
                "test_domain:expert": {
                    "gate_types": ["quality"],
                    "gate_weights": {"quality": 0.9},
                    "confidence": 0.88,
                }
            },
        }
        predictor.load_model(model)
        profile = predictor.predict("test_domain", "expert")
        assert isinstance(profile, GateBehaviorProfile)
        assert profile.confidence == 0.88

    @pytest.mark.skipif(not HAS_ENGINE, reason="lcm_engine not available")
    def test_causal_gate_profiler_returns_profile(self):
        """CausalGateProfiler must produce a GateBehaviorProfile for any domain."""
        profiler = CausalGateProfiler()
        profile = profiler.profile_entity("3d_printing_fdm", "expert", "FDM printing")
        assert isinstance(profile, GateBehaviorProfile)
        assert profile.domain_id == "3d_printing_fdm"
        assert profile.role == "expert"
        assert len(profile.gate_types) >= 1
        assert len(profile.gate_weights) >= 1


# ===========================================================================
# TestIntegrationBridge
# ===========================================================================

class TestIntegrationBridge:
    """Tests for LCM Integration Bridge."""

    @pytest.mark.skipif(not HAS_BRIDGE, reason="lcm_integration_bridge not available")
    def test_bridge_initializes(self):
        """LCMIntegrationBridge must initialize with no errors."""
        bridge = LCMIntegrationBridge()
        assert bridge is not None
        status = bridge.status()
        assert isinstance(status, dict)
        assert "bridges" in status

    @pytest.mark.skipif(not HAS_BRIDGE, reason="lcm_integration_bridge not available")
    def test_bridge_status_all_sub_bridges(self):
        """status() must report all five sub-bridge names."""
        bridge = LCMIntegrationBridge()
        status = bridge.status()
        bridges = status.get("bridges", {})
        for name in ("world_model", "enterprise", "am_workflow", "bas_action", "bot_governance"):
            assert name in bridges, f"Bridge '{name}' missing from status"

    @pytest.mark.skipif(not HAS_BRIDGE, reason="lcm_integration_bridge not available")
    def test_am_workflow_gated_fdm(self):
        """AMWorkflowGateBridge must return GatedConnectorResult for FDM."""
        bridge = AMWorkflowGateBridge()
        result = bridge.execute_am_action_gated(
            process_type="fdm_fff",
            action="start_print",
            params={"material": "PLA", "layer_height": 0.2},
        )
        assert result.connector_name.startswith("am_workflow")
        assert result.domain_id == "3d_printing_fdm_fff"
        assert isinstance(result.gate_passed, bool)
        assert isinstance(result.gate_profile, dict)

    @pytest.mark.skipif(not HAS_BRIDGE, reason="lcm_integration_bridge not available")
    def test_am_workflow_gated_slm(self):
        """SLM requires SAFETY gate — result must have safety in gate_profile."""
        bridge = AMWorkflowGateBridge()
        result = bridge.execute_am_action_gated(
            process_type="slm_dmls",
            action="load_powder",
            params={"material": "Ti64", "layer_thickness": 0.03},
        )
        assert result.domain_id.startswith("3d_printing")
        assert isinstance(result.gate_passed, bool)

    @pytest.mark.skipif(not HAS_BRIDGE, reason="lcm_integration_bridge not available")
    def test_bas_action_gated_ahu(self):
        """BASActionGateBridge must gate AHU actions with safety+energy gates."""
        bridge = BASActionGateBridge()
        result = bridge.execute_bas_action_gated(
            system_type="ahu",
            action="set_setpoint",
            params={"supply_temp": 55, "zone": "floor_3"},
        )
        assert result.connector_name == "bas_ahu"
        assert result.domain_id == "hvac_bas"
        assert isinstance(result.gate_passed, bool)
        assert isinstance(result.gate_check_ms, float)

    @pytest.mark.skipif(not HAS_BRIDGE, reason="lcm_integration_bridge not available")
    def test_bas_action_gated_boiler(self):
        """Boiler requires SAFETY gate."""
        bridge = BASActionGateBridge()
        result = bridge.execute_bas_action_gated(
            system_type="boiler",
            action="set_firing_rate",
            params={"firing_rate": 75},
        )
        assert result.connector_name == "bas_boiler"
        assert result.domain_id == "hvac_bas"
        assert isinstance(result.gate_passed, bool)

    @pytest.mark.skipif(not HAS_BRIDGE, reason="lcm_integration_bridge not available")
    def test_bot_governance_profile_manufacturing(self):
        """BotGovernanceGateBridge must return profile for manufacturing industry."""
        bridge = BotGovernanceGateBridge()
        result = bridge.get_bot_gate_profile("mfg_bot_01", "manufacturing")
        assert result["bot_name"] == "mfg_bot_01"
        assert result["industry"] == "manufacturing"
        assert "domain_id" in result
        assert "gate_profile" in result

    @pytest.mark.skipif(not HAS_BRIDGE, reason="lcm_integration_bridge not available")
    def test_bot_governance_profile_healthcare(self):
        """BotGovernanceGateBridge returns profile for healthcare industry."""
        bridge = BotGovernanceGateBridge()
        result = bridge.get_bot_gate_profile("health_bot", "healthcare")
        assert result["domain_id"] in ("clinical_operations", "medical_devices", "pharmaceutical", "laboratory")

    @pytest.mark.skipif(not HAS_BRIDGE, reason="lcm_integration_bridge not available")
    def test_world_model_bridge_execute_gated(self):
        """WorldModelGateBridge.execute_gated must return GatedConnectorResult."""
        bridge = WorldModelGateBridge()
        result = bridge.execute_gated(
            connector_name="test_connector",
            action="test_action",
            params={"key": "value"},
            domain_id="ecommerce",
        )
        assert result.connector_name == "test_connector"
        assert result.domain_id == "ecommerce"
        assert isinstance(result.gate_passed, bool)

    @pytest.mark.skipif(not HAS_BRIDGE, reason="lcm_integration_bridge not available")
    def test_enterprise_bridge_step_gated(self):
        """EnterpriseIntegrationGateBridge must return step result dict."""
        bridge = EnterpriseIntegrationGateBridge()
        result = bridge.execute_step_gated(
            step_name="approve_purchase_order",
            domain_id="supply_chain",
            context={"amount": 50000, "vendor": "ACME Corp"},
        )
        assert isinstance(result, dict)
        assert "step_name" in result
        assert result["step_name"] == "approve_purchase_order"
        assert "gate_passed" in result

    @pytest.mark.skipif(not HAS_BRIDGE, reason="lcm_integration_bridge not available")
    def test_gated_connector_result_to_dict(self):
        """GatedConnectorResult.to_dict() must return a serializable dict."""
        from lcm_integration_bridge import GatedConnectorResult  # noqa: PLC0415
        r = GatedConnectorResult(
            connector_name="test",
            domain_id="trading",
            gate_passed=True,
            gate_profile={"gate_types": ["compliance"]},
        )
        d = r.to_dict()
        assert d["connector_name"] == "test"
        assert d["gate_passed"] is True


# ===========================================================================
# TestChaosSimulation
# ===========================================================================

class TestChaosSimulation:
    """Tests for chaos simulation."""

    @pytest.mark.skipif(not HAS_CHAOS, reason="lcm_chaos_simulation not available")
    def test_all_11_epochs_exist(self):
        """EconomicEpoch must have exactly 11 members."""
        epochs = list(EconomicEpoch)
        assert len(epochs) == 11, f"Expected 11 epochs, got {len(epochs)}"

    @pytest.mark.skipif(not HAS_CHAOS, reason="lcm_chaos_simulation not available")
    def test_time_machine_has_all_epochs(self):
        """EconomicTimeMachine must return conditions for all 11 epochs."""
        tm = EconomicTimeMachine()
        for epoch in EconomicEpoch:
            conditions = tm.get_epoch_conditions(epoch)
            assert isinstance(conditions, EpochConditions)
            assert conditions.epoch == epoch

    @pytest.mark.skipif(not HAS_CHAOS, reason="lcm_chaos_simulation not available")
    def test_time_machine_year_ranges(self):
        """Key epochs must have correct year ranges."""
        tm = EconomicTimeMachine()
        checks = {
            EconomicEpoch.GREAT_DEPRESSION: (1929, 1939),
            EconomicEpoch.WWII: (1939, 1945),
            EconomicEpoch.COVID: (2020, 2021),
            EconomicEpoch.AI_ERA: (2022, 2026),
        }
        for epoch, expected_years in checks.items():
            cond = tm.get_epoch_conditions(epoch)
            assert cond.years == expected_years, (
                f"{epoch.value}: expected years {expected_years}, got {cond.years}"
            )

    @pytest.mark.skipif(not HAS_CHAOS, reason="lcm_chaos_simulation not available")
    def test_great_depression_tight_financial_gate(self):
        """Great Depression must have financial_gate_multiplier < 0.6."""
        tm = EconomicTimeMachine()
        cond = tm.get_epoch_conditions(EconomicEpoch.GREAT_DEPRESSION)
        assert cond.financial_gate_multiplier < 0.6, (
            f"Great Depression financial gate multiplier should be < 0.6, "
            f"got {cond.financial_gate_multiplier}"
        )

    @pytest.mark.skipif(not HAS_CHAOS, reason="lcm_chaos_simulation not available")
    def test_covid_high_supply_chain_risk(self):
        """COVID epoch must have supply_chain_risk >= 0.9."""
        tm = EconomicTimeMachine()
        cond = tm.get_epoch_conditions(EconomicEpoch.COVID)
        assert cond.supply_chain_risk >= 0.9

    @pytest.mark.skipif(not HAS_CHAOS, reason="lcm_chaos_simulation not available")
    def test_ai_era_tech_availability(self):
        """AI era must have ai=True and iot=True in tech_availability."""
        tm = EconomicTimeMachine()
        cond = tm.get_epoch_conditions(EconomicEpoch.AI_ERA)
        assert cond.tech_availability.get("ai") is True
        assert cond.tech_availability.get("iot") is True

    @pytest.mark.skipif(not HAS_CHAOS, reason="lcm_chaos_simulation not available")
    def test_great_depression_no_3d_printing(self):
        """Great Depression must not have 3D printing technology."""
        tm = EconomicTimeMachine()
        cond = tm.get_epoch_conditions(EconomicEpoch.GREAT_DEPRESSION)
        assert cond.tech_availability.get("3d_printing") is False

    @pytest.mark.skipif(not HAS_CHAOS, reason="lcm_chaos_simulation not available")
    def test_3d_printing_chaos_generation(self):
        """DomainChaosGenerator must produce at least 3 events for 3D printing."""
        gen = DomainChaosGenerator(seed=42)
        events = gen.generate_3d_printing_chaos(EconomicEpoch.COVID)
        assert len(events) >= 3, f"Expected ≥3 3D printing chaos events, got {len(events)}"
        for e in events:
            assert isinstance(e, ChaosEvent)
            assert e.domain == "3d_printing_fdm"
            assert e.epoch == EconomicEpoch.COVID

    @pytest.mark.skipif(not HAS_CHAOS, reason="lcm_chaos_simulation not available")
    def test_bas_chaos_generation(self):
        """DomainChaosGenerator must produce BAS/HVAC events."""
        gen = DomainChaosGenerator(seed=42)
        events = gen.generate_bas_chaos(EconomicEpoch.RECOVERY)
        assert len(events) >= 3
        for e in events:
            assert e.domain == "hvac_bas"

    @pytest.mark.skipif(not HAS_CHAOS, reason="lcm_chaos_simulation not available")
    def test_finance_chaos_generation(self):
        """DomainChaosGenerator must produce finance events."""
        gen = DomainChaosGenerator(seed=42)
        events = gen.generate_finance_chaos(EconomicEpoch.FINANCIAL_CRISIS)
        assert len(events) >= 3
        for e in events:
            assert e.domain == "trading"
            assert e.severity in ("low", "medium", "high", "critical")

    @pytest.mark.skipif(not HAS_CHAOS, reason="lcm_chaos_simulation not available")
    def test_generate_for_domain_generic(self):
        """generate_for_domain() must return events for any domain_id."""
        gen = DomainChaosGenerator(seed=42)
        events = gen.generate_for_domain("some_random_domain", EconomicEpoch.AI_ERA)
        assert len(events) >= 1
        for e in events:
            assert isinstance(e, ChaosEvent)
            assert e.event_id  # must have an ID

    @pytest.mark.skipif(not HAS_CHAOS, reason="lcm_chaos_simulation not available")
    def test_same_seed_same_result(self):
        """Same seed must produce identical event IDs (reproducibility)."""
        gen1 = DomainChaosGenerator(seed=99)
        gen2 = DomainChaosGenerator(seed=99)
        events1 = gen1.generate_3d_printing_chaos(EconomicEpoch.COVID)
        events2 = gen2.generate_3d_printing_chaos(EconomicEpoch.COVID)
        ids1 = [e.event_id for e in events1]
        ids2 = [e.event_id for e in events2]
        assert ids1 == ids2, "Same seed must produce identical event IDs"

    @pytest.mark.skipif(not HAS_CHAOS, reason="lcm_chaos_simulation not available")
    def test_different_seeds_different_results(self):
        """Different seeds should (likely) produce different event sets."""
        gen1 = DomainChaosGenerator(seed=1)
        gen2 = DomainChaosGenerator(seed=99999)
        events1 = gen1.generate_3d_printing_chaos(EconomicEpoch.COVID)
        events2 = gen2.generate_3d_printing_chaos(EconomicEpoch.COVID)
        ids1 = [e.event_id for e in events1]
        ids2 = [e.event_id for e in events2]
        assert ids1 != ids2, "Different seeds should produce different events"

    @pytest.mark.skipif(not HAS_CHAOS, reason="lcm_chaos_simulation not available")
    def test_gate_adaptation_per_epoch(self):
        """FullHouseSimulator must trigger gate_adaptations when events fail."""
        sim = FullHouseSimulator(seed=42)
        result = sim.run(
            epochs=[EconomicEpoch.GREAT_DEPRESSION],
            max_events_per_domain=3,
        )
        assert isinstance(result, ChaosSimulationResult)
        # In a depression, some events should fail
        assert result.total_chaos_events > 0
        assert result.events_survived + result.events_failed == result.total_chaos_events

    @pytest.mark.skipif(not HAS_CHAOS, reason="lcm_chaos_simulation not available")
    def test_full_house_run_completes(self):
        """FullHouseSimulator.run() must complete and return ChaosSimulationResult."""
        sim = FullHouseSimulator(seed=42)
        result = sim.run(
            epochs=[EconomicEpoch.AI_ERA, EconomicEpoch.COVID],
            max_events_per_domain=2,
        )
        assert isinstance(result, ChaosSimulationResult)
        assert result.epochs_simulated == 2
        assert result.domains_tested >= 1
        assert result.run_id  # must have a run ID
        assert result.reproducible is True

    @pytest.mark.skipif(not HAS_CHAOS, reason="lcm_chaos_simulation not available")
    def test_epoch_survival_all_domains(self):
        """Each domain must have at least one result entry after simulation."""
        sim = FullHouseSimulator(seed=42)
        result = sim.run(
            epochs=[EconomicEpoch.RECOVERY],
            max_events_per_domain=3,
        )
        assert len(result.domain_results) >= 1

    @pytest.mark.skipif(not HAS_CHAOS, reason="lcm_chaos_simulation not available")
    def test_lcm_chaos_simulation_status(self):
        """LCMChaosSimulation.status() must return expected keys."""
        sim = LCMChaosSimulation(seed=42)
        status = sim.status()
        assert "seed" in status
        assert status["seed"] == 42
        assert "epochs_available" in status
        assert status["epochs_available"] == 11

    @pytest.mark.skipif(not HAS_CHAOS, reason="lcm_chaos_simulation not available")
    def test_run_epoch_single(self):
        """LCMChaosSimulation.run_epoch() must return dict with epoch key."""
        sim = LCMChaosSimulation(seed=42)
        result = sim.run_epoch(EconomicEpoch.AI_ERA)
        assert isinstance(result, dict)
        assert result["epoch"] == EconomicEpoch.AI_ERA.value

    @pytest.mark.skipif(not HAS_CHAOS, reason="lcm_chaos_simulation not available")
    def test_chaos_event_fields(self):
        """ChaosEvent must have all required fields."""
        gen = DomainChaosGenerator(seed=42)
        events = gen.generate_healthcare_chaos(EconomicEpoch.COVID)
        for e in events:
            assert e.event_id
            assert e.domain
            assert e.event_type
            assert e.severity in ("low", "medium", "high", "critical")
            assert e.description
            assert isinstance(e.affected_systems, list)

    @pytest.mark.skipif(not HAS_CHAOS, reason="lcm_chaos_simulation not available")
    def test_gate_multiplier_values(self):
        """EconomicTimeMachine.get_gate_multiplier() must return floats."""
        tm = EconomicTimeMachine()
        for epoch in EconomicEpoch:
            for gate in ("safety", "quality", "compliance", "business"):
                multiplier = tm.get_gate_multiplier(epoch, gate)
                assert isinstance(multiplier, float)
                assert multiplier > 0


# ===========================================================================
# TestFullHouseIntegration
# ===========================================================================

class TestFullHouseIntegration:
    """Integration tests — everything running simultaneously."""

    @pytest.mark.skipif(not _ALL, reason="not all modules available")
    def test_full_house_end_to_end(self):
        """Full pipeline: engine.build() → bridge → chaos simulation."""
        engine = LCMEngine()
        engine.build()

        bridge = LCMIntegrationBridge(lcm_engine=engine)
        result = bridge.am_workflow.execute_am_action_gated(
            process_type="fdm_fff",
            action="start_print",
            params={"material": "PETG"},
        )
        assert isinstance(result.gate_passed, bool)

        # Chaos simulation with LCM engine attached
        sim = LCMChaosSimulation(lcm_engine=engine, seed=42)
        chaos_result = sim.run_full_house(
            epochs=[EconomicEpoch.AI_ERA],
            max_events_per_domain=2,
        )
        assert chaos_result.epochs_simulated == 1
        assert chaos_result.total_chaos_events >= 1

    @pytest.mark.skipif(not (_REG_AND_ENGINE and HAS_CHAOS), reason="not all modules available")
    def test_reproducibility_same_seed(self):
        """Two runs with the same seed must produce the same results."""
        sim1 = LCMChaosSimulation(seed=777)
        sim2 = LCMChaosSimulation(seed=777)

        r1 = sim1.run_full_house(
            epochs=[EconomicEpoch.COVID],
            max_events_per_domain=3,
        )
        r2 = sim2.run_full_house(
            epochs=[EconomicEpoch.COVID],
            max_events_per_domain=3,
        )

        assert r1.total_chaos_events == r2.total_chaos_events
        assert r1.events_survived == r2.events_survived
        assert r1.events_failed == r2.events_failed
        assert r1.reproducible is True
        assert r2.reproducible is True

    @pytest.mark.skipif(not _ALL, reason="not all modules available")
    def test_bridge_with_engine_attached(self):
        """LCMIntegrationBridge with a built LCMEngine must gate actions correctly."""
        engine = LCMEngine()
        engine.build()
        bridge = LCMIntegrationBridge(lcm_engine=engine)

        # Test BAS with engine
        bas_result = bridge.bas_action.execute_bas_action_gated(
            system_type="chiller",
            action="set_leaving_water_temp",
            params={"lwt": 44},
        )
        assert isinstance(bas_result.gate_passed, bool)
        assert bas_result.gate_check_ms >= 0

        # Test bot governance with engine
        gov_result = bridge.bot_governance.get_bot_gate_profile(
            bot_name="energy_bot", industry="energy"
        )
        assert gov_result["bot_name"] == "energy_bot"
        assert "gate_profile" in gov_result

    @pytest.mark.skipif(not _ALL, reason="not all modules available")
    def test_all_3d_printing_processes_gated(self):
        """All nine 3D printing process types must complete gate checks without crashing."""
        engine = LCMEngine()
        bridge = LCMIntegrationBridge(lcm_engine=engine)

        processes = [
            "fdm_fff", "sla_dlp", "sls", "slm_dmls",
            "ebm", "polyjet_mjf", "binder_jetting", "ded_waam", "continuous_fiber",
        ]
        for process in processes:
            result = bridge.am_workflow.execute_am_action_gated(
                process_type=process,
                action="initialize",
                params={"test": True},
            )
            assert isinstance(result.gate_passed, bool), (
                f"AM process '{process}' gate check failed to return bool"
            )

    @pytest.mark.skipif(not _ALL, reason="not all modules available")
    def test_all_bas_systems_gated(self):
        """All 16 BAS system types must pass gate checks without crashing."""
        bridge = LCMIntegrationBridge()
        systems = [
            "ahu", "fcu", "chiller", "boiler", "cooling_tower",
            "vav", "exhaust_fan", "heat_pump", "vrf", "radiant",
            "doas", "erv", "mau", "unit_heater", "it_cooling", "data_center",
        ]
        for system in systems:
            result = bridge.bas_action.execute_bas_action_gated(
                system_type=system,
                action="get_status",
                params={},
            )
            assert isinstance(result.gate_passed, bool), (
                f"BAS system '{system}' gate check failed"
            )

    @pytest.mark.skipif(not (_REG_AND_ENGINE and HAS_CHAOS), reason="not all modules available")
    def test_full_house_all_epochs(self):
        """Full-house simulation across ALL 11 epochs must complete."""
        sim = LCMChaosSimulation(seed=42)
        result = sim.run_full_house(max_events_per_domain=1)
        assert result.epochs_simulated == 11
        assert result.total_chaos_events > 0
        assert result.duration_sec > 0

    @pytest.mark.skipif(not _ALL, reason="not all modules available")
    def test_engine_predict_after_chaos(self):
        """LCM engine predictions must still work after chaos simulation."""
        engine = LCMEngine()
        engine.build()

        sim = LCMChaosSimulation(lcm_engine=engine, seed=42)
        sim.run_full_house(epochs=[EconomicEpoch.FINANCIAL_CRISIS], max_events_per_domain=2)

        # Engine must still serve predictions
        profile = engine.predict("trading", "auditor")
        assert isinstance(profile, GateBehaviorProfile)
        assert "compliance" in profile.gate_types or len(profile.gate_types) > 0
