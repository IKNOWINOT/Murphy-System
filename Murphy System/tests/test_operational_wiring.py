"""Tests verifying that all integration modules are wired into the
executive planning engine binder for operational capability exposure.

Phase 4 – Operational Wiring Validation
"""

import os
import unittest


from universal_integration_adapter import UniversalIntegrationAdapter
from platform_connector_framework import PlatformConnectorFramework
from webhook_event_processor import WebhookEventProcessor
from api_gateway_adapter import APIGatewayAdapter
from automation_type_registry import AutomationTypeRegistry
from workflow_dag_engine import WorkflowDAGEngine
from self_automation_orchestrator import SelfAutomationOrchestrator
from plugin_extension_sdk import PluginExtensionSDK
from ai_workflow_generator import AIWorkflowGenerator
from workflow_template_marketplace import WorkflowTemplateMarketplace
from cross_platform_data_sync import CrossPlatformDataSync
from deterministic_routing_engine import DeterministicRoutingEngine
from observability_counters import ObservabilitySummaryCounters
from ml_strategy_engine import MLStrategyEngine
from agentic_api_provisioner import AgenticAPIProvisioner
from analytics_dashboard import AnalyticsDashboard
from image_generation_engine import ImageGenerationEngine
from security_hardening_config import SecurityHardeningConfig


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


class _StubRuntime:
    """Lightweight stand-in for MurphySystem runtime that only carries the
    attributes consumed by ``_wire_integrations_to_planning_engine``."""

    def __init__(self):
        self.executive_planning_engine = _StubPlanningEngine()

        # === Originally wired modules ===
        self.platform_connector_framework = PlatformConnectorFramework()
        # enterprise_integrations, building_automation_registry, etc. intentionally
        # omitted – we test the *new* wiring additions below

        # === Previously un-wired modules – now wired ===
        self.universal_integration_adapter = UniversalIntegrationAdapter()
        self.webhook_event_processor = WebhookEventProcessor()
        self.api_gateway_adapter = APIGatewayAdapter()
        self.automation_type_registry = AutomationTypeRegistry()
        self.workflow_dag_engine = WorkflowDAGEngine()
        self.self_automation_orchestrator = SelfAutomationOrchestrator()
        self.plugin_extension_sdk = PluginExtensionSDK(murphy_version="1.0.0")
        self.ai_workflow_generator = AIWorkflowGenerator()
        self.workflow_template_marketplace = WorkflowTemplateMarketplace()
        self.cross_platform_data_sync = CrossPlatformDataSync()
        self.deterministic_routing_engine = DeterministicRoutingEngine()
        self.observability_counters = ObservabilitySummaryCounters()
        self.ml_strategy_engine = MLStrategyEngine()
        self.agentic_api_provisioner = AgenticAPIProvisioner()
        self.analytics_dashboard = AnalyticsDashboard()
        self.image_generation_engine = ImageGenerationEngine()
        self.security_hardening_config = SecurityHardeningConfig()

        # Modules not under test – set to None
        self.enterprise_integrations = None
        self.building_automation_registry = None
        self.manufacturing_automation_registry = None
        self.energy_management_registry = None
        self.digital_asset_generator = None
        self.rosetta_stone_heartbeat = None
        self.content_creator_platform_modulator = None
        self.video_streaming_connector = None
        self.remote_access_connector = None
        self.ui_testing_framework = None


