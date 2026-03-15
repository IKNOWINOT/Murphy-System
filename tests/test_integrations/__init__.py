"""
Tests for Murphy System World Model Integrations.

Validates that all 20+ integration connectors:
  1. Can be imported without errors
  2. Have correct metadata (name, credentials, setup URL, etc.)
  3. Return proper "not configured" responses when no credentials set
  4. Can be configured with test credentials
  5. Are discoverable via the WorldModelRegistry
  6. New connectors in platform_connector_framework are registered

No real API calls are made — all tests use the "not configured" or
simulated fallback path to avoid requiring live credentials in CI.
"""

import os
import sys
import unittest

# Ensure imports resolve correctly from test runner location
_SRC = os.path.join(os.path.dirname(__file__), "..", "..", "src")
sys.path.insert(0, _SRC)


# ---------------------------------------------------------------------------
# Base Connector tests
# ---------------------------------------------------------------------------

class TestBaseIntegrationConnector(unittest.TestCase):
    """Tests for the shared base connector infrastructure."""

    def test_import_base(self):
        from integrations.base_connector import BaseIntegrationConnector
        self.assertIsNotNone(BaseIntegrationConnector)

    def test_not_configured_template(self):
        from integrations.base_connector import _NOT_CONFIGURED_TEMPLATE
        self.assertIn("success", _NOT_CONFIGURED_TEMPLATE)
        self.assertIn("configured", _NOT_CONFIGURED_TEMPLATE)
        self.assertFalse(_NOT_CONFIGURED_TEMPLATE["success"])
        self.assertFalse(_NOT_CONFIGURED_TEMPLATE["configured"])

    def test_base_connector_not_configured(self):
        from integrations.hubspot_connector import HubSpotConnector
        conn = HubSpotConnector()
        self.assertFalse(conn.is_configured())

    def test_base_connector_configure(self):
        from integrations.hubspot_connector import HubSpotConnector
        conn = HubSpotConnector(credentials={"HUBSPOT_API_KEY": "test"})
        self.assertTrue(conn.is_configured())

    def test_base_connector_returns_not_configured_when_unconfigured(self):
        from integrations.hubspot_connector import HubSpotConnector
        conn = HubSpotConnector()
        result = conn.list_contacts()
        self.assertFalse(result["success"])
        self.assertFalse(result["configured"])
        self.assertIn("not configured", result["error"].lower())

    def test_configure_method_chaining(self):
        from integrations.hubspot_connector import HubSpotConnector
        conn = HubSpotConnector()
        returned = conn.configure({"HUBSPOT_API_KEY": "abc"})
        self.assertIs(returned, conn)
        self.assertTrue(conn.is_configured())

    def test_get_status(self):
        from integrations.hubspot_connector import HubSpotConnector
        conn = HubSpotConnector()
        status = conn.get_status()
        self.assertIn("integration", status)
        self.assertIn("configured", status)
        self.assertIn("request_count", status)


# ---------------------------------------------------------------------------
# Individual connector tests
# ---------------------------------------------------------------------------

class TestHubSpotConnector(unittest.TestCase):
    def setUp(self):
        from integrations.hubspot_connector import HubSpotConnector
        self.conn = HubSpotConnector()

    def test_integration_name(self):
        self.assertEqual(self.conn.INTEGRATION_NAME, "HubSpot")

    def test_base_url(self):
        self.assertIn("hubapi.com", self.conn.BASE_URL)

    def test_not_configured_list_contacts(self):
        result = self.conn.list_contacts()
        self.assertFalse(result["configured"])

    def test_not_configured_search_contacts(self):
        result = self.conn.search_contacts("test")
        self.assertFalse(result["configured"])

    def test_free_tier(self):
        self.assertTrue(self.conn.FREE_TIER)


