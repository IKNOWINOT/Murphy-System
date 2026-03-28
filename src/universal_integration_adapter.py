"""
Universal Integration Adapter — Murphy System

Provides a plug-and-play framework for connecting **any** external service,
API, webhook, database, message queue, or protocol to Murphy System.

Users define an ``IntegrationSpec`` (service name, auth method, base URL,
available actions) and the adapter handles:

  - Credential management (API key, OAuth, basic, certificate, custom headers)
  - Rate limiting (per-service, configurable window)
  - Retry with exponential backoff
  - Health checks
  - Action execution with timeout
  - Event-driven webhook ingestion
  - Thread-safe registry

Pre-loaded with 80+ common integration templates (Slack, Discord, Notion,
Airtable, Zapier, IFTTT, n8n, Make, Vercel, Netlify, Supabase, Firebase,
Cloudflare, Twitch, YouTube, Spotify, Salesforce, HubSpot, Stripe, PayPal,
Shopify, Zendesk, Datadog, PagerDuty, Sentry, Twilio, SendGrid, etc.).

Design Label: INT-002
Thread-safe: Yes
Persistence: Optional (logs to ``.murphy_persistence/integrations/``)

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

import enum
import json
import logging
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
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


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class IntegrationAuthMethod(enum.Enum):
    """Supported authentication methods."""
    NONE = "none"
    API_KEY = "api_key"
    BEARER_TOKEN = "bearer_token"
    OAUTH2 = "oauth2"
    BASIC_AUTH = "basic_auth"
    CERTIFICATE = "certificate"
    CUSTOM_HEADER = "custom_header"
    WEBHOOK_SECRET = "webhook_secret"


class IntegrationCategory(enum.Enum):
    """Service categories for organisation and discovery."""
    COMMUNICATION = "communication"
    PROJECT_MANAGEMENT = "project_management"
    CRM = "crm"
    STORAGE = "storage"
    DATABASE = "database"
    ANALYTICS = "analytics"
    AUTOMATION = "automation"
    DEPLOYMENT = "deployment"
    MONITORING = "monitoring"
    SOCIAL_MEDIA = "social_media"
    MEDIA_STREAMING = "media_streaming"
    PAYMENT = "payment"
    EMAIL = "email"
    AI_ML = "ai_ml"
    DEVELOPER_TOOLS = "developer_tools"
    CLOUD_INFRASTRUCTURE = "cloud_infrastructure"
    CUSTOM = "custom"
    WEBSITE_BUILDER = "website_builder"


class IntegrationStatus(enum.Enum):
    """Health/status of an integration."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"
    DISABLED = "disabled"
    NOT_CONFIGURED = "not_configured"


class ActionStatus(enum.Enum):
    """Status of an executed action."""
    SUCCESS = "success"
    FAILED = "failed"
    RATE_LIMITED = "rate_limited"
    TIMEOUT = "timeout"
    AUTH_ERROR = "auth_error"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class IntegrationAction:
    """Describes one action an integration supports."""
    name: str
    description: str = ""
    method: str = "POST"
    endpoint: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    requires_auth: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "method": self.method,
            "endpoint": self.endpoint,
            "parameters": self.parameters,
            "requires_auth": self.requires_auth,
        }


@dataclass
class IntegrationSpec:
    """Complete specification for an external service integration."""
    service_id: str = ""
    name: str = ""
    category: IntegrationCategory = IntegrationCategory.CUSTOM
    description: str = ""
    base_url: str = ""
    auth_method: IntegrationAuthMethod = IntegrationAuthMethod.API_KEY
    auth_config: Dict[str, str] = field(default_factory=dict)
    actions: List[IntegrationAction] = field(default_factory=list)
    rate_limit: Dict[str, int] = field(default_factory=lambda: {
        "requests_per_minute": 60,
        "burst_limit": 10,
    })
    webhook_url: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.service_id:
            self.service_id = self.name.lower().replace(" ", "_").replace("-", "_")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "service_id": self.service_id,
            "name": self.name,
            "category": self.category.value,
            "description": self.description,
            "base_url": self.base_url,
            "auth_method": self.auth_method.value,
            "actions": [a.to_dict() for a in self.actions],
            "rate_limit": self.rate_limit,
            "webhook_url": self.webhook_url,
            "metadata": self.metadata,
        }


@dataclass
class ActionResult:
    """Result of executing an integration action."""
    action_name: str = ""
    service_id: str = ""
    status: ActionStatus = ActionStatus.SUCCESS
    response_data: Any = None
    error: Optional[str] = None
    latency_seconds: float = 0.0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_name": self.action_name,
            "service_id": self.service_id,
            "status": self.status.value,
            "response_data": self.response_data,
            "error": self.error,
            "latency_seconds": self.latency_seconds,
            "timestamp": self.timestamp,
        }


# ---------------------------------------------------------------------------
# Integration instance (runtime state)
# ---------------------------------------------------------------------------

class _IntegrationInstance:
    """Runtime state for a registered integration."""

    def __init__(self, spec: IntegrationSpec):
        self.spec = spec
        self.status = IntegrationStatus.NOT_CONFIGURED
        self.credentials: Dict[str, str] = {}
        self.request_count = 0
        self.error_count = 0
        self.window_start = time.time()
        self.window_requests = 0
        self.action_log: List[Dict[str, Any]] = []
        self.custom_handlers: Dict[str, Callable] = {}
        self.enabled = True

    def configure(self, credentials: Dict[str, str]) -> None:
        self.credentials = dict(credentials)
        self.status = IntegrationStatus.UNKNOWN

    def health_check(self) -> Dict[str, Any]:
        if not self.enabled:
            self.status = IntegrationStatus.DISABLED
        elif not self.credentials and self.spec.auth_method != IntegrationAuthMethod.NONE:
            self.status = IntegrationStatus.NOT_CONFIGURED
        elif self.request_count == 0:
            self.status = IntegrationStatus.UNKNOWN
        else:
            error_rate = self.error_count / max(self.request_count, 1)
            if error_rate > 0.5:
                self.status = IntegrationStatus.UNHEALTHY
            elif error_rate > 0.1:
                self.status = IntegrationStatus.DEGRADED
            else:
                self.status = IntegrationStatus.HEALTHY
        return {
            "service_id": self.spec.service_id,
            "name": self.spec.name,
            "status": self.status.value,
            "enabled": self.enabled,
            "configured": bool(self.credentials) or self.spec.auth_method == IntegrationAuthMethod.NONE,
            "request_count": self.request_count,
            "error_count": self.error_count,
        }

    def check_rate_limit(self) -> bool:
        now = time.time()
        window = 60.0
        if now - self.window_start > window:
            self.window_start = now
            self.window_requests = 0
        rpm = self.spec.rate_limit.get("requests_per_minute", 60)
        return self.window_requests < rpm

    def record_request(self, success: bool) -> None:
        self.request_count += 1
        self.window_requests += 1
        if not success:
            self.error_count += 1

    def register_handler(self, action_name: str, handler: Callable) -> None:
        self.custom_handlers[action_name] = handler

    def execute_action(
        self, action_name: str, params: Optional[Dict[str, Any]] = None
    ) -> ActionResult:
        params = params or {}
        start = time.time()

        if not self.enabled:
            return ActionResult(
                action_name=action_name,
                service_id=self.spec.service_id,
                status=ActionStatus.FAILED,
                error="Integration is disabled",
            )

        if not self.check_rate_limit():
            self.record_request(False)
            return ActionResult(
                action_name=action_name,
                service_id=self.spec.service_id,
                status=ActionStatus.RATE_LIMITED,
                error="Rate limit exceeded",
            )

        # Custom handler takes priority
        if action_name in self.custom_handlers:
            try:
                result_data = self.custom_handlers[action_name](params, self.credentials)
                self.record_request(True)
                return ActionResult(
                    action_name=action_name,
                    service_id=self.spec.service_id,
                    status=ActionStatus.SUCCESS,
                    response_data=result_data,
                    latency_seconds=time.time() - start,
                )
            except Exception as exc:
                logger.debug("Caught exception: %s", exc)
                self.record_request(False)
                return ActionResult(
                    action_name=action_name,
                    service_id=self.spec.service_id,
                    status=ActionStatus.FAILED,
                    error=str(exc),
                    latency_seconds=time.time() - start,
                )

        # Default: simulate action execution (real HTTP would go here)
        action_spec = None
        for a in self.spec.actions:
            if a.name == action_name:
                action_spec = a
                break

        if action_spec is None:
            self.record_request(False)
            return ActionResult(
                action_name=action_name,
                service_id=self.spec.service_id,
                status=ActionStatus.FAILED,
                error=f"Unknown action '{action_name}' for service '{self.spec.name}'",
                latency_seconds=time.time() - start,
            )

        # Check auth
        if action_spec.requires_auth and not self.credentials and self.spec.auth_method != IntegrationAuthMethod.NONE:
            self.record_request(False)
            return ActionResult(
                action_name=action_name,
                service_id=self.spec.service_id,
                status=ActionStatus.AUTH_ERROR,
                error="Credentials not configured",
                latency_seconds=time.time() - start,
            )

        self.record_request(True)
        return ActionResult(
            action_name=action_name,
            service_id=self.spec.service_id,
            status=ActionStatus.SUCCESS,
            response_data={
                "message": f"Action '{action_name}' executed on '{self.spec.name}'",
                "endpoint": f"{self.spec.base_url}{action_spec.endpoint}",
                "method": action_spec.method,
                "params": params,
            },
            latency_seconds=time.time() - start,
        )


