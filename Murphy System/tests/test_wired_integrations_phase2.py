"""
Tests for Wired Integrations Phase 2 — validates cross-layer gap closure,
new adapter templates, new connector definitions, and new webhook sources
added to close coverage gaps between all three integration layers.

Design Label: TEST-INT-WIRED-002
Owner: Platform Engineering / QA Team
"""

import os
import unittest


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
# INT-002 Phase 2 — New Adapter Templates (Cloud, DevOps, PM, Messaging, etc.)
# ---------------------------------------------------------------------------

class TestAdapterPhase2Templates(unittest.TestCase):
    """Verify new adapter templates added in phase 2 for cross-layer parity."""

    def setUp(self):
        self.adapter = UniversalIntegrationAdapter()

    def _service_ids(self):
        return [s["service_id"] for s in self.adapter.list_services()]

    # -- Cloud Infrastructure --

    def test_aws_registered(self):
        self.assertIn("aws", self._service_ids())
        svc = self.adapter.get_service("aws")
        self.assertEqual(svc["category"], "cloud_infrastructure")
        actions = [a["name"] for a in svc["actions"]]
        self.assertIn("manage_ec2", actions)
        self.assertIn("invoke_lambda", actions)

    def test_azure_registered(self):
        self.assertIn("azure", self._service_ids())
        svc = self.adapter.get_service("azure")
        self.assertEqual(svc["category"], "cloud_infrastructure")

    def test_gcp_registered(self):
        self.assertIn("gcp", self._service_ids())
        svc = self.adapter.get_service("gcp")
        self.assertEqual(svc["category"], "cloud_infrastructure")

    # -- DevOps --

    def test_github_adapter(self):
        self.assertIn("github", self._service_ids())
        svc = self.adapter.get_service("github")
        self.assertEqual(svc["category"], "developer_tools")
        actions = [a["name"] for a in svc["actions"]]
        self.assertIn("create_issue", actions)
        self.assertIn("create_pr", actions)
        self.assertIn("trigger_workflow", actions)

    def test_gitlab_adapter(self):
        self.assertIn("gitlab", self._service_ids())
        svc = self.adapter.get_service("gitlab")
        self.assertEqual(svc["category"], "developer_tools")
        actions = [a["name"] for a in svc["actions"]]
        self.assertIn("create_mr", actions)
        self.assertIn("trigger_pipeline", actions)

    # -- Project Management --

    def test_jira_adapter(self):
        self.assertIn("jira", self._service_ids())
        svc = self.adapter.get_service("jira")
        self.assertEqual(svc["category"], "project_management")
        actions = [a["name"] for a in svc["actions"]]
        self.assertIn("create_issue", actions)
        self.assertIn("search_issues", actions)

    def test_asana_adapter(self):
        self.assertIn("asana", self._service_ids())
        svc = self.adapter.get_service("asana")
        self.assertEqual(svc["category"], "project_management")

    def test_monday_adapter(self):
        self.assertIn("monday", self._service_ids())
        svc = self.adapter.get_service("monday")
        self.assertEqual(svc["category"], "project_management")
        actions = [a["name"] for a in svc["actions"]]
        self.assertIn("create_item", actions)

    # -- Knowledge --

    def test_confluence_adapter(self):
        self.assertIn("confluence", self._service_ids())
        svc = self.adapter.get_service("confluence")
        actions = [a["name"] for a in svc["actions"]]
        self.assertIn("create_page", actions)

    def test_google_workspace_adapter(self):
        self.assertIn("google_workspace", self._service_ids())
        svc = self.adapter.get_service("google_workspace")
        actions = [a["name"] for a in svc["actions"]]
        self.assertIn("gmail_send", actions)
        self.assertIn("drive_upload", actions)

    # -- ITSM --

    def test_servicenow_adapter(self):
        self.assertIn("servicenow", self._service_ids())
        svc = self.adapter.get_service("servicenow")
        actions = [a["name"] for a in svc["actions"]]
        self.assertIn("create_incident", actions)

    # -- Communication --

    def test_whatsapp_adapter(self):
        self.assertIn("whatsapp", self._service_ids())
        svc = self.adapter.get_service("whatsapp")
        self.assertEqual(svc["category"], "communication")
        actions = [a["name"] for a in svc["actions"]]
        self.assertIn("send_message", actions)

    def test_telegram_adapter(self):
        self.assertIn("telegram", self._service_ids())
        svc = self.adapter.get_service("telegram")
        self.assertEqual(svc["category"], "communication")

    # -- Analytics --

    def test_snowflake_adapter(self):
        self.assertIn("snowflake", self._service_ids())
        svc = self.adapter.get_service("snowflake")
        self.assertEqual(svc["category"], "analytics")
        actions = [a["name"] for a in svc["actions"]]
        self.assertIn("execute_query", actions)

    # -- Messaging (Extended) --

    def test_signal_adapter(self):
        self.assertIn("signal", self._service_ids())
        svc = self.adapter.get_service("signal")
        self.assertEqual(svc["category"], "communication")
        actions = [a["name"] for a in svc["actions"]]
        self.assertIn("send_message", actions)

    def test_google_business_messages_adapter(self):
        self.assertIn("google_business_messages", self._service_ids())
        svc = self.adapter.get_service("google_business_messages")
        self.assertEqual(svc["category"], "communication")

    def test_kakaotalk_adapter(self):
        self.assertIn("kakaotalk", self._service_ids())
        svc = self.adapter.get_service("kakaotalk")
        self.assertEqual(svc["category"], "communication")

    def test_line_adapter(self):
        self.assertIn("line", self._service_ids())
        svc = self.adapter.get_service("line")
        self.assertEqual(svc["category"], "communication")

    def test_wechat_adapter(self):
        self.assertIn("wechat", self._service_ids())
        svc = self.adapter.get_service("wechat")
        self.assertEqual(svc["category"], "communication")

    def test_snapchat_adapter(self):
        self.assertIn("snapchat", self._service_ids())
        svc = self.adapter.get_service("snapchat")
        self.assertEqual(svc["category"], "social_media")

    def test_zenbusiness_adapter(self):
        self.assertIn("zenbusiness", self._service_ids())
        svc = self.adapter.get_service("zenbusiness")

    # -- Service count --

    def test_total_adapter_services_count(self):
        services = self.adapter.list_services()
        self.assertGreaterEqual(len(services), 76)

    def test_cloud_category_has_services(self):
        services = self.adapter.list_services(category="cloud_infrastructure")
        self.assertGreaterEqual(len(services), 3)

    def test_developer_tools_has_services(self):
        services = self.adapter.list_services(category="developer_tools")
        self.assertGreaterEqual(len(services), 4)


