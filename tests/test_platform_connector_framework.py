"""Tests for PlatformConnectorFramework."""

import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from platform_connector_framework import (
    PlatformConnectorFramework,
    ConnectorDefinition,
    ConnectorCategory,
    AuthType,
    ConnectorHealth,
    ConnectorAction,
    RateLimitConfig,
)


class TestPlatformConnectorFramework(unittest.TestCase):

    def setUp(self):
        self.fw = PlatformConnectorFramework()

    def test_default_platforms_registered(self):
        connectors = self.fw.list_available_connectors()
        self.assertGreater(len(connectors), 15)
        ids = [c["connector_id"] for c in connectors]
        for p in ["slack", "jira", "salesforce", "github", "aws", "stripe"]:
            self.assertIn(p, ids)

    def test_list_by_category(self):
        comm = self.fw.list_by_category(ConnectorCategory.COMMUNICATION)
        self.assertGreater(len(comm), 0)
        for c in comm:
            self.assertEqual(c["category"], "communication")

    def test_configure_connector(self):
        result = self.fw.configure_connector("slack", {"bot_token": "xoxb-test"})
        self.assertTrue(result)
        instance = self.fw.get_connector("slack")
        self.assertIsNotNone(instance)
        self.assertTrue(instance.enabled)

    def test_configure_unknown_connector(self):
        result = self.fw.configure_connector("nonexistent", {})
        self.assertFalse(result)

    def test_list_configured(self):
        self.fw.configure_connector("slack", {"token": "test"})
        self.fw.configure_connector("github", {"token": "test"})
        configured = self.fw.list_configured()
        self.assertEqual(len(configured), 2)

    def test_execute_action_success(self):
        self.fw.configure_connector("slack", {"token": "test"})
        action = ConnectorAction(
            action_id="act1",
            connector_id="slack",
            action_type="send_message",
            resource="channel",
            payload={"text": "hello"},
        )
        result = self.fw.execute_action(action)
        self.assertTrue(result.success)
        self.assertIsNotNone(result.data)

    def test_execute_action_not_configured(self):
        action = ConnectorAction(
            action_id="act2",
            connector_id="slack",
            action_type="send_message",
            resource="channel",
        )
        result = self.fw.execute_action(action)
        self.assertFalse(result.success)
        self.assertIn("not configured", result.error)

    def test_execute_action_disabled(self):
        self.fw.configure_connector("slack", {"token": "test"})
        self.fw.disable_connector("slack")
        action = ConnectorAction(
            action_id="act3",
            connector_id="slack",
            action_type="send_message",
            resource="channel",
        )
        result = self.fw.execute_action(action)
        self.assertFalse(result.success)
        self.assertIn("disabled", result.error)

    def test_rate_limit(self):
        defn = ConnectorDefinition(
            connector_id="test_rl",
            name="Rate Limited",
            category=ConnectorCategory.CUSTOM,
            platform="test",
            auth_type=AuthType.NONE,
            rate_limit=RateLimitConfig(max_requests=2, window_seconds=60),
        )
        self.fw.register_connector(defn)
        self.fw.configure_connector("test_rl", {})
        for i in range(2):
            action = ConnectorAction(action_id=f"rl{i}", connector_id="test_rl", action_type="read", resource="test")
            result = self.fw.execute_action(action)
            self.assertTrue(result.success)
        action = ConnectorAction(action_id="rl_blocked", connector_id="test_rl", action_type="read", resource="test")
        result = self.fw.execute_action(action)
        self.assertFalse(result.success)
        self.assertIn("Rate limit", result.error)

    def test_health_check_unknown(self):
        health = self.fw.health_check("nonexistent")
        self.assertEqual(health, ConnectorHealth.UNKNOWN)

    def test_health_check_healthy(self):
        self.fw.configure_connector("slack", {"token": "test"})
        inst = self.fw.get_connector("slack")
        inst.request_count = 100
        inst.error_count = 1
        health = self.fw.health_check("slack")
        self.assertEqual(health, ConnectorHealth.HEALTHY)

    def test_health_check_degraded(self):
        self.fw.configure_connector("slack", {"token": "test"})
        inst = self.fw.get_connector("slack")
        inst.request_count = 100
        inst.error_count = 15
        health = self.fw.health_check("slack")
        self.assertEqual(health, ConnectorHealth.DEGRADED)

    def test_health_check_unhealthy(self):
        self.fw.configure_connector("slack", {"token": "test"})
        inst = self.fw.get_connector("slack")
        inst.request_count = 100
        inst.error_count = 60
        health = self.fw.health_check("slack")
        self.assertEqual(health, ConnectorHealth.UNHEALTHY)

    def test_disable_enable_connector(self):
        self.fw.configure_connector("slack", {"token": "test"})
        self.assertTrue(self.fw.disable_connector("slack"))
        self.assertEqual(self.fw.get_connector("slack").health, ConnectorHealth.DISABLED)
        self.assertTrue(self.fw.enable_connector("slack"))
        self.assertTrue(self.fw.get_connector("slack").enabled)

    def test_action_history(self):
        self.fw.configure_connector("slack", {"token": "test"})
        action = ConnectorAction(action_id="hist1", connector_id="slack", action_type="read", resource="test")
        self.fw.execute_action(action)
        history = self.fw.get_action_history("slack")
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["action_id"], "hist1")

    def test_register_custom_connector(self):
        defn = ConnectorDefinition(
            connector_id="custom1",
            name="My Custom",
            category=ConnectorCategory.CUSTOM,
            platform="custom",
            auth_type=AuthType.API_KEY,
            capabilities=["custom_action"],
        )
        self.assertTrue(self.fw.register_connector(defn))
        connectors = self.fw.list_available_connectors()
        ids = [c["connector_id"] for c in connectors]
        self.assertIn("custom1", ids)

    def test_statistics(self):
        stats = self.fw.get_statistics()
        self.assertGreater(stats["total_definitions"], 15)
        self.assertIn("categories", stats)
        self.assertIn("platforms", stats)

    def test_status(self):
        status = self.fw.status()
        self.assertEqual(status["module"], "platform_connector_framework")
        self.assertIn("statistics", status)

    def test_crm_connectors_available(self):
        crm = self.fw.list_by_category(ConnectorCategory.CRM)
        self.assertGreater(len(crm), 0)
        platforms = [c["connector_id"] for c in crm]
        self.assertIn("salesforce", platforms)
        self.assertIn("hubspot", platforms)

    def test_devops_connectors_available(self):
        devops = self.fw.list_by_category(ConnectorCategory.DEVOPS)
        self.assertGreater(len(devops), 0)
        platforms = [c["connector_id"] for c in devops]
        self.assertIn("github", platforms)

    def test_cloud_connectors_available(self):
        cloud = self.fw.list_by_category(ConnectorCategory.CLOUD)
        self.assertGreater(len(cloud), 0)
        platforms = [c["connector_id"] for c in cloud]
        self.assertIn("aws", platforms)
        self.assertIn("azure", platforms)
        self.assertIn("gcp", platforms)

    def test_generic_action_type(self):
        self.fw.configure_connector("slack", {"token": "test"})
        action = ConnectorAction(action_id="gen1", connector_id="slack", action_type="read", resource="test")
        result = self.fw.execute_action(action)
        self.assertTrue(result.success)

    def test_unsupported_action_type(self):
        self.fw.configure_connector("slack", {"token": "test"})
        action = ConnectorAction(action_id="bad1", connector_id="slack", action_type="destroy_everything", resource="test")
        result = self.fw.execute_action(action)
        self.assertFalse(result.success)
        self.assertIn("not supported", result.error)

    def test_all_default_categories_present(self):
        connectors = self.fw.list_available_connectors()
        categories = set(c["category"] for c in connectors)
        for expected in ["communication", "crm", "devops", "cloud", "payment", "knowledge", "itsm"]:
            self.assertIn(expected, categories)

    def test_connector_capabilities_populated(self):
        connectors = self.fw.list_available_connectors()
        for c in connectors:
            self.assertIsInstance(c["capabilities"], list)
            self.assertGreater(len(c["capabilities"]), 0)


if __name__ == "__main__":
    unittest.main()