# ---------------------------------------------------------------------------
# Default integration templates
# ---------------------------------------------------------------------------

def _default_integration_templates() -> List[IntegrationSpec]:
    """Pre-loaded templates for 80+ common services."""
    return [
        # --- Communication ---
        IntegrationSpec(
            name="Slack", category=IntegrationCategory.COMMUNICATION,
            description="Team messaging and workflow automation",
            base_url="https://slack.com/api",
            auth_method=IntegrationAuthMethod.BEARER_TOKEN,
            actions=[
                IntegrationAction("send_message", "Send a message to a channel", "POST", "/chat.postMessage"),
                IntegrationAction("list_channels", "List available channels", "GET", "/conversations.list"),
                IntegrationAction("upload_file", "Upload a file to a channel", "POST", "/files.upload"),
            ],
        ),
        IntegrationSpec(
            name="Discord", category=IntegrationCategory.COMMUNICATION,
            description="Community chat and bot integration",
            base_url="https://discord.com/api/v10",
            auth_method=IntegrationAuthMethod.BEARER_TOKEN,
            actions=[
                IntegrationAction("send_message", "Send a message to a channel", "POST", "/channels/{channel_id}/messages"),
                IntegrationAction("create_channel", "Create a new channel", "POST", "/guilds/{guild_id}/channels"),
                IntegrationAction("list_members", "List guild members", "GET", "/guilds/{guild_id}/members"),
            ],
        ),
        IntegrationSpec(
            service_id="ms_teams",
            name="Microsoft Teams", category=IntegrationCategory.COMMUNICATION,
            description="Enterprise team collaboration",
            base_url="https://graph.microsoft.com/v1.0",
            auth_method=IntegrationAuthMethod.OAUTH2,
            actions=[
                IntegrationAction("send_message", "Send a message to a channel", "POST", "/teams/{team_id}/channels/{channel_id}/messages"),
                IntegrationAction("list_teams", "List teams", "GET", "/me/joinedTeams"),
            ],
        ),
        # --- Project Management ---
        IntegrationSpec(
            name="Notion", category=IntegrationCategory.PROJECT_MANAGEMENT,
            description="All-in-one workspace for notes, tasks, and databases",
            base_url="https://api.notion.com/v1",
            auth_method=IntegrationAuthMethod.BEARER_TOKEN,
            actions=[
                IntegrationAction("create_page", "Create a new page", "POST", "/pages"),
                IntegrationAction("query_database", "Query a database", "POST", "/databases/{database_id}/query"),
                IntegrationAction("search", "Search across workspace", "POST", "/search"),
            ],
        ),
        IntegrationSpec(
            name="Airtable", category=IntegrationCategory.PROJECT_MANAGEMENT,
            description="Spreadsheet-database hybrid for project tracking",
            base_url="https://api.airtable.com/v0",
            auth_method=IntegrationAuthMethod.BEARER_TOKEN,
            actions=[
                IntegrationAction("list_records", "List records in a table", "GET", "/{base_id}/{table_name}"),
                IntegrationAction("create_record", "Create a new record", "POST", "/{base_id}/{table_name}"),
                IntegrationAction("update_record", "Update a record", "PATCH", "/{base_id}/{table_name}/{record_id}"),
            ],
        ),
        IntegrationSpec(
            name="Linear", category=IntegrationCategory.PROJECT_MANAGEMENT,
            description="Modern issue tracking for software teams",
            base_url="https://api.linear.app",
            auth_method=IntegrationAuthMethod.BEARER_TOKEN,
            actions=[
                IntegrationAction("create_issue", "Create a new issue", "POST", "/graphql"),
                IntegrationAction("list_issues", "List issues", "POST", "/graphql"),
            ],
        ),
        IntegrationSpec(
            name="Trello", category=IntegrationCategory.PROJECT_MANAGEMENT,
            description="Visual project management with boards and cards",
            base_url="https://api.trello.com/1",
            auth_method=IntegrationAuthMethod.API_KEY,
            actions=[
                IntegrationAction("create_card", "Create a new card", "POST", "/cards"),
                IntegrationAction("list_boards", "List boards", "GET", "/members/me/boards"),
            ],
        ),
        # --- Automation ---
        IntegrationSpec(
            name="Zapier", category=IntegrationCategory.AUTOMATION,
            description="No-code workflow automation between 5000+ apps",
            base_url="https://hooks.zapier.com",
            auth_method=IntegrationAuthMethod.WEBHOOK_SECRET,
            actions=[
                IntegrationAction("trigger_zap", "Trigger a Zapier webhook", "POST", "/hooks/catch/{zap_id}"),
            ],
        ),
        IntegrationSpec(
            name="n8n", category=IntegrationCategory.AUTOMATION,
            description="Open-source workflow automation (self-hosted)",
            base_url="http://localhost:5678",
            auth_method=IntegrationAuthMethod.API_KEY,
            actions=[
                IntegrationAction("trigger_workflow", "Trigger a workflow", "POST", "/api/v1/workflows/{workflow_id}/activate"),
                IntegrationAction("list_workflows", "List workflows", "GET", "/api/v1/workflows"),
            ],
        ),
        IntegrationSpec(
            service_id="make",
            name="Make (Integromat)", category=IntegrationCategory.AUTOMATION,
            description="Visual automation platform",
            base_url="https://hook.make.com",
            auth_method=IntegrationAuthMethod.WEBHOOK_SECRET,
            actions=[
                IntegrationAction("trigger_scenario", "Trigger a scenario webhook", "POST", "/{scenario_id}"),
            ],
        ),
        IntegrationSpec(
            name="IFTTT", category=IntegrationCategory.AUTOMATION,
            description="Simple conditional automation",
            base_url="https://maker.ifttt.com",
            auth_method=IntegrationAuthMethod.API_KEY,
            actions=[
                IntegrationAction("trigger_event", "Trigger an IFTTT event", "POST", "/trigger/{event}/with/key/{key}"),
            ],
        ),
        # --- Deployment ---
        IntegrationSpec(
            name="Vercel", category=IntegrationCategory.DEPLOYMENT,
            description="Frontend cloud platform for serverless deployment",
            base_url="https://api.vercel.com",
            auth_method=IntegrationAuthMethod.BEARER_TOKEN,
            actions=[
                IntegrationAction("list_deployments", "List deployments", "GET", "/v6/deployments"),
                IntegrationAction("create_deployment", "Create a deployment", "POST", "/v13/deployments"),
                IntegrationAction("list_projects", "List projects", "GET", "/v9/projects"),
            ],
        ),
        IntegrationSpec(
            name="Netlify", category=IntegrationCategory.DEPLOYMENT,
            description="Web hosting and serverless backend platform",
            base_url="https://api.netlify.com/api/v1",
            auth_method=IntegrationAuthMethod.BEARER_TOKEN,
            actions=[
                IntegrationAction("list_sites", "List sites", "GET", "/sites"),
                IntegrationAction("create_deploy", "Create a deploy", "POST", "/sites/{site_id}/deploys"),
            ],
        ),
        IntegrationSpec(
            name="Railway", category=IntegrationCategory.DEPLOYMENT,
            description="Infrastructure platform for full-stack apps",
            base_url="https://backboard.railway.app/graphql/v2",
            auth_method=IntegrationAuthMethod.BEARER_TOKEN,
            actions=[
                IntegrationAction("list_projects", "List projects", "POST", ""),
                IntegrationAction("deploy", "Trigger deployment", "POST", ""),
            ],
        ),
        # --- Database / Storage ---
        IntegrationSpec(
            name="Supabase", category=IntegrationCategory.DATABASE,
            description="Open-source Firebase alternative (Postgres + auth + storage)",
            base_url="https://{project_ref}.supabase.co",
            auth_method=IntegrationAuthMethod.API_KEY,
            actions=[
                IntegrationAction("query", "Execute a SQL query via REST", "POST", "/rest/v1/rpc/{function_name}"),
                IntegrationAction("insert", "Insert rows into a table", "POST", "/rest/v1/{table}"),
                IntegrationAction("select", "Select rows from a table", "GET", "/rest/v1/{table}"),
            ],
        ),
        IntegrationSpec(
            name="Firebase", category=IntegrationCategory.DATABASE,
            description="Google cloud backend (Firestore, Auth, Storage, Functions)",
            base_url="https://firestore.googleapis.com/v1",
            auth_method=IntegrationAuthMethod.BEARER_TOKEN,
            actions=[
                IntegrationAction("get_document", "Get a Firestore document", "GET", "/projects/{project}/databases/{db}/documents/{path}"),
                IntegrationAction("create_document", "Create a Firestore document", "POST", "/projects/{project}/databases/{db}/documents/{collection}"),
            ],
        ),
        IntegrationSpec(
            name="MongoDB Atlas", category=IntegrationCategory.DATABASE,
            description="Cloud-hosted MongoDB with Data API",
            base_url="https://data.mongodb-api.com/app/{app_id}/endpoint/data/v1",
            auth_method=IntegrationAuthMethod.API_KEY,
            actions=[
                IntegrationAction("find", "Find documents", "POST", "/action/find"),
                IntegrationAction("insert_one", "Insert a document", "POST", "/action/insertOne"),
                IntegrationAction("update_one", "Update a document", "POST", "/action/updateOne"),
            ],
        ),
        IntegrationSpec(
            name="Cloudflare", category=IntegrationCategory.CLOUD_INFRASTRUCTURE,
            description="CDN, DNS, Workers, R2 storage, and edge computing",
            base_url="https://api.cloudflare.com/client/v4",
            auth_method=IntegrationAuthMethod.BEARER_TOKEN,
            actions=[
                IntegrationAction("list_zones", "List DNS zones", "GET", "/zones"),
                IntegrationAction("purge_cache", "Purge CDN cache", "POST", "/zones/{zone_id}/purge_cache"),
                IntegrationAction("create_worker", "Create a Worker script", "PUT", "/accounts/{account_id}/workers/scripts/{script_name}"),
            ],
        ),
        # --- Social Media ---
        IntegrationSpec(
            service_id="twitter",
            name="Twitter/X", category=IntegrationCategory.SOCIAL_MEDIA,
            description="Social media platform for posts and engagement",
            base_url="https://api.twitter.com/2",
            auth_method=IntegrationAuthMethod.OAUTH2,
            actions=[
                IntegrationAction("post_tweet", "Create a tweet", "POST", "/tweets"),
                IntegrationAction("get_timeline", "Get user timeline", "GET", "/users/{user_id}/tweets"),
            ],
        ),
        IntegrationSpec(
            name="LinkedIn", category=IntegrationCategory.SOCIAL_MEDIA,
            description="Professional networking and content platform",
            base_url="https://api.linkedin.com/v2",
            auth_method=IntegrationAuthMethod.OAUTH2,
            actions=[
                IntegrationAction("create_post", "Create a post", "POST", "/ugcPosts"),
                IntegrationAction("get_profile", "Get user profile", "GET", "/me"),
            ],
        ),
        IntegrationSpec(
            name="Reddit", category=IntegrationCategory.SOCIAL_MEDIA,
            description="Community discussion platform",
            base_url="https://oauth.reddit.com",
            auth_method=IntegrationAuthMethod.OAUTH2,
            actions=[
                IntegrationAction("submit_post", "Submit a post", "POST", "/api/submit"),
                IntegrationAction("get_subreddit", "Get subreddit posts", "GET", "/r/{subreddit}/hot"),
            ],
        ),
        IntegrationSpec(
            name="Product Hunt", category=IntegrationCategory.SOCIAL_MEDIA,
            description="Product launch and discovery platform",
            base_url="https://api.producthunt.com/v2/api/graphql",
            auth_method=IntegrationAuthMethod.BEARER_TOKEN,
            actions=[
                IntegrationAction("get_posts", "Get trending posts", "POST", ""),
                IntegrationAction("create_post", "Submit a product", "POST", ""),
            ],
        ),
        # --- Media Streaming ---
        IntegrationSpec(
            name="Twitch", category=IntegrationCategory.MEDIA_STREAMING,
            description="Live streaming platform",
            base_url="https://api.twitch.tv/helix",
            auth_method=IntegrationAuthMethod.OAUTH2,
            actions=[
                IntegrationAction("get_streams", "Get live streams", "GET", "/streams"),
                IntegrationAction("get_users", "Get user info", "GET", "/users"),
            ],
        ),
        IntegrationSpec(
            name="YouTube", category=IntegrationCategory.MEDIA_STREAMING,
            description="Video hosting and streaming platform",
            base_url="https://www.googleapis.com/youtube/v3",
            auth_method=IntegrationAuthMethod.API_KEY,
            actions=[
                IntegrationAction("search", "Search videos", "GET", "/search"),
                IntegrationAction("list_videos", "List videos", "GET", "/videos"),
                IntegrationAction("upload_video", "Upload a video", "POST", "/videos"),
            ],
        ),
        IntegrationSpec(
            name="Spotify", category=IntegrationCategory.MEDIA_STREAMING,
            description="Music streaming platform API",
            base_url="https://api.spotify.com/v1",
            auth_method=IntegrationAuthMethod.OAUTH2,
            actions=[
                IntegrationAction("search", "Search tracks/artists/albums", "GET", "/search"),
                IntegrationAction("get_playlists", "Get user playlists", "GET", "/me/playlists"),
            ],
        ),
        # --- AI/ML ---
        IntegrationSpec(
            name="HuggingFace", category=IntegrationCategory.AI_ML,
            description="Open-source AI model hub and inference API",
            base_url="https://api-inference.huggingface.co",
            auth_method=IntegrationAuthMethod.BEARER_TOKEN,
            actions=[
                IntegrationAction("inference", "Run model inference", "POST", "/models/{model_id}"),
                IntegrationAction("list_models", "List available models", "GET", "/api/models"),
            ],
        ),
        IntegrationSpec(
            name="Ollama", category=IntegrationCategory.AI_ML,
            description="Run open-source LLMs locally",
            base_url=os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/"),
            auth_method=IntegrationAuthMethod.NONE,
            actions=[
                IntegrationAction("generate", "Generate text", "POST", "/api/generate"),
                IntegrationAction("chat", "Chat completion", "POST", "/api/chat"),
                IntegrationAction("list_models", "List local models", "GET", "/api/tags"),
            ],
        ),
        IntegrationSpec(
            name="Replicate", category=IntegrationCategory.AI_ML,
            description="Run open-source ML models in the cloud",
            base_url="https://api.replicate.com/v1",
            auth_method=IntegrationAuthMethod.BEARER_TOKEN,
            actions=[
                IntegrationAction("create_prediction", "Run a model", "POST", "/predictions"),
                IntegrationAction("get_prediction", "Get prediction status", "GET", "/predictions/{prediction_id}"),
            ],
        ),
        # --- Email ---
        IntegrationSpec(
            name="Resend", category=IntegrationCategory.EMAIL,
            description="Modern email API for developers",
            base_url="https://api.resend.com",
            auth_method=IntegrationAuthMethod.API_KEY,
            actions=[
                IntegrationAction("send_email", "Send an email", "POST", "/emails"),
                IntegrationAction("list_emails", "List sent emails", "GET", "/emails"),
            ],
        ),
        IntegrationSpec(
            name="Mailgun", category=IntegrationCategory.EMAIL,
            description="Transactional email API",
            base_url="https://api.mailgun.net/v3",
            auth_method=IntegrationAuthMethod.BASIC_AUTH,
            actions=[
                IntegrationAction("send_email", "Send an email", "POST", "/{domain}/messages"),
                IntegrationAction("list_events", "List email events", "GET", "/{domain}/events"),
            ],
        ),
        # --- Analytics ---
        IntegrationSpec(
            name="Mixpanel", category=IntegrationCategory.ANALYTICS,
            description="Product analytics platform",
            base_url="https://api.mixpanel.com",
            auth_method=IntegrationAuthMethod.API_KEY,
            actions=[
                IntegrationAction("track_event", "Track an event", "POST", "/track"),
                IntegrationAction("query", "Query analytics data", "POST", "/jql"),
            ],
        ),
        IntegrationSpec(
            name="PostHog", category=IntegrationCategory.ANALYTICS,
            description="Open-source product analytics",
            base_url="https://app.posthog.com",
            auth_method=IntegrationAuthMethod.API_KEY,
            actions=[
                IntegrationAction("capture_event", "Capture an event", "POST", "/capture"),
                IntegrationAction("list_events", "List events", "GET", "/api/event"),
            ],
        ),
        # --- CRM ---
        IntegrationSpec(
            name="Salesforce", category=IntegrationCategory.CRM,
            description="Enterprise CRM for sales, service, and marketing automation",
            base_url="https://login.salesforce.com/services/data/v59.0",
            auth_method=IntegrationAuthMethod.OAUTH2,
            actions=[
                IntegrationAction("query", "Execute a SOQL query", "GET", "/query"),
                IntegrationAction("create_record", "Create a record", "POST", "/sobjects/{object_type}"),
                IntegrationAction("update_record", "Update a record", "PATCH", "/sobjects/{object_type}/{record_id}"),
                IntegrationAction("delete_record", "Delete a record", "DELETE", "/sobjects/{object_type}/{record_id}"),
            ],
        ),
        IntegrationSpec(
            name="HubSpot", category=IntegrationCategory.CRM,
            description="Inbound marketing, sales, and CRM platform",
            base_url="https://api.hubapi.com",
            auth_method=IntegrationAuthMethod.BEARER_TOKEN,
            actions=[
                IntegrationAction("create_contact", "Create a contact", "POST", "/crm/v3/objects/contacts"),
                IntegrationAction("update_deal", "Update a deal", "PATCH", "/crm/v3/objects/deals/{deal_id}"),
                IntegrationAction("list_pipelines", "List sales pipelines", "GET", "/crm/v3/pipelines/deals"),
                IntegrationAction("create_ticket", "Create a support ticket", "POST", "/crm/v3/objects/tickets"),
            ],
        ),
        # --- Payment ---
        IntegrationSpec(
            name="Stripe", category=IntegrationCategory.PAYMENT,
            description="Payment processing platform for internet businesses",
            base_url="https://api.stripe.com/v1",
            auth_method=IntegrationAuthMethod.BEARER_TOKEN,
            actions=[
                IntegrationAction("create_charge", "Create a payment charge", "POST", "/charges"),
                IntegrationAction("create_customer", "Create a customer", "POST", "/customers"),
                IntegrationAction("list_invoices", "List invoices", "GET", "/invoices"),
                IntegrationAction("create_subscription", "Create a subscription", "POST", "/subscriptions"),
            ],
        ),
        IntegrationSpec(
            name="PayPal", category=IntegrationCategory.PAYMENT,
            description="Online payment system for businesses and consumers",
            base_url="https://api-m.paypal.com/v2",
            auth_method=IntegrationAuthMethod.OAUTH2,
            actions=[
                IntegrationAction("create_order", "Create a payment order", "POST", "/checkout/orders"),
                IntegrationAction("capture_payment", "Capture an authorized payment", "POST", "/checkout/orders/{order_id}/capture"),
                IntegrationAction("create_payout", "Create a payout", "POST", "/payments/payouts"),
            ],
        ),
        # --- E-commerce ---
        IntegrationSpec(
            name="Shopify", category=IntegrationCategory.CUSTOM,
            description="E-commerce platform for online stores",
            base_url="https://{store}.myshopify.com/admin/api/2024-01",
            auth_method=IntegrationAuthMethod.BEARER_TOKEN,
            actions=[
                IntegrationAction("list_products", "List products", "GET", "/products.json"),
                IntegrationAction("create_product", "Create a product", "POST", "/products.json"),
                IntegrationAction("list_orders", "List orders", "GET", "/orders.json"),
                IntegrationAction("create_order", "Create an order", "POST", "/orders.json"),
                IntegrationAction("update_inventory", "Update inventory level", "POST", "/inventory_levels/set.json"),
            ],
        ),
        IntegrationSpec(
            name="WooCommerce", category=IntegrationCategory.CUSTOM,
            description="Open-source e-commerce plugin for WordPress",
            base_url="https://{site}/wp-json/wc/v3",
            auth_method=IntegrationAuthMethod.BASIC_AUTH,
            actions=[
                IntegrationAction("list_products", "List products", "GET", "/products"),
                IntegrationAction("create_product", "Create a product", "POST", "/products"),
                IntegrationAction("list_orders", "List orders", "GET", "/orders"),
                IntegrationAction("update_order", "Update an order", "PUT", "/orders/{order_id}"),
            ],
        ),
        # --- Customer Support ---
        IntegrationSpec(
            name="Zendesk", category=IntegrationCategory.CUSTOM,
            description="Customer service and support ticketing platform",
            base_url="https://{subdomain}.zendesk.com/api/v2",
            auth_method=IntegrationAuthMethod.BEARER_TOKEN,
            actions=[
                IntegrationAction("create_ticket", "Create a support ticket", "POST", "/tickets.json"),
                IntegrationAction("update_ticket", "Update a ticket", "PUT", "/tickets/{ticket_id}.json"),
                IntegrationAction("list_tickets", "List tickets", "GET", "/tickets.json"),
                IntegrationAction("add_comment", "Add a comment to a ticket", "PUT", "/tickets/{ticket_id}.json"),
            ],
        ),
        IntegrationSpec(
            name="Intercom", category=IntegrationCategory.CUSTOM,
            description="Conversational relationship platform for customer engagement",
            base_url="https://api.intercom.io",
            auth_method=IntegrationAuthMethod.BEARER_TOKEN,
            actions=[
                IntegrationAction("create_contact", "Create or update a contact", "POST", "/contacts"),
                IntegrationAction("send_message", "Send a message", "POST", "/messages"),
                IntegrationAction("list_conversations", "List conversations", "GET", "/conversations"),
                IntegrationAction("create_ticket", "Create a ticket", "POST", "/tickets"),
            ],
        ),
        IntegrationSpec(
            name="Freshdesk", category=IntegrationCategory.CUSTOM,
            description="Cloud-based customer support software",
            base_url="https://{domain}.freshdesk.com/api/v2",
            auth_method=IntegrationAuthMethod.API_KEY,
            actions=[
                IntegrationAction("create_ticket", "Create a ticket", "POST", "/tickets"),
                IntegrationAction("list_tickets", "List tickets", "GET", "/tickets"),
                IntegrationAction("update_ticket", "Update a ticket", "PUT", "/tickets/{ticket_id}"),
            ],
        ),
        # --- Observability & Monitoring ---
        IntegrationSpec(
            name="Datadog", category=IntegrationCategory.MONITORING,
            description="Cloud-scale monitoring and analytics platform",
            base_url="https://api.datadoghq.com/api/v1",
            auth_method=IntegrationAuthMethod.API_KEY,
            actions=[
                IntegrationAction("send_metrics", "Submit time-series metrics", "POST", "/series"),
                IntegrationAction("create_event", "Post an event", "POST", "/events"),
                IntegrationAction("query_metrics", "Query time-series data", "GET", "/query"),
                IntegrationAction("create_monitor", "Create a monitor", "POST", "/monitor"),
            ],
        ),
        IntegrationSpec(
            name="PagerDuty", category=IntegrationCategory.MONITORING,
            description="Incident management and on-call scheduling platform",
            base_url="https://api.pagerduty.com",
            auth_method=IntegrationAuthMethod.BEARER_TOKEN,
            actions=[
                IntegrationAction("create_incident", "Create an incident", "POST", "/incidents"),
                IntegrationAction("list_incidents", "List incidents", "GET", "/incidents"),
                IntegrationAction("resolve_incident", "Resolve an incident", "PUT", "/incidents/{incident_id}"),
                IntegrationAction("list_oncalls", "List on-call schedules", "GET", "/oncalls"),
            ],
        ),
        IntegrationSpec(
            name="Sentry", category=IntegrationCategory.MONITORING,
            description="Application performance monitoring and error tracking",
            base_url="https://sentry.io/api/0",
            auth_method=IntegrationAuthMethod.BEARER_TOKEN,
            actions=[
                IntegrationAction("list_issues", "List project issues", "GET", "/projects/{org}/{project}/issues/"),
                IntegrationAction("resolve_issue", "Resolve an issue", "PUT", "/issues/{issue_id}/"),
                IntegrationAction("list_events", "List error events", "GET", "/projects/{org}/{project}/events/"),
            ],
        ),
        IntegrationSpec(
            service_id="newrelic",
            name="New Relic", category=IntegrationCategory.MONITORING,
            description="Full-stack observability platform",
            base_url="https://api.newrelic.com/v2",
            auth_method=IntegrationAuthMethod.API_KEY,
            actions=[
                IntegrationAction("list_applications", "List applications", "GET", "/applications.json"),
                IntegrationAction("get_metrics", "Get application metrics", "GET", "/applications/{app_id}/metrics/data.json"),
                IntegrationAction("create_deployment", "Record a deployment", "POST", "/applications/{app_id}/deployments.json"),
            ],
        ),
        # --- CI/CD ---
        IntegrationSpec(
            name="CircleCI", category=IntegrationCategory.DEVELOPER_TOOLS,
            description="Continuous integration and delivery platform",
            base_url="https://circleci.com/api/v2",
            auth_method=IntegrationAuthMethod.BEARER_TOKEN,
            actions=[
                IntegrationAction("trigger_pipeline", "Trigger a pipeline", "POST", "/project/{project_slug}/pipeline"),
                IntegrationAction("list_pipelines", "List pipelines", "GET", "/project/{project_slug}/pipeline"),
                IntegrationAction("get_workflow", "Get workflow details", "GET", "/workflow/{workflow_id}"),
            ],
        ),
        IntegrationSpec(
            name="Jenkins", category=IntegrationCategory.DEVELOPER_TOOLS,
            description="Open-source automation server for CI/CD",
            base_url="https://{host}/api",
            auth_method=IntegrationAuthMethod.BASIC_AUTH,
            actions=[
                IntegrationAction("trigger_build", "Trigger a job build", "POST", "/job/{job_name}/build"),
                IntegrationAction("get_build_status", "Get build status", "GET", "/job/{job_name}/lastBuild/api/json"),
                IntegrationAction("list_jobs", "List all jobs", "GET", "/json"),
            ],
        ),
        # --- Communication (SMS/Voice) ---
        IntegrationSpec(
            name="Twilio", category=IntegrationCategory.COMMUNICATION,
            description="Cloud communications platform for SMS, voice, and messaging",
            base_url="https://api.twilio.com/2010-04-01",
            auth_method=IntegrationAuthMethod.BASIC_AUTH,
            actions=[
                IntegrationAction("send_sms", "Send an SMS message", "POST", "/Accounts/{account_sid}/Messages.json"),
                IntegrationAction("make_call", "Initiate a phone call", "POST", "/Accounts/{account_sid}/Calls.json"),
                IntegrationAction("list_messages", "List SMS messages", "GET", "/Accounts/{account_sid}/Messages.json"),
            ],
        ),
        IntegrationSpec(
            name="SendGrid", category=IntegrationCategory.EMAIL,
            description="Cloud-based email delivery platform",
            base_url="https://api.sendgrid.com/v3",
            auth_method=IntegrationAuthMethod.BEARER_TOKEN,
            actions=[
                IntegrationAction("send_email", "Send an email", "POST", "/mail/send"),
                IntegrationAction("list_contacts", "List marketing contacts", "GET", "/marketing/contacts"),
                IntegrationAction("create_campaign", "Create an email campaign", "POST", "/marketing/singlesends"),
            ],
        ),
        # --- Document & Signature ---
        IntegrationSpec(
            name="DocuSign", category=IntegrationCategory.CUSTOM,
            description="Electronic signature and agreement cloud platform",
            base_url="https://demo.docusign.net/restapi/v2.1",
            auth_method=IntegrationAuthMethod.OAUTH2,
            actions=[
                IntegrationAction("create_envelope", "Create and send an envelope for signing", "POST", "/accounts/{account_id}/envelopes"),
                IntegrationAction("get_envelope", "Get envelope status", "GET", "/accounts/{account_id}/envelopes/{envelope_id}"),
                IntegrationAction("list_envelopes", "List envelopes", "GET", "/accounts/{account_id}/envelopes"),
            ],
        ),
        IntegrationSpec(
            name="Dropbox", category=IntegrationCategory.STORAGE,
            description="Cloud file storage and collaboration platform",
            base_url="https://api.dropboxapi.com/2",
            auth_method=IntegrationAuthMethod.BEARER_TOKEN,
            actions=[
                IntegrationAction("upload_file", "Upload a file", "POST", "/files/upload"),
                IntegrationAction("list_folder", "List folder contents", "POST", "/files/list_folder"),
                IntegrationAction("create_shared_link", "Create a shared link", "POST", "/sharing/create_shared_link_with_settings"),
            ],
        ),
        IntegrationSpec(
            name="Google Drive", category=IntegrationCategory.STORAGE,
            description="Cloud storage and file synchronization service",
            base_url="https://www.googleapis.com/drive/v3",
            auth_method=IntegrationAuthMethod.OAUTH2,
            actions=[
                IntegrationAction("list_files", "List files", "GET", "/files"),
                IntegrationAction("upload_file", "Upload a file", "POST", "/files"),
                IntegrationAction("create_folder", "Create a folder", "POST", "/files"),
                IntegrationAction("share_file", "Share a file", "POST", "/files/{file_id}/permissions"),
            ],
        ),
        # --- Calendar & Scheduling ---
        IntegrationSpec(
            name="Calendly", category=IntegrationCategory.CUSTOM,
            description="Scheduling and appointment platform",
            base_url="https://api.calendly.com",
            auth_method=IntegrationAuthMethod.BEARER_TOKEN,
            actions=[
                IntegrationAction("list_events", "List scheduled events", "GET", "/scheduled_events"),
                IntegrationAction("get_event_types", "Get event types", "GET", "/event_types"),
                IntegrationAction("cancel_event", "Cancel an event", "POST", "/scheduled_events/{event_uuid}/cancellation"),
            ],
        ),
        IntegrationSpec(
            name="Google Calendar", category=IntegrationCategory.CUSTOM,
            description="Online calendar and scheduling service",
            base_url="https://www.googleapis.com/calendar/v3",
            auth_method=IntegrationAuthMethod.OAUTH2,
            actions=[
                IntegrationAction("list_events", "List calendar events", "GET", "/calendars/{calendar_id}/events"),
                IntegrationAction("create_event", "Create a calendar event", "POST", "/calendars/{calendar_id}/events"),
                IntegrationAction("update_event", "Update a calendar event", "PUT", "/calendars/{calendar_id}/events/{event_id}"),
            ],
        ),
        # --- Accounting ---
        IntegrationSpec(
            service_id="quickbooks",
            name="QuickBooks Online", category=IntegrationCategory.CUSTOM,
            description="Cloud accounting software for small businesses",
            base_url="https://quickbooks.api.intuit.com/v3",
            auth_method=IntegrationAuthMethod.OAUTH2,
            actions=[
                IntegrationAction("create_invoice", "Create an invoice", "POST", "/company/{realm_id}/invoice"),
                IntegrationAction("list_customers", "List customers", "GET", "/company/{realm_id}/query"),
                IntegrationAction("create_payment", "Record a payment", "POST", "/company/{realm_id}/payment"),
            ],
        ),
        # --- Cloud Infrastructure ---
        IntegrationSpec(
            service_id="aws",
            name="Amazon Web Services", category=IntegrationCategory.CLOUD_INFRASTRUCTURE,
            description="Cloud computing platform with 200+ services",
            base_url="https://aws.amazon.com",
            auth_method=IntegrationAuthMethod.API_KEY,
            actions=[
                IntegrationAction("manage_ec2", "Manage EC2 instances", "POST", "/ec2"),
                IntegrationAction("manage_s3", "Manage S3 buckets", "POST", "/s3"),
                IntegrationAction("invoke_lambda", "Invoke Lambda function", "POST", "/lambda/invoke"),
            ],
        ),
        IntegrationSpec(
            service_id="azure",
            name="Microsoft Azure", category=IntegrationCategory.CLOUD_INFRASTRUCTURE,
            description="Enterprise cloud computing platform",
            base_url="https://management.azure.com",
            auth_method=IntegrationAuthMethod.OAUTH2,
            actions=[
                IntegrationAction("manage_vms", "Manage virtual machines", "POST", "/subscriptions/{sub_id}/providers/Microsoft.Compute/virtualMachines"),
                IntegrationAction("manage_storage", "Manage storage accounts", "POST", "/subscriptions/{sub_id}/providers/Microsoft.Storage/storageAccounts"),
            ],
        ),
        IntegrationSpec(
            service_id="gcp",
            name="Google Cloud Platform", category=IntegrationCategory.CLOUD_INFRASTRUCTURE,
            description="Suite of cloud computing services",
            base_url="https://cloud.google.com",
            auth_method=IntegrationAuthMethod.OAUTH2,
            actions=[
                IntegrationAction("manage_compute", "Manage Compute Engine instances", "POST", "/compute/v1/projects/{project}/zones/{zone}/instances"),
                IntegrationAction("manage_storage", "Manage Cloud Storage", "POST", "/storage/v1/b"),
            ],
        ),
        # --- DevOps ---
        IntegrationSpec(
            name="GitHub", category=IntegrationCategory.DEVELOPER_TOOLS,
            description="Software development platform with version control and CI/CD",
            base_url="https://api.github.com",
            auth_method=IntegrationAuthMethod.BEARER_TOKEN,
            actions=[
                IntegrationAction("create_issue", "Create a repository issue", "POST", "/repos/{owner}/{repo}/issues"),
                IntegrationAction("create_pr", "Create a pull request", "POST", "/repos/{owner}/{repo}/pulls"),
                IntegrationAction("list_repos", "List repositories", "GET", "/user/repos"),
                IntegrationAction("trigger_workflow", "Trigger a GitHub Actions workflow", "POST", "/repos/{owner}/{repo}/actions/workflows/{workflow_id}/dispatches"),
            ],
        ),
        IntegrationSpec(
            name="GitLab", category=IntegrationCategory.DEVELOPER_TOOLS,
            description="DevOps lifecycle platform with CI/CD",
            base_url="https://gitlab.com/api/v4",
            auth_method=IntegrationAuthMethod.BEARER_TOKEN,
            actions=[
                IntegrationAction("create_issue", "Create a project issue", "POST", "/projects/{project_id}/issues"),
                IntegrationAction("create_mr", "Create a merge request", "POST", "/projects/{project_id}/merge_requests"),
                IntegrationAction("trigger_pipeline", "Trigger a CI/CD pipeline", "POST", "/projects/{project_id}/pipeline"),
            ],
        ),
        # --- Project Management ---
        IntegrationSpec(
            name="Jira", category=IntegrationCategory.PROJECT_MANAGEMENT,
            description="Issue and project tracking for agile teams",
            base_url="https://api.atlassian.com/ex/jira/{cloud_id}/rest/api/3",
            auth_method=IntegrationAuthMethod.OAUTH2,
            actions=[
                IntegrationAction("create_issue", "Create an issue", "POST", "/issue"),
                IntegrationAction("search_issues", "Search issues with JQL", "POST", "/search"),
                IntegrationAction("transition_issue", "Transition issue status", "POST", "/issue/{issue_id}/transitions"),
            ],
        ),
        IntegrationSpec(
            name="Asana", category=IntegrationCategory.PROJECT_MANAGEMENT,
            description="Work management platform for teams",
            base_url="https://app.asana.com/api/1.0",
            auth_method=IntegrationAuthMethod.BEARER_TOKEN,
            actions=[
                IntegrationAction("create_task", "Create a task", "POST", "/tasks"),
                IntegrationAction("list_projects", "List projects", "GET", "/projects"),
                IntegrationAction("update_task", "Update a task", "PUT", "/tasks/{task_id}"),
            ],
        ),
        IntegrationSpec(
            service_id="monday",
            name="Monday.com", category=IntegrationCategory.PROJECT_MANAGEMENT,
            description="Work OS for managing projects and workflows",
            base_url="https://api.monday.com/v2",
            auth_method=IntegrationAuthMethod.API_KEY,
            actions=[
                IntegrationAction("create_item", "Create a board item", "POST", ""),
                IntegrationAction("list_boards", "List boards", "POST", ""),
            ],
        ),
        # --- Knowledge & Content ---
        IntegrationSpec(
            name="Confluence", category=IntegrationCategory.CUSTOM,
            description="Team workspace for documentation and knowledge sharing",
            base_url="https://api.atlassian.com/ex/confluence/{cloud_id}/wiki/api/v2",
            auth_method=IntegrationAuthMethod.OAUTH2,
            actions=[
                IntegrationAction("create_page", "Create a page", "POST", "/pages"),
                IntegrationAction("search", "Search content", "GET", "/search"),
                IntegrationAction("list_spaces", "List spaces", "GET", "/spaces"),
            ],
        ),
        IntegrationSpec(
            name="Google Workspace", category=IntegrationCategory.CUSTOM,
            description="Cloud-based productivity and collaboration tools",
            base_url="https://www.googleapis.com",
            auth_method=IntegrationAuthMethod.OAUTH2,
            actions=[
                IntegrationAction("gmail_send", "Send an email via Gmail", "POST", "/gmail/v1/users/me/messages/send"),
                IntegrationAction("drive_upload", "Upload a file to Drive", "POST", "/upload/drive/v3/files"),
                IntegrationAction("calendar_create", "Create a calendar event", "POST", "/calendar/v3/calendars/primary/events"),
                IntegrationAction("sheets_read", "Read spreadsheet data", "GET", "/v4/spreadsheets/{spreadsheet_id}/values/{range}"),
            ],
        ),
        # --- ITSM ---
        IntegrationSpec(
            name="ServiceNow", category=IntegrationCategory.CUSTOM,
            description="Digital workflow platform for enterprise IT service management",
            base_url="https://{instance}.service-now.com/api",
            auth_method=IntegrationAuthMethod.OAUTH2,
            actions=[
                IntegrationAction("create_incident", "Create an incident", "POST", "/now/table/incident"),
                IntegrationAction("list_incidents", "List incidents", "GET", "/now/table/incident"),
                IntegrationAction("create_change", "Create a change request", "POST", "/now/table/change_request"),
            ],
        ),
        # --- Communication (Messaging) ---
        IntegrationSpec(
            service_id="whatsapp",
            name="WhatsApp Business", category=IntegrationCategory.COMMUNICATION,
            description="Business messaging platform via Meta Cloud API",
            base_url="https://graph.facebook.com/v17.0",
            auth_method=IntegrationAuthMethod.BEARER_TOKEN,
            actions=[
                IntegrationAction("send_message", "Send a text message", "POST", "/{phone_number_id}/messages"),
                IntegrationAction("send_template", "Send a template message", "POST", "/{phone_number_id}/messages"),
                IntegrationAction("send_media", "Send a media message", "POST", "/{phone_number_id}/messages"),
            ],
        ),
        IntegrationSpec(
            name="Telegram", category=IntegrationCategory.COMMUNICATION,
            description="Messaging platform with bot API",
            base_url="https://api.telegram.org/bot{token}",
            auth_method=IntegrationAuthMethod.BEARER_TOKEN,
            actions=[
                IntegrationAction("send_message", "Send a message", "POST", "/sendMessage"),
                IntegrationAction("send_photo", "Send a photo", "POST", "/sendPhoto"),
                IntegrationAction("get_updates", "Get bot updates", "GET", "/getUpdates"),
            ],
        ),
        # --- Analytics ---
        IntegrationSpec(
            name="Snowflake", category=IntegrationCategory.ANALYTICS,
            description="Cloud data platform for analytics and data warehousing",
            base_url="https://{account}.snowflakecomputing.com",
            auth_method=IntegrationAuthMethod.BEARER_TOKEN,
            actions=[
                IntegrationAction("execute_query", "Execute a SQL query", "POST", "/api/v2/statements"),
                IntegrationAction("list_databases", "List databases", "GET", "/api/v2/databases"),
            ],
        ),
        # --- Messaging (Extended) ---
        IntegrationSpec(
            name="Signal", category=IntegrationCategory.COMMUNICATION,
            description="Private messenger with end-to-end encryption",
            base_url="https://signal.org/api",
            auth_method=IntegrationAuthMethod.BEARER_TOKEN,
            actions=[
                IntegrationAction("send_message", "Send a message", "POST", "/messages"),
                IntegrationAction("list_contacts", "List contacts", "GET", "/contacts"),
            ],
        ),
        IntegrationSpec(
            name="Google Business Messages", category=IntegrationCategory.COMMUNICATION,
            description="Business messaging via Google platforms",
            base_url="https://businessmessages.googleapis.com/v1",
            auth_method=IntegrationAuthMethod.OAUTH2,
            actions=[
                IntegrationAction("send_message", "Send a message to user", "POST", "/conversations/{conversationId}/messages"),
                IntegrationAction("list_agents", "List business agents", "GET", "/brands/{brandId}/agents"),
            ],
        ),
        IntegrationSpec(
            name="KakaoTalk", category=IntegrationCategory.COMMUNICATION,
            description="Korean messaging platform with business APIs",
            base_url="https://kapi.kakao.com/v2",
            auth_method=IntegrationAuthMethod.BEARER_TOKEN,
            actions=[
                IntegrationAction("send_message", "Send a message", "POST", "/api/talk/memo/default/send"),
                IntegrationAction("get_profile", "Get user profile", "GET", "/user/me"),
            ],
        ),
        IntegrationSpec(
            name="LINE", category=IntegrationCategory.COMMUNICATION,
            description="Messaging platform popular in Japan and Southeast Asia",
            base_url="https://api.line.me/v2",
            auth_method=IntegrationAuthMethod.BEARER_TOKEN,
            actions=[
                IntegrationAction("send_push", "Send a push message", "POST", "/bot/message/push"),
                IntegrationAction("send_reply", "Send a reply message", "POST", "/bot/message/reply"),
                IntegrationAction("get_profile", "Get user profile", "GET", "/bot/profile/{userId}"),
            ],
        ),
        IntegrationSpec(
            name="Snapchat", category=IntegrationCategory.SOCIAL_MEDIA,
            description="Social media platform with marketing API",
            base_url="https://adsapi.snapchat.com/v1",
            auth_method=IntegrationAuthMethod.OAUTH2,
            actions=[
                IntegrationAction("create_ad", "Create an ad", "POST", "/adaccounts/{ad_account_id}/ads"),
                IntegrationAction("list_campaigns", "List campaigns", "GET", "/adaccounts/{ad_account_id}/campaigns"),
            ],
        ),
        IntegrationSpec(
            name="WeChat", category=IntegrationCategory.COMMUNICATION,
            description="Chinese messaging and social media platform",
            base_url="https://api.weixin.qq.com/cgi-bin",
            auth_method=IntegrationAuthMethod.CUSTOM_HEADER,
            actions=[
                IntegrationAction("send_message", "Send a customer service message", "POST", "/message/custom/send"),
                IntegrationAction("create_menu", "Create custom menu", "POST", "/menu/create"),
                IntegrationAction("get_user_info", "Get user info", "GET", "/user/info"),
            ],
        ),
        # --- ERP ---
        IntegrationSpec(
            name="ZenBusiness", category=IntegrationCategory.CUSTOM,
            description="Business formation and compliance platform",
            base_url="https://api.zenbusiness.com/v1",
            auth_method=IntegrationAuthMethod.API_KEY,
            actions=[
                IntegrationAction("create_entity", "Create a business entity", "POST", "/entities"),
                IntegrationAction("list_entities", "List business entities", "GET", "/entities"),
                IntegrationAction("check_compliance", "Check compliance status", "GET", "/entities/{entity_id}/compliance"),
            ],
        ),
        # --- New World Model Integrations ---
        IntegrationSpec(
            service_id="mailchimp",
            name="Mailchimp", category=IntegrationCategory.COMMUNICATION,
            description="Email marketing platform with audience management and campaign automation",
            base_url="https://us1.api.mailchimp.com/3.0",
            auth_method=IntegrationAuthMethod.API_KEY,
            actions=[
                IntegrationAction("list_campaigns", "List email campaigns", "GET", "/campaigns"),
                IntegrationAction("create_campaign", "Create a campaign", "POST", "/campaigns"),
                IntegrationAction("send_campaign", "Send a campaign", "POST", "/campaigns/{campaign_id}/actions/send"),
                IntegrationAction("list_subscribers", "List audience members", "GET", "/lists/{list_id}/members"),
                IntegrationAction("add_subscriber", "Add a subscriber", "POST", "/lists/{list_id}/members"),
            ],
        ),
        IntegrationSpec(
            service_id="google_analytics",
            name="Google Analytics", category=IntegrationCategory.ANALYTICS,
            description="Web analytics service — GA4 Data API",
            base_url="https://analyticsdata.googleapis.com/v1beta",
            auth_method=IntegrationAuthMethod.OAUTH2,
            actions=[
                IntegrationAction("run_report", "Run a GA4 report", "POST", "/properties/{property_id}:runReport"),
                IntegrationAction("run_realtime_report", "Run a realtime report", "POST", "/properties/{property_id}:runRealtimeReport"),
                IntegrationAction("get_metadata", "Get property metadata", "GET", "/properties/{property_id}/metadata"),
            ],
        ),
        IntegrationSpec(
            service_id="openai",
            name="OpenAI", category=IntegrationCategory.CUSTOM,
            description="OpenAI GPT models, DALL-E, Whisper, and Embeddings APIs",
            base_url="https://api.openai.com/v1",
            auth_method=IntegrationAuthMethod.BEARER_TOKEN,
            actions=[
                IntegrationAction("chat_completion", "Chat completion (GPT-4o etc.)", "POST", "/chat/completions"),
                IntegrationAction("embedding", "Generate text embeddings", "POST", "/embeddings"),
                IntegrationAction("image_generation", "Generate images with DALL-E", "POST", "/images/generations"),
                IntegrationAction("transcription", "Transcribe audio with Whisper", "POST", "/audio/transcriptions"),
                IntegrationAction("list_models", "List available models", "GET", "/models"),
            ],
        ),
        IntegrationSpec(
            service_id="anthropic",
            name="Anthropic Claude", category=IntegrationCategory.CUSTOM,
            description="Anthropic Claude AI models API",
            base_url="https://api.anthropic.com/v1",
            auth_method=IntegrationAuthMethod.API_KEY,
            actions=[
                IntegrationAction("message", "Send a message to Claude", "POST", "/messages"),
                IntegrationAction("list_models", "List available Claude models", "GET", "/models"),
            ],
        ),
        IntegrationSpec(
            service_id="yahoo_finance",
            name="Yahoo Finance", category=IntegrationCategory.ANALYTICS,
            description="Free market data — stock quotes, history, financials (no API key required)",
            base_url="https://query1.finance.yahoo.com",
            auth_method=IntegrationAuthMethod.NONE,
            actions=[
                IntegrationAction("get_quote", "Get real-time stock quote", "GET", "/v8/finance/quote"),
                IntegrationAction("get_history", "Get price history", "GET", "/v8/finance/chart/{symbol}"),
                IntegrationAction("search_tickers", "Search ticker symbols", "GET", "/v1/finance/search"),
                IntegrationAction("get_financials", "Get financial statements", "GET", "/v10/finance/quoteSummary/{symbol}"),
            ],
        ),
        IntegrationSpec(
            service_id="openweathermap",
            name="OpenWeatherMap", category=IntegrationCategory.CUSTOM,
            description="Weather data API — current, forecast, historical, air quality",
            base_url="https://api.openweathermap.org/data/2.5",
            auth_method=IntegrationAuthMethod.API_KEY,
            actions=[
                IntegrationAction("get_current_weather", "Get current weather", "GET", "/weather"),
                IntegrationAction("get_forecast", "Get 5-day forecast", "GET", "/forecast"),
                IntegrationAction("get_air_quality", "Get air quality index", "GET", "/air_pollution"),
            ],
        ),
        # --- Industrial / SCADA ---
        IntegrationSpec(
            service_id="scada_modbus",
            name="SCADA / Modbus TCP", category=IntegrationCategory.CUSTOM,
            description="Modbus TCP/RTU protocol for industrial controllers, PLCs, and sensors",
            base_url="",
            auth_method=IntegrationAuthMethod.NONE,
            actions=[
                IntegrationAction("read_holding_registers", "Read holding registers", "GET", "/modbus/holding"),
                IntegrationAction("write_register", "Write a register value", "POST", "/modbus/holding"),
                IntegrationAction("read_coils", "Read coil states", "GET", "/modbus/coils"),
                IntegrationAction("write_coil", "Write a coil state", "POST", "/modbus/coils"),
                IntegrationAction("health_check", "Check Modbus connection", "GET", "/modbus/health"),
            ],
        ),
        IntegrationSpec(
            service_id="scada_bacnet",
            name="SCADA / BACnet IP", category=IntegrationCategory.CUSTOM,
            description="BACnet/IP protocol for building automation systems",
            base_url="",
            auth_method=IntegrationAuthMethod.NONE,
            actions=[
                IntegrationAction("read_property", "Read a BACnet object property", "GET", "/bacnet/read"),
                IntegrationAction("write_property", "Write a BACnet object property", "POST", "/bacnet/write"),
                IntegrationAction("who_is", "Discover BACnet devices (Who-Is)", "GET", "/bacnet/who_is"),
                IntegrationAction("health_check", "Check BACnet connection", "GET", "/bacnet/health"),
            ],
        ),
        IntegrationSpec(
            service_id="scada_opcua",
            name="SCADA / OPC UA", category=IntegrationCategory.CUSTOM,
            description="OPC Unified Architecture for industrial data exchange",
            base_url="",
            auth_method=IntegrationAuthMethod.CERTIFICATE,
            actions=[
                IntegrationAction("browse", "Browse OPC UA node tree", "GET", "/opcua/browse"),
                IntegrationAction("read_node", "Read a node value", "GET", "/opcua/read"),
                IntegrationAction("write_node", "Write a node value", "POST", "/opcua/write"),
                IntegrationAction("subscribe", "Subscribe to node changes", "POST", "/opcua/subscribe"),
                IntegrationAction("health_check", "Check OPC UA connection", "GET", "/opcua/health"),
            ],
        ),
        IntegrationSpec(
            service_id="additive_manufacturing",
            name="Additive Manufacturing / 3D Printing", category=IntegrationCategory.CUSTOM,
            description="Unified interface for FDM/SLA/SLS/DMLS 3D printing systems — OPC UA AM companion spec, MTConnect, REST vendor APIs",
            base_url="",
            auth_method=IntegrationAuthMethod.API_KEY,
            actions=[
                IntegrationAction("submit_job", "Submit a print job", "POST", "/am/jobs"),
                IntegrationAction("get_job_status", "Get print job status", "GET", "/am/jobs/{job_id}"),
                IntegrationAction("get_machine_status", "Get machine/printer status", "GET", "/am/machines/{machine_id}"),
                IntegrationAction("start_print", "Start a print job", "POST", "/am/jobs/{job_id}/start"),
                IntegrationAction("pause_print", "Pause a running print", "POST", "/am/jobs/{job_id}/pause"),
                IntegrationAction("upload_model", "Upload a 3D model file", "POST", "/am/models"),
                IntegrationAction("health_check", "Check AM system connection", "GET", "/am/health"),
            ],
        ),
        IntegrationSpec(
            service_id="building_automation",
            name="Building Automation (BAS/BMS)", category=IntegrationCategory.CUSTOM,
            description="Building management systems — HVAC, lighting, access control, energy metering via BACnet/Modbus/KNX/LonWorks",
            base_url="",
            auth_method=IntegrationAuthMethod.API_KEY,
            actions=[
                IntegrationAction("read_sensor", "Read a sensor value", "GET", "/bas/sensors/{sensor_id}"),
                IntegrationAction("write_setpoint", "Write a setpoint", "POST", "/bas/setpoints"),
                IntegrationAction("get_hvac_status", "Get HVAC system status", "GET", "/bas/hvac"),
                IntegrationAction("set_hvac_mode", "Set HVAC operating mode", "POST", "/bas/hvac/mode"),
                IntegrationAction("get_energy_usage", "Get energy consumption data", "GET", "/bas/energy"),
                IntegrationAction("list_devices", "List all building devices", "GET", "/bas/devices"),
                IntegrationAction("health_check", "Check BAS connection", "GET", "/bas/health"),
            ],
        ),
        IntegrationSpec(
            service_id="energy_management",
            name="Energy Management System (EMS)", category=IntegrationCategory.CUSTOM,
            description="Energy management — consumption, demand response, solar, battery, SCADA integration",
            base_url="",
            auth_method=IntegrationAuthMethod.API_KEY,
            actions=[
                IntegrationAction("get_consumption", "Get energy consumption", "GET", "/ems/consumption"),
                IntegrationAction("get_demand", "Get demand data", "GET", "/ems/demand"),
                IntegrationAction("set_demand_response", "Configure demand response", "POST", "/ems/demand_response"),
                IntegrationAction("get_solar_output", "Get solar generation data", "GET", "/ems/solar"),
                IntegrationAction("get_battery_status", "Get battery storage status", "GET", "/ems/battery"),
                IntegrationAction("generate_report", "Generate energy report", "POST", "/ems/reports"),
                IntegrationAction("health_check", "Check EMS connection", "GET", "/ems/health"),
            ],
        ),
        # --- Website Builders / CMS ---
        IntegrationSpec(
            service_id="wordpress",
            name="WordPress", category=IntegrationCategory.WEBSITE_BUILDER,
            description="WordPress CMS — pull pages, posts, forms, WooCommerce orders, and site analytics as automation inputs",
            base_url="https://{site}/wp-json",
            auth_method=IntegrationAuthMethod.BASIC_AUTH,
            actions=[
                IntegrationAction("list_posts", "List published posts", "GET", "/wp/v2/posts"),
                IntegrationAction("get_post", "Get a single post", "GET", "/wp/v2/posts/{post_id}"),
                IntegrationAction("create_post", "Create a new post", "POST", "/wp/v2/posts"),
                IntegrationAction("update_post", "Update an existing post", "PUT", "/wp/v2/posts/{post_id}"),
                IntegrationAction("list_pages", "List published pages", "GET", "/wp/v2/pages"),
                IntegrationAction("list_media", "List media library items", "GET", "/wp/v2/media"),
                IntegrationAction("list_users", "List site users", "GET", "/wp/v2/users"),
                IntegrationAction("list_comments", "List comments", "GET", "/wp/v2/comments"),
                IntegrationAction("get_site_settings", "Get site settings", "GET", "/wp/v2/settings"),
                IntegrationAction("list_form_entries", "List form entries (Contact Form 7 / Gravity Forms)", "GET", "/gf/v2/entries"),
                IntegrationAction("list_wc_orders", "List WooCommerce orders", "GET", "/wc/v3/orders"),
                IntegrationAction("list_wc_products", "List WooCommerce products", "GET", "/wc/v3/products"),
                IntegrationAction("list_wc_customers", "List WooCommerce customers", "GET", "/wc/v3/customers"),
                IntegrationAction("get_analytics", "Get site analytics summary", "GET", "/wp-site-health/v1/tests/background-updates"),
                IntegrationAction("health_check", "Check WordPress REST API connectivity", "GET", "/wp/v2"),
            ],
        ),
        IntegrationSpec(
            service_id="wix",
            name="Wix", category=IntegrationCategory.WEBSITE_BUILDER,
            description="Wix website platform — pull site content, form submissions, bookings, e-commerce orders, and contacts as automation inputs",
            base_url="https://www.wixapis.com",
            auth_method=IntegrationAuthMethod.BEARER_TOKEN,
            actions=[
                IntegrationAction("list_site_pages", "List site pages", "GET", "/site-properties/v4/properties"),
                IntegrationAction("list_blog_posts", "List blog posts", "GET", "/blog/v3/posts"),
                IntegrationAction("get_blog_post", "Get a blog post", "GET", "/blog/v3/posts/{post_id}"),
                IntegrationAction("list_form_submissions", "List form submissions", "GET", "/forms/v4/submissions"),
                IntegrationAction("list_contacts", "List CRM contacts", "GET", "/contacts/v4/contacts"),
                IntegrationAction("create_contact", "Create a CRM contact", "POST", "/contacts/v4/contacts"),
                IntegrationAction("list_orders", "List e-commerce orders", "GET", "/stores/v2/orders"),
                IntegrationAction("list_products", "List e-commerce products", "GET", "/stores/v1/products"),
                IntegrationAction("list_bookings", "List bookings / appointments", "GET", "/bookings/v2/bookings"),
                IntegrationAction("list_members", "List site members", "GET", "/members/v1/members"),
                IntegrationAction("get_site_properties", "Get site properties", "GET", "/site-properties/v4/properties"),
                IntegrationAction("list_collections", "List CMS data collections", "GET", "/data/v2/collections"),
                IntegrationAction("query_collection", "Query items in a CMS collection", "POST", "/data/v2/items/query"),
                IntegrationAction("health_check", "Check Wix API connectivity", "GET", "/site-properties/v4/properties"),
            ],
        ),
        IntegrationSpec(
            service_id="squarespace",
            name="Squarespace", category=IntegrationCategory.WEBSITE_BUILDER,
            description="Squarespace website platform — pull pages, blog posts, e-commerce orders, form submissions, and inventory as automation inputs",
            base_url="https://api.squarespace.com/1.0",
            auth_method=IntegrationAuthMethod.BEARER_TOKEN,
            actions=[
                IntegrationAction("list_orders", "List e-commerce orders", "GET", "/commerce/orders"),
                IntegrationAction("get_order", "Get a single order", "GET", "/commerce/orders/{order_id}"),
                IntegrationAction("list_products", "List products", "GET", "/commerce/products"),
                IntegrationAction("list_inventory", "List inventory levels", "GET", "/commerce/inventory"),
                IntegrationAction("list_profiles", "List customer profiles", "GET", "/profiles"),
                IntegrationAction("list_form_submissions", "List form submissions", "GET", "/forms/submissions"),
                IntegrationAction("get_site_info", "Get site information", "GET", "/sites"),
                IntegrationAction("health_check", "Check Squarespace API connectivity", "GET", "/sites"),
            ],
        ),
        IntegrationSpec(
            service_id="webflow",
            name="Webflow", category=IntegrationCategory.WEBSITE_BUILDER,
            description="Webflow website builder — pull CMS collections, form submissions, e-commerce orders, and site structure as automation inputs",
            base_url="https://api.webflow.com/v2",
            auth_method=IntegrationAuthMethod.BEARER_TOKEN,
            actions=[
                IntegrationAction("list_sites", "List sites", "GET", "/sites"),
                IntegrationAction("get_site", "Get site details", "GET", "/sites/{site_id}"),
                IntegrationAction("list_collections", "List CMS collections", "GET", "/sites/{site_id}/collections"),
                IntegrationAction("list_collection_items", "List items in a CMS collection", "GET", "/collections/{collection_id}/items"),
                IntegrationAction("create_collection_item", "Create a CMS item", "POST", "/collections/{collection_id}/items"),
                IntegrationAction("list_form_submissions", "List form submissions", "GET", "/sites/{site_id}/form-submissions"),
                IntegrationAction("list_orders", "List e-commerce orders", "GET", "/sites/{site_id}/orders"),
                IntegrationAction("list_products", "List e-commerce products", "GET", "/sites/{site_id}/products"),
                IntegrationAction("health_check", "Check Webflow API connectivity", "GET", "/sites"),
            ],
        ),
    ]


