"""
Murphy System — Architecture Validation Commissioning Tests
Owner: @arch-lead
Phase: 4 — Architecture & Integration Tools
Completion: 100%

Resolves GAP-009 (no automated architecture diagrams) and
GAP-011 (no integration point mapping).
Uses AST-based static analysis to validate the architecture
against documented expectations.
"""

import ast
import pytest
from pathlib import Path

from tests.commissioning.integration_mapper import IntegrationMapper


# ═══════════════════════════════════════════════════════════════════════════
# Architecture Validation Tests
# Owner: @arch-lead | Completion: 100%
# ═══════════════════════════════════════════════════════════════════════════


class TestArchitectureComponentCoverage:
    """@arch-lead: Validates that key architecture components exist."""

    def test_core_runtime_exists(self, project_root):
        """@arch-lead: Verify core runtime file exists."""
        runtime = project_root / "murphy_system_1.0_runtime.py"
        assert runtime.exists(), "murphy_system_1.0_runtime.py not found"

    def test_universal_control_plane_exists(self, project_root):
        """@arch-lead: Verify universal control plane exists."""
        ucp = project_root / "universal_control_plane.py"
        assert ucp.exists(), "universal_control_plane.py not found"

    def test_business_automation_exists(self, project_root):
        """@arch-lead: Verify business automation module exists."""
        biz = project_root / "inoni_business_automation.py"
        assert biz.exists(), "inoni_business_automation.py not found"

    def test_two_phase_orchestrator_exists(self, project_root):
        """@arch-lead: Verify two-phase orchestrator exists."""
        orch = project_root / "two_phase_orchestrator.py"
        assert orch.exists(), "two_phase_orchestrator.py not found"

    def test_source_directory_has_modules(self, src_dir):
        """@arch-lead: Verify source directory has substantial modules."""
        py_files = list(src_dir.rglob("*.py"))
        assert len(py_files) >= 100, (
            f"Expected 100+ source modules, found {len(py_files)}"
        )


class TestArchitectureKeySubsystems:
    """@arch-lead: Validates key subsystem source files exist."""

    REQUIRED_SUBSYSTEMS = [
        "confidence_engine",
        "control_plane_separation",
        "self_improvement_engine",
        "self_automation_orchestrator",
        "governance_framework",
        "event_backbone",
        "persistence_manager",
        "health_monitor",
        "sales_automation",
        "organization_chart_system",
        "emergency_stop_controller",
        "safety_validation_pipeline",
    ]

    @pytest.mark.parametrize("subsystem", REQUIRED_SUBSYSTEMS)
    def test_subsystem_exists(self, src_dir, subsystem):
        """@arch-lead: Verify required subsystem exists."""
        # Check for file or directory
        file_path = src_dir / f"{subsystem}.py"
        dir_path = src_dir / subsystem

        assert file_path.exists() or dir_path.exists(), (
            f"Required subsystem '{subsystem}' not found in src/"
        )


class TestArchitectureDualPlane:
    """@arch-lead: Validates dual-plane architecture separation."""

    def test_control_plane_exists(self, src_dir):
        """@arch-lead: Verify control plane components exist."""
        control_plane = src_dir / "control_plane"
        assert control_plane.exists() or (src_dir / "control_plane_separation.py").exists()

    def test_execution_engine_exists(self, src_dir):
        """@arch-lead: Verify execution engine exists."""
        exec_engine = src_dir / "execution_engine"
        exec_orch = src_dir / "execution_orchestrator"
        assert exec_engine.exists() or exec_orch.exists()

    def test_security_plane_exists(self, src_dir):
        """@arch-lead: Verify security plane exists."""
        security = src_dir / "security_plane"
        assert security.exists() or (src_dir / "security_plane_adapter.py").exists()