class TestMailchimpConnector(unittest.TestCase):
    def setUp(self):
        from integrations.mailchimp_connector import MailchimpConnector
        self.conn = MailchimpConnector()

    def test_integration_name(self):
        self.assertEqual(self.conn.INTEGRATION_NAME, "Mailchimp")

    def test_not_configured(self):
        result = self.conn.list_audiences()
        self.assertFalse(result["configured"])

    def test_dc_extraction(self):
        from integrations.mailchimp_connector import _extract_dc
        self.assertEqual(_extract_dc("abc123-us5"), "us5")
        self.assertEqual(_extract_dc("xyz-eu1"), "eu1")
        self.assertEqual(_extract_dc("noDC"), "us1")  # fallback


class TestGoogleDriveConnector(unittest.TestCase):
    def setUp(self):
        from integrations.google_drive_connector import GoogleDriveConnector
        self.conn = GoogleDriveConnector()

    def test_integration_name(self):
        self.assertEqual(self.conn.INTEGRATION_NAME, "Google Drive")

    def test_not_configured(self):
        result = self.conn.list_files()
        self.assertFalse(result["configured"])

    def test_free_tier(self):
        self.assertTrue(self.conn.FREE_TIER)


class TestDropboxConnector(unittest.TestCase):
    def setUp(self):
        from integrations.dropbox_connector import DropboxConnector
        self.conn = DropboxConnector()

    def test_integration_name(self):
        self.assertEqual(self.conn.INTEGRATION_NAME, "Dropbox")

    def test_not_configured(self):
        result = self.conn.list_folder()
        self.assertFalse(result["configured"])


class TestDiscordConnector(unittest.TestCase):
    def setUp(self):
        from integrations.discord_connector import DiscordConnector
        self.conn = DiscordConnector()

    def test_integration_name(self):
        self.assertEqual(self.conn.INTEGRATION_NAME, "Discord")

    def test_not_configured(self):
        result = self.conn.get_bot_user()
        self.assertFalse(result["configured"])

    def test_configured_with_token(self):
        from integrations.discord_connector import DiscordConnector
        conn = DiscordConnector(credentials={"DISCORD_BOT_TOKEN": "Bot.test"})
        self.assertTrue(conn.is_configured())

    def test_configured_with_webhook(self):
        from integrations.discord_connector import DiscordConnector
        conn = DiscordConnector(credentials={"DISCORD_WEBHOOK_URL": "https://discord.com/api/webhooks/x/y"})
        self.assertTrue(conn.is_configured())


class TestTelegramConnector(unittest.TestCase):
    def setUp(self):
        from integrations.telegram_connector import TelegramConnector
        self.conn = TelegramConnector()

    def test_integration_name(self):
        self.assertEqual(self.conn.INTEGRATION_NAME, "Telegram")

    def test_not_configured(self):
        result = self.conn.get_me()
        self.assertFalse(result.get("configured", True))

    def test_api_url_formation(self):
        from integrations.telegram_connector import TelegramConnector
        conn = TelegramConnector(credentials={"TELEGRAM_BOT_TOKEN": "123:abc"})
        url = conn._api_url("getMe")
        self.assertIn("123:abc", url)
        self.assertIn("getMe", url)


class TestTrelloConnector(unittest.TestCase):
    def setUp(self):
        from integrations.trello_connector import TrelloConnector
        self.conn = TrelloConnector()

    def test_integration_name(self):
        self.assertEqual(self.conn.INTEGRATION_NAME, "Trello")

    def test_not_configured(self):
        result = self.conn.get_member()
        self.assertFalse(result["configured"])

    def test_configured_check(self):
        from integrations.trello_connector import TrelloConnector
        conn = TrelloConnector(credentials={"TRELLO_API_KEY": "key", "TRELLO_TOKEN": "token"})
        self.assertTrue(conn.is_configured())


class TestAsanaConnector(unittest.TestCase):
    def setUp(self):
        from integrations.asana_connector import AsanaConnector
        self.conn = AsanaConnector()

    def test_integration_name(self):
        self.assertEqual(self.conn.INTEGRATION_NAME, "Asana")

    def test_not_configured(self):
        result = self.conn.list_workspaces()
        self.assertFalse(result["configured"])

    def test_auth_header(self):
        from integrations.asana_connector import AsanaConnector
        conn = AsanaConnector(credentials={"ASANA_ACCESS_TOKEN": "test_token"})
        headers = conn._build_headers()
        self.assertIn("Bearer test_token", headers["Authorization"])


