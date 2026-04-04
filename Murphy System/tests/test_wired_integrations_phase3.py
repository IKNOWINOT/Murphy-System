"""
Tests for Wired Integrations Phase 3 — validates complete cross-layer parity:
new adapter templates for connector-only services, newly enabled webhook
capabilities, new webhook sources, and normalization rules.

Design Label: TEST-INT-WIRED-003
Owner: Platform Engineering / QA Team
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from universal_integration_adapter import (
    UniversalIntegrationAdapter,
    IntegrationCategory,
    IntegrationAuthMethod,
    ActionStatus,
)
from platform_connector_framework import (
    PlatformConnectorFramework,
    ConnectorCategory,
    ConnectorAction,
    ConnectorHealth,
)
from webhook_event_processor import (
    WebhookEventProcessor,
    WebhookStatus,
)


# ---------------------------------------------------------------------------
# Phase 3A — New Adapter Templates (7 connector-only services)
# ---------------------------------------------------------------------------

class TestAdapterPhase3Templates(unittest.TestCase):
    """Verify 7 new adapter templates for services that previously only had connectors."""

    def setUp(self):
        self.adapter = UniversalIntegrationAdapter()

    def _service_ids(self):
        return [s["service_id"] for s in self.adapter.list_services()]

    def test_signal_registered(self):
        self.assertIn("signal", self._service_ids())
        svc = self.adapter.get_service("signal")
        self.assertEqual(svc["category"], "communication")
        actions = [a["name"] for a in svc["actions"]]
        self.assertIn("send_message", actions)

    def test_google_business_messages_registered(self):
        self.assertIn("google_business_messages", self._service_ids())
        svc = self.adapter.get_service("google_business_messages")
        self.assertEqual(svc["category"], "communication")
        actions = [a["name"] for a in svc["actions"]]
        self.assertIn("send_message", actions)

    def test_kakaotalk_registered(self):
        self.assertIn("kakaotalk", self._service_ids())
        svc = self.adapter.get_service("kakaotalk")
        self.assertEqual(svc["category"], "communication")
        actions = [a["name"] for a in svc["actions"]]
        self.assertIn("send_message", actions)

    def test_line_registered(self):
        self.assertIn("line", self._service_ids())
        svc = self.adapter.get_service("line")
        self.assertEqual(svc["category"], "communication")
        actions = [a["name"] for a in svc["actions"]]
        self.assertIn("send_push", actions)
        self.assertIn("send_reply", actions)

    def test_snapchat_registered(self):
        self.assertIn("snapchat", self._service_ids())
        svc = self.adapter.get_service("snapchat")
        self.assertEqual(svc["category"], "social_media")
        actions = [a["name"] for a in svc["actions"]]
        self.assertIn("create_ad", actions)

    def test_wechat_registered(self):
        self.assertIn("wechat", self._service_ids())
        svc = self.adapter.get_service("wechat")
        self.assertEqual(svc["category"], "communication")
        actions = [a["name"] for a in svc["actions"]]
        self.assertIn("send_message", actions)

    def test_zenbusiness_registered(self):
        self.assertIn("zenbusiness", self._service_ids())
        svc = self.adapter.get_service("zenbusiness")
        actions = [a["name"] for a in svc["actions"]]
        self.assertIn("create_entity", actions)
        self.assertIn("check_compliance", actions)

    def test_adapter_service_count(self):
        """Total adapter services should now be at least 76."""
        services = self.adapter.list_services()
        self.assertGreaterEqual(len(services), 76)


# ---------------------------------------------------------------------------
# Phase 3B — Newly Enabled Webhook Capabilities (14 connectors)
# ---------------------------------------------------------------------------

class TestWebhookCapabilityEnabled(unittest.TestCase):
    """Verify webhook capability was added to 14 connectors."""

    def setUp(self):
        self.fw = PlatformConnectorFramework()

    def _connector(self, connector_id):
        return next(
            (c for c in self.fw.list_available_connectors() if c["connector_id"] == connector_id),
            None,
        )

    def test_asana_has_webhook(self):
        self.assertIn("webhook", self._connector("asana")["capabilities"])

    def test_notion_has_webhook(self):
        self.assertIn("webhook", self._connector("notion")["capabilities"])

    def test_monday_has_webhook(self):
        self.assertIn("webhook", self._connector("monday")["capabilities"])

    def test_jenkins_has_webhook(self):
        self.assertIn("webhook", self._connector("jenkins")["capabilities"])

    def test_freshdesk_has_webhook(self):
        self.assertIn("webhook", self._connector("freshdesk")["capabilities"])

    def test_newrelic_has_webhook(self):
        self.assertIn("webhook", self._connector("newrelic")["capabilities"])

    def test_woocommerce_has_webhook(self):
        self.assertIn("webhook", self._connector("woocommerce")["capabilities"])

    def test_confluence_has_webhook(self):
        self.assertIn("webhook", self._connector("confluence")["capabilities"])

    def test_firebase_has_webhook(self):
        self.assertIn("webhook", self._connector("firebase")["capabilities"])

    def test_linkedin_has_webhook(self):
        self.assertIn("webhook", self._connector("linkedin")["capabilities"])

    def test_mongodb_atlas_has_webhook(self):
        self.assertIn("webhook", self._connector("mongodb_atlas")["capabilities"])

    def test_quickbooks_has_webhook(self):
        self.assertIn("webhook", self._connector("quickbooks")["capabilities"])

    def test_google_workspace_has_webhook(self):
        self.assertIn("webhook", self._connector("google_workspace")["capabilities"])

    def test_ms_teams_has_webhook(self):
        self.assertIn("webhook", self._connector("ms_teams")["capabilities"])


# ---------------------------------------------------------------------------
# Phase 3C — New Webhook Sources (14 sources)
# ---------------------------------------------------------------------------

class TestPhase3WebhookSources(unittest.TestCase):
    """Verify 14 new webhook sources are registered."""

    def setUp(self):
        self.processor = WebhookEventProcessor()

    def _source_ids(self):
        return [s["source_id"] for s in self.processor.list_sources()]

    def test_asana_webhook_source(self):
        self.assertIn("asana_webhook", self._source_ids())

    def test_notion_webhook_source(self):
        self.assertIn("notion_webhook", self._source_ids())

    def test_monday_webhook_source(self):
        self.assertIn("monday_webhook", self._source_ids())

    def test_jenkins_webhook_source(self):
        self.assertIn("jenkins_webhook", self._source_ids())

    def test_freshdesk_webhook_source(self):
        self.assertIn("freshdesk_webhook", self._source_ids())

    def test_newrelic_webhook_source(self):
        self.assertIn("newrelic_webhook", self._source_ids())

    def test_woocommerce_webhook_source(self):
        self.assertIn("woocommerce_webhook", self._source_ids())

    def test_confluence_webhook_source(self):
        self.assertIn("confluence_webhook", self._source_ids())

    def test_firebase_webhook_source(self):
        self.assertIn("firebase_webhook", self._source_ids())

    def test_linkedin_webhook_source(self):
        self.assertIn("linkedin_webhook", self._source_ids())

    def test_mongodb_atlas_webhook_source(self):
        self.assertIn("mongodb_atlas_webhook", self._source_ids())

    def test_quickbooks_webhook_source(self):
        self.assertIn("quickbooks_webhook", self._source_ids())

    def test_google_workspace_webhook_source(self):
        self.assertIn("google_workspace_webhook", self._source_ids())

    def test_ms_teams_webhook_source(self):
        self.assertIn("ms_teams_webhook", self._source_ids())

    def test_webhook_source_count(self):
        """Total webhook sources should now be at least 61."""
        sources = self.processor.list_sources()
        self.assertGreaterEqual(len(sources), 61)


# ---------------------------------------------------------------------------
# Phase 3D — Normalization Rules for New Sources
# ---------------------------------------------------------------------------

class TestPhase3NormalizationRules(unittest.TestCase):
    """Verify normalization rules for the 14 new webhook sources."""

    def setUp(self):
        self.processor = WebhookEventProcessor()

    def test_asana_task_normalization(self):
        event = self.processor.process_webhook(
            source_id="asana_webhook",
            payload={
                "resource_type": "task",
                "resource": {"gid": "12345"},
                "action": "changed",
            },
        )
        self.assertEqual(event.status, WebhookStatus.PROCESSED)
        self.assertEqual(event.normalized_event_type, "task_updated")
        self.assertEqual(event.normalized_payload.get("task_id"), "12345")

    def test_notion_page_normalization(self):
        event = self.processor.process_webhook(
            source_id="notion_webhook",
            payload={
                "type": "page.updated",
                "data": {"id": "abc-123", "properties": {"title": "Test Page"}},
            },
        )
        self.assertEqual(event.status, WebhookStatus.PROCESSED)
        self.assertEqual(event.normalized_event_type, "page_updated")
        self.assertEqual(event.normalized_payload.get("page_id"), "abc-123")

    def test_monday_item_normalization(self):
        event = self.processor.process_webhook(
            source_id="monday_webhook",
            payload={
                "event": {"type": "create_pulse", "pulseId": 99, "pulseName": "New Task", "boardId": 42},
            },
        )
        self.assertEqual(event.normalized_event_type, "task_created")
        self.assertEqual(event.normalized_payload.get("item_id"), 99)

    def test_jenkins_build_normalization(self):
        event = self.processor.process_webhook(
            source_id="jenkins_webhook",
            payload={
                "build": {"phase": "COMPLETED", "full_url": "https://ci.example.com/job/test/1", "number": 42},
                "name": "test-job",
            },
        )
        self.assertEqual(event.normalized_event_type, "build_completed")
        self.assertEqual(event.normalized_payload.get("build_number"), 42)

    def test_freshdesk_ticket_normalization(self):
        event = self.processor.process_webhook(
            source_id="freshdesk_webhook",
            payload={
                "event": "ticket_created",
                "ticket_id": 5001,
                "subject": "Urgent issue",
                "priority": 1,
            },
        )
        self.assertEqual(event.normalized_event_type, "ticket_created")
        self.assertEqual(event.normalized_payload.get("title"), "Urgent issue")

    def test_newrelic_alert_normalization(self):
        event = self.processor.process_webhook(
            source_id="newrelic_webhook",
            payload={
                "event_type": "INCIDENT_OPEN",
                "incident_id": "INC-001",
                "policy_name": "HighCPU",
                "condition_name": "cpu > 90%",
            },
        )
        self.assertEqual(event.normalized_event_type, "alert_triggered")
        self.assertEqual(event.normalized_payload.get("alert_id"), "INC-001")

    def test_woocommerce_order_normalization(self):
        event = self.processor.process_webhook(
            source_id="woocommerce_webhook",
            payload={
                "action": "order.created",
                "id": 7890,
                "total": "49.99",
                "currency": "USD",
                "billing": {"email": "customer@example.com"},
            },
        )
        self.assertEqual(event.normalized_event_type, "order_created")
        self.assertEqual(event.normalized_payload.get("order_id"), 7890)

    def test_confluence_page_normalization(self):
        event = self.processor.process_webhook(
            source_id="confluence_webhook",
            payload={
                "eventType": "page_created",
                "page": {"id": "pg-001", "title": "Release Notes", "space": {"key": "ENG"}},
            },
        )
        self.assertEqual(event.normalized_event_type, "page_created")
        self.assertEqual(event.normalized_payload.get("title"), "Release Notes")

    def test_mongodb_alert_normalization(self):
        event = self.processor.process_webhook(
            source_id="mongodb_atlas_webhook",
            payload={
                "eventTypeName": "ALERT",
                "alertId": "alert-xyz",
                "clusterName": "prod-cluster",
                "metricName": "CONNECTIONS",
            },
        )
        self.assertEqual(event.normalized_event_type, "alert_triggered")
        self.assertEqual(event.normalized_payload.get("cluster"), "prod-cluster")

    def test_ms_teams_message_normalization(self):
        event = self.processor.process_webhook(
            source_id="ms_teams_webhook",
            payload={
                "type": "message",
                "from": {"id": "user-123"},
                "text": "Hello from Teams",
                "channelId": "general",
            },
        )
        self.assertEqual(event.status, WebhookStatus.PROCESSED)
        self.assertEqual(event.normalized_event_type, "chat_message")
        self.assertEqual(event.normalized_payload.get("content"), "Hello from Teams")


# ---------------------------------------------------------------------------
# Phase 3E — Full Cross-Layer Parity Validation
# ---------------------------------------------------------------------------

class TestFullCrossLayerParity(unittest.TestCase):
    """Verify every connector with webhook capability has a webhook source."""

    def setUp(self):
        self.adapter = UniversalIntegrationAdapter()
        self.fw = PlatformConnectorFramework()
        self.processor = WebhookEventProcessor()

    def test_zero_webhook_capable_connectors_without_sources(self):
        """CRITICAL: Every connector with webhook capability must have a webhook source."""
        connector_ids = [c["connector_id"] for c in self.fw.list_available_connectors()]
        source_ids = [s["source_id"] for s in self.processor.list_sources()]
        source_bases = [s.replace("_webhook", "") for s in source_ids]

        missing = []
        for c in self.fw.list_available_connectors():
            if "webhook" in c.get("capabilities", []):
                if c["connector_id"] not in source_bases:
                    missing.append(c["connector_id"])
        self.assertEqual(missing, [], f"Connectors with webhook capability but no source: {missing}")

    def test_adapter_connector_parity(self):
        """Every adapter service should have a connector counterpart (direct or aliased)."""
        known_aliases = {
            "amazon_web_services": "aws",
            "google_cloud_platform": "gcp",
            "microsoft_azure": "azure",
            "microsoft_teams": "ms_teams",
            "monday.com": "monday",
            "new_relic": "newrelic",
            "quickbooks_online": "quickbooks",
            "twitter/x": "twitter",
            "whatsapp_business": "whatsapp",
            "make_(integromat)": "make",
        }
        adapter_ids = set(s["service_id"] for s in self.adapter.list_services())
        connector_ids = set(c["connector_id"] for c in self.fw.list_available_connectors())

        unmatched = []
        for aid in adapter_ids:
            if aid not in connector_ids and known_aliases.get(aid) not in connector_ids:
                unmatched.append(aid)
        self.assertEqual(unmatched, [], f"Adapter services with no connector: {unmatched}")

    def test_connector_adapter_parity(self):
        """Every connector should have an adapter service counterpart (direct or aliased)."""
        known_aliases_rev = {
            "aws": "amazon_web_services",
            "gcp": "google_cloud_platform",
            "azure": "microsoft_azure",
            "ms_teams": "microsoft_teams",
            "monday": "monday.com",
            "newrelic": "new_relic",
            "quickbooks": "quickbooks_online",
            "twitter": "twitter/x",
            "whatsapp": "whatsapp_business",
            "make": "make_(integromat)",
        }
        adapter_ids = set(s["service_id"] for s in self.adapter.list_services())
        connector_ids = set(c["connector_id"] for c in self.fw.list_available_connectors())

        unmatched = []
        for cid in connector_ids:
            if cid not in adapter_ids and known_aliases_rev.get(cid) not in adapter_ids:
                unmatched.append(cid)
        self.assertEqual(unmatched, [], f"Connectors with no adapter service: {unmatched}")

    def test_layer_counts_match(self):
        """Adapter and connector layer should have the same number of integrations."""
        adapter_count = len(self.adapter.list_services())
        connector_count = len(self.fw.list_available_connectors())
        self.assertEqual(adapter_count, connector_count,
                         f"Adapter ({adapter_count}) vs Connector ({connector_count}) count mismatch")


# ---------------------------------------------------------------------------
# Phase 3F — Configure and Execute Pattern Validation
# ---------------------------------------------------------------------------

class TestPhase3ConfigureAndExecute(unittest.TestCase):
    """Verify new connectors can be configured and execute actions."""

    def setUp(self):
        self.fw = PlatformConnectorFramework()

    def test_configure_and_execute_notion(self):
        self.fw.configure_connector("notion", {"token": "ntn_test"})
        action = ConnectorAction(
            action_id="test-notion",
            connector_id="notion",
            action_type="search",
            resource="pages",
        )
        result = self.fw.execute_action(action)
        self.assertTrue(result.success)

    def test_configure_and_execute_asana(self):
        self.fw.configure_connector("asana", {"token": "asana_test"})
        action = ConnectorAction(
            action_id="test-asana",
            connector_id="asana",
            action_type="list_projects",
            resource="projects",
        )
        result = self.fw.execute_action(action)
        self.assertTrue(result.success)

    def test_configure_and_execute_monday(self):
        self.fw.configure_connector("monday", {"token": "monday_test"})
        action = ConnectorAction(
            action_id="test-monday",
            connector_id="monday",
            action_type="list_boards",
            resource="boards",
        )
        result = self.fw.execute_action(action)
        self.assertTrue(result.success)


# ---------------------------------------------------------------------------
# Phase 3G — Integration Metrics (Overall)
# ---------------------------------------------------------------------------

class TestOverallIntegrationMetrics(unittest.TestCase):
    """Verify final integration counts across all layers."""

    def test_adapter_count_at_least_76(self):
        adapter = UniversalIntegrationAdapter()
        self.assertGreaterEqual(len(adapter.list_services()), 76)

    def test_connector_count_at_least_76(self):
        fw = PlatformConnectorFramework()
        self.assertGreaterEqual(len(fw.list_available_connectors()), 76)

    def test_webhook_source_count_at_least_61(self):
        proc = WebhookEventProcessor()
        self.assertGreaterEqual(len(proc.list_sources()), 61)

    def test_webhook_capable_count_at_least_48(self):
        fw = PlatformConnectorFramework()
        webhook_capable = [c for c in fw.list_available_connectors() if "webhook" in c.get("capabilities", [])]
        self.assertGreaterEqual(len(webhook_capable), 48)


if __name__ == "__main__":
    unittest.main()
