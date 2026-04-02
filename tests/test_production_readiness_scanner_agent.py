#!/usr/bin/env python3
# Copyright (C) 2020 Inoni Limited Liability Company
# Creator: Corey Post | License: BSL-1.1
#
# Tests for the Production Readiness Scanner Agent (READINESS-SCANNER-001)
#
# Commissioning profile:
#   G1: Validates each scan check produces correct outputs
#   G2: Tests the 13 scan phases and task classification
#   G3: Covers empty dirs, missing files, full/standard depth
#   G4: Full range of scan conditions and edge cases
#   G5: Expected: structured JSON checklist with correct fields
#   G6: Actual: verified via assertions
#   G9: Hardening checks included

"""Tests for Murphy System Production Readiness Scanner Agent."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

# Ensure Murphy System/scripts is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from production_readiness_scanner_agent import (  # noqa: E402
    AGENT_LABEL,
    AGENT_VERSION,
    CRITICAL_MODULES,
    classify_tasks,
    generate_checklist,
    run_scan,
    scan_config_files,
    scan_critical_module_tests,
    scan_debt_markers,
    scan_docstring_coverage,
    scan_env_example,
    scan_error_handling,
    scan_module_inventory,
    scan_source_parity,
    scan_test_coverage,
    scan_workflow_health,
)


# -- Fixtures ----------------------------------------------------------------


@pytest.fixture
def tmp_output(tmp_path):
    """Provide a temporary output directory."""
    out = tmp_path / "output"
    out.mkdir()
    return out


@pytest.fixture
def tmp_src(tmp_path):
    """Provide a temporary src directory with sample modules."""
    src = tmp_path / "src"
    src.mkdir()
    # Create a package
    pkg = src / "my_package"
    pkg.mkdir()
    (pkg / "__init__.py").write_text('"""My Package."""\n')
    (pkg / "core.py").write_text('"""Core module."""\nclass Foo: pass\n')
    # Create a single-file module
    (src / "single_module.py").write_text('"""Single module docstring."""\ndef bar(): pass\n')
    # Create a module without docstring
    (src / "no_docstring.py").write_text("def baz(): pass\n")
    # Create __init__.py (should be skipped)
    (src / "__init__.py").write_text("")
    return src


@pytest.fixture
def tmp_tests(tmp_path):
    """Provide a temporary tests directory with sample test files."""
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_my_package.py").write_text("def test_foo(): pass\n")
    (tests / "test_single_module.py").write_text("def test_bar(): pass\n")
    return tests


@pytest.fixture
def tmp_murphy(tmp_path):
    """Provide a temporary Murphy System directory structure."""
    murphy = tmp_path / "Murphy System"
    murphy.mkdir()
    (murphy / "src").mkdir()
    (murphy / "tests").mkdir()
    (murphy / "docs").mkdir()
    (murphy / "scripts").mkdir()
    return murphy


# -- Test: Module Inventory ---------------------------------------------------


class TestScanModuleInventory:
    """G1: Module inventory correctly identifies packages and files."""

    def test_inventory_finds_packages_and_modules(self, tmp_src, monkeypatch):
        """G2: Inventory lists packages and single-file modules."""
        monkeypatch.setattr("production_readiness_scanner_agent.REPO_ROOT", tmp_src.parent)
        result = scan_module_inventory(tmp_src)
        assert result["total_modules"] >= 3
        assert result["packages"] >= 1
        assert result["single_files"] >= 2
        names = [m["name"] for m in result["modules"]]
        assert "my_package" in names
        assert "single_module" in names

    def test_inventory_empty_dir(self, tmp_path):
        """G3: Empty directory returns zero modules."""
        empty = tmp_path / "empty_src"
        empty.mkdir()
        result = scan_module_inventory(empty)
        assert result["total_modules"] == 0

    def test_inventory_nonexistent_dir(self, tmp_path):
        """G3: Nonexistent directory returns zero modules."""
        result = scan_module_inventory(tmp_path / "nonexistent")
        assert result["total_modules"] == 0
        assert result["modules"] == []


# -- Test: Test Coverage ------------------------------------------------------


class TestScanTestCoverage:
    """G4: Test coverage scan identifies covered and uncovered modules."""

    def test_coverage_detects_covered_modules(self, tmp_tests, tmp_src):
        """G4: Modules with test files are marked covered."""
        modules = [
            {"name": "my_package", "type": "package"},
            {"name": "single_module", "type": "module"},
            {"name": "no_docstring", "type": "module"},
        ]
        result = scan_test_coverage(tmp_tests, modules)
        assert result["covered"] == 2
        assert result["uncovered"] == 1
        assert "no_docstring" in result["uncovered_modules"]

    def test_coverage_empty_tests_dir(self, tmp_path):
        """G3: Empty test dir means 0 coverage."""
        empty_tests = tmp_path / "tests"
        empty_tests.mkdir()
        modules = [{"name": "foo", "type": "module"}]
        result = scan_test_coverage(empty_tests, modules)
        assert result["covered"] == 0
        assert result["uncovered"] == 1

    def test_coverage_no_modules(self, tmp_tests):
        """G3: No modules yields 0/0 with no errors."""
        result = scan_test_coverage(tmp_tests, [])
        assert result["total_modules"] == 0
        assert result["coverage_ratio"] == 0


# -- Test: Critical Module Tests ----------------------------------------------


class TestScanCriticalModuleTests:
    """G4: Critical modules are checked for test files."""

    def test_critical_modules_detected(self, tmp_path):
        """G4: Missing critical module tests are reported."""
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        # Create a test for one critical module
        (tests_dir / "test_errors.py").write_text("def test_codes(): pass\n")
        result = scan_critical_module_tests(tests_dir)
        assert "errors" in result["present_tests"]
        assert result["tested"] >= 1
        # The rest should be missing
        assert len(result["missing_tests"]) == len(CRITICAL_MODULES) - 1

    def test_critical_all_missing(self, tmp_path):
        """G3: All critical tests missing when tests dir is empty."""
        tests_dir = tmp_path / "empty_tests"
        tests_dir.mkdir()
        result = scan_critical_module_tests(tests_dir)
        assert result["all_covered"] is False
        assert len(result["missing_tests"]) == len(CRITICAL_MODULES)


# -- Test: Debt Markers -------------------------------------------------------


class TestScanDebtMarkers:
    """G7: Debt markers are detected and counted."""

    def test_detects_todo_markers(self, tmp_src, monkeypatch):
        """G7: TODO markers are found in source files."""
        monkeypatch.setattr("production_readiness_scanner_agent.REPO_ROOT", tmp_src.parent)
        (tmp_src / "debt_file.py").write_text(
            "# TODO: fix this\n# FIXME: broken\ndef stub(): pass  # HACK\n"
        )
        result = scan_debt_markers(tmp_src)
        assert result["total"] >= 3
        assert result["by_type"]["TODO"] >= 1
        assert result["by_type"]["FIXME"] >= 1
        assert result["by_type"]["HACK"] >= 1

    def test_no_debt_markers(self, tmp_path):
        """G3: Clean source has zero markers."""
        clean = tmp_path / "clean_src"
        clean.mkdir()
        (clean / "clean.py").write_text("def hello(): return 'world'\n")
        result = scan_debt_markers(clean)
        assert result["total"] == 0

    def test_empty_dir(self, tmp_path):
        """G3: Empty dir returns zero markers."""
        result = scan_debt_markers(tmp_path / "nonexistent")
        assert result["total"] == 0


# -- Test: Docstring Coverage -------------------------------------------------


class TestScanDocstringCoverage:
    """G2/G8: Docstring coverage is tracked."""

    def test_detects_missing_docstrings(self, tmp_src, monkeypatch):
        """G2: Files without docstrings are flagged."""
        monkeypatch.setattr("production_readiness_scanner_agent.REPO_ROOT", tmp_src.parent)
        result = scan_docstring_coverage(tmp_src)
        assert result["with_docstring"] >= 1  # single_module.py has one
        assert result["without_docstring"] >= 1  # no_docstring.py lacks one

    def test_empty_dir(self, tmp_path, monkeypatch):
        """G3: Empty dir returns zero."""
        monkeypatch.setattr("production_readiness_scanner_agent.REPO_ROOT", tmp_path)
        empty = tmp_path / "nonexistent"
        empty.mkdir(exist_ok=True)
        result = scan_docstring_coverage(empty)
        assert result["total_files"] == 0


# -- Test: Error Handling -----------------------------------------------------


class TestScanErrorHandling:
    """G9: Bare except clauses are detected."""

    def test_detects_bare_except(self, tmp_path, monkeypatch):
        """G9: Bare `except:` is flagged."""
        monkeypatch.setattr("production_readiness_scanner_agent.REPO_ROOT", tmp_path)
        src = tmp_path / "src"
        src.mkdir()
        (src / "bad.py").write_text(
            "try:\n    pass\nexcept:\n    pass\n"
        )
        result = scan_error_handling(src)
        assert result["bare_except_count"] >= 1
        assert any("bad.py" in v["file"] for v in result["violations"])

    def test_clean_code(self, tmp_path):
        """G3: Clean code has zero violations."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "good.py").write_text(
            "try:\n    pass\nexcept ValueError as e:\n    print(e)\n"
        )
        result = scan_error_handling(src)
        assert result["bare_except_count"] == 0


