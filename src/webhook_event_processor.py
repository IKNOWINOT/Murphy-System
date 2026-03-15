"""
Webhook Event Processor — Inbound webhook handling for event-driven
integrations with signature verification, payload normalization,
event routing, and processing pipeline.
"""

import hashlib
import hmac
import json
import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)


class WebhookStatus(Enum):
    """Webhook status (Enum subclass)."""
    RECEIVED = "received"
    VERIFIED = "verified"
    REJECTED = "rejected"
    PROCESSED = "processed"
    FAILED = "failed"
    RETRYING = "retrying"


class SignatureAlgorithm(Enum):
    """Signature algorithm (Enum subclass)."""
    SHA256 = "sha256"
    SHA1 = "sha1"
    MD5 = "md5"
    NONE = "none"


@dataclass
class WebhookSource:
    """Webhook source."""
    source_id: str
    name: str
    platform: str
    signature_header: str = "X-Signature"
    signature_algorithm: SignatureAlgorithm = SignatureAlgorithm.SHA256
    secret: str = ""
    event_type_field: str = "event"
    payload_format: str = "json"  # json, form, xml
    active: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class NormalizationRule:
    """Normalization rule."""
    rule_id: str
    source_id: str
    source_event: str
    normalized_event: str
    field_mapping: Dict[str, str] = field(default_factory=dict)  # source_field -> murphy_field
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WebhookEvent:
    """Webhook event."""
    event_id: str
    source_id: str
    raw_event_type: str
    normalized_event_type: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    normalized_payload: Dict[str, Any] = field(default_factory=dict)
    headers: Dict[str, str] = field(default_factory=dict)
    status: WebhookStatus = WebhookStatus.RECEIVED
    error: Optional[str] = None
    received_at: float = field(default_factory=time.time)
    processed_at: float = 0.0
    retries: int = 0


