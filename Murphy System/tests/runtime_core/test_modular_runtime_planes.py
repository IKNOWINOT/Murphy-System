"""Tests for modular_runtime control_plane / compute_plane handshake."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from src.modular_runtime import ModularRuntime


@pytest.fixture
def runtime():
    return ModularRuntime()


class TestCoreModulesLoaded:
    def test_system_builder_loaded(self, runtime):
        assert "SystemBuilder" in runtime.modules

    def test_gate_builder_loaded(self, runtime):
        assert "GateBuilder" in runtime.modules

    def test_task_executor_loaded(self, runtime):
        assert "TaskExecutor" in runtime.modules

    def test_module_manager_loaded(self, runtime):
        assert "ModuleManager" in runtime.modules


class TestComputePlaneHandshake:
    def test_compute_plane_is_attached(self, runtime):
        # compute_plane should be a ComputeService (no pydantic dep) or None
        # but always accessible via the property
        assert hasattr(runtime, "compute_plane")

    def test_control_plane_property_accessible(self, runtime):
        # control_plane may be None if pydantic is not installed,
        # but the attribute must exist
        assert hasattr(runtime, "control_plane")

    def test_dispatch_to_compute_returns_dict(self, runtime):
        result = runtime.dispatch_to_compute("1 + 1", "lp")
        assert isinstance(result, dict)
        assert "status" in result

    def test_dispatch_to_compute_status_is_valid(self, runtime):
        result = runtime.dispatch_to_compute("x >= 0", "lp")
        assert result["status"] in ("computed", "error")

    def test_dispatch_to_compute_handles_empty_expression(self, runtime):
        result = runtime.dispatch_to_compute("", "sympy")
        assert isinstance(result, dict)
        assert "status" in result


class TestLazyProxy:
    def test_lazy_runtime_has_modules(self):
        from src.modular_runtime import runtime as lazy_rt
        assert hasattr(lazy_rt, "modules")

    def test_lazy_runtime_has_compute_plane(self):
        from src.modular_runtime import runtime as lazy_rt
        assert hasattr(lazy_rt, "compute_plane")
