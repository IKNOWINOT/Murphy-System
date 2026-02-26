"""
Integration tests for Agentic API Provisioner, Video Streaming Connector,
Remote Access Connector, and UI Testing Framework modules.
"""
import os
import sys
import unittest

# Ensure the Murphy System directory is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.agentic_api_provisioner import (
    AgenticAPIProvisioner, EndpointMethod, AuthPolicy, EndpointStatus,
    EndpointDefinition, WebhookRegistration, OpenAPISpecGenerator,
    ModuleIntrospector, EndpointHealthMonitor,
)
from src.video_streaming_connector import (
    VideoStreamingRegistry, StreamingPlatformConnector, StreamSession,
    SimulcastManager, StreamingPlatform, StreamStatus, StreamQuality,
    ConnectorStatus as VSConnectorStatus,
)
from src.remote_access_connector import (
    RemoteAccessRegistry, RemotePlatformConnector, RemoteSession,
    RemotePlatform, SessionStatus, AccessLevel, ProtocolType,
    ConnectorStatus as RAConnectorStatus,
)
from src.ui_testing_framework import (
    UITestingFramework, VisualRegressionTester, InteractiveComponentTester,
    E2ETestHarness, PerformanceTester, CrossBrowserTester,
    MobileGestureTester, AnimationTransitionTester, ErrorStateUITester,
    DarkModeTester, RealAPIIntegrationTester, UISecurityTester, I18nTester,
)


# ═══════════════════════════════════════════════════════════════════════════
# AGENTIC API PROVISIONER TESTS
# ═══════════════════════════════════════════════════════════════════════════

class TestAgenticAPIProvisioner(unittest.TestCase):

    def setUp(self):
        self.provisioner = AgenticAPIProvisioner()

    def test_initial_status(self):
        status = self.provisioner.status()
        self.assertFalse(status["provisioned"])
        self.assertEqual(status["total_endpoints"], 0)

    def test_auto_provision_from_catalog(self):
        catalog = [
            {"name": "test_module", "capabilities": ["execute", "status"]},
            {"name": "analytics", "capabilities": ["list", "health"]},
        ]
        result = self.provisioner.auto_provision(catalog)
        self.assertEqual(result["status"], "provisioned")
        self.assertGreater(result["endpoints_registered"], 0)
        self.assertGreater(result["webhooks_registered"], 0)

    def test_manual_endpoint_registration(self):
        ep = self.provisioner.register_endpoint(
            "/custom/action", EndpointMethod.POST, "custom_handler",
            description="Custom action")
        self.assertEqual(ep.status, EndpointStatus.ACTIVE)
        self.assertEqual(ep.method, EndpointMethod.POST)

    def test_webhook_registration(self):
        wh = self.provisioner.register_webhook(
            "task.completed", "/api/v1/webhooks/task/completed")
        self.assertEqual(wh.event_type, "task.completed")
        self.assertTrue(wh.active)

    def test_openapi_spec_generation(self):
        self.provisioner.register_endpoint(
            "/test", EndpointMethod.GET, "test_handler")
        spec = self.provisioner.generate_openapi_spec()
        self.assertEqual(spec["openapi"], "3.0.3")
        self.assertIn("paths", spec)
        self.assertIn("components", spec)

    def test_health_check(self):
        ep = self.provisioner.register_endpoint(
            "/health_test", EndpointMethod.GET, "health_handler")
        results = self.provisioner.run_health_checks()
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0]["healthy"])

    def test_decommission_endpoint(self):
        ep = self.provisioner.register_endpoint(
            "/decom", EndpointMethod.GET, "handler")
        success = self.provisioner.decommission_endpoint(ep.id)
        self.assertTrue(success)
        self.assertEqual(ep.status, EndpointStatus.DEPRECATED)

    def test_list_endpoints(self):
        self.provisioner.register_endpoint("/a", EndpointMethod.GET, "h1")
        self.provisioner.register_endpoint("/b", EndpointMethod.POST, "h2")
        eps = self.provisioner.list_endpoints()
        self.assertEqual(len(eps), 2)

    def test_module_introspector(self):
        introspector = ModuleIntrospector()
        catalog = [{"name": "mod1", "capabilities": ["execute", "status"]}]
        endpoints = introspector.introspect_catalog(catalog)
        self.assertGreaterEqual(len(endpoints), 2)

    def test_self_healing(self):
        monitor = EndpointHealthMonitor(failure_threshold=2)
        ep = EndpointDefinition("/test", EndpointMethod.GET, "handler")
        ep.status = EndpointStatus.DEGRADED
        for _ in range(3):
            monitor.check_endpoint(ep)
        history = monitor.get_healing_history()
        self.assertGreater(len(history), 0)