# Default webhook sources for popular platforms
DEFAULT_SOURCES = [
    WebhookSource(
        source_id="github_webhook",
        name="GitHub Webhooks",
        platform="github",
        signature_header="X-Hub-Signature-256",
        signature_algorithm=SignatureAlgorithm.SHA256,
        event_type_field="X-GitHub-Event",
    ),
    WebhookSource(
        source_id="slack_webhook",
        name="Slack Events",
        platform="slack",
        signature_header="X-Slack-Signature",
        signature_algorithm=SignatureAlgorithm.SHA256,
        event_type_field="type",
    ),
    WebhookSource(
        source_id="stripe_webhook",
        name="Stripe Events",
        platform="stripe",
        signature_header="Stripe-Signature",
        signature_algorithm=SignatureAlgorithm.SHA256,
        event_type_field="type",
    ),
    WebhookSource(
        source_id="jira_webhook",
        name="Jira Webhooks",
        platform="jira",
        signature_header="X-Atlassian-Webhook-Signature",
        signature_algorithm=SignatureAlgorithm.SHA256,
        event_type_field="webhookEvent",
    ),
    WebhookSource(
        source_id="hubspot_webhook",
        name="HubSpot Webhooks",
        platform="hubspot",
        signature_header="X-HubSpot-Signature-v3",
        signature_algorithm=SignatureAlgorithm.SHA256,
        event_type_field="eventType",
    ),
    WebhookSource(
        source_id="servicenow_webhook",
        name="ServiceNow Events",
        platform="servicenow",
        event_type_field="event_type",
        signature_algorithm=SignatureAlgorithm.NONE,
    ),
    WebhookSource(
        source_id="salesforce_webhook",
        name="Salesforce Platform Events",
        platform="salesforce",
        signature_header="X-Salesforce-Signature",
        signature_algorithm=SignatureAlgorithm.SHA256,
        event_type_field="event_type",
    ),
    WebhookSource(
        source_id="azure_webhook",
        name="Azure Event Grid",
        platform="azure",
        signature_header="aeg-event-type",
        signature_algorithm=SignatureAlgorithm.NONE,
        event_type_field="eventType",
    ),
    WebhookSource(
        source_id="aws_webhook",
        name="AWS SNS/EventBridge",
        platform="aws",
        event_type_field="Type",
        signature_algorithm=SignatureAlgorithm.NONE,
    ),
    # ---- Wired Integration Webhook Sources ----
    WebhookSource(
        source_id="discord_webhook",
        name="Discord Events",
        platform="discord",
        signature_header="X-Signature-Ed25519",
        signature_algorithm=SignatureAlgorithm.NONE,
        event_type_field="t",
    ),
    WebhookSource(
        source_id="shopify_webhook",
        name="Shopify Webhooks",
        platform="shopify",
        signature_header="X-Shopify-Hmac-Sha256",
        signature_algorithm=SignatureAlgorithm.SHA256,
        event_type_field="X-Shopify-Topic",
    ),
    WebhookSource(
        source_id="twilio_webhook",
        name="Twilio Status Callbacks",
        platform="twilio",
        signature_header="X-Twilio-Signature",
        signature_algorithm=SignatureAlgorithm.SHA1,
        event_type_field="MessageStatus",
    ),
    WebhookSource(
        source_id="pagerduty_webhook",
        name="PagerDuty Webhooks",
        platform="pagerduty",
        signature_header="X-PagerDuty-Signature",
        signature_algorithm=SignatureAlgorithm.SHA256,
        event_type_field="event.event_type",
    ),
    WebhookSource(
        source_id="datadog_webhook",
        name="Datadog Webhooks",
        platform="datadog",
        signature_algorithm=SignatureAlgorithm.NONE,
        event_type_field="event_type",
    ),
    WebhookSource(
        source_id="zendesk_webhook",
        name="Zendesk Webhooks",
        platform="zendesk",
        signature_header="X-Zendesk-Webhook-Signature",
        signature_algorithm=SignatureAlgorithm.SHA256,
        event_type_field="type",
    ),
    WebhookSource(
        source_id="zapier_webhook",
        name="Zapier Webhooks",
        platform="zapier",
        signature_algorithm=SignatureAlgorithm.NONE,
        event_type_field="event",
    ),
    WebhookSource(
        source_id="n8n_webhook",
        name="n8n Webhooks",
        platform="n8n",
        signature_algorithm=SignatureAlgorithm.NONE,
        event_type_field="event",
    ),
    WebhookSource(
        source_id="sendgrid_webhook",
        name="SendGrid Event Webhooks",
        platform="sendgrid",
        signature_header="X-Twilio-Email-Event-Webhook-Signature",
        signature_algorithm=SignatureAlgorithm.NONE,
        event_type_field="event",
    ),
    WebhookSource(
        source_id="paypal_webhook",
        name="PayPal Webhooks",
        platform="paypal",
        signature_header="PAYPAL-TRANSMISSION-SIG",
        signature_algorithm=SignatureAlgorithm.SHA256,
        event_type_field="event_type",
    ),
    WebhookSource(
        source_id="intercom_webhook",
        name="Intercom Webhooks",
        platform="intercom",
        signature_header="X-Hub-Signature",
        signature_algorithm=SignatureAlgorithm.SHA1,
        event_type_field="topic",
    ),
    WebhookSource(
        source_id="calendly_webhook",
        name="Calendly Webhooks",
        platform="calendly",
        signature_header="Calendly-Webhook-Signature",
        signature_algorithm=SignatureAlgorithm.SHA256,
        event_type_field="event",
    ),
    WebhookSource(
        source_id="sentry_webhook",
        name="Sentry Webhooks",
        platform="sentry",
        signature_header="Sentry-Hook-Signature",
        signature_algorithm=SignatureAlgorithm.SHA256,
        event_type_field="action",
    ),
    WebhookSource(
        source_id="circleci_webhook",
        name="CircleCI Webhooks",
        platform="circleci",
        signature_header="Circleci-Signature",
        signature_algorithm=SignatureAlgorithm.SHA256,
        event_type_field="type",
    ),
    WebhookSource(
        source_id="docusign_webhook",
        name="DocuSign Connect",
        platform="docusign",
        signature_header="X-DocuSign-Signature-1",
        signature_algorithm=SignatureAlgorithm.SHA256,
        event_type_field="event",
    ),
    WebhookSource(
        source_id="dropbox_webhook",
        name="Dropbox Webhooks",
        platform="dropbox",
        signature_header="X-Dropbox-Signature",
        signature_algorithm=SignatureAlgorithm.SHA256,
        event_type_field="list_folder.accounts",
    ),
    WebhookSource(
        source_id="whatsapp_webhook",
        name="WhatsApp Cloud API Webhooks",
        platform="whatsapp",
        signature_header="X-Hub-Signature-256",
        signature_algorithm=SignatureAlgorithm.SHA256,
        event_type_field="object",
    ),
    WebhookSource(
        source_id="telegram_webhook",
        name="Telegram Bot Webhooks",
        platform="telegram",
        signature_algorithm=SignatureAlgorithm.NONE,
        event_type_field="update_type",
    ),
    WebhookSource(
        source_id="make_webhook",
        name="Make (Integromat) Webhooks",
        platform="make",
        signature_algorithm=SignatureAlgorithm.NONE,
        event_type_field="event",
    ),
    WebhookSource(
        source_id="ifttt_webhook",
        name="IFTTT Webhooks",
        platform="ifttt",
        signature_algorithm=SignatureAlgorithm.NONE,
        event_type_field="event",
    ),
    WebhookSource(
        source_id="github_actions_webhook",
        name="GitHub Actions Webhooks",
        platform="github",
        signature_header="X-Hub-Signature-256",
        signature_algorithm=SignatureAlgorithm.SHA256,
        event_type_field="action",
    ),
    WebhookSource(
        source_id="gitlab_webhook",
        name="GitLab Webhooks",
        platform="gitlab",
        signature_header="X-Gitlab-Token",
        signature_algorithm=SignatureAlgorithm.NONE,
        event_type_field="object_kind",
    ),
    WebhookSource(
        source_id="vercel_webhook",
        name="Vercel Deploy Hooks",
        platform="vercel",
        signature_header="x-vercel-signature",
        signature_algorithm=SignatureAlgorithm.SHA1,
        event_type_field="type",
    ),
    WebhookSource(
        source_id="netlify_webhook",
        name="Netlify Deploy Notifications",
        platform="netlify",
        signature_header="X-Webhook-Signature",
        signature_algorithm=SignatureAlgorithm.SHA256,
        event_type_field="state",
    ),
    WebhookSource(
        source_id="trello_webhook",
        name="Trello Webhooks",
        platform="trello",
        signature_header="x-trello-webhook",
        signature_algorithm=SignatureAlgorithm.NONE,
        event_type_field="action.type",
    ),
    WebhookSource(
        source_id="linear_webhook",
        name="Linear Webhooks",
        platform="linear",
        signature_header="Linear-Signature",
        signature_algorithm=SignatureAlgorithm.SHA256,
        event_type_field="type",
    ),
    WebhookSource(
        source_id="airtable_webhook",
        name="Airtable Webhooks",
        platform="airtable",
        signature_header="X-Airtable-Content-MAC",
        signature_algorithm=SignatureAlgorithm.SHA256,
        event_type_field="type",
    ),
    WebhookSource(
        source_id="twitch_webhook",
        name="Twitch EventSub",
        platform="twitch",
        signature_header="Twitch-Eventsub-Message-Signature",
        signature_algorithm=SignatureAlgorithm.SHA256,
        event_type_field="subscription.type",
    ),
    WebhookSource(
        source_id="resend_webhook",
        name="Resend Webhooks",
        platform="resend",
        signature_header="svix-signature",
        signature_algorithm=SignatureAlgorithm.SHA256,
        event_type_field="type",
    ),
    WebhookSource(
        source_id="mailgun_webhook",
        name="Mailgun Webhooks",
        platform="mailgun",
        signature_header="X-Mailgun-Signature",
        signature_algorithm=SignatureAlgorithm.SHA256,
        event_type_field="event-data.event",
    ),
    WebhookSource(
        source_id="cloudflare_webhook",
        name="Cloudflare Webhooks",
        platform="cloudflare",
        signature_algorithm=SignatureAlgorithm.NONE,
        event_type_field="event",
    ),
    WebhookSource(
        source_id="posthog_webhook",
        name="PostHog Webhooks",
        platform="posthog",
        signature_algorithm=SignatureAlgorithm.NONE,
        event_type_field="event",
    ),
    WebhookSource(
        source_id="railway_webhook",
        name="Railway Deploy Webhooks",
        platform="railway",
        signature_algorithm=SignatureAlgorithm.NONE,
        event_type_field="type",
    ),
    WebhookSource(
        source_id="replicate_webhook",
        name="Replicate Prediction Webhooks",
        platform="replicate",
        signature_header="Webhook-Secret",
        signature_algorithm=SignatureAlgorithm.SHA256,
        event_type_field="status",
    ),
    WebhookSource(
        source_id="google_calendar_webhook",
        name="Google Calendar Push Notifications",
        platform="google_calendar",
        signature_algorithm=SignatureAlgorithm.NONE,
        event_type_field="X-Goog-Resource-State",
    ),
    WebhookSource(
        source_id="google_drive_webhook",
        name="Google Drive Push Notifications",
        platform="google_drive",
        signature_algorithm=SignatureAlgorithm.NONE,
        event_type_field="X-Goog-Resource-State",
    ),
    WebhookSource(
        source_id="signal_webhook",
        name="Signal Webhooks",
        platform="signal",
        signature_algorithm=SignatureAlgorithm.NONE,
        event_type_field="type",
    ),
    WebhookSource(
        source_id="asana_webhook",
        name="Asana Webhooks",
        platform="asana",
        signature_header="X-Hook-Secret",
        signature_algorithm=SignatureAlgorithm.SHA256,
        event_type_field="resource_type",
    ),
    WebhookSource(
        source_id="notion_webhook",
        name="Notion Webhooks",
        platform="notion",
        signature_algorithm=SignatureAlgorithm.NONE,
        event_type_field="type",
    ),
    WebhookSource(
        source_id="monday_webhook",
        name="Monday.com Webhooks",
        platform="monday",
        signature_algorithm=SignatureAlgorithm.NONE,
        event_type_field="event.type",
    ),
    WebhookSource(
        source_id="jenkins_webhook",
        name="Jenkins Webhooks",
        platform="jenkins",
        signature_algorithm=SignatureAlgorithm.NONE,
        event_type_field="build.phase",
    ),
    WebhookSource(
        source_id="freshdesk_webhook",
        name="Freshdesk Webhooks",
        platform="freshdesk",
        signature_algorithm=SignatureAlgorithm.NONE,
        event_type_field="event",
    ),
    WebhookSource(
        source_id="newrelic_webhook",
        name="New Relic Webhooks",
        platform="newrelic",
        signature_algorithm=SignatureAlgorithm.NONE,
        event_type_field="event_type",
    ),
    WebhookSource(
        source_id="woocommerce_webhook",
        name="WooCommerce Webhooks",
        platform="woocommerce",
        signature_header="X-WC-Webhook-Signature",
        signature_algorithm=SignatureAlgorithm.SHA256,
        event_type_field="action",
    ),
    WebhookSource(
        source_id="confluence_webhook",
        name="Confluence Webhooks",
        platform="confluence",
        signature_algorithm=SignatureAlgorithm.NONE,
        event_type_field="eventType",
    ),
    WebhookSource(
        source_id="firebase_webhook",
        name="Firebase Cloud Functions Webhooks",
        platform="firebase",
        signature_algorithm=SignatureAlgorithm.NONE,
        event_type_field="eventType",
    ),
    WebhookSource(
        source_id="linkedin_webhook",
        name="LinkedIn Webhooks",
        platform="linkedin",
        signature_algorithm=SignatureAlgorithm.NONE,
        event_type_field="eventType",
    ),
    WebhookSource(
        source_id="mongodb_atlas_webhook",
        name="MongoDB Atlas Alerts",
        platform="mongodb_atlas",
        signature_header="X-MDB-Signature",
        signature_algorithm=SignatureAlgorithm.SHA256,
        event_type_field="eventTypeName",
    ),
    WebhookSource(
        source_id="quickbooks_webhook",
        name="QuickBooks Webhooks",
        platform="quickbooks",
        signature_header="Intuit-Signature",
        signature_algorithm=SignatureAlgorithm.SHA256,
        event_type_field="eventNotifications.0.dataChangeEvent.entities.0.name",
    ),
    WebhookSource(
        source_id="google_workspace_webhook",
        name="Google Workspace Events",
        platform="google_workspace",
        signature_algorithm=SignatureAlgorithm.NONE,
        event_type_field="type",
    ),
    WebhookSource(
        source_id="ms_teams_webhook",
        name="Microsoft Teams Webhooks",
        platform="ms_teams",
        signature_header="Authorization",
        signature_algorithm=SignatureAlgorithm.SHA256,
        event_type_field="type",
    ),
    WebhookSource(
        source_id="custom_webhook",
        name="Custom Webhook",
        platform="custom",
        signature_algorithm=SignatureAlgorithm.NONE,
        event_type_field="event",
    ),
]

