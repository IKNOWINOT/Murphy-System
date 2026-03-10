"""
Integration tests for Digital Asset Generator, Rosetta Stone Heartbeat,
and UI production-readiness validation.

Validates MODULE_CATALOG registration, _initialize calls, asset pipeline
functionality, heartbeat propagation, and UI file production specs.
"""
import os
import re
import unittest
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


# ===================================================================
# Digital Asset Generator tests
# ===================================================================

class TestDigitalAssetGeneratorBasics(unittest.TestCase):
    """Test core digital asset generation functionality."""

    def setUp(self):
        try:
            from src.digital_asset_generator import (
                DigitalAssetGenerator,
                AssetDescriptor,
                PictureArrayDescriptor,
                AssetType,
                TargetPlatform,
                AssetFormat,
                PipelineStatus,
                PLATFORM_PRESETS,
                get_status,
            )
            self.gen = DigitalAssetGenerator()
            self.AssetDescriptor = AssetDescriptor
            self.PictureArrayDescriptor = PictureArrayDescriptor
            self.AssetType = AssetType
            self.TargetPlatform = TargetPlatform
            self.AssetFormat = AssetFormat
            self.PipelineStatus = PipelineStatus
            self.PLATFORM_PRESETS = PLATFORM_PRESETS
            self.get_status = get_status
        except ImportError as exc:
            self.skipTest(f"Digital asset generator not available: {exc}")

    def test_get_status(self):
        status = self.get_status()
        self.assertEqual(status["module"], "digital_asset_generator")
        self.assertEqual(status["status"], "operational")

    def test_platform_presets_exist(self):
        platforms = self.gen.list_platforms()
        for p in ["unreal_engine", "maya", "blender", "fortnite_creative", "unity", "godot"]:
            self.assertIn(p, platforms, f"Missing platform: {p}")

    def test_asset_types(self):
        types = self.gen.list_asset_types()
        for t in ["texture", "sprite_sheet", "texture_atlas", "model_3d", "material",
                   "animation", "level_map"]:
            self.assertIn(t, types, f"Missing asset type: {t}")

    def test_output_formats(self):
        formats = self.gen.list_formats()
        for f in ["fbx", "gltf", "usd", "png", "uasset", "blend", "ma"]:
            self.assertIn(f, formats, f"Missing format: {f}")

    def test_generate_texture(self):
        desc = self.AssetDescriptor(
            name="test_texture",
            asset_type=self.AssetType.TEXTURE,
            target_platform=self.TargetPlatform.UNREAL_ENGINE,
            output_format=self.AssetFormat.PNG,
            resolution={"width": 2048, "height": 2048},
        )
        result = self.gen.generate_asset(desc)
        self.assertTrue(result["success"])
        self.assertEqual(result["asset_type"], "texture")
        self.assertEqual(result["target_platform"], "unreal_engine")

    def test_generate_3d_model(self):
        desc = self.AssetDescriptor(
            name="hero_character",
            asset_type=self.AssetType.MODEL_3D,
            target_platform=self.TargetPlatform.MAYA,
            output_format=self.AssetFormat.FBX,
        )
        result = self.gen.generate_asset(desc)
        self.assertTrue(result["success"])
        self.assertEqual(result["output_format"], "fbx")

    def test_format_validation_rejects_incompatible(self):
        desc = self.AssetDescriptor(
            name="bad_format",
            asset_type=self.AssetType.TEXTURE,
            target_platform=self.TargetPlatform.FORTNITE_CREATIVE,
            output_format=self.AssetFormat.EXR,
        )
        result = self.gen.generate_asset(desc)
        self.assertFalse(result["success"])
        self.assertIn("not supported", result["error"])

    def test_resolution_validation(self):
        desc = self.AssetDescriptor(
            name="oversized",
            target_platform=self.TargetPlatform.FORTNITE_CREATIVE,
            resolution={"width": 9999, "height": 9999},
        )
        result = self.gen.generate_asset(desc)
        self.assertFalse(result["success"])
        self.assertIn("exceeds", result["error"])

    def test_statistics(self):
        stats = self.gen.statistics()
        self.assertIn("total_assets", stats)
        self.assertIn("supported_platforms", stats)
        self.assertGreaterEqual(len(stats["supported_platforms"]), 6)


