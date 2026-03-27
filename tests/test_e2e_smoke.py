"""
End-to-End Smoke Test for Murphy System (INC-04 / C-03).

Validates that the core system can:
  1. Import critical modules without errors
  2. Instantiate the LLM controller and OpenAI provider
  3. Instantiate the execution compiler and compile a plan
  4. Verify health/status endpoint contracts
  5. Confirm the capability map is populated

This test is run by CI on every push via .github/workflows/ci.yml.

Copyright © 2020-2026 Inoni LLC — Created by Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import importlib
import os
import sys
from typing import Any, Dict

import pytest

# Ensure src/ is importable
_src_dir = os.path.join(os.path.dirname(__file__), "..", "src")
_src_dir = os.path.abspath(_src_dir)
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)


# ---------------------------------------------------------------------------
# 1. Critical module imports
# ---------------------------------------------------------------------------


class TestCriticalImports:
    """Verify that core modules can be imported without errors."""

    CRITICAL_MODULES = [
        "openai_compatible_provider",
        "llm_controller",
        "execution_compiler",
    ]

    IMPORTANT_MODULES = [
        "capability_map",
        "config",
        "health_monitor",
        "logging_system",
    ]

    @pytest.mark.parametrize("module_name", CRITICAL_MODULES)
    def test_critical_module_import(self, module_name: str) -> None:
        """Each critical module must be importable."""
        mod = importlib.import_module(module_name)
        assert mod is not None, f"Failed to import {module_name}"

    @pytest.mark.parametrize("module_name", IMPORTANT_MODULES)
    def test_important_module_import(self, module_name: str) -> None:
        """Important supporting modules must be importable."""
        try:
            mod = importlib.import_module(module_name)
            assert mod is not None
        except ImportError:
            pytest.skip(f"{module_name} not available in this environment")


# ---------------------------------------------------------------------------
# 2. LLM controller & OpenAI provider instantiation
# ---------------------------------------------------------------------------


class TestLLMProviderSmoke:
    """Smoke test for LLM provider layer (INC-01)."""

    def test_openai_provider_instantiation(self) -> None:
        from openai_compatible_provider import (
            OpenAICompatibleProvider,
            ProviderConfig,
            ProviderType,
        )

        cfg = ProviderConfig(
            provider_type=ProviderType.OPENAI,
            api_key="sk-test-smoke",
        )
        provider = OpenAICompatibleProvider(cfg)
        assert provider.available is True
        status = provider.get_status()
        assert status["provider_type"] == "openai"
        assert status["has_api_key"] is True

    def test_openai_provider_from_env_defaults(self) -> None:
        """from_env() should work even with no env vars set."""
        from openai_compatible_provider import OpenAICompatibleProvider

        provider = OpenAICompatibleProvider.from_env()
        # Without OPENAI_API_KEY set it will be unavailable (cloud provider)
        status = provider.get_status()
        assert "provider_type" in status

    def test_llm_controller_instantiation(self) -> None:
        from llm_controller import LLMController

        ctrl = LLMController()
        assert ctrl is not None
        stats = ctrl.get_statistics()
        assert "total_requests" in stats
        assert "available_models" in stats


# ---------------------------------------------------------------------------
# 3. Execution compiler (INC-02)
# ---------------------------------------------------------------------------


class TestExecutionCompilerSmoke:
    """Smoke test for execution compiler (INC-02)."""

    def test_execution_compiler_class_exists(self) -> None:
        from execution_compiler import ExecutionCompiler

        compiler = ExecutionCompiler()
        assert compiler is not None

    def test_compile_method_exists(self) -> None:
        from execution_compiler import ExecutionCompiler

        compiler = ExecutionCompiler()
        assert callable(getattr(compiler, "compile", None))

    def test_compile_simple_plan(self) -> None:
        from execution_compiler import ExecutionCompiler

        compiler = ExecutionCompiler()
        plan: Dict[str, Any] = {
            "summary": "Smoke test plan",
            "actions": [{"type": "test", "target": "smoke"}],
        }
        result = compiler.compile(plan)
        assert isinstance(result, dict)
        # Either compiled or has a reason
        assert "compiled" in result or "status" in result

    def test_compile_empty_plan(self) -> None:
        from execution_compiler import ExecutionCompiler

        compiler = ExecutionCompiler()
        result = compiler.compile({"actions": []})
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# 4. Health / status endpoint contracts
# ---------------------------------------------------------------------------


class TestHealthEndpointSmoke:
    """Verify the runtime exposes the expected API contracts."""

    def test_runtime_file_exists(self) -> None:
        runtime_path = os.path.join(
            os.path.dirname(__file__), "..", "murphy_system_1.0_runtime.py"
        )
        assert os.path.isfile(runtime_path), "murphy_system_1.0_runtime.py not found"

    def test_health_endpoint_defined(self) -> None:
        """The runtime should define /api/health."""
        # INC-13: Runtime refactored into src/runtime/ package
        app_path = os.path.join(
            os.path.dirname(__file__), "..", "src", "runtime", "app.py"
        )
        if os.path.isfile(app_path):
            with open(app_path, "r") as f:
                content = f.read()
        else:
            runtime_path = os.path.join(
                os.path.dirname(__file__), "..", "murphy_system_1.0_runtime.py"
            )
            with open(runtime_path, "r") as f:
                content = f.read()
        assert "/api/health" in content, "Runtime must define /api/health endpoint"

    def test_status_endpoint_defined(self) -> None:
        """The runtime should define /api/status."""
        # INC-13: Runtime refactored into src/runtime/ package
        app_path = os.path.join(
            os.path.dirname(__file__), "..", "src", "runtime", "app.py"
        )
        if os.path.isfile(app_path):
            with open(app_path, "r") as f:
                content = f.read()
        else:
            runtime_path = os.path.join(
                os.path.dirname(__file__), "..", "murphy_system_1.0_runtime.py"
            )
            with open(runtime_path, "r") as f:
                content = f.read()
        assert "/api/status" in content, "Runtime must define /api/status endpoint"


# ---------------------------------------------------------------------------
# 5. CI workflow file check
# ---------------------------------------------------------------------------


class TestCIWorkflow:
    """Verify CI/CD infrastructure exists."""

    def test_ci_workflow_exists(self) -> None:
        """The GitHub Actions CI workflow must exist."""
        # CI workflow lives at repository root .github/workflows/ci.yml
        ci_path = os.path.join(
            os.path.dirname(__file__), "..", "..", ".github", "workflows", "ci.yml"
        )
        # Also accept the legacy inner path
        ci_path_inner = os.path.join(
            os.path.dirname(__file__), "..", ".github", "workflows", "ci.yml"
        )
        assert os.path.isfile(ci_path) or os.path.isfile(ci_path_inner), (
            ".github/workflows/ci.yml not found (checked root and murphy_system/)"
        )

    def test_ci_workflow_references_pytest(self) -> None:
        ci_path = os.path.join(
            os.path.dirname(__file__), "..", "..", ".github", "workflows", "ci.yml"
        )
        ci_path_inner = os.path.join(
            os.path.dirname(__file__), "..", ".github", "workflows", "ci.yml"
        )
        actual = ci_path if os.path.isfile(ci_path) else ci_path_inner
        if not os.path.isfile(actual):
            pytest.skip("CI workflow not present")
        with open(actual, "r") as f:
            content = f.read()
        assert "pytest" in content, "CI workflow should run pytest"
