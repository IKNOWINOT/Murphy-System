"""Tests for integrated execution wiring.

Validates that persistence_manager, event_backbone, gate_execution_wiring,
delivery_adapters, self_improvement_engine, operational_slo_tracker, and
automation_scheduler are properly wired into the main execute_task path.
"""
import asyncio
import importlib.util
from pathlib import Path


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


_runtime = load_runtime_module()
MurphySystem = _runtime.MurphySystem


def _run(coro):
    """Run a coroutine in a new event loop."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class TestIntegratedModuleInitialization:
    """Verify integrated modules are initialized on MurphySystem."""

    def test_persistence_manager_initialized(self):
        system = MurphySystem()
        assert hasattr(system, "persistence_manager")

    def test_event_backbone_initialized(self):
        system = MurphySystem()
        assert hasattr(system, "event_backbone")

    def test_delivery_orchestrator_initialized(self):
        system = MurphySystem()
        assert hasattr(system, "delivery_orchestrator")

    def test_gate_wiring_initialized(self):
        system = MurphySystem()
        assert hasattr(system, "gate_wiring")

    def test_self_improvement_initialized(self):
        system = MurphySystem()
        assert hasattr(system, "self_improvement")

    def test_slo_tracker_initialized(self):
        system = MurphySystem()
        assert hasattr(system, "slo_tracker")

    def test_automation_scheduler_initialized(self):
        system = MurphySystem()
        assert hasattr(system, "automation_scheduler")

    def test_capability_map_initialized(self):
        system = MurphySystem()
        assert hasattr(system, "capability_map")

    def test_compliance_engine_initialized(self):
        system = MurphySystem()
        assert hasattr(system, "compliance_engine")

    def test_rbac_governance_initialized(self):
        system = MurphySystem()
        assert hasattr(system, "rbac_governance")

    def test_ticketing_adapter_initialized(self):
        system = MurphySystem()
        assert hasattr(system, "ticketing_adapter")


class TestExecuteTaskIntegration:
    """Verify execute_task wires through integrated modules."""

    def test_fallback_response_includes_gate_evaluations(self):
        system = MurphySystem()
        result = _run(system.execute_task("test task", "general", parameters={"enforce_policy": False}))
        assert "gate_evaluations" in result

    def test_fallback_response_includes_integrated_modules(self):
        system = MurphySystem()
        result = _run(system.execute_task("test task", "general", parameters={"enforce_policy": False}))
        assert "integrated_modules" in result
        modules = result["integrated_modules"]
        assert "gate_execution_wiring" in modules
        assert "event_backbone" in modules
        assert "delivery_orchestrator" in modules
        assert "self_improvement_engine" in modules
        assert "persistence_manager" in modules
        assert "slo_tracker" in modules
        assert "automation_scheduler" in modules

    def test_fallback_records_slo(self):
        system = MurphySystem()
        _run(system.execute_task("test task", "general", parameters={"enforce_policy": False}))
        slo = getattr(system, "slo_tracker", None)
        if slo is not None:
            status = slo.get_status()
            assert status.get("total_records", 0) >= 1

    def test_fallback_records_self_improvement_outcome(self):
        system = MurphySystem()
        _run(system.execute_task("test task", "general", parameters={"enforce_policy": False}))
        engine = getattr(system, "self_improvement", None)
        if engine is not None:
            status = engine.get_status()
            assert status.get("total_outcomes", 0) >= 1

    def test_event_backbone_receives_events(self):
        system = MurphySystem()
        _run(system.execute_task("test task", "general", parameters={"enforce_policy": False}))
        backbone = getattr(system, "event_backbone", None)
        if backbone is not None:
            status = backbone.get_status()
            assert status.get("events_published", 0) >= 1


class TestSystemStatusIntegration:
    """Verify system status includes integrated module details."""

    def test_status_has_integrated_modules(self):
        system = MurphySystem()
        status = system.get_system_status()
        assert "integrated_modules" in status

    def test_status_components_include_new_modules(self):
        system = MurphySystem()
        status = system.get_system_status()
        components = status["components"]
        assert "slo_tracker" in components
        assert "automation_scheduler" in components
        assert "capability_map" in components
        assert "compliance_engine" in components
        assert "rbac_governance" in components
        assert "ticketing_adapter" in components

    def test_integrated_summary_has_all_keys(self):
        system = MurphySystem()
        status = system.get_system_status()
        modules = status["integrated_modules"]
        expected_keys = {
            "gate_execution_wiring",
            "event_backbone",
            "delivery_orchestrator",
            "self_improvement_engine",
            "persistence_manager",
            "slo_tracker",
            "automation_scheduler",
            "capability_map",
            "compliance_engine",
            "rbac_governance",
            "ticketing_adapter",
        }
        assert expected_keys.issubset(set(modules.keys()))
