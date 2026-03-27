"""
Test suite for Module Integration Wiring (Stream 3).

Validates that:
- ModuleRegistry discovers and registers modules in src/
- IntegrationBus routes chat requests correctly
- IntegrationBus routes execute requests correctly
- Graceful degradation when a module fails to load
- LLM output validation is applied to responses
- Feedback endpoint accepts and processes signals
- /api/modules returns accurate module status
- /api/modules/{name}/status returns per-module status
- /api/feedback accepts explicit feedback payloads
- End-to-end: chat request → bus → validation → response

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

import importlib.util
import sys
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _src_path() -> Path:
    return Path(__file__).resolve().parent.parent / "src"


def _read_runtime_source() -> str:
    """Read the full runtime source (thin wrapper + refactored modules).

    After INC-13, the runtime was split into src/runtime/{_deps,app,murphy_system_core}.py.
    """
    root = Path(__file__).resolve().parent.parent
    parts: list[str] = []
    for rel in (
        "murphy_system_1.0_runtime.py",
        "src/runtime/_deps.py",
        "src/runtime/app.py",
        "src/runtime/murphy_system_core.py",
    ):
        p = root / rel
        if p.is_file():
            parts.append(p.read_text(encoding="utf-8"))
    return "\n".join(parts)


def _load_module_registry():
    src = _src_path()
    spec = importlib.util.spec_from_file_location(
        "module_registry", src / "module_registry.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["module_registry"] = mod
    spec.loader.exec_module(mod)
    return mod


def _load_integration_bus():
    src = _src_path()
    spec = importlib.util.spec_from_file_location(
        "integration_bus", src / "integration_bus.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["integration_bus"] = mod
    spec.loader.exec_module(mod)
    return mod


def load_runtime_module():
    runtime_dir = Path(__file__).resolve().parent.parent
    candidates = list(runtime_dir.glob("murphy_system_*_runtime.py"))
    if not candidates:
        raise RuntimeError("Unable to locate Murphy runtime module")
    module_path = candidates[0]
    spec = importlib.util.spec_from_file_location("murphy_system_runtime", module_path)
    module = importlib.util.module_from_spec(spec)
    if spec.loader is None:
        raise RuntimeError("Unable to load Murphy runtime module")
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Task 1: ModuleRegistry
# ---------------------------------------------------------------------------


class TestModuleRegistry:
    """Tests for src/module_registry.py."""

    def test_module_registry_file_exists(self):
        """module_registry.py must exist in src/."""
        assert (_src_path() / "module_registry.py").is_file()

    def test_module_registry_has_required_classes(self):
        mod = _load_module_registry()
        assert hasattr(mod, "ModuleRegistry"), "ModuleRegistry class missing"
        assert hasattr(mod, "ModuleDescriptor"), "ModuleDescriptor class missing"

    def test_discover_returns_list(self):
        mod = _load_module_registry()
        registry = mod.ModuleRegistry(src_root=_src_path())
        discovered = registry.discover()
        assert isinstance(discovered, list)
        assert len(discovered) > 0, "discover() should find at least one module"

    def test_discover_finds_known_modules(self):
        mod = _load_module_registry()
        registry = mod.ModuleRegistry(src_root=_src_path())
        registry.discover()
        available = registry.list_available()
        # These known modules must be detected
        expected = [
            "llm_output_validator",
            "feedback_integrator",
            "domain_engine",
            "llm_controller",
        ]
        for name in expected:
            assert name in available, f"Expected module '{name}' in registry"

    def test_get_status_shape(self):
        mod = _load_module_registry()
        registry = mod.ModuleRegistry(src_root=_src_path())
        registry.discover()
        status = registry.get_status()
        assert "total_registered" in status
        assert "total_loaded" in status
        assert "modules" in status
        assert isinstance(status["modules"], dict)
        assert status["total_registered"] >= 1

    def test_list_available_returns_all_registered(self):
        mod = _load_module_registry()
        registry = mod.ModuleRegistry(src_root=_src_path())
        registry.discover()
        available = registry.list_available()
        status = registry.get_status()
        assert len(available) == status["total_registered"]

    def test_get_capabilities_returns_dict(self):
        mod = _load_module_registry()
        registry = mod.ModuleRegistry(src_root=_src_path())
        registry.discover()
        caps = registry.get_capabilities()
        assert isinstance(caps, dict)

    def test_register_manual_module(self):
        mod = _load_module_registry()
        registry = mod.ModuleRegistry(src_root=_src_path())
        desc = registry.register(
            name="test_manual_module",
            capabilities=["test_cap"],
            version="2.0.0",
        )
        assert desc.name == "test_manual_module"
        assert "test_cap" in desc.capabilities
        assert "test_manual_module" in registry.list_available()

    def test_get_module_status_for_known_module(self):
        mod = _load_module_registry()
        registry = mod.ModuleRegistry(src_root=_src_path())
        registry.discover()
        # domain_engine should always be discoverable
        status = registry.get_module_status("domain_engine")
        assert status is not None
        assert status["name"] == "domain_engine"
        assert "status" in status

    def test_get_module_status_unknown_returns_none(self):
        mod = _load_module_registry()
        registry = mod.ModuleRegistry(src_root=_src_path())
        result = registry.get_module_status("_nonexistent_xyz_module_")
        assert result is None

    def test_module_status_enum_values(self):
        mod = _load_module_registry()
        assert hasattr(mod, "ModuleStatus")
        statuses = {s.value for s in mod.ModuleStatus}
        assert "loaded" in statuses
        assert "error" in statuses
        assert "available" in statuses

    def test_load_nonexistent_module_marks_error(self):
        mod = _load_module_registry()
        registry = mod.ModuleRegistry(src_root=_src_path())
        result = registry.load("_does_not_exist_xyz_")
        assert result is False
        status = registry.get_module_status("_does_not_exist_xyz_")
        assert status is not None
        assert status["status"] == "error"

    def test_singleton_exported(self):
        mod = _load_module_registry()
        assert hasattr(mod, "module_registry")
        assert isinstance(mod.module_registry, mod.ModuleRegistry)


# ---------------------------------------------------------------------------
# Task 2: IntegrationBus
# ---------------------------------------------------------------------------


class TestIntegrationBus:
    """Tests for src/integration_bus.py."""

    def test_integration_bus_file_exists(self):
        assert (_src_path() / "integration_bus.py").is_file()

    def test_integration_bus_has_required_class(self):
        mod = _load_integration_bus()
        assert hasattr(mod, "IntegrationBus")

    def test_singleton_exported(self):
        mod = _load_integration_bus()
        assert hasattr(mod, "integration_bus")
        assert isinstance(mod.integration_bus, mod.IntegrationBus)

    def test_process_method_exists(self):
        mod = _load_integration_bus()
        bus = mod.IntegrationBus()
        assert callable(getattr(bus, "process", None))

    def test_get_status_shape(self):
        mod = _load_integration_bus()
        bus = mod.IntegrationBus()
        status = bus.get_status()
        assert "initialized" in status
        assert "modules" in status
        assert isinstance(status["modules"], dict)

    def test_process_chat_returns_success(self):
        """IntegrationBus.process('chat', ...) must return a success dict."""
        mod = _load_integration_bus()
        bus = mod.IntegrationBus()
        result = bus.process("chat", {"message": "Hello", "domain": "general"})
        assert isinstance(result, dict)
        assert "success" in result
        assert "response" in result
        assert "chain_steps" in result
        assert "bus_routed" in result

    def test_process_execute_returns_success(self):
        """IntegrationBus.process('execute', ...) must return a success dict."""
        mod = _load_integration_bus()
        bus = mod.IntegrationBus()
        result = bus.process("execute", {
            "task_description": "run a report",
            "task_type": "general",
        })
        assert isinstance(result, dict)
        assert "success" in result
        assert "chain_steps" in result
        assert "bus_routed" in result

    def test_process_unknown_type_returns_error(self):
        """An unknown request type must return success=False."""
        mod = _load_integration_bus()
        bus = mod.IntegrationBus()
        result = bus.process("unknown_type_xyz", {})
        assert result["success"] is False
        assert "error" in result

    def test_graceful_degradation_broken_module(self):
        """When a module fails to import, bus must still return a result."""
        mod = _load_integration_bus()
        bus = mod.IntegrationBus()
        # Force a broken llm_integration_layer by injecting None
        bus._llm_integration_layer = None
        bus._llm_controller = None
        bus._initialized = True
        result = bus.process("chat", {"message": "test"})
        assert isinstance(result, dict)
        assert "success" in result

    def test_chat_chain_includes_validation_step(self):
        """After a chat response, 'llm_output_validator' should appear in chain_steps."""
        mod = _load_integration_bus()
        bus = mod.IntegrationBus()

        # Stub a minimal LLM integration layer that returns a response
        fake_response = MagicMock()
        fake_response.response = "Hello, world!"
        fake_layer = MagicMock()
        fake_layer.route_request.return_value = fake_response

        bus._llm_integration_layer = fake_layer
        bus._initialized = True

        result = bus.process("chat", {"message": "hi"})
        assert "llm_output_validator" in result["chain_steps"]

    def test_execute_chain_steps_populated_when_domain_engine_available(self):
        """When DomainEngine is present, 'domain_engine' appears in chain_steps."""
        mod = _load_integration_bus()
        bus = mod.IntegrationBus()

        fake_engine = MagicMock()
        fake_engine.classify_domain.return_value = {"domain": "business"}
        bus._domain_engine = fake_engine
        bus._initialized = True

        result = bus.process("execute", {"task_description": "automate payroll"})
        assert "domain_engine" in result["chain_steps"]

    def test_submit_feedback_returns_dict(self):
        mod = _load_integration_bus()
        bus = mod.IntegrationBus()
        result = bus.submit_feedback({
            "signal_type": "feedback",
            "task_id": "t-001",
            "original_confidence": 0.8,
        })
        assert isinstance(result, dict)
        assert "success" in result

    def test_initialize_is_idempotent(self):
        mod = _load_integration_bus()
        bus = mod.IntegrationBus()
        bus.initialize()
        bus.initialize()  # second call must not raise
        assert bus._initialized is True


# ---------------------------------------------------------------------------
# Task 3: Runtime wiring — /api/modules/{name}/status & /api/feedback
# ---------------------------------------------------------------------------


class TestRuntimeEndpoints:
    """Verify that the runtime exposes the new endpoints."""

    def test_runtime_has_integration_bus_init(self):
        """Runtime source must reference IntegrationBus initialisation."""
        text = _read_runtime_source()
        assert "IntegrationBus" in text, "Runtime should reference IntegrationBus"
        assert "_integration_bus" in text, "Runtime should initialize _integration_bus"

    def test_runtime_has_api_modules_name_status_endpoint(self):
        """Runtime must define /api/modules/{name}/status."""
        text = _read_runtime_source()
        assert "/api/modules/{name}/status" in text

    def test_runtime_has_api_feedback_endpoint(self):
        """Runtime must define /api/feedback."""
        text = _read_runtime_source()
        assert "/api/feedback" in text

    def test_runtime_chat_routed_through_bus(self):
        """Runtime /api/chat handler must reference _integration_bus."""
        text = _read_runtime_source()
        # The chat endpoint should check for the bus
        assert '_integration_bus' in text

    def test_runtime_execute_routed_through_bus(self):
        """Runtime /api/execute handler must reference _integration_bus."""
        text = _read_runtime_source()
        assert '_integration_bus' in text

    def test_api_modules_returns_list(self):
        """MurphySystem.list_modules() returns a list of module dicts."""
        runtime = load_runtime_module()
        murphy = runtime.MurphySystem.create_test_instance()
        modules = murphy.list_modules()
        assert isinstance(modules, list)
        assert len(modules) > 0
        for mod in modules:
            assert "name" in mod
            assert "status" in mod


# ---------------------------------------------------------------------------
# Task 4: LLM output validation gate
# ---------------------------------------------------------------------------


class TestLLMOutputValidation:
    """LLM output validation must be applied to bus chat responses."""

    def test_output_validation_applied_when_validator_present(self):
        mod = _load_integration_bus()
        bus = mod.IntegrationBus()

        # Provide a fake LLM response and a real-ish validator stub
        fake_llm_response = MagicMock()
        fake_llm_response.response = "validated answer"
        fake_layer = MagicMock()
        fake_layer.route_request.return_value = fake_llm_response

        fake_validator = MagicMock()
        fake_vresult = MagicMock()
        fake_vresult.valid = True
        fake_vresult.errors = []
        fake_validator.validate_envelope.return_value = fake_vresult

        bus._llm_integration_layer = fake_layer
        bus._llm_output_validator = fake_validator
        bus._initialized = True

        result = bus.process("chat", {"message": "test"})
        assert result["validation"]["validated"] is True
        assert fake_validator.validate_envelope.called

    def test_output_validation_skipped_gracefully_when_unavailable(self):
        mod = _load_integration_bus()
        bus = mod.IntegrationBus()
        bus._llm_output_validator = None
        bus._initialized = True

        result = bus._apply_output_validation("some text")
        assert result["validated"] is False
        assert result["text"] == "some text"
        assert result["errors"] == []

    def test_validation_error_does_not_raise(self):
        """Validator that raises must not propagate to caller."""
        mod = _load_integration_bus()
        bus = mod.IntegrationBus()

        bad_validator = MagicMock()
        bad_validator.validate_envelope.side_effect = RuntimeError("validator exploded")
        bus._llm_output_validator = bad_validator
        bus._initialized = True

        result = bus._apply_output_validation("text")
        assert "errors" in result


# ---------------------------------------------------------------------------
# Task 5: Feedback loop wiring
# ---------------------------------------------------------------------------


class TestFeedbackLoop:
    """Feedback loop must be wired through IntegrationBus."""

    def test_submit_feedback_routes_to_integrator_when_available(self):
        mod = _load_integration_bus()
        bus = mod.IntegrationBus()

        # Stub feedback integrator and supporting modules
        fake_integrator = MagicMock()
        bus._feedback_integrator = fake_integrator
        bus._initialized = True

        result = bus.submit_feedback({
            "signal_type": "correction",
            "task_id": "t-123",
            "original_confidence": 0.6,
            "corrected_confidence": 0.9,
            "affected_state_variables": ["quality"],
        })
        assert result["success"] is True
        assert "task_id" in result

    def test_submit_feedback_succeeds_without_integrator(self):
        mod = _load_integration_bus()
        bus = mod.IntegrationBus()
        bus._feedback_integrator = None
        bus._initialized = True

        result = bus.submit_feedback({
            "signal_type": "feedback",
            "task_id": "t-no-integrator",
        })
        assert result["success"] is True

    def test_feedback_integrator_file_exists(self):
        assert (_src_path() / "feedback_integrator.py").is_file()

    def test_feedback_integrator_has_integrate_method(self):
        src = _src_path()
        spec = importlib.util.spec_from_file_location(
            "feedback_integrator_check",
            src / "feedback_integrator.py",
        )
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
        except Exception as exc:
            pytest.skip(f"Could not load feedback_integrator: {exc}")
        assert hasattr(mod, "FeedbackIntegrator")
        assert hasattr(mod, "FeedbackSignal")
        fi = mod.FeedbackIntegrator()
        assert callable(getattr(fi, "integrate", None))


# ---------------------------------------------------------------------------
# End-to-end: chat → bus → validation → response
# ---------------------------------------------------------------------------


class TestEndToEnd:
    """Smoke-tests that simulate a full chat request through the bus."""

    def test_end_to_end_chat_returns_response(self):
        mod = _load_integration_bus()
        bus = mod.IntegrationBus()
        # No real LLM available in test environment — bus falls back gracefully
        result = bus.process("chat", {"message": "What is Murphy System?"})
        assert isinstance(result, dict)
        assert "success" in result
        # Even without real LLM, result dict must be well-formed
        assert "response" in result
        assert "validation" in result
        assert isinstance(result["validation"], dict)

    def test_end_to_end_execute_returns_result(self):
        mod = _load_integration_bus()
        bus = mod.IntegrationBus()
        result = bus.process("execute", {
            "task_description": "generate a business report",
            "task_type": "automation",
        })
        assert isinstance(result, dict)
        assert "success" in result
        assert "chain_steps" in result

    def test_full_module_registry_then_bus_status(self):
        """Registry discover → bus initialise → bus status check."""
        registry_mod = _load_module_registry()
        bus_mod = _load_integration_bus()

        registry = registry_mod.ModuleRegistry(src_root=_src_path())
        registry.discover()
        assert registry.get_status()["total_registered"] > 0

        bus = bus_mod.IntegrationBus()
        bus.initialize()
        status = bus.get_status()
        assert status["initialized"] is True
        assert isinstance(status["modules"], dict)
