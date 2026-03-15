"""
Tests for CI/CD infrastructure.

Validates that:
- .github/workflows/ci.yml exists and is valid YAML
- requirements_murphy_1.0.txt is parseable
- All test files in tests/ are discoverable
- No test file in tests/ has Python syntax errors (spot-check sample)
"""

import ast
import os
import sys

import pytest
import yaml

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
REPO_ROOT = os.path.abspath(os.path.join(PROJECT_ROOT, ".."))
TESTS_DIR = os.path.join(PROJECT_ROOT, "tests")
CI_WORKFLOW = os.path.join(REPO_ROOT, ".github", "workflows", "ci.yml")
REQUIREMENTS_FILE = os.path.join(PROJECT_ROOT, "requirements_murphy_1.0.txt")


class TestCIWorkflow:
    """Validate the GitHub Actions CI workflow file."""

    def test_ci_workflow_exists(self):
        """The ci.yml workflow file must exist."""
        assert os.path.isfile(CI_WORKFLOW), (
            f"Expected CI workflow at {CI_WORKFLOW}"
        )

    def test_ci_workflow_is_valid_yaml(self):
        """ci.yml must be parseable as YAML."""
        with open(CI_WORKFLOW, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        assert isinstance(data, dict), "ci.yml must be a YAML mapping"

    def test_ci_workflow_has_name(self):
        """ci.yml must declare a workflow name."""
        with open(CI_WORKFLOW, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        assert "name" in data, "ci.yml must have a 'name' key"

    def _get_on_section(self, data: dict) -> dict:
        """
        Return the 'on' trigger section from a parsed YAML dict.

        PyYAML parses the bare key ``on`` as the Python boolean ``True``,
        so we check both the string ``"on"`` and the boolean ``True``.
        """
        return data.get("on") or data.get(True) or {}

    def test_ci_workflow_has_on_trigger(self):
        """ci.yml must declare an 'on' trigger."""
        with open(CI_WORKFLOW, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        on_section = self._get_on_section(data)
        assert on_section, "ci.yml must have an 'on' trigger section"

    def test_ci_workflow_triggers_on_push(self):
        """ci.yml must trigger on push to main."""
        with open(CI_WORKFLOW, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        on_section = self._get_on_section(data)
        assert "push" in on_section, "ci.yml must trigger on push"

    def test_ci_workflow_triggers_on_pull_request(self):
        """ci.yml must trigger on pull_request."""
        with open(CI_WORKFLOW, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        on_section = self._get_on_section(data)
        assert "pull_request" in on_section, "ci.yml must trigger on pull_request"

    def test_ci_workflow_has_jobs(self):
        """ci.yml must define at least one job."""
        with open(CI_WORKFLOW, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        assert "jobs" in data, "ci.yml must have a 'jobs' section"
        assert len(data["jobs"]) >= 1, "ci.yml must define at least one job"

    def test_ci_workflow_test_job_exists(self):
        """ci.yml must define a 'test' job."""
        with open(CI_WORKFLOW, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        assert "test" in data.get("jobs", {}), "ci.yml must define a 'test' job"

    def test_ci_workflow_test_job_has_steps(self):
        """The 'test' job must contain steps."""
        with open(CI_WORKFLOW, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        steps = data["jobs"]["test"].get("steps", [])
        assert len(steps) >= 1, "'test' job must have at least one step"

    def test_ci_workflow_has_matrix_strategy(self):
        """The 'test' job should use a matrix strategy for Python versions."""
        with open(CI_WORKFLOW, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        strategy = data["jobs"]["test"].get("strategy", {})
        assert "matrix" in strategy, "'test' job should define a matrix strategy"

    def test_ci_workflow_has_security_job(self):
        """ci.yml must define a 'security' job for dependency scanning."""
        with open(CI_WORKFLOW, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        assert "security" in data.get("jobs", {}), (
            "ci.yml must define a 'security' job for pip-audit and bandit"
        )


class TestRequirementsFile:
    """Validate the requirements file."""

    def test_requirements_file_exists(self):
        """requirements_murphy_1.0.txt must exist."""
        assert os.path.isfile(REQUIREMENTS_FILE), (
            f"Expected requirements file at {REQUIREMENTS_FILE}"
        )

    def test_requirements_file_parseable(self):
        """requirements_murphy_1.0.txt must be readable line by line."""
        with open(REQUIREMENTS_FILE, encoding="utf-8") as fh:
            lines = fh.readlines()
        assert len(lines) > 0, "requirements file must not be empty"

    def test_requirements_file_has_fastapi(self):
        """requirements_murphy_1.0.txt must include fastapi."""
        with open(REQUIREMENTS_FILE, encoding="utf-8") as fh:
            content = fh.read().lower()
        assert "fastapi" in content, "requirements file must include fastapi"

    def test_requirements_file_no_unpinned_star(self):
        """requirements_murphy_1.0.txt must not use wildcard (*) version pins."""
        with open(REQUIREMENTS_FILE, encoding="utf-8") as fh:
            lines = fh.readlines()
        bad = [
            ln.strip()
            for ln in lines
            if not ln.strip().startswith("#") and ln.strip().endswith("==*")
        ]
        assert bad == [], f"Found wildcard pins: {bad}"


class TestTestDiscovery:
    """Validate that pytest can discover test files."""

    def _collect_test_files(self):
        """Return all test_*.py files under TESTS_DIR (excluding e2e/)."""
        test_files = []
        for root, dirs, files in os.walk(TESTS_DIR):
            dirs[:] = [d for d in dirs if d != "e2e" and d != "__pycache__"]
            for fname in files:
                if fname.startswith("test_") and fname.endswith(".py"):
                    test_files.append(os.path.join(root, fname))
        return test_files

    def test_test_files_are_discoverable(self):
        """There must be at least one test file discoverable by pytest."""
        files = self._collect_test_files()
        assert len(files) >= 1, "No test files found under tests/"

    def test_substantial_test_suite(self):
        """There must be a substantial number of test files (>= 50)."""
        files = self._collect_test_files()
        assert len(files) >= 50, (
            f"Expected >= 50 test files, found {len(files)}"
        )


class TestTestFileSyntax:
    """Spot-check that test files contain no Python syntax errors."""

    _SPOT_CHECK_NAMES = [
        "test_gap_closure_round35.py",
        "test_orchestrator.py",
        "test_governance_kernel.py",
        "test_risk_manager.py",
        "test_performance.py",
    ]

    @pytest.mark.parametrize("filename", _SPOT_CHECK_NAMES)
    def test_no_syntax_errors(self, filename):
        """Named test file must parse without syntax errors."""
        path = os.path.join(TESTS_DIR, filename)
        if not os.path.isfile(path):
            pytest.skip(f"{filename} not found — skipping syntax check")
        with open(path, encoding="utf-8") as fh:
            source = fh.read()
        try:
            ast.parse(source, filename=filename)
        except SyntaxError as exc:
            pytest.fail(f"SyntaxError in {filename}: {exc}")

    def test_conftest_no_syntax_errors(self):
        """conftest.py must parse without syntax errors."""
        path = os.path.join(TESTS_DIR, "conftest.py")
        if not os.path.isfile(path):
            pytest.skip("conftest.py not found")
        with open(path, encoding="utf-8") as fh:
            source = fh.read()
        ast.parse(source, filename="conftest.py")