# -- Test: Source Parity ------------------------------------------------------


class TestScanSourceParity:
    """G8: Source parity between Murphy System/ and root is checked."""

    def test_in_sync(self, tmp_path):
        """G8: Identical trees report in_sync=True."""
        murphy_src = tmp_path / "murphy_src"
        root_src = tmp_path / "root_src"
        murphy_src.mkdir()
        root_src.mkdir()
        (murphy_src / "mod.py").write_text("x = 1\n")
        (root_src / "mod.py").write_text("x = 1\n")
        result = scan_source_parity(murphy_src, root_src)
        assert result["in_sync"] is True
        assert result["drift_count"] == 0

    def test_drift_detected(self, tmp_path):
        """G8: Mismatched trees report drift."""
        murphy_src = tmp_path / "murphy_src"
        root_src = tmp_path / "root_src"
        murphy_src.mkdir()
        root_src.mkdir()
        (murphy_src / "mod.py").write_text("x = 1\n")
        (murphy_src / "extra.py").write_text("y = 2\n")
        (root_src / "mod.py").write_text("x = 1\n")
        result = scan_source_parity(murphy_src, root_src)
        assert result["in_sync"] is False
        assert "extra.py" in result["only_in_murphy"]


# -- Test: Config Files -------------------------------------------------------


