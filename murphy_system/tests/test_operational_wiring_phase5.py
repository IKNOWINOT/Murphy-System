"""Tests verifying that Phase 5 operational modules are wired into the
executive planning engine binder for full operational capability exposure.

Phase 5 – Extended Operational Wiring Validation
"""

import os
import unittest


from event_backbone import EventBackbone
from compliance_engine import ComplianceEngine
from ticketing_adapter import TicketingAdapter
from wingman_protocol import WingmanProtocol
from operational_slo_tracker import OperationalSLOTracker
from automation_scheduler import AutomationScheduler
from rbac_governance import RBACGovernance
from self_improvement_engine import SelfImprovementEngine
from golden_path_bridge import GoldenPathBridge
from control_plane_separation import ControlPlaneSeparation
from runtime_profile_compiler import RuntimeProfileCompiler
from durable_swarm_orchestrator import DurableSwarmOrchestrator
from hitl_autonomy_controller import HITLAutonomyController
from shadow_agent_integration import ShadowAgentIntegration
from semantics_boundary_controller import SemanticsBoundaryController
from rubix_evidence_adapter import RubixEvidenceAdapter
from triage_rollcall_adapter import TriageRollcallAdapter
from bot_governance_policy_mapper import BotGovernancePolicyMapper
from bot_telemetry_normalizer import BotTelemetryNormalizer
from legacy_compatibility_matrix import LegacyCompatibilityMatrixAdapter


# ---------------------------------------------------------------------------
# Minimal stub that records binder.register_integration() calls
# ---------------------------------------------------------------------------

class _StubBinder:
    """Mimics ExecutivePlanningEngine.binder for testing."""

    def __init__(self):
        self.registered: list = []

    def register_integration(self, entry: dict) -> None:
        self.registered.append(entry)


class _StubPlanningEngine:
    """Mimics ExecutivePlanningEngine with only the .binder attribute."""

    def __init__(self):
        self.binder = _StubBinder()


class _Phase5StubRuntime:
    """Lightweight stand-in for MurphySystem runtime that carries only the
    Phase 5 operational modules under test."""

    def __init__(self):
        self.executive_planning_engine = _StubPlanningEngine()

        # Phase 5 modules
        self.event_backbone = EventBackbone()
        self.compliance_engine = ComplianceEngine()
        self.ticketing_adapter = TicketingAdapter()
        self.wingman_protocol = WingmanProtocol()
        self.slo_tracker = OperationalSLOTracker()
        self.automation_scheduler = AutomationScheduler()
        self.rbac_governance = RBACGovernance()
        self.self_improvement = SelfImprovementEngine()
        self.golden_path_bridge = GoldenPathBridge()
        self.control_plane_separation = ControlPlaneSeparation()
        self.runtime_profile_compiler = RuntimeProfileCompiler()
        self.durable_swarm_orchestrator = DurableSwarmOrchestrator()
        self.hitl_autonomy_controller = HITLAutonomyController()
        self.shadow_agent_integration = ShadowAgentIntegration()
        self.semantics_boundary_controller = SemanticsBoundaryController()
        self.rubix_evidence_adapter = RubixEvidenceAdapter()
        self.triage_rollcall_adapter = TriageRollcallAdapter()
        self.bot_governance_policy_mapper = BotGovernancePolicyMapper()
        self.bot_telemetry_normalizer = BotTelemetryNormalizer()
        self.legacy_compatibility_matrix = LegacyCompatibilityMatrixAdapter()

        # Modules from earlier phases – set to None (not under test here)
        self.platform_connector_framework = None
        self.enterprise_integrations = None
        self.building_automation_registry = None
        self.manufacturing_automation_registry = None
        self.energy_management_registry = None
        self.digital_asset_generator = None
        self.rosetta_stone_heartbeat = None
        self.content_creator_platform_modulator = None
        self.video_streaming_connector = None
        self.remote_access_connector = None
        self.universal_integration_adapter = None
        self.webhook_event_processor = None
        self.api_gateway_adapter = None
        self.automation_type_registry = None
        self.workflow_dag_engine = None
        self.self_automation_orchestrator = None
        self.plugin_extension_sdk = None
        self.ai_workflow_generator = None
        self.workflow_template_marketplace = None
        self.cross_platform_data_sync = None
        self.deterministic_routing_engine = None
        self.observability_counters = None
        self.ml_strategy_engine = None
        self.agentic_api_provisioner = None
        self.analytics_dashboard = None
        self.image_generation_engine = None
        self.security_hardening_config = None
        self.ui_testing_framework = None