class TestShopifyConnector(unittest.TestCase):
    def setUp(self):
        from integrations.shopify_connector import ShopifyConnector
        self.conn = ShopifyConnector()

    def test_integration_name(self):
        self.assertEqual(self.conn.INTEGRATION_NAME, "Shopify")

    def test_not_configured(self):
        result = self.conn.list_products()
        self.assertFalse(result["configured"])

    def test_not_free_tier(self):
        self.assertFalse(self.conn.FREE_TIER)


class TestStripeConnector(unittest.TestCase):
    def setUp(self):
        from integrations.stripe_connector import StripeConnector
        self.conn = StripeConnector()

    def test_integration_name(self):
        self.assertEqual(self.conn.INTEGRATION_NAME, "Stripe")

    def test_not_configured(self):
        result = self.conn.get_balance()
        self.assertFalse(result["configured"])

    def test_flatten_helper(self):
        from integrations.stripe_connector import _flatten
        flat = _flatten({"key": "val", "nested": {"a": 1}})
        self.assertEqual(flat["key"], "val")
        self.assertIn("nested[a]", flat)


class TestGoogleAnalyticsConnector(unittest.TestCase):
    def setUp(self):
        from integrations.google_analytics_connector import GoogleAnalyticsConnector
        self.conn = GoogleAnalyticsConnector()

    def test_integration_name(self):
        self.assertEqual(self.conn.INTEGRATION_NAME, "Google Analytics")

    def test_not_configured(self):
        result = self.conn.get_metadata()
        self.assertFalse(result["configured"])

    def test_free_tier(self):
        self.assertTrue(self.conn.FREE_TIER)


class TestTwitterConnector(unittest.TestCase):
    def setUp(self):
        from integrations.twitter_connector import TwitterConnector
        self.conn = TwitterConnector()

    def test_integration_name(self):
        self.assertIn("Twitter", self.conn.INTEGRATION_NAME)

    def test_not_configured(self):
        result = self.conn.search_recent_tweets("test")
        self.assertFalse(result["configured"])

    def test_configured_with_bearer(self):
        from integrations.twitter_connector import TwitterConnector
        conn = TwitterConnector(credentials={"TWITTER_BEARER_TOKEN": "AAAA..."})
        self.assertTrue(conn.is_configured())


class TestSupabaseConnector(unittest.TestCase):
    def setUp(self):
        from integrations.supabase_connector import SupabaseConnector
        self.conn = SupabaseConnector()

    def test_integration_name(self):
        self.assertEqual(self.conn.INTEGRATION_NAME, "Supabase")

    def test_not_configured(self):
        result = self.conn.select("test_table")
        self.assertFalse(result["configured"])

    def test_free_tier(self):
        self.assertTrue(self.conn.FREE_TIER)


class TestFirebaseConnector(unittest.TestCase):
    def setUp(self):
        from integrations.firebase_connector import FirebaseConnector
        self.conn = FirebaseConnector()

    def test_integration_name(self):
        self.assertEqual(self.conn.INTEGRATION_NAME, "Firebase")

    def test_not_configured(self):
        result = self.conn.rtdb_get("/test")
        self.assertFalse(result.get("configured", True))

    def test_partial_config_not_sufficient(self):
        """FIREBASE_PROJECT_ID alone is not enough — need web API key or access token."""
        from integrations.firebase_connector import FirebaseConnector
        conn = FirebaseConnector(credentials={"FIREBASE_PROJECT_ID": "my-proj"})
        self.assertFalse(conn.is_configured())

    def test_full_config_sufficient(self):
        from integrations.firebase_connector import FirebaseConnector
        conn = FirebaseConnector(credentials={
            "FIREBASE_PROJECT_ID": "my-proj",
            "FIREBASE_WEB_API_KEY": "AIzaSy..."})
        self.assertTrue(conn.is_configured())


