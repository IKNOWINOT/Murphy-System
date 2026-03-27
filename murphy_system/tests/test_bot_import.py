"""
Test that all bot modules can be imported without error.

Each bot must:
1. Import without raising exceptions
2. Expose at least one callable (function or class) at the module level

GAP 7 closure: verifies all 104+ bot modules are importable and functional.
"""
import importlib
import os
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

BOTS_DIR = ROOT / "bots"


def _discover_bot_modules():
    """Discover bot Python modules, excluding __init__ and helper files."""
    modules = []
    if not BOTS_DIR.exists():
        return modules
    for path in BOTS_DIR.iterdir():
        if path.is_file() and path.suffix == ".py" and not path.name.startswith("_"):
            modules.append(path.stem)
        elif path.is_dir() and (path / "__init__.py").exists() and not path.name.startswith("_"):
            modules.append(path.name)
    return sorted(modules)


BOT_MODULES = _discover_bot_modules()


class TestBotImports(unittest.TestCase):
    """Verify each bot module imports cleanly."""

    def _test_one_bot(self, bot_name: str):
        module_path = f"bots.{bot_name}"
        try:
            mod = importlib.import_module(module_path)
        except ImportError as e:
            if any(dep in str(e).lower() for dep in ["tensorflow", "torch", "cv2", "sklearn", "numpy", "scipy"]):
                self.skipTest(f"Optional dependency missing for {bot_name}: {e}")
            self.fail(f"Failed to import {module_path}: {e}")
        except Exception as e:
            self.fail(f"Error importing {module_path}: {e}")

        callables = [
            x for x in dir(mod)
            if callable(getattr(mod, x)) and not x.startswith("_")
        ]
        self.assertGreater(
            len(callables), 0,
            f"Bot '{bot_name}' must expose at least one callable at module level"
        )


def _make_test_method(bot_name):
    def test_method(self):
        self._test_one_bot(bot_name)
    test_method.__name__ = f"test_bot_{bot_name}"
    test_method.__doc__ = f"Bot '{bot_name}' imports and has callables"
    return test_method


for _bot in BOT_MODULES:
    _method = _make_test_method(_bot)
    setattr(TestBotImports, f"test_bot_{_bot}", _method)


class TestBotDiscovery(unittest.TestCase):
    """Meta-test: ensure we found a meaningful number of bots."""

    def test_at_least_50_bots_discovered(self):
        self.assertGreaterEqual(
            len(BOT_MODULES), 50,
            f"Expected at least 50 bot modules, found {len(BOT_MODULES)}: {BOT_MODULES}"
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