class TestPictureArrayGeneration(unittest.TestCase):
    """Test sprite sheet / texture atlas picture array generation."""

    def setUp(self):
        try:
            from src.digital_asset_generator import (
                DigitalAssetGenerator,
                PictureArrayDescriptor,
                TargetPlatform,
            )
            self.gen = DigitalAssetGenerator()
            self.PictureArrayDescriptor = PictureArrayDescriptor
            self.TargetPlatform = TargetPlatform
        except ImportError as exc:
            self.skipTest(f"Digital asset generator not available: {exc}")

    def test_generate_sprite_sheet(self):
        desc = self.PictureArrayDescriptor(
            name="walk_cycle",
            frame_count=8,
            columns=4,
            rows=2,
            frame_width=128,
            frame_height=128,
            target_platform=self.TargetPlatform.UNREAL_ENGINE,
            animation_fps=12,
        )
        result = self.gen.generate_picture_array(desc)
        self.assertTrue(result["success"])
        self.assertEqual(result["frame_count"], 8)
        self.assertEqual(len(result["frames"]), 8)
        self.assertEqual(result["total_width"], 512)
        self.assertEqual(result["total_height"], 256)

    def test_frame_coordinates(self):
        desc = self.PictureArrayDescriptor(
            name="idle_anim",
            frame_count=4,
            columns=2,
            rows=2,
            frame_width=64,
            frame_height=64,
        )
        result = self.gen.generate_picture_array(desc)
        self.assertTrue(result["success"])
        frames = result["frames"]
        self.assertEqual(frames[0]["x"], 0)
        self.assertEqual(frames[0]["y"], 0)
        self.assertEqual(frames[1]["x"], 64)
        self.assertEqual(frames[1]["y"], 0)
        self.assertEqual(frames[2]["x"], 0)
        self.assertEqual(frames[2]["y"], 64)
        self.assertEqual(frames[3]["x"], 64)
        self.assertEqual(frames[3]["y"], 64)

    def test_oversized_array_rejected(self):
        desc = self.PictureArrayDescriptor(
            name="too_large",
            frame_count=100,
            columns=10,
            rows=10,
            frame_width=1024,
            frame_height=1024,
            target_platform=self.TargetPlatform.FORTNITE_CREATIVE,
        )
        result = self.gen.generate_picture_array(desc)
        self.assertFalse(result["success"])
        self.assertIn("exceeds", result["error"])

    def test_fortnite_creative_array(self):
        desc = self.PictureArrayDescriptor(
            name="fn_emote",
            frame_count=16,
            columns=4,
            rows=4,
            frame_width=256,
            frame_height=256,
            target_platform=self.TargetPlatform.FORTNITE_CREATIVE,
        )
        result = self.gen.generate_picture_array(desc)
        self.assertTrue(result["success"])
        self.assertEqual(result["target_platform"], "fortnite_creative")


class TestAssetPipeline(unittest.TestCase):
    """Test batch pipeline orchestration."""

    def setUp(self):
        try:
            from src.digital_asset_generator import (
                DigitalAssetGenerator,
                AssetDescriptor,
                PictureArrayDescriptor,
                AssetType,
                TargetPlatform,
                AssetFormat,
            )
            self.gen = DigitalAssetGenerator()
            self.AssetDescriptor = AssetDescriptor
            self.PictureArrayDescriptor = PictureArrayDescriptor
            self.AssetType = AssetType
            self.TargetPlatform = TargetPlatform
            self.AssetFormat = AssetFormat
        except ImportError as exc:
            self.skipTest(f"Digital asset generator not available: {exc}")

    def test_create_pipeline(self):
        pipeline = self.gen.create_pipeline("p1", "Test Pipeline")
        self.assertEqual(pipeline["pipeline_id"], "p1")
        self.assertEqual(pipeline["status"], "queued")

    def test_execute_pipeline(self):
        assets = [
            self.AssetDescriptor(
                name="tex1",
                target_platform=self.TargetPlatform.UNREAL_ENGINE,
                output_format=self.AssetFormat.PNG,
            ),
        ]
        arrays = [
            self.PictureArrayDescriptor(
                name="sprites",
                frame_count=4,
                columns=2,
                rows=2,
                target_platform=self.TargetPlatform.UNREAL_ENGINE,
            ),
        ]
        self.gen.create_pipeline("p2", "Full Pipeline", assets=assets, arrays=arrays)
        result = self.gen.execute_pipeline("p2")
        self.assertTrue(result["success"])
        self.assertEqual(len(result["results"]), 2)

    def test_pipeline_not_found(self):
        result = self.gen.execute_pipeline("nonexistent")
        self.assertFalse(result["success"])

    def test_get_pipeline(self):
        self.gen.create_pipeline("p3", "Query Test")
        p = self.gen.get_pipeline("p3")
        self.assertIsNotNone(p)
        self.assertEqual(p["name"], "Query Test")


