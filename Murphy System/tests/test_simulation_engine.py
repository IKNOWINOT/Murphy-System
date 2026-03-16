"""Tests for StrategicSimulationEngine."""

from pathlib import Path

import pytest
from src.simulation_engine import StrategicSimulationEngine, SimulationResult


@pytest.fixture
def engine():
    return StrategicSimulationEngine()


def _make_spec(
    name="test_module",
    description="A test module",
    dependencies=None,
    subsystem="core",
    compliance_domains=None,
    estimated_complexity="medium",
):
    return {
        "name": name,
        "description": description,
        "dependencies": dependencies or [],
        "subsystem": subsystem,
        "compliance_domains": compliance_domains or [],
        "estimated_complexity": estimated_complexity,
    }


# 1
def test_simulate_module_creation_returns_result(engine):
    result = engine.simulate_module_creation(_make_spec())
    assert isinstance(result, SimulationResult)


# 2
def test_scenario_id_generated(engine):
    result = engine.simulate_module_creation(_make_spec())
    assert isinstance(result.scenario_id, str)
    assert len(result.scenario_id) > 0


# 3
def test_cost_impact_increases_with_dependencies(engine):
    low = engine.simulate_module_creation(_make_spec(dependencies=[]))
    high = engine.simulate_module_creation(
        _make_spec(dependencies=[f"dep{i}" for i in range(11)])
    )
    assert high.cost_impact > low.cost_impact


# 4
def test_complexity_low(engine):
    result = engine.simulate_module_creation(_make_spec(estimated_complexity="low"))
    assert result.complexity_impact < 3.0


# 5
def test_complexity_medium(engine):
    result = engine.simulate_module_creation(_make_spec(estimated_complexity="medium"))
    assert 2.5 <= result.complexity_impact <= 4.5


# 6
def test_complexity_high(engine):
    result = engine.simulate_module_creation(_make_spec(estimated_complexity="high"))
    low_result = engine.simulate_module_creation(_make_spec(estimated_complexity="low"))
    assert result.complexity_impact > low_result.complexity_impact


# 7
def test_compliance_impact_no_domains(engine):
    result = engine.simulate_module_creation(_make_spec(compliance_domains=[]))
    assert result.compliance_impact <= 1.0


# 8
def test_compliance_impact_multiple_domains(engine):
    result = engine.simulate_module_creation(
        _make_spec(compliance_domains=["GDPR", "HIPAA", "SOX"])
    )
    none_result = engine.simulate_module_creation(_make_spec(compliance_domains=[]))
    assert result.compliance_impact > none_result.compliance_impact


# 9
def test_overall_score_is_average(engine):
    result = engine.simulate_module_creation(_make_spec())
    expected = (
        result.cost_impact
        + result.complexity_impact
        + result.compliance_impact
        + result.performance_impact
    ) / 4.0
    assert abs(result.overall_score - expected) < 1e-9


# 10
def test_risk_level_low(engine):
    result = engine.simulate_module_creation(
        _make_spec(dependencies=[], compliance_domains=[], estimated_complexity="low")
    )
    assert result.risk_level == "low"


# 11
def test_risk_level_moderate(engine):
    result = engine.simulate_module_creation(
        _make_spec(
            dependencies=["d1", "d2", "d3"],
            compliance_domains=[],
            estimated_complexity="medium",
        )
    )
    assert result.risk_level == "moderate"


# 12
def test_risk_level_significant(engine):
    result = engine.simulate_module_creation(
        _make_spec(
            dependencies=["dep1", "dep2", "dep3", "dep4"],
            compliance_domains=["GDPR"],
            estimated_complexity="medium",
        )
    )
    assert result.risk_level == "significant"


# 13
def test_risk_level_high(engine):
    result = engine.simulate_module_creation(
        _make_spec(
            dependencies=[f"dep{i}" for i in range(11)],
            compliance_domains=["GDPR", "HIPAA", "SOX", "PCI"],
            estimated_complexity="high",
        )
    )
    assert result.risk_level in ("high", "unacceptable")


# 14
def test_recommended_true_low_risk(engine):
    result = engine.simulate_module_creation(
        _make_spec(dependencies=[], compliance_domains=[], estimated_complexity="low")
    )
    assert result.overall_score < 4.0
    assert result.recommended is True


# 15
def test_recommended_false_high_risk(engine):
    result = engine.simulate_module_creation(
        _make_spec(
            dependencies=[f"dep{i}" for i in range(11)],
            compliance_domains=["GDPR", "HIPAA", "SOX", "PCI"],
            estimated_complexity="high",
        )
    )
    assert result.overall_score >= 4.0
    assert result.recommended is False


# 16
def test_engineering_hours_positive(engine):
    result = engine.simulate_module_creation(_make_spec())
    assert result.estimated_engineering_hours > 0


# 17
def test_engineering_hours_higher_for_complex(engine):
    low = engine.simulate_module_creation(_make_spec(estimated_complexity="low"))
    high = engine.simulate_module_creation(_make_spec(estimated_complexity="high"))
    assert high.estimated_engineering_hours > low.estimated_engineering_hours


# 18
def test_warnings_present_high_risk(engine):
    result = engine.simulate_module_creation(
        _make_spec(
            dependencies=[f"dep{i}" for i in range(12)],
            compliance_domains=["GDPR", "HIPAA", "SOX", "PCI"],
            estimated_complexity="high",
        )
    )
    assert len(result.warnings) > 0


# 19
def test_simulate_modification_returns_result(engine):
    result = engine.simulate_module_modification(
        "src/some_module.py",
        {
            "description": "Modified module",
            "added_dependencies": ["new_dep"],
            "removed_dependencies": [],
            "compliance_domains": ["GDPR"],
        },
    )
    assert isinstance(result, SimulationResult)


# 20
def test_modification_scores_lower(engine):
    creation = engine.simulate_module_creation(
        _make_spec(
            dependencies=["dep1"],
            compliance_domains=["GDPR"],
            estimated_complexity="medium",
        )
    )
    modification = engine.simulate_module_modification(
        "src/test_module.py",
        {
            "description": "Modified module",
            "added_dependencies": ["dep1"],
            "removed_dependencies": [],
            "compliance_domains": ["GDPR"],
        },
    )
    assert modification.cost_impact <= creation.cost_impact
    assert modification.complexity_impact <= creation.complexity_impact
    assert modification.compliance_impact <= creation.compliance_impact


# 21
def test_compare_scenarios_returns_list(engine):
    specs = [_make_spec(name=f"mod{i}") for i in range(3)]
    results = engine.compare_scenarios(specs)
    assert isinstance(results, list)
    assert all(isinstance(r, SimulationResult) for r in results)


# 22
def test_compare_scenarios_sorted_ascending(engine):
    specs = [
        _make_spec(name="low", dependencies=[], estimated_complexity="low"),
        _make_spec(
            name="high",
            dependencies=[f"d{i}" for i in range(8)],
            estimated_complexity="high",
            compliance_domains=["GDPR", "HIPAA"],
        ),
        _make_spec(name="mid", dependencies=["d1"], estimated_complexity="medium"),
    ]
    results = engine.compare_scenarios(specs)
    scores = [r.overall_score for r in results]
    assert scores == sorted(scores)


# 23
def test_empty_spec_minimal(engine):
    result = engine.simulate_module_creation({"name": "minimal"})
    assert isinstance(result, SimulationResult)
    assert result.scenario_id


# 24
def test_affected_modules_includes_name(engine):
    result = engine.simulate_module_creation(_make_spec(name="my_module"))
    assert "my_module" in result.affected_modules
