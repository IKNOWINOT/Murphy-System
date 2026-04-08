"""
Forge Rate Limiter — Murphy System
====================================
Tier-aware rate limiting for POST /api/demo/generate-deliverable.

Each forge build launches a dynamic swarm — the agent count scales with
task complexity.  Rate limits are expressed in BUILDS (not raw HTTP
requests or a fixed agent count) to correctly reflect computational cost.

Tiers (builds/hour / builds/day / burst):
  anonymous    :  3 / 5   / 1
  free         :  5 / 10  / 2
  solo         : 20 / 100 / 5
  business     : 60 / 500 / 10
  professional :120 / ∞   / 20
  enterprise   :  ∞ / ∞   / ∞

Set MURPHY_RATE_LIMIT_BACKEND=redis (and REDIS_URL) for shared counters
across multiple Gunicorn workers.  Falls back to in-memory when Redis is
unavailable with a warning log.

Copyright © 2020 Inoni LLC — BSL 1.1
"""
from __future__ import annotations

import logging
import os
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# One MultiCursorBrowser controller is allocated per agent in a build.
# Agent count per build is dynamic — it scales with task complexity.
CURSORS_PER_AGENT = 1

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
    """In-process token-bucket + sliding-window rate limiter for forge builds.

    When MURPHY_RATE_LIMIT_BACKEND=redis (and REDIS_URL is set), daily counters
    are stored in Redis so they are shared across all Gunicorn workers.  Falls
    back to in-memory with a warning if Redis is unavailable.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # hourly token buckets: key → {"tokens": float, "last_refill": float}
        self._hourly: Dict[str, Dict] = {}
        # daily sliding window: key → list[float] of timestamps
        self._daily: Dict[str, list] = {}

        # Gap 5: Redis backend for shared daily counters
        self._redis_client: Optional[Any] = None
        self._redis_available = False
        _backend = os.environ.get("MURPHY_RATE_LIMIT_BACKEND", "memory").lower()
        if _backend == "redis":
            _redis_url = os.environ.get("REDIS_URL", "")
            if _redis_url:
                try:
                    import redis as _redis_mod  # type: ignore
                    self._redis_client = _redis_mod.from_url(_redis_url, socket_connect_timeout=2)
                    self._redis_client.ping()
                    self._redis_available = True
                    logger.info("ForgeRateLimiter: daily limits using Redis backend")
                except Exception as _exc:
                    logger.warning(
                        "Redis unavailable (%s) — ForgeRateLimiter running in per-worker mode "
                        "— limits not shared across workers.",
                        _exc,
                    )
            else:
                logger.warning(
                    "MURPHY_RATE_LIMIT_BACKEND=redis but REDIS_URL is not set "
                    "— ForgeRateLimiter falling back to in-memory rate limiting."
                )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check_and_record(self, request: Any) -> Dict[str, Any]:
        """Check limits and record a build attempt.

        Returns a result dict.  Callers MUST check ``result["allowed"]``
        before proceeding with the build.
        Daily counters use Redis when available so limits are shared across
        all Gunicorn workers.
        """
        user_id, client_ip = self._extract_identity(request)
        tier = self._resolve_tier(request, user_id)
        key = user_id if user_id != "anonymous" else f"ip:{client_ip}"

        hourly_limit, daily_limit, burst = _TIER_LIMITS.get(tier, _TIER_LIMITS["free"])

        # Enterprise / Professional unlimited
        if hourly_limit == -1:
            return self._unlimited_result(tier, key)

        now = time.time()

        # ── Redis daily check (shared across workers) ─────────────────────────
        if self._redis_available and daily_limit != -1:
            redis_daily_ok, redis_daily_used, redis_daily_remaining = \
                self._check_daily_redis(key, daily_limit, now)
        else:
            redis_daily_ok = None  # signals: use in-memory path

        with self._lock:
            hourly_ok, hourly_remaining, retry_after = self._check_hourly(key, hourly_limit, burst, now)

            if redis_daily_ok is not None:
                daily_ok = redis_daily_ok
                daily_used = redis_daily_used
                daily_remaining = redis_daily_remaining
            else:
                daily_ok, daily_used, daily_remaining = self._check_daily(key, daily_limit, now)

            allowed = hourly_ok and daily_ok

            if allowed:
                self._record_hourly(key, burst, now)
                if redis_daily_ok is None:
                    self._record_daily(key, now)
                # Redis daily was already incremented in _check_daily_redis


        result: Dict[str, Any] = {
            "allowed": allowed,
            "tier": tier,
            "builds_used_today": daily_used + (1 if allowed else 0),
            "builds_remaining_today": max(0, daily_remaining - (1 if allowed else 0)) if daily_limit != -1 else -1,
            "builds_remaining_hour": max(0, hourly_remaining - (1 if allowed else 0)),
            "swarm_cost": {
                "cursors_per_agent": CURSORS_PER_AGENT,
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

    # Lua script for atomic daily check-and-increment (SEC-RATE-001)
    _REDIS_INCR_LUA = """\
local limit = tonumber(ARGV[1])
local expire_at = tonumber(ARGV[2])
local cur = tonumber(redis.call('GET', KEYS[1])) or 0
if cur >= limit then
    return -1
end
local new = redis.call('INCR', KEYS[1])
redis.call('EXPIREAT', KEYS[1], expire_at)
return new
"""

    def _check_daily_redis(self, key: str, daily_limit: int, now: float):
        """Atomically check-and-increment the daily counter in Redis.

        Uses a Lua script so the check and increment are atomic — no race
        condition between the read and the write (SEC-RATE-001).

        Returns (allowed, used, remaining).  On Redis error, returns
        (True, 0, daily_limit) and disables Redis so the in-memory path
        takes over.
        """
        try:
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            next_midnight = (datetime.now(timezone.utc) + timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            redis_key = f"murphy:forge:{key}:{today}"
            result = self._redis_client.eval(
                self._REDIS_INCR_LUA,
                1,                                       # numkeys
                redis_key,                               # KEYS[1]
                str(daily_limit),                        # ARGV[1]
                str(int(next_midnight.timestamp())),      # ARGV[2]
            )
            val = int(result)
            if val == -1:
                # Over limit — Lua confirmed atomically, no decrement needed
                return False, daily_limit, 0
            used = val
            remaining = max(0, daily_limit - used)
            return True, used, remaining
        except Exception as _exc:
            logger.warning("ForgeRateLimiter Redis error (%s) — falling back to memory", _exc)
            self._redis_available = False
            return True, 0, daily_limit

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
            logger.debug("Suppressed exception in forge_rate_limiter")
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
                "cursors_per_agent": CURSORS_PER_AGENT,
            },
        }


# Module-level singleton
_limiter: Optional[ForgeRateLimiter] = None


def get_forge_rate_limiter() -> ForgeRateLimiter:
    global _limiter
    if _limiter is None:
        _limiter = ForgeRateLimiter()
    return _limiter