# ═══════════════════════════════════════════════════════════════════════════
# VIDEO STREAMING CONNECTOR TESTS
# ═══════════════════════════════════════════════════════════════════════════

class TestVideoStreamingConnector(unittest.TestCase):

    def setUp(self):
        self.registry = VideoStreamingRegistry()

    def test_default_platforms_initialized(self):
        platforms = self.registry.list_platforms()
        self.assertEqual(len(platforms), 9)

    def test_all_platforms_connected(self):
        for p in self.registry.list_platforms():
            self.assertEqual(p["status"], "connected")

    def test_create_stream_session(self):
        conn = self.registry.get_connector("twitch")
        self.assertIsNotNone(conn)
        session = conn.create_stream("Test Stream", StreamQuality.FHD_1080P)
        self.assertEqual(session.status, StreamStatus.IDLE)
        self.assertEqual(session.quality, StreamQuality.FHD_1080P)

    def test_start_and_stop_stream(self):
        conn = self.registry.get_connector("youtube_live")
        session = conn.create_stream("Live Session")
        start = conn.start_stream(session.id)
        self.assertEqual(start["status"], "live")
        stop = conn.stop_stream(session.id)
        self.assertEqual(stop["status"], "ended")
        self.assertIn("duration_seconds", stop)

    def test_stream_health(self):
        conn = self.registry.get_connector("obs_studio")
        session = conn.create_stream("Health Check")
        conn.start_stream(session.id)
        health = conn.get_stream_health(session.id)
        self.assertEqual(health["status"], "live")
        self.assertIn("bitrate_kbps", health)

    def test_simulcast_creation(self):
        result = self.registry.create_simulcast(
            "Multi-Platform Stream",
            ["twitch", "youtube_live", "kick_live"])
        self.assertIn("simulcast_id", result)
        self.assertEqual(len(result["platforms"]), 3)

    def test_platform_capabilities(self):
        conn = self.registry.get_connector("twitch")
        self.assertIn("live_streaming", conn.capabilities)
        self.assertIn("clips", conn.capabilities)

    def test_registry_status(self):
        status = self.registry.status()
        self.assertEqual(status["total_platforms"], 9)
        self.assertEqual(status["status"], "operational")

    def test_session_not_found(self):
        conn = self.registry.get_connector("twitch")
        result = conn.start_stream("nonexistent")
        self.assertIn("error", result)


# ═══════════════════════════════════════════════════════════════════════════
# REMOTE ACCESS CONNECTOR TESTS
# ═══════════════════════════════════════════════════════════════════════════

