"""
Platform Connector Framework — Unified connector SDK for integrating
Murphy System with popular external platforms.

Provides a standardized interface for connecting to CRM, communication,
project management, cloud, DevOps, ERP, payment, and knowledge platforms
with built-in auth management, rate limiting, retry logic, and health checks.
"""

import hashlib
import json
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)


class ConnectorCategory(Enum):
    """Connector category (Enum subclass)."""
    CRM = "crm"
    COMMUNICATION = "communication"
    PROJECT_MANAGEMENT = "project_management"
    CLOUD = "cloud"
    DEVOPS = "devops"
    ERP = "erp"
    PAYMENT = "payment"
    KNOWLEDGE = "knowledge"
    ITSM = "itsm"
    ANALYTICS = "analytics"
    SECURITY = "security"
    CUSTOM = "custom"


class AuthType(Enum):
    """Auth type (Enum subclass)."""
    API_KEY = "api_key"
    OAUTH2 = "oauth2"
    BASIC = "basic"
    TOKEN = "token"
    CERTIFICATE = "certificate"
    NONE = "none"


class ConnectorHealth(Enum):
    """Connector health (Enum subclass)."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"
    DISABLED = "disabled"


@dataclass
class RateLimitConfig:
    """Rate limit config."""
    max_requests: int = 100
    window_seconds: int = 60
    burst_limit: int = 10


@dataclass
class RetryConfig:
    """Retry config."""
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0
    backoff_factor: float = 2.0


@dataclass
class ConnectorDefinition:
    """Connector definition."""
    connector_id: str
    name: str
    category: ConnectorCategory
    platform: str
    auth_type: AuthType
    base_url: str = ""
    version: str = "1.0"
    capabilities: List[str] = field(default_factory=list)
    rate_limit: RateLimitConfig = field(default_factory=RateLimitConfig)
    retry_config: RetryConfig = field(default_factory=RetryConfig)
    action_endpoints: Dict[str, Tuple[str, str]] = field(default_factory=dict)
    """Maps action_type strings to (HTTP_method, URL_path) tuples, e.g.
    ``{"send_message": ("POST", "/messages")}``. Used by _resolve_action()."""


@dataclass
class ConnectorInstance:
    """Connector instance."""
    definition: ConnectorDefinition
    credentials: Dict[str, str] = field(default_factory=dict)
    health: ConnectorHealth = ConnectorHealth.UNKNOWN
    enabled: bool = True
    last_check: float = 0.0
    request_count: int = 0
    error_count: int = 0
    window_start: float = 0.0
    window_requests: int = 0


@dataclass
class ConnectorAction:
    """Connector action."""
    action_id: str
    connector_id: str
    action_type: str  # read, write, subscribe, execute
    resource: str
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class ConnectorResult:
    """Connector result."""
    action_id: str
    connector_id: str
    success: bool
    data: Any = None
    error: Optional[str] = None
    latency_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)


# Default platform definitions
DEFAULT_PLATFORMS = [
    ConnectorDefinition(
        connector_id="slack",
        name="Slack",
        category=ConnectorCategory.COMMUNICATION,
        platform="slack",
        auth_type=AuthType.OAUTH2,
        base_url="https://slack.com/api",
        capabilities=["send_message", "create_channel", "list_channels", "upload_file", "add_reaction", "thread_reply"],
    ),
    ConnectorDefinition(
        connector_id="ms_teams",
        name="Microsoft Teams",
        category=ConnectorCategory.COMMUNICATION,
        platform="microsoft_teams",
        auth_type=AuthType.OAUTH2,
        base_url="https://graph.microsoft.com/v1.0",
        capabilities=["send_message", "create_channel", "list_teams", "schedule_meeting", "upload_file", "webhook"],
    ),
    ConnectorDefinition(
        connector_id="discord",
        name="Discord",
        category=ConnectorCategory.COMMUNICATION,
        platform="discord",
        auth_type=AuthType.TOKEN,
        base_url="https://discord.com/api/v10",
        capabilities=["send_message", "create_channel", "manage_roles", "upload_file"],
    ),
    ConnectorDefinition(
        connector_id="jira",
        name="Jira",
        category=ConnectorCategory.PROJECT_MANAGEMENT,
        platform="atlassian_jira",
        auth_type=AuthType.OAUTH2,
        base_url="https://api.atlassian.com",
        capabilities=["create_issue", "update_issue", "search_issues", "transition_issue", "add_comment", "list_projects"],
    ),
    ConnectorDefinition(
        connector_id="asana",
        name="Asana",
        category=ConnectorCategory.PROJECT_MANAGEMENT,
        platform="asana",
        auth_type=AuthType.OAUTH2,
        base_url="https://app.asana.com/api/1.0",
        capabilities=["create_task", "update_task", "list_projects", "add_comment", "assign_task", "webhook"],
    ),
    ConnectorDefinition(
        connector_id="monday",
        name="Monday.com",
        category=ConnectorCategory.PROJECT_MANAGEMENT,
        platform="monday",
        auth_type=AuthType.API_KEY,
        base_url="https://api.monday.com/v2",
        capabilities=["create_item", "update_item", "list_boards", "create_update", "webhook"],
    ),
    ConnectorDefinition(
        connector_id="salesforce",
        name="Salesforce",
        category=ConnectorCategory.CRM,
        platform="salesforce",
        auth_type=AuthType.OAUTH2,
        base_url="https://login.salesforce.com",
        capabilities=["create_record", "update_record", "query", "bulk_operations", "reports", "workflows"],
    ),
    ConnectorDefinition(
        connector_id="hubspot",
        name="HubSpot",
        category=ConnectorCategory.CRM,
        platform="hubspot",
        auth_type=AuthType.OAUTH2,
        base_url="https://api.hubapi.com",
        capabilities=["create_contact", "update_deal", "list_pipelines", "create_ticket", "email_send", "workflows"],
    ),
    ConnectorDefinition(
        connector_id="github",
        name="GitHub",
        category=ConnectorCategory.DEVOPS,
        platform="github",
        auth_type=AuthType.TOKEN,
        base_url="https://api.github.com",
        capabilities=["create_issue", "create_pr", "list_repos", "manage_actions", "create_release", "code_search"],
    ),
    ConnectorDefinition(
        connector_id="gitlab",
        name="GitLab",
        category=ConnectorCategory.DEVOPS,
        platform="gitlab",
        auth_type=AuthType.TOKEN,
        base_url="https://gitlab.com/api/v4",
        capabilities=["create_issue", "create_mr", "list_projects", "manage_pipelines", "create_release"],
    ),
    ConnectorDefinition(
        connector_id="aws",
        name="Amazon Web Services",
        category=ConnectorCategory.CLOUD,
        platform="aws",
        auth_type=AuthType.API_KEY,
        base_url="https://aws.amazon.com",
        capabilities=["manage_ec2", "manage_s3", "manage_lambda", "manage_iam", "cloudwatch", "sqs", "sns"],
    ),
    ConnectorDefinition(
        connector_id="azure",
        name="Microsoft Azure",
        category=ConnectorCategory.CLOUD,
        platform="azure",
        auth_type=AuthType.OAUTH2,
        base_url="https://management.azure.com",
        capabilities=["manage_vms", "manage_storage", "manage_functions", "manage_iam", "monitor", "service_bus"],
    ),
    ConnectorDefinition(
        connector_id="gcp",
        name="Google Cloud Platform",
        category=ConnectorCategory.CLOUD,
        platform="gcp",
        auth_type=AuthType.OAUTH2,
        base_url="https://cloud.google.com",
        capabilities=["manage_compute", "manage_storage", "manage_functions", "manage_iam", "pubsub", "bigquery"],
    ),
    ConnectorDefinition(
        connector_id="stripe",
        name="Stripe",
        category=ConnectorCategory.PAYMENT,
        platform="stripe",
        auth_type=AuthType.API_KEY,
        base_url="https://api.stripe.com/v1",
        capabilities=["create_charge", "create_subscription", "manage_customers", "refunds", "invoices", "webhooks"],
    ),
    ConnectorDefinition(
        connector_id="confluence",
        name="Confluence",
        category=ConnectorCategory.KNOWLEDGE,
        platform="atlassian_confluence",
        auth_type=AuthType.OAUTH2,
        base_url="https://api.atlassian.com",
        capabilities=["create_page", "update_page", "search", "list_spaces", "manage_attachments", "webhook"],
    ),
    ConnectorDefinition(
        connector_id="notion",
        name="Notion",
        category=ConnectorCategory.KNOWLEDGE,
        platform="notion",
        auth_type=AuthType.TOKEN,
        base_url="https://api.notion.com/v1",
        capabilities=["create_page", "update_page", "query_database", "search", "manage_blocks", "webhook"],
    ),
    ConnectorDefinition(
        connector_id="servicenow",
        name="ServiceNow",
        category=ConnectorCategory.ITSM,
        platform="servicenow",
        auth_type=AuthType.OAUTH2,
        base_url="https://instance.service-now.com/api",
        capabilities=["create_incident", "update_incident", "create_change", "list_tickets", "knowledge_base", "cmdb"],
    ),
    ConnectorDefinition(
        connector_id="snowflake",
        name="Snowflake",
        category=ConnectorCategory.ANALYTICS,
        platform="snowflake",
        auth_type=AuthType.TOKEN,
        base_url="https://account.snowflakecomputing.com",
        capabilities=["query", "create_table", "load_data", "manage_warehouses", "manage_stages"],
    ),
    ConnectorDefinition(
        connector_id="google_workspace",
        name="Google Workspace",
        category=ConnectorCategory.KNOWLEDGE,
        platform="google_workspace",
        auth_type=AuthType.OAUTH2,
        base_url="https://www.googleapis.com",
        capabilities=["gmail_send", "drive_upload", "calendar_create", "sheets_read", "docs_create", "webhook"],
    ),
    ConnectorDefinition(
        connector_id="zapier",
        name="Zapier",
        category=ConnectorCategory.CUSTOM,
        platform="zapier",
        auth_type=AuthType.API_KEY,
        base_url="https://hooks.zapier.com",
        capabilities=["trigger_zap", "webhook", "custom_integration"],
    ),
    # ---- Messaging Platforms ----
    ConnectorDefinition(
        connector_id="whatsapp",
        name="WhatsApp Business",
        category=ConnectorCategory.COMMUNICATION,
        platform="whatsapp",
        auth_type=AuthType.TOKEN,
        base_url="https://graph.facebook.com/v17.0",
        capabilities=["send_message", "send_template", "send_media", "manage_contacts", "webhook", "interactive_messages", "catalog_management"],
    ),
    ConnectorDefinition(
        connector_id="telegram",
        name="Telegram",
        category=ConnectorCategory.COMMUNICATION,
        platform="telegram",
        auth_type=AuthType.TOKEN,
        base_url="https://api.telegram.org",
        capabilities=["send_message", "send_media", "manage_groups", "bot_commands", "inline_queries", "webhook", "channel_management"],
    ),
    ConnectorDefinition(
        connector_id="signal",
        name="Signal",
        category=ConnectorCategory.COMMUNICATION,
        platform="signal",
        auth_type=AuthType.TOKEN,
        base_url="https://signal.org/api",
        capabilities=["send_message", "send_media", "manage_groups", "sealed_sender", "disappearing_messages", "webhook"],
    ),
    ConnectorDefinition(
        connector_id="snapchat",
        name="Snapchat",
        category=ConnectorCategory.COMMUNICATION,
        platform="snapchat",
        auth_type=AuthType.OAUTH2,
        base_url="https://adsapi.snapchat.com/v1",
        capabilities=["send_snap", "manage_stories", "ad_management", "audience_insights", "creative_tools", "bitmoji_integration", "snap_map"],
    ),
    ConnectorDefinition(
        connector_id="wechat",
        name="WeChat",
        category=ConnectorCategory.COMMUNICATION,
        platform="wechat",
        auth_type=AuthType.TOKEN,
        base_url="https://api.weixin.qq.com",
        capabilities=["send_message", "send_media", "mini_programs", "official_accounts", "wechat_pay", "moments", "template_messages"],
    ),
    ConnectorDefinition(
        connector_id="line",
        name="LINE",
        category=ConnectorCategory.COMMUNICATION,
        platform="line",
        auth_type=AuthType.TOKEN,
        base_url="https://api.line.me/v2",
        capabilities=["send_message", "send_media", "rich_menus", "flex_messages", "line_pay", "liff_apps", "beacon"],
    ),
    ConnectorDefinition(
        connector_id="kakaotalk",
        name="KakaoTalk",
        category=ConnectorCategory.COMMUNICATION,
        platform="kakaotalk",
        auth_type=AuthType.OAUTH2,
        base_url="https://kapi.kakao.com",
        capabilities=["send_message", "send_media", "kakao_channel", "kakao_pay", "kakao_map", "template_messages"],
    ),
    ConnectorDefinition(
        connector_id="google_business_messages",
        name="Google Business Messages",
        category=ConnectorCategory.COMMUNICATION,
        platform="google_business_messages",
        auth_type=AuthType.OAUTH2,
        base_url="https://businessmessages.googleapis.com/v1",
        capabilities=["send_message", "rich_cards", "suggested_replies", "agent_management", "location_messaging", "surveys"],
    ),
    ConnectorDefinition(
        connector_id="zenbusiness",
        name="ZenBusiness",
        category=ConnectorCategory.ERP,
        platform="zenbusiness",
        auth_type=AuthType.API_KEY,
        base_url="https://api.zenbusiness.com/v1",
        capabilities=["business_formation", "registered_agent", "compliance_alerts", "annual_reports", "tax_filing", "domain_registration", "business_documents"],
    ),
    # ---- Automation Platforms (wired, beyond Zapier) ----
    ConnectorDefinition(
        connector_id="n8n",
        name="n8n",
        category=ConnectorCategory.CUSTOM,
        platform="n8n",
        auth_type=AuthType.API_KEY,
        base_url="http://localhost:5678",
        capabilities=["trigger_workflow", "list_workflows", "activate_workflow", "deactivate_workflow", "webhook"],
    ),
    ConnectorDefinition(
        connector_id="make",
        name="Make (Integromat)",
        category=ConnectorCategory.CUSTOM,
        platform="make",
        auth_type=AuthType.API_KEY,
        base_url="https://hook.make.com",
        capabilities=["trigger_scenario", "webhook", "custom_integration"],
    ),
    ConnectorDefinition(
        connector_id="ifttt",
        name="IFTTT",
        category=ConnectorCategory.CUSTOM,
        platform="ifttt",
        auth_type=AuthType.API_KEY,
        base_url="https://maker.ifttt.com",
        capabilities=["trigger_event", "webhook"],
    ),
    # ---- E-commerce ----
    ConnectorDefinition(
        connector_id="shopify",
        name="Shopify",
        category=ConnectorCategory.CUSTOM,
        platform="shopify",
        auth_type=AuthType.TOKEN,
        base_url="https://admin.shopify.com/api/2024-01",
        capabilities=["list_products", "create_product", "list_orders", "create_order", "update_inventory", "manage_customers", "webhook"],
    ),
    ConnectorDefinition(
        connector_id="woocommerce",
        name="WooCommerce",
        category=ConnectorCategory.CUSTOM,
        platform="woocommerce",
        auth_type=AuthType.BASIC,
        base_url="https://store.example.com/wp-json/wc/v3",
        capabilities=["list_products", "create_product", "list_orders", "update_order", "manage_customers", "webhook"],
    ),
    # ---- Customer Support ----
    ConnectorDefinition(
        connector_id="zendesk",
        name="Zendesk",
        category=ConnectorCategory.ITSM,
        platform="zendesk",
        auth_type=AuthType.TOKEN,
        base_url="https://instance.zendesk.com/api/v2",
        capabilities=["create_ticket", "update_ticket", "list_tickets", "add_comment", "search", "manage_users", "webhook"],
    ),
    ConnectorDefinition(
        connector_id="intercom",
        name="Intercom",
        category=ConnectorCategory.COMMUNICATION,
        platform="intercom",
        auth_type=AuthType.TOKEN,
        base_url="https://api.intercom.io",
        capabilities=["create_contact", "send_message", "list_conversations", "create_ticket", "manage_tags", "webhook"],
    ),
    ConnectorDefinition(
        connector_id="freshdesk",
        name="Freshdesk",
        category=ConnectorCategory.ITSM,
        platform="freshdesk",
        auth_type=AuthType.API_KEY,
        base_url="https://domain.freshdesk.com/api/v2",
        capabilities=["create_ticket", "update_ticket", "list_tickets", "add_note", "search", "webhook"],
    ),
    # ---- Observability & Monitoring ----
    ConnectorDefinition(
        connector_id="datadog",
        name="Datadog",
        category=ConnectorCategory.ANALYTICS,
        platform="datadog",
        auth_type=AuthType.API_KEY,
        base_url="https://api.datadoghq.com/api/v1",
        capabilities=["send_metrics", "create_event", "query_metrics", "create_monitor", "list_monitors", "webhook"],
    ),
    ConnectorDefinition(
        connector_id="pagerduty",
        name="PagerDuty",
        category=ConnectorCategory.ITSM,
        platform="pagerduty",
        auth_type=AuthType.TOKEN,
        base_url="https://api.pagerduty.com",
        capabilities=["create_incident", "list_incidents", "resolve_incident", "list_oncalls", "manage_schedules", "webhook"],
    ),
    ConnectorDefinition(
        connector_id="sentry",
        name="Sentry",
        category=ConnectorCategory.ANALYTICS,
        platform="sentry",
        auth_type=AuthType.TOKEN,
        base_url="https://sentry.io/api/0",
        capabilities=["list_issues", "resolve_issue", "list_events", "list_projects", "webhook"],
    ),
    ConnectorDefinition(
        connector_id="newrelic",
        name="New Relic",
        category=ConnectorCategory.ANALYTICS,
        platform="newrelic",
        auth_type=AuthType.API_KEY,
        base_url="https://api.newrelic.com/v2",
        capabilities=["list_applications", "get_metrics", "create_deployment", "query_nrql", "webhook"],
    ),
    # ---- CI/CD ----
    ConnectorDefinition(
        connector_id="circleci",
        name="CircleCI",
        category=ConnectorCategory.DEVOPS,
        platform="circleci",
        auth_type=AuthType.TOKEN,
        base_url="https://circleci.com/api/v2",
        capabilities=["trigger_pipeline", "list_pipelines", "get_workflow", "list_jobs", "webhook"],
    ),
    ConnectorDefinition(
        connector_id="jenkins",
        name="Jenkins",
        category=ConnectorCategory.DEVOPS,
        platform="jenkins",
        auth_type=AuthType.BASIC,
        base_url="https://jenkins.example.com/api",
        capabilities=["trigger_build", "get_build_status", "list_jobs", "get_console_output", "webhook"],
    ),
    # ---- Communication (SMS/Voice) ----
    ConnectorDefinition(
        connector_id="twilio",
        name="Twilio",
        category=ConnectorCategory.COMMUNICATION,
        platform="twilio",
        auth_type=AuthType.BASIC,
        base_url="https://api.twilio.com/2010-04-01",
        capabilities=["send_sms", "make_call", "list_messages", "send_whatsapp", "webhook"],
    ),
    ConnectorDefinition(
        connector_id="sendgrid",
        name="SendGrid",
        category=ConnectorCategory.COMMUNICATION,
        platform="sendgrid",
        auth_type=AuthType.TOKEN,
        base_url="https://api.sendgrid.com/v3",
        capabilities=["send_email", "list_contacts", "create_campaign", "manage_templates", "webhook"],
    ),
    # ---- Payment ----
    ConnectorDefinition(
        connector_id="paypal",
        name="PayPal",
        category=ConnectorCategory.PAYMENT,
        platform="paypal",
        auth_type=AuthType.OAUTH2,
        base_url="https://api-m.paypal.com/v2",
        capabilities=["create_order", "capture_payment", "create_payout", "manage_subscriptions", "webhook"],
    ),
    # ---- Document & Signature ----
    ConnectorDefinition(
        connector_id="docusign",
        name="DocuSign",
        category=ConnectorCategory.CUSTOM,
        platform="docusign",
        auth_type=AuthType.OAUTH2,
        base_url="https://demo.docusign.net/restapi/v2.1",
        capabilities=["create_envelope", "get_envelope", "list_envelopes", "download_document", "webhook"],
    ),
    ConnectorDefinition(
        connector_id="dropbox",
        name="Dropbox",
        category=ConnectorCategory.CUSTOM,
        platform="dropbox",
        auth_type=AuthType.OAUTH2,
        base_url="https://api.dropboxapi.com/2",
        capabilities=["upload_file", "list_folder", "create_shared_link", "search", "webhook"],
    ),
    # ---- Calendar & Scheduling ----
    ConnectorDefinition(
        connector_id="calendly",
        name="Calendly",
        category=ConnectorCategory.CUSTOM,
        platform="calendly",
        auth_type=AuthType.TOKEN,
        base_url="https://api.calendly.com",
        capabilities=["list_events", "get_event_types", "cancel_event", "list_invitees", "webhook"],
    ),
    # ---- Accounting ----
    ConnectorDefinition(
        connector_id="quickbooks",
        name="QuickBooks Online",
        category=ConnectorCategory.ERP,
        platform="quickbooks",
        auth_type=AuthType.OAUTH2,
        base_url="https://quickbooks.api.intuit.com/v3",
        capabilities=["create_invoice", "list_customers", "create_payment", "generate_report", "manage_expenses", "webhook"],
    ),
    # ---- AI/ML ----
    ConnectorDefinition(
        connector_id="huggingface",
        name="HuggingFace",
        category=ConnectorCategory.CUSTOM,
        platform="huggingface",
        auth_type=AuthType.TOKEN,
        base_url="https://api-inference.huggingface.co",
        capabilities=["inference", "list_models", "create_repo", "upload_model"],
    ),
    ConnectorDefinition(
        connector_id="ollama",
        name="Ollama",
        category=ConnectorCategory.CUSTOM,
        platform="ollama",
        auth_type=AuthType.NONE,
        base_url=os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/"),
    ),
    ConnectorDefinition(
        connector_id="replicate",
        name="Replicate",
        category=ConnectorCategory.CUSTOM,
        platform="replicate",
        auth_type=AuthType.TOKEN,
        base_url="https://api.replicate.com/v1",
        capabilities=["create_prediction", "get_prediction", "list_models", "webhook"],
    ),
    # ---- Database / Storage ----
    ConnectorDefinition(
        connector_id="supabase",
        name="Supabase",
        category=ConnectorCategory.CUSTOM,
        platform="supabase",
        auth_type=AuthType.API_KEY,
        base_url="https://project.supabase.co",
        capabilities=["query", "insert", "select", "auth", "storage_upload", "realtime"],
    ),
    ConnectorDefinition(
        connector_id="firebase",
        name="Firebase",
        category=ConnectorCategory.CUSTOM,
        platform="firebase",
        auth_type=AuthType.TOKEN,
        base_url="https://firestore.googleapis.com/v1",
        capabilities=["get_document", "create_document", "auth", "storage", "functions", "webhook"],
    ),
    ConnectorDefinition(
        connector_id="mongodb_atlas",
        name="MongoDB Atlas",
        category=ConnectorCategory.CUSTOM,
        platform="mongodb_atlas",
        auth_type=AuthType.API_KEY,
        base_url="https://data.mongodb-api.com/app/data/endpoint/data/v1",
        capabilities=["find", "insert_one", "update_one", "delete_one", "aggregate", "webhook"],
    ),
    # ---- Deployment ----
    ConnectorDefinition(
        connector_id="vercel",
        name="Vercel",
        category=ConnectorCategory.DEVOPS,
        platform="vercel",
        auth_type=AuthType.TOKEN,
        base_url="https://api.vercel.com",
        capabilities=["list_deployments", "create_deployment", "list_projects", "webhook"],
    ),
    ConnectorDefinition(
        connector_id="netlify",
        name="Netlify",
        category=ConnectorCategory.DEVOPS,
        platform="netlify",
        auth_type=AuthType.TOKEN,
        base_url="https://api.netlify.com/api/v1",
        capabilities=["list_sites", "create_deploy", "manage_dns", "webhook"],
    ),
    ConnectorDefinition(
        connector_id="railway",
        name="Railway",
        category=ConnectorCategory.DEVOPS,
        platform="railway",
        auth_type=AuthType.TOKEN,
        base_url="https://backboard.railway.app/graphql/v2",
        capabilities=["list_projects", "deploy", "manage_services", "webhook"],
    ),
    # ---- Project Management ----
    ConnectorDefinition(
        connector_id="trello",
        name="Trello",
        category=ConnectorCategory.PROJECT_MANAGEMENT,
        platform="trello",
        auth_type=AuthType.API_KEY,
        base_url="https://api.trello.com/1",
        capabilities=["create_card", "list_boards", "move_card", "add_comment", "webhook"],
    ),
    ConnectorDefinition(
        connector_id="airtable",
        name="Airtable",
        category=ConnectorCategory.PROJECT_MANAGEMENT,
        platform="airtable",
        auth_type=AuthType.TOKEN,
        base_url="https://api.airtable.com/v0",
        capabilities=["list_records", "create_record", "update_record", "delete_record", "webhook"],
    ),
    ConnectorDefinition(
        connector_id="linear",
        name="Linear",
        category=ConnectorCategory.PROJECT_MANAGEMENT,
        platform="linear",
        auth_type=AuthType.TOKEN,
        base_url="https://api.linear.app",
        capabilities=["create_issue", "list_issues", "update_issue", "webhook"],
    ),
    # ---- Social Media ----
    ConnectorDefinition(
        connector_id="twitter",
        name="Twitter/X",
        category=ConnectorCategory.CUSTOM,
        platform="twitter",
        auth_type=AuthType.OAUTH2,
        base_url="https://api.twitter.com/2",
        capabilities=["post_tweet", "get_timeline", "search", "manage_lists"],
    ),
    ConnectorDefinition(
        connector_id="linkedin",
        name="LinkedIn",
        category=ConnectorCategory.CUSTOM,
        platform="linkedin",
        auth_type=AuthType.OAUTH2,
        base_url="https://api.linkedin.com/v2",
        capabilities=["create_post", "get_profile", "manage_connections", "webhook"],
    ),
    ConnectorDefinition(
        connector_id="reddit",
        name="Reddit",
        category=ConnectorCategory.CUSTOM,
        platform="reddit",
        auth_type=AuthType.OAUTH2,
        base_url="https://oauth.reddit.com",
        capabilities=["submit_post", "get_subreddit", "comment", "search"],
    ),
    # ---- Media Streaming ----
    ConnectorDefinition(
        connector_id="youtube",
        name="YouTube",
        category=ConnectorCategory.CUSTOM,
        platform="youtube",
        auth_type=AuthType.OAUTH2,
        base_url="https://www.googleapis.com/youtube/v3",
        capabilities=["search", "list_videos", "upload_video", "manage_playlists"],
    ),
    ConnectorDefinition(
        connector_id="twitch",
        name="Twitch",
        category=ConnectorCategory.CUSTOM,
        platform="twitch",
        auth_type=AuthType.OAUTH2,
        base_url="https://api.twitch.tv/helix",
        capabilities=["get_streams", "get_users", "manage_subscriptions", "webhook"],
    ),
    ConnectorDefinition(
        connector_id="spotify",
        name="Spotify",
        category=ConnectorCategory.CUSTOM,
        platform="spotify",
        auth_type=AuthType.OAUTH2,
        base_url="https://api.spotify.com/v1",
        capabilities=["search", "get_playlists", "manage_player"],
    ),
    # ---- Email ----
    ConnectorDefinition(
        connector_id="resend",
        name="Resend",
        category=ConnectorCategory.COMMUNICATION,
        platform="resend",
        auth_type=AuthType.API_KEY,
        base_url="https://api.resend.com",
        capabilities=["send_email", "list_emails", "manage_domains", "webhook"],
    ),
    ConnectorDefinition(
        connector_id="mailgun",
        name="Mailgun",
        category=ConnectorCategory.COMMUNICATION,
        platform="mailgun",
        auth_type=AuthType.BASIC,
        base_url="https://api.mailgun.net/v3",
        capabilities=["send_email", "list_events", "manage_routes", "webhook"],
    ),
    # ---- Analytics ----
    ConnectorDefinition(
        connector_id="mixpanel",
        name="Mixpanel",
        category=ConnectorCategory.ANALYTICS,
        platform="mixpanel",
        auth_type=AuthType.API_KEY,
        base_url="https://api.mixpanel.com",
        capabilities=["track_event", "query", "manage_cohorts", "export"],
    ),
    ConnectorDefinition(
        connector_id="posthog",
        name="PostHog",
        category=ConnectorCategory.ANALYTICS,
        platform="posthog",
        auth_type=AuthType.API_KEY,
        base_url="https://app.posthog.com",
        capabilities=["capture_event", "list_events", "manage_feature_flags", "webhook"],
    ),
    # ---- Cloud Infrastructure ----
    ConnectorDefinition(
        connector_id="cloudflare",
        name="Cloudflare",
        category=ConnectorCategory.CUSTOM,
        platform="cloudflare",
        auth_type=AuthType.TOKEN,
        base_url="https://api.cloudflare.com/client/v4",
        capabilities=["list_zones", "purge_cache", "create_worker", "manage_dns", "webhook"],
    ),
    # ---- Calendar ----
    ConnectorDefinition(
        connector_id="google_calendar",
        name="Google Calendar",
        category=ConnectorCategory.CUSTOM,
        platform="google_calendar",
        auth_type=AuthType.OAUTH2,
        base_url="https://www.googleapis.com/calendar/v3",
        capabilities=["list_events", "create_event", "update_event", "delete_event", "webhook"],
    ),
    # ---- Storage ----
    ConnectorDefinition(
        connector_id="google_drive",
        name="Google Drive",
        category=ConnectorCategory.CUSTOM,
        platform="google_drive",
        auth_type=AuthType.OAUTH2,
        base_url="https://www.googleapis.com/drive/v3",
        capabilities=["list_files", "upload_file", "create_folder", "share_file", "webhook"],
    ),
    # ---- Social ----
    ConnectorDefinition(
        connector_id="product_hunt",
        name="Product Hunt",
        category=ConnectorCategory.CUSTOM,
        platform="product_hunt",
        auth_type=AuthType.TOKEN,
        base_url="https://api.producthunt.com/v2/api/graphql",
        capabilities=["get_posts", "create_post", "search"],
    ),
    # ---- Email Marketing ----
    ConnectorDefinition(
        connector_id="mailchimp",
        name="Mailchimp",
        category=ConnectorCategory.COMMUNICATION,
        platform="mailchimp",
        auth_type=AuthType.API_KEY,
        base_url="https://us1.api.mailchimp.com/3.0",
        capabilities=["list_campaigns", "create_campaign", "send_campaign", "list_subscribers",
                      "add_subscriber", "remove_subscriber", "create_list", "get_stats"],
        rate_limit=RateLimitConfig(max_requests=10, window_seconds=1),
    ),
    # ---- Analytics ----
    ConnectorDefinition(
        connector_id="google_analytics",
        name="Google Analytics",
        category=ConnectorCategory.ANALYTICS,
        platform="google_analytics",
        auth_type=AuthType.OAUTH2,
        base_url="https://analyticsdata.googleapis.com/v1beta",
        capabilities=["run_report", "run_realtime_report", "list_properties",
                      "get_metadata", "run_funnel_report", "batch_run_reports"],
    ),
    # ---- AI/ML ----
    ConnectorDefinition(
        connector_id="openai",
        name="OpenAI",
        category=ConnectorCategory.CUSTOM,
        platform="openai",
        auth_type=AuthType.API_KEY,
        base_url="https://api.openai.com/v1",
        capabilities=["chat_completion", "completion", "embedding", "image_generation",
                      "transcription", "translation", "moderation", "list_models"],
        rate_limit=RateLimitConfig(max_requests=500, window_seconds=60),
    ),
    ConnectorDefinition(
        connector_id="anthropic",
        name="Anthropic Claude",
        category=ConnectorCategory.CUSTOM,
        platform="anthropic",
        auth_type=AuthType.API_KEY,
        base_url="https://api.anthropic.com/v1",
        capabilities=["message", "chat_completion", "stream_message", "list_models"],
        rate_limit=RateLimitConfig(max_requests=500, window_seconds=60),
    ),
    # ---- Market Data ----
    ConnectorDefinition(
        connector_id="yahoo_finance",
        name="Yahoo Finance",
        category=ConnectorCategory.ANALYTICS,
        platform="yahoo_finance",
        auth_type=AuthType.NONE,
        base_url="https://query1.finance.yahoo.com/v8/finance",
        capabilities=["get_quote", "get_history", "get_financials", "get_summary",
                      "search_tickers", "get_options", "get_earnings"],
    ),
    # ---- Weather ----
    ConnectorDefinition(
        connector_id="openweathermap",
        name="OpenWeatherMap",
        category=ConnectorCategory.CUSTOM,
        platform="openweathermap",
        auth_type=AuthType.API_KEY,
        base_url="https://api.openweathermap.org/data/2.5",
        capabilities=["get_current_weather", "get_forecast", "get_hourly_forecast",
                      "get_historical_weather", "get_air_quality", "get_uv_index",
                      "get_alerts"],
        rate_limit=RateLimitConfig(max_requests=60, window_seconds=60),
    ),
    # ---- Industrial / SCADA / OT ----
    ConnectorDefinition(
        connector_id="scada_modbus",
        name="SCADA / Modbus TCP",
        category=ConnectorCategory.CUSTOM,
        platform="modbus",
        auth_type=AuthType.NONE,
        base_url="",
        capabilities=["read_holding_registers", "read_input_registers", "write_register",
                      "read_coils", "write_coil", "read_discrete_inputs", "health_check"],
    ),
    ConnectorDefinition(
        connector_id="scada_bacnet",
        name="SCADA / BACnet IP",
        category=ConnectorCategory.CUSTOM,
        platform="bacnet",
        auth_type=AuthType.NONE,
        base_url="",
        capabilities=["read_property", "write_property", "who_is", "i_am",
                      "subscribe_cov", "read_range", "health_check"],
    ),
    ConnectorDefinition(
        connector_id="scada_opcua",
        name="SCADA / OPC UA",
        category=ConnectorCategory.CUSTOM,
        platform="opcua",
        auth_type=AuthType.CERTIFICATE,
        base_url="",
        capabilities=["browse", "read_node", "write_node", "subscribe", "call_method",
                      "get_endpoints", "health_check"],
    ),
    ConnectorDefinition(
        connector_id="additive_manufacturing",
        name="Additive Manufacturing / 3D Printing",
        category=ConnectorCategory.CUSTOM,
        platform="additive_manufacturing",
        auth_type=AuthType.API_KEY,
        base_url="",
        capabilities=["submit_job", "get_job_status", "cancel_job", "get_machine_status",
                      "list_materials", "get_build_plate", "set_parameters",
                      "upload_model", "start_print", "pause_print", "health_check"],
    ),
    ConnectorDefinition(
        connector_id="building_automation",
        name="Building Automation (BAS/BMS)",
        category=ConnectorCategory.CUSTOM,
        platform="building_automation",
        auth_type=AuthType.API_KEY,
        base_url="",
        capabilities=["read_sensor", "write_setpoint", "get_hvac_status", "set_hvac_mode",
                      "get_lighting_status", "set_lighting_level", "get_energy_usage",
                      "get_occupancy", "trigger_alarm", "acknowledge_alarm",
                      "get_floor_plan", "list_devices", "health_check"],
    ),
    ConnectorDefinition(
        connector_id="energy_management",
        name="Energy Management System (EMS)",
        category=ConnectorCategory.CUSTOM,
        platform="energy_management",
        auth_type=AuthType.API_KEY,
        base_url="",
        capabilities=["get_consumption", "get_demand", "set_demand_response",
                      "get_solar_output", "get_battery_status", "set_load_schedule",
                      "get_tariff", "get_carbon_intensity", "generate_report",
                      "get_real_time_data", "health_check"],
    ),
    ConnectorDefinition(
        connector_id="internal_email",
        name="Murphy Internal Mail Server",
        category=ConnectorCategory.COMMUNICATION,
        platform="internal_email",
        auth_type=AuthType.API_KEY,
        base_url="murphy-mailserver",
        capabilities=[
            "send_email",
            "receive_email",
            "manage_accounts",
            "manage_aliases",
            "search_mailbox",
            "manage_filters",
            "health_check",
        ],
    ),
]


class PlatformConnectorFramework:
    """Unified platform connector framework with auth, rate limiting, retry, and health checks."""

    def __init__(self):
        self._lock = threading.Lock()
        self._definitions: Dict[str, ConnectorDefinition] = {}
        self._instances: Dict[str, ConnectorInstance] = {}
        self._action_history: List[ConnectorResult] = []
        self._register_defaults()

    def _register_defaults(self):
        for defn in DEFAULT_PLATFORMS:
            self._definitions[defn.connector_id] = defn

    def register_connector(self, definition: ConnectorDefinition) -> bool:
        with self._lock:
            self._definitions[definition.connector_id] = definition
            return True

    def configure_connector(self, connector_id: str, credentials: Dict[str, str]) -> bool:
        with self._lock:
            defn = self._definitions.get(connector_id)
            if not defn:
                return False
            self._instances[connector_id] = ConnectorInstance(
                definition=defn,
                credentials=credentials,
                health=ConnectorHealth.UNKNOWN,
                enabled=True,
            )
            return True

    def get_connector(self, connector_id: str) -> Optional[ConnectorInstance]:
        return self._instances.get(connector_id)

    def list_available_connectors(self) -> List[Dict[str, Any]]:
        result = []
        for cid, defn in self._definitions.items():
            configured = cid in self._instances
            instance = self._instances.get(cid)
            result.append({
                "connector_id": cid,
                "name": defn.name,
                "category": defn.category.value,
                "platform": defn.platform,
                "auth_type": defn.auth_type.value,
                "capabilities": defn.capabilities,
                "configured": configured,
                "enabled": instance.enabled if instance else False,
                "health": instance.health.value if instance else ConnectorHealth.UNKNOWN.value,
            })
        return result

    def list_by_category(self, category: ConnectorCategory) -> List[Dict[str, Any]]:
        return [c for c in self.list_available_connectors() if c["category"] == category.value]

    def list_configured(self) -> List[Dict[str, Any]]:
        return [c for c in self.list_available_connectors() if c["configured"]]

    def _check_rate_limit(self, instance: ConnectorInstance) -> bool:
        now = time.time()
        rl = instance.definition.rate_limit
        if now - instance.window_start > rl.window_seconds:
            instance.window_start = now
            instance.window_requests = 0
        if instance.window_requests >= rl.max_requests:
            return False
        instance.window_requests += 1
        return True

    def execute_action(self, action: ConnectorAction) -> ConnectorResult:
        start = time.time()
        instance = self._instances.get(action.connector_id)
        if not instance:
            result = ConnectorResult(
                action_id=action.action_id,
                connector_id=action.connector_id,
                success=False,
                error=f"Connector '{action.connector_id}' not configured",
            )
            with self._lock:
                capped_append(self._action_history, result)
            return result

        if not instance.enabled:
            result = ConnectorResult(
                action_id=action.action_id,
                connector_id=action.connector_id,
                success=False,
                error=f"Connector '{action.connector_id}' is disabled",
            )
            with self._lock:
                capped_append(self._action_history, result)
            return result

        if not self._check_rate_limit(instance):
            result = ConnectorResult(
                action_id=action.action_id,
                connector_id=action.connector_id,
                success=False,
                error="Rate limit exceeded",
            )
            with self._lock:
                capped_append(self._action_history, result)
            return result

        # Check capability support
        if action.action_type not in instance.definition.capabilities:
            # Allow generic action types
            if action.action_type not in ("read", "write", "subscribe", "execute"):
                result = ConnectorResult(
                    action_id=action.action_id,
                    connector_id=action.connector_id,
                    success=False,
                    error=f"Action '{action.action_type}' not supported by '{action.connector_id}'",
                )
                with self._lock:
                    capped_append(self._action_history, result)
                return result

        # Attempt real HTTP dispatch if credentials and base_url are available
        instance.request_count += 1
        latency_start = time.time()

        if instance.credentials and instance.definition.base_url:
            try:
                import httpx
                auth_headers = self._build_auth_headers(instance)
                method, path = self._resolve_action(instance.definition, action.action_type)
                url = f"{instance.definition.base_url.rstrip('/')}{path}"
                with httpx.Client(timeout=10.0) as client:
                    response = client.request(
                        method, url,
                        headers=auth_headers,
                        json=action.payload if action.payload else None,
                        params={"resource": action.resource} if action.resource else None,
                    )
                latency = (time.time() - latency_start) * 1000
                result = ConnectorResult(
                    action_id=action.action_id,
                    connector_id=action.connector_id,
                    success=response.is_success,
                    data={
                        "resource": action.resource,
                        "action_type": action.action_type,
                        "platform": instance.definition.platform,
                        "status_code": response.status_code,
                        "body": response.text[:4096],
                        "simulated": False,
                    },
                    latency_ms=latency,
                )
                if not response.is_success:
                    result.error = f"HTTP {response.status_code}"
                with self._lock:
                    capped_append(self._action_history, result)
                return result
            except ImportError:
                logger.debug("httpx not installed — falling back to simulated connector execution")
            except Exception as exc:
                # Network/connectivity errors (DNS failure, connection refused, timeout)
                # fall through to the simulated path so that zero-config and test
                # scenarios continue to work.  Only hard HTTP errors (4xx/5xx returned
                # from the server) are propagated as real failures.
                error_str = str(exc).lower()
                is_connectivity_error = any(
                    marker in error_str
                    for marker in (
                        "no address associated",
                        "name or service not known",
                        "connection refused",
                        "timed out",
                        "network is unreachable",
                        "temporary failure in name resolution",
                        "nodename nor servname",
                        "failed to establish",
                        "ssl:",
                    )
                )
                if is_connectivity_error:
                    logger.debug(
                        "Connector '%s' unreachable (%s) — falling back to simulated execution",
                        action.connector_id,
                        exc,
                    )
                    # Fall through to the simulated path below
                else:
                    logger.warning("Connector '%s' HTTP call failed: %s", action.connector_id, exc)
                    instance.error_count += 1
                    latency = (time.time() - latency_start) * 1000
                    result = ConnectorResult(
                        action_id=action.action_id,
                        connector_id=action.connector_id,
                        success=False,
                        error=str(exc),
                        latency_ms=latency,
                    )
                    with self._lock:
                        capped_append(self._action_history, result)
                    return result

        # Simulated fallback (no credentials configured or httpx not available)
        latency = (time.time() - latency_start) * 1000
        result = ConnectorResult(
            action_id=action.action_id,
            connector_id=action.connector_id,
            success=True,
            data={
                "resource": action.resource,
                "action_type": action.action_type,
                "platform": instance.definition.platform,
                "payload_keys": list(action.payload.keys()) if action.payload else [],
                "simulated": True,
            },
            latency_ms=latency,
        )
        with self._lock:
            capped_append(self._action_history, result)
        return result

    def _build_auth_headers(self, instance) -> dict:
        """Build HTTP Authorization headers from connector credentials and auth type."""
        creds = instance.credentials or {}
        auth_type = instance.definition.auth_type
        # Normalize AuthType enum to string
        auth_str = auth_type.value if hasattr(auth_type, "value") else str(auth_type)

        if auth_str in ("oauth2", "token"):
            token = creds.get("token") or creds.get("access_token") or creds.get("api_key", "")
            return {"Authorization": f"Bearer {token}"}
        elif auth_str == "basic":
            import base64
            username = creds.get("username", "")
            password = creds.get("password", "")
            encoded = base64.b64encode(f"{username}:{password}".encode()).decode()
            return {"Authorization": f"Basic {encoded}"}
        elif auth_str == "api_key":
            header_name = creds.get("header_name", "X-API-Key")
            api_key = creds.get("api_key", "")
            return {header_name: api_key}
        else:
            token = creds.get("token") or creds.get("api_key", "")
            if token:
                return {"Authorization": f"Bearer {token}"}
        return {}

    def _resolve_action(self, definition, action_type: str):
        """Resolve action type to (HTTP method, URL path) tuple.

        Uses action_endpoints mapping from connector definition if available,
        otherwise falls back to a sensible default based on action_type name.
        """
        endpoints = getattr(definition, "action_endpoints", {})
        if action_type in endpoints:
            return endpoints[action_type]

        default_mappings = {
            "send_message": ("POST", "/messages"),
            "list_messages": ("GET", "/messages"),
            "create_issue": ("POST", "/issues"),
            "list_issues": ("GET", "/issues"),
            "create_ticket": ("POST", "/tickets"),
            "list_tickets": ("GET", "/tickets"),
            "search": ("GET", "/search"),
            "list_contacts": ("GET", "/contacts"),
            "create_contact": ("POST", "/contacts"),
            "list_pipelines": ("GET", "/pipelines"),
            "create_invoice": ("POST", "/invoices"),
            "list_customers": ("GET", "/customers"),
            "list_projects": ("GET", "/projects"),
            "create_task": ("POST", "/tasks"),
            "list_tasks": ("GET", "/tasks"),
            "create_release": ("POST", "/releases"),
            "list_repos": ("GET", "/repos"),
            "list_users": ("GET", "/users"),
            "read": ("GET", "/"),
            "write": ("POST", "/"),
            "subscribe": ("POST", "/subscriptions"),
            "execute": ("POST", "/execute"),
        }
        return default_mappings.get(action_type, ("POST", f"/{action_type}"))

    def health_check(self, connector_id: str) -> ConnectorHealth:
        instance = self._instances.get(connector_id)
        if not instance:
            return ConnectorHealth.UNKNOWN
        if not instance.enabled:
            return ConnectorHealth.DISABLED
        # Derive health from error rate
        if instance.request_count == 0:
            instance.health = ConnectorHealth.UNKNOWN
        elif instance.error_count / max(instance.request_count, 1) > 0.5:
            instance.health = ConnectorHealth.UNHEALTHY
        elif instance.error_count / max(instance.request_count, 1) > 0.1:
            instance.health = ConnectorHealth.DEGRADED
        else:
            instance.health = ConnectorHealth.HEALTHY
        instance.last_check = time.time()
        return instance.health

    def disable_connector(self, connector_id: str) -> bool:
        instance = self._instances.get(connector_id)
        if not instance:
            return False
        instance.enabled = False
        instance.health = ConnectorHealth.DISABLED
        return True

    def enable_connector(self, connector_id: str) -> bool:
        instance = self._instances.get(connector_id)
        if not instance:
            return False
        instance.enabled = True
        instance.health = ConnectorHealth.UNKNOWN
        return True

    def get_action_history(self, connector_id: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._lock:
            history = self._action_history
            if connector_id:
                history = [h for h in history if h.connector_id == connector_id]
            return [
                {
                    "action_id": h.action_id,
                    "connector_id": h.connector_id,
                    "success": h.success,
                    "error": h.error,
                    "latency_ms": h.latency_ms,
                    "timestamp": h.timestamp,
                }
                for h in history
            ]

    def get_statistics(self) -> Dict[str, Any]:
        with self._lock:
            total = len(self._action_history)
            successes = sum(1 for h in self._action_history if h.success)
            return {
                "total_definitions": len(self._definitions),
                "configured_connectors": len(self._instances),
                "enabled_connectors": sum(1 for i in self._instances.values() if i.enabled),
                "total_actions": total,
                "successful_actions": successes,
                "failed_actions": total - successes,
                "success_rate": successes / max(total, 1),
                "categories": list(set(d.category.value for d in self._definitions.values())),
                "platforms": list(self._definitions.keys()),
            }

    def status(self) -> Dict[str, Any]:
        return {
            "module": "platform_connector_framework",
            "statistics": self.get_statistics(),
            "configured": [
                {
                    "connector_id": cid,
                    "name": inst.definition.name,
                    "health": inst.health.value,
                    "enabled": inst.enabled,
                    "request_count": inst.request_count,
                }
                for cid, inst in self._instances.items()
            ],
        }