# ---------------------------------------------------------------------------
# Phase 5 wiring logic (mirrors runtime's _wire_integrations_to_planning_engine)
# ---------------------------------------------------------------------------

def _wire_phase5(runtime):
    """Replicate Phase 5 wiring logic for the modules under test."""
    epe = getattr(runtime, 'executive_planning_engine', None)
    if epe is None:
        return 0
    binder = epe.binder
    wired = 0

    # Event Backbone
    eb = getattr(runtime, 'event_backbone', None)
    if eb is not None:
        binder.register_integration({
            "integration_id": "event_backbone",
            "name": "Event Backbone",
            "category": "event_routing",
            "capability": "publish,subscribe,dead_letter_queue",
            "source": "event_backbone",
        })
        wired += 1

    # Compliance Engine
    ce = getattr(runtime, 'compliance_engine', None)
    if ce is not None:
        binder.register_integration({
            "integration_id": "compliance_engine",
            "name": "Compliance Engine",
            "category": "compliance",
            "capability": "requirement_check,release_readiness,audit",
            "source": "compliance_engine",
        })
        wired += 1

    # Ticketing Adapter
    ta = getattr(runtime, 'ticketing_adapter', None)
    if ta is not None:
        binder.register_integration({
            "integration_id": "ticketing_adapter",
            "name": "Ticketing Adapter",
            "category": "issue_tracking",
            "capability": "create_ticket,escalate,patch_rollback",
            "source": "ticketing_adapter",
        })
        wired += 1

    # Wingman Protocol
    wp = getattr(runtime, 'wingman_protocol', None)
    if wp is not None:
        binder.register_integration({
            "integration_id": "wingman_protocol",
            "name": "Wingman Protocol",
            "category": "execution_validation",
            "capability": "pair_executor_validator,runbook,validate_output",
            "source": "wingman_protocol",
        })
        wired += 1

    # Operational SLO Tracker
    slo = getattr(runtime, 'slo_tracker', None)
    if slo is not None:
        binder.register_integration({
            "integration_id": "slo_tracker",
            "name": "Operational SLO Tracker",
            "category": "slo_monitoring",
            "capability": "record_execution,slo_compliance,metrics",
            "source": "operational_slo_tracker",
        })
        wired += 1

    # Automation Scheduler
    asch = getattr(runtime, 'automation_scheduler', None)
    if asch is not None:
        binder.register_integration({
            "integration_id": "automation_scheduler",
            "name": "Automation Scheduler",
            "category": "scheduling",
            "capability": "project_scheduling,batch_execution,queue",
            "source": "automation_scheduler",
        })
        wired += 1

    # RBAC Governance
    rbac = getattr(runtime, 'rbac_governance', None)
    if rbac is not None:
        binder.register_integration({
            "integration_id": "rbac_governance",
            "name": "RBAC Governance",
            "category": "access_control",
            "capability": "permission_check,tenant_isolation,role_management",
            "source": "rbac_governance",
        })
        wired += 1

    # Self-Improvement Engine
    sie = getattr(runtime, 'self_improvement', None)
    if sie is not None:
        binder.register_integration({
            "integration_id": "self_improvement_engine",
            "name": "Self-Improvement Engine",
            "category": "learning",
            "capability": "pattern_extraction,remediation,confidence_calibration",
            "source": "self_improvement_engine",
        })
        wired += 1

    # Golden Path Bridge
    gpb = getattr(runtime, 'golden_path_bridge', None)
    if gpb is not None:
        binder.register_integration({
            "integration_id": "golden_path_bridge",
            "name": "Golden Path Bridge",
            "category": "execution_optimization",
            "capability": "success_replay,path_matching,invalidation",
            "source": "golden_path_bridge",
        })
        wired += 1

    # Control Plane Separation
    cps = getattr(runtime, 'control_plane_separation', None)
    if cps is not None:
        binder.register_integration({
            "integration_id": "control_plane_separation",
            "name": "Control Plane Separation",
            "category": "routing",
            "capability": "mode_switching,task_routing,handler_registry",
            "source": "control_plane_separation",
        })
        wired += 1

    # Runtime Profile Compiler
    rpc = getattr(runtime, 'runtime_profile_compiler', None)
    if rpc is not None:
        binder.register_integration({
            "integration_id": "runtime_profile_compiler",
            "name": "Runtime Profile Compiler",
            "category": "execution_profiles",
            "capability": "profile_compile,autonomy_check,tool_allowlist",
            "source": "runtime_profile_compiler",
        })
        wired += 1

    # Durable Swarm Orchestrator
    dso = getattr(runtime, 'durable_swarm_orchestrator', None)
    if dso is not None:
        binder.register_integration({
            "integration_id": "durable_swarm_orchestrator",
            "name": "Durable Swarm Orchestrator",
            "category": "swarm_management",
            "capability": "spawn_task,budget_control,rollback",
            "source": "durable_swarm_orchestrator",
        })
        wired += 1

    # HITL Autonomy Controller
    hitl = getattr(runtime, 'hitl_autonomy_controller', None)
    if hitl is not None:
        binder.register_integration({
            "integration_id": "hitl_autonomy_controller",
            "name": "HITL Autonomy Controller",
            "category": "human_oversight",
            "capability": "autonomy_evaluation,cooldown,policy_management",
            "source": "hitl_autonomy_controller",
        })
        wired += 1

    # Shadow Agent Integration
    sai = getattr(runtime, 'shadow_agent_integration', None)
    if sai is not None:
        binder.register_integration({
            "integration_id": "shadow_agent_integration",
            "name": "Shadow Agent Integration",
            "category": "agent_management",
            "capability": "shadow_create,governance_boundary,role_binding",
            "source": "shadow_agent_integration",
        })
        wired += 1

    # Semantics Boundary Controller
    sbc = getattr(runtime, 'semantics_boundary_controller', None)
    if sbc is not None:
        binder.register_integration({
            "integration_id": "semantics_boundary_controller",
            "name": "Semantics Boundary Controller",
            "category": "risk_analysis",
            "capability": "belief_tracking,expected_loss,rvoi_questions",
            "source": "semantics_boundary_controller",
        })
        wired += 1

    # Rubix Evidence Adapter
    rea = getattr(runtime, 'rubix_evidence_adapter', None)
    if rea is not None:
        binder.register_integration({
            "integration_id": "rubix_evidence_adapter",
            "name": "Rubix Evidence Adapter",
            "category": "statistical_evidence",
            "capability": "confidence_interval,hypothesis_test,monte_carlo",
            "source": "rubix_evidence_adapter",
        })
        wired += 1

    # Triage Rollcall Adapter
    tra = getattr(runtime, 'triage_rollcall_adapter', None)
    if tra is not None:
        binder.register_integration({
            "integration_id": "triage_rollcall_adapter",
            "name": "Triage Rollcall Adapter",
            "category": "bot_triage",
            "capability": "candidate_probe,rollcall,ranking",
            "source": "triage_rollcall_adapter",
        })
        wired += 1

    # Bot Governance Policy Mapper
    bgpm = getattr(runtime, 'bot_governance_policy_mapper', None)
    if bgpm is not None:
        binder.register_integration({
            "integration_id": "bot_governance_policy_mapper",
            "name": "Bot Governance Policy Mapper",
            "category": "bot_governance",
            "capability": "policy_mapping,gate_check,budget_report",
            "source": "bot_governance_policy_mapper",
        })
        wired += 1

    # Bot Telemetry Normalizer
    btn = getattr(runtime, 'bot_telemetry_normalizer', None)
    if btn is not None:
        binder.register_integration({
            "integration_id": "bot_telemetry_normalizer",
            "name": "Bot Telemetry Normalizer",
            "category": "telemetry",
            "capability": "event_normalization,batch_normalize,unmapped_events",
            "source": "bot_telemetry_normalizer",
        })
        wired += 1

    # Legacy Compatibility Matrix
    lcm = getattr(runtime, 'legacy_compatibility_matrix', None)
    if lcm is not None:
        binder.register_integration({
            "integration_id": "legacy_compatibility_matrix",
            "name": "Legacy Compatibility Matrix",
            "category": "compatibility",
            "capability": "compatibility_check,migration_path,bridge_execution",
            "source": "legacy_compatibility_matrix",
        })
        wired += 1

    return wired


