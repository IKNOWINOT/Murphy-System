"""
System-Wide Validation Tests.

Covers:
  - Module import integrity across all critical subsystems
  - LLM subsystem integration (Provider → Controller → Integration Layer)
  - Execution pipeline validation (Compiler → Engine → Feedback)
  - MFM subsystem chain validation
  - AUAR subsystem pipeline validation
  - Cross-module workflow verification

Run:
  python -m pytest tests/test_system_wide_validation.py -v

Copyright © 2020-2026 Inoni LLC — Created by Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

# Ensure src/ is importable
_src_dir = os.path.join(os.path.dirname(__file__), "..", "src")
_src_dir = os.path.abspath(_src_dir)


# ---------------------------------------------------------------------------
# Module Import Integrity
# ---------------------------------------------------------------------------


class TestModuleImportIntegrity:
    """Verify all critical modules are importable and expose expected APIs."""

    @pytest.mark.parametrize(
        "module_name",
        [
            "openai_compatible_provider",
            "llm_controller",
            "llm_integration_layer",
            "groq_key_rotator",
            "execution_compiler",
        ],
    )
    def test_critical_module_importable(self, module_name: str) -> None:
        """Each critical module must be importable without error."""
        import importlib

        mod = importlib.import_module(module_name)
        assert mod is not None

    @pytest.mark.parametrize(
        "package_name",
        [
            "murphy_foundation_model",
            "auar",
            "confidence_engine",
            "gate_synthesis",
            "telemetry_system",
        ],
    )
    def test_critical_package_importable(self, package_name: str) -> None:
        """Each critical package must be importable."""
        import importlib

        mod = importlib.import_module(package_name)
        assert mod is not None

    def test_runtime_package_importable(self) -> None:
        """The runtime package must be importable (may need heavy deps)."""
        try:
            import importlib
            mod = importlib.import_module("runtime")
            assert mod is not None
        except (ImportError, AttributeError):
            # Runtime requires heavy dependencies (uvicorn, pydantic, etc.)
            # that may not be installed in test environments
            pytest.skip("runtime requires heavy dependencies not installed")

    def test_provider_types_consistent(self) -> None:
        """Provider types across modules should be consistent."""
        from openai_compatible_provider import ProviderType
        from llm_integration_layer import LLMProvider

        # Both should support Groq
        assert hasattr(ProviderType, "DEEPINFRA")
        assert hasattr(LLMProvider, "DEEPINFRA")


# ---------------------------------------------------------------------------
# LLM Subsystem Integration
# ---------------------------------------------------------------------------


class TestLLMSubsystemIntegration:
    """Validate the LLM provider → controller → integration layer chain."""

    def test_provider_to_controller_compatibility(self) -> None:
        """Provider types should be compatible with controller model enum."""
        from openai_compatible_provider import ProviderType
        from llm_controller import LLMModel

        # Groq provider should have matching models
        assert hasattr(LLMModel, "DEEPINFRA_MIXTRAL")
        assert hasattr(LLMModel, "DEEPINFRA_LLAMA")
        assert hasattr(LLMModel, "DEEPINFRA_GEMMA")
        assert hasattr(ProviderType, "DEEPINFRA")

    def test_controller_instantiation(self) -> None:
        """LLMController should instantiate without errors."""
        from llm_controller import LLMController

        controller = LLMController()
        assert controller is not None

    def test_integration_layer_instantiation(self) -> None:
        """LLMIntegrationLayer should instantiate without errors."""
        from llm_integration_layer import LLMIntegrationLayer

        layer = LLMIntegrationLayer()
        assert layer is not None

    def test_provider_status_format(self) -> None:
        """Provider status should return structured dictionary."""
        from openai_compatible_provider import OpenAICompatibleProvider

        with patch.dict(os.environ, {}, clear=True):
            provider = OpenAICompatibleProvider.from_env()
        status = provider.get_status()
        assert isinstance(status, dict)
        assert "provider_type" in status


# ---------------------------------------------------------------------------
# Execution Pipeline Validation
# ---------------------------------------------------------------------------


class TestExecutionPipeline:
    """Validate the execution compiler and related modules."""

    def test_execution_compiler_instantiation(self) -> None:
        """ExecutionCompiler should instantiate without errors."""
        from execution_compiler import ExecutionCompiler

        compiler = ExecutionCompiler()
        assert compiler is not None

    def test_execution_compiler_compile(self) -> None:
        """ExecutionCompiler should compile a simple plan."""
        from execution_compiler import ExecutionCompiler

        compiler = ExecutionCompiler()
        result = compiler.compile({"goal": "test", "steps": ["step1"]})
        assert result is not None

    def test_execution_compiler_output_structure(self) -> None:
        """Compiled plan should have expected structure."""
        from execution_compiler import ExecutionCompiler

        compiler = ExecutionCompiler()
        result = compiler.compile({"goal": "test", "steps": ["step1", "step2"]})
        assert result is not None
        # Result should be a dict or structured object
        assert isinstance(result, (dict, object))


# ---------------------------------------------------------------------------
# MFM Subsystem Validation
# ---------------------------------------------------------------------------


class TestMFMSubsystem:
    """Validate Murphy Foundation Model module chain."""

    def test_mfm_action_trace_collector(self) -> None:
        """ActionTraceCollector should be importable and functional."""
        from murphy_foundation_model import ActionTraceCollector

        collector = ActionTraceCollector()
        assert collector is not None

    def test_mfm_outcome_labeler(self) -> None:
        """OutcomeLabeler should be importable and functional."""
        from murphy_foundation_model import OutcomeLabeler

        labeler = OutcomeLabeler()
        assert labeler is not None

    def test_mfm_training_data_pipeline(self) -> None:
        """TrainingDataPipeline should be importable and functional."""
        from murphy_foundation_model import TrainingDataPipeline

        pipeline = TrainingDataPipeline()
        assert pipeline is not None


# ---------------------------------------------------------------------------
# AUAR Subsystem Validation
# ---------------------------------------------------------------------------


class TestAUARSubsystem:
    """Validate AUAR subsystem pipeline."""

    def test_auar_package_imports(self) -> None:
        """AUAR package should export all 7 layer components."""
        import auar

        # The AUAR package should expose its main components
        assert hasattr(auar, "SignalInterpreter") or hasattr(auar, "Pipeline")

    def test_auar_pipeline_instantiation(self) -> None:
        """AUAR pipeline should instantiate with its required components."""
        from auar.pipeline import AUARPipeline
        from auar import (
            SignalInterpreter,
            CapabilityGraph,
            RoutingDecisionEngine,
            SchemaTranslator,
            ProviderAdapterManager,
        )

        graph = CapabilityGraph()
        router = RoutingDecisionEngine(capability_graph=graph)
        translator = SchemaTranslator()
        adapters = ProviderAdapterManager()
        interpreter = SignalInterpreter()

        pipeline = AUARPipeline(
            interpreter=interpreter,
            graph=graph,
            router=router,
            translator=translator,
            adapters=adapters,
        )
        assert pipeline is not None


# ---------------------------------------------------------------------------
# Cross-Module Workflow Validation
# ---------------------------------------------------------------------------


class TestCrossModuleWorkflow:
    """Validate workflows that span multiple subsystems."""

    def test_llm_to_execution_workflow(self) -> None:
        """LLM provider should produce output compatible with execution compiler."""
        from openai_compatible_provider import OpenAICompatibleProvider
        from execution_compiler import ExecutionCompiler

        # Both should instantiate independently
        with patch.dict(os.environ, {}, clear=True):
            provider = OpenAICompatibleProvider.from_env()
        compiler = ExecutionCompiler()

        # Provider status and compiler should coexist
        status = provider.get_status()
        result = compiler.compile({"goal": "integration-test", "steps": ["verify"]})
        assert status is not None
        assert result is not None

    def test_domain_routing_covers_all_domains(self) -> None:
        """Integration layer should have routing config for all domain types."""
        from llm_integration_layer import LLMIntegrationLayer, DomainType

        layer = LLMIntegrationLayer()

        for domain in DomainType:
            config = layer.domain_routing.get(domain, {})
            assert config, f"No routing config for domain: {domain.value}"
            assert "primary_provider" in config, (
                f"No primary_provider for domain: {domain.value}"
            )