# ---------------------------------------------------------------------------
# Connector Framework Phase 2 — New Connector Definitions
# ---------------------------------------------------------------------------

class TestConnectorPhase2Definitions(unittest.TestCase):
    """Verify new connector definitions added in phase 2."""

    def setUp(self):
        self.fw = PlatformConnectorFramework()

    def _connector_ids(self):
        return [c["connector_id"] for c in self.fw.list_available_connectors()]

    # -- AI/ML --

    def test_huggingface_connector(self):
        self.assertIn("huggingface", self._connector_ids())
        conns = self.fw.list_available_connectors()
        hf = next(c for c in conns if c["connector_id"] == "huggingface")
        self.assertIn("inference", hf["capabilities"])

    def test_ollama_connector(self):
        self.assertIn("ollama", self._connector_ids())
        conns = self.fw.list_available_connectors()
        ol = next(c for c in conns if c["connector_id"] == "ollama")
        self.assertIn("generate", ol["capabilities"])
        self.assertIn("chat", ol["capabilities"])

    def test_replicate_connector(self):
        self.assertIn("replicate", self._connector_ids())

    # -- Database --

    def test_supabase_connector(self):
        self.assertIn("supabase", self._connector_ids())

    def test_firebase_connector(self):
        self.assertIn("firebase", self._connector_ids())

    def test_mongodb_atlas_connector(self):
        self.assertIn("mongodb_atlas", self._connector_ids())

    # -- Deployment --

    def test_vercel_connector(self):
        self.assertIn("vercel", self._connector_ids())
        conns = self.fw.list_available_connectors()
        v = next(c for c in conns if c["connector_id"] == "vercel")
        self.assertIn("webhook", v["capabilities"])

    def test_netlify_connector(self):
        self.assertIn("netlify", self._connector_ids())

    def test_railway_connector(self):
        self.assertIn("railway", self._connector_ids())

    # -- Project Management --

    def test_trello_connector(self):
        self.assertIn("trello", self._connector_ids())

    def test_airtable_connector(self):
        self.assertIn("airtable", self._connector_ids())

    def test_linear_connector(self):
        self.assertIn("linear", self._connector_ids())

    # -- Social Media --

    def test_twitter_connector(self):
        self.assertIn("twitter", self._connector_ids())

    def test_linkedin_connector(self):
        self.assertIn("linkedin", self._connector_ids())

    def test_reddit_connector(self):
        self.assertIn("reddit", self._connector_ids())

    # -- Media Streaming --

    def test_youtube_connector(self):
        self.assertIn("youtube", self._connector_ids())

    def test_twitch_connector(self):
        self.assertIn("twitch", self._connector_ids())

    def test_spotify_connector(self):
        self.assertIn("spotify", self._connector_ids())

    # -- Email --

    def test_resend_connector(self):
        self.assertIn("resend", self._connector_ids())

    def test_mailgun_connector(self):
        self.assertIn("mailgun", self._connector_ids())

    # -- Analytics --

    def test_mixpanel_connector(self):
        self.assertIn("mixpanel", self._connector_ids())

    def test_posthog_connector(self):
        self.assertIn("posthog", self._connector_ids())

    # -- Cloud Infrastructure --

    def test_cloudflare_connector(self):
        self.assertIn("cloudflare", self._connector_ids())

    # -- Calendar/Storage/Social --

    def test_google_calendar_connector(self):
        self.assertIn("google_calendar", self._connector_ids())

    def test_google_drive_connector(self):
        self.assertIn("google_drive", self._connector_ids())

    def test_product_hunt_connector(self):
        self.assertIn("product_hunt", self._connector_ids())

    # -- Connector count --

    def test_total_connector_count(self):
        connectors = self.fw.list_available_connectors()
        self.assertGreaterEqual(len(connectors), 76)

    # -- Configure and execute --

    def test_configure_and_execute_huggingface(self):
        self.fw.configure_connector("huggingface", {"token": "hf_test"})
        action = ConnectorAction(
            action_id="test-hf",
            connector_id="huggingface",
            action_type="inference",
            resource="models/test-model",
        )
        result = self.fw.execute_action(action)
        self.assertTrue(result.success)

    def test_configure_and_execute_vercel(self):
        self.fw.configure_connector("vercel", {"token": "vercel_test"})
        action = ConnectorAction(
            action_id="test-vercel",
            connector_id="vercel",
            action_type="list_deployments",
            resource="deployments",
        )
        result = self.fw.execute_action(action)
        self.assertTrue(result.success)