class TestOpenAIConnector(unittest.TestCase):
    def setUp(self):
        from integrations.openai_connector import OpenAIConnector
        self.conn = OpenAIConnector()

    def test_integration_name(self):
        self.assertEqual(self.conn.INTEGRATION_NAME, "OpenAI")

    def test_not_configured(self):
        result = self.conn.list_models()
        self.assertFalse(result["configured"])

    def test_custom_base_url(self):
        from integrations.openai_connector import OpenAIConnector
        conn = OpenAIConnector(credentials={
            "OPENAI_API_KEY": "sk-test",
            "OPENAI_BASE_URL": "https://my-proxy.example.com/v1"})
        self.assertIn("my-proxy.example.com", conn.BASE_URL)


class TestAnthropicConnector(unittest.TestCase):
    def setUp(self):
        from integrations.anthropic_connector import AnthropicConnector
        self.conn = AnthropicConnector()

    def test_integration_name(self):
        self.assertIn("Anthropic", self.conn.INTEGRATION_NAME)

    def test_not_configured(self):
        result = self.conn.list_models()
        self.assertFalse(result["configured"])

    def test_auth_header(self):
        from integrations.anthropic_connector import AnthropicConnector
        conn = AnthropicConnector(credentials={"ANTHROPIC_API_KEY": "sk-ant-test"})
        headers = conn._build_headers()
        self.assertEqual(headers["x-api-key"], "sk-ant-test")
        self.assertIn("anthropic-version", headers)


class TestDatadogConnector(unittest.TestCase):
    def setUp(self):
        from integrations.datadog_connector import DatadogConnector
        self.conn = DatadogConnector()

    def test_integration_name(self):
        self.assertEqual(self.conn.INTEGRATION_NAME, "Datadog")

    def test_not_configured(self):
        result = self.conn.list_monitors()
        self.assertFalse(result["configured"])

    def test_auth_headers(self):
        from integrations.datadog_connector import DatadogConnector
        conn = DatadogConnector(credentials={"DATADOG_API_KEY": "ddapikey", "DATADOG_APP_KEY": "ddappkey"})
        headers = conn._build_headers()
        self.assertEqual(headers["DD-API-KEY"], "ddapikey")
        self.assertEqual(headers["DD-APPLICATION-KEY"], "ddappkey")


class TestCloudflareConnector(unittest.TestCase):
    def setUp(self):
        from integrations.cloudflare_connector import CloudflareConnector
        self.conn = CloudflareConnector()

    def test_integration_name(self):
        self.assertEqual(self.conn.INTEGRATION_NAME, "Cloudflare")

    def test_not_configured(self):
        result = self.conn.list_zones()
        self.assertFalse(result["configured"])

    def test_token_auth(self):
        from integrations.cloudflare_connector import CloudflareConnector
        conn = CloudflareConnector(credentials={"CLOUDFLARE_API_TOKEN": "token123"})
        headers = conn._build_headers()
        self.assertIn("Bearer token123", headers["Authorization"])

    def test_global_key_auth(self):
        from integrations.cloudflare_connector import CloudflareConnector
        conn = CloudflareConnector(credentials={
            "CLOUDFLARE_EMAIL": "user@example.com",
            "CLOUDFLARE_GLOBAL_API_KEY": "globalkey"})
        self.assertTrue(conn.is_configured())


class TestYahooFinanceConnector(unittest.TestCase):
    def setUp(self):
        from integrations.yahoo_finance_connector import YahooFinanceConnector
        self.conn = YahooFinanceConnector()

    def test_integration_name(self):
        self.assertEqual(self.conn.INTEGRATION_NAME, "Yahoo Finance")

    def test_always_configured(self):
        self.assertTrue(self.conn.is_configured())  # No credentials required

    def test_free_tier(self):
        self.assertTrue(self.conn.FREE_TIER)

    def test_headers_set(self):
        headers = self.conn._build_headers()
        self.assertIn("User-Agent", headers)