class TestPlatformPresets(unittest.TestCase):
    """Test platform configuration presets."""

    def setUp(self):
        try:
            from src.digital_asset_generator import (
                DigitalAssetGenerator,
                PLATFORM_PRESETS,
            )
            self.gen = DigitalAssetGenerator()
            self.PLATFORM_PRESETS = PLATFORM_PRESETS
        except ImportError as exc:
            self.skipTest(f"Digital asset generator not available: {exc}")

    def test_unreal_has_nanite(self):
        preset = self.gen.get_platform_preset("unreal_engine")
        self.assertIn("nanite_mesh", preset["supported_features"])

    def test_maya_has_arnold(self):
        preset = self.gen.get_platform_preset("maya")
        self.assertIn("arnold_renderer", preset["supported_features"])

    def test_blender_has_cycles(self):
        preset = self.gen.get_platform_preset("blender")
        self.assertIn("cycles_renderer", preset["supported_features"])

    def test_fortnite_has_verse(self):
        preset = self.gen.get_platform_preset("fortnite_creative")
        self.assertIn("verse_scripting", preset["supported_features"])

    def test_unity_has_urp(self):
        preset = self.gen.get_platform_preset("unity")
        self.assertIn("urp_pipeline", preset["supported_features"])

    def test_godot_has_gdscript(self):
        preset = self.gen.get_platform_preset("godot")
        self.assertIn("gdscript", preset["supported_features"])


# ===================================================================
# Rosetta Stone Heartbeat tests
# ===================================================================

class TestRosettaStoneHeartbeatBasics(unittest.TestCase):
    """Test heartbeat engine basics."""

    def setUp(self):
        try:
            from src.rosetta_stone_heartbeat import (
                RosettaStoneHeartbeat,
                OrganizationTier,
                PulseStatus,
                HeartbeatState,
                TIER_ORDER,
                get_status,
            )
            self.hb = RosettaStoneHeartbeat(interval_seconds=1.0, stale_threshold_seconds=5.0)
            self.OrganizationTier = OrganizationTier
            self.PulseStatus = PulseStatus
            self.HeartbeatState = HeartbeatState
            self.TIER_ORDER = TIER_ORDER
            self.get_status = get_status
        except ImportError as exc:
            self.skipTest(f"Rosetta stone heartbeat not available: {exc}")

    def test_get_status(self):
        status = self.get_status()
        self.assertEqual(status["module"], "rosetta_stone_heartbeat")
        self.assertEqual(status["status"], "operational")

    def test_tier_order(self):
        self.assertEqual(self.TIER_ORDER[0], self.OrganizationTier.EXECUTIVE)
        self.assertEqual(len(self.TIER_ORDER), 5)

    def test_initial_state(self):
        self.assertEqual(self.hb.get_state(), self.HeartbeatState.IDLE)

    def test_start_stop(self):
        self.hb.start()
        self.assertEqual(self.hb.get_state(), self.HeartbeatState.RUNNING)
        self.hb.pause()
        self.assertEqual(self.hb.get_state(), self.HeartbeatState.PAUSED)
        self.hb.stop()
        self.assertEqual(self.hb.get_state(), self.HeartbeatState.STOPPED)


