"""
Forge Rate Limiter — Murphy System
====================================
Tier-aware rate limiting for POST /api/demo/generate-deliverable.

Each forge build launches a 64-agent dual-swarm (exploration + control)
with one MultiCursorBrowser controller per agent = 64 compute units per build.
Rate limits are expressed in BUILDS (not raw HTTP requests) to correctly
reflect the actual computational cost.

Tiers (builds/hour / builds/day / burst):
  anonymous    :  3 / 5   / 1
  free         :  5 / 10  / 2
  solo         : 20 / 100 / 5
  business     : 60 / 500 / 10
  professional :120 / ∞   / 20
  enterprise   :  ∞ / ∞   / ∞

Copyright © 2020 Inoni LLC — BSL 1.1
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Compute cost per forge build
AGENTS_PER_BUILD = 64
CURSORS_PER_AGENT = 1
TOTAL_COMPUTE_UNITS = AGENTS_PER_BUILD * CURSORS_PER_AGENT  # 64

# Tier limits: (hourly_builds, daily_builds, burst)
# -1 = unlimited
_TIER_LIMITS: Dict[str, tuple] = {
    "anonymous":    (3,   5,   1),
    "free":         (5,   10,  2),
    "solo":         (20,  100, 5),
    "business":     (60,  500, 10),
    "professional": (120, -1,  20),
    "enterprise":   (-1,  -1,  -1),
}

_WINDOW_HOUR = 3600
_WINDOW_DAY  = 86400


class ForgeRateLimiter:
    """In-process token-bucket + sliding-window rate limiter for forge builds."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # hourly token buckets: key → {"tokens": float, "last_refill": float}
        self._hourly: Dict[str, Dict] = {}
        # daily sliding window: key → list[float] of timestamps
        self._daily: Dict[str, list] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check_and_record(self, request: Any) -> Dict[str, Any]:
        """Check limits and record a build attempt.

        Returns a result dict.  Callers MUST check ``result["allowed"]``
        before proceeding with the build.
        """
        user_id, client_ip = self._extract_identity(request)
        tier = self._resolve_tier(request, user_id)
        key = user_id if user_id != "anonymous" else f"ip:{client_ip}"

        hourly_limit, daily_limit, burst = _TIER_LIMITS.get(tier, _TIER_LIMITS["free"])

        # Enterprise / Professional unlimited
        if hourly_limit == -1:
            return self._unlimited_result(tier, key)

        with self._lock:
            now = time.time()
            hourly_ok, hourly_remaining, retry_after = self._check_hourly(key, hourly_limit, burst, now)
            daily_ok, daily_used, daily_remaining = self._check_daily(key, daily_limit, now)

            allowed = hourly_ok and daily_ok

            if allowed:
                self._record_hourly(key, burst, now)
                self._record_daily(key, now)

        result: Dict[str, Any] = {
            "allowed": allowed,
            "tier": tier,
            "builds_used_today": daily_used + (1 if allowed else 0),
            "builds_remaining_today": max(0, daily_remaining - (1 if allowed else 0)) if daily_limit != -1 else -1,
            "builds_remaining_hour": max(0, hourly_remaining - (1 if allowed else 0)),
            "swarm_cost": {
                "agents": AGENTS_PER_BUILD,
                "cursors_per_agent": CURSORS_PER_AGENT,
                "total_compute_units": TOTAL_COMPUTE_UNITS,
            },
        }
        if not allowed:
            result["error"] = "forge_rate_limit_exceeded"
            result["retry_after_seconds"] = int(retry_after)
            result["upgrade_url"] = "/pricing"
        return result

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _extract_identity(self, request: Any):
        headers = getattr(request, "headers", {}) or {}
        user_id = (headers.get("X-User-ID") or "").strip() or "anonymous"
        fwd = (headers.get("X-Forwarded-For") or "").split(",")[0].strip()
        client = getattr(request, "client", None)
        client_ip = fwd or (client.host if client else "unknown")
        return user_id, client_ip

    def _resolve_tier(self, request: Any, user_id: str) -> str:
        if user_id == "anonymous":
            return "anonymous"
        try:
            from src.subscription_manager import SubscriptionManager
            sm = SubscriptionManager()
            sub = sm.get_subscription(user_id)
            if sub:
                return sub.tier.value.lower()
        except Exception:
            pass
        # Fall back to X-Subscription-Tier header (set by auth middleware)
        headers = getattr(request, "headers", {}) or {}
        return (headers.get("X-Subscription-Tier") or "free").lower()

    def _check_hourly(self, key: str, limit: int, burst: int, now: float):
        bucket = self._hourly.get(key) or {"tokens": float(burst), "last_refill": now}
        elapsed = now - bucket["last_refill"]
        refill = (limit / _WINDOW_HOUR) * elapsed
        tokens = min(float(burst), bucket["tokens"] + refill)
        bucket["last_refill"] = now
        bucket["tokens"] = tokens
        self._hourly[key] = bucket
        allowed = tokens >= 1.0
        remaining = int(tokens)
        retry_after = (1.0 - tokens) / (limit / _WINDOW_HOUR) if not allowed and limit > 0 else 0
        return allowed, remaining, retry_after

    def _record_hourly(self, key: str, burst: int, now: float):
        bucket = self._hourly.get(key, {"tokens": float(burst), "last_refill": now})
        bucket["tokens"] = max(0.0, bucket["tokens"] - 1.0)
        self._hourly[key] = bucket

    def _check_daily(self, key: str, daily_limit: int, now: float):
        if daily_limit == -1:
            return True, 0, -1
        window_start = now - _WINDOW_DAY
        timestamps = [t for t in (self._daily.get(key) or []) if t > window_start]
        self._daily[key] = timestamps
        used = len(timestamps)
        remaining = max(0, daily_limit - used)
        return used < daily_limit, used, remaining

    def _record_daily(self, key: str, now: float):
        if key not in self._daily:
            self._daily[key] = []
        self._daily[key].append(now)

    def _unlimited_result(self, tier: str, key: str) -> Dict[str, Any]:
        return {
            "allowed": True,
            "tier": tier,
            "builds_used_today": 0,
            "builds_remaining_today": -1,
            "builds_remaining_hour": -1,
            "swarm_cost": {
                "agents": AGENTS_PER_BUILD,
                "cursors_per_agent": CURSORS_PER_AGENT,
                "total_compute_units": TOTAL_COMPUTE_UNITS,
            },
        }


# Module-level singleton
_limiter: Optional[ForgeRateLimiter] = None


def get_forge_rate_limiter() -> ForgeRateLimiter:
    global _limiter
    if _limiter is None:
        _limiter = ForgeRateLimiter()
    return _limiter