class TestScanConfigFiles:
    """G8/G9: Required config files are verified."""

    def test_missing_configs(self, tmp_path):
        """G3: Missing config files are reported."""
        result = scan_config_files(tmp_path)
        assert result["present"] == 0
        assert len(result["missing"]) > 0

    def test_existing_configs(self, tmp_path):
        """G5: Existing config files are counted."""
        (tmp_path / "requirements_ci.txt").write_text("pytest\n")
        (tmp_path / "pyproject.toml").write_text("[build-system]\n")
        result = scan_config_files(tmp_path)
        assert result["present"] >= 2


# -- Test: Env Example --------------------------------------------------------


class TestScanEnvExample:
    """G3: .env.example documents required variables."""

    def test_missing_env_vars(self, tmp_path):
        """G3: Missing required env vars are flagged."""
        murphy = tmp_path / "Murphy System"
        murphy.mkdir()
        (murphy / ".env.example").write_text("SOME_VAR=value\n")
        result = scan_env_example(murphy)
        assert len(result["required_vars_missing"]) > 0

    def test_all_vars_present(self, tmp_path):
        """G5: All required vars documented."""
        murphy = tmp_path / "Murphy System"
        murphy.mkdir()
        content = "MURPHY_SECRET_KEY=changeme\nMURPHY_ENV=production\nDATABASE_URL=sqlite:///\n"
        (murphy / ".env.example").write_text(content)
        result = scan_env_example(murphy)
        assert result["all_required_documented"] is True


# -- Test: Workflow Health ----------------------------------------------------


class TestScanWorkflowHealth:
    """G5: CI/CD workflow existence is verified."""

    def test_missing_workflows(self, tmp_path):
        """G3: Missing workflows are reported."""
        result = scan_workflow_health(tmp_path)
        assert result["present"] == 0

    def test_existing_workflows(self, tmp_path):
        """G5: Existing workflows are counted."""
        wf_dir = tmp_path / ".github" / "workflows"
        wf_dir.mkdir(parents=True)
        (wf_dir / "ci.yml").write_text("name: CI\n")
        result = scan_workflow_health(tmp_path)
        assert result["present"] >= 1


# -- Test: Task Classification ------------------------------------------------


