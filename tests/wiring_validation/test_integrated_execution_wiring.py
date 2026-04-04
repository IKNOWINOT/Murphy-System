"""Tests for integrated execution wiring.

Validates that persistence_manager, event_backbone, gate_execution_wiring,
delivery_adapters, self_improvement_engine, operational_slo_tracker, and
automation_scheduler are properly wired into the main execute_task path.
"""
import asyncio
import importlib.util
from pathlib import Path


def load_runtime_module():
    runtime_dir = Path(__file__).resolve().parent.parent.parent
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

    def test_wingman_protocol_initialized(self):
        system = MurphySystem()
        assert hasattr(system, "wingman_protocol")

    def test_runtime_profile_compiler_initialized(self):
        system = MurphySystem()
        assert hasattr(system, "runtime_profile_compiler")

    def test_governance_kernel_initialized(self):
        system = MurphySystem()
        assert hasattr(system, "governance_kernel")

    def test_control_plane_separation_initialized(self):
        system = MurphySystem()
        assert hasattr(system, "control_plane_separation")

    def test_durable_swarm_orchestrator_initialized(self):
        system = MurphySystem()
        assert hasattr(system, "durable_swarm_orchestrator")

    def test_golden_path_bridge_initialized(self):
        system = MurphySystem()
        assert hasattr(system, "golden_path_bridge")

    def test_org_chart_enforcement_initialized(self):
        system = MurphySystem()
        assert hasattr(system, "org_chart_enforcement")

    def test_shadow_agent_integration_initialized(self):
        system = MurphySystem()
        assert hasattr(system, "shadow_agent_integration")

    def test_triage_rollcall_adapter_initialized(self):
        system = MurphySystem()
        assert hasattr(system, "triage_rollcall_adapter")

    def test_rubix_evidence_adapter_initialized(self):
        system = MurphySystem()
        assert hasattr(system, "rubix_evidence_adapter")

    def test_semantics_boundary_controller_initialized(self):
        system = MurphySystem()
        assert hasattr(system, "semantics_boundary_controller")

    def test_bot_governance_policy_mapper_initialized(self):
        system = MurphySystem()
        assert hasattr(system, "bot_governance_policy_mapper")

    def test_bot_telemetry_normalizer_initialized(self):
        system = MurphySystem()
        assert hasattr(system, "bot_telemetry_normalizer")

    def test_legacy_compatibility_matrix_initialized(self):
        system = MurphySystem()
        assert hasattr(system, "legacy_compatibility_matrix")

    def test_hitl_autonomy_controller_initialized(self):
        system = MurphySystem()
        assert hasattr(system, "hitl_autonomy_controller")

    def test_compliance_region_validator_initialized(self):
        system = MurphySystem()
        assert hasattr(system, "compliance_region_validator")

    def test_observability_counters_initialized(self):
        system = MurphySystem()
        assert hasattr(system, "observability_counters")

    def test_deterministic_routing_engine_initialized(self):
        system = MurphySystem()
        assert hasattr(system, "deterministic_routing_engine")

    def test_platform_connector_framework_initialized(self):
        system = MurphySystem()
        assert hasattr(system, "platform_connector_framework")

    def test_workflow_dag_engine_initialized(self):
        system = MurphySystem()
        assert hasattr(system, "workflow_dag_engine")

    def test_automation_type_registry_initialized(self):
        system = MurphySystem()
        assert hasattr(system, "automation_type_registry")

    def test_api_gateway_adapter_initialized(self):
        system = MurphySystem()
        assert hasattr(system, "api_gateway_adapter")

    def test_webhook_event_processor_initialized(self):
        system = MurphySystem()
        assert hasattr(system, "webhook_event_processor")

    def test_self_automation_orchestrator_initialized(self):
        system = MurphySystem()
        assert hasattr(system, "self_automation_orchestrator")

    def test_plugin_extension_sdk_initialized(self):
        system = MurphySystem()
        assert hasattr(system, "plugin_extension_sdk")

    def test_ai_workflow_generator_initialized(self):
        system = MurphySystem()
        assert hasattr(system, "ai_workflow_generator")

    def test_workflow_template_marketplace_initialized(self):
        system = MurphySystem()
        assert hasattr(system, "workflow_template_marketplace")

    def test_cross_platform_data_sync_initialized(self):
        system = MurphySystem()
        assert hasattr(system, "cross_platform_data_sync")


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
        assert "wingman_protocol" in components
        assert "runtime_profile_compiler" in components
        assert "governance_kernel" in components
        assert "control_plane_separation" in components
        assert "durable_swarm_orchestrator" in components
        assert "golden_path_bridge" in components
        assert "org_chart_enforcement" in components
        assert "shadow_agent_integration" in components
        assert "triage_rollcall_adapter" in components
        assert "rubix_evidence_adapter" in components
        assert "semantics_boundary_controller" in components
        assert "bot_governance_policy_mapper" in components
        assert "bot_telemetry_normalizer" in components
        assert "legacy_compatibility_matrix" in components
        assert "hitl_autonomy_controller" in components
        assert "compliance_region_validator" in components
        assert "observability_counters" in components
        assert "deterministic_routing_engine" in components
        assert "platform_connector_framework" in components
        assert "workflow_dag_engine" in components
        assert "automation_type_registry" in components
        assert "api_gateway_adapter" in components
        assert "webhook_event_processor" in components
        assert "self_automation_orchestrator" in components
        assert "plugin_extension_sdk" in components
        assert "ai_workflow_generator" in components
        assert "workflow_template_marketplace" in components
        assert "cross_platform_data_sync" in components

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
            "wingman_protocol",
            "runtime_profile_compiler",
            "governance_kernel",
            "control_plane_separation",
            "durable_swarm_orchestrator",
            "golden_path_bridge",
            "org_chart_enforcement",
            "shadow_agent_integration",
            "triage_rollcall_adapter",
            "rubix_evidence_adapter",
            "semantics_boundary_controller",
            "bot_governance_policy_mapper",
            "bot_telemetry_normalizer",
            "legacy_compatibility_matrix",
            "hitl_autonomy_controller",
            "compliance_region_validator",
            "observability_counters",
            "deterministic_routing_engine",
            "platform_connector_framework",
            "workflow_dag_engine",
            "automation_type_registry",
            "api_gateway_adapter",
            "webhook_event_processor",
            "self_automation_orchestrator",
            "plugin_extension_sdk",
            "ai_workflow_generator",
            "workflow_template_marketplace",
            "cross_platform_data_sync",
        }
        assert expected_keys.issubset(set(modules.keys()))