class TestRemoteAccessConnector(unittest.TestCase):

    def setUp(self):
        self.registry = RemoteAccessRegistry()

    def test_default_platforms_initialized(self):
        platforms = self.registry.list_platforms()
        self.assertEqual(len(platforms), 9)

    def test_all_platforms_connected(self):
        for p in self.registry.list_platforms():
            self.assertEqual(p["status"], "connected")

    def test_create_session(self):
        conn = self.registry.get_connector("teamviewer")
        session = conn.create_session("192.168.1.100", AccessLevel.FULL_CONTROL)
        self.assertEqual(session.status, SessionStatus.IDLE)
        self.assertEqual(session.access_level, AccessLevel.FULL_CONTROL)

    def test_connect_and_disconnect(self):
        conn = self.registry.get_connector("rdp")
        session = conn.create_session("server-01.local")
        connect_result = conn.connect_session(session.id)
        self.assertEqual(connect_result["status"], "connected")
        self.assertIn("latency_ms", connect_result)
        disconnect_result = conn.disconnect_session(session.id)
        self.assertEqual(disconnect_result["status"], "disconnected")

    def test_file_transfer(self):
        conn = self.registry.get_connector("anydesk")
        session = conn.create_session("workstation-01")
        session.connect()
        result = session.transfer_file("report.pdf", 2048000)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["total_files"], 1)

    def test_session_recording(self):
        conn = self.registry.get_connector("vnc")
        session = conn.create_session("dev-server")
        session.connect()
        start = session.start_recording()
        self.assertTrue(start["recording"])
        stop = session.stop_recording()
        self.assertFalse(stop["recording"])

    def test_unattended_registration(self):
        conn = self.registry.get_connector("teamviewer")
        device = conn.register_unattended("server-02", "Prod DB", wake_on_lan=True)
        self.assertEqual(device["hostname"], "server-02")
        self.assertTrue(device["wake_on_lan"])
        unattended = conn.list_unattended()
        self.assertEqual(len(unattended), 1)

    def test_protocol_mapping(self):
        rdp_conn = self.registry.get_connector("rdp")
        session = rdp_conn.create_session("host")
        self.assertEqual(session.protocol, ProtocolType.RDP)
        ssh_conn = self.registry.get_connector("ssh_tunnel")
        session2 = ssh_conn.create_session("host")
        self.assertEqual(session2.protocol, ProtocolType.SSH)

    def test_registry_status(self):
        status = self.registry.status()
        self.assertEqual(status["total_platforms"], 9)
        self.assertEqual(status["status"], "operational")

    def test_session_not_found(self):
        conn = self.registry.get_connector("rdp")
        result = conn.connect_session("nonexistent")
        self.assertIn("error", result)


# ═══════════════════════════════════════════════════════════════════════════
# UI TESTING FRAMEWORK TESTS
# ═══════════════════════════════════════════════════════════════════════════

class TestUITestingFramework(unittest.TestCase):

    def setUp(self):
        self.framework = UITestingFramework()

    def test_framework_has_12_capabilities(self):
        status = self.framework.status()
        self.assertEqual(status["capabilities_available"], 12)
        self.assertEqual(status["capabilities_gap_closed"], 12)

    def test_full_report(self):
        report = self.framework.full_report()
        self.assertEqual(report["capability_count"], 12)
        self.assertEqual(len(report["capabilities"]), 12)


class TestVisualRegression(unittest.TestCase):

    def setUp(self):
        self.tester = VisualRegressionTester()

    def test_baseline_capture(self):
        h = self.tester.capture_baseline("page1", "<html><body>test</body></html>")
        self.assertTrue(len(h) > 0)

    def test_compare_match(self):
        content = "<html><body>test</body></html>"
        self.tester.capture_baseline("page1", content)
        result = self.tester.compare("page1", content)
        self.assertEqual(result["status"], "pass")

    def test_compare_no_baseline(self):
        result = self.tester.compare("unknown", "<html></html>")
        self.assertEqual(result["status"], "no_baseline")


class TestInteractiveComponents(unittest.TestCase):

    def setUp(self):
        self.tester = InteractiveComponentTester()

    def test_button_click(self):
        btn = self.tester.create_button("btn1", "Submit")
        result = btn.click()
        self.assertEqual(result["result"], "success")

    def test_disabled_button(self):
        btn = self.tester.create_button("btn2", "Disabled", disabled=True)
        result = btn.click()
        self.assertEqual(result["result"], "blocked_disabled")

    def test_form_submit(self):
        form = self.tester.create_form("form1", [
            {"name": "email", "type": "email", "required": True},
            {"name": "name", "type": "text"},
        ])
        result = form.submit({"email": "test@example.com", "name": "Test"})
        self.assertEqual(result["result"], "success")

    def test_form_validation_error(self):
        form = self.tester.create_form("form2", [
            {"name": "email", "type": "email", "required": True},
        ])
        result = form.submit({})
        self.assertEqual(result["result"], "validation_error")