# ---------------------------------------------------------------------------
# Main registry
# ---------------------------------------------------------------------------

class UniversalIntegrationAdapter:
    """
    Plug-and-play registry for connecting any external service to Murphy System.

    Comes pre-loaded with 80+ integration templates. Users can:

    1. **Use a template** — ``adapter.configure("slack", {"token": "xoxb-..."})``
    2. **Add a custom service** — ``adapter.register(IntegrationSpec(...))``
    3. **Register handlers** — ``adapter.register_handler("slack", "send_message", my_fn)``
    4. **Execute actions** — ``adapter.execute("slack", "send_message", {"channel": "#general"})``

    Thread-safe with per-service rate limiting and health checks.
    """

    MAX_LOG_SIZE = 1000

    def __init__(self):
        self._lock = threading.Lock()
        self._integrations: Dict[str, _IntegrationInstance] = {}
        self._action_log: List[Dict[str, Any]] = []
        self._register_defaults()

        logger.info(
            "UniversalIntegrationAdapter initialized with %d templates",
            len(self._integrations),
        )

    # -- registration -------------------------------------------------------

    def _register_defaults(self) -> None:
        for spec in _default_integration_templates():
            self._integrations[spec.service_id] = _IntegrationInstance(spec)

    def register(self, spec: IntegrationSpec) -> Dict[str, Any]:
        """Register a new integration (or overwrite an existing template)."""
        with self._lock:
            self._integrations[spec.service_id] = _IntegrationInstance(spec)
        return {"registered": spec.service_id, "name": spec.name}

    def unregister(self, service_id: str) -> bool:
        """Remove an integration."""
        with self._lock:
            return self._integrations.pop(service_id, None) is not None

    # -- configuration ------------------------------------------------------

    def configure(self, service_id: str, credentials: Dict[str, str]) -> Dict[str, Any]:
        """Configure credentials for a registered integration."""
        with self._lock:
            inst = self._integrations.get(service_id)
            if inst is None:
                return {"error": f"Unknown service '{service_id}'"}
            inst.configure(credentials)
            return {"configured": service_id, "status": inst.status.value}

    # -- execution ----------------------------------------------------------

    def execute(
        self,
        service_id: str,
        action_name: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> ActionResult:
        """Execute an action on a service."""
        with self._lock:
            inst = self._integrations.get(service_id)
        if inst is None:
            return ActionResult(
                action_name=action_name,
                service_id=service_id,
                status=ActionStatus.FAILED,
                error=f"Unknown service '{service_id}'",
            )
        result = inst.execute_action(action_name, params)
        with self._lock:
            if len(self._action_log) >= self.MAX_LOG_SIZE:
                self._action_log.pop(0)
            capped_append(self._action_log, result.to_dict())
        return result

    def register_handler(
        self,
        service_id: str,
        action_name: str,
        handler: Callable,
    ) -> bool:
        """Register a custom handler function for a service action."""
        with self._lock:
            inst = self._integrations.get(service_id)
            if inst is None:
                return False
            inst.register_handler(action_name, handler)
            return True

    # -- discovery ----------------------------------------------------------

    def list_services(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all registered services, optionally filtered by category."""
        with self._lock:
            services = []
            for inst in self._integrations.values():
                if category and inst.spec.category.value != category:
                    continue
                services.append({
                    "service_id": inst.spec.service_id,
                    "name": inst.spec.name,
                    "category": inst.spec.category.value,
                    "description": inst.spec.description,
                    "status": inst.status.value,
                    "configured": bool(inst.credentials) or inst.spec.auth_method == IntegrationAuthMethod.NONE,
                    "actions": [a.name for a in inst.spec.actions],
                })
            return services

    def list_categories(self) -> List[str]:
        """Return all available integration categories."""
        return [c.value for c in IntegrationCategory]

    def get_service(self, service_id: str) -> Optional[Dict[str, Any]]:
        """Get full details for a service."""
        with self._lock:
            inst = self._integrations.get(service_id)
            if inst is None:
                return None
            return {
                **inst.spec.to_dict(),
                "status": inst.status.value,
                "configured": bool(inst.credentials) or inst.spec.auth_method == IntegrationAuthMethod.NONE,
                "request_count": inst.request_count,
                "error_count": inst.error_count,
            }

    # -- health -------------------------------------------------------------

    def health_check_all(self) -> Dict[str, Any]:
        """Run health checks on all integrations."""
        with self._lock:
            results = {}
            for sid, inst in self._integrations.items():
                results[sid] = inst.health_check()
            healthy = sum(1 for r in results.values() if r["status"] == "healthy")
            total = len(results)
            return {
                "total": total,
                "healthy": healthy,
                "services": results,
            }

    # -- statistics ---------------------------------------------------------

    def statistics(self) -> Dict[str, Any]:
        """Return adapter statistics."""
        with self._lock:
            total = len(self._integrations)
            configured = sum(
                1 for i in self._integrations.values()
                if i.credentials or i.spec.auth_method == IntegrationAuthMethod.NONE
            )
            categories = {}
            for inst in self._integrations.values():
                cat = inst.spec.category.value
                categories[cat] = categories.get(cat, 0) + 1
            return {
                "total_integrations": total,
                "configured": configured,
                "categories": categories,
                "action_log_size": len(self._action_log),
            }

    def get_action_log(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Return recent action execution log."""
        with self._lock:
            return list(self._action_log[-limit:])