class TestClassifyTasks:
    """G2: Tasks are correctly classified as human or agent tasks."""

    def test_parity_drift_creates_agent_task(self):
        """G8: Parity drift generates an agent task."""
        scan_results = {
            "source_parity": {"in_sync": False, "drift_count": 5,
                              "only_in_murphy": ["a.py"], "only_in_root": []},
            "critical_module_tests": {"missing_tests": [], "all_covered": True},
            "smoke_imports": {"failures": []},
            "error_handling": {"bare_except_count": 0},
            "config_files": {"missing": []},
            "security_hardening": {"missing_security_modules": [], "potential_secrets": 0},
            "workflow_health": {"missing": []},
            "debt_markers": {"total": 0},
            "docstring_coverage": {"without_docstring": 0},
            "env_example": {"all_required_documented": True},
            "api_documentation": {"api_routes_exists": True},
        }
        human, agent = classify_tasks(scan_results)
        assert any(t["id"] == "PARITY-001" for t in agent)

    def test_missing_critical_tests_creates_agent_task(self):
        """G4: Missing critical tests generate agent tasks."""
        scan_results = {
            "source_parity": {"in_sync": True},
            "critical_module_tests": {"missing_tests": ["errors"]},
            "smoke_imports": {"failures": []},
            "error_handling": {"bare_except_count": 0},
            "config_files": {"missing": []},
            "security_hardening": {"missing_security_modules": [], "potential_secrets": 0},
            "workflow_health": {"missing": []},
            "debt_markers": {"total": 0},
            "docstring_coverage": {"without_docstring": 0},
            "env_example": {"all_required_documented": True},
            "api_documentation": {"api_routes_exists": True},
        }
        human, agent = classify_tasks(scan_results)
        assert any("errors" in t["id"].lower() for t in agent)

    def test_potential_secrets_creates_human_task(self):
        """G9: Potential secrets require human review."""
        scan_results = {
            "source_parity": {"in_sync": True},
            "critical_module_tests": {"missing_tests": []},
            "smoke_imports": {"failures": []},
            "error_handling": {"bare_except_count": 0},
            "config_files": {"missing": []},
            "security_hardening": {"missing_security_modules": [],
                                   "potential_secrets": 3,
                                   "secret_findings": [{"file": "x.py"}]},
            "workflow_health": {"missing": []},
            "debt_markers": {"total": 0},
            "docstring_coverage": {"without_docstring": 0},
            "env_example": {"all_required_documented": True},
            "api_documentation": {"api_routes_exists": True},
        }
        human, agent = classify_tasks(scan_results)
        assert any("SECURITY-SECRETS" in t["id"] for t in human)

    def test_clean_system_no_tasks(self):
        """G5: Clean system generates no tasks."""
        scan_results = {
            "source_parity": {"in_sync": True},
            "critical_module_tests": {"missing_tests": []},
            "smoke_imports": {"failures": []},
            "error_handling": {"bare_except_count": 0},
            "config_files": {"missing": []},
            "security_hardening": {"missing_security_modules": [], "potential_secrets": 0},
            "workflow_health": {"missing": []},
            "debt_markers": {"total": 0},
            "docstring_coverage": {"without_docstring": 0},
            "env_example": {"all_required_documented": True},
            "api_documentation": {"api_routes_exists": True},
        }
        human, agent = classify_tasks(scan_results)
        assert len(human) == 0
        assert len(agent) == 0


# -- Test: Checklist Generation -----------------------------------------------


