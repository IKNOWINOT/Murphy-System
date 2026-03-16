"""
Tests for UI Test Completeness Framework

Covers all five subsystems:
- ComponentContractValidator
- DataShapeValidator
- AccessibilityChecker
- ResponsiveLayoutTester
- UserInteractionSimulator
- UITestSuite facade
"""

import threading
import unittest

from src.ui_test_completeness import (
    AccessibilityChecker,
    ComponentContractValidator,
    DataShapeValidator,
    ResponsiveLayoutTester,
    UITestSuite,
    UserInteractionSimulator,
    VIEWPORT_PRESETS,
    _contrast_ratio,
    _relative_luminance,
)


# ============================================================================
# ComponentContractValidator Tests
# ============================================================================

class TestComponentContractValidator(unittest.TestCase):

    def setUp(self):
        self.v = ComponentContractValidator()
        self.v.register_component(
            "Button",
            required_props=["label"],
            optional_props=["disabled", "variant"],
            state_fields=["pressed"],
            events=["onClick", "onFocus"],
            render_output_keys=["element", "class_name"],
        )

    def test_register_component(self):
        result = self.v.register_component("Card", required_props=["title"])
        self.assertTrue(result["registered"])
        self.assertEqual(result["component"], "Card")

    def test_validate_props_valid(self):
        r = self.v.validate_props("Button", {"label": "OK", "disabled": True})
        self.assertTrue(r["valid"])
        self.assertEqual(r["errors"], [])

    def test_validate_props_missing_required(self):
        r = self.v.validate_props("Button", {"disabled": True})
        self.assertFalse(r["valid"])
        self.assertTrue(any("label" in e for e in r["errors"]))

    def test_validate_props_unknown_prop(self):
        r = self.v.validate_props("Button", {"label": "X", "color": "red"})
        self.assertFalse(r["valid"])
        self.assertTrue(any("color" in e for e in r["errors"]))

    def test_validate_props_unregistered_component(self):
        r = self.v.validate_props("Missing", {})
        self.assertFalse(r["valid"])

    def test_validate_state_valid(self):
        r = self.v.validate_state("Button", {"pressed": False})
        self.assertTrue(r["valid"])

    def test_validate_state_missing_field(self):
        r = self.v.validate_state("Button", {})
        self.assertFalse(r["valid"])

    def test_validate_state_unexpected_field(self):
        r = self.v.validate_state("Button", {"pressed": True, "hovered": True})
        self.assertFalse(r["valid"])

    def test_validate_events_valid(self):
        r = self.v.validate_events("Button", ["onClick"])
        self.assertTrue(r["valid"])

    def test_validate_events_undeclared(self):
        r = self.v.validate_events("Button", ["onHover"])
        self.assertFalse(r["valid"])

    def test_validate_render_output_valid(self):
        r = self.v.validate_render_output("Button", {"element": "<btn>", "class_name": "btn"})
        self.assertTrue(r["valid"])

    def test_validate_render_output_missing_key(self):
        r = self.v.validate_render_output("Button", {"element": "<btn>"})
        self.assertFalse(r["valid"])

    def test_get_contract(self):
        r = self.v.get_contract("Button")
        self.assertTrue(r["found"])
        self.assertEqual(r["contract"]["name"], "Button")

    def test_get_contract_missing(self):
        r = self.v.get_contract("NonExistent")
        self.assertFalse(r["found"])

    def test_list_components(self):
        r = self.v.list_components()
        self.assertIn("Button", r["components"])
        self.assertGreaterEqual(r["count"], 1)


# ============================================================================
# DataShapeValidator Tests
# ============================================================================

class TestDataShapeValidator(unittest.TestCase):

    def setUp(self):
        self.v = DataShapeValidator()

    def test_validate_status_endpoint_valid(self):
        data = {"status": "ok", "uptime": 123.5, "version": "1.0"}
        r = self.v.validate("status_endpoint", data)
        self.assertTrue(r["valid"])

    def test_validate_status_endpoint_missing_field(self):
        data = {"status": "ok", "version": "1.0"}
        r = self.v.validate("status_endpoint", data)
        self.assertFalse(r["valid"])

    def test_validate_status_endpoint_wrong_type(self):
        data = {"status": 123, "uptime": 10, "version": "1.0"}
        r = self.v.validate("status_endpoint", data)
        self.assertFalse(r["valid"])

    def test_validate_execution_summary(self):
        data = {"task_id": "t1", "status": "done", "started_at": "2024-01-01", "duration": 1.5}
        r = self.v.validate("execution_summary", data)
        self.assertTrue(r["valid"])

    def test_validate_module_catalog(self):
        data = {"modules": ["a", "b"], "total_count": 2}
        r = self.v.validate("module_catalog", data)
        self.assertTrue(r["valid"])

    def test_validate_unknown_schema(self):
        r = self.v.validate("nope", {})
        self.assertFalse(r["valid"])

    def test_register_and_validate_custom_schema(self):
        self.v.register_schema("custom", required_fields=["x"], field_types={"x": int})
        r = self.v.validate("custom", {"x": 42})
        self.assertTrue(r["valid"])

    def test_validate_list_items(self):
        items = [
            {"status": "ok", "uptime": 1, "version": "1"},
            {"status": "ok"},
        ]
        r = self.v.validate_list_items("status_endpoint", items)
        self.assertFalse(r["all_valid"])
        self.assertEqual(r["total"], 2)

    def test_list_schemas(self):
        r = self.v.list_schemas()
        self.assertIn("status_endpoint", r["builtin"])


