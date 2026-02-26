"""
Tests for enterprise_integrations module.
"""

import sys
import os
import unittest
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from enterprise_integrations import (
    IntegrationCategory,
    AuthMethod,
    ConnectorStatus,
    EnterpriseConnector,
    EnterpriseIntegrationRegistry,
    IntegrationWorkflowBinder,
    AutomationCapabilityMapper,
    DEFAULT_ENTERPRISE_CONNECTORS,
)


class TestEnums(unittest.TestCase):
    def test_integration_category_values(self):
        self.assertEqual(IntegrationCategory.ACCOUNTING_FINANCE.value, "accounting_finance")
        self.assertEqual(IntegrationCategory.ENGINEERING_DESIGN.value, "engineering_design")
        self.assertEqual(IntegrationCategory.DEVOPS_INFRASTRUCTURE.value, "devops_infrastructure")

    def test_auth_method_values(self):
        self.assertEqual(AuthMethod.API_KEY.value, "api_key")
        self.assertEqual(AuthMethod.OAUTH.value, "oauth")
        self.assertEqual(AuthMethod.BASIC.value, "basic")
        self.assertEqual(AuthMethod.CERTIFICATE.value, "certificate")

    def test_connector_status_values(self):
        self.assertEqual(ConnectorStatus.HEALTHY.value, "healthy")
        self.assertEqual(ConnectorStatus.DISABLED.value, "disabled")


class TestEnterpriseConnector(unittest.TestCase):
    def _make(self, **overrides):
        defaults = {
            "name": "TestPlatform",
            "category": IntegrationCategory.DEVOPS_INFRASTRUCTURE,
            "platform_type": "test_platform",
            "auth_config": {"method": "api_key"},
            "rate_limit": {"requests_per_minute": 60, "burst_limit": 10},
            "capabilities": ["deploy", "rollback", "status"],
        }
        defaults.update(overrides)
        return EnterpriseConnector(**defaults)

    def test_create_connector(self):
        c = self._make()
        self.assertEqual(c.name, "TestPlatform")
        self.assertEqual(c.platform_type, "test_platform")

    def test_list_available_actions(self):
        c = self._make()
        self.assertIn("deploy", c.list_available_actions())
        self.assertEqual(len(c.list_available_actions()), 3)

    def test_execute_action_success(self):
        c = self._make()
        result = c.execute_action("deploy", {"version": "1.0"})
        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["action"], "deploy")
        self.assertIsNone(result["error"])

    def test_execute_unsupported_action(self):
        c = self._make()
        result = c.execute_action("nonexistent")
        self.assertFalse(result["success"])
        self.assertIn("Unsupported", result["error"])

    def test_execute_disabled_connector(self):
        c = self._make()
        c.disable()
        result = c.execute_action("deploy")
        self.assertFalse(result["success"])
        self.assertIn("disabled", result["error"])

    def test_health_check_unknown_initially(self):
        c = self._make()
        h = c.health_check()
        self.assertEqual(h["status"], "unknown")

    def test_health_check_healthy_after_success(self):
        c = self._make()
        c.execute_action("deploy")
        h = c.health_check()
        self.assertEqual(h["status"], "healthy")

    def test_health_check_disabled(self):
        c = self._make()
        c.disable()
        h = c.health_check()
        self.assertEqual(h["status"], "disabled")

    def test_enable_disable(self):
        c = self._make()
        self.assertTrue(c.is_enabled())
        c.disable()
        self.assertFalse(c.is_enabled())
        c.enable()
        self.assertTrue(c.is_enabled())

    def test_configure(self):
        c = self._make()
        result = c.configure({"api_key": "secret"})
        self.assertTrue(result["configured"])

    def test_to_dict(self):
        c = self._make()
        d = c.to_dict()
        self.assertEqual(d["name"], "TestPlatform")
        self.assertIn("capabilities", d)
        self.assertIn("rate_limit", d)

    def test_rate_limit_enforced(self):
        c = self._make(rate_limit={"requests_per_minute": 3, "burst_limit": 3})
        for _ in range(3):
            r = c.execute_action("deploy")
            self.assertTrue(r["success"])
        r = c.execute_action("deploy")
        self.assertFalse(r["success"])
        self.assertIn("Rate limit", r["error"])

    def test_metadata(self):
        c = self._make(metadata={"region": "us-east-1"})
        self.assertEqual(c.metadata["region"], "us-east-1")