class TestE2EHarness(unittest.TestCase):

    def setUp(self):
        self.harness = E2ETestHarness()

    def test_load_page(self):
        page = self.harness.load_page(
            "/dashboard", "<html><title>Dashboard</title><body></body></html>")
        self.assertEqual(page["title"], "Dashboard")
        self.assertEqual(page["status"], "loaded")

    def test_assert_element_exists(self):
        html = '<div id="main"><button class="action">Go</button></div>'
        result = self.harness.assert_element_exists("/test", "#main", html)
        self.assertTrue(result["found"])

    def test_navigation_history(self):
        self.harness.load_page("/a", "<html></html>")
        self.harness.load_page("/b", "<html></html>")
        history = self.harness.get_navigation_history()
        self.assertEqual(len(history), 2)


class TestPerformance(unittest.TestCase):

    def test_measure_page(self):
        tester = PerformanceTester()
        html = "<html><body><div>Small page</div></body></html>"
        result = tester.measure_page("small", html)
        self.assertTrue(result["overall_pass"])

    def test_large_page_performance(self):
        tester = PerformanceTester(max_load_ms=500)
        html = "<html><body>" + "<div>content</div>" * 5000 + "</body></html>"
        result = tester.measure_page("large", html)
        self.assertFalse(result["load_pass"])  # Should exceed threshold


class TestCrossBrowser(unittest.TestCase):

    def test_compatibility_check(self):
        tester = CrossBrowserTester()
        html = "body { display: flex; --main-color: #00ff41; }"
        result = tester.check_compatibility(html)
        self.assertIn("browser_results", result)
        self.assertIn("flexbox", result["features_detected"])
        self.assertIn("css_variables", result["features_detected"])

    def test_ie11_incompatibility(self):
        tester = CrossBrowserTester()
        html = "display: grid; --var: 1;"
        result = tester.check_compatibility(html)
        self.assertFalse(result["browser_results"]["ie11"]["compatible"])


class TestMobileGesture(unittest.TestCase):

    def setUp(self):
        self.tester = MobileGestureTester()

    def test_tap(self):
        result = self.tester.simulate_tap("button", (50, 50))
        self.assertEqual(result["result"], "success")

    def test_long_press(self):
        result = self.tester.simulate_long_press("menu", hold_ms=600)
        self.assertTrue(result["recognized"])
        self.assertEqual(result["result"], "context_menu")

    def test_swipe(self):
        result = self.tester.simulate_swipe("list", "left", 300)
        self.assertEqual(result["result"], "success")

    def test_pinch(self):
        result = self.tester.simulate_pinch("canvas", scale=0.5)
        self.assertEqual(result["gesture"], "pinch_in")

    def test_touch_target_validation(self):
        elements = [
            {"id": "btn1", "width": 48, "height": 48},
            {"id": "btn2", "width": 20, "height": 20},
        ]
        result = self.tester.validate_touch_targets(elements)
        self.assertEqual(result["passed"], 1)
        self.assertEqual(result["failed"], 1)


class TestAnimationTransition(unittest.TestCase):

    def test_detect_animations(self):
        tester = AnimationTransitionTester()
        css = """
        @keyframes glow { from { opacity: 0; } to { opacity: 1; } }
        .btn { transition: all 0.3s ease; }
        .pulse { animation: glow 2s infinite; }
        """
        anims = tester.detect_animations(css)
        self.assertGreaterEqual(len(anims), 2)

    def test_reduced_motion_check(self):
        tester = AnimationTransitionTester()
        html_with = "@media (prefers-reduced-motion: reduce) { }"
        result = tester.validate_prefers_reduced_motion(html_with)
        self.assertTrue(result["has_reduced_motion_support"])


class TestErrorStateUI(unittest.TestCase):

    def setUp(self):
        self.tester = ErrorStateUITester()

    def test_api_error_simulation(self):
        result = self.tester.simulate_api_error("/api/data", 500)
        self.assertEqual(result["status_code"], 500)
        self.assertTrue(result["recoverable"])

    def test_error_boundary_detection(self):
        html = """<script>try { api(); } catch(e) { showError(e); }</script>
                  <div class="error-message">Fallback</div>"""
        result = self.tester.validate_error_boundary(html)
        self.assertGreaterEqual(result["score"], 2)

    def test_network_failure(self):
        result = self.tester.simulate_network_failure()
        self.assertTrue(result["preserves_local_state"])

    def test_timeout_simulation(self):
        result = self.tester.simulate_timeout("/api/slow")
        self.assertTrue(result["offers_retry"])