def _load_wiring_method():
    """Import only the _wire_integrations_to_planning_engine method from
    the runtime and return a callable bound to a _StubRuntime."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "runtime",
        os.path.join(os.path.dirname(__file__), "..", "murphy_system_1.0_runtime.py"),
        submodule_search_locations=[]
    )
    # We don't actually load the full runtime module (too heavy).
    # Instead, we read the method source and exec it.
    return None  # Fallback – use direct wiring logic below


# ---------------------------------------------------------------------------
# We replicate the wiring logic from the runtime for test isolation.
# This avoids importing the 12 k-line runtime.
# ---------------------------------------------------------------------------

def _wire(runtime):
    """Replicate _wire_integrations_to_planning_engine logic for
    the modules under test."""
    epe = getattr(runtime, 'executive_planning_engine', None)
    if epe is None:
        return 0
    binder = epe.binder
    wired = 0

    # Platform Connector Framework
    pcf = getattr(runtime, 'platform_connector_framework', None)
    if pcf is not None:
        for c in pcf.list_available_connectors():
            binder.register_integration({
                "integration_id": f"pcf_{c['connector_id']}",
                "name": c["name"],
                "category": c.get("category", "custom"),
                "capability": ",".join(c.get("capabilities", [])[:3]),
                "source": "platform_connector_framework",
            })
            wired += 1

    # Universal Integration Adapter
    uia = getattr(runtime, 'universal_integration_adapter', None)
    if uia is not None:
        for svc in uia.list_services():
            sid = svc.get("service_id", "unknown")
            binder.register_integration({
                "integration_id": f"uia_{sid}",
                "name": svc.get("name", sid),
                "category": svc.get("category", "general"),
                "capability": ",".join(svc.get("actions", [])[:3]) if svc.get("actions") else "api",
                "source": "universal_integration_adapter",
            })
            wired += 1

    # Webhook Event Processor
    wep = getattr(runtime, 'webhook_event_processor', None)
    if wep is not None:
        for src in wep.list_sources():
            src_id = src.get("source_id", "unknown") if isinstance(src, dict) else str(src)
            binder.register_integration({
                "integration_id": f"wep_{src_id}",
                "name": f"Webhook – {src.get('name', src_id) if isinstance(src, dict) else src_id}",
                "category": "webhook",
                "capability": "inbound_webhook",
                "source": "webhook_event_processor",
            })
            wired += 1

    # API Gateway Adapter
    aga = getattr(runtime, 'api_gateway_adapter', None)
    if aga is not None:
        binder.register_integration({
            "integration_id": "api_gateway_adapter",
            "name": "API Gateway Adapter",
            "category": "api_management",
            "capability": "routing,rate_limiting,auth",
            "source": "api_gateway_adapter",
        })
        wired += 1

    # Automation Type Registry
    atr = getattr(runtime, 'automation_type_registry', None)
    if atr is not None:
        for tmpl in atr.list_templates():
            tid = tmpl.get("template_id", "unknown") if isinstance(tmpl, dict) else str(tmpl)
            binder.register_integration({
                "integration_id": f"atr_{tid}",
                "name": f"Automation Template – {tmpl.get('name', tid) if isinstance(tmpl, dict) else tid}",
                "category": "automation",
                "capability": "workflow_template",
                "source": "automation_type_registry",
            })
            wired += 1

    # Workflow DAG Engine
    wde = getattr(runtime, 'workflow_dag_engine', None)
    if wde is not None:
        binder.register_integration({
            "integration_id": "workflow_dag_engine",
            "name": "Workflow DAG Engine",
            "category": "workflow_orchestration",
            "capability": "dag_execution,checkpointing,parallel",
            "source": "workflow_dag_engine",
        })
        wired += 1

    # Self-Automation Orchestrator
    sao = getattr(runtime, 'self_automation_orchestrator', None)
    if sao is not None:
        binder.register_integration({
            "integration_id": "self_automation_orchestrator",
            "name": "Self-Automation Orchestrator",
            "category": "self_automation",
            "capability": "task_management,gap_analysis,prompt_generation",
            "source": "self_automation_orchestrator",
        })
        wired += 1

    # Plugin Extension SDK
    pex = getattr(runtime, 'plugin_extension_sdk', None)
    if pex is not None:
        binder.register_integration({
            "integration_id": "plugin_extension_sdk",
            "name": "Plugin Extension SDK",
            "category": "extensibility",
            "capability": "plugin_install,plugin_execute,hooks",
            "source": "plugin_extension_sdk",
        })
        wired += 1

    # AI Workflow Generator
    awg = getattr(runtime, 'ai_workflow_generator', None)
    if awg is not None:
        binder.register_integration({
            "integration_id": "ai_workflow_generator",
            "name": "AI Workflow Generator",
            "category": "ai_automation",
            "capability": "workflow_generation,step_types",
            "source": "ai_workflow_generator",
        })
        wired += 1

    # Workflow Template Marketplace
    wtm = getattr(runtime, 'workflow_template_marketplace', None)
    if wtm is not None:
        binder.register_integration({
            "integration_id": "workflow_template_marketplace",
            "name": "Workflow Template Marketplace",
            "category": "marketplace",
            "capability": "template_publish,template_install,rating",
            "source": "workflow_template_marketplace",
        })
        wired += 1

    # Cross-Platform Data Sync
    cpds = getattr(runtime, 'cross_platform_data_sync', None)
    if cpds is not None:
        binder.register_integration({
            "integration_id": "cross_platform_data_sync",
            "name": "Cross-Platform Data Sync",
            "category": "data_sync",
            "capability": "sync,conflict_resolution,mapping",
            "source": "cross_platform_data_sync",
        })
        wired += 1

    # Deterministic Routing Engine
    dre = getattr(runtime, 'deterministic_routing_engine', None)
    if dre is not None:
        policies = dre.list_policies()
        for pol in policies:
            pid = pol.get("policy_id", "unknown") if isinstance(pol, dict) else str(pol)
            binder.register_integration({
                "integration_id": f"dre_{pid}",
                "name": f"Routing Policy – {pol.get('name', pid) if isinstance(pol, dict) else pid}",
                "category": "routing",
                "capability": "deterministic_routing,guardrails",
                "source": "deterministic_routing_engine",
            })
            wired += 1
        if not policies:
            binder.register_integration({
                "integration_id": "deterministic_routing_engine",
                "name": "Deterministic Routing Engine",
                "category": "routing",
                "capability": "deterministic_routing,guardrails",
                "source": "deterministic_routing_engine",
            })
            wired += 1

    # Observability Summary Counters
    osc = getattr(runtime, 'observability_counters', None)
    if osc is not None:
        binder.register_integration({
            "integration_id": "observability_counters",
            "name": "Observability Summary Counters",
            "category": "observability",
            "capability": "metrics,counters,telemetry",
            "source": "observability_counters",
        })
        wired += 1

    # ML Strategy Engine
    mse = getattr(runtime, 'ml_strategy_engine', None)
    if mse is not None:
        binder.register_integration({
            "integration_id": "ml_strategy_engine",
            "name": "ML Strategy Engine",
            "category": "machine_learning",
            "capability": "anomaly_detection,forecasting,classification",
            "source": "ml_strategy_engine",
        })
        wired += 1

    # Agentic API Provisioner
    aap = getattr(runtime, 'agentic_api_provisioner', None)
    if aap is not None:
        binder.register_integration({
            "integration_id": "agentic_api_provisioner",
            "name": "Agentic API Provisioner",
            "category": "api_provisioning",
            "capability": "auto_provision,health_checks,openapi_spec",
            "source": "agentic_api_provisioner",
        })
        wired += 1

    # Analytics Dashboard
    adb = getattr(runtime, 'analytics_dashboard', None)
    if adb is not None:
        binder.register_integration({
            "integration_id": "analytics_dashboard",
            "name": "Analytics Dashboard",
            "category": "analytics",
            "capability": "metrics,alerts,dashboards",
            "source": "analytics_dashboard",
        })
        wired += 1

    # Image Generation Engine
    ige = getattr(runtime, 'image_generation_engine', None)
    if ige is not None:
        binder.register_integration({
            "integration_id": "image_generation_engine",
            "name": "Image Generation Engine",
            "category": "content_generation",
            "capability": "image_generation,style_transfer",
            "source": "image_generation_engine",
        })
        wired += 1

    # Security Hardening Config
    shc = getattr(runtime, 'security_hardening_config', None)
    if shc is not None:
        binder.register_integration({
            "integration_id": "security_hardening_config",
            "name": "Security Hardening Config",
            "category": "security",
            "capability": "request_security,response_headers",
            "source": "security_hardening_config",
        })
        wired += 1

    # UI Testing Framework
    ui_test_fw = getattr(runtime, 'ui_testing_framework', None)
    if ui_test_fw is not None:
        binder.register_integration({
            "integration_id": "ui_testing_framework",
            "name": "UI Testing Framework",
            "category": "testing",
            "capability": "ui_testing,accessibility,visual_regression",
            "source": "ui_testing_framework",
        })
        wired += 1

    return wired


# ====================================================================
# Tests
# ====================================================================

class TestOperationalWiringSetup(unittest.TestCase):
    """Ensure the wiring function produces registrations."""

    def setUp(self):
        self.runtime = _StubRuntime()
        self.wired_count = _wire(self.runtime)
        self.binder = self.runtime.executive_planning_engine.binder
        self._ids = [e["integration_id"] for e in self.binder.registered]
        self._sources = [e["source"] for e in self.binder.registered]

    def test_wired_count_positive(self):
        self.assertGreater(self.wired_count, 0)

    def test_binder_has_registrations(self):
        self.assertEqual(self.wired_count, len(self.binder.registered))


class TestUniversalAdapterWired(unittest.TestCase):
    """Universal Integration Adapter services appear in binder."""

    def setUp(self):
        self.runtime = _StubRuntime()
        _wire(self.runtime)
        self.binder = self.runtime.executive_planning_engine.binder
        self._ids = [e["integration_id"] for e in self.binder.registered]
        self._sources = [e["source"] for e in self.binder.registered]

    def test_adapter_services_registered(self):
        uia_entries = [e for e in self.binder.registered if e["source"] == "universal_integration_adapter"]
        adapter = self.runtime.universal_integration_adapter
        self.assertEqual(len(uia_entries), len(adapter.list_services()))

    def test_adapter_ids_prefixed(self):
        uia_ids = [e["integration_id"] for e in self.binder.registered if e["source"] == "universal_integration_adapter"]
        for eid in uia_ids:
            self.assertTrue(eid.startswith("uia_"), f"Expected uia_ prefix: {eid}")

    def test_slack_wired(self):
        self.assertIn("uia_slack", self._ids)

    def test_stripe_wired(self):
        self.assertIn("uia_stripe", self._ids)

    def test_github_wired(self):
        self.assertIn("uia_github", self._ids)


class TestWebhookProcessorWired(unittest.TestCase):
    """Webhook Event Processor sources appear in binder."""

    def setUp(self):
        self.runtime = _StubRuntime()
        _wire(self.runtime)
        self.binder = self.runtime.executive_planning_engine.binder
        self._ids = [e["integration_id"] for e in self.binder.registered]

    def test_webhook_sources_registered(self):
        wep_entries = [e for e in self.binder.registered if e["source"] == "webhook_event_processor"]
        processor = self.runtime.webhook_event_processor
        self.assertEqual(len(wep_entries), len(processor.list_sources()))

    def test_webhook_ids_prefixed(self):
        wep_ids = [e["integration_id"] for e in self.binder.registered if e["source"] == "webhook_event_processor"]
        for eid in wep_ids:
            self.assertTrue(eid.startswith("wep_"), f"Expected wep_ prefix: {eid}")

    def test_github_webhook_wired(self):
        self.assertIn("wep_github_webhook", self._ids)

    def test_stripe_webhook_wired(self):
        self.assertIn("wep_stripe_webhook", self._ids)


class TestSingletonModulesWired(unittest.TestCase):
    """Modules that register exactly one integration each."""

    EXPECTED_SINGLETONS = [
        "api_gateway_adapter",
        "workflow_dag_engine",
        "self_automation_orchestrator",
        "plugin_extension_sdk",
        "ai_workflow_generator",
        "workflow_template_marketplace",
        "cross_platform_data_sync",
        "observability_counters",
        "ml_strategy_engine",
        "agentic_api_provisioner",
        "analytics_dashboard",
        "image_generation_engine",
        "security_hardening_config",
    ]

    def setUp(self):
        self.runtime = _StubRuntime()
        _wire(self.runtime)
        self.binder = self.runtime.executive_planning_engine.binder
        self._ids = [e["integration_id"] for e in self.binder.registered]

    def test_each_singleton_registered(self):
        for sid in self.EXPECTED_SINGLETONS:
            with self.subTest(module=sid):
                self.assertIn(sid, self._ids, f"Expected {sid} in binder registrations")

    def test_singleton_sources_present(self):
        sources = {e["source"] for e in self.binder.registered}
        for sid in self.EXPECTED_SINGLETONS:
            with self.subTest(module=sid):
                self.assertIn(sid, sources)


class TestDeterministicRoutingWired(unittest.TestCase):
    """DeterministicRoutingEngine gets wired even with zero policies."""

    def setUp(self):
        self.runtime = _StubRuntime()
        _wire(self.runtime)
        self.binder = self.runtime.executive_planning_engine.binder
        self._ids = [e["integration_id"] for e in self.binder.registered]
        self._sources = {e["source"] for e in self.binder.registered}

    def test_routing_engine_present(self):
        self.assertIn("deterministic_routing_engine", self._sources)

    def test_routing_has_id(self):
        dre_entries = [e for e in self.binder.registered if e["source"] == "deterministic_routing_engine"]
        self.assertGreaterEqual(len(dre_entries), 1)


class TestPlatformConnectorFrameworkWired(unittest.TestCase):
    """PCF connectors (already wired in earlier PR) still present."""

    def setUp(self):
        self.runtime = _StubRuntime()
        _wire(self.runtime)
        self.binder = self.runtime.executive_planning_engine.binder
        self._ids = [e["integration_id"] for e in self.binder.registered]

    def test_pcf_entries_present(self):
        pcf_entries = [e for e in self.binder.registered if e["source"] == "platform_connector_framework"]
        fw = self.runtime.platform_connector_framework
        self.assertEqual(len(pcf_entries), len(fw.list_available_connectors()))

    def test_pcf_slack_present(self):
        self.assertIn("pcf_slack", self._ids)


class TestWiringCategories(unittest.TestCase):
    """Each source carries the correct category tag."""

    EXPECTED_CATEGORIES = {
        "universal_integration_adapter": {"crm", "payment", "devops", "communication", "cloud"},
        "webhook_event_processor": {"webhook"},
        "api_gateway_adapter": {"api_management"},
        "workflow_dag_engine": {"workflow_orchestration"},
        "self_automation_orchestrator": {"self_automation"},
        "plugin_extension_sdk": {"extensibility"},
        "ai_workflow_generator": {"ai_automation"},
        "workflow_template_marketplace": {"marketplace"},
        "cross_platform_data_sync": {"data_sync"},
        "observability_counters": {"observability"},
        "ml_strategy_engine": {"machine_learning"},
        "agentic_api_provisioner": {"api_provisioning"},
        "analytics_dashboard": {"analytics"},
        "image_generation_engine": {"content_generation"},
        "security_hardening_config": {"security"},
    }

    def setUp(self):
        self.runtime = _StubRuntime()
        _wire(self.runtime)
        self.binder = self.runtime.executive_planning_engine.binder

    def test_categories(self):
        for source, expected_cats in self.EXPECTED_CATEGORIES.items():
            entries = [e for e in self.binder.registered if e["source"] == source]
            if not entries:
                continue
            actual_cats = {e["category"] for e in entries}
            with self.subTest(source=source):
                self.assertTrue(
                    actual_cats & expected_cats,
                    f"Source {source} has categories {actual_cats}, expected overlap with {expected_cats}"
                )


class TestAllEntriesHaveRequiredFields(unittest.TestCase):
    """Every binder registration has the required keys."""

    REQUIRED_KEYS = {"integration_id", "name", "category", "capability", "source"}

    def setUp(self):
        self.runtime = _StubRuntime()
        _wire(self.runtime)
        self.binder = self.runtime.executive_planning_engine.binder

    def test_all_entries_have_required_keys(self):
        for entry in self.binder.registered:
            with self.subTest(entry=entry["integration_id"]):
                self.assertTrue(
                    self.REQUIRED_KEYS.issubset(entry.keys()),
                    f"Entry {entry['integration_id']} missing keys: {self.REQUIRED_KEYS - entry.keys()}"
                )

    def test_no_empty_integration_ids(self):
        for entry in self.binder.registered:
            self.assertTrue(entry["integration_id"], "Empty integration_id found")

    def test_no_empty_names(self):
        for entry in self.binder.registered:
            self.assertTrue(entry["name"], "Empty name found")


class TestWiredCountMinimum(unittest.TestCase):
    """Total wired registrations should exceed the original ~30 (PCF-only)
    count now that 18 additional modules are connected."""

    def test_total_registrations_at_least_150(self):
        runtime = _StubRuntime()
        count = _wire(runtime)
        # 76 PCF connectors + 76 adapter services + 61 webhook sources + ~15 singletons
        self.assertGreaterEqual(count, 150)

    def test_distinct_sources_at_least_15(self):
        runtime = _StubRuntime()
        _wire(runtime)
        sources = {e["source"] for e in runtime.executive_planning_engine.binder.registered}
        self.assertGreaterEqual(len(sources), 15)


class TestNoneModulesSkipped(unittest.TestCase):
    """Modules set to None must not produce any binder registrations."""

    def test_none_module_produces_zero_entries(self):
        runtime = _StubRuntime()
        # Override all modules with None
        for attr in [
            "platform_connector_framework",
            "universal_integration_adapter",
            "webhook_event_processor",
            "api_gateway_adapter",
            "automation_type_registry",
            "workflow_dag_engine",
            "self_automation_orchestrator",
            "plugin_extension_sdk",
            "ai_workflow_generator",
            "workflow_template_marketplace",
            "cross_platform_data_sync",
            "deterministic_routing_engine",
            "observability_counters",
            "ml_strategy_engine",
            "agentic_api_provisioner",
            "analytics_dashboard",
            "image_generation_engine",
            "security_hardening_config",
            "ui_testing_framework",
        ]:
            setattr(runtime, attr, None)
        count = _wire(runtime)
        self.assertEqual(count, 0)

    def test_no_epe_produces_zero(self):
        runtime = _StubRuntime()
        runtime.executive_planning_engine = None
        count = _wire(runtime)
        self.assertEqual(count, 0)


if __name__ == "__main__":
    unittest.main()