# ====================================================================
# Tests
# ====================================================================

PHASE5_MODULE_IDS = [
    "event_backbone",
    "compliance_engine",
    "ticketing_adapter",
    "wingman_protocol",
    "slo_tracker",
    "automation_scheduler",
    "rbac_governance",
    "self_improvement_engine",
    "golden_path_bridge",
    "control_plane_separation",
    "runtime_profile_compiler",
    "durable_swarm_orchestrator",
    "hitl_autonomy_controller",
    "shadow_agent_integration",
    "semantics_boundary_controller",
    "rubix_evidence_adapter",
    "triage_rollcall_adapter",
    "bot_governance_policy_mapper",
    "bot_telemetry_normalizer",
    "legacy_compatibility_matrix",
]


class TestPhase5WiringSetup(unittest.TestCase):
    """Ensure the Phase 5 wiring function produces registrations."""

    def setUp(self):
        self.runtime = _Phase5StubRuntime()
        self.wired_count = _wire_phase5(self.runtime)
        self.binder = self.runtime.executive_planning_engine.binder
        self._ids = [e["integration_id"] for e in self.binder.registered]

    def test_wired_count_equals_20(self):
        self.assertEqual(self.wired_count, 20)

    def test_binder_has_20_registrations(self):
        self.assertEqual(len(self.binder.registered), 20)


