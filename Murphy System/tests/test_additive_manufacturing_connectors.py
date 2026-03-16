"""
Tests for Additive Manufacturing / 3D Printing Connectors Module.

Validates connector registry, health checks, action execution,
workflow orchestration, and all AM process/vendor coverage.
"""
import unittest
import os



class TestAMConnectorBasics(unittest.TestCase):
    """Basic connector functionality."""

    def setUp(self):
        from src.additive_manufacturing_connectors import (
            AdditiveManufacturingRegistry,
            AMWorkflowBinder,
            AdditiveProcess,
            AMProtocol,
            AMSystemLayer,
            MaterialClass,
            get_status,
        )
        self.registry = AdditiveManufacturingRegistry()
        self.binder = AMWorkflowBinder(self.registry)
        self.Process = AdditiveProcess
        self.Protocol = AMProtocol
        self.Layer = AMSystemLayer
        self.Material = MaterialClass
        self.get_status = get_status

    def test_registry_has_default_connectors(self):
        connectors = self.registry.discover()
        self.assertGreaterEqual(len(connectors), 10,
                                "Should have at least 10 default connectors")

    def test_all_am_processes_covered(self):
        processes = self.registry.list_processes()
        required = {"fdm_fff", "sla_dlp", "sls", "slm_dmls", "ebm",
                     "polyjet_mjf", "binder_jetting", "ded_waam",
                     "continuous_fiber"}
        for proc in required:
            self.assertIn(proc, processes, f"Missing AM process: {proc}")

    def test_vendor_coverage(self):
        vendors = self.registry.list_vendors()
        for v in ["stratasys", "ultimaker", "formlabs", "hp",
                   "eos", "markforged", "desktop_metal"]:
            self.assertIn(v, vendors, f"Missing vendor: {v}")

    def test_protocol_coverage(self):
        protocols = self.registry.list_protocols()
        for p in ["rest_api", "opc_ua_am", "mtconnect", "mqtt_sparkplug_b"]:
            self.assertIn(p, protocols, f"Missing protocol: {p}")

    def test_layer_coverage(self):
        layers = self.registry.list_layers()
        for layer in ["L0", "L1", "L2", "L3"]:
            self.assertIn(layer, layers, f"Missing ISA-95 layer: {layer}")

    def test_connector_health_check(self):
        connectors = self.registry.discover()
        key = list(self.registry._connectors.keys())[0]
        health = self.registry.health_check(key)
        self.assertIn("status", health)
        self.assertIn("name", health)
        self.assertIn("vendor", health)

    def test_connector_execute_action(self):
        # Find a connector and execute one of its capabilities
        key = list(self.registry._connectors.keys())[0]
        connector = self.registry.get_connector(key)
        action = connector.capabilities[0]
        result = self.registry.execute(key, action)
        self.assertTrue(result.get("success"), f"Action '{action}' should succeed")

    def test_connector_unknown_action_fails(self):
        key = list(self.registry._connectors.keys())[0]
        result = self.registry.execute(key, "nonexistent_action_xyz")
        self.assertFalse(result.get("success"))

    def test_connector_disable_enable(self):
        key = list(self.registry._connectors.keys())[0]
        connector = self.registry.get_connector(key)
        connector.disable()
        self.assertFalse(connector.is_enabled())
        result = connector.execute_action("submit_build_job")
        self.assertFalse(result.get("success"))
        connector.enable()
        self.assertTrue(connector.is_enabled())

    def test_health_check_all(self):
        health = self.registry.health_check_all()
        self.assertGreaterEqual(len(health), 10)
        for key, report in health.items():
            self.assertIn("status", report)

    def test_statistics(self):
        stats = self.registry.statistics()
        self.assertGreaterEqual(stats["total_connectors"], 10)
        self.assertGreaterEqual(stats["enabled_connectors"], 10)
        self.assertEqual(stats["disabled_connectors"], 0)
        self.assertGreater(len(stats["vendors"]), 5)

    def test_get_status(self):
        status = self.get_status()
        self.assertEqual(status["module"], "additive_manufacturing_connectors")
        self.assertIn("statistics", status)
        self.assertIn("health", status)

    def test_register_custom_connector(self):
        from src.additive_manufacturing_connectors import AMConnector
        custom = AMConnector(
            name="Custom Printer",
            vendor="custom_vendor",
            process=self.Process.FDM_FFF,
            protocol=self.Protocol.REST_API,
            layer=self.Layer.SUPERVISORY,
            protocol_version="1.0",
            connection_config={"requests_per_minute": 60},
            capabilities=["submit_build_job", "cancel_job"],
            supported_materials=[self.Material.THERMOPLASTIC],
        )
        result = self.registry.register(custom, key="custom_test")
        self.assertTrue(result["registered"])
        self.assertIsNotNone(self.registry.get_connector("custom_test"))

    def test_unregister_connector(self):
        from src.additive_manufacturing_connectors import AMConnector
        custom = AMConnector(
            name="Temp Printer",
            vendor="temp",
            process=self.Process.SLA_DLP,
            protocol=self.Protocol.REST_API,
            layer=self.Layer.SUPERVISORY,
            protocol_version="1.0",
            connection_config={"requests_per_minute": 60},
            capabilities=["submit_build_job"],
        )
        self.registry.register(custom, key="temp_test")
        result = self.registry.unregister("temp_test")
        self.assertTrue(result["unregistered"])
        self.assertIsNone(self.registry.get_connector("temp_test"))

    def test_discover_by_process(self):
        fdm = self.registry.discover(process=self.Process.FDM_FFF)
        self.assertGreaterEqual(len(fdm), 3, "Should have multiple FDM connectors")
        for c in fdm:
            self.assertEqual(c["process"], "fdm_fff")

    def test_discover_by_vendor(self):
        stratasys = self.registry.discover(vendor="stratasys")
        self.assertGreaterEqual(len(stratasys), 1)

    def test_discover_by_layer(self):
        l3 = self.registry.discover(layer=self.Layer.SITE_OPERATIONS)
        self.assertGreaterEqual(len(l3), 3)
        for c in l3:
            self.assertEqual(c["layer"], "L3")

    def test_connector_to_dict(self):
        key = list(self.registry._connectors.keys())[0]
        connector = self.registry.get_connector(key)
        d = connector.to_dict()
        self.assertIn("name", d)
        self.assertIn("vendor", d)
        self.assertIn("process", d)
        self.assertIn("protocol", d)
        self.assertIn("capabilities", d)
        self.assertIn("supported_materials", d)