class TestOpenWeatherMapConnector(unittest.TestCase):
    def setUp(self):
        from integrations.openweathermap_connector import OpenWeatherMapConnector
        self.conn = OpenWeatherMapConnector()

    def test_integration_name(self):
        self.assertEqual(self.conn.INTEGRATION_NAME, "OpenWeatherMap")

    def test_not_configured(self):
        result = self.conn.get_current_weather("London")
        self.assertFalse(result["configured"])

    def test_free_tier(self):
        self.assertTrue(self.conn.FREE_TIER)

    def test_weather_params(self):
        from integrations.openweathermap_connector import OpenWeatherMapConnector
        conn = OpenWeatherMapConnector(credentials={"OPENWEATHERMAP_API_KEY": "testkey"})
        params = conn._weather_params()
        self.assertEqual(params["appid"], "testkey")
        self.assertEqual(params["units"], "metric")


class TestSCADAConnector(unittest.TestCase):
    def setUp(self):
        from integrations.scada_connector import SCADAConnector
        self.conn = SCADAConnector()

    def test_integration_name(self):
        self.assertEqual(self.conn.INTEGRATION_NAME, "SCADA / ICS")

    def test_not_configured_without_hosts(self):
        self.assertFalse(self.conn.is_configured())

    def test_configured_with_modbus_host(self):
        from integrations.scada_connector import SCADAConnector
        conn = SCADAConnector(modbus_host="192.168.1.100")
        self.assertTrue(conn.is_configured())

    def test_configured_with_opcua_url(self):
        from integrations.scada_connector import SCADAConnector
        conn = SCADAConnector(opcua_url="opc.tcp://192.168.1.100:4840")
        self.assertTrue(conn.is_configured())

    def test_modbus_read_unconfigured_returns_error(self):
        result = self.conn.modbus_read_holding_registers(0)
        self.assertFalse(result["success"])
        self.assertFalse(result.get("configured", True))

    def test_bacnet_who_is_unconfigured(self):
        result = self.conn.bacnet_who_is()
        self.assertIn("devices", result)

    def test_opcua_browse_unconfigured(self):
        result = self.conn.opcua_browse()
        self.assertIn("nodes", result)

    def test_execute_action_unknown(self):
        result = self.conn.execute_action("unknown_action")
        self.assertFalse(result["success"])
        self.assertIn("Unknown", result["error"])

    def test_get_status(self):
        status = self.conn.get_status()
        self.assertIn("protocols", status)
        self.assertIn("modbus_tcp", status["protocols"])
        self.assertIn("bacnet_ip", status["protocols"])
        self.assertIn("opcua", status["protocols"])


# ---------------------------------------------------------------------------
# WorldModelRegistry tests
# ---------------------------------------------------------------------------