class TestDefaultConnectors(unittest.TestCase):
    def test_defaults_loaded(self):
        self.assertGreater(len(DEFAULT_ENTERPRISE_CONNECTORS), 25)

    def test_all_categories_present(self):
        cats = {c.category for c in DEFAULT_ENTERPRISE_CONNECTORS}
        for cat in IntegrationCategory:
            self.assertIn(cat, cats)

    def test_quickbooks_capabilities(self):
        qb = next(c for c in DEFAULT_ENTERPRISE_CONNECTORS if c.platform_type == "quickbooks")
        self.assertIn("invoicing", qb.capabilities)
        self.assertIn("payroll_sync", qb.capabilities)

    def test_kubernetes_auth(self):
        k8s = next(c for c in DEFAULT_ENTERPRISE_CONNECTORS if c.platform_type == "kubernetes")
        self.assertEqual(k8s.auth_config["method"], "certificate")


class TestEnterpriseIntegrationRegistry(unittest.TestCase):
    def setUp(self):
        self.reg = EnterpriseIntegrationRegistry(load_defaults=True)

    def test_discover_all(self):
        all_c = self.reg.discover()
        self.assertGreater(len(all_c), 25)

    def test_discover_by_category(self):
        devops = self.reg.discover(IntegrationCategory.DEVOPS_INFRASTRUCTURE)
        self.assertTrue(all(c["category"] == "devops_infrastructure" for c in devops))
        self.assertGreaterEqual(len(devops), 4)

    def test_register_custom_connector(self):
        c = EnterpriseConnector(
            name="Custom",
            category=IntegrationCategory.ERP_BUSINESS,
            platform_type="custom_erp",
            auth_config={"method": "api_key"},
            rate_limit={"requests_per_minute": 10, "burst_limit": 2},
            capabilities=["sync"],
        )
        result = self.reg.register(c)
        self.assertTrue(result["registered"])
        self.assertIsNotNone(self.reg.get_connector("custom_erp"))

    def test_unregister(self):
        self.reg.unregister("quickbooks")
        self.assertIsNone(self.reg.get_connector("quickbooks"))

    def test_unregister_unknown(self):
        result = self.reg.unregister("nope")
        self.assertFalse(result["unregistered"])

    def test_execute_action(self):
        result = self.reg.execute("trello", "create_card", {"name": "task1"})
        self.assertTrue(result["success"])

    def test_execute_unknown_platform(self):
        result = self.reg.execute("nonexistent", "do_stuff")
        self.assertFalse(result["success"])

    def test_health_check(self):
        h = self.reg.health_check("terraform")
        self.assertIn("status", h)

    def test_health_check_unknown_platform(self):
        h = self.reg.health_check("nope")
        self.assertEqual(h["status"], "unknown")

    def test_health_check_all(self):
        results = self.reg.health_check_all()
        self.assertGreater(len(results), 25)

    def test_statistics(self):
        stats = self.reg.statistics()
        self.assertGreater(stats["total_connectors"], 0)
        self.assertIn("platforms", stats)

    def test_list_categories(self):
        cats = self.reg.list_categories()
        self.assertIn("accounting_finance", cats)

    def test_list_platforms(self):
        platforms = self.reg.list_platforms()
        self.assertIn("docker", platforms)

    def test_empty_registry(self):
        reg = EnterpriseIntegrationRegistry(load_defaults=False)
        self.assertEqual(len(reg.discover()), 0)


