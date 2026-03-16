"""
Tests: Health Monitor — Bounded History (collections.deque)

Proves that HealthMonitor._history never exceeds _max_history entries,
eliminating the previous memory-spike pattern of grow-then-truncate.

Bug Label  : CWE-770 — Allocation of Resources Without Limits
Module     : src/health_monitor.py
Fixed In   : HealthMonitor.__init__ (switched to collections.deque)
"""

import collections
import os
import unittest


from health_monitor import HealthMonitor


class TestBoundedHistory(unittest.TestCase):
    """HealthMonitor._history uses deque(maxlen=...) and never overflows."""

    def setUp(self):
        self.monitor = HealthMonitor()
        self.monitor.register("ok", lambda: {"status": "healthy", "message": "ok"})

    def test_history_is_deque(self):
        """Implementation must be collections.deque, not list."""
        self.assertIsInstance(self.monitor._history, collections.deque)

    def test_deque_has_maxlen(self):
        """The deque must have a maxlen equal to _max_history."""
        self.assertEqual(self.monitor._history.maxlen, self.monitor._max_history)

    def test_history_never_exceeds_max(self):
        """After many check_all() calls the history stays bounded."""
        for _ in range(self.monitor._max_history + 50):
            self.monitor.check_all()

        self.assertLessEqual(len(self.monitor._history), self.monitor._max_history)

    def test_oldest_entries_are_evicted(self):
        """Oldest reports are evicted once the cap is reached."""
        # Fill exactly to cap
        for _ in range(self.monitor._max_history):
            self.monitor.check_all()

        first_id = self.monitor._history[0].report_id

        # One more check should evict the oldest
        self.monitor.check_all()
        self.assertNotEqual(self.monitor._history[0].report_id, first_id)

    def test_get_history_works_after_overflow(self):
        """get_history() still returns correct results after overflow."""
        for _ in range(self.monitor._max_history + 20):
            self.monitor.check_all()

        history = self.monitor.get_history(limit=5)
        self.assertEqual(len(history), 5)
        # Each entry should be a dict with expected keys
        for entry in history:
            self.assertIn("report_id", entry)
            self.assertIn("system_status", entry)

    def test_get_latest_report_after_overflow(self):
        """get_latest_report() returns the most recent report."""
        for _ in range(self.monitor._max_history + 10):
            self.monitor.check_all()

        latest = self.monitor.get_latest_report()
        self.assertIsNotNone(latest)
        # Should be the same as the last item in the deque
        self.assertEqual(latest.report_id, self.monitor._history[-1].report_id)


if __name__ == "__main__":
    unittest.main()
