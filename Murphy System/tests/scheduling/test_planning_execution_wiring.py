"""
Integration tests for executive planning engine wiring — validates that all
integration modules (platform connectors, enterprise integrations, building
automation, manufacturing, energy, digital assets, rosetta stone heartbeat,
content creator platforms) are registered with the executive planning engine's
IntegrationAutomationBinder during runtime initialization.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestIntegrationCatalogExpansion(unittest.TestCase):
    """Test that _INTEGRATION_CATALOG has entries for all module categories."""

    def setUp(self):
        try:
            from executive_planning_engine import (
                _INTEGRATION_CATALOG, ObjectiveCategory,
            )
            self.catalog = _INTEGRATION_CATALOG
            self.OC = ObjectiveCategory
        except ImportError as exc:
            self.skipTest(f"Executive planning engine not available: {exc}")

    def test_revenue_has_content_creator(self):
        ids = [e["integration_id"] for e in self.catalog[self.OC.REVENUE_TARGET]]
        self.assertIn("content_creator_platforms", ids)

    def test_revenue_has_messaging(self):
        ids = [e["integration_id"] for e in self.catalog[self.OC.REVENUE_TARGET]]
        self.assertIn("messaging_platforms", ids)

    def test_revenue_has_digital_asset(self):
        ids = [e["integration_id"] for e in self.catalog[self.OC.REVENUE_TARGET]]
        self.assertIn("digital_asset_pipeline", ids)

    def test_cost_reduction_has_building_automation(self):
        ids = [e["integration_id"] for e in self.catalog[self.OC.COST_REDUCTION]]
        self.assertIn("building_automation", ids)

    def test_cost_reduction_has_energy_management(self):
        ids = [e["integration_id"] for e in self.catalog[self.OC.COST_REDUCTION]]
        self.assertIn("energy_management", ids)

    def test_cost_reduction_has_manufacturing(self):
        ids = [e["integration_id"] for e in self.catalog[self.OC.COST_REDUCTION]]
        self.assertIn("manufacturing_automation", ids)

    def test_market_expansion_has_messaging(self):
        ids = [e["integration_id"] for e in self.catalog[self.OC.MARKET_EXPANSION]]
        self.assertIn("messaging_platforms", ids)

    def test_market_expansion_has_platform_connectors(self):
        ids = [e["integration_id"] for e in self.catalog[self.OC.MARKET_EXPANSION]]
        self.assertIn("platform_connectors", ids)

    def test_compliance_has_building_automation(self):
        ids = [e["integration_id"] for e in self.catalog[self.OC.COMPLIANCE_MANDATE]]
        self.assertIn("building_automation", ids)

    def test_compliance_has_manufacturing(self):
        ids = [e["integration_id"] for e in self.catalog[self.OC.COMPLIANCE_MANDATE]]
        self.assertIn("manufacturing_automation", ids)

    def test_operational_has_rosetta_stone(self):
        ids = [e["integration_id"] for e in self.catalog[self.OC.OPERATIONAL_EFFICIENCY]]
        self.assertIn("rosetta_stone_heartbeat", ids)

    def test_operational_has_enterprise_integrations(self):
        ids = [e["integration_id"] for e in self.catalog[self.OC.OPERATIONAL_EFFICIENCY]]
        self.assertIn("enterprise_integrations", ids)

    def test_catalog_total_entries(self):
        total = sum(len(v) for v in self.catalog.values())
        # Expanded from 15 to 34 (7+6+6+6+7 per category)
        self.assertGreaterEqual(total, 32)


class TestExecutivePlanningDiscovery(unittest.TestCase):
    """Test that discover_integrations_for_objective returns expanded catalog."""

    def setUp(self):
        try:
            from executive_planning_engine import ExecutivePlanningEngine
            self.engine = ExecutivePlanningEngine()
        except ImportError as exc:
            self.skipTest(f"Executive planning engine not available: {exc}")

    def test_revenue_discovery_includes_messaging(self):
        results = self.engine.binder.discover_integrations_for_objective(
            "obj-test-1", "revenue_target"
        )
        ids = [r["integration_id"] for r in results]
        self.assertIn("messaging_platforms", ids)

    def test_cost_discovery_includes_building(self):
        results = self.engine.binder.discover_integrations_for_objective(
            "obj-test-2", "cost_reduction"
        )
        ids = [r["integration_id"] for r in results]
        self.assertIn("building_automation", ids)

    def test_operational_discovery_includes_heartbeat(self):
        results = self.engine.binder.discover_integrations_for_objective(
            "obj-test-3", "operational_efficiency"
        )
        ids = [r["integration_id"] for r in results]
        self.assertIn("rosetta_stone_heartbeat", ids)

    def test_market_discovery_includes_content_creator(self):
        results = self.engine.binder.discover_integrations_for_objective(
            "obj-test-4", "market_expansion"
        )
        ids = [r["integration_id"] for r in results]
        self.assertIn("content_creator_platforms", ids)

    def test_compliance_discovery_includes_energy(self):
        results = self.engine.binder.discover_integrations_for_objective(
            "obj-test-5", "compliance_mandate"
        )
        ids = [r["integration_id"] for r in results]
        self.assertIn("energy_management", ids)


class TestBinderRegistration(unittest.TestCase):
    """Test that custom integrations can be registered and discovered."""

    def setUp(self):
        try:
            from executive_planning_engine import ExecutivePlanningEngine
            self.engine = ExecutivePlanningEngine()
        except ImportError as exc:
            self.skipTest(f"Executive planning engine not available: {exc}")

    def test_register_custom_integration(self):
        result = self.engine.binder.register_integration({
            "integration_id": "test_whatsapp",
            "name": "WhatsApp Business",
            "category": "revenue_target",
            "capability": "messaging",
        })
        self.assertTrue(result["registered"])

    def test_registered_integration_discovered(self):
        self.engine.binder.register_integration({
            "integration_id": "test_telegram",
            "name": "Telegram Bot",
            "category": "revenue_target",
            "capability": "bot_messaging",
        })
        results = self.engine.binder.discover_integrations_for_objective(
            "obj-test-6", "revenue_target"
        )
        ids = [r["integration_id"] for r in results]
        self.assertIn("test_telegram", ids)

    def test_bind_integration_to_workflow(self):
        binding = self.engine.binder.bind_integration_to_workflow(
            "pcf_whatsapp", "wf-test-1",
            {"step": "send_notification", "channel": "whatsapp"},
        )
        self.assertIn("binding_id", binding)
        self.assertEqual(binding["status"], "bound")

    def test_activate_binding(self):
        binding = self.engine.binder.bind_integration_to_workflow(
            "pcf_telegram", "wf-test-2",
            {"step": "send_alert", "channel": "telegram"},
        )
        activated = self.engine.binder.activate_binding(binding["binding_id"])
        self.assertEqual(activated["status"], "active")

    def test_list_bindings_for_workflow(self):
        self.engine.binder.bind_integration_to_workflow(
            "pcf_signal", "wf-test-3", {"step": "secure_msg"},
        )
        self.engine.binder.bind_integration_to_workflow(
            "pcf_snapchat", "wf-test-3", {"step": "snap_alert"},
        )
        bindings = self.engine.binder.list_bindings_for_workflow("wf-test-3")
        self.assertEqual(len(bindings), 2)


class TestObjectiveToGateFlow(unittest.TestCase):
    """End-to-end: create objective → generate gates → discover integrations."""

    def setUp(self):
        try:
            from executive_planning_engine import ExecutivePlanningEngine
            self.engine = ExecutivePlanningEngine()
        except ImportError as exc:
            self.skipTest(f"Executive planning engine not available: {exc}")

    def test_full_objective_lifecycle(self):
        # Create and activate objective
        obj = self.engine.planner.create_objective(
            name="Expand APAC Market",
            category="market_expansion",
            target_metric="revenue >= 5M",
            deadline="2026-12-31",
            priority=1,
        )
        self.assertIn("objective_id", obj)
        activated = self.engine.planner.activate_objective(obj["objective_id"])
        self.assertEqual(activated["status"], "active")

        # Generate gates
        gates = self.engine.gate_generator.generate_gates_for_objective(
            obj["objective_id"], "market_expansion",
        )
        self.assertGreater(len(gates), 0)

        # Discover integrations — should include messaging platforms
        intgs = self.engine.binder.discover_integrations_for_objective(
            obj["objective_id"], "market_expansion",
        )
        ids = [i["integration_id"] for i in intgs]
        self.assertIn("messaging_platforms", ids)
        self.assertIn("platform_connectors", ids)

    def test_cost_reduction_with_building_automation(self):
        obj = self.engine.planner.create_objective(
            name="Reduce HVAC Costs",
            category="cost_reduction",
            target_metric="cost <= 50K",
            deadline="2026-12-31",
            priority=2,
        )
        intgs = self.engine.binder.discover_integrations_for_objective(
            obj["objective_id"], "cost_reduction",
        )
        ids = [i["integration_id"] for i in intgs]
        self.assertIn("building_automation", ids)
        self.assertIn("energy_management", ids)

    def test_compliance_with_manufacturing(self):
        obj = self.engine.planner.create_objective(
            name="ISA-95 Compliance",
            category="compliance_mandate",
            target_metric="compliance >= 100%",
            deadline="2026-12-31",
            priority=1,
        )
        intgs = self.engine.binder.discover_integrations_for_objective(
            obj["objective_id"], "compliance_mandate",
        )
        ids = [i["integration_id"] for i in intgs]
        self.assertIn("manufacturing_automation", ids)


if __name__ == '__main__':
    unittest.main()