class TestIntegrationWorkflowBinder(unittest.TestCase):
    def setUp(self):
        self.reg = EnterpriseIntegrationRegistry(load_defaults=True)
        self.binder = IntegrationWorkflowBinder(self.reg)

    def test_create_workflow(self):
        wf = self.binder.create_workflow("wf1", "Test WF")
        self.assertEqual(wf["workflow_id"], "wf1")
        self.assertEqual(wf["status"], "created")

    def test_add_step(self):
        self.binder.create_workflow("wf1", "Test WF")
        result = self.binder.add_step("wf1", "s1", "docker", "manage_containers")
        self.assertTrue(result["success"])

    def test_add_step_unknown_workflow(self):
        result = self.binder.add_step("bad", "s1", "docker", "manage_containers")
        self.assertFalse(result["success"])

    def test_add_step_unknown_platform(self):
        self.binder.create_workflow("wf1", "Test WF")
        result = self.binder.add_step("wf1", "s1", "nonexistent", "do_stuff")
        self.assertFalse(result["success"])

    def test_add_step_bad_action(self):
        self.binder.create_workflow("wf1", "Test WF")
        result = self.binder.add_step("wf1", "s1", "docker", "fly_to_moon")
        self.assertFalse(result["success"])

    def test_execute_workflow(self):
        self.binder.create_workflow("wf1", "Deploy Pipeline")
        self.binder.add_step("wf1", "s1", "docker", "manage_images")
        self.binder.add_step("wf1", "s2", "kubernetes", "create_deployment", depends_on=["s1"])
        result = self.binder.execute_workflow("wf1")
        self.assertTrue(result["success"])
        self.assertEqual(len(result["results"]), 2)

    def test_execute_unknown_workflow(self):
        result = self.binder.execute_workflow("bad")
        self.assertFalse(result["success"])

    def test_list_workflows(self):
        self.binder.create_workflow("wf1", "A")
        self.binder.create_workflow("wf2", "B")
        wfs = self.binder.list_workflows()
        self.assertEqual(len(wfs), 2)

    def test_delete_workflow(self):
        self.binder.create_workflow("wf1", "A")
        result = self.binder.delete_workflow("wf1")
        self.assertTrue(result["deleted"])
        self.assertIsNone(self.binder.get_workflow("wf1"))

    def test_delete_unknown_workflow(self):
        result = self.binder.delete_workflow("nope")
        self.assertFalse(result["deleted"])

    def test_get_workflow(self):
        self.binder.create_workflow("wf1", "A")
        wf = self.binder.get_workflow("wf1")
        self.assertEqual(wf["name"], "A")


class TestAutomationCapabilityMapper(unittest.TestCase):
    def setUp(self):
        self.reg = EnterpriseIntegrationRegistry(load_defaults=True)
        self.mapper = AutomationCapabilityMapper(self.reg)

    def test_map_exact_match(self):
        results = self.mapper.map_action("invoicing")
        self.assertGreater(len(results), 0)
        self.assertTrue(any(r["match_score"] == 1.0 for r in results))

    def test_map_partial_match(self):
        results = self.mapper.map_action("deploy")
        self.assertGreater(len(results), 0)

    def test_map_no_match(self):
        results = self.mapper.map_action("xyzzy_magic_12345")
        self.assertEqual(len(results), 0)

    def test_register_custom_mapping(self):
        result = self.mapper.register_mapping("bill_client", "quickbooks", "create_invoice")
        self.assertTrue(result["registered"])
        matches = self.mapper.map_action("bill_client")
        self.assertTrue(any(m["source"] == "custom" for m in matches))

    def test_unregister_mapping(self):
        self.mapper.register_mapping("bill_client", "quickbooks", "create_invoice")
        result = self.mapper.unregister_mapping("bill_client", "quickbooks", "create_invoice")
        self.assertTrue(result["unregistered"])

    def test_unregister_missing_mapping(self):
        result = self.mapper.unregister_mapping("nope", "nope", "nope")
        self.assertFalse(result["unregistered"])

    def test_list_mappings(self):
        self.mapper.register_mapping("a", "quickbooks", "invoicing")
        mappings = self.mapper.list_mappings()
        self.assertIn("a", mappings)

    def test_suggest_workflow(self):
        suggestion = self.mapper.suggest_workflow("invoicing", "create_deployment")
        self.assertEqual(len(suggestion["steps"]), 2)
        self.assertGreater(suggestion["coverage"], 0)

    def test_suggest_workflow_no_match(self):
        suggestion = self.mapper.suggest_workflow("xyzzy_impossible")
        self.assertEqual(suggestion["coverage"], 0)


class TestThreadSafety(unittest.TestCase):
    def test_concurrent_execute(self):
        reg = EnterpriseIntegrationRegistry(load_defaults=True)
        errors = []

        def worker():
            try:
                for _ in range(20):
                    reg.execute("docker", "manage_containers")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(len(errors), 0)

    def test_concurrent_register(self):
        reg = EnterpriseIntegrationRegistry(load_defaults=False)
        errors = []

        def worker(idx):
            try:
                c = EnterpriseConnector(
                    name=f"C{idx}",
                    category=IntegrationCategory.DATA_ANALYTICS,
                    platform_type=f"plat_{idx}",
                    auth_config={"method": "api_key"},
                    rate_limit={"requests_per_minute": 100, "burst_limit": 10},
                    capabilities=["query"],
                )
                reg.register(c)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(len(errors), 0)
        self.assertEqual(len(reg.discover()), 10)


if __name__ == "__main__":
    unittest.main()