class TestPhase5EachModuleRegistered(unittest.TestCase):
    """Each Phase 5 module produces a binder registration."""

    def setUp(self):
        self.runtime = _Phase5StubRuntime()
        _wire_phase5(self.runtime)
        self.binder = self.runtime.executive_planning_engine.binder
        self._ids = [e["integration_id"] for e in self.binder.registered]

    def test_all_phase5_modules_registered(self):
        for mid in PHASE5_MODULE_IDS:
            with self.subTest(module=mid):
                self.assertIn(mid, self._ids, f"Expected {mid} in binder registrations")


class TestPhase5SourcesPresent(unittest.TestCase):
    """Each Phase 5 module has its source field set."""

    def setUp(self):
        self.runtime = _Phase5StubRuntime()
        _wire_phase5(self.runtime)
        self.binder = self.runtime.executive_planning_engine.binder

    def test_all_sources_non_empty(self):
        for entry in self.binder.registered:
            with self.subTest(entry=entry["integration_id"]):
                self.assertTrue(entry["source"], f"Empty source for {entry['integration_id']}")


class TestPhase5Categories(unittest.TestCase):
    """Each Phase 5 module carries a correct category tag."""

    EXPECTED_CATEGORIES = {
        "event_backbone": "event_routing",
        "compliance_engine": "compliance",
        "ticketing_adapter": "issue_tracking",
        "wingman_protocol": "execution_validation",
        "slo_tracker": "slo_monitoring",
        "automation_scheduler": "scheduling",
        "rbac_governance": "access_control",
        "self_improvement_engine": "learning",
        "golden_path_bridge": "execution_optimization",
        "control_plane_separation": "routing",
        "runtime_profile_compiler": "execution_profiles",
        "durable_swarm_orchestrator": "swarm_management",
        "hitl_autonomy_controller": "human_oversight",
        "shadow_agent_integration": "agent_management",
        "semantics_boundary_controller": "risk_analysis",
        "rubix_evidence_adapter": "statistical_evidence",
        "triage_rollcall_adapter": "bot_triage",
        "bot_governance_policy_mapper": "bot_governance",
        "bot_telemetry_normalizer": "telemetry",
        "legacy_compatibility_matrix": "compatibility",
    }

    def setUp(self):
        self.runtime = _Phase5StubRuntime()
        _wire_phase5(self.runtime)
        self.binder = self.runtime.executive_planning_engine.binder
        self._by_id = {e["integration_id"]: e for e in self.binder.registered}

    def test_categories_match(self):
        for mid, expected_cat in self.EXPECTED_CATEGORIES.items():
            with self.subTest(module=mid):
                entry = self._by_id.get(mid)
                self.assertIsNotNone(entry, f"Missing {mid}")
                self.assertEqual(entry["category"], expected_cat)