# Default normalization rules
DEFAULT_RULES = [
    NormalizationRule(
        rule_id="github_push",
        source_id="github_webhook",
        source_event="push",
        normalized_event="code_push",
        field_mapping={"repository.full_name": "repo", "ref": "branch", "pusher.name": "actor"},
    ),
    NormalizationRule(
        rule_id="github_pr",
        source_id="github_webhook",
        source_event="pull_request",
        normalized_event="pull_request_update",
        field_mapping={"action": "action", "pull_request.title": "title", "pull_request.number": "number"},
    ),
    NormalizationRule(
        rule_id="github_issue",
        source_id="github_webhook",
        source_event="issues",
        normalized_event="issue_update",
        field_mapping={"action": "action", "issue.title": "title", "issue.number": "number"},
    ),
    NormalizationRule(
        rule_id="slack_message",
        source_id="slack_webhook",
        source_event="message",
        normalized_event="chat_message",
        field_mapping={"text": "content", "channel": "channel", "user": "sender"},
    ),
    NormalizationRule(
        rule_id="stripe_payment",
        source_id="stripe_webhook",
        source_event="payment_intent.succeeded",
        normalized_event="payment_completed",
        field_mapping={"data.object.amount": "amount", "data.object.currency": "currency"},
    ),
    NormalizationRule(
        rule_id="jira_issue_created",
        source_id="jira_webhook",
        source_event="jira:issue_created",
        normalized_event="ticket_created",
        field_mapping={"issue.key": "ticket_id", "issue.fields.summary": "title"},
    ),
    NormalizationRule(
        rule_id="jira_issue_updated",
        source_id="jira_webhook",
        source_event="jira:issue_updated",
        normalized_event="ticket_updated",
        field_mapping={"issue.key": "ticket_id", "changelog": "changes"},
    ),
    # ---- Wired Integration Normalization Rules ----
    NormalizationRule(
        rule_id="discord_message",
        source_id="discord_webhook",
        source_event="MESSAGE_CREATE",
        normalized_event="chat_message",
        field_mapping={"content": "content", "channel_id": "channel", "author.username": "sender"},
    ),
    NormalizationRule(
        rule_id="shopify_order_created",
        source_id="shopify_webhook",
        source_event="orders/create",
        normalized_event="order_created",
        field_mapping={"id": "order_id", "total_price": "amount", "currency": "currency", "email": "customer_email"},
    ),
    NormalizationRule(
        rule_id="shopify_order_paid",
        source_id="shopify_webhook",
        source_event="orders/paid",
        normalized_event="payment_completed",
        field_mapping={"id": "order_id", "total_price": "amount", "currency": "currency"},
    ),
    NormalizationRule(
        rule_id="twilio_sms_received",
        source_id="twilio_webhook",
        source_event="received",
        normalized_event="sms_received",
        field_mapping={"From": "sender", "To": "recipient", "Body": "content"},
    ),
    NormalizationRule(
        rule_id="pagerduty_incident_triggered",
        source_id="pagerduty_webhook",
        source_event="incident.triggered",
        normalized_event="incident_created",
        field_mapping={"event.data.id": "incident_id", "event.data.title": "title", "event.data.urgency": "urgency"},
    ),
    NormalizationRule(
        rule_id="pagerduty_incident_resolved",
        source_id="pagerduty_webhook",
        source_event="incident.resolved",
        normalized_event="incident_resolved",
        field_mapping={"event.data.id": "incident_id", "event.data.title": "title"},
    ),
    NormalizationRule(
        rule_id="datadog_alert",
        source_id="datadog_webhook",
        source_event="alert",
        normalized_event="monitoring_alert",
        field_mapping={"title": "title", "alert_type": "severity", "body": "description"},
    ),
    NormalizationRule(
        rule_id="zendesk_ticket_created",
        source_id="zendesk_webhook",
        source_event="ticket_created",
        normalized_event="ticket_created",
        field_mapping={"ticket.id": "ticket_id", "ticket.subject": "title", "ticket.priority": "priority"},
    ),
    NormalizationRule(
        rule_id="zendesk_ticket_updated",
        source_id="zendesk_webhook",
        source_event="ticket_updated",
        normalized_event="ticket_updated",
        field_mapping={"ticket.id": "ticket_id", "ticket.subject": "title", "ticket.status": "status"},
    ),
    NormalizationRule(
        rule_id="sendgrid_email_delivered",
        source_id="sendgrid_webhook",
        source_event="delivered",
        normalized_event="email_delivered",
        field_mapping={"email": "recipient", "sg_message_id": "message_id"},
    ),
    NormalizationRule(
        rule_id="paypal_payment_completed",
        source_id="paypal_webhook",
        source_event="PAYMENT.CAPTURE.COMPLETED",
        normalized_event="payment_completed",
        field_mapping={"resource.id": "payment_id", "resource.amount.value": "amount", "resource.amount.currency_code": "currency"},
    ),
    NormalizationRule(
        rule_id="intercom_conversation_created",
        source_id="intercom_webhook",
        source_event="conversation.user.created",
        normalized_event="conversation_started",
        field_mapping={"data.item.id": "conversation_id", "data.item.user.name": "customer_name"},
    ),
    NormalizationRule(
        rule_id="calendly_event_created",
        source_id="calendly_webhook",
        source_event="invitee.created",
        normalized_event="meeting_scheduled",
        field_mapping={"payload.event": "event_uri", "payload.name": "invitee_name", "payload.email": "invitee_email"},
    ),
    NormalizationRule(
        rule_id="sentry_issue_created",
        source_id="sentry_webhook",
        source_event="created",
        normalized_event="error_detected",
        field_mapping={"data.issue.title": "title", "data.issue.id": "issue_id", "data.issue.level": "severity"},
    ),
    # ---- Additional Wired Integration Normalization Rules ----
    NormalizationRule(
        rule_id="circleci_pipeline_completed",
        source_id="circleci_webhook",
        source_event="pipeline-completed",
        normalized_event="build_completed",
        field_mapping={"pipeline.id": "pipeline_id", "pipeline.vcs.branch": "branch", "project.slug": "project"},
    ),
    NormalizationRule(
        rule_id="docusign_envelope_completed",
        source_id="docusign_webhook",
        source_event="envelope-completed",
        normalized_event="document_signed",
        field_mapping={"envelopeId": "envelope_id", "status": "status", "emailSubject": "subject"},
    ),
    NormalizationRule(
        rule_id="whatsapp_message_received",
        source_id="whatsapp_webhook",
        source_event="whatsapp_business_account",
        normalized_event="chat_message",
        field_mapping={"messaging_product": "platform", "metadata.phone_number_id": "recipient"},
    ),
    NormalizationRule(
        rule_id="telegram_message_received",
        source_id="telegram_webhook",
        source_event="message_update",
        normalized_event="chat_message",
        field_mapping={"message.text": "content", "message.from.username": "sender", "message.chat.id": "channel"},
    ),
    NormalizationRule(
        rule_id="gitlab_push",
        source_id="gitlab_webhook",
        source_event="push",
        normalized_event="code_push",
        field_mapping={"project.path_with_namespace": "repo", "ref": "branch", "user_name": "actor"},
    ),
    NormalizationRule(
        rule_id="gitlab_mr_opened",
        source_id="gitlab_webhook",
        source_event="merge_request",
        normalized_event="pull_request_update",
        field_mapping={"object_attributes.action": "action", "object_attributes.title": "title", "object_attributes.iid": "number"},
    ),
    NormalizationRule(
        rule_id="vercel_deployment_ready",
        source_id="vercel_webhook",
        source_event="deployment.ready",
        normalized_event="deployment_completed",
        field_mapping={"payload.deployment.url": "url", "payload.name": "project", "payload.deployment.meta.githubCommitRef": "branch"},
    ),
    NormalizationRule(
        rule_id="netlify_deploy_succeeded",
        source_id="netlify_webhook",
        source_event="ready",
        normalized_event="deployment_completed",
        field_mapping={"url": "url", "name": "site_name", "branch": "branch"},
    ),
    NormalizationRule(
        rule_id="trello_card_created",
        source_id="trello_webhook",
        source_event="createCard",
        normalized_event="task_created",
        field_mapping={"action.data.card.name": "title", "action.data.card.id": "task_id", "action.data.list.name": "list"},
    ),
    NormalizationRule(
        rule_id="linear_issue_created",
        source_id="linear_webhook",
        source_event="Issue",
        normalized_event="ticket_created",
        field_mapping={"data.id": "ticket_id", "data.title": "title", "data.priority": "priority"},
    ),
    NormalizationRule(
        rule_id="twitch_stream_online",
        source_id="twitch_webhook",
        source_event="stream.online",
        normalized_event="stream_started",
        field_mapping={"event.broadcaster_user_name": "streamer", "event.broadcaster_user_id": "user_id"},
    ),
    NormalizationRule(
        rule_id="resend_email_delivered",
        source_id="resend_webhook",
        source_event="email.delivered",
        normalized_event="email_delivered",
        field_mapping={"data.to": "recipient", "data.email_id": "message_id"},
    ),
    NormalizationRule(
        rule_id="mailgun_email_delivered",
        source_id="mailgun_webhook",
        source_event="delivered",
        normalized_event="email_delivered",
        field_mapping={"event-data.recipient": "recipient", "event-data.message.headers.message-id": "message_id"},
    ),
    # ---- Phase 3 normalization rules ----
    NormalizationRule(
        rule_id="asana_task_changed",
        source_id="asana_webhook",
        source_event="task",
        normalized_event="task_updated",
        field_mapping={"resource.gid": "task_id", "action": "action"},
    ),
    NormalizationRule(
        rule_id="notion_page_updated",
        source_id="notion_webhook",
        source_event="page.updated",
        normalized_event="page_updated",
        field_mapping={"data.id": "page_id", "data.properties.title": "title"},
    ),
    NormalizationRule(
        rule_id="monday_item_created",
        source_id="monday_webhook",
        source_event="create_pulse",
        normalized_event="task_created",
        field_mapping={"event.pulseId": "item_id", "event.pulseName": "item_name", "event.boardId": "board_id"},
    ),
    NormalizationRule(
        rule_id="jenkins_build_completed",
        source_id="jenkins_webhook",
        source_event="COMPLETED",
        normalized_event="build_completed",
        field_mapping={"build.full_url": "build_url", "build.number": "build_number", "name": "job_name"},
    ),
    NormalizationRule(
        rule_id="freshdesk_ticket_created",
        source_id="freshdesk_webhook",
        source_event="ticket_created",
        normalized_event="ticket_created",
        field_mapping={"ticket_id": "ticket_id", "subject": "title", "priority": "priority"},
    ),
    NormalizationRule(
        rule_id="newrelic_alert_triggered",
        source_id="newrelic_webhook",
        source_event="INCIDENT_OPEN",
        normalized_event="alert_triggered",
        field_mapping={"incident_id": "alert_id", "policy_name": "policy", "condition_name": "condition"},
    ),
    NormalizationRule(
        rule_id="woocommerce_order_created",
        source_id="woocommerce_webhook",
        source_event="order.created",
        normalized_event="order_created",
        field_mapping={"id": "order_id", "total": "total", "currency": "currency", "billing.email": "customer_email"},
    ),
    NormalizationRule(
        rule_id="confluence_page_created",
        source_id="confluence_webhook",
        source_event="page_created",
        normalized_event="page_created",
        field_mapping={"page.id": "page_id", "page.title": "title", "page.space.key": "space"},
    ),
    NormalizationRule(
        rule_id="firebase_document_written",
        source_id="firebase_webhook",
        source_event="providers/cloud.firestore/eventTypes/document.write",
        normalized_event="document_updated",
        field_mapping={"resource": "document_path", "timestamp": "updated_at"},
    ),
    NormalizationRule(
        rule_id="linkedin_share_created",
        source_id="linkedin_webhook",
        source_event="SHARE_CREATED",
        normalized_event="post_created",
        field_mapping={"data.share.id": "post_id", "data.share.owner": "author"},
    ),
    NormalizationRule(
        rule_id="mongodb_atlas_alert",
        source_id="mongodb_atlas_webhook",
        source_event="ALERT",
        normalized_event="alert_triggered",
        field_mapping={"alertId": "alert_id", "clusterName": "cluster", "metricName": "metric"},
    ),
    NormalizationRule(
        rule_id="quickbooks_entity_changed",
        source_id="quickbooks_webhook",
        source_event="Invoice",
        normalized_event="invoice_updated",
        field_mapping={"eventNotifications.0.dataChangeEvent.entities.0.id": "entity_id", "eventNotifications.0.dataChangeEvent.entities.0.operation": "operation"},
    ),
    NormalizationRule(
        rule_id="google_workspace_event",
        source_id="google_workspace_webhook",
        source_event="activity",
        normalized_event="workspace_activity",
        field_mapping={"actor.email": "actor_email", "events.0.name": "event_name"},
    ),
    NormalizationRule(
        rule_id="ms_teams_message_received",
        source_id="ms_teams_webhook",
        source_event="message",
        normalized_event="chat_message",
        field_mapping={"from.id": "sender_id", "text": "content", "channelId": "channel"},
    ),
]