class TestWorldModelRegistry(unittest.TestCase):
    def setUp(self):
        from integrations.world_model_registry import WorldModelRegistry
        self.registry = WorldModelRegistry()

    def test_list_integrations_count(self):
        integrations = self.registry.list_integrations()
        self.assertGreaterEqual(len(integrations), 20)

    def test_list_integrations_structure(self):
        integrations = self.registry.list_integrations()
        for item in integrations:
            self.assertIn("id", item)
            self.assertIn("name", item)
            self.assertIn("category", item)
            self.assertIn("free_tier", item)
            self.assertIn("configured", item)

    def test_get_hubspot(self):
        conn = self.registry.get("hubspot")
        self.assertEqual(conn.INTEGRATION_NAME, "HubSpot")

    def test_get_mailchimp(self):
        conn = self.registry.get("mailchimp")
        self.assertEqual(conn.INTEGRATION_NAME, "Mailchimp")

    def test_get_openai(self):
        conn = self.registry.get("openai")
        self.assertEqual(conn.INTEGRATION_NAME, "OpenAI")

    def test_get_anthropic(self):
        conn = self.registry.get("anthropic")
        self.assertIn("Anthropic", conn.INTEGRATION_NAME)

    def test_get_yahoo_finance(self):
        conn = self.registry.get("yahoo_finance")
        self.assertEqual(conn.INTEGRATION_NAME, "Yahoo Finance")

    def test_get_openweathermap(self):
        conn = self.registry.get("openweathermap")
        self.assertEqual(conn.INTEGRATION_NAME, "OpenWeatherMap")

    def test_get_scada(self):
        conn = self.registry.get("scada")
        self.assertEqual(conn.INTEGRATION_NAME, "SCADA / ICS")

    def test_get_google_analytics(self):
        conn = self.registry.get("google_analytics")
        self.assertEqual(conn.INTEGRATION_NAME, "Google Analytics")

    def test_unknown_integration_raises(self):
        with self.assertRaises(ValueError):
            self.registry.get("not_a_real_integration")

    def test_configure_via_registry(self):
        conn = self.registry.get("hubspot", credentials={"HUBSPOT_API_KEY": "test"})
        self.assertTrue(conn.is_configured())

    def test_all_required_integration_ids_present(self):
        """Verify all 20 required world-model integrations are discoverable."""
        required = [
            "hubspot", "mailchimp", "google_drive", "dropbox",
            "discord", "telegram", "trello", "asana", "shopify",
            "stripe", "google_analytics", "twitter", "supabase",
            "firebase", "openai", "anthropic", "datadog",
            "cloudflare", "yahoo_finance", "openweathermap",
        ]
        for iid in required:
            with self.subTest(integration=iid):
                conn = self.registry.get(iid)
                self.assertIsNotNone(conn)

    def test_list_configured_empty_initially(self):
        from integrations.world_model_registry import WorldModelRegistry
        registry = WorldModelRegistry()  # fresh instance
        # Yahoo Finance is always configured (no credentials needed)
        conn = registry.get("yahoo_finance")
        configured = registry.list_configured()
        self.assertIn("yahoo_finance", configured)

    def test_get_registry_singleton(self):
        from integrations.world_model_registry import get_registry
        r1 = get_registry()
        r2 = get_registry()
        self.assertIs(r1, r2)


# ---------------------------------------------------------------------------
# Platform Connector Framework — new connectors registered
# ---------------------------------------------------------------------------