# ---------------------------------------------------------------------------
# Webhook Phase 2 — New Sources and Normalization Rules
# ---------------------------------------------------------------------------

class TestWebhookPhase2Sources(unittest.TestCase):
    """Verify new webhook sources and normalization rules from phase 2."""

    def setUp(self):
        self.processor = WebhookEventProcessor()

    def _source_ids(self):
        return [s["source_id"] for s in self.processor.list_sources()]

    # -- New webhook sources --

    def test_circleci_webhook_registered(self):
        self.assertIn("circleci_webhook", self._source_ids())

    def test_docusign_webhook_registered(self):
        self.assertIn("docusign_webhook", self._source_ids())

    def test_dropbox_webhook_registered(self):
        self.assertIn("dropbox_webhook", self._source_ids())

    def test_whatsapp_webhook_registered(self):
        self.assertIn("whatsapp_webhook", self._source_ids())

    def test_telegram_webhook_registered(self):
        self.assertIn("telegram_webhook", self._source_ids())

    def test_make_webhook_registered(self):
        self.assertIn("make_webhook", self._source_ids())

    def test_ifttt_webhook_registered(self):
        self.assertIn("ifttt_webhook", self._source_ids())

    def test_github_actions_webhook_registered(self):
        self.assertIn("github_actions_webhook", self._source_ids())

    def test_gitlab_webhook_registered(self):
        self.assertIn("gitlab_webhook", self._source_ids())

    def test_vercel_webhook_registered(self):
        self.assertIn("vercel_webhook", self._source_ids())

    def test_netlify_webhook_registered(self):
        self.assertIn("netlify_webhook", self._source_ids())

    def test_trello_webhook_registered(self):
        self.assertIn("trello_webhook", self._source_ids())

    def test_linear_webhook_registered(self):
        self.assertIn("linear_webhook", self._source_ids())

    def test_airtable_webhook_registered(self):
        self.assertIn("airtable_webhook", self._source_ids())

    def test_twitch_webhook_registered(self):
        self.assertIn("twitch_webhook", self._source_ids())

    def test_resend_webhook_registered(self):
        self.assertIn("resend_webhook", self._source_ids())

    def test_mailgun_webhook_registered(self):
        self.assertIn("mailgun_webhook", self._source_ids())

    def test_cloudflare_webhook_registered(self):
        self.assertIn("cloudflare_webhook", self._source_ids())

    def test_posthog_webhook_registered(self):
        self.assertIn("posthog_webhook", self._source_ids())

    def test_railway_webhook_registered(self):
        self.assertIn("railway_webhook", self._source_ids())

    def test_replicate_webhook_registered(self):
        self.assertIn("replicate_webhook", self._source_ids())

    def test_google_calendar_webhook_registered(self):
        self.assertIn("google_calendar_webhook", self._source_ids())

    def test_google_drive_webhook_registered(self):
        self.assertIn("google_drive_webhook", self._source_ids())

    def test_signal_webhook_registered(self):
        self.assertIn("signal_webhook", self._source_ids())

    def test_total_webhook_sources(self):
        sources = self.processor.list_sources()
        self.assertGreaterEqual(len(sources), 47)

    # -- Normalization rules --

    def test_circleci_pipeline_normalization(self):
        event = self.processor.process_webhook(
            source_id="circleci_webhook",
            payload={
                "type": "pipeline-completed",
                "pipeline": {"id": "abc-123", "vcs": {"branch": "main"}},
                "project": {"slug": "gh/org/repo"},
            },
        )
        self.assertEqual(event.status, WebhookStatus.PROCESSED)
        self.assertEqual(event.normalized_event_type, "build_completed")
        self.assertEqual(event.normalized_payload["pipeline_id"], "abc-123")

    def test_docusign_envelope_normalization(self):
        event = self.processor.process_webhook(
            source_id="docusign_webhook",
            payload={
                "event": "envelope-completed",
                "envelopeId": "env-456",
                "status": "completed",
                "emailSubject": "Sign the contract",
            },
        )
        self.assertEqual(event.normalized_event_type, "document_signed")
        self.assertEqual(event.normalized_payload["envelope_id"], "env-456")

    def test_gitlab_push_normalization(self):
        event = self.processor.process_webhook(
            source_id="gitlab_webhook",
            payload={
                "object_kind": "push",
                "project": {"path_with_namespace": "org/repo"},
                "ref": "refs/heads/main",
                "user_name": "dev_user",
            },
        )
        self.assertEqual(event.normalized_event_type, "code_push")
        self.assertEqual(event.normalized_payload["repo"], "org/repo")
        self.assertEqual(event.normalized_payload["actor"], "dev_user")

    def test_gitlab_mr_normalization(self):
        event = self.processor.process_webhook(
            source_id="gitlab_webhook",
            payload={
                "object_kind": "merge_request",
                "object_attributes": {"action": "open", "title": "Feature X", "iid": 42},
            },
        )
        self.assertEqual(event.normalized_event_type, "pull_request_update")
        self.assertEqual(event.normalized_payload["title"], "Feature X")

    def test_vercel_deployment_normalization(self):
        event = self.processor.process_webhook(
            source_id="vercel_webhook",
            payload={
                "type": "deployment.ready",
                "payload": {
                    "deployment": {
                        "url": "https://app.vercel.app",
                        "meta": {"githubCommitRef": "main"},
                    },
                    "name": "my-app",
                },
            },
        )
        self.assertEqual(event.normalized_event_type, "deployment_completed")
        self.assertEqual(event.normalized_payload["url"], "https://app.vercel.app")

    def test_trello_card_normalization(self):
        event = self.processor.process_webhook(
            source_id="trello_webhook",
            payload={
                "action": {
                    "type": "createCard",
                    "data": {
                        "card": {"name": "New task", "id": "card-789"},
                        "list": {"name": "To Do"},
                    },
                },
            },
        )
        self.assertEqual(event.normalized_event_type, "task_created")
        self.assertEqual(event.normalized_payload["title"], "New task")

    def test_linear_issue_normalization(self):
        event = self.processor.process_webhook(
            source_id="linear_webhook",
            payload={
                "type": "Issue",
                "data": {"id": "LIN-123", "title": "Bug fix", "priority": 1},
            },
        )
        self.assertEqual(event.normalized_event_type, "ticket_created")
        self.assertEqual(event.normalized_payload["ticket_id"], "LIN-123")

    def test_twitch_stream_normalization(self):
        event = self.processor.process_webhook(
            source_id="twitch_webhook",
            payload={
                "subscription": {"type": "stream.online"},
                "event": {
                    "broadcaster_user_name": "streamer123",
                    "broadcaster_user_id": "12345",
                },
            },
        )
        self.assertEqual(event.normalized_event_type, "stream_started")
        self.assertEqual(event.normalized_payload["streamer"], "streamer123")

    def test_resend_email_normalization(self):
        event = self.processor.process_webhook(
            source_id="resend_webhook",
            payload={
                "type": "email.delivered",
                "data": {"to": "user@example.com", "email_id": "msg-001"},
            },
        )
        self.assertEqual(event.normalized_event_type, "email_delivered")
        self.assertEqual(event.normalized_payload["recipient"], "user@example.com")

    def test_whatsapp_message_normalization(self):
        event = self.processor.process_webhook(
            source_id="whatsapp_webhook",
            payload={
                "object": "whatsapp_business_account",
                "messaging_product": "whatsapp",
                "metadata": {"phone_number_id": "12345"},
            },
        )
        self.assertEqual(event.normalized_event_type, "chat_message")

    def test_telegram_message_normalization(self):
        event = self.processor.process_webhook(
            source_id="telegram_webhook",
            payload={
                "update_type": "message_update",
                "message": {
                    "text": "Hello bot",
                    "from": {"username": "testuser"},
                    "chat": {"id": 123456},
                },
            },
        )
        self.assertEqual(event.normalized_event_type, "chat_message")
        self.assertEqual(event.normalized_payload["content"], "Hello bot")
        self.assertEqual(event.normalized_payload["sender"], "testuser")


