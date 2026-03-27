"""
World Model Integration Registry — Murphy System.

Central registry of all 20+ external integrations available for the world model.
Each integration is discoverable, configurable, and testable from here.

Usage:
    from src.integrations.world_model_registry import WorldModelRegistry

    registry = WorldModelRegistry()
    connector = registry.get("hubspot")
    connector.configure({"HUBSPOT_API_KEY": "..."})
    contacts = connector.list_contacts()
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Type

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy import map — avoids importing all connectors at module load time
# ---------------------------------------------------------------------------

_CONNECTOR_MAP: Dict[str, str] = {
    # Category: CRM
    "hubspot":           "integrations.hubspot_connector.HubSpotConnector",
    # Category: Email Marketing
    "mailchimp":         "integrations.mailchimp_connector.MailchimpConnector",
    # Category: Cloud Storage
    "google_drive":      "integrations.google_drive_connector.GoogleDriveConnector",
    "dropbox":           "integrations.dropbox_connector.DropboxConnector",
    # Category: Communication
    "discord":           "integrations.discord_connector.DiscordConnector",
    "telegram":          "integrations.telegram_connector.TelegramConnector",
    # Category: Project Management
    "trello":            "integrations.trello_connector.TrelloConnector",
    "asana":             "integrations.asana_connector.AsanaConnector",
    # Category: E-Commerce
    "shopify":           "integrations.shopify_connector.ShopifyConnector",
    # Category: Payments
    "stripe":            "integrations.stripe_connector.StripeConnector",
    # Category: Analytics
    "google_analytics":  "integrations.google_analytics_connector.GoogleAnalyticsConnector",
    # Category: Social Media
    "twitter":           "integrations.twitter_connector.TwitterConnector",
    # Category: Database / Backend
    "supabase":          "integrations.supabase_connector.SupabaseConnector",
    "firebase":          "integrations.firebase_connector.FirebaseConnector",
    # Category: AI/ML
    "openai":            "integrations.openai_connector.OpenAIConnector",
    "anthropic":         "integrations.anthropic_connector.AnthropicConnector",
    # Category: Monitoring
    "datadog":           "integrations.datadog_connector.DatadogConnector",
    # Category: DNS/CDN
    "cloudflare":        "integrations.cloudflare_connector.CloudflareConnector",
    # Category: Market Data
    "yahoo_finance":     "integrations.yahoo_finance_connector.YahooFinanceConnector",
    # Category: Weather
    "openweathermap":    "integrations.openweathermap_connector.OpenWeatherMapConnector",
    # Category: Industrial / SCADA
    "scada":             "integrations.scada_connector.SCADAConnector",
}

# Human-readable metadata for each integration
_INTEGRATION_META: Dict[str, Dict[str, Any]] = {
    "hubspot":          {"name": "HubSpot",           "category": "crm",             "free": True},
    "mailchimp":        {"name": "Mailchimp",          "category": "email_marketing",  "free": True},
    "google_drive":     {"name": "Google Drive",       "category": "cloud_storage",    "free": True},
    "dropbox":          {"name": "Dropbox",            "category": "cloud_storage",    "free": True},
    "discord":          {"name": "Discord",            "category": "communication",    "free": True},
    "telegram":         {"name": "Telegram",           "category": "communication",    "free": True},
    "trello":           {"name": "Trello",             "category": "project_mgmt",     "free": True},
    "asana":            {"name": "Asana",              "category": "project_mgmt",     "free": True},
    "shopify":          {"name": "Shopify",            "category": "ecommerce",        "free": False},
    "stripe":           {"name": "Stripe",             "category": "payments",         "free": True},
    "google_analytics": {"name": "Google Analytics",  "category": "analytics",        "free": True},
    "twitter":          {"name": "Twitter / X",        "category": "social_media",     "free": True},
    "supabase":         {"name": "Supabase",           "category": "database",         "free": True},
    "firebase":         {"name": "Firebase",           "category": "database",         "free": True},
    "openai":           {"name": "OpenAI",             "category": "ai_ml",            "free": False},
    "anthropic":        {"name": "Anthropic",          "category": "ai_ml",            "free": False},
    "datadog":          {"name": "Datadog",            "category": "monitoring",       "free": True},
    "cloudflare":       {"name": "Cloudflare",         "category": "dns_cdn",          "free": True},
    "yahoo_finance":    {"name": "Yahoo Finance",      "category": "market_data",      "free": True},
    "openweathermap":   {"name": "OpenWeatherMap",     "category": "weather",          "free": True},
    "scada":            {"name": "SCADA / ICS",        "category": "industrial",       "free": True},
}


def _import_connector_class(dotted: str) -> Any:
    """Lazily import a connector class from a dotted path."""
    parts = dotted.rsplit(".", 1)
    module_path, class_name = parts[0], parts[1]
    import importlib
    try:
        mod = importlib.import_module(module_path)
    except ImportError:
        # Try relative
        mod = importlib.import_module("src." + module_path)
    return getattr(mod, class_name)


class WorldModelRegistry:
    """
    Registry for all external integrations in the Murphy System world model.

    Connectors are instantiated lazily on first access. Credentials can be
    supplied per-connector or loaded automatically from environment variables.
    """

    def __init__(self) -> None:
        self._instances: Dict[str, Any] = {}

    def get(self, integration_id: str,
            credentials: Optional[Dict[str, str]] = None) -> Any:
        """
        Return a configured connector instance.

        If credentials are provided, the connector is (re-)configured with them.
        Otherwise it uses environment variables or a previous configure() call.
        """
        if integration_id not in _CONNECTOR_MAP:
            raise ValueError(
                f"Unknown integration '{integration_id}'. "
                f"Available: {sorted(_CONNECTOR_MAP.keys())}"
            )

        instance = self._instances.get(integration_id)

        if instance is None:
            try:
                cls = _import_connector_class(_CONNECTOR_MAP[integration_id])
                instance = cls()
                self._instances[integration_id] = instance
            except Exception as exc:
                logger.error("Failed to instantiate connector '%s': %s", integration_id, exc)
                raise

        if credentials:
            instance.configure(credentials)

        return instance

    def list_integrations(self) -> List[Dict[str, Any]]:
        """Return metadata for all available integrations."""
        result = []
        for iid, meta in _INTEGRATION_META.items():
            instance = self._instances.get(iid)
            configured = instance.is_configured() if instance else False
            result.append({
                "id": iid,
                "name": meta["name"],
                "category": meta["category"],
                "free_tier": meta["free"],
                "configured": configured,
            })
        return result

    def list_configured(self) -> List[str]:
        """Return IDs of all configured integrations."""
        return [iid for iid, inst in self._instances.items()
                if inst.is_configured()]

    def health_check_all(self) -> Dict[str, Dict[str, Any]]:
        """Run health checks on all instantiated connectors."""
        results = {}
        for iid, instance in self._instances.items():
            try:
                results[iid] = instance.health_check()
            except Exception as exc:
                results[iid] = {"success": False, "error": str(exc), "integration": iid}
        return results

    def configure_all(self, credentials_map: Dict[str, Dict[str, str]]) -> None:
        """Bulk configure integrations from a map of {integration_id: credentials_dict}."""
        for iid, creds in credentials_map.items():
            try:
                self.get(iid, credentials=creds)
            except ValueError:
                logger.warning("Unknown integration id '%s' in credentials map", iid)


# Module-level singleton for convenience
_default_registry: Optional[WorldModelRegistry] = None


def get_registry() -> WorldModelRegistry:
    """Return the default global registry instance."""
    global _default_registry
    if _default_registry is None:
        _default_registry = WorldModelRegistry()
    return _default_registry