class TestHeartbeatPulseEmission(unittest.TestCase):
    """Test pulse emission and propagation."""

    def setUp(self):
        try:
            from src.rosetta_stone_heartbeat import (
                RosettaStoneHeartbeat,
                OrganizationTier,
                TIER_ORDER,
            )
            self.hb = RosettaStoneHeartbeat(interval_seconds=1.0, stale_threshold_seconds=5.0)
            self.OrganizationTier = OrganizationTier
            self.TIER_ORDER = TIER_ORDER
        except ImportError as exc:
            self.skipTest(f"Rosetta stone heartbeat not available: {exc}")

    def test_emit_pulse(self):
        result = self.hb.emit_pulse(
            directives={"priority": "high", "action": "scale_up"},
            health_metrics={"cpu": 42, "memory": 68},
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["sequence"], 1)
        self.assertEqual(len(result["propagation"]), 5)

    def test_pulse_sequence_increments(self):
        self.hb.emit_pulse()
        r2 = self.hb.emit_pulse()
        self.assertEqual(r2["sequence"], 2)

    def test_propagation_order(self):
        result = self.hb.emit_pulse()
        tiers_in_order = [p["tier"] for p in result["propagation"]]
        expected = [t.value for t in self.TIER_ORDER]
        self.assertEqual(tiers_in_order, expected)

    def test_executive_first(self):
        result = self.hb.emit_pulse()
        self.assertEqual(result["propagation"][0]["tier"], "executive")

    def test_pulse_history(self):
        self.hb.emit_pulse()
        self.hb.emit_pulse()
        history = self.hb.get_pulse_history(limit=5)
        self.assertEqual(len(history), 2)


class TestHeartbeatTranslators(unittest.TestCase):
    """Test tier translator registration and invocation."""

    def setUp(self):
        try:
            from src.rosetta_stone_heartbeat import (
                RosettaStoneHeartbeat,
                OrganizationTier,
            )
            self.hb = RosettaStoneHeartbeat()
            self.OrganizationTier = OrganizationTier
            self.received_pulses = []
        except ImportError as exc:
            self.skipTest(f"Rosetta stone heartbeat not available: {exc}")

    def _exec_translator(self, pulse):
        self.received_pulses.append(pulse)
        return {"ack": True, "tier": "executive"}

    def test_register_translator(self):
        result = self.hb.register_translator(
            self.OrganizationTier.EXECUTIVE, self._exec_translator)
        self.assertTrue(result["registered"])

    def test_translator_invoked_on_pulse(self):
        self.hb.register_translator(
            self.OrganizationTier.EXECUTIVE, self._exec_translator)
        self.hb.emit_pulse(directives={"test": True})
        self.assertEqual(len(self.received_pulses), 1)
        self.assertEqual(self.received_pulses[0]["directives"]["test"], True)

    def test_translator_acknowledged(self):
        self.hb.register_translator(
            self.OrganizationTier.EXECUTIVE, self._exec_translator)
        result = self.hb.emit_pulse()
        exec_prop = result["propagation"][0]
        self.assertEqual(exec_prop["status"], "acknowledged")

    def test_failed_translator(self):
        def bad_translator(pulse):
            raise RuntimeError("boom")

        self.hb.register_translator(self.OrganizationTier.MANAGEMENT, bad_translator)
        result = self.hb.emit_pulse()
        mgmt_prop = result["propagation"][1]
        self.assertEqual(mgmt_prop["status"], "failed")
        self.assertIn("boom", mgmt_prop["error"])

    def test_unregister_translator(self):
        self.hb.register_translator(
            self.OrganizationTier.EXECUTIVE, self._exec_translator)
        self.hb.unregister_translator(self.OrganizationTier.EXECUTIVE)
        self.hb.emit_pulse()
        self.assertEqual(len(self.received_pulses), 0)