class TestPhase5Capabilities(unittest.TestCase):
    """Each Phase 5 module declares at least one capability."""

    def setUp(self):
        self.runtime = _Phase5StubRuntime()
        _wire_phase5(self.runtime)
        self.binder = self.runtime.executive_planning_engine.binder

    def test_all_have_capabilities(self):
        for entry in self.binder.registered:
            with self.subTest(entry=entry["integration_id"]):
                self.assertTrue(
                    entry["capability"],
                    f"Empty capability for {entry['integration_id']}"
                )

    def test_capabilities_are_comma_separated(self):
        for entry in self.binder.registered:
            with self.subTest(entry=entry["integration_id"]):
                parts = entry["capability"].split(",")
                self.assertGreaterEqual(len(parts), 1)
                for part in parts:
                    self.assertTrue(part.strip(), f"Blank capability part in {entry['integration_id']}")


class TestPhase5RequiredFields(unittest.TestCase):
    """Every Phase 5 binder registration has the required keys."""

    REQUIRED_KEYS = {"integration_id", "name", "category", "capability", "source"}

    def setUp(self):
        self.runtime = _Phase5StubRuntime()
        _wire_phase5(self.runtime)
        self.binder = self.runtime.executive_planning_engine.binder

    def test_all_entries_have_required_keys(self):
        for entry in self.binder.registered:
            with self.subTest(entry=entry["integration_id"]):
                self.assertTrue(
                    self.REQUIRED_KEYS.issubset(entry.keys()),
                    f"Entry {entry['integration_id']} missing keys: {self.REQUIRED_KEYS - entry.keys()}"
                )


class TestPhase5NoneModulesSkipped(unittest.TestCase):
    """Phase 5 modules set to None must not produce any binder registrations."""

    def test_all_none_produces_zero(self):
        runtime = _Phase5StubRuntime()
        for attr in [
            "event_backbone", "compliance_engine", "ticketing_adapter",
            "wingman_protocol", "slo_tracker", "automation_scheduler",
            "rbac_governance", "self_improvement", "golden_path_bridge",
            "control_plane_separation", "runtime_profile_compiler",
            "durable_swarm_orchestrator", "hitl_autonomy_controller",
            "shadow_agent_integration", "semantics_boundary_controller",
            "rubix_evidence_adapter", "triage_rollcall_adapter",
            "bot_governance_policy_mapper", "bot_telemetry_normalizer",
            "legacy_compatibility_matrix",
        ]:
            setattr(runtime, attr, None)
        count = _wire_phase5(runtime)
        self.assertEqual(count, 0)

    def test_no_epe_produces_zero(self):
        runtime = _Phase5StubRuntime()
        runtime.executive_planning_engine = None
        count = _wire_phase5(runtime)
        self.assertEqual(count, 0)