# ---------------------------------------------------------------------------
# Cross-Layer Consistency Phase 2
# ---------------------------------------------------------------------------

class TestPhase2CrossLayerConsistency(unittest.TestCase):
    """Verify cross-layer wiring for phase 2 integrations."""

    def setUp(self):
        self.adapter = UniversalIntegrationAdapter()
        self.fw = PlatformConnectorFramework()
        self.processor = WebhookEventProcessor()
        self.adapter_ids = set(s["service_id"] for s in self.adapter.list_services())
        self.connector_ids = set(c["connector_id"] for c in self.fw.list_available_connectors())
        self.source_ids = set(s["source_id"] for s in self.processor.list_sources())

    # -- DevOps full stack --

    def test_github_all_layers(self):
        self.assertIn("github", self.adapter_ids)
        self.assertIn("github", self.connector_ids)
        self.assertIn("github_webhook", self.source_ids)

    def test_gitlab_all_layers(self):
        self.assertIn("gitlab", self.adapter_ids)
        self.assertIn("gitlab", self.connector_ids)
        self.assertIn("gitlab_webhook", self.source_ids)

    def test_circleci_all_layers(self):
        self.assertIn("circleci", self.adapter_ids)
        self.assertIn("circleci", self.connector_ids)
        self.assertIn("circleci_webhook", self.source_ids)

    # -- Project Management --

    def test_jira_all_layers(self):
        self.assertIn("jira", self.adapter_ids)
        self.assertIn("jira", self.connector_ids)
        self.assertIn("jira_webhook", self.source_ids)

    def test_trello_all_layers(self):
        self.assertIn("trello", self.adapter_ids)
        self.assertIn("trello", self.connector_ids)
        self.assertIn("trello_webhook", self.source_ids)

    def test_linear_all_layers(self):
        self.assertIn("linear", self.adapter_ids)
        self.assertIn("linear", self.connector_ids)
        self.assertIn("linear_webhook", self.source_ids)

    # -- Communication --

    def test_telegram_all_layers(self):
        self.assertIn("telegram", self.adapter_ids)
        self.assertIn("telegram", self.connector_ids)
        self.assertIn("telegram_webhook", self.source_ids)

    def test_whatsapp_all_layers(self):
        self.assertIn("whatsapp", self.adapter_ids)
        self.assertIn("whatsapp", self.connector_ids)
        self.assertIn("whatsapp_webhook", self.source_ids)

    # -- Deployment --

    def test_vercel_all_layers(self):
        self.assertIn("vercel", self.adapter_ids)
        self.assertIn("vercel", self.connector_ids)
        self.assertIn("vercel_webhook", self.source_ids)

    def test_netlify_all_layers(self):
        self.assertIn("netlify", self.adapter_ids)
        self.assertIn("netlify", self.connector_ids)
        self.assertIn("netlify_webhook", self.source_ids)

    # -- AI/ML --

    def test_huggingface_adapter_and_connector(self):
        self.assertIn("huggingface", self.adapter_ids)
        self.assertIn("huggingface", self.connector_ids)

    def test_ollama_adapter_and_connector(self):
        self.assertIn("ollama", self.adapter_ids)
        self.assertIn("ollama", self.connector_ids)

    # -- Email --

    def test_resend_all_layers(self):
        self.assertIn("resend", self.adapter_ids)
        self.assertIn("resend", self.connector_ids)
        self.assertIn("resend_webhook", self.source_ids)

    def test_mailgun_all_layers(self):
        self.assertIn("mailgun", self.adapter_ids)
        self.assertIn("mailgun", self.connector_ids)
        self.assertIn("mailgun_webhook", self.source_ids)

    # -- Analytics --

    def test_mixpanel_adapter_and_connector(self):
        self.assertIn("mixpanel", self.adapter_ids)
        self.assertIn("mixpanel", self.connector_ids)

    def test_posthog_adapter_and_connector(self):
        self.assertIn("posthog", self.adapter_ids)
        self.assertIn("posthog", self.connector_ids)

    def test_snowflake_adapter_and_connector(self):
        self.assertIn("snowflake", self.adapter_ids)
        self.assertIn("snowflake", self.connector_ids)

    # -- Media --

    def test_twitch_all_layers(self):
        self.assertIn("twitch", self.adapter_ids)
        self.assertIn("twitch", self.connector_ids)
        self.assertIn("twitch_webhook", self.source_ids)

    # -- Cloud Infrastructure --

    def test_aws_all_layers(self):
        self.assertIn("aws", self.adapter_ids)
        self.assertIn("aws", self.connector_ids)
        self.assertIn("aws_webhook", self.source_ids)

    def test_azure_all_layers(self):
        self.assertIn("azure", self.adapter_ids)
        self.assertIn("azure", self.connector_ids)
        self.assertIn("azure_webhook", self.source_ids)

    def test_gcp_adapter_and_connector(self):
        self.assertIn("gcp", self.adapter_ids)
        self.assertIn("gcp", self.connector_ids)

    # -- Automation --

    def test_make_all_layers(self):
        self.assertIn("make", self.adapter_ids)
        self.assertIn("make", self.connector_ids)
        self.assertIn("make_webhook", self.source_ids)

    # -- Project Management (aligned IDs) --

    def test_monday_adapter_and_connector(self):
        self.assertIn("monday", self.adapter_ids)
        self.assertIn("monday", self.connector_ids)

    # -- Monitoring --

    def test_newrelic_adapter_and_connector(self):
        self.assertIn("newrelic", self.adapter_ids)
        self.assertIn("newrelic", self.connector_ids)

    # -- Social Media --

    def test_twitter_adapter_and_connector(self):
        self.assertIn("twitter", self.adapter_ids)
        self.assertIn("twitter", self.connector_ids)

    # -- Enterprise --

    def test_ms_teams_adapter_and_connector(self):
        self.assertIn("ms_teams", self.adapter_ids)
        self.assertIn("ms_teams", self.connector_ids)

    def test_quickbooks_adapter_and_connector(self):
        self.assertIn("quickbooks", self.adapter_ids)
        self.assertIn("quickbooks", self.connector_ids)


