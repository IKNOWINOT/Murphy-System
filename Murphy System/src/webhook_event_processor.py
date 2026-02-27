"""
Webhook Event Processor — Inbound webhook handling for event-driven
integrations with signature verification, payload normalization,
event routing, and processing pipeline.
"""

import time
import threading
import hashlib
import hmac
import json
from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


class WebhookStatus(Enum):
    RECEIVED = "received"
    VERIFIED = "verified"
    REJECTED = "rejected"
    PROCESSED = "processed"
    FAILED = "failed"
    RETRYING = "retrying"


class SignatureAlgorithm(Enum):
    SHA256 = "sha256"
    SHA1 = "sha1"
    MD5 = "md5"
    NONE = "none"


@dataclass
class WebhookSource:
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
    rule_id: str
    source_id: str
    source_event: str
    normalized_event: str
    field_mapping: Dict[str, str] = field(default_factory=dict)  # source_field -> murphy_field
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WebhookEvent:
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
            expected = hmac.new(
                source.secret.encode(),
                payload,
                hashlib.sha1,
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
                self._events.append(event)
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
                self._events.append(event)
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
                    self._events.append(event)
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
                except Exception as e:
                    event.error = str(e)
                    event.status = WebhookStatus.FAILED
                    with self._lock:
                        self._events.append(event)
                    return event
            event.status = WebhookStatus.PROCESSED
            event.processed_at = time.time()
        else:
            event.status = WebhookStatus.PROCESSED
            event.processed_at = time.time()

        with self._lock:
            self._events.append(event)
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
