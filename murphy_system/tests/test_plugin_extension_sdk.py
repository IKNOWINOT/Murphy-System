"""Tests for plugin_extension_sdk.py"""

import os
import unittest

from plugin_extension_sdk import PluginExtensionSDK, PluginState


def _make_manifest(name="test-plugin", version="1.0.0", **overrides):
    base = {
        "name": name,
        "version": version,
        "author": "Test Author",
        "description": "A test plugin",
        "entry_point": "test_plugin:main",
        "capabilities": ["read_data", "execute_tasks"],
    }
    base.update(overrides)
    return base


class TestPluginExtensionSDK(unittest.TestCase):

    def setUp(self):
        self.sdk = PluginExtensionSDK()

    # --- Manifest validation ---
    def test_validate_valid_manifest(self):
        result = self.sdk.validate_manifest(_make_manifest())
        self.assertTrue(result["valid"])
        self.assertEqual(result["errors"], [])

    def test_validate_missing_required_field(self):
        m = _make_manifest()
        del m["name"]
        result = self.sdk.validate_manifest(m)
        self.assertFalse(result["valid"])
        self.assertIn("Missing required field: name", result["errors"])

    def test_validate_invalid_name(self):
        result = self.sdk.validate_manifest(_make_manifest(name="INVALID NAME!"))
        self.assertFalse(result["valid"])

    def test_validate_invalid_version(self):
        result = self.sdk.validate_manifest(_make_manifest(version="bad"))
        self.assertFalse(result["valid"])

    def test_validate_unknown_capability_warning(self):
        result = self.sdk.validate_manifest(_make_manifest(capabilities=["read_data", "fly_to_moon"]))
        self.assertTrue(result["valid"])
        self.assertTrue(any("fly_to_moon" in w for w in result["warnings"]))

    # --- Registration ---
    def test_register_plugin(self):
        result = self.sdk.register_plugin(_make_manifest())
        self.assertTrue(result["registered"])
        self.assertEqual(result["plugin"], "test-plugin")

    def test_register_invalid_plugin(self):
        m = _make_manifest()
        del m["version"]
        result = self.sdk.register_plugin(m)
        self.assertFalse(result["registered"])

    def test_register_duplicate_fails(self):
        self.sdk.register_plugin(_make_manifest())
        result = self.sdk.register_plugin(_make_manifest())
        self.assertFalse(result["registered"])

    # --- Install ---
    def test_install_plugin(self):
        self.sdk.register_plugin(_make_manifest())
        handler = lambda: "hello"
        result = self.sdk.install_plugin("test-plugin", handler=handler)
        self.assertTrue(result["installed"])
        self.assertIn("read_data", result["capabilities_granted"])

    def test_install_not_found(self):
        result = self.sdk.install_plugin("nonexistent")
        self.assertFalse(result["installed"])

    # --- Activate ---
    def test_activate_plugin(self):
        self.sdk.register_plugin(_make_manifest())
        self.sdk.install_plugin("test-plugin", handler=lambda: "ok")
        result = self.sdk.activate_plugin("test-plugin")
        self.assertTrue(result["activated"])

    def test_activate_not_installed_fails(self):
        self.sdk.register_plugin(_make_manifest())
        result = self.sdk.activate_plugin("test-plugin")
        self.assertFalse(result["activated"])

    # --- Execute ---
    def test_execute_plugin(self):
        self.sdk.register_plugin(_make_manifest())
        self.sdk.install_plugin("test-plugin", handler=lambda: {"result": 42})
        self.sdk.activate_plugin("test-plugin")
        result = self.sdk.execute_plugin("test-plugin")
        self.assertTrue(result["success"])
        self.assertEqual(result["result"], {"result": 42})

    def test_execute_inactive_plugin(self):
        self.sdk.register_plugin(_make_manifest())
        self.sdk.install_plugin("test-plugin", handler=lambda: None)
        result = self.sdk.execute_plugin("test-plugin")
        self.assertFalse(result["success"])

    def test_execute_handler_exception(self):
        def bad_handler():
            raise ValueError("boom")
        self.sdk.register_plugin(_make_manifest())
        self.sdk.install_plugin("test-plugin", handler=bad_handler)
        self.sdk.activate_plugin("test-plugin")
        result = self.sdk.execute_plugin("test-plugin")
        self.assertFalse(result["success"])
        self.assertEqual(result["error_type"], "ValueError")

    # --- Suspend ---
    def test_suspend_plugin(self):
        self.sdk.register_plugin(_make_manifest())
        self.sdk.install_plugin("test-plugin", handler=lambda: None)
        self.sdk.activate_plugin("test-plugin")
        result = self.sdk.suspend_plugin("test-plugin", reason="maintenance")
        self.assertTrue(result["suspended"])
        self.assertEqual(result["reason"], "maintenance")

    # --- Uninstall ---
    def test_uninstall_plugin(self):
        self.sdk.register_plugin(_make_manifest())
        self.sdk.install_plugin("test-plugin", handler=lambda: None)
        result = self.sdk.uninstall_plugin("test-plugin")
        self.assertTrue(result["uninstalled"])

    # --- Lifecycle ---
    def test_full_lifecycle(self):
        self.sdk.register_plugin(_make_manifest())
        self.sdk.install_plugin("test-plugin", handler=lambda: "alive")
        self.sdk.activate_plugin("test-plugin")
        exec_result = self.sdk.execute_plugin("test-plugin")
        self.assertTrue(exec_result["success"])
        self.sdk.suspend_plugin("test-plugin")
        exec_result = self.sdk.execute_plugin("test-plugin")
        self.assertFalse(exec_result["success"])
        self.sdk.uninstall_plugin("test-plugin")
        info = self.sdk.get_plugin_info("test-plugin")
        self.assertEqual(info["state"], "uninstalled")

    # --- Info and listing ---
    def test_get_plugin_info(self):
        self.sdk.register_plugin(_make_manifest())
        info = self.sdk.get_plugin_info("test-plugin")
        self.assertIsNotNone(info)
        self.assertEqual(info["name"], "test-plugin")
        self.assertEqual(info["state"], "validated")

    def test_list_plugins(self):
        self.sdk.register_plugin(_make_manifest(name="plugin-a"))
        self.sdk.register_plugin(_make_manifest(name="plugin-b"))
        plugins = self.sdk.list_plugins()
        self.assertEqual(len(plugins), 2)

    def test_list_plugins_by_state(self):
        self.sdk.register_plugin(_make_manifest(name="plugin-a"))
        self.sdk.register_plugin(_make_manifest(name="plugin-b"))
        self.sdk.install_plugin("plugin-a", handler=lambda: None)
        self.assertEqual(len(self.sdk.list_plugins(state="installed")), 1)

    # --- Events ---
    def test_event_log(self):
        self.sdk.register_plugin(_make_manifest())
        events = self.sdk.get_event_log("test-plugin")
        self.assertTrue(len(events) >= 1)
        self.assertEqual(events[0]["action"], "registered")

    # --- Hooks ---
    def test_register_hook(self):
        called = []
        self.sdk.register_hook("on_activate", lambda name: called.append(name))
        m = _make_manifest(hooks={"on_activate": "on_activate"})
        self.sdk.register_plugin(m)
        self.sdk.install_plugin("test-plugin", handler=lambda: None)
        self.sdk.activate_plugin("test-plugin")
        self.assertIn("test-plugin", called)

    # --- Status ---
    def test_status(self):
        status = self.sdk.get_status()
        self.assertEqual(status["module"], "plugin_extension_sdk")
        self.assertIn("total_plugins", status)
        self.assertIn("available_capabilities", status)

    # --- Sandbox stats ---
    def test_sandbox_stats(self):
        self.sdk.register_plugin(_make_manifest())
        self.sdk.install_plugin("test-plugin", handler=lambda: 1)
        self.sdk.activate_plugin("test-plugin")
        self.sdk.execute_plugin("test-plugin")
        self.sdk.execute_plugin("test-plugin")
        info = self.sdk.get_plugin_info("test-plugin")
        self.assertEqual(info["stats"]["call_count"], 2)
        self.assertEqual(info["stats"]["error_count"], 0)

    # --- Re-register after uninstall ---
    def test_reregister_after_uninstall(self):
        self.sdk.register_plugin(_make_manifest())
        self.sdk.install_plugin("test-plugin", handler=lambda: None)
        self.sdk.uninstall_plugin("test-plugin")
        result = self.sdk.register_plugin(_make_manifest(version="2.0.0"))
        self.assertTrue(result["registered"])


if __name__ == "__main__":
    unittest.main()
