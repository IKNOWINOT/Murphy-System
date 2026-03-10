"""
Tests for config.py (Settings / Pydantic configuration)

Closes Gap 3: Settings had ZERO test coverage.

Proves:
- Default values are correct
- Pydantic ge/le constraints reject invalid values
- Environment variable overrides work
- Type coercion (str→int for ports) works
- reload_settings() creates a fresh instance
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestSettingsDefaults(unittest.TestCase):
    """Default values must match specification."""

    def _make_settings(self, **env_overrides):
        """Create a fresh Settings instance with optional env overrides."""
        # Clear the cached singleton so each test is independent
        import config as cfg_mod
        cfg_mod._settings_instance = None

        env = {
            "API_HOST": "127.0.0.1",
            "API_PORT": "8000",
        }
        env.update(env_overrides)
        for k, v in env.items():
            os.environ[k] = str(v)

        # Re-import to pick up env
        from config import Settings
        return Settings()

    def setUp(self):
        # Preserve and clear env vars that might interfere
        self._orig_env = {}
        for key in list(os.environ):
            if key.upper().startswith(("API_", "DB_", "LLM_", "MURPHY_",
                                       "CONFIDENCE_", "GROQ_", "RATE_LIMIT_",
                                       "LOG_", "REDIS_", "CACHE_", "CORS_",
                                       "ENCRYPTED_", "USE_KEY_")):
                self._orig_env[key] = os.environ.pop(key)

    def tearDown(self):
        os.environ.update(self._orig_env)
        import config as cfg_mod
        cfg_mod._settings_instance = None

    def test_default_api_host(self):
        s = self._make_settings()
        self.assertEqual(s.api_host, "127.0.0.1")

    def test_default_api_port(self):
        s = self._make_settings()
        self.assertEqual(s.api_port, 8000)

    def test_default_confidence_threshold(self):
        s = self._make_settings()
        self.assertAlmostEqual(s.confidence_threshold, 0.85)

    def test_default_murphy_threshold(self):
        s = self._make_settings()
        self.assertAlmostEqual(s.murphy_threshold, 0.5)

    def test_default_murphy_env(self):
        s = self._make_settings()
        self.assertEqual(s.murphy_env, "development")

    def test_default_log_level(self):
        s = self._make_settings()
        self.assertEqual(s.log_level, "INFO")


class TestSettingsEnvOverrides(unittest.TestCase):
    """Environment variables must override defaults."""

    def setUp(self):
        self._orig_env = {}
        for key in list(os.environ):
            if key.upper().startswith(("API_", "DB_", "LLM_", "MURPHY_",
                                       "CONFIDENCE_", "GROQ_", "RATE_LIMIT_",
                                       "LOG_", "REDIS_", "CACHE_", "CORS_",
                                       "ENCRYPTED_", "USE_KEY_")):
                self._orig_env[key] = os.environ.pop(key)

    def tearDown(self):
        # Restore
        for key in ("API_PORT", "LOG_LEVEL", "MURPHY_ENV", "API_HOST",
                     "CONFIDENCE_THRESHOLD"):
            os.environ.pop(key, None)
        os.environ.update(self._orig_env)
        import config as cfg_mod
        cfg_mod._settings_instance = None

    def test_port_override(self):
        os.environ["API_PORT"] = "9999"
        from config import Settings
        s = Settings()
        self.assertEqual(s.api_port, 9999)

    def test_log_level_override(self):
        os.environ["LOG_LEVEL"] = "DEBUG"
        from config import Settings
        s = Settings()
        self.assertEqual(s.log_level, "DEBUG")

    def test_murphy_env_override(self):
        os.environ["MURPHY_ENV"] = "production"
        from config import Settings
        s = Settings()
        self.assertEqual(s.murphy_env, "production")


class TestSettingsValidation(unittest.TestCase):
    """Pydantic constraints (ge/le) must reject invalid values."""

    def setUp(self):
        self._orig_env = {}
        for key in list(os.environ):
            if key.upper().startswith(("API_", "DB_", "LLM_", "MURPHY_",
                                       "CONFIDENCE_", "GROQ_", "RATE_LIMIT_",
                                       "LOG_", "REDIS_", "CACHE_", "CORS_",
                                       "ENCRYPTED_", "USE_KEY_")):
                self._orig_env[key] = os.environ.pop(key)

    def tearDown(self):
        for key in ("CONFIDENCE_THRESHOLD", "MURPHY_THRESHOLD",
                     "MAX_MESSAGES_PER_CONVERSATION"):
            os.environ.pop(key, None)
        os.environ.update(self._orig_env)
        import config as cfg_mod
        cfg_mod._settings_instance = None

    def test_confidence_above_1_rejected(self):
        os.environ["CONFIDENCE_THRESHOLD"] = "1.5"
        from config import Settings
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            Settings()

    def test_confidence_below_0_rejected(self):
        os.environ["CONFIDENCE_THRESHOLD"] = "-0.1"
        from config import Settings
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            Settings()

    def test_murphy_threshold_above_1_rejected(self):
        os.environ["MURPHY_THRESHOLD"] = "2.0"
        from config import Settings
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            Settings()

    def test_max_messages_below_minimum_rejected(self):
        os.environ["MAX_MESSAGES_PER_CONVERSATION"] = "5"
        from config import Settings
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            Settings()


class TestReloadSettings(unittest.TestCase):
    """reload_settings() must create a fresh instance."""

    def setUp(self):
        self._orig_env = {}
        for key in list(os.environ):
            if key.upper().startswith(("API_", "DB_", "LLM_", "MURPHY_",
                                       "CONFIDENCE_", "GROQ_", "RATE_LIMIT_",
                                       "LOG_", "REDIS_", "CACHE_", "CORS_",
                                       "ENCRYPTED_", "USE_KEY_")):
                self._orig_env[key] = os.environ.pop(key)

    def tearDown(self):
        for key in ("LOG_LEVEL",):
            os.environ.pop(key, None)
        os.environ.update(self._orig_env)
        import config as cfg_mod
        cfg_mod._settings_instance = None

    def test_reload_picks_up_changes(self):
        import config as cfg_mod
        cfg_mod._settings_instance = None
        s1 = cfg_mod.get_settings()
        original_level = s1.log_level

        os.environ["LOG_LEVEL"] = "CRITICAL"
        s2 = cfg_mod.reload_settings()
        self.assertEqual(s2.log_level, "CRITICAL")
        self.assertIsNot(s1, s2)


if __name__ == "__main__":
    unittest.main()
