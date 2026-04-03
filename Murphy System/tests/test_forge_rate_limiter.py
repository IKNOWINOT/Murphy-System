"""Tests for ForgeRateLimiter — tier-aware, swarm-cost-aware rate limiter."""
from __future__ import annotations
import os, sys, threading
from pathlib import Path
import pytest
os.environ.setdefault("MURPHY_ENV", "test")

from src.forge_rate_limiter import ForgeRateLimiter, AGENTS_PER_BUILD, TOTAL_COMPUTE_UNITS


class _FakeRequest:
    def __init__(self, user_id="anonymous", ip="127.0.0.1", tier=None):
        self.headers = {"X-User-ID": user_id}
        if tier: self.headers["X-Subscription-Tier"] = tier
        class _Client: host = ip
        self.client = _Client()


class TestForgeRateLimiterBasics:
    def test_anonymous_allows_within_burst(self):
        lim = ForgeRateLimiter()
        r = lim.check_and_record(_FakeRequest())
        assert r["allowed"] is True

    def test_anonymous_blocks_after_burst(self):
        lim = ForgeRateLimiter()
        req = _FakeRequest(ip="1.2.3.4")
        # Use up burst (1)
        lim.check_and_record(req)
        r2 = lim.check_and_record(req)
        assert r2["allowed"] is False
        assert r2["error"] == "forge_rate_limit_exceeded"
        assert "retry_after_seconds" in r2
        assert r2["upgrade_url"] == "/pricing"

    def test_result_contains_swarm_cost(self):
        lim = ForgeRateLimiter()
        r = lim.check_and_record(_FakeRequest(ip="9.9.9.9"))
        assert r["swarm_cost"]["agents"] == AGENTS_PER_BUILD
        assert r["swarm_cost"]["total_compute_units"] == TOTAL_COMPUTE_UNITS

    def test_free_tier_has_higher_limit(self):
        lim = ForgeRateLimiter()
        req = _FakeRequest(user_id="user-free-1", tier="free")
        # Free tier has burst=2; first 2 requests should succeed
        results = [lim.check_and_record(req) for _ in range(2)]
        assert all(r["allowed"] for r in results)

    def test_enterprise_is_unlimited(self):
        lim = ForgeRateLimiter()
        req = _FakeRequest(user_id="user-ent-1", tier="enterprise")
        r = None
        for _ in range(20):
            r = lim.check_and_record(req)
            assert r["allowed"] is True
        assert r["builds_remaining_today"] == -1

    def test_different_ips_have_independent_buckets(self):
        lim = ForgeRateLimiter()
        r1 = lim.check_and_record(_FakeRequest(ip="10.0.0.1"))
        r2 = lim.check_and_record(_FakeRequest(ip="10.0.0.2"))
        assert r1["allowed"] is True
        assert r2["allowed"] is True

    def test_daily_limit_tracked(self):
        lim = ForgeRateLimiter()
        req = _FakeRequest(ip="5.5.5.5")
        r = lim.check_and_record(req)
        assert r["builds_used_today"] >= 1

    def test_tier_field_in_result(self):
        lim = ForgeRateLimiter()
        r = lim.check_and_record(_FakeRequest())
        assert r["tier"] == "anonymous"

    def test_professional_unlimited_daily(self):
        lim = ForgeRateLimiter()
        req = _FakeRequest(user_id="user-pro-1", tier="professional")
        r = lim.check_and_record(req)
        assert r["allowed"] is True
        assert r["builds_remaining_today"] == -1

    def test_concurrent_requests_safe(self):
        lim = ForgeRateLimiter()
        results = []
        def _req():
            results.append(lim.check_and_record(_FakeRequest(ip="concurrent")))
        threads = [threading.Thread(target=_req) for _ in range(5)]
        for t in threads: t.start()
        for t in threads: t.join()
        assert len(results) == 5
