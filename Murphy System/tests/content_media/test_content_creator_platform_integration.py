"""
Integration tests for Content Creator Platform Modulator.

Validates platform registry, connector execution, cross-platform syndication,
analytics aggregation, and MODULE_CATALOG wiring.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestContentCreatorPlatformRegistry(unittest.TestCase):
    """Test content creator platform registry basics."""

    def setUp(self):
        try:
            from src.content_creator_platform_modulator import (
                ContentCreatorPlatformRegistry,
                PlatformType,
                get_status,
            )
            self.registry = ContentCreatorPlatformRegistry()
            self.PlatformType = PlatformType
            self.get_status = get_status
        except ImportError as exc:
            self.skipTest(f"Content creator platform modulator not available: {exc}")

    def test_get_status(self):
        status = self.get_status()
        self.assertEqual(status["module"], "content_creator_platform_modulator")
        self.assertEqual(status["status"], "operational")

    def test_default_platforms_registered(self):
        platforms = self.registry.list_platforms()
        for p in ["youtube", "twitch", "onlyfans", "tiktok", "patreon", "kick", "rumble"]:
            self.assertIn(p, platforms, f"Missing platform: {p}")

    def test_platform_count(self):
        stats = self.registry.statistics()
        self.assertGreaterEqual(stats["total_connectors"], 7)
        self.assertGreaterEqual(stats["enabled_connectors"], 7)

    def test_platform_types_coverage(self):
        stats = self.registry.statistics()
        by_type = stats["by_platform_type"]
        self.assertIn("video", by_type)
        self.assertIn("streaming", by_type)
        self.assertIn("subscription", by_type)
        self.assertIn("short_form", by_type)


class TestYouTubeConnector(unittest.TestCase):
    """Test YouTube platform connector."""

    def setUp(self):
        try:
            from src.content_creator_platform_modulator import ContentCreatorPlatformRegistry
            self.registry = ContentCreatorPlatformRegistry()
        except ImportError as exc:
            self.skipTest(f"Module not available: {exc}")

    def test_youtube_exists(self):
        c = self.registry.get_connector("youtube")
        self.assertIsNotNone(c)
        self.assertEqual(c.name, "YouTube")

    def test_youtube_capabilities(self):
        c = self.registry.get_connector("youtube")
        for cap in ["video_upload", "live_stream_management", "analytics_reporting",
                     "shorts_publishing", "monetization_tracking"]:
            self.assertIn(cap, c.capabilities, f"Missing YouTube capability: {cap}")

    def test_youtube_execute_action(self):
        result = self.registry.execute("youtube", "video_upload", {"title": "Test"})
        self.assertTrue(result["success"])
        self.assertEqual(result["platform"], "youtube")

    def test_youtube_content_types(self):
        c = self.registry.get_connector("youtube")
        self.assertIn("video", c.content_types)
        self.assertIn("live_stream", c.content_types)
        self.assertIn("short_video", c.content_types)


class TestTwitchConnector(unittest.TestCase):
    """Test Twitch platform connector."""

    def setUp(self):
        try:
            from src.content_creator_platform_modulator import ContentCreatorPlatformRegistry
            self.registry = ContentCreatorPlatformRegistry()
        except ImportError as exc:
            self.skipTest(f"Module not available: {exc}")

    def test_twitch_exists(self):
        c = self.registry.get_connector("twitch")
        self.assertIsNotNone(c)
        self.assertEqual(c.name, "Twitch")

    def test_twitch_capabilities(self):
        c = self.registry.get_connector("twitch")
        for cap in ["live_stream_management", "chat_moderation", "subscriber_management",
                     "bits_tracking", "prediction_management"]:
            self.assertIn(cap, c.capabilities, f"Missing Twitch capability: {cap}")

    def test_twitch_execute_action(self):
        result = self.registry.execute("twitch", "live_stream_management")
        self.assertTrue(result["success"])


class TestOnlyFansConnector(unittest.TestCase):
    """Test OnlyFans platform connector."""

    def setUp(self):
        try:
            from src.content_creator_platform_modulator import ContentCreatorPlatformRegistry
            self.registry = ContentCreatorPlatformRegistry()
        except ImportError as exc:
            self.skipTest(f"Module not available: {exc}")

    def test_onlyfans_exists(self):
        c = self.registry.get_connector("onlyfans")
        self.assertIsNotNone(c)
        self.assertEqual(c.name, "OnlyFans")

    def test_onlyfans_capabilities(self):
        c = self.registry.get_connector("onlyfans")
        for cap in ["content_publishing", "subscriber_management", "ppv_messaging",
                     "tip_tracking", "mass_messaging"]:
            self.assertIn(cap, c.capabilities, f"Missing OnlyFans capability: {cap}")

    def test_onlyfans_monetization(self):
        c = self.registry.get_connector("onlyfans")
        self.assertIn("subscriptions", c.monetization_models)
        self.assertIn("tips", c.monetization_models)
        self.assertIn("pay_per_view", c.monetization_models)

    def test_onlyfans_execute_action(self):
        result = self.registry.execute("onlyfans", "content_publishing")
        self.assertTrue(result["success"])


class TestTikTokConnector(unittest.TestCase):
    """Test TikTok platform connector."""

    def setUp(self):
        try:
            from src.content_creator_platform_modulator import ContentCreatorPlatformRegistry
            self.registry = ContentCreatorPlatformRegistry()
        except ImportError as exc:
            self.skipTest(f"Module not available: {exc}")

    def test_tiktok_exists(self):
        c = self.registry.get_connector("tiktok")
        self.assertIsNotNone(c)

    def test_tiktok_capabilities(self):
        c = self.registry.get_connector("tiktok")
        for cap in ["video_publishing", "analytics_reporting", "hashtag_analytics",
                     "creator_marketplace", "shop_management"]:
            self.assertIn(cap, c.capabilities, f"Missing TikTok capability: {cap}")


class TestPatreonConnector(unittest.TestCase):
    """Test Patreon platform connector."""

    def setUp(self):
        try:
            from src.content_creator_platform_modulator import ContentCreatorPlatformRegistry
            self.registry = ContentCreatorPlatformRegistry()
        except ImportError as exc:
            self.skipTest(f"Module not available: {exc}")

    def test_patreon_exists(self):
        c = self.registry.get_connector("patreon")
        self.assertIsNotNone(c)

    def test_patreon_capabilities(self):
        c = self.registry.get_connector("patreon")
        for cap in ["post_publishing", "tier_management", "member_management", "payout_tracking"]:
            self.assertIn(cap, c.capabilities, f"Missing Patreon capability: {cap}")


class TestKickRumbleConnectors(unittest.TestCase):
    """Test Kick and Rumble connectors."""

    def setUp(self):
        try:
            from src.content_creator_platform_modulator import ContentCreatorPlatformRegistry
            self.registry = ContentCreatorPlatformRegistry()
        except ImportError as exc:
            self.skipTest(f"Module not available: {exc}")

    def test_kick_exists(self):
        c = self.registry.get_connector("kick")
        self.assertIsNotNone(c)
        self.assertIn("live_stream_management", c.capabilities)

    def test_rumble_exists(self):
        c = self.registry.get_connector("rumble")
        self.assertIsNotNone(c)
        self.assertIn("video_upload", c.capabilities)


class TestCrossPlatformSyndication(unittest.TestCase):
    """Test cross-platform content syndication."""

    def setUp(self):
        try:
            from src.content_creator_platform_modulator import ContentCreatorPlatformRegistry
            self.registry = ContentCreatorPlatformRegistry()
        except ImportError as exc:
            self.skipTest(f"Module not available: {exc}")

    def test_syndicate_to_multiple_platforms(self):
        content = {"title": "New Video", "description": "Test content"}
        result = self.registry.syndicate_content(content, ["youtube", "tiktok", "rumble"])
        self.assertTrue(result["success"])
        self.assertIn("youtube", result["platforms"])
        self.assertIn("tiktok", result["platforms"])
        self.assertIn("rumble", result["platforms"])

    def test_syndicate_handles_unknown_platform(self):
        result = self.registry.syndicate_content({}, ["youtube", "nonexistent"])
        self.assertFalse(result["success"])
        self.assertFalse(result["platforms"]["nonexistent"]["success"])

    def test_syndicate_returns_content_id(self):
        result = self.registry.syndicate_content({}, ["youtube"])
        self.assertIn("content_id", result)


class TestAnalyticsAggregation(unittest.TestCase):
    """Test cross-platform analytics aggregation."""

    def setUp(self):
        try:
            from src.content_creator_platform_modulator import ContentCreatorPlatformRegistry
            self.registry = ContentCreatorPlatformRegistry()
        except ImportError as exc:
            self.skipTest(f"Module not available: {exc}")

    def test_aggregate_all_platforms(self):
        result = self.registry.aggregate_analytics()
        self.assertGreaterEqual(result["platforms_with_analytics"], 7)

    def test_aggregate_specific_platforms(self):
        result = self.registry.aggregate_analytics(["youtube", "twitch"])
        self.assertEqual(result["total_platforms"], 2)
        self.assertIn("youtube", result["analytics"])

    def test_health_check_all(self):
        health = self.registry.health_check_all()
        self.assertGreaterEqual(health["total"], 7)
        self.assertGreaterEqual(health["active"], 7)


class TestConnectorExecution(unittest.TestCase):
    """Test connector execution edge cases."""

    def setUp(self):
        try:
            from src.content_creator_platform_modulator import ContentCreatorPlatformRegistry
            self.registry = ContentCreatorPlatformRegistry()
        except ImportError as exc:
            self.skipTest(f"Module not available: {exc}")

    def test_execute_unknown_connector(self):
        result = self.registry.execute("nonexistent", "some_action")
        self.assertFalse(result["success"])

    def test_execute_unsupported_action(self):
        result = self.registry.execute("youtube", "nonexistent_action")
        self.assertFalse(result["success"])
        self.assertIn("not supported", result["error"])

    def test_connector_to_dict(self):
        c = self.registry.get_connector("youtube")
        d = c.to_dict()
        self.assertEqual(d["connector_id"], "youtube")
        self.assertEqual(d["platform_type"], "video")
        self.assertIn("video_upload", d["capabilities"])

    def test_list_by_type(self):
        from src.content_creator_platform_modulator import PlatformType
        streaming = self.registry.list_by_type(PlatformType.STREAMING)
        platform_names = [c["platform"] for c in streaming]
        self.assertIn("twitch", platform_names)
        self.assertIn("kick", platform_names)


class TestModuleCatalogWiring(unittest.TestCase):
    """Test that the module is properly wired in MODULE_CATALOG."""

    def setUp(self):
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "murphy_runtime",
                os.path.join(os.path.dirname(__file__), '..', 'murphy_system_1.0_runtime.py')
            )
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            self.MurphySystem = mod.MurphySystem
            self.ms = self.MurphySystem()
        except Exception as exc:
            self.skipTest(f"Cannot load MurphySystem: {exc}")

    def test_module_catalog_has_content_creator_platform(self):
        names = {m["name"] for m in self.ms.MODULE_CATALOG}
        self.assertIn("content_creator_platform_modulator", names)

    def test_content_creator_platform_initialized(self):
        self.assertIsNotNone(getattr(self.ms, 'content_creator_platform_modulator', None))


if __name__ == '__main__':
    unittest.main()