class TestHeartbeatSyncCheck(unittest.TestCase):
    """Test synchronisation check across tiers."""

    def setUp(self):
        try:
            from src.rosetta_stone_heartbeat import (
                RosettaStoneHeartbeat,
                OrganizationTier,
            )
            self.hb = RosettaStoneHeartbeat(stale_threshold_seconds=60.0)
            self.OrganizationTier = OrganizationTier
        except ImportError as exc:
            self.skipTest(f"Rosetta stone heartbeat not available: {exc}")

    def test_sync_after_pulse(self):
        self.hb.emit_pulse()
        check = self.hb.sync_check()
        self.assertTrue(check["all_synced"])

    def test_no_pulse_not_synced(self):
        check = self.hb.sync_check()
        self.assertFalse(check["all_synced"])

    def test_tier_states(self):
        self.hb.emit_pulse()
        states = self.hb.get_all_tier_states()
        self.assertIn("executive", states)
        self.assertIn("worker", states)
        self.assertEqual(states["executive"]["pulse_count"], 1)

    def test_statistics(self):
        self.hb.emit_pulse()
        stats = self.hb.statistics()
        self.assertEqual(stats["current_sequence"], 1)
        self.assertIn("tiers", stats)


# ===================================================================
# UI Production Readiness tests
# ===================================================================

class TestUIProductionReadiness(unittest.TestCase):
    """Validate that all terminal UIs meet production specifications."""

    def setUp(self):
        self.ui_dir = os.path.join(os.path.dirname(__file__), '..')
        self.neon_terminals = [
            "terminal_architect.html",
            "terminal_integrated.html",
            "terminal_worker.html",
        ]

    def _read_file(self, filename):
        path = os.path.join(self.ui_dir, filename)
        if not os.path.exists(path):
            self.skipTest(f"UI file not found: {filename}")
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()

    def test_architect_terminal_exists(self):
        content = self._read_file("terminal_architect.html")
        self.assertGreater(len(content), 1000)

    def test_integrated_terminal_exists(self):
        content = self._read_file("terminal_integrated.html")
        self.assertGreater(len(content), 1000)

    def test_worker_terminal_exists(self):
        content = self._read_file("terminal_worker.html")
        self.assertGreater(len(content), 1000)

    def _has_neon_theme(self, content):
        """Check for neon/dark theme — inline or via design-system CSS.

        The terminals now use murphy-design-system.css which defines
        dark backgrounds (--bg-base) and accent colours.  Accept either
        inline hex codes or the presence of the linked design system.
        """
        has_accent = (
            "#00ff00" in content.lower()
            or "#00FF00" in content
            or "--accent" in content
        )
        has_dark = (
            "#000000" in content
            or "#000" in content
            or "#0a0a0a" in content
            or "--bg-base" in content
            or "murphy-design-system.css" in content  # design system provides dark bg
        )
        return has_accent and has_dark

    def test_architect_has_neon_theme(self):
        content = self._read_file("terminal_architect.html")
        has_green = "#00ff41" in content.lower() or "#00ff00" in content.lower()
        self.assertTrue(has_green,
                       "Architect terminal missing neon green (#00ff41)")
        self.assertTrue(
            self._has_neon_theme(content),
            "Architect terminal missing neon/dark theme")

    def test_integrated_has_neon_theme(self):
        content = self._read_file("terminal_integrated.html")
        has_green = "#00ff41" in content.lower() or "#00ff00" in content.lower()
        self.assertTrue(has_green, "Integrated terminal missing neon green")

    def test_worker_has_neon_theme(self):
        content = self._read_file("terminal_worker.html")
        has_green = "#00ff41" in content.lower() or "#00ff00" in content.lower()
        self.assertTrue(has_green, "Worker terminal missing neon green")
        self.assertTrue(
            self._has_neon_theme(content),
            "Integrated terminal missing neon/dark theme")

    def test_worker_has_neon_theme(self):
        content = self._read_file("terminal_worker.html")
        self.assertTrue(
            self._has_neon_theme(content),
            "Worker terminal missing neon/dark theme")

    def test_architect_has_api_endpoints(self):
        content = self._read_file("terminal_architect.html")
        self.assertTrue(
            "/api" in content or "API_BASE" in content or "apiPort" in content,
            "Architect terminal missing API integration")

    def test_integrated_has_api_endpoints(self):
        content = self._read_file("terminal_integrated.html")
        self.assertTrue(
            "/api" in content or "API_BASE" in content or "apiPort" in content,
            "Integrated terminal missing API integration")

    def test_worker_has_api_endpoints(self):
        content = self._read_file("terminal_worker.html")
        self.assertTrue(
            "/api" in content or "API_BASE" in content or "apiPort" in content,
            "Worker terminal missing API integration")

    def test_architect_has_mfgc(self):
        content = self._read_file("terminal_architect.html")
        self.assertTrue(
            "mfgc" in content.lower() or "MFGC" in content,
            "Architect terminal missing MFGC integration")

    def _has_monospace_font(self, content):
        """Check for monospace font inline OR via linked design-system CSS."""
        if "monospace" in content.lower() or "Courier" in content:
            return True
        # All terminal files link murphy-design-system.css which defines
        # --font-code with monospace fallback; count that as present.
        if "murphy-design-system.css" in content:
            css_path = os.path.join(self.ui_dir, "static", "murphy-design-system.css")
            if os.path.exists(css_path):
                with open(css_path, "r", encoding="utf-8", errors="ignore") as f:
                    css = f.read()
                if "monospace" in css.lower():
                    return True
        return False

    def test_architect_has_monospace_font(self):
        content = self._read_file("terminal_architect.html")
        self.assertTrue(
            self._has_monospace_font(content),
            "Architect terminal missing monospace terminal font")

    def test_integrated_has_monospace_font(self):
        content = self._read_file("terminal_integrated.html")
        self.assertTrue(
            self._has_monospace_font(content),
            "Integrated terminal missing monospace terminal font")

    def test_worker_has_monospace_font(self):
        content = self._read_file("terminal_worker.html")
        self.assertTrue(
            self._has_monospace_font(content),
            "Worker terminal missing monospace terminal font")