class WebhookEventProcessor:
    """Inbound webhook processor with signature verification, normalization, and routing."""

    def __init__(self):
        self._lock = threading.Lock()
        self._sources: Dict[str, WebhookSource] = {}
        self._rules: Dict[str, NormalizationRule] = {}
        self._handlers: Dict[str, List[Callable]] = {}
        self._events: List[WebhookEvent] = []
        self._max_retries: int = 3
        self._register_defaults()

    def _register_defaults(self):
        import copy
        for source in DEFAULT_SOURCES:
            self._sources[source.source_id] = copy.copy(source)
        for rule in DEFAULT_RULES:
            self._rules[rule.rule_id] = copy.copy(rule)

    def register_source(self, source: WebhookSource) -> bool:
        with self._lock:
            self._sources[source.source_id] = source
            return True

    def register_rule(self, rule: NormalizationRule) -> bool:
        with self._lock:
            self._rules[rule.rule_id] = rule
            return True

    def register_handler(self, normalized_event: str, handler: Callable) -> None:
        with self._lock:
            handlers = self._handlers.setdefault(normalized_event, [])
            handlers.append(handler)

    def configure_source_secret(self, source_id: str, secret: str) -> bool:
        source = self._sources.get(source_id)
        if not source:
            return False
        source.secret = secret
        return True

    def verify_signature(self, source: WebhookSource, payload: bytes, signature: str) -> bool:
        if source.signature_algorithm == SignatureAlgorithm.NONE:
            return True
        if not source.secret:
            return True  # No secret configured, skip verification
        if source.signature_algorithm == SignatureAlgorithm.SHA256:
            expected = hmac.new(
                source.secret.encode(),
                payload,
                hashlib.sha256,
            ).hexdigest()
        elif source.signature_algorithm == SignatureAlgorithm.SHA1:
            logger.warning(
                "Webhook source %s uses deprecated SHA1 signature algorithm; "
                "upgrade to SHA256 for stronger security",
                source.source_id,
            )
            expected = hmac.new(
                source.secret.encode(),
                payload,
                hashlib.sha1,
            ).hexdigest()
        elif source.signature_algorithm == SignatureAlgorithm.MD5:
            logger.warning(
                "Webhook source %s uses deprecated MD5 signature algorithm; "
                "upgrade to SHA256 for stronger security",
                source.source_id,
            )
            expected = hmac.new(
                source.secret.encode(),
                payload,
                hashlib.md5,
            ).hexdigest()
        else:
            return True

        # Handle "sha256=" prefix
        if "=" in signature:
            signature = signature.split("=", 1)[1]
        return hmac.compare_digest(expected, signature)

    def _extract_event_type(self, source: WebhookSource, payload: Dict[str, Any], headers: Dict[str, str]) -> str:
        """Extract event type from payload or headers."""
        field = source.event_type_field
        # Check headers first (GitHub uses header-based event types)
        if field in headers:
            return headers[field]
        # Then check payload using dot-notation
        return self._get_nested(payload, field, "unknown")

    def _get_nested(self, data: Dict[str, Any], path: str, default: Any = None) -> Any:
        """Get a nested value using dot notation."""
        parts = path.split(".")
        current = data
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
                if current is None:
                    return default
            else:
                return default
        return current

    def _normalize_payload(self, event_type: str, source_id: str, payload: Dict[str, Any]) -> tuple:
        """Normalize event type and payload using registered rules."""
        for rule in self._rules.values():
            if rule.source_id == source_id and rule.source_event == event_type:
                normalized_payload = {}
                for src_field, dst_field in rule.field_mapping.items():
                    value = self._get_nested(payload, src_field)
                    if value is not None:
                        normalized_payload[dst_field] = value
                return rule.normalized_event, normalized_payload
        return event_type, payload

    def process_webhook(
        self,
        source_id: str,
        payload: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None,
        raw_body: Optional[bytes] = None,
    ) -> WebhookEvent:
        headers = headers or {}
        source = self._sources.get(source_id)

        event_id = hashlib.sha256(
            f"{source_id}:{time.time()}:{json.dumps(payload, default=str)[:200]}".encode()
        ).hexdigest()[:16]

        if not source:
            event = WebhookEvent(
                event_id=event_id,
                source_id=source_id,
                raw_event_type="unknown",
                payload=payload,
                headers=headers,
                status=WebhookStatus.REJECTED,
                error=f"Unknown source: {source_id}",
            )
            with self._lock:
                capped_append(self._events, event)
            return event

        if not source.active:
            event = WebhookEvent(
                event_id=event_id,
                source_id=source_id,
                raw_event_type="unknown",
                payload=payload,
                headers=headers,
                status=WebhookStatus.REJECTED,
                error=f"Source '{source_id}' is disabled",
            )
            with self._lock:
                capped_append(self._events, event)
            return event

        # Verify signature
        if raw_body and source.secret:
            sig_header = source.signature_header
            signature = headers.get(sig_header, "")
            if not self.verify_signature(source, raw_body, signature):
                event = WebhookEvent(
                    event_id=event_id,
                    source_id=source_id,
                    raw_event_type="unknown",
                    payload=payload,
                    headers=headers,
                    status=WebhookStatus.REJECTED,
                    error="Signature verification failed",
                )
                with self._lock:
                    capped_append(self._events, event)
                return event

        # Extract event type
        raw_event_type = self._extract_event_type(source, payload, headers)

        # Normalize
        normalized_event, normalized_payload = self._normalize_payload(
            raw_event_type, source_id, payload
        )

        event = WebhookEvent(
            event_id=event_id,
            source_id=source_id,
            raw_event_type=raw_event_type,
            normalized_event_type=normalized_event,
            payload=payload,
            normalized_payload=normalized_payload,
            headers=headers,
            status=WebhookStatus.VERIFIED,
        )

        # Route to handlers
        handlers = self._handlers.get(normalized_event, [])
        if handlers:
            for handler in handlers:
                try:
                    handler(event)
                except Exception as exc:
                    logger.debug("Caught exception: %s", exc)
                    event.error = str(exc)
                    event.status = WebhookStatus.FAILED
                    with self._lock:
                        capped_append(self._events, event)
                    return event
            event.status = WebhookStatus.PROCESSED
            event.processed_at = time.time()
        else:
            event.status = WebhookStatus.PROCESSED
            event.processed_at = time.time()

        with self._lock:
            capped_append(self._events, event)
        return event

    def get_event(self, event_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            for e in self._events:
                if e.event_id == event_id:
                    return {
                        "event_id": e.event_id,
                        "source_id": e.source_id,
                        "raw_event_type": e.raw_event_type,
                        "normalized_event_type": e.normalized_event_type,
                        "status": e.status.value,
                        "error": e.error,
                        "received_at": e.received_at,
                        "processed_at": e.processed_at,
                    }
            return None

    def list_sources(self) -> List[Dict[str, Any]]:
        return [
            {
                "source_id": s.source_id,
                "name": s.name,
                "platform": s.platform,
                "signature_algorithm": s.signature_algorithm.value,
                "active": s.active,
                "has_secret": bool(s.secret),
            }
            for s in self._sources.values()
        ]

    def get_event_history(self, source_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            events = self._events
            if source_id:
                events = [e for e in events if e.source_id == source_id]
            return [
                {
                    "event_id": e.event_id,
                    "source_id": e.source_id,
                    "raw_event_type": e.raw_event_type,
                    "normalized_event_type": e.normalized_event_type,
                    "status": e.status.value,
                    "received_at": e.received_at,
                }
                for e in events[-limit:]
            ]

    def get_statistics(self) -> Dict[str, Any]:
        with self._lock:
            total = len(self._events)
            processed = sum(1 for e in self._events if e.status == WebhookStatus.PROCESSED)
            rejected = sum(1 for e in self._events if e.status == WebhookStatus.REJECTED)
            failed = sum(1 for e in self._events if e.status == WebhookStatus.FAILED)
            return {
                "total_sources": len(self._sources),
                "active_sources": sum(1 for s in self._sources.values() if s.active),
                "total_rules": len(self._rules),
                "total_handlers": sum(len(h) for h in self._handlers.values()),
                "total_events": total,
                "processed_events": processed,
                "rejected_events": rejected,
                "failed_events": failed,
                "success_rate": processed / max(total, 1),
            }

    def status(self) -> Dict[str, Any]:
        return {
            "module": "webhook_event_processor",
            "statistics": self.get_statistics(),
            "sources": self.list_sources(),
        }
