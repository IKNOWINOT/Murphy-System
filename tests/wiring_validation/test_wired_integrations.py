"""
Tests for Wired Integrations — validates new direct API integrations
added across universal_integration_adapter (INT-002),
platform_connector_framework, and webhook_event_processor modules.

Design Label: TEST-INT-WIRED-001
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
)
from webhook_event_processor import (
    WebhookEventProcessor,
    WebhookStatus,
)


# ---------------------------------------------------------------------------
# INT-002 — UniversalIntegrationAdapter: New Wired Integrations
# ---------------------------------------------------------------------------

class TestUniversalAdapterWiredIntegrations(unittest.TestCase):
    """Verify new wired integration templates are registered in INT-002."""

    def setUp(self):
        self.adapter = UniversalIntegrationAdapter()

    def _service_ids(self):
        return [s["service_id"] for s in self.adapter.list_services()]

    # -- CRM --

    def test_salesforce_registered(self):
        self.assertIn("salesforce", self._service_ids())
        svc = self.adapter.get_service("salesforce")
        self.assertEqual(svc["category"], "crm")
        self.assertIn("query", [a["name"] for a in svc["actions"]])
        self.assertIn("create_record", [a["name"] for a in svc["actions"]])

    def test_hubspot_registered(self):
        self.assertIn("hubspot", self._service_ids())
        svc = self.adapter.get_service("hubspot")
        self.assertEqual(svc["category"], "crm")
        self.assertIn("create_contact", [a["name"] for a in svc["actions"]])

    # -- Payment --

    def test_stripe_registered(self):
        self.assertIn("stripe", self._service_ids())
        svc = self.adapter.get_service("stripe")
        self.assertEqual(svc["category"], "payment")
        self.assertIn("create_charge", [a["name"] for a in svc["actions"]])

    def test_paypal_registered(self):
        self.assertIn("paypal", self._service_ids())
        svc = self.adapter.get_service("paypal")
        self.assertEqual(svc["category"], "payment")
        self.assertIn("create_order", [a["name"] for a in svc["actions"]])

    # -- E-commerce --

    def test_shopify_registered(self):
        self.assertIn("shopify", self._service_ids())
        svc = self.adapter.get_service("shopify")
        actions = [a["name"] for a in svc["actions"]]
        self.assertIn("list_products", actions)
        self.assertIn("list_orders", actions)

    def test_woocommerce_registered(self):
        self.assertIn("woocommerce", self._service_ids())

    # -- Customer Support --

    def test_zendesk_registered(self):
        self.assertIn("zendesk", self._service_ids())
        svc = self.adapter.get_service("zendesk")
        self.assertIn("create_ticket", [a["name"] for a in svc["actions"]])

    def test_intercom_registered(self):
        self.assertIn("intercom", self._service_ids())

    def test_freshdesk_registered(self):
        self.assertIn("freshdesk", self._service_ids())

    # -- Observability & Monitoring --

    def test_datadog_registered(self):
        self.assertIn("datadog", self._service_ids())
        svc = self.adapter.get_service("datadog")
        self.assertEqual(svc["category"], "monitoring")
        self.assertIn("send_metrics", [a["name"] for a in svc["actions"]])

    def test_pagerduty_registered(self):
        self.assertIn("pagerduty", self._service_ids())
        svc = self.adapter.get_service("pagerduty")
        self.assertEqual(svc["category"], "monitoring")

    def test_sentry_registered(self):
        self.assertIn("sentry", self._service_ids())

    def test_new_relic_registered(self):
        self.assertIn("newrelic", self._service_ids())

    # -- CI/CD --

    def test_circleci_registered(self):
        self.assertIn("circleci", self._service_ids())
        svc = self.adapter.get_service("circleci")
        self.assertEqual(svc["category"], "developer_tools")

    def test_jenkins_registered(self):
        self.assertIn("jenkins", self._service_ids())

    # -- Communication --

    def test_twilio_registered(self):
        self.assertIn("twilio", self._service_ids())
        svc = self.adapter.get_service("twilio")
        self.assertEqual(svc["category"], "communication")
        self.assertIn("send_sms", [a["name"] for a in svc["actions"]])

    def test_sendgrid_registered(self):
        self.assertIn("sendgrid", self._service_ids())
        svc = self.adapter.get_service("sendgrid")
        self.assertEqual(svc["category"], "email")

    # -- Document & Signature --

    def test_docusign_registered(self):
        self.assertIn("docusign", self._service_ids())

    def test_dropbox_registered(self):
        self.assertIn("dropbox", self._service_ids())
        svc = self.adapter.get_service("dropbox")
        self.assertEqual(svc["category"], "storage")

    def test_google_drive_registered(self):
        self.assertIn("google_drive", self._service_ids())

    # -- Calendar --

    def test_calendly_registered(self):
        self.assertIn("calendly", self._service_ids())

    def test_google_calendar_registered(self):
        self.assertIn("google_calendar", self._service_ids())

    # -- Accounting --

    def test_quickbooks_online_registered(self):
        self.assertIn("quickbooks", self._service_ids())

    # -- Action execution (unconfigured returns auth error) --

    def test_execute_action_requires_auth(self):
        result = self.adapter.execute("salesforce", "query", {"q": "SELECT Id FROM Account"})
        self.assertEqual(result.status, ActionStatus.AUTH_ERROR)

    def test_execute_action_configured_succeeds(self):
        self.adapter.configure("shopify", {"access_token": "test-token"})
        result = self.adapter.execute("shopify", "list_products")
        self.assertEqual(result.status, ActionStatus.SUCCESS)

    def test_total_services_count(self):
        services = self.adapter.list_services()
        self.assertGreaterEqual(len(services), 55)

    def test_categories_include_new_types(self):
        categories = self.adapter.list_categories()
        for cat in ["crm", "payment", "monitoring", "developer_tools", "storage"]:
            self.assertIn(cat, categories)


# ---------------------------------------------------------------------------
# PlatformConnectorFramework: New Wired Connectors
# ---------------------------------------------------------------------------

class TestPlatformConnectorWiredIntegrations(unittest.TestCase):
    """Verify new wired connectors are registered in the platform framework."""

    def setUp(self):
        self.fw = PlatformConnectorFramework()

    def _connector_ids(self):
        return [c["connector_id"] for c in self.fw.list_available_connectors()]

    # -- Automation platforms (beyond Zapier) --

    def test_n8n_registered(self):
        self.assertIn("n8n", self._connector_ids())

    def test_make_registered(self):
        self.assertIn("make", self._connector_ids())

    def test_ifttt_registered(self):
        self.assertIn("ifttt", self._connector_ids())

    # -- E-commerce --

    def test_shopify_connector(self):
        self.assertIn("shopify", self._connector_ids())
        connectors = self.fw.list_available_connectors()
        shopify = next(c for c in connectors if c["connector_id"] == "shopify")
        self.assertIn("list_products", shopify["capabilities"])
        self.assertIn("webhook", shopify["capabilities"])

    def test_woocommerce_connector(self):
        self.assertIn("woocommerce", self._connector_ids())

    # -- Customer Support --

    def test_zendesk_connector(self):
        self.assertIn("zendesk", self._connector_ids())

    def test_intercom_connector(self):
        self.assertIn("intercom", self._connector_ids())

    def test_freshdesk_connector(self):
        self.assertIn("freshdesk", self._connector_ids())

    # -- Observability --

    def test_datadog_connector(self):
        self.assertIn("datadog", self._connector_ids())

    def test_pagerduty_connector(self):
        self.assertIn("pagerduty", self._connector_ids())

    def test_sentry_connector(self):
        self.assertIn("sentry", self._connector_ids())

    def test_newrelic_connector(self):
        self.assertIn("newrelic", self._connector_ids())

    # -- CI/CD --

    def test_circleci_connector(self):
        self.assertIn("circleci", self._connector_ids())

    def test_jenkins_connector(self):
        self.assertIn("jenkins", self._connector_ids())

    # -- Communication --

    def test_twilio_connector(self):
        self.assertIn("twilio", self._connector_ids())

    def test_sendgrid_connector(self):
        self.assertIn("sendgrid", self._connector_ids())

    # -- Payment --

    def test_paypal_connector(self):
        self.assertIn("paypal", self._connector_ids())

    # -- Document / Storage --

    def test_docusign_connector(self):
        self.assertIn("docusign", self._connector_ids())

    def test_dropbox_connector(self):
        self.assertIn("dropbox", self._connector_ids())

    # -- Calendar --

    def test_calendly_connector(self):
        self.assertIn("calendly", self._connector_ids())

    # -- Accounting --

    def test_quickbooks_connector(self):
        self.assertIn("quickbooks", self._connector_ids())

    # -- Configure and execute --

    def test_configure_and_execute_shopify(self):
        self.fw.configure_connector("shopify", {"access_token": "test"})
        action = ConnectorAction(
            action_id="test-1",
            connector_id="shopify",
            action_type="list_products",
            resource="products",
        )
        result = self.fw.execute_action(action)
        self.assertTrue(result.success)

    def test_configure_and_execute_datadog(self):
        self.fw.configure_connector("datadog", {"api_key": "test", "app_key": "test"})
        action = ConnectorAction(
            action_id="test-2",
            connector_id="datadog",
            action_type="send_metrics",
            resource="metrics",
        )
        result = self.fw.execute_action(action)
        self.assertTrue(result.success)

    def test_total_connector_count(self):
        connectors = self.fw.list_available_connectors()
        self.assertGreaterEqual(len(connectors), 50)


# ---------------------------------------------------------------------------
# WebhookEventProcessor: New Wired Webhook Sources & Normalization
# ---------------------------------------------------------------------------

class TestWebhookProcessorWiredIntegrations(unittest.TestCase):
    """Verify new webhook sources and normalization rules for wired integrations."""

    def setUp(self):
        self.processor = WebhookEventProcessor()

    def _source_ids(self):
        return [s["source_id"] for s in self.processor.list_sources()]

    # -- New webhook sources --

    def test_discord_webhook_registered(self):
        self.assertIn("discord_webhook", self._source_ids())

    def test_shopify_webhook_registered(self):
        self.assertIn("shopify_webhook", self._source_ids())

    def test_twilio_webhook_registered(self):
        self.assertIn("twilio_webhook", self._source_ids())

    def test_pagerduty_webhook_registered(self):
        self.assertIn("pagerduty_webhook", self._source_ids())

    def test_datadog_webhook_registered(self):
        self.assertIn("datadog_webhook", self._source_ids())

    def test_zendesk_webhook_registered(self):
        self.assertIn("zendesk_webhook", self._source_ids())

    def test_zapier_webhook_registered(self):
        self.assertIn("zapier_webhook", self._source_ids())

    def test_n8n_webhook_registered(self):
        self.assertIn("n8n_webhook", self._source_ids())

    def test_sendgrid_webhook_registered(self):
        self.assertIn("sendgrid_webhook", self._source_ids())

    def test_paypal_webhook_registered(self):
        self.assertIn("paypal_webhook", self._source_ids())

    def test_intercom_webhook_registered(self):
        self.assertIn("intercom_webhook", self._source_ids())

    def test_calendly_webhook_registered(self):
        self.assertIn("calendly_webhook", self._source_ids())

    def test_sentry_webhook_registered(self):
        self.assertIn("sentry_webhook", self._source_ids())

    def test_total_webhook_sources(self):
        sources = self.processor.list_sources()
        self.assertGreaterEqual(len(sources), 23)

    # -- Normalization: Discord --

    def test_discord_message_normalization(self):
        event = self.processor.process_webhook(
            source_id="discord_webhook",
            payload={"t": "MESSAGE_CREATE", "content": "hello world", "channel_id": "123", "author": {"username": "bot_user"}},
            headers={"t": "MESSAGE_CREATE"},
        )
        self.assertEqual(event.status, WebhookStatus.PROCESSED)
        self.assertEqual(event.normalized_event_type, "chat_message")
        self.assertEqual(event.normalized_payload["content"], "hello world")
        self.assertEqual(event.normalized_payload["sender"], "bot_user")

    # -- Normalization: Shopify --

    def test_shopify_order_created_normalization(self):
        event = self.processor.process_webhook(
            source_id="shopify_webhook",
            payload={"id": 12345, "total_price": "99.99", "currency": "USD", "email": "cust@example.com"},
            headers={"X-Shopify-Topic": "orders/create"},
        )
        self.assertEqual(event.status, WebhookStatus.PROCESSED)
        self.assertEqual(event.normalized_event_type, "order_created")
        self.assertEqual(event.normalized_payload["order_id"], 12345)

    def test_shopify_order_paid_normalization(self):
        event = self.processor.process_webhook(
            source_id="shopify_webhook",
            payload={"id": 67890, "total_price": "50.00", "currency": "EUR"},
            headers={"X-Shopify-Topic": "orders/paid"},
        )
        self.assertEqual(event.normalized_event_type, "payment_completed")

    # -- Normalization: PagerDuty --

    def test_pagerduty_incident_triggered(self):
        event = self.processor.process_webhook(
            source_id="pagerduty_webhook",
            payload={
                "event": {
                    "event_type": "incident.triggered",
                    "data": {"id": "P123", "title": "Server Down", "urgency": "high"},
                }
            },
        )
        self.assertEqual(event.normalized_event_type, "incident_created")
        self.assertEqual(event.normalized_payload["incident_id"], "P123")

    # -- Normalization: Zendesk --

    def test_zendesk_ticket_created(self):
        event = self.processor.process_webhook(
            source_id="zendesk_webhook",
            payload={"type": "ticket_created", "ticket": {"id": 999, "subject": "Help needed", "priority": "urgent"}},
        )
        self.assertEqual(event.normalized_event_type, "ticket_created")
        self.assertEqual(event.normalized_payload["ticket_id"], 999)

    # -- Normalization: Calendly --

    def test_calendly_event_created(self):
        event = self.processor.process_webhook(
            source_id="calendly_webhook",
            payload={"event": "invitee.created", "payload": {"event": "https://calendly.com/evt/1", "name": "Alice", "email": "alice@example.com"}},
        )
        self.assertEqual(event.normalized_event_type, "meeting_scheduled")
        self.assertEqual(event.normalized_payload["invitee_name"], "Alice")

    # -- Normalization: Sentry --

    def test_sentry_issue_created(self):
        event = self.processor.process_webhook(
            source_id="sentry_webhook",
            payload={"action": "created", "data": {"issue": {"title": "TypeError", "id": "42", "level": "error"}}},
        )
        self.assertEqual(event.normalized_event_type, "error_detected")
        self.assertEqual(event.normalized_payload["title"], "TypeError")

    # -- Normalization: PayPal --

    def test_paypal_payment_completed(self):
        event = self.processor.process_webhook(
            source_id="paypal_webhook",
            payload={
                "event_type": "PAYMENT.CAPTURE.COMPLETED",
                "resource": {"id": "PAY123", "amount": {"value": "100.00", "currency_code": "USD"}},
            },
        )
        self.assertEqual(event.normalized_event_type, "payment_completed")
        self.assertEqual(event.normalized_payload["payment_id"], "PAY123")


# ---------------------------------------------------------------------------
# Cross-module consistency checks
# ---------------------------------------------------------------------------

class TestWiredIntegrationConsistency(unittest.TestCase):
    """
    Verify that wired integrations are consistently registered across
    the Universal Adapter, Platform Connector Framework, and Webhook
    Event Processor for end-to-end functionality.
    """

    def setUp(self):
        self.adapter = UniversalIntegrationAdapter()
        self.fw = PlatformConnectorFramework()
        self.processor = WebhookEventProcessor()

    def test_shopify_exists_in_all_layers(self):
        """Shopify should have adapter template, connector, and webhook source."""
        adapter_ids = [s["service_id"] for s in self.adapter.list_services()]
        connector_ids = [c["connector_id"] for c in self.fw.list_available_connectors()]
        source_ids = [s["source_id"] for s in self.processor.list_sources()]

        self.assertIn("shopify", adapter_ids)
        self.assertIn("shopify", connector_ids)
        self.assertIn("shopify_webhook", source_ids)

    def test_pagerduty_exists_in_all_layers(self):
        adapter_ids = [s["service_id"] for s in self.adapter.list_services()]
        connector_ids = [c["connector_id"] for c in self.fw.list_available_connectors()]
        source_ids = [s["source_id"] for s in self.processor.list_sources()]

        self.assertIn("pagerduty", adapter_ids)
        self.assertIn("pagerduty", connector_ids)
        self.assertIn("pagerduty_webhook", source_ids)

    def test_datadog_exists_in_all_layers(self):
        adapter_ids = [s["service_id"] for s in self.adapter.list_services()]
        connector_ids = [c["connector_id"] for c in self.fw.list_available_connectors()]
        source_ids = [s["source_id"] for s in self.processor.list_sources()]

        self.assertIn("datadog", adapter_ids)
        self.assertIn("datadog", connector_ids)
        self.assertIn("datadog_webhook", source_ids)

    def test_zendesk_exists_in_all_layers(self):
        adapter_ids = [s["service_id"] for s in self.adapter.list_services()]
        connector_ids = [c["connector_id"] for c in self.fw.list_available_connectors()]
        source_ids = [s["source_id"] for s in self.processor.list_sources()]

        self.assertIn("zendesk", adapter_ids)
        self.assertIn("zendesk", connector_ids)
        self.assertIn("zendesk_webhook", source_ids)

    def test_twilio_exists_in_adapter_and_connector(self):
        adapter_ids = [s["service_id"] for s in self.adapter.list_services()]
        connector_ids = [c["connector_id"] for c in self.fw.list_available_connectors()]
        source_ids = [s["source_id"] for s in self.processor.list_sources()]

        self.assertIn("twilio", adapter_ids)
        self.assertIn("twilio", connector_ids)
        self.assertIn("twilio_webhook", source_ids)

    def test_sentry_exists_in_all_layers(self):
        adapter_ids = [s["service_id"] for s in self.adapter.list_services()]
        connector_ids = [c["connector_id"] for c in self.fw.list_available_connectors()]
        source_ids = [s["source_id"] for s in self.processor.list_sources()]

        self.assertIn("sentry", adapter_ids)
        self.assertIn("sentry", connector_ids)
        self.assertIn("sentry_webhook", source_ids)

    def test_sendgrid_exists_in_all_layers(self):
        adapter_ids = [s["service_id"] for s in self.adapter.list_services()]
        connector_ids = [c["connector_id"] for c in self.fw.list_available_connectors()]
        source_ids = [s["source_id"] for s in self.processor.list_sources()]

        self.assertIn("sendgrid", adapter_ids)
        self.assertIn("sendgrid", connector_ids)
        self.assertIn("sendgrid_webhook", source_ids)


if __name__ == "__main__":
    unittest.main()
