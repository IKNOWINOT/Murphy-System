"""
Integration tests for messaging platform connectors — Snapchat, Telegram,
WhatsApp, Signal, WeChat, LINE, KakaoTalk, Google Business Messages,
and ZenBusiness.

Validates platform_connector_framework, enterprise_integrations, and
MODULE_CATALOG wiring for new messaging/business platform connectors.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


# ===================================================================
# Platform Connector Framework tests — new messaging connectors
# ===================================================================

class TestPlatformFrameworkMessagingConnectors(unittest.TestCase):
    """Test messaging connectors in PlatformConnectorFramework."""

    def setUp(self):
        try:
            from platform_connector_framework import (
                PlatformConnectorFramework, ConnectorAction, ConnectorCategory,
            )
            self.fw = PlatformConnectorFramework()
            self.ConnectorAction = ConnectorAction
            self.ConnectorCategory = ConnectorCategory
        except ImportError as exc:
            self.skipTest(f"Platform connector framework not available: {exc}")

    def _find_connector(self, connector_id):
        connectors = self.fw.list_available_connectors()
        for c in connectors:
            if c["connector_id"] == connector_id:
                return c
        return None

    def test_whatsapp_registered(self):
        c = self._find_connector("whatsapp")
        self.assertIsNotNone(c, "WhatsApp connector not found")
        self.assertEqual(c["name"], "WhatsApp Business")
        self.assertIn("send_message", c["capabilities"])
        self.assertIn("send_template", c["capabilities"])

    def test_telegram_registered(self):
        c = self._find_connector("telegram")
        self.assertIsNotNone(c, "Telegram connector not found")
        self.assertEqual(c["name"], "Telegram")
        self.assertIn("send_message", c["capabilities"])
        self.assertIn("bot_commands", c["capabilities"])

    def test_signal_registered(self):
        c = self._find_connector("signal")
        self.assertIsNotNone(c, "Signal connector not found")
        self.assertEqual(c["name"], "Signal")
        self.assertIn("send_message", c["capabilities"])
        self.assertIn("sealed_sender", c["capabilities"])

    def test_snapchat_registered(self):
        c = self._find_connector("snapchat")
        self.assertIsNotNone(c, "Snapchat connector not found")
        self.assertEqual(c["name"], "Snapchat")
        self.assertIn("send_snap", c["capabilities"])
        self.assertIn("manage_stories", c["capabilities"])

    def test_wechat_registered(self):
        c = self._find_connector("wechat")
        self.assertIsNotNone(c, "WeChat connector not found")
        self.assertEqual(c["name"], "WeChat")
        self.assertIn("send_message", c["capabilities"])
        self.assertIn("mini_programs", c["capabilities"])
        self.assertIn("wechat_pay", c["capabilities"])

    def test_line_registered(self):
        c = self._find_connector("line")
        self.assertIsNotNone(c, "LINE connector not found")
        self.assertEqual(c["name"], "LINE")
        self.assertIn("send_message", c["capabilities"])
        self.assertIn("flex_messages", c["capabilities"])
        self.assertIn("line_pay", c["capabilities"])

    def test_kakaotalk_registered(self):
        c = self._find_connector("kakaotalk")
        self.assertIsNotNone(c, "KakaoTalk connector not found")
        self.assertEqual(c["name"], "KakaoTalk")
        self.assertIn("send_message", c["capabilities"])
        self.assertIn("kakao_pay", c["capabilities"])

    def test_google_business_messages_registered(self):
        c = self._find_connector("google_business_messages")
        self.assertIsNotNone(c, "Google Business Messages connector not found")
        self.assertEqual(c["name"], "Google Business Messages")
        self.assertIn("send_message", c["capabilities"])
        self.assertIn("rich_cards", c["capabilities"])

    def test_zenbusiness_registered(self):
        c = self._find_connector("zenbusiness")
        self.assertIsNotNone(c, "ZenBusiness connector not found")
        self.assertEqual(c["name"], "ZenBusiness")
        self.assertIn("business_formation", c["capabilities"])
        self.assertIn("compliance_alerts", c["capabilities"])

    def test_total_connector_count(self):
        connectors = self.fw.list_available_connectors()
        # Previously 20, now 29 (added 9)
        self.assertGreaterEqual(len(connectors), 29)

    def test_communication_category_count(self):
        comm = self.fw.list_by_category(self.ConnectorCategory.COMMUNICATION)
        # Previously 3 (Slack, Teams, Discord), now 11 (+8 messaging)
        self.assertGreaterEqual(len(comm), 11)


class TestMessagingConnectorExecution(unittest.TestCase):
    """Test execution of messaging connector actions."""

    def setUp(self):
        try:
            from platform_connector_framework import (
                PlatformConnectorFramework, ConnectorAction,
            )
            self.fw = PlatformConnectorFramework()
            self.ConnectorAction = ConnectorAction
        except ImportError as exc:
            self.skipTest(f"Platform connector framework not available: {exc}")

    def _execute(self, connector_id, action_type, resource, payload=None):
        self.fw.configure_connector(connector_id, {"token": "test_token"})
        action = self.ConnectorAction(
            action_id=f"test_{connector_id}",
            connector_id=connector_id,
            action_type=action_type,
            resource=resource,
            payload=payload or {},
        )
        return self.fw.execute_action(action)

    def test_whatsapp_execute(self):
        result = self._execute("whatsapp", "send_message", "messages",
                               {"to": "+1234567890", "text": "hello"})
        self.assertTrue(result.success)
        self.assertEqual(result.connector_id, "whatsapp")

    def test_telegram_execute(self):
        result = self._execute("telegram", "send_message", "messages",
                               {"chat_id": "123", "text": "hello"})
        self.assertTrue(result.success)

    def test_signal_execute(self):
        result = self._execute("signal", "send_message", "messages",
                               {"recipient": "+1234567890"})
        self.assertTrue(result.success)

    def test_snapchat_execute(self):
        result = self._execute("snapchat", "send_snap", "snaps",
                               {"media_type": "image"})
        self.assertTrue(result.success)

    def test_wechat_execute(self):
        result = self._execute("wechat", "send_message", "messages",
                               {"openid": "test", "text": "hello"})
        self.assertTrue(result.success)

    def test_line_execute(self):
        result = self._execute("line", "send_message", "messages",
                               {"to": "user_id", "text": "hello"})
        self.assertTrue(result.success)

    def test_kakaotalk_execute(self):
        result = self._execute("kakaotalk", "send_message", "messages",
                               {"receiver_uuids": ["test"]})
        self.assertTrue(result.success)

    def test_google_business_messages_execute(self):
        result = self._execute("google_business_messages", "send_message",
                               "messages", {"text": "hello"})
        self.assertTrue(result.success)

    def test_zenbusiness_execute(self):
        result = self._execute("zenbusiness", "business_formation",
                               "formations", {"state": "CA"})
        self.assertTrue(result.success)


# ===================================================================
# Enterprise Integrations tests — new messaging/business connectors
# ===================================================================

class TestEnterpriseIntegrationsMessaging(unittest.TestCase):
    """Test messaging connectors in EnterpriseIntegrationRegistry."""

    def setUp(self):
        try:
            from enterprise_integrations import EnterpriseIntegrationRegistry
            self.registry = EnterpriseIntegrationRegistry()
        except ImportError as exc:
            self.skipTest(f"Enterprise integrations not available: {exc}")

    def _has_platform(self, platform_type):
        return platform_type in self.registry.list_platforms()

    def _get_connector_dict(self, platform_type):
        """Get connector as dict via discover()."""
        results = self.registry.discover()
        for r in results:
            if r.get("platform_type") == platform_type:
                return r
        return None

    def test_whatsapp_in_enterprise(self):
        self.assertTrue(self._has_platform("whatsapp"),
                        "WhatsApp not in enterprise registry")

    def test_telegram_in_enterprise(self):
        self.assertTrue(self._has_platform("telegram"),
                        "Telegram not in enterprise registry")

    def test_signal_in_enterprise(self):
        self.assertTrue(self._has_platform("signal"),
                        "Signal not in enterprise registry")

    def test_snapchat_in_enterprise(self):
        self.assertTrue(self._has_platform("snapchat"),
                        "Snapchat not in enterprise registry")

    def test_wechat_in_enterprise(self):
        self.assertTrue(self._has_platform("wechat"),
                        "WeChat not in enterprise registry")

    def test_line_in_enterprise(self):
        self.assertTrue(self._has_platform("line"),
                        "LINE not in enterprise registry")

    def test_kakaotalk_in_enterprise(self):
        self.assertTrue(self._has_platform("kakaotalk"),
                        "KakaoTalk not in enterprise registry")

    def test_google_business_messages_in_enterprise(self):
        self.assertTrue(self._has_platform("google_business_messages"),
                        "Google Business Messages not in enterprise registry")

    def test_zenbusiness_in_enterprise(self):
        self.assertTrue(self._has_platform("zenbusiness"),
                        "ZenBusiness not in enterprise registry")

    def test_total_enterprise_connectors(self):
        platforms = self.registry.list_platforms()
        # Previously 45, now 55 (added 10)
        self.assertGreaterEqual(len(platforms), 54)

    def test_communication_connectors_count(self):
        results = self.registry.discover()
        comm_count = sum(
            1 for r in results
            if r.get("category") == "communication"
        )
        # Previously 3 (Zoom, Twilio, Webex), now 11 (+8 messaging)
        self.assertGreaterEqual(comm_count, 11)


if __name__ == '__main__':
    unittest.main()
