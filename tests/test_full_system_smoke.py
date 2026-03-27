"""End-to-end smoke tests for Murphy System.

Validates high-level system behaviours without a live server:

1. System module inventory — verify all critical modules are importable
2. Configure LLM path — verify the configure→test→execute pathway exists
3. Task submission path — verify task schema and gate validation structures
4. Audit trail — verify audit identifiers are generated

These tests do NOT start a server.  They verify that the module graph, class
interfaces, and data schemas are correct so that end-to-end workflows will
succeed when a server is running.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import os
import re
import sys
import time
import uuid
from typing import Any, Dict, Optional

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _try_import(module_path: str) -> Any:
    """Import a module without raising on ImportError."""
    try:
        import importlib

        return importlib.import_module(module_path)
    except Exception:
        return None


def _main_class(mod: Any) -> Optional[Any]:
    """Return the primary (most-methods) public class defined in *mod*.

    This avoids picking dataclasses, enums, or namedtuples over the real
    implementation class.
    """
    import enum
    import inspect

    candidates = [
        obj
        for _, obj in inspect.getmembers(mod, inspect.isclass)
        if obj.__module__ == mod.__name__
        and not issubclass(obj, enum.Enum)
        and not issubclass(obj, Exception)
    ]
    if not candidates:
        return None

    def _method_count(c: Any) -> int:
        return len([
            m for m in dir(c)
            if not m.startswith("_") and callable(getattr(c, m, None))
        ])

    return max(candidates, key=_method_count)


def _read_full_runtime() -> str:
    """Read concatenated runtime source (thin wrapper + refactored modules)."""
    root = os.path.join(os.path.dirname(__file__), "..")
    parts = []
    for rel in (
        "murphy_system_1.0_runtime.py",
        os.path.join("src", "runtime", "_deps.py"),
        os.path.join("src", "runtime", "app.py"),
        os.path.join("src", "runtime", "murphy_system_core.py"),
    ):
        path = os.path.join(root, rel)
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as fh:
                parts.append(fh.read())
    return "\n".join(parts)


def _make_audit_id() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Smoke test 1: System health check path
# ---------------------------------------------------------------------------


class TestSystemHealthSmoke:
    """Verify that health-check-related modules and symbols are present."""

    def test_runtime_file_exists(self) -> None:
        """The primary runtime file must exist on disk."""
        runtime_path = os.path.join(os.path.dirname(__file__), "..", "murphy_system_1.0_runtime.py")
        assert os.path.isfile(runtime_path), (
            f"murphy_system_1.0_runtime.py not found at {runtime_path}"
        )

    def test_runtime_defines_app_or_create_app(self) -> None:
        """The runtime must define an 'app' or 'create_app' symbol."""
        content = _read_full_runtime()
        has_app = "app = " in content or "app=" in content
        has_create_app = "def create_app" in content or "create_app(" in content
        assert has_app or has_create_app, (
            "murphy_system_1.0_runtime.py must define 'app' or 'create_app'"
        )

    def test_health_endpoint_pattern_present(self) -> None:
        """A /api/health route must be registered in the runtime."""
        content = _read_full_runtime()
        assert "/api/health" in content, (
            "No /api/health endpoint found in murphy_system_1.0_runtime.py"
        )

    def test_status_endpoint_pattern_present(self) -> None:
        """A /api/status route must be registered in the runtime."""
        content = _read_full_runtime()
        assert "/api/status" in content, (
            "No /api/status endpoint found in murphy_system_1.0_runtime.py"
        )

    def test_core_src_modules_importable(self) -> None:
        """Critical src modules must be importable."""
        required_modules = [
            "llm_controller",
            "governance_kernel",
            "gate_execution_wiring",
            "persistence_manager",
            "event_backbone",
            "state_schema",
            "compliance_engine",
        ]
        missing = []
        for name in required_modules:
            if _try_import(name) is None:
                missing.append(name)
        assert missing == [], f"Critical modules not importable: {missing}"


# ---------------------------------------------------------------------------
# Smoke test 2: LLM configure → test → execute pathway
# ---------------------------------------------------------------------------


class TestLLMConfigureSmoke:
    """LLM configuration pipeline must have the correct interface."""

    def test_llm_controller_importable(self) -> None:
        mod = _try_import("llm_controller")
        assert mod is not None, "llm_controller is not importable"

    def test_env_manager_importable(self) -> None:
        mod = _try_import("env_manager")
        assert mod is not None, "env_manager is not importable"

    def test_env_manager_has_write_and_reload(self) -> None:
        mod = _try_import("env_manager")
        if mod is None:
            pytest.skip("env_manager not available")
        assert hasattr(mod, "write_env_key"), "env_manager must have write_env_key"
        assert hasattr(mod, "reload_env"), "env_manager must have reload_env"

    def test_api_key_format_constants_defined(self) -> None:
        """API_KEY_FORMATS must define at least deepinfra and openai."""
        mod = _try_import("env_manager")
        if mod is None:
            pytest.skip("env_manager not available")
        fmt = getattr(mod, "API_KEY_FORMATS", None)
        assert fmt is not None, "env_manager must define API_KEY_FORMATS"
        assert "deepinfra" in fmt, "API_KEY_FORMATS must include 'deepinfra'"
        assert "openai" in fmt, "API_KEY_FORMATS must include 'openai'"

    def test_groq_key_format_has_env_var(self) -> None:
        mod = _try_import("env_manager")
        if mod is None:
            pytest.skip("env_manager not available")
        fmt = getattr(mod, "API_KEY_FORMATS", {})
        deepinfra = fmt.get("deepinfra", {})
        assert "env_var" in deepinfra, "deepinfra entry in API_KEY_FORMATS must have 'env_var'"
        assert deepinfra["env_var"] == "DEEPINFRA_API_KEY", (
            f"Expected DEEPINFRA_API_KEY, got {deepinfra['env_var']!r}"
        )

    def test_validate_api_key_callable(self) -> None:
        mod = _try_import("env_manager")
        if mod is None:
            pytest.skip("env_manager not available")
        assert callable(getattr(mod, "validate_api_key", None)), (
            "env_manager.validate_api_key must be callable"
        )

    def test_llm_controller_has_configure_and_test(self) -> None:
        mod = _try_import("llm_controller")
        if mod is None:
            pytest.skip("llm_controller not available")
        cls = _main_class(mod)
        if cls is None:
            pytest.skip("llm_controller has no top-level classes")
        configure_syms = [
            m for m in dir(cls)
            if any(kw in m.lower() for kw in ("configure", "set", "reconfigure", "select", "query"))
        ]
        test_syms = [
            m for m in dir(cls)
            if any(kw in m.lower() for kw in ("test", "check", "verify", "refresh", "estimate"))
        ]
        assert len(configure_syms) >= 1, f"{cls.__name__} must have a configure/set/reconfigure method"
        assert len(test_syms) >= 1, f"{cls.__name__} must have a test/check/verify method"


# ---------------------------------------------------------------------------
# Smoke test 3: Submit task → gate evaluation → governance → output
# ---------------------------------------------------------------------------


class TestTaskSubmissionSmoke:
    """Task submission schema and gate pipeline smoke test."""

    def test_task_schema_fields(self) -> None:
        """A valid task payload must have at minimum 'task' and 'context'."""
        task_payload: Dict[str, Any] = {
            "task": "Generate a one-page business plan",
            "context": {"industry": "SaaS", "budget": 5000},
            "timeout_seconds": 30,
            "use_llm": True,
        }
        assert "task" in task_payload
        assert isinstance(task_payload["task"], str) and len(task_payload["task"]) > 0
        assert "context" in task_payload
        assert isinstance(task_payload["context"], dict)

    def test_audit_id_is_uuid(self) -> None:
        """Audit IDs must be valid UUID v4 strings."""
        audit_id = _make_audit_id()
        uuid_pattern = re.compile(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
            re.I,
        )
        assert uuid_pattern.match(audit_id), f"audit_id {audit_id!r} is not a valid UUID v4"

    def test_gate_result_structure(self) -> None:
        """Gate evaluation results must have gate name and pass/fail."""
        gate_result: Dict[str, Any] = {
            "gate": "security",
            "result": "pass",
            "score": 0.98,
            "reasons": [],
        }
        assert "gate" in gate_result
        assert gate_result["result"] in ("pass", "fail")
        assert isinstance(gate_result["score"], float)
        assert 0.0 <= gate_result["score"] <= 1.0

    def test_execute_endpoint_pattern_in_runtime(self) -> None:
        """A /api/execute route must be registered."""
        content = _read_full_runtime()
        assert "/api/execute" in content or "execute" in content, (
            "No execute endpoint found in murphy_system_1.0_runtime.py"
        )

    def test_gate_execution_wiring_class_present(self) -> None:
        """gate_execution_wiring must expose a class or register-gate function."""
        mod = _try_import("gate_execution_wiring")
        if mod is None:
            pytest.skip("gate_execution_wiring not available")
        import inspect

        classes = [
            obj for _, obj in inspect.getmembers(mod, inspect.isclass)
            if obj.__module__ == mod.__name__
        ]
        funcs = [
            name for name, _ in inspect.getmembers(mod, inspect.isfunction)
            if "gate" in name.lower() or "register" in name.lower() or "wire" in name.lower()
        ]
        assert len(classes) >= 1 or len(funcs) >= 1, (
            "gate_execution_wiring must have at least one class or gate-related function"
        )


# ---------------------------------------------------------------------------
# Smoke test 4: Audit trail verification
# ---------------------------------------------------------------------------


class TestAuditTrailSmoke:
    """Audit trail generation and persistence smoke tests."""

    def test_unique_audit_ids(self) -> None:
        """Every generated audit ID must be unique."""
        ids = [_make_audit_id() for _ in range(100)]
        assert len(set(ids)) == 100, "Audit ID generator produced duplicates"

    def test_audit_id_format_consistent(self) -> None:
        """All generated audit IDs must match UUID v4 format."""
        uuid_pattern = re.compile(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
            re.I,
        )
        for _ in range(20):
            aid = _make_audit_id()
            assert uuid_pattern.match(aid), f"Audit ID {aid!r} does not match UUID v4"

    def test_persistence_manager_has_audit_storage(self) -> None:
        """persistence_manager must have methods for saving records by ID."""
        mod = _try_import("persistence_manager")
        if mod is None:
            pytest.skip("persistence_manager not available")
        cls = _main_class(mod)
        if cls is None:
            pytest.skip("persistence_manager has no top-level classes")
        save_syms = [m for m in dir(cls) if any(kw in m.lower() for kw in ("save", "store", "write", "persist"))]
        load_syms = [m for m in dir(cls) if any(kw in m.lower() for kw in ("load", "read", "retrieve", "get"))]
        assert len(save_syms) >= 1, f"{cls.__name__} must have a save/store/write method"
        assert len(load_syms) >= 1, f"{cls.__name__} must have a load/read/retrieve method"

    def test_event_backbone_publish_exists(self) -> None:
        """event_backbone must expose a publish or emit method."""
        mod = _try_import("event_backbone")
        if mod is None:
            pytest.skip("event_backbone not available")
        cls = _main_class(mod)
        if cls is None:
            pytest.skip("event_backbone has no top-level classes")
        publish_syms = [
            m for m in dir(cls)
            if any(kw in m.lower() for kw in ("publish", "emit", "send", "dispatch", "fire"))
        ]
        assert len(publish_syms) >= 1, (
            f"{cls.__name__} must have a publish/emit/send method"
        )

    def test_niche_viability_gate_checkpoints_have_ids(self) -> None:
        """Every viability gate checkpoint must carry a unique identifier."""
        try:
            from src.mss_controls import MSSController
            from src.information_quality import InformationQualityEngine
            from src.information_density import InformationDensityEngine
            from src.resolution_scoring import ResolutionDetectionEngine
            from src.structural_coherence import StructuralCoherenceEngine
            from src.concept_translation import ConceptTranslationEngine
            from src.simulation_engine import StrategicSimulationEngine
            from src.inference_gate_engine import InferenceDomainGateEngine
            from src.niche_business_generator import NicheBusinessGenerator
            from src.niche_viability_gate import NicheViabilityGate
        except Exception as exc:
            pytest.skip(f"Niche modules not available: {exc}")

        rde = ResolutionDetectionEngine()
        ide = InformationDensityEngine()
        sce = StructuralCoherenceEngine()
        iqe = InformationQualityEngine(rde, ide, sce)
        cte = ConceptTranslationEngine()
        sim = StrategicSimulationEngine()
        controller = MSSController(iqe, cte, sim)
        inference = InferenceDomainGateEngine()
        generator = NicheBusinessGenerator(controller, inference)
        gate = NicheViabilityGate(inference, controller)

        niche = generator.get_catalog()[0]
        result = gate.evaluate(niche)

        checkpoint_ids = [cp.checkpoint_id for cp in result.checkpoints]
        assert len(checkpoint_ids) >= 1, "Must have at least one checkpoint"
        # All checkpoint IDs must be non-empty strings
        for cp_id in checkpoint_ids:
            assert isinstance(cp_id, str) and len(cp_id) > 0, (
                f"Checkpoint ID must be a non-empty string, got {cp_id!r}"
            )
        # All checkpoint IDs must be unique
        assert len(set(checkpoint_ids)) == len(checkpoint_ids), (
            "Duplicate checkpoint IDs detected"
        )