class TestArchitectureIntegrationMapping:
    """@arch-lead: Tests using the integration mapper tool."""

    def test_integration_mapper_initialization(self, src_dir):
        """@arch-lead: Verify integration mapper can be initialized."""
        mapper = IntegrationMapper(src_dir=str(src_dir))
        assert mapper.src_dir.exists()

    def test_codebase_analysis(self, src_dir):
        """@arch-lead: Verify codebase analysis finds components."""
        mapper = IntegrationMapper(src_dir=str(src_dir))
        result = mapper.analyze_codebase()

        assert result["components"] > 50, (
            f"Expected 50+ components, found {result['components']}"
        )

    def test_integration_points_found(self, src_dir):
        """@arch-lead: Verify integration points are discovered."""
        mapper = IntegrationMapper(src_dir=str(src_dir))
        mapper.analyze_codebase()

        integration_map = mapper.get_integration_map()
        assert integration_map["total_components"] > 0

    def test_dependency_graph_generated(self, src_dir):
        """@arch-lead: Verify dependency graph is generated."""
        mapper = IntegrationMapper(src_dir=str(src_dir))
        mapper.analyze_codebase()

        graph = mapper.get_dependency_graph()
        assert len(graph) > 0

    def test_integration_map_save(self, src_dir, sandbox):
        """@arch-lead: Verify integration map can be saved."""
        mapper = IntegrationMapper(src_dir=str(src_dir))
        mapper.analyze_codebase()

        output = str(sandbox / "integration_map.json")
        saved_path = mapper.save_integration_map(output)
        assert Path(saved_path).exists()


class TestArchitectureTestCoverage:
    """@arch-lead: Validates test infrastructure coverage."""

    def test_test_directory_exists(self, project_root):
        """@arch-lead: Verify test directory exists."""
        tests_dir = project_root / "tests"
        assert tests_dir.exists()

    def test_sufficient_test_files(self, project_root):
        """@arch-lead: Verify sufficient test files exist."""
        tests_dir = project_root / "tests"
        test_files = list(tests_dir.rglob("test_*.py"))
        assert len(test_files) >= 100, (
            f"Expected 100+ test files, found {len(test_files)}"
        )

    def test_e2e_tests_exist(self, project_root):
        """@arch-lead: Verify E2E tests exist."""
        e2e_dir = project_root / "tests" / "e2e"
        assert e2e_dir.exists()
        e2e_files = list(e2e_dir.glob("test_*.py"))
        assert len(e2e_files) >= 3

    def test_commissioning_tests_exist(self, project_root):
        """@arch-lead: Verify commissioning tests directory exists."""
        comm_dir = project_root / "tests" / "commissioning"
        assert comm_dir.exists()

    def test_conftest_exists(self, project_root):
        """@arch-lead: Verify conftest.py exists for test configuration."""
        conftest = project_root / "tests" / "conftest.py"
        assert conftest.exists()


class TestArchitectureDocumentation:
    """@arch-lead: Validates architecture documentation exists."""

    def test_architecture_map_exists(self, project_root):
        """@arch-lead: Verify ARCHITECTURE_MAP.md exists."""
        arch_map = project_root / "ARCHITECTURE_MAP.md"
        assert arch_map.exists()

    def test_dependency_graph_doc_exists(self, project_root):
        """@arch-lead: Verify DEPENDENCY_GRAPH.md exists."""
        dep_graph = project_root / "DEPENDENCY_GRAPH.md"
        assert dep_graph.exists()

    def test_api_documentation_exists(self, project_root):
        """@arch-lead: Verify API documentation exists."""
        api_doc = project_root / "API_DOCUMENTATION.md"
        assert api_doc.exists()

    def test_specification_exists(self, project_root):
        """@arch-lead: Verify system specification exists."""
        spec = project_root / "MURPHY_SYSTEM_1.0_SPECIFICATION.md"
        assert spec.exists()

    def test_commissioning_docs_exist(self, project_root):
        """@arch-lead: Verify commissioning documentation exists."""
        comm_dir = project_root / "docs" / "commissioning"
        assert comm_dir.exists()

        expected_docs = [
            "MURPHY_COMMISSIONING_IMPLEMENTATION_PLAN.md",
            "ACTIVE_SYSTEM_MAP.md",
            "ARCHIVE_INVENTORY.md",
            "CLEANUP_REPORT.md",
        ]
        for doc in expected_docs:
            assert (comm_dir / doc).exists(), f"Missing: {doc}"


class TestArchitectureNewModuleDesignLabels:
    """@arch-lead: Validates new 2026-03-14 module design labels appear in ARCHITECTURE_MAP.md."""

    NEW_DESIGN_LABELS = [
        "INTRO-001",
        "SCS-001",
        "CSE-001",
        "VSB-001",
        "CEO-002",
        "PROD-ENG-001",
    ]

    @pytest.mark.parametrize("label", NEW_DESIGN_LABELS)
    def test_architecture_map_contains_new_design_label(self, project_root, label):
        """@arch-lead: ARCHITECTURE_MAP.md must reference each new design label."""
        arch_map = project_root / "ARCHITECTURE_MAP.md"
        content = arch_map.read_text(encoding="utf-8")
        assert label in content, (
            f"ARCHITECTURE_MAP.md does not contain new design label '{label}'"
        )
