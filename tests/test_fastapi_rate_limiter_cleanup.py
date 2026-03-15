"""
Tests: FastAPI Rate Limiter — TTL-Based Bucket Cleanup

Proves that the ``_FastAPIRateLimiter`` evicts stale client buckets
after the configured TTL, preventing unbounded memory growth.

Bug Label  : CWE-400 — Uncontrolled Resource Consumption
Module     : src/fastapi_security.py
Fixed In   : _FastAPIRateLimiter._evict_stale_buckets
"""

import sys
import os
import time
import unittest

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

pytest.importorskip("fastapi", reason="fastapi not installed")
from fastapi_security import _FastAPIRateLimiter


class TestRateLimiterCleanup(unittest.TestCase):
    """_FastAPIRateLimiter must evict stale buckets to bound memory."""

    def test_stale_buckets_evicted(self):
        """Buckets older than TTL are removed during the next cleanup pass."""
        rl = _FastAPIRateLimiter(requests_per_minute=1000, burst_size=100)

        # Populate with several clients
        for i in range(50):
            rl.check(f"10.0.0.{i}")
        self.assertEqual(len(rl._buckets), 50)

        # Simulate time passing beyond both the cleanup interval and the TTL
        past = time.monotonic() - rl._BUCKET_TTL_SECONDS - 1
        for bucket in rl._buckets.values():
            bucket["last_refill"] = past
        rl._last_cleanup = past

        # The next check triggers cleanup
        rl.check("10.0.0.200")
        # Only the freshly-accessed bucket should remain
        self.assertEqual(len(rl._buckets), 1)
        self.assertIn("10.0.0.200", rl._buckets)

    def test_active_buckets_not_evicted(self):
        """Recently used buckets survive the cleanup pass."""
        rl = _FastAPIRateLimiter(requests_per_minute=1000, burst_size=100)
        rl.check("active-client")

        # Force cleanup interval to be passed, but bucket is still fresh
        rl._last_cleanup = time.monotonic() - rl._CLEANUP_INTERVAL - 1
        rl.check("another-client")

        self.assertIn("active-client", rl._buckets)
        self.assertIn("another-client", rl._buckets)

    def test_cleanup_interval_respected(self):
        """Cleanup does not run on every call — only after the interval."""
        rl = _FastAPIRateLimiter(requests_per_minute=1000, burst_size=100)
        rl.check("c1")

        # Make c1 stale
        past = time.monotonic() - rl._BUCKET_TTL_SECONDS - 1
        rl._buckets["c1"]["last_refill"] = past

        # But don't advance _last_cleanup past the interval
        rl._last_cleanup = time.monotonic()

        rl.check("c2")
        # c1 should still be present because cleanup hasn't triggered
        self.assertIn("c1", rl._buckets)

    def test_rate_limiting_still_works(self):
        """Basic rate limiting behaviour is preserved after the TTL fix."""
        rl = _FastAPIRateLimiter(requests_per_minute=60, burst_size=5)

        results = [rl.check("client") for _ in range(10)]
        allowed = sum(1 for r in results if r["allowed"])
        denied = sum(1 for r in results if not r["allowed"])

        self.assertEqual(allowed, 5)
        self.assertEqual(denied, 5)

    def test_constants_are_sane(self):
        """TTL and interval values are sensible defaults."""
        self.assertGreater(_FastAPIRateLimiter._BUCKET_TTL_SECONDS, 0)
        self.assertGreater(_FastAPIRateLimiter._CLEANUP_INTERVAL, 0)
        self.assertGreater(
            _FastAPIRateLimiter._BUCKET_TTL_SECONDS,
            _FastAPIRateLimiter._CLEANUP_INTERVAL,
        )


if __name__ == "__main__":
    unittest.main()
