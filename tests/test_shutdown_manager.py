"""
Tests for shutdown_manager.py

Closes Gap 2: ShutdownManager had ZERO test coverage.

Proves:
- Cleanup handlers execute in LIFO order
- Re-entrant shutdown is prevented (is_shutting_down guard)
- Exceptions in one handler don't prevent others from running
- Manual shutdown() triggers cleanup
- Registration convenience function works
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from shutdown_manager import ShutdownManager


class TestCleanupOrder(unittest.TestCase):
    """Handlers execute in reverse registration order (LIFO)."""

    def test_lifo_order(self):
        mgr = ShutdownManager()
        order = []
        mgr.register_cleanup_handler(lambda: order.append("first"), "first")
        mgr.register_cleanup_handler(lambda: order.append("second"), "second")
        mgr.register_cleanup_handler(lambda: order.append("third"), "third")

        mgr.shutdown()
        self.assertEqual(order, ["third", "second", "first"])


class TestReentrantPrevention(unittest.TestCase):
    """Calling _cleanup twice must not re-execute handlers."""

    def test_double_cleanup_runs_once(self):
        mgr = ShutdownManager()
        count = {"n": 0}
        mgr.register_cleanup_handler(lambda: count.__setitem__("n", count["n"] + 1), "counter")

        mgr.shutdown()
        mgr.shutdown()  # second call should be a no-op

        self.assertEqual(count["n"], 1)
        self.assertTrue(mgr.is_shutting_down)


class TestHandlerExceptionIsolation(unittest.TestCase):
    """One handler raising must not prevent subsequent handlers."""

    def test_failing_handler_does_not_block_others(self):
        mgr = ShutdownManager()
        executed = []

        mgr.register_cleanup_handler(lambda: executed.append("a"), "a")
        mgr.register_cleanup_handler(lambda: (_ for _ in ()).throw(RuntimeError("boom")), "bad")
        mgr.register_cleanup_handler(lambda: executed.append("c"), "c")

        mgr.shutdown()

        # "c" is registered last → executes first (LIFO)
        # "bad" raises → logged but not re-raised
        # "a" still executes
        self.assertIn("c", executed)
        self.assertIn("a", executed)


class TestManualShutdown(unittest.TestCase):
    """shutdown() is the public API for triggering cleanup."""

    def test_shutdown_sets_flag(self):
        mgr = ShutdownManager()
        self.assertFalse(mgr.is_shutting_down)
        mgr.shutdown()
        self.assertTrue(mgr.is_shutting_down)


class TestHandlerRegistration(unittest.TestCase):
    """Registration stores handler with correct name."""

    def test_register_with_name(self):
        mgr = ShutdownManager()
        mgr.register_cleanup_handler(lambda: None, "my_handler")
        self.assertEqual(len(mgr.cleanup_handlers), 1)
        _, name = mgr.cleanup_handlers[0]
        self.assertEqual(name, "my_handler")

    def test_register_without_name_uses_func_name(self):
        mgr = ShutdownManager()

        def my_cleanup():
            pass

        mgr.register_cleanup_handler(my_cleanup)
        _, name = mgr.cleanup_handlers[0]
        self.assertEqual(name, "my_cleanup")


if __name__ == "__main__":
    unittest.main()
