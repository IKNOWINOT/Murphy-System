"""Tests for ArchitectureEvolutionEngine — architecture_evolution module."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.architecture_evolution import ArchitectureEvolutionEngine, EvolutionIndicators


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _engine(**kw) -> ArchitectureEvolutionEngine:
    return ArchitectureEvolutionEngine(**kw)


def _populated_engine() -> ArchitectureEvolutionEngine:
    """Return an engine with a handful of modules and gaps registered."""
    e = _engine()
    e.register_module("core", ["utils", "config"], subsystem="foundation")
    e.register_module("utils", [], subsystem="foundation")
    e.register_module("config", [], subsystem="foundation")
    e.register_module("api", ["core", "auth"], subsystem="services")
    e.register_module("auth", ["utils"], subsystem="services")
    e.register_gap("gap_1", "Missing caching layer", category="general")
    e.register_gap("gap_2", "No rate-limiting module", category="general")
    e.register_compliance_domain("SOC2")
    return e


# ---------------------------------------------------------------------------
# 1. Functional tests
# ---------------------------------------------------------------------------

class TestFunctional:
    def test_analyze_returns_evolution_indicators(self):
        result = _engine().analyze()
        assert isinstance(result, EvolutionIndicators)

    def test_default_analysis(self):
        result = _engine().analyze()
        assert isinstance(result.es, float)
        assert isinstance(result.dependency_ratio, float)
        assert isinstance(result.predicted_modules, list)
        assert isinstance(result.stress_warnings, list)
        assert isinstance(result.recommended_actions, list)

    def test_register_module(self):
        e = _engine()
        e.register_module("mod_a", ["mod_b"])
        result = e.analyze()
        assert result.dependency_ratio > 0

    def test_register_gap(self):
        e = _engine()
        e.register_gap("g1", "A capability gap")
        result = e.analyze()
        assert result.module_demand >= 1.0

    def test_register_compliance_domain(self):
        e = _engine()
        e.register_compliance_domain("GDPR")
        result = e.analyze()
        assert result.regulatory_expansion >= 1.0


# ---------------------------------------------------------------------------
# 2. Indicator computation tests
# ---------------------------------------------------------------------------

class TestIndicators:
    def test_dependency_ratio_calculation(self):
        e = _engine()
        e.register_module("a", ["b", "c"])
        e.register_module("b", [])
        e.register_module("c", [])
        result = e.analyze()
        expected = 2 / 3
        assert abs(result.dependency_ratio - round(expected, 2)) < 0.05

    def test_complexity_growth_scaling(self):
        low = _engine()
        low.register_module("a", ["b"])
        low.register_module("b", [])

        high = _engine()
        for i in range(5):
            high.register_module(f"m{i}", [f"d{j}" for j in range(4)])
            for j in range(4):
                high.register_module(f"d{j}", [])

        r_low = low.analyze()
        r_high = high.analyze()
        assert r_high.complexity_growth >= r_low.complexity_growth

    def test_module_demand_from_gaps(self):
        e = _engine()
        for i in range(8):
            e.register_gap(f"g{i}", f"Gap {i}")
        result = e.analyze()
        assert result.module_demand >= 4.0

    def test_regulatory_expansion(self):
        e = _engine()
        for d in ["GDPR", "SOC2", "HIPAA", "PCI-DSS"]:
            e.register_compliance_domain(d)
        result = e.analyze()
        assert result.regulatory_expansion == 4.0

    def test_es_is_average(self):
        result = _populated_engine().analyze()
        expected = (
            result.complexity_growth
            + result.module_demand
            + result.regulatory_expansion
            + result.optimization_potential
            + result.research_opportunity
        ) / 5.0
        assert abs(result.es - round(expected, 2)) < 0.02


# ---------------------------------------------------------------------------
# 3. Prediction tests
# ---------------------------------------------------------------------------

class TestPredictions:
    def test_predict_future_modules_returns_list(self):
        result = _populated_engine().predict_future_modules()
        assert isinstance(result, list)

    def test_predict_modules_with_gaps(self):
        e = _engine()
        e.register_gap("cache", "Need caching layer")
        predicted = e.predict_future_modules()
        assert len(predicted) >= 1

    def test_predicted_modules_structure(self):
        e = _engine()
        e.register_gap("cache", "Need caching")
        predicted = e.predict_future_modules()
        for m in predicted:
            assert "name" in m
            assert "purpose" in m
            assert "justification" in m


# ---------------------------------------------------------------------------
# 4. Stress detection tests
# ---------------------------------------------------------------------------

class TestStressDetection:
    def test_detect_stress_high_dependency(self):
        e = _engine()
        # 2 modules each with 4 deps → total_deps=8, total_modules=2, ratio=4.0 > 3
        e.register_module("hub_a", ["d1", "d2", "d3", "d4"], subsystem="core")
        e.register_module("hub_b", ["d5", "d6", "d7", "d8"], subsystem="core")
        warnings = e.detect_architecture_stress()
        assert any("dependency density" in w.lower() or "stress" in w.lower() for w in warnings)

    def test_detect_stress_bottleneck(self):
        e = _engine()
        for i in range(15):
            e.register_module(f"consumer_{i}", ["shared_lib"])
        e.register_module("shared_lib", [])
        warnings = e.detect_architecture_stress()
        assert any("bottleneck" in w.lower() for w in warnings)

    def test_detect_stress_underutilized(self):
        e = _engine()
        for i in range(6):
            e.register_module(f"unused_{i}", [], subsystem="test_sub")
        warnings = e.detect_architecture_stress()
        assert any("underutilized" in w.lower() for w in warnings)

    def test_no_stress_healthy_architecture(self):
        e = _engine()
        e.register_module("a", ["b"])
        e.register_module("b", [])
        warnings = e.detect_architecture_stress()
        bottleneck_warnings = [w for w in warnings if "bottleneck" in w.lower()]
        density_warnings = [w for w in warnings if "dependency density" in w.lower()]
        assert len(bottleneck_warnings) == 0
        assert len(density_warnings) == 0


# ---------------------------------------------------------------------------
# 5. Recommended actions tests
# ---------------------------------------------------------------------------

class TestRecommendedActions:
    def test_recommended_actions_generated(self):
        e = _engine()
        for i in range(20):
            e.register_module(f"m{i}", [f"d{j}" for j in range(5)])
            for j in range(5):
                e.register_module(f"d{j}", [])
        for i in range(12):
            e.register_gap(f"g{i}", f"Gap {i}")
        result = e.analyze()
        for a in result.recommended_actions:
            assert "action" in a
            assert "priority" in a
            assert "impact" in a


# ---------------------------------------------------------------------------
# 6. Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_state(self):
        result = _engine().analyze()
        assert isinstance(result, EvolutionIndicators)
        assert result.es >= 0

    def test_optional_capability_map(self):
        e = _engine(capability_map=None)
        result = e.analyze()
        assert isinstance(result, EvolutionIndicators)

    def test_optional_governance_kernel(self):
        e = _engine(governance_kernel=None)
        result = e.analyze()
        assert isinstance(result, EvolutionIndicators)


# ---------------------------------------------------------------------------
# 7. Determinism tests
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_deterministic(self):
        def _run():
            e = _engine()
            e.register_module("core", ["utils"])
            e.register_module("utils", [])
            e.register_gap("g1", "gap")
            e.register_compliance_domain("SOC2")
            return e.analyze()

        r1 = _run()
        r2 = _run()
        assert r1.es == r2.es
        assert r1.complexity_growth == r2.complexity_growth
        assert r1.module_demand == r2.module_demand
        assert r1.predicted_modules == r2.predicted_modules
        assert r1.stress_warnings == r2.stress_warnings