# ============================================================================
# AccessibilityChecker Tests
# ============================================================================

class TestAccessibilityChecker(unittest.TestCase):

    def setUp(self):
        self.c = AccessibilityChecker()

    def test_contrast_black_white_passes(self):
        r = self.c.check_color_contrast((0, 0, 0), (255, 255, 255))
        self.assertTrue(r["passed"])
        self.assertGreater(r["ratio"], 4.5)

    def test_contrast_similar_colors_fails(self):
        r = self.c.check_color_contrast((200, 200, 200), (210, 210, 210))
        self.assertFalse(r["passed"])

    def test_contrast_large_text_lower_threshold(self):
        r = self.c.check_color_contrast((100, 100, 100), (200, 200, 200), large_text=True)
        self.assertEqual(r["threshold"], 3.0)

    def test_aria_labels_valid(self):
        elems = [{"tag": "button", "aria-label": "Submit"}]
        r = self.c.check_aria_labels(elems)
        self.assertTrue(r["passed"])

    def test_aria_labels_missing(self):
        elems = [{"tag": "button"}]
        r = self.c.check_aria_labels(elems)
        self.assertFalse(r["passed"])

    def test_aria_bad_role(self):
        elems = [{"tag": "div", "role": "banana"}]
        r = self.c.check_aria_labels(elems)
        self.assertFalse(r["passed"])

    def test_keyboard_navigation_valid(self):
        r = self.c.check_keyboard_navigation(["search", "menu", "content"])
        self.assertTrue(r["passed"])

    def test_keyboard_navigation_empty(self):
        r = self.c.check_keyboard_navigation([])
        self.assertFalse(r["passed"])

    def test_keyboard_navigation_duplicates(self):
        r = self.c.check_keyboard_navigation(["a", "b", "a"])
        self.assertFalse(r["passed"])

    def test_screen_reader_valid(self):
        page = {"title": "Home", "h1": "Welcome", "landmarks": ["main"], "images": [{"src": "x.png", "alt": "logo"}]}
        r = self.c.check_screen_reader(page)
        self.assertTrue(r["passed"])

    def test_screen_reader_missing_title(self):
        r = self.c.check_screen_reader({"h1": "X", "landmarks": ["main"]})
        self.assertFalse(r["passed"])

    def test_screen_reader_missing_alt(self):
        page = {"title": "T", "h1": "H", "landmarks": ["m"], "images": [{"src": "x.png"}]}
        r = self.c.check_screen_reader(page)
        self.assertFalse(r["passed"])

    def test_get_report_aggregates(self):
        self.c.check_color_contrast((0, 0, 0), (255, 255, 255))
        self.c.check_keyboard_navigation(["a"])
        report = self.c.get_report()
        self.assertEqual(report["total_checks"], 2)
        self.assertEqual(report["passed"], 2)


# ============================================================================
# ResponsiveLayoutTester Tests
# ============================================================================

class TestResponsiveLayoutTester(unittest.TestCase):

    def setUp(self):
        self.t = ResponsiveLayoutTester()

    def test_classify_viewport_mobile(self):
        self.assertEqual(self.t.classify_viewport(320), "mobile")

    def test_classify_viewport_desktop(self):
        self.assertEqual(self.t.classify_viewport(1200), "desktop")

    def test_layout_mobile_sidebar_error(self):
        layout = {"sidebar_visible": True, "nav_type": "hamburger"}
        r = self.t.test_layout_rules("mobile", layout)
        self.assertFalse(r["valid"])

    def test_layout_desktop_valid(self):
        layout = {"sidebar_visible": True, "nav_type": "top", "columns": 3}
        r = self.t.test_layout_rules("desktop", layout)
        self.assertTrue(r["valid"])

    def test_layout_small_font_error(self):
        layout = {"font_size": 8, "nav_type": "hamburger"}
        r = self.t.test_layout_rules("mobile", layout)
        self.assertFalse(r["valid"])

    def test_layout_unknown_viewport(self):
        r = self.t.test_layout_rules("giant", {})
        self.assertFalse(r["valid"])

    def test_touch_target_too_small(self):
        layout = {"nav_type": "hamburger", "touch_target_size": 30}
        r = self.t.test_layout_rules("mobile", layout)
        self.assertFalse(r["valid"])

    def test_test_all_viewports(self):
        def layout_fn(name, w, h):
            if name == "mobile":
                return {"sidebar_visible": False, "nav_type": "hamburger", "columns": 1}
            return {"sidebar_visible": True, "nav_type": "top", "columns": 3}
        r = self.t.test_all_viewports(layout_fn)
        self.assertTrue(r["all_valid"])
        self.assertEqual(len(r["viewports"]), len(VIEWPORT_PRESETS))

    def test_get_report(self):
        self.t.test_layout_rules("desktop", {"sidebar_visible": True})
        report = self.t.get_report()
        self.assertGreaterEqual(report["total_tests"], 1)