class TestPhase5ModuleStatusMethods(unittest.TestCase):
    """Verify each Phase 5 module has a get_status() method returning valid data."""

    def setUp(self):
        self.runtime = _Phase5StubRuntime()

    def test_event_backbone_status(self):
        status = self.runtime.event_backbone.get_status()
        self.assertIsInstance(status, dict)

    def test_compliance_engine_status(self):
        status = self.runtime.compliance_engine.get_status()
        self.assertIsInstance(status, dict)

    def test_ticketing_adapter_status(self):
        status = self.runtime.ticketing_adapter.get_status()
        self.assertIsInstance(status, dict)

    def test_wingman_protocol_status(self):
        status = self.runtime.wingman_protocol.get_status()
        self.assertIsInstance(status, dict)

    def test_slo_tracker_status(self):
        status = self.runtime.slo_tracker.get_status()
        self.assertIsInstance(status, dict)

    def test_automation_scheduler_status(self):
        status = self.runtime.automation_scheduler.get_status()
        self.assertIsInstance(status, dict)

    def test_rbac_governance_status(self):
        status = self.runtime.rbac_governance.get_status()
        self.assertIsInstance(status, dict)

    def test_self_improvement_status(self):
        status = self.runtime.self_improvement.get_status()
        self.assertIsInstance(status, dict)

    def test_golden_path_bridge_status(self):
        status = self.runtime.golden_path_bridge.get_status()
        self.assertIsInstance(status, dict)

    def test_control_plane_separation_status(self):
        status = self.runtime.control_plane_separation.get_status()
        self.assertIsInstance(status, dict)

    def test_runtime_profile_compiler_status(self):
        status = self.runtime.runtime_profile_compiler.get_status()
        self.assertIsInstance(status, dict)

    def test_durable_swarm_orchestrator_status(self):
        status = self.runtime.durable_swarm_orchestrator.get_status()
        self.assertIsInstance(status, dict)

    def test_hitl_autonomy_controller_status(self):
        # Some implementations may use get_autonomy_stats instead
        obj = self.runtime.hitl_autonomy_controller
        status = getattr(obj, 'get_status', getattr(obj, 'get_autonomy_stats', None))
        self.assertIsNotNone(status)
        result = status()
        self.assertIsInstance(result, dict)

    def test_shadow_agent_integration_status(self):
        status = self.runtime.shadow_agent_integration.get_status()
        self.assertIsInstance(status, dict)

    def test_semantics_boundary_controller_status(self):
        status = self.runtime.semantics_boundary_controller.get_status()
        self.assertIsInstance(status, dict)

    def test_rubix_evidence_adapter_status(self):
        status = self.runtime.rubix_evidence_adapter.get_status()
        self.assertIsInstance(status, dict)

    def test_triage_rollcall_adapter_status(self):
        status = self.runtime.triage_rollcall_adapter.get_status()
        self.assertIsInstance(status, dict)

    def test_bot_governance_policy_mapper_status(self):
        status = self.runtime.bot_governance_policy_mapper.get_status()
        self.assertIsInstance(status, dict)

    def test_bot_telemetry_normalizer_status(self):
        status = self.runtime.bot_telemetry_normalizer.get_status()
        self.assertIsInstance(status, dict)

    def test_legacy_compatibility_matrix_report(self):
        # This module may use get_matrix_report instead of get_status
        obj = self.runtime.legacy_compatibility_matrix
        method = getattr(obj, 'get_status', getattr(obj, 'get_matrix_report', None))
        self.assertIsNotNone(method)
        result = method()
        self.assertIsInstance(result, dict)


if __name__ == "__main__":
    unittest.main()