# ---------------------------------------------------------------------------
# Webhook Capability Coverage Test
# ---------------------------------------------------------------------------

class TestWebhookCapabilityCoverage(unittest.TestCase):
    """Verify every connector with 'webhook' capability has a webhook source."""

    def setUp(self):
        self.fw = PlatformConnectorFramework()
        self.processor = WebhookEventProcessor()

    def test_all_webhook_capable_connectors_have_sources(self):
        connector_ids = set(c["connector_id"] for c in self.fw.list_available_connectors())
        source_ids = set(s["source_id"] for s in self.processor.list_sources())

        missing = []
        for cid in sorted(connector_ids):
            conns = self.fw.list_available_connectors()
            c = next((c for c in conns if c["connector_id"] == cid), None)
            if c and "webhook" in c.get("capabilities", []):
                expected_src = f"{cid}_webhook"
                if expected_src not in source_ids:
                    missing.append(cid)

        self.assertEqual(
            missing, [],
            f"Connectors with webhook capability but no webhook source: {missing}",
        )


# ---------------------------------------------------------------------------
# Overall Metrics
# ---------------------------------------------------------------------------

class TestIntegrationMetrics(unittest.TestCase):
    """Verify overall integration counts meet targets."""

    def test_adapter_has_minimum_services(self):
        adapter = UniversalIntegrationAdapter()
        services = adapter.list_services()
        self.assertGreaterEqual(len(services), 76, "Adapter should have 76+ services")

    def test_connector_has_minimum_definitions(self):
        fw = PlatformConnectorFramework()
        connectors = fw.list_available_connectors()
        self.assertGreaterEqual(len(connectors), 76, "Framework should have 76+ connectors")

    def test_webhooks_have_minimum_sources(self):
        wp = WebhookEventProcessor()
        sources = wp.list_sources()
        self.assertGreaterEqual(len(sources), 61, "Processor should have 61+ webhook sources")

    def test_adapter_categories_are_comprehensive(self):
        adapter = UniversalIntegrationAdapter()
        categories = adapter.list_categories()
        expected = [
            "communication", "project_management", "automation",
            "deployment", "database", "cloud_infrastructure",
            "developer_tools", "crm", "payment", "monitoring",
            "email", "analytics", "storage",
        ]
        for cat in expected:
            self.assertIn(cat, categories, f"Category '{cat}' should exist in adapter")

    def test_adapter_connector_full_alignment(self):
        """Every adapter service must have a matching connector and vice versa."""
        adapter = UniversalIntegrationAdapter()
        fw = PlatformConnectorFramework()
        adapter_ids = set(s["service_id"] for s in adapter.list_services())
        connector_ids = set(c["connector_id"] for c in fw.list_available_connectors())
        self.assertEqual(
            sorted(adapter_ids - connector_ids), [],
            "Adapter services missing connector definitions",
        )
        self.assertEqual(
            sorted(connector_ids - adapter_ids), [],
            "Connectors missing adapter services",
        )


if __name__ == "__main__":
    unittest.main()