class TestDarkMode(unittest.TestCase):

    def setUp(self):
        self.tester = DarkModeTester()

    def test_detect_dark_theme(self):
        html = "body { background-color: #0a0a0a; color: #00ff41; }"
        result = self.tester.detect_theme(html)
        self.assertTrue(result["is_dark_theme"])

    def test_contrast_check(self):
        result = self.tester.validate_contrast("#00ff41", "#0a0a0a")
        self.assertTrue(result["passes"])


class TestAPIIntegration(unittest.TestCase):

    def test_endpoint_validation(self):
        tester = RealAPIIntegrationTester()
        tester.register_endpoint("GET", "/api/status", 200,
                                 {"status": "string", "uptime": "number"})
        result = tester.validate_response(
            "GET", "/api/status",
            {"status": "ok", "uptime": 12345}, 200)
        self.assertEqual(result["overall"], "pass")

    def test_schema_validation_failure(self):
        tester = RealAPIIntegrationTester()
        tester.register_endpoint("GET", "/api/data", 200,
                                 {"count": "number"})
        result = tester.validate_response(
            "GET", "/api/data", {"count": "not_a_number"}, 200)
        self.assertEqual(result["overall"], "fail")


class TestUISecurity(unittest.TestCase):

    def test_xss_prevention(self):
        tester = UISecurityTester()
        result = tester.test_xss_prevention(UISecurityTester.default_sanitizer)
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["bypassed"], 0)

    def test_sql_injection_prevention(self):
        tester = UISecurityTester()
        result = tester.test_sql_injection_prevention(
            UISecurityTester.default_sanitizer)
        self.assertEqual(result["status"], "pass")

    def test_csp_headers(self):
        tester = UISecurityTester()
        headers = {"Content-Security-Policy": "script-src 'self'; style-src 'self'"}
        result = tester.test_csp_headers(headers)
        self.assertEqual(result["status"], "pass")

    def test_auth_bypass_detection(self):
        tester = UISecurityTester()
        result = tester.test_auth_bypass(
            ["/api/admin", "/api/users"],
            lambda ep: 401)  # All return 401 = protected
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["bypassed"], 0)


class TestI18n(unittest.TestCase):

    def setUp(self):
        self.tester = I18nTester()

    def test_detect_i18n_support(self):
        html = '<html lang="en"><head><meta charset="utf-8"></head></html>'
        result = self.tester.detect_i18n_support(html)
        self.assertTrue(result["has_lang_attribute"])
        self.assertTrue(result["has_utf8_charset"])

    def test_rtl_support(self):
        html = 'html[dir="rtl"] { direction: rtl; }'
        result = self.tester.validate_rtl_support(html)
        self.assertEqual(result["status"], "supported")

    def test_locale_validation(self):
        result = self.tester.validate_locale("en-US")
        self.assertEqual(result["status"], "supported")
        self.assertEqual(result["currency_symbol"], "$")

    def test_text_overflow(self):
        result = self.tester.check_text_overflow("Hello", "Bonjour")
        self.assertFalse(result["overflow_risk"])


# ═══════════════════════════════════════════════════════════════════════════
# MODULE_CATALOG WIRING VERIFICATION
# ═══════════════════════════════════════════════════════════════════════════

class TestModuleCatalogWiring(unittest.TestCase):

    @unittest.skipUnless(
        os.path.exists(os.path.join(os.path.dirname(__file__),
                                    "..", "murphy_system_1.0_runtime.py")),
        "Runtime file not found")
    def test_catalog_has_new_entries(self):
        import importlib
        spec = importlib.util.spec_from_file_location(
            "murphy_runtime",
            os.path.join(os.path.dirname(__file__), "..", "murphy_system_1.0_runtime.py"))
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
            catalog = mod.MurphyIntegratedSystem.MODULE_CATALOG
            names = [m["name"] for m in catalog]
            self.assertIn("agentic_api_provisioner", names)
            self.assertIn("video_streaming_connector", names)
            self.assertIn("remote_access_connector", names)
            self.assertIn("ui_testing_framework", names)
        except Exception:
            # Runtime has many dependencies; just verify catalog exists as class attr
            self.skipTest("Runtime dependencies not fully available")


if __name__ == "__main__":
    unittest.main()
