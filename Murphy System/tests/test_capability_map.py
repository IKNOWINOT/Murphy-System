"""Tests for the Capability Map module."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from src.capability_map import (
    CapabilityMap,
    ExecutionCriticality,
    ModuleCapability,
    UtilizationStatus,
)


BASE_PATH = os.path.join(os.path.dirname(__file__), "..")


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def cap_map():
    cm = CapabilityMap()
    cm.scan(BASE_PATH)
    return cm


@pytest.fixture
def empty_map():
    return CapabilityMap()


# ------------------------------------------------------------------
# Scanning
# ------------------------------------------------------------------

class TestScanning:
    def test_scan_finds_modules(self, cap_map):
        status = cap_map.get_status()
        assert status["total_modules"] > 0

    def test_scan_includes_known_module(self, cap_map):
        # self_improvement_engine.py should always be present
        found = any(
            "self_improvement_engine" in path
            for path in cap_map.get_dependency_graph()
        )
        assert found, "self_improvement_engine not found in scanned modules"

    def test_scan_empty_path(self, empty_map):
        empty_map.scan("/nonexistent/path")
        assert empty_map.get_status()["total_modules"] == 0

    def test_scan_detects_capabilities(self, cap_map):
        graph = cap_map.get_dependency_graph()
        for path in graph:
            if "self_improvement_engine" in path:
                mod = cap_map.get_module(path)
                assert mod is not None
                assert any("class:" in c for c in mod.capabilities)
                break

    def test_scan_detects_runtime_imports(self, cap_map):
        status = cap_map.get_status()
        assert status["runtime_imports_detected"] >= 0


# ------------------------------------------------------------------
# Module categorisation
# ------------------------------------------------------------------

class TestCategorisation:
    def test_subsystem_assigned(self, cap_map):
        graph = cap_map.get_dependency_graph()
        for path in graph:
            mod = cap_map.get_module(path)
            assert mod is not None
            assert mod.subsystem != ""

    def test_known_subsystem_mapping(self, cap_map):
        graph = cap_map.get_dependency_graph()
        for path in graph:
            if "authority_gate" in path:
                mod = cap_map.get_module(path)
                assert mod is not None
                assert mod.subsystem == "governance"
                break

    def test_get_subsystem_returns_list(self, cap_map):
        result = cap_map.get_subsystem("learning")
        assert isinstance(result, list)

    def test_get_subsystem_unknown_returns_empty(self, cap_map):
        result = cap_map.get_subsystem("nonexistent_subsystem")
        assert result == []

    def test_criticality_assigned(self, cap_map):
        graph = cap_map.get_dependency_graph()
        for path in graph:
            mod = cap_map.get_module(path)
            assert mod is not None
            assert mod.execution_criticality in (
                ExecutionCriticality.HIGH.value,
                ExecutionCriticality.MEDIUM.value,
                ExecutionCriticality.LOW.value,
            )

    def test_governance_boundary(self, cap_map):
        graph = cap_map.get_dependency_graph()
        for path in graph:
            if "authority_gate" in path:
                mod = cap_map.get_module(path)
                assert mod is not None
                assert mod.governance_boundary == "elevated"
                break


# ------------------------------------------------------------------
# Underutilised detection
# ------------------------------------------------------------------

class TestUnderutilized:
    def test_get_underutilized_returns_list(self, cap_map):
        result = cap_map.get_underutilized()
        assert isinstance(result, list)

    def test_underutilized_have_correct_status(self, cap_map):
        for mod in cap_map.get_underutilized():
            assert mod.utilization_status in (
                UtilizationStatus.PARTIAL.value,
                UtilizationStatus.UNUSED.value,
            )

    def test_active_modules_not_in_underutilized(self, cap_map):
        underutilized_paths = {m.module_path for m in cap_map.get_underutilized()}
        graph = cap_map.get_dependency_graph()
        for path in graph:
            mod = cap_map.get_module(path)
            if mod and mod.utilization_status == UtilizationStatus.ACTIVE.value:
                assert path not in underutilized_paths


# ------------------------------------------------------------------
# Gap analysis
# ------------------------------------------------------------------

class TestGapAnalysis:
    def test_gap_analysis_structure(self, cap_map):
        gap = cap_map.get_gap_analysis()
        assert "total_modules" in gap
        assert "active" in gap
        assert "partial" in gap
        assert "unused" in gap
        assert "wiring_ratio" in gap
        assert "subsystem_coverage" in gap
        assert "high_criticality_unwired" in gap

    def test_gap_analysis_counts_consistent(self, cap_map):
        gap = cap_map.get_gap_analysis()
        assert gap["active"] + gap["partial"] + gap["unused"] == gap["total_modules"]

    def test_wiring_ratio_in_range(self, cap_map):
        gap = cap_map.get_gap_analysis()
        assert 0.0 <= gap["wiring_ratio"] <= 1.0

    def test_subsystem_coverage_has_totals(self, cap_map):
        gap = cap_map.get_gap_analysis()
        for sub, counts in gap["subsystem_coverage"].items():
            assert counts["total"] == counts["active"] + counts["partial"] + counts["unused"]

    def test_gap_analysis_empty_map(self, empty_map):
        gap = empty_map.get_gap_analysis()
        assert gap["total_modules"] == 0
        assert gap["wiring_ratio"] == 0.0


# ------------------------------------------------------------------
# Remediation sequence
# ------------------------------------------------------------------

class TestRemediationSequence:
    def test_remediation_returns_list(self, cap_map):
        seq = cap_map.get_remediation_sequence()
        assert isinstance(seq, list)

    def test_remediation_ordered(self, cap_map):
        seq = cap_map.get_remediation_sequence()
        if seq:
            orders = [item["order"] for item in seq]
            assert orders == list(range(1, len(seq) + 1))

    def test_remediation_has_required_fields(self, cap_map):
        seq = cap_map.get_remediation_sequence()
        for item in seq:
            assert "order" in item
            assert "module_path" in item
            assert "subsystem" in item
            assert "criticality" in item
            assert "current_status" in item
            assert "action" in item
            assert "description" in item

    def test_remediation_high_criticality_first(self, cap_map):
        seq = cap_map.get_remediation_sequence()
        if len(seq) >= 2:
            priority = {
                ExecutionCriticality.HIGH.value: 0,
                ExecutionCriticality.MEDIUM.value: 1,
                ExecutionCriticality.LOW.value: 2,
            }
            prev = priority.get(seq[0]["criticality"], 99)
            for item in seq[1:]:
                cur = priority.get(item["criticality"], 99)
                assert cur >= prev
                prev = cur

    def test_remediation_empty_map(self, empty_map):
        assert empty_map.get_remediation_sequence() == []


# ------------------------------------------------------------------
# Status
# ------------------------------------------------------------------

class TestStatus:
    def test_status_structure(self, cap_map):
        status = cap_map.get_status()
        assert "total_modules" in status
        assert "subsystems" in status
        assert "active_modules" in status
        assert "partial_modules" in status
        assert "unused_modules" in status
        assert "runtime_imports_detected" in status

    def test_status_counts_match(self, cap_map):
        status = cap_map.get_status()
        assert (
            status["active_modules"] + status["partial_modules"] + status["unused_modules"]
            == status["total_modules"]
        )

    def test_status_subsystems_sorted(self, cap_map):
        status = cap_map.get_status()
        assert status["subsystems"] == sorted(status["subsystems"])

    def test_empty_status(self, empty_map):
        status = empty_map.get_status()
        assert status["total_modules"] == 0
        assert status["subsystems"] == []


# ------------------------------------------------------------------
# Dependency graph
# ------------------------------------------------------------------

class TestDependencyGraph:
    def test_dependency_graph_returns_dict(self, cap_map):
        graph = cap_map.get_dependency_graph()
        assert isinstance(graph, dict)

    def test_dependency_values_are_lists(self, cap_map):
        graph = cap_map.get_dependency_graph()
        for deps in graph.values():
            assert isinstance(deps, list)

    def test_get_module_none_for_missing(self, cap_map):
        assert cap_map.get_module("no/such/module.py") is None


# ------------------------------------------------------------------
# ModuleCapability dataclass
# ------------------------------------------------------------------

class TestModuleCapability:
    def test_defaults(self):
        mc = ModuleCapability(
            module_path="src/foo.py",
            subsystem="general",
            runtime_role="test",
        )
        assert mc.capabilities == []
        assert mc.dependencies == []
        assert mc.governance_boundary == "standard"
        assert mc.execution_criticality == ExecutionCriticality.MEDIUM.value
        assert mc.utilization_status == UtilizationStatus.UNUSED.value