# ============================================================================
# UserInteractionSimulator Tests
# ============================================================================

class TestUserInteractionSimulator(unittest.TestCase):

    def setUp(self):
        self.sim = UserInteractionSimulator()

    def test_login_success(self):
        r = self.sim.simulate_login("admin", "admin123")
        self.assertTrue(r["success"])
        self.assertTrue(r["state"]["authenticated"])

    def test_login_failure(self):
        r = self.sim.simulate_login("admin", "wrong")
        self.assertFalse(r["success"])
        self.assertFalse(r["state"]["authenticated"])

    def test_submit_task(self):
        r = self.sim.simulate_task_submission("build", {"target": "all"})
        self.assertTrue(r["success"])
        self.assertIn("task_id", r)

    def test_submit_task_unauthenticated(self):
        r = self.sim.simulate_task_submission("build", {}, authenticated=False)
        self.assertFalse(r["success"])

    def test_submit_task_empty_name(self):
        r = self.sim.simulate_task_submission("", {})
        self.assertFalse(r["success"])

    def test_settings_change_valid(self):
        r = self.sim.simulate_settings_change("theme", "dark", {"theme": "light"}, ["theme"])
        self.assertTrue(r["success"])
        self.assertEqual(r["settings"]["theme"], "dark")
        self.assertEqual(r["old_value"], "light")

    def test_settings_change_unknown_key(self):
        r = self.sim.simulate_settings_change("foo", "bar", {}, ["theme"])
        self.assertFalse(r["success"])

    def test_register_and_execute_flow(self):
        self.sim.register_flow(
            "onboarding",
            steps=["signup", "verify", "profile"],
            initial_state={"step": 0, "verified": False},
            transitions={
                "signup": {"step": 1},
                "verify": {"step": 2, "verified": True},
                "profile": {"step": 3},
            },
        )
        r = self.sim.execute_flow("onboarding")
        self.assertTrue(r["completed"])
        self.assertEqual(r["final_state"]["step"], 3)
        self.assertTrue(r["final_state"]["verified"])

    def test_execute_flow_with_failure(self):
        self.sim.register_flow(
            "checkout",
            steps=["cart", "payment", "confirm"],
            initial_state={"paid": False},
            transitions={"cart": {}, "payment": {"paid": True}, "confirm": {}},
        )
        r = self.sim.execute_flow("checkout", step_results={"cart": True, "payment": False})
        self.assertFalse(r["completed"])
        self.assertEqual(r["steps_executed"], 2)

    def test_execute_flow_not_registered(self):
        r = self.sim.execute_flow("nope")
        self.assertFalse(r["success"])

    def test_get_history(self):
        self.sim.simulate_login("user", "pass")
        h = self.sim.get_history()
        self.assertEqual(h["count"], 1)


# ============================================================================
# UITestSuite Facade Tests
# ============================================================================

class TestUITestSuite(unittest.TestCase):

    def test_facade_has_all_subsystems(self):
        suite = UITestSuite()
        self.assertIsInstance(suite.contracts, ComponentContractValidator)
        self.assertIsInstance(suite.shapes, DataShapeValidator)
        self.assertIsInstance(suite.accessibility, AccessibilityChecker)
        self.assertIsInstance(suite.responsive, ResponsiveLayoutTester)
        self.assertIsInstance(suite.interactions, UserInteractionSimulator)

    def test_full_report_structure(self):
        suite = UITestSuite()
        report = suite.full_report()
        self.assertIn("components", report)
        self.assertIn("schemas", report)
        self.assertIn("accessibility", report)
        self.assertIn("responsive", report)
        self.assertIn("interactions", report)


# ============================================================================
# Thread Safety Test
# ============================================================================

class TestThreadSafety(unittest.TestCase):

    def test_concurrent_contract_registration(self):
        v = ComponentContractValidator()
        errors = []

        def register(i):
            try:
                v.register_component(f"C{i}", required_props=["p"])
            except Exception as exc:
                errors.append(str(exc))

        threads = [threading.Thread(target=register, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0)
        self.assertEqual(v.list_components()["count"], 20)


# ============================================================================
# Utility Tests
# ============================================================================

class TestUtilities(unittest.TestCase):

    def test_relative_luminance_black(self):
        self.assertAlmostEqual(_relative_luminance(0, 0, 0), 0.0, places=4)

    def test_relative_luminance_white(self):
        self.assertAlmostEqual(_relative_luminance(255, 255, 255), 1.0, places=4)

    def test_contrast_ratio_symmetry(self):
        r1 = _contrast_ratio((0, 0, 0), (255, 255, 255))
        r2 = _contrast_ratio((255, 255, 255), (0, 0, 0))
        self.assertAlmostEqual(r1, r2, places=4)


if __name__ == "__main__":
    unittest.main()
