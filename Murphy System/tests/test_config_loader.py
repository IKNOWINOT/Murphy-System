# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Unit tests for config/config_loader.py

Covers:
- YAML file loading (happy path, missing file, bad YAML)
- Deep merge behaviour
- Environment variable overlay (legacy names and namespaced names)
- Type coercion (bool, int, float, str)
- get() dotted-key access with defaults
- get_all() shallow copy
- Cache invalidation / force_reload
"""

import os
import sys
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch

# ---------------------------------------------------------------------------
# Make config/ importable regardless of working directory
# ---------------------------------------------------------------------------
_CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
sys.path.insert(0, str(_CONFIG_DIR.parent))  # repo root → Murphy System/


class TestConfigLoaderYAMLLoading(unittest.TestCase):
    """_load_yaml() helper."""

    def _get_loader(self):
        import importlib
        import config.config_loader as cl
        importlib.reload(cl)
        return cl

    def test_missing_file_returns_empty_dict(self):
        cl = self._get_loader()
        result = cl._load_yaml(Path("/nonexistent/config/murphy.yaml"))
        self.assertEqual(result, {})

    def test_valid_yaml_returns_dict(self):
        import tempfile, yaml
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as fh:
            fh.write("system:\n  env: testing\n  version: '9.9.9'\n")
            tmp = Path(fh.name)
        try:
            cl = self._get_loader()
            result = cl._load_yaml(tmp)
            self.assertEqual(result["system"]["env"], "testing")
            self.assertEqual(result["system"]["version"], "9.9.9")
        finally:
            tmp.unlink(missing_ok=True)

    def test_non_dict_yaml_returns_empty_dict(self):
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as fh:
            fh.write("- item1\n- item2\n")
            tmp = Path(fh.name)
        try:
            cl = self._get_loader()
            result = cl._load_yaml(tmp)
            self.assertEqual(result, {})
        finally:
            tmp.unlink(missing_ok=True)

    def test_malformed_yaml_returns_empty_dict(self):
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as fh:
            fh.write("key: [unclosed\n")
            tmp = Path(fh.name)
        try:
            cl = self._get_loader()
            result = cl._load_yaml(tmp)
            self.assertEqual(result, {})
        finally:
            tmp.unlink(missing_ok=True)


class TestDeepMerge(unittest.TestCase):
    """_deep_merge() helper."""

    def _get_loader(self):
        import importlib
        import config.config_loader as cl
        importlib.reload(cl)
        return cl

    def test_simple_overlay(self):
        cl = self._get_loader()
        base = {"a": 1, "b": 2}
        cl._deep_merge(base, {"b": 99, "c": 3})
        self.assertEqual(base, {"a": 1, "b": 99, "c": 3})

    def test_nested_merge_does_not_obliterate(self):
        cl = self._get_loader()
        base = {"api": {"host": "127.0.0.1", "port": 8000}}
        cl._deep_merge(base, {"api": {"port": 9000}})
        self.assertEqual(base["api"]["host"], "127.0.0.1")  # preserved
        self.assertEqual(base["api"]["port"], 9000)         # overwritten

    def test_overlay_dict_over_scalar_replaces(self):
        cl = self._get_loader()
        base = {"key": "scalar"}
        cl._deep_merge(base, {"key": {"nested": True}})
        self.assertEqual(base["key"], {"nested": True})


class TestCoerce(unittest.TestCase):
    """_coerce() type conversion."""

    def _get_loader(self):
        import importlib
        import config.config_loader as cl
        importlib.reload(cl)
        return cl

    def test_true_variants(self):
        cl = self._get_loader()
        for val in ("true", "True", "TRUE", "yes", "1", "on"):
            self.assertIs(cl._coerce(val), True, msg=f"Expected True for {val!r}")

    def test_false_variants(self):
        cl = self._get_loader()
        for val in ("false", "False", "FALSE", "no", "0", "off"):
            self.assertIs(cl._coerce(val), False, msg=f"Expected False for {val!r}")

    def test_integer(self):
        cl = self._get_loader()
        self.assertEqual(cl._coerce("8000"), 8000)
        self.assertEqual(cl._coerce("-5"), -5)

    def test_float(self):
        cl = self._get_loader()
        self.assertAlmostEqual(cl._coerce("0.85"), 0.85)
        self.assertAlmostEqual(cl._coerce("3.14"), 3.14)

    def test_string_passthrough(self):
        cl = self._get_loader()
        self.assertEqual(cl._coerce("groq"), "groq")
        self.assertEqual(cl._coerce("  spaced  "), "spaced")


class TestSetDotted(unittest.TestCase):
    """_set_dotted() nested key writer."""

    def _get_loader(self):
        import importlib
        import config.config_loader as cl
        importlib.reload(cl)
        return cl

    def test_simple_set(self):
        cl = self._get_loader()
        cfg: dict = {}
        cl._set_dotted(cfg, "a.b.c", 42)
        self.assertEqual(cfg["a"]["b"]["c"], 42)

    def test_overwrites_existing(self):
        cl = self._get_loader()
        cfg = {"api": {"port": 8000}}
        cl._set_dotted(cfg, "api.port", 9000)
        self.assertEqual(cfg["api"]["port"], 9000)

    def test_creates_intermediate_dicts(self):
        cl = self._get_loader()
        cfg: dict = {}
        cl._set_dotted(cfg, "x.y.z", "hello")
        self.assertEqual(cfg["x"]["y"]["z"], "hello")


class TestEnvOverrides(unittest.TestCase):
    """Environment variable overlay via load_config()."""

    def setUp(self):
        # Wipe cache between tests
        import importlib
        import config.config_loader as cl
        importlib.reload(cl)
        self._cl = cl

    def tearDown(self):
        self._cl.invalidate_cache()

    def _load_with_env(self, env_overrides: dict) -> dict:
        """Reload config with a controlled environment."""
        self._cl.invalidate_cache()
        with patch.dict(os.environ, env_overrides, clear=False):
            return self._cl.load_config(force_reload=True)

    def test_legacy_env_var_log_level(self):
        cfg = self._load_with_env({"LOG_LEVEL": "DEBUG"})
        self.assertEqual(cfg["logging"]["level"], "DEBUG")

    def test_legacy_env_var_api_port(self):
        cfg = self._load_with_env({"API_PORT": "9999"})
        self.assertEqual(cfg["api"]["port"], 9999)

    def test_legacy_env_var_murphy_env(self):
        cfg = self._load_with_env({"MURPHY_ENV": "production"})
        self.assertEqual(cfg["system"]["env"], "production")

    def test_legacy_env_var_llm_provider(self):
        cfg = self._load_with_env({"MURPHY_LLM_PROVIDER": "openai"})
        self.assertEqual(cfg["llm"]["provider"], "openai")

    def test_legacy_env_var_confidence_threshold(self):
        cfg = self._load_with_env({"CONFIDENCE_THRESHOLD": "0.99"})
        self.assertAlmostEqual(cfg["thresholds"]["confidence"], 0.99)

    def test_namespaced_env_var_with_murphy_prefix(self):
        cfg = self._load_with_env({"MURPHY_API__PORT": "7777"})
        self.assertEqual(cfg["api"]["port"], 7777)

    def test_namespaced_env_var_without_murphy_prefix(self):
        cfg = self._load_with_env({"SWARM__MAX_ITERATIONS": "20"})
        self.assertEqual(cfg["swarm"]["max_iterations"], 20)

    def test_env_overrides_yaml_value(self):
        """Env vars must win over YAML file values."""
        cfg = self._load_with_env({"LOG_LEVEL": "CRITICAL"})
        # The YAML default is INFO; env must override it
        self.assertEqual(cfg["logging"]["level"], "CRITICAL")

    def test_boolean_coercion_via_env(self):
        cfg = self._load_with_env({"API_DEBUG": "true"})
        self.assertIs(cfg["api"]["debug"], True)


class TestGetAndGetAll(unittest.TestCase):
    """get() and get_all() public API."""

    def setUp(self):
        import importlib
        import config.config_loader as cl
        importlib.reload(cl)
        cl.invalidate_cache()
        self._cl = cl

    def tearDown(self):
        self._cl.invalidate_cache()

    def test_get_existing_key(self):
        val = self._cl.get("api.port")
        self.assertIsNotNone(val)
        self.assertIsInstance(val, int)

    def test_get_missing_key_returns_default(self):
        result = self._cl.get("no.such.key.anywhere", "fallback")
        self.assertEqual(result, "fallback")

    def test_get_missing_key_returns_none_by_default(self):
        result = self._cl.get("completely.missing")
        self.assertIsNone(result)

    def test_get_all_returns_dict(self):
        cfg = self._cl.get_all()
        self.assertIsInstance(cfg, dict)
        self.assertIn("api", cfg)

    def test_get_all_returns_copy(self):
        cfg1 = self._cl.get_all()
        cfg2 = self._cl.get_all()
        cfg1["__test__"] = True
        self.assertNotIn("__test__", cfg2)


class TestCacheAndForceReload(unittest.TestCase):
    """Caching and force_reload behaviour."""

    def setUp(self):
        import importlib
        import config.config_loader as cl
        importlib.reload(cl)
        cl.invalidate_cache()
        self._cl = cl

    def tearDown(self):
        self._cl.invalidate_cache()

    def test_second_call_returns_same_object(self):
        cfg1 = self._cl.load_config()
        cfg2 = self._cl.load_config()
        self.assertIs(cfg1, cfg2)

    def test_invalidate_cache_forces_new_object(self):
        cfg1 = self._cl.load_config()
        self._cl.invalidate_cache()
        cfg2 = self._cl.load_config()
        # After invalidation a new dict must be created
        self.assertIsNot(cfg1, cfg2)

    def test_force_reload_bypasses_cache(self):
        cfg1 = self._cl.load_config()
        cfg2 = self._cl.load_config(force_reload=True)
        self.assertIsNot(cfg1, cfg2)


class TestDefaultYAMLsLoad(unittest.TestCase):
    """Verify the real murphy.yaml and engines.yaml ship with expected keys."""

    def setUp(self):
        import importlib
        import config.config_loader as cl
        importlib.reload(cl)
        cl.invalidate_cache()
        self._cl = cl

    def tearDown(self):
        self._cl.invalidate_cache()

    def test_murphy_yaml_supplies_api_section(self):
        cfg = self._cl.load_config()
        self.assertIn("api", cfg)
        self.assertIn("port", cfg["api"])

    def test_murphy_yaml_supplies_thresholds_section(self):
        cfg = self._cl.load_config()
        self.assertIn("thresholds", cfg)
        self.assertIn("confidence", cfg["thresholds"])

    def test_engines_yaml_supplies_swarm_section(self):
        cfg = self._cl.load_config()
        self.assertIn("swarm", cfg)
        self.assertIn("exploration_agents", cfg["swarm"])

    def test_engines_yaml_supplies_domain_engines_section(self):
        cfg = self._cl.load_config()
        self.assertIn("domain_engines", cfg)
        self.assertIn("enabled", cfg["domain_engines"])

    def test_confidence_default_is_valid_fraction(self):
        confidence = self._cl.get("thresholds.confidence", 0.85)
        self.assertGreaterEqual(confidence, 0.0)
        self.assertLessEqual(confidence, 1.0)

    def test_api_port_default_is_reasonable(self):
        port = self._cl.get("api.port", 8000)
        self.assertGreater(port, 0)
        self.assertLess(port, 65536)


if __name__ == "__main__":
    unittest.main()