class TestGenerateChecklist:
    """G5/G6: Checklist output is well-formed."""

    def test_generates_json_and_markdown(self, tmp_output):
        """G5: Both JSON and Markdown files are created."""
        scan_results = {
            "module_inventory": {"total_modules": 5},
            "test_coverage": {"coverage_ratio": 0.8},
            "critical_module_tests": {"all_covered": True},
            "source_parity": {"in_sync": True},
            "debt_markers": {"total": 10},
            "smoke_imports": {"failed": 0, "passed": 5},
            "error_handling": {"bare_except_count": 0},
            "env_example": {"all_required_documented": True},
            "workflow_health": {"present": 5},
            "api_documentation": {"api_routes_exists": True},
            "docstring_coverage": {"coverage_pct": 90},
        }
        checklist = generate_checklist(scan_results, [], [], str(tmp_output))
        assert checklist["agent_version"] == AGENT_VERSION
        assert checklist["agent_label"] == AGENT_LABEL
        assert "scan_date" in checklist

        # JSON files
        json_files = list(tmp_output.glob("readiness_checklist_*.json"))
        assert len(json_files) >= 1  # dated + latest

        # Markdown file
        md_files = list(tmp_output.glob("readiness_checklist_*.md"))
        assert len(md_files) >= 1

    def test_checklist_includes_tasks(self, tmp_output):
        """G6: Tasks appear in the checklist."""
        scan_results = {
            "module_inventory": {"total_modules": 1},
            "test_coverage": {"coverage_ratio": 0},
            "critical_module_tests": {"all_covered": False},
            "source_parity": {"in_sync": True},
            "debt_markers": {"total": 0},
            "smoke_imports": {"failed": 0, "passed": 0},
            "error_handling": {"bare_except_count": 0},
            "env_example": {"all_required_documented": True},
            "workflow_health": {"present": 5},
            "api_documentation": {"api_routes_exists": True},
            "docstring_coverage": {"coverage_pct": 100},
        }
        human = [{"id": "H-1", "title": "Human task", "category": "test",
                   "description": "Do something", "priority": "HIGH"}]
        agent = [{"id": "A-1", "title": "Agent task", "category": "test",
                   "description": "Fix something", "priority": "HIGH",
                   "action": "fix_import", "commissioning": "G1"}]
        checklist = generate_checklist(scan_results, human, agent, str(tmp_output))
        assert checklist["summary"]["total_human_tasks"] == 1
        assert checklist["summary"]["total_agent_tasks"] == 1

    def test_latest_file_created(self, tmp_output):
        """G5: Latest JSON symlink is created for executor agent."""
        scan_results = {
            "module_inventory": {"total_modules": 0},
            "test_coverage": {"coverage_ratio": 0},
            "critical_module_tests": {"all_covered": True},
            "source_parity": {"in_sync": True},
            "debt_markers": {"total": 0},
            "smoke_imports": {"failed": 0, "passed": 0},
            "error_handling": {"bare_except_count": 0},
            "env_example": {"all_required_documented": True},
            "workflow_health": {"present": 5},
            "api_documentation": {"api_routes_exists": True},
            "docstring_coverage": {"coverage_pct": 100},
        }
        generate_checklist(scan_results, [], [], str(tmp_output))
        assert (tmp_output / "readiness_checklist_latest.json").exists()


# -- Test: Full Scan (integration) --------------------------------------------


class TestRunScan:
    """G1: Full scan runs end-to-end without crashing."""

    def test_scan_standard_depth(self, tmp_output, monkeypatch):
        """G1/G5: Standard scan completes and produces checklist."""
        # Point at tmp dirs so scan doesn't read the real repo
        monkeypatch.setattr(
            "production_readiness_scanner_agent.MURPHY_SRC",
            tmp_output.parent / "fake_src",
        )
        monkeypatch.setattr(
            "production_readiness_scanner_agent.MURPHY_TESTS",
            tmp_output.parent / "fake_tests",
        )
        monkeypatch.setattr(
            "production_readiness_scanner_agent.MURPHY_DOCS",
            tmp_output.parent / "fake_docs",
        )
        monkeypatch.setattr(
            "production_readiness_scanner_agent.MURPHY_SYSTEM",
            tmp_output.parent / "fake_murphy",
        )
        monkeypatch.setattr(
            "production_readiness_scanner_agent.ROOT_SRC",
            tmp_output.parent / "fake_root_src",
        )
        monkeypatch.setattr(
            "production_readiness_scanner_agent.REPO_ROOT",
            tmp_output.parent / "fake_repo",
        )
        # Create minimal directories
        (tmp_output.parent / "fake_src").mkdir(exist_ok=True)
        (tmp_output.parent / "fake_tests").mkdir(exist_ok=True)
        (tmp_output.parent / "fake_murphy").mkdir(exist_ok=True)
        (tmp_output.parent / "fake_root_src").mkdir(exist_ok=True)
        (tmp_output.parent / "fake_repo").mkdir(exist_ok=True)

        result = run_scan(str(tmp_output), scan_depth="standard")
        assert "summary" in result
        assert "human_tasks" in result
        assert "agent_tasks" in result
        assert "commissioning_assessment" in result