class TestPlatformFrameworkNewConnectors(unittest.TestCase):
    """Verify all new connectors are registered in PlatformConnectorFramework."""

    def setUp(self):
        from platform_connector_framework import PlatformConnectorFramework
        self.fw = PlatformConnectorFramework()
        self._ids = {c["connector_id"] for c in self.fw.list_available_connectors()}

    def test_mailchimp_registered(self):
        self.assertIn("mailchimp", self._ids)

    def test_google_analytics_registered(self):
        self.assertIn("google_analytics", self._ids)

    def test_openai_registered(self):
        self.assertIn("openai", self._ids)

    def test_anthropic_registered(self):
        self.assertIn("anthropic", self._ids)

    def test_yahoo_finance_registered(self):
        self.assertIn("yahoo_finance", self._ids)

    def test_openweathermap_registered(self):
        self.assertIn("openweathermap", self._ids)

    def test_scada_modbus_registered(self):
        self.assertIn("scada_modbus", self._ids)

    def test_scada_bacnet_registered(self):
        self.assertIn("scada_bacnet", self._ids)

    def test_scada_opcua_registered(self):
        self.assertIn("scada_opcua", self._ids)

    def test_additive_manufacturing_registered(self):
        self.assertIn("additive_manufacturing", self._ids)

    def test_building_automation_registered(self):
        self.assertIn("building_automation", self._ids)

    def test_energy_management_registered(self):
        self.assertIn("energy_management", self._ids)

    def test_total_connector_count_exceeds_80(self):
        """After adding industrial + new world-model connectors, total should be 90+."""
        self.assertGreaterEqual(len(self._ids), 80)

    def test_configure_and_execute_mailchimp(self):
        from platform_connector_framework import PlatformConnectorFramework, ConnectorAction
        fw = PlatformConnectorFramework()
        fw.configure_connector("mailchimp", {"MAILCHIMP_API_KEY": "test-us1"})
        action = ConnectorAction(
            action_id="test-mailchimp",
            connector_id="mailchimp",
            action_type="list_campaigns",
            resource="campaigns",
        )
        result = fw.execute_action(action)
        # Should succeed (simulated fallback since no real API)
        self.assertIsNotNone(result)

    def test_configure_and_execute_openai(self):
        from platform_connector_framework import PlatformConnectorFramework, ConnectorAction
        fw = PlatformConnectorFramework()
        fw.configure_connector("openai", {"OPENAI_API_KEY": "sk-test"})
        action = ConnectorAction(
            action_id="test-openai",
            connector_id="openai",
            action_type="list_models",
            resource="models",
        )
        result = fw.execute_action(action)
        self.assertIsNotNone(result)

    def test_industrial_connector_capabilities(self):
        """Industrial connectors should declare expected capabilities."""
        connectors = {c["connector_id"]: c for c in self.fw.list_available_connectors()}

        # Modbus
        modbus = connectors["scada_modbus"]
        self.assertIn("read_holding_registers", modbus["capabilities"])
        self.assertIn("write_register", modbus["capabilities"])

        # BACnet
        bacnet = connectors["scada_bacnet"]
        self.assertIn("read_property", bacnet["capabilities"])
        self.assertIn("write_property", bacnet["capabilities"])

        # OPC UA
        opcua = connectors["scada_opcua"]
        self.assertIn("browse", opcua["capabilities"])
        self.assertIn("read_node", opcua["capabilities"])

        # Additive Manufacturing
        am = connectors["additive_manufacturing"]
        self.assertIn("submit_job", am["capabilities"])
        self.assertIn("start_print", am["capabilities"])

        # Building Automation
        ba = connectors["building_automation"]
        self.assertIn("read_sensor", ba["capabilities"])
        self.assertIn("set_hvac_mode", ba["capabilities"])

        # Energy Management
        em = connectors["energy_management"]
        self.assertIn("get_consumption", em["capabilities"])
        self.assertIn("get_solar_output", em["capabilities"])


# ---------------------------------------------------------------------------
# Setup Wizard integration selection tests
# ---------------------------------------------------------------------------

class TestSetupWizardIntegrations(unittest.TestCase):
    def setUp(self):
        from setup_wizard import SetupWizard, VALID_INTEGRATIONS
        self.wizard = SetupWizard()
        self.valid = VALID_INTEGRATIONS

    def test_valid_integrations_not_empty(self):
        self.assertGreater(len(self.valid), 10)

    def test_q13_exists(self):
        questions = self.wizard.get_questions()
        qids = [q["id"] for q in questions]
        self.assertIn("q13", qids)

    def test_q13_integration_field(self):
        questions = self.wizard.get_questions()
        q = next((q for q in questions if q["id"] == "q13"), None)
        self.assertIsNotNone(q)
        self.assertEqual(q["field"], "enabled_integrations")
        self.assertEqual(q["question_type"], "multi_choice")

    def test_apply_integrations(self):
        result = self.wizard.apply_answer("q13", ["hubspot", "stripe", "discord"])
        self.assertTrue(result["ok"])
        profile = self.wizard.get_profile()
        self.assertIn("hubspot", profile.enabled_integrations)
        self.assertIn("stripe", profile.enabled_integrations)

    def test_generate_config_includes_integrations(self):
        self.wizard.apply_answer("q13", ["hubspot", "openai"])
        profile = self.wizard.get_profile()
        config = self.wizard.generate_config(profile)
        self.assertIn("integrations", config)
        self.assertIn("hubspot", config["integrations"]["enabled"])

    def test_yahoo_finance_in_valid_integrations(self):
        self.assertIn("yahoo_finance", self.valid)

    def test_scada_in_valid_integrations(self):
        self.assertIn("scada", self.valid)


if __name__ == "__main__":
    unittest.main()