class TestAMWorkflowBinder(unittest.TestCase):
    """Workflow orchestration tests."""

    def setUp(self):
        from src.additive_manufacturing_connectors import (
            AdditiveManufacturingRegistry,
            AMWorkflowBinder,
        )
        self.registry = AdditiveManufacturingRegistry()
        self.binder = AMWorkflowBinder(self.registry)

    def test_create_workflow(self):
        wf = self.binder.create_workflow("wf-1", "Test Print Job")
        self.assertEqual(wf["workflow_id"], "wf-1")
        self.assertEqual(wf["status"], "created")

    def test_add_step(self):
        self.binder.create_workflow("wf-2", "Step Test")
        key = list(self.registry._connectors.keys())[0]
        connector = self.registry.get_connector(key)
        action = connector.capabilities[0]
        result = self.binder.add_step("wf-2", "s1", key, action)
        self.assertTrue(result["success"])

    def test_execute_single_step_workflow(self):
        self.binder.create_workflow("wf-3", "Single Step")
        key = list(self.registry._connectors.keys())[0]
        connector = self.registry.get_connector(key)
        action = connector.capabilities[0]
        self.binder.add_step("wf-3", "s1", key, action)
        result = self.binder.execute_workflow("wf-3")
        self.assertTrue(result["success"])
        self.assertEqual(result["status"], "completed")

    def test_execute_multi_step_workflow_with_deps(self):
        self.binder.create_workflow("wf-4", "Multi Step")
        keys = list(self.registry._connectors.keys())
        c1 = self.registry.get_connector(keys[0])
        c2 = self.registry.get_connector(keys[1])
        self.binder.add_step("wf-4", "s1", keys[0], c1.capabilities[0])
        self.binder.add_step("wf-4", "s2", keys[1], c2.capabilities[0],
                             depends_on=["s1"])
        result = self.binder.execute_workflow("wf-4")
        self.assertTrue(result["success"])
        self.assertEqual(len(result["results"]), 2)

    def test_list_workflows(self):
        self.binder.create_workflow("wf-5", "List Test")
        wfs = self.binder.list_workflows()
        self.assertGreaterEqual(len(wfs), 1)
        self.assertEqual(wfs[0]["workflow_id"], "wf-5")

    def test_get_workflow(self):
        self.binder.create_workflow("wf-6", "Get Test")
        wf = self.binder.get_workflow("wf-6")
        self.assertIsNotNone(wf)
        self.assertEqual(wf["name"], "Get Test")

    def test_unknown_workflow_returns_error(self):
        result = self.binder.execute_workflow("nonexistent")
        self.assertFalse(result["success"])

    def test_step_with_bad_connector_fails(self):
        self.binder.create_workflow("wf-7", "Bad Connector")
        result = self.binder.add_step("wf-7", "s1", "fake_connector", "fake_action")
        self.assertFalse(result["success"])


class TestAMMaterialCoverage(unittest.TestCase):
    """Verify material class coverage across connectors."""

    def setUp(self):
        from src.additive_manufacturing_connectors import (
            AdditiveManufacturingRegistry,
            MaterialClass,
        )
        self.registry = AdditiveManufacturingRegistry()
        self.Material = MaterialClass

    def test_thermoplastic_support(self):
        connectors = self.registry.discover()
        has_thermo = any("thermoplastic" in c.get("supported_materials", [])
                         for c in connectors)
        self.assertTrue(has_thermo, "At least one connector should support thermoplastics")

    def test_metal_powder_support(self):
        connectors = self.registry.discover()
        has_metal = any("metal_powder" in c.get("supported_materials", [])
                        for c in connectors)
        self.assertTrue(has_metal, "At least one connector should support metal powder")

    def test_photopolymer_support(self):
        connectors = self.registry.discover()
        has_photo = any("photopolymer" in c.get("supported_materials", [])
                        for c in connectors)
        self.assertTrue(has_photo, "At least one connector should support photopolymers")


if __name__ == "__main__":
    unittest.main()
