"""Tests for WebhookEventProcessor."""

import sys
import os
import unittest
import hashlib
import hmac
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from webhook_event_processor import (
    WebhookEventProcessor,
    WebhookSource,
    NormalizationRule,
    WebhookStatus,
    SignatureAlgorithm,
)


class TestWebhookEventProcessor(unittest.TestCase):

    def setUp(self):
        self.processor = WebhookEventProcessor()

    def test_default_sources_registered(self):
        sources = self.processor.list_sources()
        self.assertGreater(len(sources), 5)
        source_ids = [s["source_id"] for s in sources]
        for expected in ["github_webhook", "slack_webhook", "stripe_webhook", "jira_webhook"]:
            self.assertIn(expected, source_ids)

    def test_process_github_push(self):
        event = self.processor.process_webhook(
            source_id="github_webhook",
            payload={"ref": "refs/heads/main", "pusher": {"name": "dev"}, "repository": {"full_name": "org/repo"}},
            headers={"X-GitHub-Event": "push"},
        )
        self.assertEqual(event.status, WebhookStatus.PROCESSED)
        self.assertEqual(event.normalized_event_type, "code_push")
        self.assertEqual(event.normalized_payload["repo"], "org/repo")

    def test_process_github_pr(self):
        event = self.processor.process_webhook(
            source_id="github_webhook",
            payload={"action": "opened", "pull_request": {"title": "Fix bug", "number": 42}},
            headers={"X-GitHub-Event": "pull_request"},
        )
        self.assertEqual(event.normalized_event_type, "pull_request_update")
        self.assertEqual(event.normalized_payload["title"], "Fix bug")

    def test_process_slack_message(self):
        event = self.processor.process_webhook(
            source_id="slack_webhook",
            payload={"type": "message", "text": "hello", "channel": "C123", "user": "U456"},
        )
        self.assertEqual(event.normalized_event_type, "chat_message")
        self.assertEqual(event.normalized_payload["content"], "hello")

    def test_process_stripe_payment(self):
        event = self.processor.process_webhook(
            source_id="stripe_webhook",
            payload={"type": "payment_intent.succeeded", "data": {"object": {"amount": 5000, "currency": "usd"}}},
        )
        self.assertEqual(event.normalized_event_type, "payment_completed")
        self.assertEqual(event.normalized_payload["amount"], 5000)

    def test_process_jira_issue_created(self):
        event = self.processor.process_webhook(
            source_id="jira_webhook",
            payload={"webhookEvent": "jira:issue_created", "issue": {"key": "PROJ-123", "fields": {"summary": "Bug"}}},
        )
        self.assertEqual(event.normalized_event_type, "ticket_created")
        self.assertEqual(event.normalized_payload["ticket_id"], "PROJ-123")

    def test_process_unknown_source(self):
        event = self.processor.process_webhook(
            source_id="nonexistent",
            payload={"data": "test"},
        )
        self.assertEqual(event.status, WebhookStatus.REJECTED)
        self.assertIn("Unknown source", event.error)

    def test_process_disabled_source(self):
        source = WebhookSource(
            source_id="disabled_src",
            name="Disabled",
            platform="test",
            active=False,
        )
        self.processor.register_source(source)
        event = self.processor.process_webhook("disabled_src", {"data": "test"})
        self.assertEqual(event.status, WebhookStatus.REJECTED)

    def test_signature_verification_sha256(self):
        secret = "my-secret"
        payload = b'{"event": "test"}'
        expected_sig = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

        self.processor.configure_source_secret("github_webhook", secret)
        event = self.processor.process_webhook(
            source_id="github_webhook",
            payload=json.loads(payload),
            headers={"X-Hub-Signature-256": f"sha256={expected_sig}", "X-GitHub-Event": "ping"},
            raw_body=payload,
        )
        self.assertNotEqual(event.status, WebhookStatus.REJECTED)

    def test_signature_verification_fails(self):
        self.processor.configure_source_secret("github_webhook", "my-secret")
        event = self.processor.process_webhook(
            source_id="github_webhook",
            payload={"event": "test"},
            headers={"X-Hub-Signature-256": "sha256=invalid", "X-GitHub-Event": "ping"},
            raw_body=b'{"event": "test"}',
        )
        self.assertEqual(event.status, WebhookStatus.REJECTED)
        self.assertIn("Signature verification failed", event.error)

    def test_register_custom_source(self):
        source = WebhookSource(
            source_id="my_api",
            name="My API",
            platform="custom",
            event_type_field="event_type",
        )
        self.assertTrue(self.processor.register_source(source))
        sources = self.processor.list_sources()
        ids = [s["source_id"] for s in sources]
        self.assertIn("my_api", ids)

    def test_register_custom_rule(self):
        rule = NormalizationRule(
            rule_id="custom_rule",
            source_id="custom_webhook",
            source_event="order_placed",
            normalized_event="new_order",
            field_mapping={"order_id": "id", "total": "amount"},
        )
        self.assertTrue(self.processor.register_rule(rule))
        event = self.processor.process_webhook(
            source_id="custom_webhook",
            payload={"event": "order_placed", "order_id": "ORD-001", "total": 99.99},
        )
        self.assertEqual(event.normalized_event_type, "new_order")
        self.assertEqual(event.normalized_payload["id"], "ORD-001")

    def test_handler_called(self):
        handled = []
        self.processor.register_handler("code_push", lambda e: handled.append(e.event_id))
        self.processor.process_webhook(
            source_id="github_webhook",
            payload={"ref": "main", "pusher": {"name": "dev"}, "repository": {"full_name": "org/repo"}},
            headers={"X-GitHub-Event": "push"},
        )
        self.assertEqual(len(handled), 1)

    def test_handler_exception(self):
        self.processor.register_handler("code_push", lambda e: 1/0)
        event = self.processor.process_webhook(
            source_id="github_webhook",
            payload={"ref": "main", "pusher": {"name": "dev"}, "repository": {"full_name": "org/repo"}},
            headers={"X-GitHub-Event": "push"},
        )
        self.assertEqual(event.status, WebhookStatus.FAILED)

    def test_event_history(self):
        self.processor.process_webhook(
            source_id="github_webhook",
            payload={"ref": "main"},
            headers={"X-GitHub-Event": "push"},
        )
        history = self.processor.get_event_history("github_webhook")
        self.assertEqual(len(history), 1)

    def test_event_history_all(self):
        self.processor.process_webhook("github_webhook", {}, headers={"X-GitHub-Event": "ping"})
        self.processor.process_webhook("slack_webhook", {"type": "message", "text": "hi"})
        history = self.processor.get_event_history()
        self.assertEqual(len(history), 2)

    def test_statistics(self):
        self.processor.process_webhook("github_webhook", {}, headers={"X-GitHub-Event": "ping"})
        stats = self.processor.get_statistics()
        self.assertGreater(stats["total_events"], 0)
        self.assertGreater(stats["total_sources"], 0)

    def test_status(self):
        status = self.processor.status()
        self.assertEqual(status["module"], "webhook_event_processor")
        self.assertIn("statistics", status)
        self.assertIn("sources", status)

    def test_configure_source_secret(self):
        self.assertTrue(self.processor.configure_source_secret("github_webhook", "secret123"))
        self.assertFalse(self.processor.configure_source_secret("nonexistent", "secret"))

    def test_unmapped_event_passthrough(self):
        event = self.processor.process_webhook(
            source_id="github_webhook",
            payload={"action": "completed"},
            headers={"X-GitHub-Event": "workflow_run"},
        )
        self.assertEqual(event.raw_event_type, "workflow_run")
        self.assertEqual(event.normalized_event_type, "workflow_run")  # passthrough

    def test_get_event(self):
        event = self.processor.process_webhook(
            source_id="github_webhook",
            payload={},
            headers={"X-GitHub-Event": "ping"},
        )
        found = self.processor.get_event(event.event_id)
        self.assertIsNotNone(found)
        self.assertEqual(found["event_id"], event.event_id)

    def test_get_event_not_found(self):
        self.assertIsNone(self.processor.get_event("nonexistent"))

    def test_no_secret_skips_verification(self):
        event = self.processor.process_webhook(
            source_id="github_webhook",
            payload={"ref": "main"},
            headers={"X-GitHub-Event": "push"},
            raw_body=b'{"ref": "main"}',
        )
        self.assertNotEqual(event.status, WebhookStatus.REJECTED)

    def test_azure_webhook(self):
        event = self.processor.process_webhook(
            source_id="azure_webhook",
            payload={"eventType": "Microsoft.Storage.BlobCreated", "data": {"url": "https://storage/blob"}},
        )
        self.assertEqual(event.status, WebhookStatus.PROCESSED)

    def test_servicenow_webhook(self):
        event = self.processor.process_webhook(
            source_id="servicenow_webhook",
            payload={"event_type": "incident_created", "number": "INC001"},
        )
        self.assertEqual(event.status, WebhookStatus.PROCESSED)


if __name__ == "__main__":
    unittest.main()