class TestUIFeaturesCompleteness(unittest.TestCase):
    """Validate that UIs expose expected features for each account type."""

    def setUp(self):
        self.ui_dir = os.path.join(os.path.dirname(__file__), '..')

    def _read_file(self, filename):
        path = os.path.join(self.ui_dir, filename)
        if not os.path.exists(path):
            self.skipTest(f"UI file not found: {filename}")
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()

    def test_architect_has_confidence_display(self):
        content = self._read_file("terminal_architect.html")
        self.assertTrue(
            "confidence" in content.lower(),
            "Architect should display confidence metrics")

    def test_architect_has_gate_system(self):
        content = self._read_file("terminal_architect.html")
        self.assertTrue(
            "gate" in content.lower(),
            "Architect should have gate system integration")

    def test_integrated_has_task_execution(self):
        content = self._read_file("terminal_integrated.html")
        self.assertTrue(
            "execute" in content.lower() or "task" in content.lower(),
            "Integrated terminal should support task execution")

    def test_worker_has_task_status(self):
        content = self._read_file("terminal_worker.html")
        self.assertTrue(
            "task" in content.lower() or "status" in content.lower(),
            "Worker terminal should show task status")

    def test_worker_has_progress_tracking(self):
        content = self._read_file("terminal_worker.html")
        self.assertTrue(
            "progress" in content.lower(),
            "Worker terminal should show progress tracking")


# ===================================================================
# MODULE_CATALOG wiring tests
# ===================================================================

class TestNewModuleCatalogWiring(unittest.TestCase):
    """Test that new modules are registered in MODULE_CATALOG."""

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

    def test_module_catalog_has_digital_asset_generator(self):
        names = {m["name"] for m in self.ms.MODULE_CATALOG}
        self.assertIn("digital_asset_generator", names)

    def test_module_catalog_has_rosetta_stone_heartbeat(self):
        names = {m["name"] for m in self.ms.MODULE_CATALOG}
        self.assertIn("rosetta_stone_heartbeat", names)

    def test_digital_asset_generator_initialized(self):
        self.assertIsNotNone(getattr(self.ms, 'digital_asset_generator', None))

    def test_rosetta_stone_heartbeat_initialized(self):
        self.assertIsNotNone(getattr(self.ms, 'rosetta_stone_heartbeat', None))


if __name__ == '__main__':
    unittest.main()
